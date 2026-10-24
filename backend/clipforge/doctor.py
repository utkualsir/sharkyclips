"""`cli.py doctor`: check everything ClipForge needs and repair what it can.

This process never imports ctranslate2 itself (tests run in a subprocess), so
pip can upgrade the GPU libraries even on Windows, where loaded DLLs are locked.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
import subprocess
import sys

from rich.table import Table

from . import config, hardware, smoke
from .errors import install_hint, pip_hint
from .hardware import BackendPlan
from .ingest import js_runtimes
from .ui import console

OK, MISSING, WARN, INFO, FAIL = "OK", "MISSING", "WARN", "INFO", "FAIL"
_STYLE = {OK: "bold green", MISSING: "bold red", FAIL: "bold red", WARN: "bold yellow", INFO: "cyan"}
REQUIRED_PACKAGES = [("faster-whisper", "faster_whisper"), ("ctranslate2", "ctranslate2"),
                     ("yt-dlp", "yt_dlp"), ("numpy", "numpy"), ("psutil", "psutil"),
                     ("rich", "rich")]
GPU_FIX_PACKAGES = ["faster-whisper", "ctranslate2", "nvidia-cublas-cu12", "nvidia-cudnn-cu12>=9,<10"]


def _version(dist: str) -> str | None:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


def _tool_version(exe: str) -> str:
    try:
        out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=15,
                             encoding="utf-8", errors="replace").stdout
        first = out.splitlines()[0] if out else ""
        return first.split(" Copyright")[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "found"


def _pip_install(packages: list[str]) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", *packages]
    console.print(f"[dim]$ {' '.join(cmd)}[/]")
    return subprocess.run(cmd).returncode == 0


class Doctor:
    def __init__(self, fix: bool = True, download_models: bool = False):
        self.fix = fix
        self.download_models = download_models
        self.rows: list[tuple[str, str, str]] = []
        self.notes: list[str] = []

    def add(self, check: str, status: str, detail: str) -> None:
        self.rows.append((check, status, detail))

    # ------------------------------------------------------------------ checks

    def run(self) -> int:
        with console.status("Detecting hardware ..."):
            hw = hardware.detect_hardware()

        self.add("Operating system", OK, f"{hw.os_name} ({hw.os_version}, {hw.arch})")
        py_ok = sys.version_info >= (3, 11)
        self.add("Python", OK if py_ok else MISSING,
                 f"{hw.python_version}" + ("" if py_ok else f"  need 3.11+: {install_hint('python')}"))
        self.add("CPU", INFO, f"{hw.cpu_name} ({hw.cpu_physical_cores} cores / "
                              f"{hw.cpu_logical_cores} threads)")
        self.add("RAM", OK if hw.ram_total_gb >= 8 else WARN,
                 f"{hw.ram_total_gb:.1f} GB total, {hw.ram_available_gb:.1f} GB free"
                 + ("" if hw.ram_total_gb >= 8 else "  (low RAM: smaller models will be used)"))

        for tool in ("ffmpeg", "ffprobe"):
            path = shutil.which(tool)
            self.add(tool, OK if path else MISSING,
                     _tool_version(path) if path else f"install: {install_hint('ffmpeg')}")

        yv = _version("yt-dlp")
        self.add("yt-dlp", OK if yv else MISSING, yv or f"install: {pip_hint('yt-dlp[default]')}")
        rts = js_runtimes()
        self.add("JS runtime (YouTube)", OK if rts else WARN,
                 ", ".join(rts) if rts else f"none - YouTube downloads may fail. {install_hint('deno')}")

        for dist, module in REQUIRED_PACKAGES:
            if dist == "yt-dlp":
                continue
            v = _version(dist)
            found = v and importlib.util.find_spec(module) is not None
            self.add(f"python: {dist}", OK if found else MISSING,
                     v if found else "install: python -m pip install -r backend/requirements.txt")

        # GPU ------------------------------------------------------------
        gpu = hw.best_nvidia
        if gpu:
            self.add("GPU", OK, f"{gpu.name}" + (f" (compute {gpu.compute_cap})" if gpu.compute_cap else "")
                     + (f"  +{len(hw.nvidia_gpus) - 1} more" if len(hw.nvidia_gpus) > 1 else ""))
            self.add("VRAM", OK if gpu.vram_gb >= 2 else WARN,
                     f"{gpu.vram_gb:.1f} GB total, {(gpu.vram_free_mb or 0) / 1024:.1f} GB free")
            self.add("NVIDIA driver", INFO, gpu.driver or "unknown")
            self._check_nvidia_libs()
        elif hw.apple_silicon:
            self.add("GPU", OK, f"Apple Silicon ({', '.join(hw.other_gpus) or hw.cpu_name})")
            self.add("VRAM", INFO, f"unified memory: {hw.ram_total_gb:.0f} GB")
            mv = _version("mlx-whisper")
            self.add("python: mlx-whisper", OK if mv else MISSING,
                     mv or f"install: {pip_hint('mlx-whisper')}")
        else:
            self.add("GPU", WARN, (", ".join(hw.other_gpus) or "none detected")
                     + " - no NVIDIA/Apple GPU, CPU mode")
            self.add("VRAM", INFO, "n/a")

        plan = self._smoke_and_plan(hw)
        self._check_whisper_model(plan)
        self._check_highlight_deps()
        self._check_encoder()
        self._check_llm()

        ws = config.workspace_dir()
        try:
            probe = ws / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            self.add("Workspace", OK, str(ws))
        except OSError as exc:
            self.add("Workspace", MISSING, f"{ws} not writable: {exc}")
        self.add("Settings file", INFO, str(config.config_path()))

        self._print(plan)
        return 1 if any(s in (MISSING, FAIL) for _, s, _ in self.rows) else 0

    def _check_whisper_model(self, plan: BackendPlan) -> None:
        """The transcription model is big (large-v3-turbo ~1.6 GB): fetch it now if asked."""
        from . import models

        mlx = plan.device == "mlx"
        name = hardware.MLX_REPOS.get(plan.model, plan.model) if mlx else plan.model
        if models.is_cached(name, mlx=mlx):
            self.add("Whisper model", OK, f"{plan.model} (downloaded)")
            return
        if not (self.download_models and self.fix):
            self.add("Whisper model", INFO, f"{plan.model} - downloads on the first transcription")
            return
        console.print(f"Downloading the Whisper model [bold]{plan.model}[/] (one time, up to 1.6 GB) ...")
        try:
            (models.mlx_model_path if mlx else models.faster_whisper_model_path)(name)
            self.add("Whisper model", OK, f"{plan.model} (downloaded)")
        except Exception as exc:  # noqa: BLE001 - retried on the first transcription
            self.add("Whisper model", WARN, f"{plan.model} download failed: {str(exc)[:200]} "
                                            "(it is retried on the first transcription)")

    def _check_highlight_deps(self) -> None:
        """Optional highlight signals: missing ones are skipped, never fatal (WARN)."""
        lv = _version("librosa")
        self.add("librosa (music mode)", OK if lv else WARN,
                 lv or f"music mode chorus detection disabled - {pip_hint('librosa')}")
        from .highlights.signals import laughter

        if not laughter.sherpa_installed():
            self.add("Laughter model", WARN,
                     f"sherpa-onnx missing, signal will be skipped - {pip_hint('sherpa-onnx')}")
            return
        if not laughter.model_ready() and self.fix:
            try:
                with console.status("Downloading audio event model (47 MB, one time) ..."):
                    laughter.ensure_model(show_progress=False)
            except Exception as exc:  # noqa: BLE001
                self.add("Laughter model", WARN, f"model download failed ({exc}); signal skipped")
                return
        if laughter.model_ready():
            self.add("Laughter model", OK,
                     f"CED-mini via sherpa-onnx {_version('sherpa-onnx')} (CPU), "
                     f"{laughter.model_dir()}")
        else:
            self.add("Laughter model", WARN, "not downloaded yet; run doctor without --no-fix")

    def _check_llm(self) -> None:
        """Ollama + the local LLM. Optional: without it, analysis/titles are skipped (WARN)."""
        from . import llm

        if config.get("llm_enabled") is False:
            self.add("Local LLM", INFO, "disabled in config (llm_enabled: false)")
            return
        exe = llm.ollama_exe()
        if exe is None and self.fix:
            cmd = llm.install_command()
            if cmd:
                console.print(f"Installing Ollama (free local LLM runner): [dim]$ {' '.join(cmd)}[/]")
                subprocess.run(cmd)
                exe = llm.ollama_exe()
        if exe is None:
            self.add("Ollama", WARN, f"not installed - LLM titles/scores disabled. Install: {llm.install_hint()}")
            return
        try:
            version = llm.ensure_server()
        except Exception as exc:  # noqa: BLE001
            self.add("Ollama", WARN, f"installed ({exe}) but the server won't start: {exc}")
            return
        self.add("Ollama", OK, f"{version} ({exe})")
        model = llm.choose_model()
        if not llm.has_model(model):
            if not self.fix:
                self.add("LLM model", WARN, f"{model} not downloaded - run doctor without --no-fix")
                return
            try:
                llm.ensure_model(model)
            except Exception as exc:  # noqa: BLE001
                self.add("LLM model", WARN, f"{model} download failed: {str(exc)[:200]}")
                return
        # Real test: load, answer a JSON question, unload (the GPU is free again afterwards).
        import time

        schema = {"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"]}
        try:
            t0 = time.perf_counter()
            with llm.session(model) as m:
                load = time.perf_counter() - t0
                t1 = time.perf_counter()
                out = m.json("Answer with JSON.", "What is 17 + 25?", schema, temperature=0.1, num_predict=40)
                answer_s = time.perf_counter() - t1
            ok = out.get("answer") == 42
            where = ", ".join(llm.loaded_models()) or "unloaded after the test"
            self.add("LLM model", OK if ok else WARN,
                     f"{model}: loaded in {load:.1f}s, JSON answer in {answer_s:.1f}s"
                     + ("" if ok else f" (wrong answer {out})") + f"; {where}")
        except Exception as exc:  # noqa: BLE001
            fb = config.get("llm_fallback_model") or llm.SMALL_MODEL
            self.add("LLM model", WARN, f"{model} test failed ({str(exc)[:160]}). For weaker PCs set "
                                         f"\"llm_model\": \"{fb}\" in {config.config_path()}")

    def _check_encoder(self) -> None:
        if not shutil.which("ffmpeg"):
            return  # already reported as MISSING
        from .render import pick_encoder

        try:
            enc, notes = pick_encoder()
        except Exception as exc:  # noqa: BLE001
            self.add("Video encoder", MISSING, str(exc)[:300])
            return
        detail = f"{enc.label} ({enc.name})"
        if notes:
            detail += "  - " + "; ".join(n.split(":")[0] for n in notes)
        self.add("Video encoder", OK if enc.hardware else WARN,
                 detail if enc.hardware else detail + " - no hardware encoder, previews use the CPU")

    def _check_nvidia_libs(self) -> None:
        libs = hardware.nvidia_libs_installed()
        if not all(libs.values()) and self.fix:
            console.print("[yellow]NVIDIA GPU found but the CUDA pip libraries are missing - "
                          "installing them (one time, ~1 GB) ...[/]")
            _pip_install(GPU_FIX_PACKAGES[2:])
            importlib.invalidate_caches()
            libs = hardware.nvidia_libs_installed()
        missing = [k for k, v in libs.items() if not v]
        detail = (f"cuBLAS {_version('nvidia-cublas-cu12') or '-'}, "
                  f"cuDNN {_version('nvidia-cudnn-cu12') or '-'} (pip, no CUDA Toolkit needed)")
        self.add("CUDA libraries", MISSING if missing else OK,
                 detail if not missing else
                 f"missing {', '.join(missing)}: python -m pip install -r backend/requirements-nvidia.txt")

    def _smoke_and_plan(self, hw) -> BackendPlan:
        """Run the real smoke test on the best device; repair / fall back as needed."""
        plan = hardware.choose_plan(hw, "auto", cuda_ok=True)
        smoke_note = "(first run downloads the 75 MB 'tiny' test model)"

        if plan.device == "cuda":
            with console.status(f"GPU smoke test on {hw.best_nvidia.name} {smoke_note} ..."):
                res = smoke.run_subprocess("cuda", plan.compute_type, plan.device_index)
            self.add("CUDA available", OK if res.get("cuda_devices") else FAIL,
                     f"{res.get('cuda_devices', 0)} device(s), ctranslate2 "
                     f"{res.get('ctranslate2', _version('ctranslate2'))}")
            if not res.get("ok") and self.fix:
                console.print(f"[yellow]GPU test failed: {res.get('error')}[/]")
                console.print("[yellow]New GPUs (e.g. RTX 50 series) can need newer libraries - "
                              "upgrading ctranslate2 + NVIDIA libs and re-testing ...[/]")
                _pip_install(GPU_FIX_PACKAGES)
                with console.status("Re-testing GPU ..."):
                    res = smoke.run_subprocess("cuda", plan.compute_type, plan.device_index)
                self.notes.append("GPU libraries were upgraded automatically.")
            if res.get("ok"):
                self.add("Smoke test (GPU)", OK,
                         f"tiny model on cuda/{plan.compute_type} in {res['seconds']}s")
                fp = hardware.gpu_fingerprint(hw, res.get("ctranslate2"))
                config.update(force_cpu=False, force_cpu_reason=None, gpu_verified=fp)
            else:
                reason = (res.get("error") or "unknown error")[:300]
                # WARN, not FAIL: ClipForge still works on the CPU (tested below).
                self.add("Smoke test (GPU)", WARN, reason)
                config.update(force_cpu=True, force_cpu_reason=reason, gpu_verified=None)
                self.notes.append(
                    "The GPU could not run Whisper even after upgrading libraries, so ClipForge "
                    "will use the CPU (slower, but works). Updating your NVIDIA driver usually "
                    "fixes this; run `python cli.py doctor` again afterwards to re-enable the GPU.")
                plan = hardware.cpu_plan(hw)
        else:
            self.add("CUDA available", INFO, "no NVIDIA GPU")

        if plan.device != "cuda":
            dev, ct = ("mlx", "float16") if plan.device == "mlx" else ("cpu", "int8")
            with console.status(f"Smoke test on {dev.upper()} {smoke_note} ..."):
                res = smoke.run_subprocess(dev, ct)
            self.add(f"Smoke test ({dev.upper()})", OK if res.get("ok") else FAIL,
                     f"tiny model on {dev}/{ct} in {res.get('seconds')}s" if res.get("ok")
                     else (res.get("error") or "unknown error")[:300])
        self.add("Chosen backend", OK, f"{plan.label}  [dim]({plan.reason})[/]")
        if plan.warning:
            self.notes.append(plan.warning)
        return plan

    # ------------------------------------------------------------------ output

    def _print(self, plan: BackendPlan) -> None:
        table = Table(title="ClipForge doctor", title_style="bold", show_lines=False)
        table.add_column("Check", style="bold")
        table.add_column("Status")
        table.add_column("Details", overflow="fold")
        for check, status, detail in self.rows:
            table.add_row(check, f"[{_STYLE[status]}]{status}[/]", detail)
        console.print(table)
        for note in self.notes:
            console.print(f"[yellow]Note:[/] {note}")
        bad = [c for c, s, _ in self.rows if s in (MISSING, FAIL)]
        if bad:
            console.print(f"[bold red]Not ready:[/] fix {', '.join(bad)} (commands above).")
        else:
            console.print(f"[bold green]Ready![/] Transcription will use {plan.label}.")


def run_doctor(fix: bool = True, download_models: bool = False) -> int:
    return Doctor(fix=fix, download_models=download_models).run()
