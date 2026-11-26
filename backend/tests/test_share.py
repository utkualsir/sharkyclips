"""1.2.66 "Share clips" + 1.2.68 "share now": no own daily limit, everything goes now up to what
YouTube really allows today, a choice (by hand now / tomorrow / a picked day) for the rest, duplicate
warnings, the status badge of every clip, batch + single sharing, Instagram's 4-hour pace as a
warning only, unschedule and retry."""

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
    from sharkyclips import youtube

    P.plan_path().unlink(missing_ok=True)
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    _clean_projects()
    config.update(platform_modes={}, publish_targets=None, youtube_daily_uploads=None,
                  publish_times=["12:00", "18:00", "21:00"], publish_learn_times=False, youtube_daily_quota=10_000)
    yield
    _wait(_idle, 60)
    config.update(platform_modes={}, publish_targets=None, youtube_daily_uploads=None)
    P.plan_path().unlink(missing_ok=True)
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    _clean_projects()


def _today_post(project, cid: str, platform: str = "tiktok") -> None:
    PF.record(project, cid, platform, mode="semi", status="published", posted_at=P.iso(P.now_utc()),
              url="https://www.tiktok.com/@demo/video/1")


# ===================================================================== what YouTube allows today


def test_no_own_daily_limit_only_youtubes_real_upload_quota(share):
    from sharkyclips import youtube
    from sharkyclips.web import share as S

    config.update(youtube_daily_uploads=None)
    assert youtube.daily_uploads() == 100 and youtube.COST["upload"] == 1  # Google's bucket since June 2026
    assert P.daily_limit() == P.quota_capacity() == 100  # the old setting is ignored
    lv = S.limit_view()
    assert (lv["limit"], lv["left"]) == (100, 100) and lv["used"] == 0
    youtube.spend_upload()
    youtube.spend_upload()
    assert S.limit_view()["left"] == 98 and youtube.quota_view()["uploads_left"] == 98
    youtube.spend(9_700)  # the units bucket (thumbnails, edits) never blocks an upload
    assert youtube.uploads_left() == 98 and not youtube.thumbnail_fits()
    c = _client()
    assert c.put("/api/share/limit", json={"limit": 4}).status_code in (404, 405)  # the setting is gone
    (youtube.folder() / "quota.json").unlink(missing_ok=True)


def _yt_usable(monkeypatch):
    from sharkyclips.web import share as S

    real = S._platforms_view

    def view():
        v = real()
        v["youtube"] = {**v["youtube"], "usable": True, "connected": True}
        return v

    monkeypatch.setattr(S, "_platforms_view", view)


def test_more_than_youtube_allows_today_needs_a_choice(share, monkeypatch):
    from sharkyclips import youtube

    _yt_usable(monkeypatch)
    config.update(youtube_daily_uploads=2)
    youtube.spend_upload()  # one of today's two is used
    project = _project("pub-sh-over", 4)
    c = _client()
    body = {"clips": ["c01", "c02", "c03"], "platforms": ["youtube", "tiktok"]}
    p = c.post(f"/api/share/{project.id}/plan", json=body).json()
    yt = {r["clip_id"]: next(x for x in r["platforms"] if x["platform"] == "youtube") for r in p["rows"]}
    assert yt["c01"]["when"] == "now" and yt["c01"]["over"] is None
    assert yt["c02"]["over"] == yt["c03"]["over"] == "ask" and p["over"] == 2 and p["uses_today"] == 1
    # TikTok is never held back by YouTube's quota: every clip goes now there
    assert all(next(x for x in r["platforms"] if x["platform"] == "tiktok")["when"] == "now" for r in p["rows"])
    # Publish without a choice is refused with a clear code
    r = c.post(f"/api/share/{project.id}/publish", json=body)
    assert r.status_code == 400 and r.json().get("code") == "over_limit", r.text
    # "tomorrow": after Google's reset, never later
    p = c.post(f"/api/share/{project.id}/plan", json={**body, "overflow": "tomorrow"}).json()
    when = datetime.fromisoformat(p["overflow_at"])
    assert timedelta(0) < when - youtube.next_reset() < timedelta(minutes=10)
    assert all(next(x for x in r["platforms"] if x["platform"] == "youtube")["when"] == p["overflow_at"]
               for r in p["rows"] if r["clip_id"] != "c01")
    # a day the user picked
    day = (datetime.now().astimezone().date() + timedelta(days=3)).isoformat()
    p = c.post(f"/api/share/{project.id}/plan", json={**body, "overflow": "date", "overflow_date": day}).json()
    assert datetime.fromisoformat(p["overflow_at"]).astimezone().date().isoformat() == day
    r = c.post(f"/api/share/{project.id}/plan", json={**body, "overflow": "date", "overflow_date": "2001-01-01"})
    assert r.status_code == 400
    # "by hand now": those clips are prepared for a manual upload
    p = c.post(f"/api/share/{project.id}/plan", json={**body, "overflow": "manual"}).json()
    x = next(x for x in p["rows"][1]["platforms"] if x["platform"] == "youtube")
    assert x["force_manual"] and x["when"] == "now"
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    config.update(youtube_daily_uploads=None)


def test_everything_picked_goes_now(share):
    project = _project("pub-sh-now", 6)
    p = _client().post(f"/api/share/{project.id}/plan", json={"clips": ["c01", "c02", "c03", "c04", "c05"],
                                                             "platforms": ["tiktok"]}).json()
    assert all(r["when"] == "now" and not r["rolled"] for r in p["rows"])
    assert all(x["when"] == "now" for r in p["rows"] for x in r["platforms"])
    assert p["count"] == 5 and p["over"] == 0 and not p["needs_consent"]


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


def test_instagram_pace_is_only_a_warning(share):
    project = _project("pub-sh-ig", 3)
    p = _client().post(f"/api/share/{project.id}/plan", json={"clips": ["c01", "c02", "c03"],
                                                              "platforms": ["reels"]}).json()
    ig = [r["platforms"][0] for r in p["rows"]]
    assert all(x["when"] == "now" and x["moved"] is None for x in ig)  # never delayed
    warns = [r["warnings"] for r in p["rows"]]
    assert warns[0] == [] and warns[1][0]["code"] == warns[2][0]["code"] == "ig_pace"
    assert p["warnings"] == 2 and p["ig_gap_hours"] == 4.0


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
    assert set(b["platforms"]) == {"youtube", "tiktok", "reels"} and b["limit"]["limit"] == 100


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


def test_batch_shares_everything_now_then_remembers_the_platforms(share):
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
    assert all(r["status"] == "ready" and not r.get("remind_at") for r in rec.values())  # all now, by hand
    assert board["targets"] == ["tiktok"]  # the last platform choice is remembered
    st = {x["id"]: x["status"]["kind"] for x in board["clips"]}
    assert st == {"c01": "scheduled", "c02": "scheduled", "c03": "scheduled", "c04": "not_shared"}


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
