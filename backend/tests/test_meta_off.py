"""1.2.50: Meta restricted the account for automation. Instagram is Manual mode only: nothing
talks to Meta by itself, automatic posts are paused (kept, never sent), a paused post can be
prepared by hand, and at its time SharkyClips reminds you once (Windows notice + in-app bar).
TikTok / YouTube: at most 3 automatic posts a day, one automatic retry."""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timedelta, timezone

import pytest

from sharkyclips import config, easy as E, platforms as PF, publishing as P, pubqueue as PQ, tiktok_browser as TB
from sharkyclips.errors import SharkyClipsError
from sharkyclips.web import multipost as M
from test_multipost import _client, _rec, _rendered
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures


@pytest.fixture
def manual(monkeypatch, tmp_path, cfg):  # noqa: F811
    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(tmp_path / "dl"))

    def no_network(*_a, **_k):
        raise AssertionError("SharkyClips must not call Meta while Meta automation is off")

    monkeypatch.setattr(PF, "_http", no_network)
    PF.forget("reels")
    config.update(platform_modes={"reels": "api"}, publish_targets=["reels"])
    _clean_projects()
    yield tmp_path / "dl"
    _wait(_idle, 60)
    PF.forget("reels")
    config.update(publish_targets=None, platform_modes={})
    _clean_projects()
    for d in config.workspace_dir().glob("meta-*"):  # this file's projects (test_projects_empty)
        shutil.rmtree(d, ignore_errors=True)


def _fake_token():
    PF.save_token("reels", {"access_token": "IGAA" + "x" * 40, "user_id": "1", "saved_at": 0, "handle": "me"})


def test_meta_automation_is_off_and_nothing_reaches_meta(manual):
    assert PF.META_AUTOMATION is False
    _fake_token()
    assert PF.mode("reels") == "semi"  # even with the old "api" switch and a token
    with pytest.raises(SharkyClipsError):
        PF.set_mode("reels", "api")
    for call in (lambda: PF.ig_container("hi"), lambda: PF.ig_publish("1"), lambda: PF.ig_recent(),
                 lambda: PF.ig_container_status("1"), PF.refresh_ig, lambda: PF.ig_connect("IGAA" + "y" * 40),
                 lambda: PF.ig_start("1", "2", 8000)):
        with pytest.raises(PF.PlatformError) as e:
            call()
        assert e.value.code == "meta_off"
    assert PF.ig_quota() is None and PF.ig_delete("1") is False and PF.ig_permalink("1") is None
    assert "refresh:reels" not in PF.keep_fresh() and "refresh_failed:reels" not in PF.keep_fresh()
    assert PF.account("reels")["meta_off"] and not PF.account("reels")["stats"]


def test_automatic_instagram_posts_are_paused_never_sent(manual):
    project = _project("meta-paused")
    _rendered(project, "c01")
    _rendered(project, "c02")
    past = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    soon = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    PF.record(project, "c01", "reels", mode="api", status="scheduled", publish_at=past, caption="A\n\n#a")
    PF.record(project, "c02", "reels", mode="api", status="failed", next_try_at=time.time() - 5, attempts=1,
              publish_at=soon, caption="B\n\n#b")
    acts = M.tick()
    assert f"paused:reels:{project.id}:c01" in acts and f"paused:reels:{project.id}:c02" in acts
    _wait(_idle)
    for cid, was in (("c01", "scheduled"), ("c02", "failed")):
        r = _rec(project, cid, "reels")
        assert r["status"] == "paused" and r["paused_from"] == was and r["paused_mode"] == "api"
        assert not r.get("container_id") and not r.get("media_id")
    assert not [a for a in M.tick() if "reels" in a]  # paused stays paused
    # a post job of an automatic Instagram post (e.g. queued before the update) pauses too
    PF.record(project, "c01", "reels", mode="api", status="preparing")
    assert M.run_post(project.id, "c01", "reels")["status"] == "paused"
    lst = M.manual_list()
    assert {r["clip_id"] for r in lst["paused"]} == {"c01", "c02"}
    # the trash keeps a "posts only" rest while its posts are paused
    from sharkyclips import trash

    assert {r["clip_id"] for r in trash.pending_posts(project) if r["platform"] == "reels"} == {"c01", "c02"}


def test_prepare_by_hand_then_one_reminder_at_the_time(manual):
    project = _project("meta-manual")
    _rendered(project, "c01")
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    PF.record(project, "c01", "reels", mode="api", status="paused", publish_at=later.isoformat(),
              caption="Big play\n\nWhat a round\n\n#clip #game")
    c = _client()
    r = c.post(f"/api/instagram/manual/{project.id}/c01/prepare")
    assert r.status_code == 200, r.text
    _wait(_idle)
    rec = _rec(project, "c01", "reels")
    assert rec["mode"] == "semi" and rec["status"] == "ready" and rec["file"].startswith(str(manual))
    assert rec["remind_at"] and not rec.get("notified_at")
    h = c.get(f"/api/publish/{project.id}/c01/handoff?platforms=reels").json()["platforms"]["reels"]
    assert h["parts"] == {"title": "Big play", "description": "What a round", "hashtags": "#clip #game",
                          "caption": "Big play\n\nWhat a round\n\n#clip #game"}
    assert h["manual_mode"] and h["folder"] and h["file"]
    seen = E.notices()["last"]
    assert not M.manual_tick(project, "c01", _rec(project, "c01", "reels"), datetime.now(timezone.utc))
    assert M.manual_list()["upcoming"][0]["clip_id"] == "c01"
    acts = M.tick(later + timedelta(minutes=1))
    assert f"remind:reels:{project.id}:c01" in acts
    new = [n for n in E.notices(seen)["items"] if n["kind"] == "instagram_manual"]
    assert len(new) == 1 and "Big play" in new[0]["body"]
    assert not [a for a in M.tick(later + timedelta(minutes=2)) if a.startswith("remind:")]  # once
    assert M.manual_list()["due"][0]["clip_id"] == "c01"
    # "later": reminds again after the snooze
    c.post(f"/api/instagram/manual/{project.id}/c01/snooze", json={"minutes": 30})
    assert not _rec(project, "c01", "reels").get("notified_at")
    # "I shared it" ends it
    c.post(f"/api/publish/{project.id}/c01/shared/reels", json={})
    assert _rec(project, "c01", "reels")["status"] == "published"
    assert not M.manual_list()["due"]


def test_publish_now_on_instagram_is_manual_and_needs_no_reminder(manual):
    project = _project("meta-now")
    _rendered(project, "c01")
    c = _client()
    v = c.get(f"/api/publish/{project.id}/c01?platforms=reels").json()
    assert v["modes"]["reels"] == "semi"
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["reels"], "when": "now"})
    assert r.status_code == 200, r.text
    _wait(_idle)
    rec = _rec(project, "c01", "reels")
    assert rec["mode"] == "semi" and rec["status"] == "ready" and rec.get("notified_at")  # the guide is open now


def test_the_chrome_briefs_never_send_anyone_to_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_QUEUE_HOME", str(tmp_path / "q"))
    text = PQ.chrome_brief(tmp_path, {"batch": "b1", "clips": []})
    assert "Never open Instagram, Facebook or Meta Business Suite" in text
    assert "youtube|tiktok|instagram" not in text and "Instagram, signed in" not in text
    assert "Business Suite ->" not in PQ.VERIFY


def test_daily_cap_and_one_automatic_retry():
    # 1.2.66: the daily upload limit tops out at 6 (YouTube's free quota), 5 by default
    assert PF.DAILY_POST_MAX == 6 and PF.AUTO_RETRY_MAX == 1
    assert M.MAX_TRIES == 2 and len(P.BACKOFF_S) == 1
    config.update(publish_daily_limit=10, tiktok_auto_daily=10)
    try:
        assert P.daily_limit() == 6 and TB.daily_cap() == 6 and TB.set_daily_cap(15) == 6
    finally:
        config.update(publish_daily_limit=None, tiktok_auto_daily=3, tiktok_auto_daily_v=None)
    # one automatic retry, then it waits for you
    item = {"attempts": 0}
    item = P.after_failure(item, RuntimeError("boom"))
    assert item["next_try_at"] and not item["attention"]
    item = P.after_failure(item, RuntimeError("boom"))
    assert item["next_try_at"] is None and item["attention"]
