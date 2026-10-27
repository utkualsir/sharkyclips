"""Resource governor: SharkyClips yields to whatever the user is doing.

Performance modes (config `performance_mode`):
  silent    (default) low priority, half the CPU cores, GPU work in short bursts; PAUSES while a
            game, streaming software, a fullscreen app or a video is on; full speed when the
            user is away (no input for `perf_idle_minutes`, or the screen is locked)
  balanced  low priority and throttled, full speed when away, never pauses
  turbo     full speed all the time

Every mode pauses when the GPU gets too hot (thermal guard).

A background thread samples the machine every ~2 s (sysmon.py: cheap OS calls, no helper
programs) and decides. Work pauses only at safe points, so it continues exactly where it
stopped:
  * `checkpoint()`  in a job's thread: progress updates, between transcription chunks, before
                    every LLM request. Can free GPU memory first (`release=`).
  * `gate()`        in hot loops of any worker thread (frame decoding, laughter windows).
  * long-running ffmpeg children are suspended (procs.track) and resumed afterwards.

The same samples feed the resource monitor in the UI (history of the last 5 minutes).
"""

from __future__ import annotations

import collections
import contextlib
import fnmatch
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterator

import psutil

from . import config, procs, sysmon

MODES = ("silent", "balanced", "turbo")
TICK = 2.0
IDLE_TICK = 10.0  # no job and nobody looking at the UI: sample rarely, CPU / RAM only
VIEWER_TIMEOUT = 15.0  # seconds after the last UI update request the UI counts as closed
BACKGROUND_GAME_GPU = 10.0  # % 3D load: a listed game behind other windows that still renders
HISTORY = 150  # 5 minutes of 2 s samples

# Process names (lower case, without .exe; * wildcards). Users can edit the list in Settings.
DEFAULT_GAMES = [
    "league of legends", "leagueclient", "leagueclientux", "deltaforce*", "delta force*", "cs2",
    "valorant", "valorant-win64-shipping",
    "fortniteclient-win64-shipping", "r5apex", "r5apex_dx12", "cod", "gta5", "gta5_enhanced",
    "rocketleague", "overwatch", "dota2", "eldenring", "tslgame", "rainbowsix", "rainbowsix_vulkan",
    "marvel-win64-shipping", "escapefromtarkov", "destiny2", "bf2042", "bf6", "rustclient",
    "pathofexile*", "diablo iv", "wow", "hearthstone", "helldivers2", "fc25", "fc26", "genshinimpact",
    "starrail", "zenlesszonezero", "robloxplayerbeta", "minecraft.windows", "cyberpunk2077",
    "witcher3", "bg3", "bg3_dx11", "deadlock", "project8",
]
# Streaming / recording software: pauses while it encodes video (= streaming or recording).
STREAMING_APPS = ["obs64", "obs32", "obs", "streamlabs obs", "streamlabs desktop", "xsplit.core",
                  "meld studio", "twitch studio", "prism live studio"]
OLLAMA_NAMES = {"ollama", "ollama.exe", "llama-server", "llama-server.exe", "ollama_llama_server",
                "ollama_llama_server.exe"}
_NOT_FULLSCREEN = {"explorer", "lockapp", "searchhost", "searchapp", "shellexperiencehost",
                   "startmenuexperiencehost", "textinputhost", "applicationframehost"}

THROTTLE = {"silent": 0.6, "balanced": 0.25}  # sleep this x the work time at every safe point


class JobCancelled(Exception):
    """The job running in this thread was cancelled (raised from checkpoints)."""


# ============================================================================ decision


@dataclass
class Decision:
    state: str  # running | throttled | paused | waiting_idle | cooling | idle (no job)
    reason: str | None = None  # game | streaming | fullscreen | video | busy | thermal | idle_only
    detail: str | None = None  # e.g. the game's process name
    away: bool = False  # the user is away: full speed
    throttle: float = 0.0
    priority: int = procs.NORMAL
    cores: int | None = None  # None = all

    @property
    def paused(self) -> bool:
        return self.state in ("paused", "waiting_idle", "cooling")


def _match(name: str | None, patterns: list[str]) -> bool:
    if not name:
        return False
    return any(fnmatch.fnmatchcase(name, p.lower().removesuffix(".exe")) for p in patterns)


def _debounce(mem: dict, key: str, cond: bool, on: int = 2, off: int = 3) -> bool:
    """True after `cond` held for `on` ticks; false again after `off` ticks without it."""
    st = mem.setdefault(key, {"on": False, "n": 0})
    if cond == st["on"]:
        st["n"] = 0
    else:
        st["n"] += 1
        if st["n"] >= (on if cond else off):
            st["on"], st["n"] = cond, 0
    return st["on"]


def headroom_mb(total_mb: float, cfg: dict) -> float:
    """VRAM always left free for games / browser / video (auto: 2 GB on an 8 GB card)."""
    want = float(cfg.get("perf_vram_headroom_mb") or 0)
    if want > 0:
        return min(want, total_mb * 0.6)
    return max(1024.0, min(3072.0, total_mb * 0.25))


def decide(mode: str, s: sysmon.Sample, cfg: dict, mem: dict, ours: set[int],
           running_apps: set[str], override: bool = False,
           games_running: dict[int, str] | None = None) -> Decision:
    """The governor's whole policy as one (testable) function. `mem` keeps hysteresis state."""
    cores = psutil.cpu_count() or 1
    half = max(1, cores // 2)
    limit = float(cfg.get("perf_gpu_temp_limit") or 85)

    # Thermal guard (every mode): pause at the limit, until 10 degC below it.
    temps = [t for t in (s.gpu_temp, s.cpu_temp) if t is not None]
    hot = max(temps) if temps else None
    if hot is not None:
        if hot >= limit:
            mem["cooling"] = True
        elif hot <= limit - 10:
            mem["cooling"] = False
    if mem.get("cooling"):
        return Decision("cooling", "thermal", f"{hot:.0f}", priority=procs.IDLE, cores=half)
    warm = hot is not None and hot >= limit - 5  # slow down before it gets too hot

    u = s.user
    idle_min = float(cfg.get("perf_idle_minutes") or 3)
    away = bool(u.locked or (u.idle_seconds is not None and u.idle_seconds >= idle_min * 60))

    if mode == "turbo":
        return Decision("running", away=away, throttle=0.3 if warm else 0.0)

    if mode == "silent" and not u.locked:
        fg = u.fg_name
        ours_fg = u.fg_pid in ours or "sharkyclips" in (u.fg_title or "").lower()
        blocker = None
        if not ours_fg and _match(fg, list(cfg.get("perf_games") or DEFAULT_GAMES)):
            blocker = ("game", fg)
        if blocker is None:  # alt-tabbed out of a game that keeps rendering (a match in progress)
            for pid, name in (games_running or {}).items():
                if s.gpu_pids.get(pid, 0.0) >= BACKGROUND_GAME_GPU:
                    blocker = ("game", name)
                    break
        if blocker is None:
            streaming = [a for a in running_apps if _match(a, STREAMING_APPS)]
            enc = bool(s.video_encode_pids) if s.per_process_gpu else True
            if _debounce(mem, "streaming", bool(streaming) and enc, on=1, off=3):
                blocker = ("streaming", streaming[0] if streaming else None)
        if blocker is None and cfg.get("perf_pause_fullscreen", True):
            full = ((u.fullscreen or u.d3d_fullscreen) and not ours_fg and fg not in _NOT_FULLSCREEN)
            if _debounce(mem, "fullscreen", full, on=1, off=2):
                blocker = ("fullscreen", fg)
        if blocker is None and cfg.get("perf_pause_video", True):
            # SharkyClips's own player plays video too: with the SharkyClips tab in front, only video
            # decoded by other apps counts (a video in another browser, a media player, ...).
            video = bool(s.video_apps - {fg}) if ours_fg else s.video_decode
            if _debounce(mem, "video", video, on=2, off=3):
                blocker = ("video", fg)
        if blocker is None and cfg.get("perf_pause_busy", True):
            other_cpu = max(0.0, s.cpu - s.cpu_ours)
            other_gpu = None if s.gpu is None else max(0.0, s.gpu - (s.gpu_ours or 0.0))
            busy_now = other_cpu >= 80 or (other_gpu is not None and other_gpu >= 85)
            calm = other_cpu < 55 and (other_gpu is None or other_gpu < 60)
            b = mem.setdefault("busy", {"on": False, "n": 0})
            flip = calm if b["on"] else busy_now  # on after 3 busy ticks, off after 3 calm ones
            b["n"] = b["n"] + 1 if flip else 0
            if b["n"] >= 3:
                b["on"], b["n"] = not b["on"], 0
            if b["on"]:
                blocker = ("busy", None)
        if blocker and not override:
            return Decision("paused", blocker[0], blocker[1], priority=procs.IDLE, cores=half)
        if cfg.get("perf_idle_only") and not away and not override:
            return Decision("waiting_idle", "idle_only", priority=procs.IDLE, cores=half)
        overridden = blocker or (("idle_only", None) if cfg.get("perf_idle_only") and not away else None)
    else:
        overridden = None
    d = _run_decision(mode, away, warm, half)
    if overridden:  # "Resume anyway" is active: keep the reason so the UI can say so
        d.reason, d.detail = overridden
    return d


def _run_decision(mode: str, away: bool, warm: bool, half: int) -> Decision:
    if away:  # nobody is using the PC: all cores, no pauses; still low priority so it's
        # back out of the way the moment the user returns
        return Decision("running", away=True, throttle=0.3 if warm else 0.0, priority=procs.BELOW_NORMAL)
    if mode == "balanced":
        return Decision("throttled", throttle=max(THROTTLE["balanced"], 0.4 if warm else 0.0),
                        priority=procs.BELOW_NORMAL, cores=half)
    return Decision("throttled", throttle=max(THROTTLE["silent"], 0.8 if warm else 0.0),
                    priority=procs.IDLE, cores=half)


# ============================================================================ governor


class _CfgCache:
    def __init__(self):
        self.mtime = None
        self.cfg = config.load()

    def get(self) -> dict:
        try:
            m = config.config_path().stat().st_mtime
        except OSError:
            m = None
        if m != self.mtime:
            self.mtime = m
            self.cfg = config.load()
        return self.cfg


class Governor:
    def __init__(self, busy: Callable[[], bool] = lambda: False):
        self.busy = busy
        self.monitor = sysmon.Monitor()
        self.enforcer = procs.Enforcer()
        self.history: collections.deque = collections.deque(maxlen=HISTORY)
        self.decision = Decision("throttled")
        self.sample: sysmon.Sample | None = None
        self.rev = 0
        self._cfg = _CfgCache()
        self._mem: dict = {}
        self._go = threading.Event()
        self._go.set()
        self._override_until = 0.0
        self._override_reason: str | None = None
        self._paused_since: float | None = None
        self._paused_total = 0.0
        self._ours: set[int] = {os.getpid()}
        self._apps: set[str] = set()
        self._games: dict[int, str] = {}  # running processes from the game list: pid -> name
        self._viewer_at = 0.0  # last time the UI asked for live numbers
        self.light = False  # last tick was an idle tick (no GPU sensors read)
        self._ollama: list[psutil.Process] = []
        self._tick_n = 0
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._stop_wait = threading.Event()  # wakes the loop early (stop, UI opened)
        self.on_change: list[Callable[[], None]] = []
        self.tick_seconds = 0.0
        self.cancel_epoch = 0  # bumped when a job is cancelled (wakes paused helper threads)

    # ------------------------------------------------------------- control

    def job_cancelled(self) -> None:
        self.cancel_epoch += 1  # (suspended ffmpeg children are killed by their owners)

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="sharkyclips-governor", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._stop_wait.set()
        self._go.set()
        procs.resume_all()
        self.enforcer.restore_external()

    @property
    def mode(self) -> str:
        m = str(self._cfg.get().get("performance_mode") or "silent")
        return m if m in MODES else "silent"

    def resume_anyway(self) -> None:
        """'Resume anyway': ignore the current pause reason until it goes away (max 3 h)."""
        with self._lock:
            self._override_reason = self.decision.reason
            self._override_until = time.monotonic() + 3 * 3600
        self.tick()

    def paused_total(self) -> float:
        """Seconds work was paused since start (for ETAs)."""
        with self._lock:
            extra = time.monotonic() - self._paused_since if self._paused_since else 0.0
            return self._paused_total + extra

    @property
    def paused(self) -> bool:
        return not self._go.is_set()

    # ------------------------------------------------------------- budgets

    def cpu_threads(self) -> int:
        """Threads heavy CPU work may use right now."""
        total = psutil.cpu_count() or 1
        return max(1, self.decision.cores or total)

    def full_speed(self) -> bool:
        return self.mode == "turbo" or self.decision.away

    def vram_budget_mb(self) -> float | None:
        """VRAM SharkyClips may use now: total - headroom - what other apps use."""
        s = self.sample
        if s is None or s.vram_total_mb is None or s.vram_used_mb is None:
            return None
        others = max(0.0, s.vram_used_mb - (s.vram_ours_mb or 0.0))
        return max(0.0, s.vram_total_mb - headroom_mb(s.vram_total_mb, self._cfg.get()) - others)

    def prefer_small_llm(self) -> bool:
        return self.mode == "silent" and not self.decision.away

    # ---------------------------------------------------------------- loop

    def watched(self) -> None:
        """The UI shows live numbers (SSE stream open): sample every TICK seconds."""
        wake = self.idle()
        self._viewer_at = time.monotonic()
        if wake:
            self._stop_wait.set()

    def idle(self) -> bool:
        """No job and nobody watching: the governor only takes a cheap CPU / RAM sample every
        IDLE_TICK seconds and leaves the GPU alone (reading it can wake a sleeping laptop GPU)."""
        return not self.busy() and time.monotonic() - self._viewer_at > VIEWER_TIMEOUT

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - the governor must never take the server down
                from .ui import console

                console.print(f"[yellow]Governor tick failed: {exc}[/]")
            self._stop_wait.wait(IDLE_TICK if self.light else TICK)
            self._stop_wait.clear()

    def _scan_processes(self, cfg: dict) -> None:
        apps, ollama, games = set(), [], {}
        patterns = list(cfg.get("perf_games") or DEFAULT_GAMES)
        for p in psutil.process_iter(["name"]):
            n = (p.info.get("name") or "").lower()
            if n in OLLAMA_NAMES:
                ollama.append(p)
            n = n[:-4] if n.endswith(".exe") else n
            apps.add(n)
            if _match(n, patterns):
                games[p.pid] = n
        self._apps, self._ollama, self._games = apps, ollama, games

    def tick(self) -> None:
        t0 = time.perf_counter()
        # Ask the job manager BEFORE taking our lock: the job list takes its lock and then ours
        # (paused_total for the ETAs), so the other order would deadlock the whole server.
        idle = self.idle()
        with self._lock:
            cfg = self._cfg.get()
            if idle:
                s = self.monitor.sample(set(self._ours), light=True)
                self.sample, self.light = s, True
                self.decision = Decision("idle", priority=self.decision.priority, cores=self.decision.cores)
                row = s.to_dict()
                row["state"] = "idle"
                self.history.append(row)
                self.rev += 1
                self._tick_n = 0  # rescan processes on the next full tick
                self.tick_seconds = time.perf_counter() - t0
                return
            self.light = False
            if self._tick_n % 5 == 0:
                self._scan_processes(cfg)
            self._tick_n += 1
            busy = self.busy()
            ollama_ours = busy or any(p.pid in self._ours for p in self._ollama)
            ours = set(self._ours) | ({p.pid for p in self._ollama} if ollama_ours else set())
            s = self.monitor.sample(ours)
            override = time.monotonic() < self._override_until
            d = decide(self.mode, s, cfg, self._mem, ours, self._apps, override=override,
                       games_running=self._games)
            if override and d.reason is None and not d.paused:
                self._override_until = 0.0  # the reason is gone: the next pause counts again
            self.sample, self.decision = s, d
            external = [p for p in self._ollama if p.pid not in self._ours] if busy else []
            if not busy:
                self.enforcer.restore_external()
            self._ours = self.enforcer.apply(procs.Policy(d.priority, d.cores, low_io=d.priority != procs.NORMAL),
                                             external)
            row = s.to_dict()
            row["state"] = d.state
            self.history.append(row)
            self._set_paused(d.paused and not self._stop.is_set())
            self.rev += 1
            self.tick_seconds = time.perf_counter() - t0
        self.notify()

    def notify(self) -> None:
        for cb in list(self.on_change):
            try:
                cb()
            except Exception:  # noqa: BLE001
                pass

    def _set_paused(self, paused: bool) -> None:
        if paused and self._go.is_set():
            self._go.clear()
            self._paused_since = time.monotonic()
            procs.suspend_all()
            if self.busy():  # give the game the VRAM now, not at the job's next safe point
                threading.Thread(target=_unload_llm, name="sharkyclips-llm-unload", daemon=True).start()
        elif not paused and not self._go.is_set():
            if self._paused_since:
                self._paused_total += time.monotonic() - self._paused_since
            self._paused_since = None
            procs.resume_all()
            self._go.set()

    # ---------------------------------------------------------------- view

    def view(self, history: bool = False) -> dict:
        d, s = self.decision, self.sample
        total = s.vram_total_mb if s else None
        cfg = self._cfg.get()
        out = {
            "mode": self.mode, "state": d.state, "reason": d.reason, "detail": d.detail, "away": d.away,
            "throttle": d.throttle, "cores": d.cores, "cpu_count": psutil.cpu_count() or 1,
            "override": time.monotonic() < self._override_until,
            "paused": self.paused, "busy": self.busy(),
            "sample": s.to_dict() if s else None,
            "limits": {"gpu_temp": float(cfg.get("perf_gpu_temp_limit") or 85),
                       "vram_headroom_mb": round(headroom_mb(total, cfg)) if total else None,
                       "vram_budget_mb": None if self.vram_budget_mb() is None else round(self.vram_budget_mb())},
            "sensors": {"gpu": self.monitor.nvml.ok, "per_process_gpu": self.monitor.counters.ok,
                        "gpu_name": self.monitor.nvml.names[0] if self.monitor.nvml.names else None},
            "job_object": procs.server_job() is not None,
        }
        if history:
            out["history"] = list(self.history)
        return out


def _unload_llm() -> None:
    try:
        from . import llm

        llm.unload_all()
    except Exception:  # noqa: BLE001
        pass


# ===================================================================== module helpers

_gov: Governor | None = None
_tls = threading.local()


def install(busy: Callable[[], bool] = lambda: False, start: bool = True) -> Governor:
    global _gov
    if _gov is None:
        _gov = Governor(busy)
        if start:
            _gov.start()
    return _gov


def get() -> Governor | None:
    return _gov


def set_current_job(job) -> None:
    _tls.job = job


def current_job():
    return getattr(_tls, "job", None)


@contextlib.contextmanager
def deferred() -> Iterator[None]:
    """Inside: safe points don't pause (only throttle). Used while a GPU model is busy with a
    chunk, so a pause happens at the chunk boundary where the model can be unloaded first."""
    old = getattr(_tls, "defer", False)
    _tls.defer = True
    try:
        yield
    finally:
        _tls.defer = old


def _throttle(g: Governor) -> None:
    th = g.decision.throttle
    now = time.monotonic()
    last = getattr(_tls, "t", None)
    if th <= 0 or last is None or now - last > 5:
        _tls.t = now
        return
    worked = now - last
    if worked >= 0.25:
        time.sleep(min(1.5, worked * th))
        _tls.t = time.monotonic()


def gate(stop: threading.Event | None = None) -> None:
    """Hot-loop safe point for any thread: waits while paused, throttles otherwise."""
    g = _gov
    if g is None:
        return
    if not g._go.is_set() and not getattr(_tls, "defer", False):
        epoch = g.cancel_epoch
        while not g._go.wait(0.5):
            if stop is not None and stop.is_set():
                return
            job = current_job()
            if job is not None and job.cancel_requested:
                raise JobCancelled()
            if g.cancel_epoch != epoch:  # a job was cancelled: let its helper threads run out
                return
        _tls.t = time.monotonic()
    _throttle(g)


def checkpoint(release: Callable[[], None] | None = None) -> bool:
    """Safe point in a job's thread. Raises JobCancelled if the job was cancelled; while
    paused, calls `release()` once (free GPU memory) and waits. Returns True if it paused."""
    job = current_job()
    if job is not None and job.cancel_requested:
        raise JobCancelled()
    g = _gov
    if g is None:
        return False
    if g.light:  # the governor was idle (no job): decide now, not up to 10 s later
        g.tick()
    if g._go.is_set() or getattr(_tls, "defer", False):
        _throttle(g)
        return False
    if release is not None:
        try:
            release()
        except Exception:  # noqa: BLE001
            pass
    if job is not None:
        job.paused = True
        g.notify()
    try:
        while not g._go.wait(0.5):
            if job is not None and job.cancel_requested:
                raise JobCancelled()
    finally:
        if job is not None:
            job.paused = False
    _tls.t = time.monotonic()
    return True


def cpu_threads(default: int | None = None) -> int:
    """Thread budget for CPU-heavy work (the CLI, without a governor: `default` or all cores)."""
    g = _gov
    if g is None:
        return default or psutil.cpu_count() or 1
    return g.cpu_threads()


def prefer_small_llm() -> bool:
    return _gov is not None and _gov.prefer_small_llm()


def vram_budget_mb() -> float | None:
    return None if _gov is None else _gov.vram_budget_mb()


def limit_thread_pools() -> None:
    """Cap math-library thread pools at half the cores (set before numpy/onnx load).
    SharkyClips's own heavy steps size their worker pools from cpu_threads() instead."""
    half = str(max(1, (psutil.cpu_count() or 2) // 2))
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS"):
        os.environ.setdefault(var, half)
