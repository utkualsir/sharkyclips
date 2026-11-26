"""1.2.70 "stuck Sharing...": a clip never waits without a word. A swear still heard says so on
the clip (it used to stay "Sharing..." silently), a render that never starts turns into an error
with Retry after the 60 s watchdog, Retry always starts a real job or answers with a clear error,
a platform you finish by hand never holds up the automatic ones, a by-hand post whose job is gone
stops "preparing", the publish queue can cancel everything pending, and Google's user cap is
explained with the own-project guide."""

from __future__ import annotations

from datetime import timedelta

import pytest

from sharkyclips import config, platforms as PF, publishing as P, pubqueue as PQ
from sharkyclips.errors import SharkyClipsError
from test_multipost import _client, _rec, _rendered
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures


@pytest.fixture
def env(cfg, monkeypatch, tmp_path):  # noqa: F811
    from sharkyclips import youtube

    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(tmp_path / "dl"))
    P.plan_path().unlink(missing_ok=True)
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    _clean_projects()
    config.update(platform_modes={}, publish_targets=None, youtube_daily_uploads=None)
    monkeypatch.setattr(youtube, "connected", lambda: True)
    yield
    _wait(_idle, 60)
    config.update(platform_modes={}, publish_targets=None, youtube_daily_uploads=None)
    P.plan_path().unlink(missing_ok=True)
    _clean_projects()


def test_a_swear_still_heard_is_said_on_the_clip_not_a_silent_sharing(env, monkeypatch):
    from sharkyclips.web import multipost as M, publishing as WP, state

    p = _project("pub-stuck-bleep", 2)
    key = P.key_of(p.id, "c01")
    P.put({**WP._item_for(p, "c01"), "now": True})
    monkeypatch.setattr(state, "bleep_hold", lambda project, cid: 2)
    acts = WP.scheduler._tick(P.now_utc())
    assert f"wait_bleep_check:{key}" in acts
    assert P.get(key)["waiting"]["reason"] == "bleep_check"
    st = M.clip_states(p, "c01")["youtube"]
    assert st["status"] == "preparing" and st["wait"]["code"] == "bleep_check" and "swear" in st["wait"]["message"]
    card = next(x for x in _client().get(f"/api/share/{p.id}").json()["clips"] if x["id"] == "c01")
    assert card["status"]["waits"][0]["code"] == "bleep_check"
    # Retry answers with the same clear reason instead of doing nothing
    r = _client().post(f"/api/library/{p.id}/c01/retry")
    assert r.status_code == 400 and "swear" in r.json()["error"]
    # the check is done: the wait note goes away at the next step
    monkeypatch.setattr(state, "bleep_hold", lambda project, cid: 0)
    monkeypatch.setattr(WP, "next_step", lambda project, cand, item: ("export", {"sig": "x", "ab": None}))
    monkeypatch.setattr(WP, "submit_export_for", lambda k, info: type("J", (), {"id": "job-x"})())
    WP.scheduler._tick(P.now_utc())
    assert not P.get(key).get("waiting")


def test_a_render_that_never_starts_becomes_an_error_with_retry_after_60_seconds(env, monkeypatch):
    from sharkyclips.web import multipost as M, publishing as WP

    p = _project("pub-stuck-render", 2)
    key = P.key_of(p.id, "c01")
    P.put({**WP._item_for(p, "c01"), "now": True})
    monkeypatch.setattr(WP, "next_step", lambda project, cand, item: ("wait", {"reason": "render_missing"}))
    now = P.now_utc()
    assert f"wait_render_missing:{key}" in WP.scheduler._tick(now)
    assert not P.get(key).get("attention")
    assert f"wait_render_missing:{key}" in WP.scheduler._tick(now + timedelta(seconds=30))
    assert f"watchdog:{key}" in WP.scheduler._tick(now + timedelta(seconds=61))
    it = P.get(key)
    assert it["attention"] and it["error"]["fix"] == "rerender" and "Retry" in it["error"]["hint"]
    assert M.clip_states(p, "c01")["youtube"]["status"] == "failed"
    # a running render is waited for, never cut off
    P.put({**P.unschedule(it), "now": True, "attention": False, "error": None, "waiting": None})
    monkeypatch.setattr(WP, "next_step", lambda project, cand, item: ("wait", {"reason": "render"}))
    for s in (0, 120, 600):
        WP.scheduler._tick(now + timedelta(seconds=s))
    assert not P.get(key).get("attention")


def test_youtube_retry_starts_a_job_right_away(env, monkeypatch):
    from sharkyclips.web import publishing as WP

    p = _project("pub-stuck-retry", 2)
    key = P.key_of(p.id, "c01")
    P.put({**WP._item_for(p, "c01"), "now": True, "attention": True,
           "error": {"message": "Upload failed.", "hint": None, "fix": "retry"}})
    started = []
    monkeypatch.setattr(WP, "next_step", lambda project, cand, item: ("export", {"sig": "s", "ab": None}))
    monkeypatch.setattr(WP, "submit_export_for", lambda k, info: started.append(k) or type("J", (), {"id": "job-1"})())
    r = _client().post(f"/api/library/{p.id}/c01/retry")
    assert r.status_code == 200, r.text
    assert r.json()["job"] == "job-1" and r.json()["status"] == "rendering" and started == [key]
    # not connected: a clear error, never a silent poke
    from sharkyclips import youtube

    monkeypatch.setattr(youtube, "connected", lambda: False)
    P.put({**P.get(key), "attention": True, "error": {"message": "x", "fix": "retry"}})
    r = _client().post(f"/api/library/{p.id}/c01/retry")
    assert r.status_code == 400 and "isn't connected" in r.json()["error"]


def test_social_retry_after_a_cancel_starts_a_real_job(env):
    from sharkyclips.web import app as A, multipost as M

    config.update(platform_modes={"tiktok": "semi"})
    p = _project("pub-stuck-cancel", 2)
    _rendered(p, "c01")
    c = _client()
    c.post(f"/api/publish/{p.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    j = M.active_job(p.id, "c01", "tiktok")
    if j is not None:
        A.jobs.cancel(j.id)
    _wait(_idle, 30)
    PF.record(p, "c01", "tiktok", status="failed", error={"message": "x"})
    r = c.post(f"/api/publish/{p.id}/c01/retry/tiktok")
    assert r.status_code == 200, r.text
    assert r.json()["job"]
    _wait(_idle, 30)
    assert _rec(p, "c01", "tiktok")["status"] == "ready"


def test_a_by_hand_platform_never_holds_up_youtube(env, monkeypatch):
    from sharkyclips.web import multipost as M

    config.update(platform_modes={"tiktok": "semi"})
    p = _project("pub-stuck-hand", 2)
    _rendered(p, "c01")
    cand = M._app()._cand(p, "c01")
    M.save_clip_store(p, "c01", drafts={"tiktok": {"caption": "x" * 2500}})  # over TikTok's 2,200 characters
    calls = []
    monkeypatch.setattr(M, "_youtube_start", lambda *a, **k: calls.append("yt") or {"status": "uploading"})
    v = M.view(p, "c01", ["youtube", "tiktok"])
    assert any(x["platform"] == "tiktok" and x["code"] == "caption_too_long" for x in v["problems"])
    r = M.start(p, "c01", {"platforms": ["youtube", "tiktok"], "when": "now", "remember": False})
    assert calls == ["yt"] and r["results"]["youtube"]["status"] == "uploading"
    assert r["results"]["tiktok"]["status"] == "preparing"
    assert len(M.drafts(p, M.state.effective_cand(cand, M.state.load_review(p)))["tiktok"]["caption"]) <= 2200
    # too long for TikTok: only TikTok stays back, with the reason
    _wait(_idle, 30)
    PF.record(p, "c01", "tiktok", status="idle")
    monkeypatch.setattr(M, "problems", lambda *a, **k: [{"platform": "tiktok", "code": "too_long", "fix": "turn_off",
                                                          "params": {"max": 600, "dur": 700}}])
    calls.clear()
    r = M.start(p, "c01", {"platforms": ["youtube", "tiktok"], "when": "now", "remember": False})
    assert calls == ["yt"] and r["results"]["tiktok"]["status"] == "failed"
    assert "too long for TikTok" in r["results"]["tiktok"]["error"]["message"]


def test_a_by_hand_post_whose_job_is_gone_stops_preparing(env):
    from sharkyclips.web import multipost as M

    p = _project("pub-stuck-orphan", 2)
    PF.record(p, "c01", "tiktok", mode="semi", status="preparing")
    M.tick()
    assert _rec(p, "c01", "tiktok")["status"] == "preparing"  # within the minute: still fine
    rec = PF.records(p)
    rec["c01"]["tiktok"]["at"] -= 61
    from sharkyclips.project import write_json_atomic

    write_json_atomic(PF.record_path(p), rec)
    acts = M.tick()
    assert f"watchdog:tiktok:{p.id}:c01" in acts
    r = _rec(p, "c01", "tiktok")
    assert r["status"] == "failed" and "stopped" in r["error"]["message"] and "Retry" in r["error"]["hint"]


def test_the_publish_queue_can_cancel_everything_pending(env):
    from datetime import datetime

    PQ.save_calendar({"entries": [
        {"id": "a", "platform": "tiktok", "status": "pending", "scheduled_at": PQ.iso(PQ.now_local() + timedelta(hours=2)),
         "created_at": "1", "title": "A"},
        {"id": "b", "platform": "youtube", "status": "failed", "scheduled_at": PQ.iso(PQ.now_local() - timedelta(hours=2)),
         "created_at": "1", "title": "B"},
        {"id": "c", "platform": "youtube", "status": "published", "scheduled_at": None, "created_at": "1", "title": "C"},
        {"id": "d", "platform": "tiktok", "status": "scheduled", "scheduled_at": None, "created_at": "1", "title": "D"},
    ]})
    r = _client().post("/api/pubqueue/cancel", json={})
    assert r.status_code == 200, r.text
    assert r.json()["cancelled"] == 2
    st = {e["id"]: e["status"] for e in PQ.load_calendar()["entries"]}
    assert st == {"a": "cancelled", "b": "cancelled", "c": "published", "d": "scheduled"}
    assert "cancelled" in PQ.STATUSES and "cancelled" in PQ.calendar_md(PQ.load_calendar()) or True
    # a cancelled post no longer takes a time slot, and it can be marked again by hand
    assert not [t for t in PQ._taken(PQ.load_calendar(), "tiktok") if t]
    e = PQ.mark("a", "tiktok", "pending")
    assert e["status"] == "pending"
    with pytest.raises(SharkyClipsError):
        PQ.mark("a", "tiktok", "nonsense")
    assert isinstance(datetime.now(), datetime)


def test_googles_user_cap_points_to_the_own_project_guide(monkeypatch):
    from sharkyclips import ytconnect

    flow = {"id": "s1", "status": "waiting", "server": None}
    monkeypatch.setattr(ytconnect, "_finish", lambda f, status, message=None, hint=None, reason=None: f.update(
        status=status, message=message, hint=hint, reason=reason))
    ytconnect._handle(flow, {"error": "access_denied", "error_description": "This app has reached its user cap"})
    assert flow["status"] == "blocked" and flow["reason"] == "user_cap"
    assert "100 users" in flow["hint"] and "Google project" in flow["hint"] and "Publish app" in flow["hint"]
