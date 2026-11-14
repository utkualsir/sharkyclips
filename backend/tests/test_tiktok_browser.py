"""1.2.42: automatic TikTok through TikTok Studio in SharkyClips' own browser profile, tested
against a local fake TikTok Studio (fake_tiktok_studio.py: same data-e2e structure, Turkish texts):
upload, caption (hashtags last, never Enter after a hashtag), schedule (date + time pickers),
visibility, AI label, success read-back, and the stops: CAPTCHA, upload failure, UI changed,
login wall. Then the one Publish button end to end (browser lane, daily limit, fallback to by hand)
and the reconcile of overdue publish-queue entries."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from fake_tiktok_studio import FakeStudio, ahead  # noqa: E402
from sharkyclips import config, platforms as PF, tiktok_browser as TB  # noqa: E402
from test_publishing import cfg  # noqa: E402,F401 - fixture

ENV = {"SHARKYCLIPS_TT_HEADLESS": "1", "SHARKYCLIPS_TT_PACE": "0.01,0.03", "SHARKYCLIPS_TT_TYPE_MS": "0,2",
       "SHARKYCLIPS_TT_TIMEOUT_SCALE": "0.15"}

CAPTION = ("Akali'yle kaçırılan combo suçlu kanka mıydı?\n\nTakım savaşında her şey ters gitti.\n\n"
           "#lol #leagueoflegends #oyun #shorts\n\nYouTube: https://youtube.com/@utkualsir · Instagram @utkualsirr48")


@pytest.fixture(scope="module")
def studio():
    s = FakeStudio().start()
    env = {**ENV, "SHARKYCLIPS_TT_STUDIO": s.url}
    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        with TB._Session() as sess:  # logs the fake account in (a cookie in the profile)
            sess.page.goto(s.url + "/__autologin")
            assert sess.session_cookie()
    except TB.Blocked as exc:  # no Chrome / Edge / Chromium on this machine
        s.stop()
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        pytest.skip(f"no browser: {exc.message} {exc.hint}")
    TB._save(logged_in=True, username="fakeuser", login_at=time.time(), checked_at=time.time(), blocked=None)
    yield s
    s.stop()
    for k, v in old.items():
        os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@pytest.fixture
def fresh(studio):
    studio.mode = "normal"
    studio.posts.clear()
    studio.seed.clear()
    TB._save(logged_in=True, blocked=None, username="fakeuser")
    yield studio
    studio.mode = "normal"
    TB._save(logged_in=True, blocked=None)


@pytest.fixture
def video(tmp_path) -> Path:
    f = tmp_path / "klip-dosya-adi.mp4"
    f.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4000)
    return f


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def test_split_caption_puts_the_hashtags_last():
    body, tags = TB.split_caption(CAPTION)
    assert tags == ["#lol", "#leagueoflegends", "#oyun", "#shorts"]
    assert body.endswith("Instagram @utkualsirr48") and "#" not in body  # socials before the hashtags
    assert TB.expected_text(body, tags).endswith("#oyun #shorts")


def test_window_and_rounding():
    now = datetime.now(timezone.utc)
    assert not TB.in_window(now + timedelta(minutes=10), now)
    assert TB.in_window(now + timedelta(days=2), now)
    assert not TB.in_window(now + timedelta(days=11), now)
    r = TB.round_slot(datetime(2026, 11, 16, 17, 58, tzinfo=timezone.utc))
    assert r.minute % 5 == 0 and r >= datetime(2026, 11, 16, 17, 58, tzinfo=timezone.utc)


def test_post_now_types_the_caption_and_reads_back_the_post(fresh, video, tmp_path):
    steps = []
    res = TB.post(video, CAPTION, title="Akali'yle kaçırılan combo suçlu kanka mıydı?",
                  shots_dir=tmp_path / "shots", on_step=lambda s, f: steps.append(s), on_submit=lambda: steps.append("SUBMIT"))
    assert res["status"] == "published" and res["confirmed"]
    assert res["url"] and "/video/" in res["url"] and res["username"] == "fakeuser"
    p = fresh.posts[-1]
    body, tags = TB.split_caption(CAPTION)
    assert _flat(p["caption"]) == TB.expected_text(body, tags)  # the filename prefill is gone
    assert "klip-dosya-adi" not in p["caption"]
    assert p["picked"] == 0  # no hashtag / mention suggestion was ever picked by an Enter
    assert p["schedule"] == "post_now" and p["visibility"] == "Herkes"
    assert p["aigc"] is False and p["disclose"] is False and p["comment"] is True
    assert steps.index("SUBMIT") > steps.index("caption")


def test_schedule_two_days_ahead_with_the_ai_label(fresh, video):
    when = ahead(2, 18, 0)
    res = TB.post(video, CAPTION, when=when, ai_label=True, title="Akali'yle kaçırılan combo suçlu kanka mıydı?")
    assert res["status"] == "scheduled" and res["confirmed"] and res["url"] is None
    assert "(GMT" in res["row"]  # read back from the content list
    p = fresh.posts[-1]
    assert p["schedule"] == "schedule" and p["date"] == when.strftime("%Y-%m-%d") and p["time"] == "18:00"
    assert p["aigc"] is True  # dubbed clip: AI-generated switch on


def test_time_is_rounded_to_tiktoks_5_minutes(fresh, video):
    when = ahead(3, 9, 7)
    TB.post(video, "Kısa başlık burada\n\n#test", when=when, title="Kısa başlık burada")
    assert fresh.posts[-1]["time"] == "09:10"


def test_outside_tiktoks_window_nothing_is_posted(fresh, video):
    with pytest.raises(TB.ScheduleUnavailable):
        TB.post(video, CAPTION, when=ahead(12, 18, 0), title="x")
    assert fresh.posts == []


def test_captcha_stops_at_once_with_a_screenshot(fresh, video, tmp_path):
    fresh.mode = "captcha"
    with pytest.raises(TB.Blocked) as e:
        TB.post(video, CAPTION, shots_dir=tmp_path / "shots", tag="c04")
    assert e.value.reason == "captcha" and not e.value.submitted
    assert e.value.shot and Path(e.value.shot).is_file() and "c04" in Path(e.value.shot).name
    assert fresh.posts == []


def test_upload_failure_stops(fresh, video, tmp_path):
    fresh.mode = "uploadfail"
    with pytest.raises(TB.Blocked) as e:
        TB.post(video, CAPTION, shots_dir=tmp_path)
    assert e.value.reason == "upload_failed" and e.value.shot
    assert fresh.posts == []


def test_changed_ui_stops_instead_of_guessing(fresh, video, tmp_path):
    fresh.mode = "uichanged"
    with pytest.raises(TB.Blocked) as e:
        TB.post(video, CAPTION, shots_dir=tmp_path)
    assert e.value.reason == "ui_changed" and e.value.step == "caption"
    assert fresh.posts == []


def test_login_wall_stops_and_marks_signed_out(fresh, video):
    fresh.mode = "nologin"
    with pytest.raises(TB.Blocked) as e:
        TB.post(video, CAPTION)
    assert e.value.reason == "login"
    assert fresh.posts == []


# ---------------------------------------------------------------- 1.2.43: the plain-Chrome login


@pytest.fixture
def own_root(tmp_path, monkeypatch):
    """A browser folder of its own (the module's fake account stays logged in elsewhere)."""
    channel = TB._load().get("channel")
    monkeypatch.setattr(TB, "root", lambda: tmp_path / "browser")
    if channel:
        TB._save(channel=channel)
    return tmp_path / "browser"


def _fake_cmd(*extra: str) -> str:
    import json
    import sys

    exe = Path(sys.executable)
    if os.name == "nt" and exe.with_name("pythonw.exe").is_file():
        exe = exe.with_name("pythonw.exe")  # a GUI-less python: no console window for the fake "Chrome"
    return json.dumps([str(exe), str(Path(__file__).with_name("fake_login_browser.py")), *extra])


def _login_and_wait(seconds: float = 120) -> list[str]:
    TB.login_start()
    seen = []
    end = time.time() + seconds
    while time.time() < end:
        st = TB.status()["login"]["state"]
        if not seen or seen[-1] != st:
            seen.append(st)
        if st not in ("opening", "waiting", "checking"):
            return seen
        time.sleep(0.2)
    raise AssertionError(f"login still running: {seen}")


def test_prepare_profile_clears_stale_locks_and_old_automation_profiles(own_root):
    prof = TB.profile_dir()
    (prof / "Default").mkdir(parents=True)
    (prof / "Local State").write_text("{}", encoding="utf-8")
    for name in ("SingletonLock", "lockfile"):
        (prof / name).write_text("", encoding="utf-8")
    TB._save(logged_in=False, profile_v=None)  # made by the 1.2.42 automated window, never logged in
    rep = TB.prepare_profile(for_login=True)
    assert rep["reset"] == "automation" and prof.is_dir() and not any(prof.iterdir())

    TB._save(profile_v=TB.PROFILE_V)
    (prof / "Local State").write_text('{"broken', encoding="utf-8")
    assert TB.prepare_profile(for_login=True)["reset"] == "corrupted"

    (prof / "Local State").write_text("{}", encoding="utf-8")
    (prof / "SingletonLock").write_text("", encoding="utf-8")
    rep = TB.prepare_profile(for_login=True)
    assert rep["reset"] is None and rep["removed_locks"] == ["SingletonLock"]
    assert (prof / "Local State").is_file()  # a good profile is kept

    TB._save(logged_in=True, profile_v=None)  # logged in before: never thrown away
    assert TB.prepare_profile(for_login=True)["reset"] is None


def test_login_is_a_plain_browser_and_is_checked_after_the_window_closes(studio, own_root, monkeypatch):
    ch = TB._load().get("channel") or "chromium"
    monkeypatch.setenv("SHARKYCLIPS_TT_LOGIN_CMD", _fake_cmd("--stay=2", f"--channel={ch}"))
    TB._save(logged_in=False, login_at=None, profile_v=None)
    seen = _login_and_wait()
    assert "waiting" in seen and seen[-1] == "done", (seen, TB.status()["login"])
    st = TB.status()
    assert st["logged_in"] and st["login_at"] and st["pill"] == "ok"
    assert TB._load()["profile_v"] == TB.PROFILE_V
    assert TB._profile_pids() == []  # nothing left open on the profile


def test_closing_the_window_without_logging_in_says_so(studio, own_root, monkeypatch):
    ch = TB._load().get("channel") or "chromium"
    monkeypatch.setenv("SHARKYCLIPS_TT_LOGIN_CMD", _fake_cmd("--stay=1", "--no-login", f"--channel={ch}"))
    TB._save(logged_in=False, login_at=None, profile_v=TB.PROFILE_V)
    seen = _login_and_wait()
    assert seen[-1] == "not_logged_in", (seen, TB.status()["login"])
    assert not TB.status()["logged_in"]


def test_the_login_command_has_no_automation_attached(own_root, monkeypatch):
    calls = []
    monkeypatch.setattr(TB, "find_browser", lambda: ("chrome", ["C:/Chrome/chrome.exe"]))
    monkeypatch.setattr(TB.procs, "launch_app", lambda cmd: calls.append(cmd) or 1)
    monkeypatch.setattr(TB, "_wait_closed", lambda cancel: "cancelled")
    monkeypatch.setattr(TB, "_close_profile_browser", lambda: 0)
    TB._login["cancel"] = __import__("threading").Event()
    TB._login_run()
    (cmd,) = calls
    assert cmd[0] == "C:/Chrome/chrome.exe" and cmd[-1] == TB.login_url()
    assert f"--user-data-dir={TB.profile_dir()}" in cmd
    assert not [a for a in cmd if "remote-debugging" in a or "automation" in a or "headless" in a]
    assert TB._load()["channel"] == "chrome"  # the automation later opens the same Chrome


def test_find_posts_reads_the_content_list(fresh):
    fresh.seed[:] = [{"caption": "Bu kadar şansa mı güvendi? 😱\nalt satır", "scheduled": None, "id": "7311"},
                     {"caption": "50 PİNG'li saldırı, Miss Fortune'un sonu! 💀", "scheduled": "14 Kas, 18:00 (GMT+1) Budapest",
                      "id": "7312"}]
    rows = TB.find_posts(["Bu kadar şansa mı güvendi? 😱", "50 PİNG'li saldırı, Miss Fortune'un sonu! 💀",
                          "Hiç paylaşılmamış bir başlık"])
    assert rows[0]["found"] and not rows[0]["scheduled"] and rows[0]["href"].endswith("/video/7311")
    assert rows[1]["found"] and rows[1]["scheduled"]
    assert not rows[2]["found"]


def test_check_reads_the_username(fresh):
    TB._save(username=None)
    st = TB.check()
    assert st["logged_in"] and st["username"] == "fakeuser" and st["pill"] == "ok"


# ===================================================================== the one Publish button


@pytest.fixture
def lane(fresh, monkeypatch, tmp_path, cfg):  # noqa: F811
    from test_publishing import _clean_projects

    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(tmp_path / "dl"))
    PF.forget("tiktok")
    config.update(platform_modes={"tiktok": "browser"}, publish_targets=["tiktok"], tiktok_auto_daily=3)
    _clean_projects()
    yield fresh
    from test_publishing import _idle, _wait

    _wait(_idle, 60)
    config.update(publish_targets=None, platform_modes={}, tiktok_auto_daily=3)
    _clean_projects()


def _setup(name: str, cid: str = "c01"):
    from test_multipost import _rendered
    from test_publishing import _project

    project = _project(name)
    _rendered(project, cid)
    return project


def test_publish_posts_tiktok_through_the_studio(lane):
    from test_multipost import _client, _rec
    from test_publishing import _idle, _wait

    assert PF.mode("tiktok") == "browser"
    project = _setup("pub-tt-browser")
    c = _client()
    v = c.get(f"/api/publish/{project.id}/c01?platforms=tiktok").json()
    assert v["modes"]["tiktok"] == "browser" and not v["problems"] and v["tiktok"] is None
    assert v["accounts"]["tiktok"]["connected"] and v["accounts"]["tiktok"]["handle"] == "fakeuser"
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    assert r.status_code == 200, r.text
    _wait(_idle, 120)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "published" and rec["mode"] == "browser" and "/video/" in rec["url"], rec
    assert rec["submitted_at"] and len(lane.posts) == 1
    # idempotent: Publish again never posts twice
    again = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"}).json()
    assert again["results"]["tiktok"]["skipped"]
    _wait(_idle, 60)
    assert len(lane.posts) == 1


def test_publish_plans_in_tiktok_and_counts_the_daily_limit(lane):
    from test_multipost import _client, _rec
    from test_publishing import _idle, _wait
    from sharkyclips.web import multipost as MP

    config.update(tiktok_auto_daily=1)
    project = _setup("pub-tt-plan")
    from test_multipost import _rendered

    _rendered(project, "c02")
    when = ahead(2, 18, 0)
    c = _client()
    r1 = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": when.isoformat()}).json()
    assert r1["results"]["tiktok"]["status"] == "scheduled"
    _wait(_idle, 120)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "scheduled" and rec["remote"] and "(GMT" in (rec.get("scheduled_text") or ""), rec
    assert lane.posts[-1]["date"] == when.strftime("%Y-%m-%d")
    # the day is full (limit 1): the next clip moves to the next day
    r2 = c.post(f"/api/publish/{project.id}/c02", json={"platforms": ["tiktok"], "when": when.isoformat()}).json()
    moved = datetime.fromisoformat(r2["results"]["tiktok"]["publish_at"].replace("Z", "+00:00"))
    assert moved.astimezone().date() == (when + timedelta(days=1)).date() and r2["results"]["tiktok"]["moved"]
    _wait(_idle, 120)
    assert lane.posts[-1]["date"] == (when + timedelta(days=1)).strftime("%Y-%m-%d")
    # TikTok holds it: taking it off the plan is done in TikTok Studio
    from sharkyclips.errors import SharkyClipsError

    with pytest.raises(SharkyClipsError):
        MP.unplan(project, "c01", "tiktok")


def test_captcha_falls_back_to_by_hand_and_tells_you(lane, monkeypatch):
    from test_multipost import _client, _rec
    from test_publishing import _idle, _wait
    from sharkyclips import easy, phone

    sent = []
    monkeypatch.setattr(phone, "send_text", lambda text: sent.append(text) or True)
    lane.mode = "captcha"
    project = _setup("pub-tt-captcha")
    _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    _wait(_idle, 120)
    rec = _rec(project, "c01", "tiktok")
    assert rec["mode"] == "semi" and rec["status"] == "ready", rec  # by hand: file + caption ready
    assert rec["fallback"]["reason"] == "captcha" and Path(rec["fallback"]["shot"]).is_file()
    assert Path(rec["file"]).is_file() and lane.posts == []
    assert sent and "CAPTCHA" in sent[0] or sent  # Telegram (if paired)
    assert any(n["kind"] == "tiktok_stopped" for n in easy.notices()["items"])  # tray notice
    assert TB.blocked() and PF.mode("tiktok") == "semi"  # no more automatic posts for a while
    TB.clear_block()
    assert PF.mode("tiktok") == "browser"


def test_reconcile_fixes_overdue_queue_entries(lane, monkeypatch):
    from sharkyclips import pubqueue as PQ
    from sharkyclips.web import pubqueue_api as QA

    now = PQ.now_local()
    past = PQ.iso(now - timedelta(days=1))
    cal = {"version": 1, "entries": [
        {"id": "p_c04", "platform": "tiktok", "status": "pending", "scheduled_at": past, "source": "p:c04",
         "title": "Akali'yle kaçırılan combo suçlu kanka mıydı?", "batch": None},
        {"id": "p_c06", "platform": "tiktok", "status": "pending", "scheduled_at": past, "source": "p:c06",
         "title": "50 PİNG'li saldırı, Miss Fortune'un sonu! 💀", "batch": None},
        {"id": "p_c01", "platform": "tiktok", "status": "pending", "scheduled_at": past, "source": "p:c01",
         "title": "Komut verdim ama Renekton'a ölüm düştü! 💀", "batch": None},
        {"id": "p_c04", "platform": "instagram", "status": "pending", "scheduled_at": past, "source": "p:c04",
         "title": "Akali'yle kaçırılan combo suçlu kanka mıydı?", "batch": None, "account": "me48"},
        {"id": "p_c05", "platform": "instagram", "status": "pending", "scheduled_at": past, "source": "p:c05",
         "title": "Kanka sıkıntım var derken beni yakaladılar amman!", "batch": None, "account": "me48"},
    ]}
    PQ.save_calendar(cal)
    lane.seed[:] = [{"caption": "Akali'yle kaçırılan combo suçlu kanka mıydı? 😅 #lol", "scheduled": None, "id": "7401"},
                    {"caption": "50 PİNG'li saldırı, Miss Fortune'un sonu! 💀", "scheduled": "16 Kas, 18:00 (GMT+1) Budapest",
                     "id": "7402"}]
    monkeypatch.setattr(PF, "account", lambda name: {"connected": True, "handle": "me48"} if name == "reels"
                        else {"connected": False})
    monkeypatch.setattr(PF, "ig_recent", lambda limit=12: [
        {"id": "1", "caption": "Kanka sıkıntım var derken beni yakaladılar amman!  Arkadaşım...",
         "permalink": "https://www.instagram.com/reel/abc/", "timestamp": "2026-11-12T17:01:24+0000"}])
    out = QA.reconcile()
    by = {(e["id"], e["platform"]): e for e in PQ.load_calendar()["entries"]}
    assert by[("p_c04", "tiktok")]["status"] == "published" and by[("p_c04", "tiktok")]["url"].endswith("/video/7401")
    assert by[("p_c06", "tiktok")]["status"] == "scheduled"
    assert by[("p_c01", "tiktok")]["status"] == "failed"  # not there: never posted (can be planned again)
    assert by[("p_c05", "instagram")]["status"] == "published" and by[("p_c05", "instagram")]["url"].endswith("/abc/")
    assert by[("p_c04", "instagram")]["status"] == "failed"
    assert not PQ.overdue() and out["checked"] == 5
    # the one Publish button skips clips the queue already has out there
    assert QA.live_elsewhere("p", "c04", "tiktok") == "published"
    assert QA.live_elsewhere("p", "c05", "reels") == "published"
    assert QA.live_elsewhere("p", "c01", "tiktok") is None


def test_planned_beyond_tiktoks_window_is_posted_by_the_loop_at_its_time(lane, monkeypatch):
    from test_multipost import _client, _rec, _tick
    from test_publishing import _idle, _wait
    from sharkyclips.web import multipost as MP

    project = _setup("pub-tt-far")
    when = ahead(12, 18, 0)
    r = _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": when.isoformat()}).json()
    assert r["results"]["tiktok"]["status"] == "scheduled"
    _wait(_idle, 60)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "scheduled" and not rec.get("remote") and lane.posts == []
    _tick()  # not due, not inside TikTok's window yet: nothing
    _wait(_idle, 60)
    assert lane.posts == []
    later = when.astimezone(timezone.utc) + timedelta(minutes=1)
    monkeypatch.setattr(MP, "_now", lambda: later)
    _tick(later)
    _wait(_idle, 120)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "published" and len(lane.posts) == 1 and lane.posts[0]["schedule"] == "post_now", rec


def test_a_post_planned_in_tiktok_turns_published_with_its_link(lane, monkeypatch):
    from test_multipost import _client, _rec, _tick
    from test_publishing import _idle, _wait
    from sharkyclips.web import multipost as MP

    project = _setup("pub-tt-live")
    when = ahead(2, 20, 0)
    _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": when.isoformat()})
    _wait(_idle, 120)
    assert _rec(project, "c01", "tiktok")["remote"]
    lane.posts[-1]["schedule"] = "post_now"  # TikTok published it at its time
    later = when.astimezone(timezone.utc) + timedelta(minutes=20)
    monkeypatch.setattr(MP, "_now", lambda: later)
    _tick(later)
    _wait(_idle, 120)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "published" and "/video/" in (rec.get("url") or ""), rec
    assert len(lane.posts) == 1  # looked up, never posted again


def test_an_unreported_queue_post_is_looked_up_before_posting(lane):
    from test_multipost import _client, _rec
    from test_publishing import _idle, _wait
    from sharkyclips import pubqueue as PQ
    from sharkyclips.web import multipost as MP

    project = _setup("pub-tt-unsure")
    title = "Bu kadar şansa mı güvendi? 😱"
    MP.save_clip_store(project, "c01", drafts={"tiktok": {"caption": f"{title}\n\n#lol #shorts"}})
    PQ.save_calendar({"version": 1, "entries": [
        {"id": "u_c01", "platform": "tiktok", "status": "pending", "source": f"{project.id}:c01", "title": title,
         "scheduled_at": PQ.iso(PQ.now_local() - timedelta(hours=3)), "batch": None}]})
    lane.seed[:] = [{"caption": title, "scheduled": None, "id": "7501"}]  # you posted it by hand
    _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    _wait(_idle, 120)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "published" and rec["url"].endswith("/video/7501") and lane.posts == [], rec
    assert PQ.load_calendar()["entries"][0]["status"] == "published"
