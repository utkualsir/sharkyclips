"""1.2.8 "Connect with Google": the built-in (shared) client, the one-shot loopback listener on a
random port, and every way a sign-in can end (allow, cancel on Google, cancel in the app,
no channel, several channels, revoked later, timeout) against the fake Google server."""

from __future__ import annotations

import json
import socket
import time
import urllib.parse

import pytest
import requests

from fake_youtube import FakeYouTube
from sharkyclips import config, welcome, youtube, ytconnect
from sharkyclips.errors import SharkyClipsError

SHARED_ID = "777-shared.apps.googleusercontent.com"
FILES = ("token.enc", "token.json", "client.json", "quota.json", "sessions.json", "locked.json",
         "unlocked.json", "playlists.json", "signed_out.json")


def _clean() -> None:
    for name in FILES:
        (youtube.folder() / name).unlink(missing_ok=True)


@pytest.fixture
def google(monkeypatch, tmp_path):
    """The fake Google server and a built-in client; nothing connected yet."""
    fake = FakeYouTube()
    monkeypatch.setenv("SHARKYCLIPS_YT_ENDPOINT", fake.start())
    shared = tmp_path / "google_client.json"
    shared.write_text(json.dumps({"client_id": SHARED_ID, "client_secret": "GOCSPX-public", "project_id": "sharkyclips",
                                  "verification": "unverified", "user_cap": 100}), encoding="utf-8")
    monkeypatch.setenv("SHARKYCLIPS_SHARED_CLIENT", str(shared))
    old_lang = config.get("ui_language")
    config.update(ui_language="en")
    _clean()
    yield fake
    ytconnect.cancel()
    fake.stop()
    _clean()
    config.update(ui_language=old_lang or "en")


def _wait_status(flow_id: str, timeout: float = 10) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        st = ytconnect.get(flow_id)
        if st["status"] != "waiting":
            return st
        time.sleep(0.02)
    raise AssertionError("the sign-in never finished")


def _port_closed(port: int, timeout: float = 5) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1).close()
        except OSError:
            return True
        time.sleep(0.1)
    return False


def _browser(url: str) -> requests.Response:
    """What the system browser does: open Google's page, follow the redirect to our listener."""
    res = requests.get(url, timeout=10)
    res.encoding = "utf-8"
    return res


def test_shared_client_is_the_default_and_signs_in_on_a_random_port(google):
    st = youtube.status()
    assert st["mode"] == "shared" and st["ready"] and not st["client"] and not st["connected"]
    assert st["shared"] == {"available": True, "verification": "unverified", "user_cap": 100,
                            "project_id": "sharkyclips"}
    f1 = ytconnect.start()
    assert f1["opened"] is False  # SHARKYCLIPS_NO_BROWSER in tests
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(f1["url"]).query))
    assert q["client_id"] == SHARED_ID and q["redirect_uri"] == f"http://127.0.0.1:{f1['port']}/"
    assert q["code_challenge_method"] == "S256" and "select_account" in q["prompt"] and "consent" in q["prompt"]
    page = _browser(f1["url"])
    assert page.status_code == 200 and "Connected!" in page.text and "Fake Channel" in page.text
    assert "window.close" in page.text
    flow = _wait_status(f1["id"])
    assert flow["status"] == "ok"
    st = youtube.status()
    assert st["connected"] and st["channel"]["title"] == "Fake Channel" and st["mode"] == "shared"
    assert youtube._token()["client_id"] == SHARED_ID
    assert _port_closed(f1["port"])  # the listener is gone after one sign-in
    # a refresh uses the client the token was made with
    youtube._expire_access()
    assert youtube.access_token()
    assert google.refreshes == 1


def test_two_sign_ins_use_different_ports_and_the_old_one_stops(google):
    a = ytconnect.start()
    b = ytconnect.start()
    assert a["port"] != b["port"]
    assert ytconnect.get(a["id"])["status"] == "cancelled" and not youtube.is_pending(a["id"])
    assert ytconnect.get(b["id"])["status"] == "waiting"


def test_cancel_on_googles_screen(google):
    google.deny_auth = True
    f = ytconnect.start()
    page = _browser(f["url"])
    assert "Connection cancelled" in page.text and "window.close" not in page.text
    st = _wait_status(f["id"])
    assert st["status"] == "cancelled" and st["reason"] == "google"
    assert not youtube.connected()


def test_cancel_in_the_app_closes_the_listener(google):
    f = ytconnect.start()
    ytconnect.cancel(f["id"])
    assert ytconnect.get(f["id"])["status"] == "cancelled"
    assert _port_closed(f["port"])


def test_a_slow_sign_in_expires(google, monkeypatch):
    monkeypatch.setattr(ytconnect, "TIMEOUT", 0.2)
    f = ytconnect.start()
    st = _wait_status(f["id"], 5)
    assert st["status"] == "expired" and not youtube.is_pending(f["id"])


def test_wrong_state_or_path_is_ignored(google):
    f = ytconnect.start()
    base = f"http://127.0.0.1:{f['port']}"
    assert requests.get(f"{base}/?code=x&state=forged", timeout=5).status_code == 404
    assert requests.get(f"{base}/favicon.ico", timeout=5).status_code == 404
    assert ytconnect.get(f["id"])["status"] == "waiting"


def test_account_without_a_channel_then_check_again(google):
    google.channel_count = 0
    f = ytconnect.start()
    page = _browser(f["url"])
    assert "no YouTube channel yet" in page.text and youtube.CREATE_CHANNEL_URL in page.text
    assert _wait_status(f["id"])["status"] == "no_channel"
    st = youtube.status()
    assert st["connected"] and st["no_channel"] and st["channel"] is None
    google.channel_count = 1  # the user made a channel on youtube.com
    st = youtube.recheck_channel()
    assert not st["no_channel"] and st["channel"]["title"] == "Fake Channel"


def test_several_channels_let_the_user_pick(google):
    google.channel_count = 2
    f = ytconnect.start()
    _browser(f["url"])
    assert _wait_status(f["id"])["status"] == "choose_channel"
    st = youtube.status()
    assert [c["title"] for c in st["channels"]] == ["Fake Channel", "Second Channel"]
    st = youtube.select_channel("UCfake2")
    assert st["channel"]["title"] == "Second Channel"
    with pytest.raises(SharkyClipsError):
        youtube.select_channel("UCnope")


def test_revoked_access_shows_a_reconnect_banner_until_reconnected(google):
    f = ytconnect.start()
    _browser(f["url"])
    _wait_status(f["id"])
    google.revoke_refresh = True  # the user removed SharkyClips in their Google account
    youtube._expire_access()
    with pytest.raises(SharkyClipsError) as e:
        youtube.access_token()
    assert e.value.reason == "signed_out"
    st = youtube.status()
    assert not st["connected"] and st["signed_out"]["channel"]["title"] == "Fake Channel"
    assert welcome.app_state()["youtube_signed_out"]["reason"] == "invalid_grant"
    google.revoke_refresh = False
    f = ytconnect.start()  # one click: Reconnect
    _browser(f["url"])
    assert _wait_status(f["id"])["status"] == "ok"
    assert youtube.status()["signed_out"] is None and welcome.app_state()["youtube_signed_out"] is None


def test_disconnect_by_the_user_shows_no_banner(google):
    f = ytconnect.start()
    _browser(f["url"])
    _wait_status(f["id"])
    youtube.disconnect()
    assert youtube.status()["signed_out"] is None and google.revoked == 1


def test_result_page_speaks_the_ui_language(google):
    config.update(ui_language="tr")
    f = ytconnect.start()
    page = _browser(f["url"])
    assert "Bağlandı!" in page.text and 'lang="tr"' in page.text
    config.update(ui_language="ar")
    google.deny_auth = True
    f = ytconnect.start()
    page = _browser(f["url"])
    assert 'dir="rtl"' in page.text and "أُلغي الربط" in page.text


def test_own_client_wins_and_removing_it_goes_back_to_easy_mode(google):
    youtube.set_client({"installed": {"client_id": "9-own.apps.googleusercontent.com", "client_secret": "s",
                                      "project_id": "mine"}})
    assert youtube.status()["mode"] == "own"
    f = ytconnect.start()
    assert "9-own.apps" in f["url"]
    _browser(f["url"])
    _wait_status(f["id"])
    assert youtube._token()["client_id"] == "9-own.apps.googleusercontent.com"
    youtube.remove_client()
    st = youtube.status()
    assert st["mode"] == "shared" and not st["connected"] and st["signed_out"] is None


def test_no_client_at_all_explains(monkeypatch, tmp_path):
    monkeypatch.setenv("SHARKYCLIPS_SHARED_CLIENT", str(tmp_path / "missing.json"))
    _clean()
    st = youtube.status()
    assert st["mode"] is None and not st["ready"] and not st["shared"]["available"]
    with pytest.raises(SharkyClipsError) as e:
        ytconnect.start()
    assert "Advanced" in e.value.hint and e.value.reason == "no_client"


@pytest.mark.parametrize("text, reason", [
    ("", "empty"),
    ("AIzaSyB-something", "api_key"),
    ("123-abc.apps.googleusercontent.com", "id_only"),
    ("{not json", "not_json"),
    ("[1, 2]", "not_client"),
    ('{"type": "service_account", "client_email": "x@y"}', "service_account"),
    ('{"web": {"client_id": "1.apps.googleusercontent.com", "client_secret": "s"}}', "web_client"),
    ('{"installed": {"client_id": "nope"}}', "no_client_id"),
    ('{"installed": {"client_id": "1.apps.googleusercontent.com"}}', "no_secret"),
])
def test_client_json_problems_are_explained(text, reason):
    with pytest.raises(SharkyClipsError) as e:
        youtube.check_client_text(text)
    assert e.value.reason == reason and e.value.hint is not None or reason in ("not_client",)


def test_client_json_ok_with_bom_and_whitespace():
    c = youtube.check_client_text('﻿  {"installed": {"client_id": "1.apps.googleusercontent.com", '
                                  '"client_secret": "s", "project_id": "p"}}\n')
    assert c["project_id"] == "p"


def test_web_api_connect_poll_cancel_and_check(google):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    c = TestClient(app)
    r = c.post("/api/youtube/connect", json={"open": False}).json()
    assert r["id"] and r["url"].startswith(google.base)
    assert c.get(f"/api/youtube/connect/{r['id']}").json()["status"] == "waiting"
    _browser(r["url"])
    end = time.time() + 10
    while (s := c.get(f"/api/youtube/connect/{r['id']}").json())["status"] == "waiting" and time.time() < end:
        time.sleep(0.02)
    assert s["status"] == "ok" and s["youtube"]["channel"]["title"] == "Fake Channel"
    r2 = c.post("/api/youtube/connect", json={"open": False}).json()
    assert c.delete(f"/api/youtube/connect/{r2['id']}").json()["status"] == "cancelled"
    bad = c.post("/api/youtube/client/check", content=b"AIzaKEY").json()
    assert bad == {"ok": False, "error": bad["error"], "hint": bad["hint"], "reason": "api_key"}
    good = c.post("/api/youtube/client/check", content=json.dumps(
        {"installed": {"client_id": "1.apps.googleusercontent.com", "client_secret": "s", "project_id": "p"}}).encode()).json()
    assert good["ok"] and good["project_id"] == "p"
    assert c.get("/api/youtube/connect/unknown").status_code >= 400
