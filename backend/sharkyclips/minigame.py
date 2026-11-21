"""The waiting mini game (1.2.59): a small shark game while a project is processing.

The game itself runs in the browser (frontend/src/minigame/). The server only keeps the player's
numbers in the settings file (config key "minigame"), so they survive a browser change or a new
port: best score, today's best (the player's local date, sent with each round), rounds played,
fish eaten, best combo, the chosen skin and two small preferences (muted, how-to seen).

Skins are earned by playing (rounds, fish, a score or a combo once reached). Nothing expires,
nothing is bought, there are no streaks or timers that push the player to come back.
"""

from __future__ import annotations

import re
import threading

from . import config

# (id, rule, amount): rounds / fish = totals over all rounds; best / combo = reached once
SKINS: list[tuple[str, str, int]] = [
    ("classic", "free", 0),
    ("reef", "rounds", 3),
    ("tiger", "best", 3000),
    ("neon", "fish", 250),
    ("ghost", "combo", 15),
    ("deep", "rounds", 15),
    ("gold", "best", 8000),
]
SKIN_IDS = {s[0] for s in SKINS}
MAX_SCORE = 100_000  # a sanity cap (the game is local: this only keeps the numbers readable)
MAX_FISH = 2_000
MAX_COMBO = 500
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_lock = threading.RLock()


def enabled() -> bool:
    return config.get("minigame_enabled") is not False  # on by default; Settings can turn it off


def _raw() -> dict:
    d = config.get("minigame")
    return dict(d) if isinstance(d, dict) else {}


def _int(v, hi: int) -> int:
    try:
        return max(0, min(hi, int(v)))
    except (TypeError, ValueError):
        return 0


def _progress(d: dict, rule: str) -> int:
    return {"free": 0, "rounds": _int(d.get("rounds"), 10**9), "fish": _int(d.get("fish"), 10**9),
            "best": _int(d.get("best"), MAX_SCORE), "combo": _int(d.get("best_combo"), MAX_COMBO)}[rule]


def unlocked(d: dict) -> list[str]:
    return [sid for sid, rule, need in SKINS if rule == "free" or _progress(d, rule) >= need]


def view(today: str | None = None) -> dict:
    d = _raw()
    have = set(unlocked(d))
    skin = d.get("skin") if d.get("skin") in have else "classic"
    daily = d.get("daily") if isinstance(d.get("daily"), dict) else {}
    day_best = _int(daily.get("best"), MAX_SCORE) if today and daily.get("date") == today else 0
    return {
        "enabled": enabled(),
        "best": _int(d.get("best"), MAX_SCORE),
        "today_best": day_best,
        "rounds": _int(d.get("rounds"), 10**9),
        "fish": _int(d.get("fish"), 10**9),
        "best_combo": _int(d.get("best_combo"), MAX_COMBO),
        "skin": skin,
        "muted": d.get("muted") is not False,  # sound is off until the player turns it on
        "howto_seen": bool(d.get("howto_seen")),
        "skins": [{"id": sid, "rule": rule, "need": need, "have": min(need, _progress(d, rule)) if need else 0,
                   "unlocked": sid in have} for sid, rule, need in SKINS],
    }


def record_round(body: dict) -> dict:
    """One finished round: {score, fish, combo, date}. Returns the new view + what this round did."""
    score = _int(body.get("score"), MAX_SCORE)
    fish = _int(body.get("fish"), MAX_FISH)
    combo = _int(body.get("combo"), MAX_COMBO)
    date = str(body.get("date") or "")
    date = date if _DATE.match(date) else None
    with _lock:
        d = _raw()
        before = set(unlocked(d))
        old_best = _int(d.get("best"), MAX_SCORE)
        d["best"] = max(old_best, score)
        d["rounds"] = _int(d.get("rounds"), 10**9) + 1
        d["fish"] = _int(d.get("fish"), 10**9) + fish
        d["best_combo"] = max(_int(d.get("best_combo"), MAX_COMBO), combo)
        daily = d.get("daily") if isinstance(d.get("daily"), dict) else {}
        old_day = _int(daily.get("best"), MAX_SCORE) if date and daily.get("date") == date else 0
        if date:
            d["daily"] = {"date": date, "best": max(old_day, score)}
        config.update(minigame=d)
        new_skins = [s for s in unlocked(d) if s not in before]
    out = view(date)
    out["round"] = {"score": score, "new_best": score > old_best and score > 0,
                    "new_today": bool(date) and score > old_day and score > 0, "new_skins": new_skins}
    return out


def save_prefs(body: dict, today: str | None = None) -> dict:
    """skin / muted / howto_seen / enabled."""
    with _lock:
        d = _raw()
        changed = False
        if body.get("skin") in SKIN_IDS and body["skin"] in unlocked(d):
            d["skin"] = body["skin"]
            changed = True
        for key in ("muted", "howto_seen"):
            if key in body:
                d[key] = bool(body[key])
                changed = True
        if changed:
            config.update(minigame=d)
        if "enabled" in body:
            config.update(minigame_enabled=bool(body["enabled"]))
    return view(today)
