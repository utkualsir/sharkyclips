"""Pluggable game profiles (1.2.53): one folder per game, `game/profiles/<id>/profile.json`.

A profile tells SharkyClips everything game-specific, as data (no code), so players can add a
game (docs/ADDING_A_GAME.md):

    id, name, status       "verified" (checked on real footage) | "beta" | "preview" (game not out
                           on PC / HUD unknown). Beta and preview show a "beta" badge in the UI.
    engine                 "banners" (generic: OCR the listed HUD regions when they change) or
                           "builtin" (League of Legends / Delta Force keep their own scanners)
    kind                   tactical_shooter | battle_royale | moba | hero_shooter | open_world |
                           sandbox | sports | extraction_shooter (tunes the generic context rules)
    aliases, hints         title / category names, and words streamers say (auto-detection)
    regions                {name: {"box": [x, y, w, h] on 1920x1080, "label"}}
    ocr                    {region: {event_code: [phrases, EN + TR, "-word" = must not be there]}}
    events                 {event_code: {"strength" 0..1, "label", "dedupe" s, "pre" s, "post" s}}
    audio_cues, vocabulary, terms, hashtags {"all": [...], "<lang>": [...]}, title_style {lang: hint}
    hud_areas              {name: {"box": [x, y, w, h] on 1920x1080, "label", "guess": bool}} (1.2.59):
                           the game's own HUD (kill feed, score, minimap ...). Animated graphics
                           never cover them. "guess": true = not checked on real footage yet.

Users can drop their own profile folder into `<settings>/game_profiles/<id>/profile.json`: it is
loaded too, and wins over a built-in profile with the same id.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .. import config

BUILTIN_DIR = Path(__file__).resolve().parent / "profiles"
STATUSES = ("verified", "beta", "preview")
KINDS = ("tactical_shooter", "battle_royale", "moba", "hero_shooter", "open_world", "sandbox", "sports",
         "extraction_shooter", "other")
REQUIRED = ("id", "name", "aliases")


def user_dir() -> Path:
    return config.config_dir() / "game_profiles"


def validate(p: dict) -> list[str]:
    """Problems with a profile (empty = fine). Used by the loader and by tests / contributors."""
    errs = [f"missing '{k}'" for k in REQUIRED if not p.get(k)]
    if p.get("status", "beta") not in STATUSES:
        errs.append(f"status must be one of {STATUSES}")
    if p.get("kind", "other") not in KINDS:
        errs.append(f"kind must be one of {KINDS}")
    regions = p.get("regions") or {}
    for name, r in regions.items():
        box = (r or {}).get("box")
        if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
            errs.append(f"region {name}: box must be [x, y, w, h]")
            continue
        x, y, w, h = box
        if w < 4 or h < 4 or x < 0 or y < 0 or x + w > 1920 or y + h > 1080:
            errs.append(f"region {name}: box outside the 1920x1080 frame")
    events = p.get("events") or {}
    for region, rules in (p.get("ocr") or {}).items():
        if region not in regions:
            errs.append(f"ocr region '{region}' is not in regions")
        for code, phrases in (rules or {}).items():
            if code not in events:
                errs.append(f"ocr event '{code}' has no entry in events")
            if not isinstance(phrases, list) or not any(not str(x).startswith("-") for x in phrases):
                errs.append(f"ocr event '{code}' needs at least one phrase")
    for code, ev in events.items():
        s = (ev or {}).get("strength")
        if not isinstance(s, (int, float)) or not 0 <= s <= 1:
            errs.append(f"event {code}: strength must be 0..1")
    if p.get("engine", "banners") == "banners" and p.get("ocr") and not regions:
        errs.append("a 'banners' profile with ocr rules needs regions")
    errs += validate_graphics(p)
    errs += validate_hud(p)
    return errs


HUD_AREAS = ("kill_feed", "kill_text", "score", "minimap", "health", "ammo", "abilities", "timer", "objective",
             "chat", "scoreboard")


def validate_hud(p: dict) -> list[str]:
    """1.2.59 `hud_areas`: {name: {"box": [x, y, w, h] on 1920x1080, "label", "guess": bool}}."""
    areas = p.get("hud_areas")
    if areas is None:
        return []
    if not isinstance(areas, dict):
        return ["hud_areas must be an object"]
    errs = []
    for name, a in areas.items():
        base = str(name).split(".")[0]  # "kill_feed.2": a second area of the same kind
        if base not in HUD_AREAS:
            errs.append(f"hud area {name}: name must be one of {HUD_AREAS}")
        box = (a or {}).get("box") if isinstance(a, dict) else None
        if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box)):
            errs.append(f"hud area {name}: box must be [x, y, w, h]")
            continue
        x, y, w, h = box
        if w < 8 or h < 8 or x < 0 or y < 0 or x + w > 1920 or y + h > 1080:
            errs.append(f"hud area {name}: box outside the 1920x1080 frame")
        elif w * h > 0.2 * 1920 * 1080:
            errs.append(f"hud area {name}: box too big (more than a fifth of the screen)")
        if "guess" in a and not isinstance(a["guess"], bool):
            errs.append(f"hud area {name}: guess must be true or false")
    return errs


def hud_boxes(game_id: str | None) -> list[tuple[float, float, float, float]]:
    """The game's HUD areas as fractions of the frame (x0, y0, x1, y1); [] for an unknown game."""
    p = get(game_id) if game_id else None
    out = []
    for a in ((p or {}).get("hud_areas") or {}).values():
        x, y, w, h = a["box"]
        out.append((x / 1920, y / 1080, (x + w) / 1920, (y + h) / 1080))
    return out


def validate_graphics(p: dict) -> list[str]:
    """1.2.58 `graphics`: {"kills": [event codes], "events": {code: {"type": banner|score, "text", "icon"}}}."""
    from ..edit.graphics import ICONS

    g = p.get("graphics")
    if g is None:
        return []
    if not isinstance(g, dict):
        return ["graphics must be an object"]
    errs = []
    if not isinstance(g.get("kills", []), list):
        errs.append("graphics.kills must be a list of event codes")
    for code, ev in (g.get("events") or {}).items():
        if not isinstance(ev, dict) or ev.get("type") not in ("banner", "score"):
            errs.append(f"graphics event {code}: type must be banner or score")
            continue
        if not str(ev.get("text") or "").strip() or len(str(ev["text"])) > 24:
            errs.append(f"graphics event {code}: text must be 1-24 characters")
        if ev.get("icon") and ev["icon"] not in ICONS:
            errs.append(f"graphics event {code}: icon must be one of {sorted(ICONS)}")
    return errs


def _read(folder: Path) -> dict | None:
    f = folder / "profile.json"
    try:
        p = json.loads(f.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    if not isinstance(p, dict) or validate(p):
        return None
    p.setdefault("status", "beta")
    p.setdefault("engine", "banners")
    p.setdefault("kind", "other")
    p["_source"] = "user" if folder.parent == user_dir() else "builtin"
    return p


@lru_cache(maxsize=4)
def _load(user_key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for base in (BUILTIN_DIR, user_dir()):
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if d.is_dir():
                p = _read(d)
                if p:
                    out[p["id"]] = p
    return out


def _user_key() -> str:
    d = user_dir()
    try:
        return "|".join(f"{f}:{f.stat().st_mtime_ns}" for f in sorted(d.glob("*/profile.json")))
    except OSError:
        return ""


def all_profiles() -> dict[str, dict]:
    return _load(_user_key())


def get(game_id: str | None) -> dict | None:
    return all_profiles().get(game_id or "")


def is_beta(game_id: str | None) -> bool:
    p = get(game_id)
    return bool(p and p.get("status") != "verified")


def banner_games() -> dict[str, dict]:
    return {k: p for k, p in all_profiles().items() if p.get("engine") == "banners" and p.get("ocr")}


def hashtags(game_id: str | None, lang: str | None) -> list[str]:
    """The game's hashtags for this content language: local ones first, then the global ones."""
    p = get(game_id)
    if not p:
        return []
    h = p.get("hashtags") or {}
    out: list[str] = []
    for t in list(h.get((lang or "")[:2]) or []) + list(h.get("all") or []):
        if t not in out:
            out.append(t)
    return out


def title_hint(game_id: str | None, lang: str | None) -> str:
    p = get(game_id)
    ts = (p or {}).get("title_style") or {}
    return str(ts.get((lang or "")[:2]) or ts.get("en") or "")


def summary(game_id: str) -> dict:
    p = get(game_id) or {}
    return {"id": game_id, "name": p.get("name", game_id), "status": p.get("status", "beta"),
            "beta": p.get("status", "beta") != "verified", "kind": p.get("kind", "other"),
            "engine": p.get("engine", "banners"), "source": p.get("_source", "builtin"),
            "notes": p.get("notes", ""), "events": {k: v.get("label", k) for k, v in (p.get("events") or {}).items()},
            # 1.2.53: the moments already read correctly on real videos (shown next to the beta badge)
            "checked": [(p.get("events") or {}).get(c, {}).get("label", c) for c in ((p.get("checked") or {}).get("events") or [])]}


def install(presets_mod, events_mod) -> None:
    """Plug the 'banners' profiles into the HUD presets / event strengths (idempotent)."""
    for gid, p in banner_games().items():
        presets_mod.GAMES[gid] = p["name"]
        presets_mod.REGIONS[gid] = {k: {"box": list(v["box"]), "label": v.get("label", k)}
                                    for k, v in p["regions"].items()}
        presets_mod.TEXT_RULES[gid] = {r: {c: list(ph) for c, ph in rules.items()} for r, rules in p["ocr"].items()}
        for code, ev in (p.get("events") or {}).items():
            events_mod.STRENGTH[code] = float(ev["strength"])
    for gid, p in all_profiles().items():
        presets_mod.GAMES.setdefault(gid, p["name"])
