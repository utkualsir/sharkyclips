"""`cli.py selftest`: render a tiny generated clip on the CPU (1.2.56, the installer's smoke test).

Makes an 8-second test video with FFmpeg (test pattern + a tone) in a temporary folder, never in
the workspace, renders it as a 9:16 clip with bold subtitles and checks the result with ffprobe.
No model, no network, no GPU: it proves the bundled Python, FFmpeg and the render pipeline work.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .errors import SharkyClipsError
from .procs import no_window

DURATION = 8.0
WORDS = ["this", "is", "the", "SharkyClips", "self", "test", "clip", "render", "works", "fine"]


def _make_project(root: Path):
    from .project import Project, write_json_atomic

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SharkyClipsError("FFmpeg wasn't found.", "Reinstall SharkyClips.")
    d = root / "selftest"
    d.mkdir(parents=True)
    subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"testsrc2=size=640x360:rate=30:duration={DURATION}", "-f", "lavfi", "-i",
                    f"sine=frequency=440:sample_rate=48000:duration={DURATION}", "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", "-shortest",
                    str(d / "source.mp4")], check=True, capture_output=True, timeout=120, **no_window())
    write_json_atomic(d / "meta.json", {"title": "selftest", "duration": DURATION, "width": 640, "height": 360,
                                        "fps": 30.0, "mode": "gaming", "audio_codec": "aac"})
    step = (DURATION - 1.0) / len(WORDS)
    words = [{"start": 0.5 + i * step, "end": 0.5 + (i + 0.8) * step, "word": " " + w, "probability": 0.95}
             for i, w in enumerate(WORDS)]
    write_json_atomic(d / "transcript.json", {"language": "en", "created_at": "selftest", "segments": [
        {"start": 0.5, "end": DURATION - 0.5, "text": " ".join(WORDS), "words": words}]})
    return Project("selftest", d)


def run(cpu: bool = True) -> dict:
    from . import clips, render
    from .clips import ClipOptions, OutputSpec

    if cpu:  # the CI runner has no GPU anyway; on a PC this proves the CPU path on its own
        render._candidates = lambda: ["libx264"]  # type: ignore[attr-defined]
        render.pick_encoder.cache_clear()
    t0 = time.perf_counter()
    tmp = Path(tempfile.mkdtemp(prefix="sharkyclips-selftest-"))
    try:
        proj = _make_project(tmp)
        cand = {"id": "c01", "rank": 1, "start": 0.5, "end": DURATION - 0.5, "duration": DURATION - 1.0,
                "peak": 4.0, "text": " ".join(WORDS), "reasons": []}
        opts = ClipOptions.from_dict({"subtitles": "bold", "hook": False, "profanity": "off", "replay": "off"})
        out = tmp / "clip.mp4"
        res = clips.render_clip(proj, cand, opts, None, out, spec=OutputSpec(width=540, height=960, fps=30))
        probe = subprocess.run([shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries",
                                "stream=codec_type,width,height:format=duration", "-of", "json", str(out)],
                               capture_output=True, text=True, timeout=60, **no_window())
        info = json.loads(probe.stdout or "{}")
        video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
        duration = float((info.get("format") or {}).get("duration") or 0)
        ok = video.get("width") == 540 and video.get("height") == 960 and audio and duration > DURATION - 3
        return {"ok": bool(ok), "encoder": res.encoder, "width": video.get("width"), "height": video.get("height"),
                "audio": audio, "duration": round(duration, 2), "bytes": res.size_bytes,
                "seconds": round(time.perf_counter() - t0, 1)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # our own temporary folder, never a project
