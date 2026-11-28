"""Processing device + the "Light" preset for slow PCs (1.2.53).

A user report: Intel i3-1115G4 (2 cores / 4 threads), 8 GB RAM, Intel UHD graphics: a 17-minute
video took ~1 h 20 min. Settings > Performance now has

    processing_device   auto | cpu | gpu
        auto  = an NVIDIA GPU (>= 4 GB VRAM) or Apple Silicon for the AI, else the CPU. A weak
                integrated GPU is NEVER used for the AI (Ollama would otherwise try Intel / AMD
                iGPUs through Vulkan: slower than the CPU and it shares the little RAM).
                Intel Quick Sync is still used for video encoding (render.py tests it first).
        cpu   = everything AI on the CPU (also an NVIDIA GPU is left alone)
        gpu   = the GPU when there is a usable one (falls back to the CPU with a note)
    performance_preset  auto | light | normal
        auto  = "light" on a weak PC (detected on the first run), else normal

The Light preset: Whisper "small" (or "base" on very weak PCs) int8 with tuned threads, a small
LLM (qwen3.5:2b) or no LLM at all (template titles) below 12 GB RAM, voice separation off by
default, half the HUD OCR frames, lighter previews, one heavy job at a time.

Env for tests / the low-end profile: SHARKYCLIPS_SIM_RAM_GB, SHARKYCLIPS_SIM_THREADS,
SHARKYCLIPS_SIM_NO_GPU=1 pretend to be a smaller PC.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field

from . import config, hardware

DEVICES = ("auto", "cpu", "gpu")
PRESETS = ("auto", "light", "normal")
LIGHT_LLM = "qwen3.5:2b"
LIGHT_CTX = 4096
WEAK_RAM_GB = 12.0  # below this the 9B / 4B models swap next to Whisper, the browser and the game
TINY_RAM_GB = 6.0  # below this no LLM at all: template titles
SPEEDS_FILE = "perf_speeds.json"


@dataclass
class Machine:
    ram_gb: float
    threads: int
    cores: int
    nvidia_vram_gb: float | None
    nvidia_name: str | None
    apple_silicon: bool
    igpu: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def machine() -> Machine:
    hw = hardware.detect_hardware()
    gpu = hw.best_nvidia
    m = Machine(ram_gb=float(hw.ram_total_gb or 0), threads=int(hw.cpu_logical_cores or os.cpu_count() or 1),
                cores=int(hw.cpu_physical_cores or 1), nvidia_vram_gb=gpu.vram_gb if gpu else None,
                nvidia_name=gpu.name if gpu else None, apple_silicon=bool(hw.apple_silicon and not hw.rosetta),
                igpu=list(hw.other_gpus or []))
    if os.environ.get("SHARKYCLIPS_SIM_RAM_GB"):
        m.ram_gb = float(os.environ["SHARKYCLIPS_SIM_RAM_GB"])
    if os.environ.get("SHARKYCLIPS_SIM_THREADS"):
        m.threads = int(os.environ["SHARKYCLIPS_SIM_THREADS"])
        m.cores = max(1, m.threads // 2)
    if os.environ.get("SHARKYCLIPS_SIM_NO_GPU") == "1":
        m.nvidia_vram_gb, m.nvidia_name, m.apple_silicon = None, None, False
    return m


def weak_reasons(m: Machine | None = None) -> list[str]:
    """Why this PC counts as slow (empty = it doesn't). Short English codes for the UI."""
    m = m or machine()
    out = []
    if m.ram_gb and m.ram_gb < WEAK_RAM_GB:
        out.append("ram")
    if m.threads <= 4:
        out.append("cpu")
    if not (m.nvidia_vram_gb and m.nvidia_vram_gb >= 4) and not m.apple_silicon:
        out.append("no_gpu")
    # a fast desktop CPU without an NVIDIA GPU is not "weak": it needs low RAM or few threads too
    return out if ("ram" in out or "cpu" in out) else []


def is_weak(m: Machine | None = None) -> bool:
    return bool(weak_reasons(m))


def gpu_usable(m: Machine | None = None) -> bool:
    """A GPU good enough for the AI: NVIDIA with >= 4 GB VRAM, or Apple Silicon. Never an iGPU."""
    m = m or machine()
    return bool((m.nvidia_vram_gb and m.nvidia_vram_gb >= 4) or m.apple_silicon)


_DEDICATED = (
    # Radeon RX 7900 GRE, Radeon Pro W7600, Radeon VII ("Radeon RX Vega 11 Graphics" is a Ryzen iGPU)
    re.compile(r"radeon.*\b(rx\s*\d|pro\s*w\s*\d|vii\b)", re.I),
    # Intel Arc A770 / B580 / Pro A60M (iGPUs: "Arc Graphics", "Arc Pro Graphics", "Arc 140V")
    re.compile(r"\barc\b.*\b[ab]\d{2,3}[a-z]?\b", re.I),
)


def dedicated_other_gpu(m: Machine | None = None) -> str | None:
    """A dedicated AMD Radeon / Intel Arc card (issue #10). Whisper can't use it (no CUDA), but
    Ollama runs the LLM on it (ROCm / Vulkan), so the LLM must not be pinned to the CPU there.
    Integrated GPUs ("AMD Radeon(TM) Graphics", "Radeon 780M", "Intel Arc Graphics") don't count."""
    m = m or machine()
    if os.environ.get("SHARKYCLIPS_SIM_NO_GPU") == "1":
        return None
    return next((g for g in m.igpu if any(p.search(g) for p in _DEDICATED)), None)


def llm_on_gpu(m: Machine | None = None) -> bool:
    """May Ollama put the LLM on a GPU? NVIDIA / Apple (device 'gpu'), or a dedicated AMD / Intel
    card unless the user picked "CPU" in Settings > Performance."""
    m = m or machine()
    if str(config.get("processing_device") or "auto") == "cpu":
        return False
    return device(m) == "gpu" or dedicated_other_gpu(m) is not None


def device(m: Machine | None = None) -> str:
    """'gpu' or 'cpu': where the AI (Whisper, the LLM, voice models) runs."""
    want = str(config.get("processing_device") or "auto")
    if want == "cpu":
        return "cpu"
    return "gpu" if gpu_usable(m) else "cpu"


def light(m: Machine | None = None) -> bool:
    p = str(config.get("performance_preset") or "auto")
    if p == "light":
        return True
    if p == "normal":
        return False
    return is_weak(m)


def knobs(m: Machine | None = None) -> dict:
    """The concrete settings for this PC (used by transcribe / llm / game OCR / voices / UI)."""
    m = m or machine()
    lt = light(m)
    dev = device(m)
    if not lt:
        return {"light": False, "device": dev, "whisper_model": None, "cpu_threads": None, "llm_threads": None,
                "llm_model": None,
                "llm_ctx": None, "template_titles": False, "voices": True, "ocr_spacing": 1.0, "ocr_fps": 2.0,
                "one_job": False, "preview_height": None}
    # Whisper int8 on the CPU: "small" is the best quality / speed trade-off; "base" on 2 threads
    wmodel = "base" if (m.threads <= 2 or m.ram_gb < 4) else "small"
    # Measured on a 2-core / 4-thread laptop (1.2.53 low-end profile): Whisper (CTranslate2) is
    # 1.4x faster on the physical cores only (2 threads: 121 s vs 167 s for 17 min of audio), the
    # LLM (llama.cpp) is 1.6x faster with every thread (4: 736 s vs 1148 s).
    threads = max(1, min(m.cores, 8))
    llm_threads = max(1, min(m.threads, 8))
    template = bool(m.ram_gb and m.ram_gb < TINY_RAM_GB) or config.get("llm_enabled") is False
    llm_model = None if template else (LIGHT_LLM if m.ram_gb < WEAK_RAM_GB else None)
    return {"light": True, "device": dev, "whisper_model": wmodel if dev == "cpu" else None, "cpu_threads": threads,
            "llm_threads": llm_threads,
            "llm_model": llm_model, "llm_ctx": LIGHT_CTX, "template_titles": template,
            "voices": bool(config.get("voices_on_light")), "ocr_spacing": 2.0, "ocr_fps": 1.0,
            "one_job": True, "preview_height": 360}


def status() -> dict:
    """For Settings > Performance and the first-run check."""
    m = machine()
    k = knobs(m)
    return {"machine": m.to_dict(), "weak": is_weak(m), "weak_reasons": weak_reasons(m),
            "gpu_usable": gpu_usable(m), "device": k["device"], "light": k["light"], "knobs": k,
            "processing_device": str(config.get("processing_device") or "auto"),
            "performance_preset": str(config.get("performance_preset") or "auto"),
            "first_run_light": bool(config.get("light_auto_picked"))}


def first_run_pick() -> bool:
    """On the first run: a weak PC gets the Light preset (once; the user can change it)."""
    if config.get("light_checked"):
        return False
    weak = is_weak()
    changes: dict = {"light_checked": True}
    if weak and str(config.get("performance_preset") or "auto") == "auto":
        changes.update(performance_preset="light", light_auto_picked=True)
    config.update(**changes)
    return weak


# ------------------------------------------------------------------ time estimate

# seconds of work per second of video, per step, measured on the reference PCs (1.2.53 profile):
# "fast" = RTX laptop, "light" = 4-thread CPU with the Light preset, "slow" = CPU, normal preset.
DEFAULT_SPEEDS = {
    "fast": {"transcribe": 0.03, "highlights": 0.05, "game": 0.08, "analyze": 0.04, "render": 0.30},
    "light": {"transcribe": 0.30, "highlights": 0.10, "game": 0.20, "analyze": 0.25, "render": 0.70},
    "slow": {"transcribe": 0.90, "highlights": 0.20, "game": 0.45, "analyze": 2.20, "render": 1.10},
}


def _speeds_path():
    return config.config_dir() / SPEEDS_FILE


def _klass() -> str:
    if device() == "gpu":
        return "fast"
    return "light" if light() else "slow"


def learn(step: str, video_seconds: float, work_seconds: float) -> None:
    """Remember how fast a step really ran on this PC (moving average per preset)."""
    if video_seconds < 30 or work_seconds <= 0:
        return
    path = _speeds_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    k = _klass()
    cur = data.setdefault(k, {}).get(step)
    rate = work_seconds / video_seconds
    data[k][step] = round(rate if cur is None else 0.7 * float(cur) + 0.3 * rate, 4)
    data["updated"] = time.time()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def estimate(video_seconds: float, steps: list[str] | None = None, clips: int = 6) -> dict:
    """Rough time for the big job before it starts ("about 20 min on this PC")."""
    k = _klass()
    try:
        learned = json.loads(_speeds_path().read_text(encoding="utf-8")).get(k, {})
    except (OSError, ValueError):
        learned = {}
    rates = {**DEFAULT_SPEEDS[k], **learned}
    steps = steps or ["transcribe", "highlights", "analyze", "render"]
    out = {}
    for s in steps:
        base = clips * 40.0 if s == "render" else video_seconds  # renders: ~40 s clips each
        out[s] = round(rates.get(s, 0.2) * base)
    total = sum(out.values())
    return {"class": k, "steps": out, "seconds": total, "slow_pc": k != "fast" and is_weak(),
            "learned": bool(learned)}
