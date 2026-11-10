"""SharkyClips - local, free, open-source stream & video highlight clipper."""

from pathlib import Path


def _read_version() -> str:
    # One source of truth: the VERSION file at the repo root (UI, installers and CLI all read it).
    try:
        return (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


__version__ = _read_version()


def _prefer_full_ffmpeg() -> None:
    """macOS: Homebrew's plain `ffmpeg` has no libass / freetype (no subtitles, bleep renders or covers).
    `ffmpeg-full` has them but is keg-only (not on PATH): put it first so every ffmpeg call finds it."""
    import os
    import sys

    if sys.platform != "darwin":
        return
    for prefix in ("/opt/homebrew", "/usr/local"):
        bin_dir = os.path.join(prefix, "opt", "ffmpeg-full", "bin")
        if os.path.isfile(os.path.join(bin_dir, "ffmpeg")):
            path = os.environ.get("PATH", "")
            if bin_dir not in path.split(os.pathsep):
                os.environ["PATH"] = bin_dir + (os.pathsep + path if path else "")
            return


_prefer_full_ffmpeg()
