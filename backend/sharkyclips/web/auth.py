"""LAN access PIN: the login API and the guard in front of every other API call.

Only requests from other devices are checked, and only when a PIN is set (lanauth.enabled()).
The UI files themselves (index.html, /assets) stay public so the login screen can load; every
/api/ path except /api/auth/* and the OpenAPI schema need a valid session cookie.
"""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from .. import lanauth

LOCAL_HOSTS = ("127.0.0.1", "::1", "localhost", "testclient")
OPEN_PREFIXES = ("/api/auth/",)
GUARDED_PREFIXES = ("/api/", "/openapi.json")

router = APIRouter(prefix="/api/auth")


def is_local_host(host: str | None) -> bool:
    return (host or "") in LOCAL_HOSTS


def _host(conn: HTTPConnection) -> str:
    return conn.client.host if conn.client else ""


def needs_login(conn: HTTPConnection) -> bool:
    """True when this request may not reach the API yet."""
    if is_local_host(_host(conn)) or not lanauth.enabled():
        return False
    path = conn.url.path
    if path.startswith(OPEN_PREFIXES) or not path.startswith(GUARDED_PREFIXES):
        return False
    return not lanauth.session_valid(conn.cookies.get(lanauth.COOKIE))


class LanGuard:
    """Pure ASGI middleware (no buffering, so the live event stream is unaffected)."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and needs_login(HTTPConnection(scope)):
            res = JSONResponse({"error": "Log in with the access PIN first.", "code": "auth_required",
                                "hint": None}, status_code=401)
            await res(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _status(request: Request) -> dict:
    local = is_local_host(_host(request))
    on = lanauth.enabled()
    authed = local or not on or lanauth.session_valid(request.cookies.get(lanauth.COOKIE))
    return {"enabled": on, "kind": lanauth.kind(), "is_local": local, "required": on and not local,
            "authenticated": authed, "lan": bool(getattr(request.app.state, "lan_url", None))}


def _local_only(request: Request) -> None:
    if not is_local_host(_host(request)):
        raise HTTPException(403, "Only the computer running SharkyClips can change the access PIN.")


@router.get("/status")
def auth_status(request: Request) -> dict:
    return _status(request)


@router.post("/login")
def auth_login(request: Request, body: dict | None = None) -> JSONResponse:
    ip = _host(request)
    if is_local_host(ip) or not lanauth.enabled():
        return JSONResponse(_status(request))
    wait = lanauth.limiter.wait(ip)
    if wait > 0:
        secs = math.ceil(wait)
        return JSONResponse({"error": "Too many tries. Wait a moment.", "code": "locked", "retry_after": secs,
                             "hint": None}, status_code=429, headers={"Retry-After": str(secs)})
    if not lanauth.verify(str((body or {}).get("secret") or "")):
        wait = lanauth.limiter.fail(ip)
        return JSONResponse({"error": "Wrong PIN or password.", "code": "wrong",
                             "retry_after": math.ceil(wait) or None, "hint": None}, status_code=401)
    lanauth.limiter.success(ip)
    res = JSONResponse({**_status(request), "authenticated": True})
    res.set_cookie(lanauth.COOKIE, lanauth.new_session(), max_age=lanauth.SESSION_DAYS * 86400,
                   httponly=True, samesite="strict", path="/")
    return res


@router.post("/logout")
def auth_logout(request: Request) -> JSONResponse:
    lanauth.end_session(request.cookies.get(lanauth.COOKIE))
    res = JSONResponse({**_status(request), "authenticated": is_local_host(_host(request)) or not lanauth.enabled()})
    res.delete_cookie(lanauth.COOKIE, path="/")
    return res


@router.put("/secret")
def auth_set(request: Request, body: dict | None = None) -> dict:
    _local_only(request)
    lanauth.set_secret(str((body or {}).get("secret") or ""))
    return _status(request)


@router.delete("/secret")
def auth_clear(request: Request) -> dict:
    _local_only(request)
    lanauth.clear_secret()
    return _status(request)
