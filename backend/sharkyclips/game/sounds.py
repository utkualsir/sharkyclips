"""Find announcer lines / game sounds in the stream audio from short reference clips.

Put clips (wav/mp3/ogg/m4a, 0.5-6 s, just the sound) in
    ~/.sharkyclips/game_sounds/<game>/<event>.wav     e.g. game_sounds/lol/lol_pentakill.mp3
Several clips per event are fine: lol_pentakill 2.wav, lol_pentakill_tr.ogg ...
(<game> is "lol" or "delta_force"; <event> is any event code, see events.STRENGTH.)

Matching: log-mel spectrograms (64 bands, 32 ms hop), normalized cross-correlation of the clip
against the whole stream, computed with FFTs in 10-minute blocks. A clip matches where the
similarity is high above that clip's own typical level. Only runs when clips exist.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np

from .. import audio as audio_mod
from .. import config
from ..procs import no_window

SR = audio_mod.SAMPLE_RATE
HOP = 512  # 32 ms at 16 kHz
N_MELS = 64
EXTS = {".wav", ".mp3", ".ogg", ".m4a", ".flac", ".opus"}
DEFAULT_THRESHOLD = 0.62


def sounds_dir(game: str) -> Path:
    return config.config_dir() / "game_sounds" / game


def reference_files(game: str) -> list[Path]:
    d = sounds_dir(game)
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() in EXTS and p.is_file())


def event_code(path: Path, known: set[str]) -> str | None:
    """File name -> event code: the longest known code the name starts with
    ("lol_pentakill_tr 2.mp3" -> "lol_pentakill")."""
    stem = re.sub(r"\s+", "_", path.stem.lower())
    return next((k for k in sorted(known, key=len, reverse=True) if stem.startswith(k)), None)


def digest(game: str) -> str:
    import hashlib

    h = hashlib.sha1()
    for p in reference_files(game):
        st = p.stat()
        h.update(f"{p.name}|{st.st_size}|{int(st.st_mtime)}".encode())
    return h.hexdigest()[:10]


def _load_clip(path: Path) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, timeout=60, **no_window())
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode(errors="replace")[-200:])
    return np.frombuffer(r.stdout, np.float32)


def _features(x: np.ndarray) -> np.ndarray:
    import librosa

    m = librosa.feature.melspectrogram(y=x, sr=SR, n_fft=1024, hop_length=HOP, n_mels=N_MELS, fmin=60, fmax=7600)
    f = np.log(m + 1e-6).T.astype(np.float32)  # (frames, bands)
    return f - f.mean(axis=1, keepdims=True)  # loudness-independent shape per frame


def _ncc(feat: np.ndarray, tmpl: np.ndarray) -> np.ndarray:
    """Normalized cross-correlation of tmpl (m x B) along feat (n x B) -> (n - m + 1,)."""
    from scipy.signal import fftconvolve

    m = len(tmpl)
    n = len(feat)
    if n < m:
        return np.zeros(0)
    t = tmpl - tmpl.mean()
    num = np.zeros(n - m + 1, dtype=np.float64)
    for b in range(feat.shape[1]):
        num += fftconvolve(feat[:, b], t[::-1, b], mode="valid")
    f_mean = feat.mean()
    sq = np.concatenate([[0.0], np.cumsum(((feat - f_mean) ** 2).sum(axis=1))])
    win = sq[m:] - sq[:-m]
    return num / (np.sqrt(np.maximum(win, 1e-9)) * np.linalg.norm(t) + 1e-9)


def find(game: str, audio_path: Path, duration: float, known: set[str],
         threshold: float = DEFAULT_THRESHOLD) -> tuple[list[dict], dict]:
    """Returns (matches [{t, code, score, file}], info)."""
    refs = []
    skipped = []
    for p in reference_files(game):
        code = event_code(p, known)
        if not code:
            skipped.append(p.name)
            continue
        try:
            x = _load_clip(p)[: SR * 8]
        except Exception:
            skipped.append(p.name)
            continue
        if len(x) < SR * 0.3:
            skipped.append(p.name)
            continue
        refs.append((p.name, code, _features(x)))
    info = {"folder": str(sounds_dir(game)), "clips": [r[0] for r in refs], "ignored": skipped}
    if not refs:
        return [], info

    block = 600.0
    longest = max(len(f) for _, _, f in refs) * HOP / SR
    matches: list[dict] = []
    t = 0.0
    while t < duration:
        x = audio_mod.read_wav_segment(audio_path, t, min(duration, t + block + longest))
        if len(x) < SR:
            break
        feat = _features(x)
        for name, code, tmpl in refs:
            c = _ncc(feat, tmpl)
            if not len(c):
                continue
            from scipy.signal import find_peaks

            peaks, props = find_peaks(c, height=threshold, distance=max(1, len(tmpl)))
            for p, h in zip(peaks, props["peak_heights"]):
                at = t + p * HOP / SR
                if at < t + block or t + block >= duration:
                    matches.append({"t": round(at + len(tmpl) * HOP / SR * 0.5, 2), "code": code,
                                    "score": round(float(h), 3), "file": name})
        t += block
    matches.sort(key=lambda m: m["t"])
    # One match per event within a few seconds (several reference clips can hit the same line).
    out: list[dict] = []
    for m in matches:
        if out and out[-1]["code"] == m["code"] and m["t"] - out[-1]["t"] < 4:
            if m["score"] > out[-1]["score"]:
                out[-1] = m
            continue
        out.append(m)
    return out, info
