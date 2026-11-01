"""1.2.11: one SharkyClips server per settings folder, and renames that wait out a short lock.

Found in the real upload test: a second server (port 8001) started while the first restarted
after an update; both schedulers rendered the same scheduled clip and the second rename failed
with WinError 5 (the first file was being read)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import cli
from sharkyclips import __version__, config, instance
from sharkyclips.project import replace_retry

BACKEND = Path(__file__).resolve().parents[1]
HOLD = (
    "import sys; sys.path.insert(0, sys.argv[1]); from sharkyclips import instance\n"
    "f = instance.acquire()\n"
    "instance.note(int(sys.argv[2])) if f else None\n"
    "print('held' if f else 'busy', flush=True)\n"
    "sys.stdin.read()\n"
)


@pytest.fixture
def holder():
    """Another process (like a running `serve` supervisor) holding the server lock."""
    procs: list[subprocess.Popen] = []

    def start(port: int) -> subprocess.Popen:
        p = subprocess.Popen([sys.executable, "-c", HOLD, str(BACKEND), str(port)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert p.stdout.readline().strip() == "held"
        procs.append(p)
        return p

    yield start
    for p in procs:
        if p.poll() is None:
            p.kill()
            p.wait(5)
    (config.config_dir() / instance.INFO_FILE).unlink(missing_ok=True)


class _Meta:
    """A fake SharkyClips answering /api/meta."""

    def __init__(self, version: str = __version__):
        me = self
        self.version = version

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):  # noqa: N802
                raw = json.dumps({"version": me.version, "reason_codes": {}}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()


def test_lock_is_exclusive_and_dies_with_its_process(holder):
    assert instance.running() is None
    p = holder(8123)
    assert instance.acquire() is None
    assert instance.running()["port"] == 8123
    p.kill()
    p.wait(5)
    mine = instance.acquire(wait=5)  # the OS drops a dead process's lock (Windows: a moment later)
    assert mine is not None
    instance.release(mine)
    assert instance.running() is None


def test_waiting_rereads_a_port_note_written_after_the_lock(holder):
    """A supervisor takes the lock first and writes its port a moment later."""
    fake = _Meta()
    try:
        holder(fake.port)
        info = instance.running()
        (config.config_dir() / instance.INFO_FILE).unlink()  # as if not written yet
        threading.Timer(0.6, lambda: (config.config_dir() / instance.INFO_FILE).write_text(
            json.dumps(info), encoding="utf-8")).start()
        assert cli._wait_for_running({}, wait=5) == (fake.port, __version__)
    finally:
        fake.stop()


def test_serve_takes_over_when_the_lock_holder_died(holder, monkeypatch):
    """Clicking the shortcut right after a crash: the lock is still held for a moment and nothing
    answers. serve must start (once the lock is free), not silently do nothing."""
    p = holder(1)  # nothing answers on its port
    monkeypatch.setattr(cli, "_wait_for_running", lambda info, wait=30.0: (p.kill(), (None, None))[1])
    started: list[int] = []
    monkeypatch.setattr(cli, "_serve_locked", lambda args, code: started.append(args.port) or 0)

    class Args:
        port, lan, no_browser, tray = 8998, False, True, False

    assert cli.cmd_serve(Args()) == 0
    assert started == [8998]
    assert instance.running() is None  # released after serving


def test_a_stale_port_note_without_a_lock_is_ignored():
    (config.config_dir() / instance.INFO_FILE).write_text('{"pid": 1, "port": 8000}', encoding="utf-8")
    assert instance.running() is None
    assert not (config.config_dir() / instance.INFO_FILE).exists()


def test_second_serve_opens_the_running_one_instead_of_starting(holder, monkeypatch):
    fake = _Meta()
    try:
        holder(fake.port)
        monkeypatch.setattr(cli, "_serve_locked", lambda *a: pytest.fail("a second server started"))
        opened: list[str] = []
        monkeypatch.setattr("webbrowser.open", lambda u, *a, **k: opened.append(u))

        class Args:
            port, lan, no_browser, tray = 8999, False, False, False

        assert cli.cmd_serve(Args()) == 0
        assert opened == [f"http://localhost:{fake.port}"]
    finally:
        fake.stop()


def test_launch_waits_for_a_restarting_server_instead_of_starting_another(holder, monkeypatch):
    """The 8001 case: the lock holder's server is restarting (not answering yet)."""
    fake = _Meta()
    port = fake.port
    fake.stop()  # restarting: nothing answers on its port for a moment
    holder(port)
    later: dict = {}
    threading.Timer(1.0, lambda: later.setdefault("srv", _restart_on(port))).start()
    monkeypatch.setattr(cli, "cmd_serve", lambda a: pytest.fail("a second server started"))
    monkeypatch.setattr(cli, "_migrate_windows_shortcuts", lambda: None)
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda u, *a, **k: opened.append(u))
    try:
        assert cli.cmd_launch(type("A", (), {"tray": False})()) == 0
        assert opened == [f"http://localhost:{port}"]
    finally:
        if "srv" in later:
            later["srv"].shutdown()
            later["srv"].server_close()


def _restart_on(port: int) -> ThreadingHTTPServer:
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            raw = json.dumps({"version": __version__, "reason_codes": {}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_replace_retry_waits_while_the_destination_is_open(tmp_path):
    dest, tmp = tmp_path / "clip.mp4", tmp_path / "clip.partial.mp4"
    dest.write_bytes(b"old")
    tmp.write_bytes(b"new")
    reader = open(dest, "rb")  # Windows: an open file can't be replaced (like a preview playing it)
    threading.Timer(0.4, reader.close).start()
    t = time.monotonic()
    replace_retry(tmp, dest, seconds=5)
    assert dest.read_bytes() == b"new" and not tmp.exists()
    if os.name == "nt":
        assert time.monotonic() - t >= 0.3


def test_replace_retry_gives_up_after_its_time(tmp_path):
    if os.name != "nt":
        pytest.skip("POSIX replaces open files")
    dest, tmp = tmp_path / "a.mp4", tmp_path / "a.partial.mp4"
    dest.write_bytes(b"x")
    tmp.write_bytes(b"y")
    with open(dest, "rb"), pytest.raises(PermissionError):
        replace_retry(tmp, dest, seconds=0.3)
