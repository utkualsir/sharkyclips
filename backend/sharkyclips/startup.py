"""Keep Ollama from starting with Windows unless the user wants it (config `ollama_autostart`).

The Ollama installer, and every Ollama update, puts "Ollama.lnk" into the user's Startup
folder, so the Ollama server runs from boot. SharkyClips starts Ollama itself when it needs it
(and stops it with itself), so by default the shortcut is moved to
~/.sharkyclips/disabled-startup/. Turning the setting on moves it back.

Windows only; elsewhere these functions do nothing.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import config

LINK = "Ollama.lnk"


def startup_dir() -> Path | None:
    if os.name != "nt":
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def backup_dir() -> Path:
    return config.config_dir() / "disabled-startup"


def ollama_autostart_enabled() -> bool | None:
    """Whether Ollama starts with Windows right now (None: not Windows / Ollama not installed)."""
    d = startup_dir()
    if d is None:
        return None
    if (d / LINK).is_file():
        return True
    return False if (backup_dir() / LINK).is_file() else None


def apply_ollama_autostart(enabled: bool | None = None) -> bool | None:
    """Make the Startup folder match the setting. Returns the resulting state."""
    d = startup_dir()
    if d is None:
        return None
    if enabled is None:
        enabled = bool(config.get("ollama_autostart"))
    live, saved = d / LINK, backup_dir() / LINK
    try:
        if not enabled and live.is_file():
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(live), str(saved))  # (replaces an older backup)
        elif enabled and not live.is_file() and saved.is_file():
            shutil.move(str(saved), str(live))
    except OSError:
        pass
    return ollama_autostart_enabled()
