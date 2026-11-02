"""CPU engines of the voice pass (sherpa-onnx) and the small DSP helpers around them.

Everything here runs on the CPU with the governor's thread count, so Whisper can have the
GPU to itself afterwards (Whisper and the LLM never share it either).
"""

from __future__ import annotations

import numpy as np

SR = 16000


# ------------------------------------------------------------------------------- DSP

def resample(x: np.ndarray, sr_from: int, sr_to: int = SR) -> np.ndarray:
    if sr_from == sr_to or len(x) == 0:
        return x.astype(np.float32)
    from math import gcd

    from scipy.signal import resample_poly

    g = gcd(sr_from, sr_to)
    return resample_poly(x, sr_to // g, sr_from // g).astype(np.float32)


def level(x: np.ndarray, target_db: float = -20.0, max_gain_db: float = 30.0) -> np.ndarray:
    """Bring a short piece of speech to a fixed loudness (quiet voices get boosted)."""
    if len(x) == 0:
        return x.astype(np.float32)
    act = active(x)
    ref = x[act] if act.sum() > SR // 10 else x
    db = 10 * np.log10(float(np.mean(ref.astype(np.float64) ** 2)) + 1e-12)
    y = x * (10 ** (np.clip(target_db - db, -12.0, max_gain_db) / 20))
    peak = float(np.abs(y).max()) if len(y) else 0.0
    if peak > 0.98:
        y = y * (0.98 / peak)
    return y.astype(np.float32)


def frame_db(x: np.ndarray, hop: float = 0.05) -> np.ndarray:
    n = int(SR * hop)
    k = len(x) // n
    if k == 0:
        return np.zeros(0)
    return 10 * np.log10(np.mean(x[:k * n].reshape(k, n).astype(np.float64) ** 2, axis=1) + 1e-12)


def active(x: np.ndarray, hop: float = 0.05) -> np.ndarray:
    """Per-sample mask of the louder half of the signal (rough speech activity)."""
    db = frame_db(x, hop)
    if len(db) == 0:
        return np.zeros(len(x), bool)
    floor = np.percentile(db, 30)
    on = db > max(floor + 6, -55)
    mask = np.repeat(on, int(SR * hop))
    return np.pad(mask, (0, len(x) - len(mask)))


def energy_turns(x: np.ndarray, min_len: float = 0.4, gap: float = 0.5) -> list[tuple[float, float, int]]:
    """Speech-ish regions from loudness alone (when the diarization model is missing)."""
    hop = 0.05
    db = frame_db(x, hop)
    if len(db) == 0:
        return []
    floor = np.percentile(db, 25)
    on = db > max(min(floor + 8, -35), -50)  # a track that is loud all the time is all speech
    turns, start, last = [], None, None
    for i, v in enumerate(on):
        t = i * hop
        if v:
            if start is None:
                start = t
            last = t + hop
        elif start is not None and t - last > gap:
            if last - start >= min_len:
                turns.append((start, last, 0))
            start = None
    if start is not None and last - start >= min_len:
        turns.append((start, last, 0))
    return turns


# ------------------------------------------------------------------------------- engines

def _threads() -> int:
    from .. import governor

    return max(1, min(8, governor.cpu_threads(4)))


class Separator:
    """Voices out of the mix (UVR MDX-Net). Input: stereo/mono 44.1 kHz; output: 16 kHz mono."""

    def __init__(self):
        import sherpa_onnx as so

        from . import models

        self.so = so
        cfg = so.OfflineSourceSeparationConfig(model=so.OfflineSourceSeparationModelConfig(
            uvr=so.OfflineSourceSeparationUvrModelConfig(model=str(models.ensure("separator"))),
            num_threads=_threads()))
        self.engine = so.OfflineSourceSeparation(cfg)

    def __call__(self, x44: np.ndarray) -> np.ndarray:
        if x44.ndim == 1:
            x44 = np.stack([x44, x44])
        out = self.engine.process(sample_rate=44100, samples=np.ascontiguousarray(x44, dtype=np.float32))
        vocals = np.asarray(out.stems[0].data, dtype=np.float32)
        vocals = vocals.mean(axis=0) if vocals.ndim == 2 else vocals
        return resample(vocals, int(out.sample_rate), SR)


class Diarizer:
    """Who speaks when (pyannote segmentation + WeSpeaker embeddings, clustered per range)."""

    def __init__(self, threshold: float = 0.5):
        import sherpa_onnx as so

        from . import models

        t = _threads()
        cfg = so.OfflineSpeakerDiarizationConfig(
            segmentation=so.OfflineSpeakerSegmentationModelConfig(
                pyannote=so.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(models.ensure("segmentation"))),
                num_threads=t),
            embedding=so.SpeakerEmbeddingExtractorConfig(model=str(models.ensure("embedding")), num_threads=t),
            clustering=so.FastClusteringConfig(num_clusters=-1, threshold=threshold),
            min_duration_on=0.3, min_duration_off=0.5)
        self.engine = so.OfflineSpeakerDiarization(cfg)
        self.embedder = so.SpeakerEmbeddingExtractor(
            so.SpeakerEmbeddingExtractorConfig(model=str(models.ensure("embedding")), num_threads=t))

    def turns(self, x16: np.ndarray) -> list[tuple[float, float, int]]:
        res = self.engine.process(np.ascontiguousarray(x16, dtype=np.float32)).sort_by_start_time()
        return [(float(s.start), float(s.end), int(s.speaker)) for s in res]

    def embed(self, x16: np.ndarray) -> np.ndarray | None:
        if len(x16) < SR * 0.6:
            return None
        st = self.embedder.create_stream()
        st.accept_waveform(SR, np.ascontiguousarray(x16, dtype=np.float32))
        st.input_finished()
        if not self.embedder.is_ready(st):
            return None
        v = np.asarray(self.embedder.compute(st), dtype=np.float32)
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else None


# Cosine similarity of two speakers' mean fingerprints that counts as one voice. Measured on a
# 3-player Delta Force stream: fingerprints of separated voices (or clean tracks) split cleanly
# between 0.55 and 0.65; with game sound in them everything is more alike, so the bar is higher.
SAME_VOICE = 0.57
SAME_VOICE_MIX = 0.70


def cluster_speakers(units: list[tuple[object, np.ndarray, float]], threshold: float = SAME_VOICE) -> list[int]:
    """One id per voice over the whole video.

    units: (group, fingerprint, seconds) = one speaker of one clip range (the diarization's
    own clusters). Two speakers of the same range are never merged (the diarization already
    heard them as different people). Average linkage on duration-weighted mean fingerprints."""
    n = len(units)
    if n == 0:
        return []
    groups = [[i] for i in range(n)]
    vecs = [u[1] * max(0.1, float(u[2])) for u in units]

    def sim(a: list[int], b: list[int]) -> float:
        if {units[i][0] for i in a} & {units[j][0] for j in b}:
            return -2.0  # cannot-link
        va, vb = np.sum([vecs[i] for i in a], axis=0), np.sum([vecs[j] for j in b], axis=0)
        na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
        return float(va @ vb / (na * nb)) if na and nb else -2.0

    while len(groups) > 1:
        best, pair = -3.0, None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                s = sim(groups[i], groups[j])
                if s > best:
                    best, pair = s, (i, j)
        if pair is None or best < threshold:
            break
        i, j = pair
        groups[i] += groups.pop(j)
    out = [0] * n
    for gid, g in enumerate(sorted(groups, key=lambda g: min(g))):
        for i in g:
            out[i] = gid
    return out
