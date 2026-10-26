"""Brand kit: channel name / handle, logo watermark, intro / outro cards and caption style,
saved as presets (config `brand_presets`, active one in `brand_active`). A render with the
"Brand kit" option on uses the active preset. Logos live in ~/.sharkyclips/brand/."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path

from .. import config
from ..errors import SharkyClipsError

POSITIONS = ("tl", "tr", "bl", "br")
LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp")
MAX_LOGO_BYTES = 8 * 1024 * 1024
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

DEFAULT = {
    "name": "My channel",
    "channel": "",
    "handle": "",
    "logo": None,
    "logo_pos": "tr",
    "logo_size": 16,  # % of the canvas width
    "logo_opacity": 0.85,
    "show_handle": True,
    "intro": {"enabled": False, "text": "", "seconds": 1.5},
    "outro": {"enabled": False, "text": "", "seconds": 2.5},
    "card_color": "#0E1A33",
    "caption_font": "",  # "" = the default font for the language
    "caption_color": "#FFFFFF",
    "caption_highlight": "#D9B56A",
    "caption_outline": "#000000",
    "rev": 0,
}


def folder() -> Path:
    return config.config_dir() / "brand"


def _clamp(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


def _color(v, default: str) -> str:
    v = str(v or "").strip()
    return v.upper() if HEX.match(v) else default


def _card(d, default: dict) -> dict:
    d = d if isinstance(d, dict) else {}
    return {"enabled": bool(d.get("enabled", default["enabled"])), "text": " ".join(str(d.get("text") or "").split())[:80],
            "seconds": _clamp(d.get("seconds", default["seconds"]), 0.5, 6.0, default["seconds"])}


def clean(p: dict, old: dict | None = None) -> dict:
    """A valid preset from UI input (unknown keys dropped)."""
    base = {**DEFAULT, **(old or {})}
    out = {"id": str(p.get("id") or base.get("id") or "b" + secrets.token_hex(3))[:24]}
    out["name"] = " ".join(str(p.get("name", base["name"]) or "").split())[:40] or "Brand"
    out["channel"] = " ".join(str(p.get("channel", base["channel"]) or "").split())[:60]
    out["handle"] = str(p.get("handle", base["handle"]) or "").strip().lstrip("@").replace(" ", "")[:40]
    out["logo"] = base.get("logo")  # only the logo upload changes it
    pos = p.get("logo_pos", base["logo_pos"])
    out["logo_pos"] = pos if pos in POSITIONS else "tr"
    out["logo_size"] = _clamp(p.get("logo_size", base["logo_size"]), 5, 45, 16)
    out["logo_opacity"] = _clamp(p.get("logo_opacity", base["logo_opacity"]), 0.1, 1.0, 0.85)
    out["show_handle"] = bool(p.get("show_handle", base["show_handle"]))
    out["intro"] = _card(p.get("intro", base["intro"]), DEFAULT["intro"])
    out["outro"] = _card(p.get("outro", base["outro"]), DEFAULT["outro"])
    out["card_color"] = _color(p.get("card_color", base["card_color"]), DEFAULT["card_color"])
    out["caption_font"] = " ".join(str(p.get("caption_font", base["caption_font"]) or "").split())[:60]
    for k in ("caption_color", "caption_highlight", "caption_outline"):
        out[k] = _color(p.get(k, base[k]), DEFAULT[k])
    out["rev"] = int(base.get("rev") or 0) + (1 if old is not None and _sig(out) != _sig(old) else 0)
    return out


def _sig(p: dict) -> str:
    return json.dumps({k: v for k, v in p.items() if k != "rev"}, sort_keys=True)


def load() -> dict:
    presets = [clean(p, p) for p in (config.get("brand_presets") or []) if isinstance(p, dict)]
    active = config.get("brand_active")
    if active not in {p["id"] for p in presets}:
        active = presets[0]["id"] if presets else None
    return {"presets": presets, "active": active}


def save(presets: list[dict], active: str | None) -> dict:
    old = {p["id"]: p for p in load()["presets"]}
    out = []
    for p in presets[:20]:
        if not isinstance(p, dict):
            continue
        prev = old.get(str(p.get("id") or ""))
        out.append(clean(p, prev))
    ids = {p["id"] for p in out}
    for pid, p in old.items():  # removed presets: delete their logo
        if pid not in ids and p.get("logo"):
            (folder() / p["logo"]).unlink(missing_ok=True)
    config.update(brand_presets=out, brand_active=active if active in ids else (out[0]["id"] if out else None))
    return load()


def get(pid: str | None) -> dict | None:
    data = load()
    pid = pid or data["active"]
    return next((p for p in data["presets"] if p["id"] == pid), None)


def active_preset() -> dict | None:
    return get(None)


def logo_path(preset: dict | None) -> Path | None:
    if not preset or not preset.get("logo"):
        return None
    path = folder() / preset["logo"]
    return path if path.is_file() else None


def store_logo(pid: str, data: bytes, filename: str) -> dict:
    data_all = load()
    preset = next((p for p in data_all["presets"] if p["id"] == pid), None)
    if preset is None:
        raise SharkyClipsError("This brand preset doesn't exist any more.")
    ext = Path(filename).suffix.lower()
    if ext not in LOGO_EXTS:
        raise SharkyClipsError("Use a PNG, JPG or WebP image for the logo.", "A PNG with a transparent background looks best.")
    if not data or len(data) > MAX_LOGO_BYTES:
        raise SharkyClipsError("The logo file is empty or larger than 8 MB.")
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SharkyClipsError("This image file can't be read.", "Save it as PNG and try again.")
    folder().mkdir(parents=True, exist_ok=True)
    name = f"{pid}_{hashlib.sha1(data).hexdigest()[:8]}{ext}"
    if preset.get("logo") and preset["logo"] != name:
        (folder() / preset["logo"]).unlink(missing_ok=True)
    (folder() / name).write_bytes(data)
    presets = [{**p, "logo": name, "rev": int(p.get("rev") or 0) + 1} if p["id"] == pid else p
               for p in data_all["presets"]]
    config.update(brand_presets=presets)
    return get(pid) or {}


def remove_logo(pid: str) -> dict:
    data_all = load()
    presets = []
    for p in data_all["presets"]:
        if p["id"] == pid and p.get("logo"):
            (folder() / p["logo"]).unlink(missing_ok=True)
            p = {**p, "logo": None, "rev": int(p.get("rev") or 0) + 1}
        presets.append(p)
    config.update(brand_presets=presets)
    return get(pid) or {}


def ass_color(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR."""
    h = hex_color.lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def fingerprint(preset: dict | None) -> str:
    return f"{preset['id']}:{preset.get('rev', 0)}" if preset else ""


def card_seconds(preset: dict | None) -> tuple[float, float]:
    """(intro, outro) seconds when the cards are on."""
    if not preset:
        return 0.0, 0.0
    i, o = preset.get("intro") or {}, preset.get("outro") or {}
    return (float(i.get("seconds") or 0) if i.get("enabled") else 0.0,
            float(o.get("seconds") or 0) if o.get("enabled") else 0.0)


def intro_text(preset: dict) -> str:
    return (preset.get("intro") or {}).get("text") or preset.get("channel") or preset.get("name") or ""


def outro_text(preset: dict) -> str:
    t = (preset.get("outro") or {}).get("text")
    if t:
        return t
    return f"@{preset['handle']}" if preset.get("handle") else (preset.get("channel") or "")
