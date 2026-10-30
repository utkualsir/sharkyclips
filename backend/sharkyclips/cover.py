"""Covers for YouTube (1.2.7): the thumbnail of a 16:9 video, or the first frame of a Short.

Kinds of cover:
  peak    the AI's cover idea on the clip's peak moment (its short cover text)
  action  the same idea on another strong moment of the clip (a second reason / the middle)
  face    the streamer's strongest facial expression in the facecam over the peak moment
  custom  the user's own image (cache/thumbnails/<clip>.jpg)

"Strongest expression" is measured on the facecam frames of the clip (OpenCV's bundled face and
smile models, no download): how far the face moves away from its own neutral look, an open
mouth, a smile and how loud the streamer is at that moment, ignoring blurry frames.

The text uses the app's look (white, gold accent, navy outline) or the active brand kit's
caption colours / font. YouTube takes no custom thumbnail for Shorts through its API, so a
Short can get the cover burned in as its first ~0.3 s instead (`burn_first_frame`).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Callable

import numpy as np

from . import languages
from .clips import GOLD, NAVY, WHITE, Facecam, _ass_escape, _font_for, _upper
from .errors import SharkyClipsError, require_tool
from .procs import no_window
from .project import Project, read_json, write_json_atomic

KINDS = ("peak", "action", "face", "custom", "none")
SIZES = {"wide": (1280, 720), "tall": (1080, 1920)}
FIRST_FRAME_S = 0.3
MAX_FRAMES = 40


def folder(project: Project) -> Path:
    return project.cache_dir / "covers"


def _sig(*parts) -> str:
    from .publishing import signature

    return signature(*parts)


# ------------------------------------------------------------------ strongest expression


def _clip_frames(src: Path, start: float, end: float, box: tuple[float, float, float, float] | None,
                 src_w: int, src_h: int) -> tuple[list[float], list[np.ndarray]]:
    ffmpeg = require_tool("ffmpeg")
    dur = max(0.5, end - start)
    fps = min(4.0, MAX_FRAMES / dur)
    bw = src_w * (box[2] if box else 1.0)
    bh = src_h * (box[3] if box else 1.0)
    w = 240
    h = max(2, int(round(w * bh / max(bw, 1) / 2)) * 2)
    vf = (f"crop=iw*{box[2]:.4f}:ih*{box[3]:.4f}:iw*{box[0]:.4f}:ih*{box[1]:.4f}," if box else "")
    vf += f"fps={fps:.4f},scale={w}:{h}:flags=area,format=bgr24"
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
           "-i", str(src), "-an", "-vf", vf, "-f", "rawvideo", "pipe:1"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=300, **no_window()).stdout
    except (OSError, subprocess.SubprocessError):
        return [], []
    size = w * h * 3
    n = len(out) // size
    frames = [np.frombuffer(out[i * size:(i + 1) * size], np.uint8).reshape(h, w, 3) for i in range(n)]
    times = [start + (i + 0.5) / fps for i in range(n)]
    return times, frames


def _loudness(project: Project, times: list[float], win: float = 0.5) -> np.ndarray:
    path = project.audio_path
    if not times or not path.is_file():
        return np.zeros(len(times))
    try:
        with wave.open(str(path), "rb") as w:
            sr = w.getframerate()
            a = max(0, int((min(times) - win) * sr))
            b = int((max(times) + win) * sr)
            w.setpos(min(a, w.getnframes()))
            raw = w.readframes(max(0, b - a))
            width = w.getsampwidth()
            ch = w.getnchannels()
    except (OSError, wave.Error, EOFError):
        return np.zeros(len(times))
    if width != 2 or not raw:
        return np.zeros(len(times))
    y = np.frombuffer(raw, "<i2").astype(np.float32) / 32768.0
    if ch > 1:
        y = y[: len(y) // ch * ch].reshape(-1, ch).mean(axis=1)
    out = []
    for t in times:
        i, j = int((t - win / 2) * sr) - a, int((t + win / 2) * sr) - a
        seg = y[max(0, i):max(0, j)]
        out.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    return np.array(out)


def _rank(v: np.ndarray) -> np.ndarray:
    """0..1 by rank (robust to outliers and units)."""
    if len(v) < 2 or float(np.ptp(v)) == 0.0:
        return np.zeros(len(v))
    order = v.argsort().argsort().astype(np.float64)
    return order / (len(v) - 1)


def score_faces(frames: list[np.ndarray], loud: np.ndarray) -> list[dict]:
    """Per frame: {face (bool), score 0..1, parts}. Kept separate from the video reading so it
    can be tested on synthetic pictures."""
    import cv2

    base = Path(cv2.data.haarcascades)
    face_m = cv2.CascadeClassifier(str(base / "haarcascade_frontalface_default.xml"))
    smile_m = cv2.CascadeClassifier(str(base / "haarcascade_smile.xml"))
    if face_m.empty():
        return [{"face": False, "score": 0.0, "parts": {}} for _ in frames]
    crops: list[np.ndarray | None] = []
    sharp, mouth, smile = [], [], []
    for img in frames:
        g = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        found = face_m.detectMultiScale(g, 1.1, 4, minSize=(max(20, g.shape[1] // 8),) * 2)
        if not len(found):
            crops.append(None)
            sharp.append(0.0)
            mouth.append(0.0)
            smile.append(0.0)
            continue
        x, y, w, h = max(found, key=lambda f: f[2] * f[3])
        face = g[y:y + h, x:x + w]
        crops.append(cv2.resize(face, (48, 48), interpolation=cv2.INTER_AREA).astype(np.float32))
        sharp.append(float(cv2.Laplacian(face, cv2.CV_64F).var()))
        low = face[int(h * 0.66):, int(w * 0.25):int(w * 0.75)]
        thr = float(face.mean()) - 0.8 * float(face.std())
        mouth.append(float((low < thr).mean()) if low.size else 0.0)
        lower = face[h // 2:, :]
        hit = len(smile_m.detectMultiScale(lower, 1.7, 18, minSize=(max(12, w // 5), max(8, h // 10)))) if not smile_m.empty() else 0
        smile.append(1.0 if hit else 0.0)
    have = [c for c in crops if c is not None]
    if not have:
        return [{"face": False, "score": 0.0, "parts": {}} for _ in frames]
    stack = np.stack(have)
    stack = (stack - stack.mean(axis=(1, 2), keepdims=True)) / (stack.std(axis=(1, 2), keepdims=True) + 1e-6)
    neutral = np.median(stack, axis=0)
    dev_have = np.abs(stack - neutral).mean(axis=(1, 2))
    idx = [i for i, c in enumerate(crops) if c is not None]
    dev = np.zeros(len(frames))
    dev[idx] = dev_have
    sub = np.array(idx)
    r_dev, r_mouth, r_loud = np.zeros(len(frames)), np.zeros(len(frames)), np.zeros(len(frames))
    r_dev[sub] = _rank(dev[sub])
    r_mouth[sub] = _rank(np.array(mouth)[sub])
    loud = np.asarray(loud, dtype=np.float64)
    if len(loud) == len(frames):
        r_loud[sub] = _rank(loud[sub])
    sharp_a = np.array(sharp)
    med_sharp = float(np.median(sharp_a[sub])) or 1.0
    out = []
    for i in range(len(frames)):
        if crops[i] is None:
            out.append({"face": False, "score": 0.0, "parts": {}})
            continue
        parts = {"change": 0.35 * r_dev[i], "mouth": 0.25 * r_mouth[i], "loud": 0.25 * r_loud[i],
                 "smile": 0.15 * smile[i]}
        crisp = min(1.0, sharp[i] / med_sharp) ** 0.5
        out.append({"face": True, "score": float(sum(parts.values()) * crisp), "parts": parts})
    return out


def best_face(project: Project, cand: dict, facecam: Facecam | None) -> dict | None:
    """The clip moment with the streamer's strongest expression: {t, score 0..100, reasons,
    faces (share of frames with a face), box (the face region used)}. None = no face found."""
    src = project.source_path
    if src is None:
        return None
    meta = project.load_meta()
    box = (facecam.x, facecam.y, facecam.w, facecam.h) if facecam else None
    key = _sig("face2", cand["start"], cand["end"], box)
    cache = folder(project) / f"face_{cand['id']}_{key}.json"
    if cache.is_file():
        try:
            data = read_json(cache)
            return data or None
        except Exception:  # noqa: BLE001
            pass
    times, frames = _clip_frames(src, float(cand["start"]), float(cand["end"]), box,
                                 int(meta.get("width") or 1920), int(meta.get("height") or 1080))
    result: dict = {}
    if frames:
        scored = score_faces(frames, _loudness(project, times))
        faces = sum(1 for s in scored if s["face"])
        if faces:
            i = max(range(len(scored)), key=lambda k: scored[k]["score"])
            parts = scored[i]["parts"]
            reasons = [k for k, v in sorted(parts.items(), key=lambda kv: -kv[1]) if v >= 0.12][:3]
            result = {"t": round(times[i], 2), "score": int(round(scored[i]["score"] * 100)), "reasons": reasons,
                      "faces": round(faces / len(scored), 2), "box": list(box) if box else None}
    folder(project).mkdir(parents=True, exist_ok=True)
    write_json_atomic(cache, result)
    return result or None


# ------------------------------------------------------------------ cover images


def moments(cand: dict) -> dict[str, float]:
    """Source times the cover kinds use."""
    start, end = float(cand["start"]), float(cand["end"])
    peak = float(cand.get("peak") or (start + end) / 2)
    others = sorted((r for r in cand.get("reasons") or [] if isinstance(r.get("t"), (int, float))),
                    key=lambda r: -float(r.get("strength") or 0))
    action = next((float(r["t"]) for r in others if abs(float(r["t"]) - peak) >= 1.5 and start <= r["t"] <= end), None)
    if action is None:
        action = start + (end - start) * (0.3 if peak > (start + end) / 2 else 0.7)
    return {"peak": round(peak, 2), "action": round(action, 2)}


def _style(lang: str | None) -> dict:
    from .edit import brand

    preset = brand.active_preset()
    font = _font_for(lang)
    prim, accent, outline = WHITE, GOLD, NAVY
    if preset:
        from .edit.brand import ass_color

        font = preset.get("caption_font") or font
        prim = ass_color(preset.get("caption_color") or "#FFFFFF")
        accent = ass_color(preset.get("caption_highlight") or "#D9B56A")
        outline = ass_color(preset.get("caption_outline") or "#0E1A33")
    return {"font": font, "primary": prim, "accent": accent, "outline": outline}


def _cover_ass(text: str, frame: str, has_face: bool, lang: str | None) -> str:
    w, h = SIZES[frame]
    st = _style(lang)
    words = _upper(_ass_escape(text), lang).split()
    if not words:
        body = ""
    else:  # the longest word in the accent colour (the "punch" word)
        k = max(range(len(words)), key=lambda i: len(words[i]))
        body = " ".join(f"{{\\c{st['accent']}}}{wd}{{\\c{st['primary']}}}" if i == k else wd
                        for i, wd in enumerate(words))
    rtl = languages.is_rtl(lang)
    if frame == "wide":
        size = 104 if len(text) <= 18 else 88 if len(text) <= 34 else 72
        if has_face:
            align, ml, mr, pos = (6 if rtl else 4), 60, 600, None
        else:
            align, ml, mr, pos = 2, 80, 80, None
        mv = 70
    else:
        size = 132 if len(text) <= 18 else 112 if len(text) <= 34 else 92
        align, ml, mr, mv = 5, 70, 70, 0
        pos = (w // 2, int(h * (0.66 if has_face else 0.5)))
    tag = f"{{\\pos({pos[0]},{pos[1]})}}" if pos else ""
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: cover,{st['font']},{size},{st['primary']},{st['accent']},{st['outline']},&H96000000,-1,0,0,0,"
        f"100,100,0,0,1,{max(6, size // 10)},{max(3, size // 26)},{align},{ml},{mr},{mv},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,0:00:00.00,0:00:10.00,cover,,0,0,0,,{tag}{body}", ""])


def make_cover(project: Project, cand: dict, facecam: Facecam | None, kind: str, text: str, frame: str = "wide",
               lang: str | None = None, face_t: float | None = None) -> Path:
    """Render a cover image (JPEG). kind: peak | action | face | custom. Cached by its inputs."""
    if frame not in SIZES:
        raise SharkyClipsError(f"Unknown cover size '{frame}'.")
    if kind == "custom":
        custom = project.cache_dir / "thumbnails" / f"{cand['id']}.jpg"
        if not custom.is_file():
            raise SharkyClipsError("Choose your own image first.")
        return custom
    if kind not in ("peak", "action", "face"):
        raise SharkyClipsError(f"Unknown cover kind '{kind}'.")
    src = project.source_path
    if src is None:
        raise SharkyClipsError("The source video of this project is missing.")
    m = moments(cand)
    bg_t = m["action"] if kind == "action" else m["peak"]
    face = None
    if kind == "face":
        if face_t is None:
            best = best_face(project, cand, facecam)
            if not best:
                raise SharkyClipsError("No face found in this clip.", "Pick another cover.")
            face_t = best["t"]
        face = (facecam.x, facecam.y, facecam.w, facecam.h) if facecam else None
    text = " ".join((text or "").split())[:80]
    w, h = SIZES[frame]
    key = _sig("cover3", kind, frame, text, bg_t, face_t, face, lang, _style(lang))
    dest = folder(project) / f"{cand['id']}_{kind}_{frame}_{key}.jpg"
    if dest.is_file():
        return dest
    folder(project).mkdir(parents=True, exist_ok=True)
    ffmpeg = require_tool("ffmpeg")
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-cover-"))
    try:
        (work / "cover.ass").write_text(_cover_ass(text, frame, kind == "face", lang), encoding="utf-8")
        inputs = ["-ss", f"{bg_t:.3f}", "-i", str(src)]
        bg = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,"
              f"eq=saturation=1.22:contrast=1.06:brightness=-0.02")
        if frame == "wide" and kind == "face":
            bg += f",drawbox=x=0:y=0:w={int(w * 0.6)}:h={h}:color=0x0E1A33@0.42:t=fill"
        elif frame == "wide":
            bg += f",drawbox=x=0:y={int(h * 0.62)}:w={w}:h={h - int(h * 0.62)}:color=0x0E1A33@0.42:t=fill"
        else:
            bg += f",drawbox=x=0:y={int(h * 0.52)}:w={w}:h={int(h * 0.3)}:color=0x0E1A33@0.38:t=fill"
        graph = bg + "[bg]"
        last = "bg"
        if kind == "face":
            inputs += ["-ss", f"{face_t:.3f}", "-i", str(src)]
            crop = f"crop=iw*{face[2]:.4f}:ih*{face[3]:.4f}:iw*{face[0]:.4f}:ih*{face[1]:.4f}," if face else ""
            if frame == "wide":
                fw, fh, pos = 540, 600, "x=W-w-36:y=(H-h)/2"
            else:
                fw, fh, pos = 940, 900, "x=(W-w)/2:y=150"
            graph += (f";[1:v]{crop}scale={fw}:{fh}:force_original_aspect_ratio=decrease,setsar=1,"
                      f"pad=iw+16:ih+16:8:8:color=0xD9B56A[face];[bg][face]overlay={pos}[wf]")
            last = "wf"
        graph += f";[{last}]ass=cover.ass[out]"
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", graph,
               "-map", "[out]", "-frames:v", "1", "-q:v", "3", "cover.jpg"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(work), **no_window())
        out = work / "cover.jpg"
        if res.returncode != 0 or not out.is_file():
            raise SharkyClipsError("Could not make the cover image.", (res.stderr or "")[-300:] or None)
        shutil.move(str(out), dest)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for old in folder(project).glob(f"{cand['id']}_{kind}_{frame}_*.jpg"):  # keep the folder small
        if old != dest:
            old.unlink(missing_ok=True)
    return dest


# ------------------------------------------------------------------ Shorts: cover as first frame


def _probe_size(path: Path) -> tuple[int, int, float]:
    ffprobe = require_tool("ffprobe")
    res = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, timeout=60, **no_window())
    import json

    try:
        d = json.loads(res.stdout or "{}")
        s = (d.get("streams") or [{}])[0]
        return int(s["width"]), int(s["height"]), float((d.get("format") or {}).get("duration") or 0)
    except (ValueError, KeyError, TypeError):
        raise SharkyClipsError("Could not read the video to put the cover in.") from None


def burn_first_frame(video: Path, image: Path, dest: Path, bitrate_k: int = 12000, seconds: float = FIRST_FRAME_S,
                     on_progress: Callable[[float], None] | None = None) -> Path:
    """The video with `image` shown for its first `seconds` (same length, audio untouched).
    Shorts use their first frame as the default cover."""
    from .clips import bitrate_args
    from .render import pick_codec, run_ffmpeg

    w, h, dur = _probe_size(video)
    enc = pick_codec("h264")
    if enc is None:
        raise SharkyClipsError("No H.264 encoder found for the cover frame.")
    tmp = dest.with_name(dest.stem + ".part" + dest.suffix)
    graph = (f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuv420p[c];"
             f"[0:v][c]overlay=0:0:enable='lt(t,{seconds:.3f})':eof_action=pass,format=yuv420p[v]")
    cmd = [require_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1",
           "-i", str(video), "-loop", "1", "-t", f"{seconds + 0.1:.3f}", "-i", str(image),
           "-filter_complex", graph, "-map", "[v]", "-map", "0:a?", "-c:a", "copy",
           "-c:v", enc.name, *bitrate_args(enc, bitrate_k), "-movflags", "+faststart", str(tmp)]
    code, err = run_ffmpeg(cmd, dur, on_progress)
    if code != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise SharkyClipsError("Could not put the cover into the video.", err[-300:] or None)
    tmp.replace(dest)
    return dest
