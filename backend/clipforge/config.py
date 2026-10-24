"""User settings stored as JSON in the user's home directory (~/.clipforge/config.json).

Set CLIPFORGE_HOME to use a different settings folder.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from . import languages

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = REPO_ROOT / "workspace"

DEFAULTS: dict[str, Any] = {
    "config_version": 1,
    "workspace_dir": None,  # None -> <repo>/workspace
    "ui_language": languages.DEFAULT_UI_LANGUAGE,
    "output_language": languages.DEFAULT_OUTPUT_LANGUAGE,
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
    # Run the AI analysis (titles, viral score, ...) by itself after highlights are found.
    "auto_analyze": True,
    # Names and words AI titles must spell exactly like this (game maps, operators, nicknames,
    # your own words). A list, or per output language: {"all": [...], "tr": [...]}.
    "glossary": [],
    "ollama_url": "http://127.0.0.1:11434",
    # Chat reacts a few seconds after the moment; the chat curve is shifted back by this much.
    "chat_delay": 5,
    # Set by `doctor` when the GPU smoke test fails even after upgrading libraries.
    "force_cpu": False,
    "force_cpu_reason": None,
    # Fingerprint of the last GPU setup that passed the smoke test.
    "gpu_verified": None,
}


def config_dir() -> Path:
    override = os.environ.get("CLIPFORGE_HOME")
    return Path(override).expanduser() if override else Path.home() / ".clipforge"


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


def save(cfg: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def get(key: str) -> Any:
    return load().get(key, DEFAULTS.get(key))


def update(**values: Any) -> dict[str, Any]:
    cfg = load()
    cfg.update(values)
    save(cfg)
    return cfg


def workspace_dir() -> Path:
    custom = get("workspace_dir")
    path = Path(custom).expanduser() if custom else DEFAULT_WORKSPACE
    path.mkdir(parents=True, exist_ok=True)
    return path
