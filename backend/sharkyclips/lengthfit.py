"""Clip length target from the channel's own views (1.2.35).

The Easy mode length target (shaping.TARGETS) is a good guess for everyone. Once a channel has
published enough shorts, its own numbers say better which length works for it:

1. learned: the length band (under 20, 20-30, 30-45, over 45 s, as in the weekly digest) whose shorts got the most views on
   average, per mode (gaming / study / music). Only when there is enough data: MIN_SAMPLE
   published shorts with views of that mode, MIN_BAND of them in the winning band, the band
   at least MIN_RATIO x the mode's average (and its median above the mode's median, so one
   viral clip alone doesn't decide). Shorts younger than MIN_AGE_H hours are left out (their
   views are still climbing).
2. saved: config "length_targets" {"gaming": {"min": 30, "max": 45, ...}}, a target set from
   the channel's numbers before there were enough of them (used until 1. takes over).
3. none: the built-in targets.

Everything comes from the upload records (uploads.json, views refreshed every 6 hours).
"""

from __future__ import annotations

import statistics
import threading
import time
from datetime import datetime, timedelta, timezone

MIN_SAMPLE = 8
MIN_BAND = 3
MIN_RATIO = 1.15
MIN_AGE_H = 48
# the digest's length groups -> the target they set
BANDS = ((0.0, 20.0, (15.0, 20.0)), (20.0, 30.0, (20.0, 30.0)), (30.0, 45.0, (30.0, 45.0)), (45.0, 1e9, (45.0, 60.0)))
CACHE_S = 600.0

_cache: dict[str, tuple[float, dict | None]] = {}
_lock = threading.Lock()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _band(d: float) -> tuple[float, float] | None:
    if d <= 0:
        return None
    return next(t for lo, hi, t in BANDS if lo <= d < hi)


def band_name(tgt: dict | None) -> str | None:
    """The digest's length group name of a target ("30_45"), None for another range."""
    if not tgt:
        return None
    names = {(15.0, 20.0): "lt20", (20.0, 30.0): "20_30", (30.0, 45.0): "30_45", (45.0, 60.0): "gt45"}
    return names.get((float(tgt["min"]), float(tgt["max"])))


def learn(items: list[dict], mode: str, now: datetime) -> dict | None:
    """The winning band of this mode's shorts, or None (not enough data / no clear winner).
    items: digest.shorts() rows (views, duration, at, mode)."""
    old = now - timedelta(hours=MIN_AGE_H)
    known = [s for s in items if (s.get("mode") or "gaming") == mode and s.get("views") is not None
             and s.get("at") is not None and s["at"] <= old and _band(float(s.get("duration") or 0))]
    if len(known) < MIN_SAMPLE:
        return None
    views = [int(s["views"]) for s in known]
    avg, med = sum(views) / len(views), statistics.median(views)
    if avg <= 0:
        return None
    groups: dict[tuple[float, float], list[int]] = {}
    for s in known:
        groups.setdefault(_band(float(s["duration"])), []).append(int(s["views"]))
    if len(groups) < 2:
        return None
    best = None
    for band, vs in groups.items():
        if len(vs) < MIN_BAND:
            continue
        ratio = (sum(vs) / len(vs)) / avg
        if ratio >= MIN_RATIO and statistics.median(vs) > med and (best is None or ratio > best["ratio"]):
            best = {"min": band[0], "max": band[1], "source": "learned", "ratio": round(ratio, 2),
                    "n": len(known), "band_n": len(vs)}
    return best


def saved(mode: str) -> dict | None:
    from . import config

    raw = (config.get("length_targets") or {}).get(mode)
    if not isinstance(raw, dict):
        return None
    try:
        lo, hi = float(raw["min"]), float(raw["max"])
    except (KeyError, TypeError, ValueError):
        return None
    if not 5.0 <= lo < hi <= 180.0:
        return None
    out = {"min": lo, "max": hi, "source": "channel"}
    if raw.get("ratio") is not None:
        out["ratio"] = float(raw["ratio"])
    return out


def for_mode(mode: str, now: datetime | None = None) -> dict | None:
    """The channel's length target for this mode ({"min", "max", "source", ...}) or None."""
    with _lock:
        hit = _cache.get(mode)
        if hit and time.monotonic() - hit[0] < CACHE_S and now is None:
            return hit[1]
    out = None
    try:
        from . import digest

        now_ = now or datetime.now(timezone.utc)
        out = learn(digest.shorts(now_), mode, now_)
    except Exception:  # noqa: BLE001 - a broken upload record never breaks shaping
        out = None
    out = out or saved(mode)
    if now is None:
        with _lock:
            _cache[mode] = (time.monotonic(), out)
    return out
