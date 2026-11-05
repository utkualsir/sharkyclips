"""1.2.18 TikTok / Instagram Reels: captions, the honest mode (semi by default), TikTok PKCE sign-in
and Direct Post (private until audited), Instagram token check + resumable Reels upload, and the
one-click post API (export with the preset into Downloads, then upload in API mode)."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from fake_platforms import FakePlatforms
from sharkyclips import config, platforms as PF
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic


@pytest.fixture(autouse=True)
def _no_leftover_projects():
    yield
    for d in config.workspace_dir().glob("pf-*"):
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    f = FakePlatforms()
    monkeypatch.setenv("SHARKYCLIPS_TIKTOK_ENDPOINT", f.url)
    monkeypatch.setenv("SHARKYCLIPS_IG_ENDPOINT", f.url)
    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(tmp_path / "dl"))
    for p in ("tiktok", "reels"):
        PF.forget(p)
    config.update(platform_modes={}, easy_platform="youtube")
    yield f
    f.close()
    for p in ("tiktok", "reels"):
        PF.forget(p)
    config.update(platform_modes={})


def _connect_tiktok(fake) -> None:
    url = PF.tiktok_start("ck-123", "cs-456", 8000)
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert q["code_challenge_method"] == "S256" and q["client_key"] == "ck-123"
    assert q["redirect_uri"] == "http://127.0.0.1:8000/api/platforms/tiktok/callback"
    fake.state["codes"]["CODE1"] = q["code_challenge"]
    PF.tiktok_finish("CODE1", q["state"])


def test_caption_keeps_the_platform_limits():
    tags = [f"tag{i}" for i in range(40)] + ["#Tag1", "tag1"]
    tt = PF.caption("tiktok", "Huge play", "What a moment.\n\n#a #b", tags)
    assert tt.startswith("Huge play\n\nWhat a moment.") and tt.count("#") == 10
    assert PF.caption("reels", "Huge play", "", tags).count("#") == 30
    long = PF.caption("tiktok", "x" * 3000, "", ["gg"])
    assert len(long) <= 2200 and long.endswith("#gg")


def test_semi_mode_by_default_and_api_mode_needs_a_connection(fake):
    assert PF.mode("tiktok") == "semi" and PF.mode("reels") == "semi"
    with pytest.raises(SharkyClipsError, match="Connect"):
        PF.set_mode("tiktok", "api")
    _connect_tiktok(fake)
    assert PF.status("tiktok")["account"] == "utku" and PF.mode("tiktok") == "semi"  # still the user's choice
    assert PF.set_mode("tiktok", "api")["mode"] == "api"
    tok = (config.config_dir() / "platforms" / "tiktok" / "token.enc").read_text(encoding="utf-8")
    assert "TT-ACCESS" not in tok  # kept encrypted


def test_tiktok_sign_in_refuses_a_wrong_state(fake):
    PF.tiktok_start("ck", "cs", 8000)
    with pytest.raises(SharkyClipsError, match="expired"):
        PF.tiktok_finish("CODE", "not-the-state")


def test_tiktok_direct_post_is_private_until_the_app_is_audited(fake, tmp_path):
    _connect_tiktok(fake)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"\0" * 300_000)
    res = PF.tiktok_post(video, "Huge play #gaming", poll=0.01)
    post = fake.state["tiktok_posts"][-1]
    assert res["status"] == "published" and res["privacy"] == "self_only"
    assert post["post_info"]["privacy_level"] == "SELF_ONLY" and post["source_info"]["video_size"] == 300_000
    up = fake.state["tiktok_uploads"][post["id"]]
    assert up == [{"range": "bytes 0-299999/300000", "len": 300_000, "type": "video/mp4"}]
    PF.set_audited("tiktok", True)
    fake.state["privacy_options"] = ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]
    assert PF.tiktok_post(video, "again", poll=0.01)["privacy"] == "public_to_everyone"


def test_tiktok_refreshes_an_expired_token(fake, tmp_path):
    _connect_tiktok(fake)
    tok = PF.load_token("tiktok")
    PF.save_token("tiktok", {**tok, "expires_at": time.time() - 10})
    PF.tiktok_call("POST", "/v2/post/publish/creator_info/query/")
    assert fake.state["refreshes"] == 1


def test_instagram_checks_the_token_and_the_account_type(fake):
    with pytest.raises(SharkyClipsError, match="refused"):
        PF.ig_connect("WRONG-TOKEN-xxxxxxxxxxxxxxxxx")
    fake.state["account_type"] = "PERSONAL"
    with pytest.raises(SharkyClipsError, match="Business or Creator"):
        PF.ig_connect("IGTOKEN-0123456789abcdef")
    fake.state["account_type"] = "MEDIA_CREATOR"
    st = PF.ig_connect("IGTOKEN-0123456789abcdef")
    assert st["connected"] and st["account"] == "utku.clips" and st["privacy_note"] == "app_review"


def test_instagram_reels_resumable_upload(fake, tmp_path):
    PF.ig_connect("IGTOKEN-0123456789abcdef")
    video = tmp_path / "r.mp4"
    video.write_bytes(b"\1" * 123_456)
    res = PF.ig_post(video, "Huge play #reels", poll=0.01)
    up = fake.state["ig_uploads"]["C1"]
    assert up["bytes"] == 123_456 and up["file_size"] == "123456" and up["auth"] == "OAuth IGTOKEN-0123456789abcdef"
    assert up["form"]["media_type"] == "REELS" and up["form"]["upload_type"] == "resumable"
    assert res == {"media_id": "MC1", "status": "published", "url": "https://www.instagram.com/reel/MC1/"}


def test_endpoints_may_only_point_at_this_computer(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_TIKTOK_ENDPOINT", "https://evil.example.com")
    with pytest.raises(SharkyClipsError):
        PF.tiktok_api()


# ------------------------------------------------------------------ the one-click API


def _project(pid: str) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    subprocess.run([shutil.which("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=320x180:rate=30:duration=10", "-f", "lavfi", "-i",
                    "sine=frequency=300:sample_rate=48000:duration=10", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "source.mp4")], check=True, capture_output=True)
    write_json_atomic(d / "meta.json", {"title": "Platform test", "duration": 10, "width": 320, "height": 180,
                                        "fps": 30, "audio_codec": "aac", "mode": "gaming"})
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [
        {"start": 1.0, "end": 6.0, "text": "what a shot", "words": [{"start": 1.0 + i, "end": 1.5 + i, "word": f" w{i}"} for i in range(4)]}]})
    cands = [{"id": "c01", "rank": 1, "start": 1.0, "end": 6.0, "duration": 5.0, "peak": 3.0, "text": "what a shot",
              "publish": {"available": True, "titles": ["Huge play"], "hashtags": ["#deltaforce", "#gaming"],
                          "description": "What a moment.\n\n#deltaforce", "language": "en"}}]
    write_json_atomic(d / "highlights.json", {"created_at": "2026-11-01T00:00:00+00:00", "candidates": cands})
    write_json_atomic(d / "review.json", {"highlights_created_at": "2026-11-01T00:00:00+00:00", "accepted": ["c01"]})
    return Project(pid, d)


def _wait_job(jobs, jid: str, timeout: float = 180):
    end = time.time() + timeout
    while jobs.get(jid).status in ("queued", "running"):
        assert time.time() < end, "job timed out"
        time.sleep(0.1)
    return jobs.get(jid)


@pytest.mark.requires_ffmpeg
def test_one_click_semi_and_api(fake, tmp_path):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app, jobs

    project = _project("pf-api")
    c = TestClient(app)
    ov = c.get("/api/platforms").json()
    assert ov["tiktok"]["mode"] == "semi" and ov["chosen"] == "youtube"
    r = c.post(f"/api/platforms/tiktok/clips/{project.id}/c01").json()
    assert r["mode"] == "semi" and r["upload_page"].startswith("https://www.tiktok.com/") and "#deltaforce" in r["caption"]
    j = _wait_job(jobs, r["job"]["id"])
    assert j.status == "done", j.error
    f = Path(j.result["file"])
    assert f.is_file() and f.parent.parent == tmp_path / "dl" and f.name.endswith(" - TikTok.mp4")
    assert f.with_suffix(".txt").read_text(encoding="utf-8").startswith("Huge play")
    assert config.get("easy_platform") == "tiktok"  # remembered
    rec = json.loads((project.dir / "platform_uploads.json").read_text())["c01"]["tiktok"]
    assert rec["status"] == "exported" and rec["mode"] == "semi"
    probe = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(f)], capture_output=True, text=True)
    assert probe.stdout.strip() == "1080,1920"
    # API mode: export, then the upload job in the network lane
    PF.ig_connect("IGTOKEN-0123456789abcdef")
    assert c.put("/api/platforms/reels/mode", json={"mode": "api"}).json()["mode"] == "api"
    r = c.post(f"/api/platforms/reels/clips/{project.id}/c01").json()
    assert r["mode"] == "api"
    _wait_job(jobs, r["job"]["id"])
    up = next(x for x in jobs.jobs() if x.kind == "platform_upload" and x.project_id == project.id)
    up = _wait_job(jobs, up.id)
    assert up.status == "done", up.error
    rec = json.loads((project.dir / "platform_uploads.json").read_text())["c01"]["reels"]
    assert rec["status"] == "published" and rec["url"].startswith("https://www.instagram.com/reel/")
    view = c.get(f"/api/easy/projects/{project.id}").json()
    assert view["clips"][0]["platforms"]["reels"]["status"] == "published"
    # reveal only inside the downloads folder
    assert c.post("/api/platforms/reveal", json={"file": str(f)}).status_code == 200
    assert c.post("/api/platforms/reveal", json={"file": str(tmp_path / "x.mp4")}).status_code == 400
