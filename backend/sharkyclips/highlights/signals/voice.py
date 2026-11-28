"""Voice excitement: moments that aren't kills (1.2.77, phase D8).

Competitors mostly find kills. Many of the best moments are a voice going up instead: a scream, a
sudden "WHAT?!", a long quiet stretch broken by a burst. This signal listens to the streamer's
VOICE (pitch + loudness against their own usual level), so it works for every game, Just Chatting,
IRL and study streams, with no model download and no GPU.

How
  * pitch: autocorrelation per 50 ms frame (70-700 Hz, the human voice incl. screams), on the CPU,
    streamed in 2-minute blocks (a 6 h stream stays low-memory)
  * a rolling baseline (2 minutes) of the speaker's own pitch and voice loudness, so a deep voice
    and a high voice, a quiet and a loud streamer are all measured against themselves
  * with a transcript only seconds where words are spoken count as "voice" (game music and sound
    effects are periodic too and would look like singing)

Reasons
  voice_excited   value "+5 st" = semitones above the speaker's usual pitch, louder than usual
  scream          very high and very loud, held for at least a second
  silence_break   value "12s" = a long quiet stretch (no words), then a sudden loud reaction
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d

from ... import audio as audio_mod
from .base import ReasonEvent, Signal, SignalResult, clip01, local_peaks, register

HOP_S = 0.05
FRAME = 1024  # 64 ms at 16 kHz: two periods of a 70 Hz voice
F_MIN, F_MAX = 70.0, 700.0
VOICED_R = 0.45  # normalized autocorrelation needed to call a frame "voiced"
SILENCE_DB = -50.0
BASELINE_S = 121
SPEECH_PAD_S = 3
BLOCK_S = 120.0
PITCH_UP_ST = 2.5  # semitones above usual before it counts
LOUD_UP_DB = 3.0
SCREAM_ST, SCREAM_DB = 7.0, 9.0
MAX_UP_ST = 24.0  # more than 2 octaves above the usual pitch is a tracking error (game sound), not a voice
SILENCE_MIN_S = 8.0  # a quiet stretch at least this long ...
SILENCE_MAX_S = 180.0
BREAK_JUMP_DB = 7.0  # ... broken by audio this much louder than the quiet stretch ...
BREAK_VOICE_DB = 3.0  # ... and by the streamer's voice louder than they usually talk
BREAK_PITCH_ST = 4.0  # (or clearly higher)


def frame_pitch(x: np.ndarray, sr: int = audio_mod.SAMPLE_RATE) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(pitch Hz or nan, voicing 0..1, level dB) for every 50 ms frame of x."""
    hop = int(HOP_S * sr)
    if len(x) < FRAME:
        x = np.pad(x, (0, FRAME - len(x)))
    m = 1 + (len(x) - FRAME) // hop
    idx = np.arange(FRAME)[None, :] + hop * np.arange(m)[:, None]
    frames = x[idx].astype(np.float32)
    frames -= frames.mean(axis=1, keepdims=True)
    db = 10 * np.log10(np.mean(frames ** 2, axis=1) + 1e-10)
    win = np.hanning(FRAME).astype(np.float32)
    spec = np.fft.rfft(frames * win, n=2 * FRAME, axis=1)
    ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :FRAME]
    # unbias for the window (the autocorrelation of the window itself)
    wac = np.fft.irfft(np.abs(np.fft.rfft(win, n=2 * FRAME)) ** 2)[:FRAME]
    ac = ac / np.maximum(wac, 1e-6) * wac[0]
    lo, hi = int(sr / F_MAX), int(sr / F_MIN)
    r0 = np.maximum(ac[:, 0], 1e-10)
    seg = ac[:, lo:hi + 1] / r0[:, None]
    best = seg.max(axis=1)
    # The FIRST peak close to the best one: multiples of the period score just as high (octave errors).
    peak = np.zeros_like(seg, dtype=bool)
    peak[:, 1:-1] = (seg[:, 1:-1] >= seg[:, :-2]) & (seg[:, 1:-1] >= seg[:, 2:])
    good = peak & (seg >= 0.9 * best[:, None])
    k = np.where(good.any(axis=1), np.argmax(good, axis=1), np.argmax(seg, axis=1))
    r = seg[np.arange(m), k]
    lag = (k + lo).astype(np.float64)
    # parabolic interpolation around the peak (smoother pitch)
    inner = (k > 0) & (k < seg.shape[1] - 1)
    a = np.where(inner, seg[np.arange(m), np.clip(k - 1, 0, None)], 0)
    b = np.where(inner, seg[np.arange(m), np.clip(k + 1, None, seg.shape[1] - 1)], 0)
    den = a - 2 * r + b
    lag = lag + np.where(inner & (np.abs(den) > 1e-9), 0.5 * (a - b) / np.where(den == 0, 1, den), 0)
    voiced = (r >= VOICED_R) & (db > SILENCE_DB)
    f0 = np.where(voiced, sr / np.maximum(lag, 1), np.nan)
    return f0, np.clip(r, 0, 1), db


def _rolling_nanmedian(v: np.ndarray, size: int) -> np.ndarray:
    ok = np.isfinite(v)
    if not ok.any():
        return np.full_like(v, np.nan)
    fill = float(np.nanmedian(v))
    filled = np.where(ok, v, fill)
    # median over a window where missing seconds count as "usual": robust and fast
    return median_filter(filled, size=size, mode="nearest")


@register
class VoiceSignal(Signal):
    name = "voice"
    version = 8
    cacheable = True

    def cache_key(self, ctx) -> str:
        payload = {"v": self.version, "audio": ctx.audio_fingerprint, "t": ctx.transcript_fingerprint}
        return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def compute(self, ctx) -> SignalResult:
        from ... import governor

        n = ctx.n
        per = int(round(1 / HOP_S))  # frames per second
        st = np.full(n, np.nan)  # median pitch per second, semitones re 100 Hz
        vdb = np.full(n, np.nan)  # voice level per second
        voiced_share = np.zeros(n)
        t = 0.0
        while t < ctx.duration:
            governor.gate()
            x = audio_mod.read_wav_segment(ctx.audio_path, t, t + BLOCK_S + FRAME / audio_mod.SAMPLE_RATE)
            if len(x) == 0:
                break
            f0, _r, db = frame_pitch(x)
            first = int(round(t))
            for k in range(int(BLOCK_S)):
                sec = first + k
                if sec >= n:
                    break
                fr = slice(k * per, (k + 1) * per)
                f, d = f0[fr], db[fr]
                if len(f) == 0:
                    break
                ok = np.isfinite(f)
                voiced_share[sec] = ok.mean()
                if ok.sum() >= 3:
                    st[sec] = float(np.median(12 * np.log2(f[ok] / 100.0)))
                    vdb[sec] = float(np.mean(d[ok]))
            t += BLOCK_S

        spoken = self._spoken(ctx)
        if spoken is not None:  # only the streamer's voice counts, not game music
            near = self._near_speech(spoken)
            st = np.where(near, st, np.nan)
            vdb = np.where(near, vdb, np.nan)
        base_st = _rolling_nanmedian(st, BASELINE_S)
        base_db = _rolling_nanmedian(vdb, BASELINE_S)
        up_st = np.nan_to_num(st - base_st, nan=0.0)
        up_st = np.where(up_st > MAX_UP_ST, 0.0, up_st)
        up_db = np.nan_to_num(vdb - base_db, nan=0.0)
        pitch_up = clip01((up_st - PITCH_UP_ST) / 5.0)
        loud_up = clip01((up_db - LOUD_UP_DB) / 9.0)
        # A higher voice is the excitement; louder makes it count more. Loud alone is the
        # loudness signal's job, so it adds little here.
        excited = clip01(pitch_up * (0.5 + 0.5 * loud_up) + 0.15 * loud_up * (pitch_up > 0))
        excited = uniform_filter1d(excited, 2, mode="constant")
        scream_raw = (up_st >= SCREAM_ST) & (up_db >= SCREAM_DB)
        scream_raw &= voiced_share >= 0.5
        held = scream_raw[:-1] & scream_raw[1:]  # held[i]: seconds i and i+1 both scream
        scream = np.zeros(n, dtype=bool)  # 2 s in a row: both seconds count
        scream[:-1] |= held
        scream[1:] |= held

        brk, events = self._silence_breaks(ctx, spoken, up_db, up_st)
        scream_score = scream * 1.0
        for k, w in ((1, 0.7), (2, 0.7)):  # the seconds right after a scream are the reaction to it
            scream_score[k:] = np.maximum(scream_score[k:], scream[:-k] * w)
        scores = np.maximum(np.maximum(excited, scream_score), brk)
        for i in local_peaks(excited, 0.45, 8):
            code = "scream" if scream[max(0, i - 1):i + 2].any() else "voice_excited"
            events.append(ReasonEvent(float(i), code, f"+{up_st[i]:.0f} st", float(scores[i])))
        for i in np.flatnonzero(scream):
            if not any(abs(e.t - i) < 4 for e in events if e.code == "scream"):
                events.append(ReasonEvent(float(i), "scream", f"+{up_st[i]:.0f} st", 1.0))
        events.sort(key=lambda e: e.t)
        known = np.isfinite(base_st)
        return SignalResult(self.name, scores, events, {
            "usual_pitch_hz": round(float(100 * 2 ** (np.nanmedian(base_st) / 12)), 1) if known.any() else None,
            "voiced_seconds": int(np.isfinite(st).sum()),
            "speech_gate": spoken is not None,
            "screams": sum(e.code == "scream" for e in events),
            "silence_breaks": sum(e.code == "silence_break" for e in events),
        })

    @staticmethod
    def _spoken(ctx) -> np.ndarray | None:
        if len(ctx.words) < 20:
            return None
        spoken = np.zeros(ctx.n, dtype=bool)
        for w in ctx.words:
            a, b = int(max(0, w.start)), int(min(ctx.n - 1, w.end))
            spoken[a:b + 1] = True
        return spoken

    @staticmethod
    def _near_speech(spoken: np.ndarray, pad: int = SPEECH_PAD_S) -> np.ndarray:
        """Seconds within `pad` of a spoken word: a scream or a gasp right before / after talking has
        no words (Whisper writes nothing), but it is still the streamer."""
        k = np.ones(2 * pad + 1)
        return np.convolve(spoken.astype(float), k, mode="same") > 0

    @staticmethod
    def _silence_breaks(ctx, spoken: np.ndarray | None, up_db: np.ndarray,
                        up_st: np.ndarray) -> tuple[np.ndarray, list[ReasonEvent]]:
        """A long quiet stretch (no words; without a transcript: quiet audio), then a burst.
        The tension of the silence is the setup, the burst is the payoff."""
        n = ctx.n
        out = np.zeros(n)
        events: list[ReasonEvent] = []
        db = ctx.rms_db.astype(np.float64)  # every 0.5 s
        fps = 2
        gaps: list[tuple[float, float]] = []
        if spoken is not None:
            words = ctx.words
            for i in range(1, len(words)):
                a, b = words[i - 1].end, words[i].start
                if SILENCE_MIN_S <= b - a <= SILENCE_MAX_S:
                    gaps.append((a, b))
        else:
            quiet = db < np.median(db) - 6
            i = 0
            while i < len(quiet):
                if quiet[i]:
                    j = i
                    while j < len(quiet) and quiet[j]:
                        j += 1
                    if SILENCE_MIN_S * fps <= j - i <= SILENCE_MAX_S * fps:
                        gaps.append((i / fps, j / fps))
                    i = j
                else:
                    i += 1
        for a, b in gaps:
            ga, gb = int(a * fps), int(b * fps)
            if gb - ga < 4 or gb + 1 >= len(db):
                continue
            calm = float(np.median(db[ga:gb]))
            burst = float(db[gb:min(len(db), gb + 3 * fps)].max())
            jump = burst - calm
            if jump < BREAK_JUMP_DB:
                continue
            if spoken is not None:  # the burst is the streamer: how much louder than they usually talk
                sec0 = int(b)
                win = slice(sec0, min(ctx.n, sec0 + 3))
                voice_up = float(up_db[win].max(initial=0.0))
                pitch_up = float(up_st[win].max(initial=0.0))
                if voice_up < BREAK_VOICE_DB and pitch_up < BREAK_PITCH_ST:
                    continue
                excite = max(clip01((voice_up - BREAK_VOICE_DB) / 7.0), clip01((pitch_up - BREAK_PITCH_ST) / 6.0))
                strength = float(min(1.0, (b - a) / 15.0) ** 0.5 * excite)
            else:
                strength = float(min(1.0, (b - a) / 15.0) ** 0.5 * clip01((jump - 4.0) / 10.0))
            if strength < 0.3:
                continue
            sec = int(b)
            if sec < n:
                out[sec:min(n, sec + 3)] = np.maximum(out[sec:min(n, sec + 3)], strength)
                events.append(ReasonEvent(float(b), "silence_break", f"{b - a:.0f}s", strength))
        return out, events
