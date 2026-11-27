"""1.2.75 Uploads stats: my uploads today / this week / in total, per platform.

Built from the upload history (history.py), so it counts what SharkyClips shared plus what the
user marked "I posted it". Four groups, in this fixed order (the chart colours follow it):

  youtube  uploaded to YouTube by SharkyClips
  reels    posted to Instagram by SharkyClips
  tiktok   posted to TikTok by SharkyClips
  manual   posted by hand on any platform (the row still says which one)

A manual post counts ONLY under "manual", so the groups add up to the total. Days and weeks are
this computer's local time; a week starts on Monday. Every number comes with the posts behind it
(clip, time, platform, link, status) for the hover details.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from . import history

GROUPS = ("youtube", "reels", "tiktok", "manual")
DAYS = 14  # bars in the chart
DETAIL_MAX = 200  # posts listed for one number (the newest)


def group(row: dict) -> str | None:
    if row.get("manual"):
        return "manual"
    p = row.get("platform")
    return p if p in GROUPS else None


def status(row: dict) -> str:
    if row.get("manual"):
        return "by_hand"
    return "private" if row.get("private") else "published"


def _local(iso: str | None, tz) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at.astimezone(tz)


def _item(row: dict, at: datetime) -> dict:
    return {"key": row.get("key"), "title": row.get("title") or row.get("clip_id"),
            "project_title": row.get("project_title"), "game": row.get("game"),
            "platform": row.get("platform"), "group": group(row), "at": at.isoformat(timespec="seconds"),
            "url": row.get("url"), "status": status(row)}


def _bucket(items: list[dict]) -> dict:
    by = {g: 0 for g in GROUPS}
    for it in items:
        by[it["group"]] += 1
    return {"total": len(items), "by": by,
            "items": sorted(items, key=lambda i: i["at"], reverse=True)[:DETAIL_MAX]}


def stats(now: datetime | None = None, tz=None) -> dict:
    tz = tz or datetime.now().astimezone().tzinfo
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    today: date = now.date()
    week_start = today - timedelta(days=today.weekday())
    first_day = today - timedelta(days=DAYS - 1)
    items: list[dict] = []
    for row in history.load()["posts"]:
        if not isinstance(row, dict) or group(row) is None:
            continue
        at = _local(row.get("at"), tz)
        if at is not None:
            items.append(_item(row, at))
    day_of = {id(i): datetime.fromisoformat(i["at"]).date() for i in items}
    days = []
    for n in range(DAYS):
        d = first_day + timedelta(days=n)
        b = _bucket([i for i in items if day_of[id(i)] == d])
        days.append({"date": d.isoformat(), **b})
    return {
        "groups": list(GROUPS),
        "today": {"from": today.isoformat(), **_bucket([i for i in items if day_of[id(i)] == today])},
        "week": {"from": week_start.isoformat(), **_bucket([i for i in items if week_start <= day_of[id(i)] <= today])},
        "total": {"from": min((i["at"] for i in items), default=None), **_bucket(items)},
        "days": days,
        "generated_at": now.isoformat(timespec="seconds"),
    }
