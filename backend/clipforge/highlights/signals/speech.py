"""Speech signals from WORD timestamps.

speech        -> excitement: words-per-second spikes and "pause, then burst"
                 (setup -> punchline)
steady_speech -> study mode: continuous, calm, normal-paced explanation
"""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import gaussian_filter1d, uniform_filter1d

from .base import (ReasonEvent, Signal, SignalResult, SignalUnavailable, clip01, local_peaks,
                   register)

BASELINE_S = 61


def words_per_second(ctx) -> np.ndarray:
    counts = np.zeros(ctx.n)
    for w in ctx.words:
        i = int((w.start + w.end) / 2)
        if 0 <= i < ctx.n:
            counts[i] += 1
    return counts


def rolling_speaking_median(rate: np.ndarray, speaking: np.ndarray) -> np.ndarray:
    """Median speaking rate over a 60 s window, ignoring silent seconds."""
    vals = np.where(speaking, rate, np.nan)
    glob = np.nanmedian(vals) if speaking.any() else 2.5
    half = BASELINE_S // 2
    padded = np.pad(vals, half, constant_values=np.nan)
    win = sliding_window_view(padded, BASELINE_S)
    with np.errstate(all="ignore"):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(win, axis=1)
    med = np.where(np.isfinite(med), med, glob)
    # Don't let a few words make a near-zero baseline.
    return np.maximum(med, max(1.0, 0.6 * glob))


class _WordSignal(Signal):
    def check(self, ctx) -> None:
        if len(ctx.words) < 20:
            raise SignalUnavailable("no transcript with word timestamps (run transcribe first)")


@register
class SpeechSignal(_WordSignal):
    name = "speech"
    version = 1

    def compute(self, ctx) -> SignalResult:
        wps = uniform_filter1d(words_per_second(ctx), 3, mode="constant")
        speaking = wps > 0.4
        base = rolling_speaking_median(wps, speaking)
        ratio = wps / base
        fast = clip01((ratio - 1.3) / 0.9) * (wps >= 2.0)

        burst = np.zeros(ctx.n)
        events: list[ReasonEvent] = []
        words = ctx.words
        starts = ctx.word_starts
        for i in range(1, len(words)):
            gap = words[i].start - words[i - 1].end
            if not 1.2 <= gap <= 8.0:
                continue
            t = words[i].start
            n_after = int(np.searchsorted(starts, t + 2.0) - i)
            rate = n_after / 2.0
            sec = int(t)
            if sec >= ctx.n or rate < 1.3 * base[sec] or n_after < 4:
                continue
            strength = float(min(1.0, gap / 3.0) * min(1.0, rate / (1.6 * base[sec])))
            burst[sec:min(ctx.n, sec + 3)] = np.maximum(burst[sec:min(ctx.n, sec + 3)], strength)
            if strength >= 0.4:
                events.append(ReasonEvent(t, "pause_then_burst", f"{gap:.1f}s", strength))

        scores = np.maximum(fast, burst)
        for i in local_peaks(fast, 0.4, 10):
            events.append(ReasonEvent(float(i), "fast_speech", f"x{ratio[i]:.1f}", float(fast[i])))
        return SignalResult(self.name, scores, events,
                            {"median_wps": round(float(np.median(base)), 2)})


@register
class SteadySpeechSignal(_WordSignal):
    name = "steady_speech"
    version = 1

    def compute(self, ctx) -> SignalResult:
        wps = uniform_filter1d(words_per_second(ctx), 3, mode="constant")
        speaking = wps > 0.4
        base = rolling_speaking_median(wps, speaking)
        coverage = uniform_filter1d(speaking.astype(float), 20, mode="constant")
        closeness = np.exp(-(((wps / base) - 1.0) / 0.35) ** 2)
        closeness = gaussian_filter1d(closeness, 3)
        scores = clip01(gaussian_filter1d(coverage * closeness, 4))
        events = [ReasonEvent(float(i), "steady_explanation", None, float(scores[i]))
                  for i in local_peaks(scores, 0.6, 30)]
        return SignalResult(self.name, scores, events)
