"""Thumbs up/down on titles, kept in ~/.sharkyclips/title_feedback.json.

Liked titles become extra few-shot examples for the same output language (same content type
first), disliked ones are shown to the LLM as "not this style". So titles drift towards the
creator's own style over time.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .. import config

MAX_ITEMS = 2000
_lock = threading.RLock()


def path() -> Path:
    return config.config_dir() / "title_feedback.json"


def _load() -> list[dict]:
    p = path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        return [x for x in data.get("items", []) if isinstance(x, dict) and x.get("text")]
    except (OSError, json.JSONDecodeError):
        return []


def _save(items: list[dict]) -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"version": 1, "items": items[-MAX_ITEMS:]}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(tmp, p)


def vote(text: str, lang: str, value: int, *, mode: str = "", topic: str = "", project: str = "",
         clip: str = "") -> None:
    """value: 1 = like, -1 = dislike, 0 = remove the vote."""
    text = " ".join(text.split())
    with _lock:
        items = [x for x in _load() if not (x["text"] == text and x.get("lang") == lang)]
        if value:
            items.append({"text": text, "lang": lang, "vote": 1 if value > 0 else -1, "mode": mode,
                          "topic": topic, "project": project, "clip": clip,
                          "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        _save(items)


def votes_for(texts: list[str], lang: str | None) -> dict[str, int]:
    want = set(texts)
    return {x["text"]: x["vote"] for x in _load() if x["text"] in want and (lang is None or x.get("lang") == lang)}


def examples(lang: str, mode: str, liked: int = 8, disliked: int = 5) -> tuple[list[str], list[str]]:
    """Most recent liked / disliked titles for this language (this content type first)."""
    items = [x for x in _load() if x.get("lang") == lang]

    def pick(v: int, n: int) -> list[str]:
        mine = [x for x in items if x["vote"] == v]
        same = [x["text"] for x in reversed(mine) if x.get("mode") == mode]
        other = [x["text"] for x in reversed(mine) if x.get("mode") != mode]
        return (same + other)[:n]

    return pick(1, liked), pick(-1, disliked)
