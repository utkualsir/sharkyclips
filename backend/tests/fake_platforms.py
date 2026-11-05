"""Fake TikTok Content Posting API + Instagram Graph API on 127.0.0.1 for the tests."""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import threading
from urllib.parse import parse_qs, urlparse


class FakePlatforms:
    def __init__(self):
        self.state = {"tiktok_uploads": {}, "tiktok_posts": [], "ig_uploads": {}, "ig_posts": [], "codes": {},
                      "account_type": "MEDIA_CREATOR", "privacy_options": ["SELF_ONLY"], "status_polls": 0,
                      "refreshes": 0}
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _body(self) -> bytes:
                n = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(n) if n else b""

            def _json(self, code: int, data: dict):
                raw = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):  # noqa: N802
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                st = fake.state
                if u.path == "/v2/user/info/":
                    return self._json(200, {"data": {"user": {"display_name": "utku"}}, "error": {"code": "ok"}})
                if u.path == "/v21.0/me":
                    if q.get("access_token") != "IGTOKEN-0123456789abcdef":
                        return self._json(400, {"error": {"code": 190, "message": "Invalid OAuth access token"}})
                    return self._json(200, {"user_id": "1784", "username": "utku.clips", "account_type": st["account_type"]})
                if u.path == "/refresh_access_token":
                    st["refreshes"] += 1
                    return self._json(200, {"access_token": q["access_token"], "expires_in": 5184000})
                if u.path.startswith("/v21.0/"):
                    obj = u.path.split("/")[2]
                    if "status_code" in q.get("fields", ""):
                        up = st["ig_uploads"].get(obj)
                        return self._json(200, {"status_code": "FINISHED" if up and up["bytes"] else "IN_PROGRESS"})
                    if "permalink" in q.get("fields", ""):
                        return self._json(200, {"permalink": f"https://www.instagram.com/reel/{obj}/"})
                return self._json(404, {"error": {"message": "not found"}})

            def do_PUT(self):  # noqa: N802
                u = urlparse(self.path)
                if u.path.startswith("/upload/"):
                    pid = u.path.split("/")[2]
                    data = self._body()
                    fake.state["tiktok_uploads"].setdefault(pid, []).append(
                        {"range": self.headers.get("Content-Range"), "len": len(data), "type": self.headers.get("Content-Type")})
                    return self._json(201, {})
                return self._json(404, {})

            def do_POST(self):  # noqa: N802
                u = urlparse(self.path)
                raw = self._body()
                st = fake.state
                ctype = self.headers.get("Content-Type") or ""
                form = {k: v[0] for k, v in parse_qs(raw.decode(errors="replace")).items()} \
                    if "x-www-form-urlencoded" in ctype else {}
                if u.path == "/v2/oauth/token/":
                    if form.get("grant_type") == "authorization_code":
                        want = st["codes"].get(form.get("code"))
                        ok = want and base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest()
                                                              ).rstrip(b"=").decode() == want
                        if not ok:
                            return self._json(400, {"error": "invalid_grant", "error_description": "bad code or verifier"})
                    else:
                        st["refreshes"] += 1
                    return self._json(200, {"access_token": "TT-ACCESS", "refresh_token": "TT-REFRESH", "expires_in": 86400,
                                            "refresh_expires_in": 31536000, "open_id": "o1",
                                            "scope": "user.info.basic,video.publish,video.upload"})
                if u.path == "/v2/post/publish/creator_info/query/":
                    return self._json(200, {"data": {"privacy_level_options": st["privacy_options"]}, "error": {"code": "ok"}})
                if u.path == "/v2/post/publish/video/init/":
                    body = json.loads(raw)
                    pid = f"p{len(st['tiktok_posts']) + 1}"
                    st["tiktok_posts"].append({"id": pid, **body})
                    port = self.server.server_address[1]
                    return self._json(200, {"data": {"publish_id": pid, "upload_url": f"http://127.0.0.1:{port}/upload/{pid}"},
                                            "error": {"code": "ok"}})
                if u.path == "/v2/post/publish/status/fetch/":
                    st["status_polls"] += 1
                    return self._json(200, {"data": {"status": "PUBLISH_COMPLETE"}, "error": {"code": "ok"}})
                if u.path.startswith("/ig-api-upload/"):
                    cid = u.path.split("/")[-1]
                    up = st["ig_uploads"].setdefault(cid, {"bytes": 0})
                    up["bytes"] = len(raw)
                    up["file_size"] = self.headers.get("file_size")
                    up["auth"] = self.headers.get("Authorization")
                    return self._json(200, {"success": True})
                if u.path.endswith("/media_publish"):
                    st["ig_posts"].append(form)
                    return self._json(200, {"id": "M" + form.get("creation_id", "")})
                if u.path.endswith("/media"):
                    cid = f"C{len(st['ig_uploads']) + 1}"
                    st["ig_uploads"][cid] = {"bytes": 0, "form": form}
                    return self._json(200, {"id": cid, "uri": f"https://rupload.facebook.com/ig-api-upload/v21.0/{cid}"})
                return self._json(404, {"error": {"message": "not found"}})

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
