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
        if url.endswith("/api/v2/channels/5077/messages"):
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
    assert (chat_id, t0, length) == (5077, START, 3600)
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
