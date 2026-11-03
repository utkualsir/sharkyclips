"""Auto clips after a stream: watch the recording folder(s) and start the Easy pipeline when a
new recording is finished.

"Finished" = its size and modification time haven't changed for STABLE_S seconds AND no
program holds it open for writing (Windows: opening it without write sharing must succeed;
macOS / Linux have no such lock, so they wait longer). A file that is still being written is
never opened by anything else here.

- Only recordings written after the watcher was switched on (state "baseline"): files that
  were finished before are never touched (one still being recorded then is taken when it ends).
- OBS remuxing MKV -> MP4: the MP4 is used, the MKV skipped.
- Every decision is kept in <settings>/watch.json, so a restart never imports a recording twice.

The scan is a pure function of the folder listing (tests drive it with fake clocks); the
thread that calls it every few seconds lives in web/live.py.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from . import config
from .obs import VIDEO_EXT
from .project import read_json, write_json_atomic

STABLE_S = 20.0  # unchanged this long (+ unlocked) = finished
STABLE_S_NOLOCK = 60.0  # macOS / Linux: no write lock to check
REMUX_WAIT_S = 180.0  # an MKV waits this long for OBS's MP4 copy
MIN_BYTES = 5 * 1024 * 1024
DEFAULT_TOP = 6
PUBLISH = ("off", "plan", "now")

_lock = threading.RLock()


def state_path() -> Path:
    return config.config_dir() / "watch.json"


def load_state() -> dict:
    with _lock:
        p = state_path()
        try:
            data = read_json(p) if p.is_file() else {}
        except (OSError, ValueError):
            data = {}
        return {"baseline": data.get("baseline"), "files": dict(data.get("files") or {})}


def save_state(data: dict) -> None:
    with _lock:
        files = data.get("files") or {}
        if len(files) > 400:  # keep the newest decisions
            keep = sorted(files.items(), key=lambda kv: -float(kv[1].get("at") or 0))[:300]
            data = {**data, "files": dict(keep)}
        write_json_atomic(state_path(), data)


# ===================================================================== settings


def detected_folder() -> str | None:
    try:
        from . import obs

        return obs.settings().get("record_dir")
    except Exception:  # noqa: BLE001
        return None


def folders() -> list[str]:
    got = config.get("watch_folders")
    if isinstance(got, list) and got:
        return [str(x) for x in got if str(x).strip()]
    d = detected_folder()
    return [d] if d else []


def settings() -> dict:
    pub = config.get("watch_publish")
    top = config.get("watch_render_top")
    custom = config.get("watch_folders")
    return {"enabled": bool(config.get("auto_clip_enabled")), "folders": folders(),
            "custom_folders": isinstance(custom, list) and bool(custom), "detected": detected_folder(),
            "render_top": int(top) if isinstance(top, int) and 1 <= top <= 30 else DEFAULT_TOP,
            "publish": pub if pub in PUBLISH else "off",
            "publish_top": int(config.get("watch_publish_top") or 3),
            "min_minutes": float(config.get("watch_min_minutes") or 2)}


def enable(on: bool) -> None:
    """Switching on sets the baseline: recordings that exist now are never imported."""
    changes: dict = {"auto_clip_enabled": bool(on)}
    config.update(**changes)
    if on:
        st = load_state()
        st["baseline"] = time.time()
        save_state(st)


# ===================================================================== file checks


def is_locked(path: Path) -> bool | None:
    """True when another program has the file open for writing (Windows); None = can't tell."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING = 0x80000000, 0x1, 3
    h = k32.CreateFileW(str(path), GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, 0x80, None)
    if h in (None, wintypes.HANDLE(-1).value, -1):
        err = ctypes.get_last_error()
        return err in (32, 33)  # sharing / lock violation: someone writes it
    k32.CloseHandle(h)
    return False


def _list(folder: Path, exclude: Path | None) -> list[Path]:
    try:
        items = list(folder.iterdir())
    except OSError:
        return []
    out = []
    for p in items:
        if p.suffix.lower() not in VIDEO_EXT or p.name.startswith(".") or not p.is_file():
            continue
        if exclude is not None:
            try:
                p.resolve().relative_to(exclude)
                continue
            except ValueError:
                pass
        out.append(p)
    return out


def scan(paths: list[Path], st: dict, pending: dict, now: float, locked=is_locked,
         auto_remux: bool = False) -> list[Path]:
    """One look at the folder listing. pending: {path: {"size", "mtime", "since"}} kept between
    calls (in memory). Returns the recordings that are finished now (marks them "ready")."""
    baseline = float(st.get("baseline") or now)
    files = st["files"]
    seen_now = set()
    ready: list[Path] = []
    stems = {(p.parent, p.stem.lower()): p for p in paths if p.suffix.lower() == ".mp4"}
    stable_need = STABLE_S if os.name == "nt" else STABLE_S_NOLOCK
    for p in paths:
        key = str(p)
        seen_now.add(key)
        if key in files:
            continue
        try:
            s = p.stat()
        except OSError:
            continue
        born = getattr(s, "st_birthtime", None) or (s.st_ctime if os.name == "nt" else s.st_mtime)
        if s.st_mtime < baseline and born < baseline:
            continue  # it was there before auto clips were switched on
        cur = pending.get(key)
        if cur is None or cur["size"] != s.st_size or cur["mtime"] != s.st_mtime:
            pending[key] = {"size": s.st_size, "mtime": s.st_mtime, "since": now, "born": born}
            continue
        if now - cur["since"] < stable_need:
            continue
        if locked(p):
            cur["since"] = now  # still being written: look again later
            continue
        if s.st_size < MIN_BYTES:
            files[key] = {"status": "skipped", "reason": "too_small", "at": now, "size": s.st_size}
            pending.pop(key, None)
            continue
        if p.suffix.lower() in (".mkv", ".flv"):
            twin = stems.get((p.parent, p.stem.lower()))
            if twin is not None:
                files[key] = {"status": "skipped", "reason": "remuxed", "at": now, "twin": str(twin)}
                pending.pop(key, None)
                continue
            if auto_remux and now - cur["since"] < REMUX_WAIT_S:
                continue  # OBS writes an MP4 copy of it in a moment
        files[key] = {"status": "ready", "at": now, "size": s.st_size, "mtime": s.st_mtime, "born": born}
        pending.pop(key, None)
        ready.append(p)
    for key in list(pending):
        if key not in seen_now:
            pending.pop(key, None)  # deleted / renamed (OBS's remux replaces the name)
    return ready


def candidates_now(now: float | None = None, pending: dict | None = None) -> tuple[list[Path], dict]:
    """Scan every watched folder (used by the watcher thread)."""
    from . import obs

    st = load_state()
    if st.get("baseline") is None:
        st["baseline"] = time.time()
    before = json.dumps(st, sort_keys=True, default=str)
    exclude = None
    try:
        exclude = config.workspace_dir().resolve()
    except OSError:
        pass
    paths: list[Path] = []
    for f in folders():
        d = Path(f).expanduser()
        if d.is_dir():
            paths += _list(d, exclude)
    remux = False
    try:
        remux = bool(obs.settings().get("auto_remux"))
    except Exception:  # noqa: BLE001
        pass
    ready = scan(paths, st, pending if pending is not None else {}, now or time.time(), auto_remux=remux)
    if json.dumps(st, sort_keys=True, default=str) != before:  # no disk write when nothing changed
        save_state(st)
    return ready, st


def mark(path: Path, **fields) -> None:
    with _lock:
        st = load_state()
        cur = st["files"].get(str(path)) or {}
        st["files"][str(path)] = {**cur, **fields, "at": cur.get("at") or time.time()}
        save_state(st)


def recent(limit: int = 8) -> list[dict]:
    st = load_state()
    rows = [{"path": k, "name": Path(k).name, **v} for k, v in st["files"].items()]
    rows.sort(key=lambda r: -float(r.get("at") or 0))
    return rows[:limit]
