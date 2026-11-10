"""Facecam detection: where is the webcam overlay in the frame?

A webcam overlay is a STATIC rectangle with a LIVE face in it. A face alone is not enough:
games are full of faces (characters, cutscenes, HUD portraits).

1. Sample ~32 frames spread over the whole video.
2. Find faces in every frame (YuNet, a 230 KB OpenCV model downloaded once into the settings
   folder; OpenCV's bundled Haar cascades when it can't be downloaded).
3. Group faces that sit at the same spot across frames. A webcam face shows up in many frames
   (presence) and moves a little (liveness). Faces that wander around the scene never form a
   big group; a HUD portrait is pixel-identical in every frame and is rejected as "not alive".
4. Grow a box from the face over pixels that barely change (the room behind the streamer),
   then snap each side to a PERSISTENT border: an edge that is there in most frames, because
   the room and the game on either side of it are unrelated. The more sides have such a border
   (or touch the frame edge), the more it looks like an overlay rectangle.
5. Score every group (presence, liveness, border, plausible size). The best one wins; all of
   them are kept as candidates so the UI can let the user pick with one click when unsure.

Layouts the user confirmed are remembered per channel + resolution (facecam_layouts.json)
and reused on new projects after a quick check that a live face is still in that box.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from .clips import Facecam
from .errors import require_module, require_tool

ANALYSIS_W = 1280  # face detection
STAT_W = 480  # change / border statistics
SAMPLES = 32
LOW_CONFIDENCE = 0.6  # below this the UI asks the user to pick

YUNET_NAME = "face_detection_yunet_2023mar.onnx"
YUNET_URL = ("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/"
             "face_detection_yunet/" + YUNET_NAME)
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"

_model_lock = threading.Lock()


# ----------------------------------------------------------------------------- face model

def _model_path() -> Path:
    from . import config

    return config.config_dir() / "models" / "yunet" / YUNET_NAME


def ensure_face_model(download: bool = True) -> Path | None:
    """The YuNet model (downloaded once, checked by hash). None = offline: use Haar instead."""
    path = _model_path()
    with _model_lock:
        if path.is_file():
            return path
        if not download or os.environ.get("SHARKYCLIPS_NO_DOWNLOADS"):
            return None
        try:
            import requests

            r = requests.get(YUNET_URL, timeout=30)
            if not r.ok or hashlib.sha256(r.content).hexdigest() != YUNET_SHA256:
                return None
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(r.content)
            os.replace(tmp, path)
            return path
        except Exception:  # noqa: BLE001 - offline -> Haar
            return None


class FaceFinder:
    """Faces as (x, y, w, h, score) in pixels of the given BGR frame."""

    def __init__(self, use_model: bool = True):
        self.cv2 = require_module("cv2", "opencv-python-headless")
        self.yunet = None
        model = ensure_face_model() if use_model else None
        if model is not None and hasattr(self.cv2, "FaceDetectorYN"):
            try:
                self.yunet = self.cv2.FaceDetectorYN.create(str(model), "", (320, 320), 0.7, 0.3, 50)
            except Exception:  # noqa: BLE001 - broken model file -> Haar
                self.yunet = None
        self.kind = "yunet" if self.yunet is not None else "haar"

    def __call__(self, bgr: np.ndarray) -> list[tuple[int, int, int, int, float]]:
        h, w = bgr.shape[:2]
        if self.yunet is not None:
            self.yunet.setInputSize((w, h))
            _, found = self.yunet.detect(bgr)
            out = []
            for f in (found if found is not None else []):
                x, y, fw, fh = (int(round(v)) for v in f[:4])
                if fh >= h * 0.035:
                    out.append((x, y, fw, fh, float(f[-1])))
            return out
        return [(*f, 0.75) for f in _haar_faces(self.cv2, self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2GRAY))]


def _haar_faces(cv2, gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    h = gray.shape[0]
    gray = cv2.equalizeHist(gray)
    found = []
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml"):
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        found += [tuple(int(v) for v in f) for f in cascade.detectMultiScale(
            gray, scaleFactor=1.08, minNeighbors=4, minSize=(int(h * 0.05), int(h * 0.05)),
            maxSize=(int(h * 0.6), int(h * 0.6)))]
    unique: list[tuple[int, int, int, int]] = []
    for f in sorted(found, key=lambda f: -f[2]):  # both cascades often find the same face
        if all(abs(f[0] - u[0]) > u[2] / 2 or abs(f[1] - u[1]) > u[3] / 2 for u in unique):
            unique.append(f)
    return unique


# ----------------------------------------------------------------------------- frames

def _sample_times(duration: float, count: int) -> list[float]:
    return [duration * (0.03 + 0.94 * i / max(1, count - 1)) for i in range(count)]


def _grab(path: Path, t: float, out_w: int, out_h: int) -> np.ndarray | None:
    import subprocess

    from .procs import no_window

    cmd = [require_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(path),
           "-frames:v", "1", "-vf", f"scale={out_w}:{out_h}:flags=area",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=60, **no_window())
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode == 0 and len(res.stdout) == out_w * out_h * 3:
        return np.frombuffer(res.stdout, np.uint8).reshape(out_h, out_w, 3)
    return None


def _sample_frames(path: Path, duration: float, count: int = SAMPLES,
                   times: list[float] | None = None) -> tuple[list[np.ndarray], list[float]]:
    """(frames as BGR arrays ANALYSIS_W wide, their times). ffmpeg seeks fast in every codec."""
    from .audio import probe

    info = probe(path)
    sw, sh = info.get("width") or 1920, info.get("height") or 1080
    out_h = int(round(sh * ANALYSIS_W / sw / 2)) * 2
    times = times if times is not None else _sample_times(duration, count)
    with ThreadPoolExecutor(max_workers=3) as pool:
        grabbed = list(pool.map(lambda t: _grab(path, t, ANALYSIS_W, out_h), times))
    pairs = [(f, t) for f, t in zip(grabbed, times) if f is not None]
    return [p[0] for p in pairs], [p[1] for p in pairs]


# ----------------------------------------------------------------------------- statistics

class _Stats:
    """Per-pixel statistics over all frames at STAT_W: how much it changes, persistent edges."""

    def __init__(self, frames: list[np.ndarray]):
        cv2 = require_module("cv2", "opencv-python-headless")
        h, w = frames[0].shape[:2]
        self.scale = STAT_W / w
        sh = max(8, int(round(h * self.scale)))
        grays = [cv2.GaussianBlur(cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (STAT_W, sh),
                                             interpolation=cv2.INTER_AREA), (3, 3), 0).astype(np.float32)
                 for f in frames]
        self.stack = np.stack(grays)  # (n, sh, STAT_W)
        self.h, self.w = sh, STAT_W
        self.std = self.stack.std(axis=0)
        self.static = (self.std < 14).astype(np.float32)
        self.dynamic = (self.std > 18).astype(np.float32)  # gameplay-like change
        # An edge between two unrelated pictures (room | game) is there in almost every frame.
        gx = np.abs(np.diff(self.stack, axis=2))  # (n, sh, w-1): edge between x and x+1
        gy = np.abs(np.diff(self.stack, axis=1))
        self.pv = np.pad((gx > 9).mean(axis=0), ((0, 0), (0, 1)))  # vertical lines
        self.ph = np.pad((gy > 9).mean(axis=0), ((0, 1), (0, 0)))  # horizontal lines

    def vline(self, x: int, y0: int, y1: int) -> float:
        """How persistent a vertical border between columns x-1 and x is over rows y0..y1."""
        if x <= 0 or x >= self.w or y1 - y0 < 2:
            return 0.0
        cols = self.pv[y0:y1, max(0, x - 2):min(self.w, x + 1)]
        return float(cols.max(axis=1).mean())

    def hline(self, y: int, x0: int, x1: int) -> float:
        if y <= 0 or y >= self.h or x1 - x0 < 2:
            return 0.0
        rows = self.ph[max(0, y - 2):min(self.h, y + 1), x0:x1]
        return float(rows.max(axis=0).mean())


def _cluster(faces: list[tuple], tol: float) -> list[list[tuple]]:
    """Group face boxes (x, y, w, h, score, frame) whose centers are close and sizes similar."""
    clusters: list[list[tuple]] = []
    for f in sorted(faces, key=lambda f: -f[4]):
        cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
        for cl in clusters:
            gx = np.mean([g[0] + g[2] / 2 for g in cl])
            gy = np.mean([g[1] + g[3] / 2 for g in cl])
            gs = np.median([g[3] for g in cl])
            if abs(cx - gx) < tol and abs(cy - gy) < tol and 0.6 < f[3] / gs < 1.67:
                cl.append(f)
                break
        else:
            clusters.append([f])
    return clusters


def _grow(static: np.ndarray, box: list[int], min_fill: float = 0.62) -> list[int]:
    """Expand box [x0, y0, x1, y1] side by side while the new strip is mostly static."""
    h, w = static.shape
    x0, y0, x1, y1 = box
    step = max(1, w // 160)
    grew = True
    while grew:
        grew = False
        if x0 - step >= 0 and static[y0:y1, x0 - step:x0].mean() >= min_fill:
            x0 -= step
            grew = True
        if x1 + step <= w and static[y0:y1, x1:x1 + step].mean() >= min_fill:
            x1 += step
            grew = True
        if y0 - step >= 0 and static[y0 - step:y0, x0:x1].mean() >= min_fill:
            y0 -= step
            grew = True
        if y1 + step <= h and static[y1:y1 + step, x0:x1].mean() >= min_fill:
            y1 += step
            grew = True
    return [max(0, x0), max(0, y0), min(w, x1), min(h, y1)]


LINE_MIN = 0.5  # persistence that counts as an overlay border


def _snap_sides(st: _Stats, box: list[int], face: list[int]) -> tuple[list[int], list[float]]:
    """Move each side of the box onto the most persistent border near it (or the frame edge).

    A border only counts when the strip just OUTSIDE it changes like gameplay does: an edge with
    the room on both sides is furniture (a shelf, a door frame) or the streamer's shoulder.
    Next to the frame edge an inner line must be clearly persistent to win over the edge.
    Returns the box and one border score per side (left, top, right, bottom); 1.0 = the side
    is the frame edge. Sides never cross the face."""
    x0, y0, x1, y1 = box
    fx0, fy0, fx1, fy1 = face
    fs = max(4, fy1 - fy0)
    strip = max(2, fs // 2)
    edge = max(2, int(st.w * 0.03))
    scores = [0.0] * 4

    def outside(side: int, c: int) -> float:
        if side == 0:
            a = st.dynamic[y0:y1, max(0, c - strip):c]
        elif side == 2:
            a = st.dynamic[y0:y1, c:c + strip]
        elif side == 1:
            a = st.dynamic[max(0, c - strip):c, x0:x1]
        else:
            a = st.dynamic[c:c + strip, x0:x1]
        return float(a.mean()) if a.size else 0.0

    def pick(side: int, cands, line, at_edge: bool, cur: int, frame_edge: int):
        vals = [(line(c), c) for c in cands if outside(side, c) >= 0.35]
        s, c = max(vals) if vals else (0.0, None)
        if at_edge and s < 0.75:
            return frame_edge, 1.0
        if c is not None and s >= LINE_MIN:
            return c, s
        return cur, line(cur)

    for _ in range(2):  # the second pass uses the corrected extent of the other sides
        lo, hi = max(0, x0 - 2 * fs), min(fx0, x0 + fs)
        x0, scores[0] = pick(0, range(max(1, lo), max(1, hi) + 1), lambda x: st.vline(x, y0, y1),
                             x0 <= edge or lo <= edge, x0, 0)
        lo, hi = max(fx1, x1 - fs), min(st.w, x1 + 2 * fs)
        x1, scores[2] = pick(2, range(lo, min(st.w - 1, hi) + 1), lambda x: st.vline(x, y0, y1),
                             x1 >= st.w - edge or hi >= st.w - edge, x1, st.w)
        lo, hi = max(0, y0 - 2 * fs), min(fy0, y0 + fs)
        y0, scores[1] = pick(1, range(max(1, lo), max(1, hi) + 1), lambda y: st.hline(y, x0, x1),
                             y0 <= edge or lo <= edge, y0, 0)
        lo, hi = max(fy1, y1 - fs), min(st.h, y1 + 2 * fs)
        y1, scores[3] = pick(3, range(lo, min(st.h - 1, hi) + 1), lambda y: st.hline(y, x0, x1),
                             y1 >= st.h - edge or hi >= st.h - edge, y1, st.h)
    return [x0, y0, x1, y1], scores


def _liveness(st: _Stats, face: list[int], frames_idx: list[int]) -> float:
    """0..1: does the face change between frames? A real person moves; a HUD portrait doesn't."""
    fx0, fy0, fx1, fy1 = face
    if fx1 - fx0 < 2 or fy1 - fy0 < 2:
        return 0.0
    crop = st.stack[frames_idx, fy0:fy1, fx0:fx1] if len(frames_idx) >= 2 else st.stack[:, fy0:fy1, fx0:fx1]
    std = float(crop.std(axis=0).mean())
    return float(np.clip((std - 2.5) / 7.5, 0.0, 1.0))


def _candidate(st: _Stats, cl: list[tuple], n: int, fw: int, fh: int) -> dict:
    """Score one face group and build its overlay box (normalized)."""
    s = st.scale
    fx = float(np.median([f[0] for f in cl]))
    fy = float(np.median([f[1] for f in cl]))
    fs_w = float(np.median([f[2] for f in cl]))
    fs_h = float(np.median([f[3] for f in cl]))
    frames_idx = sorted({f[5] for f in cl})
    presence = len(frames_idx) / max(1, n)
    face = [int(fx * s), int(fy * s), int((fx + fs_w) * s), int((fy + fs_h) * s)]
    face = [max(0, face[0]), max(0, face[1]), min(st.w, face[2]), min(st.h, face[3])]
    fsz = max(4, face[3] - face[1])
    live = _liveness(st, face, frames_idx)

    seed = [max(0, face[0] - fsz // 2), max(0, face[1] - fsz // 2),
            min(st.w, face[2] + fsz // 2), min(st.h, face[3] + fsz)]
    grown = _grow(st.static, seed)
    bw, bh = grown[2] - grown[0], grown[3] - grown[1]
    if bw < fsz * 1.6 or bh < fsz * 1.4 or bw * bh > 0.4 * st.w * st.h:
        # The room isn't static enough to grow over: a typical webcam box around the face.
        bw, bh = int(fsz * 3.4), int(fsz * 2.6)
        x0 = max(0, min(st.w - bw, (face[0] + face[2]) // 2 - bw // 2))
        y0 = max(0, min(st.h - bh, face[1] + fsz // 2 - int(bh * 0.42)))
        grown = [x0, y0, x0 + bw, y0 + bh]
    box, sides = _snap_sides(st, grown, face)
    x0, y0, x1, y1 = box
    border = float(np.mean(sides))
    inner = [v for v in sides if v < 1.0]
    area = (x1 - x0) * (y1 - y0) / (st.w * st.h)
    ratio = fsz / max(1, y1 - y0)
    plausible = 1.0
    if not 0.01 <= area <= 0.35:
        plausible *= 0.4
    if not 0.12 <= ratio <= 0.75:
        plausible *= 0.6

    conf = (0.40 * min(1.0, presence / 0.5) + 0.25 * border + 0.20 * live + 0.15 * plausible)
    if live < 0.15:
        conf *= 0.25  # pixel-identical "face": a HUD portrait, a logo, a poster in the game
    if presence < 0.25:
        conf *= presence / 0.25  # a face that is here only now and then: a character moving around
    if inner and min(inner) < 0.3 and len(inner) >= 2:
        conf *= 0.85  # floating box without clear borders
    return {
        "x": round(x0 / st.w, 4), "y": round(y0 / st.h, 4),
        "w": round((x1 - x0) / st.w, 4), "h": round((y1 - y0) / st.h, 4),
        "confidence": round(float(np.clip(conf, 0, 1)), 2),
        "presence": round(presence, 2), "liveness": round(live, 2), "border": round(border, 2),
        "face": {"x": round(face[0] / st.w, 4), "y": round(face[1] / st.h, 4),
                 "w": round((face[2] - face[0]) / st.w, 4), "h": round((face[3] - face[1]) / st.h, 4)},
        "frames": frames_idx,
    }


def _overlap(a: dict, b: dict) -> float:
    ix = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    iy = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    inter = ix * iy
    return inter / max(1e-6, min(a["w"] * a["h"], b["w"] * b["h"]))


def analyze_frames(frames: list[np.ndarray], finder: FaceFinder | None = None) -> dict:
    """Candidates (best first) from already sampled frames. Pure - the tests feed synthetic frames."""
    if len(frames) < 4:
        return {"candidates": [], "frames": len(frames), "detector": None}
    finder = finder or FaceFinder()
    h, w = frames[0].shape[:2]
    faces = [(*f, i) for i, fr in enumerate(frames) for f in finder(fr)]
    st = _Stats(frames)
    n = len(frames)
    clusters = [cl for cl in _cluster(faces, tol=h * 0.06) if len({f[5] for f in cl}) >= max(2, n // 10)]
    cands = [_candidate(st, cl, n, w, h) for cl in clusters]
    cands.sort(key=lambda c: -c["confidence"])
    unique: list[dict] = []
    for c in cands:  # two faces in one overlay (duo cam) -> one box
        if all(_overlap(c, u) < 0.6 for u in unique):
            unique.append(c)
    return {"candidates": unique[:6], "frames": n, "detector": finder.kind,
            "faces": len(faces)}


def to_facecam(c: dict, source: str = "auto") -> Facecam:
    """Candidate -> Facecam, snapped to the frame edges when close (overlays sit in a corner)."""
    snap = 0.03
    x0, y0, x1, y1 = c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"]
    x0 = 0.0 if x0 < snap else x0
    y0 = 0.0 if y0 < snap else y0
    x1 = 1.0 if x1 > 1 - snap else x1
    y1 = 1.0 if y1 > 1 - snap else y1
    return Facecam(x0, y0, x1 - x0, y1 - y0, source=source, confidence=c.get("confidence"))


def analyze(path: Path, duration: float, count: int = SAMPLES, frame_out: Path | None = None) -> dict:
    """Full analysis of a video. With frame_out, a JPEG of a frame with the best face is saved
    there (the UI draws the candidates on it for the one-click pick)."""
    cv2 = require_module("cv2", "opencv-python-headless")
    t0 = time.time()
    frames, times = _sample_frames(path, duration, count)
    res = analyze_frames(frames)
    res["seconds"] = round(time.time() - t0, 1)
    best = res["candidates"][0] if res["candidates"] else None
    res["confidence"] = best["confidence"] if best else 0.0
    if frame_out is not None and frames:
        idx = best["frames"][len(best["frames"]) // 2] if best and best["frames"] else len(frames) // 2
        frame_out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(frame_out), frames[idx], [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        res["frame_time"] = round(times[idx], 2)
        h, w = frames[idx].shape[:2]
        res["frame_size"] = [w, h]
    return res


def verify_box(path: Path, duration: float, box: dict, count: int = 10) -> float:
    """Share of sampled frames with a live face inside a remembered box (0..1)."""
    frames, _ = _sample_frames(path, duration, count)
    if len(frames) < 3:
        return 0.0
    finder = FaceFinder()
    h, w = frames[0].shape[:2]
    bx0, by0 = box["x"] * w, box["y"] * h
    bx1, by1 = bx0 + box["w"] * w, by0 + box["h"] * h
    hits = []
    for i, fr in enumerate(frames):
        for (x, y, fw, fh, _s) in finder(fr):
            cx, cy = x + fw / 2, y + fh / 2
            if bx0 <= cx <= bx1 and by0 <= cy <= by1 and fh < (by1 - by0):
                hits.append((x, y, fw, fh, _s, i))
                break
    if not hits:
        return 0.0
    st = _Stats(frames)
    s = st.scale
    fx, fy = np.median([f[0] for f in hits]) * s, np.median([f[1] for f in hits]) * s
    fsz = np.median([f[3] for f in hits]) * s
    live = _liveness(st, [int(fx), int(fy), int(fx + fsz), int(fy + fsz)], sorted({f[5] for f in hits}))
    if live < 0.15:
        return 0.0
    return len({f[5] for f in hits}) / len(frames)


# ----------------------------------------------------------------------------- remembered layouts

def _layouts_path() -> Path:
    from . import config

    return config.config_dir() / "facecam_layouts.json"


def layout_key(meta: dict) -> dict:
    """Who / what resolution a project's facecam layout belongs to."""
    src = meta.get("source") or {}
    channel = str(src.get("uploader") or src.get("channel") or "").strip()
    if not channel:
        channel = "local files" if src.get("type") == "file" else "unknown"
    game = (meta.get("game_detect") or {}).get("game") or ""
    if meta.get("game") and meta.get("game") != "auto":
        game = meta["game"]
    return {"channel": channel, "width": int(meta.get("width") or 0), "height": int(meta.get("height") or 0),
            "game": str(game or "")}


def load_layouts() -> list[dict]:
    from .project import read_json

    try:
        data = read_json(_layouts_path())
    except Exception:  # noqa: BLE001
        return []
    return data.get("layouts", []) if isinstance(data, dict) else []


def find_layout(meta: dict) -> dict | None:
    """The remembered layout for this channel + resolution (same game preferred)."""
    key = layout_key(meta)
    same = [lay for lay in load_layouts() if lay.get("channel") == key["channel"]
            and lay.get("width") == key["width"] and lay.get("height") == key["height"]]
    if not same:
        return None
    same.sort(key=lambda lay: (lay.get("game") == key["game"], lay.get("confirmed", False),
                               lay.get("saved_at", "")), reverse=True)
    return same[0]


def remember_layout(meta: dict, fc: Facecam, confirmed: bool) -> None:
    """Save (or replace) the layout for this channel + resolution + game."""
    from .project import write_json_atomic

    key = layout_key(meta)
    if not key["width"] or not key["height"]:
        return
    layouts = [lay for lay in load_layouts() if not (
        lay.get("channel") == key["channel"] and lay.get("width") == key["width"]
        and lay.get("height") == key["height"] and lay.get("game", "") == key["game"])]
    old = find_layout(meta)
    if old and old.get("confirmed") and not confirmed and old.get("game", "") == key["game"]:
        return  # never overwrite the user's own choice with a guess
    box = fc.to_dict()
    layouts.append({**key, "box": {k: box[k] for k in ("x", "y", "w", "h")}, "confirmed": bool(confirmed),
                    "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    write_json_atomic(_layouts_path(), {"layouts": layouts[-200:]})


def forget_layout(meta: dict) -> None:
    from .project import write_json_atomic

    key = layout_key(meta)
    layouts = [lay for lay in load_layouts() if not (
        lay.get("channel") == key["channel"] and lay.get("width") == key["width"]
        and lay.get("height") == key["height"])]
    write_json_atomic(_layouts_path(), {"layouts": layouts})


def analysis_paths(project) -> tuple[Path, Path]:
    d = project.cache_dir / "facecam"
    return d / "analysis.json", d / "frame.jpg"


def detect_for_project(project, use_memory: bool = True) -> dict:
    """What the facecam job runs: remembered layout (checked) or a full analysis.

    Returns {"facecam": dict | None, "from": "memory" | "detect", "confidence", "ask": bool}."""
    from .project import write_json_atomic

    meta = project.load_meta()
    duration = float(meta.get("duration") or 0)
    if use_memory:
        lay = find_layout(meta)
        if lay and verify_box(project.source_path, duration, lay["box"]) >= 0.25:
            fc = Facecam.from_dict({**lay["box"], "source": "remembered", "confidence": 0.95})
            return {"facecam": fc.to_dict(), "from": "memory", "confidence": 0.95, "ask": False,
                    "layout": {k: lay.get(k) for k in ("channel", "width", "height", "game")}}
    out_json, out_jpg = analysis_paths(project)
    res = analyze(project.source_path, duration, frame_out=out_jpg)
    cands = res["candidates"]
    best = cands[0] if cands and cands[0]["confidence"] >= 0.2 else None
    close = len(cands) > 1 and best is not None and cands[1]["confidence"] >= best["confidence"] - 0.15
    ask = bool(cands) and (best is None or best["confidence"] < LOW_CONFIDENCE or close)
    write_json_atomic(out_json, {**{k: v for k, v in res.items()}, "ask": ask,
                                 "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    fc = to_facecam(best) if best else None
    if fc and not ask and best["confidence"] >= 0.75:
        remember_layout(meta, fc, confirmed=False)
    return {"facecam": fc.to_dict() if fc else None, "from": "detect",
            "confidence": res["confidence"], "ask": ask}


def load_analysis(project) -> dict | None:
    from .project import read_json

    path, _ = analysis_paths(project)
    try:
        data = read_json(path)
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None
