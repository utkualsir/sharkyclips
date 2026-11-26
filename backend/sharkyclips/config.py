"""User settings stored as JSON in the user's home directory (~/.sharkyclips/config.json).

Set SHARKYCLIPS_HOME to use a different settings folder (the old CLIPFORGE_HOME still works).
The old ~/.clipforge folder is moved here on the first start (migrate.py).
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from . import languages

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = REPO_ROOT / "workspace"

DEFAULTS: dict[str, Any] = {
    "config_version": 1,
    "workspace_dir": None,  # None -> <repo>/workspace (installed copy: Videos/SharkyClips)
    "ui_language": languages.DEFAULT_UI_LANGUAGE,
    "output_language": languages.DEFAULT_OUTPUT_LANGUAGE,
    # 1.2.53: the "content language" (= output_language, kept under both names) drives AI titles,
    # descriptions, hashtags, captions and YouTube metadata; UI language stays separate.
    "spanish_variant": "es-419",  # es-419 (Latin America) | es-ES (Spain)
    "default_mode": "gaming",
    "transcribe_language": "auto",
    "transcribe_model": "auto",
    "download_max_height": 1080,
    # Extra highlight trigger words per language, merged with the built-in lists.
    # {"tr": ["kral"]} or {"tr": {"reaction": ["kral"], "study": ["ezber"]}}
    "custom_triggers": {},
    # Preview/clip encoder: "auto" (first working hardware encoder, else CPU) or an ffmpeg
    # name: h264_nvenc, h264_videotoolbox, h264_qsv, h264_amf, libx264
    "video_encoder": "auto",
    # Local LLM (Ollama). "auto" picks by hardware: qwen3.5:9b with 8 GB+ VRAM, else the fallback.
    "llm_enabled": True,
    "llm_model": "auto",
    "llm_fallback_model": "qwen3.5:4b",
    "llm_num_ctx": 8192,
    # "Fast analysis": the small model (llm_fallback_model) and fewer title drafts.
    "fast_analysis": False,
    # Titles / descriptions: "auto" = the big model and more drafts while the PC is idle or in
    # Turbo mode, "best" = always, "normal" = never (quality over speed for titles).
    "metadata_quality": "auto",
    # Run the AI analysis (titles, viral score, ...) by itself after highlights are found.
    "auto_analyze": True,
    # Names and words AI titles must spell exactly like this (game maps, operators, nicknames,
    # your own words). A list, or per output language: {"all": [...], "tr": [...]}.
    "glossary": [],
    "channel_text": None,  # Brand kit > Channel text: channel hashtags, tag names, socials block
    "ollama_url": "http://127.0.0.1:11434",
    # Chat reacts a few seconds after the moment; the chat curve is shifted back by this much.
    "chat_delay": 5,
    # Resource governor (governor.py): "silent" (pauses for games / fullscreen / video, full
    # speed when you're away), "balanced" (throttled, never pauses) or "turbo" (full speed).
    "performance_mode": "silent",
    "perf_idle_minutes": 3,  # no keyboard/mouse input this long (or a locked screen) = full speed
    "perf_pause_fullscreen": True,
    "perf_pause_video": True,
    "perf_pause_busy": True,  # other apps keep the CPU / GPU busy
    "perf_idle_only": False,  # Silent: only work while you're away
    "perf_gpu_temp_limit": 85,  # degC: pause until 10 degC cooler
    "perf_vram_headroom_mb": 0,  # VRAM always left free for other apps; 0 = auto (2 GB on 8 GB)
    "perf_games": None,  # process names that pause Silent mode; None = built-in list
    # Windows: let Ollama start with Windows (its installer/updater adds a Startup shortcut;
    # SharkyClips moves it away unless this is on - SharkyClips starts Ollama itself when needed).
    "ollama_autostart": False,
    # UI motion: "full", "reduced" (simple fades) or "off". The OS "reduce motion" setting
    # always means at most "reduced". ui_theme: last theme picked in the UI (the launcher's
    # splash page uses it, it can't read the browser's storage).
    "ui_motion": "full",
    "ui_theme": None,
    # 1.2.69 Settings > Personalization: preset, mode, accent, own colours (personal.clean) and the
    # splash page's colours of that theme (welcome.clean_splash).
    "ui_personal": None,
    "ui_splash": None,
    # Editing tools (1.2.4). Word lists per language replace the built-in ones when set:
    # {"tr": ["amk", "siktir*"]} / {"tr": {"sure": ["ııı"], "maybe": ["şey"]}}
    "profanity_lists": {},
    "filler_lists": {},
    "cut_silence_ms": {},  # {"light": 800, "strong": 450}: silences longer than this are cut
    "music_dir": None,  # None -> ~/.sharkyclips/music
    "music_credit": None,  # None -> "Music: {title} by {artist}" (added to YouTube descriptions)
    "music_credit_enabled": True,
    "brand_presets": [],  # brand kit presets (edit/brand.py); the active one is brand_active
    "brand_active": None,
    # YouTube Data API units per day of the user's own Google Cloud project (Google's default).
    "youtube_daily_quota": 10000,
    # 1.2.17 automation + live (watch.py, markers.py, livechat.py, phone.py, web/live.py)
    "auto_clip_enabled": False,  # watch the recording folder(s); a finished recording -> Easy clips
    "watch_folders": None,  # None -> the folder OBS records into (detected)
    "watch_render_top": 6,
    "watch_publish": "off",  # off | plan | now: what happens to the best clips of an auto project
    "watch_publish_top": 3,
    "watch_min_minutes": 2,  # shorter recordings are skipped
    # 1.2.57 channel monitoring (channels.py, web/channels_api.py; the channels in <settings>/channels.json)
    "channel_pause_metered": True,  # no VOD downloads on a metered connection
    "channel_pause_games": True,  # a VOD download doesn't start while a game is running
    "channel_min_free_gb": 5,  # always left free on the projects drive
    "channel_min_minutes": 5,  # shorter streams / uploads are skipped
    "marker_hotkey": "ctrl+alt+c",
    "marker_hotkey_enabled": True,
    "live_clip_command": "!clip",
    "live_twitch_channel": "",  # read-only: "!clip" from you / your mods + chat for the bubbles
    "live_youtube_chat": False,
    "live_chat_record": True,
    "obs_websocket": "auto",  # auto (OBS's own websocket config) | off
    "phone_send": True,  # ready clips go to the paired Telegram bot
    "phone_send_top": 3,
    "phone_lan": False,
    # 1.2.42: automatic TikTok through TikTok Studio in SharkyClips' own browser profile
    "tiktok_auto_daily": 3,  # at most this many automatic TikTok posts a day (1.2.66: never above the daily limit)
    # 1.2.47: days a deleted project / clip stays in the trash (0 = deleted for good at once)
    "trash_keep_days": 30,
    "tiktok_browser": "auto",  # auto (Chrome, then Edge, then Playwright's Chromium) | chrome | msedge | chromium  # the phone approval page on the Wi-Fi (needs an access PIN)
    "replay_smooth": "auto",  # instant replay frames: auto | motion | blend
    # Easy mode clip length target per mode, set from the channel's own views (lengthfit.py):
    # {"gaming": {"min": 30, "max": 45}}. Empty = the built-in targets until enough published
    # clips have views; then the learned target wins.
    "length_targets": {},
    # 1.2.53 Settings > Performance (perf.py): where the AI runs and the Light preset for slow PCs
    "processing_device": "auto",  # auto | cpu | gpu (auto never uses a weak integrated GPU)
    "performance_preset": "auto",  # auto (Light on a weak PC) | light | normal
    "voices_on_light": False,  # voice separation also with the Light preset
    "light_checked": False,
    "light_auto_picked": False,
    # Set by `doctor` when the GPU smoke test fails even after upgrading libraries.
    "force_cpu": False,
    "force_cpu_reason": None,
    # Fingerprint of the last GPU setup that passed the smoke test.
    "gpu_verified": None,
}


def config_dir() -> Path:
    override = os.environ.get("SHARKYCLIPS_HOME") or os.environ.get("CLIPFORGE_HOME")
    return Path(override).expanduser() if override else Path.home() / ".sharkyclips"


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    path = config_path()
    if path.is_file():
        try:
            # utf-8-sig: Windows editors sometimes save JSON with a BOM.
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                cfg.update(data)
        except (OSError, json.JSONDecodeError):
            pass  # a broken config falls back to defaults; it is rewritten on next save
    return cfg


_lock = threading.RLock()


def save(cfg: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        tmp = path.with_name(f"config.json.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        # Windows: replacing fails while another thread / process has config.json open for
        # reading (the governor reads it every few seconds). That lasts milliseconds: retry.
        for attempt in range(40):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 39:
                    tmp.unlink(missing_ok=True)
                    raise
                time.sleep(0.025)


def get(key: str) -> Any:
    return load().get(key, DEFAULTS.get(key))


def update(**values: Any) -> dict[str, Any]:
    with _lock:
        cfg = load()
        cfg.update(values)
        save(cfg)
        return cfg


def workspace_dir() -> Path:
    custom = get("workspace_dir")
    if custom:
        path = Path(custom).expanduser()
    else:  # 1.2.56: an installed copy keeps its projects in Videos/SharkyClips (appinstall.py)
        from . import appinstall

        path = appinstall.default_workspace()
    path.mkdir(parents=True, exist_ok=True)
    return path
