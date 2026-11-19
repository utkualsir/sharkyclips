"""Build the one-click Windows installer (1.2.56).

    python installer/windows/build_installer.py [--out installer/dist] [--iscc PATH] [--no-compile]
                                                [--stage-only] [--cache DIR]

Runs on Windows (the launcher is compiled with the csc.exe of the .NET Framework that ships with
Windows, ISCC is Inno Setup's compiler, the .pyc files are made by the bundled Python). The host
Python only runs pip; the wheels are picked for win_amd64 / CPython 3.12 explicitly.

Steps (see docs/installer-design.md):
  1. python.org embeddable Python 3.12.10 + FFmpeg 9.0.2 essentials, both SHA-256 pinned (cached)
  2. every CPU dependency of backend/requirements.txt (+ pip) into python/Lib/site-packages
  3. the app files from `git ls-files` (never an untracked local file: no secrets, no google_client.json)
  4. the launcher SharkyClips.exe (icon + version from VERSION), install.json, third-party notices
  5. ISCC -> installer/dist/SharkyClips-Setup-<v>.exe + .sha256
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUILD = ROOT / "installer" / "build"

PYTHON = {"version": "3.12.10", "file": "python-3.12.10-embed-amd64.zip",
          "url": "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip",
          # python.org's SPDX file for this download lists this SHA-256
          "sha256": "4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3"}
FFMPEG = {"version": "9.0.2", "file": "ffmpeg-9.0.2-essentials_build.zip",
          "url": "https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip",
          "sha256": "60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba"}
# Folders of the repository that the app needs at runtime (everything else stays out).
APP_PATHS = ("backend/cli.py", "backend/sharkyclips", "backend/requirements.txt", "backend/requirements-nvidia.txt",
             "frontend/dist", "assets/icon", "docs/google-verification.md", "VERSION", "CHANGELOG.md", "LICENSE")
NEVER = (re.compile(r"(^|/)tests?/"), re.compile(r"google_client\.json$"), re.compile(r"\.env$"),
         re.compile(r"(^|/)__pycache__/"), re.compile(r"secrets?\.json$"))
# Junk in site-packages the app never uses (saves ~40 MB); tests folders are kept (some packages import them).
PRUNE_DIRS = ("bin", "Scripts")


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def fetch(item: dict, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / item["file"]
    if dest.is_file() and sha256(dest) == item["sha256"]:
        return dest
    log(f"download {item['url']}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(item["url"], headers={"User-Agent": "SharkyClips-build"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:  # noqa: S310 - pinned https URLs
        shutil.copyfileobj(r, f, 1 << 20)
    got = sha256(tmp)
    if got != item["sha256"]:
        tmp.unlink()
        raise SystemExit(f"checksum mismatch for {item['file']}: {got}")
    os.replace(tmp, dest)
    return dest


def version() -> str:
    v = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        raise SystemExit(f"bad VERSION: {v!r}")
    return v


# ------------------------------------------------------------------ 1-2 Python


def stage_python(stage: Path, cache: Path, compile_pyc: bool) -> None:
    py = stage / "python"
    with zipfile.ZipFile(fetch(PYTHON, cache)) as z:
        z.extractall(py)
    # Paths are relative to python/. "import site" processes Lib/site-packages; ..\backend makes
    # `python -m sharkyclips.smoke` (and every `-m` call the app makes) work: embedded Python
    # ignores PYTHONPATH.
    pth = next(py.glob("python3*._pth"))
    zipname = next(py.glob("python3*.zip")).name
    pth.write_text(f"{zipname}\n.\nLib\\site-packages\n..\\backend\nimport site\n", encoding="utf-8")
    site = py / "Lib" / "site-packages"
    site.mkdir(parents=True, exist_ok=True)
    req = BUILD / "requirements-installer.txt"
    lines = [ln for ln in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
             if "nvidia" not in ln.lower()]
    req.write_text("\n".join(lines + ["pip"]) + "\n", encoding="utf-8")
    log("pip install (win_amd64, cp312) -> python/Lib/site-packages")
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--quiet",
           "--target", str(site), "--platform", "win_amd64", "--python-version", "3.12", "--implementation", "cp",
           "--abi", "cp312", "--only-binary=:all:", "--no-compile", "-r", str(req)]
    subprocess.run(cmd, check=True)
    for d in PRUNE_DIRS:
        shutil.rmtree(site / d, ignore_errors=True)
    if compile_pyc:
        # The bundled Python compiles its own .pyc files (hash-based: valid whatever the file times).
        log("compile .pyc (bundled Python)")
        subprocess.run([str(py / "python.exe"), "-m", "compileall", "-q", "-j", "0", "--invalidation-mode",
                        "unchecked-hash", str(site), str(stage / "backend")], check=False)


# ------------------------------------------------------------------ 3 app files


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", *APP_PATHS], cwd=ROOT, capture_output=True, check=True)
    files = [f for f in out.stdout.decode("utf-8").split("\0") if f]
    return [f for f in files if not any(p.search(f) for p in NEVER)]


def stage_app(stage: Path, ver: str) -> None:
    files = tracked_files()
    if not any(f.startswith("frontend/dist/") for f in files):
        raise SystemExit("frontend/dist is missing: run `npm run build` in frontend/ first")
    for rel in files:
        src, dst = ROOT / rel, stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (stage / "install.json").write_text(json.dumps({"kind": "installer", "version": ver,
                                                    "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                                                   indent=2), encoding="utf-8")
    log(f"{len(files)} app files")


def stage_ffmpeg(stage: Path, cache: Path) -> None:
    out = stage / "ffmpeg" / "bin"
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(fetch(FFMPEG, cache)) as z:
        for name in z.namelist():
            base = name.rsplit("/", 1)[-1]
            if base in ("ffmpeg.exe", "ffprobe.exe"):
                with z.open(name) as s, open(out / base, "wb") as d:
                    shutil.copyfileobj(s, d)
            elif base == "LICENSE" and "/" in name:
                with z.open(name) as s:
                    (stage / "ffmpeg" / "LICENSE.txt").write_bytes(s.read())
    if not (out / "ffmpeg.exe").is_file():
        raise SystemExit("ffmpeg.exe not found in the FFmpeg archive")


def notices(stage: Path) -> None:
    site = stage / "python" / "Lib" / "site-packages"
    rows = []
    for meta in sorted(site.glob("*.dist-info/METADATA")):
        name = ver = lic = ""
        for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Name: "):
                name = line[6:].strip()
            elif line.startswith("Version: "):
                ver = line[9:].strip()
            elif line.startswith("License-Expression: ") or (line.startswith("License: ") and not lic):
                lic = line.split(": ", 1)[1].strip()[:80]
            elif not line.strip():
                break
        rows.append(f"  {name} {ver}  ({lic or 'see the package'})")
    text = "\n".join([
        "SharkyClips bundles these third-party components. Their licenses are in the folders next to",
        "this file (python\\LICENSE.txt, ffmpeg\\LICENSE.txt, python\\Lib\\site-packages\\*.dist-info).",
        "",
        f"Python {PYTHON['version']} (embeddable package, python.org) - Python Software Foundation License",
        f"FFmpeg {FFMPEG['version']} essentials build by gyan.dev - GPL v3. Source code: https://ffmpeg.org/download.html,",
        "  build scripts and exact sources: https://www.gyan.dev/ffmpeg/builds/ and",
        "  https://github.com/GyanD/codexffmpeg (release " + FFMPEG["version"] + ").",
        "",
        "Python packages (pip, from PyPI):",
        *rows, ""])
    (stage / "THIRD-PARTY-NOTICES.txt").write_text(text, encoding="utf-8")


# ------------------------------------------------------------------ 4 launcher


def csc_path() -> Path:
    win = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for fw in ("Framework64", "Framework"):
        p = win / "Microsoft.NET" / fw / "v4.0.30319" / "csc.exe"
        if p.is_file():
            return p
    raise SystemExit("csc.exe (.NET Framework 4.x) not found")


def build_launcher(stage: Path, ver: str) -> None:
    info = BUILD / "AssemblyInfo.cs"
    info.write_text("\n".join([
        "using System.Reflection;",
        '[assembly: AssemblyTitle("SharkyClips")]',
        '[assembly: AssemblyProduct("SharkyClips")]',
        '[assembly: AssemblyDescription("SharkyClips - clip Shorts from your streams")]',
        f'[assembly: AssemblyVersion("{ver}.0")]',
        f'[assembly: AssemblyFileVersion("{ver}.0")]',
        f'[assembly: AssemblyInformationalVersion("{ver}")]', ""]), encoding="utf-8")
    out = stage / "SharkyClips.exe"
    cmd = [str(csc_path()), "-nologo", "-target:winexe", "-platform:anycpu", "-optimize+",
           f"-out:{out}", f"-win32icon:{ROOT / 'assets' / 'icon' / 'sharkyclips.ico'}",
           "-r:System.Windows.Forms.dll", "-r:System.Drawing.dll", str(HERE / "launcher" / "SharkyClips.cs"), str(info)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not out.is_file():
        raise SystemExit("launcher build failed:\n" + res.stdout + res.stderr)
    log(f"launcher {out.stat().st_size // 1024} KB")


# ------------------------------------------------------------------ checks + 5 ISCC


def check_stage(stage: Path) -> None:
    """No secret may ever ship: no Google client, no token-like text in the app's own files."""
    bad = [p for p in stage.rglob("google_client.json")] + [p for p in stage.rglob("*.env")]
    if bad:
        raise SystemExit(f"refusing to ship: {bad}")
    token = re.compile(r"ya29\.[0-9A-Za-z_\-]{20,}|GOCSPX-[0-9A-Za-z_\-]{10,}|ghp_[0-9A-Za-z]{30,}|github_pat_[0-9A-Za-z_]{30,}")
    for p in list((stage / "backend").rglob("*.py")) + list((stage / "backend").rglob("*.json")):
        if token.search(p.read_text(encoding="utf-8", errors="replace")):
            raise SystemExit(f"token-like text in {p}")
    for must in ("python/python.exe", "python/pythonw.exe", "ffmpeg/bin/ffmpeg.exe", "ffmpeg/bin/ffprobe.exe",
                 "backend/cli.py", "frontend/dist/index.html", "SharkyClips.exe", "install.json", "VERSION"):
        if not (stage / must).is_file():
            raise SystemExit(f"missing in the stage: {must}")


def find_iscc(given: str | None) -> Path:
    cands = [given] if given else []
    cands += [os.environ.get("ISCC")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            for v in ("Inno Setup 7", "Inno Setup 6"):
                cands.append(str(Path(base) / v / "ISCC.exe"))
                cands.append(str(Path(base) / "Programs" / v / "ISCC.exe"))
    found = shutil.which("iscc")
    if found:
        cands.append(found)
    for c in cands:
        if c and Path(c).is_file():
            return Path(c)
    raise SystemExit("ISCC.exe (Inno Setup 6 or 7) not found: install Inno Setup or pass --iscc")


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "installer" / "dist"))
    ap.add_argument("--iscc")
    ap.add_argument("--cache", default=str(BUILD / "cache"))
    ap.add_argument("--no-compile", action="store_true", help="don't precompile .pyc files")
    ap.add_argument("--stage-only", action="store_true", help="stop after staging (no ISCC)")
    ap.add_argument("--reuse-stage", action="store_true", help="skip staging, run ISCC on the last stage")
    args = ap.parse_args()
    if os.name != "nt":
        raise SystemExit("build the Windows installer on Windows")
    if sys.version_info[:2] != (3, 12):
        log(f"note: host Python is {sys.version.split()[0]}; wheels are still picked for CPython 3.12")
    ver = version()
    cache = Path(args.cache)
    stage = BUILD / "stage"
    t0 = time.time()
    if not args.reuse_stage:
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True)
        BUILD.mkdir(parents=True, exist_ok=True)
        stage_app(stage, ver)
        stage_python(stage, cache, compile_pyc=not args.no_compile)
        stage_ffmpeg(stage, cache)
        build_launcher(stage, ver)
        notices(stage)
    check_stage(stage)
    log(f"stage: {dir_size(stage) / 1e6:.0f} MB in {time.time() - t0:.0f} s")
    if args.stage_only:
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    iscc = find_iscc(args.iscc)
    log(f"ISCC {iscc}")
    t1 = time.time()
    subprocess.run([str(iscc), "/Q", f"/DAppVersion={ver}", f"/DStageDir={stage}", f"/DOutDir={out}",
                    str(HERE / "SharkyClips.iss")], check=True)
    exe = out / f"SharkyClips-Setup-{ver}.exe"
    digest = sha256(exe)
    (out / (exe.name + ".sha256")).write_text(f"{digest}  {exe.name}\n", encoding="utf-8")
    log(f"{exe.name}: {exe.stat().st_size / 1e6:.0f} MB, sha256 {digest} (ISCC {time.time() - t1:.0f} s)")


if __name__ == "__main__":
    main()
