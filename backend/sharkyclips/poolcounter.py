"""1.2.75 shared-pool counter (prepared, OFF until Google's verification of the built-in client).

Users of the built-in SharkyClips Google client share ONE daily YouTube upload pool. This PC
only knows its own uploads, so without this counter the app says "Shared daily pool" and never
invents a number. With the counter on, it reads the project-wide number from a tiny Cloudflare
Worker (workers/shared-pool/worker.js) that asks Google Cloud Monitoring with a read-only
service account and answers only

    {"used": 50, "limit": 100, "resets_at": "2026-11-28T08:00:00Z"}

What the app sends: a plain GET without parameters, cookies, tokens or IDs (User-Agent
"SharkyClips"). Nothing about the user or their videos. The answer is cached for 5 minutes and
is only shown; a missing or broken answer simply falls back to "Shared daily pool".

Settings (config.json):
  youtube_pool_counter  bool, default DEFAULT_ON (False): ask the Worker at all
  youtube_pool_url      the Worker address (default POOL_URL, empty until the Worker exists);
                        https only (loopback http for tests)
"""

from __future__ import annotations

import threading
import time
import urllib.parse
from datetime import datetime, timezone

from . import config

DEFAULT_ON = False  # flip with the release that follows Google's verification (docs/phase-d5.md)
POOL_URL = ""  # e.g. "https://sharkyclips-pool.<account>.workers.dev/" once deployed
CACHE_S = 300
TIMEOUT_S = 5

_lock = threading.Lock()
_cache: dict = {"at": 0.0, "url": None, "value": None}


def enabled() -> bool:
    v = config.get("youtube_pool_counter")
    return (DEFAULT_ON if v is None else v is True) and bool(url())


def url() -> str | None:
    raw = str(config.get("youtube_pool_url") or POOL_URL or "").strip()
    if not raw:
        return None
    parts = urllib.parse.urlsplit(raw)
    loopback = parts.hostname in ("127.0.0.1", "localhost", "::1")
    if parts.scheme == "https" or (parts.scheme == "http" and loopback):
        if parts.username or parts.password or parts.query or parts.fragment:
            return None
        return raw
    return None


def parse(data: object, now: datetime | None = None) -> dict | None:
    """The Worker's answer, checked: whole numbers, 0 <= used, 0 < limit <= 1e7, a future-ish reset."""
    if not isinstance(data, dict):
        return None
    used, limit, resets = data.get("used"), data.get("limit"), data.get("resets_at")
    if isinstance(used, bool) or isinstance(limit, bool) or not isinstance(used, int) or not isinstance(limit, int):
        return None
    if used < 0 or not 0 < limit <= 10_000_000 or not isinstance(resets, str) or len(resets) > 40:
        return None
    try:
        at = datetime.fromisoformat(resets.replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        return None
    now = now or datetime.now(timezone.utc)
    if not -3600 < (at - now).total_seconds() < 49 * 3600:
        return None
    return {"used": min(used, limit), "limit": limit, "left": max(0, limit - used),
            "resets_at": at.astimezone(timezone.utc).isoformat(timespec="seconds")}


def _fetch(address: str) -> object:
    import requests

    res = requests.get(address, timeout=TIMEOUT_S, allow_redirects=False,
                       headers={"User-Agent": "SharkyClips", "Accept": "application/json"})
    if res.status_code != 200 or len(res.content) > 4096:
        return None
    return res.json()


def read(now: datetime | None = None) -> dict | None:
    """{"used", "limit", "left", "resets_at", "fetched_at"} or None (off, unreachable, broken)."""
    if not enabled():
        return None
    address = url()
    with _lock:
        fresh = _cache["url"] == address and time.monotonic() - _cache["at"] < CACHE_S
        if fresh:
            return _cache["value"]
    try:
        value = parse(_fetch(address), now)
    except Exception:  # noqa: BLE001 - offline / not deployed / bad JSON: "Shared daily pool"
        value = None
    if value is not None:
        value["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _lock:
        _cache.update(at=time.monotonic(), url=address, value=value)
    return value


def clear_cache() -> None:
    with _lock:
        _cache.update(at=0.0, url=None, value=None)
