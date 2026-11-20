"""Channel monitoring (1.2.57): connect a Kick / Twitch / YouTube channel once; when a stream
ends, its VOD is downloaded and clipped by the normal Easy pipeline. No OBS recording needed.

Everything here is about WHAT to do; web/channels_api.py runs it (the background thread, the
import jobs, the API). The engine is a pure function of the channel list, the platform answers
and a clock, so the tests drive it with fake endpoints and fake time.

Sources (public, no login, no cookies; docs/channel-monitor.md explains the choices)
  kick     kick.com/api/v2/channels/<slug>            name, avatar, live
           kick.com/api/v2/channels/<slug>/videos     past + current streams (is_live, video.uuid,
                                                      status, duration ms, category)
  twitch   gql.twitch.tv (Twitch's public web client id, the one chat.py uses): user, stream,
           the last 20 archives (status RECORDING while live)
  youtube  the channel page once (id, name, avatar), then the public RSS feed
           (feeds/videos.xml, newest 15), and yt-dlp metadata for each new entry
           (live_status: is_live / post_live / was_live / not_live, availability)

Rules
  * A new channel never processes its back catalog: VODs that already ended when it was added
    are stored as "baseline" (the "Import the last N streams" button can take them).
  * Every VOD is stored by "<platform>:<id>" for good: it is never downloaded twice.
  * Polling: every 5 min while live / just ended / a VOD is still processing, every 30 min
    otherwise, +-10 % jitter; errors back off 5 min * 2^n up to 6 h; HTTP 429 honours Retry-After.
  * One download at a time, oldest first (catch-up after the PC was off or asleep).
  * Before a download: free disk space, metered connection (optional), a running game.
"""

from __future__ import annotations

import os
import random
import re
import shutil
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlparse
from xml.etree import ElementTree

from . import config
from .errors import SharkyClipsError
from .project import read_json, write_json_atomic

PLATFORMS = ("kick", "twitch", "youtube")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0 Safari/537.36")
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Twitch's public web client id (chat.py too)

LIVE_EVERY_S = 5 * 60  # live, just ended, or a VOD is still processing
IDLE_EVERY_S = 30 * 60
ENDED_FAST_S = 3 * 3600  # after a stream ends, look every 5 min this long (late VODs)
BACKOFF_BASE_S = 5 * 60
BACKOFF_MAX_S = 6 * 3600
MISSING_POLLS = 3  # a VOD gone from the list this many times in a row = deleted
MAX_ATTEMPTS = 4  # download tries per VOD (resumable: each try continues the last)
RETRY_BASE_S = 15 * 60
MIN_FREE_GB = 5.0  # always left free on the projects drive
BYTES_PER_S = 1_000_000  # 1080p60 VOD + audio.wav + margin (~3.6 GB / hour)
DEFAULT_KEEP_DAYS = 7  # the downloaded VOD -> trash this long after its clips are ready
DEFAULT_MIN_MINUTES = 5.0
WAKE_GAP_S = 5 * 60  # the loop slept this much longer than planned: the PC was asleep
VERIFY_MIN = 0.9  # a download shorter than 90 % of the stream's length is incomplete

# status -> group (the UI's chips)
WAITING = ("queued", "retry", "waiting_disk", "waiting_metered", "waiting_game")
WATCHING = ("live", "processing", "upcoming")
FINAL = ("done", "skipped", "gone", "error", "baseline")

_lock = threading.RLock()


# ===================================================================== store


def state_path() -> Path:
    return config.config_dir() / "channels.json"


def _empty() -> dict:
    return {"version": 1, "channels": {}, "vods": {}, "log": []}


def load() -> dict:
    with _lock:
        p = state_path()
        try:
            data = read_json(p) if p.is_file() else {}
        except (OSError, ValueError):
            data = {}
        out = _empty()
        out["channels"] = dict(data.get("channels") or {})
        out["vods"] = dict(data.get("vods") or {})
        out["log"] = list(data.get("log") or [])[-200:]
        return out


def save(data: dict) -> None:
    with _lock:
        vods = data.get("vods") or {}
        if len(vods) > 3000:  # never drop done / downloading ones (they guard against doubles)
            drop = sorted((k for k, v in vods.items() if v.get("status") in ("baseline", "skipped", "gone")),
                          key=lambda k: float(vods[k].get("first_seen") or 0))[: len(vods) - 2500]
            for k in drop:
                vods.pop(k, None)
        data["log"] = (data.get("log") or [])[-200:]
        write_json_atomic(state_path(), data)


def log(data: dict, kind: str, channel: str | None = None, vod: str | None = None, note: str = "",
        now: float | None = None) -> None:
    data.setdefault("log", []).append({"at": now or time.time(), "kind": kind, "channel": channel, "vod": vod,
                                       "note": str(note)[:300]})


def settings() -> dict:
    """The monitor's global settings (Settings > Channels)."""
    def num(key: str, default: float, lo: float, hi: float) -> float:
        try:
            v = float(config.get(key))
        except (TypeError, ValueError):
            return default
        return max(lo, min(hi, v))

    return {"pause_metered": config.get("channel_pause_metered") is not False,
            "min_free_gb": num("channel_min_free_gb", MIN_FREE_GB, 1, 500),
            "min_minutes": num("channel_min_minutes", DEFAULT_MIN_MINUTES, 0, 240),
            "pause_games": config.get("channel_pause_games") is not False}


# ===================================================================== HTTP (polite, IPv4 fallback)

_V4 = {"only": False}


def ipv4_only() -> bool:
    """True once an IPv6 connection timed out and IPv4 worked (a broken IPv6 route makes every
    request wait for the IPv6 timeout first; the dev PC has one). yt-dlp gets source_address too."""
    return _V4["only"]


def _force_ipv4() -> None:
    if _V4["only"]:
        return
    try:
        import urllib3.util.connection as uc

        uc.allowed_gai_family = lambda: socket.AF_INET  # type: ignore[assignment]
        _V4["only"] = True
    except Exception:  # noqa: BLE001
        pass


class Http:
    """requests with short connect timeouts, one IPv4 fallback and HTTP 429 handling.
    Tests replace `channels.HTTP` with a fake that has the same `get` / `post`."""

    def __init__(self):
        self._s = None

    def _session(self):
        if self._s is None:
            import requests

            s = requests.Session()
            s.headers.update({"User-Agent": UA, "Accept-Language": "en"})
            self._s = s
        return self._s

    def request(self, method: str, url: str, **kw) -> "Resp":
        from . import netguard

        netguard.check_public_url(url)
        import requests

        kw.setdefault("timeout", (6, 30))
        _probe_v6(url)
        for attempt in range(2):
            try:
                r = self._session().request(method, url, **kw)
                return Resp(r.status_code, r.content, dict(r.headers))
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == 0 and not _V4["only"] and _has_v6(url):
                    _force_ipv4()
                    continue
                raise NetError(f"{urlparse(url).hostname}: {type(exc).__name__}") from exc
        raise NetError(urlparse(url).hostname or url)

    def get(self, url: str, **kw) -> "Resp":
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> "Resp":
        return self.request("POST", url, **kw)


def _probe_v6(url: str) -> None:
    """Once per run: the host has an IPv6 address but an IPv6 connection doesn't come up within
    2.5 s while IPv4 does -> IPv4 only (else every new connection waits for the IPv6 timeout;
    urllib3 tries the addresses one by one, so nothing fails, it is only slow)."""
    if _V4["only"] or _V4.get("probed"):
        return
    _V4["probed"] = True
    host = urlparse(url).hostname
    try:
        v6 = [a[4] for a in socket.getaddrinfo(host, 443, socket.AF_INET6, socket.SOCK_STREAM)]
        v4 = [a[4] for a in socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)]
    except OSError:
        return
    if not v6 or not v4:
        return

    def ok(addr, fam) -> bool:
        try:
            with socket.socket(fam, socket.SOCK_STREAM) as s:
                s.settimeout(2.5)
                s.connect(addr)
            return True
        except OSError:
            return False

    if not ok(v6[0], socket.AF_INET6) and ok(v4[0], socket.AF_INET):
        _force_ipv4()


def _has_v6(url: str) -> bool:
    try:
        return any(a[0] == socket.AF_INET6 for a in socket.getaddrinfo(urlparse(url).hostname, 443))
    except OSError:
        return False


@dataclass
class Resp:
    status: int
    body: bytes
    headers: dict

    def json(self) -> Any:
        import json

        return json.loads(self.body.decode("utf-8", "replace"))

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


class NetError(Exception):
    """The platform didn't answer (network, 5xx, Cloudflare page): try again later."""

    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


HTTP: Any = Http()


def _json(resp: Resp, what: str) -> Any:
    if resp.status == 429:
        ra = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
        try:
            wait = float(ra) if ra else None
        except ValueError:
            wait = None
        raise NetError(f"{what}: rate limited (HTTP 429)", retry_after=wait)
    if resp.status >= 500 or resp.status in (403, 408):
        raise NetError(f"{what}: HTTP {resp.status}")
    try:
        return resp.json()
    except ValueError as exc:
        raise NetError(f"{what}: unexpected answer (not JSON)") from exc


# ===================================================================== parsing what people type


def _kick_site() -> str:
    return os.environ.get("SHARKYCLIPS_KICK_ENDPOINT", "https://kick.com").rstrip("/")


def _twitch_gql() -> str:
    return os.environ.get("SHARKYCLIPS_TWITCH_GQL", "https://gql.twitch.tv/gql")


def _yt_site() -> str:
    return os.environ.get("SHARKYCLIPS_YT_WEB", "https://www.youtube.com").rstrip("/")


def parse(text: str, platform: str | None = None) -> tuple[str, str]:
    """(platform, handle) from a URL or a name. A bare name uses `platform` (Kick by default)."""
    t = str(text or "").strip()
    if not t:
        raise SharkyClipsError("Type a channel link or name.", "e.g. kick.com/yourname")
    if not re.match(r"^https?://", t, re.I) and re.match(r"^(www\.|m\.)?(kick\.com|twitch\.tv|youtube\.com|youtu\.be)/", t, re.I):
        t = "https://" + t
    if re.match(r"^https?://", t, re.I):
        u = urlparse(t)
        host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        parts = [p for p in u.path.split("/") if p]
        if host == "kick.com" and parts:
            return "kick", _check("kick", parts[0])
        if host == "twitch.tv" and parts:
            return "twitch", _check("twitch", parts[0])
        if host == "youtube.com" and parts:
            if parts[0] == "channel" and len(parts) > 1:
                return "youtube", _check("youtube", parts[1])
            if parts[0].startswith("@"):
                return "youtube", _check("youtube", parts[0])
            if parts[0] in ("c", "user") and len(parts) > 1:
                return "youtube", _check("youtube", f"{parts[0]}/{parts[1]}")
        raise SharkyClipsError("That isn't a Kick, Twitch or YouTube channel link.",
                               "e.g. kick.com/name, twitch.tv/name or youtube.com/@name")
    p = platform if platform in PLATFORMS else "kick"
    name = t.lstrip("#")
    if p == "youtube" and not name.startswith(("@", "UC")):
        name = "@" + name.lstrip("@")
    return p, _check(p, name.lstrip("@") if p != "youtube" else name)


def _check(platform: str, handle: str) -> str:
    h = handle.strip()
    ok = {"kick": r"[A-Za-z0-9_-]{2,40}", "twitch": r"[A-Za-z0-9_]{3,25}",
          "youtube": r"(@[\w.\-]{2,60}|UC[\w-]{22}|(c|user)/[\w.\-]{1,80})"}[platform]
    if not re.fullmatch(ok, h, re.UNICODE):
        raise SharkyClipsError(f"'{handle}' isn't a {platform.capitalize()} channel name.",
                               "Check the spelling, or paste the channel's link.")
    return h if platform == "youtube" else h.lower()


def channel_id(platform: str, handle: str) -> str:
    return f"{platform}:{handle}"


# ===================================================================== platform adapters
#
# lookup(handle) -> {"handle", "name", "avatar", "url", "live", "ext_id"}
# listing(ch)    -> {"live": bool, "vods": [entry], "complete": bool (not a full page), "oldest": ts | None}
# entry: {"vod_id", "url", "title", "started_at", "duration", "state", "note", "game", "kind"}
#   state: live | processing | upcoming | ready | restricted | deleted


def _ts(value: Any) -> float | None:
    if not value:
        return None
    s = str(value).strip().replace("Z", "+00:00")
    if " " in s and "T" not in s:
        s = s.replace(" ", "T")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # Kick's "2026-11-19 21:03:03" is UTC
    return dt.timestamp()


class Kick:
    platform = "kick"

    def lookup(self, handle: str) -> dict:
        r = HTTP.get(f"{_kick_site()}/api/v2/channels/{quote(handle)}", headers={"Accept": "application/json"})
        if r.status == 404:
            raise SharkyClipsError(f"Kick has no channel called '{handle}'.", "Check the spelling.")
        d = _json(r, "Kick")
        if not isinstance(d, dict) or not d.get("id"):
            raise SharkyClipsError(f"Kick has no channel called '{handle}'.", "Check the spelling.")
        user = d.get("user") or {}
        slug = str(d.get("slug") or handle).lower()
        return {"handle": slug, "name": user.get("username") or slug, "avatar": user.get("profile_pic"),
                "url": f"https://kick.com/{slug}", "live": bool(d.get("livestream")), "ext_id": d.get("id"),
                "vod_enabled": d.get("vod_enabled") is not False}

    def listing(self, ch: dict) -> dict:
        slug = ch["handle"]
        r = HTTP.get(f"{_kick_site()}/api/v2/channels/{quote(slug)}/videos", headers={"Accept": "application/json"})
        if r.status == 404:
            raise NetError("Kick: channel not found (renamed or banned?)")
        rows = _json(r, "Kick")
        if not isinstance(rows, list):
            raise NetError("Kick: unexpected answer")
        out, live = [], False
        for v in rows:
            video = v.get("video") or {}
            uuid = video.get("uuid")
            started = _ts(v.get("start_time") or v.get("created_at"))
            is_live = bool(v.get("is_live"))
            live = live or is_live
            if not uuid:  # the stream exists but its VOD isn't made yet
                if is_live or started:
                    out.append({"vod_id": f"stream-{v.get('id')}", "url": None, "title": v.get("session_title"),
                                "started_at": started, "duration": None, "state": "live" if is_live else "processing",
                                "note": None, "game": _first_cat(v), "kind": "live", "placeholder": True})
                continue
            dur = (float(v.get("duration") or 0) / 1000.0) or None
            if is_live:
                state, note = "live", None
            elif video.get("deleted_at") or video.get("is_pruned"):
                state, note = "deleted", "deleted"
            elif video.get("is_private") or (video.get("status") not in (None, "public")):
                state, note = "restricted", "subscriber_only"
            elif not dur:
                state, note = "processing", None
            else:
                state, note = "ready", None
            out.append({"vod_id": str(uuid), "url": f"https://kick.com/{slug}/videos/{uuid}",
                        "title": v.get("session_title") or uuid, "started_at": started, "duration": dur,
                        "state": state, "note": note, "game": _first_cat(v), "kind": "live",
                        "stream_id": str(v.get("id") or "")})
        return {"live": live, "vods": out, "complete": len(rows) < 20,
                "oldest": min((e["started_at"] for e in out if e["started_at"]), default=None)}


def _first_cat(v: dict) -> str | None:
    cats = v.get("categories") or []
    return (cats[0] or {}).get("name") if cats else None


class Twitch:
    platform = "twitch"
    Q = ("query($login: String!) { user(login: $login) { id login displayName profileImageURL(width: 70) "
         "stream { id createdAt game { name } } "
         "videos(first: 20, type: ARCHIVE, sort: TIME) { edges { node { id title createdAt lengthSeconds "
         "status game { name } } } } } }")

    def _user(self, login: str) -> dict:
        r = HTTP.post(_twitch_gql(), json={"query": self.Q, "variables": {"login": login}},
                      headers={"Client-Id": TWITCH_CLIENT_ID, "Content-Type": "application/json"})
        d = _json(r, "Twitch")
        if isinstance(d, list):
            d = d[0] if d else {}
        if d.get("errors") and not d.get("data"):
            raise NetError(f"Twitch: {str(d['errors'])[:120]}")
        return ((d.get("data") or {}).get("user")) or {}

    def lookup(self, handle: str) -> dict:
        u = self._user(handle)
        if not u.get("id"):
            raise SharkyClipsError(f"Twitch has no channel called '{handle}'.", "Check the spelling.")
        login = str(u.get("login") or handle).lower()
        return {"handle": login, "name": u.get("displayName") or login, "avatar": u.get("profileImageURL"),
                "url": f"https://www.twitch.tv/{login}", "live": bool(u.get("stream")), "ext_id": u.get("id")}

    def listing(self, ch: dict) -> dict:
        u = self._user(ch["handle"])
        if not u.get("id"):
            raise NetError("Twitch: channel not found (renamed or banned?)")
        out = []
        for edge in ((u.get("videos") or {}).get("edges") or []):
            n = edge.get("node") or {}
            if not n.get("id"):
                continue
            st = str(n.get("status") or "").upper()
            dur = float(n.get("lengthSeconds") or 0) or None
            state = "live" if st == "RECORDING" else "ready" if st == "RECORDED" and dur else "processing"
            out.append({"vod_id": str(n["id"]), "url": f"https://www.twitch.tv/videos/{n['id']}",
                        "title": n.get("title") or n["id"], "started_at": _ts(n.get("createdAt")), "duration": dur,
                        "state": state, "note": None, "game": (n.get("game") or {}).get("name"), "kind": "live"})
        stream = u.get("stream")
        if stream and not any(e["state"] == "live" for e in out):
            # live without an archive (yet): remember the stream so "ended" is noticed
            out.append({"vod_id": f"stream-{stream.get('id')}", "url": None, "title": None,
                        "started_at": _ts(stream.get("createdAt")), "duration": None, "state": "live", "note": None,
                        "game": (stream.get("game") or {}).get("name"), "kind": "live", "placeholder": True})
        return {"live": bool(stream), "vods": out, "complete": len(out) < 20,
                "oldest": min((e["started_at"] for e in out if e["started_at"]), default=None)}


_ATOM = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def yt_lookup(url: str) -> dict:
    """yt-dlp metadata of one YouTube video (no download). Tests replace it."""
    from .errors import require_module
    from .ingest import _YdlLogger, js_runtimes

    yt_dlp = require_module("yt_dlp", "yt-dlp[default]")
    opts = {"quiet": True, "skip_download": True, "noplaylist": True, "socket_timeout": 30, "retries": 3,
            "logger": _YdlLogger(), **({"js_runtimes": js_runtimes()} if js_runtimes() else {})}
    if ipv4_only():
        opts["source_address"] = "0.0.0.0"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
    except Exception as exc:  # noqa: BLE001 - the message says what happened
        return {"error": str(exc)[:400]}
    return {k: info.get(k) for k in ("id", "title", "live_status", "duration", "availability", "release_timestamp",
                                     "timestamp", "categories", "age_limit", "is_live", "was_live")}


_YT_RESTRICTED = ("members-only", "members only", "join this channel", "sign in to confirm your age",
                  "age-restricted", "age restricted", "inappropriate for some users", "private video",
                  "premium", "sign in")
_YT_GONE = ("video unavailable", "has been removed", "no longer available", "does not exist", "terminated")


class Youtube:
    platform = "youtube"
    FEED = "/feeds/videos.xml?channel_id="
    LOOKUPS_PER_POLL = 4  # yt-dlp lookups per poll (each is a few page loads)

    def lookup(self, handle: str) -> dict:
        path = f"/channel/{handle}" if handle.startswith("UC") else f"/{handle}"
        r = HTTP.get(_yt_site() + path, cookies={"SOCS": "CAI", "CONSENT": "YES+"})
        if r.status == 404:
            raise SharkyClipsError(f"YouTube has no channel '{handle}'.", "Check the @name or paste the channel link.")
        if r.status >= 400:
            raise NetError(f"YouTube: HTTP {r.status}")
        html = r.text
        m = re.search(r'"externalId":"(UC[\w-]{22})"', html) or re.search(r'channel/(UC[\w-]{22})', html)
        if not m:
            raise SharkyClipsError("YouTube didn't show that channel.", "Paste the channel's link (youtube.com/@name).")
        cid = m.group(1)
        title = _meta(html, "og:title") or handle
        return {"handle": cid, "name": title, "avatar": _meta(html, "og:image"),
                "url": f"https://www.youtube.com/channel/{cid}", "live": False, "ext_id": cid,
                "at": handle if handle.startswith("@") else None}

    def listing(self, ch: dict, known: dict | None = None, baseline: float | None = None) -> dict:
        r = HTTP.get(_yt_site() + self.FEED + quote(ch["handle"]))
        if r.status == 404:
            raise NetError("YouTube: channel feed not found")
        if r.status >= 400:
            raise NetError(f"YouTube: HTTP {r.status}")
        try:
            root = ElementTree.fromstring(r.body)
        except ElementTree.ParseError as exc:
            raise NetError("YouTube: the feed isn't readable") from exc
        known = known or {}
        out, live, lookups = [], False, 0
        for e in root.findall("a:entry", _ATOM):
            vid = (e.findtext("yt:videoId", None, _ATOM) or "").strip()
            if not vid:
                continue
            published = _ts(e.findtext("a:published", None, _ATOM))
            key = f"youtube:{vid}"
            rec = known.get(key)
            entry = {"vod_id": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                     "title": e.findtext("a:title", None, _ATOM) or vid, "started_at": published,
                     "duration": None, "state": "ready", "note": None, "game": None, "kind": "upload"}
            if rec is not None and rec.get("status") not in WATCHING:
                entry.update(state="known", kind=rec.get("kind") or "upload")
                out.append(entry)
                continue
            if rec is None and baseline and published and published < baseline - 24 * 3600:
                entry["state"] = "old"  # long before the channel was added: no lookup
                out.append(entry)
                continue
            if lookups >= self.LOOKUPS_PER_POLL:
                entry["state"] = "later"  # looked up on the next poll
                out.append(entry)
                continue
            lookups += 1
            info = yt_lookup(entry["url"])
            entry.update(_yt_state(info))
            live = live or entry["state"] == "live"
            out.append(entry)
        return {"live": live, "vods": out, "complete": len(out) < 15,
                "oldest": min((x["started_at"] for x in out if x["started_at"]), default=None)}


def _yt_state(info: dict) -> dict:
    err = str(info.get("error") or "").lower()
    if err:
        if any(m in err for m in _YT_RESTRICTED):
            note = "age_restricted" if "age" in err or "inappropriate" in err else "subscriber_only"
            return {"state": "restricted", "note": note}
        if any(m in err for m in _YT_GONE):
            return {"state": "deleted", "note": "deleted"}
        if "live event will begin" in err or "premieres in" in err:
            return {"state": "upcoming", "note": None}
        raise NetError(f"YouTube: {err[:160]}")
    av = str(info.get("availability") or "")
    if av in ("subscriber_only", "premium_only", "needs_auth"):
        return {"state": "restricted", "note": "subscriber_only" if av != "needs_auth" else "age_restricted"}
    if (info.get("age_limit") or 0) >= 18:
        return {"state": "restricted", "note": "age_restricted"}
    ls = str(info.get("live_status") or "")
    dur = float(info.get("duration") or 0) or None
    started = info.get("release_timestamp") or info.get("timestamp")
    base = {"duration": dur, **({"started_at": float(started)} if started else {}),
            "game": next((c for c in info.get("categories") or [] if c and c != "Gaming"), None)}
    if ls == "is_live":
        return {**base, "state": "live", "kind": "live", "note": None}
    if ls == "is_upcoming":
        return {**base, "state": "upcoming", "kind": "live", "note": None}
    if ls == "post_live":
        return {**base, "state": "processing", "kind": "live", "note": None}
    if ls == "was_live":
        return {**base, "state": "ready" if dur else "processing", "kind": "live", "note": None}
    return {**base, "state": "ready", "kind": "upload", "note": None}


def _meta(html: str, prop: str) -> str | None:
    m = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', html)
    if not m:
        return None
    import html as h

    return h.unescape(m.group(1))


SOURCES: dict[str, Any] = {"kick": Kick(), "twitch": Twitch(), "youtube": Youtube()}


def lookup(text: str, platform: str | None = None) -> dict:
    p, handle = parse(text, platform)
    try:
        info = SOURCES[p].lookup(handle)
    except NetError as exc:
        raise SharkyClipsError(f"{p.capitalize()} isn't answering right now.", f"Try again in a minute ({exc}).") from exc
    return {"platform": p, "id": channel_id(p, info["handle"]), **info}


# ===================================================================== channels


def new_channel(info: dict, own: bool, now: float, **opts) -> dict:
    ch = {"id": info["id"], "platform": info["platform"], "handle": info["handle"], "name": info.get("name"),
          "avatar": info.get("avatar"), "url": info.get("url"), "at": info.get("at"),
          "own": bool(own), "mode": "auto", "game": "auto", "auto_publish": False,
          "keep_days": DEFAULT_KEEP_DAYS, "yt_kinds": "both", "enabled": True,
          "added_at": now, "baseline": now, "first_listing": True, "live": bool(info.get("live")),
          "live_since": now if info.get("live") else None, "ended_at": None,
          "last_check": None, "next_check": now, "fails": 0, "last_error": None, "last_ok": None}
    apply_options(ch, opts)
    return ch


def apply_options(ch: dict, opts: dict) -> dict:
    from .project import MODES

    if "mode" in opts and opts["mode"] is not None:
        if opts["mode"] not in ("auto", *MODES):
            raise SharkyClipsError(f"Unknown content type '{opts['mode']}'.")
        ch["mode"] = opts["mode"]
    if "game" in opts and opts["game"] is not None:
        from .game import CHOICES

        if opts["game"] not in CHOICES:
            raise SharkyClipsError(f"Unknown game '{opts['game']}'.")
        ch["game"] = opts["game"]
    if "auto_publish" in opts and opts["auto_publish"] is not None:
        ch["auto_publish"] = bool(opts["auto_publish"])
    if "keep_days" in opts and opts["keep_days"] is not None:
        k = int(opts["keep_days"])
        if k not in (-1, 0, 1, 3, 7, 14, 30):
            raise SharkyClipsError("Keep the source video for 0, 1, 3, 7, 14 or 30 days, or forever.")
        ch["keep_days"] = k
    if "yt_kinds" in opts and opts["yt_kinds"] is not None:
        if opts["yt_kinds"] not in ("both", "live", "uploads"):
            raise SharkyClipsError("Pick live streams, uploads or both.")
        ch["yt_kinds"] = opts["yt_kinds"]
    if "own" in opts and opts["own"] is not None:
        ch["own"] = bool(opts["own"])
    if "enabled" in opts and opts["enabled"] is not None:
        ch["enabled"] = bool(opts["enabled"])
    return ch


def interval(ch: dict, data: dict, now: float) -> float:
    """Seconds until the next look (without jitter)."""
    if ch.get("fails"):
        return min(BACKOFF_MAX_S, BACKOFF_BASE_S * (2 ** (int(ch["fails"]) - 1)))
    busy = ch.get("live") or (ch.get("ended_at") and now - float(ch["ended_at"]) < ENDED_FAST_S)
    if not busy:
        busy = any(v.get("channel") == ch["id"] and v.get("status") in WATCHING for v in data["vods"].values())
    return LIVE_EVERY_S if busy else IDLE_EVERY_S


def _jitter(s: float, rnd: Callable[[], float] = random.random) -> float:
    return s * (0.9 + 0.2 * rnd())


def poll(data: dict, ch: dict, now: float, rnd: Callable[[], float] = random.random) -> dict:
    """Look at one channel once and merge what it shows. Returns {"new": [keys], "error": str|None}."""
    src = SOURCES[ch["platform"]]
    ch["last_check"] = now
    try:
        if ch["platform"] == "youtube":
            mine = {k: v for k, v in data["vods"].items() if v.get("channel") == ch["id"]}
            listing = src.listing(ch, mine, ch.get("baseline"))
        else:
            listing = src.listing(ch)
    except NetError as exc:
        ch["fails"] = int(ch.get("fails") or 0) + 1
        ch["last_error"] = str(exc)[:200]
        wait = interval(ch, data, now)
        if exc.retry_after:
            wait = max(wait, min(BACKOFF_MAX_S, float(exc.retry_after)))
        ch["next_check"] = now + _jitter(wait, rnd)
        if ch["fails"] in (1, 4):
            log(data, "poll_failed", ch["id"], note=str(exc), now=now)
        return {"new": [], "error": str(exc)}
    except SharkyClipsError as exc:
        ch["fails"] = int(ch.get("fails") or 0) + 1
        ch["last_error"] = exc.message[:200]
        ch["next_check"] = now + _jitter(interval(ch, data, now), rnd)
        return {"new": [], "error": exc.message}
    ch["fails"], ch["last_error"], ch["last_ok"] = 0, None, now
    was_live = bool(ch.get("live"))
    ch["live"] = bool(listing["live"])
    if ch["live"] and not was_live:
        ch["live_since"], ch["ended_at"] = now, None
        log(data, "live", ch["id"], now=now)
    if was_live and not ch["live"]:
        ch["ended_at"] = now
        log(data, "ended", ch["id"], now=now)
    first = bool(ch.pop("first_listing", False))
    new = []
    seen = set()
    for e in listing["vods"]:
        key = f"{ch['platform']}:{e['vod_id']}"
        seen.add(key)
        if merge(data, ch, key, e, now, first):
            new.append(key)
    _placeholders(data, ch, listing, now)
    _missing(data, ch, listing, seen, now)
    ch["next_check"] = now + _jitter(interval(ch, data, now), rnd)
    return {"new": new, "error": None}


def _min_s() -> float:
    return settings()["min_minutes"] * 60


def merge(data: dict, ch: dict, key: str, e: dict, now: float, first: bool = False) -> bool:
    """One entry of a listing. True when it was queued just now."""
    vods = data["vods"]
    rec = vods.get(key)
    state = e.get("state")
    if state in ("known", "later"):
        return False
    if rec is None:
        if e.get("placeholder"):
            if state != "live":
                return False
            rec = {"channel": ch["id"], "platform": ch["platform"], "vod_id": e["vod_id"], "first_seen": now,
                   "placeholder": True}
            vods[key] = rec
        else:
            started = e.get("started_at")
            # ended before the channel was added = back catalog; a stream that is live right now
            # counts (it ends after the channel was added)
            old = state == "old" or (state != "live" and started is not None
                                     and started < float(ch.get("baseline") or now))
            if old and state != "old" and _was_watched(vods, ch, e):
                old = False  # its live stream was seen (a stand-in): the VOD of that stream counts
            rec ={"channel": ch["id"], "platform": ch["platform"], "vod_id": e["vod_id"], "first_seen": now}
            vods[key] = rec
            if old:
                _fill(rec, e)
                rec["status"] = "baseline"
                return False
    elif rec.get("status") not in WATCHING and rec.get("status") is not None:
        if rec.get("status") in ("queued", "retry", "waiting_disk", "waiting_metered", "waiting_game") \
                and state == "deleted":
            rec.update(status="gone", note="deleted", done_at=now)
            log(data, "gone", ch["id"], key, now=now)
        rec["missing"] = 0
        if rec.get("status") == "baseline":
            _fill(rec, e)
        return False
    rec["missing"] = 0
    _fill(rec, e)
    if state == "old":
        rec["status"] = "baseline"
        return False
    if e.get("placeholder"):
        rec["status"] = "live" if state == "live" else "processing"
        return False
    return _decide(data, ch, key, rec, state, e.get("note"), now)


def _was_watched(vods: dict, ch: dict, e: dict) -> bool:
    sid = f"stream-{e.get('stream_id')}" if e.get("stream_id") else None
    started = float(e.get("started_at") or 0)
    for r in vods.values():
        if r.get("channel") != ch["id"] or not r.get("placeholder"):
            continue
        if (sid and str(r.get("vod_id")) == sid) or (started and abs(float(r.get("started_at") or 0) - started) < 900):
            return True
    return False


def _fill(rec: dict, e: dict) -> None:
    for k in ("url", "title", "started_at", "duration", "game", "kind", "stream_id"):
        if e.get(k) is not None:
            rec[k] = e[k]


def _decide(data: dict, ch: dict, key: str, rec: dict, state: str | None, note: str | None, now: float) -> bool:
    if state == "live":
        rec["status"] = "live"
        return False
    if state in ("processing", "upcoming"):
        rec["status"] = state
        return False
    if state == "restricted":
        rec.update(status="skipped", note=note or "subscriber_only", done_at=now)
        log(data, "skipped", ch["id"], key, note=rec["note"], now=now)
        return False
    if state == "deleted":
        rec.update(status="gone", note="deleted", done_at=now)
        log(data, "gone", ch["id"], key, now=now)
        return False
    # ready
    if ch["platform"] == "youtube":
        kinds = ch.get("yt_kinds") or "both"
        kind = rec.get("kind") or "upload"
        if (kinds == "live" and kind != "live") or (kinds == "uploads" and kind == "live"):
            rec.update(status="skipped", note="kind_off", done_at=now)
            return False
    dur = rec.get("duration")
    if dur is not None and dur < _min_s():
        rec.update(status="skipped", note="too_short", done_at=now)
        return False
    rec.update(status="queued", queued_at=now, attempts=int(rec.get("attempts") or 0))
    log(data, "queued", ch["id"], key, note=rec.get("title") or "", now=now)
    return True


def _placeholders(data: dict, ch: dict, listing: dict, now: float) -> None:
    """A "stream-<id>" stand-in (live, no VOD id yet) is dropped once a real VOD of that stream
    shows up, or after the stream ended for good (12 h)."""
    real = {str(e.get("stream_id")) for e in listing["vods"] if e.get("stream_id")}
    for key, rec in list(data["vods"].items()):
        if rec.get("channel") != ch["id"] or not rec.get("placeholder"):
            continue
        sid = str(rec["vod_id"]).removeprefix("stream-")
        if sid in real or (ch["platform"] == "twitch" and any(
                e["state"] in ("live", "ready", "processing") and not e.get("placeholder")
                and (e.get("started_at") or 0) >= (rec.get("started_at") or 0) - 600 for e in listing["vods"])):
            data["vods"].pop(key, None)
        elif rec.get("status") in WATCHING and not ch.get("live") and now - float(ch.get("ended_at") or now) > 12 * 3600:
            rec.update(status="gone", note="no_vod", done_at=now)
            log(data, "no_vod", ch["id"], key, now=now)


def _missing(data: dict, ch: dict, listing: dict, seen: set[str], now: float) -> None:
    """Waiting / watched VODs that the (complete enough) listing doesn't show any more."""
    oldest = listing.get("oldest")
    for key, rec in data["vods"].items():
        if rec.get("channel") != ch["id"] or key in seen or rec.get("placeholder"):
            continue
        if rec.get("status") not in WAITING + WATCHING:
            continue
        if not listing.get("complete") and oldest is not None and (rec.get("started_at") or 0) < oldest:
            continue  # a full page: it may simply be older than what the list shows
        rec["missing"] = int(rec.get("missing") or 0) + 1
        if rec["missing"] >= MISSING_POLLS:
            rec.update(status="gone", note="deleted", done_at=now)
            log(data, "gone", ch["id"], key, now=now)


def due(data: dict, now: float) -> list[dict]:
    return [c for c in data["channels"].values()
            if c.get("enabled", True) and float(c.get("next_check") or 0) <= now]


def wake_all(data: dict, now: float) -> None:
    """The PC was off or asleep: look at every channel now (catch-up)."""
    for c in data["channels"].values():
        c["next_check"] = min(float(c.get("next_check") or now), now)


def next_waiting(data: dict, now: float) -> tuple[str, dict] | None:
    """The VOD to download next: the oldest stream first (catch-up keeps the order)."""
    rows = []
    for k, v in data["vods"].items():
        if v.get("status") not in WAITING:
            continue
        if v.get("status") == "retry" and float(v.get("next_try") or 0) > now:
            continue
        ch = data["channels"].get(v.get("channel") or "")
        if ch is None or not ch.get("enabled", True):
            continue
        rows.append((float(v.get("started_at") or v.get("first_seen") or 0), k, v))
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    return rows[0][1], rows[0][2]


def import_recent(data: dict, cid: str, count: int, now: float) -> list[str]:
    """The "Import the last N streams" button: the newest N baseline VODs, oldest first."""
    count = max(1, min(10, int(count)))
    rows = [(float(v.get("started_at") or 0), k, v) for k, v in data["vods"].items()
            if v.get("channel") == cid and v.get("status") == "baseline" and v.get("url")]
    rows.sort(key=lambda r: -r[0])
    out = []
    for _t, k, v in sorted(rows[:count], key=lambda r: r[0]):
        dur = v.get("duration")
        if dur is not None and dur < _min_s():
            continue
        v.update(status="queued", queued_at=now, attempts=0, requested=True)
        out.append(k)
    if out:
        log(data, "import_recent", cid, note=str(len(out)), now=now)
    return out


# ===================================================================== gates before a download


def need_bytes(duration: float | None) -> int:
    return int((duration or 3 * 3600) * BYTES_PER_S)


def disk_ok(duration: float | None, folder: Path | None = None) -> tuple[bool, int, int]:
    """(enough, free bytes, needed bytes incl. the reserve)."""
    folder = folder or config.workspace_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(folder).free
    except OSError:
        return True, 0, 0
    need = need_bytes(duration) + int(settings()["min_free_gb"] * 1024 ** 3)
    return free >= need, free, need


_metered: dict = {"at": 0.0, "value": None}


def metered() -> bool | None:
    """Windows: the internet connection is metered (Fixed / Variable cost). None = can't tell.
    Cached 10 minutes (it starts a hidden PowerShell)."""
    forced = os.environ.get("SHARKYCLIPS_METERED")
    if forced in ("0", "1"):
        return forced == "1"
    if os.name != "nt":
        return None
    if time.time() - _metered["at"] < 600:
        return _metered["value"]
    import subprocess

    from .procs import no_window

    script = ("[void][Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,"
              "ContentType=WindowsRuntime];$p=[Windows.Networking.Connectivity.NetworkInformation]::"
              "GetInternetConnectionProfile();if($p){$p.GetConnectionCost().NetworkCostType}else{'none'}")
    value = None
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                           capture_output=True, text=True, timeout=20, **no_window())
        out = (r.stdout or "").strip().lower()
        value = out in ("fixed", "variable") if out and out != "none" else None
    except Exception:  # noqa: BLE001
        value = None
    _metered.update(at=time.time(), value=value)
    return value


def game_running() -> str | None:
    """A game from the governor's list is running (any window state). Only in the governor's
    Silent mode (the default), like the governor's own pauses."""
    if os.environ.get("SHARKYCLIPS_GAME_RUNNING") is not None:
        return os.environ["SHARKYCLIPS_GAME_RUNNING"] or None
    try:
        from . import governor

        if str(config.get("performance_mode") or "silent") != "silent":
            return None
        pats = list(config.get("perf_games") or governor.DEFAULT_GAMES)
        import psutil

        for p in psutil.process_iter(["name"]):
            name = (p.info.get("name") or "").lower().removesuffix(".exe")
            if name and governor._match(name, pats):
                return name
    except Exception:  # noqa: BLE001
        return None
    return None


# ===================================================================== after the import


_LOGIN = ("sign in", "your age", "age-restricted", "login", "log in", "private video", "members-only",
          "subscriber", "cookies", "without an account")
_GONE = ("no video with that link", "deleted", "expired", "does not exist", "404", "not found", "unavailable",
         "removed")
_DISK = ("no space left", "disk full", "not enough space", "errno 28", "winerror 112")


def classify_failure(message: str) -> str:
    """restricted | gone | disk | retry"""
    m = (message or "").lower()
    if any(x in m for x in _DISK):
        return "disk"
    if any(x in m for x in _LOGIN):
        return "restricted"
    if any(x in m for x in _GONE):
        return "gone"
    return "retry"


def on_import_failed(data: dict, key: str, message: str, now: float) -> str:
    rec = data["vods"].get(key)
    if rec is None:
        return "unknown"
    kind = classify_failure(message)
    rec["last_error"] = str(message)[:300]
    rec.pop("job_id", None)
    if kind == "restricted":
        note = "age_restricted" if "age" in message.lower() else "subscriber_only"
        rec.update(status="skipped", note=note, done_at=now)
    elif kind == "gone":
        rec.update(status="gone", note="deleted", done_at=now)
    elif kind == "disk":
        rec.update(status="waiting_disk", note="disk_full")
    elif int(rec.get("attempts") or 0) >= MAX_ATTEMPTS:
        rec.update(status="error", note="download_failed", done_at=now)
    else:
        rec.update(status="retry", next_try=now + RETRY_BASE_S * (2 ** max(0, int(rec.get("attempts") or 1) - 1)))
    log(data, "import_" + rec["status"], rec.get("channel"), key, note=message, now=now)
    return rec["status"]


def verify(expected: float | None, got: float | None) -> bool:
    """The downloaded file is (nearly) as long as the stream."""
    if not expected or not got:
        return bool(got)
    return got >= expected * VERIFY_MIN


def source_due(rec: dict, ch: dict | None, now: float) -> bool:
    """The downloaded VOD of a finished stream goes to the trash now."""
    if rec.get("status") != "done" or rec.get("source_trashed") or not rec.get("project_id"):
        return False
    keep = DEFAULT_KEEP_DAYS if ch is None else int(ch.get("keep_days", DEFAULT_KEEP_DAYS))
    if keep < 0:
        return False
    return now >= float(rec.get("done_at") or now) + keep * 86400


# ===================================================================== views


def channel_view(ch: dict, data: dict) -> dict:
    mine = [v for v in data["vods"].values() if v.get("channel") == ch["id"]]
    counts: dict[str, int] = {}
    for v in mine:
        counts[v.get("status") or "?"] = counts.get(v.get("status") or "?", 0) + 1
    return {k: ch.get(k) for k in ("id", "platform", "handle", "name", "avatar", "url", "at", "own", "mode", "game",
                                   "auto_publish", "keep_days", "yt_kinds", "enabled", "added_at", "live",
                                   "live_since", "ended_at", "last_check", "next_check", "fails", "last_error",
                                   "last_ok")} | {"counts": counts,
                                                  "can_import": sum(1 for v in mine if v.get("status") == "baseline"
                                                                    and v.get("url"))}


def vod_view(key: str, v: dict, ch: dict | None) -> dict:
    return {"key": key, **{k: v.get(k) for k in ("channel", "platform", "vod_id", "url", "title", "started_at",
                                                 "duration", "status", "note", "game", "kind", "project_id",
                                                 "clips", "attempts", "next_try", "done_at", "last_error",
                                                 "source_trashed", "queued_at")},
            "channel_name": (ch or {}).get("name"), "own": bool((ch or {}).get("own"))}
