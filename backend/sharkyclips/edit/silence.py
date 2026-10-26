"""Quiet gaps inside a clip (from the project's 16 kHz audio.wav).

A gap counts as silence only when nobody speaks (no transcript word) AND the audio is
really quiet: game sounds, music or shouting in a pause are never "silence". "Quiet" is
relative to the clip's own level, so a loud stream and a soft one behave the same.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import audio as audio_mod

FRAME_S = 0.02


def frame_db(path: Path, start: float, end: float) -> np.ndarray:
    """Loudness in dBFS per 20 ms frame of [start, end]."""
    y = audio_mod.read_wav_segment(path, start, end)
    hop = int(audio_mod.SAMPLE_RATE * FRAME_S)
    n = len(y) // hop
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    rms = np.sqrt(np.mean(y[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    return (20 * np.log10(rms + 1e-9)).astype(np.float32)


def quiet_threshold(db: np.ndarray) -> float:
    """dBFS below which a frame is quiet: 26 dB under the clip's loud parts, within -58..-34."""
    if len(db) == 0:
        return -45.0
    loud = float(np.percentile(db, 90))
    return float(min(-34.0, max(-58.0, loud - 26.0)))


def find_silences(db: np.ndarray, words: list[tuple[float, float]], min_s: float,
                  start: float = 0.0) -> list[tuple[float, float]]:
    """Quiet stretches of at least min_s seconds without words. db: frames from `start`;
    words: (start, end) in the same absolute time. Returns absolute (a, b)."""
    if len(db) == 0:
        return []
    quiet = db < quiet_threshold(db)
    for ws, we in words:  # speech is never silence (Whisper's word edges are a bit tight)
        a = max(0, int((ws - 0.08 - start) / FRAME_S))
        b = min(len(quiet), int(np.ceil((we + 0.08 - start) / FRAME_S)))
        quiet[a:b] = False
    out = []
    i = 0
    n = len(quiet)
    while i < n:
        if not quiet[i]:
            i += 1
            continue
        j = i
        while j < n and quiet[j]:
            j += 1
        if (j - i) * FRAME_S >= min_s:
            out.append((start + i * FRAME_S, start + j * FRAME_S))
        i = j
    return out
