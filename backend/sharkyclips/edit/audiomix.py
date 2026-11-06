"""The finished clip's sound, built in numpy (48 kHz stereo) and handed to ffmpeg as a WAV.

  [intro card] [hook flash] [main part with cuts] [outro card]

- cuts: equal-power crossfades (40 ms). Each side of a join borrows 20 ms from the cut
  part, so the sound stays exactly as long as the picture (frame-accurate cut points).
- swear words: a bleep (classic 1 kHz, soft boop or your own sound) 3 dB under the voice,
  or silence (mute), with 12 ms fades.
- music: starts at the song's strongest part, ducks under speech (word timestamps,
  smooth attack / release) and comes back in pauses, fades out at the end. With music
  the whole mix is normalized to -14 LUFS with peaks under -1 dBFS.
- seamless loop (loop.py): no fades at the edges; what the source says right after the end
  point is crossfaded under the first samples, the end is gained toward the opening's level,
  the music bed loops the same way and ducks as if the clip repeated.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import governor
from . import loop as loop_mod
from . import loudness
from .music import decode
from .plan import EditPlan

SR = 48000
XFADE = 0.04
BLEEP_HZ = 1000.0
MUSIC_UNDER_SPEECH_DB = -20.0  # music level under speech, relative to the clip's speech loudness
MUSIC_IN_PAUSES_DB = -9.0
TARGET_LUFS = -14.0
MUSIC_LOOP_XFADE = 0.3


@dataclass
class MixResult:
    path: Path
    seconds: float
    lufs: float | None
    music: dict | None
    seam: dict | None = None  # seamless loop: the seam measured on the finished mix


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


BLEEP_FADE = 0.012
BLEEP_SOUNDS = ("classic", "boop", "custom")


def custom_bleep_path() -> Path:
    from .. import config

    return config.config_dir() / "bleep" / "custom.wav"


def _bleep_tone(n: int, sound: str, custom: np.ndarray | None) -> np.ndarray:
    """A unit-RMS bleep of n samples (mono)."""
    tt = np.arange(n, dtype=np.float32) / SR
    if sound == "custom" and custom is not None and len(custom) > SR // 50:
        reps = int(np.ceil(n / len(custom)))
        tone = np.tile(custom, reps)[:n].astype(np.float32)
    elif sound == "boop":
        # A soft "boop": a low sine gliding down a little, with a warm second harmonic.
        f = 520.0 - 140.0 * np.minimum(1.0, tt / max(0.12, n / SR))
        phase = 2 * np.pi * np.cumsum(f) / SR
        tone = (np.sin(phase) + 0.25 * np.sin(2 * phase)).astype(np.float32)
    else:
        tone = np.sin(2 * np.pi * BLEEP_HZ * tt).astype(np.float32)
    rms = float(np.sqrt(np.mean(tone ** 2) + 1e-12))
    return tone / rms


def _voice_rms(y: np.ndarray, ia: int, ib: int) -> float:
    """How loud the speaker is: the swear itself, or the speech around it when that's louder."""
    seg = y[ia:ib]
    own = float(np.sqrt(np.mean(seg ** 2) + 1e-12))
    ctx = y[max(0, ia - _n(0.6)):min(len(y), ib + _n(0.6))]
    if len(ctx) > _n(0.05):
        hop = _n(0.05)
        k = len(ctx) // hop
        fr = np.sqrt(np.mean(ctx[:k * hop].reshape(k, hop, -1) ** 2, axis=(1, 2)))
        own = max(own, float(np.percentile(fr, 75)) * 0.9)
    return own


def apply_bleeps(y: np.ndarray, ranges: list[tuple[float, float]], mode: str, sound: str = "classic",
                 custom: np.ndarray | None = None) -> np.ndarray:
    """Bleep (or mute) the ranges with short fades. The bleep's loudness follows the voice
    (3 dB under it) so it never jumps out of a quiet clip or drowns in a loud one."""
    if mode not in ("bleep", "mute"):
        return y
    fade = _n(BLEEP_FADE)
    for a, b in ranges:
        ia, ib = max(0, _n(a)), min(len(y), _n(b))
        if ib - ia < 2:
            continue
        seg = y[ia:ib]
        env = np.ones(ib - ia, np.float32)
        r = min(fade, (ib - ia) // 2)
        if r:
            cos = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, r))).astype(np.float32)
            env[:r] = cos
            env[-r:] = cos[::-1]
        if mode == "mute":
            y[ia:ib] = seg * (1 - env)[:, None]
            continue
        target = min(0.25, max(0.02, _voice_rms(y, ia, ib) * 0.71))
        tone = _bleep_tone(ib - ia, sound, custom) * target
        y[ia:ib] = seg * (1 - env)[:, None] + (tone * env)[:, None]
    return y


def load_custom_bleep() -> np.ndarray | None:
    p = custom_bleep_path()
    if not p.is_file():
        return None
    try:
        x = decode(p, 0.0, 3.0, sr=SR, channels=1)
        return x[:, 0] if x.ndim == 2 else x
    except Exception:  # noqa: BLE001
        return None


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


def music_bed(path: Path, best_start: float | None, duration: float | None, total: float,
              looped: bool = False) -> tuple[np.ndarray, float]:
    """The song from its strongest part (earlier if what's left is too short), faded.
    looped: no fades; the song's continuation past the end is crossfaded under its start."""
    dur = float(duration or 0)
    off = float(best_start or 0)
    extra = MUSIC_LOOP_XFADE if looped else 0.0
    if dur and dur - off < total + extra:
        off = max(0.0, dur - total - extra)
    y = decode(path, off, total + extra + 0.1, sr=SR, channels=2)
    if len(y) < _n(total + extra):
        y = np.concatenate([y, np.zeros((_n(total + extra) - len(y), 2), np.float32)])
    if looped:
        cont = y[_n(total): _n(total + extra)]
        y = loop_mod.crossfade_head(y[: _n(total)].copy(), cont, extra, SR)
        return y, off
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
    dec = decode
    if plan.dub is not None:  # 1.2.18: the dubbed sound stands in for the source's sound
        from .. import dub as dub_mod

        info = plan.dub

        def dec(path, start=0.0, duration=None, sr=SR, channels=1):
            if Path(path) == Path(source):
                return dub_mod.decode_track(info, Path(source), start, duration, sr, channels)
            return decode(path, start, duration, sr=sr, channels=channels)
    seam = plan.loop
    cont = None
    if has_audio:
        t0 = max(0.0, plan.start - 0.1)
        after = (seam.audio_xfade + 0.05) if seam is not None else 0.1
        src = dec(source, t0, plan.end - t0 + max(0.1, after), sr=SR, channels=2)
        main = cut_and_join(src, t0, plan)
        if seam is not None and seam.tail_ok:  # the sound right after the end point
            b = _n(plan.start - t0 + plan.frames()[-1][1] / plan.fps)
            cont = src[b: b + _n(seam.audio_xfade)]
    else:
        main = np.zeros((_n(plan.out_duration), 2), np.float32)
    main = apply_bleeps(main, plan.bleeps, plan.bleep_mode, plan.bleep_sound,
                         load_custom_bleep() if plan.bleep_sound == "custom" else None)
    if seam is not None:
        main, end_gain = loop_mod.meet_levels(main, SR)
        if cont is not None and end_gain:
            cont = cont * np.float32(10 ** (end_gain / 20))  # it continues the (re-leveled) end
        main = loop_mod.crossfade_head(main, cont, seam.audio_xfade, SR)
    else:
        main = _fade(main, 0.12, 0.2)
    speech_ref = loudness.integrated_lufs(main)
    fxp = plan.fx
    if fxp is not None and (fxp.inserts or fxp.sfx):
        from . import fx as fx_mod

        main = fx_mod.splice_audio(main, fxp, source, SR, has_audio, dec)
    governor.checkpoint()

    parts = [np.zeros((_n(plan.intro_s), 2), np.float32)]
    lead = plan.intro_s
    if flash:
        fs, fd = flash
        fl = dec(source, fs, fd, sr=SR, channels=2) if has_audio else np.zeros((_n(fd), 2), np.float32)
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
        bed, off = music_bed(mpath, plan.music.get("best_start"), plan.music.get("duration"), total,
                             looped=seam is not None)
        governor.checkpoint()
        m_lufs = loudness.integrated_lufs(bed)
        ref = speech_ref if speech_ref > -60 else -20.0
        gain = 10 ** ((ref + MUSIC_IN_PAUSES_DB - m_lufs) / 20) if m_lufs > -69 else 0.0
        speech = [(a + lead, b + lead) for a, b in plan.speech_out()]
        if fxp is not None:
            speech = [(fxp.final(a - lead) + lead, fxp.final(b - lead, end=True) + lead) for a, b in speech]
        duck = MUSIC_UNDER_SPEECH_DB - MUSIC_IN_PAUSES_DB
        if seam is not None:  # duck as if the clip repeated: the end already dips for the opening
            n = len(bed)
            env = duck_envelope(3 * n, [(a + total, b + total) for a, b in loop_mod.periodic(speech, total)],
                                duck)[n: 2 * n]
        else:
            env = duck_envelope(len(bed), speech, duck)
        mix = mix + bed * (gain * env)[:, None]
        music_info = {**plan.music, "offset": round(off, 2)}
        mix, _before = loudness.normalize(mix, TARGET_LUFS)
        lufs = round(loudness.integrated_lufs(mix), 1)
    else:
        mix = loudness.limit(mix, -1.0)
    governor.checkpoint()
    write_wav(dest, mix)
    seam_m = loop_mod.measure_audio(np.clip(mix, -1.0, 1.0), SR) if seam is not None and len(mix) >= SR else None
    return MixResult(dest, total, lufs, music_info, seam_m)
