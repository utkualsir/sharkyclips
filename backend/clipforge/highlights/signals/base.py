"""Signal interface.

A signal looks at a project and returns one score per second (0..1) plus
"reason events" that explain its peaks. The scorer combines signals with
per-mode weights, so adding a signal (e.g. chat activity or a local LLM in
Phase 3) means: write a subclass, decorate it with @register, give it a weight
in modes.py. Nothing else changes.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from ..context import AnalysisContext


@dataclass
class ReasonEvent:
    """Why a moment is interesting. `code` is stable and translated by the UI."""

    t: float  # seconds from the start of the video
    code: str  # e.g. "loudness_spike", "keyword", "laughter"
    value: str | None = None  # e.g. "+14 dB", "nasıl ya"
    strength: float = 1.0  # 0..1

    def to_dict(self) -> dict:
        d = {"code": self.code}
        if self.value is not None:
            d["value"] = self.value
        d["t"] = round(self.t, 2)
        d["strength"] = round(float(self.strength), 3)
        return d


@dataclass
class SignalResult:
    name: str
    scores: np.ndarray  # shape (n_seconds,), values 0..1
    events: list[ReasonEvent] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class SignalUnavailable(Exception):
    """Raised by a signal that can't run here (missing package, no transcript...).
    The scorer skips it and re-normalizes the other weights."""


class Signal(ABC):
    name: str = ""
    version: int = 1  # bump to invalidate cached results
    cacheable: bool = False  # cache results on disk (for expensive signals)

    def check(self, ctx: AnalysisContext) -> None:
        """Raise SignalUnavailable if this signal can't run. Default: always available."""

    @abstractmethod
    def compute(self, ctx: AnalysisContext) -> SignalResult: ...

    def cache_key(self, ctx: AnalysisContext) -> str:
        """Inputs that change the result. Override to add more."""
        payload = {"v": self.version, "audio": ctx.audio_fingerprint}
        return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    # ---------------------------------------------------------------- caching

    def run(self, ctx: AnalysisContext) -> SignalResult:
        self.check(ctx)
        if not self.cacheable:
            return self.compute(ctx)
        cache = ctx.cache_dir / f"{self.name}.npz"
        key = self.cache_key(ctx)
        if cache.is_file():
            try:
                # `with`: NpzFile keeps the file open, which blocks replacing it on Windows.
                with np.load(cache, allow_pickle=False) as data:
                    if str(data["key"]) == key and len(data["scores"]) == ctx.n:
                        scores = np.array(data["scores"])
                        events = [ReasonEvent(**e) for e in json.loads(str(data["events"]))]
                        meta = json.loads(str(data["meta"]))
                        return SignalResult(self.name, scores, events, meta | {"cached": True})
            except Exception:
                pass
        res = self.compute(ctx)
        ctx.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_name(cache.stem + ".tmp.npz")
        np.savez_compressed(tmp, key=key, scores=res.scores.astype(np.float32),
                            events=json.dumps([asdict(e) for e in res.events]),
                            meta=json.dumps(res.meta))
        tmp.replace(cache)
        return res


# ---------------------------------------------------------------- registry

REGISTRY: dict[str, type[Signal]] = {}


def register(cls: type[Signal]) -> type[Signal]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} needs a name")
    REGISTRY[cls.name] = cls
    return cls


# ---------------------------------------------------------------- helpers


def clip01(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 0.0, 1.0)


def frames_to_seconds(frames: np.ndarray, frames_per_second: int, n: int) -> np.ndarray:
    """Max-pool a finer frame array into one value per second (length n)."""
    need = n * frames_per_second
    if len(frames) < need:
        frames = np.pad(frames, (0, need - len(frames)))
    return frames[:need].reshape(n, frames_per_second).max(axis=1)


def local_peaks(scores: np.ndarray, threshold: float, distance: int) -> np.ndarray:
    """Indices of local maxima above threshold, at least `distance` seconds apart."""
    from scipy.signal import find_peaks

    if len(scores) == 0:
        return np.zeros(0, dtype=int)
    peaks, _ = find_peaks(np.concatenate([[0.0], scores, [0.0]]), height=threshold,
                          distance=max(1, distance))
    return peaks - 1
