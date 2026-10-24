"""Check for and install a new ClipForge version (Settings -> Updates).

ClipForge is installed as a git checkout, so an update is `git pull --ff-only`
followed by `pip install -r requirements.txt` when the requirements changed.
The server then restarts itself (see `cli.py serve`, exit code RESTART_CODE).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from . import __version__
from .config import REPO_ROOT
from .errors import ClipForgeError

RESTART_CODE = 75  # `serve` restarts the server when it exits with this code
REQUIREMENTS = ("backend/requirements.txt", "backend/requirements-nvidia.txt")
RELEASES_URL = "https://github.com/utkualsir/clipforge/releases"
_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')


def _git_env() -> dict[str, str]:
    # Never wait for a password prompt in the background (the server has no terminal).
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "LC_ALL": "C"}


def git(*args: str, timeout: float = 60, root: Path = REPO_ROOT) -> str:
    exe = shutil.which("git")
    if exe is None:
        raise ClipForgeError("git isn't installed, so ClipForge can't update itself.",
                             "Run the installer again, or download the new version from " + RELEASES_URL)
    try:
        res = subprocess.run([exe, *args], cwd=root, capture_output=True, text=True, timeout=timeout,
                             env=_git_env(), encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        raise ClipForgeError(f"git {args[0]} took too long.", "Check your internet connection and try again.")
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip().splitlines()
        raise ClipForgeError(f"git {args[0]} failed: {(msg[-1] if msg else 'unknown error')[:300]}")
    return res.stdout.strip()


def parse_version(text: str) -> str | None:
    m = _VERSION_RE.search(text or "")
    return m.group(1) if m else None


def version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def _requirements_hash(root: Path = REPO_ROOT) -> str:
    h = hashlib.sha256()
    for rel in REQUIREMENTS:
        p = root / rel
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


def status(fetch: bool = True, root: Path = REPO_ROOT) -> dict:
    """Current vs. latest version. Never raises: problems come back as `reason`."""
    out: dict = {"current": __version__, "latest": None, "available": False, "behind": 0,
                 "changes": [], "supported": False, "reason": None, "releases_url": RELEASES_URL}
    if shutil.which("git") is None:
        out["reason"] = "no_git"
        return out
    if not (root / ".git").exists():
        out["reason"] = "not_git_checkout"
        return out
    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD", root=root)
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", root=root)
    except ClipForgeError:
        out["reason"] = "no_upstream"
        return out
    out.update(supported=True, branch=branch, upstream=upstream)
    if fetch:
        try:
            git("fetch", "--quiet", "--tags", root=root, timeout=90)
        except ClipForgeError as exc:
            out["reason"] = "fetch_failed"
            out["error"] = exc.message
            return out
    behind = int(git("rev-list", "--count", "HEAD..@{u}", root=root) or 0)
    out["behind"] = behind
    out["ahead"] = int(git("rev-list", "--count", "@{u}..HEAD", root=root) or 0)
    if behind:
        log = git("log", "--format=%s", "-n", "15", "HEAD..@{u}", root=root)
        out["changes"] = [line for line in log.splitlines() if line.strip()]
        try:
            out["latest"] = parse_version(git("show", "@{u}:backend/clipforge/__init__.py", root=root))
        except ClipForgeError:
            pass
    out["latest"] = out["latest"] or __version__
    out["available"] = behind > 0
    out["dirty"] = bool(git("status", "--porcelain", "--untracked-files=no", root=root))
    return out


def apply(on_stage: Callable[[str], None] | None = None, root: Path = REPO_ROOT,
          python: str = sys.executable) -> dict:
    """git pull, then reinstall Python packages if the requirements changed."""
    stage = on_stage or (lambda _s: None)
    before_rev = git("rev-parse", "HEAD", root=root)
    before_req = _requirements_hash(root)
    stage("update_download")
    try:
        git("pull", "--ff-only", "--quiet", root=root, timeout=300)
    except ClipForgeError as exc:
        raise ClipForgeError(exc.message, "Files of ClipForge were changed on this computer. Undo those "
                                          "changes (or run `git stash` in the ClipForge folder) and try again.")
    after_rev = git("rev-parse", "HEAD", root=root)
    deps = False
    if _requirements_hash(root) != before_req:
        stage("update_packages")
        files = ["-r", str(root / REQUIREMENTS[0])]
        from .hardware import nvidia_libs_installed

        if any(nvidia_libs_installed().values()):
            files += ["-r", str(root / REQUIREMENTS[1])]
        res = subprocess.run([python, "-m", "pip", "install", "--upgrade", "--quiet",
                              "--disable-pip-version-check", *files],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["unknown error"]
            raise ClipForgeError(f"Installing the new Python packages failed: {tail[0][:300]}",
                                 "Run the installer again to repair ClipForge.")
        deps = True
    try:
        new_version = parse_version((root / "backend/clipforge/__init__.py").read_text(encoding="utf-8"))
    except OSError:
        new_version = None
    return {"from": before_rev[:10], "to": after_rev[:10], "changed": before_rev != after_rev,
            "packages_updated": deps, "version": new_version or __version__, "restart_needed": True}
