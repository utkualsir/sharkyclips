"""Caption layout: which words share a caption, and where its (max two) lines break.

A caption ends at a natural place: a sentence end, a pause, a new speaker. It never
splits what belongs together:
  - names / titles ("Delta Force", "Ahmet Yılmaz": capitalised words in a row),
  - a number and its word ("55 kill", "2 tane"),
  - a word and the particle after it (Turkish "de/da", "mi/mı/mu/mü", "ki"),
  - a small opener and its word ("bir", "çok", "en", "the", "a", "my"...),
  - glossary phrases (Settings > glossary).
Lines inside a caption are balanced (the bottom line may be a little longer).
"""

from __future__ import annotations

import re

from .edit.words import token

NO_SPACE_LANGS = {"zh", "ja"}
SENTENCE_END = tuple(".!?。！？…؟")
SOFT_END = tuple(",，;:")

PARTICLES = {
    "tr": {"de", "da", "mi", "mı", "mu", "mü", "ki", "mısın", "misin", "musun", "müsün", "mıyım", "miyim",
           "değil", "gibi", "kadar", "için", "ile"},
    "en": {"'s", "too", "though"},
    "de": {"nicht", "auch"},
}
OPENERS = {
    "tr": {"bir", "çok", "en", "bu", "şu", "her", "hiç", "daha", "aynı", "ne", "kaç", "o", "biraz", "tam"},
    "en": {"a", "an", "the", "my", "your", "his", "her", "our", "their", "to", "of", "in", "on", "at", "for",
           "with", "this", "that", "very", "so", "no", "not"},
    "de": {"der", "die", "das", "ein", "eine", "einen", "mein", "dein", "zu", "im", "am", "sehr", "kein"},
    "hu": {"a", "az", "egy", "nem", "nagyon"},
    "ru": {"в", "на", "с", "к", "по", "не", "о", "у", "за", "от", "из", "до", "очень"},
}
_NUM = re.compile(r"^\d+([.,:]\d+)?%?$")


def _is_cap(word: str) -> bool:
    w = word.strip("\"'([{«“")
    return bool(w) and w[0].isupper()


def _glossary_pairs(lang: str | None) -> set[tuple[str, str]]:
    """Consecutive word pairs of multi-word glossary entries (kept on one line)."""
    try:
        from . import config

        g = config.get("glossary") or []
    except Exception:  # noqa: BLE001
        return set()
    entries = g if isinstance(g, list) else [*(g.get("all") or []), *(g.get(lang or "") or [])]
    pairs = set()
    for e in entries:
        parts = [token(p, lang) for p in str(e).split()]
        pairs.update(zip(parts, parts[1:]))
    return pairs


def bound(prev: dict, nxt: dict, lang: str | None, glossary: set[tuple[str, str]] | None = None) -> float:
    """How bad a break between prev and nxt is: 0 = fine, 1 = never."""
    a, b = prev["word"].strip(), nxt["word"].strip()
    if a.endswith(SENTENCE_END) or a.endswith(SOFT_END):
        return 0.0
    ta, tb = token(a, lang), token(b, lang)
    if glossary and (ta, tb) in glossary:
        return 1.0
    if tb in PARTICLES.get(lang or "", set()):
        return 0.95
    if ta in OPENERS.get(lang or "", set()):
        return 0.8
    if _NUM.match(ta):
        return 0.75
    if _is_cap(a) and _is_cap(b) and not prev.get("_sentence_start"):
        return 0.85  # a name / title
    return 0.0


def _len(ws: list[dict], joiner: str) -> int:
    return len(joiner.join(w["word"] for w in ws))


def cards(words: list[dict], lang: str | None, max_chars: int, max_lines: int = 2,
          max_words: int = 14, max_gap: float = 0.6) -> list[list[dict]]:
    """Split words into captions (each shown alone on screen)."""
    joiner = "" if lang in NO_SPACE_LANGS else " "
    gl = _glossary_pairs(lang)
    limit = max_chars * max_lines
    out: list[list[dict]] = []
    cur: list[dict] = []
    for i, w in enumerate(words):
        w = dict(w)
        w["_sentence_start"] = i == 0 or words[i - 1]["word"].strip().endswith(SENTENCE_END)
        if cur:
            prev = cur[-1]
            gap = w["start"] - prev["end"]
            text_len = _len(cur + [w], joiner)
            hard = (gap > max_gap or prev["word"].strip().endswith(SENTENCE_END)
                    or (w.get("spk") and prev.get("spk") and w["spk"] != prev["spk"]))
            soft = prev["word"].strip().endswith(SOFT_END) and gap > 0.25 and _len(cur, joiner) > limit * 0.5
            if hard or soft:
                out.append(cur)
                cur = []
            elif text_len > limit or len(cur) >= max_words:
                # Too long: end the caption at the best place among the last few words.
                best_k, best_cost = len(cur), 9.0
                for k in range(len(cur), max(0, len(cur) - 4), -1):
                    if k < 1:
                        break
                    nxt = cur[k] if k < len(cur) else w
                    cost = bound(cur[k - 1], nxt, lang, gl) * 2 + (len(cur) - k) * 0.35
                    if cost < best_cost:
                        best_k, best_cost = k, cost
                out.append(cur[:best_k])
                cur = cur[best_k:]
        cur.append(w)
    if cur:
        out.append(cur)
    for c in out:
        for w in c:
            w.pop("_sentence_start", None)
    return [c for c in out if c]


def split_lines(card: list[dict], lang: str | None, max_chars: int, max_lines: int = 2) -> list[list[dict]]:
    """One or two balanced lines for a caption."""
    joiner = "" if lang in NO_SPACE_LANGS else " "
    if max_lines < 2 or len(card) < 2 or _len(card, joiner) <= max_chars:
        return [card]
    gl = _glossary_pairs(lang)
    best, best_cost = 1, 1e9
    for k in range(1, len(card)):
        l1, l2 = _len(card[:k], joiner), _len(card[k:], joiner)
        over = max(0, l1 - max_chars) + max(0, l2 - max_chars)
        diff = l1 - l2
        cost = over * 4 + abs(diff) * (1.3 if diff > 0 else 1.0) + bound(card[k - 1], card[k], lang, gl) * 25
        if cost < best_cost:
            best, best_cost = k, cost
    return [card[:best], card[best:]]


# Speaker colours (#RRGGBB): me = the style's own colour; friends get these.
SPEAKER_COLORS = {"f1": "#7FD6FF", "f2": "#FF9ED8", "f3": "#B8F27A", "f4": "#FFC46B"}
DEFAULT_NAMES = {
    "en": ("Me", "Friend"), "tr": ("Ben", "Arkadaş"), "de": ("Ich", "Freund"), "hu": ("Én", "Barát"),
    "ru": ("Я", "Друг"), "ar": ("أنا", "صديق"), "zh": ("我", "朋友"),
}


def speaker_label(spk: str, names: dict | None, lang: str | None) -> str:
    custom = (names or {}).get(spk) or ""
    if custom:
        return custom
    me, friend = DEFAULT_NAMES.get(lang or "en", DEFAULT_NAMES["en"])
    if spk == "me":
        return me
    n = spk[1:] if spk.startswith("f") else ""
    return friend if n in ("", "1") else f"{friend} {n}"
