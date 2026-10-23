"""Shared console output helpers (rich)."""

from __future__ import annotations

import sys
import threading
from typing import Callable

from rich.console import Console
from rich.progress import (BarColumn, DownloadColumn, Progress, TaskProgressColumn, TextColumn,
                           TimeElapsedColumn, TimeRemainingColumn, TransferSpeedColumn)

for _stream in (sys.stdout, sys.stderr):
    try:  # Turkish / Russian / Arabic / Chinese text on older Windows consoles
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

console = Console(highlight=False)

# --------------------------------------------------------------- progress sink
# The web UI runs pipeline steps in a worker thread and wants their progress.
# A thread can register a sink; every progress bar created in that thread then
# reports (description, completed, total) to it instead of drawing in the terminal.
ProgressSink = Callable[[str, float, "float | None"], None]
_local = threading.local()


def set_progress_sink(sink: ProgressSink | None) -> None:
    _local.sink = sink


def progress_sink() -> ProgressSink | None:
    return getattr(_local, "sink", None)


class _ReportingProgress(Progress):
    """A rich Progress that also reports every change to the thread's sink."""

    def __init__(self, *columns, sink: ProgressSink, **kwargs):
        super().__init__(*columns, disable=True, **kwargs)
        self._sink = sink

    def _report(self, task_id) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            self._sink(task.description, float(task.completed), task.total)

    def add_task(self, description, *args, **kwargs):
        task_id = super().add_task(description, *args, **kwargs)
        self._report(task_id)
        return task_id

    def update(self, task_id, *args, **kwargs) -> None:
        super().update(task_id, *args, **kwargs)
        self._report(task_id)

    def advance(self, task_id, advance: float = 1) -> None:
        super().advance(task_id, advance)
        self._report(task_id)

    def reset(self, task_id, *args, **kwargs) -> None:
        super().reset(task_id, *args, **kwargs)
        self._report(task_id)


def _progress(*columns) -> Progress:
    sink = progress_sink()
    if sink is not None:
        return _ReportingProgress(*columns, sink=sink, console=console)
    return Progress(*columns, console=console)


def fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return "?"
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class _MediaTime(TextColumn):
    """Shows processed / total media time, e.g. 12:30 / 3:02:11."""

    def __init__(self):
        super().__init__("")

    def render(self, task):
        from rich.text import Text

        return Text(f"{fmt_time(task.completed)} / {fmt_time(task.total)}", style="cyan")


def time_progress() -> Progress:
    """Progress bar for media time (seconds) with ETA."""
    return _progress(
        TextColumn("[bold]{task.description}"), BarColumn(), TaskProgressColumn(),
        _MediaTime(), TextColumn("elapsed"), TimeElapsedColumn(),
        TextColumn("ETA"), TimeRemainingColumn(),
    )


def download_progress() -> Progress:
    return _progress(
        TextColumn("[bold]{task.description}"), BarColumn(), TaskProgressColumn(),
        DownloadColumn(), TransferSpeedColumn(), TextColumn("ETA"), TimeRemainingColumn(),
    )
