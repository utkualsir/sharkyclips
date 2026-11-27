"""1.2.75 Uploads stats + honest YouTube quota.

GET /api/uploads/stats            my uploads today / this week / total per platform (uploadstats.py)
GET /api/youtube/quota            today's quota in the words of the client mode (youtube.quota_view)
                                  + the reset time + the owner links (only with the owner setting)
PUT /api/youtube/quota/settings   {"owner_view": bool, "pool_counter": bool, "pool_url": str}

Owner view = a link to the Cloud Console quota page of the built-in client's project, where the
project owner sees the real usage of everybody. It is only a link: no owner credentials exist in
SharkyClips, and the page asks Google for the owner's own sign-in.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Body, HTTPException, Request

from .. import config, poolcounter, uploadstats, youtube
from ..errors import SharkyClipsError

router = APIRouter()

QUOTA_PAGE = "https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas"


def console_url(project_id: str | None) -> str:
    if not project_id:
        return QUOTA_PAGE
    return f"{QUOTA_PAGE}?{urllib.parse.urlencode({'project': project_id})}"


def quota() -> dict:
    q = youtube.quota_view()
    mode = q["mode"]
    own = youtube.load_client() or {}
    shared = youtube.shared_info()
    owner_on = config.get("owner_view") is True
    return {
        "quota": q,
        "mode": mode,
        "connected": youtube.connected(),
        "resets_at": q["resets_at"],
        # the user's own project is theirs: its quota page is always offered
        "own_console_url": console_url(own.get("project_id")) if mode == "own" else None,
        "owner": {"enabled": owner_on,
                  "console_url": console_url(shared.get("project_id")) if owner_on else None},
        "pool_counter": {"enabled": poolcounter.enabled(), "on": config.get("youtube_pool_counter") is True,
                         "url": config.get("youtube_pool_url") or poolcounter.POOL_URL or ""},
    }


@router.get("/api/uploads/stats")
def api_upload_stats() -> dict:
    return uploadstats.stats()


@router.get("/api/youtube/quota")
def api_youtube_quota() -> dict:
    return quota()


@router.put("/api/youtube/quota/settings")
def api_youtube_quota_settings(request: Request, body: dict | None = Body(default=None)) -> dict:
    """Only from this computer: the pool address makes the server fetch a URL (phones on the
    LAN can read the quota, not change where it comes from)."""
    from .app import _is_local

    if not _is_local(request):
        raise HTTPException(403, "Change this on the computer that runs SharkyClips.")
    body = body or {}
    changes: dict = {}
    if "owner_view" in body:
        changes["owner_view"] = body["owner_view"] is True
    if "pool_counter" in body:
        changes["youtube_pool_counter"] = body["pool_counter"] is True
    if "pool_url" in body:
        raw = str(body["pool_url"] or "").strip()[:300]
        if raw:
            old = config.get("youtube_pool_url")
            config.update(youtube_pool_url=raw)
            ok = poolcounter.url() == raw
            if not ok:
                config.update(youtube_pool_url=old)
                raise SharkyClipsError("The pool counter address must start with https:// (no login, no ? part).")
        changes["youtube_pool_url"] = raw or None
    if changes:
        config.update(**changes)
        poolcounter.clear_cache()
    return quota()
