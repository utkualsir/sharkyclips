"""Integrated loudness (ITU-R BS.1770-4 / EBU R128, the "LUFS" YouTube and TikTok use)
and a look-ahead peak limiter, for 48 kHz float audio shaped (samples, channels)."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import lfilter

SR = 48000
# K-weighting at 48 kHz: high shelf (head) + high-pass (RLB), coefficients from the standard.
_SHELF = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
_HIGHPASS = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def integrated_lufs(x: np.ndarray, sr: int = SR) -> float:
    """Gated integrated loudness. Silence -> -70.0."""
    if x.ndim == 1:
        x = x[:, None]
    if len(x) < int(0.4 * sr):
        x = np.pad(x, ((0, int(0.4 * sr) - len(x)), (0, 0)))
    y = lfilter(*_SHELF, x, axis=0)
    y = lfilter(*_HIGHPASS, y, axis=0)
    block, step = int(0.4 * sr), int(0.1 * sr)
    sq = np.cumsum(np.concatenate([np.zeros((1, y.shape[1])), y ** 2]), axis=0)
    starts = np.arange(0, len(y) - block + 1, step)
    z = (sq[starts + block] - sq[starts]) / block  # mean square per block and channel
    power = z.sum(axis=1)
    loud = -0.691 + 10 * np.log10(power + 1e-12)
    keep = loud > -70.0
    if not keep.any():
        return -70.0
    rel = -0.691 + 10 * np.log10(power[keep].mean()) - 10.0
    keep &= loud > rel
    if not keep.any():
        return -70.0
    return float(-0.691 + 10 * np.log10(power[keep].mean()))


def limit(x: np.ndarray, ceiling_db: float = -1.0, sr: int = SR, lookahead_s: float = 0.005) -> np.ndarray:
    """Keep every sample under the ceiling with a smooth gain (no clipping distortion)."""
    ceiling = 10 ** (ceiling_db / 20)
    peak = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    if peak.max(initial=0.0) <= ceiling:
        return x
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-9))
    win = max(1, int(lookahead_s * sr))
    # Each dip starts `win` samples early and ends `win` late, then gets smoothed: the
    # smoothed gain at a peak only averages values that are already low enough.
    gain = minimum_filter1d(need, size=2 * win + 1)
    gain = np.minimum(uniform_filter1d(gain, size=win), need)
    return x * (gain[:, None] if x.ndim == 2 else gain)


def normalize(x: np.ndarray, target_lufs: float = -14.0, ceiling_db: float = -1.0,
              sr: int = SR) -> tuple[np.ndarray, float]:
    """Gain to target loudness, then limit peaks (twice: limiting lowers loudness a bit).
    Returns (audio, measured loudness before)."""
    before = integrated_lufs(x, sr)
    if before <= -69.0:
        return x, before
    y, gain_db = x, target_lufs - before
    for _ in range(6):  # limiting lowers the loudness: add the difference again
        y = limit(x * 10 ** (gain_db / 20), ceiling_db, sr)
        cur = integrated_lufs(y, sr)
        if abs(cur - target_lufs) < 0.15:
            break
        gain_db += target_lufs - cur
    return y.astype(np.float32), before
