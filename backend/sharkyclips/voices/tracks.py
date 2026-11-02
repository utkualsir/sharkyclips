"""Audio tracks of a video (OBS multitrack: mic, Discord, game, music...).

Labels per track: me | friends | mixed | game | music | ignore. "me" / "friends" / "mixed" are
voice tracks and get transcribed on their own. The labels are remembered per channel and
track layout (<settings>/audio_tracks.json), so a new recording with the same OBS setup is
labelled already.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from ..errors import require_tool

LABELS = ("me", "friends", "mixed", "game", "music", "ignore")
VOICE_LABELS = ("me", "friends", "mixed")

_HINTS = (  # track title words -> label (OBS names, English + Turkish + a few more)
    ("me", ("mic", "mikrofon", "microphone", "mikro", "voice me", "my voice", "sesim", "yeti", "shure")),
    ("friends", ("discord", "teamspeak", "ts3", "party", "friends", "arkadaş", "arkadas", "voice chat",
                 "chat", "call", "zoom")),
    ("music", ("music", "müzik", "muzik", "spotify", "song")),
    ("game", ("game", "oyun", "desktop", "masaüstü", "system", "sistem", "spiel")),
)


def audio_streams(path: Path) -> list[dict]:
    """[{"pos": 0, "index": 1, "codec", "channels", "title"}] for every audio stream."""
    from ..procs import no_window

    ffprobe = require_tool("ffprobe")
    cmd = [ffprobe, "-v", "error", "-select_streams", "a",
           "-show_entries", "stream=index,codec_name,channels:stream_tags=title,handler_name,language",
           "-of", "json", str(path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=60, **no_window())
        data = json.loads(res.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    out = []
    for pos, s in enumerate(data.get("streams") or []):
        tags = s.get("tags") or {}
        title = str(tags.get("title") or "").strip()
        handler = str(tags.get("handler_name") or "").strip()
        if not title and handler and not re.search(r"handler|media file|soundhandler", handler, re.I):
            title = handler
        out.append({"pos": pos, "index": s.get("index"), "codec": s.get("codec_name"),
                    "channels": s.get("channels"), "title": title, "language": tags.get("language")})
    return out


def guess_labels(streams: list[dict]) -> list[str]:
    if len(streams) <= 1:
        return ["mixed"] * len(streams)
    labels = []
    for i, s in enumerate(streams):
        t = (s.get("title") or "").lower()
        label = next((lab for lab, keys in _HINTS if any(k in t for k in keys)), None)
        if label is None:  # OBS: track 1 is usually everything mixed
            label = "mixed" if i == 0 else "ignore"
        labels.append(label)
    return labels


def _memory_path() -> Path:
    from .. import config

    return config.config_dir() / "audio_tracks.json"


def layout_key(meta: dict, streams: list[dict]) -> str:
    src = meta.get("source") or {}
    channel = str(src.get("uploader") or ("local files" if src.get("type") == "file" else "unknown"))
    return channel + "|" + str(len(streams)) + "|" + "/".join((s.get("title") or "-") for s in streams)


def _load_memory() -> dict:
    try:
        from ..project import read_json

        data = read_json(_memory_path())
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def labels_for(meta: dict, streams: list[dict]) -> tuple[list[str], str]:
    """(labels, where they came from: project | remembered | guess)."""
    got = meta.get("audio_tracks")
    if isinstance(got, list) and len(got) == len(streams) and all(lab in LABELS for lab in got):
        return list(got), "project"
    mem = _load_memory().get(layout_key(meta, streams))
    if isinstance(mem, list) and len(mem) == len(streams) and all(lab in LABELS for lab in mem):
        return list(mem), "remembered"
    return guess_labels(streams), "guess"


def save_labels(project, labels: list[str]) -> list[str]:
    from ..project import write_json_atomic

    streams = audio_streams(project.source_path)
    labels = [lab if lab in LABELS else "ignore" for lab in labels][:len(streams)]
    labels += ["ignore"] * (len(streams) - len(labels))
    meta = project.load_meta()
    meta["audio_tracks"] = labels
    project.save_meta(meta)
    mem = _load_memory()
    mem[layout_key(meta, streams)] = labels
    write_json_atomic(_memory_path(), mem)
    return labels


def read_track(path: Path, pos: int, start: float, end: float, sr: int = 16000,
               channels: int = 1) -> np.ndarray:
    """Part of one audio stream as float32: (n,) mono or (channels, n)."""
    from ..procs import no_window

    cmd = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, start):.3f}",
           "-t", f"{max(0.05, end - start):.3f}", "-i", str(path), "-map", f"0:a:{pos}", "-vn",
           "-ac", str(channels), "-ar", str(sr), "-f", "f32le", "pipe:1"]
    res = subprocess.run(cmd, capture_output=True, timeout=600, **no_window())
    y = np.frombuffer(res.stdout, np.float32)
    if channels == 1:
        return y.copy()
    n = len(y) // channels
    return y[:n * channels].reshape(n, channels).T.copy()
