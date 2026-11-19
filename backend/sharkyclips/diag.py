"""Diagnostic report (1.2.56): what the launcher's error screen and Settings copy to the clipboard.

Plain text, safe to paste into a GitHub issue: no tokens, keys, passwords or e-mail addresses
(redact.py), the user's name in paths replaced by <user>, no project titles, no settings values
except a short list of harmless ones. `python cli.py diag` prints it.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from pathlib import Path

from . import __version__, appinstall, config

SAFE_SETTINGS = ("ui_language", "output_language", "performance_mode", "performance_preset",
                 "processing_device", "video_encoder", "transcribe_model", "llm_enabled", "llm_model",
                 "force_cpu", "onboarding_done", "installer_migrated", "setup_downloads_at")
LOG_LINES = 40
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _anon(text: str) -> str:
    from .redact import redact

    text = redact(text)
    home = str(Path.home())
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    for variant in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
        if variant:
            text = text.replace(variant, "~")
    if len(user) >= 3:
        text = re.sub(re.escape(user), "<user>", text, flags=re.I)
    return _EMAIL.sub("<e-mail>", text)


def log_path() -> Path:
    return config.config_dir() / "logs" / "sharkyclips.log"


def log_tail(path: Path | None = None, lines: int = LOG_LINES) -> list[str]:
    path = path or log_path()
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 64 * 1024))
            data = f.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return data.splitlines()[-lines:]


def report(with_hardware: bool = True) -> dict:
    out: dict = {"version": __version__, "install": appinstall.summary(),
                 "os": f"{platform.system()} {platform.release()} ({platform.version()}) {platform.machine()}",
                 "python": f"{sys.version.split()[0]} ({sys.executable})", "frozen": bool(getattr(sys, "frozen", False))}
    try:
        cfg = config.load()
        out["settings"] = {k: cfg.get(k) for k in SAFE_SETTINGS if k in cfg}
    except Exception as exc:  # noqa: BLE001
        out["settings"] = f"unreadable: {type(exc).__name__}"
    try:
        import shutil

        out["ffmpeg"] = shutil.which("ffmpeg")
        ws = config.workspace_dir()
        out["workspace"] = str(ws)
        out["disk_free_gb"] = round(shutil.disk_usage(ws).free / 1e9, 1)
    except Exception as exc:  # noqa: BLE001
        out["workspace"] = f"error: {type(exc).__name__}"
    if with_hardware:
        try:
            from . import perf

            m = perf.machine()
            out["hardware"] = {"ram_gb": round(m.ram_gb, 1), "threads": m.threads, "gpu": m.nvidia_name,
                               "vram_gb": m.nvidia_vram_gb, "other_gpus": m.igpu, "light": perf.light(m)}
        except Exception as exc:  # noqa: BLE001
            out["hardware"] = f"error: {type(exc).__name__}: {exc}"
        try:
            from . import components

            out["components"] = {i["id"]: ("present" if i["present"] else "missing")
                                 for i in components.plan()["items"]}
        except Exception as exc:  # noqa: BLE001
            out["components"] = f"error: {type(exc).__name__}"
    out["log"] = log_tail()
    return out


def report_text(with_hardware: bool = True) -> str:
    r = report(with_hardware)
    lines = [f"SharkyClips {r['version']} diagnostic report"]
    for key in ("install", "os", "python", "ffmpeg", "workspace", "disk_free_gb", "hardware", "components", "settings"):
        if key in r:
            lines.append(f"{key}: {r[key]}")
    lines.append(f"--- last {LOG_LINES} log lines ---")
    lines += r["log"] or ["(no log)"]
    return _anon("\n".join(lines))
