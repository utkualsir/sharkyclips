"""Build the files attached to a GitHub release.

    python installer/build_release.py      -> installer/dist/

ClipForge-Setup.bat: a single file for Windows users. It carries installer/windows/install.ps1,
writes it to %TEMP% and runs it; the installer then downloads ClipForge with git.
install.sh: the macOS installer (it downloads ClipForge by itself when run on its own).
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "installer" / "dist"
MARKER = "#__CLIPFORGE_INSTALL_PS1__"

HEADER = r"""@echo off
rem ClipForge setup for Windows 10/11. Double-click to install.
rem Kurulum: cift tiklayin. (This file carries installer\windows\install.ps1 below.)
setlocal
set "CF_SELF=%~f0"
set "CF_PS1=%TEMP%\clipforge-install-%RANDOM%%RANDOM%.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$l = [IO.File]::ReadAllLines($env:CF_SELF, [Text.Encoding]::UTF8); $i = [Array]::IndexOf($l, '{marker}'); [IO.File]::WriteAllLines($env:CF_PS1, $l[($i + 1)..($l.Length - 1)], (New-Object Text.UTF8Encoding $true))"
if errorlevel 1 (
  echo Could not unpack the installer. / Kurulum dosyasi acilamadi.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CF_PS1%" %*
set "RC=%ERRORLEVEL%"
del "%CF_PS1%" >nul 2>&1
echo.
pause
exit /b %RC%
""".replace("{marker}", MARKER)


def main() -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    ps1 = (ROOT / "installer" / "windows" / "install.ps1").read_text(encoding="utf-8-sig")
    text = HEADER + MARKER + "\n" + ps1.replace("\r\n", "\n")
    # No BOM: cmd.exe would choke on it. CRLF: cmd needs it.
    (DIST / "ClipForge-Setup.bat").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    shutil.copyfile(ROOT / "install.sh", DIST / "install.sh")
    for f in sorted(DIST.iterdir()):
        print(f"{f.relative_to(ROOT)}  {f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
