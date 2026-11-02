"""The small ONNX models of the voice pass, downloaded once into <settings>/models/voices.

All run with sherpa-onnx (already a dependency, CPU wheels for Windows / macOS / Linux, no
account or token needed):
  separator     UVR MDX-Net 9482 (MIT): voices vs. game sound / music, ~30 MB
  segmentation  pyannote segmentation 3.0 (MIT): who speaks when, ~6 MB
  embedding     WeSpeaker ResNet34 (Apache-2.0): a voice "fingerprint" per turn, ~26 MB
"""

from __future__ import annotations

import hashlib
import io
import os
import tarfile
import threading
from dataclasses import dataclass
from pathlib import Path

from ..errors import SharkyClipsError

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/"


@dataclass(frozen=True)
class Model:
    file: str
    url: str
    sha256: str  # of the model file itself
    size_mb: int
    member: str | None = None  # inside a .tar.bz2


MODELS: dict[str, Model] = {
    "separator": Model("UVR_MDXNET_9482.onnx", BASE + "source-separation-models/UVR_MDXNET_9482.onnx",
                       "9d78f8566fa8198065214ab628be1de966a500c57786695aa4b13e2b27a7727d", 30),
    "segmentation": Model("pyannote-segmentation-3.0.onnx",
                          BASE + "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2",
                          "220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079", 7,
                          member="sherpa-onnx-pyannote-segmentation-3-0/model.onnx"),
    "embedding": Model("wespeaker_en_voxceleb_resnet34_LM.onnx",
                       BASE + "speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx",
                       "e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012", 26),
}

_lock = threading.Lock()


def model_dir() -> Path:
    from .. import config

    return config.config_dir() / "models" / "voices"


def path(name: str) -> Path:
    return model_dir() / MODELS[name].file


def sherpa_ok() -> bool:
    import importlib.util

    return importlib.util.find_spec("sherpa_onnx") is not None


def available(name: str) -> bool:
    return sherpa_ok() and path(name).is_file()


def ensure(name: str) -> Path:
    """The model file, downloaded (and hash-checked) the first time."""
    m = MODELS[name]
    dest = path(name)
    with _lock:
        if dest.is_file():
            return dest
        if os.environ.get("SHARKYCLIPS_NO_DOWNLOADS"):
            raise SharkyClipsError(f"The {name} model isn't downloaded yet.")
        try:
            import requests

            r = requests.get(m.url, timeout=120)
            r.raise_for_status()
            data = r.content
        except Exception as exc:  # noqa: BLE001
            raise SharkyClipsError(f"Could not download the voice model '{name}' ({exc}).",
                                   "Check the internet connection; it's downloaded once.") from exc
        if m.member:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:bz2") as tar:
                f = tar.extractfile(m.member)  # read one member only: no paths from the archive
                if f is None:
                    raise SharkyClipsError(f"The {name} model archive is missing {m.member}.")
                data = f.read()
        if hashlib.sha256(data).hexdigest() != m.sha256:
            raise SharkyClipsError(f"The downloaded {name} model is damaged (hash mismatch).",
                                   "Try again later.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        return dest


def status() -> dict:
    return {"sherpa": sherpa_ok(),
            "models": {n: {"ready": path(n).is_file(), "size_mb": m.size_mb} for n, m in MODELS.items()}}
