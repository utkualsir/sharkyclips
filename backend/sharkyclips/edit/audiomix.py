"""The finished clip's sound, built in numpy (48 kHz stereo) and handed to ffmpeg as a WAV.

  [intro card] [hook flash] [main part with cuts] [outro card]

- cuts: equal-power crossfades (40 ms). Each side of a join borrows 20 ms from the cut
  part, so the sound stays exactly as long as the picture (frame-accurate cut points).
- swear words: a 1 kHz bleep at the speech's level, or silence (mute).
- music: starts at the song's strongest part, ducks under speech (word timestamps,
  smooth attack / release) and comes back in pauses, fades out at the end. With music
  the whole mix is normalized to -14 LUFS with peaks under -1 dBFS.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import governor
from . import loudness
from .music import decode
from .plan import EditPlan

SR = 48000
XFADE = 0.04
BLEEP_HZ = 1000.0
MUSIC_UNDER_SPEECH_DB = -20.0  # music level under speech, relative to the clip's speech loudness
MUSIC_IN_PAUSES_DB = -9.0
TARGET_LUFS = -14.0


@dataclass
class MixResult:
    path: Path
    seconds: float
    lufs: float | None
    music: dict | None


def _n(t: float) -> int:
    return int(round(t * SR))


def _ramp(n: int) -> np.ndarray:
    return np.linspace(0.0, 1.0, max(1, n), dtype=np.float32)


def _fade(y: np.ndarray, fade_in: float, fade_out: float) -> np.ndarray:
    n = len(y)
    a, b = min(n, _n(fade_in)), min(n, _n(fade_out))
    if a:
        y[:a] *= _ramp(a)[:, None]
    if b:
        y[n - b:] *= _ramp(b)[::-1][:, None]
    return y


def cut_and_join(audio: np.ndarray, t0: float, plan: EditPlan) -> np.ndarray:
    """audio: samples from source time t0. Returns the main part (kept ranges, crossfaded)."""
    frames = plan.frames()
    h = _n(XFADE / 2)
    parts = []
    for k, (fa, fb) in enumerate(frames):
        a = _n(plan.start - t0 + fa / plan.fps)
        b = _n(plan.start - t0 + fb / plan.fps)
        left = h if k > 0 else 0
        right = h if k < len(frames) - 1 else 0
        seg = audio[max(0, a - left): b + right]
        want = (b - a) + left + right
        if len(seg) < want:  # end of the source: pad with silence
            seg = np.concatenate([seg, np.zeros((want - len(seg), audio.shape[1]), np.float32)])
        parts.append(seg.astype(np.float32, copy=True))
    out = parts[0]
    n = 2 * h
    if n:
        theta = np.linspace(0, np.pi / 2, n, dtype=np.float32)[:, None]
        fin, fout = np.sin(theta), np.cos(theta)
    for seg in parts[1:]:
        if n == 0:
            out = np.concatenate([out, seg])
            continue
        mixed = out[-n:] * fout + seg[:n] * fin
        out = np.concatenate([out[:-n], mixed, seg[n:]])
    return out


def apply_bleeps(y: np.ndarray, ranges: list[tuple[float, float]], mode: str) -> np.ndarray:
    if mode not in ("bleep", "mute"):
        return y
    ramp = _n(0.006)
    for a, b in ranges:
        ia, ib = max(0, _n(a)), min(len(y), _n(b))
        if ib - ia < 2:
            continue
        seg = y[ia:ib]
        env = np.ones(ib - ia, np.float32)
        r = min(ramp, (ib - ia) // 2)
        if r:
            env[:r] = _ramp(r)
            env[-r:] = _ramp(r)[::-1]
        if mode == "mute":
            y[ia:ib] = seg * (1 - env)[:, None]
            continue
        rms = float(np.sqrt(np.mean(seg ** 2) + 1e-12))
        amp = min(0.32, max(0.06, rms * 1.6))
        tt = np.arange(ib - ia, dtype=np.float32) / SR
        tone = (amp * np.sin(2 * np.pi * BLEEP_HZ * tt)).astype(np.float32)
        y[ia:ib] = seg * (1 - env)[:, None] + (tone * env)[:, None]
    return y


def duck_envelope(n: int, speech: list[tuple[float, float]], duck_db: float,
                  attack: float = 0.12, release: float = 0.4) -> np.ndarray:
    """Gain per sample: 1 in pauses, 10^(duck_db/20) under speech, smooth in between."""
    step = 0.01
    m = int(np.ceil(n / SR / step)) + 1
    target = np.ones(m, np.float32)
    low = 10 ** (duck_db / 20)
    for a, b in speech:
        target[max(0, int(a / step)): max(0, int(np.ceil(b / step)))] = low
    env = np.empty_like(target)
    g = 1.0
    ka, kr = 1 - np.exp(-step / attack), 1 - np.exp(-step / release)
    for i, v in enumerate(target):  # one-pole: fast down (attack), slow up (release)
        g += (v - g) * (ka if v < g else kr)
        env[i] = g
    # Look ahead by the attack time so the music is already down when the first word starts.
    shift = int(attack / step)
    env = np.concatenate([env[shift:], np.full(shift, env[-1], np.float32)])
    return np.interp(np.arange(n) / SR, np.arange(m) * step, env).astype(np.float32)


def music_bed(path: Path, best_start: float | None, duration: float | None, total: float) -> tuple[np.ndarray, float]:
    """The song from its strongest part (earlier if what's left is too short), faded."""
    dur = float(duration or 0)
    off = float(best_start or 0)
    if dur and dur - off < total:
        off = max(0.0, dur - total)
    y = decode(path, off, total + 0.1, sr=SR, channels=2)
    if len(y) < _n(total):
        y = np.concatenate([y, np.zeros((_n(total) - len(y), 2), np.float32)])
    y = y[: _n(total)]
    fade_out = min(2.0, max(0.6, total * 0.12))
    return _fade(y, 0.3, fade_out), off


def write_wav(path: Path, y: np.ndarray) -> None:
    pcm = (np.clip(y, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build(source: Path, plan: EditPlan, dest: Path, *, has_audio: bool = True,
          flash: tuple[float, float] | None = None) -> MixResult:
    """Write the clip's full sound track to `dest` (WAV). flash: (source start, seconds)."""
    from .music import path_of

    governor.checkpoint()
    if has_audio:
        t0 = max(0.0, plan.start - 0.1)
        src = decode(source, t0, plan.end - t0 + 0.1, sr=SR, channels=2)
        main = cut_and_join(src, t0, plan)
    else:
        main = np.zeros((_n(plan.out_duration), 2), np.float32)
    main = apply_bleeps(main, plan.bleeps, plan.bleep_mode)
    main = _fade(main, 0.12, 0.2)
    speech_ref = loudness.integrated_lufs(main)
    governor.checkpoint()

    parts = [np.zeros((_n(plan.intro_s), 2), np.float32)]
    lead = plan.intro_s
    if flash:
        fs, fd = flash
        fl = decode(source, fs, fd, sr=SR, channels=2) if has_audio else np.zeros((_n(fd), 2), np.float32)
        fl = np.concatenate([fl, np.zeros((max(0, _n(fd) - len(fl)), 2), np.float32)])[: _n(fd)]
        parts.append(_fade(fl, 0.05, 0.12))
        lead += fd
    parts += [main, np.zeros((_n(plan.outro_s), 2), np.float32)]
    mix = np.concatenate(parts)
    total = len(mix) / SR

    music_info = None
    lufs = None
    mpath = path_of(plan.music["name"]) if plan.music else None
    if mpath is not None:
        bed, off = music_bed(mpath, plan.music.get("best_start"), plan.music.get("duration"), total)
        governor.checkpoint()
        m_lufs = loudness.integrated_lufs(bed)
        ref = speech_ref if speech_ref > -60 else -20.0
        gain = 10 ** ((ref + MUSIC_IN_PAUSES_DB - m_lufs) / 20) if m_lufs > -69 else 0.0
        speech = [(a + lead, b + lead) for a, b in plan.speech_out()]
        env = duck_envelope(len(bed), speech, MUSIC_UNDER_SPEECH_DB - MUSIC_IN_PAUSES_DB)
        mix = mix + bed * (gain * env)[:, None]
        music_info = {**plan.music, "offset": round(off, 2)}
        mix, _before = loudness.normalize(mix, TARGET_LUFS)
        lufs = round(loudness.integrated_lufs(mix), 1)
    else:
        mix = loudness.limit(mix, -1.0)
    governor.checkpoint()
    write_wav(dest, mix)
    return MixResult(dest, total, lufs, music_info)
