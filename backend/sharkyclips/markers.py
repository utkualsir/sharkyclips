"""Live markers: "this moment!" during a stream, from a global hotkey or a "!clip" in chat.

A marker is stored with the wall clock time and, when obs-websocket is reachable, OBS's own
recording time (exact even after a pause). When a finished recording is imported (watch.py),
the markers that fall inside it are written to <project>/markers.json in video seconds; the
highlight engine turns them into top candidates ("marked by you", build-up included).

Global hotkey (Windows): RegisterHotKey on a thread of its own with a message loop. It works
while a game has the focus and never takes the focus away; a short system sound confirms it.
macOS / Linux: not available (macOS needs an accessibility permission prompt; use "!clip").
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable

from . import config
from .project import Project, read_json, write_json_atomic

DEFAULT_HOTKEY = "ctrl+alt+c"
DEFAULT_COMMAND = "!clip"
KEEP_DAYS = 14
DEDUPE_S = 4.0  # two marks this close are one moment (hotkey + a mod's !clip)
BUILD_UP_S = 25.0  # seconds before a marker that the clip keeps (what led to it)
AFTER_S = 6.0

_lock = threading.RLock()


def store_path() -> Path:
    return config.config_dir() / "live" / "markers.json"


def load_all() -> list[dict]:
    with _lock:
        p = store_path()
        try:
            data = read_json(p) if p.is_file() else {}
        except (OSError, ValueError):
            data = {}
        return list(data.get("markers") or [])


def _save_all(items: list[dict]) -> None:
    cutoff = time.time() - KEEP_DAYS * 86400
    items = [m for m in items if float(m.get("at") or 0) >= cutoff][-2000:]
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(p, {"markers": items})


_listeners: list[Callable[[dict], None]] = []


def add(source: str, by: str | None = None, at: float | None = None, note: str | None = None,
        rec: dict | None | bool = True) -> dict | None:
    """Store a marker. rec=True asks OBS for the recording time now (pass a dict to reuse one,
    None to skip). Returns None when it repeats one from a moment ago."""
    at = float(at if at is not None else time.time())
    if rec is True:
        from . import obs

        rec = obs.record_status()
    m: dict = {"id": f"mk{int(at * 1000)}", "at": round(at, 3), "source": source}
    if by:
        m["by"] = str(by)[:40]
    if note:
        m["note"] = str(note)[:80]
    if isinstance(rec, dict) and rec.get("active"):
        m["rec_ms"] = int(rec["ms"])
    with _lock:
        items = load_all()
        if any(abs(float(x["at"]) - at) < DEDUPE_S for x in items[-20:]):
            return None
        items.append(m)
        _save_all(items)
    for fn in list(_listeners):
        try:
            fn(m)
        except Exception:  # noqa: BLE001 - a listener never breaks marking
            pass
    return m


def remove(mid: str) -> bool:
    with _lock:
        items = load_all()
        left = [m for m in items if m.get("id") != mid]
        if len(left) == len(items):
            return False
        _save_all(left)
        return True


def recent(limit: int = 20) -> list[dict]:
    return list(reversed(load_all()))[:limit]


# ===================================================================== markers -> a recording


def for_recording(start: float, end: float, items: list[dict] | None = None) -> tuple[list[dict], float]:
    """Markers inside a recording that ran from `start` to `end` (wall clock): [{"t", ...}] in
    video seconds, and the recording start used (OBS's own time moves it when it knows better)."""
    items = items if items is not None else load_all()
    inside = [m for m in items if start - 5 <= float(m["at"]) <= end + 5]
    # OBS knows the recording time: start = when the marker was set - recording time
    obs_starts = [float(m["at"]) - m["rec_ms"] / 1000 for m in inside if m.get("rec_ms") is not None]
    rec_start = sorted(obs_starts)[len(obs_starts) // 2] if obs_starts else start
    out = []
    for m in inside:
        t = m["rec_ms"] / 1000 if m.get("rec_ms") is not None else float(m["at"]) - rec_start
        if t < 0 or t > end - rec_start + 5:
            continue
        out.append({"t": round(t, 2), "source": m["source"], "by": m.get("by"), "note": m.get("note"),
                    "id": m["id"], "exact": m.get("rec_ms") is not None})
    out.sort(key=lambda x: x["t"])
    return out, rec_start


def project_path(project: Project) -> Path:
    return project.dir / "markers.json"


def attach(project: Project, start: float, end: float) -> list[dict]:
    """Write the markers of a recording into its project (before the highlights run)."""
    got, rec_start = for_recording(start, end)
    if got:
        write_json_atomic(project_path(project), {"markers": got, "recording_start": rec_start})
    return got


def load_project(project: Project) -> list[dict]:
    p = project_path(project)
    try:
        return list((read_json(p) if p.is_file() else {}).get("markers") or [])
    except (OSError, ValueError):
        return []


# ===================================================================== global hotkey (Windows)

MODS = {"ctrl": 0x2, "control": 0x2, "alt": 0x1, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
NAMED_KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "home": 0x24, "end": 0x23, "insert": 0x2D,
              "delete": 0x2E, "pageup": 0x21, "pagedown": 0x22, "pause": 0x13, "scrolllock": 0x91,
              "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
              **{f"num{i}": 0x60 + i for i in range(10)}, **{f"f{i}": 0x6F + i for i in range(1, 25)}}


def parse_hotkey(text: str) -> tuple[int, int]:
    """"ctrl+alt+c" -> (modifiers, virtual key). ValueError when it isn't a usable shortcut."""
    parts = [p.strip().lower() for p in str(text or "").replace(" ", "").split("+") if p.strip()]
    if not parts:
        raise ValueError("empty shortcut")
    mods = 0
    for p in parts[:-1]:
        if p not in MODS:
            raise ValueError(f"unknown modifier {p!r}")
        mods |= MODS[p]
    key = parts[-1]
    if len(key) == 1 and (key.isalpha() and key.isascii() or key.isdigit()):
        vk = ord(key.upper())
    elif key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    else:
        raise ValueError(f"unknown key {key!r}")
    if mods == 0 and not (0x70 <= vk <= 0x87 or key in ("pause", "scrolllock")):
        raise ValueError("a shortcut needs Ctrl, Alt, Shift or Win (or an F key)")
    return mods, vk


def normalize_hotkey(text: str) -> str:
    mods, _vk = parse_hotkey(text)
    parts = [n for n, bit in (("ctrl", 0x2), ("alt", 0x1), ("shift", 0x4), ("win", 0x8)) if mods & bit]
    return "+".join(parts + [str(text).replace(" ", "").split("+")[-1].lower()])


class Hotkey:
    """One global hotkey on its own thread. status: off | on | taken | unsupported | invalid."""

    HOTKEY_ID = 0x5C01

    def __init__(self, on_press: Callable[[], None]):
        self.on_press = on_press
        self.status = "off"
        self.combo: str | None = None
        self._thread: threading.Thread | None = None
        self._tid: int | None = None
        self._ready = threading.Event()

    def start(self, combo: str) -> str:
        self.stop()
        if os.name != "nt":
            self.status = "unsupported"
            return self.status
        try:
            mods, vk = parse_hotkey(combo)
        except ValueError:
            self.status = "invalid"
            return self.status
        self.combo = combo
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, args=(mods, vk), name="sharkyclips-hotkey", daemon=True)
        self._thread.start()
        self._ready.wait(3)
        return self.status

    def _run(self, mods: int, vk: int) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        k32 = ctypes.WinDLL("kernel32")
        self._tid = k32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, self.HOTKEY_ID, mods | MOD_NOREPEAT, vk):
            self.status = "taken"  # another program uses this shortcut
            self._ready.set()
            return
        self.status = "on"
        self._ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312 and msg.wParam == self.HOTKEY_ID:  # WM_HOTKEY
                    threading.Thread(target=self._pressed, daemon=True).start()
        finally:
            user32.UnregisterHotKey(None, self.HOTKEY_ID)

    def _pressed(self) -> None:
        try:
            self.on_press()
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        if self._thread is not None and self._tid is not None and self._thread.is_alive():
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._tid, 0x0012, 0, 0)  # WM_QUIT
            self._thread.join(2)
        self._thread = None
        self._tid = None
        if self.status == "on":
            self.status = "off"


def confirm_sound() -> None:
    """A short system sound: heard over the game, no window, no focus change."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        if os.name == "nt":
            import winsound

            winsound.MessageBeep(winsound.MB_OK)
    except Exception:  # noqa: BLE001
        pass
