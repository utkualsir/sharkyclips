"""1.2.18 my-voice dubbing: consent + own sample first, only the user's lines are re-voiced (friends
keep their voice), timing kept, the game sound stays, the render uses the dub track."""

from __future__ import annotations

import json
import shutil
import subprocess

import numpy as np
import pytest

from sharkyclips import config, dub
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic

ME, FRIEND = np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])


@pytest.fixture(autouse=True)
def _clean():
    dub.revoke()
    yield
    dub.revoke()
    for d in config.workspace_dir().glob("dub-*"):
        shutil.rmtree(d, ignore_errors=True)


def _wav(path, seconds: float, freq: float = 220.0, sr: int = 24000):
    import soundfile

    t = np.arange(int(seconds * sr)) / sr
    soundfile.write(str(path), (0.3 * np.sin(2 * np.pi * freq * t) * (1 + 0.3 * np.sin(2 * np.pi * 3 * t))).astype(np.float32), sr)
    return path


def _project(pid: str) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    subprocess.run([shutil.which("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=320x180:rate=30:duration=14", "-f", "lavfi", "-i",
                    "sine=frequency=500:sample_rate=48000:duration=14", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "source.mp4")], check=True, capture_output=True)
    write_json_atomic(d / "meta.json", {"title": "Dub test", "duration": 14, "width": 320, "height": 180, "fps": 30,
                                        "audio_codec": "aac", "mode": "gaming"})
    segs = [{"start": 4.0, "end": 6.5, "text": "bu nasıl bir oyun", "words": [
        {"start": 4.0 + i * 0.6, "end": 4.5 + i * 0.6, "word": w} for i, w in enumerate(["bu", "nasıl", "bir", "oyun"])]},
        {"start": 7.5, "end": 9.5, "text": "kanka arkanda", "words": [
            {"start": 7.5, "end": 8.2, "word": "kanka"}, {"start": 8.4, "end": 9.4, "word": "arkanda"}]}]
    write_json_atomic(d / "transcript.json", {"language": "tr", "segments": segs})
    cands = [{"id": "c01", "rank": 1, "start": 3.5, "end": 10.5, "duration": 7.0, "peak": 5.0, "text": "bu nasıl bir oyun"}]
    write_json_atomic(d / "highlights.json", {"created_at": "2026-11-01T00:00:00+00:00", "candidates": cands})
    write_json_atomic(d / "review.json", {"highlights_created_at": "2026-11-01T00:00:00+00:00", "accepted": ["c01"]})
    return Project(pid, d)


class FakeVoice:
    def __init__(self):
        self.calls = []

    def say(self, text: str, speed: float = 1.0) -> np.ndarray:
        self.calls.append((text, speed))
        n = int(dub.TTS_SR * 0.7 * len(text.split()) / speed)  # longer than its slot: forces the fit
        t = np.arange(n) / dub.TTS_SR
        return (0.2 * np.sin(2 * np.pi * 900 * t)).astype(np.float32)

    def close(self):
        pass


def _engines(order: list[np.ndarray]):
    it = iter(order)
    return {"separate": lambda x, threads: (x * 0.6, x * 0.4),  # "voice" and "game" parts of the fake mix
            "embed": lambda seg: next(it), "fingerprint": lambda: ME}


def _ready(tmp_path):
    dub.give_consent("Utku")
    dub.save_sample(_wav(tmp_path / "me.wav", 9.0), "recorded")


def _translate():
    return [{"start": 4.0, "end": 6.5, "text": "what kind of game is this"},
            {"start": 7.5, "end": 9.5, "text": "bro behind you"}]


# ------------------------------------------------------------------ the voice profile


def test_no_voice_without_consent_and_an_own_sample(tmp_path):
    with pytest.raises(SharkyClipsError) as e:
        dub.require_ready("en")
    assert getattr(e.value, "code", None) == "voice_setup"
    with pytest.raises(SharkyClipsError, match="own voice"):
        dub.save_sample(_wav(tmp_path / "a.wav", 9.0), "file")
    with pytest.raises(SharkyClipsError):
        dub.give_consent("  ")
    dub.give_consent("Utku")
    with pytest.raises(SharkyClipsError, match="too short"):
        dub.save_sample(_wav(tmp_path / "b.wav", 2.0), "file")
    p = dub.save_sample(_wav(tmp_path / "c.wav", 40.0), "recorded")
    assert p["ready"] and p["sample_source"] == "recorded" and 5 <= p["sample_seconds"] <= 30.5
    with pytest.raises(SharkyClipsError, match="isn't possible yet"):
        dub.require_ready("tr")
    assert dub.revoke()["ready"] is False and not dub.sample_path().exists()


def test_api_consent_needs_both_boxes():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    c = TestClient(app)
    assert c.post("/api/voice/consent", json={"name": "Utku", "own_voice": True}).status_code == 400
    r = c.post("/api/voice/consent", json={"name": "Utku", "own_voice": True, "no_others": True})
    assert r.status_code == 200 and r.json()["consent"] and not r.json()["ready"]


# ------------------------------------------------------------------ whose line


def test_only_the_users_own_lines_are_dubbed():
    L = dub.Line
    lines = [L(0, 1, "a", "", spk="me", sim=0.8), L(1, 2, "b", "", spk="f1", sim=0.9),  # a friend that sounds alike
             L(2, 3, "c", "", spk="me", sim=0.1), L(3, 4, "d", "", spk="me", sim=None)]
    dub.decide(lines, voice_pass=True)
    assert [ln.dub for ln in lines] == [True, False, False, False]
    assert [ln.why for ln in lines] == ["me", "other_speaker", "not_like_sample", "no_voice"]
    alone = [L(0, 1, "a", "", sim=0.7), L(1, 2, "b", "", sim=0.5)]
    dub.decide(alone, voice_pass=False)
    assert [ln.dub for ln in alone] == [True, False]  # without a voice pass: must clearly be the user


# ------------------------------------------------------------------ the dub track


@pytest.mark.requires_ffmpeg
def test_dub_track_keeps_timing_the_game_sound_and_the_friends_voice(tmp_path):
    import soundfile

    project = _project("dub-track")
    _ready(tmp_path)
    cand = json.loads((project.dir / "highlights.json").read_text())["candidates"][0]
    v = FakeVoice()
    info = dub.make(project, cand, "en", translate=_translate, voice=v, engines_override=_engines([ME, FRIEND]))
    assert info["dubbed"] == 1 and info["kept"] == 1
    assert [ln["why"] for ln in info["lines"]] == ["like_sample", "not_like_sample"]
    assert [c[0] for c in v.calls][0] == "what kind of game is this" and v.calls[-1][1] > 1.0  # sped up to fit
    y, sr = soundfile.read(info["path"], dtype="float32")
    off = info["offset"]
    assert sr == 48000 and abs(len(y) / sr - (info["end"] - off)) < 0.05

    def seg(a, b):
        return y[int((a - off) * sr): int((b - off) * sr)].mean(axis=1)

    from sharkyclips.edit.music import decode

    orig = decode(project.source_path, off, info["end"] - off, sr=48000, channels=2).mean(axis=1)

    def oseg(a, b):
        return orig[int((a - off) * sr): int((b - off) * sr)]

    friend, me = seg(7.6, 9.4), seg(4.2, 6.2)
    assert np.allclose(friend, oseg(7.6, 9.4), atol=0.02)  # untouched where a friend talks
    assert not np.allclose(me, oseg(4.2, 6.2), atol=0.05)  # my line: new voice
    spec = np.abs(np.fft.rfft(me))
    f = np.fft.rfftfreq(len(me), 1 / sr)
    assert spec[(f > 880) & (f < 920)].max() > 0.2 * spec.max()  # the (fake) dubbed voice is in
    assert spec[(f > 490) & (f < 510)].max() > 0.1 * spec.max()  # and the game sound stays underneath
    assert seg(4.2, 6.2).size and abs(np.abs(seg(3.6, 3.9)).mean() - np.abs(oseg(3.6, 3.9)).mean()) < 0.02  # before: same
    # cached: the same inputs don't run the voice again
    again = dub.make(project, cand, "en", translate=_translate, voice=v, engines_override=_engines([ME, FRIEND]))
    assert again["path"] == info["path"] and len(v.calls) == 2
    assert dub.track_for(project, cand, "en")["path"] == info["path"]


@pytest.mark.requires_ffmpeg
def test_render_uses_the_dub_and_english_subtitles(tmp_path):
    from sharkyclips.clips import ClipOptions, render_clip
    from sharkyclips.edit.music import decode
    from sharkyclips.web import state

    project = _project("dub-render")
    _ready(tmp_path)
    cand = json.loads((project.dir / "highlights.json").read_text())["candidates"][0]
    dub.make(project, cand, "en", translate=_translate, voice=FakeVoice(), engines_override=_engines([ME, FRIEND]))
    state.save_review(project, {"dub": {"c01": "en", "c99": "xx"}})
    review = state.load_review(project)
    assert review["dub"] == {"c01": "en"}
    eff = state.effective_cand(cand, review)
    assert eff["dub"] == "en" and state.edit_fingerprint(cand, review, {}) != ""
    dest = project.dir / "clips" / "c01.mp4"
    render_clip(project, eff, ClipOptions.from_dict({"subtitles": "bold", "hook": False}), None, dest)
    a = decode(dest, 0.0, 7.0, sr=48000, channels=1)
    seg = a[int(1.0 * 48000): int(2.6 * 48000)]  # 4.5-6.1 s in the source = my dubbed line
    spec = np.abs(np.fft.rfft(seg))
    f = np.fft.rfftfreq(len(seg), 1 / 48000)
    assert spec[(f > 880) & (f < 920)].max() > 0.2 * spec.max()
    with pytest.raises(SharkyClipsError):
        ClipOptions.from_dict({"dub": "tr"})


@pytest.mark.requires_ffmpeg
def test_api_dub_flow(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from sharkyclips.web import app as A, dub_api, state

    project = _project("dub-api")
    c = TestClient(app=A.app)
    r = c.post(f"/api/projects/{project.id}/clips/c01/dub", json={"lang": "en"})
    assert r.status_code == 400 and r.json().get("code") == "voice_setup"
    _ready(tmp_path)
    monkeypatch.setattr(A, "llm_available", lambda: True)
    import sharkyclips.analyze as an

    monkeypatch.setattr(an, "translate_clip", lambda project, cid, lang: _translate())
    real_make = dub.make
    monkeypatch.setattr(dub, "make", lambda project, cand, lang, progress=None, translate=None: real_make(
        project, cand, lang, progress, translate=translate, voice=FakeVoice(), engines_override=_engines([ME, FRIEND])))
    rendered = []
    monkeypatch.setattr(dub_api, "_rerender", lambda project, cid: rendered.append(cid))
    r = c.post(f"/api/projects/{project.id}/clips/c01/dub", json={"lang": "en"}).json()
    import time

    end = time.time() + 60
    while A.jobs.get(r["job"]["id"]).status in ("queued", "running") and time.time() < end:
        time.sleep(0.1)
    j = A.jobs.get(r["job"]["id"])
    assert j.status == "done", j.error
    time.sleep(0.3)
    v = c.get(f"/api/projects/{project.id}/clips/c01/dub").json()
    assert v["lang"] == "en" and v["info"]["dubbed"] == 1 and rendered == ["c01"]
    v = c.post(f"/api/projects/{project.id}/clips/c01/dub", json={"lang": ""}).json()
    assert v["lang"] == "" and state.load_review(project)["dub"] == {} and rendered == ["c01", "c01"]
