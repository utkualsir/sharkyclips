"""1.2.41 publish queue: generic defaults (no account / brand tag / zone in code), the time zone
setting, overdue posts (time passed, no report), marking by hand, planning again, the check brief
for Claude in Chrome, and browser posts linked into the Library and the digest."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sharkyclips import config, digest, pubqueue as PQ
from sharkyclips.errors import SharkyClipsError
from sharkyclips.web import pubqueue_api as API, state
from test_multipost import _client, _rec
from test_publishing import _clean_projects, _project, cfg  # noqa: F401 - fixtures


@pytest.fixture
def pq(monkeypatch, tmp_path, cfg):  # noqa: F811
    monkeypatch.setenv("SHARKYCLIPS_QUEUE_HOME", str(tmp_path / "SharkyClips"))
    config.update(pubqueue={"timezone": "Europe/Budapest"})
    _clean_projects()
    yield tmp_path / "SharkyClips"
    config.update(pubqueue=None)
    _clean_projects()


def test_generic_defaults_have_no_accounts_brand_or_fixed_zone(monkeypatch, cfg):  # noqa: F811
    config.update(pubqueue=None)
    s = PQ.settings()
    assert s["brand_hashtag"] == "" and s["instagram_accounts"] == [] and s["timezone"] == ""
    assert PQ.instagram_account("gaming", s) == ""  # the signed-in account
    assert PQ.with_brand(["#gaming"], s["brand_hashtag"]) == ["#gaming"]
    # nothing personal is left in the module's defaults
    blob = repr(PQ.DEFAULTS).lower()
    assert "utkualsir" not in blob and "budapest" not in blob
    monkeypatch.setenv("TZ", "")
    assert PQ.zone_name({"timezone": ""}) in ("local", PQ._system_zone_name())


def test_the_time_zone_is_a_setting(cfg):  # noqa: F811
    config.update(pubqueue=None)
    s = PQ.save_settings({"timezone": "America/New_York", "instagram_accounts": "@One, two;two @three!"})
    assert s["timezone"] == "America/New_York" and PQ.zone_name() == "America/New_York"
    assert s["instagram_accounts"] == ["One", "two", "three"]
    assert PQ.parse_time("2026-11-12 18:00").isoformat() == "2026-11-12T18:00:00-05:00"
    assert PQ.parse_time("2026-07-12 18:00").isoformat() == "2026-07-12T18:00:00-04:00"
    with pytest.raises(SharkyClipsError, match="time zone"):
        PQ.save_settings({"timezone": "Mars/Olympus"})
    # a removed account can't stay picked
    s = PQ.save_settings({"instagram_gaming": "three", "instagram_accounts": ["One"]})
    assert s["instagram_gaming"] == "One"
    config.update(pubqueue=None)


def test_this_computers_zone_follows_summer_time():
    z = PQ._SystemLocal()
    import time as _t

    for month in (1, 7):
        dt = datetime(2026, month, 10, 12, 0, tzinfo=z)
        ts = _t.mktime((2026, month, 10, 12, 0, 0, 0, 0, -1))
        assert dt.utcoffset() == timedelta(seconds=_t.localtime(ts).tm_gmtoff)
        back = dt.astimezone(timezone.utc).astimezone(z)
        assert back.replace(tzinfo=None) == dt.replace(tzinfo=None)


def bud(*a):
    return datetime(*a, tzinfo=PQ.budapest())


def _items():
    return [{"id": f"p_c0{i}", "source": f"p:c0{i}", "sha256": f"s{i}", "file": f"/x/p_c0{i}.mp4", "title": f"Clip {i}",
             "description": "d", "tags": [], "hashtags": [], "mode": "gaming", "platforms": ["tiktok", "instagram"]}
            for i in (1, 2)]


def test_overdue_mark_replan_and_the_check_brief(pq):
    s = PQ.settings()
    plan_now = bud(2026, 11, 11, 9)
    folder = PQ.new_batch_dir(plan_now.date())
    PQ.write_queue(folder, PQ.plan_batch(_items(), s, plan_now, batch=folder.name), s)
    later = bud(2026, 11, 11, 19)  # 12:00 and 18:00 have passed, nothing was reported
    od = PQ.overdue(later)
    assert {(e["id"], e["platform"]) for e in od} == {("p_c01", "tiktok"), ("p_c01", "instagram"),
                                                       ("p_c02", "tiktok"), ("p_c02", "instagram")}
    assert all(e["overdue"] for e in od)
    brief = PQ.verify_brief(later)
    assert brief["count"] == 4 and "TikTok Studio" in brief["text"] and "p_c02" in brief["text"]
    assert '"status": "published|scheduled|pending|failed"' in brief["text"]

    # Claude in Chrome looked: one is live, one isn't there, one is planned for later
    res = PQ.import_status({"results": [
        {"id": "p_c01", "platform": "tiktok", "status": "live", "url": "https://www.tiktok.com/@me/video/1"},
        {"id": "p_c01", "platform": "instagram", "status": "not found", "note": "not in Meta Business Suite"},
        {"id": "p_c02", "platform": "tiktok", "status": "scheduled", "scheduled_at": "2026-11-12T20:00:00+01:00",
         "batch": folder.name}]})
    assert res["updated"] == 3 and not res["unmatched"]
    by = {(e["id"], e["platform"]): e for e in PQ.load_calendar()["entries"]}
    assert by[("p_c01", "tiktok")]["status"] == "published"
    assert by[("p_c01", "instagram")]["status"] == "pending"
    assert by[("p_c02", "tiktok")]["scheduled_at"] == "2026-11-12T20:00:00+01:00"
    # marked by hand
    e = PQ.mark("p_c02", "instagram", "failed", url="javascript:alert(1)", note="upload error")
    assert e["status"] == "failed" and e["url"] is None and not e["overdue"]
    with pytest.raises(SharkyClipsError):
        PQ.mark("p_c02", "instagram", "exploded")

    # plan again: only the overdue one (p_c01 instagram), at the next free time >= 1 h from now
    rows = PQ.replan(now=later)
    assert [(r["id"], r["platform"]) for r in rows] == [("p_c01", "instagram")]
    assert rows[0]["scheduled_at"] == "2026-11-11T21:00:00+01:00" and not rows[0]["overdue"]
    import json

    q = json.loads((folder / "queue.json").read_text(encoding="utf-8"))
    c1 = next(c for c in q["clips"] if c["id"] == "p_c01")
    assert c1["platforms"]["instagram"]["scheduled_at"] == "2026-11-11T21:00:00+01:00"
    assert c1["platforms"]["tiktok"]["status"] == "published"
    # a failed one can be planned again on purpose
    rows = PQ.replan([{"id": "p_c02", "platform": "instagram"}], now=later)
    assert rows[0]["status"] == "pending" and rows[0]["scheduled_at"] > "2026-11-11T21:00"
    with pytest.raises(SharkyClipsError, match="Nothing to check"):
        PQ.verify_brief(later)


def test_browser_posts_land_in_the_library_and_the_digest(pq):
    project = _project("pub-pq-link", n=2)
    s = PQ.settings()
    now = PQ.now_local()
    past = now - timedelta(hours=3)
    items = [{"id": API.clip_uid(project.id, "c01"), "source": API.source_key(project.id, "c01"), "sha256": "a",
              "file": "/x/a.mp4", "title": "Clip one", "description": "", "tags": [], "hashtags": [], "mode": "gaming",
              "times": {"youtube": PQ.iso(now + timedelta(days=2)), "tiktok": PQ.iso(now + timedelta(days=2)),
                        "instagram": PQ.iso(now + timedelta(days=2))}}]
    PQ.plan_batch(items, s, batch="b1")
    uid = items[0]["id"]
    PQ.import_status({"results": [
        {"id": uid, "platform": "youtube", "status": "scheduled", "url": "https://youtube.com/shorts/2ghZg4Y96JQ"},
        {"id": uid, "platform": "tiktok", "status": "scheduled"},
        {"id": uid, "platform": "instagram", "status": "published", "url": "https://www.instagram.com/reel/abc/",
         "scheduled_at": PQ.iso(past)}]})
    assert API.link_library() == 3
    assert API.link_library() == 0  # idempotent
    up = state.load_uploads(project)["c01"][0]
    assert up["video_id"] == "2ghZg4Y96JQ" and up["via"] == "chrome" and up["privacy"] == "private"
    assert up["publish_at"].endswith("Z") and state.live_upload(project, "c01")["video_id"] == "2ghZg4Y96JQ"
    tt, ig = _rec(project, "c01", "tiktok"), _rec(project, "c01", "reels")
    assert tt["status"] == "scheduled" and tt["mode"] == "semi" and tt["via"] == "chrome"
    assert ig["status"] == "published" and ig["url"].startswith("https://www.instagram.com/reel/")
    # the Library shows them with the platform badges
    c = _client()
    lib = c.get("/api/library").json()
    row = next(r for r in lib["rows"] if r["project_id"] == project.id and r["clip_id"] == "c01")
    assert row["status"] == "scheduled"
    from sharkyclips.web import multipost as MP

    st = MP.clip_states(project, "c01")
    assert st["tiktok"]["status"] == "scheduled" and st["reels"]["status"] == "published"
    # the publish loop never posts a browser post itself; when its time has come it counts as out

    PQ.mark(uid, "tiktok", "scheduled")
    cal = PQ.load_calendar()
    for e in cal["entries"]:
        if e["platform"] == "tiktok":
            e["scheduled_at"] = PQ.iso(past)
    PQ.save_calendar(cal)
    API._link_at["t"] = 0
    MP.tick()
    assert _rec(project, "c01", "tiktok")["status"] == "published"
    assert _rec(project, "c01", "tiktok").get("mode") == "semi"
    d = digest.weekly(datetime.now(timezone.utc) + timedelta(minutes=1))
    assert d["elsewhere"]["tiktok"] == 1 and d["elsewhere"]["reels"] == 1


def test_a_post_made_another_way_is_never_overwritten(pq):
    from sharkyclips import platforms as PF

    project = _project("pub-pq-keep", n=1)
    PF.record(project, "c01", "tiktok", status="published", url="https://www.tiktok.com/@me/video/9", mode="api")
    PQ.plan_batch([{"id": API.clip_uid(project.id, "c01"), "source": API.source_key(project.id, "c01"), "sha256": "k",
                    "file": "/x/k.mp4", "title": "K", "platforms": ["tiktok"], "mode": "gaming"}], PQ.settings(), batch="b")
    PQ.import_status({"results": [{"id": API.clip_uid(project.id, "c01"), "platform": "tiktok", "status": "published"}]})
    API.link_library()
    r = _rec(project, "c01", "tiktok")
    assert r["mode"] == "api" and r["url"].endswith("/9") and r.get("via") is None
