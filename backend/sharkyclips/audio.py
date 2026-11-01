"""Audio extraction (16 kHz mono WAV) and low-memory WAV reading."""

from __future__ import annotations

import json
import subprocess
import wave
from fractions import Fraction
from pathlib import Path
from typing import Callable

import numpy as np

from .errors import SharkyClipsError, require_tool
from .procs import no_window
from .project import replace_retry

SAMPLE_RATE = 16000


def probe(path: Path) -> dict:
    """ffprobe a media file -> duration, resolution, fps, codecs."""
    ffprobe = require_tool("ffprobe", "ffmpeg")
    res = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        **no_window(),
    )
    if res.returncode != 0:
        raise SharkyClipsError(f"ffprobe could not read '{path.name}': {res.stderr.strip()[:300]}",
                               "Is the file a valid video/audio file?")
    data = json.loads(res.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps = None
    if video:
        for key in ("avg_frame_rate", "r_frame_rate"):
            rate = video.get(key)
            try:
                if rate and Fraction(rate) > 0:
                    fps = round(float(Fraction(rate)), 3)
                    break
            except (ValueError, ZeroDivisionError):
                continue
    duration = data.get("format", {}).get("duration")
    return {
        "duration": round(float(duration), 3) if duration else None,
        "width": video.get("width") if video else None,
        "height": video.get("height") if video else None,
        "fps": fps,
        "video_codec": video.get("codec_name") if video else None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "has_video": video is not None,
        "has_audio": audio is not None,
    }


def wav_is_valid(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as w:
            return (w.getframerate() == SAMPLE_RATE and w.getnchannels() == 1
                    and w.getsampwidth() == 2 and w.getnframes() > 0)
    except (OSError, wave.Error, EOFError):
        return False


def extract_audio(source: Path, dest: Path, duration: float | None = None,
                  on_progress: Callable[[float], None] | None = None) -> Path:
    """Extract 16 kHz mono 16-bit WAV. Skips work if a valid file already exists."""
    if dest.is_file() and wav_is_valid(dest):
        return dest
    ffmpeg = require_tool("ffmpeg")
    tmp = dest.with_name(dest.stem + ".partial.wav")
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
           "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
           "-c:a", "pcm_s16le", "-progress", "pipe:1", str(tmp)]
    from . import procs

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", **no_window())
    procs.track(proc)  # suspended while the governor pauses
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if on_progress and line.startswith("out_time_us=") and duration:
                try:
                    secs = min(int(line.split("=", 1)[1]) / 1e6, duration)
                except ValueError:
                    continue
                on_progress(secs)
    except BaseException:  # cancelled: stop ffmpeg and drop the partial file
        proc.kill()
        proc.wait()
        tmp.unlink(missing_ok=True)
        raise
    finally:
        procs.untrack(proc)
    stderr = proc.stderr.read() if proc.stderr else ""
    if proc.wait() != 0:
        tmp.unlink(missing_ok=True)
        raise SharkyClipsError(f"ffmpeg failed to extract audio: {stderr.strip()[-400:]}",
                               "Check that the video has an audio track and isn't corrupted.")
    replace_retry(tmp, dest)
    return dest


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def read_wav_segment(path: Path, start_s: float, end_s: float) -> np.ndarray:
    """Read part of a 16 kHz mono WAV as float32 without loading the whole file."""
    with wave.open(str(path), "rb") as w:
        sr, total = w.getframerate(), w.getnframes()
        a = max(0, int(start_s * sr))
        b = min(total, int(end_s * sr))
        if b <= a:
            return np.zeros(0, dtype=np.float32)
        w.setpos(a)
        raw = w.readframes(b - a)
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def quietest_point(path: Path, center_s: float, window_s: float = 20.0,
                   frame_s: float = 0.25) -> float:
    """Time of the quietest short frame within +/- window_s of center_s.

    Used to split long audio into chunks at a pause instead of mid-word.
    """
    start = max(0.0, center_s - window_s)
    samples = read_wav_segment(path, start, center_s + window_s)
    frame = int(frame_s * SAMPLE_RATE)
    n = len(samples) // frame
    if n < 2:
        return center_s
    energy = np.sqrt(np.mean(samples[: n * frame].reshape(n, frame) ** 2, axis=1))
    best = int(np.argmin(energy))
    return round(start + (best + 0.5) * frame_s, 3)
