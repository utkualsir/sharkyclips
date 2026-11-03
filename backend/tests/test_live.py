"""Automation + live (1.2.17): OBS detection, the folder watcher, live markers, the hotkey and
live chat (Twitch IRC / YouTube). The phone side is test_phone.py."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import threading
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import config, livechat, markers, obs, watch
from sharkyclips.project import Project, read_json, write_json_atomic


@pytest.fixture(autouse=True)
def _clean():
    keys = ("auto_clip_enabled", "watch_folders", "watch_publish", "marker_hotkey", "live_clip_command",
            "live_twitch_channel", "easy_replay", "easy_bubbles", "easy_memes")
    yield
    config.update(**{k: None for k in keys})
    for p in (watch.state_path(), markers.store_path()):
        p.unlink(missing_ok=True)
    shutil.rmtree(config.config_dir() / "live", ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_leftover_projects():
    """Projects made by a test are removed afterwards (other tests expect an empty workspace)."""
    before = set(config.workspace_dir().iterdir())
    yield
    for d in set(config.workspace_dir().iterdir()) - before:
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


# ===================================================================== OBS settings


def _obs_home(tmp_path: Path, simple: bool = True, user_ini: bool = False, remux: str = "true") -> Path:
    home = tmp_path / "obs-studio"
    prof = home / "basic" / "profiles" / "Başlıksız"
    prof.mkdir(parents=True)
    (home / ("user.ini" if user_ini else "global.ini")).write_text(
        f"\ufeff[Basic]\nProfile=Başlıksız\nProfileDir=Başlıksız\n\n[Video]\nAutoRemux={remux}\n", encoding="utf-8")
    if simple:
        basic = "[Output]\nMode=Simple\n\n[SimpleOutput]\nFilePath=D:/Rec\nRecFormat2=mkv\n"
    else:
        basic = "[Output]\nMode=Advanced\n\n[AdvOut]\nRecType=Standard\nRecFilePath=E:\\Streams\nRecFormat2=hybrid_mp4\n"
    (prof / "basic.ini").write_text(basic, encoding="utf-8")
    ws = home / "plugin_config" / "obs-websocket"
    ws.mkdir(parents=True)
    (ws / "config.json").write_text(json.dumps({"server_enabled": True, "server_port": 4466, "auth_required": True,
                                                "server_password": "pw"}), encoding="utf-8")
    return home


def test_obs_settings_simple_and_advanced(tmp_path, monkeypatch):
    monkeypatch.setenv("OBS_HOME", str(_obs_home(tmp_path / "a")))
    s = obs.settings()
    assert s["found"] and s["record_dir"].replace("\\", "/") == "D:/Rec" and s["format"] == "mkv"
    assert s["auto_remux"] is True and s["profile"] == "Başlıksız"
    assert s["websocket"] == {"enabled": True, "port": 4466, "password": "pw"}
    monkeypatch.setenv("OBS_HOME", str(_obs_home(tmp_path / "b", simple=False, user_ini=True, remux="false")))
    s = obs.settings()
    assert s["record_dir"].endswith("Streams") and s["format"] == "mp4" and s["auto_remux"] is False
    monkeypatch.setenv("OBS_HOME", str(tmp_path / "none"))
    assert obs.settings()["found"] is False and obs.connection() is None


class FakeObs:
    """A tiny obs-websocket v5 server: hello with auth, identify, GetRecordStatus / GetVersion."""

    def __init__(self, password: str = "pw", ms: int = 754_321):
        self.password, self.ms = password, ms
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(c,), daemon=True).start()

    @staticmethod
    def _send(c, obj):
        data = json.dumps(obj).encode()
        head = bytes([0x81, len(data)]) if len(data) < 126 else bytes([0x81, 126]) + len(data).to_bytes(2, "big")
        c.sendall(head + data)

    @staticmethod
    def _recv(c):
        b0, b1 = c.recv(2)
        n = b1 & 0x7F
        if n == 126:
            n = int.from_bytes(c.recv(2), "big")
        mask = c.recv(4)
        data = b""
        while len(data) < n:
            data += c.recv(n - len(data))
        if b0 & 0x0F == 0x8:
            return None
        return json.loads(bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _client(self, c):
        req = b""
        while b"\r\n\r\n" not in req:
            req += c.recv(1024)
        key = [ln.split(":", 1)[1].strip() for ln in req.decode().split("\r\n") if ln.lower().startswith("sec-websocket-key")][0]
        acc = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        c.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Accept: {acc}\r\n\r\n".encode())
        self._send(c, {"op": 0, "d": {"rpcVersion": 1, "authentication": {"salt": "s4lt", "challenge": "ch4l"}}})
        ident = self._recv(c)
        if ident["d"].get("authentication") != obs.auth_string(self.password, "s4lt", "ch4l"):
            c.sendall(bytes([0x88, 0]))
            c.close()
            return
        self._send(c, {"op": 2, "d": {"negotiatedRpcVersion": 1}})
        while True:
            msg = self._recv(c)
            if msg is None:
                break
            d = msg["d"]
            data = {"outputActive": True, "outputPaused": False, "outputDuration": self.ms} \
                if d["requestType"] == "GetRecordStatus" else {"obsVersion": "31.0.0", "obsWebSocketVersion": "5.5"}
            self._send(c, {"op": 7, "d": {"requestType": d["requestType"], "requestId": d["requestId"],
                                          "requestStatus": {"result": True, "code": 100}, "responseData": data}})
        c.close()


def test_obs_websocket_client(monkeypatch):
    srv = FakeObs()
    config.update(obs_ws_port=srv.port, obs_ws_password="pw")
    try:
        assert obs.record_status() == {"active": True, "paused": False, "ms": 754_321}
        assert obs.check()["ok"] is True
        config.update(obs_ws_password="wrong")
        assert obs.record_status() is None
        assert obs.check()["reason"] == "password"
        config.update(obs_websocket="off")
        assert obs.record_status() is None
    finally:
        config.update(obs_ws_port=None, obs_ws_password=None, obs_websocket=None)


# ===================================================================== folder watcher


def _write(path: Path, size: int) -> None:
    with open(path, "ab") as f:
        f.write(b"\0" * size)


def test_watch_scan_waits_for_a_finished_file(tmp_path):
    rec = tmp_path / "rec"
    rec.mkdir()
    old = rec / "old.mkv"
    _write(old, watch.MIN_BYTES + 10)
    st = {"baseline": time.time() + 1, "files": {}}
    pending: dict = {}
    os.utime(old, (time.time() - 100, time.time() - 100))
    now = time.time() + 2
    new = rec / "2026-11-03 20-00-00.mp4"
    _write(new, watch.MIN_BYTES + 10)
    os.utime(new, (now, now))
    paths = [old, new]
    unlocked = lambda p: False  # noqa: E731
    assert watch.scan(paths, st, pending, now, unlocked) == []  # first look: remembered
    assert str(old) not in pending  # it was there before the switch
    assert watch.scan(paths, st, pending, now + 5, unlocked) == []  # not stable long enough
    _write(new, 1000)  # still growing: the clock starts again
    os.utime(new, (now + 6, now + 6))
    assert watch.scan(paths, st, pending, now + 30, unlocked) == []
    assert watch.scan(paths, st, pending, now + 40, lambda p: True) == []  # 10 s: not stable yet
    assert watch.scan(paths, st, pending, now + 52, lambda p: True) == []  # stable but someone writes it
    assert watch.scan(paths, st, pending, now + 60, unlocked) == []  # unlocked: wait the stable time again
    got = watch.scan(paths, st, pending, now + 80, unlocked)
    assert got == [new] and st["files"][str(new)]["status"] == "ready"
    assert watch.scan(paths, st, pending, now + 200, unlocked) == []  # never twice


def test_watch_remux_twin_and_small_files(tmp_path):
    rec = tmp_path / "rec"
    rec.mkdir()
    now = time.time() + 5
    mkv, mp4, tiny = rec / "a.mkv", rec / "a.mp4", rec / "replay.mp4"
    for p, size in ((mkv, watch.MIN_BYTES + 5), (mp4, watch.MIN_BYTES + 5), (tiny, 1000)):
        _write(p, size)
        os.utime(p, (now, now))
    st = {"baseline": now - 10, "files": {}}
    pending: dict = {}
    for t in (now, now + 100):
        got = watch.scan([mkv, mp4, tiny], st, pending, t, lambda p: False)
    assert got == [mp4]
    assert st["files"][str(mkv)]["reason"] == "remuxed" and st["files"][str(tiny)]["reason"] == "too_small"
    # OBS remuxes later: the MKV waits for its MP4 copy
    st2 = {"baseline": now - 10, "files": {}}
    pending2: dict = {}
    watch.scan([mkv], st2, pending2, now, lambda p: False, auto_remux=True)
    assert watch.scan([mkv], st2, pending2, now + 60, lambda p: False, auto_remux=True) == []
    assert watch.scan([mkv], st2, pending2, now + 60 + watch.REMUX_WAIT_S, lambda p: False, auto_remux=True) == [mkv]


@pytest.mark.skipif(os.name != "nt", reason="the write lock check is Windows only")
def test_is_locked_while_written(tmp_path):
    p = tmp_path / "rec.mp4"
    with open(p, "ab") as f:
        f.write(b"x" * 100)
        assert watch.is_locked(p) is True
    assert watch.is_locked(p) is False


def test_watch_state_survives_restart_and_settings(tmp_path):
    rec = tmp_path / "rec"
    rec.mkdir()
    config.update(watch_folders=[str(rec)])
    watch.enable(True)
    s = watch.settings()
    assert s["enabled"] and s["folders"] == [str(rec)] and s["render_top"] == 6 and s["publish"] == "off"
    watch.mark(rec / "x.mp4", status="imported", project_id="p1")
    assert watch.load_state()["files"][str(rec / "x.mp4")]["project_id"] == "p1"
    assert watch.recent()[0]["name"] == "x.mp4"


# ===================================================================== live markers


def test_markers_add_dedupe_and_recording_time():
    t0 = 1_800_000_000.0
    m1 = markers.add("hotkey", at=t0 + 100, rec={"active": True, "ms": 90_500})
    assert m1["rec_ms"] == 90_500
    assert markers.add("chat", by="mod1", at=t0 + 102, rec=None) is None  # the same moment
    m2 = markers.add("chat", by="mod1", at=t0 + 300, rec=None)
    assert m2 is not None and "rec_ms" not in m2
    got, start = markers.for_recording(t0, t0 + 1000)
    # OBS said the first mark was at 90.5 s: the recording really started 9.5 s after t0 (a pause / late start)
    assert start == pytest.approx(t0 + 9.5)
    assert [g["t"] for g in got] == [90.5, pytest.approx(290.5)]
    assert got[0]["exact"] and not got[1]["exact"]
    assert markers.for_recording(t0 + 5000, t0 + 6000)[0] == []
    assert markers.remove(m2["id"]) and not markers.remove("nope")


def test_hotkey_parse():
    assert markers.parse_hotkey("Ctrl+Alt+C") == (0x3, ord("C"))
    assert markers.parse_hotkey("shift+f9") == (0x4, 0x78)
    assert markers.parse_hotkey("f10") == (0, 0x79)
    assert markers.normalize_hotkey("ALT + ctrl + c") == "ctrl+alt+c"
    for bad in ("", "c", "ctrl+", "hyper+c", "ctrl+ö"):
        with pytest.raises(ValueError):
            markers.parse_hotkey(bad)


@pytest.mark.skipif(os.name != "nt", reason="global hotkeys: Windows only")
def test_hotkey_registers_and_fires():
    import ctypes

    pressed = threading.Event()
    hk = markers.Hotkey(pressed.set)
    combo = next((c for c in (f"ctrl+alt+shift+f{n}" for n in range(24, 13, -1)) if hk.start(c) == "on"), None)
    assert combo is not None  # some rarely used shortcut is free on any machine
    other = markers.Hotkey(lambda: None)
    try:
        assert other.start(combo) == "taken"  # already registered: told, not crashed
        # simulate the key press: the WM_HOTKEY message the system would post
        ctypes.windll.user32.PostThreadMessageW(hk._tid, 0x0312, markers.Hotkey.HOTKEY_ID, 0)
        assert pressed.wait(3)
    finally:
        hk.stop()
        other.stop()
    assert hk.status == "off"
    assert markers.Hotkey(lambda: None).start("nonsense+x") == "invalid"


def _wav(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(np.zeros(int(seconds * 16000), np.int16).tobytes())


def test_markers_become_top_candidates():
    from sharkyclips.highlights.candidates import pick_candidates
    from sharkyclips.highlights.context import AnalysisContext
    from sharkyclips.highlights.modes import get_mode
    from sharkyclips.highlights.signals.base import ReasonEvent, SignalResult

    d = config.workspace_dir() / "marker-cands"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": 600, "mode": "gaming"})
    _wav(d / "audio.wav", 600)
    words = [{"start": float(i), "end": i + 0.6, "word": " a."} for i in range(0, 600, 2)]
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [{"start": 0, "end": 600, "words": words}]})
    proj = Project("marker-cands", d)
    write_json_atomic(d / "markers.json", {"markers": [{"t": 400.0, "source": "chat", "by": "mod"},
                                                       {"t": 406.0, "source": "hotkey"}]})
    ctx = AnalysisContext(proj, get_mode("gaming"))
    curve = np.zeros(600)
    curve[100] = 1.0  # one loud moment elsewhere
    curve[99], curve[101] = 0.6, 0.6

    class Hype:
        smoothed = curve
        combined = curve
        results = {"loudness": SignalResult("loudness", curve, [ReasonEvent(100, "loudness_spike", "+10 dB", 1.0)])}
        shares = {"loudness": 1.0}

    cands = pick_candidates(ctx, Hype(), top=3)
    first = cands[0]
    assert first.marker is not None and first.reasons[0]["code"] == "marker"
    assert first.start <= 400 - 10 and first.end >= 407  # the build-up and both marks are in it
    assert sum(c.marker is not None for c in cands) == 1  # two marks 6 s apart = one clip
    assert any(c.marker is None and c.start <= 100 <= c.end for c in cands)


# ===================================================================== live chat


def test_parse_irc_and_command():
    line = ("@badge-info=;badges=moderator/1;color=#FF0000;display-name=ModGuy;mod=1;tmi-sent-ts=1700000000000 "
            ":modguy!modguy@modguy.tmi.twitch.tv PRIVMSG #streamer :!clip what a shot")
    m = livechat.parse_irc(line)
    assert m["user"] == "ModGuy" and m["mod"] and not m["owner"] and m["color"] == "#FF0000"
    assert m["at"] == 1_700_000_000 and m["text"] == "!clip what a shot"
    assert livechat.is_command(m["text"], "!clip") == (True, "what a shot")
    assert livechat.is_command("!clipboard", "!clip")[0] is False
    assert livechat.parse_irc(":tmi.twitch.tv 001 justinfan :Welcome") is None
    own = livechat.parse_irc("@badges=broadcaster/1 :me!me@me PRIVMSG #me :!CLIP")
    assert own["owner"] and livechat.is_command(own["text"], "!clip")[0]


def test_twitch_reader_against_a_fake_irc_server(monkeypatch):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    got_join = threading.Event()

    def serve():
        c, _ = srv.accept()
        buf = b""
        while b"JOIN #streamer" not in buf:
            buf += c.recv(1024)
        got_join.set()
        c.sendall(b"PING :tmi.twitch.tv\r\n")
        ts = str(int(time.time() * 1000)).encode()
        c.sendall(b"@badges=moderator/1;display-name=Mod;tmi-sent-ts=" + ts + b" :mod!m@m PRIVMSG #streamer :!clip\r\n")
        c.sendall(b"@badges=;display-name=Viewer;color=#00FF00 :v!v@v PRIVMSG #streamer :!clip\r\n")
        c.sendall(b"@badges=;display-name=Viewer :v!v@v PRIVMSG #streamer :LETS GO\r\n")
        pong = b""
        while b"PONG" not in pong:
            pong += c.recv(1024)
        time.sleep(0.3)
        c.close()

    threading.Thread(target=serve, daemon=True).start()
    monkeypatch.setenv("SHARKYCLIPS_TWITCH_IRC", f"127.0.0.1:{port}")
    from sharkyclips.web.live import LiveService

    svc = LiveService()
    seen: list = []

    def on(msg):
        seen.append(msg)
        svc.on_chat(msg)

    r = livechat.TwitchReader("#Streamer", on).start()
    try:
        assert got_join.wait(5)
        deadline = time.time() + 5
        while len(seen) < 3 and time.time() < deadline:
            time.sleep(0.05)
    finally:
        r.stop()
    assert [m["user"] for m in seen] == ["Mod", "Viewer", "Viewer"]
    mk = markers.recent()
    assert len(mk) == 1 and mk[0]["by"] == "Mod" and mk[0]["source"] == "chat"  # viewers can't mark
    rows = livechat.rows_between(time.time() - 60, time.time() + 10)
    assert {r["text"] for r in rows} == {"!clip", "LETS GO"}


def test_live_chat_becomes_the_projects_chat():
    d = config.workspace_dir() / "live-chat-proj"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": 100})
    proj = Project("live-chat-proj", d)
    t0 = time.time() - 50
    livechat.record("twitch", "Efe", "first", "#FF0000", at=t0 + 10)
    livechat.record("twitch", "Bob", "second", None, at=t0 + 20)
    livechat.record("twitch", "Bob", "too late", None, at=t0 + 500)
    assert livechat.attach(proj, t0, t0 + 100) == 2
    chat = read_json(d / "chat.json")
    assert chat["source"] == "live" and chat["names"] == ["Efe", "Bob"] and chat["colors"] == {"Efe": "#FF0000"}
    assert [m[0] for m in chat["messages"]] == [pytest.approx(10, abs=0.01), pytest.approx(20, abs=0.01)]
    assert livechat.attach(proj, t0, t0 + 100) == 0  # never replaces an existing chat


def test_youtube_reader_marks_owner_and_mods(monkeypatch):
    from sharkyclips import youtube

    monkeypatch.setattr(youtube, "connected", lambda: True)
    monkeypatch.setattr(youtube, "_get", lambda path, params: {"items": [{"snippet": {"liveChatId": "chat1"}}]})
    pages = [{"items": [{"snippet": {"displayMessage": "old !clip"}, "authorDetails": {"isChatOwner": True}}],
              "nextPageToken": "a", "pollingIntervalMillis": 10},
             {"items": [{"snippet": {"displayMessage": "!clip", "publishedAt": "2026-11-03T20:00:00Z"},
                         "authorDetails": {"displayName": "Me", "isChatOwner": True}},
                        {"snippet": {"displayMessage": "!clip"}, "authorDetails": {"displayName": "Rando"}}],
              "nextPageToken": "b", "pollingIntervalMillis": 10}]
    calls = []

    def call(method, path, params, **kw):
        calls.append(params.get("pageToken"))
        return pages[min(len(calls) - 1, 1)] if len(calls) <= 2 else {"items": [], "pollingIntervalMillis": 10}

    monkeypatch.setattr(youtube, "_call", call)
    monkeypatch.setattr(livechat, "YT_MIN_POLL_S", 0.01)
    seen: list = []
    r = livechat.YoutubeReader(seen.append).start()
    deadline = time.time() + 5
    while len(seen) < 2 and time.time() < deadline:
        time.sleep(0.02)
    r.stop()
    assert [m["user"] for m in seen[:2]] == ["Me", "Rando"]  # the backlog page was skipped
    assert seen[0]["owner"] and not seen[1]["owner"] and calls[:2] == [None, "a"]


# ===================================================================== API


def test_live_settings_api(tmp_path):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    rec = tmp_path / "rec"
    rec.mkdir()
    r = client.put("/api/live/watch", json={"enabled": True})
    assert r.status_code == 400  # no folder known (no OBS in tests)
    v = client.put("/api/live/watch", json={"folders": [str(rec)], "enabled": True, "render_top": 4,
                                            "publish": "plan"}).json()
    assert v["watch"]["enabled"] and v["watch"]["folders"] == [str(rec)] and v["watch"]["render_top"] == 4
    assert client.put("/api/live/watch", json={"folders": [str(tmp_path / "missing")]}).status_code == 400
    v = client.put("/api/live/markers", json={"hotkey": "Alt+Ctrl+X", "twitch_channel": "https://twitch.tv/Some_One",
                                              "command": "!klip"}).json()
    assert v["markers"]["hotkey"] == "ctrl+alt+x" and v["markers"]["twitch_channel"] == "some_one"
    assert v["markers"]["command"] == "!klip"
    from sharkyclips.web.live import service

    service().reconfigure()  # the test turned a Twitch reader on: stop it again
    config.update(live_twitch_channel="")
    service().reconfigure()
    assert client.put("/api/live/markers", json={"hotkey": "q"}).status_code == 400
    assert client.put("/api/live/markers", json={"command": "clip now"}).status_code == 400
    m = client.post("/api/live/markers", json={}).json()
    assert m["marker"]["source"] == "button"
    s = client.put("/api/easy/settings", json={"replay": False, "memes": "light", "auto_clip": False}).json()
    assert s["replay"] is False and s["memes"] == "light" and s["auto_clip"] is False and s["bubbles"] is True



def test_easy_fx_defaults_only_for_new_projects():
    from sharkyclips import easy as E

    assert E.fx_options({"fx": True}) == {"replay": "auto", "chat_bubbles": True, "memes": "off"}
    assert E.fx_options({"fx": False}) == {"replay": "off", "chat_bubbles": False, "memes": "off"}
    config.update(easy_memes="light", easy_replay=True)  # a switch the user flipped applies everywhere
    assert E.fx_options({"fx": False}) == {"replay": "auto", "chat_bubbles": False, "memes": "light"}


def test_service_tick_imports_a_simulated_obs_recording(tmp_path, monkeypatch):
    """OBS writes a recording (held open = locked), stops; the watcher imports it exactly once."""
    from sharkyclips.web import app as appmod
    from sharkyclips.web import live

    rec = tmp_path / "rec"
    rec.mkdir()
    config.update(watch_folders=[str(rec)])
    live.enable_auto(True)
    submitted = []

    class J:
        id = "job1"

    monkeypatch.setattr(appmod, "submit_import", lambda *a, **k: (submitted.append((a, k)), J())[1])
    monkeypatch.setattr(live, "_duration", lambda p: 3600.0)
    if os.name != "nt":
        monkeypatch.setattr(watch, "STABLE_S_NOLOCK", watch.STABLE_S)
    svc = live.LiveService()
    path = rec / "2026-11-03 21-00-00.mp4"
    f = open(path, "ab")  # OBS is recording
    try:
        f.write(b"\0" * (watch.MIN_BYTES + 1))
        f.flush()
        now = time.time() + 1
        assert svc.tick(now) == []
        assert svc.tick(now + 30) == [] if os.name == "nt" else True
    finally:
        f.close()  # OBS stopped
    assert svc.tick(now + 31) == [] or os.name != "nt"
    started = svc.tick(now + 60) or svc.tick(now + 120)
    assert started == [path] and len(submitted) == 1
    a, k = submitted[0]
    assert a[0] == str(path) and k["extra"]["auto_watch"] == str(path) and k["extra"]["easy"] is True
    assert k["extra"]["rec_start"] > 0 and a[3].startswith("Stream ")
    assert svc.tick(now + 500) == []  # never twice, also after a restart:
    assert live.LiveService().tick(now + 900) == [] and len(submitted) == 1
    # SharkyClips stopped while it imported: the next start imports it again (same project id)
    assert live.LiveService().resume() == [path] and len(submitted) == 2
    watch.mark(path, status="imported", project_id="p")
    assert live.LiveService().resume() == []
    # too short recordings are skipped with a reason
    monkeypatch.setattr(live, "_duration", lambda p: 30.0)
    short = rec / "short.mp4"
    _write(short, watch.MIN_BYTES + 1)
    os.utime(short, (now + 1000, now + 1000))
    svc.tick(now + 1000)
    assert svc.tick(now + 1100) == []
    assert watch.load_state()["files"][str(short)]["reason"] == "too_short"
