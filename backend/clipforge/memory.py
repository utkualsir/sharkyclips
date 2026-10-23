"""Load/release heavy models so only ONE is ever on the GPU at a time.

Whisper (this phase) and a local LLM (later phases) share the same GPU. Use
`exclusive_model()` for anything big: it unloads whatever was loaded before,
and fully releases the new model when the block ends (even on errors/Ctrl+C).

    with exclusive_model("whisper", load_fn) as model:
        ...
"""

from __future__ import annotations

import gc
import sys
from contextlib import contextmanager
from typing import Any, Callable, Iterator

_current: dict[str, Any] | None = None  # {"name", "obj", "release"}


def release_model(obj: Any) -> None:
    """Free a model object and its GPU memory. Safe to call with None or twice."""
    if obj is None:
        return
    # Engines / pipelines that know how to clean up after themselves.
    close = getattr(obj, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
    # faster-whisper: BatchedInferencePipeline.model -> WhisperModel.model -> ctranslate2 Whisper
    seen: set[int] = set()
    node = obj
    for _ in range(4):
        if node is None or id(node) in seen:
            break
        seen.add(id(node))
        unload = getattr(node, "unload_model", None)
        if callable(unload):
            try:
                unload()  # ctranslate2 frees the weights from VRAM right away
            except Exception:
                pass
        node = getattr(node, "model", None)
    clear_framework_caches()
    gc.collect()


def clear_framework_caches() -> None:
    # MLX (Apple Silicon): mlx-whisper keeps the last model in a class-level holder.
    if "mlx_whisper" in sys.modules:
        try:
            from mlx_whisper.transcribe import ModelHolder

            ModelHolder.model = None
            ModelHolder.model_path = None
        except Exception:
            pass
    if "mlx.core" in sys.modules:
        try:
            import mlx.core as mx

            (getattr(mx, "clear_cache", None) or mx.metal.clear_cache)()
        except Exception:
            pass
    # PyTorch, in case a later phase uses it.
    if "torch" in sys.modules:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def release_current() -> None:
    """Unload whatever heavy model is currently registered."""
    global _current
    if _current is not None:
        entry, _current = _current, None
        entry["release"](entry["obj"])
        gc.collect()


def register(name: str, obj: Any, release: Callable[[Any], None] = release_model) -> None:
    """Mark obj as THE loaded heavy model (unloading any previous one first).

    Call release_current() before loading when possible, so two models never
    overlap in memory even briefly.
    """
    global _current
    if _current is not None and _current["obj"] is not obj:
        release_current()
    _current = {"name": name, "obj": obj, "release": release}


def current_model_name() -> str | None:
    return _current["name"] if _current else None


@contextmanager
def exclusive_model(name: str, loader: Callable[[], Any],
                    release: Callable[[Any], None] = release_model) -> Iterator[Any]:
    """Load a model as the only heavy model in memory; release it on exit."""
    global _current
    release_current()
    obj = loader()
    _current = {"name": name, "obj": obj, "release": release}
    try:
        yield obj
    finally:
        if _current is not None and _current["obj"] is obj:
            release_current()
        else:
            release(obj)
        del obj
        gc.collect()
