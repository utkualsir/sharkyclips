"""Multilingual transcription with word-level timestamps.

Long streams (3-6 h) are split into ~10 minute chunks, cut at the quietest
moment near each boundary. Only one chunk is in memory at a time, and every
finished chunk is saved to workspace/<id>/cache/, so an interrupted run
resumes where it stopped and re-runs skip finished work.

Backends (picked by hardware.py):
  * faster-whisper on CUDA (batched) or CPU (int8)
  * mlx-whisper on Apple Silicon
"""

from __future__ import annotations

import bisect
import contextlib
import gc
import importlib.metadata
import shutil
import time
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from . import audio, config, governor, hardware, languages, memory
from .errors import SharkyClipsError, pip_hint
from .hardware import MLX_REPOS, MODEL_FALLBACK, BackendPlan, HardwareInfo
from .models import faster_whisper_model_path, is_cached, mlx_model_path
from .project import Project, read_json, write_json_atomic
from .ui import console, fmt_time, time_progress

CHUNK_SECONDS = 600.0
TRANSCRIPT_VERSION = 1
ProgressFn = Callable[[float], None]


@dataclass
class ChunkResult:
    segments: list[dict]
    language: str | None
    language_probability: float | None


# ---------------------------------------------------------------------- engines


def _pick_cuda_compute(wanted: str, device_index: int) -> str:
    import ctranslate2

    supported = set(ctranslate2.get_supported_compute_types("cuda", device_index))
    if wanted in supported:
        return wanted
    for alt in ("int8_float16", "float16", "int8_float32", "int8", "float32"):
        if alt in supported:
            return alt
    return wanted


class FasterWhisperEngine:
    def __init__(self, plan: BackendPlan):
        if plan.device == "cuda":
            hardware.setup_cuda_dlls()
        from faster_whisper import BatchedInferencePipeline, WhisperModel

        compute = plan.compute_type
        if plan.device == "cuda":
            compute = _pick_cuda_compute(compute, plan.device_index)
        self.plan = replace(plan, compute_type=compute)
        self.model = WhisperModel(
            faster_whisper_model_path(plan.model), device=plan.device, device_index=plan.device_index,
            compute_type=compute, cpu_threads=plan.cpu_threads or 0,
        )
        self.pipeline = BatchedInferencePipeline(self.model) if plan.batch_size > 1 else None

    def transcribe(self, samples: np.ndarray, language: str | None,
                   on_progress: ProgressFn) -> ChunkResult:
        common = dict(language=language, task="transcribe", word_timestamps=True,
                      vad_filter=True, beam_size=self.plan.beam_size,
                      condition_on_previous_text=False,
                      language_detection_segments=3)
        if self.pipeline is not None:
            segments, info = self.pipeline.transcribe(samples, batch_size=self.plan.batch_size,
                                                      **common)
        else:
            segments, info = self.model.transcribe(
                samples, vad_parameters={"min_silence_duration_ms": 500}, **common)
        out = []
        for seg in segments:  # lazy generator: the real work happens here
            out.append({
                "start": seg.start, "end": seg.end, "text": seg.text.strip(),
                "avg_logprob": round(seg.avg_logprob, 4),
                "no_speech_prob": round(seg.no_speech_prob, 4),
                "words": [{"start": w.start, "end": w.end, "word": w.word,
                           "probability": round(w.probability, 4)} for w in (seg.words or [])],
            })
            on_progress(seg.end)
        return ChunkResult(out, info.language, info.language_probability)

    def close(self) -> None:
        if self.model is not None:
            try:
                self.model.model.unload_model()
            except Exception:
                pass
        self.pipeline = None
        self.model = None
        gc.collect()


class MlxWhisperEngine:
    """Apple Silicon backend. Silero VAD (from faster-whisper) removes silence first."""

    def __init__(self, plan: BackendPlan):
        import mlx_whisper  # noqa: F401  (fails early with a clear error if missing)

        self.plan = plan
        self.repo = mlx_model_path(MLX_REPOS[plan.model])

    @staticmethod
    def _speech_only(samples: np.ndarray) -> tuple[np.ndarray, list[int], list[int]]:
        try:
            from faster_whisper.vad import VadOptions, get_speech_timestamps

            regions = get_speech_timestamps(samples, VadOptions(min_silence_duration_ms=500))
        except Exception:
            regions = [{"start": 0, "end": len(samples)}]
        if not regions:
            return np.zeros(0, dtype=np.float32), [], []
        parts, concat_starts, orig_starts, pos = [], [], [], 0
        for r in regions:
            parts.append(samples[r["start"]:r["end"]])
            concat_starts.append(pos)
            orig_starts.append(r["start"])
            pos += r["end"] - r["start"]
        return np.concatenate(parts), concat_starts, orig_starts

    def transcribe(self, samples: np.ndarray, language: str | None,
                   on_progress: ProgressFn) -> ChunkResult:
        import mlx_whisper

        speech, concat_starts, orig_starts = self._speech_only(samples)
        if len(speech) < audio.SAMPLE_RATE // 2:
            return ChunkResult([], None, None)

        def remap(t: float) -> float:
            s = t * audio.SAMPLE_RATE
            i = max(0, bisect.bisect_right(concat_starts, s) - 1)
            return (orig_starts[i] + (s - concat_starts[i])) / audio.SAMPLE_RATE

        result = mlx_whisper.transcribe(
            speech, path_or_hf_repo=self.repo, language=language, word_timestamps=True,
            condition_on_previous_text=False, verbose=None,
        )
        out = []
        for seg in result.get("segments", []):
            out.append({
                "start": remap(seg["start"]), "end": remap(seg["end"]),
                "text": seg["text"].strip(),
                "avg_logprob": round(seg.get("avg_logprob", 0.0), 4),
                "no_speech_prob": round(seg.get("no_speech_prob", 0.0), 4),
                "words": [{"start": remap(w["start"]), "end": remap(w["end"]), "word": w["word"],
                           "probability": round(w.get("probability", 0.0), 4)}
                          for w in seg.get("words", [])],
            })
            on_progress(out[-1]["end"])
        return ChunkResult(out, result.get("language"), None)

    def close(self) -> None:
        memory.clear_framework_caches()


def _load_engine(plan: BackendPlan):
    try:
        if plan.backend == "mlx-whisper":
            return MlxWhisperEngine(plan)
        return FasterWhisperEngine(plan)
    except ImportError as exc:
        pkg = "mlx-whisper" if plan.backend == "mlx-whisper" else "faster-whisper"
        raise SharkyClipsError(f"{pkg} is not installed ({exc}).", pip_hint(pkg)) from exc


# --------------------------------------------------------------- fallbacks


def _is_resource_error(exc: BaseException) -> bool:
    if isinstance(exc, MemoryError):
        return True
    text = str(exc).lower()
    return isinstance(exc, (RuntimeError, OSError, ValueError)) and any(
        k in text for k in ("out of memory", "cuda", "cudnn", "cublas", "alloc", "metal",
                            "insufficient memory"))


def _is_download_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    text = str(exc).lower()
    return name in ("LocalEntryNotFoundError", "HfHubHTTPError", "RepositoryNotFoundError") or (
        "huggingface" in text and ("connect" in text or "offline" in text))


def fallback_chain(plan: BackendPlan, hw: HardwareInfo) -> list[BackendPlan]:
    """The plan, then progressively lighter alternatives to try if it doesn't fit."""
    chain = [plan]
    if plan.device == "cuda":
        half = max(1, plan.batch_size // 2)
        if plan.compute_type == "float16":
            chain.append(replace(plan, compute_type="int8_float16", batch_size=half))
        m = MODEL_FALLBACK.get(plan.model)
        while m:
            chain.append(replace(plan, model=m, compute_type="int8_float16", batch_size=half))
            m = MODEL_FALLBACK.get(m)
        chain.append(hardware.cpu_plan(hw, warning="GPU could not run Whisper - using CPU."))
    else:
        m = MODEL_FALLBACK.get(plan.model)
        while m:
            chain.append(replace(plan, model=m))
            m = MODEL_FALLBACK.get(m)
    return chain


# Rough VRAM need of each setup (weights + work memory), measured on CUDA with faster-whisper.
WHISPER_VRAM_MB = {("large-v3", "float16"): 4300, ("large-v3", "int8_float16"): 2500,
                   ("large-v3-turbo", "float16"): 2600, ("large-v3-turbo", "int8_float16"): 1500,
                   ("medium", "float16"): 2400, ("medium", "int8_float16"): 1300,
                   ("small", "float16"): 1000, ("small", "int8_float16"): 700}


def _vram_need(p: BackendPlan) -> float:
    return WHISPER_VRAM_MB.get((p.model, p.compute_type), 2600) + 60 * p.batch_size


def fit_to_budget(plan: BackendPlan, hw: HardwareInfo, budget_mb: float | None,
                  cpu_threads: int | None = None) -> BackendPlan:
    """The first setup in the fallback chain that leaves the governor's VRAM headroom free
    (games / browser keep their memory). None = no budget known."""
    if plan.device == "cpu" and cpu_threads:
        return replace(plan, cpu_threads=min(plan.cpu_threads or cpu_threads, cpu_threads))
    if plan.device != "cuda" or budget_mb is None or _vram_need(plan) <= budget_mb:
        return plan
    for cand in fallback_chain(plan, hw)[1:]:
        if cand.device == "cpu":
            return replace(cand, cpu_threads=cpu_threads or cand.cpu_threads,
                           warning=f"Only {budget_mb:.0f} MB of GPU memory is free for SharkyClips "
                                   "(other apps use the rest) - transcribing on the CPU.")
        if _vram_need(cand) <= budget_mb:
            return replace(cand, reason=f"{plan.reason}; {cand.model} {cand.compute_type} fits the "
                                        f"free GPU memory ({budget_mb:.0f} MB)")
    return plan


def _load_from(chain: list[BackendPlan], start: int):
    """Load the first plan in chain[start:] that works. Returns (engine, index)."""
    last_exc: BaseException | None = None
    for i in range(start, len(chain)):
        p = chain[i]
        memory.release_current()
        from .llm import unload_all

        unload_all()  # an LLM loaded by another SharkyClips process must not share the GPU either
        console.print(f"Loading model [bold]{p.model}[/] ({p.label}) ...")
        mlx = p.backend == "mlx-whisper"
        if not is_cached(MLX_REPOS[p.model] if mlx else p.model, mlx=mlx):
            size = {"large-v3": "3.1 GB", "large-v3-turbo": "1.6 GB", "medium": "1.5 GB", "small": "0.5 GB"}.get(p.model, "")
            console.print(f"[dim]First use downloads the model ({size}); it's cached afterwards.[/]")
        try:
            engine = _load_engine(p)
            memory.register("whisper", engine)
            return engine, i
        except SharkyClipsError:
            raise
        except Exception as exc:  # noqa: BLE001
            if _is_download_error(exc):
                raise SharkyClipsError(
                    f"Could not download Whisper model '{p.model}': {exc}",
                    "Check your internet connection. Models are downloaded once and then cached "
                    "in ~/.cache/huggingface.") from exc
            if not _is_resource_error(exc):
                raise
            last_exc = exc
            console.print(f"[yellow]Couldn't load {p.label}: {str(exc)[:200]}[/]")
    raise SharkyClipsError(f"No Whisper model could be loaded: {last_exc}",
                           "Run `python cli.py doctor` to diagnose.")


# ------------------------------------------------------------------- chunks


def plan_chunks(audio_path: Path, duration: float) -> list[list[float]]:
    bounds = [0.0]
    while duration - bounds[-1] > CHUNK_SECONDS * 1.25:
        bounds.append(audio.quietest_point(audio_path, bounds[-1] + CHUNK_SECONDS))
    bounds.append(round(duration, 3))
    return [[a, b] for a, b in zip(bounds[:-1], bounds[1:])]


def _load_chunk_plan(cache: Path, audio_path: Path, duration: float) -> list[list[float]]:
    plan_file = cache / "chunks.json"
    size = audio_path.stat().st_size
    if plan_file.is_file():
        data = read_json(plan_file)
        if data.get("audio_size") == size and data.get("chunk_seconds") == CHUNK_SECONDS:
            return data["chunks"]
    chunks = plan_chunks(audio_path, duration)
    write_json_atomic(plan_file, {"audio_size": size, "chunk_seconds": CHUNK_SECONDS,
                                  "chunks": chunks})
    return chunks


def _shift(seg: dict, offset: float) -> dict:
    seg = dict(seg)
    seg["start"] = round(seg["start"] + offset, 3)
    seg["end"] = round(seg["end"] + offset, 3)
    seg["words"] = [{**w, "start": round(w["start"] + offset, 3), "end": round(w["end"] + offset, 3)}
                    for w in seg["words"]]
    return seg


# --------------------------------------------------------------------- main


def _verify_gpu_once(hw: HardwareInfo, plan: BackendPlan) -> BackendPlan:
    """Before the first CUDA run on this setup, do the quick smoke test in a subprocess
    (a broken CUDA install can crash the process, so never test in-process)."""
    from . import smoke

    try:
        ct2 = importlib.metadata.version("ctranslate2")
    except importlib.metadata.PackageNotFoundError:
        ct2 = None
    fp = hardware.gpu_fingerprint(hw, ct2)
    if config.get("gpu_verified") == fp:
        return plan
    console.print("Checking the GPU once with a quick test ...")
    res = smoke.run_subprocess("cuda", plan.compute_type, plan.device_index)
    if res.get("ok"):
        config.update(gpu_verified=fp, force_cpu=False, force_cpu_reason=None)
        return plan
    reason = res.get("error") or "unknown error"
    return hardware.cpu_plan(hw, warning=(
        f"GPU test failed ({reason[:200]}). Using CPU for now. "
        "Run `python cli.py doctor` - it can repair the GPU libraries automatically."))


def load_whisper(model: str = "auto"):
    """A Whisper engine picked like transcribe_project does (hardware, GPU check, governor's
    VRAM budget, LLM unloaded first). The caller releases it with memory.release_current().
    model "check": the full large-v3 (not turbo) on a GPU with 6 GB+, for the swear check's
    second pass; elsewhere (CPU, small GPU, short VRAM budget) the normal model."""
    hw = hardware.detect_hardware()
    cfg = config.load()
    cuda_ok = bool(hw.best_nvidia) and not cfg.get("force_cpu") and hardware.cuda_device_count() > 0
    check = model == "check"
    plan = hardware.choose_plan(hw, "auto" if check else model, cuda_ok=cuda_ok,
                                force_cpu=bool(cfg.get("force_cpu")), force_cpu_reason=cfg.get("force_cpu_reason"))
    if check and plan.device in ("cuda", "mlx") and (hw.best_nvidia is None or hw.best_nvidia.vram_gb >= 6):
        compute = plan.compute_type if plan.device == "mlx" else (
            "float16" if hw.best_nvidia and hw.best_nvidia.vram_gb >= 8 else "int8_float16")
        plan = replace(plan, model="large-v3", compute_type=compute, batch_size=1,
                       reason=plan.reason + "; swear check -> large-v3")
    if plan.device == "cuda":
        plan = _verify_gpu_once(hw, plan)
    if governor.get() is not None:
        from .llm import unload_all

        unload_all()
        governor.get().tick()
        plan = fit_to_budget(plan, hw, governor.vram_budget_mb(), governor.cpu_threads())
    engine, _i = _load_from(fallback_chain(plan, hw), 0)
    return engine


def transcribe_short(engine, samples: np.ndarray, language: str | None, hotwords: str | None = None,
                     vad: bool = False) -> list[dict]:
    """Segments of a short piece (a speaker turn, a word window): no VAD, no batching, so quiet
    speech isn't thrown away. hotwords bias the decoder (faster-whisper only)."""
    if isinstance(engine, MlxWhisperEngine):
        import mlx_whisper

        res = mlx_whisper.transcribe(samples, path_or_hf_repo=engine.repo, language=language,
                                     word_timestamps=True, condition_on_previous_text=False, verbose=None,
                                     initial_prompt=hotwords)
        segs = res.get("segments", [])
        return [{"start": s["start"], "end": s["end"], "text": s["text"].strip(),
                 "avg_logprob": s.get("avg_logprob", 0.0), "no_speech_prob": s.get("no_speech_prob", 0.0),
                 "compression_ratio": s.get("compression_ratio", 1.0),
                 "words": [{"start": w["start"], "end": w["end"], "word": w["word"],
                            "probability": w.get("probability", 0.0)} for w in s.get("words", [])]}
                for s in segs]
    model = engine.model
    segments, _info = model.transcribe(samples, language=language, task="transcribe", word_timestamps=True,
                                       vad_filter=vad, beam_size=5, condition_on_previous_text=False,
                                       hotwords=hotwords or None, no_speech_threshold=0.75)
    out = []
    for seg in segments:
        out.append({"start": seg.start, "end": seg.end, "text": seg.text.strip(),
                    "avg_logprob": seg.avg_logprob, "no_speech_prob": seg.no_speech_prob,
                    "compression_ratio": seg.compression_ratio,
                    "words": [{"start": w.start, "end": w.end, "word": w.word, "probability": w.probability}
                              for w in (seg.words or [])]})
    return out


def check_model_ready() -> bool:
    """The swear check's large-v3 is downloaded (renders never wait for a 3 GB download)."""
    try:
        hw = hardware.detect_hardware()
        mlx = bool(hw.apple_silicon and not hw.rosetta)
        return is_cached(MLX_REPOS["large-v3"] if mlx else "large-v3", mlx=mlx)
    except Exception:  # noqa: BLE001
        return False


def transcribe_check(engine, samples: np.ndarray, language: str | None, prompt: str | None = None,
                     temperature: float = 0.0, hotwords: str | None = None) -> list[dict]:
    """One decoding pass of a short window for the swear check: no VAD (quiet bursts stay),
    beam search at temperature 0 (sampling with best-of-5 above), an optional initial prompt
    (the swear words of the language), no fallback and no silence skipping."""
    if isinstance(engine, MlxWhisperEngine):
        import mlx_whisper

        res = mlx_whisper.transcribe(samples, path_or_hf_repo=engine.repo, language=language,
                                     word_timestamps=True, condition_on_previous_text=False, verbose=None,
                                     initial_prompt=prompt, temperature=temperature, no_speech_threshold=None)
        segs = res.get("segments", [])
        return [{"start": s["start"], "end": s["end"], "text": s["text"].strip(),
                 "avg_logprob": s.get("avg_logprob", 0.0), "no_speech_prob": s.get("no_speech_prob", 0.0),
                 "compression_ratio": s.get("compression_ratio", 1.0),
                 "words": [{"start": w["start"], "end": w["end"], "word": w["word"],
                            "probability": w.get("probability", 0.0)} for w in s.get("words", [])]}
                for s in segs]
    segments, _info = engine.model.transcribe(
        samples, language=language, task="transcribe", word_timestamps=True, vad_filter=False,
        beam_size=5, best_of=5, temperature=[float(temperature)], condition_on_previous_text=False,
        initial_prompt=prompt or None, hotwords=hotwords or None, no_speech_threshold=None,
        log_prob_threshold=None, compression_ratio_threshold=None)
    out = []
    for seg in segments:
        out.append({"start": seg.start, "end": seg.end, "text": seg.text.strip(),
                    "avg_logprob": seg.avg_logprob, "no_speech_prob": seg.no_speech_prob,
                    "compression_ratio": seg.compression_ratio,
                    "words": [{"start": w.start, "end": w.end, "word": w.word, "probability": w.probability}
                              for w in (seg.words or [])]})
    return out


def transcribe_project(project: Project, lang: str = "auto", model: str = "auto",
                       force: bool = False) -> dict:
    if lang != languages.AUTO:
        languages.require(lang)
    meta = project.load_meta()
    if not project.audio_path.is_file() or not audio.wav_is_valid(project.audio_path):
        src = project.source_path
        if src is None:
            raise SharkyClipsError(f"Project '{project.id}' has no audio.wav and no source video.",
                                   "Re-run: python cli.py ingest <url-or-path>")
        console.print("audio.wav missing - extracting it again ...")
        audio.extract_audio(src, project.audio_path)
    duration = audio.wav_duration(project.audio_path)

    # Already done with the same settings?
    if project.transcript_path.is_file() and not force:
        old = project.load_transcript()
        if (old.get("request", {}).get("language") == lang
                and old.get("request", {}).get("model") == model):
            console.print(f"[green]Already transcribed[/] ({old.get('model')}, "
                          f"language={old.get('language')}). Use --force to redo it.")
            return old

    hw = hardware.detect_hardware()
    cfg = config.load()
    cuda_ok = bool(hw.best_nvidia) and not cfg.get("force_cpu") and hardware.cuda_device_count() > 0
    plan = hardware.choose_plan(hw, model, cuda_ok=cuda_ok, force_cpu=bool(cfg.get("force_cpu")),
                                force_cpu_reason=cfg.get("force_cpu_reason"))
    if plan.device == "cuda":
        plan = _verify_gpu_once(hw, plan)
    if governor.get() is not None:
        from .llm import unload_all

        unload_all()  # our own LLM must not count as "used by other apps"
        governor.get().tick()
        plan = fit_to_budget(plan, hw, governor.vram_budget_mb(), governor.cpu_threads())
    if plan.warning:
        console.print(f"[yellow]{plan.warning}[/]")
    console.print(f"Backend: [bold]{plan.label}[/]  [dim]({plan.reason})[/]")

    cache = project.cache_dir / "transcribe" / f"{plan.model}-{lang}"
    if force and cache.exists():
        shutil.rmtree(cache)
    cache.mkdir(parents=True, exist_ok=True)
    chunks = _load_chunk_plan(cache, project.audio_path, duration)
    state_file = cache / "state.json"
    state = read_json(state_file) if state_file.is_file() else {}
    locked = lang if lang != languages.AUTO else state.get("language")

    chain = fallback_chain(plan, hw)
    chain_idx = 0
    engine = None
    run_start = time.perf_counter()
    processed_audio = 0.0
    vram_before = hardware.gpu_memory_used_mb(plan.device_index) if plan.device == "cuda" else None

    def free_model() -> None:  # the governor pauses: give the GPU memory back while waiting
        nonlocal engine
        memory.release_current()
        engine = None
        gc.collect()

    on_gpu = plan.device != "cpu"
    try:
        with time_progress() as prog:
            task = prog.add_task("Transcribing", total=duration)
            for i, (c_start, c_end) in enumerate(chunks):
                chunk_file = cache / f"chunk_{i:04d}.json"
                if chunk_file.is_file():
                    prog.update(task, completed=c_end)
                    continue
                # Safe point between chunks: a pause unloads the model first (reloaded below).
                if governor.checkpoint(release=free_model if on_gpu else None) and engine is None:
                    console.print("[dim]Resuming transcription ...[/]")
                if engine is None:
                    prog.stop()
                    engine, chain_idx = _load_from(chain, 0)
                    prog.start()
                    prog.reset(task, completed=c_start)  # ETA from real work only
                samples = audio.read_wav_segment(project.audio_path, c_start, c_end)
                t0 = time.perf_counter()
                while True:
                    try:
                        # On the GPU a chunk runs to its end (pausing mid-chunk would keep the
                        # model in VRAM); progress updates still throttle.
                        with governor.deferred() if on_gpu else contextlib.nullcontext():
                            res = engine.transcribe(
                                samples, locked,
                                lambda t, s=c_start: prog.update(task, completed=min(s + t, c_end)))
                        break
                    except Exception as exc:  # noqa: BLE001
                        if not _is_resource_error(exc) or chain_idx + 1 >= len(chain):
                            raise
                        prog.stop()
                        console.print(f"[yellow]Out of resources on {chain[chain_idx].label} "
                                      f"({str(exc)[:150]}); trying a lighter setup ...[/]")
                        engine, chain_idx = _load_from(chain, chain_idx + 1)
                        prog.start()
                elapsed = time.perf_counter() - t0
                del samples
                used = engine.plan
                write_json_atomic(chunk_file, {
                    "index": i, "start": c_start, "end": c_end,
                    "model": used.model, "backend": used.backend, "device": used.device,
                    "compute_type": used.compute_type, "elapsed": round(elapsed, 2),
                    "language": res.language, "language_probability": res.language_probability,
                    "segments": [_shift(s, c_start) for s in res.segments],
                })
                processed_audio += c_end - c_start
                if locked is None and res.segments and res.language and (
                        res.language_probability is None or res.language_probability >= 0.5):
                    locked = res.language
                    write_json_atomic(state_file, {"language": locked,
                                                   "probability": res.language_probability})
                prog.update(task, completed=c_end)
    finally:
        memory.release_current()  # model fully out of (GPU) memory before we return
        engine = None
        gc.collect()

    run_elapsed = time.perf_counter() - run_start
    transcript = _assemble(project, cache, chunks, lang, model, locked, duration)
    transcript["timing"]["this_run_seconds"] = round(run_elapsed, 2)
    transcript["timing"]["this_run_audio_seconds"] = round(processed_audio, 2)
    from .textutil import clean_transcript

    clean_transcript(transcript)  # no endless "Zzzz..." words
    write_json_atomic(project.transcript_path, transcript)

    meta["transcript"] = {"file": project.transcript_path.name, "language": transcript["language"],
                          "model": transcript["model"], "segments": transcript["stats"]["segments"],
                          "words": transcript["stats"]["words"]}
    project.save_meta(meta)

    if plan.device == "cuda":
        after = hardware.gpu_memory_used_mb(plan.device_index)
        if after is not None:
            console.print(f"[dim]Whisper unloaded from the GPU: {after} MB VRAM in use now "
                          f"({vram_before} MB before loading).[/]")
    return transcript


def _assemble(project: Project, cache: Path, chunks: list, lang: str, model: str,
              locked: str | None, duration: float) -> dict:
    segments, models, votes = [], Counter(), Counter()
    compute_seconds = 0.0
    last: dict = {}
    for i in range(len(chunks)):
        data = read_json(cache / f"chunk_{i:04d}.json")
        last = data
        compute_seconds += data.get("elapsed", 0)
        models[f"{data['model']} ({data['backend']}, {data['device']}, {data['compute_type']})"] += 1
        for seg in data["segments"]:
            seg = {"id": len(segments), **seg}
            segments.append(seg)
            if data.get("language"):
                votes[data["language"]] += len(seg["words"]) or 1
    language = locked or (votes.most_common(1)[0][0] if votes else None)
    reg = languages.from_whisper_code(language)
    probs = [read_json(cache / "state.json").get("probability")] if (cache / "state.json").is_file() else []
    word_count = sum(len(s["words"]) for s in segments)
    return {
        "version": TRANSCRIPT_VERSION,
        "project_id": project.id,
        "request": {"language": lang, "model": model},
        "language": language,
        "language_name": reg.english_name if reg else None,
        "language_native_name": reg.native_name if reg else None,
        "language_supported": reg is not None,
        "language_probability": probs[0] if probs else None,
        "is_rtl": bool(reg and reg.is_rtl),
        "model": last.get("model"),
        "backend": last.get("backend"),
        "device": last.get("device"),
        "compute_type": last.get("compute_type"),
        "models_used": dict(models),
        "duration": round(duration, 3),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timing": {"compute_seconds": round(compute_seconds, 2),
                   "realtime_factor": round(duration / compute_seconds, 1) if compute_seconds else None},
        "stats": {"segments": len(segments), "words": word_count, "chunks": len(chunks)},
        "segments": segments,
    }


def summary_line(t: dict) -> str:
    rtf = t["timing"].get("realtime_factor")
    return (f"segments: {t['stats']['segments']}, words: {t['stats']['words']}, language="
            f"{t['language']} ({t.get('language_name') or 'not in SharkyClips list'}), "
            f"{fmt_time(t['duration'])} of audio in {fmt_time(t['timing']['compute_seconds'])}"
            + (f" ({rtf}x realtime)" if rtf else ""))
