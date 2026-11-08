"""Action tracking for the full-height crop (Easy mode 2.0, 1.2.34).

A 9:16 crop of a 16:9 game shows a third of the picture. A fixed centre crop misses fights at the
side; this follows the action instead, like a camera operator:

1. motion map: the source at 6 fps, 160x90 grey; frame differences without the HUD bands (top /
   bottom) and without the camera's own pan (the per-frame median is taken away), so only things
   that move on their own count;
2. target per frame: the crop window with the most motion in it, with a pull back to the centre
   (the crosshair of a shooter, the champion of a MOBA) when nothing stands out;
3. camera operator: the window only moves when the target leaves its middle part (dead zone),
   eases at a limited speed and holds still otherwise - no jitter, no fast pans.

Result: keyframes (source time, crop centre 0..1 of the picture width), cached per cut in
<project>/cache/track/. clips.py turns them into an ffmpeg crop x expression.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

from ..project import Project, read_json, write_json_atomic

VERSION = 1
FPS = 6
GW, GH = 160, 90
HUD_TOP, HUD_BOTTOM = 0.12, 0.18  # bands ignored (kill feed, health bars, ability bar)
CENTER_PULL = 0.35  # how strongly the window prefers the centre (0 = not at all)
QUIET = 0.04  # below this share of a busy frame's motion: "nothing happens" (hold)
DEAD_ZONE = 0.20  # of the window width: the target may wander this far before the window moves
MAX_SPEED = 0.85  # window widths per second at most
KEY_EVERY = 0.5  # seconds between keyframes (before simplifying)


def crop_width(src_w: int, src_h: int, aspect: float = 9 / 16) -> float:
    """The crop window's width as a share of the picture width (0.316 for 16:9 -> 9:16)."""
    return min(1.0, (src_h * aspect) / max(1, src_w))


def _cache_path(project: Project, start: float, end: float, src_w: int, src_h: int):
    src = project.source_path
    st = src.stat() if src is not None and src.exists() else None
    key = hashlib.sha1(json.dumps([VERSION, round(start, 2), round(end, 2), src_w, src_h,
                                   st.st_size if st else 0, int(st.st_mtime) if st else 0]).encode()).hexdigest()[:16]
    return project.cache_dir / "track" / f"{key}.json"


def compute(project: Project, start: float, end: float, src_w: int, src_h: int) -> list[tuple[float, float]]:
    """Keyframes [(source time, centre 0..1)] for [start, end]; [] when tracking can't help."""
    cw = crop_width(src_w, src_h)
    if cw >= 0.95 or end - start < 1.0:
        return []
    path = _cache_path(project, start, end, src_w, src_h)
    if path.is_file():
        try:
            return [tuple(k) for k in read_json(path)["keys"]]  # type: ignore[misc]
        except (OSError, ValueError, KeyError):
            pass
    from ..abtest import _gray

    src = project.source_path
    frames = _gray(src, start, end, fps=FPS, w=GW, h=GH) if src is not None else None
    keys = track(frames, start, cw) if frames is not None and len(frames) >= 3 else []
    write_json_atomic(path, {"version": VERSION, "keys": keys})
    return keys


def targets(frames: np.ndarray, cw: float) -> np.ndarray:
    """Where the action is in each frame step (centre of the best window, 0..1)."""
    d = np.abs(np.diff(frames.astype(np.float32), axis=0))  # (n-1, GH, GW)
    top, bot = int(GH * HUD_TOP), int(GH * (1 - HUD_BOTTOM))
    d = d[:, top:bot, :]
    d = np.clip(d - np.median(d, axis=(1, 2))[:, None, None] - 0.02, 0, None)  # the camera's own pan out
    col = d.sum(axis=1)  # (n-1, GW) motion per column
    win = max(2, int(round(cw * GW)))
    inner = max(1, win // 2)
    cum = np.concatenate([np.zeros((len(col), 1), np.float32), np.cumsum(col, axis=1)], axis=1)
    sums = cum[:, win:] - cum[:, :-win]  # (n-1, GW-win+1): motion inside each window position
    off = (win - inner) // 2  # the same, for the middle half of each window (action centred)
    mids = cum[:, off + inner: off + inner + sums.shape[1]] - cum[:, off: off + sums.shape[1]]
    sums = 0.5 * sums + 0.5 * mids
    centers = (np.arange(sums.shape[1]) + win / 2) / GW
    energy = col.sum(axis=1)
    busy = float(np.percentile(energy, 90)) if len(energy) else 0.0
    out = np.full(len(col), 0.5, np.float32)
    prev = 0.5
    for i in range(len(col)):
        if busy <= 0 or energy[i] < QUIET * busy:
            out[i] = prev  # nothing moves on its own: hold where we are
            continue
        share = sums[i] / (energy[i] + 1e-6)
        score = share - CENTER_PULL * np.abs(centers - 0.5) / 0.5 * (1 - cw)
        prev = float(centers[int(np.argmax(score))])
        out[i] = prev
    lo, hi = cw / 2, 1 - cw / 2
    return np.clip(out, lo, hi)


def _smooth(x: np.ndarray, sigma: float) -> np.ndarray:
    if len(x) < 3 or sigma <= 0:
        return x
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.pad(x, r, mode="edge")
    return np.convolve(pad, k, mode="valid")


def operator(tg: np.ndarray, cw: float, fps: float = FPS) -> np.ndarray:
    """The camera operator: dead zone + limited, eased speed."""
    if len(tg) == 0:
        return tg
    med = np.array([np.median(tg[max(0, i - 2): i + 3]) for i in range(len(tg))], np.float32)  # spikes out
    tg = _smooth(med, 2.0)
    x = float(np.median(tg[: max(1, int(fps))]))  # start where the first second's action is
    out = np.empty(len(tg), np.float32)
    v = 0.0
    vmax = MAX_SPEED * cw / fps
    for i, t in enumerate(tg):
        err = float(t) - x
        if abs(err) > DEAD_ZONE * cw:
            want = np.clip(err * 0.4, -vmax, vmax)
        else:
            want = 0.0
        v = 0.6 * v + 0.4 * want  # ease in / out
        x += v
        out[i] = x
    return np.clip(out, cw / 2, 1 - cw / 2)


def simplify(keys: list[tuple[float, float]], tol: float = 0.004) -> list[tuple[float, float]]:
    """Drop keyframes a straight line between their neighbours already gives."""
    if len(keys) <= 2:
        return keys
    out = [keys[0]]
    for i in range(1, len(keys) - 1):
        (t0, x0), (t1, x1), (t2, x2) = out[-1], keys[i], keys[i + 1]
        lin = x0 + (x2 - x0) * (t1 - t0) / max(1e-6, t2 - t0)
        if abs(lin - x1) > tol:
            out.append(keys[i])
    out.append(keys[-1])
    return out


def track(frames: np.ndarray, start: float, cw: float) -> list[tuple[float, float]]:
    path = operator(targets(frames, cw), cw)
    step = max(1, int(round(KEY_EVERY * FPS)))
    keys = [(round(start + (i + 1) / FPS, 3), round(float(path[i]), 4)) for i in range(0, len(path), step)]
    if len(path) and (len(path) - 1) % step:
        keys.append((round(start + len(path) / FPS, 3), round(float(path[-1]), 4)))
    keys = simplify(keys)
    if all(abs(x - 0.5) < 0.01 for _t, x in keys):
        return []  # the centre all along: a plain centre crop is the same
    return keys


def at(keys: list[tuple[float, float]], t: float) -> float:
    if not keys:
        return 0.5
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, x0), (t1, x1) in zip(keys, keys[1:]):
        if t <= t1:
            return x0 + (x1 - x0) * (t - t0) / max(1e-6, t1 - t0)
    return keys[-1][1]


def expr(keys: list[tuple[float, float]]) -> str:
    """keys in OUTPUT time (seconds from the stream start) -> an ffmpeg expression of t giving the
    centre (0..1). Piecewise linear, nested if()s (the keyframes are few after simplify()); used
    inside single quotes in the filter graph, so its commas need no escaping."""
    if not keys:
        return "0.5"
    if len(keys) == 1:
        return f"{keys[0][1]:.4f}"
    tail = f"{keys[-1][1]:.4f}"
    for (t0, x0), (t1, x1) in reversed(list(zip(keys, keys[1:]))):
        seg = f"{x0:.4f}+({x1 - x0:.4f})*(t-{t0:.3f})/{max(1e-3, t1 - t0):.3f}"
        tail = f"if(lt(t,{t1:.3f}),{seg},{tail})"
    return f"if(lt(t,{keys[0][0]:.3f}),{keys[0][1]:.4f},{tail})"
