"""Detect the user's hardware at runtime and pick a transcription backend.

Nothing here assumes a particular machine: every decision is derived from what
is detected (OS, NVIDIA GPU + VRAM, Apple Silicon, RAM, CPU cores).
"""

from __future__ import annotations

import ctypes
import functools
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import psutil

# Model names ClipForge accepts on the command line.
MODEL_CHOICES = ("auto", "large-v3-turbo", "medium", "small")
# When a model doesn't fit, step down to the next one.
MODEL_FALLBACK = {"large-v3-turbo": "medium", "medium": "small", "small": None}
# MLX (Apple Silicon) model repos on Hugging Face.
MLX_REPOS = {
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "medium": "mlx-community/whisper-medium-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "tiny": "mlx-community/whisper-tiny",
}


# --------------------------------------------------------------------------- data


@dataclass
class GPUInfo:
    index: int
    name: str
    vram_total_mb: int
    vram_free_mb: int | None = None
    driver: str | None = None
    compute_cap: str | None = None

    @property
    def vram_gb(self) -> float:
        return self.vram_total_mb / 1024


@dataclass
class HardwareInfo:
    os_name: str
    os_version: str
    arch: str
    python_version: str
    cpu_name: str
    cpu_physical_cores: int
    cpu_logical_cores: int
    ram_total_gb: float
    ram_available_gb: float
    nvidia_gpus: list[GPUInfo] = field(default_factory=list)
    other_gpus: list[str] = field(default_factory=list)
    apple_silicon: bool = False
    rosetta: bool = False  # x86 Python running on an Apple Silicon Mac

    @property
    def best_nvidia(self) -> GPUInfo | None:
        return max(self.nvidia_gpus, key=lambda g: g.vram_total_mb, default=None)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BackendPlan:
    backend: str  # "faster-whisper" | "mlx-whisper"
    device: str  # "cuda" | "cpu" | "mlx"
    model: str  # large-v3-turbo | medium | small
    compute_type: str  # float16 | int8_float16 | int8 | (mlx: float16)
    device_index: int = 0
    batch_size: int = 1  # >1 uses faster-whisper's batched pipeline (GPU only)
    beam_size: int = 5
    cpu_threads: int = 0
    reason: str = ""
    warning: str | None = None

    @property
    def label(self) -> str:
        return f"{self.backend} | {self.device} | {self.model} | {self.compute_type}"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------- helpers


def _run(cmd: list[str], timeout: float = 15) -> str | None:
    """Run a command without a shell; return stdout on success, else None."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, **kwargs,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


def find_nvidia_smi() -> str | None:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    if os.name == "nt":
        candidates = [
            Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe",
        ]
        for c in candidates:
            if c.is_file():
                return str(c)
    return None


def _num(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def detect_nvidia_gpus() -> list[GPUInfo]:
    smi = find_nvidia_smi()
    if not smi:
        return []
    fields = "index,name,memory.total,memory.free,driver_version,compute_cap"
    out = _run([smi, f"--query-gpu={fields}", "--format=csv,noheader,nounits"])
    if out is None:  # very old drivers don't know compute_cap
        out = _run([smi, "--query-gpu=index,name,memory.total,memory.free,driver_version",
                    "--format=csv,noheader,nounits"])
    if not out:
        return []
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        gpus.append(GPUInfo(
            index=_num(parts[0]) or 0,
            name=parts[1],
            vram_total_mb=_num(parts[2]) or 0,
            vram_free_mb=_num(parts[3]) if len(parts) > 3 else None,
            driver=parts[4] if len(parts) > 4 else None,
            compute_cap=parts[5] if len(parts) > 5 and parts[5] not in ("[N/A]", "") else None,
        ))
    return gpus


def gpu_memory_used_mb(index: int = 0) -> int | None:
    """Current VRAM in use on one NVIDIA GPU (None if unknown)."""
    smi = find_nvidia_smi()
    if not smi:
        return None
    out = _run([smi, f"--id={index}", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
    return _num(out.strip()) if out else None


def detect_other_gpus() -> list[str]:
    """Best-effort list of non-NVIDIA GPU names (informational only)."""
    names: list[str] = []
    system = platform.system()
    if system == "Windows":
        out = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                    "(Get-CimInstance Win32_VideoController).Name"])
        if out:
            names = [ln.strip() for ln in out.splitlines() if ln.strip()]
    elif system == "Darwin":
        out = _run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=30)
        if out:
            try:
                for item in json.loads(out).get("SPDisplaysDataType", []):
                    if item.get("sppci_model"):
                        names.append(item["sppci_model"])
            except json.JSONDecodeError:
                pass
    else:
        out = _run(["lspci"])
        if out:
            names = [ln.split(": ", 1)[-1] for ln in out.splitlines()
                     if "VGA" in ln or "3D controller" in ln]
    return [n for n in names if "nvidia" not in n.lower()]


def _cpu_name() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            import winreg

            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        if system == "Darwin":
            out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
            if out:
                return out.strip()
        else:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or platform.machine()


def _os_name_version() -> tuple[str, str]:
    system = platform.system()
    if system == "Windows":
        build = sys.getwindowsversion().build
        return ("Windows 11" if build >= 22000 else f"Windows {platform.release()}"), f"build {build}"
    if system == "Darwin":
        return "macOS", platform.mac_ver()[0]
    return system, platform.release()


@functools.lru_cache(maxsize=1)
def detect_hardware() -> HardwareInfo:
    os_name, os_version = _os_name_version()
    machine = platform.machine().lower()
    apple_silicon = rosetta = False
    if platform.system() == "Darwin":
        hw_arm = (_run(["sysctl", "-n", "hw.optional.arm64"]) or "").strip() == "1"
        apple_silicon = machine == "arm64" or hw_arm
        rosetta = hw_arm and machine != "arm64"
    vm = psutil.virtual_memory()
    return HardwareInfo(
        os_name=os_name,
        os_version=os_version,
        arch=machine,
        python_version=platform.python_version(),
        cpu_name=_cpu_name(),
        cpu_physical_cores=psutil.cpu_count(logical=False) or os.cpu_count() or 1,
        cpu_logical_cores=psutil.cpu_count(logical=True) or os.cpu_count() or 1,
        ram_total_gb=round(vm.total / 1024**3, 1),
        ram_available_gb=round(vm.available / 1024**3, 1),
        nvidia_gpus=detect_nvidia_gpus(),
        other_gpus=detect_other_gpus(),
        apple_silicon=apple_silicon,
        rosetta=rosetta,
    )


# ------------------------------------------------------- CUDA libraries via pip

_DLL_HANDLES: list = []
_CUDA_DIRS: list[Path] | None = None


def nvidia_lib_dirs() -> list[Path]:
    """Folders of the pip-installed NVIDIA libraries (nvidia-cublas-cu12, nvidia-cudnn-cu12)."""
    sub = "bin" if os.name == "nt" else "lib"
    dirs: list[Path] = []
    for entry in sys.path:
        if not entry:
            continue
        base = Path(entry) / "nvidia"
        if base.is_dir():
            for d in sorted(base.glob(f"*/{sub}")):
                if d.is_dir() and d not in dirs:
                    dirs.append(d)
    return dirs


def nvidia_libs_installed() -> dict[str, bool]:
    names = {d.parent.name for d in nvidia_lib_dirs()}
    return {"cublas": "cublas" in names, "cudnn": "cudnn" in names}


def setup_cuda_dlls() -> list[Path]:
    """Make the pip-installed CUDA libraries loadable. Call before importing ctranslate2.

    This is what removes the need for a manual CUDA Toolkit / cuDNN install.
    """
    global _CUDA_DIRS
    if _CUDA_DIRS is not None:
        return _CUDA_DIRS
    dirs = nvidia_lib_dirs()
    if os.name == "nt":
        for d in dirs:
            try:
                _DLL_HANDLES.append(os.add_dll_directory(str(d)))
            except OSError:
                pass
        # cuDNN loads its sub-libraries lazily with plain LoadLibrary, which uses PATH.
        os.environ["PATH"] = os.pathsep.join([str(d) for d in dirs] + [os.environ.get("PATH", "")])
    elif sys.platform.startswith("linux"):
        for d in dirs:
            for lib in sorted(d.glob("lib*.so*")):
                if lib.name.startswith(("libcublas", "libcudnn")):
                    try:
                        _DLL_HANDLES.append(ctypes.CDLL(str(lib), mode=ctypes.RTLD_GLOBAL))
                    except OSError:
                        pass
    _CUDA_DIRS = dirs
    return dirs


def cuda_device_count() -> int:
    """Number of CUDA devices ctranslate2 can use (0 if none / not installed)."""
    setup_cuda_dlls()
    try:
        import ctranslate2

        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def mlx_available() -> bool:
    return importlib.util.find_spec("mlx_whisper") is not None


# ------------------------------------------------------------- plan selection


def cpu_plan(hw: HardwareInfo, requested_model: str = "auto", warning: str | None = None,
             reason: str = "") -> BackendPlan:
    if requested_model == "auto":
        model = "medium" if hw.ram_total_gb >= 12 else "small"
        reason = reason or f"CPU mode, {hw.ram_total_gb:.0f} GB RAM -> {model} int8"
    else:
        model = requested_model
        reason = reason or f"CPU mode, model chosen by user ({model})"
    return BackendPlan(
        backend="faster-whisper", device="cpu", model=model, compute_type="int8",
        batch_size=1, beam_size=1, cpu_threads=hw.cpu_physical_cores,
        reason=reason, warning=warning,
    )


def cuda_compute_for(vram_gb: float) -> str:
    return "float16" if vram_gb >= 6 else "int8_float16"


def cuda_batch_for(vram_gb: float) -> int:
    if vram_gb >= 10:
        return 16
    if vram_gb >= 6:
        return 8
    return 4


def choose_plan(hw: HardwareInfo, requested_model: str = "auto", *, cuda_ok: bool = True,
                force_cpu: bool = False, force_cpu_reason: str | None = None) -> BackendPlan:
    """Pick backend, model and compute type for this machine."""
    if requested_model not in MODEL_CHOICES:
        from .errors import ClipForgeError

        raise ClipForgeError(f"Unknown model '{requested_model}'.",
                             f"Use one of: {', '.join(MODEL_CHOICES)}")

    other = ", ".join(hw.other_gpus) or "no dedicated GPU found"
    slow = "This will be slower than on an NVIDIA GPU or Apple Silicon, but it works."

    # Apple Silicon -> MLX
    if hw.apple_silicon and not hw.rosetta:
        if mlx_available():
            if requested_model == "auto":
                model = "large-v3-turbo" if hw.ram_total_gb >= 8 else "small"
                reason = f"Apple Silicon, {hw.ram_total_gb:.0f} GB unified memory -> {model}"
            else:
                model, reason = requested_model, f"Apple Silicon, model chosen by user ({model})"
            return BackendPlan(backend="mlx-whisper", device="mlx", model=model,
                               compute_type="float16", reason=reason)
        return cpu_plan(hw, requested_model, warning=(
            "Apple Silicon detected but mlx-whisper is not installed - using CPU. "
            "Fix: python -m pip install mlx-whisper"))
    if hw.rosetta:
        return cpu_plan(hw, requested_model, warning=(
            "Python is running under Rosetta (x86). Install an arm64 Python "
            "(brew install python@3.12) to use the much faster MLX backend."))

    gpu = hw.best_nvidia
    if gpu and force_cpu:
        return cpu_plan(hw, requested_model, warning=(
            f"GPU disabled after a failed GPU test: {force_cpu_reason or 'unknown reason'}. "
            f"Run `python cli.py doctor` to re-test. {slow}"))
    if gpu and not cuda_ok:
        return cpu_plan(hw, requested_model, warning=(
            f"NVIDIA GPU found ({gpu.name}) but CUDA is not usable. "
            f"Run `python cli.py doctor` to diagnose. {slow}"))
    if gpu:
        v = gpu.vram_gb
        if requested_model != "auto":
            model, compute = requested_model, cuda_compute_for(v)
            reason = f"{gpu.name} ({v:.1f} GB VRAM), model chosen by user"
        elif v >= 6:
            model, compute = "large-v3-turbo", "float16"
            reason = f"{gpu.name} ({v:.1f} GB VRAM >= 6 GB) -> large-v3-turbo float16"
        elif v >= 4:
            model, compute = "large-v3-turbo", "int8_float16"
            reason = f"{gpu.name} ({v:.1f} GB VRAM < 6 GB) -> large-v3-turbo int8_float16"
        elif v >= 2.5:
            model, compute = "medium", "int8_float16"
            reason = f"{gpu.name} ({v:.1f} GB VRAM) -> medium int8_float16"
        elif v >= 1.5:
            model, compute = "small", "int8_float16"
            reason = f"{gpu.name} ({v:.1f} GB VRAM) -> small int8_float16"
        else:
            return cpu_plan(hw, requested_model, warning=(
                f"{gpu.name} has too little VRAM ({v:.1f} GB) for Whisper. {slow}"))
        return BackendPlan(
            backend="faster-whisper", device="cuda", device_index=gpu.index, model=model,
            compute_type=compute, batch_size=cuda_batch_for(v), beam_size=5, reason=reason,
        )

    # AMD / Intel / no GPU
    return cpu_plan(hw, requested_model, warning=(
        f"No NVIDIA GPU detected ({other}). AMD/Intel GPUs aren't supported by the "
        f"transcriber yet, so ClipForge runs on the CPU (int8). {slow}"))


def gpu_fingerprint(hw: HardwareInfo, ct2_version: str | None) -> str | None:
    gpu = hw.best_nvidia
    if not gpu:
        return None
    return f"{gpu.name}|{gpu.driver}|ct2={ct2_version}"
