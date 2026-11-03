"""Sound effects for replays and meme effects, synthesized here in numpy.

No sample files: every sound is made from sine sweeps and filtered noise when a clip renders,
so there is nothing copyrighted and nothing to download. 48 kHz stereo float32, peak ~0.9.

  boom    deep "dun" hit with a long tail (freeze frames)
  whoosh  rising-falling air sweep (start of a replay)
  thud    short punchy low hit (fails: zoom / shake)
  rewind  quick tape-rewind chirp (end of a replay)
"""

from __future__ import annotations

import numpy as np

SR = 48000
NAMES = ("boom", "whoosh", "thud", "rewind")


def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR), dtype=np.float64) / SR


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    """Fast linear attack, exponential decay (time constant `decay` seconds)."""
    t = np.arange(n, dtype=np.float64) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-np.maximum(0.0, t - attack) / decay)


def _noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(n)


def _lowpass(x: np.ndarray, cutoff: np.ndarray | float) -> np.ndarray:
    """One-pole low-pass with a (possibly moving) cutoff in Hz."""
    cut = np.broadcast_to(np.asarray(cutoff, dtype=np.float64), x.shape)
    alpha = 1.0 - np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # short sounds (< 1 s): a plain loop is fast enough
        acc += alpha[i] * (x[i] - acc)
        y[i] = acc
    return y


def _norm(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = float(np.max(np.abs(x))) or 1.0
    y = (x / m * peak).astype(np.float32)
    fade = min(len(y), int(0.01 * SR))
    if fade:
        y[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return y


def boom(seconds: float = 1.1) -> np.ndarray:
    t = _t(seconds)
    freq = 38 + 52 * np.exp(-t / 0.09)  # 90 Hz falling to ~38 Hz
    phase = 2 * np.pi * np.cumsum(freq) / SR
    body = np.sin(phase) * _env(len(t), 0.004, 0.42)
    body = np.tanh(2.2 * body)  # a little drive: it reads on phone speakers
    click = _lowpass(_noise(len(t), 1), 2500.0) * _env(len(t), 0.001, 0.012) * 1.6
    sub = np.sin(2 * np.pi * 45 * t) * _env(len(t), 0.01, 0.6) * 0.35
    return _norm(body + click + sub)


def whoosh(seconds: float = 0.55) -> np.ndarray:
    t = _t(seconds)
    x = t / seconds
    shape = np.sin(np.pi * x) ** 2
    cutoff = 300 + 5200 * np.sin(np.pi * x) ** 1.5
    air = _lowpass(_noise(len(t), 2), cutoff) - _lowpass(_noise(len(t), 3), 120.0) * 0.3
    return _norm(air * shape, 0.7)


def thud(seconds: float = 0.35) -> np.ndarray:
    t = _t(seconds)
    freq = 60 + 110 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * _env(len(t), 0.002, 0.09)
    hit = _lowpass(_noise(len(t), 4), 1800.0) * _env(len(t), 0.001, 0.02)
    return _norm(np.tanh(1.8 * body) + hit * 1.2, 0.85)


def rewind(seconds: float = 0.4) -> np.ndarray:
    t = _t(seconds)
    freq = 900 + 2600 * (t / seconds) ** 2  # rising chirp
    tone = np.sign(np.sin(2 * np.pi * np.cumsum(freq) / SR)) * 0.25  # square-ish, tape-like
    flutter = 1 + 0.3 * np.sin(2 * np.pi * 38 * t)
    y = _lowpass(tone * flutter, 3500.0) * np.sin(np.pi * t / seconds) ** 0.7
    return _norm(y, 0.45)


_CACHE: dict[str, np.ndarray] = {}


def sound(name: str) -> np.ndarray:
    """Stereo (n, 2) float32 of a named effect (cached per process)."""
    if name not in NAMES:
        raise ValueError(f"unknown sound effect {name!r}")
    if name not in _CACHE:
        mono = {"boom": boom, "whoosh": whoosh, "thud": thud, "rewind": rewind}[name]()
        _CACHE[name] = np.repeat(mono[:, None], 2, axis=1)
    return _CACHE[name]
