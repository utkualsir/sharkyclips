"""Shared console output helpers (rich)."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.progress import (BarColumn, DownloadColumn, Progress, TaskProgressColumn, TextColumn,
                           TimeElapsedColumn, TimeRemainingColumn, TransferSpeedColumn)

for _stream in (sys.stdout, sys.stderr):
    try:  # Turkish / Russian / Arabic / Chinese text on older Windows consoles
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

console = Console(highlight=False)


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
    return Progress(
        TextColumn("[bold]{task.description}"), BarColumn(), TaskProgressColumn(),
        _MediaTime(), TextColumn("elapsed"), TimeElapsedColumn(),
        TextColumn("ETA"), TimeRemainingColumn(), console=console,
    )


def download_progress() -> Progress:
    return Progress(
        TextColumn("[bold]{task.description}"), BarColumn(), TaskProgressColumn(),
        DownloadColumn(), TransferSpeedColumn(), TextColumn("ETA"), TimeRemainingColumn(),
        console=console,
    )
