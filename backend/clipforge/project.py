"""Project folders (workspace/<id>/) and meta.json helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config
from .errors import ClipForgeError

MODES = ("gaming", "study", "music")
_PARTIAL_SUFFIXES = {".part", ".ytdl", ".tmp", ".temp"}


def write_json_atomic(path: Path, data: Any) -> None:
    """Write JSON so a crash never leaves a half-written file behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_TR_MAP = str.maketrans({"ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G",
                         "ß": "ss", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE"})


def slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text.translate(_TR_MAP))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "video"


def make_project_id(title: str, source_key: str) -> str:
    """Readable, filesystem-safe and stable: same source -> same id."""
    digest = hashlib.sha1(source_key.encode("utf-8")).hexdigest()[:8]
    return f"{slugify(title)}-{digest}"


@dataclass
class Project:
    id: str
    dir: Path

    @property
    def meta_path(self) -> Path:
        return self.dir / "meta.json"

    @property
    def audio_path(self) -> Path:
        return self.dir / "audio.wav"

    @property
    def transcript_path(self) -> Path:
        return self.dir / "transcript.json"

    @property
    def cache_dir(self) -> Path:
        return self.dir / "cache"

    @property
    def source_path(self) -> Path | None:
        for p in sorted(self.dir.glob("source.*")):
            if p.is_file() and not (set(s.lower() for s in p.suffixes) & _PARTIAL_SUFFIXES):
                return p
        return None

    def load_meta(self) -> dict[str, Any]:
        if not self.meta_path.is_file():
            return {}
        return read_json(self.meta_path)

    def save_meta(self, meta: dict[str, Any]) -> None:
        write_json_atomic(self.meta_path, meta)


def project_for_id(project_id: str) -> Project:
    return Project(project_id, config.workspace_dir() / project_id)


def list_projects() -> list[Project]:
    root = config.workspace_dir()
    return [Project(p.name, p) for p in sorted(root.iterdir())
            if p.is_dir() and (p / "meta.json").is_file()]


def get_project(project_id: str) -> Project:
    """Find a project by id (a unique prefix is enough)."""
    projects = list_projects()
    exact = [p for p in projects if p.id == project_id]
    matches = exact or [p for p in projects if p.id.startswith(project_id)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        known = ", ".join(p.id for p in projects[-5:]) or "none yet"
        raise ClipForgeError(f"No project with id '{project_id}' in {config.workspace_dir()}.",
                             f"Run `python cli.py list` to see projects (recent: {known}).")
    raise ClipForgeError(f"'{project_id}' matches several projects: "
                         + ", ".join(p.id for p in matches), "Use the full id.")
