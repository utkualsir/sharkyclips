"""1.2.36 one Publish button, three platforms: captions + limits + one-tap fixes, TikTok's required
post screen, the posting engine against fake YouTube / TikTok / Instagram servers (parallel posts,
slow processing, expired token, rate limit, partial failure, crash mid-upload, lost answers,
duplicate protection), planned posts + catch-up, accounts, quotas and views."""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from fake_platforms import IG_TOKEN, FakePlatforms
from sharkyclips import config, platforms as PF
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic
from test_publishing import _clean_projects, _idle, _project, _ready, _wait, cfg, yt  # noqa: F401 - fixtures


def _client():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    return TestClient(app)


@pytest.fixture
def social(monkeypatch, cfg):  # noqa: F811
    """Fake TikTok + Instagram, both connected; fast polling; clean records."""
    from sharkyclips.web import multipost as MP

    f = FakePlatforms()
    monkeypatch.setenv("SHARKYCLIPS_TIKTOK_ENDPOINT", f.url)
    monkeypatch.setenv("SHARKYCLIPS_IG_ENDPOINT", f.url)
    monkeypatch.setenv("SHARKYCLIPS_FB_ENDPOINT", f.url)
    monkeypatch.setattr(MP, "POLL_S", 0.01)
    for p in ("tiktok", "reels"):
        PF.forget(p)
    PF._creator_cache.clear()
    config.update(platform_modes={}, publish_targets=["youtube", "tiktok", "reels"])
    _clean_projects()
    url = PF.tiktok_start("ck-123", "cs-456", 8000)
    from urllib.parse import parse_qs, urlparse

    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    f.state["codes"]["CODE1"] = q["code_challenge"]
    PF.tiktok_finish("CODE1", q["state"])
    PF.ig_connect(IG_TOKEN)
    yield f
    _wait(_idle, 60)
    f.close()
    for p in ("tiktok", "reels"):
        PF.forget(p)
    PF._creator_cache.clear()
    config.update(publish_targets=None)
    _clean_projects()


def _rendered(project: Project, cid: str, size: int = 200_000) -> None:
    """A rendered 9:16 clip on disk (what TikTok / Instagram get), no ffmpeg needed."""
    (project.dir / "clips").mkdir(exist_ok=True)
    (project.dir / "clips" / f"{cid}.mp4").write_bytes(os.urandom(size))
    path = project.dir / "clips.json"
    data = json.loads(path.read_text()) if path.is_file() else {"version": 1, "clips": {}}
    data["clips"][cid] = {"file": f"{cid}.mp4", "rendered_at": time.time()}
    write_json_atomic(path, data)


def _rec(project: Project, cid: str, p: str) -> dict:
    return (PF.records(project).get(cid) or {}).get(p) or {}


def _tick(now=None):
    from sharkyclips.web import jobs as J, multipost as MP

    with J.automatic():
        acts = MP.tick(now)
    _wait(_idle, 60)
    return acts


def _ok_tiktok(c, pid, cid, **extra):
    return {"platforms": ["tiktok"], "when": "now", "consent": True, **extra}


# ===================================================================== content + checks


def test_captions_lead_with_the_channel_tag_and_respect_the_limits(social):
    from sharkyclips.web import multipost as MP

    from sharkyclips.edit import brand

    old = config.get("channel_text")
    brand.save_channel_text({"hashtags": ["#utkualsirr"]})
    try:
        _caption_checks(MP)
    finally:
        config.update(channel_text=old)


def _caption_checks(MP):
    project = _project("pub-mp-cap")
    _rendered(project, "c01")
    v = MP.view(project, "c01", ["youtube", "tiktok", "reels"])
    cap = v["drafts"]["reels"]["caption"]
    assert cap.startswith("Huge play 1\n\nWhat a moment 1.")
    tags = [w for w in cap.split() if w.startswith("#")]
    assert tags[0] == "#utkualsirr" and "#deltaforce" in tags
    assert v["drafts"]["youtube"]["title"] == "Huge play 1" and v["limits"]["reels"]["hashtags"] == 30
    assert {p["code"] for p in v["problems"]} == {"not_connected"}  # YouTube isn't connected here
    # too long / too many hashtags / long title: inline problems with one-tap fixes
    many = "Big one\n\n" + " ".join(f"#t{i}" for i in range(40))
    MP.save_clip_store(project, "c01", drafts={"reels": {"caption": many}, "tiktok": {"caption": "x" * 2300},
                                               "youtube": {"title": "word " * 30}})
    v = MP.view(project, "c01", ["youtube", "tiktok", "reels"])
    codes = {(p["platform"], p["code"]): p for p in v["problems"]}
    assert codes[("reels", "too_many_hashtags")]["params"] == {"n": 40, "max": 30}
    assert codes[("tiktok", "caption_too_long")]["fix"] == "shorten_caption"
    assert codes[("youtube", "title_too_long")]["fix"] == "shorten_title"
    for (plat, _code), p in codes.items():
        if p["fix"] in ("shorten_caption", "trim_hashtags", "shorten_title"):
            v = MP.apply_fix(project, "c01", plat, p["fix"])
    assert MP.hashtag_count(v["drafts"]["reels"]["caption"]) == 30
    assert len(v["drafts"]["tiktok"]["caption"]) <= 2200
    assert len(v["drafts"]["youtube"]["title"]) <= 100 and v["drafts"]["youtube"]["title"].endswith("…")
    assert not [p for p in v["problems"] if p["code"] != "not_connected"]


def test_swears_are_censored_in_every_caption(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-swear")
    _rendered(project, "c01")
    MP.save_clip_store(project, "c01", drafts={"tiktok": {"caption": "what the fuck was that"},
                                               "youtube": {"title": "fuck yes"}})
    d = MP.view(project, "c01")["drafts"]
    assert "fuck" not in d["tiktok"]["caption"].lower() and "fuck" not in d["youtube"]["title"].lower()


def test_tiktok_post_screen_follows_tiktoks_rules(social):
    """Creator info, privacy picked by hand (no default once audited), interactions off by
    default and greyed when the creator disabled them, disclosure + branded content rules,
    the music confirmation, and SELF_ONLY until the app is audited."""
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-ux")
    _rendered(project, "c01")
    c = _client()
    v = c.get(f"/api/publish/{project.id}/c01", params={"platforms": "tiktok"}).json()
    tt = v["tiktok"]
    assert tt["ok"] and tt["creator"] == {"username": "utkualsirr", "nickname": "utku alsir"}
    assert tt["privacy_options"] == ["SELF_ONLY"] and tt["privacy"] == "SELF_ONLY" and not tt["audited"]
    assert tt["stitch_disabled"] and tt["music_url"].startswith("https://www.tiktok.com/legal/")
    assert tt["settings"]["allow_comment"] is False and tt["settings"]["allow_duet"] is False
    assert not v["problems"]
    # branded content can never be private: while unaudited the fix is to switch it off
    v = c.put(f"/api/publish/{project.id}/c01", params={"platforms": "tiktok"},
              json={"tiktok": {"disclose": True}}).json()
    assert [p["code"] for p in v["problems"]] == ["disclosure_incomplete"]
    v = c.put(f"/api/publish/{project.id}/c01", params={"platforms": "tiktok"},
              json={"tiktok": {"brand_content": True}}).json()
    assert [(p["code"], p["fix"]) for p in v["problems"]] == [("branded_private", "no_branded")]
    v = c.post(f"/api/publish/{project.id}/c01/fix", json={"platform": "tiktok", "code": "no_branded"}).json()
    v = c.put(f"/api/publish/{project.id}/c01", params={"platforms": "tiktok"},
              json={"tiktok": {"disclose": False}}).json()
    assert not v["problems"]
    # consent (the Music Usage Confirmation) is required
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    assert r.status_code == 400 and "Music Usage" in r.json()["error"]
    # audited app: the creator's own choices, and nothing is picked for the user
    PF.set_audited("tiktok", True)
    social.state["privacy_options"] = ["PUBLIC_TO_EVERYONE", "FOLLOWER_OF_CREATOR", "SELF_ONLY"]
    PF._creator_cache.clear()
    v = c.get(f"/api/publish/{project.id}/c01", params={"platforms": "tiktok"}).json()
    assert v["tiktok"]["privacy"] is None and [p["code"] for p in v["problems"]] == ["privacy_missing"]
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now", "consent": True})
    assert r.status_code == 400 and r.json()["problems"][0]["code"] == "privacy_missing"
    v = c.put(f"/api/publish/{project.id}/c01", params={"platforms": "tiktok"},
              json={"tiktok": {"privacy": "FOLLOWER_OF_CREATOR", "allow_comment": True}}).json()
    assert not v["problems"]
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now", "consent": True})
    assert r.status_code == 200, r.text
    _wait(_idle)
    post = social.state["tiktok_posts"][-1]["post_info"]
    assert post["privacy_level"] == "FOLLOWER_OF_CREATOR" and post["disable_comment"] is False
    assert post["disable_duet"] is True and post["disable_stitch"] is True  # off by default / creator disabled
    assert post["brand_content_toggle"] is False and post["brand_organic_toggle"] is False
    assert post["video_cover_timestamp_ms"] == 2500  # the peak frame is the cover
    assert MP.targets() == ["tiktok"]  # remembered


def test_unaudited_tiktok_posts_only_me_and_says_how_to_open_it(social):
    project = _project("pub-mp-self")
    _rendered(project, "c01")
    c = _client()
    r = c.post(f"/api/publish/{project.id}/c01", json=_ok_tiktok(c, project.id, "c01"))
    assert r.status_code == 200, r.text
    _wait(_idle)
    st = c.get(f"/api/publish/{project.id}/c01").json()["states"]["tiktok"]
    assert st["status"] == "published" and st["privacy"] == "self_only"
    assert st["make_public_url"] == "https://www.tiktok.com/tiktokstudio/content"
    assert st["url"] == "https://www.tiktok.com/@utkualsirr"
    assert social.state["tiktok_posts"][-1]["post_info"]["privacy_level"] == "SELF_ONLY"


# ===================================================================== the engine


def test_everywhere_at_once_in_parallel_and_never_twice(yt, social):  # noqa: F811
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-all")
    _rendered(project, "c01")
    _ready(project, "c01")
    social.state["tt_processing_polls"] = 40  # TikTok is slow today: Instagram mustn't wait for it
    c = _client()
    v = c.get(f"/api/publish/{project.id}/c01").json()
    assert not v["problems"], v["problems"]
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["youtube", "tiktok", "reels"], "when": "now",
                                                       "consent": True}).json()
    assert {p: x["status"] for p, x in r["results"].items()} == {"youtube": "uploading", "tiktok": "uploading",
                                                                 "reels": "uploading"}
    _wait(_idle)
    from sharkyclips.web import app as A

    posts = {j.params.get("platform"): j for j in A.jobs.jobs() if j.kind == "post" and j.project_id == project.id}
    tt, ig = posts["tiktok"], posts["reels"]
    # side by side: each started before the other finished (timestamps, so a fast machine can't miss it)
    assert ig.started < tt.finished and tt.started < ig.finished, "TikTok and Instagram should upload side by side"
    sts = MP.clip_states(project, "c01")
    assert [sts[p]["status"] for p in ("youtube", "tiktok", "reels")] == ["published"] * 3, sts
    assert sts["everywhere"] and sts["reels"]["url"] == "https://www.instagram.com/reel/MC1/"
    assert len(yt.videos) == 1 and len(social.state["tiktok_posts"]) == 1 and len(social.state["ig_posts"]) == 1
    # again: nothing new goes out anywhere
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["youtube", "tiktok", "reels"], "when": "now",
                                                       "consent": True}).json()
    assert all(x.get("skipped") for x in r["results"].values())
    # many clicks at the same time: still one post
    for p in ("tiktok", "reels"):
        PF.record(project, "c01", p, status="failed")  # (pretend: a retry is allowed now)
    _rendered(project, "c02")
    threads = [threading.Thread(target=lambda: c.post(f"/api/publish/{project.id}/c02", json={
        "platforms": ["tiktok", "reels"], "when": "now", "consent": True})) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    _wait(_idle)
    assert len(social.state["tiktok_posts"]) == 2 and len(social.state["ig_posts"]) == 2
    # a failed record that still has its TikTok publish_id: Retry asks TikTok first, posts nothing new
    MP.retry(project, "c01", "tiktok")
    MP.retry(project, "c01", "reels")  # (Instagram: the stored post id answers at once)
    _wait(_idle)
    assert len(social.state["tiktok_posts"]) == 2 and _rec(project, "c01", "tiktok")["status"] == "published"
    assert len(social.state["ig_posts"]) == 2 and _rec(project, "c01", "reels")["status"] == "published"
    # Library: badges per platform, filters can use them, "posted everywhere"
    lib = c.get("/api/library").json()
    row = next(r for r in lib["rows"] if r["project_id"] == project.id and r["clip_id"] == "c01")
    assert row["platforms"]["everywhere"] and row["platforms"]["tiktok"]["status"] == "published"
    assert lib["targets"] == ["tiktok", "reels"] and lib["accounts"]["reels"]["handle"] == "utku.clips"


def test_partial_failure_keeps_the_others_and_retry_redoes_only_the_failed_one(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-part")
    _rendered(project, "c01")
    social.state["ig_rate_limit"] = 1
    c = _client()
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok", "reels"], "when": "now", "consent": True})
    _wait(_idle)
    sts = MP.clip_states(project, "c01")
    assert sts["tiktok"]["status"] == "published" and sts["reels"]["status"] == "failed"
    assert sts["reels"]["error"]["kind"] == "rate_limit" and sts["reels"]["next_try_at"]
    v = c.post(f"/api/publish/{project.id}/c01/retry/reels").json()
    _wait(_idle)
    sts = MP.clip_states(project, "c01")
    assert sts["reels"]["status"] == "published" and len(social.state["tiktok_posts"]) == 1
    assert v["states"]["tiktok"]["status"] == "published"


def test_rate_limit_retries_by_itself_with_backoff(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-rate")
    _rendered(project, "c01")
    social.state["tt_rate_limit"] = 1
    MP.start(project, "c01", {"platforms": ["tiktok"], "when": "now", "consent": True})
    _wait(_idle)
    r = _rec(project, "c01", "tiktok")
    assert r["status"] == "failed" and r["error"]["kind"] == "rate_limit" and r["next_try_at"] > time.time()
    assert not [a for a in _tick() if a.startswith("retry")]  # not yet
    PF.record(project, "c01", "tiktok", next_try_at=time.time() - 1)
    assert any(a.startswith("retry:tiktok") for a in _tick())
    assert _rec(project, "c01", "tiktok")["status"] == "published"


def test_expired_tiktok_token_is_refreshed_mid_post(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-tok")
    _rendered(project, "c01")
    social.state["tt_expire_token"] = True
    before = social.state["refreshes"]
    MP.start(project, "c01", {"platforms": ["tiktok"], "when": "now", "consent": True})
    _wait(_idle)
    assert _rec(project, "c01", "tiktok")["status"] == "published"
    assert social.state["refreshes"] == before + 1


def test_slow_processing_is_checked_later_by_the_loop(social, monkeypatch):
    from sharkyclips.web import multipost as MP

    monkeypatch.setattr(MP, "PROCESS_WAIT_S", 0.05)
    project = _project("pub-mp-slow")
    _rendered(project, "c01")
    social.state["tt_processing_polls"] = 10_000
    social.state["ig_processing_polls"] = 10_000
    MP.start(project, "c01", {"platforms": ["tiktok", "reels"], "when": "now", "consent": True})
    _wait(_idle)
    sts = MP.clip_states(project, "c01")
    assert sts["tiktok"]["status"] == "processing" and sts["reels"]["status"] == "processing"
    social.state["tt_processing_polls"] = 0
    social.state["ig_processing_polls"] = 0
    for p in ("tiktok", "reels"):
        PF.record(project, "c01", p, checked_at=0)
    _tick()
    sts = MP.clip_states(project, "c01")
    assert sts["tiktok"]["status"] == "published" and sts["reels"]["status"] == "published"
    assert len(social.state["tiktok_posts"]) == 1 and len(social.state["ig_posts"]) == 1


def test_crash_mid_upload_continues_without_posting_twice(social, monkeypatch):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-crash")
    _rendered(project, "c01")
    real_send, real_pub = PF.tiktok_send, PF.ig_publish
    monkeypatch.setattr(PF, "tiktok_send", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("power cut")))

    def publish_then_die(container):
        real_pub(container)  # Instagram published it, but the answer never arrived
        raise RuntimeError("power cut")

    monkeypatch.setattr(PF, "ig_publish", publish_then_die)
    MP.start(project, "c01", {"platforms": ["tiktok", "reels"], "when": "now", "consent": True})
    _wait(_idle)
    tt, ig = _rec(project, "c01", "tiktok"), _rec(project, "c01", "reels")
    assert tt["status"] == "uploading" and tt["publish_id"] == "p1" and not tt["upload_done"]
    assert ig["status"] == "uploading" and ig["publish_sent"] and not ig.get("media_id")
    monkeypatch.setattr(PF, "tiktok_send", real_send)
    monkeypatch.setattr(PF, "ig_publish", real_pub)
    acts = _tick()  # the next start / minute: picks both up where they stopped
    assert any(a.startswith("resume:tiktok") for a in acts) and any(a.startswith("resume:reels") for a in acts)
    tt, ig = _rec(project, "c01", "tiktok"), _rec(project, "c01", "reels")
    assert tt["status"] == "published" and ig["status"] == "published" and ig["media_id"] == "MC1"
    assert len(social.state["tiktok_posts"]) == 1 and len(social.state["ig_posts"]) == 1  # never twice
    assert len(social.state["tiktok_uploads"]["p1"]) == 1  # the bytes went once (the first try never sent them)


def test_a_failed_tiktok_attempt_is_replaced_once(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-ttfail")
    _rendered(project, "c01")
    social.state["tt_fail_status"] = "internal_error"
    MP.start(project, "c01", {"platforms": ["tiktok"], "when": "now", "consent": True})
    _wait(_idle)
    r = _rec(project, "c01", "tiktok")
    assert r["status"] == "failed" and r["publish_id"] is None and r["next_try_at"]
    MP.retry(project, "c01", "tiktok")
    _wait(_idle)
    assert _rec(project, "c01", "tiktok")["status"] == "published" and len(social.state["tiktok_posts"]) == 2


def test_daily_cap_is_a_quota_failure_that_waits(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-cap2")
    _rendered(project, "c01")
    social.state["tt_daily_cap"] = 0
    MP.start(project, "c01", {"platforms": ["tiktok"], "when": "now", "consent": True})
    _wait(_idle)
    r = _rec(project, "c01", "tiktok")
    assert r["error"]["kind"] == "quota" and r["next_try_at"] - time.time() > 3 * 3600


def test_planned_posts_go_out_on_time_and_catch_up_after_the_pc_was_off(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-plan")
    _rendered(project, "c01")
    at = datetime.now(timezone.utc) + timedelta(hours=2)
    c = _client()
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok", "reels"], "when": at.isoformat(),
                                                       "consent": True}).json()
    assert r["results"]["tiktok"]["status"] == "scheduled" and r["results"]["reels"]["publish_at"]
    assert not _tick() or not social.state["tiktok_posts"]
    assert MP.clip_states(project, "c01")["tiktok"]["status"] == "scheduled"
    # the PC was off at that time: the next tick (start) posts it and says it came late
    acts = _tick(at + timedelta(hours=5))
    assert any(a.startswith("late:tiktok") for a in acts)
    sts = MP.clip_states(project, "c01")
    assert sts["tiktok"]["status"] == "published" and sts["tiktok"]["late"] and sts["reels"]["late"]
    # planning needs a time ahead
    r = c.post(f"/api/publish/{project.id}/c02", json={"platforms": ["reels"], "when": datetime.now(timezone.utc).isoformat()})
    assert r.status_code == 400
    # unplan
    _rendered(project, "c02")
    c.post(f"/api/publish/{project.id}/c02", json={"platforms": ["reels"], "when": at.isoformat()})
    v = c.post(f"/api/publish/{project.id}/c02/unplan/reels").json()
    assert v["states"]["reels"]["status"] == "idle"


def test_planned_youtube_time_is_shared_with_the_others(yt, social):  # noqa: F811
    project = _project("pub-mp-ytplan")
    _rendered(project, "c01")
    _ready(project, "c01")
    at = (datetime.now(timezone.utc) + timedelta(days=3)).replace(minute=0, second=0, microsecond=0)
    r = _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["youtube", "tiktok", "reels"],
                                                               "when": at.isoformat(), "consent": True}).json()
    yt_at = r["results"]["youtube"]["publish_at"]
    assert r["results"]["youtube"]["status"] == "scheduled"
    assert r["results"]["tiktok"]["publish_at"] == r["results"]["reels"]["publish_at"] == yt_at


def test_cancelled_post_is_final_for_the_loop(social, monkeypatch):
    from sharkyclips.web import app as A, multipost as MP

    project = _project("pub-mp-cancel")
    _rendered(project, "c01")
    gate = threading.Event()
    real = PF.tiktok_creator_info
    monkeypatch.setattr(PF, "tiktok_creator_info", lambda fresh=False: (gate.wait(10) if fresh else True) and real(fresh))
    MP.start(project, "c01", {"platforms": ["tiktok"], "when": "now", "consent": True})
    j = MP.active_job(project.id, "c01", "tiktok")
    A.jobs.cancel(j.id)
    gate.set()
    _wait(lambda: j.finished is not None)  # (cancelled at once; its thread unwinds a moment later)
    assert _rec(project, "c01", "tiktok")["status"] == "cancelled"
    assert not [a for a in _tick() if "tiktok" in a]
    assert not social.state["tiktok_posts"]


def test_unbleeped_swear_blocks_every_platform(social):
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-bleep")
    _rendered(project, "c01")
    data = json.loads((project.dir / "clips.json").read_text())
    data["clips"]["c01"]["edits"] = {"bleep_report": {"audible": 2}}
    write_json_atomic(project.dir / "clips.json", data)
    v = MP.view(project, "c01", ["tiktok", "reels"])
    assert v["problems"][0]["code"] == "bleep_hold" and v["problems"][0]["params"] == {"n": 2}
    with pytest.raises(SharkyClipsError) as e:
        MP.start(project, "c01", {"platforms": ["tiktok", "reels"], "when": "now", "consent": True})
    assert e.value.code == "problems"
    assert not social.state["tiktok_posts"] and not social.state["ig_uploads"]


def test_ai_voice_line_and_labels_on_every_platform(social, monkeypatch):
    from sharkyclips.web import multipost as MP, state

    project = _project("pub-mp-ai")
    _rendered(project, "c01")
    monkeypatch.setattr(state, "file_dub", lambda *a, **k: "en")
    v = MP.view(project, "c01", ["tiktok", "reels"])
    line = v["ai_voice"]["line"]
    assert line and line in v["drafts"]["tiktok"]["caption"] and line in v["drafts"]["reels"]["caption"]
    MP.start(project, "c01", {"platforms": ["tiktok", "reels"], "when": "now", "consent": True})
    _wait(_idle)
    assert social.state["tiktok_posts"][-1]["post_info"]["is_aigc"] is True
    assert social.state["ig_uploads"]["C1"]["form"]["is_ai_generated"] == "true"


# ===================================================================== accounts, quotas, views


def test_accounts_cards_health_and_disconnect_keeps_the_app(social):
    c = _client()
    a = c.get("/api/accounts").json()
    assert a["tiktok"]["connected"] and a["tiktok"]["handle"] == "utkualsirr" and a["tiktok"]["health"]["pill"] == "ok"
    assert a["reels"]["handle"] == "utku.clips" and a["reels"]["encrypted"]
    assert a["youtube"]["health"]["pill"] == "signed_out"
    assert a["quota"]["reels"] == {"used": 0, "total": 50} and a["quota"]["tiktok"]["total"] == PF.TIKTOK_DAILY_CAP
    assert "TT-ACCESS" not in (PF.folder("tiktok") / "token.enc").read_text(encoding="utf-8")
    # an Instagram token near its end: amber; a revoked TikTok refresh: red
    tok = PF.load_token("reels")
    PF.save_token("reels", {**tok, "expires_at": time.time() + 86400})
    assert c.get("/api/accounts").json()["reels"]["health"]["pill"] == "attention"
    tok = PF.load_token("tiktok")
    PF.save_token("tiktok", {**tok, "refresh_token": "REVOKED", "expires_at": time.time() - 5})
    assert "refresh_failed:tiktok" in PF.keep_fresh()
    assert c.get("/api/accounts").json()["tiktok"]["health"] == {
        "pill": "signed_out", "reason": "signed_out", "message": "TikTok refused the refresh: refresh token revoked."}
    # Disconnect: signed out, but the developer app stays for a one-click Reconnect
    a = c.delete("/api/accounts/tiktok").json()
    assert not a["tiktok"]["connected"] and a["tiktok"]["has_app"] and a["tiktok"]["app_id"] == "ck-123"
    assert a["tiktok"]["health"]["reason"] == "not_connected"


def test_instagram_login_with_the_address_pasted_back(social):
    PF.forget("reels")
    c = _client()
    r = c.post("/api/platforms/reels/oauth", json={"app_id": "123", "app_secret": "abc"}).json()
    assert r["redirect_uri"] == "https://localhost:8000/api/platforms/reels/callback" or r["redirect_uri"].startswith("https://localhost")
    from urllib.parse import parse_qs, urlparse

    q = {k: v[0] for k, v in parse_qs(urlparse(r["url"]).query).items()}
    assert q["scope"] == PF.IG_SCOPES and q["client_id"] == "123"
    social.state["ig_codes"]["AQB"] = True
    bad = c.post("/api/platforms/reels/oauth/finish", json={"url": f"{r['redirect_uri']}?code=AQB&state=wrong#_"})
    assert bad.status_code == 400 and "expired" in bad.json()["error"]
    a = c.post("/api/platforms/reels/oauth/finish",
               json={"url": f"{r['redirect_uri']}?code=AQB&state={q['state']}#_"}).json()
    assert a["reels"]["connected"] and a["reels"]["handle"] == "utku.clips"
    assert PF.load_token("reels")["access_token"] == IG_TOKEN


def test_views_and_likes_from_every_platform_feed_the_library_and_calibration(social):
    from sharkyclips import calibration
    from sharkyclips.web import multipost as MP

    project = _project("pub-mp-stats")
    _rendered(project, "c01")
    MP.start(project, "c01", {"platforms": ["tiktok", "reels"], "when": "now", "consent": True})
    _wait(_idle)
    rec = _rec(project, "c01", "tiktok")
    social.state["tt_videos"] = [{"id": "7300", "title": rec["caption"], "create_time": int(time.time()),
                                  "view_count": 1000, "like_count": 50, "share_url": "https://www.tiktok.com/@utkualsirr/video/7300"}]
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    for p in ("tiktok", "reels"):
        PF.record(project, "c01", p, posted_at=old)
    got = MP.sync_stats()
    assert got == {"tiktok": 1, "reels": 1}
    sts = MP.clip_states(project, "c01")
    assert sts["tiktok"]["views"] == 1000 and sts["reels"]["views"] == 321 and sts["reels"]["likes"] == 12
    assert sts["total_views"] == 1321 and sts["tiktok"]["url"].endswith("/video/7300")
    e = calibration.load()["entries"][calibration.entry_key(project.id, "c01")]
    assert e["views"] == 1321 and e["platforms"]["tiktok"]["views"] == 1000
    calibration.delete_entry(calibration.entry_key(project.id, "c01"))


def test_instagram_delete_for_the_real_test(social):
    project = _project("pub-mp-del")
    _rendered(project, "c01")
    from sharkyclips.web import multipost as MP

    MP.start(project, "c01", {"platforms": ["reels"], "when": "now"})
    _wait(_idle)
    assert PF.ig_delete(_rec(project, "c01", "reels")["media_id"]) and social.state["ig_deleted"] == ["MC1"]


def test_facebook_token_posts_and_a_revoked_one_signs_out(social):
    from fake_platforms import FB_IG_ID, FB_TOKEN

    from sharkyclips.web import multipost as MP

    PF.ig_connect(FB_TOKEN)  # 1.2.37: a system-user token from "API setup with unified login"
    project = _project("pub-mp-fb")
    _rendered(project, "c01")
    MP.start(project, "c01", {"platforms": ["reels"], "when": "now"})
    _wait(_idle)
    assert _rec(project, "c01", "reels")["status"] == "published"
    assert ("POST", f"/v24.0/{FB_IG_ID}/media_publish") in social.state["fb_calls"]
    social.state["fb_revoked"] = True
    _rendered(project, "c02")
    MP.start(project, "c02", {"platforms": ["reels"], "when": "now"})
    _wait(_idle)
    assert _rec(project, "c02", "reels")["status"] == "failed"
    assert _client().get("/api/accounts").json()["reels"]["health"]["pill"] == "signed_out"
