"""Resource governor: decisions, safe points, process control."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

import psutil
import pytest

from clipforge import governor, procs
from clipforge.sysmon import Sample, UserState

CFG = {"perf_idle_minutes": 3, "perf_gpu_temp_limit": 85, "perf_pause_fullscreen": True,
       "perf_pause_video": True, "perf_pause_busy": True}


def sample(**kw) -> Sample:
    user = kw.pop("user", UserState(idle_seconds=5, fg_name="code", fg_pid=1))
    base = dict(t=0, cpu=10, cpu_ours=5, ram_used_mb=4000, ram_total_mb=16000, ram_ours_mb=500,
                gpu=10, gpu_ours=0, vram_used_mb=1000, vram_total_mb=8192, vram_ours_mb=0, gpu_temp=50,
                per_process_gpu=True)
    base.update(kw)
    return Sample(user=user, **base)


def decide(mode="silent", s=None, mem=None, apps=(), cfg=None, override=False, ticks=1):
    mem = {} if mem is None else mem
    d = None
    for _ in range(ticks):
        d = governor.decide(mode, s or sample(), {**CFG, **(cfg or {})}, mem, {999}, set(apps), override)
    return d


def test_silent_throttles_while_user_is_active():
    d = decide()
    assert d.state == "throttled" and d.priority == procs.IDLE
    assert d.cores == max(1, (psutil.cpu_count() or 2) // 2) and d.throttle > 0


def test_game_in_foreground_pauses_silent_only():
    s = sample(user=UserState(idle_seconds=1, fg_name="deltaforceclient-win64-shipping", fg_pid=50))
    assert decide("silent", s).state == "paused"
    assert decide("silent", s).reason == "game"
    assert decide("balanced", s).state == "throttled"
    assert decide("turbo", s).state == "running"


def test_game_list_is_configurable_and_exact():
    s = sample(user=UserState(idle_seconds=1, fg_name="code", fg_pid=50))
    assert decide(s=s).state == "throttled"  # "cod" (Call of Duty) must not match VS Code
    assert decide(s=s, cfg={"perf_games": ["code"]}).reason == "game"


def test_fullscreen_and_video_pause_but_not_clipforge_itself():
    full = sample(user=UserState(idle_seconds=1, fg_name="vlc", fg_pid=50, fullscreen=True))
    assert decide(s=full).reason == "fullscreen"
    ours = sample(user=UserState(idle_seconds=1, fg_name="msedge", fg_pid=50, fullscreen=True,
                                 fg_title="ClipForge - Microsoft Edge"))
    assert decide(s=ours).state == "throttled"
    video = sample(video_decode=True, user=UserState(idle_seconds=1, fg_name="chrome", fg_pid=50))
    mem: dict = {}
    assert decide(s=video, mem=mem).state == "throttled"  # one tick could be a thumbnail
    assert decide(s=video, mem=mem).reason == "video"
    ui = UserState(idle_seconds=1, fg_name="chrome", fg_pid=50, fg_title="ClipForge - Google Chrome")
    own_player = sample(video_decode=True, video_apps={"chrome"}, user=ui)
    assert decide(s=own_player, ticks=3).state == "throttled"  # ClipForge's review player
    other = sample(video_decode=True, video_apps={"chrome", "msedge"}, user=ui)
    assert decide(s=other, ticks=2).reason == "video"  # a video in another app still pauses


def test_streaming_software_pauses_while_it_encodes():
    assert decide(apps={"obs64"}).state == "throttled"  # OBS just open
    s = sample(video_encode_pids=[1234])
    assert decide(s=s, apps={"obs64"}).reason == "streaming"


def test_busy_other_apps_with_hysteresis():
    mem: dict = {}
    busy = sample(cpu=95, cpu_ours=5)
    assert decide(s=busy, mem=mem, ticks=2).state == "throttled"
    assert decide(s=busy, mem=mem).reason == "busy"  # third busy tick
    calm = sample(cpu=30, cpu_ours=5)
    assert decide(s=calm, mem=mem, ticks=2).reason == "busy"
    assert decide(s=calm, mem=mem).state == "throttled"


def test_away_means_full_speed_but_games_still_win():
    away = sample(user=UserState(idle_seconds=600, fg_name="code", fg_pid=1))
    d = decide(s=away)
    assert d.state == "running" and d.away and d.cores is None and d.throttle == 0
    locked = sample(user=UserState(idle_seconds=10, locked=True))
    assert decide(s=locked).away
    game_away = sample(user=UserState(idle_seconds=600, fg_name="cs2", fg_pid=5))
    assert decide(s=game_away).reason == "game"  # gamepad play doesn't count as input


def test_idle_only_waits_and_override_resumes():
    assert decide(cfg={"perf_idle_only": True}).state == "waiting_idle"
    d = decide(cfg={"perf_idle_only": True}, override=True)
    assert d.state == "throttled" and d.reason == "idle_only"
    s = sample(user=UserState(idle_seconds=1, fg_name="cs2", fg_pid=5))
    d = decide(s=s, override=True)
    assert not d.paused and d.reason == "game"  # running anyway, reason still shown


def test_thermal_guard_in_every_mode():
    mem: dict = {}
    assert decide("turbo", sample(gpu_temp=86), mem=mem).state == "cooling"
    assert decide("turbo", sample(gpu_temp=80), mem=mem).state == "cooling"  # not cool enough yet
    assert decide("turbo", sample(gpu_temp=74), mem=mem).state == "running"
    assert decide("turbo", sample(gpu_temp=82)).throttle > 0  # warm: slow down


def test_vram_headroom():
    assert governor.headroom_mb(8192, {}) == 2048
    assert governor.headroom_mb(4096, {}) == 1024
    assert governor.headroom_mb(24576, {}) == 3072
    assert governor.headroom_mb(8192, {"perf_vram_headroom_mb": 1500}) == 1500


def test_affinity_mask_uses_last_cores():
    assert procs.affinity_mask(4, 8) == 0b11110000
    assert procs.affinity_mask(8, 8) is None
    assert procs.affinity_mask(0, 8) == 0b10000000


class _FakeJob:
    cancel_requested = False
    paused = False


def test_checkpoint_waits_resumes_and_cancels():
    g = governor.Governor()  # not started, no module install: drive it by hand
    old = governor._gov
    governor._gov = g
    try:
        g._go.clear()
        job = _FakeJob()
        out = []

        def worker():
            governor.set_current_job(job)
            try:
                out.append(governor.checkpoint(release=lambda: out.append("released")))
            except governor.JobCancelled:
                out.append("cancelled")

        th = threading.Thread(target=worker)
        th.start()
        time.sleep(0.3)
        assert out == ["released"] and job.paused
        g._go.set()
        th.join(3)
        assert out == ["released", True] and not job.paused

        g._go.clear()
        out.clear()
        th = threading.Thread(target=worker)
        th.start()
        time.sleep(0.3)
        job.cancel_requested = True
        th.join(3)
        assert out == ["released", "cancelled"]
    finally:
        g._go.set()
        governor._gov = old


def test_gate_is_free_without_governor():
    governor.gate()
    assert governor.checkpoint() is False
    assert governor.cpu_threads(3) == 3


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Objects")
def test_job_object_limits_and_kills_children():
    job = procs.Job(kill_on_close=True)
    assert job.ok
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                             creationflags=0x4)  # suspended until it's in the job
    try:
        assert job.assign(child.pid)
        procs.resume_pid(child.pid)
        assert job.set_limits(procs.BELOW_NORMAL, procs.affinity_mask(1))
        assert psutil.Process(child.pid).nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS
        import ctypes

        ctypes.windll.kernel32.CloseHandle(job.handle)  # like the server exiting / crashing
        child.wait(timeout=5)
        assert child.returncode is not None
    finally:
        if child.poll() is None:
            child.kill()


def test_suspend_and_resume_tracked_process():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        procs.track(child)
        procs.suspend_all()
        assert psutil.Process(child.pid).status() in (psutil.STATUS_STOPPED, "suspended") or os.name == "nt"
        procs.resume_all()
        assert child.poll() is None
    finally:
        procs.untrack(child)
        child.kill()


def test_game_rendering_behind_other_windows_pauses():
    s = sample(gpu_pids={4242: 60.0})
    assert decide(s=s).state == "throttled"  # without a known game: just another app
    d = governor.decide("silent", s, CFG, {}, {999}, set(), games_running={4242: "league of legends"})
    assert d.reason == "game" and d.detail == "league of legends"
    calm = sample(gpu_pids={4242: 2.0})  # a launcher idling in the background
    assert governor.decide("silent", calm, CFG, {}, {999}, set(),
                           games_running={4242: "leagueclientux"}).state == "throttled"


def test_league_client_is_in_the_default_list():
    for name in ("league of legends", "leagueclient", "leagueclientux", "deltaforceclient-win64-shipping",
                 "cs2", "valorant-win64-shipping"):
        s = sample(user=UserState(idle_seconds=1, fg_name=name, fg_pid=50))
        assert decide(s=s).reason == "game", name


def test_idle_governor_samples_cheaply_and_wakes_for_jobs(monkeypatch):
    busy = {"v": False}
    g = governor.Governor(busy=lambda: busy["v"])
    reads = []
    monkeypatch.setattr(g.monitor.nvml, "read", lambda *a: reads.append(1) or None)
    g.tick()
    assert g.light and g.decision.state == "idle" and reads == []  # GPU untouched
    g.watched()  # the UI is open
    g.tick()
    assert not g.light and reads == [1]
    g._viewer_at = 0
    busy["v"] = True  # a job started
    g.tick()
    assert not g.light


def test_hidden_child_windows(monkeypatch):
    if os.name != "nt":
        pytest.skip("Windows only")
    seen = []
    monkeypatch.setattr(subprocess.Popen, "__init__", lambda self, *a, **kw: seen.append(kw.get("creationflags")))
    monkeypatch.setattr(procs, "_hidden", False)
    procs.hide_child_windows()
    subprocess.Popen(["ffmpeg"])
    subprocess.Popen(["x"], creationflags=0x4)
    subprocess.Popen(["x"], creationflags=0x10)  # CREATE_NEW_CONSOLE: asked for a window
    assert seen == [subprocess.CREATE_NO_WINDOW, 0x4 | subprocess.CREATE_NO_WINDOW, 0x10]


def test_ollama_autostart_link_is_parked_and_restored(tmp_path, monkeypatch):
    from clipforge import startup

    start = tmp_path / "Startup"
    start.mkdir()
    (start / "Ollama.lnk").write_bytes(b"lnk")
    monkeypatch.setattr(startup, "startup_dir", lambda: start)
    monkeypatch.setattr(startup, "backup_dir", lambda: tmp_path / "parked")
    assert startup.ollama_autostart_enabled() is True
    assert startup.apply_ollama_autostart(False) is False
    assert not (start / "Ollama.lnk").exists() and (tmp_path / "parked" / "Ollama.lnk").is_file()
    assert startup.apply_ollama_autostart(True) is True
    assert (start / "Ollama.lnk").read_bytes() == b"lnk"
