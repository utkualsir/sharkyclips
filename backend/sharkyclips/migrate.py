"""One-time move from the old name (ClipForge) to SharkyClips. Runs on every start, cheap when done.

  settings   ~/.clipforge -> ~/.sharkyclips: config, workspace path, liked titles, glossary,
             calibration, fonts, game regions, models. Entries are moved (merged into a folder
             that already exists), never overwritten; paths inside config.json are rewritten.
  Windows    "ClipForge.lnk" on the desktop / Start menu -> "SharkyClips.lnk" (same target,
             new icon); the "Apps & features" entry is renamed. Only shortcuts that point to
             this installation are touched.
  macOS      ~/Applications/ClipForge.app -> SharkyClips.app (best effort).
  repo       an empty backend/clipforge folder (only __pycache__ left after `git pull`) is removed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

OLD_HOME_NAME = ".clipforge"
OLD_NAME = "ClipForge"
NEW_NAME = "SharkyClips"
MARKER = "migrated_from_clipforge.json"


def old_home() -> Path | None:
    """The folder to migrate from. With SHARKYCLIPS_HOME set (tests, custom setups) only an
    explicit CLIPFORGE_HOME is used, never the real ~/.clipforge."""
    old_env = os.environ.get("CLIPFORGE_HOME")
    if os.environ.get("SHARKYCLIPS_HOME"):
        return Path(old_env).expanduser() if old_env else None
    if old_env:
        return None  # config_dir() keeps using CLIPFORGE_HOME itself
    return Path.home() / OLD_HOME_NAME


def _merge_move(src: Path, dst: Path, moved: list[str], kept: list[str]) -> None:
    """Move src into dst. Existing files in dst win (they are newer); folders are merged."""
    if not dst.exists():
        try:
            shutil.move(str(src), str(dst))
            moved.append(dst.name)
            return
        except OSError:
            pass  # e.g. a file held open on Windows: fall back to copying
        try:
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            moved.append(dst.name + " (copied)")
        except OSError:
            kept.append(str(src))
        return
    if src.is_dir() and dst.is_dir():
        for child in list(src.iterdir()):
            _merge_move(child, dst / child.name, moved, kept)
        try:
            src.rmdir()
        except OSError:
            pass
    else:
        kept.append(str(src))  # both exist: keep the new one, leave the old one where it was


def _rewrite_paths(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        if value.startswith(old):
            return new + value[len(old):]
        return value.replace(old + os.sep, new + os.sep).replace(old + "/", new + "/")
    if isinstance(value, list):
        return [_rewrite_paths(v, old, new) for v in value]
    if isinstance(value, dict):
        return {k: _rewrite_paths(v, old, new) for k, v in value.items()}
    return value


def migrate_home() -> dict | None:
    """Move the old settings folder. Returns what happened, or None when there was nothing to do."""
    new = config.config_dir()
    old = old_home()
    if old is None or not old.is_dir() or (new / MARKER).is_file():
        return None
    if new.exists() and new.resolve() == old.resolve():
        return None
    new.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    kept: list[str] = []
    old_cfg = old / "config.json"
    if old_cfg.is_file() and (new / "config.json").is_file():
        # A config in the new folder can only come from something that ran before the migration:
        # the user's real settings (the old file) win.
        try:
            merged = {**json.loads((new / "config.json").read_text(encoding="utf-8-sig")),
                      **json.loads(old_cfg.read_text(encoding="utf-8-sig"))}
            (new / "config.json").write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
            old_cfg.unlink()
            moved.append("config.json (merged)")
        except (OSError, ValueError):
            pass
    for entry in sorted(old.iterdir()):
        _merge_move(entry, new / entry.name, moved, kept)
    # Paths inside the settings that pointed into the old folder.
    cfg_path = new / "config.json"
    if cfg_path.is_file():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            fixed = _rewrite_paths(data, str(old), str(new))
            if fixed != data:
                cfg_path.write_text(json.dumps(fixed, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError):
            pass
    old_log = new / "logs" / "clipforge.log"
    if old_log.is_file() and not (new / "logs" / "clipforge.old.log").exists():
        try:
            old_log.replace(new / "logs" / "clipforge.old.log")
        except OSError:
            pass
    try:
        old.rmdir()  # only when everything moved
        removed = True
    except OSError:
        removed = False
        try:
            (old / "MOVED_TO_SHARKYCLIPS.txt").write_text(
                f"ClipForge is now SharkyClips. Its settings moved to {new}.\n"
                "Files still here could not be moved (they exist in the new folder too).\n",
                encoding="utf-8")
        except OSError:
            pass
    info = {"from": str(old), "to": str(new), "moved": moved, "kept_in_old_folder": kept,
            "old_folder_removed": removed, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        (new / MARKER).write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return info


# ------------------------------------------------------------------ Windows shortcuts / Apps entry

_PS_SHORTCUTS = r"""
$ErrorActionPreference = 'Stop'
$root = $env:SC_ROOT.TrimEnd('\')
$icon = $env:SC_ICON
$shell = New-Object -ComObject WScript.Shell
$dirs = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'),
          (Join-Path $env:APPDATA 'Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'))
foreach ($d in $dirs) {
    $old = Join-Path $d 'ClipForge.lnk'
    if (-not (Test-Path -LiteralPath $old)) { continue }
    $s = $shell.CreateShortcut($old)
    $mine = ($s.TargetPath + ' ' + $s.Arguments + ' ' + $s.WorkingDirectory) -like ('*' + $root + '*')
    if (-not $mine) { continue }
    $newPath = Join-Path $d 'SharkyClips.lnk'
    $n = $shell.CreateShortcut($newPath)
    $n.TargetPath = $s.TargetPath
    $n.Arguments = $s.Arguments.Replace('ClipForge.bat', 'SharkyClips.bat')
    $n.TargetPath = $n.TargetPath.Replace('ClipForge.bat', 'SharkyClips.bat')
    $n.WorkingDirectory = $s.WorkingDirectory
    $n.IconLocation = "$icon,0"
    $n.Description = 'SharkyClips: clip Shorts from your streams'
    $n.Save()
    Remove-Item -LiteralPath $old -Force
    Write-Output "shortcut:$newPath"
}
$oldKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipForge'
$newKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SharkyClips'
if (Test-Path $oldKey) {
    $p = Get-ItemProperty $oldKey
    if (("" + $p.InstallLocation).TrimEnd('\') -eq $root) {
        New-Item -Path $newKey -Force | Out-Null
        $values = @{
            DisplayName = 'SharkyClips'; DisplayVersion = $env:SC_VERSION; Publisher = 'SharkyClips'
            DisplayIcon = $icon; InstallLocation = $p.InstallLocation
            UninstallString = $p.UninstallString; URLInfoAbout = 'https://github.com/utkualsir/sharkyclips'
        }
        foreach ($k in $values.Keys) { Set-ItemProperty -Path $newKey -Name $k -Value $values[$k] }
        Set-ItemProperty -Path $newKey -Name NoModify -Value 1 -Type DWord
        Set-ItemProperty -Path $newKey -Name NoRepair -Value 1 -Type DWord
        Remove-Item -Path $oldKey -Recurse -Force
        Write-Output 'apps:renamed'
    }
}
if (Test-Path $newKey) { Set-ItemProperty -Path $newKey -Name DisplayVersion -Value $env:SC_VERSION }
"""


def rebrand_windows(root: Path = config.REPO_ROOT, version: str | None = None) -> list[str]:
    """Old shortcuts / Apps entry -> the new name. Returns what changed."""
    if os.name != "nt":
        return []
    from . import __version__

    version = version or __version__
    appdata = Path(os.environ.get("APPDATA", ""))
    dirs = [Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop",
            appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            appdata / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar"]
    has_old = any((d / f"{OLD_NAME}.lnk").exists() for d in dirs)
    new_version = _apps_value(NEW_NAME, "DisplayVersion")
    if not has_old and _apps_value(OLD_NAME, "DisplayName") is None and new_version in (None, version):
        return []  # nothing to do (the usual case: no PowerShell start)
    env = {**os.environ, "SC_ROOT": str(root), "SC_ICON": str(root / "assets" / "icon" / "sharkyclips.ico"),
           "SC_VERSION": version}
    try:
        from .procs import no_window

        res = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                              "-Command", _PS_SHORTCUTS], env=env, capture_output=True, text=True, timeout=30,
                             **no_window(), encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def _apps_value(name: str, value: str) -> str | None:
    """A value of this user's "Apps & features" entry `name`; None if there is none."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{name}") as k:
            return str(winreg.QueryValueEx(k, value)[0])
    except OSError:
        return None


def rebrand_macos() -> list[str]:
    if sys.platform != "darwin":
        return []
    old = Path.home() / "Applications" / f"{OLD_NAME}.app"
    new = Path.home() / "Applications" / f"{NEW_NAME}.app"
    if not old.is_dir() or new.exists():
        return []
    try:
        import plistlib

        old.rename(new)
        info = new / "Contents" / "Info.plist"
        data = plistlib.loads(info.read_bytes())
        data.update(CFBundleName=NEW_NAME, CFBundleDisplayName=NEW_NAME,
                    CFBundleIdentifier="io.github.utkualsir.sharkyclips", CFBundleExecutable=NEW_NAME)
        exe_old, exe_new = new / "Contents" / "MacOS" / OLD_NAME, new / "Contents" / "MacOS" / NEW_NAME
        if exe_old.is_file():
            text = exe_old.read_text(encoding="utf-8").replace(OLD_NAME, NEW_NAME)
            exe_new.write_text(text, encoding="utf-8")
            exe_new.chmod(0o755)
            exe_old.unlink()
        info.write_bytes(plistlib.dumps(data))
        return [f"app:{new}"]
    except Exception:  # noqa: BLE001 - best effort; the old app keeps working
        return []


def cleanup_old_package(root: Path = config.REPO_ROOT) -> bool:
    """`git pull` leaves backend/clipforge/ behind when it only holds __pycache__ folders."""
    old = root / "backend" / "clipforge"
    if not old.is_dir():
        return False
    if any(p.is_file() and "__pycache__" not in p.parts for p in old.rglob("*")):
        return False  # real files in there: not ours to delete
    shutil.rmtree(old, ignore_errors=True)
    return True


def run_all() -> dict:
    """Everything above; never raises (a failed step is retried on the next start)."""
    out: dict = {}
    if os.environ.get("SHARKYCLIPS_NO_MIGRATE") == "1":  # tests: never touch the real shortcuts
        return out
    for name, fn in (("home", migrate_home), ("windows", rebrand_windows), ("macos", rebrand_macos),
                     ("package", cleanup_old_package)):
        try:
            res = fn()
        except Exception as exc:  # noqa: BLE001
            res = {"error": str(exc)}
        if res:
            out[name] = res
    return out
