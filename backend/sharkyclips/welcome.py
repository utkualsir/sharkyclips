"""App-shell state for the web UI: first-run onboarding, "What's new", the dev banner, the splash.

  onboarding   config `onboarding_done`; shown once on a fresh install (never to people who
               already have projects).
  what's new   config `seen_version`; after an update the UI shows this version's CHANGELOG.md
               entry once, in the UI language (<!-- lang:xx --> blocks, English fallback).
  dev flag     <config dir>/dev_in_progress.json {"started_at", "task"}: written by the developer
               (Claude Code) while an update is being built; the UI shows an "under construction"
               banner. Older than 12 hours = stale: no banner, only a note in Settings.
  splash       the launcher opens splash.html (a local file) right away; it polls the starting
               server and hands over to the app, so the splash never adds waiting time.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import __version__, config

DEV_FLAG = "dev_in_progress.json"
STALE_HOURS = 12
CHANGELOG = config.REPO_ROOT / "CHANGELOG.md"
SPLASH_TEMPLATE = Path(__file__).resolve().parent / "web" / "splash.html"
CONTENT_TYPES = ("gaming", "study", "music")


# ------------------------------------------------------------------ dev flag


def dev_flag_path() -> Path:
    return config.config_dir() / DEV_FLAG


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def dev_state(now: datetime | None = None) -> dict | None:
    """{"task", "started_at", "hours", "stale"} while the flag file exists, else None."""
    path = dev_flag_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    started = _parse_time(data.get("started_at"))
    if started is None:  # unreadable: fall back to the file time
        started = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    now = now or datetime.now(timezone.utc)
    hours = max(0.0, (now - started).total_seconds() / 3600)
    return {"task": str(data.get("task") or "")[:300], "started_at": started.isoformat(timespec="seconds"),
            "hours": round(hours, 2), "stale": hours > STALE_HOURS}


def clear_dev_flag() -> bool:
    try:
        dev_flag_path().unlink()
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ changelog


def changelog_entry(version: str, lang: str = "en", path: Path = CHANGELOG) -> dict | None:
    """The CHANGELOG.md section of `version` in `lang` (English when there is no such block)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    if not m:
        return None
    head = m.group(0).splitlines()[0]
    date = (re.search(r"\d{4}-\d{2}-\d{2}", head) or [None])[0]
    body = m.group(1)
    blocks: dict[str, str] = {}
    parts = re.split(r"<!--\s*lang:([a-z]{2})\s*-->", body)
    blocks["en"] = parts[0]
    for code, chunk in zip(parts[1::2], parts[2::2]):
        blocks[code] = chunk
    chosen = lang if blocks.get(lang, "").strip() else "en"
    md = blocks[chosen]
    # <details>/<summary> wrappers only exist for GitHub's view of the file
    md = re.sub(r"</?details>|<summary>.*?</summary>", "", md, flags=re.S).strip()
    md = re.sub(r"^\*\*[^*\n]{2,20}\*\*\s*\n", "", md)  # the "**Türkçe**" label for GitHub readers
    return {"version": version, "date": date, "lang": chosen, "markdown": md}


# ------------------------------------------------------------------ onboarding / what's new


def has_projects() -> bool:
    try:
        ws = config.workspace_dir()
    except OSError:
        return False
    return any((p / "meta.json").is_file() for p in ws.iterdir() if p.is_dir() and not p.name.startswith("_"))


def onboarding_needed(cfg: dict | None = None) -> bool:
    cfg = cfg if cfg is not None else config.load()
    if cfg.get("onboarding_done"):
        return False
    if has_projects():  # someone who already uses the app: don't greet them like a new user
        config.update(onboarding_done=True)
        return False
    return True


def whats_new(cfg: dict | None = None) -> str | None:
    """The version whose "What's new" the UI should show once, or None."""
    cfg = cfg if cfg is not None else config.load()
    if cfg.get("seen_version") == __version__ or onboarding_needed(cfg):
        return None
    return __version__ if changelog_entry(__version__) else None


def mark_seen(version: str = __version__) -> None:
    config.update(seen_version=version)


def finish_onboarding(body: dict) -> dict:
    """Save the onboarding answers (all optional; Skip sends nothing)."""
    from . import governor, languages

    changes: dict = {"onboarding_done": True, "seen_version": __version__}
    if body.get("ui_language"):
        changes["ui_language"] = languages.require(str(body["ui_language"])).code
    types = [t for t in (body.get("content_types") or []) if t in CONTENT_TYPES]
    if types:
        changes["content_types"] = types
        changes["default_mode"] = types[0]
    mode = body.get("performance_mode")
    if mode in governor.MODES:
        changes["performance_mode"] = mode
    config.update(**changes)
    return changes


def app_state() -> dict:
    cfg = config.load()
    dev = dev_state()
    return {"version": __version__, "onboarding": onboarding_needed(cfg), "whats_new": whats_new(cfg),
            "dev": dev if dev and not dev["stale"] else None, "dev_stale": dev if dev and dev["stale"] else None,
            "content_types": cfg.get("content_types") or [cfg.get("default_mode") or "gaming"]}


# ------------------------------------------------------------------ quick hardware check


def hardware_check() -> dict:
    """What this PC can do, in one short look (onboarding step 3)."""
    from . import hardware, llm
    from .render import pick_encoder

    hw = hardware.detect_hardware()
    gpu = hw.best_nvidia
    try:
        plan = hardware.choose_plan(hw, str(config.get("transcribe_model") or "auto"),
                                    force_cpu=bool(config.get("force_cpu")))
        whisper = {"model": plan.model, "device": plan.device}
    except Exception:  # noqa: BLE001
        whisper = {"model": None, "device": "cpu"}
    try:
        enc, _tried = pick_encoder()
        encoder = {"name": enc.name, "label": enc.label, "hardware": enc.hardware}
    except Exception:  # noqa: BLE001
        encoder = None
    try:
        llm_ok = llm.ollama_exe() is not None or llm.server_version(0.3) is not None
    except Exception:  # noqa: BLE001
        llm_ok = False
    big = (gpu and gpu.vram_gb >= 7.5) or (hw.apple_silicon and hw.ram_total_gb >= 15)
    if whisper["device"] in ("cuda", "mlx") and encoder and encoder["hardware"]:
        verdict = "great"
    elif whisper["device"] in ("cuda", "mlx") or (encoder and encoder["hardware"]):
        verdict = "good"
    else:
        verdict = "cpu"
    return {"cpu": hw.cpu_name, "cores": hw.cpu_logical_cores, "ram_gb": round(hw.ram_total_gb),
            "gpu": gpu.name if gpu else (hw.other_gpus[0] if hw.other_gpus else None),
            "vram_gb": round(gpu.vram_gb, 1) if gpu else None, "apple_silicon": hw.apple_silicon,
            "whisper": whisper, "encoder": encoder, "llm": {"available": llm_ok,
                                                            "model": llm.DEFAULT_MODEL if big else llm.SMALL_MODEL},
            "verdict": verdict}


# ------------------------------------------------------------------ splash (launcher)


def write_splash(url: str, lang: str | None = None) -> Path | None:
    """A local splash page that waits for the server at `url`, then opens the app. Returns
    its path, or None (then the launcher opens the app the old way)."""
    from . import languages

    try:
        html = SPLASH_TEMPLATE.read_text(encoding="utf-8")
    except OSError:
        return None
    cfg = config.load()
    lang = lang or str(cfg.get("ui_language") or languages.DEFAULT_UI_LANGUAGE)
    theme = cfg.get("ui_theme") if cfg.get("ui_theme") in ("dark", "light") else "auto"
    motion = cfg.get("ui_motion") if cfg.get("ui_motion") in ("full", "reduced", "off") else "full"
    html = (html.replace("__APP_URL__", json.dumps(url)).replace("__LANG__", json.dumps(lang))
            .replace("__DIR__", "rtl" if languages.is_rtl(lang) else "ltr")
            .replace("__THEME__", theme).replace("__MOTION__", motion))
    out = config.config_dir() / "splash.html"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    except OSError:
        return None
    return out
