"""Friendly errors and per-OS install hints for missing dependencies."""

from __future__ import annotations

import importlib
from types import ModuleType
import platform
import shutil


class SharkyClipsError(Exception):
    """An error meant to be shown to the user as-is, with an optional fix hint."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint


def os_key() -> str:
    return {"Windows": "windows", "Darwin": "macos"}.get(platform.system(), "linux")


# Exact install commands for external tools, per OS.
INSTALL_COMMANDS: dict[str, dict[str, str]] = {
    "ffmpeg": {
        "windows": "winget install --id Gyan.FFmpeg -e   (then open a NEW terminal)",
        "macos": "brew install ffmpeg",
        "linux": "sudo apt install ffmpeg   (or your distro's package manager)",
    },
    "deno": {
        "windows": "winget install --id DenoLand.Deno -e   (then open a NEW terminal)",
        "macos": "brew install deno",
        "linux": "curl -fsSL https://deno.land/install.sh | sh",
    },
    "python": {
        "windows": "winget install --id Python.Python.3.12 -e",
        "macos": "brew install python@3.12",
        "linux": "sudo apt install python3.12 python3.12-venv",
    },
}


def install_hint(tool: str) -> str:
    return INSTALL_COMMANDS[tool][os_key()]


def pip_hint(*packages: str) -> str:
    quoted = " ".join(f'"{p}"' if any(c in p for c in "[]<>=") else p for p in packages)
    return f"python -m pip install -U {quoted}   (inside the activated venv)"


def require_tool(name: str, install_key: str | None = None) -> str:
    """Return the absolute path of an executable on PATH or raise a friendly error."""
    path = shutil.which(name)
    if path:
        return path
    key = install_key or name
    hint = install_hint(key) if key in INSTALL_COMMANDS else None
    raise SharkyClipsError(f"'{name}' was not found on your PATH.", hint)


def require_module(module: str, pip_name: str | None = None) -> ModuleType:
    """Import a Python module or raise a friendly error with the pip command."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise SharkyClipsError(
            f"Python package '{pip_name or module}' is not installed ({exc}).",
            pip_hint(pip_name or module),
        ) from exc
