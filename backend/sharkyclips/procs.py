"""Child-process control: priority, CPU limits, suspend/resume, and no orphans.

Windows: the server puts itself into a Job Object. Every process it starts (ffmpeg, the OCR
workers, an `ollama serve` we launched, ...) is automatically in the same job, so
  * one call changes the priority class and CPU affinity of ALL of them (governor modes), and
  * when the server exits or crashes, Windows kills everything in the job (KILL_ON_JOB_CLOSE).
I/O priority is set per process (psutil) as new children appear.

macOS: background QoS (PRIO_DARWIN_BG = low CPU, I/O and GPU priority, reversible) per process;
the supervisor runs the server in its own process group and kills the group afterwards.
Linux: CPU affinity only.

Long-running children (renders, audio extraction, frame decoders) are registered with
`track()`, so the governor can suspend them while paused and resume them exactly where they were.
"""

from __future__ import annotations

import atexit
import ctypes
import os
import platform
import signal
import subprocess
import threading
import weakref

import psutil

IS_WIN = os.name == "nt"
IS_MAC = platform.system() == "Darwin"

# Windows priority classes
IDLE = 0x40
BELOW_NORMAL = 0x4000
NORMAL = 0x20
_PRIORITY_NAMES = {IDLE: "idle", BELOW_NORMAL: "below_normal", NORMAL: "normal"}


# ======================================================================= Windows job


if IS_WIN:
    from ctypes import wintypes

    class _BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount",
                                                      "OtherOperationCount", "ReadTransferCount",
                                                      "WriteTransferCount", "OtherTransferCount")]

    class _EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BASIC), ("IoInfo", _IO),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.GetCurrentProcess.restype = wintypes.HANDLE

    _KILL_ON_CLOSE = 0x2000
    _DIE_ON_UNHANDLED = 0x400  # no "program stopped working" dialogs from crashed children
    _LIMIT_PRIORITY = 0x20
    _LIMIT_AFFINITY = 0x10
    _EXTENDED_INFO = 9


class Job:
    """A Windows Job Object (does nothing elsewhere)."""

    def __init__(self, kill_on_close: bool = True):
        self.handle = None
        self.flags = 0
        self.priority = None
        self.affinity = None
        if not IS_WIN:
            return
        h = _k32.CreateJobObjectW(None, None)
        if not h:
            return
        self.handle = h
        self.flags = (_KILL_ON_CLOSE if kill_on_close else 0) | _DIE_ON_UNHANDLED
        self._apply()

    @property
    def ok(self) -> bool:
        return self.handle is not None

    def _apply(self) -> bool:
        info = _EXTENDED()
        flags = self.flags
        if self.priority is not None:
            flags |= _LIMIT_PRIORITY
            info.BasicLimitInformation.PriorityClass = self.priority
        if self.affinity:
            flags |= _LIMIT_AFFINITY
            info.BasicLimitInformation.Affinity = self.affinity
        info.BasicLimitInformation.LimitFlags = flags
        return bool(_k32.SetInformationJobObject(self.handle, _EXTENDED_INFO, ctypes.byref(info),
                                                 ctypes.sizeof(info)))

    def set_limits(self, priority: int | None, affinity: int | None) -> bool:
        if not self.ok:
            return False
        if (priority, affinity) == (self.priority, self.affinity):
            return True
        self.priority, self.affinity = priority, affinity
        return self._apply()

    def assign_self(self) -> bool:
        return bool(self.ok and _k32.AssignProcessToJobObject(self.handle, _k32.GetCurrentProcess()))

    def assign(self, pid: int) -> bool:
        if not self.ok:
            return False
        h = _k32.OpenProcess(0x0101, False, pid)  # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        if not h:
            return False
        try:
            return bool(_k32.AssignProcessToJobObject(self.handle, h))
        finally:
            _k32.CloseHandle(h)


_job: Job | None = None


def server_job() -> Job | None:
    return _job


def contain_server() -> Job | None:
    """Called once by the web server: from now on every child process is contained."""
    global _job
    if _job is None and IS_WIN:
        job = Job(kill_on_close=True)
        if job.ok and job.assign_self():
            _job = job
    atexit.register(kill_children)
    if not IS_WIN:
        def _term(_sig, _frame):
            kill_children()
            raise SystemExit(0)
        try:
            signal.signal(signal.SIGTERM, _term)
        except ValueError:  # not the main thread
            pass
    return _job


# ======================================================================== priorities


def affinity_mask(cores: int, total: int | None = None) -> int | None:
    """Mask of the LAST `cores` logical CPUs (on hybrid Intel CPUs those are the efficiency
    cores, which leaves the fast cores to the game / browser). None = no limit."""
    total = total or psutil.cpu_count() or 1
    if cores >= total or total > 64:  # >64 CPUs: processor groups, leave it alone
        return None
    cores = max(1, cores)
    return ((1 << cores) - 1) << (total - cores)


_DARWIN_BG = 0x1000
_PRIO_DARWIN_PROCESS = 4
_libc = None


def _darwin_bg(pid: int, on: bool) -> None:
    global _libc
    try:
        if _libc is None:
            _libc = ctypes.CDLL(None, use_errno=True)
        _libc.setpriority(_PRIO_DARWIN_PROCESS, pid, _DARWIN_BG if on else 0)
    except (OSError, AttributeError):
        pass


class Policy:
    """What the governor wants right now."""

    def __init__(self, priority: int = NORMAL, cores: int | None = None, low_io: bool = False):
        self.priority = priority
        self.cores = cores  # None = all
        self.low_io = low_io

    def key(self) -> tuple:
        return (self.priority, self.cores, self.low_io)

    def to_dict(self) -> dict:
        return {"priority": _PRIORITY_NAMES.get(self.priority, str(self.priority)), "cores": self.cores,
                "low_io": self.low_io}


class Enforcer:
    """Applies a Policy to the server, its children and (optionally) other processes such as
    an Ollama server started by the user. Call `apply()` every governor tick: it only touches
    processes that are new or whose policy changed."""

    def __init__(self):
        self.me = psutil.Process()
        self.policy = Policy()
        self._done: dict[int, tuple] = {}  # pid -> policy key applied
        self._external: dict[int, psutil.Process] = {}

    def tree(self) -> list[psutil.Process]:
        try:
            return [self.me, *self.me.children(recursive=True)]
        except psutil.Error:
            return [self.me]

    def apply(self, policy: Policy, external: list[psutil.Process] | None = None) -> set[int]:
        """Returns the pids of our own process tree."""
        changed = policy.key() != self.policy.key()
        self.policy = policy
        job = server_job()
        total = psutil.cpu_count() or 1
        mask = affinity_mask(policy.cores, total) if policy.cores else None
        if job is not None:
            job.set_limits(policy.priority, mask)
        procs = self.tree()
        pids = {p.pid for p in procs}
        others = []
        for p in external or []:
            if p.pid not in pids:
                others.append(p)
                self._external[p.pid] = p
        key = policy.key()
        for p in procs + others:
            if self._done.get(p.pid) == key and not changed:
                continue
            self._set(p, policy, mask, in_job=job is not None and p.pid in pids)
            self._done[p.pid] = key
        alive = pids | {p.pid for p in others}
        for pid in [k for k in self._done if k not in alive]:
            self._done.pop(pid, None)
            self._external.pop(pid, None)
        return pids

    def _set(self, p: psutil.Process, policy: Policy, mask: int | None, in_job: bool) -> None:
        low = policy.priority != NORMAL
        try:
            if IS_WIN:
                if not in_job:  # inside the job, the job sets priority + affinity
                    p.nice({IDLE: psutil.IDLE_PRIORITY_CLASS, BELOW_NORMAL: psutil.BELOW_NORMAL_PRIORITY_CLASS}
                           .get(policy.priority, psutil.NORMAL_PRIORITY_CLASS))
                    cpus = list(range(psutil.cpu_count() or 1))
                    if mask:
                        cpus = [i for i in cpus if mask >> i & 1]
                    p.cpu_affinity(cpus)
                p.ionice(psutil.IOPRIO_LOW if (policy.low_io or low) else psutil.IOPRIO_NORMAL)
            elif IS_MAC:
                _darwin_bg(p.pid, low)
            elif hasattr(p, "cpu_affinity"):
                cpus = list(range(psutil.cpu_count() or 1))
                if mask:
                    cpus = [i for i in cpus if mask >> i & 1]
                p.cpu_affinity(cpus)
        except (psutil.Error, OSError, ValueError, AttributeError):
            pass

    def restore_external(self) -> None:
        """Give processes we don't own (the user's Ollama) their normal priority back."""
        for p in list(self._external.values()):
            self._set(p, Policy(), None, in_job=False)
        self._external.clear()


# ======================================================================== tracking


_tracked: "weakref.WeakSet[subprocess.Popen]" = weakref.WeakSet()
_lock = threading.Lock()
_suspended: set[int] = set()


def track(proc: subprocess.Popen) -> subprocess.Popen:
    """Register a long-running child: suspended while the governor pauses, killed on exit."""
    with _lock:
        _tracked.add(proc)
        paused = _paused
    if paused:
        _suspend(proc)
    return proc


def untrack(proc: subprocess.Popen) -> None:
    with _lock:
        _tracked.discard(proc)
        _suspended.discard(proc.pid)


_paused = False


def _suspend(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        psutil.Process(proc.pid).suspend()
        _suspended.add(proc.pid)
    except (psutil.Error, OSError):
        pass


def suspend_all() -> int:
    global _paused
    with _lock:
        _paused = True
        procs = list(_tracked)
    for p in procs:
        if p.pid not in _suspended:
            _suspend(p)
    return len(procs)


def resume_all() -> None:
    global _paused
    with _lock:
        _paused = False
        procs = list(_tracked)
    for p in procs:
        if p.pid in _suspended:
            try:
                psutil.Process(p.pid).resume()
            except (psutil.Error, OSError):
                pass
            _suspended.discard(p.pid)


def resume_pid(pid: int) -> None:
    try:
        psutil.Process(pid).resume()
    except (psutil.Error, OSError):
        pass


def kill_children() -> None:
    """Kill every process this one started (also the ones started by them)."""
    try:
        kids = psutil.Process().children(recursive=True)
    except psutil.Error:
        return
    for k in kids:
        try:
            if k.status() == psutil.STATUS_STOPPED:
                k.resume()
        except (psutil.Error, OSError):
            pass
        try:
            k.kill()
        except (psutil.Error, OSError):
            pass
    psutil.wait_procs(kids, timeout=3)


CREATE_NO_WINDOW = 0x08000000
_CREATE_NEW_CONSOLE = 0x10
_DETACHED_PROCESS = 0x8
_STARTF_USESHOWWINDOW = 0x1
_SW_HIDE = 0


def _hidden_startupinfo(si=None):
    si = si if si is not None else subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    si.dwFlags |= _STARTF_USESHOWWINDOW
    si.wShowWindow = _SW_HIDE
    return si


def no_window(extra_flags: int = 0) -> dict:
    """kwargs for EVERY subprocess.run / Popen in SharkyClips: `subprocess.run(cmd, **no_window())`.

    Windows: CREATE_NO_WINDOW plus a STARTUPINFO that says SW_HIDE, so no console window ever
    flashes up (tests/test_no_window.py fails on a call without it). Elsewhere: {} (or just
    `extra_flags`, which are Windows creation flags and ignored there)."""
    if not IS_WIN:
        return {}
    # Never detached / a new console: a child without a console makes every console program IT
    # starts (ollama -> llama-server, ...) open a visible window. A hidden one is inherited.
    extra_flags &= ~(_DETACHED_PROCESS | _CREATE_NEW_CONSOLE)
    return {"creationflags": CREATE_NO_WINDOW | extra_flags, "startupinfo": _hidden_startupinfo()}


def run_streamed(cmd: list[str], **kwargs) -> int:
    """Run a console tool (pip, npm, an installer) without a window and copy its output to
    ours line by line, so a terminal user still sees it. Returns the exit code."""
    import sys

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", **kwargs, **no_window())
    assert proc.stdout is not None
    for line in proc.stdout:
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except (OSError, ValueError, AttributeError):  # pythonw: no stdout
            pass
    return proc.wait()


_hidden = False


def hide_child_windows() -> None:
    """Windows safety net under no_window(): every program this process starts from now on,
    including the ones libraries start on their own (yt-dlp, ...), gets CREATE_NO_WINDOW and a
    hidden STARTUPINFO, so no black window ever flashes up - essential without a console of
    our own (pythonw)."""
    global _hidden
    if not IS_WIN or _hidden:
        return
    _hidden = True
    original = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):
        flags = kwargs.get("creationflags", 0) or 0
        if not flags & _CREATE_NEW_CONSOLE:  # an explicit new console asked for a window
            # DETACHED -> hidden console: a detached child's own children each get a window
            kwargs["creationflags"] = (flags & ~_DETACHED_PROCESS) | CREATE_NO_WINDOW
        kwargs["startupinfo"] = _hidden_startupinfo(kwargs.get("startupinfo"))
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__  # type: ignore[method-assign]
