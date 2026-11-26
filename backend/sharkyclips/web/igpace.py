"""1.2.62: a safe pace for Instagram, and Instagram paused as a default target.

Instagram restricts accounts that look automated. So, whatever the mode (Manual reminders or the
API, if it is ever switched back on):
  pace      at least MIN_GAP_HOURS between two Instagram posts (posted, planned or reminded); a
            post asked for sooner moves to the next safe time (its reminder moves with it)
  hashtags  at most HASHTAGS per caption (the channel's own tags first), rotated so the set is
            not the same as the last Instagram post's when the clip has other tags to offer
  captions  never the same caption as the previous Instagram post (generated captions try the
            clip's other titles; an edited one shows a problem with a "Vary it" fix)
  paused    once (config "ig_paused_at"), Instagram leaves the remembered publish targets and the
            publish queue: the setup and the connection stay, switching it back on is up to you.
            An account / permission refusal from Instagram pauses it again (see pause_after_block).

(1.2.62 was written while the developer's Instagram account was suspended. It is active again since
2026-11-26: these rules stay as the safe default for everyone, Instagram stays Manual.)
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta, timezone

from .. import config
from .. import platforms as PF

MIN_GAP_HOURS = 4.0
HASHTAGS = 5
_cache: dict = {"at": 0.0, "events": []}
_lock = threading.Lock()


def min_gap() -> timedelta:
    return timedelta(hours=MIN_GAP_HOURS)


def _ts(value) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _event_time(r: dict) -> float | None:
    """When this Instagram post went out / is meant to go out (None: nothing planned)."""
    st = r.get("status")
    if st in ("idle", "cancelled", "paused", None) and not r.get("media_id"):
        return None
    if st == "failed" and not r.get("next_try_at"):
        return None
    for k in ("posted_at", "shared_at", "publish_at", "remind_at", "notified_at", "init_at"):
        t = _ts(r.get(k))
        if t:
            return t
    return None


def events(app=None, fresh: bool = False) -> list[dict]:
    """Every Instagram post across the projects: [{key, at, caption}], oldest first (cached 5 s)."""
    with _lock:
        if not fresh and time.time() - _cache["at"] < 5:
            return list(_cache["events"])
    if app is None:
        from . import multipost

        app = multipost._app()
    out = []
    for project in app.list_projects():
        try:
            recs = PF.records(project)
        except Exception:  # noqa: BLE001 - one broken project never stops the pace check
            continue
        for cid, plats in (recs or {}).items():
            r = (plats or {}).get("reels") or {}
            at = _event_time(r)
            if at is not None:
                out.append({"key": (project.id, cid), "at": at, "caption": r.get("caption") or ""})
    out.sort(key=lambda e: e["at"])
    with _lock:
        _cache.update(at=time.time(), events=out)
    return list(out)


def forget_cache() -> None:
    with _lock:
        _cache["at"] = 0.0


def next_safe(wanted: datetime, others: list[dict], skip=None) -> datetime:
    """The earliest time >= wanted that is MIN_GAP_HOURS away from every other Instagram post."""
    gap = min_gap().total_seconds()
    times = sorted(e["at"] for e in others if e["key"] != skip)
    t = wanted.timestamp()
    for _ in range(len(times) + 1):
        clash = next((x for x in times if abs(t - x) < gap), None)
        if clash is None:
            break
        t = clash + gap
    return datetime.fromtimestamp(t, tz=wanted.tzinfo or timezone.utc)


def last_before(others: list[dict], skip=None) -> dict | None:
    """The latest other Instagram post (what the next caption must not repeat)."""
    rest = [e for e in others if e["key"] != skip]
    return rest[-1] if rest else None


_TAG = re.compile(r"(?<![\w#])#([^\s#]+)")


def tags_of(caption: str) -> set[str]:
    return {t.casefold() for t in _TAG.findall(caption or "")}


def norm(caption: str) -> str:
    return re.sub(r"\s+", " ", (caption or "").strip()).casefold()


def pick_hashtags(tags: list[str], channel: int, last: set[str]) -> list[str]:
    """At most HASHTAGS: the channel's own `channel` tags first, then the clip's others, rotated
    so the chosen set differs from `last` (the previous Instagram post's) when it can."""
    clean = [t.lstrip("#") for t in tags if t.lstrip("#")]
    head, rest = clean[:min(channel, HASHTAGS)], clean[channel:]
    room = HASHTAGS - len(head)
    if room <= 0 or not rest:
        return head
    fresh = [t for t in rest if t.casefold() not in last]
    used = [t for t in rest if t.casefold() in last]
    pick = (fresh + used)[:room]  # tags the last post didn't use come first
    if {t.casefold() for t in head + pick} == last and len(rest) > room:
        pick = rest[1:room + 1]
    return head + pick


# ===================================================================== paused as a target


def pause_once() -> None:
    """1.2.62 (once): Instagram off in the remembered targets and the publish queue."""
    if config.get("ig_paused_at"):
        return
    changes: dict = {"ig_paused_at": time.time()}
    t = config.get("publish_targets")
    if isinstance(t, list) and "reels" in t:
        changes["publish_targets"] = [p for p in t if p != "reels"]
    q = config.get("pubqueue")
    if isinstance(q, dict) and isinstance((q.get("platforms") or {}).get("instagram"), dict):
        q = {**q, "platforms": {**q["platforms"], "instagram": {**q["platforms"]["instagram"], "on": False}}}
        changes["pubqueue"] = q
    config.update(**changes)


ACCOUNT_MESSAGE = {
    "reels": ("Instagram refused this post because of your account: it may be restricted, suspended or "
              "missing a permission.",
              "SharkyClips won't try again by itself and paused your other automatic Instagram posts. Check "
              "Settings > Account status in the Instagram app. When the account is fine again, press Retry."),
    "tiktok": ("TikTok refused this post because of your account: it may be restricted or banned from posting.",
               "SharkyClips won't try again by itself. Check your account in the TikTok app. When it's fine "
               "again, press Retry."),
}


def pause_after_block(app=None) -> int:
    """An account / permission refusal from Instagram: every other automatic Instagram post that
    hasn't gone out is paused (kept, never sent by itself) and Instagram leaves the targets."""
    from . import multipost as M

    app = app or M._app()
    n = 0
    for project in app.list_projects():
        try:
            recs = PF.records(project)
        except Exception:  # noqa: BLE001
            continue
        for cid, plats in (recs or {}).items():
            r = (plats or {}).get("reels") or {}
            if r.get("mode") != "semi" and r.get("status") != "failed" and M._pausable(r):
                M.pause_meta(project, cid, r)
                n += 1
    t = config.get("publish_targets")
    if isinstance(t, list) and "reels" in t:
        config.update(publish_targets=[p for p in t if p != "reels"])
    forget_cache()
    return n
