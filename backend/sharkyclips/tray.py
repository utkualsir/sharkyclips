"""Notification-area (tray) icon for SharkyClips started without a console window.

Menu: Open SharkyClips (also a left click), the performance mode, Quit SharkyClips.
Needs `pystray` (Windows; optional elsewhere). Everything else talks to the running server
over its HTTP API, so the icon costs nothing while it sits there.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Callable

from . import config

TEXT = {
    "tr": {"open": "SharkyClips'i aç", "quit": "SharkyClips'i kapat", "mode": "Performans",
           "silent": "Sessiz", "balanced": "Dengeli", "turbo": "Turbo", "tip": "SharkyClips çalışıyor"},
    "en": {"open": "Open SharkyClips", "quit": "Quit SharkyClips", "mode": "Performance",
           "silent": "Silent", "balanced": "Balanced", "turbo": "Turbo", "tip": "SharkyClips is running"},
}


def available() -> bool:
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:  # noqa: BLE001 - missing, or no desktop session
        return False
    return True


def _t(key: str) -> str:
    lang = str(config.get("ui_language") or "en")
    return TEXT.get(lang, TEXT["en"])[key]


def _icon_image():
    from PIL import Image

    path = Path(__file__).resolve().parents[2] / "assets" / "icon" / "sharkyclips.png"
    try:
        return Image.open(path).convert("RGBA").resize((64, 64))
    except OSError:
        return Image.new("RGBA", (64, 64), (230, 80, 40, 255))


class _Mode:
    """Current performance mode, read from the server at most every 3 s (menu redraws)."""

    def __init__(self, url: str):
        self.url = url
        self.value = str(config.get("performance_mode") or "silent")
        self.at = 0.0

    def get(self) -> str:
        if time.monotonic() - self.at > 3:
            self.at = time.monotonic()
            try:
                with urllib.request.urlopen(f"{self.url}/api/governor", timeout=0.5) as r:
                    self.value = json.load(r).get("mode") or self.value
            except Exception:  # noqa: BLE001 - server still starting
                pass
        return self.value

    def set(self, mode: str) -> None:
        self.value, self.at = mode, time.monotonic()
        req = urllib.request.Request(f"{self.url}/api/governor", data=json.dumps({"mode": mode}).encode(),
                                     headers={"Content-Type": "application/json"}, method="PUT")
        try:
            urllib.request.urlopen(req, timeout=3).close()
        except Exception:  # noqa: BLE001
            config.update(performance_mode=mode)  # the server reads it on its next tick


def run(url: str, on_quit: Callable[[], None], stopped: threading.Event) -> None:
    """Show the icon until Quit is chosen or `stopped` is set (server gone). Blocks; call it
    from the main thread (required on macOS)."""
    import pystray

    mode = _Mode(url)

    def open_ui(_icon=None, _item=None) -> None:
        webbrowser.open(url)

    def quit_app(icon, _item) -> None:
        icon.visible = False
        on_quit()
        icon.stop()

    def mode_item(name: str):
        return pystray.MenuItem(_t(name), lambda _i, _it: mode.set(name),
                                checked=lambda _it: mode.get() == name, radio=True)

    menu = pystray.Menu(
        pystray.MenuItem(_t("open"), open_ui, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("mode"), pystray.Menu(*(mode_item(m) for m in ("silent", "balanced", "turbo")))),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_t("quit"), quit_app),
    )
    icon = pystray.Icon("SharkyClips", _icon_image(), f"{_t('tip')}: {url}", menu)

    def watch() -> None:  # the server ended on its own (crash, update failure): remove the icon
        stopped.wait()
        icon.stop()

    threading.Thread(target=watch, daemon=True).start()
    icon.run()
