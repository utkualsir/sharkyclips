"""First-run downloads (1.2.56): the big optional parts that are not in the Windows installer.

    plan()        what this PC needs, what is already there, how big it is (works offline)
    install(ids)  download + verify + install the picked parts, with progress (bytes, speed,
                  time left); every download resumes from a .part file and is checked before use

Components (picked by hardware, see `plan`):
    whisper       the transcription model for this PC (Light / CPU: small, GPU: large-v3-turbo)
    whisper_tiny  the tiny model (doctor, quick checks)
    cuda          NVIDIA CUDA libraries (cuBLAS + cuDNN 9) as pip wheels, NVIDIA GPU >= 4 GB only;
                  installed with `pip --target` into <runtime>/gpu (appinstall.gpu_dir)
    deno          yt-dlp's JavaScript runtime (full YouTube support), into <runtime>/tools/deno
    ollama        the local AI app (Windows: its official installer, run silently, per user)
    llm           the AI model for titles / viral score (pulled through Ollama, digest-checked)

Checks: Whisper files against the Hugging Face repo's LFS SHA-256 (git blob SHA-1 for the small
JSON files), CUDA wheels against PyPI's SHA-256 (from pip's own resolver report), Deno against a
pinned SHA-256, the Ollama installer against GitHub's asset digest. Sources are https only.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import appinstall, config
from .errors import SharkyClipsError
from .procs import no_window

MB = 1024 * 1024
CHUNK = 1024 * 1024
USER_AGENT = "SharkyClips-setup"

# Sizes for the plan (offline); the real size comes from the source when the download starts.
WHISPER_MB = {"tiny": 75, "base": 141, "small": 463, "medium": 1459, "large-v3-turbo": 1546, "large-v3": 2950}
WHISPER_FILES = ("config.json", "preprocessor_config.json", "model.bin", "tokenizer.json")
LLM_MB = {"qwen3.5:9b": 6247, "qwen3.5:4b": 3170, "qwen3.5:2b": 2559}
CUDA_MB = 1250
OLLAMA_MB = 1772

DENO = {"version": "2.9.8", "file": "deno-x86_64-pc-windows-msvc.zip", "size": 42917472,
        "sha256": "cba84b26e0df5ae7f74fc66b86a95b866872a86292ebd84fa1e959927edd93bf"}
DENO_URL = "https://github.com/denoland/deno/releases/download/v{version}/{file}"
OLLAMA_RELEASE_API = "https://api.github.com/repos/ollama/ollama/releases/latest"
HF_ENDPOINT = "https://huggingface.co"


# ------------------------------------------------------------------ plan


@dataclass
class Item:
    id: str
    size_mb: float
    present: bool
    selected: bool  # picked by default (the user can untick optional ones)
    optional: bool
    detail: dict = field(default_factory=dict)
    available: bool = True  # False: can't be installed here (shown as a note)

    def to_dict(self) -> dict:
        return {"id": self.id, "size_mb": round(self.size_mb), "present": self.present,
                "selected": self.selected and not self.present and self.available,
                "optional": self.optional, "available": self.available, "detail": self.detail}


def whisper_model_for_pc() -> str:
    """The model transcribe_project will load on this PC (no GPU test, nothing loaded)."""
    from . import hardware, transcribe

    hw = hardware.detect_hardware()
    cfg = config.load()
    want = str(cfg.get("transcribe_model") or "auto")
    want = want if want in hardware.MODEL_CHOICES else "auto"
    plan = hardware.choose_plan(hw, want, cuda_ok=bool(hw.best_nvidia) and not cfg.get("force_cpu"),
                                force_cpu=bool(cfg.get("force_cpu")), force_cpu_reason=cfg.get("force_cpu_reason"))
    plan = transcribe.apply_perf(plan, hw, want)
    return plan.model


def whisper_present(name: str) -> bool:
    from . import models

    return models.is_cached(name)


def cuda_present() -> bool:
    from . import hardware

    return all(hardware.nvidia_libs_installed().values())


def deno_present() -> bool:
    from .ingest import js_runtimes

    return bool(js_runtimes())


def ollama_present() -> bool:
    from . import llm

    return llm.ollama_exe() is not None


def llm_present(name: str) -> bool:
    from . import llm

    if llm.server_version(timeout=1.0) is None:
        return _ollama_manifest_exists(name)
    return llm.has_model(name)


def _ollama_manifest_exists(name: str) -> bool:
    from . import llm

    repo, _, tag = name.partition(":")
    repo = repo if "/" in repo else f"library/{repo}"
    return (llm.models_dir() / "manifests" / "registry.ollama.ai" / repo / (tag or "latest")).is_file()


def plan() -> dict:
    """What the first-run step shows. Never downloads anything, works offline."""
    from . import hardware, llm, perf

    m = perf.machine()
    k = perf.knobs(m)
    windows = os.name == "nt"
    items: list[Item] = []
    wmodel = whisper_model_for_pc()
    items.append(Item("whisper", WHISPER_MB.get(wmodel, 500), whisper_present(wmodel), True, False,
                      {"model": wmodel, "device": k["device"]}))
    if wmodel != "tiny":
        items.append(Item("whisper_tiny", WHISPER_MB["tiny"], whisper_present("tiny"), True, False, {"model": "tiny"}))
    gpu = bool(m.nvidia_vram_gb and m.nvidia_vram_gb >= 4) and k["device"] == "gpu"
    if gpu and sys.platform != "darwin":
        items.append(Item("cuda", CUDA_MB, cuda_present(), True, False, {"gpu": m.nvidia_name,
                                                                           "vram_gb": m.nvidia_vram_gb}))
    items.append(Item("deno", DENO["size"] / MB, deno_present(), True, True,
                      {"version": DENO["version"]}, available=windows or deno_present()))
    template = bool(k.get("template_titles"))
    model = llm.choose_model(ignore_fast=True)
    has_ollama = ollama_present()
    items.append(Item("ollama", OLLAMA_MB, has_ollama, not template, True, {},
                      available=windows or has_ollama))
    items.append(Item("llm", LLM_MB.get(model, 4000), llm_present(model), not template, True, {"model": model}))
    total = sum(i.size_mb for i in items if i.selected and not i.present and i.available)
    try:
        free = shutil.disk_usage(_disk_probe()).free / MB
    except OSError:
        free = None
    missing_required = [i.id for i in items if not i.optional and not i.present and i.available]
    return {"items": [i.to_dict() for i in items], "total_mb": round(total), "free_mb": None if free is None else round(free),
            "light": k["light"], "device": k["device"], "weak_reasons": perf.weak_reasons(m),
            "machine": {"ram_gb": round(m.ram_gb, 1), "threads": m.threads, "gpu": m.nvidia_name,
                        "vram_gb": m.nvidia_vram_gb, "cpu": hardware.detect_hardware().cpu_name},
            "install_kind": appinstall.kind(), "ready": not missing_required,
            "missing_required": missing_required}


def _disk_probe() -> Path:
    p = Path.home()
    return p if p.exists() else Path(tempfile.gettempdir())


def needs_setup() -> bool:
    """An installed copy whose required parts (the Whisper models, CUDA on an NVIDIA PC) aren't
    there yet: the UI offers the Downloads step (also to people who finished the onboarding)."""
    if not appinstall.is_installer():
        return False
    try:
        return not plan()["ready"]
    except Exception:  # noqa: BLE001 - never break /api/app over this
        return False


_READY: dict = {"at": 0.0, "value": None, "busy": False}
READY_TTL_S = 600


def needs_setup_cached() -> bool | None:
    """needs_setup() for /api/app, which the UI polls: computed in the background (the hardware
    check takes seconds), None until the first answer, then refreshed every 10 minutes."""
    import threading

    now = time.monotonic()
    if (_READY["value"] is None or now - _READY["at"] > READY_TTL_S) and not _READY["busy"]:
        _READY["busy"] = True

        def work() -> None:
            try:
                _READY["value"] = needs_setup()
                _READY["at"] = time.monotonic()
            finally:
                _READY["busy"] = False

        threading.Thread(target=work, name="sharkyclips-setup-check", daemon=True).start()
    return _READY["value"]


def forget_ready() -> None:
    _READY.update(at=0.0, value=None)


# ------------------------------------------------------------------ progress


class Progress:
    """Bytes of all picked downloads together -> fraction, speed (5 s window) and time left."""

    def __init__(self, items: list[dict], report: Callable[[dict], None]):
        self.items = {i["id"]: {"id": i["id"], "status": "waiting", "done": 0.0,
                                "total": float(i["size_mb"]) * MB} for i in items}
        self.report = report
        self.current: str | None = None
        self._samples: list[tuple[float, float]] = []
        self._last = 0.0

    def total(self) -> float:
        return sum(i["total"] for i in self.items.values())

    def done(self) -> float:
        return sum(min(i["done"], i["total"]) for i in self.items.values())

    def start(self, item_id: str, total: float | None = None) -> None:
        self.current = item_id
        it = self.items[item_id]
        it["status"] = "downloading"
        if total:
            it["total"] = float(total)
        self.emit(force=True)

    def set(self, item_id: str, done: float, total: float | None = None, status: str | None = None) -> None:
        it = self.items[item_id]
        it["done"] = float(done)
        if total:
            it["total"] = float(total)
        if status:
            it["status"] = status
        self.emit()

    def finish(self, item_id: str, status: str = "done") -> None:
        it = self.items[item_id]
        it["status"] = status
        if status == "done":
            it["done"] = it["total"]
        self.emit(force=True)

    def emit(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last < 0.4:
            return
        self._last = now
        done, total = self.done(), self.total()
        self._samples.append((now, done))
        self._samples = [s for s in self._samples if now - s[0] <= 5.0]
        speed = 0.0
        if len(self._samples) >= 2 and self._samples[-1][0] > self._samples[0][0]:
            speed = (self._samples[-1][1] - self._samples[0][1]) / (self._samples[-1][0] - self._samples[0][0])
        eta = (total - done) / speed if speed > 1024 else None
        self.report({"current": self.current, "done_bytes": int(done), "total_bytes": int(total),
                     "speed_bps": int(speed), "eta_s": None if eta is None else int(eta),
                     "fraction": (done / total) if total else None,
                     "items": [dict(i, done=int(i["done"]), total=int(i["total"])) for i in self.items.values()]})


# ------------------------------------------------------------------ downloads


def _session():
    import requests

    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _check_url(url: str) -> None:
    """https only. Tests serve files from 127.0.0.1 over http (SHARKYCLIPS_ALLOW_LOCAL_HTTP=1)."""
    low = url.lower()
    if low.startswith("https://"):
        return
    if os.environ.get("SHARKYCLIPS_ALLOW_LOCAL_HTTP") == "1" and low.startswith("http://127.0.0.1:"):
        return
    raise SharkyClipsError(f"Refused a download that isn't https: {url[:80]}")


def file_hash(path: Path, algo: str = "sha256", git_blob: bool = False) -> str:
    h = hashlib.new(algo)
    if git_blob:
        h.update(f"blob {path.stat().st_size}\0".encode())
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK * 4):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, *, sha256: str | None = None, sha1_blob: str | None = None,
             size: int | None = None, on_bytes: Callable[[int, int | None], None] | None = None,
             cancelled: Callable[[], bool] = lambda: False, attempts: int = 6) -> Path:
    """Resumable download to dest (via dest.part), checked before it gets its final name.
    A wrong checksum deletes the part file (a new download starts next time)."""
    import requests

    _check_url(url)
    if dest.is_file() and _hash_ok(dest, sha256, sha1_blob):
        if on_bytes:
            on_bytes(dest.stat().st_size, dest.stat().st_size)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    sess = _session()
    for attempt in range(1, attempts + 1):
        have = part.stat().st_size if part.is_file() else 0
        if size and have > size:
            part.unlink()
            have = 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with sess.get(url, headers=headers, stream=True, timeout=(15, 60), allow_redirects=True) as r:
                if r.status_code == 416 and size and have == size:
                    break  # already complete
                if r.status_code not in (200, 206):
                    raise SharkyClipsError(f"Download failed (HTTP {r.status_code}): {url.split('?')[0][-80:]}",
                                           "Check your internet connection and try again.")
                _check_url(r.url)
                if r.status_code == 200:
                    have = 0  # the server ignored the Range header: start over
                length = r.headers.get("Content-Length")
                total = size or ((int(length) + have) if length and length.isdigit() else None)
                with open(part, "ab" if have else "wb") as f:
                    for chunk in r.iter_content(CHUNK):
                        if cancelled():
                            raise _Cancelled()
                        f.write(chunk)
                        have += len(chunk)
                        if on_bytes:
                            on_bytes(have, total)
            if size is None or have >= size:
                break
        except (requests.RequestException, OSError) as exc:
            if attempt == attempts:
                raise SharkyClipsError(f"Download interrupted: {type(exc).__name__}",
                                       "Check your internet connection and press Download again: "
                                       "it continues where it stopped.") from exc
            time.sleep(min(20, 2 * attempt))
    if not _hash_ok(part, sha256, sha1_blob):
        part.unlink(missing_ok=True)
        raise SharkyClipsError(f"The downloaded file {dest.name} is damaged (checksum mismatch) and was deleted.",
                               "Press Download again to get a fresh copy.")
    os.replace(part, dest)
    return dest


def _hash_ok(path: Path, sha256: str | None, sha1_blob: str | None) -> bool:
    if sha256:
        return file_hash(path).lower() == sha256.lower()
    if sha1_blob:
        return file_hash(path, "sha1", git_blob=True).lower() == sha1_blob.lower()
    return False  # nothing to check against: never trusted as complete


class _Cancelled(Exception):
    pass


# ------------------------------------------------------------------ installers per component


def _hf_cache() -> Path:
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def install_whisper(name: str, prog: Progress, item_id: str, cancelled: Callable[[], bool]) -> None:
    """Files of the faster-whisper repo into the Hugging Face cache layout, so
    faster_whisper.utils.download_model(name, local_files_only=True) finds them offline."""
    from faster_whisper.utils import _MODELS

    if whisper_present(name):
        prog.finish(item_id, "present")
        return
    repo = _MODELS.get(name, name)
    sess = _session()
    endpoint = os.environ.get("HF_ENDPOINT") or HF_ENDPOINT
    _check_url(endpoint)
    r = sess.get(f"{endpoint}/api/models/{repo}?blobs=true", timeout=30)
    if r.status_code != 200:
        raise SharkyClipsError(f"Couldn't read the model list from Hugging Face (HTTP {r.status_code}).",
                               "Check your internet connection and try again.")
    meta = r.json()
    commit = meta["sha"]
    files = [s for s in meta.get("siblings", []) if s["rfilename"] in WHISPER_FILES
             or s["rfilename"].startswith("vocabulary")]
    if not any(s["rfilename"] == "model.bin" for s in files):
        raise SharkyClipsError(f"The model repository {repo} has no model.bin.")
    total = sum(int(s.get("size") or (s.get("lfs") or {}).get("size") or 0) for s in files)
    prog.start(item_id, total)
    base = _hf_cache() / ("models--" + repo.replace("/", "--"))
    snap = base / "snapshots" / commit
    done_before = 0
    for s in files:
        lfs = s.get("lfs") or {}
        blob_name = lfs.get("sha256") or s.get("blobId")
        blob = base / "blobs" / blob_name
        fsize = int(s.get("size") or lfs.get("size") or 0) or None

        def on_bytes(n: int, _t: int | None, _base: int = done_before) -> None:
            prog.set(item_id, _base + n)

        download(f"{endpoint}/{repo}/resolve/{commit}/{s['rfilename']}", blob,
                 sha256=lfs.get("sha256"), sha1_blob=None if lfs else s.get("blobId"),
                 size=fsize, on_bytes=on_bytes, cancelled=cancelled)
        done_before += fsize or blob.stat().st_size
        target = snap / s["rfilename"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            try:
                os.link(blob, target)  # no extra disk space
            except OSError:
                shutil.copyfile(blob, target)
    (base / "refs").mkdir(parents=True, exist_ok=True)
    (base / "refs" / "main").write_text(commit, encoding="utf-8")
    if not whisper_present(name):
        raise SharkyClipsError(f"The Whisper model '{name}' was downloaded but can't be loaded.")
    prog.finish(item_id)


def install_deno(prog: Progress, item_id: str, cancelled: Callable[[], bool]) -> None:
    if deno_present():
        prog.finish(item_id, "present")
        return
    if os.name != "nt":
        raise SharkyClipsError("Deno is downloaded automatically on Windows only.",
                               "Install it with your package manager (macOS: brew install deno).")
    prog.start(item_id, DENO["size"])
    dl = appinstall.updates_dir().parent / "downloads"
    z = download(DENO_URL.format(**DENO), dl / DENO["file"], sha256=DENO["sha256"], size=DENO["size"],
                 on_bytes=lambda n, _t: prog.set(item_id, n), cancelled=cancelled)
    prog.set(item_id, DENO["size"], status="installing")
    out = appinstall.tools_dir() / "deno"
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        member = next((n for n in zf.namelist() if n.lower().endswith("deno.exe")), None)
        if member is None:
            raise SharkyClipsError("The Deno download has no deno.exe.")
        tmp = out / "deno.exe.new"
        with zf.open(member) as src, open(tmp, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.replace(tmp, out / "deno.exe")
    z.unlink(missing_ok=True)
    appinstall.setup_paths()
    prog.finish(item_id)


def _pip_report(requirements: Path) -> list[dict]:
    """pip's own resolver says which wheels (url + sha256) requirements-nvidia.txt needs."""
    with tempfile.TemporaryDirectory(prefix="sc-pip-") as tmp:
        report = Path(tmp) / "report.json"
        cmd = [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed", "--quiet",
               "--disable-pip-version-check", "--only-binary=:all:", "--report", str(report),
               "-r", str(requirements)]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=300, **no_window())
        if res.returncode != 0 or not report.is_file():
            tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["unknown error"]
            raise SharkyClipsError(f"Couldn't look up the GPU libraries: {tail[0][:300]}",
                                   "Check your internet connection and try again.")
        data = json.loads(report.read_text(encoding="utf-8"))
    out = []
    for it in data.get("install", []):
        info = it.get("download_info") or {}
        url = info.get("url") or ""
        sha = ((info.get("archive_info") or {}).get("hashes") or {}).get("sha256")
        if not sha:
            h = (info.get("archive_info") or {}).get("hash") or ""
            sha = h.split("=", 1)[1] if h.startswith("sha256=") else None
        if not url or not sha:
            raise SharkyClipsError("A GPU library has no checksum on PyPI; nothing was installed.")
        out.append({"name": it.get("metadata", {}).get("name"), "url": url, "sha256": sha,
                    "file": url.rsplit("/", 1)[-1].split("#")[0]})
    return out


def install_cuda(prog: Progress, item_id: str, cancelled: Callable[[], bool]) -> None:
    if cuda_present():
        prog.finish(item_id, "present")
        return
    req = config.REPO_ROOT / "backend" / "requirements-nvidia.txt"
    wheels = _pip_report(req)
    sess = _session()
    sizes = []
    for w in wheels:
        try:
            h = sess.head(w["url"], timeout=30, allow_redirects=True)
            sizes.append(int(h.headers.get("Content-Length") or 0) or None)
        except Exception:  # noqa: BLE001
            sizes.append(None)
    total = sum(s or 0 for s in sizes) or None
    prog.start(item_id, total)
    dl = appinstall.updates_dir().parent / "downloads" / "gpu"
    files: list[Path] = []
    before = 0
    for w, size in zip(wheels, sizes):
        def on_bytes(n: int, _t: int | None, _b: int = before) -> None:
            prog.set(item_id, _b + n)

        files.append(download(w["url"], dl / w["file"], sha256=w["sha256"], size=size,
                              on_bytes=on_bytes, cancelled=cancelled))
        before += size or files[-1].stat().st_size
    prog.set(item_id, before, status="installing")
    target = appinstall.gpu_dir()
    new = target.with_name(target.name + ".new")
    shutil.rmtree(new, ignore_errors=True)
    res = subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--no-index", "--quiet",
                          "--disable-pip-version-check", "--target", str(new), *map(str, files)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                         **no_window())
    if res.returncode != 0:
        tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["unknown error"]
        shutil.rmtree(new, ignore_errors=True)
        raise SharkyClipsError(f"Installing the GPU libraries failed: {tail[0][:300]}")
    old = target.with_name(target.name + ".old")
    shutil.rmtree(old, ignore_errors=True)
    if target.exists():
        os.replace(target, old)
    os.replace(new, target)
    shutil.rmtree(old, ignore_errors=True)
    shutil.rmtree(dl, ignore_errors=True)
    appinstall.setup_paths()
    prog.finish(item_id)


def _ollama_asset() -> dict:
    sess = _session()
    r = sess.get(OLLAMA_RELEASE_API, timeout=30, headers={"Accept": "application/vnd.github+json"})
    if r.status_code != 200:
        raise SharkyClipsError(f"Couldn't read Ollama's latest release (HTTP {r.status_code}).",
                               "Try again later, or install Ollama yourself from https://ollama.com/download.")
    rel = r.json()
    for a in rel.get("assets", []):
        if a.get("name") == "OllamaSetup.exe":
            digest = str(a.get("digest") or "")
            if not digest.startswith("sha256:"):
                raise SharkyClipsError("Ollama's installer has no checksum on GitHub; nothing was downloaded.",
                                       "Install Ollama yourself from https://ollama.com/download.")
            return {"url": a["browser_download_url"], "size": int(a["size"]), "sha256": digest[7:],
                    "version": rel.get("tag_name")}
    raise SharkyClipsError("Ollama's latest release has no Windows installer.",
                           "Install Ollama yourself from https://ollama.com/download.")


def install_ollama(prog: Progress, item_id: str, cancelled: Callable[[], bool]) -> None:
    if ollama_present():
        prog.finish(item_id, "present")
        return
    if os.name != "nt":
        raise SharkyClipsError("Ollama is installed automatically on Windows only.",
                               "Install it from https://ollama.com/download.")
    asset = _ollama_asset()
    prog.start(item_id, asset["size"])
    dl = appinstall.updates_dir().parent / "downloads"
    exe = download(asset["url"], dl / "OllamaSetup.exe", sha256=asset["sha256"], size=asset["size"],
                   on_bytes=lambda n, _t: prog.set(item_id, n), cancelled=cancelled)
    prog.set(item_id, asset["size"], status="installing")
    # Ollama's own installer (Inno Setup): per user, no admin, no window.
    res = subprocess.run([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
                         timeout=1200, **no_window())
    if res.returncode != 0 or not ollama_present():
        raise SharkyClipsError(f"Ollama's installer failed (exit code {res.returncode}).",
                               "Install Ollama yourself from https://ollama.com/download, then press Download again.")
    _park_ollama_autostart()
    exe.unlink(missing_ok=True)
    prog.finish(item_id)


def _park_ollama_autostart() -> None:
    """Ollama's installer makes it start with Windows; SharkyClips starts it when needed
    (config ollama_autostart, same as install.ps1)."""
    if config.get("ollama_autostart") or os.name != "nt":
        return
    startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    lnk = startup / "Ollama.lnk"
    if lnk.is_file():
        parked = config.config_dir() / "parked-startup"
        parked.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(lnk, parked / "Ollama.lnk")
        except OSError:
            pass


def install_llm(name: str, prog: Progress, item_id: str, cancelled: Callable[[], bool]) -> None:
    from . import llm

    llm.ensure_server()
    if llm.has_model(name):
        prog.finish(item_id, "present")
        return
    total = LLM_MB.get(name, 4000) * MB
    prog.start(item_id, total)

    def cb(_status: str, frac: float | None) -> None:
        if cancelled():
            raise _Cancelled()
        if frac is not None:
            prog.set(item_id, frac * total)

    llm.pull_model(name, cb)
    prog.finish(item_id)


# ------------------------------------------------------------------ run


def install(ids: list[str], report: Callable[[dict], None], cancelled: Callable[[], bool] = lambda: False) -> dict:
    """Install the picked components in a safe order. One failure doesn't stop the others;
    the result lists what worked and what didn't (the step can be run again: it resumes)."""
    p = plan()
    by_id = {i["id"]: i for i in p["items"]}
    order = ["cuda", "whisper_tiny", "whisper", "deno", "ollama", "llm"]
    picked = [by_id[i] for i in order if i in ids and i in by_id and by_id[i]["available"]]
    prog = Progress(picked, report)
    results: dict[str, dict] = {}
    for it in picked:
        iid = it["id"]
        if cancelled():
            break
        if it["present"]:
            prog.finish(iid, "present")
            results[iid] = {"ok": True, "present": True}
            continue
        if iid == "llm" and not ollama_present():
            prog.finish(iid, "skipped")
            results[iid] = {"ok": False, "error": "Ollama isn't installed."}
            continue
        try:
            if iid in ("whisper", "whisper_tiny"):
                install_whisper(it["detail"]["model"], prog, iid, cancelled)
            elif iid == "cuda":
                install_cuda(prog, iid, cancelled)
            elif iid == "deno":
                install_deno(prog, iid, cancelled)
            elif iid == "ollama":
                install_ollama(prog, iid, cancelled)
            elif iid == "llm":
                install_llm(it["detail"]["model"], prog, iid, cancelled)
            results[iid] = {"ok": True}
        except _Cancelled:
            prog.finish(iid, "cancelled")
            results[iid] = {"ok": False, "cancelled": True}
            break
        except SharkyClipsError as exc:
            prog.finish(iid, "error")
            results[iid] = {"ok": False, "error": exc.message, "hint": exc.hint}
        except Exception as exc:  # noqa: BLE001 - one part failing must not hide the others
            prog.finish(iid, "error")
            results[iid] = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    if any(r.get("ok") for r in results.values()):
        config.update(setup_downloads_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    return {"results": results, "ok": all(r.get("ok") for r in results.values()),
            "cancelled": any(r.get("cancelled") for r in results.values())}
