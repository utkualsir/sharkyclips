"""Kick VOD / clip import: link shapes, the public-endpoint fallback, chat replay (no network)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sharkyclips import config, chat, ingest, kick
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import project_for_id

VOD = "01a1c1f6-5dd8-7684-ba8e-ea1737b63d0a"
CLIP = "clip_01M6PNKW26FJF62TKZ6SA51BC5"
START = datetime(2026, 11, 9, 20, 18, 31, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_leftover_projects():
    """Other test files expect an empty shared workspace (test_web.test_projects_empty)."""
    import shutil

    yield
    for pid in ['kick-chat-test', 'kick-game-test']:
        shutil.rmtree(project_for_id(pid).dir, ignore_errors=True)
    for p in config.workspace_dir().glob("*"):
        if p.is_dir() and (p / "source.mp4").is_file() and p.name.startswith(("ranked-grind", "kick", "demo", "ace")):
            shutil.rmtree(p, ignore_errors=True)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class _Resp:
    def __init__(self, status: int, data):
        self.status_code, self._data = status, data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeKick:
    """Answers like kick.com / web.kick.com for one channel ("demo"), one VOD and one clip."""

    def __init__(self, subscriber_only: bool = False):
        self.calls: list[tuple[str, str, dict]] = []
        self.subscriber_only = subscriber_only
        # chat: one message every 2 s for the first 60 s of the VOD (+ a duplicate + an event)
        self.chat = [{"id": f"m{i}", "type": "message", "content": f"hi {i} [emote:37226:KEKW]",
                      "created_at": _iso(START + timedelta(seconds=2 * i)), "sender": {"slug": f"u{i % 3}"}}
                     for i in range(30)]
        self.chat.append({"id": "sub", "type": "celebration", "content": "x", "created_at": _iso(START),
                          "sender": {"slug": "x"}})

    def request(self, method, url, timeout=None, params=None, json=None):
        self.calls.append((method, url, params or {}))
        if url.endswith("/api/v2/channels/demo"):
            return _Resp(200, {"id": 77, "slug": "demo", "chatroom": {"id": 5077}, "user": {"username": "Demo"}})
        if url.endswith(f"/api/v1/stream/{VOD}/playback"):
            if self.subscriber_only:
                return _Resp(200, {"video_session": {"creator_id": "77"}, "playback_url": {"vod": ""}})
            return _Resp(200, {"video_session": {"creator_id": "77"},
                               "playback_url": {"vod": "https://cdn.example/vod.m3u8"}})
        if url.endswith("/api/v1/channels/77/videos"):
            return _Resp(200, {"data": [{"id": VOD, "title": "Ranked grind", "duration": 3600,
                                         "start_time": _iso(START), "is_live": False,
                                         "channel": {"id": 77, "slug": "demo", "username": "Demo"},
                                         "category": {"name": "Valorant"}}]})
        if url.endswith(f"/api/v2/clips/{CLIP}"):
            return _Resp(200, {"clip": {"id": CLIP, "title": "ace", "duration": 20,
                                        "video_url": "https://clips.example/c.m3u8",
                                        "started_at": _iso(START + timedelta(seconds=10)),
                                        "created_at": "2026-11-10T01:00:00Z",
                                        "channel": {"slug": "demo", "username": "Demo"},
                                        "category": {"name": "Valorant"}}})
        if url.endswith("/api/v2/channels/77/messages"):  # 1.2.57: channel id, not chatroom
            at = datetime.fromisoformat(params["start_time"].replace("Z", "+00:00"))
            win = [m for m in self.chat
                   if at <= datetime.fromisoformat(m["created_at"].replace("Z", "+00:00")) < at + timedelta(seconds=5)]
            return _Resp(200, {"data": {"messages": win + win[:1], "cursor": "1"}})  # + a repeat
        return _Resp(404, {})


@pytest.fixture
def fake(monkeypatch):
    f = FakeKick()
    monkeypatch.setattr(kick, "_http", lambda: f)
    return f


def test_link_shapes():
    assert kick.parse(f"https://kick.com/demo/videos/{VOD}") == kick.Link("vod", VOD, "demo")
    assert kick.parse(f"https://kick.com/video/{VOD.upper()}") == kick.Link("vod", VOD, None)
    assert kick.parse(f"https://kick.com/demo/clips/{CLIP}") == kick.Link("clip", CLIP, "demo")
    assert kick.parse(f"https://www.kick.com/demo?clip={CLIP}") == kick.Link("clip", CLIP, "demo")
    assert kick.parse("https://kick.com/Demo") == kick.Link("channel", "demo")
    assert kick.parse("https://kick.com/demo/videos") == kick.Link("channel", "demo")
    assert kick.parse("https://kick.com/categories/valorant") is None
    assert kick.parse("https://www.youtube.com/watch?v=abc") is None
    assert kick.is_kick("https://kick.com/x") and not kick.is_kick("https://notkick.com/x")


def test_canonical(fake):
    assert kick.canonical(f"https://kick.com/demo/videos/{VOD}") == f"https://kick.com/demo/videos/{VOD}"
    assert kick.canonical(f"https://kick.com/demo?clip={CLIP}") == f"https://kick.com/demo/clips/{CLIP}"
    assert kick.canonical(f"https://kick.com/video/{VOD}") == f"https://kick.com/demo/videos/{VOD}"
    with pytest.raises(SharkyClipsError, match="channel, not a video"):
        kick.canonical("https://kick.com/demo")
    assert kick.canonical("https://example.com/a.mp4") == "https://example.com/a.mp4"


def test_resolve_vod_and_clip(fake):
    v = kick.resolve(f"https://kick.com/video/{VOD}")
    assert v["extractor_key"] == "KickVOD" and v["title"] == "Ranked grind" and v["duration"] == 3600
    assert v["media_url"] == "https://cdn.example/vod.m3u8" and v["uploader_id"] == "demo"
    assert v["upload_date"] == "20261109" and v["categories"] == ["Valorant"]
    c = kick.resolve(f"https://kick.com/demo/clips/{CLIP}")
    assert c["extractor_key"] == "KickClip" and c["media_url"] == "https://clips.example/c.m3u8"
    assert c["webpage_url"] == f"https://kick.com/demo/clips/{CLIP}"


def test_subscriber_only_vod_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(kick, "_http", lambda: FakeKick(subscriber_only=True))
    with pytest.raises(SharkyClipsError, match="subscribers only"):
        kick.resolve(f"https://kick.com/demo/videos/{VOD}")


def test_chat_replay_windows(fake):
    chat_id, t0, length = kick.chat_plan(f"https://kick.com/demo/videos/{VOD}", 0)
    assert (chat_id, t0, length) == (77, START, 3600)  # the channel id (1.2.57)
    rows = kick.chat_segment(chat_id, t0, 0, 60)
    assert [r[0] for r in rows] == [2.0 * i for i in range(30)]  # in order, no repeats, no events
    assert rows[1] == (2.0, "hi 1 KEKW", "u1")  # emote codes become the emote's name
    assert len([c for c in fake.calls if c[1].endswith("/messages")]) == 12  # one call per 5 s
    # a clip's chat starts at the clip's own start (second 0 = 10 s into the stream)
    cid, ct0, clen = kick.chat_plan(f"https://kick.com/demo/clips/{CLIP}", 0)
    assert ct0 == START + timedelta(seconds=10) and clen == 20
    assert kick.chat_segment(cid, ct0, 0, clen)[0] == (0.0, "hi 5 KEKW", "u2")


def test_ensure_chat_uses_kick(fake, tmp_path):
    p = project_for_id("kick-chat-test")
    p.dir.mkdir(parents=True, exist_ok=True)
    p.save_meta({"id": p.id, "title": "x", "duration": 60,
                 "source": {"type": "url", "extractor": "KickVOD", "webpage_url": f"https://kick.com/demo/videos/{VOD}"}})
    data = chat.ensure_chat(p, force=True)
    assert data["status"] == "ok" and data["source"] == "kick" and data["count"] == 30 and data["authors"] == 3


class _FakeYDL:
    """yt-dlp whose Kick extractor is broken: lookups fail, plain HLS downloads work."""

    downloaded: list[str] = []

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        raise RuntimeError("ERROR: [kick:vod] Unable to extract playback")

    def download(self, urls):
        _FakeYDL.downloaded += urls
        out = Path(self.opts["outtmpl"].replace("%(ext)s", "mp4"))
        out.write_bytes(b"\0" * 10)


def test_ingest_falls_back_to_kick_endpoints(fake, monkeypatch):
    import types

    monkeypatch.setattr(ingest, "require_module", lambda *a: types.SimpleNamespace(YoutubeDL=_FakeYDL))
    monkeypatch.setattr(ingest, "require_tool", lambda name: "/usr/bin/ffmpeg")
    project, info = ingest._ingest_url(f"https://kick.com/video/{VOD}")
    assert _FakeYDL.downloaded[-1] == "https://cdn.example/vod.m3u8"
    assert info["extractor"] == "KickVOD" and info["category"] == "Valorant" and info["uploader"] == "Demo"
    assert info["webpage_url"] == f"https://kick.com/demo/videos/{VOD}"
    assert project.source_path is not None and project.source_path.name == "source.mp4"


def test_download_leftovers_are_never_the_source(tmp_path):
    """Issue #16: `source.mp4.part-Frag100` (one 10 s HLS fragment) became the whole project."""
    from sharkyclips.project import Project, is_partial_download

    for name in ("source.mp4.part", "source.mp4.part-Frag100", "source.mp4.part-Frag7.part", "source.mp4.ytdl",
                 "source.f137.mp4", "source.f140.m4a", "source.f299-1.mp4", "source.temp.mp4"):
        assert is_partial_download(Path(name)), name
    for name in ("source.mp4", "source.webm", "source.mkv", "source.MP4"):
        assert not is_partial_download(Path(name)), name
    p = Project("leftovers", tmp_path)
    for name in ("source.mp4.part", "source.mp4.part-Frag100", "source.mp4.ytdl", "source.f137.mp4"):
        (tmp_path / name).write_bytes(b"\0" * 10)
    assert p.source_path is None  # -> the import downloads again (and yt-dlp resumes the .part)
    (tmp_path / "source.mp4").write_bytes(b"\0" * 10)
    assert p.source_path is not None and p.source_path.name == "source.mp4"


def test_short_download_check():
    assert ingest.short_download(10.0, 3600) and ingest.short_download(959, 3600)
    assert not ingest.short_download(3590, 3600) and not ingest.short_download(3600, 3600)
    assert not ingest.short_download(20, 30)  # short clips: a few seconds off is normal
    assert not ingest.short_download(10, None) and not ingest.short_download(10, "x")


def _av(path: Path, seconds: float) -> Path:
    import shutil
    import subprocess

    subprocess.run([shutil.which("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", f"testsrc2=size=160x90:rate=15:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=16000:duration={seconds}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    "-f", "mp4", str(path)], check=True, capture_output=True)
    return path


def test_project_stuck_on_a_fragment_recovers(fake, monkeypatch, tmp_path):
    """Issue #16 end to end: a project made from a fragment gets the full video on the next
    import (the download runs again instead of "Already downloaded"), new audio, and a note
    when the file is still much shorter than the VOD."""
    import shutil
    import types

    from sharkyclips import audio
    from sharkyclips.project import make_project_id, read_json

    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    full = _av(tmp_path / "full.mp4", 6)
    p = project_for_id(make_project_id("Ranked grind", f"url:KickVOD:{VOD}"))
    p.dir.mkdir(parents=True, exist_ok=True)
    _av(p.dir / "source.mp4.part-Frag100", 2)  # what 1.2.65 left behind
    audio.extract_audio(p.dir / "source.mp4.part-Frag100", p.audio_path)
    p.save_meta({"id": p.id, "title": "Ranked grind", "duration": 2.0,
                 "files": {"source": "source.mp4.part-Frag100", "audio": "audio.wav"}})

    class _YDL(_FakeYDL):
        def download(self, urls):
            _FakeYDL.downloaded += urls
            shutil.copyfile(full, self.opts["outtmpl"].replace("%(ext)s", "mp4"))

    _FakeYDL.downloaded = []
    monkeypatch.setattr(ingest, "require_module", lambda *a: types.SimpleNamespace(YoutubeDL=_YDL))
    got = ingest.ingest(f"https://kick.com/video/{VOD}")
    assert got.id == p.id and _FakeYDL.downloaded == ["https://cdn.example/vod.m3u8"]
    meta = read_json(p.meta_path)
    assert meta["files"]["source"] == "source.mp4" and meta["duration"] > 5
    assert audio.wav_duration(p.audio_path) > 5  # taken again from the real video
    assert meta["download_incomplete"]["expected"] == 3600  # the fake VOD says 1 h: told, not hidden
    assert "expected_duration" not in meta["source"]


def test_transcript_of_other_audio_is_not_reused(monkeypatch, tmp_path):
    """Issue #16: the 10 s fragment's transcript must not stand in for the full video's."""
    import wave

    from sharkyclips import hardware, transcribe
    from sharkyclips.project import Project, write_json_atomic

    p = Project("stale-transcript", tmp_path)
    with wave.open(str(p.audio_path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\0\0" * 16000 * 30)  # 30 s
    old = {"request": {"language": "en", "model": "small"}, "language": "en", "segments": [], "duration": 30.0}
    write_json_atomic(p.transcript_path, old)

    class Reached(Exception):
        pass

    def stop(*a, **k):
        raise Reached

    monkeypatch.setattr(hardware, "detect_hardware", stop)
    assert transcribe.transcribe_project(p, "en", "small")["duration"] == 30.0  # same audio: reused
    write_json_atomic(p.transcript_path, old | {"duration": 10.0})  # made from the fragment
    with pytest.raises(Reached):  # -> transcribes again
        transcribe.transcribe_project(p, "en", "small")


def test_channel_link_is_refused_before_any_download(fake, monkeypatch):
    monkeypatch.setattr(ingest, "require_module", lambda *a: pytest.fail("yt-dlp must not run"))
    with pytest.raises(SharkyClipsError, match="channel, not a video"):
        ingest._ingest_url("https://kick.com/demo")


def test_category_helps_game_detection():
    from sharkyclips import game

    p = project_for_id("kick-game-test")
    p.dir.mkdir(parents=True, exist_ok=True)
    p.save_meta({"id": p.id, "title": "late night ranked", "source": {"category": "League of Legends"}})
    r = game.resolve(p)
    assert r["detected"] == "lol", r
    json.dumps(r)
