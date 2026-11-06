"""TikTok and Instagram Reels (1.2.18), next to YouTube.

Two ways to post, and the app always says which one is active:
  semi  (default) the clip is exported with the platform's preset into Downloads/SharkyClips, the
        caption + hashtags go to the clipboard and the platform's upload page opens: you drop the
        file in and press Post. Works for everyone, no account linking.
  api   automatic, through the official APIs, after a guided setup with YOUR OWN developer app:
        TikTok Content Posting API (Login Kit + PKCE, loopback redirect), Instagram Graph API
        (Instagram Login token of a Business / Creator account, resumable Reels upload).
        Both platforms review apps first: until TikTok approves yours, its posts are private
        ("Only me"); until Meta approves yours, only the app's own accounts can post.

Tokens are kept encrypted (secretstore) in <settings>/platforms/<name>/token.enc.
Tests point the API hosts at fake servers: SHARKYCLIPS_TIKTOK_ENDPOINT / SHARKYCLIPS_IG_ENDPOINT
(loopback only).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode, urlparse

from . import config, secretstore
from .errors import SharkyClipsError

PLATFORMS = ("youtube", "tiktok", "reels")
PRESET = {"tiktok": "tiktok", "reels": "instagram_reels", "youtube": "youtube_shorts"}
UPLOAD_PAGE = {"tiktok": "https://www.tiktok.com/tiktokstudio/upload",
               "reels": "https://www.instagram.com/"}
CAPTION_MAX = {"tiktok": 2200, "reels": 2200}
HASHTAG_MAX = {"tiktok": 10, "reels": 30}
TIKTOK_SCOPES = "user.info.basic,video.publish,video.upload"
CHUNK = 10 * 1024 * 1024
ProgressFn = Callable[[float], None]


def _endpoint(env: str, default: str) -> str:
    url = os.environ.get(env)
    if url:
        host = urlparse(url).hostname or ""
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise SharkyClipsError(f"{env} may only point at this computer.")
        return url.rstrip("/")
    return default


def tiktok_api() -> str:
    return _endpoint("SHARKYCLIPS_TIKTOK_ENDPOINT", "https://open.tiktokapis.com")


def tiktok_auth_url() -> str:
    return _endpoint("SHARKYCLIPS_TIKTOK_ENDPOINT", "https://www.tiktok.com")


def ig_api() -> str:
    return _endpoint("SHARKYCLIPS_IG_ENDPOINT", "https://graph.instagram.com")


def ig_upload_api() -> str:
    return _endpoint("SHARKYCLIPS_IG_ENDPOINT", "https://rupload.facebook.com")


IG_VERSION = "v21.0"


def _http():
    import requests

    return requests


def folder(name: str) -> Path:
    return config.config_dir() / "platforms" / name


def _token_path(name: str) -> Path:
    return folder(name) / "token.enc"


def load_token(name: str) -> dict | None:
    return secretstore.load(_token_path(name))


def save_token(name: str, data: dict) -> None:
    folder(name).mkdir(parents=True, exist_ok=True)
    secretstore.save(_token_path(name), data)


def forget(name: str) -> None:
    _token_path(name).unlink(missing_ok=True)
    app = folder(name) / "app.enc"
    app.unlink(missing_ok=True)


def load_app(name: str) -> dict | None:
    return secretstore.load(folder(name) / "app.enc")


def save_app(name: str, data: dict) -> None:
    folder(name).mkdir(parents=True, exist_ok=True)
    secretstore.save(folder(name) / "app.enc", data)


# ===================================================================== status / mode


def connected(name: str) -> bool:
    tok = load_token(name)
    return bool(tok and tok.get("access_token"))


def mode(name: str) -> str:
    """'api' only when connected AND the user turned automatic posting on; else 'semi'."""
    if name == "youtube":
        return "api"
    want = (config.get("platform_modes") or {}).get(name)
    return "api" if want == "api" and connected(name) else "semi"


def status(name: str) -> dict:
    tok = load_token(name) or {}
    app = load_app(name) or {}
    out = {"platform": name, "mode": mode(name), "connected": bool(tok.get("access_token")),
           "account": tok.get("account"), "audited": bool(app.get("audited")),
           "has_app": bool(app.get("client_key") or app.get("app_id") or name == "reels"),
           "upload_page": UPLOAD_PAGE.get(name), "preset": PRESET[name]}
    if name == "tiktok":
        out["privacy_note"] = "self_only" if not app.get("audited") else None
    if name == "reels":
        out["privacy_note"] = "app_review" if not app.get("audited") else None
        out["expires_at"] = tok.get("expires_at")
    return out


def set_mode(name: str, value: str) -> dict:
    if name not in ("tiktok", "reels") or value not in ("semi", "api"):
        raise SharkyClipsError("Unknown platform or mode.")
    if value == "api" and not connected(name):
        raise SharkyClipsError("Connect the account first.", "Follow the guided setup, or keep the semi-automatic mode.")
    modes = dict(config.get("platform_modes") or {})
    modes[name] = value
    config.update(platform_modes=modes)
    return status(name)


def set_audited(name: str, audited: bool) -> dict:
    app = load_app(name) or {}
    app["audited"] = bool(audited)
    save_app(name, app)
    return status(name)


# ===================================================================== captions


def caption(platform: str, title: str, description: str, hashtags: list[str], note: str | None = None) -> str:
    """Title + the first line of the description (+ `note`, e.g. the AI-voice line) + hashtags,
    within the platform's limits. The note is never cut off."""
    tags = []
    for h in hashtags:
        h = "#" + str(h).lstrip("#").strip()
        if len(h) > 1 and h.lower() not in (t.lower() for t in tags):
            tags.append(h)
    tags = tags[: HASHTAG_MAX.get(platform, 10)]
    first = next((ln.strip() for ln in (description or "").splitlines()
                  if ln.strip() and not ln.strip().startswith("#")), "")
    body = title.strip()
    if first and first.lower() != body.lower():
        body += "\n\n" + first
    extra = f"\n\n{note.strip()}" if note and note.strip() else ""
    tail = ("\n\n" + " ".join(tags)) if tags else ""
    text = (body + extra + tail).strip()
    limit = CAPTION_MAX.get(platform, 2200)
    if len(text) > limit:
        text = body[: max(0, limit - len(extra) - len(tail) - 1)].rstrip() + "…" + extra + tail
    return text


# ===================================================================== TikTok


_pending: dict[str, dict] = {}
_plock = threading.Lock()


def tiktok_redirect(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/platforms/tiktok/callback"


def tiktok_start(client_key: str, client_secret: str, port: int) -> str:
    """Save the user's app and return the TikTok sign-in URL (PKCE)."""
    client_key, client_secret = client_key.strip(), client_secret.strip()
    if not client_key or not client_secret:
        raise SharkyClipsError("Enter the Client key and Client secret of your TikTok app.",
                               "developers.tiktok.com -> Manage apps -> your app -> Credentials.")
    app = load_app("tiktok") or {}
    save_app("tiktok", {**app, "client_key": client_key, "client_secret": client_secret})
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    with _plock:
        _pending.clear()
        _pending[state] = {"verifier": verifier, "redirect": tiktok_redirect(port), "at": time.time()}
    q = {"client_key": client_key, "scope": TIKTOK_SCOPES, "response_type": "code",
         "redirect_uri": tiktok_redirect(port), "state": state, "code_challenge": challenge,
         "code_challenge_method": "S256"}
    return f"{tiktok_auth_url()}/v2/auth/authorize/?{urlencode(q)}"


def tiktok_finish(code: str, state: str) -> dict:
    with _plock:
        p = _pending.pop(state, None)
    if p is None or time.time() - p["at"] > 900:
        raise SharkyClipsError("This TikTok sign-in expired.", "Start the connection again.")
    app = load_app("tiktok") or {}
    r = _http().post(f"{tiktok_api()}/v2/oauth/token/", timeout=30, data={
        "client_key": app.get("client_key"), "client_secret": app.get("client_secret"), "code": code,
        "grant_type": "authorization_code", "redirect_uri": p["redirect"], "code_verifier": p["verifier"]})
    tok = _tiktok_json(r, "sign-in")
    _save_tiktok_token(tok)
    try:
        info = tiktok_call("GET", "/v2/user/info/?fields=open_id,display_name")
        name = ((info.get("data") or {}).get("user") or {}).get("display_name")
    except SharkyClipsError:
        name = None
    t = load_token("tiktok") or {}
    t["account"] = name
    save_token("tiktok", t)
    return status("tiktok")


def _save_tiktok_token(tok: dict) -> None:
    now = time.time()
    old = load_token("tiktok") or {}
    save_token("tiktok", {**old, "access_token": tok["access_token"],
                          "refresh_token": tok.get("refresh_token") or old.get("refresh_token"),
                          "expires_at": now + float(tok.get("expires_in") or 86400),
                          "refresh_expires_at": now + float(tok.get("refresh_expires_in") or 31536000),
                          "scope": tok.get("scope") or old.get("scope") or "", "open_id": tok.get("open_id")})


def _tiktok_json(r, what: str) -> dict:
    try:
        d = r.json()
    except ValueError:
        d = {}
    err = d.get("error")
    if isinstance(err, dict):
        code, msg = err.get("code"), err.get("message")
    else:
        code, msg = err, d.get("error_description")
    if r.status_code >= 400 or (code and code != "ok"):
        raise SharkyClipsError(f"TikTok refused the {what}: {msg or code or r.status_code}.", _tiktok_hint(str(code)))
    return d


def _tiktok_hint(code: str) -> str | None:
    return {
        "access_token_invalid": "Connect TikTok again in Settings.",
        "scope_not_authorized": "Your TikTok app needs the Content Posting API with video.publish: add it in the developer portal.",
        "unaudited_client_can_only_post_to_private_accounts": "Until TikTok reviews your app, set your TikTok account to private or use the semi-automatic mode.",
        "spam_risk_too_many_posts": "TikTok's daily posting limit is reached: try again tomorrow.",
        "rate_limit_exceeded": "Too many requests: wait a minute and try again.",
        "invalid_grant": "Connect TikTok again in Settings.",
    }.get(code)


def _tiktok_access() -> str:
    tok = load_token("tiktok")
    if not tok or not tok.get("access_token"):
        raise SharkyClipsError("TikTok isn't connected.", "Connect it in Settings, or use the semi-automatic mode.")
    if tok.get("expires_at", 0) - time.time() < 120:
        app = load_app("tiktok") or {}
        r = _http().post(f"{tiktok_api()}/v2/oauth/token/", timeout=30, data={
            "client_key": app.get("client_key"), "client_secret": app.get("client_secret"),
            "grant_type": "refresh_token", "refresh_token": tok.get("refresh_token")})
        _save_tiktok_token(_tiktok_json(r, "refresh"))
        tok = load_token("tiktok") or {}
    return tok["access_token"]


def tiktok_call(method: str, path: str, body: dict | None = None) -> dict:
    r = _http().request(method, f"{tiktok_api()}{path}", timeout=60, json=body,
                        headers={"Authorization": f"Bearer {_tiktok_access()}",
                                 "Content-Type": "application/json; charset=UTF-8"})
    return _tiktok_json(r, "request")


def tiktok_post(file: Path, text: str, on_progress: ProgressFn | None = None,
                poll: float = 3.0, cancel: threading.Event | None = None, ai_label: bool = False) -> dict:
    """Direct Post (FILE_UPLOAD) -> {"publish_id", "status", "privacy"}. Private until audited.
    ai_label: TikTok's "AI-generated content" label (post_info.is_aigc, 1.2.20)."""
    info = tiktok_call("POST", "/v2/post/publish/creator_info/query/")
    opts = (info.get("data") or {}).get("privacy_level_options") or ["SELF_ONLY"]
    audited = bool((load_app("tiktok") or {}).get("audited"))
    privacy = "PUBLIC_TO_EVERYONE" if audited and "PUBLIC_TO_EVERYONE" in opts else "SELF_ONLY"
    if privacy not in opts:
        privacy = opts[0]
    size = file.stat().st_size
    chunk = size if size <= 64 * 1024 * 1024 else CHUNK
    count = max(1, size // chunk)
    post_info = {"title": text[:2200], "privacy_level": privacy, "disable_comment": False,
                 "disable_duet": False, "disable_stitch": False}
    if ai_label:
        post_info["is_aigc"] = True
    init = tiktok_call("POST", "/v2/post/publish/video/init/", {
        "post_info": post_info,
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": count}})
    data = init.get("data") or {}
    url, pid = data.get("upload_url"), data.get("publish_id")
    if not url or not pid:
        raise SharkyClipsError("TikTok didn't give an upload address.", "Try again later.")
    with open(file, "rb") as f:
        for i in range(count):
            a = i * chunk
            b = size - 1 if i == count - 1 else a + chunk - 1
            f.seek(a)
            part = f.read(b - a + 1)
            r = _http().put(url, data=part, timeout=300, headers={
                "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                "Content-Range": f"bytes {a}-{b}/{size}"})
            if r.status_code not in (200, 201, 206):
                raise SharkyClipsError(f"TikTok stopped the upload ({r.status_code}).", "Try again later.")
            if on_progress:
                on_progress(0.9 * (b + 1) / size)
    end = time.time() + 600
    while time.time() < end:
        if cancel is not None and cancel.is_set():
            break
        st = tiktok_call("POST", "/v2/post/publish/status/fetch/", {"publish_id": pid})
        s = (st.get("data") or {}).get("status")
        if s in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            if on_progress:
                on_progress(1.0)
            return {"publish_id": pid, "status": "published", "privacy": privacy.lower()}
        if s == "FAILED":
            reason = (st.get("data") or {}).get("fail_reason") or "unknown"
            raise SharkyClipsError(f"TikTok couldn't publish the video ({reason}).", _tiktok_hint(reason))
        time.sleep(poll)
    return {"publish_id": pid, "status": "processing", "privacy": privacy.lower()}


# ===================================================================== Instagram


def ig_connect(token: str) -> dict:
    """Check a pasted Instagram Login access token (Business / Creator account) and keep it."""
    token = token.strip()
    if len(token) < 20:
        raise SharkyClipsError("Paste the long access token of your Instagram app.",
                               "Meta for Developers -> your app -> Instagram -> API setup -> Generate token.")
    r = _http().get(f"{ig_api()}/{IG_VERSION}/me", timeout=30,
                    params={"fields": "user_id,username,account_type", "access_token": token})
    d = _ig_json(r, "connection")
    kind = (d.get("account_type") or "").upper()
    if kind and kind not in ("BUSINESS", "MEDIA_CREATOR", "CREATOR"):
        raise SharkyClipsError("Instagram only lets Business or Creator accounts post through its API.",
                               "Switch the account to Creator in the Instagram app (Settings -> Account type), or keep the semi-automatic mode.")
    save_token("reels", {"access_token": token, "user_id": str(d.get("user_id") or d.get("id")),
                         "account": d.get("username"), "saved_at": time.time(),
                         "expires_at": time.time() + 60 * 86400})
    if load_app("reels") is None:
        save_app("reels", {"audited": False})
    return status("reels")


def _ig_json(r, what: str) -> dict:
    try:
        d = r.json()
    except ValueError:
        d = {}
    if r.status_code >= 400 or "error" in d:
        e = d.get("error") or {}
        code = e.get("code")
        hint = {190: "The token expired or was revoked: make a new one and paste it in Settings.",
                10: "Your Meta app lacks the instagram_business_content_publish permission.",
                200: "Your Meta app lacks the instagram_business_content_publish permission.",
                9007: "Instagram is still processing the video: try again in a minute.",
                4: "Instagram's hourly limit is reached: try again later.",
                }.get(code)
        raise SharkyClipsError(f"Instagram refused the {what}: {e.get('message') or r.status_code}.", hint)
    return d


def _ig_token() -> dict:
    tok = load_token("reels")
    if not tok or not tok.get("access_token"):
        raise SharkyClipsError("Instagram isn't connected.", "Connect it in Settings, or use the semi-automatic mode.")
    if time.time() - float(tok.get("saved_at") or 0) > 30 * 86400:  # long-lived tokens: refresh monthly
        try:
            r = _http().get(f"{ig_api()}/refresh_access_token", timeout=30,
                            params={"grant_type": "ig_refresh_token", "access_token": tok["access_token"]})
            d = _ig_json(r, "token refresh")
            tok.update(access_token=d["access_token"], saved_at=time.time(),
                       expires_at=time.time() + float(d.get("expires_in") or 60 * 86400))
            save_token("reels", tok)
        except SharkyClipsError:
            pass  # still valid for a while; the next post tries again
    return tok


def ig_post(file: Path, text: str, on_progress: ProgressFn | None = None, poll: float = 3.0,
            cancel: threading.Event | None = None, ai_label: bool = False) -> dict:
    """Reels upload: container (resumable) -> bytes to rupload -> wait FINISHED -> publish.
    ai_label: Instagram's AI self-disclosure (is_ai_generated, 1.2.20)."""
    tok = _ig_token()
    acc, uid = tok["access_token"], tok["user_id"]
    data = {"media_type": "REELS", "upload_type": "resumable", "caption": text[:2200], "share_to_feed": "true",
            "access_token": acc}
    if ai_label:
        data["is_ai_generated"] = "true"
    r = _http().post(f"{ig_api()}/{IG_VERSION}/{uid}/media", timeout=60, data=data)
    cont = _ig_json(r, "upload")
    cid = cont.get("id")
    if not cid:
        raise SharkyClipsError("Instagram didn't create the upload.", "Try again later.")
    size = file.stat().st_size
    with open(file, "rb") as f:
        r = _http().post(f"{ig_upload_api()}/ig-api-upload/{IG_VERSION}/{cid}", data=f, timeout=900, headers={
            "Authorization": f"OAuth {acc}", "offset": "0", "file_size": str(size)})
    _ig_json(r, "upload")
    if on_progress:
        on_progress(0.8)
    end = time.time() + 900
    while True:
        if cancel is not None and cancel.is_set():
            raise SharkyClipsError("Cancelled.")
        r = _http().get(f"{ig_api()}/{IG_VERSION}/{cid}", timeout=30,
                        params={"fields": "status_code,status", "access_token": acc})
        st = _ig_json(r, "upload").get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise SharkyClipsError("Instagram couldn't process the video.",
                                   "Reels need MP4 H.264, 3-180 s; the Reels preset makes that. Try again.")
        if time.time() > end:
            raise SharkyClipsError("Instagram is taking too long with this video.", "Try again later.")
        time.sleep(poll)
    r = _http().post(f"{ig_api()}/{IG_VERSION}/{uid}/media_publish", timeout=60,
                     data={"creation_id": cid, "access_token": acc})
    media = _ig_json(r, "publish").get("id")
    url = None
    try:
        r = _http().get(f"{ig_api()}/{IG_VERSION}/{media}", timeout=30,
                        params={"fields": "permalink", "access_token": acc})
        url = _ig_json(r, "link").get("permalink")
    except SharkyClipsError:
        pass
    if on_progress:
        on_progress(1.0)
    return {"media_id": media, "status": "published", "url": url}


# ===================================================================== per-clip record


def record_path(project) -> Path:
    return project.dir / "platform_uploads.json"


_rlock = threading.RLock()


def records(project) -> dict:
    p = record_path(project)
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        return {}


def record(project, cid: str, platform: str, **data) -> dict:
    from .project import write_json_atomic

    with _rlock:
        all_ = records(project)
        cur = {**(all_.get(cid) or {}).get(platform, {}), **data, "at": time.time()}
        all_.setdefault(cid, {})[platform] = cur
        write_json_atomic(record_path(project), all_)
        return cur
