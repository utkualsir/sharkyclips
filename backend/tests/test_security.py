"""1.2.52 security audit: one regression test (at least) for every fix (docs/SECURITY_AUDIT.md)."""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sharkyclips import config, lanauth, netguard, phone, platforms as PF, redact, updater, youtube
from sharkyclips.web import security
from sharkyclips.web.app import app

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
EVIL = "http://evil.example"


def client(**kw) -> TestClient:
    """A browser-like client WITHOUT the API token (conftest adds it to every other client)."""
    c = TestClient(app, **kw)
    c.headers.pop(security.TOKEN_HEADER, None)
    return c


def token_client(**kw) -> TestClient:
    return TestClient(app, headers={security.TOKEN_HEADER: security.token()}, **kw)


def _all_routes():
    out = []

    def walk(routes):
        for r in routes:
            if hasattr(r, "original_router"):
                walk(r.original_router.routes)
            elif hasattr(r, "path") and hasattr(r, "methods"):
                out.append(r)

    walk(app.routes)
    return out


# ------------------------------------------------------------------ C8: DNS rebinding (Host header)


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "localhost.evil.example",
                                  "127.0.0.1.nip.io:8000", "attacker.com:80"])
def test_rebinding_host_is_refused(host):
    r = client().get("/api/settings", headers={"Host": host})
    assert r.status_code == 421 and r.json()["code"] == "bad_host"
    assert token_client().post("/api/projects", json={}, headers={"Host": host}).status_code == 421


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "[::1]:8000", "192.168.1.20:8000",
                                  "testserver", "localhost"])
def test_own_host_names_are_served(host):
    assert client().get("/api/meta", headers={"Host": host}).status_code in (200, 403)  # 403: LAN PIN
    assert security.host_allowed(host)


def test_host_parsing_edge_cases():
    assert not security.host_allowed("")
    assert not security.host_allowed("localhost:80x")
    assert not security.host_allowed("[::1")
    assert security.host_allowed("[::1]")
    assert security.host_allowed("app.localhost:5173")


# ------------------------------------------------------------------ C8: CSRF / Origin / token


def test_cross_origin_post_is_refused_even_with_token():
    c = token_client()
    for headers in ({"Origin": EVIL}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"},
                    {"Sec-Fetch-Site": "same-site", "Origin": "http://localhost:3000"},
                    {"Origin": "http://127.0.0.1:9999", "Host": "127.0.0.1:8000"}):
        r = c.put("/api/settings", json={"default_mode": "study"}, headers=headers)
        assert r.status_code == 403 and r.json()["code"] == "cross_origin", headers
    assert config.get("default_mode") != "study"


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/quit"), ("POST", "/api/update/restart"), ("POST", "/api/update"),
    ("PUT", "/api/settings"), ("POST", "/api/projects"), ("DELETE", "/api/projects/x"),
    ("POST", "/api/youtube/disconnect"), ("PUT", "/api/youtube/client"), ("POST", "/api/youtube/connect"),
    ("POST", "/api/youtube/shared-client/reload"), ("PUT", "/api/uploads?filename=a.mp4"),
    ("POST", "/api/music/open"), ("POST", "/api/platforms/reveal"), ("POST", "/api/pubqueue/open"),
    ("PUT", "/api/auth/secret"), ("DELETE", "/api/auth/secret"), ("POST", "/api/library/tick"),
])
def test_state_changing_requests_need_the_token(method, path):
    """A form / fetch from another site can't add the header; a same-origin page can't either
    without reading index.html (which another site can't)."""
    r = client().request(method, path, json={})
    assert r.status_code == 403 and r.json()["code"] == "csrf", (method, path)
    r = client().request(method, path, json={}, headers={security.TOKEN_HEADER: "wrong" * 10})
    assert r.status_code == 403


def test_every_write_route_is_guarded():
    """No POST / PUT / DELETE route anywhere slips past the token check."""
    c = client()
    writes = [(m, r.path) for r in _all_routes() for m in (r.methods or ()) if m in ("POST", "PUT", "PATCH", "DELETE")]
    assert len(writes) > 150
    for method, path in writes:
        url = re.sub(r"\{[^}]+\}", "x", path)
        res = c.request(method, url, content=b"{}", headers={"Content-Type": "application/json"})
        assert res.status_code == 403, (method, path, res.status_code)


def test_token_lets_the_ui_through_and_is_in_index_html(tmp_path, monkeypatch):
    assert token_client().put("/api/settings", json={"default_mode": "gaming"}).status_code == 200
    from sharkyclips.web import app as A

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html><head><title>t</title><script>var a=1;</script>"
                                     "</head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(A, "FRONTEND_DIST", dist)
    r = client().get("/")
    assert r.status_code == 200
    assert f'<meta name="sharkyclips-token" content="{security.token()}"' in r.text
    csp = r.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in csp and "'sha256-" in csp and "'unsafe-inline'" not in csp.split("style-src")[0]
    assert r.headers["cache-control"] == "no-store"
    assert client().get("/index.html").text == r.text  # never the raw file without the token


def test_token_is_stable_and_private(tmp_path, monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(tmp_path))
    t1 = security.token()
    security._token.clear()
    assert security.token() == t1 == (tmp_path / "api_token").read_text().strip()  # open tabs survive restarts
    assert len(t1) >= 40
    assert security.local_headers() == {"X-SharkyClips-Token": t1}


def test_cross_site_reads_of_the_api_are_refused():
    """<img src>, <video src>, <script src> or a no-cors fetch from another site get nothing."""
    c = client()
    for headers in ({"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "image"},
                    {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors", "Origin": EVIL},
                    {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"}):
        r = c.get("/api/settings", headers=headers)
        assert r.status_code == 403, headers
    # an OAuth provider sending the browser back is a top-level navigation: allowed (it checks `state`)
    r = c.get("/api/platforms/reels/callback?code=x", headers={"Sec-Fetch-Site": "cross-site",
                                                               "Sec-Fetch-Mode": "navigate"})
    assert r.status_code == 200 and "expired" in r.text
    assert c.get("/api/settings", headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200


def test_no_cors_and_security_headers():
    r = client().get("/api/meta", headers={"Origin": "http://testserver"})
    h = {k.lower() for k in r.headers}
    assert not any(k.startswith("access-control-") for k in h)
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cross-origin-resource-policy"] == "same-origin"
    assert "sandbox" in r.headers["content-security-policy"]
    pre = client().options("/api/settings", headers={"Origin": EVIL, "Access-Control-Request-Method": "PUT"})
    assert "access-control-allow-origin" not in {k.lower() for k in pre.headers}


def test_api_docs_are_off():
    assert client().get("/api/docs").status_code == 404
    assert client().get("/openapi.json").status_code in (404, 200) and "paths" not in client().get("/openapi.json").text


def test_huge_bodies_are_refused():
    big = str(security.MAX_BODY + 1)
    r = token_client().put("/api/settings", content=b"{}", headers={"Content-Length": big,
                                                                     "Content-Type": "application/json"})
    assert r.status_code == 413


# ------------------------------------------------------------------ C9: LAN mode


def phone_client() -> TestClient:
    return TestClient(app, client=("192.168.1.50", 50000), headers={security.TOKEN_HEADER: security.token()})


def test_lan_without_pin_serves_no_api_and_no_media():
    lanauth.clear_secret()
    p = phone_client()
    for path in ("/api/settings", "/api/projects", "/api/youtube", "/api/projects/x/media/source",
                 "/api/projects/x/clips/c01/video"):
        r = p.get(path)
        assert r.status_code == 403 and r.json()["code"] == "pin_required", path


def test_lan_session_cookie_flags_and_lockout():
    lanauth.set_secret("135790")
    lanauth.limiter = lanauth.Limiter()
    try:
        p = phone_client()
        for _ in range(5):
            assert p.post("/api/auth/login", json={"secret": "000000"}).status_code == 401
        r = p.post("/api/auth/login", json={"secret": "135790"})
        assert r.status_code == 429  # locked, even with the right PIN
        lanauth.limiter = lanauth.Limiter()
        r = p.post("/api/auth/login", json={"secret": "135790"})
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert p.get("/api/settings").status_code == 200
        assert p.post("/api/youtube/shared-client/reload").status_code == 403  # this PC only
    finally:
        lanauth.clear_secret()


# ------------------------------------------------------------------ B6: secrets never reach the UI

FAKE = {
    "yt_refresh": "1//0gFAKErefreshTOKENabcdefghijklmnopqrstuvwxyz0123456789",
    "yt_access": "ya29.FAKEaccessTOKENabcdefghijklmnopqrstuvwxyz",
    "yt_secret": "GOCSPX-FAKEclientSECRETabcdef",
    "tg": "123456789:AAFAKEbotTOKENabcdefghijklmnopqrstuvwx",
    "ig": "IGAAFAKEinstagramTOKENabcdefghijklmnopqrstuvwxyz",
    "tt": "act.FAKEtiktokACCESSabcdefghijklmnopqrstuvwxyz",
    "meta_secret": "fakeMetaAppSecret0123456789abcdef",
}


class _NoNet:
    def __getattr__(self, name):
        def fail(*a, **kw):
            raise ConnectionError("no network in tests")
        return fail


def test_no_secret_in_any_api_answer(monkeypatch):
    monkeypatch.setattr(youtube, "_http", lambda: _NoNet())
    monkeypatch.setattr(PF, "_http", lambda: _NoNet())
    monkeypatch.setenv("SHARKYCLIPS_TG_ENDPOINT", "http://127.0.0.1:9")
    cid = "123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com"
    youtube.set_client({"installed": {"client_id": cid, "client_secret": FAKE["yt_secret"], "project_id": "p"}})
    youtube._write_token({"refresh_token": FAKE["yt_refresh"], "access_token": FAKE["yt_access"],
                          "expires_at": 9e12, "client_id": cid, "channel": {"id": "UC1", "title": "Me"}})
    phone._save({"token": FAKE["tg"], "bot": "b", "code": "c", "chat_id": 42, "offset": 0})
    PF.save_token("reels", {"access_token": FAKE["ig"], "user_id": "1"})
    PF.save_token("tiktok", {"access_token": FAKE["tt"], "refresh_token": FAKE["tt"] + "R"})
    PF.save_app("reels", {"app_id": "1", "app_secret": FAKE["meta_secret"]})
    lanauth.set_secret("4321")
    try:
        c = token_client(raise_server_exceptions=False)
        seen = 0
        for r in _all_routes():
            if "GET" not in (r.methods or ()) or "{" in r.path or r.path in ("/api/events", "/api/update"):
                continue
            res = c.get(r.path)
            text = res.text
            seen += 1
            for name, value in FAKE.items():
                assert value not in text, (r.path, name)
            assert "scrypt$" not in text and security.token() not in text, r.path
        assert seen > 30
        assert c.get("/api/update?fetch=false").status_code == 200
    finally:
        youtube.disconnect()
        youtube.remove_client() if youtube.load_client() else None
        phone._save({})
        PF.forget("reels")
        PF.forget("tiktok")
        lanauth.clear_secret()


def test_secrets_are_encrypted_at_rest():
    cid = "123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com"
    youtube._write_token({"refresh_token": FAKE["yt_refresh"], "client_id": cid})
    phone._save({"token": FAKE["tg"], "chat_id": 1})
    PF.save_token("reels", {"access_token": FAKE["ig"]})
    try:
        for f in config.config_dir().rglob("*"):
            if f.is_file() and f.stat().st_size < 2_000_000:
                raw = f.read_bytes()
                for name in ("yt_refresh", "tg", "ig"):
                    assert FAKE[name].encode() not in raw, (f, name)
    finally:
        youtube.disconnect()
        phone._save({})
        PF.forget("reels")


# ------------------------------------------------------------------ B6: redaction


@pytest.mark.parametrize("secret", [
    FAKE["yt_refresh"], FAKE["yt_access"], FAKE["yt_secret"], FAKE["tg"], FAKE["ig"],
    "AIzaSyFAKEfakeFAKEfakeFAKEfakeFAKEfake12", "ghp_" + "a" * 36, "EAAB" + "x" * 40,
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
])
def test_redact_masks_token_like_text(secret):
    for text in (f"error {secret} here", f"https://x.test/cb?access_token={secret}&a=1",
                 json.dumps({"refresh_token": secret}), f"Authorization: Bearer {secret}",
                 f"https://api.telegram.org/bot{FAKE['tg']}/getMe"):
        out = redact.redact(text)
        assert secret not in out and FAKE["tg"] not in out


def test_redact_keeps_normal_text():
    for text in ("Rendered 3 clips in 12.5 s", "Wrong PIN or password.", "Enter the app secret of your Meta app.",
                 "c01 -> https://youtu.be/abc123", "exit code 1"):
        assert redact.redact(text) == text


def test_redacting_stream_and_logging():
    buf = io.StringIO()
    s = redact.RedactingStream(buf)
    s.write(f"refresh with {FAKE['yt_refresh']}\n")
    assert FAKE["yt_refresh"] not in buf.getvalue() and "[redacted]" in buf.getvalue()
    import logging

    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "token=%s", (FAKE["ig"],), None)
    redact.RedactingFilter().filter(rec)
    assert FAKE["ig"] not in rec.getMessage()


def test_cli_installs_redaction():
    code = ("import sys; sys.argv=['cli.py','--help']\n"
            "try:\n import cli\nexcept SystemExit: pass\n"
            "from sharkyclips.redact import RedactingStream\n"
            "print(isinstance(sys.stdout, RedactingStream))\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120)
    assert out.stdout.strip().endswith("True"), out.stderr[-500:]


def test_error_answers_and_job_errors_are_redacted():
    from sharkyclips.errors import SharkyClipsError
    from sharkyclips.web import jobs as J

    jm = J.JobManager()

    def boom(_job):
        raise SharkyClipsError(f"Google said invalid_grant for {FAKE['yt_refresh']}", f"token={FAKE['ig']}")

    job = jm.submit("analyze", "io", None, {}, boom)
    for _ in range(200):
        if job.status in ("error", "done"):
            break
        import time

        time.sleep(0.02)
    assert job.status == "error"
    assert FAKE["yt_refresh"] not in json.dumps(job.error) and FAKE["ig"] not in json.dumps(job.error)


# ------------------------------------------------------------------ D11: path traversal

PAYLOADS = ["..", "...", "..\\..\\..\\secret-marker.txt", "..\\secret-marker.txt", "C:\\Windows\\win.ini",
            "\\\\evil\\share\\x", "%2e%2e", "con", "c01\\..\\..\\..\\secret-marker.txt", "x\x00.mp4"]


@pytest.fixture
def victim_project():
    ws = config.workspace_dir()
    p = ws / "sec-test"
    (p / "clips").mkdir(parents=True, exist_ok=True)
    (p / "meta.json").write_text(json.dumps({"id": "sec-test", "title": "<img src=x onerror=alert(1)>",
                                             "mode": "gaming", "files": {"source": "..\\..\\secret-marker.txt"}}),
                                 encoding="utf-8")
    marker = config.config_dir() / "secret-marker.txt"
    marker.write_text("SC-SECRET-MARKER-42", encoding="utf-8")
    (ws / "secret-marker.txt").write_text("SC-SECRET-MARKER-42", encoding="utf-8")
    yield "sec-test"
    import shutil

    shutil.rmtree(p, ignore_errors=True)
    (ws / "secret-marker.txt").unlink(missing_ok=True)


def test_no_route_reads_files_outside_the_workspace(victim_project):
    c = token_client(raise_server_exceptions=False)
    checked = 0
    for r in _all_routes():
        if "GET" not in (r.methods or ()) or "{" not in r.path:
            continue
        names = re.findall(r"\{([^}:]+)(?::[^}]+)?\}", r.path)
        for payload in PAYLOADS:
            url = r.path
            for n in names:
                val = victim_project if n == "project_id" and payload != ".." else payload
                url = re.sub(r"\{" + n + r"(?::[^}]+)?\}", urllib.parse.quote(val, safe=""), url)
            try:
                res = c.get(url)
            except Exception:  # noqa: BLE001 - a crash is not a leak (the server answers 500)
                continue
            checked += 1
            assert b"SC-SECRET-MARKER-42" not in res.content, (r.path, payload)
            assert b"[fonts]" not in res.content.lower() and b"; for 16-bit" not in res.content.lower(), (r.path, payload)
    assert checked > 100


def test_static_ui_route_stays_inside_dist(tmp_path, monkeypatch):
    from sharkyclips.web import app as A

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><head></head></html>", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("SC-SECRET-MARKER-42", encoding="utf-8")
    monkeypatch.setattr(A, "FRONTEND_DIST", dist)
    c = client()
    for p in ("../outside.txt", "..%2foutside.txt", "..%5coutside.txt", "%2e%2e/outside.txt", "..\\outside.txt"):
        assert "SC-SECRET-MARKER-42" not in c.get("/" + p).text, p


def test_open_folder_never_runs_a_file(tmp_path):
    from sharkyclips import easy as E

    exe = tmp_path / "evil.bat"
    exe.write_text("echo pwned", encoding="utf-8")
    assert not E.is_openable_folder(exe)
    assert not E.open_folder(exe)
    assert not E.is_openable_folder(Path("\\\\evil\\share"))
    assert E.is_openable_folder(tmp_path)


def test_reveal_only_inside_downloads(tmp_path):
    r = token_client().post("/api/platforms/reveal", json={"file": str(tmp_path / "x.mp4")})
    assert r.status_code == 400
    r = token_client().post("/api/platforms/reveal", json={"file": str(PF.config.config_dir() / ".." / "x")})
    assert r.status_code == 400


def test_upload_filename_cant_escape(tmp_path):
    c = token_client()
    r = c.put("/api/uploads?filename=..%5C..%5Cevil.exe", content=b"x")
    assert r.status_code == 400  # not a video type
    r = c.put("/api/uploads?filename=..%5C..%5C..%5Cevil.mp4", content=b"")
    assert r.status_code == 400 and not (config.workspace_dir().parent / "evil.mp4").exists()


# ------------------------------------------------------------------ D12: command injection


def test_no_shell_true_or_eval_anywhere():
    bad = re.compile(r"shell\s*=\s*True|os\.system\(|os\.popen\(|\beval\(|pickle\.loads?\(|yaml\.load\(")
    hits = []
    for f in list((BACKEND / "sharkyclips").rglob("*.py")) + [BACKEND / "cli.py"]:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if bad.search(line) and not line.lstrip().startswith("#"):
                hits.append(f"{f.name}:{i}: {line.strip()}")
    assert not hits, hits


def test_powershell_scripts_get_paths_as_env_not_text():
    src = (BACKEND / "cli.py").read_text(encoding="utf-8")
    block = src[src.index("def _migrate_windows_shortcuts"):]
    block = block[:block.index("subprocess.run")]
    assert "{pythonw}" not in block and "{root}" not in block and "$env:SC_PYW" in block


# ------------------------------------------------------------------ D13: SSRF


def _res(mapping):
    return lambda host: mapping.get(host, [])


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/api/settings", "http://localhost/", "http://[::1]/", "http://0.0.0.0/",
    "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/v.mp4", "http://192.168.1.1/",
    "http://172.16.0.1/", "http://100.64.0.1/", "http://[::ffff:127.0.0.1]/", "http://[fe80::1]/",
    "http://nas.local/v.mp4", "http://router.lan/", "http://rebind.example/", "http://2130706433/",
    "file:///C:/Windows/win.ini", "ftp://example.com/x", "http://user:pw@example.com/v",
    "gopher://127.0.0.1:25/", "http://224.0.0.1/",
])
def test_ssrf_links_are_refused(url):
    resolver = _res({"rebind.example": ["127.0.0.1"], "2130706433": ["127.0.0.1"]})
    with pytest.raises(netguard.SharkyClipsError):
        netguard.check_public_url(url, resolve=resolver)


def test_public_links_pass():
    resolver = _res({"www.twitch.tv": ["151.101.2.167"], "www.youtube.com": ["142.250.185.78", "2a00:1450:4001:82a::200e"]})
    assert netguard.check_public_url("https://www.twitch.tv/videos/1", resolve=resolver)
    assert netguard.check_public_url("https://www.youtube.com/watch?v=x", resolve=resolver)
    # a name that resolves to one public AND one private address is refused
    with pytest.raises(netguard.SharkyClipsError):
        netguard.check_public_url("https://mixed.example/", resolve=_res({"mixed.example": ["8.8.8.8", "10.0.0.1"]}))


def test_ssrf_blocked_in_the_import_api():
    c = token_client()
    for path in ("/api/projects", "/api/easy/projects"):
        r = c.post(path, json={"url": "http://127.0.0.1:8000/api/settings"})
        assert r.status_code == 400 and "local network" in r.json()["error"], path


def test_private_imports_can_be_allowed_on_purpose(monkeypatch):
    monkeypatch.setattr(config, "get", lambda k, d=None: True if k == "import_allow_private" else d)
    assert netguard.check_public_url("http://192.168.1.10/v.mp4")
    with pytest.raises(netguard.SharkyClipsError):  # never file:// or credentials
        netguard.check_public_url("file:///etc/passwd")


def test_ingest_rechecks_the_url_yt_dlp_ended_on(monkeypatch):
    from sharkyclips import ingest

    class FakeYDL:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            return {"title": "t", "id": "1", "extractor_key": "Generic", "webpage_url": url,
                    "url": "http://169.254.169.254/latest/meta-data/"}

    import types

    monkeypatch.setattr(ingest, "require_module", lambda *_a, **_k: types.SimpleNamespace(YoutubeDL=FakeYDL))
    with pytest.raises(ingest.SharkyClipsError, match="local network"):
        ingest._ingest_url("https://redirect.example/v")


# ------------------------------------------------------------------ E16: OAuth


def test_instagram_callback_needs_the_state(monkeypatch):
    monkeypatch.setattr(PF, "META_AUTOMATION", True)
    called = []
    monkeypatch.setattr(PF, "_http", lambda: called.append(1) or _NoNet())
    with PF._plock:
        PF._pending["ig"] = {"state": "good-state", "redirect": "http://x", "at": __import__("time").time()}
    c = client()
    assert "expired" in c.get("/api/platforms/reels/callback?code=abc").text  # no state: login CSRF
    assert "expired" in c.get("/api/platforms/reels/callback?code=abc&state=bad").text
    assert not called  # no token exchange happened


def test_youtube_oauth_uses_pkce_state_and_loopback(monkeypatch):
    cid = "123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com"
    monkeypatch.setattr(youtube, "active_client", lambda: {"client_id": cid, "client_secret": "s"})
    url = youtube.auth_url("http://127.0.0.1:5555/")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
    assert q["code_challenge_method"] == "S256" and len(q["state"]) >= 24
    assert q["redirect_uri"].startswith("http://127.0.0.1:")
    with pytest.raises(youtube.SharkyClipsError):
        youtube.finish_auth("code", "not-the-state")
    from sharkyclips import ytconnect

    assert '"127.0.0.1", 0' in Path(ytconnect.__file__).read_text(encoding="utf-8")


# ------------------------------------------------------------------ E17: Telegram


def test_telegram_pairing_code_is_long_and_private_chat_only(monkeypatch):
    monkeypatch.setattr(phone, "call", lambda method, **kw: {"username": "bot"} if method == "getMe" else [
        {"update_id": 1, "message": {"text": "/start " + phone._load()["code"], "chat": {"id": -100, "type": "group"}}},
    ])
    phone.set_token("123456789:AAbcdefghijklmnopqrstuvwxyz012345678")
    try:
        assert len(phone._load()["code"]) >= 20
        phone.pair_check()
        assert not phone._load().get("chat_id")  # a group chat can't pair
    finally:
        phone._save({})


def test_telegram_buttons_only_from_the_paired_chat():
    acted = []
    bot = phone.Poller.__new__(phone.Poller)
    bot.act = lambda *a: acted.append(a) or "ok"
    d = {"chat_id": 42}
    bot.handle({"callback_query": {"id": "1", "data": "u|t", "message": {"chat": {"id": 99}}, "from": {"id": 99}}}, d)
    bot.handle({"callback_query": {"id": "1", "data": "u|t", "message": {"chat": {"id": 42}}, "from": {"id": 7}}}, d)
    assert not acted


# ------------------------------------------------------------------ A3: YouTube quota guard


def test_quota_reserve_keeps_room_for_deletes_and_never_blocks_uploads(monkeypatch):
    # 1.2.68: uploads have their own Google bucket; the reserve keeps units free for deletes / edits
    monkeypatch.setattr(youtube, "daily_quota", lambda: 10_000)
    monkeypatch.setattr(youtube, "quota_used", lambda now=None: 10_000 - 200)
    assert youtube.quota_reserve() == youtube.DEFAULT_RESERVE
    assert youtube.upload_room() < youtube.COST["thumbnail"] and not youtube.thumbnail_fits()
    youtube.check_quota(youtube.COST["delete"])  # a delete may still use the reserve
    with pytest.raises(youtube.SharkyClipsError):
        youtube.check_quota(250)
    monkeypatch.setattr(youtube, "uploads_used", lambda now=None: 0)
    youtube.check_upload_quota()  # the upload bucket is untouched
    assert youtube.quota_view()["uploads_left"] == youtube.daily_uploads()


def test_upload_over_quota_is_queued_for_tomorrow(monkeypatch):
    monkeypatch.setattr(youtube, "upload_room", lambda now=None: 0)
    item = youtube.defer_upload("p1", "c01", {"title": "t"})
    assert datetime.fromisoformat(item["after"]) > datetime.now(timezone.utc)
    assert [(d["project_id"], d["clip_id"]) for d in youtube.deferred_list()] == [("p1", "c01")]
    assert youtube.take_due_deferred() == []  # not yet: before the reset
    monkeypatch.setattr(youtube, "upload_room", lambda now=None: 10_000)
    due = youtube.take_due_deferred(datetime.now(timezone.utc) + timedelta(days=1, hours=1))
    assert [d["clip_id"] for d in due] == ["c01"] and youtube.deferred_list() == []


def test_shared_client_reload_endpoint(tmp_path, monkeypatch):
    f = tmp_path / "google_client.json"
    monkeypatch.setenv("SHARKYCLIPS_SHARED_CLIENT", str(f))
    c = token_client()
    r = c.post("/api/youtube/shared-client/reload")
    assert r.status_code == 200 and r.json()["reload"]["available"] is False and not r.json()["ready"]
    f.write_text("{broken", encoding="utf-8")
    assert c.post("/api/youtube/shared-client/reload").status_code == 400
    cid = "123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com"
    f.write_text(json.dumps({"client_id": cid, "client_secret": "GOCSPX-new", "project_id": "mine"}), encoding="utf-8")
    youtube._write_token({"refresh_token": "1//x", "client_id": cid})
    try:
        rel = c.post("/api/youtube/shared-client/reload").json()["reload"]
        assert rel["available"] and rel["token_ok"] and not rel["needs_reconnect"]  # rotated secret: still signed in
        f.write_text(json.dumps({"client_id": "999" + cid[3:], "client_secret": "GOCSPX-z"}), encoding="utf-8")
        assert c.post("/api/youtube/shared-client/reload").json()["reload"]["needs_reconnect"]
    finally:
        youtube.disconnect()


# ------------------------------------------------------------------ F20: updater


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def test_updater_refuses_an_unofficial_remote(tmp_path, monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_UPDATE_REPO", raising=False)
    remote, user = tmp_path / "evil.git", tmp_path / "user"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "clone", "-q", str(remote), str(user))
    (user / "VERSION").write_text("1.0.0\n")
    _git(user, "add", "-A")
    _git(user, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "x")
    _git(user, "push", "-q", "-u", "origin", "main")
    st = updater.status(root=user)
    assert st["reason"] == "unofficial_remote" and not st["available"]
    with pytest.raises(updater.SharkyClipsError, match="official"):
        updater.apply(root=user)


def test_updater_remote_normalisation():
    for url in ("https://github.com/utkualsir/sharkyclips.git", "https://github.com/utkualsir/sharkyclips",
                "git@github.com:utkualsir/sharkyclips.git", "ssh://git@github.com/utkualsir/sharkyclips.git",
                "https://GitHub.com/UtkuAlsir/SharkyClips/"):
        assert updater._norm_remote(url) == updater.OFFICIAL_REPO, url
    for url in ("https://github.com/attacker/sharkyclips.git", "https://github.com.evil.example/utkualsir/sharkyclips",
                "https://evil.example/github.com/utkualsir/sharkyclips"):
        assert updater._norm_remote(url) != updater.OFFICIAL_REPO, url


def test_updater_needs_a_release_tag_on_the_branch(tmp_path, monkeypatch):
    remote, author, user = tmp_path / "remote.git", tmp_path / "author", tmp_path / "user"
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_REPO", str(remote))
    monkeypatch.setattr(updater, "__version__", "1.0.0")
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    _git(tmp_path, "clone", "-q", str(remote), str(author))
    _git(author, "checkout", "-q", "-b", "main")

    def commit(v, tag):
        (author / "VERSION").write_text(v + "\n")
        _git(author, "add", "-A")
        _git(author, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", v)
        if tag:
            _git(author, "tag", f"v{v}")
        _git(author, "push", "-q", "--tags", "-u", "origin", "main")

    commit("1.0.0", True)
    _git(tmp_path, "clone", "-q", str(remote), str(user))
    commit("1.0.1", False)  # VERSION bumped, but no release tag (yet)
    st = updater.status(root=user)
    assert not st["available"] and st["reason"] == "not_released"
    with pytest.raises(updater.SharkyClipsError, match="isn't released"):
        updater.apply(root=user)
    assert (user / "VERSION").read_text().strip() == "1.0.0"
    _git(author, "tag", "v1.0.1")
    _git(author, "push", "-q", "--tags")
    commit("1.0.2-dev", False)  # a later, untagged commit is never installed by accident
    (author / "VERSION").write_text("1.0.1\n")
    _git(author, "add", "-A")
    _git(author, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "back")
    _git(author, "push", "-q")
    res = updater.apply(root=user)
    assert res["version"] == "1.0.1"
    assert _git(user, "rev-parse", "HEAD") == _git(user, "rev-parse", "v1.0.1^{commit}")


# ------------------------------------------------------------------ A1 / G24: repo contents


def test_no_secrets_or_personal_data_in_tracked_files():
    files = _git(REPO, "ls-files").splitlines()
    pats = [re.compile(p) for p in (r"GOCSPX-[0-9A-Za-z_\-]{10,}", r"\bAIza[0-9A-Za-z_\-]{35}", r"ya29\.[0-9A-Za-z_\-]{20,}",
                                    r"\b1//0[0-9A-Za-z_\-]{30,}", r"\b\d{8,10}:AA[0-9A-Za-z_\-]{33}", r"ghp_[0-9A-Za-z]{36}",
                                    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", r"[A-Za-z0-9._%+-]+@gmail\.com")]
    hits = []
    for name in files:
        p = REPO / name
        if not p.is_file() or p.suffix.lower() in (".png", ".jpg", ".gif", ".ico", ".mp4", ".woff2", ".ttf", ".webp"):
            continue
        if p.stat().st_size > 3_000_000:
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        for pat in pats:
            for m in pat.finditer(text):
                if ("FAKE" in m.group(0).upper() or m.group(0).lower() in ("you@gmail.com", "name@gmail.com")
                        or name == "backend/tests/test_security.py"):
                    continue  # test placeholders
                hits.append(f"{name}: {pat.pattern}")
    assert not hits, hits
    assert "backend/sharkyclips/google_client.json" not in files


# ------------------------------------------------------------------ F23: downloads are verified


def test_laughter_model_download_is_checksum_verified(tmp_path, monkeypatch):
    import tarfile

    from sharkyclips.highlights.signals import laughter

    bad = tmp_path / "evil.tar.bz2"
    payload = tmp_path / "model.int8.onnx"
    payload.write_bytes(b"not the real model")
    with tarfile.open(bad, "w:bz2") as t:
        t.add(payload, arcname="x/model.int8.onnx")
        t.add(payload, arcname="x/class_labels_indices.csv")

    class Resp(io.BytesIO):
        headers: dict = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(laughter, "model_dir", lambda: tmp_path / "ced")
    monkeypatch.setattr(laughter.urllib.request, "urlopen", lambda *a, **k: Resp(bad.read_bytes()))
    with pytest.raises(RuntimeError, match="checksum"):
        laughter.ensure_model(show_progress=False)
    assert not (tmp_path / "ced" / "model.int8.onnx").exists()
