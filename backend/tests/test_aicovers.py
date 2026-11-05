"""1.2.18 cover studio: resumable model downloads, the image runner (fake sd-cli), pause = stop and
redo, four options per size, one-click choose, the cover text on top, the facecam fallback."""

from __future__ import annotations

import hashlib
import http.server
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from sharkyclips import aicovers, config, cover, downloads, imagegen
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic

FAKE = Path(__file__).parent / "data" / "fake_sdcli.py"


def _project(pid: str) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    ff = shutil.which("ffmpeg")
    if ff:
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=320x180:rate=30:duration=12", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", str(d / "source.mp4")], check=True, capture_output=True)
    write_json_atomic(d / "meta.json", {"title": "Cover test", "duration": 12, "width": 320, "height": 180,
                                        "fps": 30, "mode": "gaming"})
    cands = [{"id": "c01", "rank": 1, "start": 1.0, "end": 8.0, "duration": 7.0, "peak": 4.0, "text": "what a shot",
              "publish": {"available": True, "cover_text": "NO WAY", "language": "en",
                          "cover_prompt": 'A soldier mid-air over a burning truck. vertical 9:16 thumbnail, cinematic '
                                          'and dramatic, high contrast, bold short overlay text "NO WAY", no logos'}}]
    write_json_atomic(d / "highlights.json", {"created_at": "2026-11-01T00:00:00+00:00", "candidates": cands})
    write_json_atomic(d / "review.json", {"highlights_created_at": "2026-11-01T00:00:00+00:00", "accepted": ["c01"]})
    return Project(pid, d)


@pytest.fixture
def fake_sd(monkeypatch, tmp_path):
    files = {}
    for k in ("diffusion", "llm", "vae"):
        files[k] = tmp_path / f"{k}.bin"
        files[k].write_bytes(b"x")
    monkeypatch.setattr(imagegen, "ensure_model", lambda *a, **k: files)
    monkeypatch.setattr(imagegen, "ensure_tool", lambda *a, **k: FAKE)
    monkeypatch.setattr(imagegen, "_command_prefix", lambda exe: [sys.executable, str(exe)])
    monkeypatch.setattr(imagegen, "free_gpu", lambda: None)
    monkeypatch.setenv("SHARKYCLIPS_IMAGEGEN_TIER", "gpu")
    log = tmp_path / "calls.log"
    monkeypatch.setenv("FAKE_SD_LOG", str(log))
    return log


# ------------------------------------------------------------------ downloads


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    data = b""
    fail_after: int | None = None
    calls: list = []

    def do_GET(self):  # noqa: N802
        rng = self.headers.get("Range")
        start = int(rng.split("=")[1].split("-")[0]) if rng else 0
        type(self).calls.append(start)
        body = self.data[start:]
        self.send_response(206 if rng else 200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.fail_after is not None and start == 0:
            self.wfile.write(body[: self.fail_after])  # the connection breaks half way
            self.wfile.flush()
            self.connection.shutdown(2)
            return
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _serve(data: bytes, fail_after: int | None):
    h = type("H", (_RangeHandler,), {"data": data, "fail_after": fail_after, "calls": []})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, h


def test_download_resumes_after_a_broken_connection_and_checks_the_hash(tmp_path, monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_NO_DOWNLOADS", raising=False)
    data = bytes(range(256)) * 4000
    srv, h = _serve(data, fail_after=300_000)
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/m.bin"
        dest = tmp_path / "m.bin"
        seen = []
        out = downloads.fetch(downloads.Remote(url, hashlib.sha256(data).hexdigest(), len(data), "m.bin"), dest,
                              lambda d, t: seen.append(d))
        assert out.read_bytes() == data and not (tmp_path / "m.bin.part").exists()
        assert h.calls[0] == 0 and any(c > 0 for c in h.calls[1:])  # second request continued (Range)
        bad = tmp_path / "bad.bin"
        with pytest.raises(SharkyClipsError, match="damaged"):
            downloads.fetch(downloads.Remote(url, "0" * 64, len(data), "bad.bin"), bad)
        assert not bad.exists() and not (tmp_path / "bad.bin.part").exists()
    finally:
        srv.shutdown()


def test_unzip_refuses_paths_outside_the_folder(tmp_path):
    import zipfile

    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../escape.txt", "x")
    with pytest.raises(SharkyClipsError):
        imagegen._unzip(z, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


# ------------------------------------------------------------------ plan / prompt


def test_prompt_drops_the_overlay_text_and_sets_the_frame():
    p = 'Soldier jumps. vertical 9:16 thumbnail, cinematic, bold short overlay text "NO WAY", no logos'
    tall, wide = imagegen.image_prompt(p, "tall"), imagegen.image_prompt(p, "wide")
    assert "NO WAY" not in tall and "overlay text" not in tall and "no text" in tall
    assert "vertical 9:16" in tall and "wide 16:9" in wide and "9:16 thumbnail" not in wide


@pytest.mark.parametrize("tier,device,use", [("gpu", "auto", "gpu"), ("cpu", "auto", "fallback"),
                                             ("cpu", "cpu", "cpu"), ("none", "cpu", "fallback"),
                                             ("gpu", "cpu", "cpu")])
def test_plan_uses_the_gpu_falls_back_on_weak_pcs_and_lets_pro_force_the_cpu(monkeypatch, tier, device, use):
    monkeypatch.setenv("SHARKYCLIPS_IMAGEGEN_TIER", tier)
    config.update(cover_ai_device=device)
    try:
        assert imagegen.plan()["use"] == use
    finally:
        config.update(cover_ai_device="auto")


def test_gpu_lost_counts_as_no_gpu(monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_IMAGEGEN_TIER", raising=False)
    from sharkyclips import hardware

    monkeypatch.setattr(hardware, "detect_nvidia_gpus", lambda: [])
    monkeypatch.setattr(imagegen, "_gpu_lost", lambda: True)
    cap = imagegen._detect()
    assert cap.reason == "gpu_lost" and cap.tier in ("cpu", "none")


# ------------------------------------------------------------------ making and choosing


@pytest.mark.requires_ffmpeg
def test_four_options_per_size_choose_and_text_on_top(fake_sd):
    project = _project("aic-make")
    cand = __import__("json").loads((project.dir / "highlights.json").read_text())["candidates"][0]
    v = aicovers.make(project, cand, ["tall", "wide"])
    assert len(v["options"]["tall"]) == 4 and len(v["options"]["wide"]) == 4
    assert v["chosen"]["tall"] == v["seeds"][0] and v["made_with"] == "gpu"
    calls = fake_sd.read_text().splitlines()
    assert len(calls) == 8 and all("NO WAY" not in c for c in calls)
    assert "-W 576 -H 1024" in calls[0] and "-W 1024 -H 576" in calls[4] and "--offload-to-cpu" in calls[0]
    seed = v["seeds"][2]
    v = aicovers.choose(project, "c01", "tall", seed)
    assert v["chosen"]["tall"] == seed
    with pytest.raises(SharkyClipsError):
        aicovers.choose(project, "c01", "tall", 12345)
    from PIL import Image

    img = cover.make_cover(project, cand, None, "ai", "NO WAY", "tall", "en")
    with Image.open(img) as im:
        assert im.size == (1080, 1920)
    with Image.open(cover.make_cover(project, cand, None, "ai", "NO WAY", "wide", "en")) as im:
        assert im.size == (1280, 720)
    # same picture, other text: no new picture, a new composite
    again = cover.make_cover(project, cand, None, "ai", "SO CLOSE", "tall", "en")
    assert again != img and len(fake_sd.read_text().splitlines()) == 8
    # a second round: new seeds, the older pictures go (the chosen one is replaced by the new first)
    v2 = aicovers.make(project, cand, ["tall"])
    assert set(v2["seeds"]).isdisjoint(v["seeds"]) and len(list(aicovers.folder(project, "c01").glob("*_tall.png"))) == 4


@pytest.mark.requires_ffmpeg
def test_no_ai_picture_falls_back_to_the_facecam_frame(fake_sd):
    from sharkyclips.web import publishing as WP, state

    project = _project("aic-fallback")
    cand = __import__("json").loads((project.dir / "highlights.json").read_text())["candidates"][0]
    review = state.load_review(project)
    assert WP.default_cover_kind(project, "c01", review) == "peak"  # no facecam, no AI picture
    img = WP.make_cover_for(project, cand, review, "ai", "NO WAY", "tall", "en")  # quietly the frame
    assert "_peak_tall_" in img.name
    aicovers.make(project, cand, ["tall"])
    assert WP.default_cover_kind(project, "c01", review) == "ai"
    assert "_ai_tall_" in WP.make_cover_for(project, cand, review, "ai", "NO WAY", "tall", "en").name
    assert "_peak_wide_" in WP.make_cover_for(project, cand, review, "ai", "NO WAY", "wide", "en").name


def test_weak_pc_says_so_instead_of_trying(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_IMAGEGEN_TIER", "none")
    project = _project("aic-weak")
    cand = __import__("json").loads((project.dir / "highlights.json").read_text())["candidates"][0]
    with pytest.raises(SharkyClipsError, match="can't make AI covers"):
        aicovers.make(project, cand, ["tall"])


def test_out_of_memory_gives_a_friendly_fix(fake_sd, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_SD_FAIL", "oom")
    with pytest.raises(SharkyClipsError) as e:
        imagegen.generate("x", "tall", [1], tmp_path / "o", use="gpu", build="win-vulkan")
    assert "ran out of memory" in (e.value.hint or "")


def test_a_governor_pause_stops_the_program_and_redoes_the_picture(fake_sd, monkeypatch, tmp_path):
    """Pause (game starts) -> sd-cli is killed at once (VRAM free) -> after the pause the same
    picture is made again from the start."""
    from sharkyclips import governor

    monkeypatch.setenv("FAKE_SD_SLEEP", "0.25")

    class G:
        def __init__(self):
            self.paused = False
            self._go = threading.Event()
            self._go.set()
            self.light = False
            self.cancel_epoch = 0
            self.decision = type("D", (), {"throttle": 0})()

        def tick(self):
            pass

        def cpu_threads(self):
            return 2

        def notify(self):
            pass

    g = G()
    monkeypatch.setattr(governor, "_gov", g)
    runner = imagegen.Runner()
    killed = []
    orig_stop = runner.stop

    def stop():
        killed.append(runner.proc is not None)
        orig_stop()

    runner.stop = stop

    def pause_then_resume():
        import time

        time.sleep(0.9)
        g.paused = True
        g._go.clear()
        time.sleep(1.0)
        g.paused = False
        g._go.set()

    threading.Thread(target=pause_then_resume, daemon=True).start()
    out = imagegen.generate("x", "tall", [7], tmp_path / "o", use="gpu", build="win-vulkan", runner=runner)
    assert out[0].is_file() and any(killed)
    assert len(fake_sd.read_text().splitlines()) == 2  # started, killed, started again


# ------------------------------------------------------------------ API


@pytest.mark.requires_ffmpeg
def test_api_make_choose_and_preview(fake_sd):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app, jobs

    project = _project("aic-api")
    c = TestClient(app)
    assert c.get("/api/covers/ai").json()["use"] == "gpu"
    r = c.post(f"/api/library/{project.id}/c01/ai-covers", json={"frames": ["tall"]})
    assert r.status_code == 200, r.text
    jid = r.json()["job"]["id"]
    import time

    end = time.time() + 60
    while jobs.get(jid).status in ("queued", "running") and time.time() < end:
        time.sleep(0.1)
    assert jobs.get(jid).status == "done", jobs.get(jid).error
    v = c.get(f"/api/library/{project.id}/c01/ai-covers").json()
    assert len(v["options"]["tall"]) == 4 and v["job"] is None
    seed = v["options"]["tall"][1]
    assert c.post(f"/api/library/{project.id}/c01/ai-covers/choose", json={"frame": "tall", "seed": seed}).json()["chosen"]["tall"] == seed
    img = c.get(f"/api/library/{project.id}/c01/ai-covers/{seed}/tall.jpg?text=NO%20WAY")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    pv = c.get(f"/api/library/{project.id}/c01/cover.jpg?kind=ai&frame=tall&text=NO")
    assert pv.status_code == 200


def test_api_weak_pc_answers_with_the_fallback(monkeypatch):
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    monkeypatch.setenv("SHARKYCLIPS_IMAGEGEN_TIER", "none")
    project = _project("aic-api-weak")
    r = TestClient(app).post(f"/api/library/{project.id}/c01/ai-covers", json={"frames": ["tall"]})
    assert r.status_code == 400 and r.json().get("code") == "fallback"
