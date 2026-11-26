"""1.2.70 assisted upload: SharkyClips fills in TikTok Studio / instagram.com in the user's own
browser (a plain browser + the SharkyClips Helper extension, nothing attached) and STOPS; the
user clicks Post. Without a browser: modes, browser choice, the extension's files and key, the
claim rules, the whole job driven by fake extension reports (ready -> posted, tab closed -> "did
you post it?", page changed -> by hand, batch one after another with a pause, setup guide, skip,
planned time). With Microsoft Edge (headless, the real extension): the fake TikTok Studio and the
fake Instagram dialog are filled in, a "person" clicks Post, nothing is ever posted without them."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

from sharkyclips import assist, config, easy as E, platforms as PF
from test_multipost import _client, _rec, _rendered
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures

EXT = Path(assist.__file__).with_name("assist_ext")


def _key() -> dict:
    return {"X-SharkyClips-Assist": assist.token()}


def _notices(kind: str) -> list[dict]:
    return [n for n in E.notices(0)["items"] if n["kind"] == kind]


@pytest.fixture
def fake_browser(monkeypatch, tmp_path, cfg):  # noqa: F811
    """'Edge' is installed (any existing file), opening a page is recorded, never a real browser."""
    from sharkyclips.web import assist_api as AA

    monkeypatch.setenv("SHARKYCLIPS_ASSIST_BROWSER", f"edge={sys.executable}")
    monkeypatch.delenv("SHARKYCLIPS_ASSIST_DEFAULT", raising=False)
    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(tmp_path / "dl"))
    PF._assist_cache.update(at=0.0)
    opened: list[str] = []
    monkeypatch.setattr(assist, "open_url", lambda url, key=None: opened.append(url) or
                        {"browser": key or "edge", "name": "Microsoft Edge", "fills": True})
    monkeypatch.setattr(assist, "pause_s", lambda: 0)
    AA.reset_for_tests()
    assist.save_state(last_done={}, seen={})
    for p in ("tiktok", "reels"):
        PF.forget(p)
    config.update(platform_modes={}, publish_targets=["tiktok"], assist_browser=None)
    _clean_projects()
    yield opened
    _wait(_idle, 60)
    AA.reset_for_tests()
    config.update(platform_modes={}, publish_targets=None, assist_browser=None)
    PF._assist_cache.update(at=0.0)
    _clean_projects()


def _setup(name: str, *cids: str):
    project = _project(name, max(2, len(cids)))
    for c in cids or ("c01",):
        _rendered(project, c)
    return project


def _task(project, cid: str, platform: str = "tiktok", timeout: float = 20.0) -> dict:
    from sharkyclips.web import assist_api as AA

    end = time.time() + timeout
    while time.time() < end:
        t = AA.find(project.id, cid, platform)
        if t and t["state"] == "opening":
            return t
        time.sleep(0.05)
    raise AssertionError(f"no opening task: {AA.find(project.id, cid, platform)}")


def _report(c, t: dict, event: str, **kw) -> dict:
    r = c.post("/api/assist/ext/report", headers=_key(), json={"id": t["id"], "tab": 7, "event": event, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _until(pred, timeout: float = 20.0) -> None:
    end = time.time() + timeout
    while not pred():
        if time.time() > end:
            raise AssertionError("timed out")
        time.sleep(0.05)


# ===================================================================== modes + browsers


def test_tiktok_is_assisted_by_default_and_manual_stays_an_option(fake_browser):
    assert PF.mode("tiktok") == "assist"
    assert PF.mode("reels") == "semi"  # Instagram: by hand unless switched on
    assert PF.set_mode("reels", "assist")["mode"] == "assist"
    PF.set_mode("tiktok", "semi")
    assert PF.mode("tiktok") == "semi"
    config.update(platform_modes={"tiktok": "semi"}, tiktok_assist_default_v1=None)
    from sharkyclips.web import history_api

    assert history_api.migrate_tiktok_assist() is True  # 1.2.68's "by hand" default moves once
    assert PF.mode("tiktok") == "assist"
    PF.set_mode("tiktok", "semi")
    assert history_api.migrate_tiktok_assist() is False and PF.mode("tiktok") == "semi"  # your choice stays
    config.update(tiktok_assist_default_v1=None)


def test_without_a_browser_that_can_be_filled_in_it_is_by_hand(monkeypatch, cfg):  # noqa: F811
    monkeypatch.delenv("SHARKYCLIPS_ASSIST_DEFAULT", raising=False)
    monkeypatch.setenv("SHARKYCLIPS_ASSIST_BROWSER", f"firefox={sys.executable}")
    PF._assist_cache.update(at=0.0)
    config.update(platform_modes={})
    try:
        assert PF.mode("tiktok") == "semi"
        with pytest.raises(Exception, match="Chrome"):
            PF.set_mode("tiktok", "assist")
    finally:
        PF._assist_cache.update(at=0.0)


def test_the_users_default_browser_is_used_unless_another_is_picked(monkeypatch, cfg):  # noqa: F811
    monkeypatch.delenv("SHARKYCLIPS_ASSIST_BROWSER", raising=False)
    monkeypatch.setattr(assist, "installed", lambda: {"chrome": "c.exe", "edge": "e.exe", "operagx": "o.exe",
                                                      "firefox": "f.exe"})
    monkeypatch.setattr(assist, "default_browser", lambda: "operagx")
    config.update(assist_browser=None)
    assert assist.pick() == ("operagx", "o.exe")
    config.update(assist_browser="edge")
    assert assist.pick() == ("edge", "e.exe")
    monkeypatch.setattr(assist, "default_browser", lambda: "firefox")
    config.update(assist_browser="auto")
    assert assist.pick() == ("firefox", "f.exe") and not assist.can_fill("firefox")
    v = assist.browsers_view()
    assert [b["key"] for b in v["installed"]] == ["chrome", "edge", "operagx", "firefox"]
    assert v["using"] == "firefox" and v["fills"] is False
    config.update(assist_browser=None)


def test_the_browser_starts_plain_with_the_extension_and_never_a_debugging_port(monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_ASSIST_CMD", raising=False)
    cmd = assist.command("edge", "msedge.exe", "https://www.tiktok.com/tiktokstudio/upload")
    joined = " ".join(cmd)
    assert f"--user-data-dir={assist.profile_dir('edge')}" in cmd and f"--load-extension={assist.ext_dir()}" in cmd
    assert cmd[-1] == "https://www.tiktok.com/tiktokstudio/upload"
    for flag in ("--remote-debugging", "--enable-automation", "--headless", "AutomationControlled", "--disable-blink-features"):
        assert flag not in joined
    from sharkyclips import tiktok_browser as TB

    assert assist.profile_dir("chrome") == TB.profile_dir()  # Chrome keeps the earlier TikTok login
    assert assist.profile_dir("edge") != assist.profile_dir("chrome")
    ff = assist.command("firefox", "firefox.exe", "https://x")
    assert ff[:3] == ["firefox.exe", "-profile", str(assist.profile_dir("firefox"))]


def test_the_extension_files_carry_this_installs_key_and_never_click_post():
    d = assist.write_extension("http://127.0.0.1:8123")
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert m["manifest_version"] == 3 and m["name"] == assist.EXT_NAME
    assert set(m["permissions"]) == {"storage"} and "debugger" not in json.dumps(m)
    assert m["host_permissions"] == ["http://127.0.0.1/*", "http://localhost/*"]
    scripts = {tuple(cs["js"]): cs["matches"] for cs in m["content_scripts"]}
    assert scripts[("common.js", "tiktok.js")][0] == "https://www.tiktok.com/*"
    assert scripts[("common.js", "instagram.js")][0] == "https://www.instagram.com/*"
    conf = (d / "config.js").read_text(encoding="utf-8")
    assert assist.token() in conf and "http://127.0.0.1:8123" in conf
    for name in assist.EXT_FILES:
        assert (d / name).read_text(encoding="utf-8") == (EXT / name).read_text(encoding="utf-8")
    # the rule, checked in the code: the Post / Share button is outlined and watched, never clicked
    tt = (EXT / "tiktok.js").read_text(encoding="utf-8")
    for line in tt.splitlines():
        if "POST_BUTTON" in line:
            assert "press(" not in line and ".click(" not in line, line
    assert not re.search(r"press\(\s*btn\s*\)|btn\.click\(", tt)
    ig = (EXT / "instagram.js").read_text(encoding="utf-8")
    watch = ig[ig.index("async function watch"):ig.index("async function fill")]
    assert "press(" not in watch and ".click(" not in watch
    assert "SCX.press(share" not in ig


def test_the_extensions_door_needs_its_own_key(fake_browser):
    c = _client()
    assert c.get("/api/assist/ext/hello").status_code == 403
    assert c.get("/api/assist/ext/hello", headers={"X-SharkyClips-Assist": "wrong-key-" * 4}).status_code == 403
    ext = {**_key(), "Origin": "chrome-extension://abcdefghijklmnop", "Sec-Fetch-Site": "cross-site"}
    r = c.get("/api/assist/ext/hello", headers=ext)
    assert r.status_code == 200 and r.json()["app"] == "sharkyclips"
    assert c.post("/api/assist/ext/report", headers=ext, json={"event": "hello"}).status_code == 200
    # the key opens only the extension's door, nothing else
    assert c.get("/api/assist", headers=ext).status_code == 403
    assert c.put("/api/assist/settings", headers=ext, json={"browser": "edge"}).status_code == 403
    assert assist.token() != __import__("sharkyclips.web.security", fromlist=["token"]).token()


# ===================================================================== the job, driven by fake reports


def test_ready_then_your_click_then_shared_with_the_link(fake_browser):
    project = _setup("pub-assist-ok")
    c = _client()
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    assert r.status_code == 200, r.text
    assert r.json()["results"]["tiktok"]["mode"] == "assist"
    t = _task(project, "c01")
    assert fake_browser == ["https://www.tiktok.com/tiktokstudio/upload"]
    rec = _rec(project, "c01", "tiktok")
    assert rec["mode"] == "assist" and rec["file"].endswith("- TikTok.mp4") and Path(rec["file"]).is_file()
    # a TikTok tab you browse yourself never takes the post; the upload page does
    other = c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 3,
                                                                 "url": "https://www.tiktok.com/foryou"}).json()
    assert other["task"] is None
    got = c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 7,
                                                               "url": "https://www.tiktok.com/tiktokstudio/upload"}).json()["task"]
    assert got["id"] == t["id"] and got["state"] == "opening" and "#" in got["text"]
    assert got["strings"]["ready"] == "Everything is ready. Check and click Post." and "file" not in got
    second = c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 8,
                                                                  "url": "https://www.tiktok.com/tiktokstudio/upload"}).json()
    assert second["task"] is None  # one tab per post
    _report(c, t, "claimed")
    _report(c, t, "step", step="uploading")
    f = c.get(f"/api/assist/ext/file/{t['id']}", headers=_key())
    assert f.status_code == 200 and f.content == Path(rec["file"]).read_bytes()
    assert c.get(f"/api/assist/ext/file/{t['id']}").status_code == 403
    _report(c, t, "step", step="filling")
    before = len(_notices("assist_ready"))
    _report(c, t, "ready", notes=[])
    _until(lambda: (_rec(project, "c01", "tiktok").get("assist") or {}).get("state") == "ready")
    assert len(_notices("assist_ready")) == before + 1
    card = c.get(f"/api/share/{project.id}").json()["clips"][0]
    assert card["posts"]["tiktok"]["assist"]["state"] == "ready"
    assert any(x["state"] == "ready" for x in c.get("/api/assist").json()["tasks"])
    # "Show the browser": the page is asked to come to the front at its next ping
    c.post(f"/api/assist/task/{t['id']}/show")
    assert _report(c, t, "ping").get("focus") is True
    _report(c, t, "post_clicked")
    _report(c, t, "posted", url="https://www.tiktok.com/@me/video/7311111111111111111")
    _wait(_idle, 30)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "published" and rec["url"].endswith("/video/7311111111111111111")
    assert rec["via"] == "assist" and not rec.get("manual")
    assert any(n["title"].startswith("Shared to TikTok") for n in _notices("shared"))
    # never twice
    again = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"}).json()
    assert again["results"]["tiktok"]["skipped"] and len(fake_browser) == 1


def test_closing_the_tab_after_it_was_ready_asks_did_you_post_it(fake_browser):
    project = _setup("pub-assist-ask", "c01", "c02")
    c = _client()
    for cid in ("c01", "c02"):
        c.post(f"/api/publish/{project.id}/{cid}", json={"platforms": ["tiktok"], "when": "now"})
        t = _task(project, cid)
        c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 7,
                                                             "url": "https://www.tiktok.com/tiktokstudio/upload"})
        _report(c, t, "claimed")
        _report(c, t, "ready")
        c.post("/api/assist/ext/report", headers=_key(), json={"tab": 7, "event": "tab_closed"})  # bg.js sends only the tab
        _until(lambda: _rec(project, cid, "tiktok").get("status") == "ready" and
               (_rec(project, cid, "tiktok").get("assist") or {}).get("state") == "confirm")
        _wait(_idle, 30)
        r = c.post(f"/api/assist/task/{t['id']}/{'posted' if cid == 'c01' else 'not_posted'}")
        assert r.status_code == 200, r.text
    assert _rec(project, "c01", "tiktok")["status"] == "published" and _rec(project, "c01", "tiktok")["manual"]
    assert _rec(project, "c02", "tiktok")["status"] == "idle"
    assert _notices("assist_confirm")


def test_a_changed_page_falls_back_to_by_hand_with_the_reason_and_retry_tries_again(fake_browser):
    project = _setup("pub-assist-ui")
    c = _client()
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    t = _task(project, "c01")
    c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 7,
                                                         "url": "https://www.tiktok.com/tiktokstudio/upload"})
    _report(c, t, "claimed")
    _report(c, t, "failed", reason="ui_changed", step="caption", detail="no caption box")
    _wait(_idle, 30)
    rec = _rec(project, "c01", "tiktok")
    assert rec["mode"] == "semi" and rec["status"] == "ready" and rec["assist_fallback"]
    assert rec["fallback"]["reason"] == "ui_changed" and "looked different" in rec["fallback"]["message"]
    assert Path(rec["file"]).is_file() and Path(rec["file"][:-4] + ".txt").is_file()  # the by-hand steps are ready
    h = c.get(f"/api/publish/{project.id}/c01/handoff").json()["platforms"]["tiktok"]
    assert h["status"] == "ready" and h["upload_page"]
    # Retry: assisted again (a fresh task, the page opens again)
    _rec_failed = PF.record(project, "c01", "tiktok", status="failed")
    assert _rec_failed["status"] == "failed"
    r = c.post(f"/api/publish/{project.id}/c01/retry/tiktok")
    assert r.status_code == 200, r.text
    t2 = _task(project, "c01")
    assert t2["id"] != t["id"] and _rec(project, "c01", "tiktok")["mode"] == "assist" and len(fake_browser) == 2
    c.post(f"/api/assist/task/{t2['id']}/skip")
    _wait(_idle, 30)
    assert _rec(project, "c01", "tiktok")["status"] == "cancelled"


def test_a_batch_opens_the_next_clip_only_after_the_previous_one_is_posted(fake_browser, monkeypatch):
    from sharkyclips.web import assist_api as AA

    monkeypatch.setattr(assist, "pause_s", lambda: 1)
    project = _setup("pub-assist-batch", "c01", "c02")
    c = _client()
    r = c.post(f"/api/share/{project.id}/publish", json={"clips": ["c01", "c02"], "platforms": ["tiktok"]})
    assert r.status_code == 200, r.text
    t1 = _task(project, "c01")
    time.sleep(1.0)
    assert len(fake_browser) == 1 and AA.find(project.id, "c02", "tiktok") is None  # waits for c01
    c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 7,
                                                         "url": "https://www.tiktok.com/tiktokstudio/upload"})
    _report(c, t1, "ready")
    _report(c, t1, "posted", url=None)
    _until(lambda: (AA.find(project.id, "c02", "tiktok") or {}).get("state") == "pause", 10)  # the short pause
    t2 = _task(project, "c02")
    assert len(fake_browser) == 2
    assert _rec(project, "c01", "tiktok")["status"] == "published"
    c.post(f"/api/assist/task/{t2['id']}/manual")  # "post this one by hand instead"
    _wait(_idle, 30)
    rec = _rec(project, "c02", "tiktok")
    assert rec["mode"] == "semi" and rec["status"] == "ready" and rec["fallback"]["reason"] == "by_choice"


def test_no_answer_from_the_page_shows_the_one_time_extension_guide(fake_browser, monkeypatch):
    from sharkyclips.web import assist_api as AA

    monkeypatch.setattr(AA, "EXT_WAIT_S", 0.3)
    project = _setup("pub-assist-setup")
    c = _client()
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    t = _task(project, "c01")
    _until(lambda: AA.find(project.id, "c01", "tiktok").get("setup") is True, 10)
    v = c.get("/api/assist").json()
    row = next(x for x in v["tasks"] if x["id"] == t["id"])
    assert row["setup"] and v["ext"]["dir"] == str(assist.ext_dir()) and v["ext"]["page"] == "edge://extensions"
    # the extension shows up (Load unpacked done): the page takes the post, the guide goes away
    c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 7,
                                                         "url": "https://www.tiktok.com/tiktokstudio/upload"})
    _until(lambda: AA.find(project.id, "c01", "tiktok").get("setup") is False, 5)
    c.post(f"/api/assist/task/{t['id']}/skip")


def test_a_login_or_captcha_waits_for_you(fake_browser):
    project = _setup("pub-assist-login")
    c = _client()
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    t = _task(project, "c01")
    c.post("/api/assist/ext/task", headers=_key(), json={"platform": "tiktok", "tab": 7,
                                                         "url": "https://www.tiktok.com/login?redirect=upload"})
    _report(c, t, "claimed")
    _report(c, t, "step", step="uploading")
    _report(c, t, "captcha", reason="captcha")
    _until(lambda: (_rec(project, "c01", "tiktok").get("assist") or {}).get("state") == "captcha")
    assert _notices("assist_action")
    time.sleep(1.2)
    assert _rec(project, "c01", "tiktok")["status"] != "ready"  # still waiting, no fallback
    _report(c, t, "resume")
    _until(lambda: (_rec(project, "c01", "tiktok").get("assist") or {}).get("state") == "uploading")
    c.post(f"/api/assist/task/{t['id']}/skip")


def test_a_planned_assisted_post_opens_at_its_time(fake_browser):
    from datetime import timedelta

    from sharkyclips.web import multipost as M

    project = _setup("pub-assist-plan")
    c = _client()
    when = (M._now() + timedelta(hours=3)).isoformat()
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": when}).json()
    assert r["results"]["tiktok"]["status"] == "scheduled" and not fake_browser
    M.tick(M._now() + timedelta(hours=1))
    assert not fake_browser
    M.tick(M._now() + timedelta(hours=3, minutes=1))
    t = _task(project, "c01")
    assert fake_browser and t["state"] == "opening"
    c.post(f"/api/assist/task/{t['id']}/skip")


def test_firefox_opens_the_page_and_goes_by_hand_with_a_clear_note(fake_browser, monkeypatch):
    project = _setup("pub-assist-ff")
    c = _client()
    assert PF.mode("tiktok") == "assist"  # chosen while a fillable browser was the one in use
    monkeypatch.setattr(assist, "pick", lambda: ("firefox", "firefox.exe"))
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    _wait(_idle, 30)
    rec = _rec(project, "c01", "tiktok")
    assert fake_browser == ["https://www.tiktok.com/tiktokstudio/upload"]  # opened in Firefox anyway
    assert rec["mode"] == "semi" and rec["fallback"]["reason"] == "firefox" and "Firefox" in rec["fallback"]["message"]


# ===================================================================== the real extension in Edge


def _edge() -> str | None:
    for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.is_file():
                return str(p)
    return shutil.which("microsoft-edge") or shutil.which("msedge")


@pytest.fixture(scope="module")
def live():
    """The real app on a real port (no start-up tasks), the fake TikTok Studio and Instagram."""
    edge = _edge()
    if not edge:
        pytest.skip("Microsoft Edge isn't installed here")
    import uvicorn

    from fake_instagram import FakeInstagram
    from fake_tiktok_studio import FakeStudio
    from sharkyclips.web.app import app

    studio, ig = FakeStudio().start(), FakeInstagram().start()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="off", log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    end = time.time() + 15
    while not server.started and time.time() < end:
        time.sleep(0.05)
    env = {"SHARKYCLIPS_TT_STUDIO": studio.url, "SHARKYCLIPS_IG_WEB": ig.url,
           "SHARKYCLIPS_ASSIST_TEST_MATCHES": studio.url, "SHARKYCLIPS_ASSIST_BROWSER": f"edge={edge}",
           "SHARKYCLIPS_ASSIST_CMD": json.dumps([edge, "--headless=new", "--user-data-dir={profile}",
                                                 "--load-extension={ext}", "--no-first-run",
                                                 "--no-default-browser-check", "--window-size=1280,900", "{url}"])}
    old = {k: os.environ.get(k) for k in [*env, "SHARKYCLIPS_ASSIST_DEFAULT"]}
    os.environ.update(env)
    os.environ.pop("SHARKYCLIPS_ASSIST_DEFAULT", None)
    assist.note_base(f"http://127.0.0.1:{port}")
    # the fake Instagram runs on another port: the content script matches it too
    yield {"studio": studio, "ig": ig, "port": port}
    _kill_browsers()
    server.should_exit = True
    th.join(10)
    studio.stop()
    ig.stop()
    for k, v in old.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _kill_browsers(marker: str | None = None) -> None:
    """Only the test's own Edge (its profile lives in a throwaway folder), with all its helper
    processes, and wait until they are gone. (Edge doesn't load a --load-extension extension again
    on a profile whose browser was killed, so every test starts with a fresh profile.)"""
    home = marker or str(config.config_dir())
    procs = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            if any(home in c for c in (p.info["cmdline"] or [])):
                procs.append(p)
        except Exception:  # noqa: BLE001
            pass
    for p in procs:
        try:
            p.kill()
        except Exception:  # noqa: BLE001
            pass
    psutil.wait_procs(procs, timeout=10)
    time.sleep(0.5)


@pytest.fixture
def real(live, monkeypatch, tmp_path, cfg):  # noqa: F811
    from sharkyclips.web import assist_api as AA

    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(tmp_path / "dl"))
    prof = tmp_path / "edge-profile"
    cmd = json.loads(os.environ["SHARKYCLIPS_ASSIST_CMD"])
    monkeypatch.setenv("SHARKYCLIPS_ASSIST_CMD", json.dumps([x.replace("{profile}", str(prof)) for x in cmd]))
    monkeypatch.setattr(assist, "pause_s", lambda: 0)
    PF._assist_cache.update(at=0.0)
    AA.reset_for_tests()
    s, ig = live["studio"], live["ig"]
    s.mode, s.draft, s.prompts, s.user_posts, s.user_login = "normal", False, True, False, False
    s.posts.clear()
    s.seed.clear()
    ig.posts.clear()
    ig.user_posts, ig.user_login, ig.logged_in = False, False, True
    for p in ("tiktok", "reels"):
        PF.forget(p)
    config.update(platform_modes={"tiktok": "assist", "reels": "assist"}, publish_targets=["tiktok"])
    _clean_projects()
    yield live
    _wait(_idle, 90)
    _kill_browsers(str(prof))
    AA.reset_for_tests()
    config.update(platform_modes={}, publish_targets=None)
    PF._assist_cache.update(at=0.0)
    _clean_projects()


def _state_is(project, cid, platform, states, timeout=60.0) -> dict:
    from sharkyclips.web import assist_api as AA

    end = time.time() + timeout
    while time.time() < end:
        t = AA.find(project.id, cid, platform)
        if t and t["state"] in states:
            return t
        time.sleep(0.2)
    raise AssertionError(f"state {AA.find(project.id, cid, platform)}")


def test_edge_fills_tiktok_studio_logs_in_once_and_waits_for_the_persons_click(real):
    s = real["studio"]
    s.user_login, s.user_posts = True, True  # the person logs in once, then checks and clicks Post
    project = _setup("pub-assist-edge")
    c = _client()
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    assert r.status_code == 200, r.text
    _wait(_idle, 300)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "published", rec.get("assist") or rec
    assert rec["url"] and "/video/" in rec["url"] and rec["via"] == "assist"
    assert len(s.posts) == 1
    post = s.posts[0]
    flat = " ".join(post["caption"].split())
    assert "#" in flat and flat.split()[-1].startswith("#")  # hashtags last
    assert post["visibility"] == "Herkes" and post["schedule"] == "post_now" and post["picked"] == 0
    assert post["prompts"] == ["checks", "tour"] and not post["checks_on"]  # TikTok's hints closed, settings kept
    assert assist.seen("edge") > 0


def test_edge_never_posts_without_the_person(real):
    s = real["studio"]
    s.user_login = True
    project = _setup("pub-assist-wait")
    c = _client()
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    t = _state_is(project, "c01", "tiktok", ("ready",), 120)
    time.sleep(4)
    assert s.posts == [] and t["state"] == "ready"  # filled in, and nobody clicked: nothing went out
    c.post(f"/api/assist/task/{t['id']}/skip")
    _wait(_idle, 30)
    assert s.posts == [] and _rec(project, "c01", "tiktok")["status"] == "cancelled"


def test_edge_falls_back_to_by_hand_when_tiktok_studio_looks_different(real):
    s = real["studio"]
    s.user_login, s.mode = True, "uichanged"
    project = _setup("pub-assist-changed")
    c = _client()
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    _wait(_idle, 300)
    rec = _rec(project, "c01", "tiktok")
    assert rec["mode"] == "semi" and rec["status"] == "ready" and rec["fallback"]["reason"] == "ui_changed"
    assert s.posts == []


def test_edge_fills_the_instagram_reel_dialog_and_the_person_shares(real):
    ig = real["ig"]
    ig.user_posts = True
    config.update(publish_targets=["reels"])
    project = _setup("pub-assist-ig")
    c = _client()
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["reels"], "when": "now"})
    assert r.status_code == 200, r.text
    assert r.json()["results"]["reels"]["mode"] == "assist"
    _wait(_idle, 300)
    rec = _rec(project, "c01", "reels")
    assert rec["status"] == "published", rec.get("assist") or rec
    assert len(ig.posts) == 1 and ig.posts[0]["crop"] == "original" and ig.posts[0]["name"].endswith(".mp4")
    assert " ".join(ig.posts[0]["caption"].split()) == " ".join(rec["caption"].split())
