"""App-shell state for the web UI: first-run onboarding, "What's new", the dev banner, the splash.

  onboarding   config `onboarding_done`; shown once on a fresh install (never to people who
               already have projects).
  what's new   config `seen_version`; after an update the UI shows this version's CHANGELOG.md
               entry once, in the UI language (<!-- lang:xx --> blocks, English fallback).
  updates      1.2.58: the "Updates" page lists every CHANGELOG.md version (newest first): a short
               summary and the details grouped as New / Improved / Fixed, in the UI language
               (English fallback). config `updates_seen`: the menu item shows "New" until the page
               is opened after an update.
  dev flag     <config dir>/dev_in_progress.json {"started_at", "task"}: written by the developer
               (a development session) while an update is being built; the UI shows an "under construction"
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


# Group headings of the release notes, in every UI language (### New / ### Yeni / ...).
GROUPS = ("new", "improved", "fixed")
GROUP_HEADINGS = {
    "new": ("new", "yeni", "nuevo", "novo", "новое", "neu", "nouveau", "جديد", "新功能", "新機能", "új"),
    "improved": ("improved", "iyileştirmeler", "mejoras", "melhorias", "улучшения", "verbessert", "améliorations",
                 "تحسينات", "改进", "改善", "fejlesztések"),
    "fixed": ("fixed", "düzeltmeler", "correcciones", "correções", "исправления", "behoben", "corrections",
              "إصلاحات", "修复", "修正", "javítások"),
}


def _norm(heading: str) -> str:
    """casefold, and Turkish "İ" without the combining dot that casefold() leaves behind."""
    return heading.strip().strip("*: ").casefold().replace("\u0307", "")


_HEADING_KIND = {_norm(h): k for k, hs in GROUP_HEADINGS.items() for h in hs}


def _blocks(body: str) -> dict[str, str]:
    """{lang: markdown} of one CHANGELOG section (English = the text before the first marker)."""
    parts = re.split(r"<!--\s*lang:([a-z]{2})\s*-->", body)
    blocks = {"en": parts[0]}
    for code, chunk in zip(parts[1::2], parts[2::2]):
        blocks[code] = chunk
    for code, md in blocks.items():
        md = re.sub(r"</?details>|<summary>.*?</summary>", "", md, flags=re.S).strip()
        blocks[code] = re.sub(r"^\*\*[^*\n]{2,20}\*\*\s*\n", "", md)  # "**Türkçe**" label for GitHub readers
    return blocks


def parse_release(md: str) -> dict:
    """One language block -> {"summary", "groups": {new|improved|fixed|other: markdown}}.

    The summary is the first paragraph (plain text before any heading or list); the groups are
    the ### New / ### Improved / ### Fixed sections (headings in any UI language). Lists under
    another heading (older entries) land in "other"."""
    summary: list[str] = []
    groups: dict[str, list[str]] = {}
    cur: str | None = None
    seen_body = False
    for raw in md.replace("\r", "").split("\n"):
        line = raw.rstrip()
        h = re.match(r"^#{2,4}\s+(.*)$", line)
        if h:
            seen_body = True
            cur = _HEADING_KIND.get(_norm(h.group(1)), "other")
            continue
        if re.match(r"^\s*<!--.*-->\s*$", line):
            continue
        if not seen_body and not re.match(r"^\s*[-*]\s+", line):
            if line.strip():
                summary.append(line.strip())
            elif summary:
                seen_body = True
            continue
        seen_body = True
        if not line.strip() and cur is None:
            continue
        groups.setdefault(cur or "other", []).append(line)
    out = {k: "\n".join(v).strip() for k, v in groups.items() if "\n".join(v).strip()}
    return {"summary": " ".join(summary), "groups": out}


def release_history(lang: str = "en", path: Path = CHANGELOG) -> list[dict]:
    """Every CHANGELOG.md version, newest first: {"version", "date", "summary", "summary_lang",
    "groups": [{"kind", "markdown"}], "details_lang"}. Text in `lang` where the entry has it,
    else English."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for m in re.finditer(r"^## \[([^\]]+)\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S):
        version = m.group(1)
        head = m.group(0).splitlines()[0]
        date = (re.search(r"\d{4}-\d{2}-\d{2}", head) or [None])[0]
        blocks = _blocks(m.group(2))
        en = parse_release(blocks["en"])
        mine = parse_release(blocks[lang]) if lang != "en" and blocks.get(lang, "").strip() else None
        summary, s_lang = (mine["summary"], lang) if mine and mine["summary"] else (en["summary"], "en")
        groups, d_lang = (mine["groups"], lang) if mine and mine["groups"] else (en["groups"], "en")
        order = [*GROUPS, "other"]
        out.append({"version": version, "date": date, "summary": summary, "summary_lang": s_lang,
                    "groups": [{"kind": k, "markdown": groups[k]} for k in order if k in groups],
                    "details_lang": d_lang})
    return out


def updates_new(cfg: dict | None = None) -> bool:
    """The "New" badge on the Updates menu item: this version's notes weren't opened yet."""
    cfg = cfg if cfg is not None else config.load()
    if cfg.get("updates_seen") == __version__ or onboarding_needed(cfg):
        return False
    return changelog_entry(__version__) is not None


def mark_updates_seen(version: str = __version__) -> None:
    config.update(updates_seen=version)


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

    changes: dict = {"onboarding_done": True, "seen_version": __version__, "updates_seen": __version__}
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
    from . import updater

    rs = updater.restart_state()
    return {"version": __version__, "disk_version": rs["disk"], "restart_needed": rs["restart_needed"],
            "onboarding": onboarding_needed(cfg), "whats_new": whats_new(cfg), "updates_new": updates_new(cfg),
            "dev": dev if dev and not dev["stale"] else None, "dev_stale": dev if dev and dev["stale"] else None,
            "content_types": cfg.get("content_types") or [cfg.get("default_mode") or "gaming"],
            "youtube_signed_out": _yt_signed_out(), "instagram_manual": _ig_manual(),
            **_install_state()}


def _install_state() -> dict:
    """1.2.56: how this copy was installed, and whether the first-run downloads are still missing."""
    try:
        from . import appinstall, components

        kind = appinstall.kind()
        return {"install_kind": kind, "setup_needed": components.needs_setup_cached() if kind == "installer" else False}
    except Exception:  # noqa: BLE001 - never break the app shell
        return {"install_kind": None, "setup_needed": False}


def _ig_manual() -> dict | None:
    """1.2.50: Instagram posts waiting for you (Manual mode reminders, paused automatic posts)."""
    try:
        from .web import multipost

        d = multipost.manual_summary()
        return d if d["due"] or d["paused"] else None
    except Exception:  # noqa: BLE001 - never break the app shell
        return None


def _yt_signed_out() -> dict | None:
    """Google ended the YouTube sign-in: every screen offers a one-click reconnect."""
    try:
        from . import youtube

        return youtube.signed_out()
    except Exception:  # noqa: BLE001 - never break the app shell
        return None


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


def _font_data_uri(name: str) -> str:
    """1.2.65: a bundled UI font as a data: URI for the local splash file (a file:// page can't
    load a font file next to it, and fonts never come from the network). "" = system font."""
    import base64

    try:
        data = (config.REPO_ROOT / "frontend" / "dist" / "fonts" / name).read_bytes()
    except OSError:
        return "''"
    return "data:font/woff2;base64," + base64.b64encode(data).decode("ascii")


# 1.2.69: the splash page takes the user's theme colours (the UI sends them as config "ui_splash",
# both modes, after every theme change). Classic is the default until it has.
SPLASH_KEYS = ("l-bg", "l-text", "l-muted", "l-water", "l-fin-a", "l-fin-b", "l-cut", "mark-fin")
SPLASH_DEFAULT = {
    "dark": {"l-bg": "#0a1020", "l-text": "#ffffff", "l-muted": "#aeb7ca", "l-water": "#5b9bff",
             "l-fin-a": "#ffffff", "l-fin-b": "#9ec2ff", "l-cut": "#d9b56a", "mark-fin": "#ffffff"},
    "light": {"l-bg": "#f9fafc", "l-text": "#0e1a33", "l-muted": "#55617a", "l-water": "#a9c6f3",
              "l-fin-a": "#1f6fe5", "l-fin-b": "#0f3a94", "l-cut": "#1f6fe5", "mark-fin": "#1650c8"},
}
_CSS_COLOUR = re.compile(r"#[0-9a-fA-F]{6}|rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(,\s*(0|1|0?\.\d+)\s*)?\)")


def clean_splash(value) -> dict | None:
    """The "ui_splash" setting, checked: only the known keys, only plain colours (it ends up in CSS)."""
    if not isinstance(value, dict):
        return None
    out: dict = {}
    for mode in ("dark", "light"):
        m = value.get(mode)
        if not isinstance(m, dict):
            return None
        row = {}
        for k in SPLASH_KEYS:
            v = str(m.get(k) or "").strip()
            if not _CSS_COLOUR.fullmatch(v):
                return None
            row[k] = v
        out[mode] = row
    return out


def splash_theme_css(cfg: dict) -> str:
    colours = clean_splash(cfg.get("ui_splash")) or SPLASH_DEFAULT

    def block(sel: str, mode: str) -> str:
        return f"  {sel} {{ " + " ".join(f"--{k}: {v};" for k, v in colours[mode].items()) + " }"

    return "\n".join([
        block(":root", "dark"),
        block(':root[data-theme="light"]', "light"),
        "  @media (prefers-color-scheme: light) {",
        "  " + block(':root[data-theme="auto"]', "light"),
        "  }",
    ])


def result_page(message: str, ok: bool) -> str:
    """A small page shown in the browser after a sign-in comes back (TikTok, Instagram), in the
    colours of the user's theme (1.2.69: no colours of its own)."""
    import html as H

    cfg = config.load()
    theme = cfg.get("ui_theme") if cfg.get("ui_theme") in ("dark", "light") else "auto"
    css = "\n".join([
        splash_theme_css(cfg),
        "  body { font-family: system-ui, sans-serif; background: var(--l-bg); color: var(--l-text);"
        " display: grid; place-items: center; height: 100vh; margin: 0; }",
        "  .box { max-width: 460px; text-align: center; padding: 16px; } h1 { color: var(--l-cut); }",
        "  p.m { color: var(--l-muted); } a { color: var(--l-text); }",
    ])
    return (f"<!doctype html><html data-theme='{theme}'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'><title>SharkyClips</title>"
            f"<style>\n{css}\n</style></head>"
            f"<body><div class='box'><h1>{'&#10003;' if ok else '!'}</h1><p>{H.escape(message)}</p>"
            "<p class='m'><a href='/#/settings'>SharkyClips</a></p></div></body></html>")


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
            .replace("__FONT_ARCHIVO__", _font_data_uri("archivo-latin-standard-normal.woff2"))
            .replace("__DIR__", "rtl" if languages.is_rtl(lang) else "ltr")
            .replace("__THEME__", theme).replace("__MOTION__", motion)
            .replace("__THEME_CSS__", splash_theme_css(cfg)))
    out = config.config_dir() / "splash.html"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    except OSError:
        return None
    return out
