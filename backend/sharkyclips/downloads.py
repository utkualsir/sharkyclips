"""Large model downloads (1.2.18): resumable, hash-checked, with progress and cancel.

Used by the cover image model (several GB) and the voice-cloning model. A download writes
<dest>.part, continues where it stopped (HTTP Range) after a broken connection or an app restart,
checks the SHA-256 and only then renames the file into place, so a half file is never used.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import SharkyClipsError

CHUNK = 1 << 18  # small reads: a broken connection loses at most this much
ProgressFn = Callable[[int, int], None]  # (bytes done, bytes total)


@dataclass(frozen=True)
class Remote:
    url: str
    sha256: str
    size: int  # bytes
    name: str  # file name on disk


_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    with _guard:
        return _locks.setdefault(str(path), threading.Lock())


def _hash_file(path: Path, cancel: threading.Event | None = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            if cancel is not None and cancel.is_set():
                raise SharkyClipsError("Download cancelled.")
            b = f.read(CHUNK * 8)
            if not b:
                return h.hexdigest()
            h.update(b)


def fetch(remote: Remote, dest: Path, on_progress: ProgressFn | None = None,
          cancel: threading.Event | None = None, label: str = "model", tries: int = 6) -> Path:
    """Download `remote` to `dest` (resuming a .part). Returns dest. Raises SharkyClipsError."""
    if dest.is_file() and dest.stat().st_size == remote.size:
        return dest
    if os.environ.get("SHARKYCLIPS_NO_DOWNLOADS"):
        raise SharkyClipsError(f"The {label} isn't downloaded yet.")
    import requests

    with _lock_for(dest):
        if dest.is_file() and dest.stat().st_size == remote.size:
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        last_err: Exception | None = None
        for attempt in range(tries):
            have = part.stat().st_size if part.is_file() else 0
            if have > remote.size:
                part.unlink()
                have = 0
            if have < remote.size:
                headers = {"Range": f"bytes={have}-"} if have else {}
                try:
                    with requests.get(remote.url, headers=headers, stream=True, timeout=(15, 60)) as r:
                        if r.status_code == 200 and have:  # the server ignored the range: start over
                            have = 0
                        elif r.status_code not in (200, 206):
                            raise SharkyClipsError(f"The {label} server answered {r.status_code}.")
                        with open(part, "ab" if have else "wb") as f:
                            done = have
                            last_cb = 0.0
                            for chunk in r.iter_content(CHUNK):
                                if cancel is not None and cancel.is_set():
                                    raise SharkyClipsError("Download cancelled.")
                                from . import governor

                                governor.gate()
                                f.write(chunk)
                                done += len(chunk)
                                now = time.monotonic()
                                if on_progress and now - last_cb > 0.5:
                                    last_cb = now
                                    on_progress(done, remote.size)
                except SharkyClipsError:
                    raise
                except Exception as exc:  # noqa: BLE001 - broken connection: resume
                    last_err = exc
                    time.sleep(min(20, 2 ** attempt))
                    continue
            if part.stat().st_size != remote.size:
                last_err = SharkyClipsError("incomplete")
                continue
            if on_progress:
                on_progress(remote.size, remote.size)
            if _hash_file(part, cancel) != remote.sha256:
                part.unlink(missing_ok=True)
                raise SharkyClipsError(f"The downloaded {label} is damaged (hash mismatch).",
                                       "Try again: it downloads fresh.")
            os.replace(part, dest)
            return dest
        raise SharkyClipsError(f"Could not download the {label} ({last_err}).",
                               "Check the internet connection and try again: it continues where it stopped.")


def partial_bytes(dest: Path) -> int:
    part = dest.with_name(dest.name + ".part")
    if dest.is_file():
        return dest.stat().st_size
    return part.stat().st_size if part.is_file() else 0
