"""Direct YouTube upload with the official, free YouTube Data API v3.

Everything stays on this computer. Two ways to sign in:

  shared ("easy")  SharkyClips ships one Google OAuth client of type "Desktop app"
                   (google_client.json next to this file). Google says an installed app's client
                   secret is not confidential; PKCE + a loopback redirect protect the sign-in.
  own ("advanced") the user makes their own free Google Cloud client and loads its JSON in
                   Settings (own quota, no shared limits). It wins over the shared one.

Files in ~/.sharkyclips/youtube/:

  client.json    client id + secret of the user's own OAuth client (advanced mode only)
  signed_out.json  Google signed us out (revoked / expired): the UI shows a reconnect banner
  token.enc      access + refresh token, encrypted (secretstore.py: DPAPI on Windows, the
                 Keychain on macOS); never leaves this PC
  playlists.json the channel's playlists (cached for the publish screen)
  quota.json     API units used today (resets at midnight Pacific Time, like Google's counter)
  sessions.json  resumable upload URLs, so a restart continues an upload instead of restarting it
  locked.json    set when Google keeps our uploads private (an unaudited API project: since 2020,
                 videos uploaded through such a project stay private until Google audits it)
  unlocked.json  set when an upload really went public / unlisted: the lock is gone

OAuth: authorization code + PKCE with a loopback redirect to a one-shot listener on a random
port (http://127.0.0.1:<port>/, see ytconnect.py), which Google allows for Desktop app clients.

Quota (default 10,000 units a day per Google Cloud project): an upload costs 1,600 units,
a thumbnail 50, changing / deleting a video or a playlist 50, reading statistics 1 per 50 videos.

Tests (and the end-to-end check) can point every Google address at a local fake server with
SHARKYCLIPS_YT_ENDPOINT=http://127.0.0.1:<port> (loopback only, so a token can't leak).
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import json
import os
import secrets
import threading
import time
import re
import urllib.parse
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import config, secretstore
from .errors import SharkyClipsError
from .project import read_json, write_json_atomic

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3"
# "youtube" = upload + manage the user's own videos: scheduled publishing, changing a scheduled
# video, deleting a cancelled one, playlists. yt-analytics.readonly: retention for the hook test.
SCOPE_MANAGE = "https://www.googleapis.com/auth/youtube"
SCOPES = (SCOPE_MANAGE, "https://www.googleapis.com/auth/yt-analytics.readonly")
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
COST = {"upload": 1600, "thumbnail": 50, "list": 1, "update": 50, "delete": 50, "playlist": 50}
DEFAULT_DAILY_QUOTA = 10_000
CHUNK = 8 * 1024 * 1024  # resumable upload chunk (multiple of 256 KiB)
PRIVACY = ("private", "unlisted", "public")
CATEGORY = {"gaming": "20", "study": "27", "music": "10"}  # Gaming, Education, Music
# Categories a video can be put in (the ones YouTube offers for uploads in every region).
CATEGORIES = ("1", "2", "10", "15", "17", "19", "20", "22", "23", "24", "25", "26", "27", "28", "29")
CONSOLE = "https://console.cloud.google.com"
SHARED_FILE = Path(__file__).with_name("google_client.json")
CREATE_CHANNEL_URL = "https://www.youtube.com/create_channel"

_lock = threading.RLock()
_pending: dict[str, dict] = {}  # OAuth state -> {verifier, redirect_uri, created}


def folder() -> Path:
    return config.config_dir() / "youtube"


def _fake_base() -> str | None:
    base = (os.environ.get("SHARKYCLIPS_YT_ENDPOINT") or "").rstrip("/")
    if not base:
        return None
    host = urllib.parse.urlsplit(base).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        warnings.warn("SHARKYCLIPS_YT_ENDPOINT must be a loopback address; ignored.", stacklevel=2)
        return None
    return base


def url(real: str) -> str:
    """A Google address, or its counterpart on the local fake server (tests)."""
    fake = _fake_base()
    if not fake:
        return real
    parts = urllib.parse.urlsplit(real)
    return f"{fake}/{parts.netloc.split('.')[0]}{parts.path}"


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


def _http() -> Any:  # the `requests` module (tests swap in a fake)
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
        raise _err("Today's YouTube upload limit is used up.",
                   f"Google's free API quota resets at midnight Pacific Time ({reset} here).", reason="quotaExceeded")


# ------------------------------------------------------------------ client + tokens


def load_client() -> dict | None:
    """The user's own OAuth client (advanced mode), or None."""
    return _read("client.json")


def _parse_client(data: Any) -> dict | None:
    """client_id / secret / project of an "installed" (Desktop app) client JSON, or of the flat
    form google_client.json uses. Google's Desktop clients list redirect_uris ["http://localhost"]
    (older ones also "urn:ietf:wg:oauth:2.0:oob"); that's fine: Desktop clients accept any
    loopback port on 127.0.0.1 / localhost, which is what the sign-in uses (ytconnect.py)."""
    if not isinstance(data, dict):
        return None
    body = data.get("installed") if isinstance(data.get("installed"), dict) else data
    cid = str(body.get("client_id") or "").strip()
    if not cid.endswith(".apps.googleusercontent.com"):
        return None
    pid = body.get("project_id")
    return {"client_id": cid, "client_secret": str(body.get("client_secret") or "").strip(),
            "project_id": str(pid) if isinstance(pid, (str, int)) and pid != "" else None}


# Google's state of the built-in client: testing (only invited test users, signed out after 7 days)
# | production (published, not verified: anyone after Google's warning screen, up to user_cap
# people) | in_review | verified. "unverified" (1.2.8 - 1.2.10) means production.
VERIFICATION = ("testing", "production", "in_review", "verified")


def shared_info() -> dict:
    """The built-in client's public facts: is it set up, Google's verification state, user cap.
    SHARKYCLIPS_SHARED_CLIENT may point at another JSON (tests, forks)."""
    env = os.environ.get("SHARKYCLIPS_SHARED_CLIENT")
    path = Path(env) if env else SHARED_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    client = _parse_client(data)
    verification = data.get("verification")
    verification = verification if verification in VERIFICATION else "production"
    return {"available": client is not None, "client": client, "verification": verification,
            "user_cap": int(data.get("user_cap") or 100), "project_id": (client or {}).get("project_id")}


def shared_client() -> dict | None:
    return shared_info()["client"]


def active_client() -> dict | None:
    """The client a new sign-in uses: the user's own one wins over the built-in one."""
    return load_client() or shared_client()


def client_mode() -> str | None:
    return "own" if load_client() else "shared" if shared_client() else None


def _client_for(tok: dict) -> dict:
    """The client a token was issued to (a refresh must use the same one)."""
    want = tok.get("client_id")
    for c in (load_client(), shared_client()):
        if c and (not want or c["client_id"] == want):
            return c
    return {}


def decode_client_bytes(raw: bytes) -> str:
    """A dropped / uploaded client file as text: UTF-8 with or without a BOM, or UTF-16 (what
    Windows Notepad saves as "Unicode"). Windows line endings are fine for JSON."""
    if raw[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def check_client_text(raw: str) -> dict:
    """Validate a pasted / dropped client_secret.json and explain any problem in plain words.
    Returns the parsed client (not saved)."""
    text = (raw or "").strip().lstrip("\ufeff")
    if not text:
        raise _err("That's empty.", "Drop the client_secret_....json file here, or paste its contents.",
                   reason="empty")
    if text.startswith("AIza"):
        raise _err("That's an API key, not an OAuth client.",
                   "SharkyClips needs the OAuth client file: Google Auth Platform > Clients > your Desktop "
                   "app > Download JSON.", reason="api_key")
    if text.endswith(".apps.googleusercontent.com") and not any(c in text for c in " {\n"):
        raise _err("That's only the client ID.",
                   "Download the whole JSON file (it also holds the client secret): Clients > your "
                   "Desktop app > Download JSON.", reason="id_only")
    try:
        data = json.loads(text)
    except ValueError:
        raise _err("That isn't a JSON file.",
                   "Use the file Google downloads as client_secret_....json, unchanged.",
                   reason="not_json") from None
    if not isinstance(data, dict):
        raise _err("That isn't a Google OAuth client file.", reason="not_client")
    if data.get("type") == "service_account":
        raise _err("That's a service account key.",
                   "YouTube uploads need an OAuth client of type 'Desktop app' (Google Auth Platform > "
                   "Clients > Create client).", reason="service_account")
    if "web" in data and "installed" not in data:
        raise _err("This is a 'Web application' client.",
                   "Create an OAuth client of type 'Desktop app' instead (it allows the local "
                   "redirect SharkyClips uses).", reason="web_client")
    client = _parse_client(data)
    if client is None:
        raise _err("That file has no Google OAuth client ID.",
                   "Download the JSON of an OAuth client of type 'Desktop app'.", reason="no_client_id")
    if not client["client_secret"]:
        raise _err("That file has no client secret.",
                   "Download the JSON again from Clients > your Desktop app > Download JSON.",
                   reason="no_secret")
    return client


def set_client(raw: str | bytes | dict) -> dict:
    """Store the user's own OAuth client (the JSON downloaded from Google Cloud Console)."""
    if isinstance(raw, dict):
        text = json.dumps(raw)
    elif isinstance(raw, bytes):
        text = decode_client_bytes(raw)
    else:
        text = str(raw)
    client = {**check_client_text(text), "saved_at": _now()}
    _write("client.json", client)
    _forget_token()  # a new client needs a new sign-in
    return client


def remove_client() -> None:
    """Back to the built-in client (easy mode): the own client's token goes too."""
    disconnect()
    (folder() / "client.json").unlink(missing_ok=True)


TOKEN_FILE = "token.enc"


def _token() -> dict | None:
    path = folder() / TOKEN_FILE
    if path.is_file():
        return secretstore.load(path)
    old = _read("token.json")  # 1.2.6 and older kept it as plain JSON: encrypt it now
    if old and old.get("refresh_token"):
        _write_token(old)
        return old
    return None


def _write_token(tok: dict) -> None:
    secretstore.save(folder() / TOKEN_FILE, tok)
    (folder() / "token.json").unlink(missing_ok=True)


def _forget_token() -> None:
    (folder() / TOKEN_FILE).unlink(missing_ok=True)
    (folder() / "token.json").unlink(missing_ok=True)
    secretstore.forget_key(folder())


def token_protection() -> str | None:
    """How the stored token is protected: dpapi | keychain | file (None = no token)."""
    path = folder() / TOKEN_FILE
    return secretstore.protection(path) if path.is_file() else None


def connected() -> bool:
    t = _token()
    return bool(t and t.get("refresh_token"))


def status() -> dict:
    client = load_client()
    tok = _token() or {}
    sh = shared_info()
    conn = connected()
    return {"client": bool(client), "client_id": (client or {}).get("client_id"),
            "project_id": (client or {}).get("project_id"), "connected": conn,
            "mode": client_mode(), "ready": active_client() is not None,
            "shared": {k: sh[k] for k in ("available", "verification", "user_cap", "project_id")},
            "channel": tok.get("channel"), "channels": tok.get("channels") or [],
            "no_channel": conn and not tok.get("channel") and bool(tok.get("channel_checked")),
            "create_channel_url": CREATE_CHANNEL_URL, "signed_out": signed_out(),
            "connected_at": tok.get("connected_at"),
            "quota": quota_view(), "scopes": list(SCOPES), "analytics": has_analytics(),
            "manage": can_manage(), "uploads_locked": uploads_locked(), "lock": lock_state(),
            "token_protection": token_protection() if conn else None}


def signed_out() -> dict | None:
    """Google signed SharkyClips out (revoked / expired): {at, channel, reason} until reconnected."""
    if connected():
        return None
    return _read("signed_out.json")


def dismiss_signed_out() -> None:
    (folder() / "signed_out.json").unlink(missing_ok=True)


def has_analytics() -> bool:
    """The token includes YouTube Analytics (connected with 1.2.5 or later)."""
    tok = _token() or {}
    return connected() and "yt-analytics.readonly" in str(tok.get("scope") or "")


def can_manage() -> bool:
    """The token may change / delete our videos and use playlists (connected with 1.2.7+)."""
    tok = _token() or {}
    return connected() and SCOPE_MANAGE in str(tok.get("scope") or "").split()


def uploads_locked() -> dict | None:
    st = lock_state()
    return {"at": st["at"], "video_id": st["video_id"]} if st["state"] == "locked" else None


def lock_state() -> dict:
    """Are uploads forced to private? locked = seen it happen, unlocked = an upload really went
    public / unlisted, unknown = no upload told us yet (a new, unaudited project starts locked)."""
    lock, free = _read("locked.json"), _read("unlocked.json")
    if lock and (not free or str(lock.get("at")) >= str(free.get("at"))):
        return {"state": "locked", "at": lock.get("at"), "video_id": lock.get("video_id")}
    if free:
        return {"state": "unlocked", "at": free.get("at"), "video_id": free.get("video_id")}
    return {"state": "unknown", "at": None, "video_id": None}


def mark_locked(video_id: str) -> None:
    """A video we asked to be public / unlisted came back private: Google locks this project's uploads."""
    if lock_state()["state"] != "locked":
        _write("locked.json", {"at": _now(), "video_id": video_id})
        (folder() / "unlocked.json").unlink(missing_ok=True)


def mark_unlocked(video_id: str) -> None:
    """One of our uploads is public / unlisted on YouTube: the project isn't locked (any more)."""
    if lock_state()["state"] != "unlocked":
        _write("unlocked.json", {"at": _now(), "video_id": video_id})
        (folder() / "locked.json").unlink(missing_ok=True)


def clear_locked() -> None:
    (folder() / "locked.json").unlink(missing_ok=True)


def auth_url(redirect_uri: str) -> str:
    client = active_client()
    if not client:
        raise _err("YouTube sign-in isn't set up in this build.",
                   "Use Settings > YouTube > Advanced to connect with your own Google project.",
                   reason="no_client")
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    with _lock:
        for k in [k for k, v in _pending.items() if time.time() - v["created"] > 900]:
            _pending.pop(k, None)
        _pending[state] = {"verifier": verifier, "redirect_uri": redirect_uri, "created": time.time(),
                           "client_id": client["client_id"]}
    # select_account: always show Google's account / channel chooser (wrong account, several
    # channels); consent: always get a refresh token.
    q = {"client_id": client["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
         "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "select_account consent",
         "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
         "include_granted_scopes": "true"}
    return url(AUTH_URL) + "?" + urllib.parse.urlencode(q)


def forget_pending(state: str | None) -> None:
    with _lock:
        _pending.pop(state or "", None)


def is_pending(state: str | None) -> bool:
    return bool(state) and state in _pending


def finish_auth(code: str, state: str) -> dict:
    with _lock:
        pend = _pending.pop(state, None)
    if pend is None:
        raise _err("This sign-in link has expired.", "Click Connect YouTube again.", reason="expired")
    client = next((c for c in (load_client(), shared_client())
                   if c and c["client_id"] == pend.get("client_id")), None) or active_client() or {}
    res = _http().post(url(TOKEN_URL), data={
        "code": code, "client_id": client.get("client_id"), "client_secret": client.get("client_secret"),
        "redirect_uri": pend["redirect_uri"], "grant_type": "authorization_code",
        "code_verifier": pend["verifier"]}, timeout=30)
    data = _json(res)
    if res.status_code != 200 or "refresh_token" not in data:
        hint = ("Check that your Google account is a test user of your OAuth app (Advanced, step 3)."
                if load_client() else "Try again in a minute.")
        raise _err("Google refused the sign-in: "
                   f"{data.get('error_description') or data.get('error') or res.status_code}", hint, reason="token")
    tok = {"access_token": data["access_token"], "refresh_token": data["refresh_token"],
           "expires_at": time.time() + int(data.get("expires_in") or 3600) - 60,
           "scope": data.get("scope"), "connected_at": _now(), "client_id": client.get("client_id")}
    _write_token(tok)
    dismiss_signed_out()
    (folder() / "playlists.json").unlink(missing_ok=True)
    _refresh_channels(tok)
    return status()


def _refresh_channels(tok: dict | None = None) -> dict:
    """Ask YouTube which channel(s) this sign-in may upload to. An API error (e.g. the API is off
    in the user's own project) is raised; the token stays."""
    found = channels()
    tok = _token() or tok or {}  # channels() may have refreshed the access token meanwhile
    tok["channels"] = found
    tok["channel_checked"] = True
    keep = (tok.get("channel") or {}).get("id")
    tok["channel"] = next((c for c in found if c["id"] == keep), found[0] if found else None)
    _write_token(tok)
    return tok


def recheck_channel() -> dict:
    """After the user made a YouTube channel: look again."""
    if not connected():
        raise _err("YouTube isn't connected.", reason="not_connected")
    _refresh_channels()
    return status()


def select_channel(channel_id: str) -> dict:
    """Several channels listed for the account: the one SharkyClips shows."""
    tok = _token() or {}
    pick = next((c for c in tok.get("channels") or [] if c["id"] == channel_id), None)
    if pick is None:
        raise _err("That channel isn't on this Google account.", reason="channel")
    tok["channel"] = pick
    tok["channel_picked"] = True
    _write_token(tok)
    return status()


def disconnect() -> None:
    tok = _token()
    if tok and tok.get("refresh_token"):
        try:
            _http().post(url(REVOKE_URL), params={"token": tok["refresh_token"]}, timeout=10)
        except Exception:  # noqa: BLE001 - offline: forget it locally anyway
            pass
    _forget_token()
    dismiss_signed_out()  # the user chose this: no "signed out" banner
    (folder() / "playlists.json").unlink(missing_ok=True)


def access_token() -> str:
    with _lock:
        tok = _token()
        if not tok or not tok.get("refresh_token"):
            raise _err("YouTube isn't connected.", "Settings > YouTube > Connect YouTube.", reason="not_connected")
        if tok.get("access_token") and time.time() < float(tok.get("expires_at") or 0):
            return tok["access_token"]
        client = _client_for(tok)
        if not client:  # the client it was made with is gone
            _signed_out(tok, "client_removed")
            raise _err("YouTube isn't connected.", "Connect YouTube again.", reason="signed_out")
        res = _http().post(url(TOKEN_URL), data={
            "client_id": client.get("client_id"), "client_secret": client.get("client_secret"),
            "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}, timeout=30)
        data = _json(res)
        if res.status_code != 200:
            if data.get("error") in ("invalid_grant", "invalid_client", "unauthorized_client"):
                _signed_out(tok, str(data.get("error")))
                why = "Google ends the sign-in when you remove access in your Google account"
                if load_client() and client.get("client_id") == load_client().get("client_id"):
                    why += ", and after 7 days if your own Google project is still in 'Testing'"
                raise _err("YouTube signed SharkyClips out.", f"Click Reconnect: it takes a few seconds. ({why}.)",
                           reason="signed_out", status=res.status_code)
            raise _err(f"Could not refresh the YouTube sign-in ({data.get('error') or res.status_code}).",
                       reason="refresh_failed", status=res.status_code)
        tok["access_token"] = data["access_token"]
        tok["expires_at"] = time.time() + int(data.get("expires_in") or 3600) - 60
        _write_token(tok)
        return tok["access_token"]


def _signed_out(tok: dict, reason: str) -> None:
    """Forget a dead token but remember whose it was, for the one-click reconnect banner."""
    _forget_token()
    _write("signed_out.json", {"at": _now(), "channel": tok.get("channel"), "reason": reason})


def _expire_access() -> None:
    with _lock:
        tok = _token()
        if tok:
            tok["expires_at"] = 0
            _write_token(tok)


def _err(message: str, hint: str | None = None, *, reason: str | None = None,
         status: int | None = None) -> SharkyClipsError:
    """A user-facing error that also says why (the publish scheduler decides retry / fix by it)."""
    e = SharkyClipsError(message, hint)
    e.reason = reason  # type: ignore[attr-defined]
    e.status = status  # type: ignore[attr-defined]
    return e


def _json(res: Any) -> dict:
    try:
        d = res.json()
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def _api_error(res: Any, what: str) -> SharkyClipsError:
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
        "forbidden": "Is the YouTube Data API v3 enabled in your Google Cloud project (Advanced, step 2)?",
        "accessNotConfigured": "Enable the YouTube Data API v3 in your Google Cloud project (Advanced, step 2).",
        "SERVICE_DISABLED": "Enable the YouTube Data API v3 in your Google Cloud project (Advanced, step 2).",
        "PERMISSION_DENIED": "Is the YouTube Data API v3 enabled in your Google Cloud project (Advanced, step 2)?",
        "invalidPublishAt": "The scheduled time must be in the future.",
        "insufficientPermissions": "Reconnect YouTube in Settings so SharkyClips may manage your scheduled videos.",
        "ACCESS_TOKEN_SCOPE_INSUFFICIENT": "Reconnect YouTube in Settings so SharkyClips may manage your scheduled videos.",
        "videoNotFound": "The video isn't on YouTube any more.",
    }
    if reason == "quotaExceeded":
        spend(daily_quota())  # Google says it's gone: show 0 left until the reset
    return _err(f"YouTube {what} failed: {msg}"[:400], hints.get(reason), reason=reason or None,
                status=getattr(res, "status_code", None))


def _get(path: str, params: dict) -> dict:
    return _call("GET", path, params, cost=COST["list"], what="request")


def _call(method: str, path: str, params: dict, body: dict | None = None, *, cost: int, what: str,
          base: str = API, ok: tuple[int, ...] = (200,)) -> dict:
    """One Data API call; an expired access token is refreshed once and the call repeated."""
    if cost > 1:
        check_quota(cost)
    for attempt in (1, 2):
        headers = {"Authorization": f"Bearer {access_token()}"}
        kw: dict = {"params": params, "headers": headers, "timeout": 30}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=UTF-8"
            kw["data"] = json.dumps(body)
        res = getattr(_http(), method.lower())(f"{url(base)}/{path}", **kw)
        if res.status_code == 401 and attempt == 1:
            _expire_access()
            continue
        spend(cost)
        if res.status_code not in ok:
            raise _api_error(res, what)
        return _json(res)
    raise _err(f"YouTube {what} failed: signed out.", reason="signed_out", status=401)


def channels() -> list[dict]:
    """The YouTube channel(s) of the signed-in account (empty: the account has no channel yet)."""
    items = _get("channels", {"part": "snippet", "mine": "true", "maxResults": 50}).get("items") or []
    out = []
    for it in items:
        sn = it.get("snippet") or {}
        out.append({"id": it.get("id"), "title": sn.get("title"),
                    "thumbnail": ((sn.get("thumbnails") or {}).get("default") or {}).get("url")})
    return out


def channel() -> dict | None:
    found = channels()
    return found[0] if found else None


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


def with_note(description: str, note: str | None, limit: int = 4900) -> str:
    """The description with `note` as its last paragraph (once; never cut off by the length limit),
    or just before the channel's socials block when the description ends with one."""
    from .edit import brand

    description = (description or "").strip()
    if not note or note in description:
        return description
    body, block = brand.split_socials(description)
    tail = f"\n\n{block}" if block else ""
    room = limit - len(note) - 2 - len(tail)
    return f"{body[:max(0, room)].rstrip()}\n\n{note}{tail}".strip()


def censor_text(text: str, lang: str | None) -> str:
    """1.2.31: every swear in an uploaded title / description / caption is censored ("S*KTİR"),
    whatever wrote it (the AI, the user, an old saved text). Links are left alone."""
    from .titles import style

    lang = lang or config.get("output_language") or "tr"
    out = []
    for part in re.split(r"(https?://\S+)", text or ""):
        out.append(part if part.startswith(("http://", "https://")) else style.censor(part, lang)[0])
    return "".join(out)


def _has_swear(text: str, lang: str | None) -> bool:
    return censor_text(str(text), lang) != str(text)


def build_body(title: str, description: str, tags: list[str], privacy: str, publish_at: str | None,
               made_for_kids: bool, category: str = "20", language: str | None = None,
               synthetic: bool = False) -> dict:
    """`synthetic`: tell YouTube the video has altered / synthetic content (status.containsSyntheticMedia)."""
    if privacy not in PRIVACY:
        raise SharkyClipsError(f"Unknown privacy '{privacy}'.")
    title = clean_text(censor_text(title, language), 100)
    if not title:
        raise SharkyClipsError("The video needs a title.")
    description = censor_text(description, language)
    tags = [t for t in tags if not _has_swear(t, language)]
    status: dict = {"privacyStatus": privacy, "selfDeclaredMadeForKids": bool(made_for_kids),
                    "embeddable": True}
    if synthetic:
        status["containsSyntheticMedia"] = True
    if publish_at:
        try:
            when = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
        except ValueError:
            raise SharkyClipsError("Unknown date format for the scheduled time.") from None
        if when.tzinfo is None:
            when = when.astimezone()  # the browser sends local time
        if when <= datetime.now(timezone.utc) + timedelta(minutes=2):
            raise _err("The scheduled time must be in the future.", reason="invalidPublishAt")
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
        for attempt in (1, 2):
            res = requests.post(f"{url(UPLOAD_API)}/videos", params={"uploadType": "resumable", "part": "snippet,status"},
                                headers={"Authorization": f"Bearer {access_token()}",
                                         "Content-Type": "application/json; charset=UTF-8",
                                         "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": mime},
                                data=json.dumps(body), timeout=60)
            if res.status_code != 401 or attempt == 2:
                break
            _expire_access()  # the access token ran out early: refresh it and ask again
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
                raise _err("The upload kept failing (network or YouTube trouble).",
                           "Retry it from the queue; it continues where it stopped.", reason="network")
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
    res = _http().post(f"{url(UPLOAD_API)}/thumbnails/set", params={"videoId": video_id},
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


def retention(ids: list[str], start_date: str, end_date: str | None = None) -> dict[str, dict]:
    """Views and average view percentage of our own videos (YouTube Analytics API, its own
    free quota). start_date / end_date: YYYY-MM-DD."""
    out: dict[str, dict] = {}
    end_date = end_date or datetime.now(timezone.utc).date().isoformat()
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        res = _http().get(url(ANALYTICS_API), params={
            "ids": "channel==MINE", "startDate": start_date, "endDate": end_date, "dimensions": "video",
            "metrics": "views,averageViewDuration,averageViewPercentage", "filters": "video==" + ",".join(chunk),
            "maxResults": 200}, headers={"Authorization": f"Bearer {access_token()}"}, timeout=30)
        if res.status_code != 200:
            err = _api_error(res, "analytics request")
            if res.status_code == 403:
                raise SharkyClipsError(err.message, "Reconnect YouTube in Settings so SharkyClips may read "
                                                    "your channel's retention (YouTube Analytics).")
            raise err
        data = _json(res)
        cols = [c.get("name") for c in data.get("columnHeaders") or []]
        for row in data.get("rows") or []:
            r = dict(zip(cols, row))
            out[str(r.get("video"))] = {"views": int(r.get("views") or 0),
                                        "avg_view_duration": float(r.get("averageViewDuration") or 0),
                                        "avg_view_percentage": float(r.get("averageViewPercentage") or 0)}
    return out


# ------------------------------------------------------------------ manage videos + playlists


def _need_manage() -> None:
    if not can_manage():
        raise _err("SharkyClips may only upload to this channel so far.",
                   "Reconnect YouTube in Settings once: scheduling, cancelling and playlists need the "
                   "'manage your YouTube videos' permission.", reason="scope")


def update_video(video_id: str, snippet: dict | None = None, status: dict | None = None) -> dict:
    """Change an uploaded video: snippet (title, description, tags, category, language) and / or
    status (privacy, publishAt). YouTube replaces the whole part, so send complete parts."""
    _need_manage()
    parts = [p for p, v in (("snippet", snippet), ("status", status)) if v is not None]
    if not parts:
        return {}
    body: dict = {"id": video_id}
    if snippet is not None:
        body["snippet"] = snippet
    if status is not None:
        body["status"] = status
    return _call("PUT", "videos", {"part": ",".join(parts)}, body, cost=COST["update"], what="update")


def delete_video(video_id: str) -> bool:
    """Delete one of our videos (cancel a scheduled upload). False = it was already gone."""
    _need_manage()
    try:
        _call("DELETE", "videos", {"id": video_id}, cost=COST["delete"], what="delete", ok=(200, 204))
    except SharkyClipsError as exc:
        if getattr(exc, "status", None) == 404:
            return False
        raise
    return True


def playlists(refresh: bool = False) -> list[dict]:
    """The channel's playlists (cached 10 minutes; 1 unit per 50)."""
    cached = _read("playlists.json")
    if cached and not refresh and time.time() - float(cached.get("at") or 0) < 600:
        return cached.get("items") or []
    out: list[dict] = []
    page = None
    for _ in range(10):
        params = {"part": "snippet,status,contentDetails", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = _get("playlists", params)
        for it in data.get("items") or []:
            sn = it.get("snippet") or {}
            out.append({"id": it.get("id"), "title": sn.get("title") or "",
                        "privacy": (it.get("status") or {}).get("privacyStatus"),
                        "count": (it.get("contentDetails") or {}).get("itemCount")})
        page = data.get("nextPageToken")
        if not page:
            break
    _write("playlists.json", {"at": time.time(), "items": out})
    return out


def create_playlist(title: str, privacy: str = "public") -> dict:
    _need_manage()
    title = clean_text(title, 150)
    if not title:
        raise SharkyClipsError("The playlist needs a name.")
    privacy = privacy if privacy in PRIVACY else "public"
    data = _call("POST", "playlists", {"part": "snippet,status"},
                 {"snippet": {"title": title}, "status": {"privacyStatus": privacy}},
                 cost=COST["playlist"], what="playlist")
    item = {"id": data.get("id"), "title": title, "privacy": privacy, "count": 0}
    cached = _read("playlists.json") or {"at": time.time(), "items": []}
    cached["items"] = [i for i in cached.get("items") or [] if i.get("id") != item["id"]] + [item]
    _write("playlists.json", cached)
    return item


def add_to_playlist(playlist_id: str, video_id: str) -> None:
    _need_manage()
    _call("POST", "playlistItems", {"part": "snippet"},
          {"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
          cost=COST["playlist"], what="playlist")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mark_synced() -> None:
    _write("sync.json", {"at": time.time()})


def last_synced() -> float:
    return float((_read("sync.json") or {}).get("at") or 0)
