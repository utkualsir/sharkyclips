"""Fake TikTok Content Posting API + Instagram API (Instagram Login) on 127.0.0.1 for the tests.

Knobs in `state` (1.2.36) make it behave like the real thing on a bad day:
  tt_audited            False: posts other than SELF_ONLY fail like an unaudited client's
  tt_processing_polls   status fetches answer PROCESSING_DOWNLOAD this many times first
  tt_fail_status        the next status fetch answers FAILED with this reason
  tt_rate_limit         the next N video inits answer 429 rate_limit_exceeded
  tt_expire_token       the current access token is refused once (access_token_invalid)
  tt_daily_cap          init answers spam_risk_too_many_posts after this many posts
  ig_processing_polls   container status answers IN_PROGRESS this many times after the bytes
  ig_rate_limit         the next N container creations answer code 4 (rate limit)
  ig_fail_publish       media_publish answers a server error once

1.2.37: the Facebook Graph side too (/v24.0/..., a system user's EAA token, FB_TOKEN). The same
Instagram account sits behind FB_IG_ID; the Reels routes are shared with the Instagram side.
  fb_pages        "pages": the account comes through /me/accounts; "business": only through
                  /me/businesses (a system user's assigned assets); "none": no Instagram account
  fb_no_publish   the token sees the account but may not post (content_publishing_limit: code 10)
  fb_revoked      every Facebook Graph call answers 190 (the token was revoked)
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import threading
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

IG_TOKEN = "IGTOKEN-0123456789abcdef"
FB_TOKEN = "EAAFAKE0123456789abcdefSYSTEMUSER"
FB_IG_ID = "17841400000000001"
FB_IG = {"id": FB_IG_ID, "username": "utkualsirr48", "profile_picture_url": ""}


class FakePlatforms:
    def __init__(self):
        self.state = {"tiktok_uploads": {}, "tiktok_posts": [], "ig_uploads": {}, "ig_posts": [], "codes": {},
                      "account_type": "MEDIA_CREATOR", "privacy_options": ["SELF_ONLY"], "status_polls": 0,
                      "refreshes": 0, "tt_audited": True, "tt_processing_polls": 0, "tt_fail_status": None,
                      "tt_rate_limit": 0, "tt_expire_token": False, "tt_token": "TT-ACCESS", "tt_daily_cap": 99,
                      "tt_status": {}, "tt_comment_disabled": False, "tt_max_seconds": 600,
                      "ig_processing_polls": 0, "ig_rate_limit": 0, "ig_fail_publish": 0, "ig_media": [],
                      "ig_codes": {}, "ig_deleted": [], "ig_container_polls": {}, "tt_videos": [], "calls": [],
                      "fb_pages": "pages", "fb_no_publish": False, "fb_revoked": False, "fb_calls": [],
                      "upload_auth": []}
        self.lock = threading.Lock()
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

            def _tt_auth(self) -> bool:
                st = fake.state
                tok = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                if st["tt_expire_token"] and tok == st["tt_token"]:
                    st["tt_expire_token"] = False
                    st["tt_token"] = st["tt_token"] + "-2"
                    self._json(401, {"error": {"code": "access_token_invalid", "message": "The access token is invalid"}})
                    return False
                return True

            def _fb(self, method: str, path: str, token: str | None, q: dict) -> str | None:
                """A /v24.0/ call: answers it (returns None) or hands back the shared Instagram path."""
                st = fake.state
                st["fb_calls"].append((method, path))
                if st["fb_revoked"] or token != FB_TOKEN:
                    msg = "Error validating access token: The session has been invalidated" if st["fb_revoked"] \
                        else "Invalid OAuth access token - Cannot parse access token"
                    self._json(400, {"error": {"code": 190, "message": msg, "type": "OAuthException"}})
                    return None
                rest = path.removeprefix("/v24.0/")
                if rest == "me":
                    self._json(200, {"id": "61550000000001", "name": "SharkyClips system user"})
                    return None
                if rest == "debug_token":
                    self._json(200, {"data": {"type": "SYSTEM_USER", "is_valid": True, "expires_at": 0,
                                              "scopes": ["instagram_basic", "instagram_content_publish",
                                                         "instagram_manage_insights", "pages_show_list"]}})
                    return None
                ig = {"instagram_business_account": FB_IG}
                if rest == "me/accounts":
                    pages = [{"id": "1001", "name": "Utku", **ig}] if st["fb_pages"] == "pages" else []
                    self._json(200, {"data": pages})
                    return None
                if rest == "me/businesses":
                    owned = [{"id": "1001", **ig}] if st["fb_pages"] == "business" else []
                    self._json(200, {"data": [{"id": "900", "owned_pages": {"data": owned}}]})
                    return None
                if rest == FB_IG_ID and method == "GET" and "status_code" not in q.get("fields", ""):
                    self._json(200, FB_IG)
                    return None
                if rest.startswith(FB_IG_ID) or rest.split("/")[0].startswith(("C", "M")):
                    if rest == f"{FB_IG_ID}/content_publishing_limit" and st["fb_no_publish"]:
                        self._json(400, {"error": {"code": 10, "message": "Application does not have permission"}})
                        return None
                    return "/v21.0/" + rest.replace(FB_IG_ID, "1784", 1)
                self._json(400, {"error": {"code": 100, "message": "Unsupported get request. Object does not exist"}})
                return None

            def do_GET(self):  # noqa: N802
                u = urlparse(self.path)
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                st = fake.state
                st["calls"].append(("GET", u.path))
                if u.path.startswith("/v24.0/"):
                    path = self._fb("GET", u.path, q.get("access_token"), q)
                    if path is None:
                        return
                    u = u._replace(path=path)
                if u.path == "/v2/user/info/":
                    return self._json(200, {"data": {"user": {"display_name": "utku"}}, "error": {"code": "ok"}})
                if u.path == "/access_token":  # IG short -> long token
                    return self._json(200, {"access_token": IG_TOKEN, "token_type": "bearer", "expires_in": 5184000})
                if u.path == "/v21.0/me":
                    if q.get("access_token") != IG_TOKEN:
                        return self._json(400, {"error": {"code": 190, "message": "Invalid OAuth access token"}})
                    return self._json(200, {"user_id": "1784", "username": "utku.clips", "account_type": st["account_type"]})
                if u.path == "/refresh_access_token":
                    st["refreshes"] += 1
                    return self._json(200, {"access_token": q["access_token"], "expires_in": 5184000})
                if u.path == "/v21.0/1784/media":
                    return self._json(200, {"data": list(reversed(st["ig_media"]))[: int(q.get("limit") or 12)]})
                if u.path == "/v21.0/1784/content_publishing_limit":
                    return self._json(200, {"data": [{"quota_usage": len(st["ig_posts"]), "config": {"quota_total": 50}}]})
                if u.path.startswith("/v21.0/") and u.path.endswith("/insights"):
                    return self._json(200, {"data": [{"name": "views", "values": [{"value": 321}]}]})
                if u.path.startswith("/v21.0/"):
                    obj = u.path.split("/")[2]
                    if "status_code" in q.get("fields", ""):
                        up = st["ig_uploads"].get(obj)
                        if not up:
                            return self._json(400, {"error": {"code": 100, "message": "no such container"}})
                        if up.get("published"):
                            return self._json(200, {"status_code": "PUBLISHED"})
                        if not up["bytes"]:
                            return self._json(200, {"status_code": "IN_PROGRESS"})
                        n = st["ig_container_polls"].get(obj, 0)
                        st["ig_container_polls"][obj] = n + 1
                        return self._json(200, {"status_code": "IN_PROGRESS" if n < st["ig_processing_polls"] else "FINISHED"})
                    if "like_count" in q.get("fields", ""):
                        return self._json(200, {"like_count": 12, "comments_count": 3,
                                                "permalink": f"https://www.instagram.com/reel/{obj}/"})
                    if "permalink" in q.get("fields", ""):
                        return self._json(200, {"permalink": f"https://www.instagram.com/reel/{obj}/"})
                return self._json(404, {"error": {"message": "not found"}})

            def do_DELETE(self):  # noqa: N802
                u = urlparse(self.path)
                if u.path.startswith("/v24.0/"):
                    q = {k: v[0] for k, v in parse_qs(u.query).items()}
                    if self._fb("DELETE", u.path, q.get("access_token"), {"fields": "status_code"}) is None:
                        return
                obj = u.path.split("/")[-1]
                fake.state["ig_deleted"].append(obj)
                fake.state["ig_media"] = [m for m in fake.state["ig_media"] if m["id"] != obj]
                return self._json(200, {"success": True})

            def do_PUT(self):  # noqa: N802
                u = urlparse(self.path)
                if u.path.startswith("/upload/"):
                    pid = u.path.split("/")[2]
                    data = self._body()
                    fake.state["tiktok_uploads"].setdefault(pid, []).append(
                        {"range": self.headers.get("Content-Range"), "len": len(data), "type": self.headers.get("Content-Type")})
                    fake.state["tt_status"][pid] = "uploaded"
                    return self._json(201, {})
                return self._json(404, {})

            def do_POST(self):  # noqa: N802
                u = urlparse(self.path)
                raw = self._body()
                st = fake.state
                st["calls"].append(("POST", u.path))
                ctype = self.headers.get("Content-Type") or ""
                form = {k: v[0] for k, v in parse_qs(raw.decode(errors="replace")).items()} \
                    if "x-www-form-urlencoded" in ctype else {}
                if u.path.startswith("/v24.0/"):
                    path = self._fb("POST", u.path, form.get("access_token"), {"fields": "status_code"})
                    if path is None:
                        return
                    u = u._replace(path=path)
                if u.path == "/v2/oauth/token/":
                    if form.get("grant_type") == "authorization_code":
                        want = st["codes"].get(form.get("code"))
                        ok = want and base64.urlsafe_b64encode(hashlib.sha256(form["code_verifier"].encode()).digest()
                                                              ).rstrip(b"=").decode() == want
                        if not ok:
                            return self._json(400, {"error": "invalid_grant", "error_description": "bad code or verifier"})
                    else:
                        st["refreshes"] += 1
                        if form.get("refresh_token") == "REVOKED":
                            return self._json(400, {"error": "invalid_grant", "error_description": "refresh token revoked"})
                    return self._json(200, {"access_token": st["tt_token"], "refresh_token": "TT-REFRESH", "expires_in": 86400,
                                            "refresh_expires_in": 31536000, "open_id": "o1",
                                            "scope": "user.info.basic,video.publish,video.list"})
                if u.path == "/oauth/access_token":  # Instagram Login: code -> short-lived token
                    if form.get("code") not in st["ig_codes"]:
                        return self._json(400, {"error_type": "OAuthException", "code": 400,
                                                "error": {"code": 400, "message": "Invalid authorization code"}})
                    return self._json(200, {"data": [{"access_token": "IG-SHORT", "user_id": "1784",
                                                      "permissions": "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights"}]})
                if u.path.startswith("/v2/"):
                    if not self._tt_auth():
                        return
                if u.path == "/v2/post/publish/creator_info/query/":
                    return self._json(200, {"data": {"privacy_level_options": st["privacy_options"],
                                                     "creator_username": "utkualsirr", "creator_nickname": "utku alsir",
                                                     "creator_avatar_url": "",
                                                     "comment_disabled": st["tt_comment_disabled"], "duet_disabled": False,
                                                     "stitch_disabled": True,
                                                     "max_video_post_duration_sec": st["tt_max_seconds"]},
                                            "error": {"code": "ok"}})
                if u.path == "/v2/post/publish/video/init/":
                    body = json.loads(raw)
                    if st["tt_rate_limit"] > 0:
                        st["tt_rate_limit"] -= 1
                        return self._json(429, {"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}})
                    pi = body.get("post_info") or {}
                    if pi.get("privacy_level") not in st["privacy_options"]:
                        return self._json(400, {"error": {"code": "privacy_level_option_mismatch", "message": "bad privacy"}})
                    if not st["tt_audited"] and pi.get("privacy_level") != "SELF_ONLY":
                        return self._json(403, {"error": {"code": "unaudited_client_can_only_post_to_private_accounts",
                                                          "message": "unaudited"}})
                    if pi.get("brand_content_toggle") and pi.get("privacy_level") == "SELF_ONLY":
                        return self._json(400, {"error": {"code": "invalid_params", "message": "branded content can't be private"}})
                    if len(st["tiktok_posts"]) >= st["tt_daily_cap"]:
                        return self._json(403, {"error": {"code": "spam_risk_too_many_posts", "message": "daily cap"}})
                    pid = f"p{len(st['tiktok_posts']) + 1}"
                    st["tiktok_posts"].append({"id": pid, **body})
                    st["tt_status"][pid] = "init"
                    port = self.server.server_address[1]
                    return self._json(200, {"data": {"publish_id": pid, "upload_url": f"http://127.0.0.1:{port}/upload/{pid}"},
                                            "error": {"code": "ok"}})
                if u.path == "/v2/post/publish/status/fetch/":
                    st["status_polls"] += 1
                    pid = json.loads(raw).get("publish_id")
                    if st["tt_fail_status"]:
                        reason, st["tt_fail_status"] = st["tt_fail_status"], None
                        st["tt_status"][pid] = "failed"
                        return self._json(200, {"data": {"status": "FAILED", "fail_reason": reason}, "error": {"code": "ok"}})
                    if st["tt_status"].get(pid) == "failed":
                        return self._json(200, {"data": {"status": "FAILED", "fail_reason": "internal"}, "error": {"code": "ok"}})
                    if st["tt_status"].get(pid) == "init":
                        return self._json(200, {"data": {"status": "PROCESSING_UPLOAD"}, "error": {"code": "ok"}})
                    if st["tt_processing_polls"] > 0:
                        st["tt_processing_polls"] -= 1
                        return self._json(200, {"data": {"status": "PROCESSING_DOWNLOAD"}, "error": {"code": "ok"}})
                    return self._json(200, {"data": {"status": "PUBLISH_COMPLETE"}, "error": {"code": "ok"}})
                if u.path == "/v2/video/list/":
                    return self._json(200, {"data": {"videos": st["tt_videos"], "has_more": False, "cursor": 0},
                                            "error": {"code": "ok"}})
                if u.path.startswith("/ig-api-upload/"):
                    cid = u.path.split("/")[-1]
                    up = st["ig_uploads"].setdefault(cid, {"bytes": 0})
                    up["bytes"] = len(raw)
                    up["file_size"] = self.headers.get("file_size")
                    up["auth"] = self.headers.get("Authorization")
                    st["upload_auth"].append((u.path, up["auth"]))
                    return self._json(200, {"success": True})
                if u.path.endswith("/media_publish"):
                    if st["ig_fail_publish"] > 0:
                        st["ig_fail_publish"] -= 1
                        return self._json(500, {"error": {"code": 2, "message": "Service temporarily unavailable"}})
                    cid = form.get("creation_id", "")
                    if st["ig_uploads"].get(cid, {}).get("published"):
                        return self._json(400, {"error": {"code": 100, "message": "already published"}})
                    st["ig_posts"].append(form)
                    mid = "M" + cid
                    st["ig_uploads"].setdefault(cid, {"bytes": 0})["published"] = True
                    cap = st["ig_uploads"][cid].get("form", {}).get("caption", "")
                    st["ig_media"].append({"id": mid, "caption": cap, "media_type": "VIDEO",
                                           "permalink": f"https://www.instagram.com/reel/{mid}/",
                                           "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")})
                    return self._json(200, {"id": mid})
                if u.path.endswith("/media"):
                    if st["ig_rate_limit"] > 0:
                        st["ig_rate_limit"] -= 1
                        return self._json(400, {"error": {"code": 4, "message": "Application request limit reached"}})
                    cid = f"C{len(st['ig_uploads']) + 1}"
                    st["ig_uploads"][cid] = {"bytes": 0, "form": form, "at": time.time()}
                    return self._json(200, {"id": cid, "uri": f"https://rupload.facebook.com/ig-api-upload/v21.0/{cid}"})
                return self._json(404, {"error": {"message": "not found"}})

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
