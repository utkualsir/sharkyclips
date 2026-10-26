"""The user's own music library (e.g. their AI songs) for background music.

Drop songs into the music folder (Studio > Music, or ~/.sharkyclips/music). Each song is
analyzed once (length, tempo, its strongest part, a mood guess); the user tags its mood:
hype / chill / sad / funny. For a clip, `suggest` picks a song whose mood fits the moment
(the AI's judgement of the clip when available, else its signals: laughs -> funny, ...).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Callable

import numpy as np

from .. import config
from ..errors import SharkyClipsError, require_tool
from ..procs import no_window
from ..project import read_json, write_json_atomic

EXTS = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac")
MOODS = ("hype", "chill", "sad", "funny")
MAX_BYTES = 200 * 1024 * 1024
ANALYSIS_VERSION = 1
SR = 22050


def folder() -> Path:
    custom = config.get("music_dir")
    path = Path(custom).expanduser() if custom else config.config_dir() / "music"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path() -> Path:
    return config.config_dir() / "music_library.json"


def _load_index() -> dict:
    try:
        return (read_json(_index_path()).get("tracks") or {}) if _index_path().is_file() else {}
    except Exception:  # noqa: BLE001
        return {}


def _save_index(tracks: dict) -> None:
    write_json_atomic(_index_path(), {"version": 1, "tracks": tracks})


def _safe_name(name: str) -> str:
    name = Path(str(name)).name
    if not name or name.startswith(".") or Path(name).suffix.lower() not in EXTS:
        raise SharkyClipsError("Not a supported music file.", f"Use one of: {', '.join(EXTS)}")
    return name


def library() -> list[dict]:
    """Every song in the folder with its tags and analysis (new files: analyzed=False)."""
    idx = _load_index()
    out = []
    for path in sorted(folder().iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.suffix.lower() not in EXTS or path.name.startswith("."):
            continue
        st = path.stat()
        e = idx.get(path.name) or {}
        fresh = e.get("size_bytes") == st.st_size and e.get("version") == ANALYSIS_VERSION
        out.append({
            "name": path.name,
            "title": e.get("title") or path.stem,
            "artist": e.get("artist") or "",
            "moods": [m for m in e.get("moods") or [] if m in MOODS],
            "mood_guess": e.get("mood_guess") if fresh else None,
            "duration": e.get("duration") if fresh else None,
            "bpm": e.get("bpm") if fresh else None,
            "best_start": e.get("best_start") if fresh else None,
            "lufs": e.get("lufs") if fresh else None,
            "analyzed": bool(fresh and e.get("duration")),
            "size_bytes": st.st_size,
        })
    return out


def track(name: str) -> dict | None:
    return next((t for t in library() if t["name"] == name), None)


def path_of(name: str) -> Path | None:
    try:
        p = folder() / _safe_name(name)
    except SharkyClipsError:
        return None
    return p if p.is_file() else None


def update(name: str, changes: dict) -> dict:
    name = _safe_name(name)
    if path_of(name) is None:
        raise SharkyClipsError("This song isn't in the music folder any more.")
    idx = _load_index()
    e = idx.get(name) or {}
    if "moods" in changes:
        e["moods"] = [m for m in (changes.get("moods") or []) if m in MOODS]
    for k, n in (("title", 80), ("artist", 60)):
        if k in changes:
            e[k] = " ".join(str(changes.get(k) or "").split())[:n]
    e["edited"] = True
    idx[name] = e
    _save_index(idx)
    return track(name) or {}


def delete(name: str) -> bool:
    p = path_of(name)
    if p is None:
        return False
    p.unlink(missing_ok=True)
    idx = _load_index()
    idx.pop(p.name, None)
    _save_index(idx)
    return True


def upload_target(filename: str) -> Path:
    """Where an uploaded song goes (checked name)."""
    return folder() / _safe_name(filename)


def finish_upload(dest: Path) -> dict:
    """After an upload replaced `dest`: forget an old analysis of a file with that name."""
    idx = _load_index()
    if idx.pop(dest.name, None) is not None:
        _save_index(idx)
    return track(dest.name) or {}


# ------------------------------------------------------------------ analysis


def decode(path: Path, start: float = 0.0, duration: float | None = None, sr: int = SR,
           channels: int = 1) -> np.ndarray:
    """Decode audio to float32 (samples,) or (samples, channels). Governor-tracked ffmpeg."""
    from .. import procs

    ffmpeg = require_tool("ffmpeg")
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin"]
    if start > 0:
        cmd += ["-ss", f"{start:.3f}"]
    if duration is not None:
        cmd += ["-t", f"{max(0.01, duration):.3f}"]
    cmd += ["-i", str(path), "-vn", "-map", "0:a:0?", "-ac", str(channels), "-ar", str(sr), "-f", "f32le", "pipe:1"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **no_window())
    procs.track(proc)
    try:
        out, err = proc.communicate(timeout=600)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    finally:
        procs.untrack(proc)
    if proc.returncode != 0:
        raise SharkyClipsError(f"ffmpeg could not read {path.name}: {err.decode('utf-8', 'replace').strip()[-300:]}")
    y = np.frombuffer(out, dtype="<f4").copy()
    return y.reshape(-1, channels) if channels > 1 else y


def _tags(path: Path) -> dict:
    try:
        ffprobe = require_tool("ffprobe")
        res = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format_tags=title,artist",
                              "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30, **no_window())
        tags = (json.loads(res.stdout or "{}").get("format") or {}).get("tags") or {}
        return {k.lower(): str(v).strip() for k, v in tags.items()}
    except Exception:  # noqa: BLE001
        return {}


def best_start(energy_db: np.ndarray, hop_s: float, beats: np.ndarray | None = None) -> float:
    """Start of the song's strongest part: loud for the next ~8 s and louder than the
    seconds before (a chorus / drop), snapped to the beat just before it."""
    n = len(energy_db)
    dur = n * hop_s
    if dur < 20:
        return 0.0
    fw, bw = max(1, int(8 / hop_s)), max(1, int(4 / hop_s))
    c = np.concatenate([[0.0], np.cumsum(energy_db)])
    idx = np.arange(bw, max(bw + 1, n - fw))
    fwd = (c[idx + fw] - c[idx]) / fw
    back = (c[idx] - c[idx - bw]) / bw
    lim = idx * hop_s <= max(3.0, dur * 0.8 - 8)
    score = (fwd - fwd.mean()) / (fwd.std() + 1e-6) + 0.6 * (fwd - back) / ((fwd - back).std() + 1e-6)
    score[~lim] = -1e9
    t = float(idx[int(np.argmax(score))] * hop_s)
    if beats is not None and len(beats):
        before = beats[beats <= t + 0.15]
        if len(before):
            t = float(before[-1])
    return round(max(0.0, t), 2)


def _mood_guess(tempo: float | None, energy: float, minor: bool) -> str:
    if tempo and tempo >= 118 and energy > -18:
        return "hype"
    if minor and (tempo or 100) < 100:
        return "sad"
    if energy < -22 or (tempo or 120) < 95:
        return "chill"
    return "hype" if (tempo or 0) >= 110 else "chill"


_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def analyze(name: str) -> dict:
    """Length, tempo, strongest part, loudness and a mood guess for one song (cached)."""
    from .. import governor
    from .loudness import integrated_lufs

    path = path_of(name)
    if path is None:
        raise SharkyClipsError("This song isn't in the music folder any more.")
    y = decode(path)
    governor.checkpoint()
    if len(y) < SR:
        raise SharkyClipsError(f"{name} is too short (under a second).")
    hop = 512
    n = len(y) // hop
    rms = np.sqrt(np.mean(y[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    energy_db = 20 * np.log10(rms + 1e-9)
    tempo, beats, minor = None, None, False
    try:
        import librosa

        tmp, frames = librosa.beat.beat_track(y=y, sr=SR, hop_length=hop)
        tempo = float(np.atleast_1d(tmp)[0]) or None
        beats = librosa.frames_to_time(frames, sr=SR, hop_length=hop)
        governor.checkpoint()
        chroma = librosa.feature.chroma_stft(y=y[: SR * 120], sr=SR, hop_length=2048).mean(axis=1)
        maj = max(np.corrcoef(np.roll(_MAJOR, k), chroma)[0, 1] for k in range(12))
        mnr = max(np.corrcoef(np.roll(_MINOR, k), chroma)[0, 1] for k in range(12))
        minor = bool(mnr > maj)
    except Exception:  # noqa: BLE001 - librosa missing / odd file: energy-only analysis
        pass
    governor.checkpoint()
    stereo = decode(path, sr=48000, channels=2, duration=min(len(y) / SR, 240))
    lufs = integrated_lufs(stereo)
    tags = _tags(path)
    loud = float(np.percentile(energy_db, 90))
    entry = {
        "version": ANALYSIS_VERSION, "size_bytes": path.stat().st_size,
        "duration": round(len(y) / SR, 2), "bpm": round(tempo) if tempo else None,
        "best_start": best_start(energy_db, hop / SR, beats), "lufs": round(lufs, 1),
        "mood_guess": _mood_guess(tempo, loud, minor), "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    idx = _load_index()
    old = idx.get(name) or {}
    entry["title"] = old.get("title") or tags.get("title") or path.stem
    entry["artist"] = old.get("artist") or tags.get("artist") or ""
    entry["moods"] = old.get("moods") if old.get("edited") else [entry["mood_guess"]]
    entry["edited"] = bool(old.get("edited"))
    idx[name] = entry
    _save_index(idx)
    return track(name) or {}


def analyze_pending(on_progress: Callable[[int, int, str], None] | None = None) -> dict:
    todo = [t["name"] for t in library() if not t["analyzed"]]
    done, failed = 0, []
    for i, name in enumerate(todo):
        if on_progress:
            on_progress(i, len(todo), name)
        try:
            analyze(name)
            done += 1
        except SharkyClipsError as exc:
            failed.append({"name": name, "error": exc.message})
    return {"analyzed": done, "failed": failed}


# ------------------------------------------------------------------ suggestions


def mood_for(cand: dict, mode: str | None = None) -> tuple[str, str]:
    """(mood, why) for a clip: the AI's judgement when the clip was analyzed, else signals."""
    if mode == "study":
        return "chill", "mode"
    llm = cand.get("llm") or {}
    funny, exciting = llm.get("funny"), llm.get("exciting")
    mtype = str(llm.get("moment_type") or "").lower()
    if funny is not None or exciting is not None or mtype:
        if mtype in ("emotional", "sad", "wholesome"):
            return "sad", "ai"
        if (funny or 0) >= 6 and (funny or 0) >= (exciting or 0):
            return "funny", "ai"
        if mtype in ("funny", "fail", "troll") and (funny or 0) >= 4:
            return "funny", "ai"
        if (exciting or 0) >= 5 or mtype in ("skill", "clutch", "hype"):
            return "hype", "ai"
        return "chill", "ai"
    s = cand.get("signal_scores") or {}
    if s.get("laughter", 0) >= 0.4:
        return "funny", "signals"
    if s.get("game", 0) >= 0.3 or s.get("loudness", 0) >= 0.6:
        return "hype", "signals"
    return "chill", "signals"


def suggest(cand: dict, mode: str | None = None, tracks: list[dict] | None = None) -> dict | None:
    tracks = [t for t in (tracks if tracks is not None else library()) if t["analyzed"]]
    if not tracks:
        return None
    mood, why = mood_for(cand, mode)
    match = [t for t in tracks if mood in (t["moods"] or [t["mood_guess"]])]
    pool = match or tracks
    need = float(cand.get("duration") or 30)
    long_enough = [t for t in pool if (t["duration"] or 0) - (t["best_start"] or 0) >= need] or pool
    # Same clip -> same song; different clips of a project spread over the fitting songs.
    k = int(hashlib.sha1(str(cand.get("id")).encode()).hexdigest(), 16) % len(long_enough)
    t = long_enough[k]
    return {"name": t["name"], "title": t["title"], "artist": t["artist"], "mood": mood, "why": why,
            "matched": bool(match)}


def credit_line(t: dict) -> str:
    """'Music: <song> by <artist>' (template in config `music_credit`)."""
    from . import brand

    artist = t.get("artist") or ((brand.active_preset() or {}).get("channel")) or ""
    tpl = str(config.get("music_credit") or "Music: {title} by {artist}")
    line = tpl.replace("{title}", t.get("title") or "").replace("{artist}", artist)
    if not artist:
        line = line.replace(" by ", " ").strip()
    return " ".join(line.split())
