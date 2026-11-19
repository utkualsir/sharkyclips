"""Check for and install a new SharkyClips version (Settings -> Updates).

SharkyClips is installed as a git checkout, so an update is `git pull --ff-only`
followed by `pip install -r requirements.txt` when the requirements changed.
The server then restarts itself (see `cli.py serve`, exit code RESTART_CODE).

1.2.51 rules (the "updated to 1.2.49, but the old 1.2.50 is still running" bug):
  * an update is offered only when the remote VERSION is a HIGHER semver than the running one
    (`is_newer`); same or lower = nothing to do, whatever the commit count says
  * `apply` refuses a lower remote version before pulling, and puts the old commit back if a
    pull ever ends on a lower VERSION: going back to an older SharkyClips is impossible
  * "restart needed" is decided by the server itself: the version this Python process loaded
    vs. the VERSION file on disk now (`restart_state`), never by a version baked into the UI

1.2.52 supply-chain rules:
  * only the official repository (OFFICIAL_REPO, over https / ssh to github.com) and branch
    (OFFICIAL_BRANCH) are updated from; any other `origin` (a fork, a planted remote) gets
    reason "unofficial_remote" and nothing is fetched or applied. Forks set
    SHARKYCLIPS_UPDATE_REPO / SHARKYCLIPS_UPDATE_BRANCH to their own.
  * only a RELEASE is installed: the commit of the tag v<remote VERSION>, which must lie on the
    official branch. `git merge --ff-only <that commit>` instead of `git pull`, so what was
    checked is exactly what gets installed (a commit pushed in between is never picked up).
  * Settings key "update_require_signed": true also needs `git verify-tag` to pass (a signed tag).
  * git itself checks every object's hash, and the transport is https to github.com.

1.2.56 installed copies (the Windows installer, appinstall.is_installer()):
  * the latest GitHub release of the official repository (api.github.com, https only) with a tag
    v<semver> strictly higher than the running version, carrying SharkyClips-Setup-<v>.exe and
    SharkyClips-Setup-<v>.exe.sha256
  * download with resume into %LOCALAPPDATA%/SharkyClips/updates; the SHA-256 must match the .sha256
    file AND GitHub's own asset digest; a signed file must have a valid Authenticode signature, and
    with "update_require_signed" an unsigned one is refused
  * the web layer runs it silently once no job is queued or running (web/app.py); the installer
    closes SharkyClips, installs over it, refuses older versions itself and starts SharkyClips again
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
from .errors import SharkyClipsError
from .procs import no_window

RESTART_CODE = 75  # `serve` restarts the server when it exits with this code
REQUIREMENTS = ("backend/requirements.txt", "backend/requirements-nvidia.txt")
RELEASES_URL = "https://github.com/utkualsir/sharkyclips/releases"
OFFICIAL_REPO = "github.com/utkualsir/sharkyclips"
OFFICIAL_BRANCH = "main"
_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')


def _git_env() -> dict[str, str]:
    # Never wait for a password prompt in the background (the server has no terminal).
    return {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "LC_ALL": "C"}


def _norm_remote(url: str) -> str:
    u = (url or "").strip().replace("\\", "/")
    u = re.sub(r"^(?:https?|ssh|git)://(?:[^@/]+@)?", "", u, flags=re.I)
    u = re.sub(r"^git@([^:/]+):", r"\1/", u, flags=re.I)
    u = re.sub(r"\.git/?$", "", u.rstrip("/"))
    return u.rstrip("/").lower()


def official_remote(root: Path = REPO_ROOT) -> str | None:
    """None when `origin` / the upstream branch are the official ones, else why not."""
    want_repo = _norm_remote(os.environ.get("SHARKYCLIPS_UPDATE_REPO") or OFFICIAL_REPO)
    want_branch = os.environ.get("SHARKYCLIPS_UPDATE_BRANCH") or OFFICIAL_BRANCH
    try:
        url = git("remote", "get-url", "origin", root=root)
        upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", root=root)
    except SharkyClipsError:
        return "no_upstream"
    if _norm_remote(url) != want_repo:
        return "unofficial_remote"
    if upstream != f"origin/{want_branch}":
        return "unofficial_branch"
    return None


def release_commit(version: str, root: Path = REPO_ROOT) -> str | None:
    """The commit of the release tag v<version> if it lies on the upstream branch (else None)."""
    try:
        sha = git("rev-parse", "--verify", "--quiet", f"refs/tags/v{version}^{{commit}}", root=root)
    except SharkyClipsError:
        return None
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha or ""):
        return None
    try:
        git("merge-base", "--is-ancestor", sha, "@{u}", root=root)
    except SharkyClipsError:
        return None  # a tag that isn't on the official branch
    return sha


def _signed_ok(version: str, root: Path) -> bool:
    from . import config

    if config.get("update_require_signed") is not True:
        return True
    try:
        git("verify-tag", f"v{version}", root=root)
        return True
    except SharkyClipsError:
        return False


def git(*args: str, timeout: float = 60, root: Path = REPO_ROOT) -> str:
    exe = shutil.which("git")
    if exe is None:
        raise SharkyClipsError("git isn't installed, so SharkyClips can't update itself.",
                               "Run the installer again, or download the new version from " + RELEASES_URL)
    try:
        res = subprocess.run([exe, *args], cwd=root, capture_output=True, text=True, timeout=timeout,
                             env=_git_env(), encoding="utf-8", errors="replace", **no_window())
    except subprocess.TimeoutExpired:
        raise SharkyClipsError(f"git {args[0]} took too long.", "Check your internet connection and try again.")
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip().splitlines()
        raise SharkyClipsError(f"git {args[0]} failed: {(msg[-1] if msg else 'unknown error')[:300]}")
    return res.stdout.strip()


def parse_version(text: str) -> str | None:
    """A VERSION file ("1.2.1") or an old __init__.py line (__version__ = "1.2.0")."""
    text = (text or "").strip()
    if re.fullmatch(r"\d+(\.\d+){1,3}([-+.\w]*)", text):
        return text
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


# Where a checkout keeps its version: VERSION (1.2.1+), older releases in the package.
VERSION_FILES = ("VERSION", "backend/sharkyclips/__init__.py", "backend/clipforge/__init__.py")


def version_tuple(v: str | None) -> tuple[int, ...]:
    """Version parts as numbers, (1, 2, 10) for 1.2.10, so 1.2.10 > 1.2.9 (never a string compare)."""
    nums = [int(x) for x in re.findall(r"\d+", str(v or ""))[:3]]
    return tuple(nums + [0] * (3 - len(nums))) if nums else (0, 0, 0)


def is_newer(candidate: str | None, current: str | None) -> bool:
    """True only when `candidate` is a strictly higher version than `current`."""
    if not candidate:
        return False
    return version_tuple(candidate) > version_tuple(current)


def disk_version(root: Path = REPO_ROOT) -> str | None:
    """The version of the files on disk right now (an update changes it under a running server)."""
    for rel in VERSION_FILES:
        try:
            v = parse_version((root / rel).read_text(encoding="utf-8"))
        except OSError:
            continue
        if v:
            return v
    return None


def restart_state(running: str = __version__, root: Path = REPO_ROOT) -> dict:
    """Does this server run older code than the files on disk? Only a HIGHER disk version asks
    for a restart; an equal or lower one never does (no loop, no downgrade)."""
    disk = disk_version(root)
    return {"running": running, "disk": disk, "restart_needed": is_newer(disk, running)}


STALE_LOCK_S = 10 * 60


def clean_stale_state(root: Path = REPO_ROOT) -> list[str]:
    """Left-overs of an update that died half-way: git lock files older than 10 minutes (a
    crashed `git pull` leaves them and every later update fails on them). Returns what went."""
    import time

    gone = []
    gitdir = root / ".git"
    if not gitdir.is_dir():
        return gone
    for rel in ("index.lock", "HEAD.lock", "ORIG_HEAD.lock", "FETCH_HEAD.lock", "shallow.lock"):
        f = gitdir / rel
        try:
            if f.is_file() and time.time() - f.stat().st_mtime > STALE_LOCK_S:
                f.unlink()
                gone.append(rel)
        except OSError:
            pass
    return gone


def _requirements_hash(root: Path = REPO_ROOT) -> str:
    h = hashlib.sha256()
    for rel in REQUIREMENTS:
        p = root / rel
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


# ------------------------------------------------------------------ installed copies (1.2.56)

RELEASE_API = "https://api.github.com/repos/utkualsir/sharkyclips/releases/latest"
SETUP_NAME = "SharkyClips-Setup-{version}.exe"
_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


def _release_api() -> str:
    from .components import _check_url

    url = os.environ.get("SHARKYCLIPS_UPDATE_API") or RELEASE_API  # tests: a local fake GitHub
    _check_url(url)
    return url


def latest_release() -> dict:
    """{"version", "setup": {name, url, size, digest}, "sha256_url", "notes", "url"}; raises."""
    import requests

    try:
        r = requests.get(_release_api(), timeout=30, headers={"Accept": "application/vnd.github+json",
                                                              "User-Agent": "SharkyClips-updater"})
    except requests.RequestException as exc:
        raise SharkyClipsError(f"Couldn't reach GitHub: {type(exc).__name__}",
                               "Check your internet connection and try again.") from exc
    if r.status_code == 404:
        raise SharkyClipsError("No published release was found on GitHub.", f"See {RELEASES_URL}.")
    if r.status_code != 200:
        raise SharkyClipsError(f"GitHub answered HTTP {r.status_code}.", "Try again in a few minutes.")
    rel = r.json()
    m = _TAG_RE.match(str(rel.get("tag_name") or ""))
    if not m or rel.get("draft") or rel.get("prerelease"):
        raise SharkyClipsError("The latest release has no version tag.", f"See {RELEASES_URL}.")
    version = m.group(1)
    want = SETUP_NAME.format(version=version)
    assets = {a.get("name"): a for a in rel.get("assets", [])}
    setup, sums = assets.get(want), assets.get(want + ".sha256")
    out = {"version": version, "notes": str(rel.get("body") or ""), "url": rel.get("html_url") or RELEASES_URL,
           "setup": None, "sha256_url": None}
    if setup and sums:
        out["setup"] = {"name": want, "url": setup.get("browser_download_url"), "size": int(setup.get("size") or 0),
                        "digest": str(setup.get("digest") or "")}
        out["sha256_url"] = sums.get("browser_download_url")
    return out


def _installer_status() -> dict:
    out: dict = {"current": __version__, "latest": None, "available": False, "behind": 0, "changes": [],
                 "supported": True, "reason": None, "releases_url": RELEASES_URL, "kind": "installer"}
    try:
        rel = latest_release()
    except SharkyClipsError as exc:
        out.update(reason="fetch_failed", error=exc.message)
        return out
    out["latest"] = rel["version"]
    out["changes"] = [ln.strip().lstrip("-*").strip() for ln in rel["notes"].splitlines()
                      if ln.strip().startswith(("-", "*"))][:15]
    if not is_newer(rel["version"], __version__):
        out["reason"] = None if rel["version"] == __version__ else "not_newer"
        return out
    if rel["setup"] is None:
        out["reason"] = "not_released"  # tagged, but CI hasn't attached the installer yet
        return out
    out.update(available=True, behind=1, size=rel["setup"]["size"])
    return out


def parse_sha256_file(text: str, name: str) -> str | None:
    for line in (text or "").splitlines():
        parts = line.strip().split()
        if parts and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            if len(parts) == 1 or parts[-1].lstrip("*") == name:
                return parts[0].lower()
    return None


def authenticode(path: Path) -> dict:
    """{"status": "Valid" | "NotSigned" | "HashMismatch" | ..., "signer": ...} (Windows only)."""
    if os.name != "nt":
        return {"status": "Unsupported"}
    script = ("$s = Get-AuthenticodeSignature -LiteralPath $env:SC_FILE; "
              "$s.Status.ToString(); if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { '' }")
    try:
        res = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=60, env={**os.environ, "SC_FILE": str(path)},
                             **no_window())
        lines = (res.stdout or "").strip().splitlines()
        return {"status": lines[0].strip() if lines else "Unknown",
                "signer": lines[1].strip() if len(lines) > 1 else ""}
    except (OSError, subprocess.SubprocessError):
        return {"status": "Unknown"}


SIGNATURE_OK = ("Valid", "NotSigned", "Unsupported", "Unknown")


def _installer_apply(on_stage: Callable[[str], None]) -> dict:
    import requests

    from . import appinstall, components, config
    from .components import _check_url

    rel = latest_release()
    if not is_newer(rel["version"], __version__):
        raise SharkyClipsError(f"The version on GitHub ({rel['version']}) isn't newer than this one ({__version__}).",
                               "SharkyClips never goes back to an older version. Nothing was changed.")
    if rel["setup"] is None:
        raise SharkyClipsError("The new version's installer isn't on GitHub yet.", "Try again in a few minutes.")
    setup = rel["setup"]
    on_stage("update_download")
    try:
        _check_url(rel["sha256_url"] or "")
        sums = requests.get(rel["sha256_url"], timeout=30, headers={"User-Agent": "SharkyClips-updater"})
        sums.raise_for_status()
    except requests.RequestException as exc:
        raise SharkyClipsError("Couldn't download the installer's checksum file.", "Try again later.") from exc
    want = parse_sha256_file(sums.text, setup["name"])
    if not want:
        raise SharkyClipsError("The installer's checksum file is unreadable. Nothing was changed.")
    digest = setup["digest"]
    if digest.startswith("sha256:") and digest[7:].lower() != want:
        raise SharkyClipsError("The checksum file and GitHub's own checksum don't agree. Nothing was changed.")
    dest = appinstall.updates_dir() / setup["name"]
    components.download(setup["url"], dest, sha256=want, size=setup["size"] or None)
    on_stage("update_verify")
    sig = authenticode(dest)
    if sig["status"] not in SIGNATURE_OK:
        dest.unlink(missing_ok=True)
        raise SharkyClipsError(f"The installer's signature is not valid ({sig['status']}). It was deleted.",
                               f"Download SharkyClips from {RELEASES_URL} instead.")
    if config.get("update_require_signed") is True and sig["status"] != "Valid":
        raise SharkyClipsError("The new installer isn't signed, and Settings require signed updates.",
                               f"Download it from {RELEASES_URL} if you trust it.")
    for old in appinstall.updates_dir().glob("SharkyClips-Setup-*.exe"):
        if old != dest:
            old.unlink(missing_ok=True)
    return {"version": rel["version"], "installer": str(dest), "signature": sig["status"], "changed": True,
            "packages_updated": False, "restart_needed": True, "pending_install": True}


def run_installer(path: str | Path) -> int:
    """Start the downloaded installer silently, outside SharkyClips' job (it closes SharkyClips,
    installs and starts it again: /RELAUNCH=1). Returns its pid."""
    from . import procs

    exe = Path(path)
    if not exe.is_file():
        raise SharkyClipsError("The downloaded installer is gone.", "Press Update again.")
    log = exe.with_suffix(".log")
    return procs.launch_app([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
                             "/RELAUNCH=1", f"/LOG={log}"])


def status(fetch: bool = True, root: Path = REPO_ROOT) -> dict:
    """Current vs. latest version. Never raises: problems come back as `reason`."""
    from . import appinstall

    if appinstall.is_installer(root):
        if fetch:
            return _installer_status()
        return {"current": __version__, "latest": None, "available": False, "behind": 0, "changes": [],
                "supported": True, "reason": None, "releases_url": RELEASES_URL, "kind": "installer"}
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
    except SharkyClipsError:
        out["reason"] = "no_upstream"
        return out
    out.update(supported=True, branch=branch, upstream=upstream)
    why = official_remote(root)
    if why:  # 1.2.52: never fetch from / update to anything but the official repository
        out.update(supported=False, reason=why)
        return out
    clean_stale_state(root)
    if fetch:
        try:
            git("fetch", "--quiet", "--tags", root=root, timeout=90)
        except SharkyClipsError as exc:
            out["reason"] = "fetch_failed"
            out["error"] = exc.message
            return out
    behind = int(git("rev-list", "--count", "HEAD..@{u}", root=root) or 0)
    out["behind"] = behind
    out["ahead"] = int(git("rev-list", "--count", "@{u}..HEAD", root=root) or 0)
    if behind:
        log = git("log", "--format=%s", "-n", "15", "HEAD..@{u}", root=root)
        out["changes"] = [line for line in log.splitlines() if line.strip()]
        for rel in VERSION_FILES:
            try:
                out["latest"] = parse_version(git("show", f"@{{u}}:{rel}", root=root))
            except SharkyClipsError:
                continue
            if out["latest"]:
                break
    out["latest"] = out["latest"] or __version__
    # Only a strictly higher version is an update: a commit without a version bump, an equal
    # or an older version is never offered (1.2.51: the app must never "update" backwards).
    out["available"] = behind > 0 and is_newer(out["latest"], __version__)
    if behind and not out["available"]:
        out["reason"] = "not_newer"
    if out["available"] and release_commit(out["latest"], root) is None:
        out.update(available=False, reason="not_released")  # VERSION bumped, but not tagged yet
    out["dirty"] = bool(git("status", "--porcelain", "--untracked-files=no", root=root))
    return out


def apply(on_stage: Callable[[str], None] | None = None, root: Path = REPO_ROOT,
          python: str = sys.executable) -> dict:
    """git pull, then reinstall Python packages if the requirements changed.
    An installed copy (1.2.56) downloads and checks the new installer instead (`_installer_apply`)."""
    from . import appinstall

    stage = on_stage or (lambda _s: None)
    if appinstall.is_installer(root):
        return _installer_apply(stage)
    if official_remote(root):
        raise SharkyClipsError("This copy of SharkyClips doesn't come from the official GitHub repository, "
                               "so it isn't updated automatically.",
                               f"Download the latest version from {RELEASES_URL}.")
    clean_stale_state(root)
    before_rev = git("rev-parse", "HEAD", root=root)
    before_ver = disk_version(root) or __version__
    before_req = _requirements_hash(root)
    stage("update_download")
    try:  # never pull an older version (a moved branch, a bad push): check before touching files
        git("fetch", "--quiet", "--tags", root=root, timeout=90)
        remote = None
        for rel in VERSION_FILES:
            try:
                remote = parse_version(git("show", f"@{{u}}:{rel}", root=root))
            except SharkyClipsError:
                continue
            if remote:
                break
    except SharkyClipsError:
        remote = None
    if remote and version_tuple(remote) < version_tuple(before_ver):
        raise SharkyClipsError(f"The version on GitHub ({remote}) is older than this one ({before_ver}).",
                               "SharkyClips never goes back to an older version. Nothing was changed.")
    target = release_commit(remote, root) if remote else None
    if target is None:
        raise SharkyClipsError("The new version isn't released yet (no release tag on GitHub).",
                               "Try again in a few minutes. Nothing was changed.")
    if not _signed_ok(remote, root):
        raise SharkyClipsError(f"The release tag v{remote} has no valid signature.",
                               "Nothing was changed. Download the release from GitHub instead.")
    try:  # exactly the checked release commit, never "whatever is on the branch now"
        git("merge", "--ff-only", "--quiet", target, root=root, timeout=300)
    except SharkyClipsError as exc:
        raise SharkyClipsError(exc.message, "Files of SharkyClips were changed on this computer. Undo those "
                                          "changes (or run `git stash` in the SharkyClips folder) and try again.")
    after_rev = git("rev-parse", "HEAD", root=root)
    after_ver = disk_version(root)
    if after_ver and version_tuple(after_ver) < version_tuple(before_ver):
        git("reset", "--keep", before_rev, root=root)  # put the newer files back
        raise SharkyClipsError(f"That update would go back to {after_ver}: undone, {before_ver} stays.",
                               "SharkyClips never goes back to an older version.")
    deps = False
    if _requirements_hash(root) != before_req:
        stage("update_packages")
        files = ["-r", str(root / REQUIREMENTS[0])]
        from .hardware import nvidia_libs_installed

        if any(nvidia_libs_installed().values()):
            files += ["-r", str(root / REQUIREMENTS[1])]
        res = subprocess.run([python, "-m", "pip", "install", "--upgrade", "--quiet",
                              "--disable-pip-version-check", *files],
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             **no_window())
        if res.returncode != 0:
            tail = (res.stderr or res.stdout).strip().splitlines()[-1:] or ["unknown error"]
            raise SharkyClipsError(f"Installing the new Python packages failed: {tail[0][:300]}",
                                   "Run the installer again to repair SharkyClips.")
        deps = True
    new_version = disk_version(root) or __version__
    return {"from": before_rev[:10], "to": after_rev[:10], "changed": before_rev != after_rev,
            "packages_updated": deps, "version": new_version,
            "restart_needed": is_newer(new_version, __version__) or deps}
