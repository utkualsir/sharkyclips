"""Music mode: find the repeated chorus (chroma self-similarity) and drops (energy rises).

The chorus is the part that repeats most AND is loud; the first strong chorus
gets a bonus, since that's usually the best clip.
"""

from __future__ import annotations

import math

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import gaussian_filter1d

from ... import audio as audio_mod
from .base import (ReasonEvent, Signal, SignalResult, SignalUnavailable, clip01, local_peaks,
                   register)

FRAMES_PER_S = 4
MAX_SSM = 2400  # cap the self-similarity matrix size (memory) for long audio
DROP_HOLD_S = 8


def _norm(x: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(x, 10), np.percentile(x, 95)
    return clip01((x - lo) / (hi - lo)) if hi > lo else np.zeros_like(x)


@register
class MusicSignal(Signal):
    name = "music"
    version = 2
    cacheable = True

    def check(self, ctx) -> None:
        import importlib.util

        if importlib.util.find_spec("librosa") is None:
            raise SignalUnavailable("librosa not installed (python -m pip install librosa)")

    def _chroma_per_second(self, ctx) -> np.ndarray:
        import librosa

        sr = audio_mod.SAMPLE_RATE
        hop = sr // FRAMES_PER_S
        cols = []
        block = 600
        for t0 in range(0, ctx.n, block):
            secs = min(block, ctx.n - t0)
            y = audio_mod.read_wav_segment(ctx.audio_path, t0, t0 + secs)
            if len(y) < sr:
                cols.append(np.zeros((12, secs)))
                continue
            c = librosa.feature.chroma_stft(y=y, sr=sr, n_fft=4096, hop_length=hop)
            need = secs * FRAMES_PER_S
            if c.shape[1] < need:
                c = np.pad(c, ((0, 0), (0, need - c.shape[1])))
            cols.append(c[:, :need].reshape(12, secs, FRAMES_PER_S).mean(axis=2))
        return np.concatenate(cols, axis=1)

    def compute(self, ctx) -> SignalResult:
        import librosa

        n = ctx.n
        chroma = self._chroma_per_second(ctx)
        r = max(1, math.ceil(n / MAX_SSM))  # seconds per SSM frame
        if r > 1:
            m = n // r
            chroma_c = chroma[:, : m * r].reshape(12, m, r).mean(axis=2)
        else:
            chroma_c = chroma
        X = librosa.feature.stack_memory(chroma_c, n_steps=4, delay=max(1, 2 // r))
        width = max(3, int(8 / r))
        if X.shape[1] > 2 * width + 2:
            R = librosa.segment.recurrence_matrix(X, mode="affinity", metric="cosine",
                                                  width=width, sym=True)
            rep = np.asarray(R.sum(axis=1)).ravel()
        else:
            rep = np.zeros(X.shape[1])
        rep = np.repeat(rep, r)[:n]
        rep = np.pad(rep, (0, n - len(rep)), mode="edge") if len(rep) < n else rep

        db = ctx.rms_db
        db_s = np.pad(db, (0, max(0, 2 * n - len(db))), mode="edge")[: 2 * n].reshape(n, 2).mean(axis=1)
        energy = gaussian_filter1d(_norm(db_s), 2)
        chorus = gaussian_filter1d(_norm(rep), 3) * (0.4 + 0.6 * energy)

        # Drop: next 4 s much louder than previous 6 s.
        csum = np.concatenate([[0.0], np.cumsum(db_s)])
        idx = np.arange(n)
        nxt = (csum[np.minimum(n, idx + 4)] - csum[idx]) / np.maximum(1, np.minimum(n, idx + 4) - idx)
        a = np.maximum(0, idx - 6)
        prv = (csum[idx] - csum[a]) / np.maximum(1, idx - a)
        rise = np.where(idx >= 6, nxt - prv, 0.0)
        drop_hit = gaussian_filter1d(clip01((rise - 3.0) / 9.0), 1)
        # The payoff is the section AFTER the drop: hold the score for 8 s so the
        # hype curve's smoothing doesn't flatten a 2 s spike.
        drop = sliding_window_view(np.pad(drop_hit, (DROP_HOLD_S - 1, 0)), DROP_HOLD_S).max(axis=1)

        events: list[ReasonEvent] = []
        peaks = local_peaks(chorus, 0.5, 20)
        strong = [p for p in peaks if chorus[p] >= 0.75 * chorus.max()] if len(peaks) else []
        bonus = np.zeros(n)
        first = int(strong[0]) if strong else None
        if first is not None:
            bonus = 0.2 * np.exp(-((idx - first) / 8.0) ** 2)
        for p in peaks:
            events.append(ReasonEvent(float(p), "chorus", "first" if p == first else None,
                                      float(chorus[p])))
        for p in local_peaks(drop_hit, 0.5, 15):
            events.append(ReasonEvent(float(p), "drop", f"+{rise[p]:.0f} dB", float(drop[p])))

        scores = clip01(np.maximum(chorus + bonus, 0.85 * drop))
        return SignalResult(self.name, scores, events,
                            {"first_chorus_at": first, "ssm_resolution_s": r})
