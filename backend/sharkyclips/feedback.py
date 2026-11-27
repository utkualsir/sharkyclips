"""Send feedback / Report a bug (1.2.74).

The UI opens a pre-filled GitHub issue form in the browser (frontend/src/feedback.ts). The only
facts SharkyClips fills in are the app version and a short system label such as
"Windows 11 (AMD64, build 26100)": no user name, computer name, paths, hardware serials or logs.
Nothing is sent by the app itself; the person reads and submits the form on GitHub.
"""

from __future__ import annotations

import platform
import re
import sys
from pathlib import Path

REPO_URL = "https://github.com/utkualsir/sharkyclips"


def _linux_name(os_release: Path = Path("/etc/os-release")) -> str:
    try:
        text = os_release.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "Linux"
    m = re.search(r'^PRETTY_NAME="?([^"\n]+)"?', text, re.M)
    return m.group(1).strip()[:60] if m else "Linux"


def system_label() -> str:
    """A short, non-identifying description of the operating system."""
    machine = (platform.machine() or "").strip()[:16]
    if sys.platform == "win32":
        try:
            build = int(sys.getwindowsversion().build)  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            build = 0
        name = "Windows 11" if build >= 22000 else "Windows 10" if build >= 10240 else "Windows"
        bits = ", ".join(x for x in (machine, f"build {build}" if build else "") if x)
        return f"{name} ({bits})" if bits else name
    if sys.platform == "darwin":
        ver = platform.mac_ver()[0] or ""
        return f"macOS {ver} ({machine})".replace("  ", " ").replace(" ()", "")
    name = _linux_name()
    return f"{name} ({machine})" if machine else name
