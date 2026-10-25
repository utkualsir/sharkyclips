"""Fast frame sampling for HUD reading.

ffmpeg decodes only reference frames (-skip_frame noref: we need 2 frames per second, not 60),
on the GPU when there is one (NVDEC), and hands over raw NV12 frames: the Y plane is a free
grayscale image and the small UV planes give colour saturation. The video is split into a few
segments decoded in parallel (measured: 2-3 NVDEC sessions ~ 45x realtime for 1080p60, vs
~10x for one CPU decoder).
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Callable, Iterator

import numpy as np

from .. import hardware

FPS = 2.0
PREFETCH = 12  # decoded frames buffered per segment (~37 MB at 1080p)
MAX_HEIGHT = 1080  # bigger videos are scaled down to 1080p (HUD presets are made for it)


@dataclass
class Frame:
    t: float  # seconds from the video start
    y: np.ndarray  # (H, W) uint8 luma
    uv: np.ndarray  # (H/2, W/2, 2) uint8 chroma


def out_size(width: int, height: int) -> tuple[int, int]:
    if height <= MAX_HEIGHT:
        w, h = width, height
    else:
        w, h = round(width * MAX_HEIGHT / height), MAX_HEIGHT
    return w - w % 2, h - h % 2


_cuda_ok: bool | None = None


def cuda_decode_available() -> bool:
    """NVDEC through ffmpeg (checked once by decoding one frame)."""
    global _cuda_ok
    if _cuda_ok is None:
        _cuda_ok = False
        try:
            if hardware.detect_nvidia_gpus() and shutil.which("ffmpeg"):
                r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-hwaccel", "cuda",
                                    "-hwaccel_output_format", "cuda", "-f", "lavfi", "-i",
                                    "testsrc2=size=256x144:rate=1:duration=1", "-vf",
                                    "format=nv12,hwupload_cuda,scale_cuda=128:72,hwdownload,format=nv12",
                                    "-frames:v", "1", "-f", "null", "-"],
                                   capture_output=True, timeout=30)
                _cuda_ok = r.returncode == 0
        except Exception:
            _cuda_ok = False
    return _cuda_ok


def _cmd(src: str, start: float, length: float, w: int, h: int, cuda: bool) -> list[str]:
    head = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-skip_frame", "noref"]
    if cuda:
        head += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
        vf = f"fps={FPS},scale_cuda={w}:{h},hwdownload,format=nv12"
    else:
        head += ["-threads", "4"]
        vf = f"fps={FPS},scale={w}:{h}:flags=fast_bilinear,format=nv12"
    return head + ["-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", src, "-an", "-sn", "-vf", vf,
                   "-f", "rawvideo", "-pix_fmt", "nv12", "-"]


def read_segment(src: str, start: float, length: float, width: int, height: int,
                 cuda: bool, stop: threading.Event | None = None) -> Iterator[Frame]:
    w, h = out_size(width, height)
    size = w * h * 3 // 2
    proc = subprocess.Popen(_cmd(src, start, length, w, h, cuda), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, bufsize=size * 2)
    # A pump thread keeps ffmpeg decoding while the caller runs OCR on earlier frames.
    frames: queue.Queue = queue.Queue(maxsize=PREFETCH)
    done = threading.Event()

    def pump() -> None:
        try:
            while not done.is_set():
                buf = proc.stdout.read(size)
                if len(buf) < size:
                    break
                frames.put(buf)
        finally:
            frames.put(None)

    th = threading.Thread(target=pump, daemon=True)
    th.start()
    i = 0
    try:
        while not (stop and stop.is_set()):
            buf = frames.get()
            if buf is None:
                break
            a = np.frombuffer(buf, np.uint8)
            yield Frame(start + i / FPS, a[: w * h].reshape(h, w), a[w * h:].reshape(h // 2, w // 2, 2))
            i += 1
    finally:
        done.set()
        if proc.poll() is None:
            proc.kill()
        while th.is_alive():  # unblock the pump if it waits on a full queue
            try:
                frames.get(timeout=0.1)
            except queue.Empty:
                pass
        proc.wait()
        err = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
        if i == 0 and err and not (stop and stop.is_set()):
            raise RuntimeError(f"ffmpeg could not decode the video: {err[-300:]}")


def segments(duration: float, workers: int) -> list[tuple[float, float]]:
    n = max(1, min(workers, int(duration // 60) or 1))
    step = duration / n
    return [(i * step, step if i < n - 1 else duration - i * step) for i in range(n)]


def scan_parallel(src: str, duration: float, width: int, height: int,
                  make_worker: Callable[[int, float, float], Callable[[Frame], None]],
                  on_progress: Callable[[float], None] | None = None,
                  workers: int | None = None) -> dict:
    """Decode the video in parallel segments; each segment gets its own frame handler from
    make_worker(index, start, end) (handlers are called from that segment's thread only)."""
    cuda = cuda_decode_available()
    workers = workers or (3 if cuda else 2)
    segs = segments(duration, workers)
    done = [0.0] * len(segs)
    errors: list[BaseException] = []
    stop = threading.Event()
    lock = threading.Lock()

    def run(i: int, start: float, length: float) -> None:
        handle = make_worker(i, start, start + length)
        try:
            for fr in read_segment(src, start, length, width, height, cuda, stop):
                handle(fr)
                with lock:
                    done[i] = fr.t - start
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller's thread
            errors.append(exc)
            stop.set()

    threads = [threading.Thread(target=run, args=(i, s, n), daemon=True) for i, (s, n) in enumerate(segs)]
    for th in threads:
        th.start()
    while any(th.is_alive() for th in threads):
        for th in threads:
            th.join(timeout=0.5)
        if on_progress:
            with lock:
                on_progress(sum(done))
    if errors:
        raise errors[0]
    return {"decoder": "nvdec" if cuda else "cpu", "segments": len(segs)}
