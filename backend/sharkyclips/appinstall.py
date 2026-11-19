"""How this copy of SharkyClips was installed, and the paths that depend on it (1.2.56).

  installer   the Windows installer (Inno Setup) wrote <app>/install.json. The app runs on the
              bundled Python (<app>/python) and FFmpeg (<app>/ffmpeg/bin); updates come as a new
              installer from the GitHub release (updater.py), never through git.
  git         a git checkout (install.bat / install.sh / a developer): unchanged behaviour.
  folder      anything else (a zip copy): updates are offered as a link only.

Runtime folder (%LOCALAPPDATA%/SharkyClips/runtime, SHARKYCLIPS_RUNTIME to override): what the
first-run downloads add outside the install folder, so an update that replaces <app>/python keeps
them: gpu/ (pip --target of the NVIDIA CUDA wheels), tools/deno/ (yt-dlp's JavaScript runtime).
`setup_paths()` (run on import of the package) puts these on PATH / sys.path.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKER = "install.json"


def marker_path(root: Path = REPO_ROOT) -> Path:
    return root / MARKER


def info(root: Path = REPO_ROOT) -> dict:
    """The installer's marker ({} when there is none / it's unreadable)."""
    try:
        data = json.loads(marker_path(root).read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def kind(root: Path = REPO_ROOT) -> str:
    if os.environ.get("SHARKYCLIPS_INSTALL_KIND") in ("installer", "git", "folder"):
        return os.environ["SHARKYCLIPS_INSTALL_KIND"]  # tests
    if info(root).get("kind") == "installer":
        return "installer"
    if (root / ".git").exists():
        return "git"
    return "folder"


def is_installer(root: Path = REPO_ROOT) -> bool:
    return kind(root) == "installer"


def local_appdata() -> Path:
    env = os.environ.get("LOCALAPPDATA")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def runtime_dir() -> Path:
    env = os.environ.get("SHARKYCLIPS_RUNTIME")
    return Path(env).expanduser() if env else local_appdata() / "SharkyClips" / "runtime"


def gpu_dir() -> Path:
    return runtime_dir() / "gpu"


def tools_dir() -> Path:
    return runtime_dir() / "tools"


def updates_dir() -> Path:
    return runtime_dir().parent / "updates"


def bundled_ffmpeg_dir(root: Path = REPO_ROOT) -> Path:
    return root / "ffmpeg" / "bin"


def default_workspace(root: Path = REPO_ROOT) -> Path:
    """Projects of an installed copy live in the user's Videos folder, never in the install folder
    (an uninstall or update must not touch them); a checkout keeps <repo>/workspace."""
    if is_installer(root):
        return videos_dir() / "SharkyClips"
    return root / "workspace"


def videos_dir() -> Path:
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            # FOLDERID_Videos {18989B1D-99B5-455B-841C-AB7C74E4DDFC}: follows a moved Videos folder
            class GUID(ctypes.Structure):
                _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD),
                            ("d4", ctypes.c_ubyte * 8)]

            fid = GUID(0x18989B1D, 0x99B5, 0x455B, (ctypes.c_ubyte * 8)(0x84, 0x1C, 0xAB, 0x7C, 0x74, 0xE4, 0xDD, 0xFC))
            out = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(fid), 0, None, ctypes.byref(out)) == 0:
                path = out.value
                ctypes.windll.ole32.CoTaskMemFree(out)
                if path:
                    return Path(path)
        except (OSError, AttributeError, ValueError):
            pass
    return Path.home() / "Videos"


def _prepend_path(folder: Path) -> None:
    if not folder.is_dir():
        return
    entries = os.environ.get("PATH", "").split(os.pathsep)
    if str(folder) not in entries:
        os.environ["PATH"] = str(folder) + (os.pathsep + os.environ["PATH"] if os.environ.get("PATH") else "")


def setup_paths(root: Path = REPO_ROOT) -> None:
    """Bundled FFmpeg first on PATH, then the downloaded tools; the GPU wheels on sys.path
    (hardware.nvidia_lib_dirs() looks for <sys.path entry>/nvidia/*/bin)."""
    try:
        _prepend_path(tools_dir() / "deno")
        _prepend_path(bundled_ffmpeg_dir(root))
        gpu = gpu_dir()
        if gpu.is_dir() and str(gpu) not in sys.path:
            sys.path.append(str(gpu))
    except OSError:
        pass


# ------------------------------------------------------------------ old git installs (migration)

OLD_UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SharkyClips"
OLD_ENTRY_NAME = "SharkyClips (old git copy)"


def old_git_install() -> Path | None:
    """The checkout install.ps1 made (Apps & features entry, else %USERPROFILE%/SharkyClips)."""
    if os.environ.get("SHARKYCLIPS_OLD_INSTALL"):  # tests
        p = Path(os.environ["SHARKYCLIPS_OLD_INSTALL"])
        return p if (p / ".git").exists() or (p / "backend" / "cli.py").is_file() else None
    found: list[Path] = []
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, OLD_UNINSTALL_KEY) as k:
                loc, _ = winreg.QueryValueEx(k, "InstallLocation")
                if loc:
                    found.append(Path(loc))
        except OSError:
            pass
    found.append(Path.home() / "SharkyClips")
    for p in found:
        try:
            if p.resolve() != REPO_ROOT.resolve() and (p / "backend" / "cli.py").is_file():
                return p
        except OSError:
            continue
    return None


def migrate_from_git(root: Path = REPO_ROOT) -> dict:
    """First start of an installed copy on a PC that had a git install. Never moves or deletes
    anything of the old copy: the projects stay where they are and are simply used from there."""
    from . import config

    done: dict = {}
    if not is_installer(root) or config.get("installer_migrated"):
        return done
    old = old_git_install()
    changes: dict = {"installer_migrated": True}
    if old is not None:
        done["old_install"] = str(old)
        ws = old / "workspace"
        if not config.get("workspace_dir") and ws.is_dir():
            changes["workspace_dir"] = str(ws)
            done["workspace"] = str(ws)
        if os.name == "nt" and not os.environ.get("SHARKYCLIPS_NO_MIGRATE"):
            done["shortcuts"] = _repoint_shortcuts(old, root)
            done["old_entry"] = _rename_old_entry(old)
    if not config.get("workspace_dir") and "workspace_dir" not in changes:
        # pin the default once, so it never changes under the user (a moved Videos folder ...)
        changes["workspace_dir"] = str(default_workspace(root))
    config.update(**changes)
    return done


def _repoint_shortcuts(old: Path, root: Path) -> int:
    import subprocess

    from .procs import no_window

    exe = root / "SharkyClips.exe"
    if not exe.is_file():
        return 0
    script = (
        "$n = 0; $sh = New-Object -ComObject WScript.Shell; "
        "foreach ($d in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) { "
        "$p = Join-Path $d 'SharkyClips.lnk'; if (-not (Test-Path -LiteralPath $p)) { continue }; "
        "$s = $sh.CreateShortcut($p); "
        "if (-not (($s.TargetPath + ' ' + $s.Arguments) -like ('*' + $env:SC_OLD + '*'))) { continue }; "
        "$s.TargetPath = $env:SC_EXE; $s.Arguments = ''; $s.WorkingDirectory = $env:SC_ROOT; "
        "$s.IconLocation = $env:SC_EXE + ',0'; $s.Save(); $n++ }; $n"
    )
    env = {**os.environ, "SC_OLD": str(old), "SC_EXE": str(exe), "SC_ROOT": str(root)}
    try:
        res = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, timeout=30, env=env, **no_window())
        return int((res.stdout or "0").strip().splitlines()[-1] or 0)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return 0


def _rename_old_entry(old: Path) -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, OLD_UNINSTALL_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            loc, _ = winreg.QueryValueEx(k, "InstallLocation")
            if Path(loc).resolve() != old.resolve():
                return False
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, OLD_ENTRY_NAME)
            return True
    except OSError:
        return False


def summary() -> dict:
    """For /api/app and the diagnostic report."""
    k = kind()
    out = {"kind": k, "runtime": str(runtime_dir())}
    if k == "installer":
        out["installed_version"] = info().get("version")
    return out
