"""Highlight engine: pluggable signals -> hype curve -> clip candidates."""

from __future__ import annotations

from typing import Any

__all__ = ["run_highlights"]


def __getattr__(name: str) -> Any:
    # Lazy: the web server imports highlights.modes at start-up; the pipeline (SciPy & co.,
    # ~0.6 s) only loads when highlights are really computed.
    if name == "run_highlights":
        from .pipeline import run_highlights

        return run_highlights
    raise AttributeError(name)
