"""Loudness: sudden jumps above a ROLLING baseline (works for loud and quiet streamers)."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import median_filter

from .base import ReasonEvent, Signal, SignalResult, clip01, frames_to_seconds, local_peaks, register

FPS = 2  # rms_db has one value per 0.5 s
BASELINE_S = 60  # rolling median window
JUMP_LOOKBACK_S = 3
SILENCE_DB = -55.0


@register
class LoudnessSignal(Signal):
    name = "loudness"
    version = 1

    def compute(self, ctx) -> SignalResult:
        db = ctx.rms_db.astype(np.float64)
        # Baseline from frames that aren't near-silent, so pauses don't drag it down.
        voiced = np.where(db > SILENCE_DB, db, np.nan)
        fill = np.nanmedian(voiced) if np.isfinite(voiced).any() else -40.0
        baseline = median_filter(np.where(np.isfinite(voiced), voiced, fill),
                                 size=BASELINE_S * FPS + 1, mode="nearest")
        excess = db - baseline

        # Jump: now vs. the average of the previous few seconds.
        k = JUMP_LOOKBACK_S * FPS
        csum = np.concatenate([[0.0], np.cumsum(db)])
        idx = np.arange(len(db))
        a = np.maximum(0, idx - k)
        cnt = idx - a
        prev_mean = np.where(cnt > 0, (csum[idx] - csum[a]) / np.maximum(cnt, 1), db)
        jump = db - prev_mean

        frame_score = 0.6 * clip01((excess - 3.0) / 12.0) + 0.4 * clip01((jump - 4.0) / 10.0)
        frame_score[db < SILENCE_DB] = 0.0
        scores = frames_to_seconds(frame_score, FPS, ctx.n)
        excess_s = frames_to_seconds(excess, FPS, ctx.n)

        events = [ReasonEvent(float(i), "loudness_spike", f"+{excess_s[i]:.0f} dB", float(scores[i]))
                  for i in local_peaks(scores, 0.45, 5) if excess_s[i] >= 3]
        return SignalResult(self.name, scores, events,
                            {"baseline_db_median": round(float(np.median(baseline)), 1)})
