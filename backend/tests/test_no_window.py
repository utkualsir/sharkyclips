"""No console window ever flashes up: every process SharkyClips starts is hidden, and the
governor's loop starts none at all."""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path

import pytest

from sharkyclips import governor, procs, sysmon

BACKEND = Path(__file__).resolve().parents[1]
SPAWNERS = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
# Anything that starts a program without going through subprocess (no way to hide its window).
FORBIDDEN = {("os", "system"), ("os", "popen"), ("os", "startfile"), ("os", "execv"), ("os", "execvp"),
             ("os", "spawnl"), ("os", "spawnv"), ("os", "posix_spawn"),
             ("asyncio", "create_subprocess_exec"), ("asyncio", "create_subprocess_shell")}
SAFE_IMPORTS = {"PIPE", "DEVNULL", "STDOUT", "TimeoutExpired", "SubprocessError", "CalledProcessError",
                "CompletedProcess", "STARTUPINFO", "CREATE_NO_WINDOW"}


def _sources() -> list[Path]:
    files = [BACKEND / "cli.py", *sorted((BACKEND / "sharkyclips").rglob("*.py"))]
    assert len(files) > 20
    return files


def _uses_no_window(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg is None and isinstance(kw.value, ast.Call):  # **no_window() / **procs.no_window(...)
            fn = kw.value.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name == "no_window":
                return True
    return False


def test_every_subprocess_call_hides_its_window():
    bad = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        rel = path.relative_to(BACKEND)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                bad += [f"{rel}:{node.lineno} from subprocess import {a.name} (call subprocess.X instead)"
                        for a in node.names if a.name not in SAFE_IMPORTS]
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            owner = node.func.value
            mod = owner.id if isinstance(owner, ast.Name) else None
            if (mod, node.func.attr) in FORBIDDEN:
                bad.append(f"{rel}:{node.lineno} {mod}.{node.func.attr}() can't hide its window")
            elif mod == "subprocess" and node.func.attr in SPAWNERS and not _uses_no_window(node):
                bad.append(f"{rel}:{node.lineno} subprocess.{node.func.attr}() without **no_window()")
    assert not bad, "Console windows would flash up:\n" + "\n".join(bad)


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_no_window_flags_and_hidden_startupinfo():
    kw = procs.no_window(0x4)
    assert kw["creationflags"] == subprocess.CREATE_NO_WINDOW | 0x4
    si = kw["startupinfo"]
    assert si.dwFlags & subprocess.STARTF_USESHOWWINDOW and si.wShowWindow == 0  # SW_HIDE
    assert procs.no_window()["startupinfo"] is not si  # a fresh one per call (Popen mutates it)
    res = subprocess.run(["cmd", "/c", "exit 3"], capture_output=True, **procs.no_window())
    assert res.returncode == 3


def test_no_window_is_empty_elsewhere(monkeypatch):
    monkeypatch.setattr(procs, "IS_WIN", False)
    assert procs.no_window(0x8) == {}


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_safety_net_adds_hidden_startupinfo(monkeypatch):
    seen = []
    monkeypatch.setattr(subprocess.Popen, "__init__", lambda self, *a, **kw: seen.append(kw))
    monkeypatch.setattr(procs, "_hidden", False)
    procs.hide_child_windows()
    subprocess.Popen(["yt-dlp"])  # a library's own call, without our kwargs
    mine = subprocess.STARTUPINFO()
    subprocess.Popen(["x"], startupinfo=mine)
    for kw in seen:
        assert kw["creationflags"] & subprocess.CREATE_NO_WINDOW
        assert kw["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW and kw["startupinfo"].wShowWindow == 0
    assert seen[1]["startupinfo"] is mine


def test_governor_loop_starts_no_processes(monkeypatch):
    """Sensors and decisions (games, video, fullscreen, NVML, GPU counters) are in-process only."""
    spawned = []

    def no_spawn(self, args, *a, **kw):
        spawned.append(args)
        raise AssertionError(f"governor started a process: {args}")

    monkeypatch.setattr(subprocess.Popen, "__init__", no_spawn)
    monkeypatch.setattr(os, "system", lambda *a: spawned.append(a) or 1)
    sysmon.read_user()
    g = governor.Governor(busy=lambda: True)  # not started: tick by hand
    try:
        for i in range(6):
            g._viewer_at = 1e18 if i % 2 else 0  # full ticks (UI open) and light ticks
            g.tick()
    finally:
        # Real sensors: while someone uses this PC the governor may decide to pause, which
        # suspends every tracked child - later tests' ffmpeg calls would hang. Undo it.
        monkeypatch.undo()
        procs.resume_all()
    assert spawned == []
    assert g.sample is not None


@pytest.mark.skipif(os.name != "nt", reason="Windows only")
def test_never_detached(monkeypatch):
    """A detached child (no console) makes each console program it starts open a new window:
    ollama serve -> llama-server / gpu-discover flashed up every second or two."""
    assert procs.no_window(0x8 | 0x4)["creationflags"] == subprocess.CREATE_NO_WINDOW | 0x4
    seen = []
    monkeypatch.setattr(subprocess.Popen, "__init__", lambda self, *a, **kw: seen.append(kw["creationflags"]))
    monkeypatch.setattr(procs, "_hidden", False)
    procs.hide_child_windows()
    subprocess.Popen(["ollama", "serve"], creationflags=0x8)  # DETACHED_PROCESS from a library
    assert seen == [subprocess.CREATE_NO_WINDOW]
