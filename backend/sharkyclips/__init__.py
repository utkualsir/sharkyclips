"""SharkyClips - local, free, open-source stream & video highlight clipper."""

from pathlib import Path


def _read_version() -> str:
    # One source of truth: the VERSION file at the repo root (UI, installers and CLI all read it).
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


__version__ = _read_version()
