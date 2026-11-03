"""Phone approval (1.2.17): the Telegram bot (fake Bot API) and the approval page's API."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from sharkyclips import config, phone
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic


@pytest.fixture(autouse=True)
def _clean():
    before = set(config.workspace_dir().iterdir())
    yield
    config.update(phone_send=None, phone_lan=None)
    for p in (phone.secret_path(), phone.cards_path()):
        p.unlink(missing_ok=True)
    for d in set(config.workspace_dir().iterdir()) - before:
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


class FakeTelegram:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.updates: list[dict] = []
        self.next_update = 1
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                token, method = self.path.split("/")[1][3:], self.path.split("/")[2]
                ctype = self.headers.get("Content-Type") or ""
                params = json.loads(raw or b"{}") if "json" in ctype else {"_multipart": len(raw)}
                outer.calls.append((method, params))
                if token != "123456:" + "A" * 35:
                    body = {"ok": False, "error_code": 401, "description": "Unauthorized"}
                    self.send_response(401)
                else:
                    self.send_response(200)
                    result: object = True
                    if method == "getMe":
                        result = {"id": 1, "username": "my_clips_bot"}
                    elif method == "getUpdates":
                        off = int(params.get("offset") or 0)
                        result = [u for u in outer.updates if u["update_id"] >= off]
                    elif method in ("sendPhoto", "sendMessage", "sendVideo"):
                        result = {"message_id": 77}
                    body = {"ok": True, "result": result}
                data = json.dumps(body).encode()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def push(self, **upd):
        self.updates.append({"update_id": self.next_update, **upd})
        self.next_update += 1

    def methods(self):
        return [m for m, _ in self.calls]


TOKEN = "123456:" + "A" * 35


@pytest.fixture
def tg(monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setenv("SHARKYCLIPS_TG_ENDPOINT", fake.url)
    yield fake
    fake.srv.shutdown()


def test_telegram_setup_and_pairing(tg):
    with pytest.raises(SharkyClipsError):
        phone.set_token("not a token")
    with pytest.raises(SharkyClipsError, match="doesn't know"):
        phone.set_token("999999:" + "B" * 35)
    st = phone.set_token(TOKEN)
    assert st["configured"] and not st["paired"] and st["bot"] == "my_clips_bot"
    code = st["link"].rsplit("=", 1)[1]
    assert st["link"] == f"https://t.me/my_clips_bot?start={code}"
    tg.push(message={"text": "/start wrongcode", "chat": {"id": 5}})
    assert phone.pair_check()["paired"] is False  # someone else / a wrong code: ignored
    tg.push(message={"text": f"/start {code}", "chat": {"id": 42, "first_name": "Utku"}})
    st = phone.pair_check()
    assert st["paired"] and st["chat"] == "Utku" and st["link"] is None
    assert tg.calls[-1][0] == "sendMessage" and tg.calls[-1][1]["chat_id"] == 42
    assert TOKEN not in phone.secret_path().read_text(encoding="utf-8", errors="replace")  # stored encrypted
    phone.send_test()
    phone.disconnect()
    assert phone.status()["configured"] is False


@pytest.mark.requires_ffmpeg
def test_telegram_clip_card_and_buttons(tg, tmp_path):
    phone.set_token(TOKEN)
    code = phone.status()["link"].rsplit("=", 1)[1]
    tg.push(message={"text": f"/start {code}", "chat": {"id": 42}})
    phone.pair_check()
    video = tmp_path / "c.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=30:duration=2",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    config.update(ui_language="tr")
    tok = phone.send_clip("p1", "c01", video, "Penta <3", "very_high", 91, "Stream", 1.0)
    config.update(ui_language=None)
    assert tok and tg.methods()[-1] == "sendPhoto" and tg.calls[-1][1]["_multipart"] > 1000
    assert phone.label("very_high") in ("very high", "çok yüksek")
    assert phone.send_clip("p1", "c01", video, "again", None, None, "Stream") is None  # never twice
    acts: list = []
    poller = phone.Poller(lambda a, p, c: (acts.append((a, p, c)), "Planned")[1], lambda p, c: video)
    d = phone._load()
    stranger = {"id": "q0", "data": f"u|{tok}", "from": {"id": 9}, "message": {"chat": {"id": 9}}}
    poller.handle({"callback_query": stranger}, d)
    assert acts == []  # only the paired chat may press
    poller.handle({"callback_query": {"id": "q1", "data": f"p|{tok}", "from": {"id": 42},
                                      "message": {"chat": {"id": 42}}}}, d)
    assert acts == [("plan", "p1", "c01")]
    assert "editMessageCaption" in tg.methods() and tg.methods()[-1] == "answerCallbackQuery"
    poller.handle({"callback_query": {"id": "q2", "data": f"u|{tok}", "from": {"id": 42},
                                      "message": {"chat": {"id": 42}}}}, d)
    assert len(acts) == 1  # a card is decided once
    poller.handle({"callback_query": {"id": "q3", "data": f"w|{tok}", "from": {"id": 42},
                                      "message": {"chat": {"id": 42}}}}, d)
    assert "sendVideo" in tg.methods()


# ===================================================================== approve page


def _easy_project(pid: str) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    (d / "clips").mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "My stream", "duration": 100.0, "mode": "gaming"})
    write_json_atomic(d / "highlights.json", {"mode": "gaming", "created_at": "x", "candidates": [
        {"rank": i, "id": f"c0{i}", "start": 10.0 * i, "end": 10.0 * i + 8, "duration": 8.0, "peak": 10.0 * i + 4,
         "hype_score": 90 - i, "reasons": [], "signal_scores": {}, "text": f"clip {i}",
         **({"marked": {"source": "hotkey", "t": 34.0}} if i == 3 else {})} for i in (1, 2, 3)]})
    write_json_atomic(d / "easy.json", {"easy": True, "fx": True})
    proj = Project(pid, d)
    from sharkyclips.web import state

    for i in (1, 2, 3):
        (d / "clips" / f"0{i}_c0{i}.mp4").write_bytes(b"\0" * 100)
        state.save_clip(proj, f"c0{i}", {"file": f"0{i}_c0{i}.mp4", "id": f"c0{i}", "rank": i, "start": 10.0 * i,
                                         "end": 10.0 * i + 8, "duration": 8.0, "options": {}, "rendered_at": f"t{i}"})
    return proj


def test_approve_api():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    _easy_project("approve-proj")
    r = client.get("/api/approve").json()
    mine = [c for c in r["clips"] if c["project_id"] == "approve-proj"]
    assert [c["clip_id"] for c in mine][0] == "c03"  # the clip you marked live comes first
    assert mine[0]["marked"] and mine[0]["video"].endswith("/clips/c03/video")
    r = client.post("/api/approve/approve-proj/c02", json={"action": "skip"})
    assert r.status_code == 200 and r.json()["status"] == "skipped"
    assert "c02" not in [c["clip_id"] for c in r.json()["clips"] if c["project_id"] == "approve-proj"]
    r = client.post("/api/approve/approve-proj/c01", json={"action": "upload"})
    assert r.status_code == 400 and "YouTube" in r.json()["error"]  # not connected: a friendly error
    assert client.post("/api/approve/approve-proj/nope", json={"action": "skip"}).status_code == 400
    r = client.put("/api/phone", json={"lan": True})
    assert r.status_code == 400 and r.json()["code"] == "needs_pin"
