"""Phase 9 (1.2.2): export formats, presets, subtitle files, editor timelines, YouTube upload."""

from __future__ import annotations

import json
import shutil
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from sharkyclips import config, editors, export, youtube
from sharkyclips.clips import Geometry, build_ass, ClipOptions
from sharkyclips.errors import SharkyClipsError


# ------------------------------------------------------------------ presets, geometry, estimate


def test_presets_and_length_warnings():
    assert set(export.PRESETS) == {"youtube_shorts", "tiktok", "instagram_reels", "x", "youtube_16x9"}
    assert export.check_length("youtube_shorts", 200)[0]["code"] == "too_long"
    assert export.check_length("youtube_shorts", 60) == []
    assert export.check_length("youtube_16x9", 5000) == []  # no limit
    assert export.check_length(None, 5000) == []


def test_safe_zone_keeps_captions_out():
    for p in export.PRESETS.values():
        spec = export.resolve_spec(export.FORMATS["mp4_h264"], p, 60, True)
        geo = Geometry.for_spec(spec, "fit")
        top, right, bottom, left = p.safe
        w, h = spec.canvas
        assert geo.cap_y is not None and geo.cap_y + 100 <= h - bottom, p.id
        assert geo.hook_y is not None and geo.hook_y >= top, p.id
        assert geo.margin_r >= right and geo.margin_l >= left
    wide = Geometry.for_spec(export.resolve_spec(export.FORMATS["mp4_h264"], export.PRESETS["youtube_16x9"], 60, True), "fit")
    assert (wide.w, wide.h) == (1920, 1080) and wide.scale < 1


def test_ass_uses_canvas_size():
    words = [{"start": 0.1, "end": 0.5, "word": "hello"}, {"start": 0.5, "end": 0.9, "word": "world"}]
    geo = Geometry(1920, 1080, 960, 900, 70, 0.72, 120, 120)
    ass = build_ass(words, 2.0, ClipOptions(), "fit", "en", "Hook!", geo=geo)
    assert "PlayResX: 1920" in ass and "PlayResY: 1080" in ass
    assert "\\pos(960,900)" in ass


def test_estimates_are_sane():
    h264 = export.estimate_bytes("mp4_h264", None, 20)
    hevc = export.estimate_bytes("mp4_hevc", None, 20)
    assert 0 < hevc < h264
    tiktok = export.estimate_bytes("mp4_h264", "tiktok", 20)
    assert 25e6 < tiktok < 30e6  # 10 Mbit/s for 20 s ~ 25 MB + overshoot + audio
    assert export.estimate_bytes("gif", None, 20, gif_max_mb=5) <= 5 * 1024 * 1024
    assert export.estimate_bytes("mp3", None, 20) == pytest.approx(192_000 / 8 * 20, rel=0.01)


def test_export_request_validation():
    with pytest.raises(SharkyClipsError):
        export.ExportRequest.from_dict({"format": "avi"})
    with pytest.raises(SharkyClipsError):
        export.ExportRequest.from_dict({"format": None})  # nothing to do
    r = export.ExportRequest.from_dict({"format": None, "subtitles": ["srt", "bogus"], "subtitle_lang": "de"})
    assert r.subtitles == ("srt",) and r.subtitle_lang == "de"
    assert export.ExportRequest.from_dict({"format": "gif", "gif_max_mb": 9999}).gif_max_mb == 100


# ------------------------------------------------------------------ subtitles


def test_srt_and_vtt():
    words = [{"start": 0.0, "end": 0.4, "word": "Merhaba"}, {"start": 0.4, "end": 0.9, "word": "dünya."},
             {"start": 2.0, "end": 2.5, "word": "Nasılsın?"}]
    cues = export.subtitle_cues(words, 3.0, "tr", offset=1.0)
    assert cues[0]["text"] == "Merhaba dünya." and cues[0]["start"] == pytest.approx(1.0)
    srt = export.to_srt(cues)
    assert srt.startswith("1\n00:00:01,000 --> ") and "2\n00:00:03,000" in srt
    vtt = export.to_vtt(cues, "tr")
    assert vtt.startswith("WEBVTT\nLanguage: tr") and "00:00:01.000 --> " in vtt
    zh = export.subtitle_cues([{"start": 0, "end": 1, "word": "你好"}, {"start": 1, "end": 2, "word": "世界"}], 2, "zh")
    assert zh[0]["text"] == "你好世界"


# ------------------------------------------------------------------ editor timelines


class FakeProject:
    id = "p1"

    def __init__(self, tmp: Path, fps: float):
        self.source_path = tmp / "my video.mp4"
        self.source_path.write_bytes(b"x")
        self._meta = {"width": 1920, "height": 1080, "fps": fps, "duration": 600.0, "audio_codec": "aac",
                      "title": "Test & <stream>"}

    def load_meta(self):
        return self._meta


CAND = {"id": "c01", "rank": 1, "start": 120.5, "end": 141.2, "duration": 20.7,
        "reasons": [{"code": "df_kill", "t": 125.0, "strength": 0.4}, {"code": "keyword", "t": 130.0,
                                                                         "value": "kanka", "strength": 0.3},
                    {"code": "laughter", "t": 300.0, "strength": 1}]}
CUES = [{"start": 0.5, "end": 2.0, "text": "Hello there"}, {"start": 2.0, "end": 4.25, "text": "General Kenobi"}]


@pytest.mark.parametrize("fps", [30.0, 60.0, 29.97])
def test_fcpxml_valid_and_frame_aligned(tmp_path, fps):
    proj = FakeProject(tmp_path, fps)
    text = editors.fcpxml(proj, CAND, CUES, "en")
    assert editors.validate(text, "fcpxml") == []
    root = editors.ET.fromstring(text.split("\n", 2)[2])
    clk = editors.Clock(fps)
    for e in root.iter():
        for attr in ("offset", "start", "duration"):
            v = e.get(attr)
            if v and v != "0s" and e.tag != "caption" or (v and attr != "start" and e.tag == "caption"):
                from fractions import Fraction

                frames = Fraction(v[:-1]) * clk.num / clk.den
                assert frames.denominator == 1, (e.tag, attr, v)
    assert [m.get("value") for m in root.iter("marker")] == ["Kill", "Reaction word: kanka"]  # 300 s is outside
    assert len(list(root.iter("caption"))) == 2
    assert "my%20video.mp4" in root.find(".//media-rep").get("src")


def test_premiere_xml_valid(tmp_path):
    proj = FakeProject(tmp_path, 29.97)
    text = editors.premiere_xml(proj, CAND, CUES, "en")
    assert editors.validate(text, "premiere") == []
    root = editors.ET.fromstring(text.split("\n", 2)[2])
    ci = root.find(".//clipitem")
    assert int(ci.findtext("in")) == round(120.5 * 30000 / 1001)
    assert root.find(".//rate/ntsc").text == "TRUE"
    assert root.findtext(".//pathurl").startswith("file://localhost/")
    assert len(root.findall("./sequence/marker")) == 2


def test_validate_catches_broken_xml():
    assert editors.validate("<fcpxml", "fcpxml")
    assert editors.validate("<fcpxml version='1.9'><x ref='nope'/></fcpxml>", "fcpxml")


# ------------------------------------------------------------------ YouTube


def test_pacific_quota_day():
    # 2026-07-01 06:30 UTC = 2026-06-30 23:30 PDT (UTC-7)
    assert youtube.pacific_now(datetime(2026, 7, 1, 6, 30, tzinfo=timezone.utc)).date().isoformat() == "2026-06-30"
    # 2026-01-15 08:30 UTC = 00:30 PST (UTC-8)
    assert youtube.pacific_now(datetime(2026, 1, 15, 8, 30, tzinfo=timezone.utc)).hour == 0
    reset = youtube.next_reset(datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc))
    assert reset == datetime(2026, 1, 16, 8, 0, tzinfo=timezone.utc)


def test_quota_counting(monkeypatch):
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    assert youtube.quota_view()["uploads_left"] == 6  # 10,000 / 1,600
    youtube.spend(1600 * 5)
    assert youtube.quota_view()["uploads_left"] == 1
    youtube.spend(1600)
    with pytest.raises(SharkyClipsError):
        youtube.check_quota(youtube.COST["upload"])
    (youtube.folder() / "quota.json").unlink()


def test_client_json_rules():
    with pytest.raises(SharkyClipsError):
        youtube.set_client("not json")
    with pytest.raises(SharkyClipsError):
        youtube.set_client({"web": {"client_id": "x.apps.googleusercontent.com", "client_secret": "s"}})
    c = youtube.set_client(json.dumps({"installed": {"client_id": "123.apps.googleusercontent.com",
                                                     "client_secret": "sec", "project_id": "sharky"}}))
    assert c["project_id"] == "sharky" and youtube.status()["client"] and not youtube.status()["connected"]
    url = youtube.auth_url("http://127.0.0.1:8000/")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["redirect_uri"] == ["http://127.0.0.1:8000/"] and q["code_challenge_method"] == ["S256"]
    assert "youtube.upload" in q["scope"][0] and q["access_type"] == ["offline"]
    assert youtube.is_pending(q["state"][0])
    youtube.remove_client()
    assert not youtube.status()["client"]


def test_build_body():
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    b = youtube.build_body("Big <win>", "desc > here", ["#gaming", "gaming", "delta force"], "public", when, False)
    assert b["snippet"]["title"] == "Big ‹win›" and ">" not in b["snippet"]["description"]
    assert b["snippet"]["tags"] == ["gaming", "delta force"]
    assert b["status"]["privacyStatus"] == "private" and b["status"]["publishAt"].endswith("Z")
    with pytest.raises(SharkyClipsError):
        youtube.build_body("t", "", [], "public", "2001-01-01T00:00:00Z", False)
    with pytest.raises(SharkyClipsError):
        youtube.build_body("", "", [], "private", None, False)


class FakeResp:
    def __init__(self, status, data=None, headers=None):
        self.status_code, self._data, self.headers = status, data or {}, headers or {}

    def json(self):
        return self._data


def test_resumable_upload_survives_a_failed_chunk(tmp_path, monkeypatch):
    youtube._write("token.json", {"access_token": "a", "refresh_token": "r", "expires_at": 9e12})
    (youtube.folder() / "quota.json").unlink(missing_ok=True)
    (youtube.folder() / "sessions.json").unlink(missing_ok=True)
    monkeypatch.setattr(youtube, "CHUNK", 256 * 1024)
    monkeypatch.setattr(youtube.time, "sleep", lambda s: None)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"v" * (600 * 1024))
    got = bytearray()
    calls = {"put": 0}

    import requests as real

    def post(url, **kw):
        assert "uploadType" in kw["params"]
        return FakeResp(200, headers={"Location": "https://upload/session1"})

    def put(url, data=None, headers=None, timeout=None):
        calls["put"] += 1
        rng = headers["Content-Range"]
        if rng.startswith("bytes */"):  # status query
            return FakeResp(308, headers={"Range": f"bytes=0-{len(got) - 1}"} if got else {})
        if calls["put"] == 2:  # second chunk: network error once
            raise real.ConnectionError("boom")
        got.extend(data)
        if len(got) >= 600 * 1024:
            return FakeResp(200, {"id": "VID123", "status": {"privacyStatus": "private"}})
        return FakeResp(308, headers={"Range": f"bytes=0-{len(got) - 1}"})

    monkeypatch.setattr(youtube, "_http", lambda: SimpleNamespace(post=post, put=put, get=None,
                                                                  RequestException=real.RequestException))
    progress = []
    res = youtube.upload(video, {"snippet": {}, "status": {}}, "k1", on_progress=progress.append)
    assert res["id"] == "VID123" and bytes(got) == video.read_bytes()
    assert progress[-1] == 1.0
    assert youtube.quota_used() == youtube.COST["upload"]
    assert "k1" not in youtube._sessions()
    (youtube.folder() / "token.json").unlink()


def test_api_endpoints():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    r = client.get("/api/export/options")
    assert r.status_code == 200  # works with or without ffmpeg (formats then show unavailable)
    data = r.json()
    assert {f["id"] for f in data["formats"]} == set(export.FORMATS)
    assert len(data["presets"]) == 5
    yt = client.get("/api/youtube").json()
    assert yt["connected"] is False and yt["quota"]["limit"] == 10000
    assert client.post("/api/youtube/stats").status_code == 400  # not connected
    s = client.put("/api/settings", json={"ui_motion": "reduced"}).json()
    assert s["ui_motion"] == "reduced"
    assert client.put("/api/settings", json={"ui_motion": "wild"}).status_code == 400
    client.put("/api/settings", json={"ui_motion": "full"})
    assert config.get("ui_motion") == "full"


def test_export_options_without_ffmpeg(monkeypatch):
    """No ffmpeg on PATH: every video format is listed as unavailable instead of an error."""
    from fastapi.testclient import TestClient

    from sharkyclips.web import app as webapp

    real_which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None if name == "ffmpeg" else real_which(name, *a, **k))
    monkeypatch.setattr(webapp, "_formats_cache", {})
    r = TestClient(webapp.app).get("/api/export/options")
    assert r.status_code == 200
    formats = {f["id"]: f for f in r.json()["formats"]}
    assert all(not f["available"] for f in formats.values() if export.FORMATS[f["id"]].codec)
    assert webapp._formats_cache == {}  # not cached: checked again once ffmpeg is installed


@pytest.mark.requires_ffmpeg
def test_export_options_h264_available():
    """With ffmpeg installed, H.264 MP4 always works (CPU libx264 at worst)."""
    assert any(f["id"] == "mp4_h264" and f["available"] for f in export.available_formats())
