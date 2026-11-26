"""1.2.66 "Share clips": the daily upload limit ("3 of 5 left today"), the plan that rolls the rest
over to the next days, duplicate warnings, the status badge of every clip, batch + single sharing,
Instagram's 4-hour pace in the summary, unschedule and retry."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from sharkyclips import config, platforms as PF, publishing as P
from test_multipost import _client, _rendered
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures


@pytest.fixture
def share(cfg):  # noqa: F811
    """By hand for TikTok / Instagram (the default: no account needed), YouTube not connected,
    fixed release times, a clean plan and no other projects."""
    P.plan_path().unlink(missing_ok=True)
    _clean_projects()
    config.update(platform_modes={}, publish_targets=None, publish_daily_limit=5,
                  publish_times=["12:00", "18:00", "21:00"], publish_learn_times=False, youtube_daily_quota=10_000)
    yield
    _wait(_idle, 60)
    config.update(platform_modes={}, publish_targets=None)
    P.plan_path().unlink(missing_ok=True)
    _clean_projects()


def _today_post(project, cid: str, platform: str = "tiktok") -> None:
    PF.record(project, cid, platform, mode="semi", status="published", posted_at=P.iso(P.now_utc()),
              url="https://www.tiktok.com/@demo/video/1")


# ===================================================================== the daily limit


def test_daily_limit_default_five_top_six_and_editable(share):
    from sharkyclips import tiktok_browser as TB
    from sharkyclips.web import share as S

    config.update(publish_daily_limit=None)
    assert P.DEFAULT_LIMIT == 5 and P.DAILY_MAX == 6 and S.daily_limit() == 5
    assert P.quota_capacity() == 6  # the free 10,000 units take 6 uploads (1,600 each, 300 kept back)
    c = _client()
    assert c.put("/api/share/limit", json={"limit": 9}).json()["limit"] == 6
    assert c.put("/api/share/limit", json={"limit": 0}).json()["limit"] == 1
    v = c.put("/api/share/limit", json={"limit": 4}).json()
    assert v == {**v, "limit": 4, "used": 0, "left": 4, "max": 6}
    # the old Library setting is the same number
    assert c.get("/api/library/settings").json()["daily_limit"] == 4
    # TikTok's automatic cap follows the limit (an old saved 3 was the forced top: it follows too)
    config.update(tiktok_auto_daily=3, tiktok_auto_daily_v=None)
    assert TB.daily_cap() == 4
    assert TB.set_daily_cap(2) == 2 and TB.daily_cap() == 2  # a lower TikTok number you chose stays
    config.update(tiktok_auto_daily=3, tiktok_auto_daily_v=None)


def test_one_clip_on_two_platforms_uses_one_upload_of_the_day(share):
    from sharkyclips.web import share as S

    project = _project("pub-sh-count", 3)
    _today_post(project, "c01", "tiktok")
    _today_post(project, "c01", "reels")
    _today_post(project, "c02", "tiktok")
    PF.record(project, "c03", "tiktok", mode="semi", status="failed", error={"message": "x"})  # doesn't count
    lv = S.limit_view()
    assert (lv["used"], lv["left"], lv["limit"]) == (2, 3, 5)
    assert _client().get(f"/api/share/{project.id}").json()["limit"]["left"] == 3


# ===================================================================== the plan


def test_more_than_today_left_rolls_over_to_the_next_days(share):
    config.update(publish_daily_limit=2)
    project = _project("pub-sh-roll", 6)
    _today_post(project, "c06")  # one of today's two is used
    c = _client()
    p = c.post(f"/api/share/{project.id}/plan", json={"clips": ["c01", "c02", "c03", "c04"],
                                                      "platforms": ["tiktok"]}).json()
    rows = {r["clip_id"]: r for r in p["rows"]}
    today = datetime.now().astimezone().date()
    assert rows["c01"]["when"] == "now" and not rows["c01"]["rolled"]
    t2, t3 = (datetime.fromisoformat(rows[k]["when"]).astimezone() for k in ("c02", "c03"))
    assert t2.date() == today + timedelta(days=1) and t3.date() == today + timedelta(days=1)
    assert (t2.strftime("%H:%M"), t3.strftime("%H:%M")) == ("12:00", "18:00")
    assert datetime.fromisoformat(rows["c04"]["when"]).astimezone().date() == today + timedelta(days=2)
    assert rows["c02"]["rolled"] and rows["c02"]["platforms"][0]["by_hand"]
    assert p["uses_today"] == 1 and p["left_after"] == 0 and p["limit"]["left"] == 1
    assert [d["count"] for d in p["days"]] == [1, 2, 1]
    assert p["count"] == 4 and p["skipped"] == 0 and not p["needs_consent"]


def test_already_shared_platforms_are_skipped_and_reported(share):
    project = _project("pub-sh-dup", 3)
    _today_post(project, "c01", "tiktok")
    c = _client()
    p = c.post(f"/api/share/{project.id}/plan", json={"clips": ["c01", "c02"], "platforms": ["tiktok"]}).json()
    r1 = next(r for r in p["rows"] if r["clip_id"] == "c01")
    assert r1["skipped"] == "already" and r1["already"][0]["platform"] == "tiktok" and not r1["platforms"]
    assert r1["already"][0]["url"].startswith("https://")
    assert p["duplicates"] == 1 and p["count"] == 1
    # with Instagram too: only Instagram goes, TikTok is reported as already there
    p = c.post(f"/api/share/{project.id}/plan", json={"clips": ["c01"], "platforms": ["tiktok", "reels"]}).json()
    r1 = p["rows"][0]
    assert [x["platform"] for x in r1["platforms"]] == ["reels"] and r1["already"][0]["platform"] == "tiktok"
    assert r1["platforms"][0]["manual"]  # Instagram: Manual mode (a reminder, posted from the app)
    # publishing only duplicates: refused, nothing changes
    r = c.post(f"/api/share/{project.id}/publish", json={"clips": ["c01"], "platforms": ["tiktok"]})
    assert r.status_code == 400 and "already" in r.json()["error"]


def test_not_connected_platforms_are_left_out(share):
    project = _project("pub-sh-conn", 2)
    p = _client().post(f"/api/share/{project.id}/plan", json={"clips": ["c01"], "platforms": ["youtube", "tiktok"]}).json()
    r = p["rows"][0]
    assert r["not_connected"] == ["youtube"] and [x["platform"] for x in r["platforms"]] == ["tiktok"]
    assert p["platforms"]["youtube"]["usable"] is False and p["platforms"]["tiktok"]["by_hand"]


def test_instagram_keeps_four_hours_apart_in_the_summary(share):
    project = _project("pub-sh-ig", 3)
    p = _client().post(f"/api/share/{project.id}/plan", json={"clips": ["c01", "c02", "c03"],
                                                              "platforms": ["reels"]}).json()
    ig = [r["platforms"][0] for r in p["rows"]]
    assert ig[0]["when"] == "now" and ig[0]["moved"] is None
    assert ig[1]["moved"] == ig[2]["moved"] == "ig_pace" and p["ig_gap_hours"] == 4.0
    t1, t2 = (datetime.fromisoformat(x["when"]) for x in ig[1:])
    assert timedelta(hours=3.9) < t2 - t1 < timedelta(hours=4.1)
    assert t1 - P.now_utc() > timedelta(hours=3.9)
    assert p["uses_today"] == 3  # all three are today's uploads (only Instagram's time moves)


def test_per_clip_platforms_override_the_batch_choice(share):
    project = _project("pub-sh-per", 2)
    p = _client().post(f"/api/share/{project.id}/plan", json={
        "clips": ["c01", "c02"], "platforms": ["tiktok"], "per_clip": {"c02": {"platforms": ["reels"]}}}).json()
    got = {r["clip_id"]: [x["platform"] for x in r["platforms"]] for r in p["rows"]}
    assert got == {"c01": ["tiktok"], "c02": ["reels"]}


# ===================================================================== status badges


def test_status_badge_of_every_clip(share):
    project = _project("pub-sh-badge", 5)
    _today_post(project, "c01")
    PF.record(project, "c02", "tiktok", mode="api", status="scheduled",
              publish_at=P.iso(P.now_utc() + timedelta(days=1)))
    PF.record(project, "c03", "tiktok", mode="api", status="failed",
              error={"message": "TikTok said no.", "hint": "Try again."})
    PF.record(project, "c04", "tiktok", mode="semi", status="ready", file="x.mp4")
    b = _client().get(f"/api/share/{project.id}").json()
    st = {c["id"]: c["status"] for c in b["clips"]}
    assert st["c01"]["kind"] == "shared" and st["c01"]["shared"] == [
        {"platform": "tiktok", "url": "https://www.tiktok.com/@demo/video/1"}]
    assert st["c02"]["kind"] == "scheduled" and st["c02"]["next_at"]
    assert st["c03"]["kind"] == "failed" and st["c03"]["failed"][0]["message"] == "TikTok said no."
    assert st["c04"]["kind"] == "scheduled" and st["c04"]["planned"][0]["by_hand"]
    assert st["c05"]["kind"] == "not_shared"
    card = next(c for c in b["clips"] if c["id"] == "c01")
    assert card["title"] == "Huge play 1" and card["viral_score"] == 80 and card["duration"] == 5.0
    assert card["video"] == {"kind": "source"}
    assert [c["id"] for c in b["clips"]] == ["c01", "c02", "c03", "c04", "c05"]  # best first, all of them
    assert set(b["platforms"]) == {"youtube", "tiktok", "reels"} and b["limit"]["limit"] == 5


def test_status_kinds_from_platform_states():
    from sharkyclips.web import share as S

    def posts(**st):
        base = {p: {"platform": p, "status": "idle"} for p in ("youtube", "tiktok", "reels")}
        for p, s in st.items():
            base[p] = {"platform": p, **s}
        return base

    assert S._status(posts())["kind"] == "not_shared"
    assert S._status(posts(youtube={"status": "uploading", "progress": 0.4}))["kind"] == "working"
    k = S._status(posts(youtube={"status": "published", "url": "u"}, tiktok={"status": "scheduled", "publish_at": "t"}))
    assert k["kind"] == "shared" and k["next_at"] == "t"  # out somewhere: shared (the rest still shows)
    assert S._status(posts(youtube={"status": "published"}, tiktok={"status": "failed", "error": {}}))["kind"] == "failed"
    assert S._status(posts(reels={"status": "cancelled"}))["kind"] == "not_shared"


# ===================================================================== batch + single


def test_batch_shares_now_and_plans_the_rest_then_remembers_the_platforms(share):
    config.update(publish_daily_limit=2)
    project = _project("pub-sh-batch", 4)
    for cid in ("c01", "c02", "c03"):
        _rendered(project, cid)
    c = _client()
    r = c.post(f"/api/share/{project.id}/publish", json={"clips": ["c01", "c02", "c03"], "platforms": ["tiktok"]})
    assert r.status_code == 200, r.text
    b = r.json()["batch"]
    assert [x["clip_id"] for x in b["rows"]] == ["c01", "c02", "c03"] and b["state"] == "running"
    from sharkyclips.web import share as S

    S.wait_batch(project.id)
    _wait(_idle, 60)
    board = c.get(f"/api/share/{project.id}").json()
    assert board["batch"]["state"] == "done"
    assert [x["state"] for x in board["batch"]["rows"]] == ["done"] * 3, board["batch"]
    rec = {cid: (PF.records(project).get(cid) or {}).get("tiktok") or {} for cid in ("c01", "c02", "c03")}
    assert rec["c01"]["status"] == rec["c02"]["status"] == "ready" and not rec["c01"].get("remind_at")
    tomorrow = datetime.now().astimezone().date() + timedelta(days=1)
    assert datetime.fromisoformat(rec["c03"]["remind_at"]).astimezone().date() == tomorrow
    assert board["limit"]["left"] == 0
    assert board["targets"] == ["tiktok"]  # the last platform choice is remembered
    st = {x["id"]: x["status"]["kind"] for x in board["clips"]}
    assert st == {"c01": "scheduled", "c02": "scheduled", "c03": "scheduled", "c04": "not_shared"}
    # a single clip (the card's own Share button) is a batch of one: today is full, so tomorrow
    _rendered(project, "c04")
    r = c.post(f"/api/share/{project.id}/publish", json={"clips": ["c04"], "platforms": ["tiktok"]}).json()
    assert r["plan"]["rows"][0]["rolled"] and r["plan"]["uses_today"] == 0
    S.wait_batch(project.id)
    _wait(_idle, 60)
    rec = (PF.records(project).get("c04") or {}).get("tiktok") or {}
    assert datetime.fromisoformat(rec["remind_at"]).astimezone().date() == tomorrow
    # the plan never puts two of tomorrow's at the same time
    assert rec["remind_at"] != ((PF.records(project).get("c03") or {}).get("tiktok") or {})["remind_at"]


def test_unschedule_and_retry(share):
    project = _project("pub-sh-undo", 3)
    PF.record(project, "c01", "tiktok", mode="api", status="scheduled",
              publish_at=P.iso(P.now_utc() + timedelta(days=1)))
    PF.record(project, "c02", "tiktok", mode="semi", status="ready", file="x.mp4", notified_at=time.time())
    c = _client()
    r = c.post(f"/api/share/{project.id}/unschedule", json={"clips": ["c01", "c02"]}).json()
    assert {(x["clip_id"], x["platform"]) for x in r["done"]} == {("c01", "tiktok"), ("c02", "tiktok")}
    st = {x["id"]: x["status"]["kind"] for x in c.get(f"/api/share/{project.id}").json()["clips"]}
    assert st["c01"] == st["c02"] == "not_shared"
    # one-tap retry of a failed one (by hand: the file is made again)
    _rendered(project, "c03")
    PF.record(project, "c03", "tiktok", mode="semi", status="failed", error={"message": "disk full"})
    r = c.post(f"/api/share/{project.id}/retry", json={"clips": ["c03"]}).json()
    assert r["done"] == [{"clip_id": "c03", "platform": "tiktok"}]
    _wait(_idle, 60)
    assert ((PF.records(project).get("c03") or {}).get("tiktok") or {})["status"] == "ready"


def test_an_empty_pick_is_refused(share):
    project = _project("pub-sh-empty", 1)
    r = _client().post(f"/api/share/{project.id}/plan", json={"clips": [], "platforms": ["tiktok"]})
    assert r.status_code >= 400


def test_a_platform_the_clip_cannot_go_to_is_left_out_not_the_whole_batch(share):
    project = _project("pub-sh-short", 2)
    hl = project.dir / "highlights.json"
    import json

    data = json.loads(hl.read_text())
    data["candidates"][0].update(end=data["candidates"][0]["start"] + 700.0, duration=700.0)  # TikTok: 600 s max
    hl.write_text(json.dumps(data))
    p = _client().post(f"/api/share/{project.id}/plan", json={"clips": ["c01", "c02"], "platforms": ["tiktok", "reels"]}).json()
    r1, r2 = p["rows"]
    assert [x["platform"] for x in r1["platforms"]] == ["reels"] and r1["dropped"][0]["code"] == "too_long"
    assert [x["platform"] for x in r2["platforms"]] == ["tiktok", "reels"] and p["problems"] == 0
    p = _client().post(f"/api/share/{project.id}/plan", json={"clips": ["c01"], "platforms": ["tiktok"]}).json()
    assert p["rows"][0]["skipped"] == "cant" and p["count"] == 0
