"""Cheap system sensors for the resource governor (see governor.py).

Everything here is read through OS APIs in-process (no helper programs started per sample),
so one sample costs a few milliseconds:

  * CPU / RAM            psutil
  * NVIDIA GPU           NVML (nvml.dll / libnvidia-ml, ships with the driver): load, VRAM, temperature
  * per-process GPU      Windows performance counters ("GPU Engine", "GPU Process Memory"), the same
                         numbers Task Manager shows: lets us split "ClipForge" from "other apps" and
                         see video decoding (a video playing) and video encoding (OBS recording)
  * the user             foreground window + fullscreen state, seconds since the last keyboard/mouse
                         input, locked screen (Windows; macOS: idle time + front app)

Every function degrades to None / empty when a sensor isn't available.
"""

from __future__ import annotations

import ctypes
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field

import psutil

IS_WIN = os.name == "nt"
IS_MAC = platform.system() == "Darwin"


# ===================================================================== NVML (NVIDIA)


class _NvmlMemory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


class _NvmlUtil(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class Nvml:
    """Minimal NVML binding: utilization, memory and temperature of GPU 0..n."""

    def __init__(self):
        self.lib = None
        self.handles: list = []
        self.names: list[str] = []
        try:
            if IS_WIN:
                path = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvml.dll")
                if not os.path.isfile(path):
                    path = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                                        "NVIDIA Corporation", "NVSMI", "nvml.dll")
                lib = ctypes.WinDLL(path)
            elif sys.platform.startswith("linux"):
                lib = ctypes.CDLL("libnvidia-ml.so.1")
            else:
                return
            if lib.nvmlInit_v2() != 0:
                return
            count = ctypes.c_uint()
            if lib.nvmlDeviceGetCount_v2(ctypes.byref(count)) != 0:
                return
            for i in range(count.value):
                h = ctypes.c_void_p()
                if lib.nvmlDeviceGetHandleByIndex_v2(i, ctypes.byref(h)) == 0:
                    self.handles.append(h)
                    buf = ctypes.create_string_buffer(96)
                    lib.nvmlDeviceGetName(h, buf, 96)
                    self.names.append(buf.value.decode(errors="replace"))
            self.lib = lib if self.handles else None
        except (OSError, AttributeError):
            self.lib = None

    @property
    def ok(self) -> bool:
        return self.lib is not None

    def read(self, index: int = 0) -> dict | None:
        if not self.lib or index >= len(self.handles):
            return None
        h = self.handles[index]
        out: dict = {"name": self.names[index]}
        mem = _NvmlMemory()
        if self.lib.nvmlDeviceGetMemoryInfo(h, ctypes.byref(mem)) == 0:
            out["vram_total_mb"] = mem.total / 1048576
            out["vram_used_mb"] = mem.used / 1048576
        util = _NvmlUtil()
        if self.lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(util)) == 0:
            out["util"] = float(util.gpu)
        temp = ctypes.c_uint()
        if self.lib.nvmlDeviceGetTemperature(h, 0, ctypes.byref(temp)) == 0:  # 0 = GPU core
            out["temp"] = float(temp.value)
        return out


# ===================================================== Windows performance counters (PDH)


class _PdhValue(ctypes.Structure):
    _fields_ = [("CStatus", ctypes.c_ulong), ("doubleValue", ctypes.c_double)]


class _PdhItem(ctypes.Structure):
    _fields_ = [("szName", ctypes.c_wchar_p), ("FmtValue", _PdhValue)]


_PDH_FMT_DOUBLE = 0x00000200
_PDH_FMT_NOCAP100 = 0x00008000
_PDH_MORE_DATA = 0x800007D2
_PID = re.compile(r"pid_(\d+)_luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)")


class GpuCounters:
    """Per-process GPU engine load and dedicated VRAM (Windows 10 1709+)."""

    def __init__(self):
        self.ok = False
        if not IS_WIN:
            return
        try:
            self.pdh = ctypes.WinDLL("pdh.dll")
            for fn in ("PdhOpenQueryW", "PdhAddEnglishCounterW", "PdhCollectQueryData",
                       "PdhGetFormattedCounterArrayW"):
                getattr(self.pdh, fn).restype = ctypes.c_ulong  # PDH status codes are unsigned
            self.query = ctypes.c_void_p()
            if self.pdh.PdhOpenQueryW(None, None, ctypes.byref(self.query)) != 0:
                return
            self.engine = ctypes.c_void_p()
            self.memory = ctypes.c_void_p()
            add = self.pdh.PdhAddEnglishCounterW
            if add(self.query, r"\GPU Engine(*)\Utilization Percentage", None, ctypes.byref(self.engine)) != 0:
                return
            if add(self.query, r"\GPU Process Memory(*)\Dedicated Usage", None, ctypes.byref(self.memory)) != 0:
                return
            self.pdh.PdhCollectQueryData(self.query)  # rates need two samples
            self.ok = True
        except (OSError, AttributeError):
            self.ok = False

    def _array(self, counter) -> list[tuple[str, float]]:
        size, count = ctypes.c_ulong(0), ctypes.c_ulong(0)
        fn = self.pdh.PdhGetFormattedCounterArrayW
        flags = _PDH_FMT_DOUBLE | _PDH_FMT_NOCAP100
        rc = fn(counter, flags, ctypes.byref(size), ctypes.byref(count), None)
        if rc != _PDH_MORE_DATA or size.value == 0:
            return []
        buf = (ctypes.c_byte * size.value)()
        rc = fn(counter, flags, ctypes.byref(size), ctypes.byref(count), buf)
        if rc != 0:
            return []
        items = ctypes.cast(buf, ctypes.POINTER(_PdhItem))
        return [(items[i].szName or "", items[i].FmtValue.doubleValue) for i in range(count.value)
                if items[i].FmtValue.CStatus in (0, 1)]

    def read(self) -> dict | None:
        """{"engine": [(pid, luid, engtype, percent)], "memory": [(pid, luid, bytes)]}"""
        if not self.ok:
            return None
        if self.pdh.PdhCollectQueryData(self.query) != 0:
            return None
        engine = []
        for name, value in self._array(self.engine):
            m = _PID.search(name)
            if m and value > 0:
                engine.append((int(m.group(1)), m.group(2), name.rsplit("engtype_", 1)[-1], value))
        memory = []
        for name, value in self._array(self.memory):
            m = _PID.search(name)
            if m and value > 0:
                memory.append((int(m.group(1)), m.group(2), value))
        return {"engine": engine, "memory": memory}


# ============================================================================ the user


@dataclass
class UserState:
    idle_seconds: float | None = None  # since the last keyboard / mouse input
    locked: bool = False
    fg_pid: int | None = None
    fg_name: str | None = None  # process name, lower case, without .exe
    fg_title: str = ""
    fullscreen: bool = False  # the foreground window covers its whole monitor
    d3d_fullscreen: bool = False  # Windows says: exclusive fullscreen game / presentation


if IS_WIN:
    from ctypes import wintypes

    class _LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.IsZoomed.argtypes = [wintypes.HWND]
    _user32.MonitorFromWindow.restype = wintypes.HANDLE
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.OpenInputDesktop.restype = wintypes.HANDLE
    _user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                  wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    _kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    try:
        _shell32 = ctypes.WinDLL("shell32")
    except OSError:
        _shell32 = None

    _SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

    def _idle_seconds() -> float | None:
        info = _LASTINPUTINFO(ctypes.sizeof(_LASTINPUTINFO), 0)
        if not _user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        now = _kernel32.GetTickCount64() & 0xFFFFFFFF  # dwTime is a 32-bit tick count
        return ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0

    def _locked() -> bool:
        """The input desktop isn't the normal one (lock screen / UAC prompt)."""
        h = _user32.OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS
        if not h:
            return True  # can't open the input desktop: the secure (lock) desktop is active
        try:
            buf = ctypes.create_unicode_buffer(64)
            need = wintypes.DWORD()
            if _user32.GetUserObjectInformationW(h, 2, buf, ctypes.sizeof(buf), ctypes.byref(need)):  # UOI_NAME
                return buf.value.lower() != "default"
            return False
        finally:
            _user32.CloseDesktop(h)

    _names: dict[int, str] = {}

    def _proc_name(pid: int) -> str | None:
        name = _names.get(pid)
        if name is None:
            try:
                name = psutil.Process(pid).name().lower()
            except (psutil.Error, OSError):
                return None
            name = name[:-4] if name.endswith(".exe") else name
            if len(_names) > 500:
                _names.clear()
            _names[pid] = name
        return name

    def read_user() -> UserState:
        st = UserState(idle_seconds=_idle_seconds(), locked=_locked())
        if _shell32 is not None:
            q = ctypes.c_int(0)
            if _shell32.SHQueryUserNotificationState(ctypes.byref(q)) == 0:
                st.d3d_fullscreen = q.value in (3, 4)  # RUNNING_D3D_FULL_SCREEN, PRESENTATION_MODE
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return st
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        st.fg_pid = pid.value or None
        st.fg_name = _proc_name(pid.value) if pid.value else None
        title = ctypes.create_unicode_buffer(256)
        _user32.GetWindowTextW(hwnd, title, 256)
        st.fg_title = title.value
        cls = ctypes.create_unicode_buffer(64)
        _user32.GetClassNameW(hwnd, cls, 64)
        if cls.value in _SHELL_CLASSES:
            return st
        rect = wintypes.RECT()
        mon = _user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        if mon and _user32.GetWindowRect(hwnd, ctypes.byref(rect)) and _user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
            m = mi.rcMonitor
            # A maximized window can cover the monitor too (auto-hidden taskbar): not fullscreen.
            st.fullscreen = (rect.left <= m.left and rect.top <= m.top and rect.right >= m.right
                             and rect.bottom >= m.bottom and not _user32.IsZoomed(hwnd))
        return st

elif IS_MAC:
    def _mac_idle() -> float | None:
        try:
            cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
            fn = cg.CGEventSourceSecondsSinceLastEventType
            fn.restype = ctypes.c_double
            fn.argtypes = [ctypes.c_int, ctypes.c_uint32]
            return float(fn(1, 0xFFFFFFFF))  # combined session state, any input event
        except (OSError, AttributeError):
            return None

    _front_cache = {"t": 0.0, "name": None}

    def _mac_front_app() -> str | None:
        """Front app name via lsappinfo (cached a few seconds; it starts a tiny helper)."""
        now = time.monotonic()
        if now - _front_cache["t"] < 4:
            return _front_cache["name"]
        name = None
        try:
            asn = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True, timeout=2).stdout.strip()
            if asn:
                out = subprocess.run(["lsappinfo", "info", "-only", "name", asn], capture_output=True,
                                     text=True, timeout=2).stdout
                m = re.search(r'"(?:LSDisplayName|name)"="([^"]+)"', out)
                name = m.group(1).lower() if m else None
        except (OSError, subprocess.SubprocessError):
            name = None
        _front_cache.update(t=now, name=name)
        return name

    def read_user() -> UserState:
        return UserState(idle_seconds=_mac_idle(), fg_name=_mac_front_app())

else:
    def read_user() -> UserState:
        return UserState()


# ========================================================================== the sample


@dataclass
class Sample:
    t: float
    cpu: float  # whole system, 0-100
    cpu_ours: float  # ClipForge's process tree, 0-100 of the whole machine
    ram_used_mb: float
    ram_total_mb: float
    ram_ours_mb: float
    gpu: float | None = None  # 0-100
    gpu_ours: float | None = None
    vram_used_mb: float | None = None
    vram_total_mb: float | None = None
    vram_ours_mb: float | None = None
    gpu_temp: float | None = None
    cpu_temp: float | None = None
    video_decode: bool = False  # another app decodes video on a GPU (a video is playing)
    video_apps: set[str] = field(default_factory=set)  # which apps (process names) decode video
    video_encode_pids: list[int] = field(default_factory=list)  # other apps encoding video (OBS, ...)
    per_process_gpu: bool = False  # the two above and the *_ours GPU numbers were measured
    gpu_pids: dict[int, float] = field(default_factory=dict)  # other apps' 3D engine load by pid
    user: UserState = field(default_factory=UserState)

    def to_dict(self) -> dict:
        r = lambda v, n=1: None if v is None else round(v, n)  # noqa: E731
        return {"t": round(self.t, 1), "cpu": r(self.cpu), "cpu_ours": r(self.cpu_ours),
                "ram_used_mb": r(self.ram_used_mb, 0), "ram_total_mb": r(self.ram_total_mb, 0),
                "ram_ours_mb": r(self.ram_ours_mb, 0), "gpu": r(self.gpu), "gpu_ours": r(self.gpu_ours),
                "vram_used_mb": r(self.vram_used_mb, 0), "vram_total_mb": r(self.vram_total_mb, 0),
                "vram_ours_mb": r(self.vram_ours_mb, 0), "gpu_temp": r(self.gpu_temp, 0),
                "cpu_temp": r(self.cpu_temp, 0)}


def _cpu_temp() -> float | None:
    """Only Linux exposes CPU temperature without admin rights or extra drivers."""
    fn = getattr(psutil, "sensors_temperatures", None)
    if fn is None:
        return None
    try:
        temps = fn()
    except Exception:  # noqa: BLE001
        return None
    for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
        if temps.get(key):
            return max(t.current for t in temps[key])
    return None


class Monitor:
    """Takes samples. `ours()` returns the pids that count as ClipForge."""

    def __init__(self):
        self.nvml = Nvml()
        self.counters = GpuCounters()
        self.cores = psutil.cpu_count() or 1
        self._procs: dict[int, psutil.Process] = {}
        self._gpu_luid: str | None = None
        psutil.cpu_percent(None)

    def _ours_cpu_ram(self, pids: set[int]) -> tuple[float, float]:
        cpu = ram = 0.0
        for pid in list(self._procs):
            if pid not in pids:
                self._procs.pop(pid, None)
        for pid in pids:
            p = self._procs.get(pid)
            try:
                if p is None:
                    p = self._procs[pid] = psutil.Process(pid)
                    p.cpu_percent(None)  # first call primes the counter
                    continue
                cpu += p.cpu_percent(None)
                ram += p.memory_info().rss
            except (psutil.Error, OSError):
                self._procs.pop(pid, None)
        return min(100.0, cpu / self.cores), ram / 1048576

    def sample(self, ours: set[int], light: bool = False) -> Sample:
        """light=True: CPU / RAM only (nothing to decide; the GPU isn't touched)."""
        vm = psutil.virtual_memory()
        cpu_ours, ram_ours = self._ours_cpu_ram(ours)
        s = Sample(t=time.time(), cpu=psutil.cpu_percent(None), cpu_ours=cpu_ours,
                   ram_used_mb=(vm.total - vm.available) / 1048576, ram_total_mb=vm.total / 1048576,
                   ram_ours_mb=ram_ours, cpu_temp=None if light else _cpu_temp())
        if light:
            return s
        g = self.nvml.read(0)
        if g:
            s.gpu, s.gpu_temp = g.get("util"), g.get("temp")
            s.vram_used_mb, s.vram_total_mb = g.get("vram_used_mb"), g.get("vram_total_mb")
        c = self.counters.read()
        if c is not None:
            self._split_gpu(s, c, ours)
        s.user = read_user()
        return s

    def _split_gpu(self, s: Sample, c: dict, ours: set[int]) -> None:
        # Which adapter is the NVIDIA one: the one whose dedicated memory matches NVML best.
        per_luid: dict[str, float] = {}
        for _pid, luid, b in c["memory"]:
            per_luid[luid] = per_luid.get(luid, 0.0) + b / 1048576
        if per_luid:
            if s.vram_used_mb is not None:
                self._gpu_luid = min(per_luid, key=lambda k: abs(per_luid[k] - s.vram_used_mb))
            else:
                self._gpu_luid = max(per_luid, key=per_luid.get)
        luid = self._gpu_luid
        s.per_process_gpu = True
        s.vram_ours_mb = sum(b for pid, lu, b in c["memory"] if pid in ours and lu == luid) / 1048576
        if s.vram_used_mb is None and per_luid and luid:
            s.vram_used_mb = per_luid[luid]
        # Engine load: Task Manager's number is the busiest engine; ClipForge's share is the
        # busiest engine summed over our processes.
        by_engine: dict[str, float] = {}
        ours_engine: dict[str, float] = {}
        for pid, lu, eng, val in c["engine"]:
            if eng.startswith("VideoDecode") and pid not in ours and val >= 1.0:
                s.video_decode = True
                s.video_apps.add(_proc_name(pid) or str(pid))
            if eng.startswith("VideoEncode") and pid not in ours and val >= 1.0:
                s.video_encode_pids.append(pid)
            if lu != luid:
                continue
            if eng.startswith("3D") and pid not in ours:
                s.gpu_pids[pid] = max(s.gpu_pids.get(pid, 0.0), val)
            by_engine[eng] = by_engine.get(eng, 0.0) + val
            if pid in ours:
                ours_engine[eng] = ours_engine.get(eng, 0.0) + val
        s.gpu_ours = min(100.0, max(ours_engine.values(), default=0.0))
        if s.gpu is None:
            s.gpu = min(100.0, max(by_engine.values(), default=0.0))
