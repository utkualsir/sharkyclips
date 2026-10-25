"""Direct YouTube upload with the official, free YouTube Data API v3.

Everything stays on this computer: the user makes their own (free) Google Cloud OAuth client
of type "Desktop app" and loads its JSON in Settings. Files in ~/.sharkyclips/youtube/:

  client.json    client id + secret of the user's own OAuth client
  token.json     access + refresh token (never leaves this PC)
  quota.json     API units used today (resets at midnight Pacific Time, like Google's counter)
  sessions.json  resumable upload URLs, so a restart continues an upload instead of restarting it

OAuth: authorization code + PKCE with a loopback redirect to this server
(http://127.0.0.1:<port>/), which Google allows for Desktop app clients on any port.

Quota (default 10,000 units a day per Google Cloud project): an upload costs 1,600 units,
a thumbnail 50, reading statistics 1 per 50 videos.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import config
from .errors import SharkyClipsError
from .project import read_json, write_json_atomic

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3"
SCOPES = ("https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly")
COST = {"upload": 1600, "thumbnail": 50, "list": 1}
DEFAULT_DAILY_QUOTA = 10_000
CHUNK = 8 * 1024 * 1024  # resumable upload chunk (multiple of 256 KiB)
PRIVACY = ("private", "unlisted", "public")
CATEGORY = {"gaming": "20", "study": "27", "music": "10"}  # Gaming, Education, Music
CONSOLE = "https://console.cloud.google.com"

_lock = threading.RLock()
_pending: dict[str, dict] = {}  # OAuth state -> {verifier, redirect_uri, created}


def folder() -> Path:
    return config.config_dir() / "youtube"


def _read(name: str) -> dict | None:
    path = folder() / name
    try:
        return read_json(path) if path.is_file() else None
    except Exception:  # noqa: BLE001 - a broken file counts as missing
        return None


def _write(name: str, data: dict) -> None:
    write_json_atomic(folder() / name, data)
    if os.name != "nt":
        try:
            os.chmod(folder() / name, 0o600)
        except OSError:
            pass


def _http():
    import requests

    return requests


# ------------------------------------------------------------------ Pacific time (quota day)


def _nth_sunday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def pacific_now(now: datetime | None = None) -> datetime:
    """US Pacific time without a tz database (Windows has none): DST from the 2nd Sunday of
    March 02:00 to the 1st Sunday of November 02:00 local time."""
    now = now or datetime.now(timezone.utc)
    utc = now.astimezone(timezone.utc).replace(tzinfo=None)
    y = utc.year
    dst_start = datetime.combine(_nth_sunday(y, 3, 2), datetime.min.time()) + timedelta(hours=10)  # 02:00 PST
    dst_end = datetime.combine(_nth_sunday(y, 11, 1), datetime.min.time()) + timedelta(hours=9)  # 02:00 PDT
    offset = 7 if dst_start <= utc < dst_end else 8
    return utc - timedelta(hours=offset)


def next_reset(now: datetime | None = None) -> datetime:
    """UTC time of the next quota reset (midnight Pacific)."""
    now = now or datetime.now(timezone.utc)
    pt = pacific_now(now)
    midnight = datetime.combine(pt.date() + timedelta(days=1), datetime.min.time())
    return now.astimezone(timezone.utc) + (midnight - pt)


# ------------------------------------------------------------------ quota


def daily_quota() -> int:
    try:
        return max(100, int(config.get("youtube_daily_quota") or DEFAULT_DAILY_QUOTA))
    except (TypeError, ValueError):
        return DEFAULT_DAILY_QUOTA


def quota_used(now: datetime | None = None) -> int:
    q = _read("quota.json") or {}
    return int(q.get("used") or 0) if q.get("day") == pacific_now(now).date().isoformat() else 0


def spend(units: int) -> None:
    with _lock:
        day = pacific_now().date().isoformat()
        q = _read("quota.json") or {}
        used = int(q.get("used") or 0) if q.get("day") == day else 0
        _write("quota.json", {"day": day, "used": used + units})


def quota_view(now: datetime | None = None) -> dict:
    used = quota_used(now)
    limit = daily_quota()
    per = COST["upload"] + COST["thumbnail"]
    return {"used": used, "limit": limit, "uploads_left": max(0, (limit - used) // COST["upload"]),
            "uploads_left_with_thumbnail": max(0, (limit - used) // per),
            "resets_at": next_reset(now).isoformat(timespec="seconds")}


def check_quota(units: int) -> None:
    left = daily_quota() - quota_used()
    if units > left:
        reset = next_reset().astimezone().strftime("%H:%M")
        raise SharkyClipsError("Today's YouTube upload limit is used up.",
                               f"Google's free API quota resets at midnight Pacific Time ({reset} here).")


# ------------------------------------------------------------------ client + tokens


def load_client() -> dict | None:
    return _read("client.json")


def set_client(raw: str | bytes | dict) -> dict:
    """Store the user's OAuth client (the JSON downloaded from Google Cloud Console)."""
    try:
        data = raw if isinstance(raw, dict) else json.loads(raw)
    except (ValueError, TypeError):
        raise SharkyClipsError("That file isn't a Google OAuth client JSON.",
                               "Download it from Google Cloud Console > Clients > your Desktop app.") from None
    kind = "installed" if "installed" in data else "web" if "web" in data else None
    body = data.get(kind) if kind else data
    cid, secret = str((body or {}).get("client_id") or ""), str((body or {}).get("client_secret") or "")
    if not cid.endswith(".apps.googleusercontent.com"):
        raise SharkyClipsError("That file has no Google OAuth client ID.",
                               "Download the JSON of an OAuth client of type 'Desktop app'.")
    if kind == "web":
        raise SharkyClipsError("This is a 'Web application' client.",
                               "Create an OAuth client of type 'Desktop app' instead (it allows the local "
                               "redirect SharkyClips uses).")
    client = {"client_id": cid, "client_secret": secret, "project_id": (body or {}).get("project_id"),
              "saved_at": _now()}
    _write("client.json", client)
    (folder() / "token.json").unlink(missing_ok=True)  # a new client needs a new sign-in
    return client


def remove_client() -> None:
    disconnect()
    (folder() / "client.json").unlink(missing_ok=True)


def _token() -> dict | None:
    return _read("token.json")


def connected() -> bool:
    t = _token()
    return bool(t and t.get("refresh_token"))


def status() -> dict:
    client = load_client()
    tok = _token() or {}
    return {"client": bool(client), "client_id": (client or {}).get("client_id"),
            "project_id": (client or {}).get("project_id"), "connected": connected(),
            "channel": tok.get("channel"), "connected_at": tok.get("connected_at"),
            "quota": quota_view(), "scopes": list(SCOPES)}


def auth_url(redirect_uri: str) -> str:
    client = load_client()
    if not client:
        raise SharkyClipsError("Load your Google OAuth client first (Settings > YouTube, step 5).")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    with _lock:
        for k in [k for k, v in _pending.items() if time.time() - v["created"] > 900]:
            _pending.pop(k, None)
        _pending[state] = {"verifier": verifier, "redirect_uri": redirect_uri, "created": time.time()}
    q = {"client_id": client["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
         "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent", "state": state,
         "code_challenge": challenge, "code_challenge_method": "S256", "include_granted_scopes": "true"}
    return AUTH_URL + "?" + urllib.parse.urlencode(q)


def is_pending(state: str | None) -> bool:
    return bool(state) and state in _pending


def finish_auth(code: str, state: str) -> dict:
    with _lock:
        pend = _pending.pop(state, None)
    if pend is None:
        raise SharkyClipsError("This sign-in link has expired.", "Click Connect YouTube again.")
    client = load_client() or {}
    res = _http().post(TOKEN_URL, data={
        "code": code, "client_id": client.get("client_id"), "client_secret": client.get("client_secret"),
        "redirect_uri": pend["redirect_uri"], "grant_type": "authorization_code",
        "code_verifier": pend["verifier"]}, timeout=30)
    data = _json(res)
    if res.status_code != 200 or "refresh_token" not in data:
        raise SharkyClipsError(f"Google refused the sign-in: {data.get('error_description') or data.get('error') or res.status_code}",
                               "Check that your Google account is a test user of the OAuth app (step 3).")
    tok = {"access_token": data["access_token"], "refresh_token": data["refresh_token"],
           "expires_at": time.time() + int(data.get("expires_in") or 3600) - 60,
           "scope": data.get("scope"), "connected_at": _now()}
    _write("token.json", tok)
    try:
        ch = channel()
        tok["channel"] = ch
        _write("token.json", tok)
    except SharkyClipsError:
        pass
    return status()


def disconnect() -> None:
    tok = _token()
    if tok and tok.get("refresh_token"):
        try:
            _http().post(REVOKE_URL, params={"token": tok["refresh_token"]}, timeout=10)
        except Exception:  # noqa: BLE001 - offline: forget it locally anyway
            pass
    (folder() / "token.json").unlink(missing_ok=True)


def access_token() -> str:
    with _lock:
        tok = _token()
        if not tok or not tok.get("refresh_token"):
            raise SharkyClipsError("YouTube isn't connected.", "Settings > YouTube > Connect YouTube.")
        if tok.get("access_token") and time.time() < float(tok.get("expires_at") or 0):
            return tok["access_token"]
        client = load_client() or {}
        res = _http().post(TOKEN_URL, data={
            "client_id": client.get("client_id"), "client_secret": client.get("client_secret"),
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=30)
        data = _json(res)
        if res.status_code != 200:
            if data.get("error") == "invalid_grant":
                (folder() / "token.json").unlink(missing_ok=True)
                raise SharkyClipsError("YouTube signed SharkyClips out.",
                                       "Connect YouTube again. (Apps in Google's 'Testing' mode are signed out "
                                       "after 7 days - publish the app in the Google Cloud console to stop that.)")
            raise SharkyClipsError(f"Could not refresh the YouTube sign-in ({data.get('error') or res.status_code}).")
        tok["access_token"] = data["access_token"]
        tok["expires_at"] = time.time() + int(data.get("expires_in") or 3600) - 60
        _write("token.json", tok)
        return tok["access_token"]


def _expire_access() -> None:
    with _lock:
        tok = _token()
        if tok:
            tok["expires_at"] = 0
            _write("token.json", tok)


def _json(res) -> dict:
    try:
        d = res.json()
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _api_error(res, what: str) -> SharkyClipsError:
    data = _json(res)
    err = data.get("error") or {}
    reason = ""
    if isinstance(err, dict):
        reason = ((err.get("errors") or [{}])[0]).get("reason") or err.get("status") or ""
        msg = err.get("message") or str(res.status_code)
    else:
        msg = str(err)
    hints = {
        "quotaExceeded": "Google's daily API quota is used up; it resets at midnight Pacific Time.",
        "uploadLimitExceeded": "YouTube's own daily upload limit for this channel is reached.",
        "youtubeSignupRequired": "This Google account has no YouTube channel yet: create one on youtube.com.",
        "forbidden": "Is the YouTube Data API v3 enabled in your Google Cloud project (step 2)?",
        "accessNotConfigured": "Enable the YouTube Data API v3 in your Google Cloud project (step 2).",
        "invalidPublishAt": "The scheduled time must be in the future.",
    }
    if reason == "quotaExceeded":
        spend(daily_quota())  # Google says it's gone: show 0 left until the reset
    return SharkyClipsError(f"YouTube {what} failed: {msg}"[:400], hints.get(reason))


def _get(path: str, params: dict) -> dict:
    res = _http().get(f"{API}/{path}", params=params, headers={"Authorization": f"Bearer {access_token()}"},
                      timeout=30)
    spend(COST["list"])
    if res.status_code != 200:
        raise _api_error(res, "request")
    return _json(res)


def channel() -> dict | None:
    items = _get("channels", {"part": "snippet", "mine": "true"}).get("items") or []
    if not items:
        return None
    sn = items[0].get("snippet") or {}
    return {"id": items[0].get("id"), "title": sn.get("title"),
            "thumbnail": ((sn.get("thumbnails") or {}).get("default") or {}).get("url")}


# ------------------------------------------------------------------ upload


def clean_text(text: str, limit: int) -> str:
    """YouTube rejects < and > in titles / descriptions."""
    text = (text or "").replace("<", "‹").replace(">", "›").strip()
    return text[:limit]


def clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    total = 0
    for t in tags:
        t = clean_text(str(t).lstrip("#").strip(), 100).replace(",", " ")
        if not t or t.lower() in (x.lower() for x in out):
            continue
        cost = len(t) + (2 if " " in t else 0) + (1 if out else 0)
        if total + cost > 480:  # YouTube: 500 characters for all tags
            break
        out.append(t)
        total += cost
    return out


def build_body(title: str, description: str, tags: list[str], privacy: str, publish_at: str | None,
               made_for_kids: bool, category: str = "20", language: str | None = None) -> dict:
    if privacy not in PRIVACY:
        raise SharkyClipsError(f"Unknown privacy '{privacy}'.")
    title = clean_text(title, 100)
    if not title:
        raise SharkyClipsError("The video needs a title.")
    status: dict = {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(made_for_kids),
                    "embeddable": True}
    if publish_at:
        try:
            when = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
        except ValueError:
            raise SharkyClipsError("Unknown date format for the scheduled time.") from None
        if when.tzinfo is None:
            when = when.astimezone()  # the browser sends local time
        if when <= datetime.now(timezone.utc) + timedelta(minutes=2):
            raise SharkyClipsError("The scheduled time must be in the future.")
        status["privacyStatus"] = "private"  # YouTube: scheduled videos are private until publishAt
        status["publishAt"] = when.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    snippet = {"title": title, "description": clean_text(description, 4900), "tags": clean_tags(tags),
               "categoryId": category}
    if language:
        snippet["defaultLanguage"] = language
        snippet["defaultAudioLanguage"] = language
    return {"snippet": snippet, "status": status}


def _sessions() -> dict:
    return _read("sessions.json") or {}


def _save_session(key: str, uri: str | None) -> None:
    with _lock:
        s = {k: v for k, v in _sessions().items() if time.time() - v.get("created", 0) < 6 * 86400}
        if uri:
            s[key] = {"uri": uri, "created": time.time()}
        else:
            s.pop(key, None)
        _write("sessions.json", s)


def upload(path: Path, body: dict, key: str, on_progress: Callable[[float], None] | None = None,
           checkpoint: Callable[[], None] | None = None) -> dict:
    """Resumable upload. `key` identifies this upload (restart = continue). Returns the video."""
    requests = _http()
    size = path.stat().st_size
    mime = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}.get(path.suffix.lower(),
                                                                                      "video/*")
    saved = _sessions().get(key)
    uri = saved["uri"] if saved else None
    offset = 0
    if uri:  # ask how much arrived before the restart
        res = requests.put(uri, headers={"Authorization": f"Bearer {access_token()}", "Content-Length": "0",
                                         "Content-Range": f"bytes */{size}"}, timeout=60)
        if res.status_code in (200, 201):
            _save_session(key, None)
            return _json(res)
        if res.status_code == 308:
            rng = res.headers.get("Range")
            offset = int(rng.split("-")[1]) + 1 if rng else 0
        else:
            uri = None
    if not uri:
        check_quota(COST["upload"])
        res = requests.post(f"{UPLOAD_API}/videos", params={"uploadType": "resumable", "part": "snippet,status"},
                            headers={"Authorization": f"Bearer {access_token()}",
                                     "Content-Type": "application/json; charset=UTF-8",
                                     "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": mime},
                            data=json.dumps(body), timeout=60)
        if res.status_code != 200 or not res.headers.get("Location"):
            raise _api_error(res, "upload")
        spend(COST["upload"])
        uri = res.headers["Location"]
        _save_session(key, uri)
    errors = 0
    with open(path, "rb") as f:
        while True:
            if checkpoint:
                checkpoint()
            f.seek(offset)
            chunk = f.read(CHUNK)
            end = offset + len(chunk) - 1
            try:
                res = requests.put(uri, data=chunk, timeout=300, headers={
                    "Authorization": f"Bearer {access_token()}", "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {offset}-{end}/{size}"})
            except requests.RequestException:
                res = None
            if res is not None and res.status_code in (200, 201):
                _save_session(key, None)
                if on_progress:
                    on_progress(1.0)
                return _json(res)
            if res is not None and res.status_code == 308:
                rng = res.headers.get("Range")
                offset = int(rng.split("-")[1]) + 1 if rng else 0
                errors = 0
                if on_progress:
                    on_progress(offset / size)
                continue
            if res is not None and res.status_code in (400, 403, 404):
                _save_session(key, None)
                raise _api_error(res, "upload")
            if res is not None and res.status_code == 401:
                _expire_access()
            errors += 1  # 5xx / network / expired token: wait, ask where we are, go on
            if errors > 8:
                raise SharkyClipsError("The upload kept failing (network or YouTube trouble).",
                                       "Retry it from the queue; it continues where it stopped.")
            time.sleep(min(60, 2 ** errors))
            try:
                st = requests.put(uri, headers={"Authorization": f"Bearer {access_token()}", "Content-Length": "0",
                                                "Content-Range": f"bytes */{size}"}, timeout=60)
                if st.status_code in (200, 201):
                    _save_session(key, None)
                    return _json(st)
                if st.status_code == 308:
                    rng = st.headers.get("Range")
                    offset = int(rng.split("-")[1]) + 1 if rng else 0
            except requests.RequestException:
                pass


def set_thumbnail(video_id: str, image: Path) -> None:
    check_quota(COST["thumbnail"])
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    res = _http().post(f"{UPLOAD_API}/thumbnails/set", params={"videoId": video_id},
                       headers={"Authorization": f"Bearer {access_token()}", "Content-Type": mime},
                       data=image.read_bytes(), timeout=120)
    spend(COST["thumbnail"])
    if res.status_code != 200:
        err = _api_error(res, "thumbnail")
        raise SharkyClipsError(err.message, err.hint or "Custom thumbnails need a verified channel "
                                                        "(youtube.com/verify, free).")


def video_stats(ids: list[str]) -> dict[str, dict]:
    """Views, likes, privacy and publish time of our own videos (1 unit per 50 videos)."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        data = _get("videos", {"part": "statistics,status,snippet", "id": ",".join(ids[i:i + 50]),
                               "maxResults": 50})
        for it in data.get("items") or []:
            st, stat, sn = it.get("status") or {}, it.get("statistics") or {}, it.get("snippet") or {}
            out[it["id"]] = {"views": int(stat.get("viewCount") or 0),
                             "likes": int(stat["likeCount"]) if "likeCount" in stat else None,
                             "privacy": st.get("privacyStatus"), "published_at": sn.get("publishedAt"),
                             "upload_status": st.get("uploadStatus")}
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mark_synced() -> None:
    _write("sync.json", {"at": time.time()})


def last_synced() -> float:
    return float((_read("sync.json") or {}).get("at") or 0)
