"""A fake Google / YouTube API server on 127.0.0.1 for tests and the end-to-end check.

Point SharkyClips at it with SHARKYCLIPS_YT_ENDPOINT=http://127.0.0.1:<port> (youtube.url()
maps https://www.googleapis.com/youtube/v3/x -> <base>/www/youtube/v3/x and so on).

It speaks just enough of the real APIs: OAuth (auth page that consents at once, token,
refresh, revoke), channels.list, resumable videos.insert, videos.list / update / delete,
thumbnails.set, playlists, playlistItems and YouTube Analytics reports. Switches:

  locked          an unaudited project: every upload stays private, publishAt is dropped
  quota_exceeded  videos.insert answers 403 quotaExceeded
  fail_inserts    this many videos.insert calls answer 500
  fail_chunks     this many upload chunks answer 503
  expire_next     the next API call with a valid token answers 401 (token expired)
  revoke_refresh  refresh answers invalid_grant (the user removed access)
  access_ttl      seconds an access token lives
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeYouTube:
    def __init__(self):
        self.lock = threading.RLock()
        self.locked = False
        self.quota_exceeded = False
        self.fail_inserts = 0
        self.fail_chunks = 0
        self.expire_next = 0
        self.revoke_refresh = False
        self.access_ttl = 3600
        self.tokens: dict[str, float] = {}  # access token -> expiry
        self.refresh_tokens: set[str] = set()
        self.codes: dict[str, str] = {}  # auth code -> scope
        self.videos: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.playlists: dict[str, dict] = {}
        self.playlist_items: list[tuple[str, str]] = []
        self.thumbnails: dict[str, int] = {}
        self.log: list[tuple[str, str]] = []
        self.refreshes = 0
        self.revoked = 0
        self._n = 0
        self.server: ThreadingHTTPServer | None = None

    # ------------------------------------------------------------- control

    def start(self) -> str:
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _go(self, method: str):
                try:
                    fake.handle(self, method)
                except Exception as exc:  # noqa: BLE001
                    fake._send(self, 500, {"error": {"message": f"fake server: {exc!r}"}})

            def do_GET(self):
                self._go("GET")

            def do_POST(self):
                self._go("POST")

            def do_PUT(self):
                self._go("PUT")

            def do_DELETE(self):
                self._go("DELETE")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self.base

    @property
    def base(self) -> str:
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def release_due(self, now: datetime | None = None) -> list[str]:
        """YouTube's own scheduler: scheduled videos whose time came go public (unless locked)."""
        now = now or datetime.now(timezone.utc)
        out = []
        with self.lock:
            for vid, v in self.videos.items():
                pa = v["status"].get("publishAt")
                if pa and datetime.fromisoformat(pa.replace("Z", "+00:00")) <= now and not self.locked:
                    v["status"]["privacyStatus"] = "public"
                    v["status"].pop("publishAt", None)
                    v["snippet"]["publishedAt"] = now.isoformat().replace("+00:00", "Z")
                    out.append(vid)
        return out

    def count(self, method: str, prefix: str) -> int:
        return sum(1 for m, p in self.log if m == method and p.startswith(prefix))

    # ------------------------------------------------------------- HTTP

    def _send(self, h, code: int, body=None, headers: dict | None = None):
        data = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        h.send_response(code)
        for k, v in (headers or {}).items():
            h.send_header(k, v)
        if body is not None and not isinstance(body, bytes):
            h.send_header("Content-Type", "application/json")
        elif isinstance(body, bytes):
            h.send_header("Content-Type", "text/html; charset=utf-8")
        h.send_header("Content-Length", str(len(data)))
        h.end_headers()
        if data:
            h.wfile.write(data)

    def _err(self, h, code: int, reason: str, message: str = ""):
        self._send(h, code, {"error": {"code": code, "message": message or reason,
                                       "errors": [{"reason": reason, "message": message or reason}]}})

    def _id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n:04d}"

    def _authed(self, h) -> bool:
        auth = h.headers.get("Authorization") or ""
        tok = auth.removeprefix("Bearer ").strip()
        with self.lock:
            exp = self.tokens.get(tok)
            if exp is None or exp < time.time():
                self._err(h, 401, "authError", "Invalid Credentials")
                return False
            if self.expire_next > 0:
                self.expire_next -= 1
                self.tokens.pop(tok, None)
                self._err(h, 401, "authError", "Invalid Credentials")
                return False
        return True

    def _body(self, h) -> bytes:
        n = int(h.headers.get("Content-Length") or 0)
        return h.rfile.read(n) if n else b""

    def handle(self, h, method: str) -> None:
        parts = urllib.parse.urlsplit(h.path)
        path, q = parts.path, dict(urllib.parse.parse_qsl(parts.query))
        with self.lock:
            self.log.append((method, path))
        raw = self._body(h) if method in ("POST", "PUT") else b""

        # ---- OAuth
        if path == "/accounts/o/oauth2/v2/auth":
            code = f"code-{self._id('c')}"
            self.codes[code] = q.get("scope", "")
            target = q["redirect_uri"] + "?" + urllib.parse.urlencode({"code": code, "state": q.get("state", "")})
            self._send(h, 302, None, {"Location": target})
            return
        if path == "/oauth2/token":
            form = dict(urllib.parse.parse_qsl(raw.decode()))
            if form.get("grant_type") == "authorization_code":
                scope = self.codes.pop(form.get("code", ""), None)
                if scope is None:
                    self._send(h, 400, {"error": "invalid_grant", "error_description": "Bad code"})
                    return
                acc, ref = self._id("acc"), self._id("ref")
                self.tokens[acc] = time.time() + self.access_ttl
                self.refresh_tokens.add(ref)
                self._send(h, 200, {"access_token": acc, "refresh_token": ref, "expires_in": self.access_ttl,
                                    "scope": scope, "token_type": "Bearer"})
                return
            if form.get("grant_type") == "refresh_token":
                if self.revoke_refresh or form.get("refresh_token") not in self.refresh_tokens:
                    self._send(h, 400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."})
                    return
                self.refreshes += 1
                acc = self._id("acc")
                self.tokens[acc] = time.time() + self.access_ttl
                self._send(h, 200, {"access_token": acc, "expires_in": self.access_ttl, "token_type": "Bearer"})
                return
            self._send(h, 400, {"error": "unsupported_grant_type"})
            return
        if path == "/oauth2/revoke":
            self.revoked += 1
            self.refresh_tokens.discard(q.get("token", ""))
            self._send(h, 200, {})
            return

        # ---- test control (end-to-end runs in another process)
        if path == "/_state":
            self._send(h, 200, {"videos": self.videos,
                                "playlists": self.playlists, "playlist_items": self.playlist_items,
                                "thumbnails": self.thumbnails, "refreshes": self.refreshes, "revoked": self.revoked,
                                "locked": self.locked})
            return
        if path == "/_set" and method == "POST":
            for k2, v2 in json.loads(raw or b"{}").items():
                if k2 == "video":  # {"id":..., "status": {...}, "statistics": {...}, "snippet": {...}}
                    v = self.videos.get(v2["id"])
                    for part in ("status", "statistics", "snippet"):
                        if v is not None and part in v2:
                            v[part].update(v2[part])
                elif k2 == "release_due":
                    self.release_due()
                elif hasattr(self, k2):
                    setattr(self, k2, v2)
            self._send(h, 200, {"ok": True})
            return

        # ---- resumable upload session
        if path.startswith("/session/"):
            self._chunk(h, path.split("/")[-1], raw)
            return

        if not self._authed(h):
            return
        if path == "/www/youtube/v3/channels":
            self._send(h, 200, {"items": [{"id": "UCfake", "snippet": {"title": "Fake Channel", "thumbnails": {
                "default": {"url": f"{self.base}/avatar.png"}}}}]})
            return
        if path == "/www/upload/youtube/v3/videos" and method == "POST":
            if self.quota_exceeded:
                self._err(h, 403, "quotaExceeded", "The request cannot be completed because you have exceeded your quota.")
                return
            if self.fail_inserts > 0:
                self.fail_inserts -= 1
                self._err(h, 500, "backendError", "Backend Error")
                return
            body = json.loads(raw or b"{}")
            sid = self._id("s")
            self.sessions[sid] = {"body": body, "size": int(h.headers.get("X-Upload-Content-Length") or 0), "got": b""}
            self._send(h, 200, {}, {"Location": f"{self.base}/session/{sid}"})
            return
        if path == "/www/upload/youtube/v3/thumbnails/set":
            vid = q.get("videoId", "")
            if vid not in self.videos:
                self._err(h, 404, "videoNotFound")
                return
            self.thumbnails[vid] = len(raw)
            self._send(h, 200, {"items": [{"default": {"url": "x"}}]})
            return
        if path == "/www/youtube/v3/videos":
            if method == "GET":
                ids = [i for i in (q.get("id") or "").split(",") if i]
                items = []
                for i in ids:
                    v = self.videos.get(i)
                    if v:
                        items.append({"id": i, "snippet": v["snippet"], "status": v["status"],
                                      "statistics": v["statistics"]})
                self._send(h, 200, {"items": items})
                return
            if method == "PUT":
                body = json.loads(raw or b"{}")
                v = self.videos.get(body.get("id", ""))
                if v is None:
                    self._err(h, 404, "videoNotFound")
                    return
                if "snippet" in body:
                    if not body["snippet"].get("title") or not body["snippet"].get("categoryId"):
                        self._err(h, 400, "invalidVideoMetadata")
                        return
                    v["snippet"].update(body["snippet"])
                if "status" in body:
                    st = dict(body["status"])
                    if self.locked:
                        st["privacyStatus"] = "private"
                        st.pop("publishAt", None)
                    v["status"] = {**{k: x for k, x in v["status"].items() if k != "publishAt"}, **st}
                    if st.get("privacyStatus") in ("public", "unlisted"):
                        v["snippet"]["publishedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                self._send(h, 200, {"id": body["id"], "snippet": v["snippet"], "status": v["status"]})
                return
            if method == "DELETE":
                if self.videos.pop(q.get("id", ""), None) is None:
                    self._err(h, 404, "videoNotFound")
                    return
                self._send(h, 204)
                return
        if path == "/www/youtube/v3/playlists":
            if method == "GET":
                self._send(h, 200, {"items": [{"id": k, "snippet": {"title": v["title"]},
                                               "status": {"privacyStatus": v["privacy"]},
                                               "contentDetails": {"itemCount": v["count"]}}
                                              for k, v in self.playlists.items()]})
                return
            body = json.loads(raw or b"{}")
            pid = self._id("PL")
            self.playlists[pid] = {"title": body["snippet"]["title"], "privacy": body["status"]["privacyStatus"], "count": 0}
            self._send(h, 200, {"id": pid, "snippet": body["snippet"], "status": body["status"]})
            return
        if path == "/www/youtube/v3/playlistItems" and method == "POST":
            body = json.loads(raw or b"{}")
            pl, vid = body["snippet"]["playlistId"], body["snippet"]["resourceId"]["videoId"]
            if pl not in self.playlists:
                self._err(h, 404, "playlistNotFound")
                return
            self.playlists[pl]["count"] += 1
            self.playlist_items.append((pl, vid))
            self._send(h, 200, {"id": self._id("PLI")})
            return
        if path == "/youtubeanalytics/v2/reports":
            ids = (q.get("filters") or "").removeprefix("video==").split(",")
            rows = [[i, self.videos[i]["statistics"]["viewCount"] and int(self.videos[i]["statistics"]["viewCount"]),
                     12.0, 55.0] for i in ids if i in self.videos]
            self._send(h, 200, {"columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "averageViewDuration"},
                                                  {"name": "averageViewPercentage"}], "rows": rows})
            return
        self._err(h, 404, "notFound", f"fake: no route {method} {path}")

    def _chunk(self, h, sid: str, raw: bytes) -> None:
        s = self.sessions.get(sid)
        if s is None:
            self._err(h, 404, "notFound")
            return
        rng = h.headers.get("Content-Range") or ""
        if rng.startswith("bytes */"):  # status query
            got = len(s["got"])
            if s.get("done"):
                self._send(h, 200, s["done"])
            else:
                self._send(h, 308, None, {"Range": f"bytes=0-{got - 1}"} if got else {})
            return
        if self.fail_chunks > 0:
            self.fail_chunks -= 1
            self._send(h, 503, {"error": {"message": "Service Unavailable"}})
            return
        start = int(rng.split(" ")[1].split("-")[0])
        s["got"] = s["got"][:start] + raw
        if len(s["got"]) < s["size"]:
            self._send(h, 308, None, {"Range": f"bytes=0-{len(s['got']) - 1}"})
            return
        body = s["body"]
        vid = self._id("VID")
        status = dict(body.get("status") or {})
        if self.locked:
            status["privacyStatus"] = "private"
            status.pop("publishAt", None)
        status["uploadStatus"] = "uploaded"
        snippet = dict(body.get("snippet") or {})
        if status.get("privacyStatus") in ("public", "unlisted"):
            snippet["publishedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.videos[vid] = {"snippet": snippet, "status": status, "statistics": {"viewCount": "0", "likeCount": "0"},
                            "bytes": len(s["got"])}
        s["done"] = {"id": vid, "snippet": snippet, "status": status}
        self._send(h, 201, s["done"])
