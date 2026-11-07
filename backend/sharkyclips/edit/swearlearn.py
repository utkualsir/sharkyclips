"""Swears learned from the user (1.2.21): every manual bleep (B key / waveform / review list)
adds the words under it to a personal list, per language and speaker; every "unbleep" of a
found word counts against it. Kept in <settings>/swear_learned.json:

  {"version": 1, "langs": {"tr": {"add":    {"sıkeyim": {"n": 2, "spk": {"me": 2}, "last": "..."}},
                                  "ignore": {"amanak":  {"n": 1, ...}}}}}

Learned words are swears for detection ("learned", sure) and hints for the re-listen
(voices/swearscan.py). An ignored word is no longer a "maybe"; a list word the user unbleeped
twice or more drops to "maybe" (so Strict still bleeps it, Normal doesn't).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from .. import config
from ..project import read_json, write_json_atomic
from .words import token

VERSION = 1
MAX_WORDS = 500
_lock = threading.Lock()


def path() -> Path:
    return config.config_dir() / "swear_learned.json"


def load() -> dict:
    p = path()
    try:
        data = read_json(p) if p.is_file() else {}
    except Exception:  # noqa: BLE001 - broken file: start over
        data = {}
    if not isinstance(data, dict) or data.get("version") != VERSION:
        data = {"version": VERSION, "langs": {}}
    data.setdefault("langs", {})
    return data


def _key(word: str, lang: str | None) -> str:
    return token(word, lang)[:40]


def learn(lang: str | None, words: list[dict], kind: str = "add") -> list[str]:
    """Count the words ({"word", "spk"?}) as swears (kind "add") or as not swears ("ignore").
    Returns the tokens saved."""
    if kind not in ("add", "ignore") or not words:
        return []
    lang = lang or "xx"
    saved = []
    with _lock:
        data = load()
        langd = data["langs"].setdefault(lang, {"add": {}, "ignore": {}})
        bucket = langd.setdefault(kind, {})
        other = langd.setdefault("ignore" if kind == "add" else "add", {})
        for w in words:
            k = _key(str(w.get("word", "")), lang)
            if len(k) < 2 or k.isdigit():
                continue
            e = bucket.setdefault(k, {"n": 0, "spk": {}})
            e["n"] = int(e.get("n", 0)) + 1
            spk = w.get("spk") or "?"
            e["spk"][spk] = int(e["spk"].get(spk, 0)) + 1
            e["last"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            other.pop(k, None)  # the latest choice wins
            saved.append(k)
        if len(bucket) > MAX_WORDS:  # keep the most used
            for k in sorted(bucket, key=lambda k: (bucket[k].get("n", 0), bucket[k].get("last", "")))[:len(bucket) - MAX_WORDS]:
                bucket.pop(k, None)
        write_json_atomic(path(), data)
    return saved


def remove(lang: str, word: str, kind: str = "add") -> None:
    with _lock:
        data = load()
        langd = data["langs"].get(lang) or {}
        (langd.get(kind) or {}).pop(word, None)
        write_json_atomic(path(), data)


def words(lang: str | None, kind: str = "add") -> dict[str, dict]:
    return dict(((load()["langs"].get(lang or "xx") or {}).get(kind)) or {})


def entries(lang: str | None) -> list[str]:
    """Learned swears as word-list entries (exact words)."""
    return sorted(words(lang, "add"))


def ignored(lang: str | None) -> dict[str, int]:
    return {k: int(v.get("n", 1)) for k, v in words(lang, "ignore").items()}


def hotwords(lang: str | None, limit: int = 20) -> list[str]:
    """The most used learned swears first (decoder hints)."""
    w = words(lang, "add")
    return sorted(w, key=lambda k: -int(w[k].get("n", 0)))[:limit]


# ------------------------------------------------------------------ from the review edits

def _ranges(e: dict | None, key: str) -> set[tuple[float, float]]:
    return {(round(float(a), 3), round(float(b), 3)) for a, b in ((e or {}).get(key) or [])}


def from_edits(project, old: dict, new: dict) -> int:
    """New manual bleeps / unbleeps between two review "edits" dicts ({cid: edit}) -> learned.
    Returns the number of words saved."""
    from .plan import transcript_words

    n = 0
    for cid, e in (new or {}).items():
        before = (old or {}).get(cid) or {}
        for key, kind in (("bleep", "add"), ("unbleep", "ignore")):
            for a, b in sorted(_ranges(e, key) - _ranges(before, key)):
                if b - a > 4.0:  # a long manual mute is not one word
                    continue
                ws, lang = transcript_words(project, a - 0.3, b + 0.3)
                under = [w for w in ws if w["start"] < b - 0.02 and w["end"] > a + 0.02]
                if kind == "add":  # the words mostly inside the bleep
                    under = [w for w in under if min(b, w["end"]) - max(a, w["start"]) >= 0.4 * (w["end"] - w["start"])]
                n += len(learn(lang, under[:3], kind))
    return n
