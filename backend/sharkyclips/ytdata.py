"""How long numbers fetched from the YouTube API stay on this computer (YouTube API Services
Developer Policies: refresh or delete stored API data within 30 days; delete authorized data
when the user revokes access).

What counts: views / likes / privacy / retention SharkyClips read from YouTube for the user's own
uploads, kept in
  * <project>/uploads.json   ("views", "likes", "retention", "stats_at" on each upload)
  * calibration.json         (entries with "source": "youtube")
  * hook_tests.json          (hook test results: retention and views per video)
Numbers the user typed in by hand ("source": "manual") are the user's own and stay.

  purge(all_=True)  Disconnect, or 7 days after Google ended the sign-in without a reconnect:
                    every fetched number goes.
  purge()           Daily: numbers not refreshed for 30 days go (the regular sync refreshes them
                    every few hours while SharkyClips runs and YouTube is connected).
The video IDs of the user's own uploads stay: SharkyClips needs them to manage those videos.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from . import calibration, config
from .project import read_json, write_json_atomic

MAX_AGE = timedelta(days=30)
REVOKED_GRACE = timedelta(days=7)
UPLOAD_FIELDS = ("views", "likes", "retention", "stats_at")
_lock = threading.Lock()
_last = {"t": 0.0}


def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _stale(iso: str | None, now: datetime) -> bool:
    t = _parse(iso)
    return t is None or now - t > MAX_AGE


def _uploads(now: datetime, all_: bool) -> int:
    n = 0
    try:
        paths = sorted(config.workspace_dir().glob("*/uploads.json"))
    except OSError:
        paths = []
    for path in paths:
        try:
            data = read_json(path)
        except Exception:  # noqa: BLE001
            continue
        changed = False
        for lst in (data.get("uploads") or {}).values():
            for u in lst:
                if not any(k in u for k in UPLOAD_FIELDS):
                    continue
                if all_ or _stale(u.get("stats_at"), now):
                    for k in UPLOAD_FIELDS:
                        u.pop(k, None)
                    changed, n = True, n + 1
        if changed:
            write_json_atomic(path, data)
    return n


def _calibration(now: datetime, all_: bool) -> int:
    with calibration._lock:
        data = calibration.load()
        drop = [k for k, e in data["entries"].items() if e.get("source") == "youtube"
                and (all_ or _stale(e.get("updated_at"), now))]
        if drop:
            for k in drop:
                data["entries"].pop(k, None)
            data["model"] = calibration.fit(data["entries"])
            calibration._save(data)
    return len(drop)


def _hook_tests(now: datetime, all_: bool) -> int:
    from . import abtest

    data = abtest.load_store()
    keep, n = [], 0
    for o in data["observations"]:
        if o.get("simulated"):
            keep.append(o)
        elif all_:
            n += 1
        elif _stale(o.get("fetched_at"), now) and ("retention" in o or "views" in o):
            # the learned reward (0..1) stays for the hook-style choice; the YouTube numbers go
            keep.append({k: v for k, v in o.items() if k not in ("retention", "views")})
            n += 1
        else:
            keep.append(o)
    if n:
        data["observations"] = keep
        abtest._save_store(data)
    return n


def purge(all_: bool = False, now: datetime | None = None) -> dict:
    """Delete fetched YouTube numbers: all of them, or the ones older than 30 days."""
    now = now or datetime.now(timezone.utc)
    with _lock:
        out = {"uploads": _uploads(now, all_), "calibration": _calibration(now, all_),
               "hook_tests": _hook_tests(now, all_)}
    if all_:
        config.update(yt_data_purged_at=now.isoformat(timespec="seconds"))
    return out


def daily(now: datetime | None = None) -> dict | None:
    """Called by the publish scheduler; runs at most once a day."""
    if time.time() - _last["t"] < 86400:
        return None
    _last["t"] = time.time()
    from . import youtube

    now = now or datetime.now(timezone.utc)
    gone = youtube.signed_out()  # Google ended the sign-in (revoked / expired) and no reconnect
    at = _parse((gone or {}).get("at"))
    if at is not None and now - at > REVOKED_GRACE:
        return purge(all_=True, now=now)
    return purge(now=now)
