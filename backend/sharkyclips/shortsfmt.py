"""1.2.68: every video is checked against the platform's short-video rules right before it goes
out (automatic upload and "Upload manually"), and fixed when it doesn't fit:

  shape     9:16 (1080x1920); anything else is scaled into 9:16 with bars (never stretched)
  length    YouTube Shorts <= 180 s, TikTok <= 600 s, Instagram Reels <= 900 s, >= 3 s
            (a clip a little too long is cut at the limit; much too long ones are refused, the
            publish check already leaves that platform out with the reason)
  codec     H.264 video (yuv420p, <= 60 fps) + AAC audio, MP4 with the index at the front
  size      under the platform's file limit

check() only reads (ffprobe); ensure() returns a file that fits: the same file when it already
does, else a fixed copy in <project>/cache/shortsfix (made again only when the clip changes).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import SharkyClipsError, require_tool
from .procs import no_window

RATIO = 9 / 16
RATIO_TOL = 0.02
MIN_S = 3.0
CUT_SLACK_S = 20.0  # up to this much over the limit is cut; more is refused
RULES = {
    "youtube": {"max_s": 180.0, "max_bytes": 256 * 1024**3, "name": "YouTube Shorts"},
    "tiktok": {"max_s": 600.0, "max_bytes": 4 * 1024**3, "name": "TikTok"},
    "reels": {"max_s": 900.0, "max_bytes": 1024**3, "name": "Instagram Reels"},
}
OK_VIDEO = ("h264",)
OK_AUDIO = ("aac",)


def probe(path: Path) -> dict:
    from .audio import probe as _probe

    info = _probe(path)
    info["size"] = path.stat().st_size
    return info


def check(path: Path, platform: str, info: dict | None = None) -> dict:
    """{"ok", "problems": [codes], "fixable", "info"}"""
    rule = RULES.get(platform) or RULES["youtube"]
    info = info or probe(path)
    w, h = int(info.get("width") or 0), int(info.get("height") or 0)
    dur = float(info.get("duration") or 0)
    probs = []
    if not info.get("has_video") or not w or not h:
        return {"ok": False, "problems": ["no_video"], "fixable": False, "info": info}
    if abs(w / h - RATIO) > RATIO_TOL:
        probs.append("not_vertical")
    if dur > rule["max_s"] + 0.05:
        probs.append("too_long")
    if dur and dur < MIN_S:
        probs.append("too_short")
    if (info.get("video_codec") or "") not in OK_VIDEO:
        probs.append("video_codec")
    if info.get("has_audio") and (info.get("audio_codec") or "") not in OK_AUDIO:
        probs.append("audio_codec")
    if (info.get("fps") or 0) > 60.5:
        probs.append("fps")
    if info.get("size", 0) > rule["max_bytes"]:
        probs.append("too_big")
    fixable = "no_video" not in probs and "too_short" not in probs and not (
        "too_long" in probs and dur > rule["max_s"] + CUT_SLACK_S)
    return {"ok": not probs, "problems": probs, "fixable": fixable, "info": info}


def _fixed_path(path: Path, platform: str, folder: Path) -> Path:
    st = path.stat()
    return folder / f"{path.stem[:60]}-{platform}-{st.st_size}-{int(st.st_mtime)}.mp4"


def ensure(path: Path, platform: str, folder: Path, on_progress=None) -> tuple[Path, list[str]]:
    """(file that fits the platform, what was fixed). Raises SharkyClipsError when it can't be fixed."""
    try:
        res = check(path, platform)
    except SharkyClipsError:
        return path, []  # ffprobe missing / unreadable: send it as it is (the platform says if not)
    if res["ok"] or "no_video" in res["problems"]:
        return path, []  # fits, or unreadable as video: sent as it is (the platform says if not)
    rule = RULES.get(platform) or RULES["youtube"]
    if not res["fixable"]:
        dur = float(res["info"].get("duration") or 0)
        if "too_short" in res["problems"]:
            raise SharkyClipsError(f"This clip is too short for {rule['name']} (at least {int(MIN_S)} s).",
                                   "Make the clip a little longer, then share it again.")
        if "too_long" in res["problems"]:
            raise SharkyClipsError(f"This clip is too long for {rule['name']} ({int(dur)} s, at most {int(rule['max_s'])} s).",
                                   "Trim the clip, or leave this platform out for it.")
        raise SharkyClipsError("This file has no video picture.", "Render the clip again.")
    out = _fixed_path(path, platform, folder)
    if out.is_file() and out.stat().st_size > 0:
        return out, res["problems"]
    folder.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".partial.mp4")
    ffmpeg = require_tool("ffmpeg", "ffmpeg")
    vf = ("scale=1080:1920:force_original_aspect_ratio=decrease,"
          "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps='min(60,source_fps)',format=yuv420p")
    if "fps" not in res["problems"]:
        vf = vf.replace(",fps='min(60,source_fps)'", "")
    else:
        vf = vf.replace("fps='min(60,source_fps)'", "fps=60")
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(path)]
    if "too_long" in res["problems"]:
        cmd += ["-t", f"{rule['max_s'] - 0.1:.2f}"]
    copy_video = set(res["problems"]) <= {"audio_codec", "too_long"}  # the picture is fine: keep it
    if copy_video:
        cmd += ["-c:v", "copy"]
    else:
        cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(tmp)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **no_window())
    if p.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise SharkyClipsError(f"Couldn't fix the video for {rule['name']}: {(p.stderr or '').strip()[:200]}",
                               "Render the clip again, then share it.")
    tmp.replace(out)
    if on_progress:
        on_progress(1.0)
    return out, res["problems"]
