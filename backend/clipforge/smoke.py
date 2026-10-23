"""Real (tiny) transcription smoke test on 2 seconds of generated audio.

Always run through run_subprocess(): a broken CUDA/cuDNN install can kill the
process outright, and on Windows loaded DLLs can't be upgraded by pip.

    python -m clipforge.smoke --device cuda --compute-type float16
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

MARK = "CLIPFORGE_SMOKE_RESULT "
BACKEND_DIR = Path(__file__).resolve().parents[1]


def generate_audio(seconds: float = 2.0, sr: int = 16000) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    voice_like = 0.3 * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
    noise = 0.02 * np.random.default_rng(0).standard_normal(len(t))
    return (voice_like + noise).astype(np.float32)


def run(device: str, compute_type: str, device_index: int = 0) -> dict:
    result: dict = {"ok": False, "device": device, "compute_type": compute_type}
    samples = generate_audio()
    t0 = time.perf_counter()
    try:
        if device == "mlx":
            import mlx_whisper

            from .hardware import MLX_REPOS
            from .models import mlx_model_path

            mlx_whisper.transcribe(samples, path_or_hf_repo=mlx_model_path(MLX_REPOS["tiny"]),
                                   word_timestamps=True, verbose=None)
        else:
            from . import hardware, memory

            if device == "cuda":
                hardware.setup_cuda_dlls()
            import ctranslate2

            result["ctranslate2"] = ctranslate2.__version__
            if device == "cuda":
                count = ctranslate2.get_cuda_device_count()
                result["cuda_devices"] = count
                if count == 0:
                    raise RuntimeError("ctranslate2 sees no CUDA device (driver too old or "
                                       "CUDA libraries not loadable)")
                result["compute_types"] = sorted(
                    ctranslate2.get_supported_compute_types("cuda", device_index))
            from faster_whisper import WhisperModel

            from .models import faster_whisper_model_path

            if os.environ.get("CLIPFORGE_SIMULATE_GPU_FAILURE") and device == "cuda":
                raise RuntimeError("simulated GPU failure (CLIPFORGE_SIMULATE_GPU_FAILURE)")
            model = WhisperModel(faster_whisper_model_path("tiny"), device=device, device_index=device_index,
                                 compute_type=compute_type)
            # No VAD here: we want the encoder + decoder to really run on the device.
            segments, info = model.transcribe(samples, vad_filter=False, word_timestamps=True,
                                              beam_size=1)
            list(segments)
            result["detected_language"] = info.language
            memory.release_model(model)
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["seconds"] = round(time.perf_counter() - t0, 2)
    return result


def run_subprocess(device: str, compute_type: str, device_index: int = 0,
                   timeout: float = 900) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, "-m", "clipforge.smoke", "--device", device,
           "--compute-type", compute_type, "--device-index", str(device_index)]
    kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, cwd=str(BACKEND_DIR), env=env,
                              **kwargs)
    except subprocess.TimeoutExpired:
        return {"ok": False, "device": device, "error": f"timed out after {timeout:.0f}s"}
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    tail = " | ".join((proc.stderr or proc.stdout).strip().splitlines()[-4:])
    return {"ok": False, "device": device, "compute_type": compute_type,
            "error": f"test process crashed (exit code {proc.returncode}): {tail[:600]}"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--device-index", type=int, default=0)
    args = ap.parse_args()
    res = run(args.device, args.compute_type, args.device_index)
    print(MARK + json.dumps(res), flush=True)


if __name__ == "__main__":
    main()
