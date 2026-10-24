"""Local LLM through Ollama (free, runs on this computer).

* The model is picked by hardware (config `llm_model`: "auto" or an Ollama tag):
  8 GB+ VRAM (or Apple Silicon with 16 GB+) -> qwen3.5:9b, otherwise qwen3.5:4b.
* Answers use Ollama's structured output (a JSON schema). Every answer is validated
  here as well and the request is retried with the problems listed when it's wrong.
* GPU sharing: the LLM is registered with memory.exclusive_model, so Whisper and the
  LLM are never loaded at the same time. When a batch ends the model is unloaded
  (keep_alive 0) so the GPU is free again.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from . import config, hardware, memory
from .errors import ClipForgeError
from .ui import console

DEFAULT_MODEL = "qwen3.5:9b"
SMALL_MODEL = "qwen3.5:4b"
MODEL_SIZES_GB = {"qwen3.5:9b": 6.6, "qwen3.5:4b": 3.3, "qwen3:8b": 5.2, "qwen3:4b": 2.5}
BATCH_KEEP_ALIVE = "10m"  # while a batch runs; unloaded explicitly afterwards


def base_url() -> str:
    return str(config.get("ollama_url") or "http://127.0.0.1:11434").rstrip("/")


def _http():
    import requests

    return requests


# ------------------------------------------------------------------ install / server


def ollama_exe() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    candidates = []
    if os.name == "nt":
        candidates.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe")
    elif platform.system() == "Darwin":
        candidates += [Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                       Path("/opt/homebrew/bin/ollama"), Path("/usr/local/bin/ollama")]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def install_command() -> list[str] | None:
    if os.name == "nt" and shutil.which("winget"):
        return ["winget", "install", "--id", "Ollama.Ollama", "-e", "--silent",
                "--accept-source-agreements", "--accept-package-agreements"]
    if platform.system() == "Darwin" and shutil.which("brew"):
        return ["brew", "install", "ollama"]
    return None


def install_hint() -> str:
    if os.name == "nt":
        return "winget install --id Ollama.Ollama -e   (or https://ollama.com/download)"
    if platform.system() == "Darwin":
        return "brew install ollama   (or https://ollama.com/download)"
    return "curl -fsSL https://ollama.com/install.sh | sh"


def server_version(timeout: float = 2.0) -> str | None:
    try:
        r = _http().get(f"{base_url()}/api/version", timeout=timeout)
        return r.json().get("version") if r.ok else None
    except Exception:
        return None


def ensure_server(start_timeout: float = 30.0) -> str:
    """Make sure the Ollama server answers; start `ollama serve` if needed."""
    v = server_version()
    if v:
        return v
    exe = ollama_exe()
    if exe is None:
        raise ClipForgeError("Ollama (the free local LLM runner) is not installed.",
                             f"Run `python cli.py doctor` or install it: {install_hint()}")
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, creationflags=flags, start_new_session=os.name != "nt")
    t0 = time.time()
    while time.time() - t0 < start_timeout:
        time.sleep(0.5)
        v = server_version()
        if v:
            return v
    raise ClipForgeError("Ollama is installed but its server didn't start.",
                         "Start the Ollama app once, or run `ollama serve` in a terminal.")


# ------------------------------------------------------------------ models


def fast_analysis() -> bool:
    return bool(config.get("fast_analysis"))


def fast_model() -> str:
    return str(config.get("llm_fallback_model") or SMALL_MODEL)


def choose_model(ignore_fast: bool = False) -> str:
    """config llm_model ("auto" = by hardware); "Fast analysis" always uses the small model."""
    if fast_analysis() and not ignore_fast:
        return fast_model()
    wanted = str(config.get("llm_model") or "auto")
    if wanted != "auto":
        return wanted
    hw = hardware.detect_hardware()
    gpu = hw.best_nvidia
    if gpu and gpu.vram_gb >= 7.5:
        return DEFAULT_MODEL
    if hw.apple_silicon and hw.ram_total_gb >= 15:
        return DEFAULT_MODEL
    return str(config.get("llm_fallback_model") or SMALL_MODEL)


def installed_models() -> list[str]:
    try:
        r = _http().get(f"{base_url()}/api/tags", timeout=10)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def has_model(name: str) -> bool:
    names = installed_models()
    return name in names or (":" not in name and f"{name}:latest" in names)


def pull_model(name: str, on_progress: Callable[[str, float | None], None] | None = None,
               attempts: int = 6) -> None:
    """Download a model. Network hiccups are retried; Ollama resumes partial downloads."""
    for attempt in range(1, attempts + 1):
        try:
            return _pull_once(name, on_progress)
        except ClipForgeError as exc:
            transient = any(k in exc.message.lower() for k in
                            ("max retries", "timeout", "connect", "reset", "eof", "tls", "temporarily"))
            if not transient or attempt == attempts:
                raise
            if attempt >= 2 and _is_local_server():
                # Ollama's own downloader keeps failing (seen with broken IPv6): fetch the
                # files ourselves over IPv4 from the same registry.
                console.print("[yellow]Ollama's download keeps failing; downloading the model "
                              "files directly instead ...[/]")
                return direct_pull(name, on_progress)
            console.print(f"[yellow]Download interrupted ({attempt}/{attempts}), resuming ...[/]")
            time.sleep(min(30, 3 * attempt))
        except OSError as exc:  # requests connection errors
            if attempt == attempts:
                raise ClipForgeError(f"Couldn't reach Ollama to download '{name}': {exc}") from exc
            time.sleep(3 * attempt)


def _is_local_server() -> bool:
    return any(h in base_url() for h in ("127.0.0.1", "localhost", "[::1]"))


def models_dir() -> Path:
    env = os.environ.get("OLLAMA_MODELS")
    return Path(env).expanduser() if env else Path.home() / ".ollama" / "models"


@contextmanager
def _ipv4_only() -> Iterator[None]:
    """Make `requests` connect over IPv4 (some networks have IPv6 that never answers)."""
    import socket

    import urllib3.util.connection as conn

    old = conn.allowed_gai_family
    conn.allowed_gai_family = lambda: socket.AF_INET
    try:
        yield
    finally:
        conn.allowed_gai_family = old


def direct_pull(name: str, on_progress: Callable[[str, float | None], None] | None = None) -> None:
    """Download a model from registry.ollama.ai into Ollama's model folder (resumable,
    sha256-verified). Ollama picks it up without a restart."""
    import hashlib

    requests = _http()
    model, _, tag = name.partition(":")
    tag = tag or "latest"
    repo = model if "/" in model else f"library/{model}"
    reg = "https://registry.ollama.ai/v2"
    root = models_dir()
    blobs = root / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    with _ipv4_only(), requests.Session() as http:
        r = http.get(f"{reg}/{repo}/manifests/{tag}", timeout=30,
                     headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"})
        if not r.ok:
            raise ClipForgeError(f"Model '{name}' not found in the Ollama registry ({r.status_code}).")
        manifest = r.json()
        layers = [manifest["config"], *manifest["layers"]]
        total = sum(int(x["size"]) for x in layers)
        done = 0
        for layer in layers:
            digest, size = layer["digest"], int(layer["size"])
            dest = blobs / digest.replace(":", "-")
            if dest.is_file() and dest.stat().st_size == size:
                done += size
                continue
            part = dest.with_name(dest.name + "-clipforge-partial")
            for attempt in range(8):
                have = part.stat().st_size if part.is_file() else 0
                headers = {"Range": f"bytes={have}-"} if have else {}
                try:
                    with http.get(f"{reg}/{repo}/blobs/{digest}", headers=headers, stream=True,
                                  timeout=(15, 60)) as resp:
                        if resp.status_code not in (200, 206):
                            raise OSError(f"HTTP {resp.status_code}")
                        if resp.status_code == 200:
                            have = 0
                        with open(part, "ab" if have else "wb") as f:
                            for chunk in resp.iter_content(1 << 20):
                                f.write(chunk)
                                have += len(chunk)
                                if on_progress:
                                    on_progress(f"downloading {digest[7:19]}", (done + have) / total)
                    break
                except (OSError, requests.RequestException) as exc:
                    if attempt == 7:
                        raise ClipForgeError(f"Model download failed: {exc}",
                                             "Check your internet connection and run it again; "
                                             "the download resumes.") from exc
                    time.sleep(2 + 2 * attempt)
            h = hashlib.sha256()
            with open(part, "rb") as f:
                while chunk := f.read(8 << 20):
                    h.update(chunk)
            if "sha256:" + h.hexdigest() != digest:
                part.unlink(missing_ok=True)
                raise ClipForgeError(f"Downloaded file for '{name}' is corrupt (checksum mismatch).",
                                     "Run the command again to re-download it.")
            part.replace(dest)
            done += size
        mdir = root / "manifests" / "registry.ollama.ai" / repo
        mdir.mkdir(parents=True, exist_ok=True)
        (mdir / tag).write_text(json.dumps(manifest), encoding="utf-8")
    if on_progress:
        on_progress("success", 1.0)
    if not has_model(name):
        raise ClipForgeError(f"Downloaded '{name}' but Ollama doesn't list it.",
                             "Restart Ollama (quit it from the tray) and try again.")


def _pull_once(name: str, on_progress: Callable[[str, float | None], None] | None) -> None:
    with _http().post(f"{base_url()}/api/pull", json={"model": name, "stream": True},
                      stream=True, timeout=(10, 600)) as r:
        if not r.ok:
            raise ClipForgeError(f"Ollama couldn't download '{name}': {r.text[:300]}")
        for line in r.iter_lines():
            if not line:
                continue
            msg = json.loads(line)
            if msg.get("error"):
                raise ClipForgeError(f"Ollama couldn't download '{name}': {msg['error']}",
                                     "Check the model name and your internet connection.")
            if on_progress:
                total, done = msg.get("total"), msg.get("completed")
                on_progress(msg.get("status", ""), (done / total) if total and done is not None else None)


def ensure_model(name: str) -> None:
    if has_model(name):
        return
    from .ui import download_progress

    size = MODEL_SIZES_GB.get(name)
    console.print(f"Downloading LLM [bold]{name}[/]" + (f" (~{size} GB, one time)" if size else "") + " ...")
    with download_progress() as prog:
        task = prog.add_task("Downloading LLM", total=100)

        def cb(status: str, frac: float | None) -> None:
            if frac is not None:
                prog.update(task, completed=frac * 100)

        pull_model(name, cb)
        prog.update(task, completed=100)


def loaded_models() -> list[str]:
    try:
        r = _http().get(f"{base_url()}/api/ps", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def gpu_share(name: str) -> float | None:
    """Part of a loaded model that sits in GPU memory (1.0 = fully on the GPU)."""
    try:
        r = _http().get(f"{base_url()}/api/ps", timeout=3)
        for m in r.json().get("models", []):
            if m.get("name") == name and m.get("size"):
                return float(m.get("size_vram", 0)) / float(m["size"])
    except Exception:
        pass
    return None


def unload(name: str) -> None:
    try:
        _http().post(f"{base_url()}/api/generate", json={"model": name, "keep_alive": 0}, timeout=30)
    except Exception:
        pass


def unload_all() -> None:
    """Free the GPU from any Ollama model (called before Whisper loads). Cheap if none."""
    if not server_version(timeout=0.5):
        return
    for name in loaded_models():
        unload(name)


# ------------------------------------------------------------------ validation


def validate(value: Any, schema: dict, path: str = "$") -> list[str]:
    """Small JSON-schema subset validator (type, enum, min/max, lengths, required)."""
    errs: list[str] = []
    t = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool,
             "integer": int, "number": (int, float)}
    if t and not isinstance(value, types[t]) or (t in ("integer", "number") and isinstance(value, bool)):
        return [f"{path} must be {t}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path} must be one of {schema['enum']}")
    if t in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path} must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path} must be <= {schema['maximum']}")
    if t == "string":
        if len(value.strip()) < schema.get("minLength", 0):
            errs.append(f"{path} is too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errs.append(f"{path} is longer than {schema['maxLength']} characters")
    if t == "array":
        if len(value) < schema.get("minItems", 0):
            errs.append(f"{path} needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errs.append(f"{path} has more than {schema['maxItems']} items")
        for i, item in enumerate(value):
            errs += validate(item, schema.get("items", {}), f"{path}[{i}]")
    if t == "object":
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}.{k} is missing")
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                errs += validate(value[k], sub, f"{path}.{k}")
    return errs


# ------------------------------------------------------------------ session


class LLM:
    """One loaded Ollama model. Use through `session()`."""

    def __init__(self, model: str, num_ctx: int):
        self.model = model
        self.num_ctx = num_ctx
        self.calls = 0
        self.seconds = 0.0
        self.retries = 0
        self.tokens_out = 0
        self.gen_seconds = 0.0  # pure generation time, for tokens/second

    def warm_up(self) -> None:
        t0 = time.perf_counter()
        r = _http().post(f"{base_url()}/api/generate",
                         json={"model": self.model, "prompt": "", "keep_alive": BATCH_KEEP_ALIVE,
                               "options": {"num_ctx": self.num_ctx}}, timeout=600)
        if not r.ok:
            raise ClipForgeError(f"Ollama couldn't load '{self.model}': {r.text[:300]}",
                                 "Run `python cli.py doctor`.")
        self.load_seconds = time.perf_counter() - t0

    def json(self, system: str, prompt: str, schema: dict, *, temperature: float = 0.6,
             retries: int = 3, check: Callable[[dict], list[str]] | None = None,
             soft: Callable[[dict], list[str]] | None = None, num_predict: int = 1800) -> dict:
        """Ask for JSON that matches `schema` (+ optional extra `check`). Retries on bad output.

        `soft` problems are asked to be fixed too, but when the retries run out an answer
        with only soft problems is still returned (listed in data["_soft_errors"])."""
        best_soft: dict | None = None
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        last_errors: list[str] = []
        for attempt in range(retries + 1):
            t0 = time.perf_counter()
            body = {"model": self.model, "messages": messages, "format": schema, "stream": False,
                    "think": False, "keep_alive": BATCH_KEEP_ALIVE,
                    "options": {"temperature": max(0.1, temperature - 0.15 * attempt),
                                "num_ctx": self.num_ctx, "num_predict": num_predict}}
            r = _http().post(f"{base_url()}/api/chat", json=body, timeout=600)
            self.calls += 1
            self.seconds += time.perf_counter() - t0
            if not r.ok:
                raise ClipForgeError(f"Ollama error: {r.text[:300]}")
            resp = r.json()
            self.tokens_out += int(resp.get("eval_count") or 0)
            self.gen_seconds += (resp.get("eval_duration") or 0) / 1e9
            content = resp.get("message", {}).get("content", "")
            soft_errors: list[str] = []
            try:
                data = json.loads(content)
                last_errors = validate(data, schema)
                if not last_errors:
                    last_errors = check(data) if check else []
                    soft_errors = soft(data) if soft and not last_errors else []
            except json.JSONDecodeError as exc:
                data, last_errors = None, [f"not valid JSON ({exc.msg})"]
            if not last_errors and not soft_errors:
                return data
            if not last_errors and (best_soft is None or len(soft_errors) < len(best_soft["_soft_errors"])):
                best_soft = {**data, "_soft_errors": soft_errors}
            if best_soft is not None and attempt >= 1:
                return best_soft  # soft problems get one retry; the caller cleans up the rest
            last_errors = last_errors + soft_errors
            self.retries += 1
            messages = messages[:2] + [
                {"role": "assistant", "content": content[:4000]},
                {"role": "user", "content": "Your answer has problems:\n- " + "\n- ".join(last_errors[:12])
                 + "\nAnswer again with the complete corrected JSON."}]
        if best_soft is not None:
            return best_soft
        raise ClipForgeError(f"The LLM kept giving invalid answers: {'; '.join(last_errors[:5])}",
                             "Try again, or set a different `llm_model` in the config.")


    @property
    def tokens_per_second(self) -> float:
        return self.tokens_out / self.gen_seconds if self.gen_seconds else 0.0


def _release(llm: LLM) -> None:
    unload(llm.model)


@contextmanager
def session(model: str | None = None) -> Iterator[LLM]:
    """Load the LLM as the only heavy model (Whisper is unloaded first); unload it afterwards."""
    ensure_server()
    name = model or choose_model()
    ensure_model(name)
    num_ctx = int(config.get("llm_num_ctx") or 8192)

    def load() -> LLM:
        llm = LLM(name, num_ctx)
        console.print(f"Loading LLM [bold]{name}[/] ...")
        llm.warm_up()
        share = gpu_share(name)
        if share is not None and share < 0.8 and (hardware.detect_hardware().best_nvidia
                                                   or hardware.detect_hardware().apple_silicon):
            console.print(f"[yellow]Only {share:.0%} of the LLM fits on the GPU (other apps are using "
                          f"its memory), so it runs slower. Close GPU-heavy apps or set "
                          f'"llm_model": "{config.get("llm_fallback_model") or SMALL_MODEL}".[/]')
        return llm

    with memory.exclusive_model(f"llm:{name}", load, release=_release) as llm:
        yield llm


class LazyLLM:
    """Like session(), but the model is only loaded when the first question is asked
    (a run where every answer is cached never touches the GPU)."""

    def __init__(self, model: str):
        from contextlib import ExitStack

        self.model = model
        self._stack = ExitStack()
        self._llm: LLM | None = None

    def _get(self) -> LLM:
        if self._llm is None:
            self._llm = self._stack.enter_context(session(self.model))
        return self._llm

    def json(self, *args, **kwargs) -> dict:
        return self._get().json(*args, **kwargs)

    def __getattr__(self, name: str):  # calls, retries, seconds, tokens_per_second, load_seconds
        if self._llm is None:
            return 0
        return getattr(self._llm, name)

    def close(self) -> None:
        self._stack.close()


@contextmanager
def lazy_session(model: str | None = None) -> Iterator[LazyLLM]:
    lz = LazyLLM(model or choose_model())
    try:
        yield lz
    finally:
        lz.close()
