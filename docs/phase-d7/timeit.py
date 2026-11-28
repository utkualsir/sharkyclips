"""Time the SharkyClips pipeline (CLI steps) on one video in a throwaway settings folder.

python timeit.py <video> <chat.txt> <label> <normal|light> <auto|cpu> <outdir>
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(r"C:\Users\redmo\Desktop\projeler\ClipForge")
PY = str(REPO / ".venv" / "Scripts" / "python.exe")
CLI = str(REPO / "backend" / "cli.py")
REAL_MODELS = Path.home() / ".sharkyclips" / "models"

video, chat, label, preset, device, outdir = sys.argv[1:7]
import threading

GAMES = ("deltaforceclient", "league of legends.exe", "leagueclient")


def game_running() -> bool:
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.lower()
    return any(g in out for g in GAMES)


DISTURBED = []


def watch():  # a game during the run makes its numbers worthless: the runner redoes it
    while True:
        if game_running():
            DISTURBED.append(time.strftime("%H:%M:%S"))
        time.sleep(30)


threading.Thread(target=watch, daemon=True).start()
outdir = Path(outdir)
outdir.mkdir(parents=True, exist_ok=True)
home = Path(tempfile.mkdtemp(prefix=f"sc-time-{label}-"))
ws = home / "ws"
ws.mkdir()
(home / "dl").mkdir()
(home / "config.json").write_text(json.dumps({
    "workspace_dir": str(ws), "performance_preset": preset, "processing_device": device,
    "light_checked": True, "language": "en", "content_language": "en"}), encoding="utf-8")
# copy (never link) the small helper models so nothing is downloaded again
for sub in ("align", "ced-mini", "yunet", "voices"):
    if (REAL_MODELS / sub).is_dir():
        shutil.copytree(REAL_MODELS / sub, home / "models" / sub)
env = dict(os.environ, SHARKYCLIPS_HOME=str(home), SHARKYCLIPS_NO_MIGRATE="1",
           SHARKYCLIPS_DOWNLOADS=str(home / "dl"), SHARKYCLIPS_QUEUE_HOME=str(home / "queue"),
           PYTHONIOENCODING="utf-8")
log = open(outdir / f"{label}.log", "w", encoding="utf-8")
res = {"label": label, "preset": preset, "device": device, "video": video, "home": str(home), "steps": {},
       "cpu": platform.processor(), "started": time.strftime("%Y-%m-%d %H:%M:%S")}


def run(name, *args):
    t = time.time()
    p = subprocess.run([PY, CLI, *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    dt = time.time() - t
    log.write(f"\n===== {name} ({dt:.1f}s, rc={p.returncode})\n{p.stdout}\n")
    log.flush()
    res["steps"][name] = round(dt, 1)
    (outdir / f"{label}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    if p.returncode:
        raise SystemExit(f"{name} failed, see log")
    return p.stdout


T0 = time.time()
run("ingest", "ingest", video)
pid = json.loads(subprocess.run([PY, "-c", "import json,sys,pathlib;print(json.dumps([p.name for p in pathlib.Path(sys.argv[1]).iterdir() if p.is_dir() and not p.name.startswith('_')]))", str(ws)], capture_output=True, text=True).stdout)[0]
res["project"] = pid
if chat != "-":
    run("chat", "chat", pid, "--file", chat)
run("transcribe", "transcribe", pid)
run("highlights", "highlights", pid)
run("analyze", "analyze", pid, "--lang", "en", "--no-translate")
run("render", "render", pid, "1", "2", "3", "4", "5", "6")
res["total"] = round(time.time() - T0, 1)
res["disturbed"] = DISTURBED[:5]
res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
(outdir / f"{label}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res))
