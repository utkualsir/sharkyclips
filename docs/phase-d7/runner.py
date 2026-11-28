"""Run the remaining benchmarks only while no game runs (phase D7).

python runner.py <scratch-dir>   (inputs in <scratch>/real, results in <scratch>/timing2)

A run starts after 5 minutes without a game. When a game starts during a run, the run is stopped at
once (its whole process tree and the local AI server) so the game gets the PC back, and it is redone
from the start later: a run that shared the PC with a game would give wrong numbers anyway.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = str(HERE.parents[1] / ".venv" / "Scripts" / "python.exe")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
GAMES = ("deltaforceclient", "league of legends.exe", "leagueclient")
scratch = Path(sys.argv[1])
out = scratch / "timing2"
# Light / CPU only for 1 hour: the 3-hour Light time is estimated from it (owner's decision, docs/phase-d7.md)
SPECS = [("real180", "gpu180", "normal", "auto"), ("real60", "light60", "light", "cpu")]


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(out / "runner.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def game_running():
    t = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, creationflags=NOWIN).stdout.lower()
    return any(g in t for g in GAMES)


def wait_quiet(minutes=5):
    quiet_since = None
    while True:
        if game_running():
            quiet_since = None
        elif quiet_since is None:
            quiet_since = time.time()
        elif time.time() - quiet_since >= minutes * 60:
            return
        time.sleep(15)


def kill_tree(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=NOWIN)
    # the AI server the run started (nothing else of SharkyClips runs while benchmarking)
    subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True, creationflags=NOWIN)


def running_pids(label):
    """timeit runs of this label that an earlier runner started (taken over, not restarted)."""
    ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'timeit.py' "
          f"-and $_.CommandLine -match ' {label} ' }} | ForEach-Object {{ $_.ProcessId }}")
    o = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, creationflags=NOWIN).stdout
    return [int(x) for x in o.split()]


for src, label, preset, device in SPECS:
    res = out / f"{label}.json"
    pids = running_pids(label)
    while pids:  # take over a run that is already going: keep yielding to games
        if game_running():
            log(f"game started: stopping the running {label}, will redo it")
            for pid in pids:
                kill_tree(pid)
            break
        time.sleep(10)
        pids = running_pids(label)
    while True:
        if res.exists() and "total" in json.loads(res.read_text(encoding="utf-8")) \
                and not json.loads(res.read_text(encoding="utf-8")).get("disturbed"):
            log(f"{label} already done")
            break
        wait_quiet()
        if res.exists():
            res.unlink()  # a stopped run's partial result (file made by this script's own run)
        log(f"start {label}")
        p = subprocess.Popen([PY, str(HERE / "timeit.py"), str(scratch / "real" / f"{src}.mp4"), "-", label, preset,
                              device, str(out)], creationflags=NOWIN, cwd=str(HERE))
        aborted = False
        while p.poll() is None:
            if game_running():
                log(f"game started: stopping {label}, will redo it")
                kill_tree(p.pid)
                aborted = True
                break
            time.sleep(10)
        if aborted:
            continue
        log(f"{label} finished rc={p.returncode}")
        if p.returncode:
            log(f"{label} FAILED, see {label}.log")
            break
log("ALLDONE")
