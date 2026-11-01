"""One SharkyClips server per settings folder.

Two servers on the same settings folder both run the background loops: the publish scheduler
(both export and upload the same scheduled clip), the job queue (both resume it), the stats
sync. 1.2.11 found this for real: a second server started on port 8001 while the first one
restarted after an update, and both rendered the same clip at the same time.

The `serve` supervisor (the long-lived parent of the web server) holds an OS lock on
<settings>/server.lock for its whole life, across server restarts, and notes its port in
<settings>/server.json. The OS drops the lock when the process ends, even after a crash, so a
stale file never blocks a start. A second `serve` / `launch` sees the lock and opens the
running SharkyClips instead of starting another one.
"""

from __future__ import annotations

import json
import os
import time
from typing import IO, Any

from . import config

LOCK_FILE = "server.lock"
INFO_FILE = "server.json"


def _lock(f: IO[Any]) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def acquire(wait: float = 0.0) -> IO[Any] | None:
    """Take the server lock. Returns the open lock file (keep it for the process's life), or None
    when another SharkyClips holds it. `wait`: keep trying this long (Windows releases a dead
    process's lock a moment after it ended, e.g. right after a crash)."""
    folder = config.config_dir()
    folder.mkdir(parents=True, exist_ok=True)
    end = time.monotonic() + wait
    while True:
        f = open(folder / LOCK_FILE, "a+")  # noqa: SIM115 - held open on purpose
        if _lock(f):
            return f
        f.close()
        if time.monotonic() >= end:
            return None
        time.sleep(0.1)


def release(f: IO[Any] | None) -> None:
    if f is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    f.close()
    (config.config_dir() / INFO_FILE).unlink(missing_ok=True)


def note(port: int) -> None:
    """The lock holder's port, so a second start can open it."""
    path = config.config_dir() / INFO_FILE
    path.write_text(json.dumps({"pid": os.getpid(), "port": port, "since": time.time()}), encoding="utf-8")


def running() -> dict | None:
    """{pid, port, since} of the SharkyClips holding the lock, or None when nobody does."""
    mine = acquire()
    if mine is not None:  # free: nobody runs (release also removes a stale server.json)
        release(mine)
        return None
    try:
        info = json.loads((config.config_dir() / INFO_FILE).read_text(encoding="utf-8"))
        return info if isinstance(info, dict) else {}
    except (OSError, ValueError):
        return {}  # locked, but the port note isn't written yet (starting up)
