"""1.2.7 publishing: encrypted token, plan / slots / daily limit, the scheduler against a fake
YouTube API server (upload, schedule, quota, failures, cancel, token refresh, private lock),
covers and the Library API."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import threading
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
import requests

from fake_youtube import FakeYouTube
from sharkyclips import config, cover, export, publishing as P, secretstore, youtube
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic


@contextlib.contextmanager
def _client():
    """An API client without the server's startup (no governor / publish loop in tests)."""
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    yield TestClient(app)


@pytest.fixture(autouse=True)
def _no_leftover_projects():
    yield
    for d in config.workspace_dir().glob("pub-*"):
        shutil.rmtree(d, ignore_errors=True)


def _wait(pred, timeout: float = 120.0) -> None:
    ev = threading.Event()
    end = datetime.now().timestamp() + timeout
    while not pred():
        if datetime.now().timestamp() > end:
            from sharkyclips.web import app as A

            raise AssertionError("timed out; jobs: " + repr([(j.kind, j.status, j.stage, j.paused, j.error)
                                                             for j in A.jobs.jobs() if j.status in ("queued", "running")]))
        ev.wait(0.05)


# ===================================================================== secret store


def test_secret_store_roundtrip_tamper_and_protection(tmp_path):
    path = tmp_path / "s" / "token.enc"
    how = secretstore.save(path, {"refresh_token": "R-secret", "n": 1})
    raw = path.read_text(encoding="utf-8")
    assert "R-secret" not in raw
    assert secretstore.load(path) == {"refresh_token": "R-secret", "n": 1}
    if os.name == "nt":
        assert how == "dpapi" and (path.parent / "key.dpapi").is_file() and not (path.parent / "key.bin").exists()
    import base64
    import json

    env = json.loads(raw)
    blob = bytearray(base64.b64decode(env["data"]))
    blob[20] ^= 1  # one flipped bit: the tag check refuses it
    env["data"] = base64.b64encode(bytes(blob)).decode()
    path.write_text(json.dumps(env), encoding="utf-8")
    assert secretstore.load(path) is None
    secretstore.save(path, {"a": 1})
    secretstore.forget_key(path.parent)  # key gone (other PC / account): counts as missing
    assert secretstore.load(path) is None


def test_old_plain_token_is_encrypted_on_first_read():
    youtube._forget_token()
    youtube._write("token.json", {"access_token": "a", "refresh_token": "r", "expires_at": 9e12, "scope": youtube.SCOPE_MANAGE})
    assert youtube.connected() and youtube.can_manage()
    assert not (youtube.folder() / "token.json").exists() and (youtube.folder() / "token.enc").is_file()
    youtube._forget_token()
    assert not youtube.connected()


# ===================================================================== plan maths


@pytest.fixture
def cfg():
    keys = ("publish_daily_limit", "publish_times", "publish_learn_times", "publish_auto", "publish_defaults",
            "youtube_daily_quota", "performance_mode")
    old = {k: config.load().get(k) for k in keys}
    config.update(performance_mode="turbo")  # this PC's games / videos must not pause the test's jobs
    yield
    c = config.load()
    for k, v in old.items():
        if v is None:
            c.pop(k, None)
        else:
            c[k] = v
    config.save(c)


def _local(day_offset: int, hhmm: str, base: datetime | None = None) -> datetime:
    base = base or datetime.now().astimezone()
    return P.at_local(base.date() + timedelta(days=day_offset), hhmm)


def test_auto_plan_spreads_at_the_daily_limit_and_best_times(cfg):
    config.update(publish_daily_limit=3, publish_times=["12:00", "18:00", "21:00"], publish_learn_times=False)
    now = _local(1, "08:00").astimezone(timezone.utc)  # tomorrow 08:00: today is out of reach
    keys = [f"p:c{i}" for i in range(7)]
    plan = P.auto_plan(keys, {}, now)
    got = [plan[k].astimezone() for k in keys]
    assert [t.strftime("%H:%M") for t in got] == ["12:00", "18:00", "21:00"] * 2 + ["12:00"]
    days = [t.date() for t in got]
    assert days[:3] == [now.astimezone().date()] * 3 and days[3:6] == [days[0] + timedelta(days=1)] * 3
    assert days[6] == days[0] + timedelta(days=2)


def test_full_day_moves_to_the_next_free_slot_and_strict_refuses(cfg):
    config.update(publish_daily_limit=2, publish_times=["12:00", "18:00"], publish_learn_times=False)
    now = _local(1, "07:00").astimezone(timezone.utc)
    rel = {"p:a": _local(1, "12:00"), "p:b": _local(1, "18:00")}
    t, moved = P.place("p:c", _local(1, "20:00"), rel, now=now)
    assert moved and t == _local(2, "12:00")
    with pytest.raises(SharkyClipsError, match="full"):
        P.place("p:c", _local(1, "20:00"), rel, now=now, strict=True)
    with pytest.raises(SharkyClipsError, match="15 minutes"):
        P.place("p:c", now + timedelta(minutes=5), rel, now=now)
    # its own slot doesn't count against itself (reschedule within the same day)
    t2, moved2 = P.place("p:a", _local(1, "13:00"), rel, now=now)
    assert not moved2 and t2 == _local(1, "13:00")
    # too close to another release (45 min gap) on a day with room
    config.update(publish_daily_limit=5)
    t3, moved3 = P.place("p:c", _local(1, "12:20"), rel, now=now)
    assert moved3 and abs((t3 - _local(1, "12:00")).total_seconds()) >= 45 * 60


def test_limit_never_above_what_the_quota_can_upload(cfg):
    config.update(publish_daily_limit=20, youtube_daily_quota=10_000)
    assert P.quota_capacity() == 5 and P.effective_limit() == 5
    assert len(P.best_times()["times"]) == 5


def test_releases_count_manual_uploads_but_not_private_ones():
    now = datetime.now(timezone.utc)
    ups = {"p:a": {"publish_at": "2030-01-01T12:00:00Z", "privacy": "private"},
           "p:b": {"requested_privacy": "public", "privacy": "public", "uploaded_at": now.isoformat()},
           "p:c": {"requested_privacy": "private", "privacy": "private", "uploaded_at": now.isoformat()}}
    items = {"p:d": {"publish_at": "2030-01-02T12:00:00+00:00"}, "p:e": {"now": True, "meta": {"privacy": "public"}},
             "p:a": {"publish_at": "2031-01-01T00:00:00+00:00"}}
    rel = P.releases(items, ups, now)
    assert set(rel) == {"p:a", "p:b", "p:d", "p:e"}
    assert rel["p:a"].year == 2030  # the live upload wins over a stale plan entry


def test_best_times_learn_from_calibration(cfg):
    config.update(publish_daily_limit=2, publish_times=["12:00", "18:00"], publish_learn_times=True)
    entries = []
    for i in range(12):
        hour = 20 if i % 2 else 9
        t = _local(-10 - i, f"{hour:02d}:05").astimezone(timezone.utc)
        entries.append({"published_at": t.isoformat(), "views": 5000 if hour == 20 else 100})
    bt = P.best_times(2, entries)
    assert bt["source"] == "learned" and bt["times"][0] == "09:00" or "20:00" in bt["times"]
    assert bt["times"] == sorted(bt["times"]) and "20:00" in bt["times"]
    few = P.best_times(2, entries[:3])
    assert few["source"] == "custom" or few["source"] == "default"
    assert few["times"] == ["12:00", "18:00"]


def test_failures_back_off_then_need_attention():
    item = P.new_item("p", "c", {})
    item["publish_at"] = "2030-01-01T00:00:00+00:00"
    now = datetime(2029, 1, 1, tzinfo=timezone.utc)
    net = SharkyClipsError("network down")
    delays = []
    for _ in range(len(P.BACKOFF_S)):
        item = P.after_failure(item, net, now)
        assert not item["attention"] and item["error"]["fix"] == "retry"
        delays.append((P.parse(item["next_try_at"]) - now).total_seconds())
    assert delays == P.BACKOFF_S
    item = P.after_failure(item, net, now)
    assert item["attention"] and item["next_try_at"] is None
    q = youtube._err("quota", reason="quotaExceeded")
    fresh = P.after_failure(P.new_item("p", "c", {}), q, now)
    assert not fresh["attention"] and fresh["attempts"] == 0 and fresh["error"]["fix"] == "wait"
    tok = youtube._err("signed out", reason="signed_out")
    assert P.after_failure(P.new_item("p", "c", {}), tok, now)["error"]["fix"] == "reconnect"
    bad = youtube._err("bad title", reason="invalidTitle", status=400)
    out = P.after_failure(P.new_item("p", "c", {}), bad, now)
    assert out["attention"] and out["error"]["fix"] == "edit"


def test_description_hashtags_and_tags():
    text, tags = P.split_hashtags("Great play here.\nSecond line.\n\n#deltaforce #gaming")
    assert text == "Great play here.\nSecond line." and tags == ["#deltaforce", "#gaming"]
    out = P.compose_description(text, ["deltaforce", "#gaming"], "Music: X by Y")
    assert out.endswith("#deltaforce #gaming") and "Music: X by Y" in out
    tags = P.suggest_tags({"hashtags": ["#deltaforce", "#clutch"] + [f"#tag{i}" * 8 for i in range(40)]},
                          {"game": "Delta Force"}, "gaming")
    assert "deltaforce" in tags and sum(len(t) + 1 for t in tags) <= 500


def test_face_scoring_without_faces_and_rank():
    frames = [np.full((96, 128, 3), 40 + i, np.uint8) for i in range(5)]
    out = cover.score_faces(frames, np.linspace(0, 1, 5))
    assert all(not s["face"] and s["score"] == 0 for s in out)
    r = cover._rank(np.array([3.0, 1.0, 2.0]))
    assert list(r) == [1.0, 0.0, 0.5]


# ===================================================================== project + fake server


SECONDS = 24.0


def _project(pid: str, n: int = 3) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    ff = shutil.which("ffmpeg")
    if ff:
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"testsrc2=size=320x180:rate=30:duration={SECONDS}", "-f", "lavfi", "-i",
                        f"sine=frequency=300:sample_rate=48000:duration={SECONDS}", "-c:v", "libx264",
                        "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "source.mp4")],
                       check=True, capture_output=True)
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(d / "source.mp4"), "-ac", "1", "-ar",
                        "16000", str(d / "audio.wav")], check=True, capture_output=True)
    else:
        (d / "source.mp4").write_bytes(b"\0" * 1000)
    write_json_atomic(d / "meta.json", {"title": f"Stream {pid}", "duration": SECONDS, "width": 320, "height": 180,
                                        "fps": 30, "audio_codec": "aac", "mode": "gaming"})
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [
        {"start": 0.5, "end": 20.0, "words": [{"start": 0.5 + i, "end": 1.2 + i, "word": f" word{i}"} for i in range(19)]}]})
    cands = []
    for i in range(n):
        s = 1.0 + i * 7.0
        cands.append({"id": f"c{i + 1:02d}", "rank": i + 1, "start": s, "end": s + 5.0, "duration": 5.0, "peak": s + 2.5,
                      "score": 0.9 - i * 0.1, "text": f"clip number {i + 1}",
                      "reasons": [{"code": "loudness_spike", "t": s + 2.5, "strength": 1}],
                      "publish": {"available": True, "viral_score": 80 - i, "viral_label": "high",
                                  "titles": [f"Huge play {i + 1}", f"Alt title {i + 1}"],
                                  "hashtags": ["#deltaforce", "#gaming", "#clutch"],
                                  "description": f"What a moment {i + 1}.\n\n#deltaforce #gaming #clutch",
                                  "cover_text": "NO WAY", "hook_text": "watch this", "language": "en"}})
    write_json_atomic(d / "highlights.json", {"created_at": "2026-10-01T00:00:00+00:00", "candidates": cands})
    write_json_atomic(d / "review.json", {"highlights_created_at": "2026-10-01T00:00:00+00:00",
                                          "accepted": [c["id"] for c in cands]})
    return Project(pid, d)


def _ready(project: Project, cid: str) -> str:
    """Pretend the clip was exported for its plan (no ffmpeg needed): a dummy MP4 + prep."""
    from sharkyclips.web import publishing as WP

    cand = next(c for c in __import__("json").loads((project.dir / "highlights.json").read_text())["candidates"]
                if c["id"] == cid)
    item = WP._item_for(project, cid)
    P.put(item)
    root = export.exports_root(project)
    root.mkdir(parents=True, exist_ok=True)
    name = f"{cand['rank']:02d}_{cid}_youtube_shorts_mp4_h264.mp4"
    (root / name).write_bytes(os.urandom(300_000))
    export._save_entry(project, {"id": name[:-4], "clip_id": cid, "rank": cand["rank"], "format": "mp4_h264",
                                 "preset": "youtube_shorts", "request": {}, "duration": 5.0, "encoder": None, "seconds": 0,
                                 "files": [export._file_entry(root / name, "media", "video/mp4")], "created_at": "x",
                                 "frame": "vertical", "warnings": []})
    step, info = WP.next_step(project, cand, P.get(P.key_of(project.id, cid)))
    assert step == "export"
    it = P.get(P.key_of(project.id, cid))
    P.patch(P.key_of(project.id, cid), prep={**(it.get("prep") or {}), "sig": info["sig"], "file": name})
    return name


@pytest.fixture
def yt(monkeypatch, cfg):
    """A connected channel on the fake server, an empty plan, no leftover jobs."""
    from sharkyclips.web import app as A

    fake = FakeYouTube()
    monkeypatch.setenv("SHARKYCLIPS_YT_ENDPOINT", fake.start())
    for name in ("token.enc", "token.json", "client.json", "quota.json", "sessions.json", "locked.json",
                 "unlocked.json", "playlists.json", "sync.json"):
        (youtube.folder() / name).unlink(missing_ok=True)
    P.plan_path().unlink(missing_ok=True)
    _clean_projects()
    config.update(publish_daily_limit=3, publish_times=["12:00", "18:00", "21:00"], publish_learn_times=False,
                  youtube_daily_quota=10_000)
    youtube.set_client({"installed": {"client_id": "1.apps.googleusercontent.com", "client_secret": "s"}})
    url = youtube.auth_url("http://127.0.0.1:8123/")
    loc = requests.get(url, allow_redirects=False, timeout=10).headers["Location"]
    q = dict(__import__("urllib.parse").parse.parse_qsl(loc.split("?", 1)[1]))
    st = youtube.finish_auth(q["code"], q["state"])
    assert st["connected"] and st["manage"] and st["channel"]["title"] == "Fake Channel"
    yield fake
    _wait(lambda: not any(j.status in ("queued", "running") for j in A.jobs.jobs()), 60)
    fake.stop()
    youtube._forget_token()
    P.plan_path().unlink(missing_ok=True)
    _clean_projects()


def _clean_projects() -> None:
    for d in config.workspace_dir().glob("pub-*"):
        shutil.rmtree(d, ignore_errors=True)


def _idle():
    from sharkyclips.web import app as A

    return not any(j.status in ("queued", "running") for j in A.jobs.jobs())


def _drive(max_ticks: int = 20, now=None) -> list[str]:
    """Tick the publish loop and let its jobs run until nothing is left to do."""
    from sharkyclips.web.publishing import scheduler

    acts: list[str] = []
    for _ in range(max_ticks):
        a = [x for x in scheduler.tick(now) if not x.startswith(("stats", "hooks"))]
        _wait(_idle)
        acts += a
        if not a:
            break
    return acts


# ===================================================================== fake server flows


def test_fake_server_upload_update_delete_playlist_and_refresh(yt, tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(os.urandom(600_000))
    body = youtube.build_body("Title", "Desc", ["a"], "private", (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
                              False, "20", "en")
    yt.fail_chunks = 1
    yt.expire_next = 1  # the insert answers 401 once: refreshed and asked again
    old = youtube.CHUNK
    youtube.CHUNK = 256 * 1024
    try:
        res = youtube.upload(video, body, "k-1")
    finally:
        youtube.CHUNK = old
    vid = res["id"]
    assert yt.videos[vid]["bytes"] == 600_000 and yt.refreshes == 1
    assert yt.videos[vid]["status"]["privacyStatus"] == "private" and yt.videos[vid]["status"]["publishAt"].endswith("Z")
    pl = youtube.create_playlist("Best of")
    youtube.add_to_playlist(pl["id"], vid)
    assert yt.playlist_items == [(pl["id"], vid)] and youtube.playlists(refresh=True)[0]["title"] == "Best of"
    youtube.update_video(vid, status={"privacyStatus": "public", "selfDeclaredMadeForKids": False})
    assert yt.videos[vid]["status"]["privacyStatus"] == "public"
    assert youtube.delete_video(vid) is True and vid not in yt.videos
    assert youtube.delete_video(vid) is False  # already gone
    used = youtube.quota_used()
    assert used >= youtube.COST["upload"] + 3 * 50


def test_quota_exceeded_on_the_server_waits_for_the_reset(yt):
    from sharkyclips.web import app as A

    project = _project("pub-quota", 1)
    _ready(project, "c01")
    key = P.key_of(project.id, "c01")
    A.app  # noqa: B018 - make sure routes are loaded
    from sharkyclips.web.publishing import schedule

    schedule([{"project_id": project.id, "clip_id": "c01"}], "auto")
    yt.quota_exceeded = True
    acts = _drive(2)
    assert f"upload:{key}" in acts
    it = P.get(key)
    assert not it["attention"] and it["error"]["fix"] == "wait" and it["attempts"] == 0
    assert P.parse(it["next_try_at"]) > datetime.now(timezone.utc) + timedelta(minutes=1)
    assert youtube.quota_view()["uploads_left"] == 0  # Google said it's gone: counter shows 0
    assert not yt.videos


def test_local_quota_limit_holds_uploads_back(yt):
    project = _project("pub-lq", 1)
    _ready(project, "c01")
    key = P.key_of(project.id, "c01")
    from sharkyclips.web.publishing import schedule

    schedule([{"project_id": project.id, "clip_id": "c01"}], "auto")
    youtube.spend(youtube.daily_quota() - 1000)
    acts = _drive(2)
    assert acts == [f"quota:{key}"] and not yt.videos
    assert P.parse(P.get(key)["next_try_at"]) == P.parse(youtube.next_reset().isoformat())


def test_network_failures_retry_with_backoff_then_need_attention_and_fix(yt):

    project = _project("pub-net", 1)
    _ready(project, "c01")
    key = P.key_of(project.id, "c01")
    from sharkyclips.web.publishing import schedule

    schedule([{"project_id": project.id, "clip_id": "c01"}], "auto")
    yt.fail_inserts = 100
    now = datetime.now(timezone.utc)
    for i in range(len(P.BACKOFF_S) + 1):
        _drive(1, now)
        it = P.get(key)
        assert it["attempts"] == i + 1
        if it["attention"]:
            break
        now = P.parse(it["next_try_at"]) + timedelta(seconds=1)
    it = P.get(key)
    assert it["attention"] and it["error"]["fix"] == "retry" and not yt.videos
    with _client() as c:
        row = next(r for r in c.get("/api/library").json()["rows"] if r["key"] == key)
        assert row["status"] == "failed" and row["error"]["fix"] == "retry"
        yt.fail_inserts = 0
        assert c.post(f"/api/library/{project.id}/c01/retry").status_code == 200
    _drive(3)
    assert len(yt.videos) == 1 and P.get(key)["video_id"] in yt.videos


def test_revoked_access_needs_a_reconnect(yt):
    project = _project("pub-tok", 1)
    _ready(project, "c01")
    key = P.key_of(project.id, "c01")
    from sharkyclips.web.publishing import schedule

    schedule([{"project_id": project.id, "clip_id": "c01"}], "auto")
    yt.revoke_refresh = True
    youtube._expire_access()
    acts = _drive(1)
    assert f"upload:{key}" in acts
    it = P.get(key)
    assert it["attention"] and it["error"]["fix"] == "reconnect"
    assert not youtube.connected()  # the dead token is gone; Settings asks to connect again


@pytest.mark.requires_ffmpeg
def test_full_schedule_flow_never_twice_reschedule_cancel_publish_now(yt):

    config.update(publish_daily_limit=2, publish_times=["12:00", "18:00"])
    project = _project("pub-flow", 3)
    keys = [P.key_of(project.id, f"c0{i}") for i in (1, 2, 3)]
    with _client() as c:
        lib = c.get("/api/library").json()
        rows = [r for r in lib["rows"] if r["project_id"] == project.id]
        assert len(rows) == 3 and {r["status"] for r in rows} == {"draft"}
        setup = c.get(f"/api/library/{project.id}/c01/setup").json()
        m = setup["meta"]
        assert m["title"] == "Huge play 1" and m["description"] == "What a moment 1." and m["category"] == "20"
        assert m["hashtags"] == ["deltaforce", "gaming", "clutch"] and "deltaforce" in m["tags"]
        assert m["preset"] == "youtube_shorts" and m["made_for_kids"] is False
        # a cover with the cover burned into the Short's first frame, and a playlist
        pl = c.post("/api/youtube/playlists", json={"title": "Clips"}).json()
        m2 = {**m, "title": "My own title", "cover": {"kind": "peak", "text": "BOOM", "burn": True},
              "playlist": {"id": pl["id"], "title": "Clips"}}
        assert c.put(f"/api/library/{project.id}/c01", json={"meta": m2}).status_code == 200
        assert config.get("publish_defaults")["cover"]["burn"] is True  # remembered for the next clip

        clips = [{"project_id": project.id, "clip_id": f"c0{i}"} for i in (1, 2, 3)]
        dry = c.post("/api/library/schedule", json={"clips": clips, "mode": "auto", "dry_run": True}).json()
        assert len(dry["planned"]) == 3 and P.get(keys[1]) is None  # dry run saves nothing
        days: dict = {}
        for p in dry["planned"]:
            t = P.parse(p["publish_at"]).astimezone()
            assert t.strftime("%H:%M") in ("12:00", "18:00")
            days[t.date()] = days.get(t.date(), 0) + 1
        assert max(days.values()) <= 2
        res = c.post("/api/library/schedule", json={"clips": clips, "mode": "auto"}).json()
        planned = {p["key"]: p["publish_at"] for p in res["planned"]}

    acts = _drive(20)
    assert any(a.startswith("export:") for a in acts) and any(a.startswith("burn:") for a in acts)
    assert sum(a.startswith("upload:") for a in acts) == 3
    assert len(yt.videos) == 3  # each clip exactly once
    by_title = {v["snippet"]["title"]: v for v in yt.videos.values()}
    v1 = by_title["My own title"]
    assert v1["status"]["privacyStatus"] == "private"
    assert P.parse(v1["status"]["publishAt"]) == P.parse(planned[keys[0]])
    assert v1["snippet"]["description"].endswith("#deltaforce #gaming #clutch")
    vid1 = P.get(keys[0])["video_id"]
    assert (pl["id"], vid1) in yt.playlist_items
    burned = next(e for e in export.load_registry(project) if e.get("publish_cover"))
    assert burned["clip_id"] == "c01"

    # nothing is uploaded twice: ticking again does nothing, scheduling again is skipped
    assert _drive(3) == []
    with _client() as c:
        again = c.post("/api/library/schedule", json={"clips": clips[:1], "mode": "auto"}).json()
        assert again["skipped"] == [{"key": keys[0], "reason": "on_youtube"}]
        rows = {r["key"]: r for r in c.get("/api/library").json()["rows"]}
        assert all(rows[k]["status"] == "scheduled" and rows[k]["step"] == "uploaded" for k in keys)

        # reschedule (calendar drag) changes YouTube's publishAt; a full day is refused
        target = P.parse(planned[keys[2]]).astimezone() + timedelta(days=5)
        target = P.at_local(target.date(), "18:00")
        r = c.post(f"/api/library/{project.id}/c01/reschedule", json={"publish_at": target.isoformat()})
        assert r.status_code == 200, r.text
        assert P.parse(yt.videos[vid1]["status"]["publishAt"]) == target
        busy_day = P.parse(planned[keys[1]]).astimezone().date()
        config.update(publish_daily_limit=1)  # c02's day is full now
        r = c.post(f"/api/library/{project.id}/c01/reschedule",
                   json={"publish_at": P.at_local(busy_day, "21:00").isoformat()})
        assert r.status_code == 400 and "full" in r.json()["error"]
        assert P.parse(yt.videos[vid1]["status"]["publishAt"]) == target  # unchanged
        config.update(publish_daily_limit=2)

        # cancel deletes the scheduled upload from YouTube; the clip is a draft again
        vid3 = P.get(keys[2])["video_id"]
        r = c.post(f"/api/library/{project.id}/c03/cancel").json()
        assert r["deleted"] and vid3 not in yt.videos
        rows = {x["key"]: x for x in c.get("/api/library").json()["rows"]}
        assert rows[keys[2]]["status"] == "draft"

        # publish now: uploads at once with the chosen privacy (counts on today's limit)
        config.update(publish_daily_limit=5)
        r = c.post(f"/api/library/{project.id}/c03/publish-now")
        assert r.status_code == 200, r.text
    _drive(5)
    vid3b = P.get(keys[2])["video_id"]
    assert vid3b and yt.videos[vid3b]["status"]["privacyStatus"] == "public"
    assert youtube.lock_state()["state"] == "unlocked"  # it really went public: no lock
    # an uploaded, still scheduled clip can go out now (videos.update)
    with _client() as c:
        r = c.post(f"/api/library/{project.id}/c02/publish-now")
        assert r.status_code == 200, r.text
        vid2 = P.get(keys[1])["video_id"]
        assert yt.videos[vid2]["status"]["privacyStatus"] == "public" and "publishAt" not in yt.videos[vid2]["status"]
        # editing an uploaded clip's details goes to YouTube too
        meta = c.get(f"/api/library/{project.id}/c02/setup").json()["meta"]
        r = c.put(f"/api/library/{project.id}/c02", json={"meta": {**meta, "title": "Renamed"}})
        assert r.json()["applied"] == "youtube" and yt.videos[vid2]["snippet"]["title"] == "Renamed"


@pytest.mark.requires_ffmpeg
def test_locked_project_is_detected_and_unlock_hides_the_banner(yt):

    from sharkyclips.web.app import submit_youtube_stats

    project = _project("pub-lock", 2)
    yt.locked = True
    assert youtube.lock_state()["state"] == "unknown"  # nothing uploaded yet: the banner shows
    with _client() as c:
        assert c.post(f"/api/library/{project.id}/c01/publish-now").status_code == 200
    _drive(5)
    vid = P.get(P.key_of(project.id, "c01"))["video_id"]
    assert yt.videos[vid]["status"]["privacyStatus"] == "private"
    assert youtube.lock_state()["state"] == "locked"
    with _client() as c:
        row = next(r for r in c.get("/api/library").json()["rows"] if r["key"] == P.key_of(project.id, "c01"))
        assert row["status"] == "locked"
        assert c.get("/api/youtube").json()["lock"]["state"] == "locked"
    # Google approved the audit: the video goes public, the next views sync notices
    yt.locked = False
    yt.videos[vid]["status"]["privacyStatus"] = "public"
    yt.videos[vid]["statistics"] = {"viewCount": "1234", "likeCount": "56"}
    yt.videos[vid]["snippet"]["publishedAt"] = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    job = submit_youtube_stats(force=True)
    _wait(lambda: job.status in ("done", "error"))
    assert job.status == "done", job.error
    assert youtube.lock_state()["state"] == "unlocked"
    # the views calibrate the viral score (public for more than 48 h)
    from sharkyclips import calibration

    assert calibration.entries_for(project.id)["c01"]["views"] == 1234
    # and the upload carries its hook style, so the A/B bandit learns from it too
    from sharkyclips import abtest
    from sharkyclips.web import state

    up = state.live_upload(project, "c01")
    assert up["hook_style"] and up["views"] == 1234
    state.patch_upload(project, "c01", vid, {"published_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()})
    assert any(cid == "c01" for _p, cid, _u in abtest.due_uploads([project]))
    calibration.delete_entry(calibration.entry_key(project.id, "c01"))


@pytest.mark.requires_ffmpeg
def test_missed_slot_moves_to_the_next_free_one(yt):
    project = _project("pub-miss", 1)
    _ready(project, "c01")
    key = P.key_of(project.id, "c01")
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    it = P.get(key)
    P.put({**it, "publish_at": past})
    from sharkyclips.web.publishing import scheduler

    acts = scheduler.tick()
    assert f"moved:{key}" in acts
    it = P.get(key)
    assert it["moved_from"] == past and P.parse(it["publish_at"]) > datetime.now(timezone.utc)
    _wait(_idle)


# ===================================================================== covers


@pytest.mark.requires_ffmpeg
def test_cover_images_and_first_frame_burn(tmp_path):
    project = _project("pub-cover", 1)
    cand = __import__("json").loads((project.dir / "highlights.json").read_text())["candidates"][0]
    wide = cover.make_cover(project, cand, None, "peak", "No way", "wide", "en")
    tall = cover.make_cover(project, cand, None, "action", "No way", "tall", "en")
    import cv2

    assert cv2.imread(str(wide)).shape[:2] == (720, 1280) and cv2.imread(str(tall)).shape[:2] == (1920, 1080)
    assert cover.make_cover(project, cand, None, "peak", "No way", "wide", "en") == wide  # cached
    assert cover.best_face(project, cand, None) is None  # test pattern: no face
    with pytest.raises(SharkyClipsError):
        cover.make_cover(project, cand, None, "face", "x", "wide", "en")
    # a 2 s clip with the cover as its first 0.3 s
    ff = shutil.which("ffmpeg")
    clip = tmp_path / "clip.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=blue:s=360x640:r=30:d=2", "-f", "lavfi",
                    "-i", "sine=duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)],
                   check=True)
    red = tmp_path / "red.jpg"
    cv2.imwrite(str(red), np.full((1920, 1080, 3), (0, 0, 255), np.uint8))
    out = cover.burn_first_frame(clip, red, tmp_path / "out.mp4", bitrate_k=2000)
    w, h, dur = cover._probe_size(out)
    assert (w, h) == (360, 640) and abs(dur - cover._probe_size(clip)[2]) < 0.1

    def frame(t):
        raw = subprocess.run([ff, "-loglevel", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", "-vf", "scale=8:8",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(8, 8, 3).mean(axis=(0, 1))

    first, later = frame(0.0), frame(1.0)
    assert first[0] > 150 and first[2] < 100  # red cover
    assert later[2] > 150 and later[0] < 100  # the blue clip


# ===================================================================== settings + endpoint mapping


def test_settings_api_and_meta_validation(cfg):

    with _client() as c:
        s = c.put("/api/library/settings", json={"daily_limit": 4, "times": ["9:00", "21:30", "bad"], "learn_times": False}).json()
        assert s["daily_limit"] == 4 and s["times"] == ["09:00", "21:30"]
        assert len(s["best_times"]["times"]) == 4
        assert c.put("/api/library/settings", json={"times": []}).status_code == 400
    from sharkyclips.web.publishing import clean_meta

    base = {"title": "x", "cover": {"kind": "peak", "text": "", "burn": False}}
    out = clean_meta({"title": "<b>Hi</b>", "tags": ["t" * 90] * 20, "category": "999", "privacy": "nope",
                      "hashtags": ["#a b", "a b", ""]}, base)
    assert out["title"] == "‹b›Hi‹/b›" and out["category"] == "20" and out["privacy"] == "public"
    assert sum(len(t) + 1 for t in out["tags"]) <= 500 and out["hashtags"] == ["ab"]
    with pytest.raises(SharkyClipsError):
        clean_meta({"title": "  "}, base)


def test_endpoint_override_is_loopback_only(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_YT_ENDPOINT", "http://127.0.0.1:9999")
    assert youtube.url(youtube.API) == "http://127.0.0.1:9999/www/youtube/v3"
    assert youtube.url(youtube.TOKEN_URL) == "http://127.0.0.1:9999/oauth2/token"
    monkeypatch.setenv("SHARKYCLIPS_YT_ENDPOINT", "http://evil.example.com")
    with pytest.warns(UserWarning):
        assert youtube.url(youtube.API) == youtube.API

