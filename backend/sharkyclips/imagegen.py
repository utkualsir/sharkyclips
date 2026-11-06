"""Local cover images (1.2.18): the AI's cover idea -> a real picture, on this computer.

Model: Z-Image-Turbo (Tongyi-MAI, Apache-2.0, 6B), 4-bit GGUF, with its Qwen3-4B text encoder
(Apache-2.0) and the FLUX VAE (Apache-2.0). It runs in stable-diffusion.cpp (MIT), a separate
small program, so "unload after use" is exact: the program exits and the GPU memory is free again.
About 6.7 GB on disk; fits 8 GB of VRAM (weights partly offloaded to RAM while idle).

GPU rules: the local LLM and Whisper are unloaded before a picture starts, and the governor's pause
(a game starts) stops the program at once, so the game gets the VRAM back; the picture is redone
after the pause.

Where it can't run well (no GPU with >= 6 GB, or an Apple Silicon Mac with < 16 GB memory) the app
says so and uses the facecam frame as the cover instead; Pro mode can still force the CPU (slow).
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from . import config
from .downloads import Remote, fetch, partial_bytes
from .errors import SharkyClipsError
from .procs import no_window, track, untrack

MODEL_ID = "z-image-turbo-q4k"
HF = "https://huggingface.co/"
MODEL_FILES: dict[str, Remote] = {
    "diffusion": Remote(HF + "leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_K.gguf",
                        "14b375ab4f226bc5378f68f37e899ef3c2242b8541e61e2bc1aff40976086fbd", 3864250304,
                        "z_image_turbo-Q4_K.gguf"),
    "llm": Remote(HF + "unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
                  "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597", 2497281120,
                  "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
    "vae": Remote(HF + "Comfy-Org/Z-Image-Turbo/resolve/main/split_files/vae/ae.safetensors",
                  "afc8e28272cd15db3919bacdb6918ce9c1ed22e96cb12c4d5ed0fba823529e38", 335304388,
                  "ae.safetensors"),
}
LICENSES = [
    {"name": "Z-Image-Turbo", "by": "Tongyi-MAI (Alibaba)", "license": "Apache-2.0",
     "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
     "source_url": "https://huggingface.co/Tongyi-MAI/Z-Image-Turbo"},
    {"name": "Qwen3-4B-Instruct-2507", "by": "Qwen (Alibaba)", "license": "Apache-2.0",
     "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
     "source_url": "https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507"},
    {"name": "FLUX.1 VAE", "by": "Black Forest Labs", "license": "Apache-2.0",
     "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
     "source_url": "https://huggingface.co/black-forest-labs/FLUX.1-schnell"},
    {"name": "stable-diffusion.cpp", "by": "leejet", "license": "MIT",
     "license_url": "https://github.com/leejet/stable-diffusion.cpp/blob/master/LICENSE",
     "source_url": "https://github.com/leejet/stable-diffusion.cpp"},
]

SD_TAG = "master-987-a77d362"
_SD = "https://github.com/leejet/stable-diffusion.cpp/releases/download/" + SD_TAG + "/sd-master-a77d362-bin-"
SD_BUILDS: dict[str, Remote] = {
    "win-vulkan": Remote(_SD + "win-vulkan-x64.zip", "a8b58fa44f2574534a61e9fa778e7fa4fede9c1e51e638e44059d43531824f07",
                         29518825, "sd-win-vulkan.zip"),
    "win-cpu": Remote(_SD + "win-cpu-x64.zip", "06d896f6098365ecd2979c2f9ed2790beadfc07fdcd5ccd85e0f5b4f84414a4d",
                      17854337, "sd-win-cpu.zip"),
    "mac-arm64": Remote(_SD + "Darwin-macOS-26.6.2-arm64.zip",
                        "e714e968a64d9a2729f1f21ac3f138c04723f51dcf04c92c665c894f8beded7c", 36875641, "sd-mac.zip"),
    "linux-vulkan": Remote(_SD + "Linux-Ubuntu-24.04-x86_64-vulkan.zip",
                           "f65d726b226c17344774eaa38173a5e811f9ab59b12bc37d0e3f3683d0ffa1f1", 36885522,
                           "sd-linux-vulkan.zip"),
    "linux-cpu": Remote(_SD + "Linux-Ubuntu-24.04-x86_64.zip",
                        "1a52ca1ab3b2364cd071bea4d6b124837d62ed88652ccf0d9506369a0a97bada", 26562164,
                        "sd-linux-cpu.zip"),
}

SIZES = {"tall": (576, 1024), "wide": (1024, 576)}  # generated, then scaled to the cover size
STEPS = 8
OPTIONS = 4
MIN_VRAM_MB = 6 * 1024
DEVICES = ("auto", "gpu", "cpu")
ProgressFn = Callable[[str, float | None], None]


def root() -> Path:
    return config.config_dir() / "models" / "image" / MODEL_ID


def tools_dir() -> Path:
    return config.config_dir() / "tools" / "sdcpp" / SD_TAG


def total_bytes() -> int:
    return sum(r.size for r in MODEL_FILES.values())


def model_ready() -> bool:
    return all((root() / r.name).is_file() and (root() / r.name).stat().st_size == r.size
               for r in MODEL_FILES.values())


def downloaded_bytes() -> int:
    return sum(min(r.size, partial_bytes(root() / r.name)) for r in MODEL_FILES.values())


# ------------------------------------------------------------------ what this computer can do


@dataclass
class Capability:
    tier: str  # gpu | cpu | none
    build: str | None  # key of SD_BUILDS
    reason: str  # code the UI translates: gpu_ok | apple_ok | no_gpu | small_gpu | small_ram | gpu_lost | os
    vram_mb: int | None = None

    def to_dict(self) -> dict:
        return {"tier": self.tier, "build": self.build, "reason": self.reason, "vram_mb": self.vram_mb}


_cap_cache: dict = {}


def capability(refresh: bool = False) -> Capability:
    """Can this computer make cover pictures, and with which build? (Cached for 10 minutes.)"""
    if os.environ.get("SHARKYCLIPS_IMAGEGEN_TIER"):  # tests
        tier = os.environ["SHARKYCLIPS_IMAGEGEN_TIER"]
        return Capability(tier, "win-cpu" if tier != "none" else None, f"test_{tier}")
    now = time.monotonic()
    if not refresh and _cap_cache.get("at", -1e9) > now - 600:
        return _cap_cache["cap"]
    cap = _detect()
    _cap_cache.update(at=now, cap=cap)
    return cap


def _detect() -> Capability:
    from . import hardware

    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin":
        if machine != "arm64":
            return Capability("none", None, "os")
        import psutil

        ram = psutil.virtual_memory().total / 2**30
        return Capability("gpu" if ram >= 15 else "none", "mac-arm64" if ram >= 15 else None,
                          "apple_ok" if ram >= 15 else "small_ram")
    if machine not in ("amd64", "x86_64"):
        return Capability("none", None, "os")
    prefix = "win" if system == "Windows" else "linux"
    try:
        gpus = hardware.detect_nvidia_gpus()
    except Exception:  # noqa: BLE001
        gpus = []
    best = max(gpus, key=lambda g: g.vram_total_mb, default=None)
    import psutil

    ram_gb = psutil.virtual_memory().total / 2**30
    cpu_ok = ram_gb >= 15  # the CPU path needs the weights in RAM
    if best is not None and best.vram_total_mb >= MIN_VRAM_MB:
        return Capability("gpu", f"{prefix}-vulkan", "gpu_ok", best.vram_total_mb)
    if best is None and _gpu_lost():
        return Capability("cpu" if cpu_ok else "none", f"{prefix}-cpu" if cpu_ok else None, "gpu_lost")
    reason = "small_gpu" if best is not None else ("no_gpu" if cpu_ok else "small_ram")
    return Capability("cpu" if cpu_ok else "none", f"{prefix}-cpu" if cpu_ok else None, reason,
                      best.vram_total_mb if best else None)


def _gpu_lost() -> bool:
    """nvidia-smi exists but can't talk to the card (Windows: 'GPU is lost', needs a restart)."""
    from . import hardware

    smi = hardware.find_nvidia_smi()
    if not smi:
        return False
    try:
        r = subprocess.run([smi, "-L"], capture_output=True, text=True, timeout=10, **no_window())
    except Exception:  # noqa: BLE001
        return False
    out = (r.stdout + r.stderr).lower()
    return "lost" in out or "no devices were found" in out


def device_setting() -> str:
    d = config.get("cover_ai_device")
    return d if d in DEVICES else "auto"


def plan() -> dict:
    """What a "Make AI covers" click would do now: {"use": "gpu"|"cpu"|"fallback", ...}."""
    cap = capability()
    dev = device_setting()
    if cap.tier == "none" or (cap.tier == "cpu" and dev != "cpu"):
        use = "fallback"
    elif dev == "cpu":
        use = "cpu"
    else:
        use = cap.tier
    build = cap.build
    if use == "cpu" and build:
        build = build.replace("vulkan", "cpu") if "vulkan" in build else build
    return {"use": use, "build": build if use != "fallback" else None, "capability": cap.to_dict(),
            "device": dev, "model_ready": model_ready(), "tool_ready": bool(build and _tool_exe(build)),
            "download_bytes": total_bytes(), "downloaded_bytes": downloaded_bytes(),
            "minutes_per_picture": 0.3 if use == "gpu" else 4.0 if use == "cpu" else None,
            "licenses": LICENSES}


# ------------------------------------------------------------------ install


def _tool_exe(build: str) -> Path | None:
    base = tools_dir() / build
    if not base.is_dir():
        return None
    name = "sd-cli.exe" if build.startswith("win") else "sd-cli"
    for p in base.rglob(name):
        return p
    alt = "sd.exe" if build.startswith("win") else "sd"
    for p in base.rglob(alt):
        return p
    return None


def _unzip(zpath: Path, dest: Path) -> None:
    tmp = dest.with_name(dest.name + ".unzip")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            target = (tmp / info.filename).resolve()
            if not str(target).startswith(str(tmp.resolve())):  # no paths out of the folder
                raise SharkyClipsError("The image tool archive looks wrong.", "Try again later.")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            mode = (info.external_attr >> 16) & 0o777
            if mode and os.name != "nt":
                os.chmod(target, mode | 0o100)
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)


def ensure_tool(build: str, on_progress: ProgressFn | None = None, cancel: threading.Event | None = None) -> Path:
    exe = _tool_exe(build)
    if exe is not None:
        return exe
    remote = SD_BUILDS[build]
    zpath = tools_dir() / remote.name

    def prog(done: int, total: int) -> None:
        if on_progress:
            on_progress("downloading_image_tool", done / max(1, total))

    fetch(remote, zpath, prog, cancel, label="image tool")
    _unzip(zpath, tools_dir() / build)
    zpath.unlink(missing_ok=True)
    exe = _tool_exe(build)
    if exe is None:
        raise SharkyClipsError("The image tool didn't unpack correctly.", "Try again later.")
    if os.name != "nt":
        os.chmod(exe, 0o755)
    return exe


def ensure_model(on_progress: ProgressFn | None = None, cancel: threading.Event | None = None) -> dict[str, Path]:
    """The three model files (downloaded once, resumable)."""
    total = total_bytes()
    out: dict[str, Path] = {}
    base = 0
    for key, remote in MODEL_FILES.items():
        def prog(done: int, _t: int, base=base) -> None:
            if on_progress:
                on_progress("downloading_image_model", (base + done) / total)

        out[key] = fetch(remote, root() / remote.name, prog, cancel, label="cover image model")
        base += remote.size
    return out


def remove_model() -> int:
    """Delete the model files (Settings: free the disk space). Returns bytes freed."""
    freed = 0
    if root().is_dir():
        for p in root().iterdir():
            freed += p.stat().st_size
        shutil.rmtree(root(), ignore_errors=True)
    return freed


# ------------------------------------------------------------------ prompts

_TEXT_CLAUSE = re.compile(r",?\s*bold short overlay text\s*\"[^\"]*\"", re.I)
_FRAME_CLAUSE = re.compile(r"vertical 9:16 thumbnail,?\s*", re.I)


_QUOTED = re.compile(r"\s*(?:with\s+)?(?:an?\s+|the\s+)?['\"\u201c\u2018][^'\"\u201d\u2019]{1,60}['\"\u201d\u2019]\s*")


def image_prompt(cover_prompt: str, frame: str) -> str:
    """The AI's cover idea without any words to paint (the app adds the cover text itself, sharp
    and in its own style; image models paint quoted words as text) and with the right frame."""
    p = _TEXT_CLAUSE.sub("", cover_prompt or "").strip()
    p = _QUOTED.sub(" ", p)
    p = re.sub(r"\s+", " ", _FRAME_CLAUSE.sub("", p)).strip(" ,.")
    if frame == "tall":
        shape = "vertical 9:16 portrait composition, the subject large in the upper two thirds, darker background below"
    else:
        shape = "wide 16:9 landscape composition, the subject large on the right, darker background on the left"
    return (f"{p}. {shape}, cinematic still, edge to edge, fills the entire canvas, high detail, "
            "no border, no frame, no white background, no text, no letters, no words, no logos, no watermark")


# ------------------------------------------------------------------ run

_STEP = re.compile(r"(\d+)/(\d+)")


class Runner:
    """One sd-cli process. stop() kills it (governor pause / cancel); the VRAM is free at once."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def stop(self) -> None:
        with self._lock:
            p = self.proc
        if p is not None and p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass

    def run(self, cmd: list[str], cwd: Path, on_step: Callable[[int, int], None] | None,
            should_stop: Callable[[], bool]) -> tuple[int, str]:
        tail: list[str] = []
        p = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1, **no_window())
        with self._lock:
            self.proc = p
        track(p)
        watcher_stop = threading.Event()

        def watch() -> None:
            while not watcher_stop.wait(0.3):
                if should_stop():
                    self.stop()
                    return

        threading.Thread(target=watch, name="sharkyclips-imagegen-watch", daemon=True).start()
        try:
            assert p.stdout is not None
            buf = ""
            while True:
                ch = p.stdout.read(256)
                if not ch:
                    break
                buf += ch
                parts = re.split(r"[\r\n]", buf)
                buf = parts.pop()
                for line in parts:
                    if not line.strip():
                        continue
                    tail = (tail + [line])[-30:]
                    m = _STEP.findall(line)
                    if on_step and m and ("it/s" in line or "s/it" in line):
                        a, b = m[-1]
                        on_step(int(a), int(b))
            code = p.wait()
        finally:
            watcher_stop.set()
            untrack(p)
            with self._lock:
                self.proc = None
        return code, "\n".join(tail)


def _command_prefix(exe: Path) -> list[str]:
    """How to start sd-cli (tests swap in a fake one)."""
    return [str(exe)]


def _threads() -> int:
    from . import governor

    return max(1, governor.cpu_threads())


def free_gpu() -> None:
    """The LLM and Whisper never share the GPU with the image model."""
    from . import llm, memory

    memory.release_current()
    try:
        if llm.server_version(timeout=1.0):
            llm.unload_all()
    except Exception:  # noqa: BLE001
        pass


def generate(prompt: str, frame: str, seeds: list[int], dest_dir: Path, *, use: str, build: str,
             on_progress: ProgressFn | None = None, runner: Runner | None = None,
             cancel: threading.Event | None = None) -> list[Path]:
    """One picture per seed into dest_dir (PNG), in ONE sd-cli run (the 6 GB of weights load once;
    sd-cli's batch uses seed, seed+1, ...). Seeds that aren't consecutive run one by one. Pauses
    (and redoes the run) while the governor pauses. Returns the files in seed order."""
    from . import governor

    if frame not in SIZES:
        raise SharkyClipsError(f"Unknown cover size '{frame}'.")
    targets = [dest_dir / f"{s}_{frame}.png" for s in seeds]
    if all(t.is_file() for t in targets):
        return targets
    files = ensure_model(on_progress, cancel)
    exe = ensure_tool(build, on_progress, cancel)
    w, h = SIZES[frame]
    runner = runner or Runner()
    dest_dir.mkdir(parents=True, exist_ok=True)
    consecutive = all(b == a + 1 for a, b in zip(seeds, seeds[1:]))
    groups = [seeds] if consecutive else [[s] for s in seeds]
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-img-"))
    done_before = 0
    try:
        for group in groups:
            if all((dest_dir / f"{s}_{frame}.png").is_file() for s in group):
                done_before += len(group)
                continue
            while True:
                governor.checkpoint(release=runner.stop)  # raises JobCancelled; waits while paused
                free_gpu()
                for old in work.glob("img*.png"):
                    old.unlink()
                cmd = [*_command_prefix(exe), "--diffusion-model", str(files["diffusion"]), "--vae", str(files["vae"]),
                       "--llm", str(files["llm"]), "-p", prompt, "--cfg-scale", "1.0", "--steps", str(STEPS),
                       "-W", str(w), "-H", str(h), "--seed", str(group[0]), "-o", str(work / "img.png"),
                       "-t", str(_threads())]
                if len(group) > 1:
                    cmd += ["-b", str(len(group))]
                if use == "gpu":
                    cmd += ["--offload-to-cpu", "--diffusion-fa", "--vae-tiling"]
                seen = {"n": 0, "last": 0}

                def step(a: int, b: int, base=done_before) -> None:
                    if a < seen["last"]:  # the next picture of the batch started
                        seen["n"] += 1
                    seen["last"] = a
                    if on_progress:
                        on_progress("making_covers", min(1.0, (base + seen["n"] + min(1.0, a / max(1, b))) / len(seeds)))

                g = governor.get()

                def stop_now() -> bool:
                    return bool((cancel is not None and cancel.is_set())
                                or (g is not None and g.paused and not getattr(governor._tls, "defer", False))
                                or _job_cancelled())

                code, tail = runner.run(cmd, work, step, stop_now)
                made = _batch_files(work, len(group))
                if code == 0 and made is not None:
                    for s, f in zip(group, made):
                        trim_border(f)
                        shutil.move(str(f), dest_dir / f"{s}_{frame}.png")
                    done_before += len(group)
                    break
                if cancel is not None and cancel.is_set() or _job_cancelled():
                    from .governor import JobCancelled

                    raise JobCancelled()
                if g is not None and g.paused:
                    continue  # stopped for a game: wait at the checkpoint, then redo this run
                raise SharkyClipsError("The cover picture could not be made.", _hint(tail))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return targets


def trim_border(path: Path, limit: float = 0.35) -> bool:
    """Image models sometimes paint the picture on a white (or black) card: cut uniform bands off
    the edges (up to `limit` of a side). The cover is then filled from what's left. True if cut."""
    from PIL import Image

    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    grey = rgb.mean(axis=2)

    def flat(line: np.ndarray) -> bool:  # one row / column: nearly one colour, very light or very dark
        m = float(line.mean())
        return float(line.std()) < 6.0 and (m > 232 or m < 14)

    top = 0
    while top < h * limit and flat(grey[top]):
        top += 1
    bottom = h
    while h - bottom < h * limit and flat(grey[bottom - 1]):
        bottom -= 1
    left = 0
    while left < w * limit and flat(grey[top:bottom, left]):
        left += 1
    right = w
    while w - right < w * limit and flat(grey[top:bottom, right - 1]):
        right -= 1
    if top + (h - bottom) < h * 0.03 and left + (w - right) < w * 0.03:
        return False
    with Image.open(path) as im:
        im.crop((left, top, right, bottom)).save(path)
    return True


def _batch_files(work: Path, n: int) -> list[Path] | None:
    """sd-cli's output names: img.png for one picture, img_0.png ... img_<n-1>.png for a batch
    (newer builds may start at 1): the n files in order, or None if some are missing."""
    if n == 1:
        one = work / "img.png"
        if one.is_file():
            return [one]
    found = []
    for p in work.glob("img_*.png"):
        try:
            found.append((int(p.stem.split("_")[-1]), p))
        except ValueError:
            pass
    found.sort()
    return [p for _i, p in found] if len(found) == n else None


def _job_cancelled() -> bool:
    from . import governor

    job = governor.current_job()
    return bool(job is not None and getattr(job, "cancel_requested", False))


def _hint(tail: str) -> str:
    low = tail.lower()
    if "out of memory" in low or "vk_error_out_of_device_memory" in low or "failed to allocate" in low:
        return "The graphics card ran out of memory: close games or other apps and try again."
    if "vulkan" in low and ("not found" in low or "no device" in low or "failed" in low):
        return "The graphics driver doesn't support Vulkan: update it, or use the processor in Settings."
    return (tail.strip().splitlines() or ["Try again."])[-1][-300:]
