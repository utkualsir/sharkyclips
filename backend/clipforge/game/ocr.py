"""Text reading for HUD crops: PaddleOCR's PP-OCR models run with onnxruntime (RapidOCR).

Why this one: no PyTorch / PaddlePaddle install (EasyOCR pulls in ~2.5 GB of PyTorch), the
models are ~15 MB and ship inside the pip package, and the multilingual recognizer reads both
English and Turkish game clients. It runs on the CPU, so it never competes with Whisper or the
LLM for GPU memory.

Speed (measured, one CPU thread pool): reading one known text line ~40 ms; finding + reading
text in a larger area ~0.3-0.5 s. The scanner therefore reads lines at fixed positions and only
looks for text in big areas when something actually changed there.
"""

from __future__ import annotations

import importlib.util
import logging
import time

import numpy as np


def installed() -> bool:
    return importlib.util.find_spec("rapidocr") is not None


class Reader:
    """One OCR engine (not shared between threads)."""

    def __init__(self, threads: int = 2):
        from rapidocr import RapidOCR

        logging.getLogger("RapidOCR").setLevel(logging.ERROR)
        self.engine = RapidOCR(params={
            "Global.log_level": "error",
            "Det.limit_side_len": 480, "Det.limit_type": "max",
            "EngineConfig.onnxruntime.intra_op_num_threads": threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        })
        self.calls = 0
        self.seconds = 0.0

    @staticmethod
    def _rgb(img: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(np.dstack([img] * 3) if img.ndim == 2 else img)

    def line(self, img: np.ndarray) -> tuple[str, float]:
        """Read one line of text that fills the crop (no text detection)."""
        self.calls += 1
        t0 = time.perf_counter()
        r = self.engine(self._rgb(img), use_det=False, use_cls=False, use_rec=True)
        self.seconds += time.perf_counter() - t0
        txts = list(r.txts or [])
        scores = list(r.scores or [])
        return (txts[0], float(scores[0])) if txts else ("", 0.0)

    def area(self, img: np.ndarray, min_score: float = 0.5) -> list[str]:
        """Find and read all text lines in a larger crop, top to bottom."""
        self.calls += 1
        t0 = time.perf_counter()
        r = self.engine(self._rgb(img), use_det=True, use_cls=False, use_rec=True)
        self.seconds += time.perf_counter() - t0
        if not r.txts:
            return []
        items = [(float(b[0][1]), t) for b, t, s in zip(r.boxes, r.txts, r.scores) if s >= min_score]
        return [t for _, t in sorted(items)]

    def close(self) -> None:
        self.engine = None


# ------------------------------------------------------------------ process pool
# RapidOCR does much of its work in Python (pre/post-processing), so OCR in threads of one
# process fights for the GIL with the frame decoding (measured: a 50 ms line read took 350 ms
# during a scan). A few worker processes, each with its own engine, avoid that.

_worker: Reader | None = None


def _init_worker(threads: int) -> None:
    global _worker
    _worker = Reader(threads=threads)


def _work(kind: str, img: np.ndarray, min_score: float):
    if kind == "line":
        return _worker.line(img)
    return _worker.area(img, min_score)


class PoolReader:
    """Same interface as Reader; safe to share between threads."""

    def __init__(self, processes: int = 4, threads: int = 2):
        import threading
        from concurrent.futures import ProcessPoolExecutor

        self.pool = ProcessPoolExecutor(processes, initializer=_init_worker, initargs=(threads,))
        self._lock = threading.Lock()
        self.calls = 0
        self.seconds = 0.0

    def _run(self, kind: str, img: np.ndarray, min_score: float = 0.5):
        t0 = time.perf_counter()
        out = self.pool.submit(_work, kind, np.ascontiguousarray(img), min_score).result()
        with self._lock:
            self.calls += 1
            self.seconds += time.perf_counter() - t0
        return out

    def line(self, img: np.ndarray) -> tuple[str, float]:
        return self._run("line", img)

    def area(self, img: np.ndarray, min_score: float = 0.5) -> list[str]:
        return self._run("area", img, min_score)

    def close(self) -> None:
        self.pool.shutdown(wait=True, cancel_futures=True)
