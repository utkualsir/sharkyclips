"""Fast local checks before a commit (docs/test-speed.md). CI still runs everything.

  .venv/Scripts/python scripts/quick-check.py            lint + tests of the changed files
  .venv/Scripts/python scripts/quick-check.py --layout   ... + a small layout smoke set (Edge)
  .venv/Scripts/python scripts/quick-check.py --full     lint + the WHOLE pytest suite (parallel)
  --base origin/main   compare with another commit instead of the working tree vs HEAD

What runs:
  1. ruff over backend + installer (about a second)
  2. pytest: the test files that changed, plus every test file that imports a changed backend
     module (sharkyclips/foo.py -> tests mentioning "foo"), in parallel with pytest-xdist
  3. frontend: typecheck when frontend/src changed, the i18n check when a locale changed
  4. --layout: a throwaway fixture server on port 8799 and layout-check.mjs on 2 sizes x tr/ar x
     light/dark (Classic) for the screens you name with --screens (default: all screens)

The full layout matrix (9 sizes x 3 languages x 4 presets) only runs in CI, split into shards.
Nothing here deletes anything; the fixture folder is a fresh mkdtemp folder in the system temp.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
SERIAL = {"test_assisted_upload.py", "test_cancel_final.py", "test_governor.py", "test_instance.py",
          "test_no_window.py", "test_stuck_exit.py", "test_tiktok_browser.py", "test_update_restart.py"}  # = conftest
NO_WINDOW = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW: never flash a console


def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None) -> int:
    print("$", " ".join(cmd), flush=True)
    t = time.monotonic()
    # explicit handles: with CREATE_NO_WINDOW a child's output is lost otherwise
    rc = subprocess.call(cmd, cwd=cwd, env=env, creationflags=NO_WINDOW,
                         stdout=sys.stdout.fileno(), stderr=sys.stderr.fileno())
    if rc == 5 and "pytest" in cmd:  # "no tests collected" (e.g. only serial files changed)
        rc = 0
    print(f"  -> exit {rc} in {time.monotonic() - t:.1f}s", flush=True)
    return rc


def changed_files(base: str | None) -> list[str]:
    def git(*a: str) -> list[str]:
        out = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, creationflags=NO_WINDOW).stdout
        return [x.strip() for x in out.splitlines() if x.strip()]

    files = set(git("diff", "--name-only", base or "HEAD"))
    files |= set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(f for f in files if (ROOT / f).exists())


def tests_for(files: list[str]) -> list[str]:
    tests_dir = ROOT / "backend" / "tests"
    picked = {f for f in files if re.match(r"backend/tests/test_\w+\.py$", f)}
    mods = set()
    for f in files:
        m = re.match(r"backend/sharkyclips/(?:.+/)?(\w+)\.py$", f)
        if m and m.group(1) != "__init__":
            mods.add(m.group(1))
        if f.startswith("frontend/src/previewMath.ts"):
            picked.add("backend/tests/test_preview_math.py")
        if f in ("CHANGELOG.md", "VERSION") or f.startswith("frontend/dist/"):
            picked.add("backend/tests/test_updates_page.py")
    if mods:
        pat = re.compile(r"\b(" + "|".join(sorted(mods)) + r")\b")
        for t in sorted(tests_dir.glob("test_*.py")):
            if pat.search(t.read_text(encoding="utf-8", errors="replace")):
                picked.add(t.relative_to(ROOT).as_posix())
    return sorted(picked)


def has_xdist() -> bool:
    return subprocess.call([PY, "-c", "import xdist"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=NO_WINDOW) == 0


def workers() -> int:
    """Each worker imports the whole backend (~0.5 GB): 24 workers ran a 16 GB PC out of memory
    (MemoryError while collecting). QUICK_WORKERS overrides."""
    try:
        return max(1, int(os.environ["QUICK_WORKERS"]))
    except (KeyError, ValueError):
        return max(1, min(6, (os.cpu_count() or 2) // 2))


def pytest(paths: list[str], extra: list[str] | None = None) -> int:
    # loadfile: one test file stays on one worker (files that share fixtures / module state)
    par = ["-n", str(workers()), "--dist", "loadfile"] if has_xdist() and (not paths or len(paths) > 1) else []
    if par and any(Path(p).name in SERIAL for p in paths):  # mixed: serial files after the parallel pass
        return run([PY, "-m", "pytest", "-q", *par, "-m", "not serial", *paths]) |             run([PY, "-m", "pytest", "-q", "-m", "serial", *paths])
    return run([PY, "-m", "pytest", "-q", *par, *(extra or []), *paths])


def layout_smoke(screens: str | None) -> int:
    home = Path(tempfile.mkdtemp(prefix="sharkyclips-quick-layout-"))
    pid = subprocess.run([PY, "frontend/scripts/layout-fixture.py", str(home)], cwd=ROOT, capture_output=True,
                         text=True, creationflags=NO_WINDOW).stdout.strip().splitlines()[-1]
    env = {**os.environ, "SHARKYCLIPS_HOME": str(home / "home"), "SHARKYCLIPS_NO_MIGRATE": "1",
           "SHARKYCLIPS_NO_BROWSER": "1", "SHARKYCLIPS_PUBLISH_LOOP": "0", "SHARKYCLIPS_LIVE_LOOP": "0",
           "SHARKYCLIPS_SHARED_CLIENT": str(home / "none.json"),
           "SHARKYCLIPS_DOWNLOADS": str(home / "downloads" / "SharkyClips"),  # never the real Downloads
           "SHARKYCLIPS_QUEUE_HOME": str(home / "queue-home")}
    log = open(home / "server.log", "w", encoding="utf-8")  # noqa: SIM115 - closed below
    srv = subprocess.Popen([PY, "backend/cli.py", "serve", "--port", "8799", "--no-browser"], cwd=ROOT, env=env,
                           stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    try:
        for _ in range(90):
            try:
                urllib.request.urlopen("http://127.0.0.1:8799/api/meta", timeout=2)
                break
            except OSError:
                time.sleep(1)
        else:
            print("fixture server did not start; log:", home / "server.log")
            return 1
        lenv = {**os.environ, "LAYOUT_SIZES": "1280x720,390x844", "LAYOUT_LANGS": "tr,ar",
                "LAYOUT_PRESETS": "classic", "LAYOUT_CHANNEL": os.environ.get("LAYOUT_CHANNEL", "msedge")}
        if screens:
            lenv["LAYOUT_SCREENS"] = screens
        rc = run(["node", "scripts/layout-check.mjs", "http://127.0.0.1:8799", pid, str(home / "shots")],
                 cwd=ROOT / "frontend", env=lenv)
        return rc
    finally:
        srv.terminate()
        log.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--full", action="store_true", help="the whole pytest suite (parallel)")
    ap.add_argument("--layout", action="store_true", help="also the small layout smoke set")
    ap.add_argument("--screens", help="layout screens, e.g. history,easy-history")
    ap.add_argument("--base", help="compare with this commit (default: HEAD + untracked files)")
    a = ap.parse_args()
    t0 = time.monotonic()
    files = changed_files(a.base)
    print(f"{len(files)} changed file(s)")
    rc = run([PY, "-m", "ruff", "check", "backend", "installer", "scripts"])
    if a.full:
        rc |= pytest([], ["-m", "not serial"])  # parallel pass
        rc |= run([PY, "-m", "pytest", "-q", "-m", "serial"])  # real browsers / servers: one at a time
    else:
        tests = tests_for(files)
        print(f"{len(tests)} test file(s) for the changes")
        if tests:
            rc |= pytest(tests)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    if any(f.startswith("frontend/src/") for f in files):
        rc |= run([npm, "run", "typecheck"], cwd=ROOT / "frontend")
    if any(f.startswith("frontend/src/i18n/") for f in files):
        rc |= run(["node", "scripts/check-i18n.mjs"], cwd=ROOT / "frontend")
    if a.layout:
        rc |= layout_smoke(a.screens)
    print(f"quick-check {'OK' if rc == 0 else 'FAILED'} in {time.monotonic() - t0:.0f}s")
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
