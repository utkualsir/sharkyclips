"""Optional access PIN / password for LAN mode (`python cli.py serve --lan`).

Off by default. The computer running SharkyClips never needs it (requests from 127.0.0.1 / ::1
always pass); once a PIN is set, every other device must log in before it can use the API.

  <config dir>/lan_auth.json      {"kind": "pin"|"password", "hash": "scrypt$n$r$p$salt$key",
                                   "set_at": ...}. Only the salted scrypt hash is stored. It lives
                                   outside config.json so the settings API can never return it.
  <config dir>/lan_sessions.json  {sha256(session token): expiry}. The raw token only exists in
                                   the browser's HttpOnly cookie, so a leaked file can't log in.

Failed logins are rate-limited per device and in total (see Limiter).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .errors import SharkyClipsError
from .project import read_json, write_json_atomic

COOKIE = "sc_session"
SESSION_DAYS = 30
MIN_LEN, MAX_LEN = 4, 128
# scrypt cost: ~50 ms and 16 MB per check on a laptop, which also slows down guessing.
N, R, P, DKLEN = 2 ** 14, 8, 1, 32

_lock = threading.RLock()
_cache: dict = {"mtime": None, "data": None}


def _read(path: Path):
    try:
        return read_json(path)
    except (OSError, ValueError):
        return None


def auth_path() -> Path:
    return config.config_dir() / "lan_auth.json"


def sessions_path() -> Path:
    return config.config_dir() / "lan_sessions.json"


# ------------------------------------------------------------------ hashing


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def hash_secret(secret: str, salt: bytes | None = None, n: int = N, r: int = R, p: int = P) -> str:
    salt = salt or secrets.token_bytes(16)
    key = hashlib.scrypt(secret.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=DKLEN)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(key)}"


def check_hash(secret: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, key = stored.split("$")
        if algo != "scrypt":
            return False
        want = base64.b64decode(key)
        got = hashlib.scrypt(secret.encode("utf-8"), salt=base64.b64decode(salt), n=int(n), r=int(r),
                             p=int(p), dklen=len(want))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, want)


def validate(secret: str) -> str:
    """'pin' (digits only) or 'password'; raises on a secret that is too short or long."""
    if not isinstance(secret, str) or not MIN_LEN <= len(secret) <= MAX_LEN:
        raise SharkyClipsError(f"Use {MIN_LEN} to {MAX_LEN} characters.",
                               "A 6-digit PIN or a password is a good choice.")
    if secret != secret.strip():
        raise SharkyClipsError("The PIN can't start or end with a space.")
    return "pin" if secret.isdigit() else "password"


# ------------------------------------------------------------------ stored secret


def _load() -> dict | None:
    path = auth_path()
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return None
    with _lock:
        if _cache["mtime"] != (path, mtime):
            data = _read(path)
            _cache.update(mtime=(path, mtime), data=data if isinstance(data, dict) and data.get("hash") else None)
        return _cache["data"]


def enabled() -> bool:
    return _load() is not None


def kind() -> str | None:
    data = _load()
    return data.get("kind") if data else None


def set_secret(secret: str) -> str:
    k = validate(secret)
    with _lock:
        write_json_atomic(auth_path(), {"kind": k, "hash": hash_secret(secret),
                                        "set_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        sessions_path().unlink(missing_ok=True)  # a new PIN logs every device out
    return k


def clear_secret() -> None:
    with _lock:
        auth_path().unlink(missing_ok=True)
        sessions_path().unlink(missing_ok=True)
        _cache.update(mtime=None, data=None)


def verify(secret: str) -> bool:
    data = _load()
    return bool(data and isinstance(secret, str) and len(secret) <= MAX_LEN and check_hash(secret, data["hash"]))


# ------------------------------------------------------------------ sessions


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _sessions(now: float) -> dict[str, float]:
    raw = _read(sessions_path())
    if not isinstance(raw, dict):
        return {}
    return {k: float(v) for k, v in raw.items() if isinstance(v, (int, float)) and v > now}


def new_session(now: float | None = None) -> str:
    now = now or time.time()
    token = secrets.token_urlsafe(32)
    with _lock:
        live = _sessions(now)
        live[_token_id(token)] = now + SESSION_DAYS * 86400
        if len(live) > 50:  # keep the newest 50 devices
            live = dict(sorted(live.items(), key=lambda kv: kv[1])[-50:])
        write_json_atomic(sessions_path(), live)
    return token


def session_valid(token: str | None, now: float | None = None) -> bool:
    if not token or len(token) > 100:
        return False
    with _lock:
        return _token_id(token) in _sessions(now or time.time())


def end_session(token: str | None) -> None:
    if not token:
        return
    with _lock:
        live = _sessions(time.time())
        if live.pop(_token_id(token), None) is not None:
            write_json_atomic(sessions_path(), live)


# ------------------------------------------------------------------ rate limit


class Limiter:
    """Failed logins: `free` tries per device within `window` seconds, then a lock that doubles
    with every further miss (30 s, 60 s, ... up to `max_lock`). On top of that, at most
    `global_per_min` failures a minute from all devices together, so switching addresses on the
    network doesn't help either."""

    def __init__(self, free: int = 5, window: float = 900, base_lock: float = 30, max_lock: float = 900,
                 global_per_min: int = 20):
        self.free, self.window, self.base_lock, self.max_lock = free, window, base_lock, max_lock
        self.global_per_min = global_per_min
        self._fails: dict[str, list[float]] = {}
        self._until: dict[str, float] = {}
        self._all: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self, ip: str, now: float | None = None) -> float:
        """Seconds this device must wait before the next try (0 = may try now)."""
        now = time.time() if now is None else now
        with self._lock:
            while self._all and now - self._all[0] >= 60:
                self._all.popleft()
            own = max(0.0, self._until.get(ip, 0.0) - now)
            total = 60 - (now - self._all[0]) if len(self._all) >= self.global_per_min else 0.0
            return max(own, total)

    def fail(self, ip: str, now: float | None = None) -> float:
        now = time.time() if now is None else now
        with self._lock:
            recent = [t for t in self._fails.get(ip, []) if now - t < self.window] + [now]
            self._fails[ip] = recent
            self._all.append(now)
            over = len(recent) - self.free
            if over >= 0:
                self._until[ip] = now + min(self.max_lock, self.base_lock * 2 ** over)
            if len(self._fails) > 1000:  # forget the oldest devices
                for k in list(self._fails)[:500]:
                    self._fails.pop(k, None)
                    self._until.pop(k, None)
        return self.wait(ip, now)

    def success(self, ip: str) -> None:
        with self._lock:
            self._fails.pop(ip, None)
            self._until.pop(ip, None)


limiter = Limiter()
