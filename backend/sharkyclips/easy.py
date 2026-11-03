"""Easy mode (1.2.16): the smart defaults behind "drop a video -> best clips -> one click".

Easy mode never has its own render path. It picks the settings a beginner would want and drives
the same jobs as Pro mode: render (9:16), the publish plan (web/publishing.py) and uploads.

- per project: <project>/easy.json  {"easy": true, "mode_auto": bool, "shown": 6, "clips": {cid: {...}},
  "notified_for": <highlights stamp>}
- downloads:   Downloads/SharkyClips/<project>/  (MP4 + .txt ready to paste + cover PNG)
- notices:     short "your clips are ready" messages; the tray icon polls /api/notices
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from . import config
from .errors import SharkyClipsError, require_tool
from .procs import no_window
from .project import Project, read_json, write_json_atomic

SHOWN = 6  # clips on the result grid at first ("Show more" adds this many)
MODES_UI = ("easy", "pro")
WHEN = ("now", "auto")

# The smart defaults: auto layout (remembered facecam), the bold captions, bleeps on, no loop,
# a text hook (or the style the A/B bandit predicts), every speaker in the captions.
DEFAULT_OPTIONS = {
    "layout": "auto", "subtitles": "bold", "hook": True, "hook_flash": False, "subtitle_lang": "",
    "profanity": "bleep", "profanity_captions": True, "bleep_sound": "classic", "speaker_colors": True,
    "speaker_names": False, "cuts": "off", "zoom": "off", "music": False, "brand": False, "loop": False,
}


# ===================================================================== settings


# Fun effects in Easy mode (1.2.17). Unset = the default below for projects made from 1.2.17 on;
# older projects keep their look until the user flips a switch (no surprise re-renders).
FX_DEFAULTS = {"replay": True, "bubbles": True, "memes": "off"}
MEMES = ("off", "light", "strong")


def fx_settings() -> dict:
    rp, bb, mm = config.get("easy_replay"), config.get("easy_bubbles"), config.get("easy_memes")
    return {"replay": FX_DEFAULTS["replay"] if rp is None else bool(rp),
            "bubbles": FX_DEFAULTS["bubbles"] if bb is None else bool(bb),
            "memes": mm if mm in MEMES else FX_DEFAULTS["memes"]}


def fx_options(data: dict) -> dict:
    """The effects' render options for one Easy project (data = load(project))."""
    s = fx_settings()
    if not data.get("fx"):
        s = {"replay": s["replay"] if config.get("easy_replay") is not None else False,
             "bubbles": s["bubbles"] if config.get("easy_bubbles") is not None else False,
             "memes": s["memes"] if config.get("easy_memes") in MEMES else "off"}
    return {"replay": "auto" if s["replay"] else "off", "chat_bubbles": bool(s["bubbles"]), "memes": s["memes"]}


def ui_mode() -> str:
    m = config.get("ui_mode")
    return m if m in MODES_UI else "easy"  # Easy is the default for new and existing users


def settings() -> dict:
    when = config.get("easy_upload_when")
    return {"mode": ui_mode(), "tour_done": bool(config.get("easy_tour_done")),
            "upload_when": when if when in WHEN else "now",
            "open_folder": config.get("easy_open_folder") is not False,
            "downloads": str(downloads_root()), **fx_settings()}


def save_settings(body: dict) -> dict:
    changes: dict = {}
    if body.get("mode") in MODES_UI:
        changes["ui_mode"] = body["mode"]
    if "tour_done" in body:
        changes["easy_tour_done"] = bool(body["tour_done"])
    if body.get("upload_when") in WHEN:
        changes["easy_upload_when"] = body["upload_when"]
    if "open_folder" in body:
        changes["easy_open_folder"] = bool(body["open_folder"])
    if "replay" in body:
        changes["easy_replay"] = bool(body["replay"])
    if "bubbles" in body:
        changes["easy_bubbles"] = bool(body["bubbles"])
    if body.get("memes") in MEMES:
        changes["easy_memes"] = body["memes"]
    if changes:
        config.update(**changes)
    return settings()


# ===================================================================== per project


def _path(project: Project) -> Path:
    return project.dir / "easy.json"


_lock = threading.RLock()


def load(project: Project) -> dict:
    with _lock:
        p = _path(project)
        try:
            data = read_json(p) if p.is_file() else {}
        except (OSError, ValueError):
            data = {}
        return {"easy": bool(data.get("easy")), "mode_auto": bool(data.get("mode_auto")),
                "shown": max(SHOWN, int(data.get("shown") or SHOWN)), "clips": dict(data.get("clips") or {}),
                "notified_for": data.get("notified_for"), "created_at": data.get("created_at"),
                # 1.2.17: made with the fun effects' defaults
                "fx": bool(data.get("fx"))}


def save(project: Project, **changes) -> dict:
    with _lock:
        data = {**load(project), **changes}
        write_json_atomic(_path(project), data)
        return data


def clip_prefs(data: dict, cid: str) -> dict:
    c = data["clips"].get(cid) or {}
    return {"title": c.get("title") or None, "subtitles": c.get("subtitles") is not False,
            "music": bool(c.get("music"))}


def set_clip_prefs(project: Project, cid: str, **changes) -> dict:
    with _lock:
        data = load(project)
        cur = {**(data["clips"].get(cid) or {})}
        cur.update({k: v for k, v in changes.items() if v is not None or k == "title"})
        data["clips"][cid] = cur
        write_json_atomic(_path(project), data)
        return clip_prefs(data, cid)


# ===================================================================== content type


_KEYWORDS = {
    "study": ("ders", "lecture", "lesson", "tutorial", "study", "studying", "ders çalış", "matematik", "math",
              "physics", "fizik", "kimya", "chemistry", "biyoloji", "biology", "kpss", "yks", "tyt", "ayt", "lgs",
              "sınav", "exam", "pomodoro", "study with me", "konu anlatım", "eğitim", "course", "kurs", "unterricht",
              "vorlesung", "lernen", "előadás", "урок", "лекция", "درس", "课程", "学习", "podcast", "webinar"),
    "music": ("music", "müzik", "şarkı", "song", "cover", "konser", "concert", "live set", "dj set", "dj ",
              "piano", "piyano", "guitar", "gitar", "remix", "official audio", "karaoke", "acoustic", "akustik",
              "musik", "zene", "музык", "песн", "موسيقى", "音乐", "演唱"),
    "gaming": ("gameplay", "oyun", "maç", "ranked", "rank", "valorant", "league of legends", "lol ", "cs2",
               "counter-strike", "fortnite", "minecraft", "pubg", "apex", "warzone", "delta force", "gta",
               "dota", "overwatch", "rust", "kill", "clutch", "stream highlights", "twitch", "speedrun",
               "spiel", "játék", "игра", "لعبة", "游戏"),
}


def detect_mode(*texts: str | None) -> str:
    """gaming | study | music from the video's title / channel (a small changeable chip in the UI)."""
    text = " ".join(t for t in texts if t).lower()
    if not text.strip():
        return str(config.get("default_mode") or "gaming")
    try:
        from .titles.glossary import detect_game

        if detect_game(text):
            return "gaming"
    except Exception:  # noqa: BLE001 - the glossary is optional here
        pass
    hits = {m: sum(1 for w in words if w in f" {text} ") for m, words in _KEYWORDS.items()}
    best = max(hits, key=lambda m: hits[m])
    if hits[best] == 0:
        return str(config.get("default_mode") or "gaming")
    return best


# ===================================================================== hook = the predicted winner


def hook_style() -> str:
    """The hook style the A/B bandit expects to keep viewers longest (statement until it knows)."""
    try:
        from . import abtest

        st = abtest.stats(draws=4000)
        if st.get("verdict"):
            return str(st["verdict"]["style"])
        lead = (st.get("styles") or [{}])[0]
        if lead.get("n", 0) >= 3 and lead.get("p_best", 0) >= 0.6:
            return str(lead["style"])
    except Exception:  # noqa: BLE001 - no data yet / SciPy missing
        pass
    return "statement"


def render_options(prefs: dict, style: str, music_ok: bool, fx: dict | None = None) -> tuple[dict, str | None]:
    """(options, hook text override or None) for one clip. fx: fx_options() of the project."""
    opts = {**DEFAULT_OPTIONS, **(fx or {})}
    if not prefs.get("subtitles", True):
        opts["subtitles"] = "none"
    opts["music"] = bool(prefs.get("music")) and music_ok
    hook = None
    if style == "flash":
        opts["hook_flash"] = True
    elif style == "question":
        hook = "question"
    return opts, hook


# ===================================================================== downloads


def downloads_root() -> Path:
    """<Downloads>/SharkyClips (SHARKYCLIPS_DOWNLOADS overrides: tests, portable setups)."""
    env = os.environ.get("SHARKYCLIPS_DOWNLOADS")
    if env:
        return Path(env).expanduser()
    base = None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

            # FOLDERID_Downloads {374DE290-123F-4565-9164-39C4925E467B}
            fid = GUID(0x374DE290, 0x123F, 0x4565, (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                base = Path(out.value)
                ctypes.windll.ole32.CoTaskMemFree(out)
        except Exception:  # noqa: BLE001
            base = None
    if base is None:
        base = Path.home() / "Downloads"
    return base / "SharkyClips"


def safe_name(text: str, limit: int = 70) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f#]', "", str(text or "")).strip(" .")
    s = re.sub(r"\s+", " ", s)[:limit].strip(" .")
    return s or "clip"


def post_text(title: str, description: str, hashtags: list[str]) -> str:
    tags = " ".join(f"#{h.lstrip('#')}" for h in hashtags if h)
    parts = [title.strip(), "", (description or "").strip()]
    if tags:
        parts += ["", tags]
    return "\n".join(parts).strip() + "\n"


def to_png(src: Path, dest: Path) -> Path:
    if src.suffix.lower() == ".png":
        dest.write_bytes(src.read_bytes())
        return dest
    ffmpeg = require_tool("ffmpeg")
    r = subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(src), "-frames:v", "1", str(dest)],
                       capture_output=True, text=True, **no_window())
    if r.returncode != 0 or not dest.is_file():
        raise SharkyClipsError("Couldn't save the cover image.", (r.stderr or "")[-300:] or None)
    return dest


def open_folder(path: Path) -> bool:
    """Show the folder in Explorer / Finder (never in tests)."""
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("SHARKYCLIPS_NO_OPEN") == "1":
        return False
    try:
        if os.name == "nt":  # Explorer through the shell: no process of ours, no console
            import ctypes

            return ctypes.windll.shell32.ShellExecuteW(None, "open", str(path), None, None, 1) > 32
        elif os.uname().sysname == "Darwin":
            subprocess.Popen(["open", str(path)], **no_window())
        else:
            subprocess.Popen(["xdg-open", str(path)], **no_window())
        return True
    except Exception:  # noqa: BLE001
        return False


# ===================================================================== notices (tray)

NOTICE_TEXT = {
    "en": ("Your clips are ready", "{n} clips from “{title}” are ready to post."),
    "tr": ("Kliplerin hazır", "“{title}” videosundan {n} klip paylaşıma hazır."),
    "de": ("Deine Clips sind fertig", "{n} Clips aus „{title}“ sind bereit zum Posten."),
    "hu": ("Elkészültek a klipjeid", "{n} klip készült a(z) „{title}” videóból."),
    "ru": ("Клипы готовы", "{n} клипов из «{title}» готовы к публикации."),
    "ar": ("مقاطعك جاهزة", "{n} مقاطع من “{title}” جاهزة للنشر."),
    "zh": ("剪辑已就绪", "“{title}” 的 {n} 个剪辑可以发布了。"),
}

_BOOT = f"{int(time.time())}-{os.getpid()}"
_notices: deque[dict] = deque(maxlen=50)
_next = [1]


def push_notice(kind: str, title: str, body: str, url: str | None = None) -> dict:
    with _lock:
        n = {"id": _next[0], "kind": kind, "title": title, "body": body, "url": url, "at": time.time()}
        _next[0] += 1
        _notices.append(n)
        return n


def notices(after: int = 0) -> dict:
    with _lock:
        return {"boot": _BOOT, "items": [n for n in _notices if n["id"] > after],
                "last": _notices[-1]["id"] if _notices else 0}


def ready_notice(project_title: str, n: int, url: str | None) -> dict:
    lang = str(config.get("ui_language") or "en")
    title, body = NOTICE_TEXT.get(lang, NOTICE_TEXT["en"])
    return push_notice("clips_ready", title, body.format(n=n, title=project_title[:60]), url)
