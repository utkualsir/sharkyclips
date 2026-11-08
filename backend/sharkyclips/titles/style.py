"""My style: the creator's own metadata style (Studio > Brand kit > My style).

Kept in ~/.sharkyclips/style/ (never in the repo; the repo ships a generic sample only):
  profile.json   real titles / descriptions / hashtags / tags that worked for this channel
                 (Shorts and long videos, per game) + liked titles (thumbs up) + settings
  glossary.json  gamer words kept as streamers write them ("kill", "revive", "ulti") and
                 corrections learned from the creator's own edits ("iki katil" -> "double kill")

While a profile is on and the output language is the profile's language, every gaming title,
description, hashtag list and tag list follows it:
  titles        ALL CAPS, "!" or "?!", 2 emojis, often a "(DELTA FORCE OYNANIŞ)" ending, real clip
                details; Shorts open with a real quote from the transcript (swears censored:
                "S*KTİR") with the hook in the first 40 characters; at most 100 characters
  description   Shorts: 2-3 short lines with emojis + a comment question ending with 👇
                long: "... ile karşınızdayım!" opener, one story paragraph, "İyi seyirler!",
                like / subscribe / comment CTA, then the socials block
  hashtags      10-12: game, game TR, names, mood / event, format, channel, #GamingTR
  tags          10-15 natural search phrases (mostly Turkish, a few English) incl. "<name> <game>"
Every output is checked against these rules (check_title / check_short_description / ...) and
written again when it fails. Examples are few-shot context (same game and format first) and are
never copied.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from .. import config
from . import lexicon

STYLE_VERSION = 1
FORMATS = ("short", "long")
SAMPLE_FILE = Path(__file__).resolve().parent / "style_sample.json"
TITLE_LIMIT = 100       # YouTube's limit
SHORT_HOOK = 40         # YouTube shows ~40 characters of a Short's title
MAX_EXAMPLES = 200
MAX_CORRECTIONS = 300
_lock = threading.RLock()

# Gaming words Turkish streamers write in English (never translated).
GAMER_TERMS = ["kill", "revive", "ulti", "gank", "pre", "duo", "tilt", "rage", "outplay", "clutch", "spawn kill",
               "carry", "feed", "flash", "combo", "ace", "pentakill", "quadra kill", "triple kill", "double kill",
               "elo", "supp", "jungle", "lane", "extract", "headshot", "knock", "loot", "rush", "push", "farm",
               "first blood", "baron", "smite", "base", "solo", "squad", "lobi", "meta", "nerf", "buff"]
# Wrong translations the AI or Whisper produce -> what streamers write.
BUILTIN_CORRECTIONS = {
    "iki katil": "double kill", "üç katil": "triple kill", "dört katil": "quadra kill", "beş katil": "pentakill",
    "çift öldürme": "double kill", "üçlü öldürme": "triple kill", "dörtlü öldürme": "quadra kill",
    "beşli öldürme": "pentakill", "revize": "revive", "revize ettim": "revive attım", "revize etti": "revive attı",
    "kurtarırdin": "kurtarırdın", "nihai yetenek": "ulti", "nihai yeteneğini": "ultisini",
    "nihai yetenekle": "ultiyle", "nihai yeteneği": "ultisi", "dubl kill": "double kill", "dubl-kill": "double kill",
    "killing sonrası": "kill sonrası",
    "çıkarma": "extract", "yeniden doğma": "spawn", "doğma noktası": "spawn",
}
# How a name sounds, for the Turkish suffix after the apostrophe ("Delta Force'ta").
BUILTIN_SOUNDS = {"Delta Force": "delta fors", "League of Legends": "lig of lecınds", "Force": "fors",
                  "Valorant": "valorant", "Counter-Strike": "kauntır sitrayk", "Nautilus": "notilus",
                  "Ashe": "eş", "Spider-Man": "spaydırmen", "Spider-Man 2": "spaydırmen tu", "Olaf": "olaf"}

# Hashtag words per game (CamelCase as the creator writes them).
GAME_TAGS = {
    "lol": {"tag": "#LeagueOfLegends", "tr": "#LoLTR", "short": "#LoLShorts", "long": "#LoLGameplay",
            "label": "LoL", "extra": ["#LoLTürkçe"]},
    "delta_force": {"tag": "#DeltaForce", "tr": "#DeltaForceTR", "short": "#FPSMoments", "long": "#DeltaForceGameplay",
                    "label": "Delta Force", "extra": ["#FPS", "#FPSGamer"]},
    "cs2": {"tag": "#CS2", "tr": "#CS2TR", "short": "#CS2Shorts", "long": "#CS2Gameplay", "label": "CS2",
            "extra": ["#FPS"]},
    "valorant": {"tag": "#Valorant", "tr": "#ValorantTR", "short": "#ValorantShorts", "long": "#ValorantGameplay",
                 "label": "Valorant", "extra": ["#FPS"]},
}
MOOD_TAGS = {
    "funny": ["#KomikAnlar", "#KomikOyunAnları"], "fail": ["#Fail", "#KomikAnlar", "#FailMoments"],
    "exciting": ["#EfsaneAnlar", "#Clutch"], "skill": ["#Outplay", "#Clutch"], "emotional": ["#Duygusal"],
    "useful": ["#Rehber"], "informative": ["#Rehber"], "other": ["#EfsaneAnlar"],
}
MOOD_EMOJI = {"funny": "😂💀", "fail": "💀😂", "exciting": "🔥😱", "skill": "🔥😱", "emotional": "😭💔",
              "useful": "🎯🔥", "informative": "🎯🔥", "other": "🔥💀"}
TILT_WORDS = re.compile(r"(?<!\w)(?:tilt|rage|sinir|sinirlen\w*|delir\w*|çıldır\w*|isyan\w*|of+\s+be|yeter\s+ya)(?!\w)", re.I)
MILD_OK = {"lan", "ulan", "len"}  # the creator's own titles use these ("NASIL ÖLDÜM LAN?!")

EMOJI_CLUSTER = re.compile(
    "(?:[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿]️?"
    "(?:‍[\U0001F000-\U0001FAFF☀-➿⬀-⯿]️?)*)")
LABEL_RE = re.compile(r"^\s*\[[^\]]{2,40}\]\s*")
QUOTE_RE = re.compile(r'^\s*"([^"]{2,90})"')
PAREN_RE = re.compile(r"\s*\(([^()]{2,48})\)\s*$")
VS_TOKEN = re.compile(r"(?<!\w)\d+v\d+(?!\w)", re.I)
HASHTAG_RE = re.compile(r"(?<!\w)#[\w]+", re.UNICODE)
DEFAULT_TEMPLATES = {
    "opener_end": "ile karşınızdayım!",
    "sign_off": "İyi seyirler!",
    "cta": "Videoyu beğenmeyi, kanala abone olmayı ve {comment} unutmayın! 🚀",
    "comment_call": "Yorumlara yazın! 👇",
    "hashtag_label": "Hashtag'ler:",
}


# ------------------------------------------------------------------ storage


def folder() -> Path:
    return config.config_dir() / "style"


def profile_path() -> Path:
    return folder() / "profile.json"


def glossary_path() -> Path:
    return folder() / "glossary.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(p: Path) -> dict:
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(p: Path, data: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _text(v, n: int) -> str:
    return " ".join(str(v or "").split())[:n] if "\n" not in str(v or "") else str(v or "").strip()[:n]


def _clean_example(e: dict) -> dict | None:
    if not isinstance(e, dict):
        return None
    title = " ".join(str(e.get("title") or e.get("text") or "").split())[:TITLE_LIMIT + 20]
    if len(title) < 3:
        return None
    fmt = e.get("format") if e.get("format") in FORMATS else "short"
    game = re.sub(r"[^a-z0-9_]", "", str(e.get("game") or "").lower())[:30]
    tags = e.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split(",")
    hashtags = e.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = hashtags.split()
    eid = str(e.get("id") or "") or hashlib.sha1(f"{fmt}|{game}|{title}".encode()).hexdigest()[:10]
    return {"id": eid[:20], "format": fmt, "game": game, "title": title,
            "description": str(e.get("description") or "").strip()[:4000],
            "hashtags": [("#" + h.strip().lstrip("#")) for h in hashtags if str(h).strip("# ")][:20],
            "tags": [" ".join(str(t).split())[:80] for t in tags if str(t).strip()][:25],
            "source": str(e.get("source") or "manual")[:12], "views": int(e.get("views") or 0) or None,
            "added_at": str(e.get("added_at") or _now())[:30]}


def _clean_profile(d: dict) -> dict:
    d = d if isinstance(d, dict) else {}
    ex: list[dict] = []
    for e in d.get("examples") or []:
        c = _clean_example(e)
        if c and c["id"] not in {x["id"] for x in ex}:
            ex.append(c)
    tpl = {k: _text((d.get("templates") or {}).get(k) or v, 200) for k, v in DEFAULT_TEMPLATES.items()}
    if "{comment}" not in tpl["cta"]:
        tpl["cta"] = DEFAULT_TEMPLATES["cta"]
    tag = re.sub(r"[^\w]", "", str(d.get("channel_tag") or "").replace("#", ""), flags=re.UNICODE)[:40]
    return {"version": STYLE_VERSION, "enabled": bool(d.get("enabled", True)) and bool(ex),
            "lang": str(d.get("lang") or "tr")[:5], "name": " ".join(str(d.get("name") or "").split())[:60],
            "channel_tag": f"#{tag}" if tag else "", "shorts_socials": bool(d.get("shorts_socials", False)),
            "learn_likes": d.get("learn_likes") is not False, "templates": tpl, "examples": ex[-MAX_EXAMPLES:]}


def exists() -> bool:
    return profile_path().is_file()


def load() -> dict:
    with _lock:
        return _clean_profile(_read(profile_path())) if exists() else _clean_profile({"enabled": False})


def save(data: dict) -> dict:
    with _lock:
        cur = _read(profile_path())
        merged = {**cur, **{k: v for k, v in (data or {}).items() if k in (
            "enabled", "lang", "name", "channel_tag", "shorts_socials", "learn_likes", "templates", "examples")}}
        if "enabled" not in (data or {}) and cur.get("enabled") is not None:
            merged["enabled"] = cur["enabled"]
        out = _clean_profile(merged)
        _write(profile_path(), out)
        _digest_cache.clear()
        return out


def sample() -> dict:
    return _clean_profile(json.loads(SAMPLE_FILE.read_text(encoding="utf-8")))


def load_sample() -> dict:
    """Start a profile from the generic sample (the editor's "Start from the sample")."""
    s = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    return save({**s, "enabled": True})


def active(lang: str | None) -> dict | None:
    """The profile when it applies to this output language."""
    p = load()
    if not p["enabled"] or not p["examples"] or (lang and lang != p["lang"]):
        return None
    return p


def socials_for_short() -> bool:
    p = load()
    return not p["enabled"] or p["shorts_socials"]


_digest_cache: dict = {}


def digest(lang: str, gid: str | None, fmt: str) -> str:
    """Part of the metadata cache keys: changes when the profile or the glossary changes."""
    p = active(lang)
    if p is None:
        return "-"
    payload = [STYLE_VERSION, gid, fmt, [(e["id"], e["title"]) for e in p["examples"]], p["templates"],
               p["channel_tag"], p["name"], sorted(glossary()["corrections"].items())]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:10]


def examples_for(p: dict, gid: str | None, fmt: str, n: int = 6) -> list[dict]:
    """Same game + same format first, then the same game's other format, then the same format
    from other games (shown as structure only)."""
    ex = list(reversed(p["examples"]))  # newest first
    out = [e for e in ex if e["game"] == (gid or "") and e["format"] == fmt]
    out += [e for e in ex if e["game"] == (gid or "") and e["format"] != fmt]
    if len([e for e in out if e["format"] == fmt]) < 3:
        out += [e for e in ex if e["game"] != (gid or "") and e["format"] == fmt]
    seen, res = set(), []
    for e in out:
        if e["id"] not in seen:
            seen.add(e["id"])
            res.append(e)
    return res[:n]


def on_vote(text: str, lang: str, value: int, gid: str | None, fmt: str = "short") -> None:
    """A liked title joins the profile's examples (removed again when the like is taken back)."""
    p = load()
    if not exists() or lang != p["lang"] or not p["learn_likes"]:
        return
    text = " ".join(text.split())
    ex = [e for e in p["examples"] if not (e["source"] == "liked" and e["title"] == text)]
    if value > 0:
        ex.append({"format": fmt, "game": gid or "", "title": text, "source": "liked"})
    if len(ex) != len(p["examples"]) or value > 0:
        save({"examples": ex})


# ------------------------------------------------------------------ glossary


def glossary() -> dict:
    d = _read(glossary_path())
    keep = [" ".join(str(t).split())[:40] for t in d.get("keep") or GAMER_TERMS if str(t).strip()]
    corr = {}
    for k, v in (d.get("corrections") or {}).items():
        k, v = lexicon.lower(" ".join(str(k).split()), "tr")[:60], " ".join(str(v).split())[:60]
        if k and v and k != lexicon.lower(v, "tr"):
            corr[k] = v
    sounds = {str(k)[:40]: str(v)[:40] for k, v in (d.get("sounds") or {}).items() if str(k).strip() and str(v).strip()}
    return {"keep": list(dict.fromkeys(keep)), "corrections": corr, "sounds": sounds,
            "learned": list(d.get("learned") or [])[-MAX_CORRECTIONS:]}


def save_glossary(data: dict) -> dict:
    with _lock:
        cur = _read(glossary_path())
        merged = {**cur, **{k: v for k, v in (data or {}).items() if k in ("keep", "corrections", "sounds")}}
        _write(glossary_path(), {**glossary_shape(merged)})
        _digest_cache.clear()
        return glossary()


def glossary_shape(d: dict) -> dict:
    return {"version": 1, "keep": d.get("keep") or GAMER_TERMS, "corrections": d.get("corrections") or {},
            "sounds": d.get("sounds") or {}, "learned": d.get("learned") or []}


def all_corrections() -> dict[str, str]:
    return {**BUILTIN_CORRECTIONS, **glossary()["corrections"]}


def keep_terms() -> list[str]:
    return glossary()["keep"]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)?|[^\w\s]", text or "")


def learn_from_edit(before: str, after: str, lang: str) -> list[tuple[str, str]]:
    """The creator corrected an AI text: every changed word (or 2-3 word phrase) is remembered
    and fixed in future metadata. Returns the new corrections."""
    p = load()
    if not exists() or lang != p["lang"]:
        return []
    a, b = _tokens(lexicon.strip_emoji(before)), _tokens(lexicon.strip_emoji(after))
    if not a or not b or SequenceMatcher(None, a, b).ratio() < 0.4:
        return []  # a different text, not a correction
    found: list[tuple[str, str]] = []
    for op, i1, i2, j1, j2 in SequenceMatcher(None, [x.casefold() for x in a], [x.casefold() for x in b]).get_opcodes():
        if op != "replace" or i2 - i1 > 3 or j2 - j1 > 3:
            continue
        old = " ".join(a[i1:i2])
        new = " ".join(b[j1:j2])
        if not re.search(r"[^\W\d_]{2}", old) or not re.search(r"[^\W\d_]{2}", new):
            continue
        if lexicon.lower(old, lang) == lexicon.lower(new, lang):
            continue  # only the case changed (the app writes titles in CAPITALS anyway)
        lo, ln = lexicon.lower(old, lang), lexicon.lower(new, lang)
        gaming = ln in {k.lower() for k in keep_terms()} or all(w.isascii() for w in ln.split())
        spelling = SequenceMatcher(None, lo, ln).ratio() >= 0.75
        unknown = any(lexicon.zipf(w, lang) == 0 for w in lo.split())
        if not (gaming or spelling or unknown):
            continue  # a style choice ("çok" -> "aşırı"), not a correction
        found.append((lexicon.lower(old, lang), lexicon.lower(new, lang) if not new.isupper() else new.lower()))
    if not found:
        return []
    with _lock:
        d = _read(glossary_path())
        g = glossary_shape(d)
        corr = dict(g["corrections"])
        learned = list(g["learned"])
        for old, new in found:
            corr[old] = new
            learned.append({"from": old, "to": new, "at": _now()})
            if " " not in new and new not in g["keep"] and lexicon.zipf(new, lang) < 2.5:
                g["keep"] = list(g["keep"]) + [new]  # a gaming word the dictionary doesn't know
        _write(glossary_path(), {**g, "corrections": dict(list(corr.items())[-MAX_CORRECTIONS:]),
                                 "learned": learned[-MAX_CORRECTIONS:]})
        _digest_cache.clear()
    return found


# ------------------------------------------------------------------ Turkish fixes

TR_VOWELS = "aeıioöuü"
TR_HIGH = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}
TR_LOW = {"a": "a", "ı": "a", "o": "a", "u": "a", "e": "e", "i": "e", "ö": "e", "ü": "e"}
VOICELESS = set("çfhkpsştcxq")  # c / x / q: English names ("Force" ~ fors)
# Personal / past endings whose vowel must follow the word's last vowel ("kurtarırdin" -> "...dın").
TR_ENDING = re.compile(r"(?P<stem>[^\W\d_]*[aeıioöuü][^\W\d_]*?[dt])(?P<v>[ıiuü])(?P<end>m|n|k|n[ıiuü]z|)$")


def fix_tr_harmony(text: str) -> tuple[str, list[tuple[str, str]]]:
    """'kurtarırdin' -> 'kurtarırdın', 'geldın' -> 'geldin': only words the dictionary doesn't
    know as written and that end in a past / personal ending."""
    fixes = []

    def sub(m: re.Match) -> str:
        w = m.group(0)
        low = lexicon.lower(w, "tr")
        if "'" in w or "’" in w or len(low) < 4 or lexicon.zipf(low, "tr") > 0:
            return w
        e = TR_ENDING.search(low)
        if not e:
            return w
        prev = [ch for ch in e.group("stem") if ch in TR_VOWELS]
        if not prev:
            return w
        want = TR_HIGH[prev[-1]]
        if want == e.group("v"):
            return w
        end = e.group("end")
        if len(end) == 3:
            end = "n" + want + "z"
        fixed = low[:e.start("v")] + want + end
        if lexicon.zipf(fixed, "tr") == 0 and lexicon.known_score(fixed, "tr") < lexicon.known_score(low, "tr"):
            return w
        out = "".join(lexicon.upper_char(c, "tr") if o.isupper() else c for c, o in zip(fixed, w + w[-1] * 5))
        fixes.append((w, out))
        return out

    return re.sub(r"[^\W\d_]+(?:['’][^\W\d_]+)?", sub, text), fixes


def _sound_of(name: str, sounds: dict[str, str]) -> str:
    for k, v in sounds.items():
        if k.casefold() == name.casefold():
            return v
    last = name.split()[-1]
    for k, v in sounds.items():
        if k.casefold() == last.casefold():
            return v
    w = lexicon.lower(last, "tr")
    if re.search(r"[a-z][^aeıioöuü]e$", w) and w.isascii():  # English silent e: "Force" ~ "fors"
        w = w[:-1]
    return w


SUFFIX_RE = re.compile(r"(?P<name>(?:[A-ZÇĞİÖŞÜ0-9][\w.-]*\s){0,3}[A-ZÇĞİÖŞÜ0-9][\w.-]*)['’](?P<suf>[dtDT][aeAE][nN]?|[dtDT][aeAE][kK][iİ])(?![\w])")


def fix_tr_suffixes(text: str, sounds: dict[str, str] | None = None) -> tuple[str, list[tuple[str, str]]]:
    """Locative / ablative after a name follow its sound: "Delta Force'da" -> "Delta Force'ta",
    "Yasuo'de" -> "Yasuo'da"."""
    sounds = {**BUILTIN_SOUNDS, **(sounds if sounds is not None else glossary()["sounds"])}
    fixes = []

    def sub(m: re.Match) -> str:
        name, suf = m.group("name"), m.group("suf")
        caps = suf.isupper()
        s = lexicon.lower(suf, "tr")
        snd = _sound_of(name, sounds)
        vowels = [ch for ch in snd if ch in TR_VOWELS]
        if not vowels or not snd[-1:].isalpha():
            return m.group(0)
        v = TR_LOW[vowels[-1]]
        c = "t" if snd[-1] in VOICELESS else "d"
        new = c + v + s[2:]
        if new == s:
            return m.group(0)
        if caps:
            new = "".join(lexicon.upper_char(ch, "tr") for ch in new)
        out = f"{name}'{new}"
        fixes.append((m.group(0), out))
        return out

    return SUFFIX_RE.sub(sub, text), fixes


def apply_corrections(text: str, corrections: dict[str, str] | None = None) -> tuple[str, list[tuple[str, str]]]:
    """Glossary corrections, case kept ("İKİ KATİL" -> "DOUBLE KILL"); also "3 katil" -> "3 kill".
    Matched on a Turkish-lowercased copy (re.I misses İ / I)."""
    corr = corrections if corrections is not None else all_corrections()
    fixes = []
    for wrong in sorted(corr, key=len, reverse=True):
        right = corr[wrong]
        pat = r"\s+".join(re.escape(x) for x in lexicon.lower(wrong, "tr").split())
        rx = re.compile(rf"(?<![\w]){pat}(?![\w])")
        low = lexicon.lower(text, "tr")
        if len(low) != len(text):
            continue
        spans = list(rx.finditer(low))
        for m in reversed(spans):
            got = text[m.start():m.end()]
            out = upper(right, "tr") if got.isupper() and len(got) > 1 else (
                right[:1].upper() + right[1:] if got[:1].isupper() and not right[:1].isupper() else right)
            fixes.append((got, out))
            text = text[:m.start()] + out + text[m.end():]
    text2 = re.sub(r"(?<!\w)(\d+)\s+(katil|KATİL|Katil)(?!\w)",
                   lambda m: f"{m.group(1)} {'KILL' if m.group(2).isupper() else 'kill'}", text)
    if text2 != text:
        fixes.append(("katil", "kill"))
    return text2, fixes


def proofread_tr(text: str, sounds: dict[str, str] | None = None) -> tuple[str, list[tuple[str, str]]]:
    """All deterministic Turkish fixes for metadata text: glossary, vowel harmony, name suffixes,
    question particle, diacritics."""
    fixes: list[tuple[str, str]] = []
    out, f = apply_corrections(text)
    fixes += f
    out, f = fix_tr_harmony(out)
    fixes += f
    out, f = fix_tr_suffixes(out, sounds)
    fixes += f
    out, f = lexicon.fix_tr_question_particle(out)
    fixes += f
    return out, fixes


# ------------------------------------------------------------------ titles: local fixes


def ascii_words() -> set[str]:
    """English gaming words written with a plain I in capitals ("KILL", not "KİLL")."""
    return {w for t in keep_terms() + list(BUILTIN_CORRECTIONS.values()) for w in t.lower().split() if w.isascii()}


def upper(text: str, lang: str, ascii_ok: set[str] | None = None, names: set[str] | None = None) -> str:
    """ALL CAPS the Turkish way (i -> İ, ı -> I); "1v9" keeps its small v; English gaming words
    ("kill", "revive") use the English capital I."""
    keep = {m.start(): m.group(0) for m in VS_TOKEN.finditer(text)}
    words = ascii_words() if ascii_ok is None else ascii_ok
    for m in re.finditer(r"[^\W\d_]+", text):
        w = m.group(0)
        lw = w.lower() if w.isascii() else lexicon.lower(w, lang)  # "REVİVE" from the model -> "revive"
        if lw.isascii() and lw in words and m.start() not in keep:
            keep[m.start()] = lw.upper()
        elif names and w.isascii() and w.lower() in names and m.start() not in keep:
            keep[m.start()] = "".join(lexicon.upper_char(ch, lang) for ch in w.lower())  # DARIUS -> DARİUS
    out, i = [], 0
    while i < len(text):
        if i in keep:
            out.append(keep[i])
            i += len(keep[i])
            continue
        out.append(lexicon.upper_char(text[i], lang))
        i += 1
    return "".join(out)


def lower_title(text: str, lang: str) -> str:
    """Lowercase a CAPS title: English gaming words with a plain i ("KILL" -> "kill", not "kıll")."""
    words = ascii_words()

    def sub(m: re.Match) -> str:
        w = m.group(0)
        if w.isascii() and w.lower() in words:
            return w.lower()
        tr = lexicon.lower(w, lang)
        if w.isascii() and lexicon.zipf(tr, lang) == 0 and lexicon.zipf(w.lower(), "en") >= 3:
            return w.lower()  # an English word in capitals ("FULL CLIP"), not Turkish "clıp"
        return tr

    return re.sub(r"[^\W\d_]+", sub, text)


def emojis(text: str) -> list[str]:
    return EMOJI_CLUSTER.findall(text or "")


def strip_emojis(text: str) -> str:
    return re.sub(r"\s{2,}", " ", EMOJI_CLUSTER.sub(" ", text or "")).strip()


def censor_word(w: str) -> str:
    """'SİKTİR' -> 'S*KTİR', 'BOK' -> 'B*K': first letter kept, the first vowel starred (short
    words: everything inside)."""
    letters = list(w)
    if len(letters) <= 4:
        return letters[0] + "*" * max(1, len(letters) - 2) + (letters[-1] if len(letters) > 1 else "")
    for i in range(1, len(letters) - 1):
        if lexicon.lower(letters[i], "tr") in TR_VOWELS + "e":
            letters[i] = "*"
            return "".join(letters)
    letters[1] = "*"
    return "".join(letters)


def is_swear(word: str, lang: str) -> bool:
    from ..analyze import has_profanity
    from ..edit import swearlex

    w = re.sub(r"['’].*$", "", word)
    if not w or "*" in w or lexicon.lower(w, lang) in MILD_OK:
        return False
    if lang == "tr" and lexicon.lower(w, lang).startswith(("şikay", "şikây")):
        return False
    hit = swearlex.classify(w, lang)
    return bool((hit and hit[0] == "sure") or has_profanity(w) or lexicon.lower(w, lang) in ("bok", "boktan"))


def censor(text: str, lang: str) -> tuple[str, int]:
    n = 0

    def sub(m: re.Match) -> str:
        nonlocal n
        w = m.group(0)
        base = re.split(r"['’]", w)[0]
        if is_swear(base, lang):
            n += 1
            return censor_word(base) + w[len(base):]
        return w

    return re.sub(r"[^\W\d_]+(?:['’][^\W\d_]+)?", sub, text), n


def _norm_quotes(text: str) -> str:
    return re.sub(r"[“”„«»]", '"', text or "").replace("''", '"')


def split_title(text: str) -> tuple[str, str, list[str]]:
    """(main part, parenthetical without brackets, emojis)."""
    em = emojis(text)
    body = strip_emojis(_norm_quotes(text))
    body = HASHTAG_RE.sub("", body).strip()
    body = LABEL_RE.sub("", body)  # "[LONG VİDEO] ..." echoed from the prompt's example labels
    paren = ""
    m = PAREN_RE.search(body)
    if m and m.start() > 8:
        paren, body = m.group(1).strip(), body[:m.start()].rstrip()
    return body.strip(" -|"), paren, em


APOS_TERMS = ("kill", "revive", "clutch", "headshot", "outplay", "pentakill", "ace", "spawn", "carry")
APOS_RE = re.compile(r"(?<![\w'])(" + "|".join(APOS_TERMS) + r")(l[ae]|[ıiuü]|[ae]|[dt][ae]|[dt][ae]n|l[ae]r[ıi]?|[ıi]n)(?![\w'])", re.I)


def fix_apostrophes(text: str) -> str:
    """English gaming words take Turkish suffixes after an apostrophe: "killle" -> "kill'le"."""
    return APOS_RE.sub(lambda m: f"{m.group(1)}'{m.group(2)}", text)


def fix_title(text: str, lang: str, moment: str | None = None, sounds: dict[str, str] | None = None,
              ascii_ok: set[str] | None = None, names: set[str] | None = None) -> str:
    """Local fixes: gaming terms kept, Turkish spelling, censored swears, ALL CAPS, strong
    punctuation, exactly 2 emojis (before the parenthetical), at most 100 characters."""
    body, paren, em = split_title(text)
    if lang == "tr":
        body = fix_apostrophes(body)
        body, _f = proofread_tr(body, sounds)
        paren, _f = proofread_tr(paren, sounds)
    body = re.sub(r"\s+([?!.,…])", r"\1", body)
    body = re.sub(r"!{2,}", "!", body).replace("?!?", "?!").replace("!?", "?!")
    body = re.sub(r"\?{2,}", "?", body)
    body, _n = censor(body, lang)
    paren, _n = censor(paren, lang)
    if lang not in ("ar", "zh", "ja"):
        body, paren = upper(body, lang, ascii_ok, names), upper(paren, lang, ascii_ok, names)
    if lang == "tr":
        body, _f = fix_tr_suffixes(body, sounds)
        paren, _f = fix_tr_suffixes(paren, sounds)
    body = body.rstrip(" ,;:")
    body = re.sub(r'\?"$', '?!"', body)
    if body.endswith("."):
        body = body.rstrip(".") + "!" if not body.endswith("...") else body
    if body.endswith("?"):
        body += "!"  # "?!"
    if not re.search(r"[!?]|\.\.\.|…", body):
        body += "!"
    want = [e for e in dict.fromkeys(em)][:2]
    for ch in MOOD_EMOJI.get(moment or "", MOOD_EMOJI["other"]) + "🔥💀":
        if len(want) >= 2:
            break
        if ch not in want:
            want.append(ch)
    tail = "".join(want)
    out = f"{body} {tail}" + (f" ({paren})" if paren else "")
    if len(out) > TITLE_LIMIT and paren:
        out = f"{body} {tail}"
    if len(out) > TITLE_LIMIT:
        cut = body[:TITLE_LIMIT - len(tail) - 2].rsplit(" ", 1)[0].rstrip(" ,")
        out = f"{cut}! {tail}" if not cut.endswith(("!", "?", "...")) else f"{cut} {tail}"
    return out


# ------------------------------------------------------------------ titles: checks


def _fold(text: str) -> str:
    t = lexicon.lower(_norm_quotes(text), "tr")
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))
    return t.replace("ı", "i")


def _words(text: str) -> list[str]:
    return re.findall(r"[\w*]+", _fold(text))


def _same_word(a: str, b: str) -> bool:
    if "*" in a:  # censored: "s*ktir" matches "siktir"
        return len(a) == len(b) and all(x == "*" or x == y for x, y in zip(a, b))
    if a == b:
        return True
    if min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)) and abs(len(a) - len(b)) <= 3:
        return True  # a suffix more or less ("öldüm" / "öldümm")
    return len(a) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.8


def quote_of(title: str) -> str | None:
    m = QUOTE_RE.match(_norm_quotes(title))
    return m.group(1).strip() if m else None


def quote_in_transcript(quote: str, clip_text: str) -> bool:
    """The quote's words appear in this order in the clip's words (Whisper spelling and a
    missing / extra word allowed)."""
    q = [w for w in _words(quote) if w]
    t = _words(clip_text)
    if len(q) < 2 or not t:
        return False
    need = max(2, int(round(len(q) * 0.75)))
    for s in range(len(t)):
        if not _same_word(q[0], t[s]) and not (len(q) > 1 and _same_word(q[1], t[s])):
            continue
        hit, j = 0, s
        for w in q:
            for k in range(j, min(len(t), j + 3)):
                if _same_word(w, t[k]):
                    hit += 1
                    j = k + 1
                    break
        if hit >= need:
            return True
    return False


def hook_end(title: str) -> int:
    """Where the hook ends: the closing quote, or the first "!", "?" or "..."."""
    body = strip_emojis(_norm_quotes(title))
    ends = [i + 1 for i, ch in enumerate(body) if ch in "!?…"]
    if body.lstrip().startswith('"'):
        j = body.find('"', body.find('"') + 1)
        if j > 0:
            ends.append(j + 1)
    k = body.find("...")
    if k > 0:
        ends.append(k + 3)
    return min(ends) if ends else len(body)


def check_title(title: str, *, lang: str, fmt: str, clip_text: str, forbidden=None,
                example_titles: list[str] | None = None, used: list[str] | None = None,
                too_similar=None) -> list[str]:
    """Rule problems of one finished title ([] = fine)."""
    errs = []
    body, paren, em = split_title(title)
    letters = [ch for ch in body + paren if ch.isalpha()]
    if lang not in ("ar", "zh", "ja") and letters and not all(ch.isupper() for ch in letters if ch.lower() != "v"):
        errs.append("write the whole title in CAPITALS")
    if len(em) != 2:
        errs.append("use exactly 2 fitting emojis")
    if not re.search(r"[!?]|\.\.\.|…", body):
        errs.append('end the hook with "!" or "?!"')
    if len(title) > TITLE_LIMIT:
        errs.append(f"at most {TITLE_LIMIT} characters")
    if HASHTAG_RE.search(title):
        errs.append("no hashtags in the title")
    bad = [w for w in re.findall(r"[^\W\d_]+", body + " " + paren) if is_swear(w, lang)]
    if bad:
        errs.append(f"censor swears like S*KTİR, never write them out: {bad[:2]}")
    if forbidden and (g := forbidden(title)):
        errs.append(f"never name {g}" if g != "a clip time" else "never write the clip times (+7s)")
    q = quote_of(title)
    if q and not quote_in_transcript(q, clip_text):
        errs.append(f'the quote "{q}" must be words really said in the CLIP lines')
    if fmt == "short" and hook_end(title) > SHORT_HOOK + 5:
        errs.append(f"Shorts: put the hook first, it must end within the first {SHORT_HOOK} characters")
    if too_similar:
        # compared without the (BRACKET) and emojis: "(DELTA FORCE)" on every title is no repeat
        main = body
        if any(too_similar(main, split_title(e)[0], phrases=False) for e in example_titles or []):
            errs.append("copies an example title; write a new one about THIS clip")
        elif any(too_similar(main, split_title(u)[0]) for u in used or []):
            errs.append("repeats another clip's title")
    return errs


def check_short_description(text: str, *, lang: str, forbidden=None) -> list[str]:
    errs = []
    paras = [p for p in text.split("\n\n") if p.strip()]
    if not 2 <= len(paras) <= 4:
        errs.append("2-3 short lines and a comment question")
    if len(emojis(text)) < 2:
        errs.append("use a few fitting emojis in the lines")
    if not text.rstrip().endswith("👇"):
        errs.append("end with the comment question and 👇")
    if "?" not in (paras[-1] if paras else ""):
        errs.append("the last line asks the viewers a question")
    errs += _common_desc_problems(text, lang, forbidden)
    return errs


def check_long_description(text: str, p: dict, *, lang: str, forbidden=None) -> list[str]:
    tpl = p["templates"]
    errs = []
    paras = [x for x in text.split("\n\n") if x.strip()]
    if not paras or not paras[0].rstrip().endswith(tpl["opener_end"].split()[-1]):  # "... maçla karşınızdayım!"
        errs.append(f'the opener ends with "{tpl["opener_end"]}"')
    if tpl["sign_off"] not in text:
        errs.append(f'the story paragraph ends with "{tpl["sign_off"]}"')
    if len(paras) < 3:
        errs.append("opener, one story paragraph, then the like / subscribe / comment line")
    errs += _common_desc_problems(text, lang, forbidden)
    return errs


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?…])\s+|\n+", strip_emojis(text or "")) if len(x.strip()) > 20]


def copied_sentences(text: str, p: dict) -> list[str]:
    """Sentences that (almost) repeat one of the creator's example descriptions. The fixed parts
    of the templates (the CTA line, "İyi seyirler!", "... karşınızdayım!") don't count."""
    tpl = p["templates"]
    pre, _, post = tpl["cta"].partition("{comment}")
    fixed = [_fold(x) for x in (tpl["sign_off"], tpl["opener_end"].split()[-1] if tpl["opener_end"] else "",
                                tpl["comment_call"]) if x]

    def core(sent: str) -> str | None:
        f = _fold(sent)
        if pre and f.startswith(_fold(pre)[:20]):
            return None  # the like / subscribe / comment line
        for x in fixed:
            f = f.replace(x, " ")
        f = " ".join(f.split())
        return f if len(f) >= 25 else None

    ex = [c for e in p["examples"] for s in _sentences(_desc_body_of(e)) if (c := core(s))]
    out = []
    for s in _sentences(text):
        c = core(s)
        if c and any(SequenceMatcher(None, c, x).ratio() >= 0.75 for x in ex):
            out.append(s)
    return out


def _common_desc_problems(text: str, lang: str, forbidden=None) -> list[str]:
    from ..analyze import has_profanity, has_timestamp

    errs = []
    if has_profanity(text) or any(is_swear(w, lang) for w in re.findall(r"[^\W\d_]+", text)):
        errs.append("no swearing in the description")
    if forbidden and (g := forbidden(text)) and g != "a clip time":
        errs.append(f"never mention {g}: this clip is not from that game")
    if has_timestamp(text):
        errs.append('never mention the clip times like "+7s"')
    if HASHTAG_RE.search(text) or "http" in text:
        errs.append("no hashtags or links (they are added later)")
    return errs


# ------------------------------------------------------------------ prompts


def _quotable(clip_text: str, lang: str, allowed: set[str] | frozenset[str] = frozenset()) -> list[str]:
    """Short spoken lines a Shorts title can quote (exclamations and questions first). Lines with
    words the dictionary doesn't know (Whisper mishearing) are left out."""
    parts = re.split(r"(?<=[.!?…])\s+|\n", clip_text or "")
    out = []
    for s in parts:
        s = s.strip(" -\"'")
        n = len(s.split())
        if not (2 <= n <= 7 and re.search(r"[^\W\d_]{3}", s)):
            continue
        if lexicon.available() and lexicon.unknown_words(re.sub(r"\S*\*\S*", " ", s), lang, allowed | MILD_OK):
            continue
        out.append(s)
    out.sort(key=lambda s: (0 if s.endswith(("!", "?")) else 1, abs(len(s.split()) - 4)))
    return list(dict.fromkeys(out))[:8]


def _ex_line(e: dict, game_name: str | None) -> str:
    fmt = "Shorts" if e["format"] == "short" else "long video"
    return f"{e['title']}   <- {fmt}{', ' + game_name if game_name else ''}"


def examples_block(p: dict, gid: str | None, fmt: str, game_names: dict[str, str], liked: list[str]) -> str:
    ex = examples_for(p, gid, fmt, n=8)
    own = [e for e in ex if e["game"] == (gid or "")]
    other = [e for e in ex if e["game"] != (gid or "")]
    lines = ["THIS creator's own titles that got views (match this style EXACTLY: CAPITALS, \"!\" / \"?!\", 2 emojis, "
             "the (PARENTHESIS) ending; never copy their content):"]
    lines += [f"- {_ex_line(e, game_names.get(e['game']))}" for e in own]
    if other:
        lines += ["Same format, other games (copy ONLY the structure, never their names or events):"]
        lines += [f"- {_ex_line(e, None)}" for e in other]
    if liked:
        lines += ["Titles the creator liked (👍), same style:"] + [f"- {t}" for t in liked[:6]]
    return "\n".join(lines)


def title_task(p: dict, *, fmt: str, gid: str | None, game_name: str, what_happens: str, facts: str,
               clip_text: str, lang_label: str, n: int, game_names: dict[str, str], liked: list[str],
               used: list[str], problems: list[str], terms: list[str], moment: str | None,
               allowed: set[str] | frozenset[str] = frozenset()) -> str:
    parens = [split_title(e["title"])[1] for e in examples_for(p, gid, fmt, n=12) if e["game"] == (gid or "")]
    parens = [x for x in dict.fromkeys(parens) if x][:5]
    quotes = _quotable(clip_text, p["lang"], allowed) if fmt == "short" else []
    parts = [
        "TASK: write YouTube " + ("Shorts" if fmt == "short" else "long video") + f" titles for THIS clip in {lang_label}.",
        f"What happens: {what_happens}",
        f"Game: {game_name or 'unknown (never name a game)'}",
    ]
    if facts:
        parts.append(f"Clip facts (reliable, use them: names, scores like 55 KILL, 1v9, events): {facts}")
    parts += ["", examples_block(p, gid, fmt, game_names, liked), ""]
    parts += [f"Write {n} different titles, strongest first. Label each with its kind."]
    if fmt == "short":
        parts += [
            'Kinds: quote = opens with a REAL line from the CLIP in double quotes ("NASIL ÖLDÜM LAN?!" style) + what it is about; '
            'situation = a relatable fail / situation line ("X DEDİKTEN 1 SANİYE SONRA..."); fact = numbers / names from the facts; '
            "question = a question to the viewer.",
            "- at least half are quote titles when the CLIP has a quotable line",
            f"- the hook (quote or first phrase) comes FIRST and ends within {SHORT_HOOK} characters (YouTube shows ~40 on Shorts)",
        ]
        if quotes:
            parts += ["Lines from the CLIP you can quote (word for word as said, spelling may be fixed):"]
            parts += [f'- "{q}"' for q in quotes]
    else:
        parts += ["Kinds: fact = the match in numbers / names (55 KILL & 44 REVIVE, 1v9, champion / operator names); "
                  "story = what happened, two strong sentences; rage = the mood (tilt, rage, chaos); question."]
    parts += [
        "Rules:",
        "- write in normal case; the app turns everything into CAPITALS",
        '- one or two strong sentences ending with "!" or "?!" (or "..." for a cliffhanger)',
        "- exactly 2 fitting emojis right after the main part (like 😂💀, 🔥😱, 🚨💀)",
        "- often a short context in brackets at the end"
        + (f", like the creator's: {', '.join('(' + x + ')' for x in parens)}" if parens else " like (FULL RAGE)"),
        f"- use real clip details (names, numbers, events); at most {TITLE_LIMIT} characters",
        "- swears are always censored with * (S*KTİR, B*K), never written out; at most ONE title may contain one "
        "(prefer quotes without swears)",
        f"- gaming terms stay as Turkish streamers write them, never translated: {', '.join(keep_terms()[:24])}",
        "- Turkish: correct spelling and vowel harmony (kurtarırdın, Delta Force'ta), apostrophe before suffixes on names",
        f"- only about {game_name}: never name another game" if game_name else "- never name or guess a game",
        "- never name a map, weapon, character or person that is not in the facts or the CLIP lines",
        "- no hashtags",
    ]
    corr = list(all_corrections().items())[:20]
    if corr:
        parts.append("- never write these, write the right form: " + "; ".join(f"{a} -> {b}" for a, b in corr))
    if terms:
        parts.append("Names: spell exactly like this: " + ", ".join(terms[:30]))
    if used:
        parts += ["Do NOT repeat these (other clips / earlier ideas):"] + [f"- {u}" for u in used[-20:]]
    if problems:
        parts += ["", "Problems with your earlier titles, fix them:"] + [f"- {x}" for x in problems[:10]]
    return "\n".join(parts)


TITLE_KINDS = ["quote", "situation", "fact", "story", "rage", "question"]


def title_schema(n: int) -> dict:
    return {"type": "object", "properties": {"titles": {
        "type": "array", "minItems": max(3, n - 3), "maxItems": n + 2, "items": {
            "type": "object", "properties": {"kind": {"type": "string", "enum": TITLE_KINDS},
                                             "text": {"type": "string", "minLength": 5, "maxLength": 130}},
            "required": ["kind", "text"]}}}, "required": ["titles"]}


PROOF_SCHEMA = {"type": "object", "properties": {"titles": {"type": "array", "items": {
    "type": "object", "properties": {"i": {"type": "integer", "minimum": 1},
                                     "text": {"type": "string", "minLength": 3, "maxLength": 130},
                                     "keep": {"type": "boolean"}},
    "required": ["i", "text", "keep"]}}}, "required": ["titles"]}
PROOF_SYSTEM = ("You are a native Turkish proofreader for a Turkish gaming YouTuber. You fix spelling, vowel harmony "
                "and grammar, keep the gamer slang and English gaming terms exactly, never add facts, and answer only "
                "with JSON.")


def proof_prompt(titles: list[str], clip_text: str, lang_label: str, terms: list[str]) -> str:
    listing = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    return f"""Proofread these {lang_label} YouTube titles of a gaming clip.

What is said in the clip:
{clip_text[:1500]}

Titles:
{listing}

For every title return i, the corrected text and keep:
- fix spelling, vowel harmony (kurtarırdın, not kurtarırdin), suffixes after names with an apostrophe (Delta Force'ta, Yasuo'yu)
- NEVER translate gaming terms; keep them as streamers write them: {', '.join(keep_terms()[:30])}
- wrong translations must become the gaming term: iki katil -> double kill, revize -> revive
- a quote in double quotes keeps the words that were said (only fix their spelling)
- keep the emojis, the brackets and the "!" / "?!" exactly; don't add facts
- names: {', '.join(terms[:20]) or '(none)'}
- keep=false only for nonsense or a near-duplicate of an earlier title"""


# ------------------------------------------------------------------ descriptions

SHORT_DESC_SCHEMA = {"type": "object", "properties": {
    "lines": {"type": "array", "minItems": 2, "maxItems": 3, "items": {"type": "string", "minLength": 10, "maxLength": 220}},
    "question": {"type": "string", "minLength": 8, "maxLength": 160},
    "mood_hashtags": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 30}},
    "search_tags": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 60}},
}, "required": ["lines", "question", "mood_hashtags", "search_tags"]}
LONG_DESC_SCHEMA = {"type": "object", "properties": {
    "opener": {"type": "string", "minLength": 20, "maxLength": 300},
    "story": {"type": "string", "minLength": 120, "maxLength": 1200},
    "comment": {"type": "string", "minLength": 10, "maxLength": 160},
    "mood_hashtags": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 30}},
    "search_tags": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 60}},
}, "required": ["opener", "story", "comment", "mood_hashtags", "search_tags"]}


def _desc_body_of(e: dict) -> str:
    """An example description without the socials block and hashtags (what the model writes)."""
    from ..edit import brand

    text = brand.split_socials(e.get("description") or "")[0]
    out = []
    for ln in text.split("\n"):
        if re.match(r"^\s*(hashtag|etiket)", ln, re.I) or (ln.strip() and all(w.startswith("#") for w in ln.split())):
            break
        out.append(ln)
    return "\n".join(out).strip()


def description_task(p: dict, *, fmt: str, gid: str | None, game_name: str, what_happens: str, facts: str,
                     clip_text: str, title: str, lang_label: str, terms: list[str], problems: list[str]) -> str:
    tpl = p["templates"]
    ex = [e for e in examples_for(p, gid, fmt, n=8) if e["format"] == fmt and _desc_body_of(e)]
    ex = sorted(ex, key=lambda e: 0 if e["game"] == (gid or "") else 1)[:2]
    parts = [f"TASK: write the YouTube {'Shorts' if fmt == 'short' else 'long video'} description in {lang_label}, "
             "in the creator's own voice (first person: I / we).",
             f"What happens: {what_happens}", f"Game: {game_name or 'unknown (never name a game)'}"]
    if facts:
        parts.append(f"Facts (reliable): {facts}")
    parts += [f"Chosen title: {title}", f"What is said in the clip:\n{clip_text[:1500]}", ""]
    if ex:
        parts += ["The creator's own descriptions (copy the style and structure exactly, never the content):"]
        for e in ex:
            parts += ["---", _desc_body_of(e)]
        parts += ["---", ""]
    if fmt == "short":
        parts += ["Return:",
                  "- lines: 2-3 short punchy lines about the moment, with a few fitting emojis (the first line sets the scene, "
                  "the next ones tell what happened)",
                  f"- question: a comment question tied to this moment (the app adds \"{tpl['comment_call']}\")"]
    else:
        parts += ["Return:",
                  f"- opener: one hook sentence about the match that ends with \"{tpl['opener_end']}\"",
                  "- story: ONE paragraph about the match: who played what (champions / operators / classes), what "
                  f"happened, the numbers; lively, 3-6 sentences (the app adds \"{tpl['sign_off']}\")",
                  "- comment: what viewers should share in the comments, tied to this video, as the object of the CTA "
                  f"sentence \"{tpl['cta'].replace('{comment}', '<comment>')}\" (e.g. \"en sevdiğiniz operatör ikilisini "
                  "yorumlarda belirtmeyi\")"]
    parts += ["- mood_hashtags: 3-5 event / mood hashtags in CamelCase (#Tilt #Rage #KomikAnlar #1v9Carry), real words",
              "- search_tags: 6-8 natural Turkish search phrases people type (\"delta force komik anlar\") and 2 English ones",
              "Rules: only what the clip / facts show, never invent scores or names; no swearing (censor with * if quoted); "
              "no hashtags, links or clip times (+7s) in the text; gaming terms stay in English as streamers write them "
              f"({', '.join(keep_terms()[:16])}); correct Turkish spelling and vowel harmony.",
              f"Names: {', '.join(terms[:30]) or '(none)'}"]
    if game_name:
        parts.append(f"Only about {game_name}: never name another game.")
    if problems:
        parts += ["", "Problems last time, fix them:"] + [f"- {x}" for x in problems[:8]]
    return "\n".join(parts)


def _polish_text(text: str, lang: str, gl=None) -> str:
    out = " ".join(text.replace("\r", "").split(" ")).strip().strip('"“”')
    out = HASHTAG_RE.sub("", out)
    out = re.sub(r"https?://\S+", "", out)
    if gl is not None:
        out = gl.canonicalize(out)
    if lang == "tr":
        out, _f = proofread_tr(out)
    out, _n = censor(out, lang)
    return re.sub(r"[ \t]{2,}", " ", re.sub(r"\s+([?!.,…])", r"\1", out)).strip()


def assemble_short(d: dict, p: dict, lang: str, gl=None) -> str:
    lines = [_polish_text(x, lang, gl) for x in d.get("lines") or [] if x.strip()]
    q = _polish_text(d.get("question") or "", lang, gl).rstrip(" 👇")
    call = p["templates"]["comment_call"]
    if call.rstrip(" 👇") not in q:
        q = f"{q} {call}"
    if not q.endswith("👇"):
        q += " 👇"
    if len(lines) >= 3:
        lines = [lines[0], " ".join(lines[1:])]
    return "\n\n".join([*lines, q]).strip()


def assemble_long(d: dict, p: dict, lang: str, gl=None) -> str:
    tpl = p["templates"]
    opener = _polish_text(d.get("opener") or "", lang, gl)
    end = tpl["opener_end"].split()[-1] if tpl["opener_end"] else ""
    if end and not opener.endswith(end) and opener.rstrip("!. ").endswith(end.rstrip("!")):
        opener = opener.rstrip("!. ") + "!"
    story = _polish_text(d.get("story") or "", lang, gl).replace(tpl["sign_off"], "").strip()
    if story and not story.endswith((".", "!", "?", "…")):
        story += "."
    comment = _polish_text(d.get("comment") or "", lang, gl).rstrip(" .!🚀")
    comment = re.sub(r"\s*unutmayın\s*$", "", comment, flags=re.I)
    cta = tpl["cta"].replace("{comment}", comment)
    return f"{opener}\n\n{story} {tpl['sign_off']}\n\n{cta}".strip()


# ------------------------------------------------------------------ hashtags + tags


def _camel(name: str) -> str:
    parts = re.findall(r"[^\W_]+", name)
    return "".join(p if p.isupper() or any(c.isupper() for c in p[1:]) else p[:1].upper() + p[1:] for p in parts)


def game_tags(gid: str | None, game_name: str) -> dict:
    g = GAME_TAGS.get(gid or "")
    if g:
        return g
    if not game_name:
        return {"tag": "", "tr": "", "short": "#GamingShorts", "long": "#Gameplay", "label": "", "extra": []}
    c = _camel(game_name)
    return {"tag": f"#{c}", "tr": f"#{c}TR", "short": f"#{c}Shorts", "long": f"#{c}Gameplay", "label": game_name,
            "extra": []}


def build_hashtags(p: dict, *, fmt: str, gid: str | None, game_name: str, facts: dict, moment: str | None,
                   clip_text: str, llm: list[str] | None, lang: str, forbidden=None) -> list[str]:
    """10-12 in the creator's order: game, game TR, names, event / mood, format, channel, #GamingTR."""
    from . import banks

    g = game_tags(gid, game_name)
    seen: set[str] = set()

    def tag(t: str, check: bool = True) -> str | None:
        w = re.sub(r"[^\w]", "", str(t).replace("#", ""), flags=re.UNICODE)
        if not w or len(w) > 30 or w.casefold() in seen:
            return None
        if check and ((forbidden and forbidden(w) and forbidden(w) != "a clip time") or banks._profane(w)):
            return None
        seen.add(w.casefold())
        return "#" + w

    def group(items, check: bool = True, limit: int = 99) -> list[str]:
        out = []
        for t in items:
            if len(out) >= limit:
                break
            x = tag(t, check) if t else None
            if x:
                out.append(x)
        return out

    head = group([g["tag"], g["tr"]])
    tail_raw = [p["channel_tag"], "#GamingTR"]
    fmt_tags = group(["#GamingShorts", "#ShortsTR"] if fmt == "short" else [g["long"]])
    tail = group(tail_raw, check=False)
    names = group([_camel(t["term"]) for t in (facts.get("terms") or [])
                   if t.get("kind") in ("champion", "champions", "operator", "operators", "agent", "agents", "class",
                                        "weapon", "weapons", "vehicle", "vehicles")], limit=3)
    mood_in: list[str] = []
    for e in (facts.get("events") or [])[:2]:
        mood_in += [_camel(h.lstrip("#")) if h.islower() else h for h in (e.get("hashtags") or [])[:1]]
    for h in llm or []:
        w = re.sub(r"[^\w]", "", h.replace("#", ""), flags=re.UNICODE)
        if w and (banks._known_tag(w, lang) or w.casefold() in {"tilt", "rage", "1v9carry"}):
            mood_in.append(w)
    if TILT_WORDS.search(clip_text or ""):
        mood_in += ["#Tilt", "#Rage"]
    mood_in += MOOD_TAGS.get(moment or "", MOOD_TAGS["other"])
    room = 12 - len(head) - len(fmt_tags) - len(tail) - len(names)
    mood = group(mood_in, limit=max(2, min(4, room)))
    extra = group(g.get("extra") or [], limit=max(0, 12 - len(head) - len(names) - len(mood) - len(fmt_tags) - len(tail)))
    out = head + names + mood + extra + fmt_tags + tail
    return out[:12] if len(out) <= 12 else head + names + mood[:12 - len(head + names + fmt_tags + tail)] + fmt_tags + tail


def real_words(text: str, extra: set[str] | frozenset[str] = frozenset()) -> bool:
    """Every word is a real Turkish or English word, a number or a known name ("leof legends": no)."""
    if not lexicon.available():
        return True
    for w in re.findall(r"[^\W_]+", text):
        lw = w.lower()
        if w.isdigit() or lw in extra or lexicon.lower(w, "tr") in extra:
            continue
        if len(w) == 1:
            return False  # "lo l şok öldüm"
        if lexicon.zipf(lexicon.lower(w, "tr"), "tr") < 2.0 and lexicon.zipf(lw, "en") < 3.0 \
                and lexicon.known_score(lexicon.lower(w, "tr"), "tr") <= 0:
            return False
    return True


def build_tags(p: dict, *, fmt: str, gid: str | None, game_name: str, facts: dict, moment: str | None,
               llm: list[str] | None, bank_tags: list[str], forbidden=None) -> list[str]:
    """10-15 search phrases: Turkish first, a few English, "<name> Shorts" / "<name> <game>"."""
    from .. import youtube
    from . import banks

    g = game_tags(gid, game_name)
    game = game_name or ""
    label = g.get("label") or game
    out: list[str] = []

    def add(t: str) -> None:
        t = " ".join(str(t).replace("#", " ").replace(",", " ").split())
        if (not t or len(t) > 60 or t.casefold() in {x.casefold() for x in out} or banks._profane(t)
                or (forbidden and forbidden(t) and forbidden(t) != "a clip time")):
            return
        out.append(t)

    if game:
        add(f"{game} Shorts" if fmt == "short" else f"{game} Türkçe")
        add(f"{game} Türkçe" if fmt == "short" else f"{game} Türkçe gameplay")
    for t in (facts.get("terms") or [])[:2]:
        if game:
            add(f"{label} {t['term']} oynanış")
    if game and moment in ("funny", "fail"):
        add(f"{game} komik anlar")
        add(f"{game} fail")
    for e in (facts.get("events") or [])[:2]:
        if game:
            add(f"{label} {(e.get('search') or e.get('label') or '').lower()}")
    if p["name"]:
        add(f"{p['name']} Shorts" if fmt == "short" else f"{p['name']} {label or 'Gaming'}")
    known_words = {w.lower() for x in [game, label, p["name"]] + [t["term"] for t in facts.get("terms") or []]
                   for w in re.findall(r"[^\W_]+", x or "")}
    for t in llm or []:
        if len(out) >= 12:
            break
        if 2 <= len(t.split()) <= 6 and real_words(t, known_words):
            add(t)
    if game:
        add(f"{game} gameplay TR")
        add(f"{game} funny moments" if moment in ("funny", "fail") else f"{game} highlights")
    if p["name"] and fmt == "short" and label:
        add(f"{p['name']} {label}")
    for t in bank_tags:
        if len(out) >= 15:
            break
        if len(t.split()) >= 2 and t.lower() not in ("shorts",):
            add(t)
    return youtube.clean_tags(out)[:15]


# ------------------------------------------------------------------ main: titles


def write_titles(model, p: dict, *, system: str, context: str, lang: str, lang_label: str, fmt: str,
                 gid: str | None, game_name: str, what_happens: str, facts: str, clip_text: str, glossary,
                 used_titles: list[str], too_similar, forbidden, moment: str | None, liked: list[str],
                 strong: bool = False, avoid: list[str] | None = None, temperature: float = 0.8,
                 n_out: int = 6, game_names: dict[str, str] | None = None) -> dict:
    """The creator-style titles of one clip: draft -> proofread -> local fixes -> rule check ->
    write again with the problems (up to 3 rounds; 4 when the PC is idle / Turbo)."""
    n = 10 if strong else 8
    rounds = 3
    example_titles = [e["title"] for e in p["examples"]]
    checks: dict = {"rejected": [], "fixed": [], "rounds": 0, "style": "my_style", "strong": strong}
    pool: list[dict] = []
    problems: list[str] = []
    terms = list(glossary.terms) if glossary is not None else []
    name_words = {w.lower() for t in terms for w in re.findall(r"[^\W\d_]+", t) if w.isascii() and len(w) > 2}
    avoid = list(avoid or [])
    for _r in range(rounds):
        checks["rounds"] += 1
        prompt = context + "\n\n" + title_task(
            p, fmt=fmt, gid=gid, game_name=game_name, what_happens=what_happens, facts=facts, clip_text=clip_text,
            lang_label=lang_label, n=n, game_names=game_names or {}, liked=liked,
            used=used_titles[-20:] + avoid + [x["text"] for x in pool], problems=problems, terms=terms, moment=moment,
            allowed=glossary.allowed if glossary is not None else frozenset())
        d = model.json(system, prompt, title_schema(n), temperature=temperature, num_predict=1400)
        d.pop("_soft_errors", None)
        drafts = [{"kind": t.get("kind") or "fact", "text": " ".join(str(t.get("text") or "").split())}
                  for t in d.get("titles") or [] if str(t.get("text") or "").strip()]
        if not drafts:
            continue
        try:
            pr = model.json(PROOF_SYSTEM, proof_prompt([t["text"] for t in drafts], clip_text, lang_label, terms),
                            PROOF_SCHEMA, temperature=0.2, num_predict=1400)
            by_i = {x["i"]: x for x in pr.get("titles") or []}
        except Exception:  # noqa: BLE001 - the proofread is a bonus; local fixes still run
            by_i = {}
        for i, t in enumerate(drafts, start=1):
            x = by_i.get(i)
            if x is not None and not x.get("keep", True):
                checks["rejected"].append({"text": t["text"], "reason": "proofread: duplicate or nonsense"})
                continue
            new = (x.get("text") or "").strip() if x else t["text"]
            if quote_of(t["text"]) and not quote_of(new):
                new = t["text"]  # the proofreader dropped the quote marks
            text = glossary.canonicalize(new) if glossary is not None else new
            final = fix_title(text, lang, moment, names=name_words)
            if final != t["text"]:
                checks["fixed"].append([t["text"], final])
            errs = check_title(final, lang=lang, fmt=fmt, clip_text=clip_text, forbidden=forbidden,
                               example_titles=example_titles, used=used_titles + avoid, too_similar=too_similar)
            plain = re.sub(r"\S*\*\S*", " ", lower_title(strip_emojis(final), lang))  # censored words
            unknown = lexicon.unknown_words(plain, lang,
                                            (glossary.allowed if glossary is not None else set())
                                            | {lexicon.lower(w, lang) for k in keep_terms() for w in k.split()}
                                            | {"lan", "ulan"})
            if unknown:
                errs.append("unknown words: " + ", ".join(unknown[:3]))
            if not errs and any(too_similar(split_title(final)[0], split_title(k["text"])[0], phrases=False) for k in pool):
                errs.append("duplicate")
            if errs:
                checks["rejected"].append({"text": final, "reason": "; ".join(errs)})
                problems.append(f"'{final}': {'; '.join(errs)}")
                continue
            pool.append({"style": t["kind"], "text": final})
        if len(pool) >= n_out:
            break
    return {"titles": pick(pool, fmt, n_out), "checks": checks}


def has_censored(text: str) -> bool:
    return bool(re.search(r"[^\W\d_]\*+[^\W\d_]", text or ""))


def pick(pool: list[dict], fmt: str, n: int = 6) -> list[dict]:
    """Strongest first, kinds mixed; Shorts: quote titles lead when there are any. At most one
    title with a (censored) swear: it stays a flavour, and keeps the channel ad-friendly."""
    swear = [t for t in pool if has_censored(t["text"])]
    if len(swear) > 1 and len(pool) - (len(swear) - 1) >= min(n, 4):
        pool = [t for t in pool if not has_censored(t["text"]) or t is swear[0]]
    out: list[dict] = []
    if fmt == "short":
        out += [t for t in pool if t["style"] == "quote"][:3]
    for k in TITLE_KINDS:
        c = next((t for t in pool if t["style"] == k and t not in out), None)
        if c and len(out) < n:
            out.append(c)
    for t in pool:
        if len(out) >= n:
            break
        if t not in out:
            out.append(t)
    order = {id(t): i for i, t in enumerate(pool)}
    lead = [t for t in out if t["style"] == "quote" and not has_censored(t["text"])] if fmt == "short" else []
    rest = sorted([t for t in out if t not in lead], key=lambda t: order[id(t)])
    return [dict(t) for t in order_titles(lead + rest)[:n]]


def order_titles(titles: list) -> list:
    """A title with a (censored) swear never comes first: the first title is the one uploaded."""
    text = lambda t: t["text"] if isinstance(t, dict) else t  # noqa: E731
    return [t for t in titles if not has_censored(text(t))] + [t for t in titles if has_censored(text(t))]


# ------------------------------------------------------------------ main: descriptions


def write_description(model, p: dict, *, system: str, context: str, lang: str, lang_label: str, fmt: str,
                      gid: str | None, game_name: str, what_happens: str, facts: str, clip_text: str, title: str,
                      glossary, forbidden, strong: bool = False) -> dict:
    """{text (body, no hashtags), mood_hashtags, search_tags, problems}."""
    terms = list(glossary.terms) if glossary is not None else []
    schema = SHORT_DESC_SCHEMA if fmt == "short" else LONG_DESC_SCHEMA
    problems: list[str] = []
    best: dict | None = None
    shown = p  # 1.2.31: an example the model keeps copying is left out of the prompt
    for _r in range(5):
        if _r >= 3 and not (best and any("copies the creator" in e for e in best["problems"])):
            break  # tries 4 and 5 only when it keeps copying an example
        prompt = context + "\n\n" + description_task(
            shown, fmt=fmt, gid=gid, game_name=game_name, what_happens=what_happens, facts=facts, clip_text=clip_text,
            title=title, lang_label=lang_label, terms=terms, problems=problems)
        d = model.json(system, prompt, schema, temperature=0.65 + 0.1 * min(_r, 3),
                       num_predict=1600 if fmt == "long" else 900)
        d.pop("_soft_errors", None)
        text = assemble_short(d, p, lang, glossary) if fmt == "short" else assemble_long(d, p, lang, glossary)
        errs = (check_short_description(text, lang=lang, forbidden=forbidden) if fmt == "short"
                else check_long_description(text, p, lang=lang, forbidden=forbidden))
        copied = copied_sentences(text, p)
        if copied:
            errs.append(f"copies the creator's example (\"{copied[0][:80]}\"): write new sentences about THIS clip")
            rest = [e for e in shown["examples"] if not _shares(e, copied, p)]
            if rest:
                shown = {**shown, "examples": rest}
        cand = {"text": text, "mood_hashtags": list(d.get("mood_hashtags") or []),
                "search_tags": list(d.get("search_tags") or []), "problems": errs}
        if best is None or len(errs) < len(best["problems"]):
            best = cand
        if not errs:
            break
        problems = errs
    assert best is not None
    if fmt == "short" and any("copies the creator" in e for e in best["problems"]):
        rescued = _without_copies(best["text"], p, lang, forbidden)  # keep the clip's own sentences
        if rescued:
            best = {**best, "text": rescued,
                    "problems": [e for e in best["problems"] if "copies the creator" not in e]}
    if any("swear" in e or "never mention" in e or "copies the creator" in e for e in best["problems"]):
        best["text"] = ""  # never publish a description that breaks the hard rules
    return best


def _shares(example: dict, copied: list[str], p: dict) -> bool:
    """Did these copied sentences come from this example?"""
    return bool(copied_sentences(" ".join(copied), {**p, "examples": [example]}))


def _without_copies(text: str, p: dict, lang: str, forbidden) -> str:
    """The description without the copied sentences, when enough of the clip's own text is left
    and it passes every other check ("" otherwise)."""
    out = text
    for s in copied_sentences(text, p):
        out = out.replace(s, " ")
    paras = []
    for para in out.split("\n\n"):
        para = re.sub(r"[ \t]{2,}", " ", para).strip()
        if re.search(r"[^\W\d_]{3,}", para):  # a paragraph left with only emojis / dots goes
            paras.append(para)
    out = "\n\n".join(paras)
    own = [x for para in paras for x in _sentences(para)]
    if len(own) < 2 or len(paras) < 2 or copied_sentences(out, p) or \
            check_short_description(out, lang=lang, forbidden=forbidden):
        return ""
    return out


def compose(body: str, hashtags: list[str]) -> str:
    """The stored description: body + the hashtag line (the label and the socials block are
    put in when it is published; see brand.with_socials)."""
    tags = " ".join(hashtags)
    return f"{body}\n\n{tags}".strip() if body else tags


def layout(lang: str | None) -> dict | None:
    """The creator's description layout: socials before the labelled hashtags."""
    p = active(lang)
    if p is None:
        return None
    return {"label": p["templates"]["hashtag_label"], "short_socials": p["shorts_socials"]}


def clone(p: dict) -> dict:
    return copy.deepcopy(p)
