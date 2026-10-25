"""Facecam detection for streams: where is the webcam overlay in the frame?

1. Sample ~12 frames spread over the video.
2. Find faces (OpenCV's bundled Haar cascade - no downloads). A facecam face
   shows up at about the same spot in many frames; faces in the game don't.
3. Grow a box from that face over the camera's background. The background of a
   webcam (a room) barely changes between frames far apart, while gameplay
   changes completely, so the region with low change over time is the facecam.

The result is a starting point; the user can fix it in the web UI.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .clips import Facecam
from .errors import require_module, require_tool

ANALYSIS_W = 1280


def _sample_frames(path: Path, duration: float, count: int = 12) -> list[np.ndarray]:
    """Frames as BGR arrays, ANALYSIS_W wide. ffmpeg seeks fast in every codec (incl. AV1)."""
    import subprocess

    from .audio import probe
    from .procs import no_window

    ffmpeg = require_tool("ffmpeg")
    info = probe(path)
    sw, sh = info.get("width") or 1920, info.get("height") or 1080
    out_h = int(round(sh * ANALYSIS_W / sw / 2)) * 2
    frames = []
    for i in range(count):
        t = duration * (0.05 + 0.9 * i / max(1, count - 1))
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(path),
               "-frames:v", "1", "-vf", f"scale={ANALYSIS_W}:{out_h}:flags=area",
               "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=60, **no_window())
        except (OSError, subprocess.SubprocessError):
            continue
        if res.returncode == 0 and len(res.stdout) == ANALYSIS_W * out_h * 3:
            frames.append(np.frombuffer(res.stdout, np.uint8).reshape(out_h, ANALYSIS_W, 3))
    return frames


def _faces(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    cv2 = require_module("cv2", "opencv-python-headless")
    h = gray.shape[0]
    gray = cv2.equalizeHist(gray)
    found = []
    for name in ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml"):
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + name)
        found += [tuple(int(v) for v in f) for f in cascade.detectMultiScale(
            gray, scaleFactor=1.08, minNeighbors=4, minSize=(int(h * 0.05), int(h * 0.05)),
            maxSize=(int(h * 0.6), int(h * 0.6)))]
    # Both cascades often find the same face: keep one box per spot.
    unique: list[tuple[int, int, int, int]] = []
    for f in sorted(found, key=lambda f: -f[2]):
        if all(abs(f[0] - u[0]) > u[2] / 2 or abs(f[1] - u[1]) > u[3] / 2 for u in unique):
            unique.append(f)
    return unique


def _cluster(faces: list[tuple[int, int, int, int, int]], tol: float) -> list[list[tuple]]:
    """Group face boxes (with frame index) whose centers are close."""
    clusters: list[list[tuple]] = []
    for f in faces:
        cx, cy = f[0] + f[2] / 2, f[1] + f[3] / 2
        for cl in clusters:
            gx = np.mean([g[0] + g[2] / 2 for g in cl])
            gy = np.mean([g[1] + g[3] / 2 for g in cl])
            if abs(cx - gx) < tol and abs(cy - gy) < tol:
                cl.append(f)
                break
        else:
            clusters.append([f])
    return clusters


def _grow(static: np.ndarray, box: list[int], min_fill: float = 0.62) -> list[int]:
    """Expand box [x0, y0, x1, y1] side by side while the new strip is mostly static."""
    h, w = static.shape
    x0, y0, x1, y1 = box
    step = max(2, w // 160)
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


def detect_facecam(path: Path, duration: float) -> Facecam | None:
    cv2 = require_module("cv2", "opencv-python-headless")
    frames = _sample_frames(path, duration)
    if len(frames) < 4:
        return None
    h, w = frames[0].shape[:2]
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    faces = [(*f, i) for i, g in enumerate(grays) for f in _faces(g)]
    if not faces:
        return None
    clusters = _cluster(faces, tol=h * 0.06)
    best = max(clusters, key=lambda cl: len({f[4] for f in cl}))
    hits = len({f[4] for f in best})
    if hits < max(3, len(frames) // 4):
        return None  # no face that stays in one place -> probably no facecam

    fx = int(np.median([f[0] for f in best]))
    fy = int(np.median([f[1] for f in best]))
    fs = int(np.median([f[2] for f in best]))

    # Pixels that barely change over time (blurred so noise / compression don't matter).
    stack = np.stack([cv2.GaussianBlur(g, (5, 5), 0).astype(np.float32) for g in grays])
    static = (stack.std(axis=0) < 14).astype(np.float32)
    seed = [max(0, fx - fs // 2), max(0, fy - fs // 2), min(w, fx + fs + fs // 2), min(h, fy + fs * 2)]
    x0, y0, x1, y1 = _grow(static, seed)

    # Sanity: a facecam is bigger than the face and not most of the screen.
    bw, bh = x1 - x0, y1 - y0
    if bw < fs * 1.6 or bh < fs * 1.4 or bw * bh > 0.5 * w * h:
        # Fall back to a typical webcam box around the face (16:9-ish, 3.2 faces wide).
        bw, bh = int(fs * 3.4), int(fs * 2.6)
        x0 = max(0, min(w - bw, fx + fs // 2 - bw // 2))
        y0 = max(0, min(h - bh, fy + fs // 2 - int(bh * 0.42)))
        x1, y1 = x0 + bw, y0 + bh
        confidence = 0.4
    else:
        confidence = 0.8

    # Snap to the frame edges when close (overlays usually sit in a corner).
    snap = 0.03
    nx0, ny0, nx1, ny1 = x0 / w, y0 / h, x1 / w, y1 / h
    nx0 = 0.0 if nx0 < snap else nx0
    ny0 = 0.0 if ny0 < snap else ny0
    nx1 = 1.0 if nx1 > 1 - snap else nx1
    ny1 = 1.0 if ny1 > 1 - snap else ny1
    return Facecam(nx0, ny0, nx1 - nx0, ny1 - ny0, source="auto",
                   confidence=round(confidence * min(1.0, hits / (len(frames) * 0.6)), 2))
