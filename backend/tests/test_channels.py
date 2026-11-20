"""Channel monitoring (1.2.57): detection, catch-up, gates, duplicates, the import hooks, the API.

Fake endpoints (fake_channels.py) and a fake clock; no network, no real downloads.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from sharkyclips import channels as C, config
from sharkyclips.project import project_for_id, write_json_atomic
from sharkyclips.web import channels_api as CA

from fake_channels import FakePlatforms

T0 = 1_790_000_000.0  # 2026-09-21: the "now" of the tests
H = 3600.0


@pytest.fixture()
def fake(monkeypatch):
    f = FakePlatforms()
    monkeypatch.setattr(C, "HTTP", f)
    monkeypatch.setattr(C, "yt_lookup", f.yt_lookup)
    monkeypatch.setenv("SHARKYCLIPS_METERED", "0")
    monkeypatch.setenv("SHARKYCLIPS_GAME_RUNNING", "")
    monkeypatch.setattr(C, "disk_ok", lambda duration, folder=None: (True, 500 * 1024 ** 3, 1))
    C.state_path().unlink(missing_ok=True)
    started: list[dict] = []

    def submit(url, mode, language, title, cleanup=None, extra=None):
        started.append({"url": url, "mode": mode, "title": title, **(extra or {})})
        return SimpleNamespace(id=f"job{len(started)}")

    from sharkyclips.web import app as A

    monkeypatch.setattr(A, "submit_import", submit)
    running: set = set()
    monkeypatch.setattr(CA, "_running", lambda: set(running))
    notices: list[tuple] = []
    monkeypatch.setattr(CA, "notify", lambda kind, key, url=None, telegram=True, **kw: notices.append((kind, key, kw)))
    mon = CA.Monitor()
    mon._resumed = True
    f.started, f.running, f.notices, f.mon = started, running, notices, mon
    yield f
    C.state_path().unlink(missing_ok=True)


def add(fake, text="kick.com/utkualsirr", now=T0, own=True, **opts) -> dict:
    info = C.lookup(text)
    with C._lock:
        data = C.load()
        ch = C.new_channel(info, own=own, now=now, **opts)
        data["channels"][ch["id"]] = ch
        C.save(data)
    fake.mon.poll_one(ch["id"], now)
    return C.load()["channels"][ch["id"]]


def vods(status: str | None = None) -> dict:
    v = C.load()["vods"]
    return {k: x for k, x in v.items() if status is None or x.get("status") == status}


# ===================================================================== parsing


@pytest.mark.parametrize("text,platform,want", [
    ("kick.com/utkualsirr", None, ("kick", "utkualsirr")),
    ("https://kick.com/UtkuAlsirr/videos", None, ("kick", "utkualsirr")),
    ("utkualsirr", None, ("kick", "utkualsirr")),
    ("https://www.twitch.tv/SomeOne", None, ("twitch", "someone")),
    ("someone", "twitch", ("twitch", "someone")),
    ("youtube.com/@Sharky.Clips", None, ("youtube", "@Sharky.Clips")),
    ("https://www.youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw", None, ("youtube", "UC-lHJZR3Gqxm24_Vd_AJ5Yw")),
    ("sharky", "youtube", ("youtube", "@sharky")),
])
def test_parse(text, platform, want):
    assert C.parse(text, platform) == want


@pytest.mark.parametrize("bad", ["", "https://example.com/x", "kick.com/", "a b c"])
def test_parse_rejects(bad):
    with pytest.raises(C.SharkyClipsError):
        C.parse(bad)


# ===================================================================== Kick detection


def test_added_channel_never_takes_the_back_catalog(fake):
    fake.kick_channel("utkualsirr")
    for i in range(5):
        fake.kick_vod("utkualsirr", T0 - (i + 1) * 24 * H, 3 * H)
    ch = add(fake)
    assert ch["name"] == "Utkualsirr" and ch["avatar"].endswith(".webp") and ch["own"] is True
    assert len(vods("baseline")) == 5 and not vods("queued")
    assert fake.mon.process(T0) is None and fake.started == []
    view = C.channel_view(ch, C.load())
    assert view["can_import"] == 5


def test_live_then_ended_then_vod_appears_late(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.go_live("utkualsirr", T0 + 600)
    fake.mon.poll_one("kick:utkualsirr", T0 + 900)
    ch = C.load()["channels"]["kick:utkualsirr"]
    assert ch["live"] is True
    assert ch["next_check"] - (T0 + 900) <= C.LIVE_EVERY_S * 1.1  # every ~5 min while live
    assert [v["status"] for v in vods().values()] == ["live"]
    # the stream ends, the VOD isn't there yet
    fake.end_stream("utkualsirr", 2 * H, vod_ready=False)
    fake.mon.poll_one("kick:utkualsirr", T0 + 3 * H)
    ch = C.load()["channels"]["kick:utkualsirr"]
    assert ch["live"] is False and ch["ended_at"] == T0 + 3 * H
    assert ch["next_check"] - (T0 + 3 * H) <= C.LIVE_EVERY_S * 1.1  # looks again soon (late VOD)
    assert not vods("queued")
    assert fake.mon.process(T0 + 3 * H) is None
    # 20 minutes later the VOD shows up
    v = next(x for x in fake.kick["utkualsirr"]["videos"])
    fake.publish_vod("utkualsirr", v, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 3 * H + 1200)
    q = vods("queued")
    assert len(q) == 1
    rec = next(iter(q.values()))
    assert rec["url"].startswith("https://kick.com/utkualsirr/videos/") and rec["duration"] == 2 * H
    assert rec["game"] == "Delta Force"
    assert not any(x.get("placeholder") for x in vods().values())  # the stand-in is gone
    key = fake.mon.process(T0 + 3 * H + 1300)
    assert key == next(iter(q))
    assert fake.started[0]["url"] == rec["url"] and fake.started[0]["channel_vod"] == key
    assert fake.started[0]["expect_duration"] == 2 * H and fake.started[0]["full_upload"] is False
    assert fake.started[0]["easy"] is True and fake.started[0]["mode_auto"] is True


def test_live_at_add_time_counts(fake):
    fake.kick_channel("utkualsirr")
    fake.go_live("utkualsirr", T0 - H)  # started before the channel was added
    add(fake)
    assert [v["status"] for v in vods().values()] == ["live"]
    fake.end_stream("utkualsirr", 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 2 * H)
    assert len(vods("queued")) == 1


def test_deleted_vod_before_download(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    v = fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    key = next(iter(vods("queued")))
    fake.delete_vod("utkualsirr", v["video"]["uuid"])
    fake.mon.poll_one("kick:utkualsirr", T0 + 4.1 * H)
    assert vods()[key]["status"] == "gone" and vods()[key]["note"] == "deleted"
    assert fake.mon.process(T0 + 5 * H) is None


def test_vod_dropped_from_list_counts_as_deleted_after_3_polls(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    old = fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    fake.kick_vod("utkualsirr", T0 + 5 * H, 2 * H)
    fake.running.add("x")  # pretend a download runs: nothing starts
    fake.mon.poll_one("kick:utkualsirr", T0 + 8 * H)
    key = f"kick:{old['video']['uuid']}"
    assert vods()[key]["status"] == "queued"
    fake.delete_vod("utkualsirr", old["video"]["uuid"], drop=True)
    for i in range(2):
        fake.mon.poll_one("kick:utkualsirr", T0 + 9 * H + i * 600)
        assert vods()[key]["status"] == "queued"  # might just be a hiccup
    fake.mon.poll_one("kick:utkualsirr", T0 + 10 * H)
    assert vods()[key]["status"] == "gone"


def test_subscriber_only_vod_is_skipped_with_a_note(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 2 * H, private=True)
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    rec = next(iter(vods().values()))
    assert rec["status"] == "skipped" and rec["note"] == "subscriber_only"


def test_short_streams_are_skipped(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 120)
    fake.mon.poll_one("kick:utkualsirr", T0 + 2 * H)
    assert next(iter(vods().values()))["note"] == "too_short"


def test_network_failure_backs_off_and_recovers(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.down.add("kick")
    waits = []
    now = T0 + H
    for _ in range(4):
        fake.mon.poll_one("kick:utkualsirr", now)
        ch = C.load()["channels"]["kick:utkualsirr"]
        waits.append(ch["next_check"] - now)
        now = ch["next_check"]
    assert ch["fails"] == 4 and "ConnectTimeout" in ch["last_error"]
    assert waits[1] > waits[0] * 1.5 and waits[3] > waits[2] * 1.5  # exponential
    assert all(w <= C.BACKOFF_MAX_S * 1.1 for w in waits)
    fake.down.clear()
    fake.kick_vod("utkualsirr", T0 + 2 * H, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", now)
    ch = C.load()["channels"]["kick:utkualsirr"]
    assert ch["fails"] == 0 and ch["last_error"] is None and len(vods("queued")) == 1


def test_rate_limit_honours_retry_after(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.rate_limited.add("kick")
    fake.mon.poll_one("kick:utkualsirr", T0 + H)
    ch = C.load()["channels"]["kick:utkualsirr"]
    assert ch["next_check"] - (T0 + H) >= 7200 * 0.9


def test_disk_full_waits_and_warns_once(fake, monkeypatch):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 6 * H)  # a 6 h stream
    fake.mon.poll_one("kick:utkualsirr", T0 + 8 * H)
    monkeypatch.setattr(C, "disk_ok", lambda duration, folder=None: (False, 10 * 1024 ** 3, int(duration * C.BYTES_PER_S)))
    assert fake.mon.process(T0 + 8 * H) is None
    assert fake.mon.process(T0 + 8.1 * H) is None
    rec = next(iter(vods().values()))
    assert rec["status"] == "waiting_disk" and fake.started == []
    assert [n[1] for n in fake.notices] == ["disk"]  # once, not every round
    assert fake.mon.waiting["reason"] == "disk"
    monkeypatch.setattr(C, "disk_ok", lambda duration, folder=None: (True, 900 * 1024 ** 3, 1))
    assert fake.mon.process(T0 + 9 * H) is not None
    assert vods("downloading")


def test_real_disk_estimate_for_long_streams(tmp_path, monkeypatch):
    monkeypatch.setattr(C.shutil, "disk_usage", lambda p: SimpleNamespace(free=20 * 1024 ** 3))
    ok, free, need = C.disk_ok(6 * H, tmp_path)
    assert not ok and need > 20 * 1024 ** 3  # 6 h ~ 21.6 GB + the reserve
    ok, _f, _n = C.disk_ok(H, tmp_path)
    assert ok


def test_metered_connection_and_running_game_wait(fake, monkeypatch):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    monkeypatch.setenv("SHARKYCLIPS_METERED", "1")
    assert fake.mon.process(T0 + 4 * H) is None
    assert next(iter(vods().values()))["status"] == "waiting_metered"
    config.update(channel_pause_metered=False)
    try:
        monkeypatch.setenv("SHARKYCLIPS_GAME_RUNNING", "deltaforceclient-win64-shipping")
        assert fake.mon.process(T0 + 4 * H) is None
        assert fake.mon.waiting == {"key": next(iter(vods())), "reason": "game",
                                    "detail": "deltaforceclient-win64-shipping", "at": T0 + 4 * H}
        monkeypatch.setenv("SHARKYCLIPS_GAME_RUNNING", "")
        assert fake.mon.process(T0 + 4 * H) is not None
    finally:
        config.update(channel_pause_metered=None)


def test_one_download_at_a_time_oldest_first(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    a = fake.kick_vod("utkualsirr", T0 + H, 2 * H, title="first")
    b = fake.kick_vod("utkualsirr", T0 + 5 * H, 2 * H, title="second")
    fake.mon.poll_one("kick:utkualsirr", T0 + 8 * H)
    k1 = fake.mon.process(T0 + 8 * H)
    assert k1 == f"kick:{a['video']['uuid']}"
    fake.running.add(k1)
    assert fake.mon.process(T0 + 8.1 * H) is None  # the first one still downloads
    CA.on_job_finished(SimpleNamespace(kind="import", params={"channel_vod": k1}, status="done",
                                       project_id=None, error=None))
    fake.running.clear()
    assert fake.mon.process(T0 + 8.2 * H) == f"kick:{b['video']['uuid']}"


def test_duplicate_protection(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    for i in range(3):
        fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H + i)
    key = fake.mon.process(T0 + 4 * H)
    with C._lock:
        data = C.load()
        data["vods"][key].update(status="done", project_id="p1", done_at=T0 + 5 * H)
        C.save(data)
    for i in range(3):
        fake.mon.poll_one("kick:utkualsirr", T0 + 6 * H + i)
    assert fake.mon.process(T0 + 7 * H) is None and len(fake.started) == 1
    # removing and adding the channel again doesn't download it again either
    with C._lock:
        data = C.load()
        data["channels"].pop("kick:utkualsirr")
        C.save(data)
    add(fake, now=T0 - 10 * 24 * H)  # even with an old baseline
    assert vods()[key]["status"] == "done"
    assert fake.mon.process(T0 + 8 * H) is None and len(fake.started) == 1


def test_pc_asleep_catch_up_in_order(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.mon.tick(T0 + 60)
    # the PC sleeps two days; three streams happen
    for d in (1, 2, 3):
        fake.kick_vod("utkualsirr", T0 + d * 12 * H, 3 * H, title=f"day {d}")
    with C._lock:
        data = C.load()
        data["channels"]["kick:utkualsirr"]["next_check"] = T0 + 100 * H  # as if it were far away
        C.save(data)
    wake = T0 + 48 * H
    res = fake.mon.tick(wake)
    assert any(e["kind"] == "catch_up" for e in C.load()["log"])
    assert res["polled"] and len(vods("queued")) == 2  # one started already
    assert fake.started[0]["title"] == "day 1"
    fake.running.add(res["started"])
    CA.on_job_finished(SimpleNamespace(kind="import", params={"channel_vod": res["started"]}, status="done",
                                       project_id=None, error=None))
    fake.running.clear()
    fake.mon.tick(wake + 30)
    assert fake.started[1]["title"] == "day 2"


def test_import_last_n_streams(fake):
    fake.kick_channel("utkualsirr")
    for i in range(4):
        fake.kick_vod("utkualsirr", T0 - (4 - i) * 24 * H, 2 * H, title=f"old {i}")
    add(fake)
    with C._lock:
        data = C.load()
        got = C.import_recent(data, "kick:utkualsirr", 2, T0 + 60)
        C.save(data)
    assert len(got) == 2
    fake.mon.process(T0 + 60)
    assert fake.started[0]["title"] == "old 2"  # the older of the two newest first


def test_import_failure_kinds(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    key = fake.mon.process(T0 + 4 * H)

    def fail(msg):
        CA.on_job_finished(SimpleNamespace(kind="import", params={"channel_vod": key}, status="error",
                                           project_id=None, error={"message": msg, "hint": None}))
        return vods()[key]

    rec = fail("Download failed: HTTP Error 502")
    assert rec["status"] == "retry" and rec["next_try"] > time.time()
    rec = fail("Kick won't play this VOD without an account (subscriber-only, deleted or expired).")
    assert rec["status"] == "skipped" and rec["note"] == "subscriber_only"
    assert fake.notices[-1][1] == "skipped"
    with C._lock:
        data = C.load()
        data["vods"][key].update(status="downloading", attempts=C.MAX_ATTEMPTS)
        C.save(data)
    rec = fail("Download failed: timed out")
    assert rec["status"] == "error" and fake.notices[-1][1] == "error"
    assert C.classify_failure("OSError: [Errno 28] No space left on device") == "disk"
    assert C.classify_failure("The download is incomplete (40 of 120 min).") == "retry"


def test_cancel_is_final(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    key = fake.mon.process(T0 + 4 * H)
    CA.on_job_finished(SimpleNamespace(kind="import", params={"channel_vod": key}, status="cancelled",
                                       project_id=None, error=None))
    assert vods()[key]["status"] == "skipped" and vods()[key]["note"] == "cancelled"
    assert fake.mon.process(T0 + 5 * H) is None


def test_restart_puts_a_cut_download_back(fake):
    fake.kick_channel("utkualsirr")
    add(fake)
    fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    key = fake.mon.process(T0 + 4 * H)
    assert vods()[key]["status"] == "downloading"
    mon = CA.Monitor()  # a new server: the job is gone
    mon.tick(T0 + 5 * H)
    assert len(fake.started) == 2 and fake.started[1]["channel_vod"] == key  # resumes (same project id)


# ===================================================================== the import + clips hooks


def _project(pid: str, clips: list[str]):
    p = project_for_id(pid)
    p.dir.mkdir(parents=True, exist_ok=True)
    p.save_meta({"id": pid, "title": "Stream", "mode": "gaming", "duration": 7200, "source": {"type": "url"}})
    write_json_atomic(p.dir / "clips.json", {"version": 1, "clips": {c: {"file": f"{c}.mp4", "id": c} for c in clips}})
    (p.dir / "clips").mkdir(exist_ok=True)
    for c in clips:
        (p.dir / "clips" / f"{c}.mp4").write_bytes(b"x")
    (p.dir / "source.mp4").write_bytes(b"x" * 2048)
    return p


def test_clips_ready_notice_game_and_source_cleanup(fake):
    import shutil

    from sharkyclips import trash

    fake.kick_channel("utkualsirr")
    add(fake, game="delta_force")
    fake.kick_vod("utkualsirr", T0 + H, 2 * H, title="Ranked night")
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    key = fake.mon.process(T0 + 4 * H)
    p = _project("chan-test-1", ["c01", "c02", "c03"])
    try:
        CA.on_job_finished(SimpleNamespace(kind="import", params={"channel_vod": key}, status="done",
                                           project_id=p.id, error=None))
        meta = p.load_meta()
        assert meta["channel"]["name"] == "Utkualsirr" and meta["channel"]["stream_title"] == "Ranked night"
        assert meta["game"] == "delta_force"
        assert vods()[key]["status"] == "clipping"
        top = [{"id": c} for c in ("c01", "c02", "c03", "c04")]
        assert CA.on_clips_ready(p, top) is True
        rec = vods()[key]
        assert rec["status"] == "done" and rec["clips"] == 3
        assert fake.notices[-1] == ("channel_ready", "ready_own",
                                    {"n": 3, "title": "Ranked night", "name": "Utkualsirr"})
        assert CA.on_clips_ready(p, top) is True and len(fake.notices) == 1  # once
        # not yet 7 days: the source stays
        assert fake.mon.cleanup_sources(time.time() + 6 * 86400) == []
        assert fake.mon.cleanup_sources(time.time() + 8 * 86400) == [key]
        assert p.source_path is None
        item = next(i for i in trash.items() if i.get("project_id") == p.id)
        assert item["titles"] == ["source"] and item.get("keep_days") == 2
        trash.restore(item["id"])  # restorable like any cleanup item
        assert p.source_path is not None
        assert fake.mon.cleanup_sources(time.time() + 9 * 86400) == []  # once
    finally:
        shutil.rmtree(p.dir, ignore_errors=True)


def test_other_peoples_channel_notice_and_no_auto_publish(fake, monkeypatch):
    import shutil

    from sharkyclips import autopilot

    calls = []
    monkeypatch.setattr(autopilot, "on_clips_ready", lambda *a, **kw: calls.append(a))
    fake.kick_channel("someone")
    add(fake, "kick.com/someone", own=False)
    ch = C.load()["channels"]["kick:someone"]
    assert ch["own"] is False and ch["auto_publish"] is False
    fake.kick_vod("someone", T0 + H, 2 * H, title="Their stream")
    fake.mon.poll_one("kick:someone", T0 + 4 * H)
    key = fake.mon.process(T0 + 4 * H)
    p = _project("chan-test-2", ["c01"])
    try:
        CA.on_job_finished(SimpleNamespace(kind="import", params={"channel_vod": key}, status="done",
                                           project_id=p.id, error=None))
        CA.on_clips_ready(p, [{"id": "c01"}])
        assert fake.notices[-1][1] == "ready_other" and fake.notices[-1][2]["name"] == "Someone"
        assert calls == []
    finally:
        shutil.rmtree(p.dir, ignore_errors=True)


def test_own_channel_auto_publish_uses_autopilot(fake, monkeypatch):
    import shutil

    from sharkyclips import autopilot

    calls = []
    monkeypatch.setattr(autopilot, "on_clips_ready", lambda project, ready, upload, when: calls.append((ready, when)))
    fake.kick_channel("utkualsirr")
    add(fake, auto_publish=True)
    fake.kick_vod("utkualsirr", T0 + H, 2 * H)
    fake.mon.poll_one("kick:utkualsirr", T0 + 4 * H)
    key = fake.mon.process(T0 + 4 * H)
    p = _project("chan-test-3", ["c01", "c02", "c03", "c04", "c05"])
    try:
        CA.on_job_finished(SimpleNamespace(kind="import", params={"channel_vod": key}, status="done",
                                           project_id=p.id, error=None))
        CA.on_clips_ready(p, [{"id": f"c0{i}"} for i in range(1, 6)])
        assert len(calls) == 1 and calls[0][1] == "auto" and len(calls[0][0]) == 3  # watch_publish_top
    finally:
        shutil.rmtree(p.dir, ignore_errors=True)


def test_non_channel_projects_keep_the_old_path(fake):
    import shutil

    p = _project("chan-test-4", ["c01"])
    try:
        assert CA.on_clips_ready(p, [{"id": "c01"}]) is False
    finally:
        shutil.rmtree(p.dir, ignore_errors=True)


# ===================================================================== Twitch + YouTube


def test_twitch_archive_live_and_ready(fake):
    fake.twitch["someone"] = {"stream": None, "videos": []}
    ch = add(fake, "twitch.tv/someone")
    assert ch["platform"] == "twitch" and ch["avatar"].endswith(".png")
    fake.twitch["someone"]["stream"] = {"id": "s1", "createdAt": "2026-09-21T03:00:00Z", "game": {"name": "VALORANT"}}
    fake.twitch["someone"]["videos"] = [{"id": "111", "title": "live", "createdAt": "2026-09-21T03:00:00Z",
                                         "lengthSeconds": 1200, "status": "RECORDING", "game": {"name": "VALORANT"}}]
    fake.mon.poll_one("twitch:someone", T0 + H)
    assert vods()["twitch:111"]["status"] == "live"
    fake.twitch["someone"]["stream"] = None
    fake.twitch["someone"]["videos"][0].update(status="RECORDED", lengthSeconds=9000)
    fake.mon.poll_one("twitch:someone", T0 + 4 * H)
    rec = vods()["twitch:111"]
    assert rec["status"] == "queued" and rec["url"] == "https://www.twitch.tv/videos/111" and rec["duration"] == 9000


def test_twitch_live_without_archive_then_archive(fake):
    fake.twitch["someone"] = {"stream": None, "videos": []}
    add(fake, "twitch.tv/someone")
    fake.twitch["someone"]["stream"] = {"id": "s9", "createdAt": "2026-09-21T03:00:00Z", "game": None}
    fake.mon.poll_one("twitch:someone", T0 + H)
    assert C.load()["channels"]["twitch:someone"]["live"] is True
    assert vods()["twitch:stream-s9"]["status"] == "live"
    fake.twitch["someone"]["stream"] = None
    fake.twitch["someone"]["videos"] = [{"id": "222", "title": "x", "createdAt": "2026-09-21T03:00:00Z",
                                         "lengthSeconds": 7000, "status": "RECORDED", "game": None}]
    fake.mon.poll_one("twitch:someone", T0 + 4 * H)
    assert "twitch:stream-s9" not in vods() and vods()["twitch:222"]["status"] == "queued"


def test_youtube_live_upload_restricted_and_kinds(fake):
    uc = "UC" + "a" * 22
    fake.yt[uc] = {"handle": "@sharky", "name": "Sharky", "entries": [
        {"id": "old1", "title": "old", "published": T0 - 30 * 24 * H}]}
    ch = add(fake, "youtube.com/@sharky", yt_kinds="both")
    assert ch["id"] == f"youtube:{uc}" and ch["name"] == "Sharky" and ch["at"] == "@sharky"
    assert vods()["youtube:old1"]["status"] == "baseline"
    assert ("YTDLP", "old1") not in fake.calls  # no lookups for the back catalog
    fake.yt[uc]["entries"][:0] = [
        {"id": "live1", "title": "LIVE", "published": T0 + H},
        {"id": "up1", "title": "Upload", "published": T0 + 2 * H},
        {"id": "mem1", "title": "Members", "published": T0 + 2 * H},
        {"id": "age1", "title": "Age", "published": T0 + 2 * H},
    ]
    fake.yt_info.update({"live1": {"live_status": "is_live"},
                         "up1": {"live_status": "not_live", "duration": 1500},
                         "mem1": {"availability": "subscriber_only", "live_status": "was_live", "duration": 9000},
                         "age1": {"error": "Sign in to confirm your age. This video may be inappropriate for some users."}})
    fake.mon.poll_one(ch["id"], T0 + 3 * H)
    v = vods()
    assert v["youtube:live1"]["status"] == "live"
    assert v["youtube:up1"]["status"] == "queued" and v["youtube:up1"]["kind"] == "upload"
    assert v["youtube:mem1"]["note"] == "subscriber_only"
    assert v["youtube:age1"]["note"] == "age_restricted"
    fake.yt_info["live1"] = {"live_status": "post_live"}
    fake.mon.poll_one(ch["id"], T0 + 5 * H)
    assert vods()["youtube:live1"]["status"] == "processing"
    n = sum(1 for c in fake.calls if c == ("YTDLP", "up1"))
    fake.yt_info["live1"] = {"live_status": "was_live", "duration": 10000}
    fake.mon.poll_one(ch["id"], T0 + 6 * H)
    assert vods()["youtube:live1"]["status"] == "queued"
    assert sum(1 for c in fake.calls if c == ("YTDLP", "up1")) == n  # decided ones aren't looked up again


def test_youtube_only_live_streams(fake):
    uc = "UC" + "b" * 22
    fake.yt[uc] = {"handle": "@other", "name": "Other", "entries": []}
    ch = add(fake, "youtube.com/@other", own=False, yt_kinds="live")
    fake.yt[uc]["entries"] = [{"id": "up2", "title": "Upload", "published": T0 + H}]
    fake.yt_info["up2"] = {"live_status": "not_live", "duration": 900}
    fake.mon.poll_one(ch["id"], T0 + 2 * H)
    assert vods()["youtube:up2"]["note"] == "kind_off"


# ===================================================================== API


def test_api_add_update_import_remove(fake, monkeypatch):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    fake.kick_channel("utkualsirr")
    for i in range(3):
        fake.kick_vod("utkualsirr", time.time() - (i + 1) * 24 * H, 2 * H)
    monkeypatch.setattr(CA, "_monitor", fake.mon)
    c = TestClient(app)
    r = c.post("/api/channels/lookup", json={"text": "kick.com/utkualsirr"})
    assert r.status_code == 200 and r.json()["name"] == "Utkualsirr" and r.json()["known"] is False
    r = c.post("/api/channels", json={"text": "kick.com/utkualsirr"})
    assert r.status_code == 200
    body = r.json()
    ch = body["channels"][0]
    assert ch["id"] == "kick:utkualsirr" and ch["own"] is True and ch["auto_publish"] is False
    assert ch["keep_days"] == 7 and ch["mode"] == "auto" and ch["game"] == "auto"
    assert "delta_force" in body["games"]
    assert c.post("/api/channels", json={"text": "kick.com/utkualsirr"}).status_code == 400  # twice
    fake.mon.poll_one("kick:utkualsirr")
    r = c.put("/api/channels/kick%3Autkualsirr/options", json={"mode": "gaming", "keep_days": -1, "auto_publish": True})
    ch = r.json()["channels"][0]
    assert ch["mode"] == "gaming" and ch["keep_days"] == -1 and ch["auto_publish"] is True and ch["can_import"] == 3
    assert c.put("/api/channels/kick%3Autkualsirr/options", json={"keep_days": 5}).status_code == 400
    r = c.post("/api/channels/kick%3Autkualsirr/import", json={"count": 2})
    assert r.status_code == 200 and len(r.json()["queued"]) == 2
    r = c.put("/api/channels/settings", json={"pause_metered": False, "min_free_gb": 20})
    assert r.json()["settings"]["pause_metered"] is False and r.json()["settings"]["min_free_gb"] == 20
    config.update(channel_pause_metered=None, channel_min_free_gb=None)
    key = r.json()["vods"][0]["key"]
    assert c.post(f"/api/channels/vods/{key}/skip").json()["vods"][0]["status"] == "skipped"
    assert c.post(f"/api/channels/vods/{key}/retry").status_code == 200
    r = c.delete("/api/channels/kick%3Autkualsirr/remove")
    assert r.json()["channels"] == []
    assert all(v["status"] in ("skipped", "baseline") for v in vods().values())


def test_api_other_channel_defaults(fake, monkeypatch):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    fake.kick_channel("someone")
    monkeypatch.setattr(CA, "_monitor", fake.mon)
    c = TestClient(app)
    r = c.post("/api/channels", json={"text": "someone", "platform": "kick", "own": False})
    ch = r.json()["channels"][0]
    assert ch["own"] is False and ch["auto_publish"] is False
    r = c.post("/api/channels/lookup", json={"text": "kick.com/nobody-here"})
    assert r.status_code == 400 and "no channel" in r.json()["error"].lower()


def test_state_file_is_compact_enough(fake):
    fake.kick_channel("utkualsirr")
    for i in range(30):
        fake.kick_vod("utkualsirr", T0 - (i + 1) * 24 * H, 2 * H)
    add(fake)
    data = json.loads(C.state_path().read_text(encoding="utf-8"))
    assert len(data["vods"]) == 30 and len(data["log"]) <= 200


# ===================================================================== Kick VOD download fallback (found by the real test)


class _V1:
    """kick.com/api/v1/video/<uuid> like on 2026-11-20 (the playback endpoint said NOT_FOUND)."""

    def __init__(self, video: dict | None):
        self.video, self.calls = video, []

    def request(self, method, url, timeout=30, **kw):
        self.calls.append(url)
        if "/api/v1/video/" in url and self.video is not None:
            return SimpleNamespace(status_code=200, json=lambda: self.video, raise_for_status=lambda: None)
        return SimpleNamespace(status_code=404, json=lambda: {}, raise_for_status=lambda: None)


def _v1_video(**over):
    v = {"uuid": "4e21ed23-37a4-47b9-9121-6e2959276dbc", "status": "public", "is_private": False, "deleted_at": None,
         "is_pruned": False, "source": "https://stream.kick.com/x/media/hls/master.m3u8",
         "livestream": {"session_title": "HOY COMENZAMOS EL GTA V", "start_time": "2026-11-09T01:51:56+00:00",
                        "duration": 598000, "is_live": False, "categories": [{"name": "Just Chatting"}],
                        "channel": {"slug": "elzeein", "user": {"username": "ElZeein"}}}}
    v.update(over)
    return v


def test_kick_resolve_uses_the_v1_video():
    from sharkyclips import kick

    info = kick.resolve("https://kick.com/elzeein/videos/4e21ed23-37a4-47b9-9121-6e2959276dbc", _V1(_v1_video()))
    assert info["media_url"].endswith("master.m3u8") and info["duration"] == 598.0
    assert info["uploader"] == "ElZeein" and info["categories"] == ["Just Chatting"]
    assert info["webpage_url"] == "https://kick.com/elzeein/videos/4e21ed23-37a4-47b9-9121-6e2959276dbc"
    # a kick.com/video/<id> link finds its channel there too
    assert kick.canonical("https://kick.com/video/4e21ed23-37a4-47b9-9121-6e2959276dbc", _V1(_v1_video())) == \
        "https://kick.com/elzeein/videos/4e21ed23-37a4-47b9-9121-6e2959276dbc"


@pytest.mark.parametrize("over,want,kind", [
    ({"is_private": True}, "subscribers only", "restricted"),
    ({"deleted_at": "2026-11-19T00:00:00Z"}, "deleted", "gone"),
])
def test_kick_v1_private_and_deleted_are_told_apart(over, want, kind):
    from sharkyclips import kick

    with pytest.raises(C.SharkyClipsError) as e:
        kick.resolve("https://kick.com/elzeein/videos/4e21ed23-37a4-47b9-9121-6e2959276dbc", _V1(_v1_video(**over)))
    assert want in e.value.message.lower()
    assert C.classify_failure(e.value.message + " " + (e.value.hint or "")) == kind
