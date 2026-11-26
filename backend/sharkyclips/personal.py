"""1.2.69 Settings > Personalization, the server side: the user's theme is kept in the config
("ui_personal") so every browser on this computer (and the phone page) gets the same look, and
the splash page gets its colours ("ui_splash", see welcome.splash_theme_css).

The UI does all the colour work (frontend/src/personalize.ts); here the setting is only checked,
because it is written into pages and files: known keys only, colours only as "#rrggbb".
"""

from __future__ import annotations

import re

PRESETS = ("classic", "ocean", "sign", "contrast")
MODES = ("dark", "light", "system")
COLOR_KEYS = ("bg", "surface", "text", "muted", "border", "button", "link", "success", "warn", "danger",
              "bleep", "caption")
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def _hex(v) -> str | None:
    return v.lower() if isinstance(v, str) and _HEX.fullmatch(v) else None


def clean(value) -> dict | None:
    """A theme setting or theme file, checked and normalised. None: not a theme."""
    if not isinstance(value, dict):
        return None
    preset = value.get("preset")
    mode = value.get("mode")
    if preset not in PRESETS or mode not in MODES:
        return None
    colors: dict = {}
    raw = value.get("colors") if isinstance(value.get("colors"), dict) else {}
    for m in ("dark", "light"):
        row = raw.get(m) if isinstance(raw.get(m), dict) else {}
        colors[m] = {k: _hex(row.get(k)) for k in COLOR_KEYS if _hex(row.get(k))}
    at = value.get("at")
    return {"v": 1, "preset": preset, "mode": mode, "accent": _hex(value.get("accent")),
            "titlebar": bool(value.get("titlebar")), "autofix": value.get("autofix") is not False,
            "colors": colors, "at": float(at) if isinstance(at, (int, float)) and at > 0 else 0.0}
