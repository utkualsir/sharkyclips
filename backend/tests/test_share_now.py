"""1.2.68 "share now": upload history + fingerprints, the already-shared warning, Upload manually,
Free up space, the Shorts format check, notices per clip, never-silent YouTube waits, the private
notice, TikTok by hand by default, titles made for views, the Google user-cap message."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import timedelta

import pytest

from sharkyclips import config, history, platforms as PF, publishing as P
from test_multipost import _client, _rendered
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures


@pytest.fixture
def now_env(cfg):  # noqa: F811
    from sharkyclips import youtube

    P.plan_path().unlink(missing_ok=True)
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    history.path().unlink(missing_ok=True)
    _clean_projects()
    config.update(platform_modes={}, publish_targets=None, youtube_daily_uploads=None)
    yield
    _wait(_idle, 60)
    config.update(platform_modes={}, publish_targets=None, youtube_daily_uploads=None)
    P.plan_path().unlink(missing_ok=True)
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    history.path().unlink(missing_ok=True)
    _clean_projects()


def _notices(kind: str | None = None, after: int = 0) -> list[dict]:
    from sharkyclips import easy as E

    items = E.notices(after)["items"]
    return [n for n in items if kind is None or n["kind"] == kind]


def _last() -> int:
    from sharkyclips import easy as E

    return E.notices(0)["last"]


# ===================================================================== history + fingerprints


def test_fingerprint_is_the_same_for_a_renamed_copy(tmp_path):
    a = tmp_path / "rec.mp4"
    a.write_bytes(b"x" * 3_000_000 + b"tail")
    b = tmp_path / "renamed.mkv"
    shutil.copyfile(a, b)
    c = tmp_path / "other.mp4"
    c.write_bytes(b"x" * 3_000_000 + b"tall")
    assert history.fingerprint(a) == history.fingerprint(b) != history.fingerprint(c)


def test_history_remembers_posts_and_warns_on_a_reimport(now_env):
    p1 = _project("pub-hist-a", 2)
    history.note_post(p1, "c01", "youtube", url="https://youtu.be/x1", video_id="x1")
    history.note_post(p1, "c02", "reels", url=None, manual=True)
    history.note_post(p1, "c01", "youtube", url="https://youtu.be/x1")  # the same post: one row
    rows = history.search()["rows"]
    assert len(rows) == 2 and {r["platform"] for r in rows} == {"youtube", "reels"}
    assert rows[0]["fingerprint"] and rows[0]["project_title"] == "Stream pub-hist-a"
    # the same recording imported again (another project, same bytes)
    p2 = _project("pub-hist-b", 2)
    shutil.copyfile(p1.dir / "source.mp4", p2.dir / "source.mp4")
    h = history.for_project(p2)
    assert h["before"] and h["before"]["by_platform"] == {"youtube": 1, "reels": 1}
    assert h["before"]["first_at"] and h["before_projects"] == ["Stream pub-hist-a"]
    assert history.for_project(p1)["before"] is None  # its own posts are no warning
    # the board shows it, the API searches it, and it outlives the project
    assert _client().get(f"/api/share/{p2.id}").json()["history"]["before"]["count"] == 2
    shutil.rmtree(p1.dir)
    r = _client().get("/api/history", params={"q": "youtube"}).json()
    assert r["total"] == 1 and r["rows"][0]["url"] == "https://youtu.be/x1"
    assert _client().get("/api/history", params={"platform": "reels"}).json()["total"] == 1


def test_backfill_adds_older_projects_once(now_env):
    from sharkyclips.web import state

    p = _project("pub-hist-old", 2)
    state.save_upload(p, "c01", {"video_id": "v9", "url": "https://youtu.be/v9", "title": "OLD", "privacy": "public",
                                 "uploaded_at": "2026-11-20T10:00:00+00:00"})
    PF.record(p, "c02", "tiktok", status="published", url="https://www.tiktok.com/@a/video/1", mode="browser")
    history.path().unlink(missing_ok=True)  # the record hook already wrote it: start from nothing
    assert history.backfill([p]) == 2
    assert history.backfill([p]) == 0  # once
    rows = {r["platform"]: r for r in history.search()["rows"]}
    assert rows["youtube"]["at"] == "2026-11-20T10:00:00+00:00" and rows["tiktok"]["url"].endswith("/1")


# ===================================================================== notices (never silent)


def test_a_finished_or_failed_post_gives_one_notice_each(now_env):
    p = _project("pub-note", 2)
    before = _last()
    PF.record(p, "c01", "tiktok", status="published", url="https://www.tiktok.com/@a/video/2")
    PF.record(p, "c01", "tiktok", status="published", views=5)  # no change of state: no new notice
    PF.record(p, "c02", "reels", status="failed", error={"message": "Instagram said no.", "hint": None})
    PF.record(p, "c02", "tiktok", status="failed", error={"message": "x"}, next_try_at="soon")  # retried by itself
    new = _notices(after=before)
    assert [n["kind"] for n in new] == ["shared", "share_failed"]
    assert new[0]["url"].endswith("/2") and "TikTok" in new[0]["title"]
    assert "Instagram said no." in new[1]["body"]
    assert history.search()["total"] == 1


# ===================================================================== Upload manually


def test_upload_manually_saves_the_file_and_texts_then_marks_it_shared(now_env):
    p = _project("pub-manual", 2)
    _rendered(p, "c01")
    c = _client()
    v = c.post(f"/api/manual/{p.id}/c01/youtube").json()
    assert v["upload_page"] == "https://www.youtube.com/upload"
    _wait(_idle, 60)
    v = c.get(f"/api/manual/{p.id}/c01/youtube").json()
    assert v["status"] == "ready" and v["file"] and v["file"].endswith("- YouTube.mp4"), v
    head = v["texts"]["title"].removesuffix("#Shorts")
    assert v["texts"]["title"].endswith("#Shorts") and head == head.upper() and head.startswith("HUGE PLAY 1")
    assert v["texts"]["hashtags"].startswith("#")
    txt = v["file"][:-4] + ".txt"
    assert open(txt, encoding="utf-8").read().startswith(v["texts"]["title"])
    assert any(n["kind"] == "manual_ready" for n in _notices())
    # the board shows it waiting for you; "I posted it" makes it shared + in the history
    card = next(x for x in c.get(f"/api/share/{p.id}").json()["clips"] if x["id"] == "c01")
    assert card["posts"]["youtube"]["status"] == "ready" and card["status"]["kind"] == "scheduled"
    v = c.post(f"/api/manual/{p.id}/c01/youtube/done", json={"url": "https://youtu.be/hand1"}).json()
    assert v["status"] == "shared"
    card = next(x for x in c.get(f"/api/share/{p.id}").json()["clips"] if x["id"] == "c01")
    assert card["status"]["kind"] == "shared" and card["status"]["shared"][0]["url"] == "https://youtu.be/hand1"
    row = history.search()["rows"][0]
    assert row["manual"] and row["platform"] == "youtube"
    # TikTok by hand marks the TikTok record published (never posted again automatically)
    c.post(f"/api/manual/{p.id}/c01/tiktok")
    _wait(_idle, 60)
    c.post(f"/api/manual/{p.id}/c01/tiktok/done", json={"url": "not a link"})
    rec = PF.records(p)["c01"]["tiktok"]
    assert rec["status"] == "published" and rec["manual"] and not rec.get("url")
    assert c.post(f"/api/manual/{p.id}/c01/myspace").status_code == 400


# ===================================================================== Free up space


def test_free_up_space_deletes_the_videos_keeps_the_rest(now_env):
    p = _project("pub-space", 2)
    _rendered(p, "c01")
    (p.dir / "exports").mkdir(exist_ok=True)
    (p.dir / "exports" / "x.mp4").write_bytes(b"0" * 50_000)
    c = _client()
    v = c.get(f"/api/space/{p.id}").json()
    assert v["source_bytes"] > 0 and v["render_bytes"] >= 250_000 and not v["all_shared"]
    assert c.post(f"/api/space/{p.id}/free", json={}).status_code == 400  # needs the confirmation
    # a post that still needs the files blocks it
    PF.record(p, "c02", "tiktok", status="scheduled", mode="api", publish_at=P.iso(P.now_utc() + timedelta(hours=2)))
    r = c.post(f"/api/space/{p.id}/free", json={"confirm": True})
    assert r.status_code == 400 and "still need" in r.json()["error"]
    PF.record(p, "c02", "tiktok", status="published", url="https://www.tiktok.com/@a/video/3")
    r = c.post(f"/api/space/{p.id}/free", json={"confirm": True}).json()
    assert r["freed"] >= v["bytes"] - 10 and r["space"]["bytes"] == 0 and r["space"]["freed_at"]
    assert p.source_path is None and not (p.dir / "clips").exists() and not (p.dir / "exports").exists()
    assert (p.dir / "highlights.json").is_file() and (p.dir / "platform_uploads.json").is_file()
    board = c.get(f"/api/share/{p.id}").json()
    assert board["has_source"] is False and all(x["video"]["kind"] == "none" for x in board["clips"])
    from sharkyclips import trash

    assert not any(i.get("titles") == ["free_space"] for i in trash.items())  # deleted for good, not kept


def test_free_up_space_can_delete_the_original_recording_too(now_env, tmp_path):
    p = _project("pub-space-orig", 1)
    orig = config.workspace_dir() / "_uploads" / "pub-space-orig.mp4"
    orig.parent.mkdir(exist_ok=True)
    orig.write_bytes(b"1" * 40_000)
    meta = p.load_meta()
    p.save_meta({**meta, "source": {"type": "file", "value": str(orig)}})
    v = _client().get(f"/api/space/{p.id}").json()
    assert v["original"]["path"] == str(orig) and v["original"]["bytes"] == 40_000
    r = _client().post(f"/api/space/{p.id}/free", json={"confirm": True, "original": True}).json()
    assert not orig.exists() and r["freed"] >= 40_000


# ===================================================================== the Shorts format check


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_a_wide_clip_is_made_vertical_before_it_goes_out(tmp_path):
    from sharkyclips import shortsfmt

    src = tmp_path / "wide.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=4",
                    "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=44100:duration=4", "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "libmp3lame", "-shortest",
                    str(src)], check=True, capture_output=True)
    res = shortsfmt.check(src, "youtube")
    assert not res["ok"] and {"not_vertical", "audio_codec"} <= set(res["problems"]) and res["fixable"]
    out, fixed = shortsfmt.ensure(src, "youtube", tmp_path / "fix")
    assert out != src and "not_vertical" in fixed
    info = shortsfmt.probe(out)
    assert (info["width"], info["height"]) == (1080, 1920) and info["video_codec"] == "h264"
    assert info["audio_codec"] == "aac" and shortsfmt.check(out, "youtube")["ok"]
    assert shortsfmt.ensure(out, "youtube", tmp_path / "fix") == (out, [])  # fits: the same file
    again, _ = shortsfmt.ensure(src, "youtube", tmp_path / "fix")
    assert again == out  # made once


def test_too_short_and_much_too_long_are_refused():
    from sharkyclips import shortsfmt

    base = {"has_video": True, "width": 1080, "height": 1920, "video_codec": "h264", "audio_codec": "aac",
            "has_audio": True, "fps": 30, "size": 1000}
    assert shortsfmt.check(None, "youtube", {**base, "duration": 20})["ok"]
    assert not shortsfmt.check(None, "youtube", {**base, "duration": 1.0})["fixable"]
    r = shortsfmt.check(None, "youtube", {**base, "duration": 190})
    assert r["problems"] == ["too_long"] and r["fixable"]  # cut at 3:00
    assert not shortsfmt.check(None, "youtube", {**base, "duration": 400})["fixable"]
    assert shortsfmt.check(None, "tiktok", {**base, "duration": 400})["ok"]
    assert shortsfmt.check(None, "youtube", {**base, "duration": 20, "width": 1920, "height": 1080})["problems"] == ["not_vertical"]


# ===================================================================== YouTube: never silent


def test_waiting_youtube_clips_say_why(now_env, monkeypatch):
    from sharkyclips import youtube
    from sharkyclips.web import multipost as M, publishing as WP

    p = _project("pub-wait", 2)
    key = P.key_of(p.id, "c01")
    P.put({**WP._item_for(p, "c01"), "now": True})
    # not connected: said on the clip at the next tick (it used to wait without a word)
    monkeypatch.setattr(youtube, "connected", lambda: False)
    WP.scheduler.tick()
    it = P.get(key)
    assert it["attention"] and it["error"]["message"] == "YouTube isn't connected."
    st = M.clip_states(p, "c01")["youtube"]
    assert st["status"] == "failed" and st["error"]["fix"] == "reconnect"
    # a full day: the clip waits for tomorrow by itself and says so
    P.put({**P.unschedule(P.get(key)), "now": True})
    monkeypatch.setattr(youtube, "connected", lambda: True)
    config.update(youtube_daily_uploads=1)
    youtube.spend_upload()
    monkeypatch.setattr(WP, "next_step", lambda project, cand, item: ("upload", {"source": "clip"}))
    acts = WP.scheduler._tick(P.now_utc())
    assert f"quota:{key}" in acts
    it = P.get(key)
    assert not it["attention"] and P.parse(it["next_try_at"]) > P.now_utc() and it["error"]["fix"] == "manual"
    st = M.clip_states(p, "c01")["youtube"]
    assert st["wait"] and "used up" in st["wait"]["message"]
    board = _client().get(f"/api/share/{p.id}").json()
    card = next(x for x in board["clips"] if x["id"] == "c01")
    assert card["status"]["waits"][0]["platform"] == "youtube"
    assert board["limit"]["left"] == 0  # the clip that waits doesn't fit either


def test_a_video_youtube_kept_private_shows_the_studio_button(now_env):
    from sharkyclips.web import multipost as M, state

    p = _project("pub-private", 1)
    state.save_upload(p, "c01", {"video_id": "pv1", "url": "https://youtu.be/pv1", "privacy": "private",
                                 "requested_privacy": "public", "publish_at": None, "uploaded_at": state.now_iso()})
    st = M.clip_states(p, "c01")["youtube"]
    assert st["private_notice"] == {"studio_url": "https://studio.youtube.com/video/pv1/edit"}
    card = _client().get(f"/api/share/{p.id}").json()["clips"][0]
    assert card["status"]["private"][0]["studio_url"].endswith("/pv1/edit")


def test_youtube_overflow_tomorrow_waits_for_the_reset(now_env, monkeypatch):
    from sharkyclips import youtube
    from sharkyclips.web import multipost as M

    p = _project("pub-after", 1)
    at = youtube.next_reset() + timedelta(minutes=5)
    cand = M._app()._cand(p, "c01")
    r = M._youtube_start(p, cand, None, M.drafts(p, cand), at)
    assert r["status"] == "scheduled"
    it = P.get(P.key_of(p.id, "c01"))
    assert it["now"] and abs((P.parse(it["next_try_at"]) - at).total_seconds()) < 1
    assert not P.due(it) and P.due(it, at + timedelta(seconds=1))
    st = M.clip_states(p, "c01")["youtube"]
    assert st["status"] == "scheduled" and st["publish_at"] and not st["wait"]


# ===================================================================== TikTok, titles, Google


def test_tiktok_is_by_hand_by_default_once(now_env):
    from sharkyclips.web import history_api

    config.update(platform_modes={"tiktok": "browser", "reels": "semi"}, tiktok_manual_default_v1=None)
    assert history_api.migrate_tiktok_manual() is True
    assert config.get("platform_modes")["tiktok"] == "semi" and config.get("tiktok_was_auto") is True
    config.update(platform_modes={"tiktok": "browser"})  # switched back on by the user: stays
    assert history_api.migrate_tiktok_manual() is False and config.get("platform_modes")["tiktok"] == "browser"
    config.update(tiktok_manual_default_v1=None, tiktok_was_auto=None)


def test_tiktok_daily_cap_never_moves_a_post_to_another_day(now_env, monkeypatch):
    from sharkyclips import tiktok_browser as TB
    from sharkyclips.errors import SharkyClipsError
    from sharkyclips.web import multipost as M

    monkeypatch.setattr(TB, "daily_cap", lambda: 1)
    monkeypatch.setattr(M, "_tiktok_day_count", lambda day_of, skip=None: 0)
    assert M.browser_slot(None) is None
    monkeypatch.setattr(M, "_tiktok_day_count", lambda day_of, skip=None: 1)
    with pytest.raises(SharkyClipsError, match="safe limit") as e:
        M.browser_slot(None)
    assert "Upload manually" in e.value.hint


def test_generated_titles_are_made_for_views_typed_ones_stay(now_env):
    from sharkyclips.web import multipost as M

    p = _project("pub-titles", 1)
    cand = M._app()._cand(p, "c01")
    d = M.drafts(p, cand)
    assert d["youtube"]["title"].startswith("HUGE PLAY 1") and d["youtube"]["title"].endswith("#Shorts")
    assert "#Shorts" not in d["tiktok"]["caption"].split("\n")[0] and d["tiktok"]["caption"].startswith("HUGE PLAY 1")
    M.save_clip_store(p, "c01", drafts={"youtube": {"title": "my own Title"}})
    assert M.drafts(p, cand)["youtube"]["title"] == "my own Title"


def test_google_user_cap_is_said_clearly(monkeypatch):
    from sharkyclips import ytconnect

    flow = {"id": "s1", "status": "waiting", "server": None}
    monkeypatch.setattr(ytconnect, "_finish", lambda f, status, message=None, hint=None, reason=None: f.update(
        status=status, message=message, hint=hint, reason=reason))
    ytconnect._handle(flow, {"error": "access_denied", "error_description": "This app has reached its user cap"})
    assert flow["status"] == "blocked" and flow["reason"] == "user_cap" and "100 users" in flow["hint"]
    flow = {"id": "s2", "status": "waiting", "server": None}
    ytconnect._handle(flow, {"error": "access_denied"})
    assert flow["status"] == "cancelled"


def test_board_json_is_plain(now_env):
    p = _project("pub-json", 1)
    b = _client().get(f"/api/share/{p.id}").json()
    json.dumps(b)
    from sharkyclips import languages

    assert b["language"] == languages.content_language(None, p) and b["space"]["bytes"] > 0 and b["limit"]["limit"] == 100
    assert b["platforms"]["tiktok"]["auto_note"] == "tiktok_manual"
