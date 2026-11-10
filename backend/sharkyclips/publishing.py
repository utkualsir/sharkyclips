"""Publishing plan (1.2.7): which clip goes to YouTube when, across all projects.

Scheduling uses YouTube's own scheduled publishing: a clip is uploaded as private with a
`publishAt` time, and YouTube makes it public at that time, so the PC doesn't have to be on
then. SharkyClips uploads in advance whenever the PC is on and the governor allows work
(web/publishing.py runs that loop).

Store: ~/.sharkyclips/publish/plan.json  {"version": 1, "items": {"<project>:<clip>": item}}

  item = {"project_id", "clip_id",
          "meta":        everything of the publish setup (title, description, hashtags, tags,
                         category, language, made_for_kids, privacy, playlist, cover, preset ...),
          "publish_at":  UTC ISO time YouTube makes it public (None = not scheduled),
          "now":         "Publish now": upload at once with meta.privacy,
          "video_id", "uploaded_at",
          "attempts", "next_try_at", "error": {message, hint, fix}, "attention": needs the user,
          "prep":        the files made for it {sig, export, file, cover_file, pending: {...}},
          "moved_from":  the time it had before a missed slot / full day moved it,
          "created_at", "updated_at"}

The daily limit counts releases per local calendar day: scheduled clips, clips published now
and clips that went public through a manual upload. It never goes above what Google's daily API
quota can upload (1 upload + thumbnail + playlist = 1,700 units).
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from statistics import median

from . import config
from .errors import SharkyClipsError
from .project import read_json, write_json_atomic

DEFAULT_LIMIT = 3
DEFAULT_TIMES = ["12:00", "18:00", "21:00"]
# More times, in the order they are used when the daily limit is above the listed times.
EXTRA_TIMES = ["15:00", "19:30", "10:00", "22:30", "13:30", "16:30", "09:00", "20:15", "11:00", "17:15"]
MIN_GAP_MIN = 45  # two releases on the same day are at least this far apart
LEAD_MIN = 15  # a release needs this much time ahead (upload + YouTube processing)
LEARN_MIN_VIDEOS = 10  # calibration entries with a publish time before the times are learned
LEARN_MIN_PER_HOUR = 2
BACKOFF_S = [60, 300, 900, 3600, 3 * 3600]  # then: needs attention
PER_UPLOAD_UNITS = 1600 + 50 + 50
FIXES = ("retry", "reconnect", "edit", "rerender", "reschedule", "wait")

_lock = threading.RLock()


def folder() -> Path:
    return config.config_dir() / "publish"


def plan_path() -> Path:
    return folder() / "plan.json"


def key_of(project_id: str, clip_id: str) -> str:
    return f"{project_id}:{clip_id}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds") if dt else None


def parse(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.astimezone()  # naive = this PC's local time


# ------------------------------------------------------------------ store


def load() -> dict[str, dict]:
    with _lock:
        try:
            data = read_json(plan_path()) if plan_path().is_file() else {}
        except Exception:  # noqa: BLE001 - a broken file starts an empty plan (it's rewritten)
            data = {}
        items = data.get("items") or {}
        return items if isinstance(items, dict) else {}


def _save(items: dict[str, dict]) -> None:
    write_json_atomic(plan_path(), {"version": 1, "items": items})


def get(key: str) -> dict | None:
    return load().get(key)


def put(item: dict) -> dict:
    with _lock:
        items = load()
        item = {**item, "updated_at": iso(now_utc())}
        item.setdefault("created_at", item["updated_at"])
        items[key_of(item["project_id"], item["clip_id"])] = item
        _save(items)
        return item


def patch(key: str, **changes) -> dict | None:
    with _lock:
        items = load()
        it = items.get(key)
        if it is None:
            return None
        it.update(changes)
        it["updated_at"] = iso(now_utc())
        _save(items)
        return it


def remove(key: str) -> None:
    with _lock:
        items = load()
        if items.pop(key, None) is not None:
            _save(items)


def new_item(project_id: str, clip_id: str, meta: dict) -> dict:
    return {"project_id": project_id, "clip_id": clip_id, "meta": meta, "publish_at": None, "now": False,
            "video_id": None, "uploaded_at": None, "attempts": 0, "next_try_at": None, "error": None,
            "attention": False, "prep": {}, "moved_from": None}


def unschedule(item: dict) -> dict:
    """Back to a draft (keeps the metadata)."""
    return {**item, "publish_at": None, "now": False, "video_id": None, "uploaded_at": None, "attempts": 0,
            "next_try_at": None, "error": None, "attention": False, "moved_from": None}


# ------------------------------------------------------------------ settings


def daily_limit() -> int:
    try:
        return max(1, min(50, int(config.get("publish_daily_limit") or DEFAULT_LIMIT)))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


def quota_capacity() -> int:
    """Uploads Google's daily API quota allows (upload + thumbnail + playlist each)."""
    from . import youtube

    return max(1, youtube.daily_quota() // PER_UPLOAD_UNITS)


def effective_limit() -> int:
    return max(1, min(daily_limit(), quota_capacity()))


def _hhmm(v: str) -> str | None:
    try:
        h, m = str(v).strip().split(":")
        h, m = int(h), int(m)
    except ValueError:
        return None
    return f"{h:02d}:{m:02d}" if 0 <= h < 24 and 0 <= m < 60 else None


def configured_times() -> list[str]:
    raw = config.get("publish_times") or DEFAULT_TIMES
    out = sorted({t for t in (_hhmm(x) for x in raw) if t})
    return out or list(DEFAULT_TIMES)


def _minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _spread(times: list[str], n: int) -> list[str]:
    """`times` filled up to n with extra times that keep MIN_GAP_MIN apart."""
    out = list(dict.fromkeys(times))[:n] if len(times) >= n else list(dict.fromkeys(times))
    for t in EXTRA_TIMES + [f"{h:02d}:00" for h in range(8, 24)]:
        if len(out) >= n:
            break
        if all(abs(_minutes(t) - _minutes(o)) >= MIN_GAP_MIN for o in out):
            out.append(t)
    return sorted(out)


def learned_hours(entries: list[dict] | None = None) -> dict:
    """Release hours that got the most views on this channel (calibration data: YouTube's views
    of clips published at least 2 days ago). Ranked by the median of log views per local hour."""
    from . import calibration

    if entries is None:
        entries = list((calibration.load().get("entries") or {}).values())
    by_hour: dict[int, list[float]] = {}
    n = 0
    for e in entries:
        t = parse(e.get("published_at"))
        if t is None or e.get("views") is None:
            continue
        n += 1
        by_hour.setdefault(t.astimezone().hour, []).append(math.log10(int(e["views"]) + 1))
    if n < LEARN_MIN_VIDEOS:
        return {"samples": n, "hours": []}
    ranked = sorted(((median(v), h) for h, v in by_hour.items() if len(v) >= LEARN_MIN_PER_HOUR), reverse=True)
    return {"samples": n, "hours": [h for _m, h in ranked]}


def best_times(n: int | None = None, entries: list[dict] | None = None) -> dict:
    """The release times of a day: learned from this channel's results once there is enough
    data (config publish_learn_times), else the configured times (default 12:00, 18:00, 21:00)."""
    n = n or effective_limit()
    base = configured_times()
    learned = learned_hours(entries) if config.get("publish_learn_times") is not False else {"samples": 0, "hours": []}
    times: list[str] = []
    for h in learned["hours"]:
        t = f"{h:02d}:00"
        if all(abs(_minutes(t) - _minutes(o)) >= MIN_GAP_MIN for o in times):
            times.append(t)
        if len(times) >= n:
            break
    source = "learned" if times else "default" if base == DEFAULT_TIMES else "custom"
    if len(times) < n:
        for t in base:
            if len(times) >= n:
                break
            if all(abs(_minutes(t) - _minutes(o)) >= MIN_GAP_MIN for o in times):
                times.append(t)
    times = _spread(sorted(times), n)
    return {"times": times, "source": source, "samples": learned["samples"], "configured": base}


# ------------------------------------------------------------------ days and slots


def local_day(dt: datetime) -> date:
    return dt.astimezone().date()


def at_local(day: date, hhmm: str) -> datetime:
    h, m = hhmm.split(":")
    return datetime.combine(day, dtime(int(h), int(m))).astimezone()  # this PC's zone, DST-aware


def releases(items: dict[str, dict], uploads: dict[str, dict], now: datetime | None = None) -> dict[str, datetime]:
    """When each clip is / was released (public or unlisted). uploads: key -> live upload entry."""
    now = now or now_utc()
    out: dict[str, datetime] = {}
    for key, u in uploads.items():
        if u.get("publish_at"):  # scheduled on YouTube (goes public then)
            when = parse(u["publish_at"])
        elif (u.get("requested_privacy") or u.get("privacy")) in ("public", "unlisted"):
            when = parse(u.get("published_at")) or parse(u.get("uploaded_at"))
        else:  # a private upload isn't a release
            when = None
        if when is not None:
            out[key] = when
    for key, it in items.items():
        if key in out:
            continue
        if it.get("publish_at"):
            t = parse(it["publish_at"])
            if t:
                out[key] = t
        elif it.get("now") and (it.get("meta") or {}).get("privacy", "public") != "private":
            out[key] = now
    return out


def day_counts(rel: dict[str, datetime], skip: set[str] | None = None) -> dict[date, int]:
    counts: dict[date, int] = {}
    for key, t in rel.items():
        if skip and key in skip:
            continue
        d = local_day(t)
        counts[d] = counts.get(d, 0) + 1
    return counts


def _taken(rel: dict[str, datetime], skip: set[str]) -> list[datetime]:
    return [t for k, t in rel.items() if k not in skip]


def free(t: datetime, rel: dict[str, datetime], limit: int, skip: set[str] | None = None) -> bool:
    skip = skip or set()
    if day_counts(rel, skip).get(local_day(t), 0) >= limit:
        return False
    return all(abs((t - o).total_seconds()) >= MIN_GAP_MIN * 60 for o in _taken(rel, skip))


def next_free_slot(after: datetime, rel: dict[str, datetime], limit: int | None = None,
                   times: list[str] | None = None, skip: set[str] | None = None,
                   max_days: int = 400) -> datetime:
    """The first release time at or after `after` on a day that still has room."""
    limit = limit or effective_limit()
    times = times or best_times(limit)["times"]
    skip = skip or set()
    day = local_day(after)
    for _ in range(max_days):
        for hhmm in times:
            t = at_local(day, hhmm)
            if t >= after and free(t, rel, limit, skip):
                return t
        day += timedelta(days=1)
    raise SharkyClipsError("No free release slot in the next year.", "Raise the daily limit in Settings.")


def earliest(now: datetime | None = None) -> datetime:
    return (now or now_utc()) + timedelta(minutes=LEAD_MIN)


def place(key: str, wanted: datetime, rel: dict[str, datetime], limit: int | None = None,
          times: list[str] | None = None, now: datetime | None = None, strict: bool = False) -> tuple[datetime, bool]:
    """A time the user picked for one clip. A full day (or a time too close to another release)
    moves it to the next free slot, unless strict (calendar drag: then it's refused)."""
    limit = limit or effective_limit()
    if wanted < earliest(now):
        raise SharkyClipsError("Pick a time at least 15 minutes from now.",
                               "YouTube needs time to take the upload before it goes public.")
    if free(wanted, rel, limit, {key}):
        return wanted, False
    if strict:
        n = day_counts(rel, {key}).get(local_day(wanted), 0)
        if n >= limit:
            raise SharkyClipsError(f"That day is full ({n}/{limit} releases).",
                                   "Pick another day or raise the daily limit in Settings.")
        raise SharkyClipsError(f"Another clip goes out within {MIN_GAP_MIN} minutes of that time.",
                               "Pick a time further apart.")
    return next_free_slot(wanted, rel, limit, times, skip={key}), True


def auto_plan(keys: list[str], rel: dict[str, datetime], now: datetime | None = None,
              limit: int | None = None, times: list[str] | None = None) -> dict[str, datetime]:
    """Spread clips over the next free slots, `limit` a day at the best times."""
    limit = limit or effective_limit()
    times = times or best_times(limit)["times"]
    rel = {k: v for k, v in rel.items() if k not in keys}
    out: dict[str, datetime] = {}
    after = earliest(now)
    for k in keys:
        t = next_free_slot(after, rel, limit, times)
        out[k] = t
        rel[k] = t
    return out


# ------------------------------------------------------------------ failures


def classify(exc: BaseException) -> dict:
    """What to do after a failed step: {fix, retry_in (seconds) | None, wait_until, count}.
    count = it uses up one of the automatic retries."""
    reason = getattr(exc, "reason", None)
    status = getattr(exc, "status", None)
    if reason in ("quotaExceeded", "uploadLimitExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
        from . import youtube

        until = youtube.next_reset() if reason != "rateLimitExceeded" else now_utc() + timedelta(minutes=15)
        return {"fix": "wait", "retry_in": None, "wait_until": iso(until), "count": False}
    if reason in ("signed_out", "not_connected", "refresh_failed", "scope", "insufficientPermissions",
                  "ACCESS_TOKEN_SCOPE_INSUFFICIENT", "youtubeSignupRequired", "forbidden", "accessNotConfigured"):
        return {"fix": "reconnect", "retry_in": None, "wait_until": None, "count": False}
    if reason == "invalidPublishAt":
        return {"fix": "reschedule", "retry_in": 0, "wait_until": None, "count": False}
    if reason in ("file", "render"):
        return {"fix": "rerender", "retry_in": 60, "wait_until": None, "count": True}
    if status in (400, 403) or reason in ("invalidTitle", "invalidDescription", "invalidTags",
                                          "invalidCategoryId", "invalidVideoMetadata", "mediaBodyRequired"):
        return {"fix": "edit", "retry_in": None, "wait_until": None, "count": False}
    return {"fix": "retry", "retry_in": 60, "wait_until": None, "count": True}  # network, 5xx, unknown


def after_failure(item: dict, exc: BaseException, now: datetime | None = None) -> dict:
    """The item after a failed step: retry later with backoff, or needs attention."""
    now = now or now_utc()
    c = classify(exc)
    msg = getattr(exc, "message", None) or str(exc) or type(exc).__name__
    hint = getattr(exc, "hint", None)
    attempts = int(item.get("attempts") or 0) + (1 if c["count"] else 0)
    out = {**item, "attempts": attempts, "error": {"message": str(msg)[:400], "hint": hint, "fix": c["fix"],
                                                   "at": iso(now)}}
    if c["wait_until"]:
        out.update(next_try_at=c["wait_until"], attention=False)
    elif c["retry_in"] is not None and attempts <= len(BACKOFF_S):
        delay = BACKOFF_S[min(attempts, len(BACKOFF_S)) - 1] if c["count"] else c["retry_in"]
        out.update(next_try_at=iso(now + timedelta(seconds=delay)), attention=False)
    else:
        out.update(next_try_at=None, attention=True)
    return out


def due(item: dict, now: datetime | None = None) -> bool:
    if item.get("attention") or item.get("video_id"):
        return False
    if not (item.get("publish_at") or item.get("now")):
        return False
    t = parse(item.get("next_try_at"))
    return t is None or t <= (now or now_utc())


# ------------------------------------------------------------------ helpers


def signature(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def split_hashtags(description: str) -> tuple[str, list[str]]:
    """The AI description ends with a line of #hashtags: return (text, hashtags)."""
    lines = (description or "").rstrip().split("\n")
    tags: list[str] = []
    while lines and lines[-1].strip() and all(w.startswith("#") for w in lines[-1].split()):
        tags = lines.pop().split() + tags
    return "\n".join(lines).rstrip(), tags


def compose_description(text: str, hashtags: list[str], credit: str | None = None, lang: str | None = None,
                        socials: bool = True, short: bool = False) -> str:
    """The YouTube description: the text, the music credit, the hashtags (channel tag first),
    then the channel's socials block from the Brand kit (once; its heading in `lang`).
    My style: the socials block comes before the labelled hashtags, and Shorts (short=True)
    get it only when the creator turned it on."""
    from .edit import brand
    from .titles import style

    if style.layout(lang) is not None:
        body, tail = brand.split_tail_hashtags(text or "")
        before, block = brand.split_socials(body)
        out = before.strip()
        if credit and credit not in out:
            out = f"{out}\n\n{credit}".strip()
        tags = [("#" + h.lstrip("#")).replace(" ", "") for h in hashtags if h.strip("# ")] or tail
        if block:
            out = f"{out}\n\n{block}"
        full = f"{out}\n\n{' '.join(tags)}".strip() if tags else out
        if not socials and not block:
            lay = style.layout(lang)
            return f"{out}\n\n{lay['label']}\n{' '.join(tags)}".strip() if tags else out
        return brand.with_socials(full, lang, limit=4900, short=short)
    body, block = brand.split_socials(text or "")
    out = body.strip()
    tags = " ".join(("#" + h.lstrip("#")).replace(" ", "") for h in hashtags if h.strip("# "))
    if credit and credit not in out:
        out = f"{out}\n\n{credit}".strip()
    if tags:
        out = f"{out}\n\n{tags}".strip()
    if block:  # the user's own block (typed into the description) stays, at the end
        return f"{out}\n\n{block}".strip()
    return brand.with_socials(out, lang, limit=4900) if socials else out


def suggest_tags(pub: dict, meta: dict, mode: str) -> list[str]:
    """YouTube tags: the ones the analysis built (game bank: game variants, names, events, TR + EN
    search phrases, channel). Older analyses: from the hashtags + topic, without other games."""
    from . import youtube
    from .edit import brand
    from .titles import banks

    if pub.get("tags"):
        return youtube.clean_tags(list(pub["tags"]))
    gid = (pub.get("game") or {}).get("id")
    out: list[str] = []
    for h in pub.get("hashtags") or []:
        w = str(h).lstrip("#").strip()
        if w:
            out.append(w)
    game = (meta.get("game") or {}).get("name") if isinstance(meta.get("game"), dict) else meta.get("game")
    if game in ("auto", "other"):
        game = None
    for extra in (game, pub.get("topic"), {"gaming": "gaming", "study": "study", "music": "music"}.get(mode),
                  *brand.channel_names(), "shorts", "highlights", "clips"):
        if extra:
            out.append(str(extra))
    if gid:
        out = [t for t in out if not banks.other_game(t, gid)]
    return youtube.clean_tags(out)


