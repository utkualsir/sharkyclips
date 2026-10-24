"""'When the queue is finished, shut down the PC' (Queue screen).

Armed by the user; when the last job finishes and nothing else is queued or running, a
60 s countdown starts (shown in every open browser tab, with a Cancel button). If a new
job starts during the countdown, the countdown stops and waits for the queue again.

Set CLIPFORGE_DRY_SHUTDOWN=1 to test it: it then only logs instead of shutting down.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from typing import Callable

from ..ui import console

COUNTDOWN_S = 60


def shutdown_command() -> list[str] | None:
    system = platform.system()
    if system == "Windows":
        return ["shutdown", "/s", "/t", "0"]
    if system == "Darwin":
        return ["osascript", "-e", 'tell application "System Events" to shut down']
    if shutil.which("systemctl"):
        return ["systemctl", "poweroff"]
    return ["shutdown", "-h", "now"]


def supported() -> bool:
    return platform.system() in ("Windows", "Darwin")


class ShutdownTimer:
    def __init__(self, busy: Callable[[], bool], changed: Callable[[], None]):
        self._busy = busy
        self._changed = changed
        self._lock = threading.Lock()
        self.enabled = False
        self.deadline: float | None = None
        self.fired_at: float | None = None
        self.last_error: str | None = None
        self.dry_run = os.environ.get("CLIPFORGE_DRY_SHUTDOWN") == "1"
        threading.Thread(target=self._loop, name="clipforge-shutdown", daemon=True).start()

    def state(self) -> dict:
        left = None if self.deadline is None else max(0.0, self.deadline - time.time())
        return {"enabled": self.enabled, "supported": supported(), "countdown": None if left is None else round(left, 1),
                "deadline": self.deadline, "seconds": COUNTDOWN_S, "dry_run": self.dry_run,
                "fired_at": self.fired_at, "error": self.last_error}

    def set_enabled(self, value: bool) -> dict:
        with self._lock:
            self.enabled = bool(value)
            self.last_error = None
            if not self.enabled:
                self.deadline = None
        self._changed()
        return self.state()

    def cancel(self) -> dict:
        """Cancel the countdown and switch the option off."""
        return self.set_enabled(False)

    def job_finished(self) -> None:
        """Called after every job: start the countdown when the queue just ran empty."""
        with self._lock:
            if self.enabled and self.deadline is None and not self._busy():
                self.deadline = time.time() + COUNTDOWN_S
                console.print(f"[yellow]Queue finished: shutting down in {COUNTDOWN_S} s (cancel in the web UI).[/]")
        self._changed()

    def _loop(self) -> None:
        while True:
            time.sleep(0.5)
            fire = False
            with self._lock:
                if self.deadline is None:
                    continue
                if not self.enabled or self._busy():
                    self.deadline = None  # new work arrived: wait for the queue to empty again
                    self._changed()
                    continue
                if time.time() >= self.deadline:
                    self.deadline, self.enabled, fire = None, False, True
            if fire:
                self.fired_at = time.time()
                self._changed()
                self._shutdown()

    def _shutdown(self) -> None:
        cmd = shutdown_command()
        if self.dry_run or cmd is None:
            console.print(f"[yellow]Dry run: would shut down now with: {' '.join(cmd or ['?'])}[/]")
            return
        console.print("[yellow]Shutting down the computer...[/]")
        try:
            subprocess.run(cmd, check=True, timeout=30, capture_output=True)
        except Exception as exc:  # noqa: BLE001 - e.g. no permission on Linux
            self.last_error = str(exc)[:300]
            console.print(f"[red]Could not shut down: {exc}[/]")
            self._changed()
