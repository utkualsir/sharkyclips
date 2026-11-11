"""1.2.40 publish queue for Claude in Chrome: compression under 10 MB, Europe/Budapest times, the
scheduler (times, per-day counts, caps, 1 hour lead, full days roll over), the calendar
(takvim.json + takvim.md), duplicates and the status import."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone

import pytest

from sharkyclips import config, pubqueue as PQ
from sharkyclips.errors import SharkyClipsError
from test_multipost import _client
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures


@pytest.fixture
def pq(monkeypatch, tmp_path, cfg):  # noqa: F811
    monkeypatch.setenv("SHARKYCLIPS_QUEUE_HOME", str(tmp_path / "SharkyClips"))
    config.update(pubqueue=None)
    _clean_projects()
    yield tmp_path / "SharkyClips"
    _wait(_idle, 120)
    config.update(pubqueue=None)
    _clean_projects()


def bud(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=PQ.budapest())


# ------------------------------------------------------------------ time zone


def test_budapest_offsets_and_the_fallback_rule_match():
    assert bud(2026, 1, 10, 12).utcoffset() == timedelta(hours=1)
    assert bud(2026, 7, 10, 12).utcoffset() == timedelta(hours=2)
    fb = PQ._EuCentral()
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    zi = PQ.budapest()
    while t < datetime(2028, 1, 1, tzinfo=timezone.utc):  # every 3 h for two years, both DST switches
        assert t.astimezone(fb).utcoffset() == t.astimezone(zi).utcoffset(), t
        assert t.astimezone(fb).replace(tzinfo=None) == t.astimezone(zi).replace(tzinfo=None), t
        t += timedelta(hours=3)
    assert PQ.parse_time("2026-11-12 18:00").isoformat() == "2026-11-12T18:00:00+01:00"
    assert PQ.parse_time("2026-06-12T18:00:00Z").isoformat() == "2026-06-12T20:00:00+02:00"


# ------------------------------------------------------------------ scheduler


def test_scheduler_times_lead_caps_and_next_day(pq):
    s = PQ.settings()
    assert s["platforms"]["youtube"]["times"] == ["12:00", "18:00", "21:00"]
    now = bud(2026, 11, 11, 11, 30)
    # 12:00 is less than an hour away: the first slot is 18:00
    taken = []
    got = []
    for _ in range(4):
        t = PQ.next_slot("youtube", taken, s, now)
        taken.append(t)
        got.append(t.strftime("%m-%d %H:%M"))
    assert got == ["11-11 18:00", "11-11 21:00", "11-12 12:00", "11-12 18:00"]
    # caps: YouTube at most 8 a day even if more times are set; TikTok's cap is a setting
    many = [f"{h:02d}:00" for h in range(8, 23)]
    s = PQ.save_settings({"platforms": {"youtube": {"per_day": 20, "times": many},
                                        "tiktok": {"per_day": 5, "times": many}}, "tiktok_cap": 2})
    assert s["platforms"]["youtube"]["per_day"] == 8 and s["platforms"]["tiktok"]["per_day"] == 2
    taken = []
    for _ in range(9):
        taken.append(PQ.next_slot("youtube", taken, s, bud(2026, 11, 11, 6)))
    assert sum(1 for t in taken if t.day == 11) == 8 and taken[-1].day == 12
    taken = [PQ.next_slot("tiktok", [], s, bud(2026, 11, 11, 6))]
    taken.append(PQ.next_slot("tiktok", taken, s, bud(2026, 11, 11, 6)))
    assert PQ.next_slot("tiktok", taken, s, bud(2026, 11, 11, 6)).day == 12  # full day -> tomorrow
    with pytest.raises(SharkyClipsError, match="1 hour"):
        PQ.check_manual("youtube", bud(2026, 11, 11, 6, 30), [], s, bud(2026, 11, 11, 6))
    with pytest.raises(SharkyClipsError, match="most a day"):
        PQ.check_manual("tiktok", bud(2026, 11, 11, 20), taken, s, bud(2026, 11, 11, 6))
    with pytest.raises(SharkyClipsError, match="isn't a time"):
        PQ.save_settings({"platforms": {"youtube": {"times": "12:00, lunch"}}})


def test_instagram_account_and_brand_hashtag(pq):
    s = PQ.settings()
    assert PQ.instagram_account("gaming", s) == "utkualsirr48"
    assert PQ.instagram_account("podcast", s) == "utkualsirr"
    s = PQ.save_settings({"instagram_account": "utkualsirr"})
    assert PQ.instagram_account("gaming", s) == "utkualsirr"
    assert PQ.with_brand(["gaming", "#DeltaForce", "#utkualsirr"], "#utkualsirr") == ["#utkualsirr", "#gaming", "#DeltaForce"]


def test_bitrate_comes_from_the_length():
    k30 = PQ.video_kbps(30)
    assert 2200 < k30 < 2500  # (9.5 MB * 8 * 0.97 / 30 s) - 96k
    assert PQ.video_kbps(120) < PQ.video_kbps(30) < PQ.video_kbps(10)
    # the whole file stays under the target
    for d in (5, 30, 59, 180):
        assert (PQ.video_kbps(d) * 1000 + PQ.AUDIO_BPS) * d / 8 < PQ.TARGET_BYTES


# ------------------------------------------------------------------ calendar, duplicates, import


def _item(i, sha=None, **kw):
    return {"id": f"proj_c0{i}", "source": f"proj:c0{i}", "sha256": sha or f"sha{i}", "file": f"/x/proj_c0{i}.mp4",
            "size_mb": 4.2, "duration_s": 30, "title": f"Clip {i}", "description": "d", "tags": ["a"],
            "hashtags": ["#utkualsirr"], "mode": "gaming", **kw}


def test_calendar_duplicates_and_status_import(pq):
    s = PQ.settings()
    now = bud(2026, 11, 11, 9)
    folder = PQ.new_batch_dir(now.date())
    assert folder.name == "2026-11-11_batch"
    clips = PQ.plan_batch([_item(1), _item(2)], s, now, batch=folder.name)
    PQ.write_queue(folder, clips, s)
    q = json.loads((folder / "queue.json").read_text(encoding="utf-8"))
    c1 = q["clips"][0]
    assert set(c1["platforms"]) == {"youtube", "tiktok", "instagram"}
    assert c1["platforms"]["instagram"]["account"] == "utkualsirr48"
    assert c1["platforms"]["youtube"] == {"scheduled_at": "2026-11-11T12:00:00+01:00", "status": "pending",
                                          "url": None, "note": None}
    assert q["clips"][1]["platforms"]["youtube"]["scheduled_at"] == "2026-11-11T18:00:00+01:00"
    assert (folder / "CHROME.md").read_text(encoding="utf-8").count("Europe/Budapest") >= 1
    md = PQ.calendar_md_path().read_text(encoding="utf-8")
    assert "| 2026-11-11 | 12:00 | YouTube | Clip 1 |" in md and "Instagram (@utkualsirr48)" in md

    # Claude in Chrome answers (in a code block, with synonyms and a typo'd row)
    answer = ("Done!\n```json\n" + json.dumps({"batch": folder.name, "results": [
        {"id": "proj_c01", "platform": "youtube", "status": "scheduled", "url": "https://youtu.be/abc"},
        {"id": "proj_c01", "platform": "reels", "status": "done", "note": "ok"},
        {"id": "proj_c02", "platform": "tiktok", "status": "failed", "note": "upload error"},
        {"id": "nope", "platform": "youtube", "status": "scheduled"}]}) + "\n```")
    res = PQ.import_status(answer)
    assert res["updated"] == 3 and len(res["unmatched"]) == 1
    q = json.loads((folder / "queue.json").read_text(encoding="utf-8"))
    assert q["clips"][0]["platforms"]["youtube"]["status"] == "scheduled"
    assert q["clips"][0]["platforms"]["youtube"]["url"] == "https://youtu.be/abc"
    assert q["clips"][0]["platforms"]["instagram"]["status"] == "scheduled"
    assert q["clips"][1]["platforms"]["tiktok"]["status"] == "failed"
    assert "youtu.be/abc" in PQ.calendar_md_path().read_text(encoding="utf-8")

    # the same file again: scheduled platforms are skipped, pending ones are re-planned (not doubled)
    again = PQ.plan_batch([_item(1)], s, now, batch="2026-11-11_batch2")[0]["platforms"]
    assert again["youtube"]["status"] == "skipped_duplicate" and again["instagram"]["status"] == "skipped_duplicate"
    assert again["tiktok"]["status"] == "pending"
    cal = PQ.load_calendar()["entries"]
    assert sum(1 for e in cal if e["source"] == "proj:c01" and e["platform"] == "tiktok") == 1
    # a re-encoded file of the same clip counts as the same clip
    again = PQ.plan_batch([_item(1, sha="other")], s, now, write=False)[0]["platforms"]
    assert again["youtube"]["status"] == "skipped_duplicate"
    # a manual time is checked
    with pytest.raises(SharkyClipsError, match="1 hour"):
        PQ.plan_batch([_item(3, times={"youtube": "2026-11-11 09:30"})], s, now, write=False)
    clip = PQ.plan_batch([_item(3, times={"youtube": "2026-11-13 10:15"}, platforms=["youtube"])], s, now, write=False)[0]
    assert list(clip["platforms"]) == ["youtube"] and clip["platforms"]["youtube"]["scheduled_at"] == "2026-11-13T10:15:00+01:00"


# ------------------------------------------------------------------ compression


@pytest.mark.requires_ffmpeg
def test_compress_a_big_clip_under_10_mb(tmp_path):
    from sharkyclips.audio import probe

    src = tmp_path / "big.mp4"
    ff = shutil.which("ffmpeg")
    subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=1080x1920:rate=60:duration=12,noise=alls=40:allf=t", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=12", "-c:v", "libx264", "-preset", "ultrafast",
                    "-b:v", "12M", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)],
                   check=True, capture_output=True)
    assert src.stat().st_size > 10_000_000
    res = PQ.compress(src, tmp_path / "out" / "c01.mp4")
    out = probe(tmp_path / "out" / "c01.mp4")
    assert res["bytes"] < 10_000_000 and res["size_mb"] < 10
    assert out["video_codec"] == "h264" and out["audio_codec"] == "aac"
    assert out["width"] * 16 == out["height"] * 9 and out["fps"] <= 30.5
    assert abs(res["duration_s"] - 12) < 0.3
    assert not list((tmp_path / "out").glob("*.partial*"))


# ------------------------------------------------------------------ the whole flow through the API


@pytest.mark.requires_ffmpeg
def test_prepare_for_chrome_end_to_end(pq):
    project = _project("pub-pq-flow", n=2)
    ff = shutil.which("ffmpeg")
    (project.dir / "clips").mkdir(exist_ok=True)
    for cid in ("c01", "c02"):
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=360x640:rate=30:duration=5", "-f", "lavfi", "-i",
                        "sine=frequency=300:sample_rate=48000:duration=5", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(project.dir / "clips" / f"{cid}.mp4")],
                       check=True, capture_output=True)
    from sharkyclips.project import write_json_atomic

    write_json_atomic(project.dir / "clips.json", {"version": 1, "clips": {
        cid: {"file": f"{cid}.mp4", "rendered_at": time.time()} for cid in ("c01", "c02")}})
    c = _client()
    ov = c.get("/api/pubqueue").json()
    rows = [r for r in ov["clips"] if r["project_id"] == project.id]
    assert [r["clip_id"] for r in rows] == ["c01", "c02"]
    assert "#utkualsirr" in rows[0]["draft"]["hashtags"] and rows[0]["draft"]["title"]
    assert rows[0]["instagram_account"] == "utkualsirr48"
    r = c.put(f"/api/pubqueue/clips/{project.id}/c01", json={"title": "My own title", "hashtags": "#gaming #fun"})
    assert r.json()["draft"]["title"] == "My own title"
    assert r.json()["draft"]["hashtags"] == ["#utkualsirr", "#gaming", "#fun"]
    items = [{"project_id": project.id, "clip_id": x} for x in ("c01", "c02")]
    pv = c.post("/api/pubqueue/preview", json={"items": items}).json()
    assert pv["ok"] and pv["clips"][0]["platforms"]["youtube"]["scheduled_at"]
    assert not PQ.calendar_path().exists()  # a preview saves nothing
    job = c.post("/api/pubqueue/prepare", json={"items": items}).json()["job"]
    _wait(_idle, 120)
    ov = c.get("/api/pubqueue").json()
    assert ov["job"]["id"] == job["id"] and ov["job"]["status"] == "done", ov["job"]
    res = ov["job"]["result"]
    folder = pq / "publish_queue" / res["batch"]
    q = json.loads((folder / "queue.json").read_text(encoding="utf-8"))
    assert [x["title"] for x in q["clips"]][0] == "My own title"
    for clip in q["clips"]:
        f = folder / f"{clip['id']}.mp4"
        assert f.is_file() and f.stat().st_size < 10_000_000 and clip["size_mb"] < 10
        assert clip["sha256"] == PQ.sha256(f) and "#utkualsirr" in clip["hashtags"]
        assert all(v["status"] == "pending" and v["scheduled_at"] for v in clip["platforms"].values())
    assert (pq / "takvim.md").read_text(encoding="utf-8").count("My own title") == 3
    b = c.get("/api/pubqueue/brief").json()
    assert b["batch"] == res["batch"] and "queue.json" in b["text"] and q["clips"][0]["id"] in b["text"]
    imp = c.post("/api/pubqueue/import", json={"text": json.dumps(
        {"results": [{"id": q["clips"][0]["id"], "platform": "youtube", "status": "scheduled", "url": "https://youtu.be/x"}]})}).json()
    assert imp["updated"] == 1
    row = next(r for r in imp["overview"]["clips"] if r["clip_id"] == "c01" and r["project_id"] == project.id)
    assert row["status"]["youtube"]["status"] == "scheduled"
    # prepared again: YouTube is already scheduled for this clip
    c.post("/api/pubqueue/prepare", json={"items": items[:1]})
    _wait(_idle, 120)
    res2 = c.get("/api/pubqueue").json()["job"]["result"]
    assert res2["batch"] != res["batch"] and res2["clips"][0]["platforms"]["youtube"]["status"] == "skipped_duplicate"


def test_a_bad_time_fails_before_any_compressing(pq):
    project = _project("pub-pq-badtime", n=1)
    c = _client()
    c.put(f"/api/pubqueue/clips/{project.id}/c01", json={"times": {"youtube": "2020-01-01T12:00"}})
    r = c.post("/api/pubqueue/prepare", json={"items": [{"project_id": project.id, "clip_id": "c01"}]})
    assert r.status_code == 400 and "1 hour" in r.json()["error"], r.json()
    assert not (pq / "publish_queue").exists() or not any((pq / "publish_queue").iterdir())
