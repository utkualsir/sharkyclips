"""Video rendering helpers: hardware encoder detection + quick preview cuts.

Encoder choice (first one that really works on this machine wins):
  NVIDIA NVENC -> Apple VideoToolbox -> Intel QSV -> AMD AMF -> libx264 (CPU)
"Really works" = a 0.5 s test encode succeeds; ffmpeg lists encoders it has no
hardware for, so listing alone proves nothing.

9:16 clips with subtitles are rendered by clips.py on top of this module.
"""

from __future__ import annotations

import functools
import os
import platform
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import config, hardware
from .errors import SharkyClipsError, require_tool
from .procs import no_window


@dataclass(frozen=True)
class Encoder:
    name: str  # ffmpeg encoder name
    label: str
    hardware: bool
    args: tuple[str, ...]  # quality settings


ENCODERS = {
    "h264_nvenc": Encoder("h264_nvenc", "NVIDIA NVENC", True,
                          # cq 30 measured: ~half the size of cq 23, SSIM still >= x264 crf 23
                          ("-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "30", "-b:v", "0")),
    "h264_videotoolbox": Encoder("h264_videotoolbox", "Apple VideoToolbox", True,
                                 ("-b:v", "6M", "-allow_sw", "0")),
    "h264_qsv": Encoder("h264_qsv", "Intel Quick Sync", True,
                        ("-preset", "faster", "-global_quality", "23")),
    "h264_amf": Encoder("h264_amf", "AMD AMF", True,
                        ("-quality", "speed", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23")),
    "libx264": Encoder("libx264", "CPU (x264)", False,
                       ("-preset", "veryfast", "-crf", "23")),
}


def _candidates() -> list[str]:
    hw = hardware.detect_hardware()
    gpus = " ".join(hw.other_gpus).lower()
    order = []
    if hw.nvidia_gpus:
        order.append("h264_nvenc")
    if platform.system() == "Darwin":
        order.append("h264_videotoolbox")
    if "intel" in gpus:
        order.append("h264_qsv")
    if "amd" in gpus or "radeon" in gpus:
        order.append("h264_amf")
    order.append("libx264")
    return order


def test_encoder(name: str) -> tuple[bool, str]:
    """Encode 0.5 s of a generated test picture with this encoder."""
    ffmpeg = require_tool("ffmpeg")
    enc = ENCODERS[name]
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi",
           "-i", "testsrc2=size=640x360:rate=30:duration=0.5",
           "-c:v", enc.name, *enc.args, "-pix_fmt", "yuv420p", "-f", "null", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60, **no_window())
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return res.returncode == 0, res.stderr.strip()[-300:]


@functools.lru_cache(maxsize=1)
def pick_encoder() -> tuple[Encoder, list[str]]:
    """Best working encoder, plus notes about hardware encoders that failed."""
    notes = []
    order = _candidates()
    wanted = str(config.get("video_encoder") or "auto")
    if wanted != "auto":
        if wanted in ENCODERS:
            order = [wanted] + [n for n in order if n != wanted]
        else:
            notes.append(f"Unknown video_encoder '{wanted}' in config (use auto or one of "
                         f"{', '.join(ENCODERS)})")
    for name in order:
        ok, err = test_encoder(name)
        if ok:
            return ENCODERS[name], notes
        notes.append(f"{ENCODERS[name].label} not usable: {err or 'unknown error'}")
    raise SharkyClipsError("No working H.264 encoder found in ffmpeg (" + "; ".join(notes) + ").",
                           "Install a full ffmpeg build (Windows: winget install --id Gyan.FFmpeg -e, "
                           "macOS: brew install ffmpeg).")


@dataclass
class RenderResult:
    path: Path
    seconds: float
    size_bytes: int
    encoder: str


def run_ffmpeg(cmd: list[str], duration: float,
               on_progress: Callable[[float], None] | None = None,
               cwd: Path | None = None) -> tuple[int, str]:
    """Run ffmpeg with -progress on stdout; report output seconds done.

    The process is registered with the governor: it's suspended while SharkyClips pauses
    (game, fullscreen, ...) and the CPU encoder uses only the thread budget."""
    from . import governor, procs

    if "libx264" in cmd and "-threads" not in cmd:
        cmd = [*cmd[:-1], "-threads", str(governor.cpu_threads()), cmd[-1]]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", **no_window(),
                            cwd=str(cwd) if cwd else None)
    procs.track(proc)
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if on_progress and line.startswith("out_time_us="):
                try:
                    secs = min(int(line.split("=", 1)[1]) / 1e6, duration)
                except ValueError:
                    continue
                on_progress(secs)
    except BaseException:  # cancelled (web UI) or Ctrl+C: don't leave ffmpeg running
        proc.kill()
        proc.wait()
        raise
    finally:
        procs.untrack(proc)
    err = proc.stderr.read() if proc.stderr else ""
    return proc.wait(), err


def export_preview(source: Path, start: float, end: float, dest: Path, max_height: int = 720,
                   on_progress: Callable[[float], None] | None = None) -> RenderResult:
    """Cut [start, end] into a quick horizontal H.264/AAC MP4 (max 720p)."""
    ffmpeg = require_tool("ffmpeg")
    duration = max(0.1, end - start)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".partial.mp4")
    enc, _ = pick_encoder()
    # Even dimensions (H.264 requirement), never upscale.
    vf = f"scale=-2:'min({max_height},ih)':flags=bicubic,format=yuv420p"

    def build(e: Encoder) -> list[str]:
        return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
                "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
                "-map", "0:v:0", "-map", "0:a:0?", "-vf", vf,
                "-c:v", e.name, *e.args, "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", "-progress", "pipe:1", str(tmp)]

    t0 = time.perf_counter()
    code, err = run_ffmpeg(build(enc), duration, on_progress)
    if code != 0 and enc.hardware:  # e.g. GPU busy / session limit: retry on the CPU
        enc = ENCODERS["libx264"]
        code, err = run_ffmpeg(build(enc), duration, on_progress)
    if code != 0:
        tmp.unlink(missing_ok=True)
        raise SharkyClipsError(f"ffmpeg could not render the preview: {err.strip()[-400:]}")
    os.replace(tmp, dest)
    return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, enc.label)


def preview_name(rank: int, score: int, start: float) -> str:
    """e.g. 01_s94_02-14-37.mp4 (rank, hype score, start time h-m-s)."""
    s = int(round(start))  # same rounding as the CLI table
    return f"{rank:02d}_s{score:02d}_{s // 3600:02d}-{s % 3600 // 60:02d}-{s % 60:02d}.mp4"
