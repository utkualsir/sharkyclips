"""Shared, lazily computed data that all signals can use (computed once per run)."""

from __future__ import annotations

import functools
import math
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import audio as audio_mod
from ..project import Project
from .modes import ModePreset

SENTENCE_END = tuple(".!?。！？…؟")


@dataclass
class Word:
    start: float
    end: float
    text: str  # as Whisper wrote it (may have a leading space)

    @property
    def clean(self) -> str:
        return self.text.strip()

    @property
    def ends_sentence(self) -> bool:
        return self.clean.endswith(SENTENCE_END)


class AnalysisContext:
    def __init__(self, project: Project, mode: ModePreset, settings: dict | None = None):
        self.project = project
        self.mode = mode
        self.settings = settings or {}
        self.meta = project.load_meta()
        self.audio_path: Path = project.audio_path
        with wave.open(str(self.audio_path), "rb") as w:
            self.duration = w.getnframes() / w.getframerate()
        self.n = max(1, math.ceil(self.duration))  # one score per second
        self.transcript = (project.load_transcript()
                           if project.transcript_path.is_file() else None)
        self.language = (self.transcript or {}).get("language")
        self.cache_dir = project.cache_dir / "signals"

    @property
    def audio_fingerprint(self) -> str:
        st = self.audio_path.stat()
        return f"{st.st_size}"

    @property
    def transcript_fingerprint(self) -> str:
        t = self.transcript or {}
        return f"{t.get('created_at')}|{t.get('model')}|{t.get('stats', {}).get('words')}"

    @functools.cached_property
    def words(self) -> list[Word]:
        if not self.transcript:
            return []
        out = []
        for seg in self.transcript.get("segments", []):
            for w in seg.get("words", []):
                if w["end"] >= w["start"]:
                    out.append(Word(float(w["start"]), float(w["end"]), w["word"]))
        out.sort(key=lambda w: w.start)
        return out

    @functools.cached_property
    def word_starts(self) -> np.ndarray:
        return np.array([w.start for w in self.words], dtype=np.float64)

    @functools.cached_property
    def rms_db(self) -> np.ndarray:
        """Loudness in dBFS every 0.5 s (streamed, so 6 h audio stays low-memory)."""
        hop = int(audio_mod.SAMPLE_RATE * 0.5)
        block = hop * 240  # 2 minutes per read
        out: list[np.ndarray] = []
        t = 0.0
        while t < self.duration:
            x = audio_mod.read_wav_segment(self.audio_path, t, t + block / audio_mod.SAMPLE_RATE)
            if len(x) == 0:
                break
            m = len(x) // hop
            if m:
                frames = x[: m * hop].reshape(m, hop)
                out.append(10 * np.log10(np.mean(frames ** 2, axis=1) + 1e-10))
            if len(x) % hop:
                tail = x[m * hop:]
                out.append(np.array([10 * np.log10(np.mean(tail ** 2) + 1e-10)]))
            t += block / audio_mod.SAMPLE_RATE
        db = np.concatenate(out) if out else np.zeros(1)
        return db.astype(np.float32)

    def text_between(self, start: float, end: float) -> str:
        i = int(np.searchsorted(self.word_starts, start))
        parts = []
        for w in self.words[i:]:
            if w.start >= end:
                break
            parts.append(w.text)
        return "".join(parts).strip()
