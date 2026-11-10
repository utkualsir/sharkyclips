"""Kick (kick.com) links: recognise them, read a VOD / clip when yt-dlp can't, and chat replay.

yt-dlp reads Kick VODs and clips itself (kick:vod, kick:clip). This module only adds:

  * parse() / canonical(): every link shape people paste (kick.com/<channel>/videos/<id>,
    kick.com/video/<id>, kick.com/<channel>/clips/<id>, kick.com/<channel>?clip=<id>,
    kick.com/<channel>) -> one canonical URL yt-dlp understands, or a clear message
  * resolve(): the same info from Kick's public web endpoints (no login), used when yt-dlp's
    Kick extractor breaks after a site change
  * chat_rows(): the chat replay of a VOD or clip (Kick's public messages endpoint, which answers
    with ~5 s of chat per call)

Only public endpoints, never a login. Subscriber-only VODs stay unreadable on purpose.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import parse_qs, urlparse

from .errors import SharkyClipsError

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
_UUID = r"[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}"
_RESERVED = {"video", "videos", "categories", "category", "search", "auth", "browse", "following",
             "clips", "dashboard", "settings", "terms-of-service", "privacy-policy", "community-guidelines"}
CHAT_WINDOW = 5.0  # seconds of chat one messages call returns
_EMOTE = re.compile(r"\[emote:\d+:([^\]]*)\]")  # "[emote:37226:KEKW]" -> "KEKW"


def _site() -> str:
    return os.environ.get("SHARKYCLIPS_KICK_ENDPOINT", "https://kick.com").rstrip("/")


def _web() -> str:
    return os.environ.get("SHARKYCLIPS_KICK_WEB_ENDPOINT", "https://web.kick.com").rstrip("/")


@dataclass(frozen=True)
class Link:
    kind: str  # "vod" | "clip" | "channel"
    id: str  # VOD uuid, clip id or channel slug
    channel: str | None = None


def is_kick(url: str) -> bool:
    host = (urlparse(url.strip()).hostname or "").lower()
    return host == "kick.com" or host.endswith(".kick.com")


def parse(url: str) -> Link | None:
    """The kind of Kick link, or None for anything that isn't one."""
    if not is_kick(url):
        return None
    u = urlparse(url.strip())
    parts = [p for p in u.path.split("/") if p]
    clip = (parse_qs(u.query).get("clip") or [None])[0]
    if clip and clip.startswith("clip_"):
        return Link("clip", clip, parts[0].lower() if parts and parts[0].lower() not in _RESERVED else None)
    for i, p in enumerate(parts):
        if re.fullmatch(_UUID, p, re.I) and i > 0 and parts[i - 1].lower() in ("video", "videos"):
            ch = parts[0].lower() if i >= 2 and parts[0].lower() not in _RESERVED else None
            return Link("vod", p.lower(), ch)
        if p.startswith("clip_") and i > 0 and parts[i - 1].lower() == "clips":
            ch = parts[0].lower() if i >= 2 and parts[0].lower() not in _RESERVED else None
            return Link("clip", p, ch)
    if len(parts) == 1 and parts[0].lower() not in _RESERVED and re.fullmatch(r"[\w-]+", parts[0]):
        return Link("channel", parts[0].lower())
    if len(parts) == 2 and parts[1].lower() in ("videos", "clips") and parts[0].lower() not in _RESERVED:
        return Link("channel", parts[0].lower())
    return None


# ------------------------------------------------------------------- HTTP


def _http():
    import requests

    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    return s


def _json(http, method: str, url: str, **kw) -> dict:
    last = None
    for attempt in range(5):
        try:
            r = http.request(method, url, timeout=30, **kw)
            if r.status_code == 404:
                return {}
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"HTTP {r.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except ValueError as exc:  # not JSON: a Cloudflare challenge page
            last = f"unexpected answer ({exc})"
            time.sleep(1.5 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - network hiccup: back off and retry
            last = str(exc)[:200]
            time.sleep(1.5 * (attempt + 1))
    raise SharkyClipsError(f"Kick isn't answering right now ({last}).", "Try again in a few minutes.")


def _channel(http, slug: str) -> dict:
    data = _json(http, "GET", f"{_site()}/api/v2/channels/{slug}")
    if not data.get("id"):
        raise SharkyClipsError(f"Kick has no channel called '{slug}'.", "Check the link.")
    return data


def _vod_entry(http, creator_id: str | int, vod_id: str) -> dict:
    videos = _json(http, "GET", f"{_web()}/api/v1/channels/{creator_id}/videos").get("data") or []
    return next((v for v in videos if str(v.get("id")) == vod_id), {})


def _playback(http, vod_id: str) -> dict:
    return _json(http, "POST", f"{_web()}/api/v1/stream/{vod_id}/playback",
                 json={"video_player": {"player": {}}, "video_session": {},
                       "user_session": {"non_personalised_ads": True}})


def _clip(http, clip_id: str) -> dict:
    data = _json(http, "GET", f"{_site()}/api/v2/clips/{clip_id}")
    clip = data.get("clip") or {}
    if not clip.get("id"):
        raise SharkyClipsError("Kick has no clip with that link (deleted or wrong link).", "Check the link.")
    return clip


def _date(iso: str | None) -> str | None:
    return iso[:10].replace("-", "") if iso else None


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00").replace(" ", "T")).astimezone(timezone.utc)


# ------------------------------------------------------------------- links


def canonical(url: str, http=None) -> str:
    """A URL yt-dlp's Kick extractors accept. Raises with a clear message for channel links."""
    link = parse(url)
    if link is None:
        return url
    if link.kind == "channel":
        raise SharkyClipsError(
            "That's a Kick channel, not a video.",
            f"Open kick.com/{link.id}/videos (or /clips), pick one, and paste that link. "
            "Live streams work once they've ended and the VOD is up.")
    if link.channel:
        kind = "videos" if link.kind == "vod" else "clips"
        return f"https://kick.com/{link.channel}/{kind}/{link.id}"
    # kick.com/video/<id>: yt-dlp needs the channel in the path
    http = http or _http()
    if link.kind == "vod":
        creator = ((_playback(http, link.id).get("video_session") or {}).get("creator_id"))
        slug = ((_vod_entry(http, creator, link.id).get("channel") or {}).get("slug")) if creator else None
    else:
        slug = (_clip(http, link.id).get("channel") or {}).get("slug")
    if not slug:
        raise SharkyClipsError("Kick has no video with that link (deleted, expired or wrong link).",
                               "Kick keeps VODs for a limited time. Check the link on kick.com.")
    return f"https://kick.com/{slug}/{'videos' if link.kind == 'vod' else 'clips'}/{link.id}"


def resolve(url: str, http=None) -> dict:
    """VOD / clip info from Kick's public endpoints (yt-dlp-like keys + "media_url": an HLS playlist)."""
    link = parse(canonical(url, http))
    assert link is not None and link.kind in ("vod", "clip")
    http = http or _http()
    if link.kind == "clip":
        c = _clip(http, link.id)
        ch = c.get("channel") or {}
        return {"id": c["id"], "title": c.get("title") or c["id"], "duration": c.get("duration"),
                "uploader": ch.get("username"), "uploader_id": ch.get("slug"),
                "upload_date": _date(c.get("created_at")), "extractor_key": "KickClip",
                "webpage_url": f"https://kick.com/{ch.get('slug')}/clips/{c['id']}",
                "media_url": c.get("video_url") or c.get("clip_url"),
                "categories": [(c.get("category") or {}).get("name")] if c.get("category") else []}
    pb = _playback(http, link.id)
    err = pb.get("data") if isinstance(pb.get("data"), dict) else None
    creator = (pb.get("video_session") or {}).get("creator_id")
    if err or not creator:
        raise SharkyClipsError("Kick won't play this VOD without an account (subscriber-only, deleted or expired).",
                               "SharkyClips doesn't log in to sites. Download the video yourself and import the file.")
    v = _vod_entry(http, creator, link.id)
    ch = v.get("channel") or {}
    m3u8 = (pb.get("playback_url") or {}).get("vod")
    if not m3u8:
        raise SharkyClipsError("This Kick VOD is for subscribers only.",
                               "SharkyClips doesn't log in to sites. Download the video yourself and import the file.")
    return {"id": link.id, "title": v.get("title") or link.id, "duration": v.get("duration"),
            "uploader": ch.get("username"), "uploader_id": ch.get("slug") or link.channel,
            "upload_date": _date(v.get("start_time")), "extractor_key": "KickVOD",
            "webpage_url": f"https://kick.com/{ch.get('slug') or link.channel}/videos/{link.id}",
            "media_url": m3u8, "is_live": bool(v.get("is_live")),
            "categories": [(v.get("category") or {}).get("name")] if v.get("category") else []}


# --------------------------------------------------------------- chat replay


def chat_plan(url: str, duration: float, http=None) -> tuple[int, datetime, float] | None:
    """(chatroom id, wall-clock time of video second 0, length) or None when Kick has no replay."""
    link = parse(url)
    if link is None or link.kind == "channel":
        return None
    http = http or _http()
    if link.kind == "clip":
        c = _clip(http, link.id)
        start, length = c.get("started_at"), float(c.get("duration") or duration or 0)
        slug = (c.get("channel") or {}).get("slug") or link.channel
    else:
        slug = link.channel
        if not slug:
            slug = parse(canonical(url, http)).channel  # type: ignore[union-attr]
        ch = _channel(http, slug)
        v = _vod_entry(http, ch["id"], link.id)
        start, length = v.get("start_time"), float(duration or v.get("duration") or 0)
    if not start or not slug:
        return None
    chat_id = (_channel(http, slug).get("chatroom") or {}).get("id")
    return (int(chat_id), _ts(start), length) if chat_id else None


def _window(http, chat_id: int, at: datetime) -> list[dict]:
    t = at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    data = _json(http, "GET", f"{_site()}/api/v2/channels/{chat_id}/messages", params={"start_time": t})
    return ((data.get("data") or {}).get("messages")) or []


def chat_segment(chat_id: int, t0: datetime, a: float, b: float,
                 on_page: Callable[[float], None] = lambda t: None, http=None) -> list[tuple[float, str, str]]:
    """Messages with a <= t < b (video seconds). One call per ~5 s window, ids de-duplicated."""
    http = http or _http()
    rows: list[tuple[float, str, str]] = []
    seen: set[str] = set()
    t = a
    while t < b:
        for m in _window(http, chat_id, t0 + timedelta(seconds=t)):
            mid = str(m.get("id") or "")
            if mid in seen or m.get("type", "message") != "message" or not m.get("created_at"):
                continue
            off = (_ts(m["created_at"]) - t0).total_seconds()
            if not (a <= off < b):
                continue
            seen.add(mid)
            text = _EMOTE.sub(r"\1", str(m.get("content") or ""))
            rows.append((off, text, str((m.get("sender") or {}).get("slug") or "")))
        t += CHAT_WINDOW
        on_page(t)
    return rows
