"""Laughter / shouting / cheering via a small, free, pretrained audio-event model.

Model: CED-mini (AudioSet, 527 sound classes, Apache-2.0), run with sherpa-onnx,
which ships prebuilt wheels for Windows, macOS (Intel + Apple Silicon) and Linux
- no PyTorch needed. The int8 model is ~10 MB and runs at a few hundred times
realtime on a CPU, so it stays on the CPU and keeps the GPU free for Whisper/LLM.

If sherpa-onnx or the model is missing, the signal is skipped (doctor says why).
"""

from __future__ import annotations

import tarfile
import urllib.request
from pathlib import Path

import numpy as np

from ... import audio as audio_mod
from ... import config
from .base import (ReasonEvent, Signal, SignalResult, SignalUnavailable, clip01, local_peaks,
                   register)

MODEL_NAME = "sherpa-onnx-ced-mini-audio-tagging-2024-04-19"
MODEL_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/"
             f"audio-tagging-models/{MODEL_NAME}.tar.bz2")
MODEL_FILES = ("model.int8.onnx", "class_labels_indices.csv")

WINDOW_S = 2.0
HOP_S = 2.0  # non-overlapping: 2 s resolution is plenty for laughter, and half the work
GROUPS = {
    "laughter": {"Laughter", "Baby laughter", "Giggle", "Snicker", "Belly laugh",
                 "Chuckle, chortle"},
    "shouting": {"Shout", "Yell", "Screaming", "Children shouting", "Battle cry", "Whoop",
                 "Bellow"},
    "cheering": {"Cheering", "Applause", "Crowd", "Clapping"},
}
GROUP_SCALE = {"laughter": 0.45, "shouting": 0.45, "cheering": 0.5}


def model_dir() -> Path:
    return config.config_dir() / "models" / "ced-mini"


def model_ready() -> bool:
    return all((model_dir() / f).is_file() for f in MODEL_FILES)


def sherpa_installed() -> bool:
    import importlib.util

    return importlib.util.find_spec("sherpa_onnx") is not None


def ensure_model(show_progress: bool = True) -> Path:
    """Download the ~47 MB archive once and keep only the two files we need."""
    d = model_dir()
    if model_ready():
        return d
    d.mkdir(parents=True, exist_ok=True)
    archive = d / "download.tar.bz2.part"
    with urllib.request.urlopen(MODEL_URL, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0) or None
        if show_progress:
            from ...ui import download_progress

            with download_progress() as prog:
                task = prog.add_task("Audio event model", total=total)
                with open(archive, "wb") as f:
                    while chunk := resp.read(1 << 20):
                        f.write(chunk)
                        prog.advance(task, len(chunk))
        else:
            with open(archive, "wb") as f:
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
    # Extract only known file names, by content: no paths from the archive are used.
    with tarfile.open(archive, "r:bz2") as tar:
        for member in tar.getmembers():
            base = member.name.rsplit("/", 1)[-1]
            if base in MODEL_FILES and member.isfile():
                src = tar.extractfile(member)
                if src is not None:
                    (d / base).write_bytes(src.read())
    archive.unlink(missing_ok=True)
    if not model_ready():
        raise RuntimeError("model archive did not contain the expected files")
    return d


@register
class LaughterSignal(Signal):
    name = "laughter"
    version = 3
    cacheable = True

    def check(self, ctx) -> None:
        if not sherpa_installed():
            raise SignalUnavailable("sherpa-onnx not installed (python -m pip install sherpa-onnx)")
        if not model_ready():
            try:
                ensure_model()
            except Exception as exc:  # offline etc.
                raise SignalUnavailable(f"audio event model could not be downloaded: {exc}")

    def cache_key(self, ctx) -> str:
        return super().cache_key(ctx) + MODEL_NAME[-10:]

    def compute(self, ctx) -> SignalResult:
        from concurrent.futures import ThreadPoolExecutor

        import psutil
        import sherpa_onnx

        d = model_dir()
        # Several single-threaded taggers working on different windows scale much better
        # than one multi-threaded tagger (measured), and leave cores free on small CPUs.
        workers = max(1, min(6, (psutil.cpu_count(logical=False) or 2) // 2))
        taggers = [sherpa_onnx.AudioTagging(sherpa_onnx.AudioTaggingConfig(
            model=sherpa_onnx.AudioTaggingModelConfig(
                ced=str(d / "model.int8.onnx"), num_threads=1, provider="cpu"),
            labels=str(d / "class_labels_indices.csv"), top_k=527)) for _ in range(workers)]

        sr = audio_mod.SAMPLE_RATE
        n = ctx.n
        win = int(WINDOW_S * sr)
        group_scores = {g: np.zeros(n) for g in GROUPS}

        def tag(worker: int, x: np.ndarray, offsets: list[int]) -> list[tuple[int, dict]]:
            tagger, out = taggers[worker], []
            for k in offsets[worker::workers]:
                seg = x[k:k + win]
                if len(seg) < sr // 2 or float(np.abs(seg).max(initial=0.0)) < 1e-3:
                    continue
                stream = tagger.create_stream()
                stream.accept_waveform(sr, seg)
                probs = {e.name: e.prob for e in tagger.compute(stream)}
                out.append((k, {g: max(probs.get(lbl, 0.0) for lbl in labels)
                                for g, labels in GROUPS.items()}))
            return out

        from ...ui import time_progress

        block_s = 600.0
        t = 0.0
        with time_progress() as prog, ThreadPoolExecutor(workers) as pool:
            task = prog.add_task("Listening for laughter", total=ctx.duration)
            while t < ctx.duration:
                x = audio_mod.read_wav_segment(ctx.audio_path, t, t + block_s)
                offsets = list(range(0, len(x), int(HOP_S * sr)))
                for part in pool.map(lambda w: tag(w, x, offsets), range(workers)):
                    for k, probs in part:
                        sec = int(t + k / sr)
                        for g, p in probs.items():
                            for s in range(sec, min(n, sec + int(WINDOW_S))):
                                group_scores[g][s] = max(group_scores[g][s], p)
                t += block_s
                prog.update(task, completed=min(t, ctx.duration))

        scaled = {g: clip01(v / GROUP_SCALE[g]) for g, v in group_scores.items()}
        scaled["cheering"] *= 0.8
        scores = np.maximum.reduce(list(scaled.values()))
        events = []
        for i in local_peaks(scores, 0.5, 4):
            g = max(scaled, key=lambda k: scaled[k][i])
            events.append(ReasonEvent(float(i), g, None, float(scores[i])))
        return SignalResult(self.name, scores, events, {
            "provider": "cpu", "workers": workers,
            "seconds_with": {g: int((v >= 0.5).sum()) for g, v in scaled.items()},
        })
