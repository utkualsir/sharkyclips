"""1.2.52: the web server's front door against other websites in the user's own browser.

SharkyClips listens on 127.0.0.1, so only programs on this PC can reach it. But the browser
that shows the UI also shows every other website, and a page from evil.example can send
requests to http://127.0.0.1:8000 too. Four layers stop that:

  1. Host check (DNS rebinding). A rebinding page talks to us under ITS OWN name
     (Host: evil.example), so only these Host names are served: localhost, IP literals
     (127.0.0.1, the LAN address, [::1]) and this computer's own name (+ .local / .lan /
     .home). SHARKYCLIPS_ALLOWED_HOSTS adds more (comma separated; tests: "testserver").
  2. Origin + Fetch Metadata. A POST / PUT / PATCH / DELETE whose Origin is another site, or
     whose Sec-Fetch-Site is "cross-site" / "same-site", is refused. GET /api/... from another
     site (an <img>, <video>, <script> or no-cors fetch) is refused too; only a top-level
     navigation to an OAuth callback is let through.
  3. API token. Every state-changing /api/ request must carry X-SharkyClips-Token. The token
     is random per install (<settings>/api_token, only this Windows / macOS user can read it)
     and reaches the UI inside index.html (<meta name="sharkyclips-token">), which another
     site can't read (same-origin policy, and layer 1 stops rebinding). Programs on this PC
     (tray, launcher) read the file.
  4. Security headers: CSP (scripts only from us), frame-ancestors 'none' / X-Frame-Options
     (no clickjacking), nosniff, Referrer-Policy no-referrer, CORP same-origin (other sites
     can't embed our videos / images), COOP. No CORS headers are ever sent.

The LAN PIN (auth.py / lanauth.py) is a separate, additional layer for other devices.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
import socket
import threading
from pathlib import Path

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .. import config

TOKEN_HEADER = "x-sharkyclips-token"
TOKEN_FILE = "api_token"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
# GET paths another site may open as a top-level page (OAuth providers send the browser back here)
NAVIGABLE_API = ("/api/platforms/reels/callback",)
# Request bodies: at most MAX_BODY bytes, except the routes that stream a file to disk (they keep
# their own limits). Stops a huge JSON / image body from filling the memory.
MAX_BODY = 64 * 1024 * 1024
STREAM_PATHS = ("/api/uploads", "/api/music/upload", "/api/bleep/custom")
STREAM_SUFFIXES = ("/chat",)

_lock = threading.Lock()
_token: dict[str, str] = {}


# ------------------------------------------------------------------ token


def token_path() -> Path:
    return config.config_dir() / TOKEN_FILE


def token() -> str:
    """The install's API token (created on first use, then reused, so open tabs survive a restart)."""
    path = token_path()
    key = str(path)
    with _lock:
        if key in _token:
            return _token[key]
        tok = ""
        try:
            tok = path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError):
            pass
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", tok):
            tok = secrets.token_urlsafe(32)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_name(path.name + ".tmp")
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="ascii") as f:
                    f.write(tok)
                os.replace(tmp, path)
            except OSError:
                pass  # read-only settings folder: the token lives for this process only
        _token[key] = tok
        return tok


def token_ok(value: str | None) -> bool:
    return bool(value) and hmac.compare_digest(str(value).encode(), token().encode())


def local_headers() -> dict[str, str]:
    """Headers for a program on this PC calling the local API (tray, launcher)."""
    try:
        return {"X-SharkyClips-Token": token()}
    except Exception:  # noqa: BLE001
        return {}


# ------------------------------------------------------------------ host names


def _own_names() -> set[str]:
    names = {"localhost"}
    try:
        host = socket.gethostname().lower().strip(".")
        if host:
            names |= {host, f"{host}.local", f"{host}.lan", f"{host}.home"}
    except OSError:
        pass
    extra = os.environ.get("SHARKYCLIPS_ALLOWED_HOSTS") or ""
    names |= {h.strip().lower() for h in extra.split(",") if h.strip()}
    return names


def split_host(value: str) -> tuple[str, str | None]:
    """'Host' header -> (lower-case name without brackets, port or None)."""
    value = (value or "").strip().lower()
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            return "", None
        name, rest = value[1:end], value[end + 1:]
        return name, rest[1:] if rest.startswith(":") else None
    if value.count(":") == 1:
        name, port = value.split(":")
        return name, port
    return value, None


def host_allowed(value: str | None) -> bool:
    name, port = split_host(value or "")
    if not name or (port is not None and not port.isdigit()):
        return False
    try:
        ipaddress.ip_address(name)
        return True  # an IP literal can't be rebound (rebinding needs a domain name)
    except ValueError:
        pass
    return name in _own_names() or name.endswith(".localhost")


# ------------------------------------------------------------------ origin


def origin_matches(origin: str, host: str) -> bool:
    """The Origin header names this very server (scheme http(s), same host and port)."""
    m = re.fullmatch(r"(https?)://(.+)", origin.strip().lower())
    if not m:
        return False
    o_name, o_port = split_host(m.group(2))
    h_name, h_port = split_host(host)
    default = "443" if m.group(1) == "https" else "80"
    return bool(o_name) and o_name == h_name and (o_port or default) == (h_port or default) \
        and host_allowed(m.group(2))


# 1.2.70: the SharkyClips Helper extension (assisted upload) calls these from its own origin
# (chrome-extension://...) with its own key; nothing else under this path is reachable cross-site
EXT_API = "/api/assist/ext/"
EXT_HEADER = "x-sharkyclips-assist"
EXT_PAIR = EXT_API + "pair"  # 1.2.74: a store copy of the Helper asks for its key with a code
EXT_ORIGINS = ("chrome-extension://", "moz-extension://", "extension://")


def check(method: str, path: str, headers: Headers) -> tuple[int, str, str] | None:
    """None = let it through; else (status, code, message)."""
    host = headers.get("host") or ""
    if not host_allowed(host):
        return 421, "bad_host", "Unknown host name. Open SharkyClips at http://127.0.0.1 or http://localhost."
    if path.startswith(EXT_API):
        from .. import assist

        if path == EXT_PAIR and method == "POST":
            # no key yet: only a browser extension (a page can't fake its Origin), code checked in the route
            if (headers.get("origin") or "").startswith(EXT_ORIGINS):
                return None
            return 403, "ext_origin", "Only the SharkyClips Helper can pair."
        if assist.token_ok(headers.get(EXT_HEADER)):
            return None
        return 403, "ext_key", "Missing or wrong SharkyClips Helper key."
    origin = headers.get("origin")
    site = (headers.get("sec-fetch-site") or "").lower()
    mode = (headers.get("sec-fetch-mode") or "").lower()
    cross = site in ("cross-site", "same-site") or (origin not in (None, "", "null") and not origin_matches(origin, host)) \
        or origin == "null"
    is_api = path.startswith("/api/") or path == "/openapi.json"
    if method not in SAFE_METHODS:
        if cross:
            return 403, "cross_origin", "Requests from other websites are blocked."
        if is_api and not token_ok(headers.get(TOKEN_HEADER)):
            return 403, "csrf", "Missing or wrong SharkyClips token. Reload the page."
        return None
    if is_api and cross and not (mode == "navigate" and path.startswith(NAVIGABLE_API)):
        return 403, "cross_origin", "Requests from other websites are blocked."
    return None


# ------------------------------------------------------------------ headers + index.html


_INLINE_SCRIPT = re.compile(rb"<script>(.*?)</script>", re.S)


def csp_for(html: bytes | None = None) -> str:
    """Scripts only from this server (+ the exact inline scripts of index.html, by hash)."""
    hashes = ""
    if html:
        hashes = "".join(f" 'sha256-{base64.b64encode(hashlib.sha256(m).digest()).decode()}'"
                         for m in _INLINE_SCRIPT.findall(html))
    return ("default-src 'self'; "
            f"script-src 'self'{hashes}; "
            "style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; "
            "img-src 'self' data: blob: https:; "
            "media-src 'self' blob: data:; "
            "connect-src 'self'; worker-src 'self'; manifest-src 'self'; "
            "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), geolocation=(), payment=(), usb=()"),
]


def render_index(raw: bytes) -> tuple[bytes, str]:
    """index.html with the API token for the UI, and its CSP."""
    meta = f'<meta name="sharkyclips-token" content="{token()}" />'.encode()
    html = raw.replace(b"<head>", b"<head>\n    " + meta, 1) if b"<head>" in raw else meta + raw
    return html, csp_for(raw)


class BodyTooLarge(Exception):
    pass


def _capped(receive: Receive, limit: int) -> Receive:
    """A chunked body without Content-Length can't grow past the limit either."""
    seen = {"n": 0}

    async def wrapped() -> Message:
        message = await receive()
        if message["type"] == "http.request":
            seen["n"] += len(message.get("body") or b"")
            if seen["n"] > limit:
                raise BodyTooLarge("request body too large")
        return message

    return wrapped


class SecurityGuard:
    """Pure ASGI middleware (no buffering: the live event stream and video ranges are unaffected)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        method = "POST" if scope["type"] == "websocket" else scope.get("method", "GET")
        refused = check(method, scope.get("path", ""), headers)
        if refused is not None:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            status, code, msg = refused
            res = JSONResponse({"error": msg, "code": code, "hint": None}, status_code=status)
            await res(scope, receive, self._sender(send, scope.get("path", "")))
            return
        path = scope.get("path", "")
        if scope["type"] == "http" and not (path.startswith(STREAM_PATHS) or path.endswith(STREAM_SUFFIXES)):
            try:
                declared = int(headers.get("content-length") or 0)
            except ValueError:
                declared = 0
            if declared > MAX_BODY:
                res = JSONResponse({"error": "This request is too large.", "code": "too_large", "hint": None},
                                   status_code=413)
                await res(scope, receive, self._sender(send, path))
                return
            receive = _capped(receive, MAX_BODY)
        await self.app(scope, receive, self._sender(send, path))

    @staticmethod
    def _sender(send: Send, path: str) -> Send:
        api = path.startswith("/api/")
        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                raw = list(message.get("headers") or [])
                have = {k.lower() for k, _ in raw}
                for k, v in BASE_HEADERS:
                    if k not in have:
                        raw.append((k, v))
                if api and b"cross-origin-resource-policy" not in have:
                    # other sites can't embed our videos / images / JSON (the splash page's
                    # favicon ping and the public UI files stay embeddable)
                    raw.append((b"cross-origin-resource-policy", b"same-origin"))
                if b"content-security-policy" not in have:
                    ctype = next((v for k, v in raw if k.lower() == b"content-type"), b"")
                    if ctype.startswith(b"text/html"):
                        raw.append((b"content-security-policy", csp_for().encode()))
                    elif not ctype.startswith((b"video/", b"audio/", b"image/")):
                        # JSON / text opened as a page: nothing in it may run or be framed
                        raw.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; sandbox"))
                # never let a browser share our answers with another site
                raw = [(k, v) for k, v in raw if not k.lower().startswith(b"access-control-")]
                message = {**message, "headers": raw}
            await send(message)

        return wrapped
