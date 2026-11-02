"""1.2.16 Easy mode: smart defaults, auto-rendered best clips, one-click download (MP4 + .txt +
cover PNG) and one-click upload against the fake YouTube server (now / automatic plan)."""

from __future__ import annotations

import json
import zipfile

import pytest

from sharkyclips import config, easy as E, youtube
from sharkyclips.web import state
from test_publishing import _client, _drive, _idle, _project, _wait, cfg, yt  # noqa: F401, F811 - fixtures


@pytest.fixture
def downloads(tmp_path, monkeypatch):
    d = tmp_path / "Downloads" / "SharkyClips"
    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(d))
    return d


@pytest.fixture
def ui_cfg():
    keys = ("ui_mode", "easy_upload_when", "easy_tour_done", "easy_open_folder")
    old = {k: config.load().get(k) for k in keys}
    yield
    c = config.load()
    for k, v in old.items():
        if v is None:
            c.pop(k, None)
        else:
            c[k] = v
    config.save(c)


def test_easy_is_the_default_and_settings_are_remembered(ui_cfg):
    for k in ("ui_mode", "easy_upload_when"):
        c = config.load()
        c.pop(k, None)
        config.save(c)
    s = E.settings()
    assert s["mode"] == "easy" and s["upload_when"] == "now" and s["open_folder"] is True
    with _client() as c:
        r = c.put("/api/easy/settings", json={"mode": "pro", "upload_when": "auto", "tour_done": True}).json()
        assert r["mode"] == "pro" and r["upload_when"] == "auto" and r["tour_done"] is True
        assert c.put("/api/easy/settings", json={"mode": "nonsense"}).json()["mode"] == "pro"
        assert c.get("/api/easy/settings").json()["upload_when"] == "auto"


def test_content_type_detection():
    assert E.detect_mode("Delta Force ranked 25 kill", None) == "gaming"
    assert E.detect_mode("VALORANT clutch moments", "x") == "gaming"
    assert E.detect_mode("KPSS matematik ders çalış 4 saat", None) == "study"
    assert E.detect_mode("Study with me - pomodoro 50/10", None) == "study"
    assert E.detect_mode("Akustik şarkı coverları canlı", None) == "music"
    assert E.detect_mode("Live piano session", "my channel") == "music"
    assert E.detect_mode("", None) == (config.get("default_mode") or "gaming")


def test_post_text_and_safe_names():
    t = E.post_text("Huge play", "What a moment.", ["deltaforce", "#gaming"])
    assert t == "Huge play\n\nWhat a moment.\n\n#deltaforce #gaming\n"
    assert E.safe_name('a/b:c*?"<>| #x  y. ') == "abc x y"
    assert E.safe_name("...") == "clip"


def test_defaults_and_hook_style():
    opts, hook = E.render_options({"subtitles": True, "music": True}, "statement", music_ok=False)
    assert opts["profanity"] == "bleep" and opts["loop"] is False and opts["layout"] == "auto"
    assert opts["music"] is False and hook is None  # no songs in the library: no music
    opts, hook = E.render_options({"subtitles": False, "music": True}, "flash", music_ok=True)
    assert opts["subtitles"] == "none" and opts["music"] is True and opts["hook_flash"] is True
    assert E.render_options({}, "question", True)[1] == "question"
    assert E.hook_style() in ("statement", "question", "flash", "cold_open")


def test_notices_for_the_tray():
    before = E.notices()["last"]
    n = E.ready_notice("My stream", 4, "/#/p/x")
    got = E.notices(before)
    assert got["items"][-1]["id"] == n["id"] and "4" in n["body"] and got["boot"]
    with _client() as c:
        assert c.get(f"/api/notices?after={n['id']}").json()["items"] == []


def test_upload_needs_youtube_with_a_code(cfg):  # noqa: F811
    youtube._forget_token()
    project = _project("pub-easy-noyt", 1)
    with _client() as c:
        r = c.post(f"/api/easy/clips/{project.id}/c01/upload", json={"when": "now"})
        assert r.status_code == 400 and r.json()["code"] == "not_connected"


@pytest.mark.requires_ffmpeg
def test_full_easy_flow_render_download_edit_upload(yt, downloads, ui_cfg):  # noqa: F811
    config.update(publish_daily_limit=2, publish_times=["12:00", "18:00"], easy_open_folder=True)
    project = _project("pub-easy-flow", 3)
    with _client() as c:
        v = c.post(f"/api/easy/projects/{project.id}/prepare").json()
        assert len(v["queued"]) == 3 and v["easy"] is True
        assert [x["id"] for x in v["clips"]] == ["c01", "c02", "c03"]  # best viral score first
        _wait(_idle, 300)
        v = c.get(f"/api/easy/projects/{project.id}").json()
        assert v["state"] == "ready" and all(x["render"]["status"] == "ready" for x in v["clips"])
        assert v["clips"][0]["title"] == "Huge play 1" and v["clips"][0]["viral_label"] == "high"
        assert [s["status"] for s in v["steps"]] == ["done"] * 5
        clip = state.load_clips(project)["c01"]
        assert clip["options"]["profanity"] == "bleep" and clip["options"]["subtitles"] == "bold"

        # one-click download: MP4 + .txt ready to paste + cover PNG (no Explorer window in tests)
        d = c.post(f"/api/easy/clips/{project.id}/c01/download").json()
        folder = downloads / "Stream pub-easy-flow"
        assert d["folder"] == str(folder) and not d.get("opened")
        names = sorted(p.name for p in folder.iterdir())
        assert names == ["01 Huge play 1 - cover.png", "01 Huge play 1.mp4", "01 Huge play 1.txt"]
        assert (folder / "01 Huge play 1.png" if False else folder / "01 Huge play 1 - cover.png").read_bytes()[:4] == b"\x89PNG"
        txt = (folder / "01 Huge play 1.txt").read_text(encoding="utf-8")
        assert txt.startswith("Huge play 1\n\nWhat a moment 1.") and "#deltaforce #gaming #clutch" in txt
        assert (folder / "01 Huge play 1.mp4").stat().st_size > 1000
        allr = c.post(f"/api/easy/projects/{project.id}/download", json={"zip": True}).json()
        assert allr["count"] == 3 and allr["zip"]
        with zipfile.ZipFile(folder / allr["zip"]) as z:
            assert len(z.namelist()) == 9

        # the edit sheet: an AI title, captions off, a shorter cut -> rendered again
        v = c.post(f"/api/easy/clips/{project.id}/c02/edit",
                   json={"title": "Alt title 2", "subtitles": False, "start": 8.5, "end": 12.0}).json()
        card = next(x for x in v["clips"] if x["id"] == "c02")
        assert card["title"] == "Alt title 2" and card["prefs"]["subtitles"] is False
        assert card["render"]["status"] in ("queued", "rendering") and abs(card["duration"] - 3.5) < 0.01
        assert c.post(f"/api/easy/clips/{project.id}/c02/edit", json={"start": 8.0, "end": 9.0}).status_code == 400
        _wait(_idle, 300)
        clip2 = state.load_clips(project)["c02"]
        assert clip2["options"]["subtitles"] == "none" and abs(clip2["end"] - clip2["start"] - 3.5) < 0.05

        # one-click upload now: prefilled title, description with hashtags, tags, cover
        r = c.post(f"/api/easy/clips/{project.id}/c02/upload", json={"when": "now"}).json()
        assert r["status"] == "uploading"
        assert config.get("easy_upload_when") == "now"
        _wait(_idle, 120)
        assert len(yt.videos) == 1
        vid, video = next(iter(yt.videos.items()))
        assert video["snippet"]["title"] == "Alt title 2"
        assert "#deltaforce" in video["snippet"]["description"] and "deltaforce" in video["snippet"]["tags"]
        assert video["status"]["privacyStatus"] == "public" and yt.thumbnails.get(vid)
        up = state.live_upload(project, "c02")
        assert up and up["file"].endswith(".mp4") and up.get("thumbnail_error") is None
        v = c.get(f"/api/easy/projects/{project.id}").json()
        assert next(x for x in v["clips"] if x["id"] == "c02")["upload"]["status"] == "published"
        again = c.post(f"/api/easy/clips/{project.id}/c02/upload", json={"when": "now"}).json()
        assert again["status"] == "published" and len(yt.videos) == 1  # never twice

        # automatic plan: a private upload with publishAt, done by the publish loop
        r = c.post("/api/easy/upload", json={"when": "auto", "clips": [
            {"project_id": project.id, "clip_id": "c01"}, {"project_id": project.id, "clip_id": "c03"}]}).json()
        assert [x["status"] for x in r["results"]] == ["scheduled", "scheduled"]
        acts = _drive(10)
        assert sum(a.startswith("upload:") for a in acts) == 2 and not any(a.startswith("export:") for a in acts)
        assert len(yt.videos) == 3
        planned = [v for v in yt.videos.values() if v["status"].get("publishAt")]
        assert len(planned) == 2 and all(v["status"]["privacyStatus"] == "private" for v in planned)
        lib = c.get("/api/easy/library").json()["tabs"]
        mine = lambda rows: sorted(r["clip_id"] for r in rows if r["project_id"] == project.id)  # noqa: E731
        assert mine(lib["planned"]) == ["c01", "c03"] and mine(lib["live"]) == ["c02"] and mine(lib["ready"]) == []

        # discard: the clip leaves the grid
        v = c.post(f"/api/easy/clips/{project.id}/c03/discard").json()
        assert [x["id"] for x in v["clips"]] == ["c01", "c02"]


@pytest.mark.requires_ffmpeg
def test_ready_notice_after_the_last_render(yt, downloads):  # noqa: F811
    from sharkyclips.web import app as A
    from sharkyclips.web import easy as WE

    WE.install(A.jobs)  # the server does this at startup (tests skip the startup)
    project = _project("pub-easy-note", 2)
    E.save(project, easy=True)
    with _client() as c:
        before = E.notices()["last"]
        c.post(f"/api/easy/projects/{project.id}/more")  # queues the renders (pipeline idle)
        _wait(_idle, 300)
    # the job counts as done a moment before its listeners have run
    _wait(lambda: any(n["kind"] == "clips_ready" for n in E.notices(before)["items"]), 30)
    items = [n for n in E.notices(before)["items"] if n["kind"] == "clips_ready"]
    assert len(items) == 1 and "Stream pub-easy-note" in items[0]["body"] and items[0]["url"] == f"/#/p/{project.id}"
    assert E.load(project)["notified_for"] == "2026-10-01T00:00:00+00:00"

    class J:  # another job ending later must not repeat it
        project_id, kind, status, params = project.id, "render", "done", {}

    WE.on_job_finished(J())
    assert not [n for n in E.notices(before)["items"] if n["id"] > items[0]["id"]]


def test_import_marks_easy_and_detects_the_mode(cfg, monkeypatch):  # noqa: F811
    from sharkyclips.web import easy as WE

    monkeypatch.setattr(WE, "ensure_renders", lambda *a, **k: [])

    project = _project("pub-easy-import", 1)
    meta = project.load_meta()
    meta.update(title="KPSS matematik ders çalış", mode="gaming")
    project.save_meta(meta)

    class J:
        project_id, kind, status, params = project.id, "import", "done", {"easy": True, "mode_auto": True}

    WE.on_job_finished(J())
    assert project.load_meta()["mode"] == "study"
    data = E.load(project)
    assert data["easy"] and data["mode_auto"]
    json.dumps(data)


def test_tray_shows_new_notices_once():
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from sharkyclips import tray

    replies = [{"boot": "a", "items": [{"id": 1, "title": "old", "body": "old"}], "last": 1},
               {"boot": "a", "items": [{"id": 2, "title": "Ready", "body": "2 clips"}], "last": 2},
               {"boot": "a", "items": [], "last": 2}]
    asked = []

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            asked.append(self.path)
            body = _json.dumps(replies[min(len(asked) - 1, 2)]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    shown = []

    class Icon:
        def notify(self, body, title):
            shown.append((title, body))

    stop = threading.Event()
    t = threading.Thread(target=tray.notify_loop, args=(f"http://127.0.0.1:{srv.server_port}", Icon(), stop, 0.05))
    t.start()
    _wait(lambda: len(asked) >= 3, 10)
    stop.set()
    t.join(5)
    srv.shutdown()
    assert shown == [("Ready", "2 clips")]  # the notice from before the tray started isn't repeated
    assert asked[1].endswith("after=1") and asked[2].endswith("after=2")
