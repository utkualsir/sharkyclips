"""OBS Studio: where it records, and the recording time for live markers.

- recording folder + format: OBS's own settings files (global.ini / user.ini -> the current
  profile's basic.ini; simple and advanced output mode), plus whether OBS remuxes MKV to MP4.
- obs-websocket (built into OBS 28+): its config (port / password) is read from OBS's settings
  folder, so nothing has to be typed in. GetRecordStatus gives the exact recording time of a
  marker even when the recording was paused.

The WebSocket client is a minimal RFC 6455 text client (no extra package): connect, identify,
one request, close. OBS_HOME overrides OBS's settings folder (tests).
"""

from __future__ import annotations

import base64
import configparser
import hashlib
import json
import os
import platform
import socket
import struct
import time
from pathlib import Path

VIDEO_EXT = {".mkv", ".mp4", ".mov", ".flv", ".ts", ".m4v", ".webm"}


def obs_home() -> Path | None:
    env = os.environ.get("OBS_HOME")
    if env:
        return Path(env) if Path(env).is_dir() else None
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        p = Path(base) / "obs-studio" if base else None
    elif system == "Darwin":
        p = Path.home() / "Library" / "Application Support" / "obs-studio"
    else:
        p = Path.home() / ".config" / "obs-studio"
    return p if p and p.is_dir() else None


def _ini(path: Path) -> configparser.ConfigParser | None:
    if not path.is_file():
        return None
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str  # keep the key case (FilePath, RecFilePath)
    try:
        cp.read_string(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, configparser.Error):
        return None
    return cp


def _get(cp: configparser.ConfigParser | None, section: str, key: str) -> str | None:
    if cp is None or not cp.has_section(section):
        return None
    v = cp.get(section, key, fallback=None)
    return v.strip() if v and v.strip() else None


def settings() -> dict:
    """{"found", "record_dir", "format", "auto_remux", "profile", "websocket": {...} | None}."""
    home = obs_home()
    out: dict = {"found": home is not None, "record_dir": None, "format": None, "auto_remux": False,
                 "profile": None, "websocket": None}
    if home is None:
        return out
    glob_ini = _ini(home / "user.ini") or _ini(home / "global.ini")  # OBS 31+ writes user.ini
    prof_dir = _get(glob_ini, "Basic", "ProfileDir") or _get(glob_ini, "Basic", "Profile")
    profiles = home / "basic" / "profiles"
    if not prof_dir and profiles.is_dir():
        found = sorted(p.name for p in profiles.iterdir() if (p / "basic.ini").is_file())
        prof_dir = found[0] if found else None
    out["profile"] = prof_dir
    remux = _get(glob_ini, "Video", "AutoRemux")
    basic = _ini(profiles / prof_dir / "basic.ini") if prof_dir else None
    mode = (_get(basic, "Output", "Mode") or "Simple").lower()
    if mode == "advanced":
        rec_type = (_get(basic, "AdvOut", "RecType") or "Standard").lower()
        if rec_type == "ffmpeg":
            path = _get(basic, "AdvOut", "FFFilePath")
            fmt = _get(basic, "AdvOut", "FFExtension") or _get(basic, "AdvOut", "FFFormat")
        else:
            path = _get(basic, "AdvOut", "RecFilePath")
            fmt = _get(basic, "AdvOut", "RecFormat2") or _get(basic, "AdvOut", "RecFormat")
    else:
        path = _get(basic, "SimpleOutput", "FilePath")
        fmt = _get(basic, "SimpleOutput", "RecFormat2") or _get(basic, "SimpleOutput", "RecFormat")
    if not path:  # OBS's default: the Videos folder (Movies on macOS)
        path = str(Path.home() / ("Movies" if platform.system() == "Darwin" else "Videos"))
    out["record_dir"] = str(Path(path).expanduser())
    fmt = (fmt or "mkv").lower()
    out["format"] = {"fragmented_mp4": "mp4", "fragmented_mov": "mov", "hybrid_mp4": "mp4", "hls": "m3u8",
                     "mpegts": "ts"}.get(fmt, fmt)
    # OBS 30+ remuxes MKV to MP4 by default after the recording
    out["auto_remux"] = (remux or "true").lower() in ("true", "1") and out["format"] in ("mkv", "flv")
    out["websocket"] = websocket_config(home)
    return out


def websocket_config(home: Path | None = None) -> dict | None:
    """obs-websocket's own settings: {"enabled", "port", "password"} (None: not installed)."""
    home = home or obs_home()
    if home is None:
        return None
    p = home / "plugin_config" / "obs-websocket" / "config.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return {"enabled": bool(data.get("server_enabled")), "port": int(data.get("server_port") or 4455),
            "password": str(data.get("server_password") or "") if data.get("auth_required", True) else ""}


# ===================================================================== WebSocket (RFC 6455)


class WsError(Exception):
    pass


class _Ws:
    def __init__(self, host: str, port: int, timeout: float = 2.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
               "Sec-WebSocket-Protocol: obswebsocket.json\r\n\r\n")
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise WsError("connection closed during the handshake")
            head += chunk
            if len(head) > 16384:
                raise WsError("bad handshake")
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status + b" ":
            raise WsError(f"handshake refused: {status.decode(errors='replace')}")
        self.buf = head.split(b"\r\n\r\n", 1)[1]

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise WsError("connection closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, obj: dict) -> None:
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(data)
        head = bytes([0x81])
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack("!Q", n)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self) -> dict:
        msg = b""
        while True:
            b0, b1 = self._read(2)
            op, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            payload = self._read(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 0x8:
                raise WsError("closed by OBS")
            if op == 0x9:  # ping -> pong
                self.sock.sendall(bytes([0x8A, 0x80 | len(payload)]) + b"\0\0\0\0" + payload)
                continue
            if op in (0x1, 0x0):
                msg += payload
                if b0 & 0x80:
                    return json.loads(msg.decode("utf-8"))

    def close(self) -> None:
        try:
            self.sock.sendall(bytes([0x88, 0x80]) + b"\0\0\0\0")
        except OSError:
            pass
        self.sock.close()


def auth_string(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(hashlib.sha256((password + salt).encode()).digest()).decode()
    return base64.b64encode(hashlib.sha256((secret + challenge).encode()).digest()).decode()


def request(req_type: str, data: dict | None = None, *, host: str = "127.0.0.1", port: int = 4455,
            password: str = "", timeout: float = 2.0) -> dict:
    """One obs-websocket v5 request -> responseData. Raises WsError (OBS closed, wrong password)."""
    try:
        ws = _Ws(host, port, timeout)
    except OSError as exc:
        raise WsError(f"OBS isn't reachable on port {port}: {exc}") from exc
    try:
        hello = ws.recv()
        if hello.get("op") != 0:
            raise WsError("unexpected first message")
        ident: dict = {"rpcVersion": 1, "eventSubscriptions": 0}
        auth = (hello.get("d") or {}).get("authentication")
        if auth:
            if not password:
                raise WsError("OBS asks for a WebSocket password")
            ident["authentication"] = auth_string(password, auth["salt"], auth["challenge"])
        ws.send({"op": 1, "d": ident})
        got = ws.recv()
        if got.get("op") != 2:
            raise WsError("OBS didn't accept the login (wrong WebSocket password?)")
        rid = f"sc{time.time_ns()}"
        ws.send({"op": 6, "d": {"requestType": req_type, "requestId": rid, "requestData": data or {}}})
        while True:
            msg = ws.recv()
            if msg.get("op") == 7 and (msg.get("d") or {}).get("requestId") == rid:
                d = msg["d"]
                st = d.get("requestStatus") or {}
                if not st.get("result", False):
                    raise WsError(f"OBS: {st.get('comment') or st.get('code')}")
                return d.get("responseData") or {}
    except (OSError, ValueError) as exc:
        raise WsError(str(exc)) from exc
    except WsError as exc:
        if "closed" in str(exc):
            raise WsError("OBS closed the connection (wrong WebSocket password?)") from exc
        raise
    finally:
        ws.close()


def connection() -> dict | None:
    """{"host", "port", "password"} to use: SharkyClips' own settings, else OBS's config."""
    from . import config

    mode = str(config.get("obs_websocket") or "auto")
    if mode == "off":
        return None
    port = config.get("obs_ws_port")
    pw = config.get("obs_ws_password")
    if port or pw:
        return {"host": "127.0.0.1", "port": int(port or 4455), "password": str(pw or "")}
    ws = websocket_config()
    if ws is None or not ws["enabled"]:
        return None
    return {"host": "127.0.0.1", "port": ws["port"], "password": ws["password"]}


def record_status(timeout: float = 1.2) -> dict | None:
    """{"active", "paused", "ms"} from OBS, or None (no OBS / websocket off / error)."""
    conn = connection()
    if conn is None:
        return None
    try:
        d = request("GetRecordStatus", host=conn["host"], port=conn["port"], password=conn["password"],
                    timeout=timeout)
    except WsError:
        return None
    return {"active": bool(d.get("outputActive")), "paused": bool(d.get("outputPaused")),
            "ms": int(d.get("outputDuration") or 0)}


def check() -> dict:
    """For the settings screen: can we talk to OBS right now?"""
    conn = connection()
    if conn is None:
        ws = websocket_config()
        return {"ok": False, "reason": "not_enabled" if ws is not None else "no_websocket"}
    try:
        d = request("GetVersion", host=conn["host"], port=conn["port"], password=conn["password"], timeout=1.5)
    except WsError as exc:
        msg = str(exc)
        return {"ok": False, "reason": "password" if "password" in msg else "not_running", "detail": msg[:200]}
    return {"ok": True, "obs": d.get("obsVersion"), "websocket": d.get("obsWebSocketVersion")}
