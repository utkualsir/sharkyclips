"""1.2.9: loading a Google "Desktop app" client JSON (Advanced mode), the built-in client, and the
old-server-after-update trap that made a valid client look broken.

The bug (1.2.8): an older SharkyClips process kept running through the update and served the new
UI. The UI's live check called POST /api/youtube/client/check, which the old server didn't have
(405), so a perfectly valid client_secret_....json showed an empty warning and Save stayed off.
"""

from __future__ import annotations

import codecs
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

import cli
from sharkyclips import __version__, youtube, ytconnect
from sharkyclips.web.app import app

# A sanitized copy of a real Desktop client file as Google downloads it in 2026: one line, no
# trailing newline, redirect_uris ["http://localhost"] (no port), fake id and secret.
FAKE_ID = "123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com"
REAL_SHAPE = (
    '{"installed":{"client_id":"' + FAKE_ID + '","project_id":"sharkyclips",'
    '"auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token",'
    '"auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",'
    '"client_secret":"GOCSPX-FAKEfakeFAKEfakeFAKEfake123","redirect_uris":["http://localhost"]}}'
)
LONG_NAME = f"client_secret_{FAKE_ID}.json"  # Google's file name: ~100 characters


def _pretty_crlf() -> str:
    return json.dumps(json.loads(REAL_SHAPE), indent=2).replace("\n", "\r\n") + "\r\n"


VARIANTS = {
    "as_downloaded": REAL_SHAPE.encode(),
    "utf8_bom": codecs.BOM_UTF8 + REAL_SHAPE.encode(),
    "crlf_pretty": _pretty_crlf().encode(),
    "bom_crlf": codecs.BOM_UTF8 + _pretty_crlf().encode(),
    "utf16le_bom": codecs.BOM_UTF16_LE + _pretty_crlf().encode("utf-16-le"),
    "utf16be_bom": codecs.BOM_UTF16_BE + REAL_SHAPE.encode("utf-16-be"),
}


@pytest.fixture
def clean():
    (youtube.folder() / "client.json").unlink(missing_ok=True)
    yield
    ytconnect.cancel()
    youtube.remove_client()


@pytest.mark.parametrize("name", VARIANTS)
def test_real_desktop_client_shape_is_accepted(name):
    c = youtube.check_client_text(youtube.decode_client_bytes(VARIANTS[name]))
    assert c == {"client_id": FAKE_ID, "client_secret": "GOCSPX-FAKEfakeFAKEfakeFAKEfake123",
                 "project_id": "sharkyclips"}


@pytest.mark.parametrize("name", VARIANTS)
def test_api_check_and_save_accept_every_encoding(name, clean):
    c = TestClient(app, base_url="http://127.0.0.1")
    body = VARIANTS[name]
    # what the browser sends: a text/plain body, the file name nowhere in the request
    chk = c.post("/api/youtube/client/check", content=body, headers={"content-type": "text/plain;charset=UTF-8"})
    assert chk.status_code == 200 and chk.json() == {"ok": True, "project_id": "sharkyclips", "client_id": FAKE_ID}
    put = c.put("/api/youtube/client", content=body, headers={"x-filename": LONG_NAME})
    assert put.status_code == 200, put.text
    st = put.json()
    assert st["client"] and st["mode"] == "own" and st["client_id"] == FAKE_ID and st["ready"]


def test_localhost_redirect_client_signs_in_on_a_random_loopback_port_with_pkce(clean):
    """redirect_uris is ["http://localhost"], but Desktop clients accept any loopback port, so the
    sign-in uses http://127.0.0.1:<random port>/ with PKCE (S256)."""
    youtube.set_client(VARIANTS["as_downloaded"])
    a, b = ytconnect.start(open_browser=False), ytconnect.start(open_browser=False)
    for flow in (a, b):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(flow["url"]).query))
        assert q["client_id"] == FAKE_ID
        assert q["redirect_uri"] == f"http://127.0.0.1:{flow['port']}/"
        assert q["code_challenge_method"] == "S256" and len(q["code_challenge"]) == 43
        assert "code_verifier" not in q and "client_secret" not in q
    assert a["port"] != b["port"]


def test_installed_wins_over_a_web_block_and_bad_shapes_explain():
    both = json.loads(REAL_SHAPE)
    both["web"] = {"client_id": "9.apps.googleusercontent.com", "client_secret": "w"}
    assert youtube.check_client_text(json.dumps(both))["client_id"] == FAKE_ID
    for bad in ('{"installed": "oops"}', '{"installed": [1]}', '{"installed": null}'):
        with pytest.raises(youtube.SharkyClipsError):
            youtube.check_client_text(bad)


def test_shipped_built_in_client_is_a_valid_desktop_client(monkeypatch):
    """backend/sharkyclips/google_client.json: Easy mode's "Connect with Google"."""
    monkeypatch.delenv("SHARKYCLIPS_SHARED_CLIENT")
    info = youtube.shared_info()
    assert info["available"], "google_client.json has no client"
    assert info["client"]["client_id"].endswith(".apps.googleusercontent.com")
    assert info["client"]["client_secret"].startswith("GOCSPX-")
    assert info["verification"] in youtube.VERIFICATION and info["user_cap"] > 0


# ------------------------------------------------------------------ old server after an update


class _OldServer:
    """A fake SharkyClips answering /api/meta with an old version until it's asked to restart."""

    def __init__(self, version: str, busy: bool = False, supervised: bool = True):
        self.version, self.busy, self.supervised, self.restarts = version, busy, supervised, 0
        me = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, data):
                raw = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):  # noqa: N802
                if self.path == "/api/meta":
                    self._json({"version": me.version, "reason_codes": {}})
                elif self.path == "/api/jobs":
                    self._json([{"status": "running"}] if me.busy else [{"status": "done"}])

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                if self.path == "/api/update/restart":
                    me.restarts += 1
                    if me.supervised:
                        me.version = __version__  # the supervisor started the new code
                    self._json({"restarting": me.supervised})

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.mark.parametrize("busy, supervised, expect", [(False, True, True), (True, True, False), (False, False, False)])
def test_launcher_restarts_an_outdated_idle_server(busy, supervised, expect):
    old = _OldServer("1.2.7", busy=busy, supervised=supervised)
    try:
        assert cli._restart_if_outdated(old.port, "1.2.7", wait=5) is expect
        assert old.restarts == (0 if busy else 1)
    finally:
        old.stop()


def test_launcher_leaves_a_current_server_alone():
    cur = _OldServer(__version__)
    try:
        assert cli._restart_if_outdated(cur.port, __version__, wait=1) is False
        assert cur.restarts == 0
    finally:
        cur.stop()
