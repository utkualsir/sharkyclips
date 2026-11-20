"""Fake Kick / Twitch / YouTube endpoints for the channel monitor (channels.HTTP is replaced).

Answers like the real public endpoints (shapes copied from kick.com/api/v2/channels/<slug>[/videos],
gql.twitch.tv and youtube.com/feeds/videos.xml on 2026-11-20). A test changes the scenario
between polls: `go_live`, `end_stream`, `publish_vod`, `delete_vod`, `fail` ...
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sharkyclips.channels import NetError, Resp


def _kick_time(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakePlatforms:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.kick: dict[str, dict] = {}  # slug -> {"live": stream|None, "videos": [...]}
        self.twitch: dict[str, dict] = {}  # login -> {"stream": ..., "videos": [...]}
        self.yt: dict[str, dict] = {}  # UC id -> {"handle", "entries": [...]}
        self.yt_info: dict[str, dict] = {}  # video id -> yt-dlp metadata
        self.down: set[str] = set()  # hosts that fail ("kick", "twitch", "youtube")
        self.rate_limited: set[str] = set()
        self._n = 1000

    # ------------------------------------------------------------------ scenario helpers
    def kick_channel(self, slug: str, videos: list[dict] | None = None) -> None:
        self.kick[slug] = {"live": None, "videos": list(videos or [])}

    def kick_vod(self, slug: str, start: float, duration_s: float, uuid: str | None = None, live: bool = False,
                 status: str = "public", private: bool = False, title: str = "Stream", game: str = "Delta Force",
                 with_video: bool = True) -> dict:
        self._n += 1
        v = {"id": self._n, "slug": f"s-{self._n}", "channel_id": 1, "created_at": _kick_time(start),
             "session_title": title, "is_live": live, "start_time": _kick_time(start),
             "duration": 0 if live else int(duration_s * 1000), "language": "Turkish",
             "categories": [{"name": game}],
             "video": ({"id": self._n, "uuid": uuid or f"00000000-0000-4000-8000-{self._n:012d}",
                        "deleted_at": None, "is_pruned": False, "is_private": private, "status": status}
                       if with_video else None)}
        self.kick[slug]["videos"].insert(0, v)
        return v

    def go_live(self, slug: str, start: float, title: str = "Live!") -> dict:
        v = self.kick_vod(slug, start, 0, live=True, title=title, with_video=False)
        self.kick[slug]["live"] = {"id": v["id"]}
        return v

    def end_stream(self, slug: str, duration_s: float, vod_ready: bool = True) -> dict:
        """The live entry ends. vod_ready=False: the VOD isn't made yet (it appears late)."""
        v = next(x for x in self.kick[slug]["videos"] if x["is_live"])
        v["is_live"] = False
        self.kick[slug]["live"] = None
        if vod_ready:
            self.publish_vod(slug, v, duration_s)
        return v

    def publish_vod(self, slug: str, v: dict, duration_s: float) -> None:
        v["duration"] = int(duration_s * 1000)
        v["video"] = {"id": v["id"], "uuid": f"00000000-0000-4000-8000-{v['id']:012d}", "deleted_at": None,
                      "is_pruned": False, "is_private": False, "status": "public"}

    def delete_vod(self, slug: str, uuid: str, drop: bool = False) -> None:
        vids = self.kick[slug]["videos"]
        for v in list(vids):
            if (v.get("video") or {}).get("uuid") == uuid:
                if drop:
                    vids.remove(v)
                else:
                    v["video"]["deleted_at"] = "2026-11-20T00:00:00Z"

    # ------------------------------------------------------------------ HTTP
    def get(self, url: str, **kw) -> Resp:
        return self._route("GET", url, kw)

    def post(self, url: str, **kw) -> Resp:
        return self._route("POST", url, kw)

    def request(self, method: str, url: str, **kw) -> Resp:
        return self._route(method, url, kw)

    def _route(self, method: str, url: str, kw: dict) -> Resp:
        self.calls.append((method, url))
        host = "kick" if "kick" in url else "twitch" if "twitch" in url else "youtube"
        if host in self.down:
            raise NetError(f"{host}: ConnectTimeout")
        if host in self.rate_limited:
            return Resp(429, b"{}", {"Retry-After": "7200"})
        path = url.split("://", 1)[1].split("/", 1)[1] if "://" in url else url
        if host == "kick":
            return self._kick(path)
        if host == "twitch":
            return self._twitch(kw.get("json") or {})
        return self._youtube(path)

    def _kick(self, path: str) -> Resp:
        parts = path.split("?")[0].strip("/").split("/")  # api/v2/channels/<slug>[/videos]
        slug = parts[3] if len(parts) > 3 else ""
        ch = self.kick.get(slug)
        if ch is None:
            return Resp(404, b'{"message":"Not found"}', {})
        if len(parts) == 4:
            body = {"id": 116630350, "slug": slug, "vod_enabled": True, "livestream": ch["live"],
                    "user": {"username": slug.capitalize(), "profile_pic": f"https://files.kick.com/{slug}.webp"},
                    "chatroom": {"id": 5}}
            return Resp(200, json.dumps(body).encode(), {"content-type": "application/json"})
        return Resp(200, json.dumps(ch["videos"]).encode(), {"content-type": "application/json"})

    def _twitch(self, body: dict) -> Resp:
        login = (body.get("variables") or {}).get("login")
        u = self.twitch.get(login or "")
        if u is None:
            return Resp(200, b'{"data":{"user":null}}', {})
        user = {"id": "552120296", "login": login, "displayName": login.capitalize(),
                "profileImageURL": f"https://static-cdn.jtvnw.net/{login}.png", "stream": u.get("stream"),
                "videos": {"edges": [{"node": v} for v in u["videos"]]}}
        return Resp(200, json.dumps({"data": {"user": user}}).encode(), {})

    def _youtube(self, path: str) -> Resp:
        if path.startswith("feeds/videos.xml"):
            cid = path.split("channel_id=", 1)[1]
            ch = self.yt.get(cid)
            if ch is None:
                return Resp(404, b"", {})
            entries = "".join(
                f"<entry><id>yt:video:{e['id']}</id><yt:videoId>{e['id']}</yt:videoId><title>{e['title']}</title>"
                f"<published>{_iso(e['published'])}</published></entry>" for e in ch["entries"])
            xml = ('<?xml version="1.0" encoding="UTF-8"?><feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" '
                   f'xmlns="http://www.w3.org/2005/Atom"><title>{ch["name"]}</title>{entries}</feed>')
            return Resp(200, xml.encode(), {})
        for cid, ch in self.yt.items():
            if path.strip("/") in (ch["handle"], f"channel/{cid}"):
                html = (f'<html><meta property="og:title" content="{ch["name"]}">'
                        f'<meta property="og:image" content="https://yt3.example/{cid}.jpg">'
                        f'<script>var x = {{"externalId":"{cid}"}};</script></html>')
                return Resp(200, html.encode(), {})
        return Resp(404, b"", {})

    def yt_lookup(self, url: str) -> dict:
        vid = url.split("v=", 1)[1]
        self.calls.append(("YTDLP", vid))
        return dict(self.yt_info.get(vid) or {"error": "Video unavailable"})
