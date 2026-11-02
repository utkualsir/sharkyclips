"""Swear detection with a safety net: every speaker, misheard words, Whisper's own censoring.

detect() returns one item per swear (or "maybe" swear) with the speaker, time and why:
  list      the word list matched (profanity.py, Settings > Studio > Word lists) -> sure
  masked    Whisper wrote it censored itself ("s**yim", "f***") -> sure
  fuzzy     one letter off a list word, said unclearly (low confidence), and not a normal
            word of the language (wordfreq) -> maybe
  phonetic  sounds like a list word (Turkish spelling folded: ı/i, ğ, ş/s, ç/c, k/q...) -> maybe
  pass2     another transcription pass (separated voices / another track) heard a swear here
  acoustic  a re-listen of the vocal stem with the swear words as hints heard one here

"sure" items are bleeped. "maybe" items are bleeped when their score is high enough (two
signals agree, or the re-listen confirmed it); all of them show up in the review list.
"""

from __future__ import annotations

import re
import unicodedata

from . import profanity
from .words import compile_entries, find, fold, token

BLEEP_MAYBE_AT = 0.6

_MASKED = re.compile(r"^[^\W\d_]+\*+[^\W\d_]*$|^\*+[^\W\d_]+$|^[^\W\d_]\*{2,}$", re.UNICODE)

# Extra spellings people write / Whisper hears (always added to the user's list for matching).
VARIANTS = {
    "tr": ["amk", "amq", "aq", "mk", "amınakoy*", "amınako*", "aminako*", "amk*", "siktir*", "sikik*",
           "sikim", "sikerim", "sikeyim", "sikiyim", "sikem", "orosbu*", "orspu*", "yavşak*", "pezeveng*",
           "amcı*"],
    "en": ["fucking", "fuckin", "motherfucker*"],
}


def _phon(t: str) -> str:
    """Turkish-friendly phonetic key: no accents, ı->i, ğ silent, q->k, w->v, doubles collapsed."""
    t = t.replace("ı", "i").replace("ğ", "").replace("q", "k").replace("w", "v").replace("x", "ks")
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))
    t = re.sub(r"[^a-zа-яё؀-ۿ]", "", t)
    return re.sub(r"(.)\1+", r"\1", t)


def _dist(a: str, b: str, limit: int = 2) -> int:
    """Levenshtein distance (stops early above limit)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _common_word(tok: str, lang: str | None) -> bool:
    """A normal word of the language (so "sıkıntı" is never a near-miss of "sik")."""
    if not lang or len(tok) < 3:
        return False
    try:
        from wordfreq import zipf_frequency

        if zipf_frequency(tok, lang) >= 3.0:
            return True
        # spoken Turkish drops the r of -yor ("sıkıyo" = "sıkıyor", to shoot)
        return lang == "tr" and tok.endswith(("yo", "yon", "yom")) and             zipf_frequency(tok[:tok.rindex("yo") + 2] + "r" + tok[tok.rindex("yo") + 2:], lang) >= 2.5
    except Exception:  # noqa: BLE001 - language not in wordfreq
        return False


def _stems(lang: str | None, entries: list[str]) -> list[tuple[str, bool]]:
    """(phonetic stem, is_prefix) of every single-word list entry long enough for fuzzy use."""
    out = []
    for e in entries + VARIANTS.get(lang or "", []):
        e = e.strip()
        if " " in e or "*" in e.rstrip("*"):
            continue
        prefix = e.endswith("*")
        p = _phon(fold(e.rstrip("*"), lang))
        if len(p) >= 4:
            out.append((p, prefix))  # 4-letter stems: same-sound matches only (see _near)
    return out


def _near(tok: str, stems: list[tuple[str, bool]]) -> str | None:
    p = _phon(tok)
    if len(p) < 3:
        return None
    for stem, prefix in stems:
        if prefix:
            head = p[:len(stem)]
            if head == stem or (len(stem) >= 5 and len(head) >= len(stem) - 1 and _dist(head, stem, 1) <= 1):
                return stem
        elif p == stem or (len(stem) >= 5 and _dist(p, stem, 1) <= 1):
            return stem
    return None


def sounds_alike(a: str, b: str, lang: str | None) -> bool:
    """Same first sound and close in the first four ("sıkeyim" ~ "sikeyim", "Sikir" ~ "siktir")."""
    pa, pb = _phon(token(a, lang)), _phon(token(b, lang))
    if not pa or not pb:
        return "*" in a  # Whisper's own censoring: "s**yim"
    return pa[0] == pb[0] and _dist(pa[:4], pb[:4], 2) <= 1


def is_masked(word: str) -> bool:
    w = word.strip().strip(".,!?;:\"'()[]…")
    return "*" in w and bool(_MASKED.match(w))


def detect(words: list[dict], lang: str | None, hints: list[dict] | None = None,
           entries: list[str] | None = None) -> list[dict]:
    """words: [{"start", "end", "word", "probability"?, "spk"?}] (absolute times).
    hints: [{"start", "end", "word", "src": pass2|acoustic, "spk"?, "score"?}].
    Returns [{"i", "start", "end", "word", "spk", "status", "why", "score"}] sorted by time."""
    entries = entries if entries is not None else profanity.word_list(lang)
    items: dict[int, dict] = {}

    def put(i: int, status: str, why: str, score: float) -> None:
        w = words[i]
        old = items.get(i)
        if old and (old["status"] == "sure" or old["score"] >= score):
            return
        items[i] = {"i": i, "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3),
                    "word": w["word"].strip(), "spk": w.get("spk"), "status": status, "why": why,
                    "score": round(score, 2)}

    texts = [w["word"] for w in words]
    full = compile_entries(entries + VARIANTS.get(lang or "", []), lang)
    for a, b, _e in find(texts, full, lang):
        for i in range(a, b + 1):
            put(i, "sure", "list", 1.0)
    stems = _stems(lang, entries)
    for i, w in enumerate(words):
        if i in items:
            continue
        if is_masked(w["word"]):
            put(i, "sure", "masked", 1.0)
            continue
        tok = token(w["word"], lang)
        if len(tok) < 3 or _common_word(tok, lang):
            continue
        p = float(w.get("probability", w.get("p", 1.0)) or 0.0)
        hit = _near(tok, stems)
        if hit is None:
            continue
        exactish = _phon(tok).startswith(hit)
        if exactish:  # same sound, other spelling ("amina", "orosbu", "sıkeyim")
            put(i, "maybe", "phonetic", 0.65 if p < 0.9 else 0.55)
        elif p < 0.75:
            put(i, "maybe", "fuzzy", 0.45 + (0.75 - p) * 0.3)

    out = list(items.values())
    # Other passes: confirm a word here (only one that sounds like the hint), or add a swear
    # the main words don't have at all.
    for h in hints or []:
        hs, he = float(h["start"]), float(h["end"])
        overlap = [it for it in out if it["start"] < he + 0.15 and it["end"] > hs - 0.15
                   and sounds_alike(it["word"], str(h.get("word", "")), lang)]
        if overlap:
            for it in overlap:
                if it["status"] == "maybe":
                    it["score"] = round(min(1.0, it["score"] + (0.35 if h.get("src") == "acoustic" else 0.25)), 2)
                    it["why"] += "+" + str(h.get("src"))
            continue
        if any(it["start"] < he and it["end"] > hs and it["status"] == "sure" for it in out):
            continue  # a sure swear is already there
        under = [i for i, w in enumerate(words) if float(w["start"]) < he and float(w["end"]) > hs
                 and sounds_alike(w["word"], str(h.get("word", "")), lang)]
        score = float(h.get("score") or (0.7 if h.get("src") == "acoustic" else 0.6))
        if under:
            for i in under[:2]:
                put(i, "maybe", str(h.get("src") or "pass2"), score)
            out = list(items.values()) + [it for it in out if it.get("i") is None]
        else:
            out.append({"i": None, "start": round(hs, 3), "end": round(he, 3), "word": str(h.get("word", "")).strip(),
                        "spk": h.get("spk"), "status": "maybe", "why": str(h.get("src") or "pass2"),
                        "score": round(score, 2)})
    out.sort(key=lambda it: it["start"])
    return out


def bleeped(item: dict) -> bool:
    """Bleeped by default (before the user's own choices)?"""
    return item["status"] == "sure" or item["score"] >= BLEEP_MAYBE_AT


def in_ranges(t0: float, t1: float, ranges: list) -> bool:
    mid = (t0 + t1) / 2
    return any(float(a) - 0.05 <= mid <= float(b) + 0.05 for a, b in ranges)
