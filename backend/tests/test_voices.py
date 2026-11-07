"""1.2.15: facecam overlay detection + remembered layouts, the voice pass (tracks, separation,
diarization, merged transcript with speakers), swear safety net + review list, bleep sounds,
caption line breaking / speaker colours / karaoke, proofreading. All models are mocked."""

from __future__ import annotations

import json
import shutil
import subprocess

import numpy as np
import pytest

from sharkyclips import captions, config, facecam
from sharkyclips.clips import ClipOptions, Facecam, build_ass
from sharkyclips.edit import audiomix, plan, proof, swears
from sharkyclips.project import Project, write_json_atomic
from sharkyclips.voices import pipeline, tracks


def W(*items, spk=None):
    return [{"start": a, "end": b, "word": w, "probability": p, **({"spk": spk} if spk else {})}
            for a, b, w, p in items]


# ------------------------------------------------------------------ facecam


class FakeFinder:
    """Faces per frame: a live webcam face bottom-left (jitters), a pixel-identical HUD
    portrait bottom-right, and a game character that wanders around."""
    kind = "fake"

    def __init__(self, n):
        self.i = -1
        self.rng = np.random.default_rng(1)
        self.n = n

    def __call__(self, frame):
        self.i += 1
        h, w = frame.shape[:2]
        out = []
        if self.i % 5 != 4:  # the streamer looks away now and then
            j = self.rng.integers(-3, 4, 2)
            out.append((int(w * 0.10) + j[0], int(h * 0.84) + j[1], int(h * 0.1), int(h * 0.11), 0.9))
        out.append((int(w * 0.86), int(h * 0.90), int(h * 0.06), int(h * 0.07), 0.8))  # HUD portrait
        out.append((int(w * self.rng.uniform(0.3, 0.7)), int(h * self.rng.uniform(0.2, 0.6)),
                    int(h * 0.09), int(h * 0.1), 0.85))
        return out


def _frames(n=24, w=640, h=360):
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:h, 0:w]
    room = np.repeat((70 + 40 * np.sin(xx / 37.0) * np.cos(yy / 23.0))[:, :, None], 3, axis=2).astype(np.uint8)
    room[:, int(w * 0.05):int(w * 0.06)] = 30  # a shelf edge inside the room
    hud = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    cam = (slice(int(h * 0.74), h), slice(0, int(w * 0.27)))
    portrait = (slice(int(h * 0.88), h), slice(int(w * 0.84), w))
    frames = []
    for i in range(n):
        # gameplay: a new scene every frame (other colours, brightness, things moving)
        f = np.clip(rng.integers(0, 200) + rng.integers(0, 56, (h, w, 3)), 0, 255).astype(np.uint8)
        f[cam] = room[cam]
        # the streamer moves inside the camera
        y0, x0 = int(h * 0.84) + (i % 3) * 2, int(w * 0.10) + (i % 4) * 2
        f[y0:y0 + int(h * 0.11), x0:x0 + int(h * 0.1)] = rng.integers(150, 230, (int(h * 0.11), int(h * 0.1), 3))
        f[portrait] = hud[portrait]  # static HUD
        frames.append(f)
    return frames


def test_facecam_picks_the_live_overlay_not_the_hud_portrait():
    frames = _frames()
    res = facecam.analyze_frames(frames, FakeFinder(len(frames)))
    best = res["candidates"][0]
    assert best["x"] < 0.03 and best["y"] == pytest.approx(0.74, abs=0.03)
    assert best["w"] == pytest.approx(0.27, abs=0.03) and best["y"] + best["h"] > 0.97
    assert best["confidence"] >= facecam.LOW_CONFIDENCE and best["liveness"] > 0.5
    hud = [c for c in res["candidates"] if c["face"]["x"] > 0.8 and c["face"]["y"] > 0.8]
    assert hud and hud[0]["liveness"] < 0.15 and hud[0]["confidence"] < 0.3  # pixel-identical "face"
    fc = facecam.to_facecam(best)
    assert fc.x == 0.0 and fc.y + fc.h == pytest.approx(1.0)


def test_facecam_layouts_are_remembered_per_channel_and_resolution(monkeypatch):
    meta = {"source": {"uploader": "utku alsir"}, "width": 1920, "height": 1080, "game_detect": {"game": "lol"}}
    facecam.forget_layout(meta)
    assert facecam.find_layout(meta) is None
    facecam.remember_layout(meta, Facecam(0, 0.74, 0.27, 0.26, "manual"), confirmed=True)
    facecam.remember_layout(meta, Facecam(0.8, 0.8, 0.2, 0.2, "auto"), confirmed=False)  # never overwrites
    lay = facecam.find_layout({**meta, "game_detect": {"game": "delta_force"}})
    assert lay["box"]["x"] == 0 and lay["confirmed"]
    assert facecam.find_layout({**meta, "width": 1280, "height": 720}) is None  # per resolution
    assert facecam.find_layout({**meta, "source": {"uploader": "someone"}}) is None  # per channel

    class P:
        source_path = "x.mp4"
        cache_dir = config.config_dir() / "fc-test-cache"

        @staticmethod
        def load_meta():
            return {**meta, "duration": 100}

    monkeypatch.setattr(facecam, "verify_box", lambda *a, **k: 0.8)
    res = facecam.detect_for_project(P())
    assert res["from"] == "memory" and res["facecam"]["x"] == 0 and res["facecam"]["source"] == "remembered"
    monkeypatch.setattr(facecam, "verify_box", lambda *a, **k: 0.0)  # layout changed -> full detection
    monkeypatch.setattr(facecam, "analyze", lambda *a, **k: {"candidates": [], "confidence": 0.0})
    res = facecam.detect_for_project(P())
    assert res["from"] == "detect" and res["facecam"] is None
    facecam.forget_layout(meta)


# ------------------------------------------------------------------ swears


def test_swear_safety_net():
    words = W((0, 0.4, "abi", 0.9), (0.4, 0.9, "s**yim", 0.6), (1.0, 1.5, "orosbu", 0.5),
              (1.6, 2.0, "sıkıntı", 0.4), (2.1, 2.5, "kahpe.", 0.9), (2.6, 3.0, "sıkeyim", 0.3),
              (3.1, 3.5, "güzel", 0.95))
    items = {it["word"]: it for it in swears.detect(words, "tr")}
    assert items["s**yim"]["status"] == "sure" and items["s**yim"]["why"] == "masked"
    assert items["kahpe."]["status"] == "sure"
    assert items["orosbu"]["status"] == "sure"  # a known variant spelling
    assert items["sıkeyim"]["status"] == "maybe"
    assert "sıkıntı" not in items and "güzel" not in items and "abi" not in items
    # another pass heard a swear where the main words have nothing -> a time-only "maybe"
    got = swears.detect(words, "tr", hints=[{"start": 5.0, "end": 5.4, "word": "siktir", "src": "acoustic",
                                             "spk": "f1", "score": 0.75}])
    extra = [it for it in got if it["i"] is None]
    assert extra and extra[0]["spk"] == "f1" and swears.bleeped(extra[0])
    # a hint confirming an unsure word raises its score
    conf = swears.detect(words, "tr", hints=[{"start": 2.6, "end": 3.0, "word": "sikeyim", "src": "acoustic"}])
    it = next(i for i in conf if i["word"] == "sıkeyim")
    assert it["score"] >= swears.BLEEP_MAYBE_AT and "acoustic" in it["why"]


def _project(pid: str) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": 60.0, "mode": "gaming"})
    write_json_atomic(d / "highlights.json", {"mode": "gaming", "created_at": "x", "candidates": [
        {"rank": 1, "id": "c01", "start": 1.0, "end": 5.0, "duration": 4.0, "peak": 2.0, "hype_score": 80,
         "reasons": [], "signal_scores": {}, "text": "hi"}]})
    write_json_atomic(d / "transcript.json", {"language": "tr", "created_at": "t1", "segments": [
        {"start": 1, "end": 4, "words": [{"start": 1.2, "end": 1.6, "word": " kanka", "probability": 0.9},
                                         {"start": 1.7, "end": 2.1, "word": " geliyor", "probability": 0.9}]}]})
    return Project(pid, d)


def test_plan_bleeps_every_speaker_and_respects_the_review_list():
    proj = _project("plan-swears")
    words = (W((1.0, 1.4, "abi", 0.9), (1.5, 1.9, "amına", 0.9), spk="me")
             + W((2.0, 2.4, "siktir", 0.8), (2.5, 2.9, "git", 0.9), (3.0, 3.4, "orosbu", 0.4), spk="f1"))
    cand = {"id": "c01", "start": 1.0, "end": 4.0}
    opts = ClipOptions.from_dict({"profanity": "bleep", "bleep_sound": "boop"})
    p = plan.build(proj, cand, opts, words=[dict(w) for w in words], lang="tr", fps=30)
    by = {it["word"]: it for it in p.swears}
    assert by["amına"]["spk"] == "me" and by["siktir"]["spk"] == "f1" and by["siktir"]["bleep"]
    # "amına" + "siktir" are 100 ms apart: one bleep (closer than 150 ms after padding)
    assert len(p.bleeps) == 2 and p.bleep_sound == "boop"
    caps = [w["word"] for w in p.out_words()]
    assert "s*****" in caps and "a****" in caps and "o*****" in caps  # censored for every speaker
    # the user: unbleep "siktir", bleep "git" by hand
    p2 = plan.build(proj, cand, opts, words=[dict(w) for w in words], lang="tr", fps=30,
                    edit={"unbleep": [[2.0, 2.4]], "bleep": [[2.5, 2.9]]})
    by2 = {it["word"]: it for it in p2.swears}
    assert not by2["siktir"]["bleep"] and by2["git"]["bleep"] and by2["git"]["status"] == "manual"
    caps2 = [w["word"] for w in p2.out_words()]
    assert "siktir" in caps2 and "g**" in caps2
    shutil.rmtree(proj.dir, ignore_errors=True)


def test_clean_edit_keeps_bleep_ranges():
    from sharkyclips.web import state

    e = state.clean_edit({"bleep": [[2, 1], [3, 3.5]], "unbleep": [["x", 1], [4, 4.2]]})
    assert e == {"bleep": [[3.0, 3.5]], "unbleep": [[4.0, 4.2]]}


# ------------------------------------------------------------------ bleep sound


def test_bleep_sounds_follow_the_voice_level_with_fades():
    sr = audiomix.SR
    t = np.arange(sr * 2) / sr
    for amp in (0.05, 0.3):
        voice = (amp * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
        y = np.stack([voice, voice], axis=1)
        for sound in ("classic", "boop", "custom"):
            custom = np.sin(2 * np.pi * 700 * t[: sr // 4]).astype(np.float32) if sound == "custom" else None
            out = audiomix.apply_bleeps(y.copy(), [(0.8, 1.2)], "bleep", sound, custom)
            seg = out[int(0.85 * sr):int(1.15 * sr), 0]
            rms = float(np.sqrt(np.mean(seg ** 2)))
            assert rms == pytest.approx(amp / np.sqrt(2) * 0.71, rel=0.2)  # 3 dB under the voice
            assert abs(out[int(0.8 * sr), 0] - y[int(0.8 * sr), 0]) < 0.01  # fades in from the original
    muted = audiomix.apply_bleeps(np.ones((sr, 2), np.float32) * 0.2, [(0.2, 0.6)], "mute")
    assert abs(muted[int(0.4 * sr), 0]) < 1e-6 and muted[int(0.1 * sr), 0] == pytest.approx(0.2)


# ------------------------------------------------------------------ captions


def test_line_breaking_keeps_names_numbers_and_particles_together():
    ws = [{"start": i * 0.3, "end": i * 0.3 + 0.25, "word": w} for i, w in enumerate(
        "bugün Delta Force oynadık ve tam 55 kill aldık sen de gördün mü".split())]
    cards = captions.cards(ws, "tr", 18, max_lines=2)
    for c in cards:
        lines = captions.split_lines(c, "tr", 18)
        assert len(lines) <= 2
        for ln_a, ln_b in zip(lines, lines[1:]):
            pair = (ln_a[-1]["word"], ln_b[0]["word"])
            assert pair not in {("Delta", "Force"), ("55", "kill"), ("sen", "de"), ("tam", "55")}
    flat = [[w["word"] for w in c] for c in cards]
    for c_a, c_b in zip(flat, flat[1:]):
        assert (c_a[-1], c_b[0]) not in {("Delta", "Force"), ("55", "kill"), ("sen", "de")}
    # a new speaker always starts a new caption
    two = [{"start": 0, "end": 0.3, "word": "abi", "spk": "me"}, {"start": 0.35, "end": 0.6, "word": "dur", "spk": "f1"}]
    assert len(captions.cards(two, "tr", 30)) == 2


def test_ass_speaker_colours_name_tags_and_karaoke():
    ws = [{"start": 0.0, "end": 0.4, "word": "abi", "spk": "me"}, {"start": 0.5, "end": 0.9, "word": "geldi", "spk": "me"},
          {"start": 1.6, "end": 2.0, "word": "kaç", "spk": "f1"}, {"start": 2.1, "end": 2.5, "word": "kanka", "spk": "f1"}]
    ass = build_ass(ws, 3.0, ClipOptions.from_dict({"subtitles": "speakers", "hook": False}), "fit", "tr", "",
                    speakers={"f1": "Efe"})
    assert "Efe" in ass and "Ben" in ass  # name tags (custom name / default)
    assert "&H00FFD67F" in ass  # friend colour #7FD6FF as &HAABBGGRR
    kara = build_ass(ws, 3.0, ClipOptions.from_dict({"subtitles": "karaoke", "hook": False}), "fit", "tr", "")
    assert "\\kf" in kara and "Style: karaoke" in kara
    plain = build_ass([{k: v for k, v in w.items() if k != "spk"} for w in ws], 3.0,
                      ClipOptions.from_dict({"subtitles": "clean", "hook": False}), "fit", "tr", "")
    assert "Efe" not in plain and "&H00FFD67F" not in plain


# ------------------------------------------------------------------ proofreading


def test_proof_fixes_capitals_questions_and_cached_llm_fixes():
    ws = [{"start": 0.0, "end": 0.3, "word": "istanbul'a"}, {"start": 0.4, "end": 0.7, "word": "geliyor"},
          {"start": 0.8, "end": 1.1, "word": "musun"}, {"start": 2.5, "end": 2.8, "word": "evet"},
          {"start": 2.9, "end": 3.2, "word": "zerodam"}]
    out = proof.fix_words(ws, "tr", fixes={proof.key(ws[1]): "Geliyor"}, terms=["ZeroDam"])
    assert [w["word"] for w in out] == ["İstanbul'a", "Geliyor", "musun?", "Evet", "ZeroDam"]
    assert out[0]["orig"] == "istanbul'a" and ws[0]["word"] == "istanbul'a"

    class FakeLLM:
        model = "fake"

        def json(self, system, prompt, schema, **kw):
            n = schema["properties"]["words"]["minItems"]
            return {"words": ["Geliyor", "musun?", "Bambaşka"][:n] + ["x"] * max(0, n - 3)}

    fixes = proof.proofread_words(FakeLLM(), ws[1:4], "tr", [])
    assert fixes == {proof.key(ws[1]): "Geliyor", proof.key(ws[2]): "musun?"}  # "Bambaşka" is a rewrite


# ------------------------------------------------------------------ voice pass (mocked models)


def _av(path, seconds, tracks_spec):
    """A small video with one audio stream per (title, frequency)."""
    ffmpeg = shutil.which("ffmpeg")
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
           f"testsrc2=size=320x180:rate=15:duration={seconds}"]
    for _title, freq in tracks_spec:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={seconds}"]
    cmd += ["-map", "0:v"]
    for i in range(len(tracks_spec)):
        cmd += ["-map", f"{i + 1}:a"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac"]
    for i, (title, _f) in enumerate(tracks_spec):
        cmd += [f"-metadata:s:a:{i}", f"title={title}", f"-metadata:s:a:{i}", f"handler_name={title}"]
    subprocess.run(cmd + ["-shortest", str(path)], check=True, capture_output=True)


class FakeDiarizer:
    def turns(self, x):
        n = len(x) / 16000
        return [(0.1, min(n, 2.0), 0), (min(n, 2.2), min(n, 3.6), 1)]

    def embed(self, x):
        v = np.zeros(4, np.float32)
        v[0 if len(x) > 16000 * 1.65 else 1] = 1.0
        return v


def _fake_asr(calls):
    def asr(x, lang, hot=None):
        calls.append((len(x), hot))
        secs = len(x) / 16000
        if hot:  # the acoustic re-listen hears the friend's swear
            return [{"start": 0.1, "end": secs, "text": "siktir", "avg_logprob": -0.3, "no_speech_prob": 0.1,
                     "words": [{"start": 0.95, "end": 1.35, "word": " siktir", "probability": 0.8}]}]
        if secs > 2.1:
            return [{"start": 0, "end": secs, "text": "geliyor musun", "avg_logprob": -0.2, "no_speech_prob": 0.0,
                     "words": [{"start": 0.3, "end": 0.7, "word": " geliyor", "probability": 0.9},
                               {"start": 0.8, "end": 1.2, "word": " musun", "probability": 0.9}]},
                    {"start": 1.2, "end": secs, "text": "İzlediğiniz için teşekkür ederim", "avg_logprob": -0.4,
                     "no_speech_prob": 0.2, "words": [{"start": 1.3, "end": 1.5, "word": " İzlediğiniz",
                                                       "probability": 0.9}]}]
        return [{"start": 0, "end": secs, "text": "kaç orosbu", "avg_logprob": -0.5, "no_speech_prob": 0.1,
                 "words": [{"start": 0.3, "end": 0.7, "word": " kaç", "probability": 0.9},
                           {"start": 0.8, "end": 1.3, "word": " sıkeyim", "probability": 0.3}]}]
    return asr


@pytest.mark.requires_ffmpeg
def test_voice_pass_single_track_separation_and_diarization():
    proj = _project("voices-single")
    _av(proj.dir / "source.mp4", 6, [("", 300)])
    calls: list = []
    eng = pipeline.Engines(separator=lambda x44: np.asarray(x44, np.float32).mean(axis=0)[::3][: x44.shape[1] * 16 // 44],
                           diarizer=FakeDiarizer(), asr=_fake_asr(calls))
    data = pipeline.run_voice_pass(proj, engines=eng)
    assert data["mode"] == "separate" and data["separated"] and data["diarized"]
    assert set(data["speakers"]) == {"me", "f1"}
    texts = [(w["word"], w["spk"]) for w in data["words"]]
    assert ("geliyor", "me") in texts and ("sıkeyim", "f1") in texts
    assert not any("İzlediğiniz" in w for w, _s in texts)  # Whisper's outro hallucination is dropped
    assert any(h["src"] == "acoustic" for h in data["hints"])  # the unsure word was re-listened to
    assert any(hot for _n, hot in calls)
    # the clip's words now come from the voice pass, with speakers; the swear is bleeped
    p = plan.build(proj, {"id": "c01", "start": 1.0, "end": 5.0}, ClipOptions.from_dict({"profanity": "bleep"}),
                   fps=30)
    spk = {w["word"]: w.get("spk") for w in p.words}
    assert spk.get("sıkeyim") == "f1"
    assert any(it["spk"] == "f1" and it["bleep"] for it in p.swears)
    assert set(p.speakers) == {"me", "f1"}
    shutil.rmtree(proj.dir, ignore_errors=True)


@pytest.mark.requires_ffmpeg
def test_voice_pass_multitrack_labels_and_memory():
    proj = _project("voices-multi")
    meta = json.loads((proj.dir / "meta.json").read_text(encoding="utf-8"))
    meta["source"] = {"type": "file"}
    write_json_atomic(proj.dir / "meta.json", meta)
    _av(proj.dir / "source.mp4", 6, [("Everything", 300), ("Mic", 400), ("Discord", 500), ("Game", 600)])
    streams = tracks.audio_streams(proj.source_path)
    assert [s["title"] for s in streams] == ["Everything", "Mic", "Discord", "Game"]
    labels, src = tracks.labels_for(proj.load_meta(), streams)
    assert labels == ["mixed", "me", "friends", "game"] and src == "guess"
    tracks.save_labels(proj, ["mixed", "me", "friends", "ignore"])
    assert tracks.labels_for({"source": {"type": "file"}}, streams) == (["mixed", "me", "friends", "ignore"],
                                                                         "remembered")
    calls: list = []
    data = pipeline.run_voice_pass(proj, engines=pipeline.Engines(diarizer=None, asr=_fake_asr(calls)))
    assert data["mode"] == "tracks"
    assert {w["spk"] for w in data["words"]} <= {"me", "f1"} and "me" in data["speakers"]
    shutil.rmtree(proj.dir, ignore_errors=True)


def test_words_for_merges_only_inside_the_voice_ranges():
    proj = _project("voices-merge")
    write_json_atomic(proj.dir / "voices.json", {
        "version": pipeline.VERSION, "ranges": [[1.0, 3.0]], "speakers": {"me": {}, "f1": {}}, "names": {},
        "words": [{"start": 1.5, "end": 1.9, "word": "yeni", "p": 0.9, "spk": "f1", "src": "voc"}], "hints": []})
    base = [{"start": 0.5, "end": 0.9, "word": "önce"}, {"start": 1.5, "end": 1.9, "word": "eski"},
            {"start": 3.5, "end": 3.9, "word": "sonra"}]
    got = pipeline.words_for(proj, 0.0, 5.0, base)
    assert [w["word"] for w in got] == ["önce", "yeni", "sonra"] and got[1]["spk"] == "f1"
    shutil.rmtree(proj.dir, ignore_errors=True)


def test_acoustic_hits_must_sound_like_what_was_heard():
    final = [{"start": 1.0, "end": 1.4, "word": "sürekli", "p": 0.4}, {"start": 2.0, "end": 2.4, "word": "sıkeyim", "p": 0.3}]
    assert not pipeline._heard_alike({"start": 1.0, "end": 1.4, "word": "siktir"}, final, [], "tr")
    assert pipeline._heard_alike({"start": 2.0, "end": 2.4, "word": "sikeyim"}, final, [], "tr")
    lone = [{"start": 5.0, "end": 5.4, "word": "siktir", "p": 0.8}]
    assert pipeline._heard_alike({"start": 5.0, "end": 5.4, "word": "siktir"}, final, lone, "tr")


def test_colloquial_words_and_speaker_smoothing():
    assert not swears.detect(W((0, 0.4, "sıkıyo", 0.4)), "tr")  # "sıkıyor" = shoots
    ws = [{"start": 0, "end": 0.3, "word": "Cb", "spk": "me"}, {"start": 0.32, "end": 0.5, "word": "'ye", "spk": "f4"},
          {"start": 0.52, "end": 0.8, "word": "gidelim", "spk": "me"}, {"start": 0.82, "end": 1.0, "word": "lan.", "spk": "f4"},
          {"start": 3.0, "end": 3.3, "word": "dur", "spk": "f1"}]
    assert [w["spk"] for w in pipeline.smooth_speakers(ws)] == ["me", "me", "me", "me", "f1"]


def test_hallucinations_and_dedupe():
    segs = [{"text": "Altyazı M.K.", "avg_logprob": -0.2, "no_speech_prob": 0.1,
             "words": [{"start": 0, "end": 0.5, "word": "Altyazı", "probability": 0.9}]},
            {"text": "tamam", "avg_logprob": -0.2, "no_speech_prob": 0.1,
             "words": [{"start": 1, "end": 1.4, "word": " tamam", "probability": 0.7}]}]
    ws = pipeline.clean_segments(segs, 10.0, 0, 100)
    assert [w["word"] for w in ws] == ["tamam"] and ws[0]["start"] == 11.0
    d = pipeline.dedupe([{"start": 1, "end": 1.4, "word": "tamam", "p": 0.5, "spk": "me"},
                         {"start": 1.05, "end": 1.4, "word": "tamam.", "p": 0.9, "spk": "me"},
                         {"start": 1.1, "end": 1.3, "word": "dur", "p": 0.8, "spk": "f1"},
                         {"start": 2.0, "end": 2.4, "word": "gidiyor", "p": 0.5, "spk": "f1"},
                         {"start": 2.05, "end": 2.4, "word": "gidelim", "p": 0.7, "spk": "me"}])
    # clear overlapping speech of two people stays; two readings of one voice -> the surer one
    assert [(w["word"], w["p"]) for w in d] == [("tamam.", 0.9), ("dur", 0.8), ("gidelim", 0.7)]


def test_api_voices_facecam_and_bleep():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    proj = _project("api-voices")
    write_json_atomic(proj.dir / "meta.json", {**proj.load_meta(), "width": 1920, "height": 1080})
    v = client.get(f"/api/projects/{proj.id}/voices").json()
    assert v["done"] is False and "separator" in v["models"]["models"]
    assert client.put(f"/api/projects/{proj.id}/voices/names", json={"names": {"f1": "Efe"}}).status_code == 400
    write_json_atomic(proj.dir / "voices.json", {
        "version": pipeline.VERSION, "ranges": [[0, 6]], "names": {"f2": "X"}, "hints": [{"start": 2, "end": 2.4, "spk": "f2"}],
        "speakers": {"me": {"seconds": 10}, "f1": {"seconds": 5}, "f2": {"seconds": 3}},
        "words": [{"start": 1, "end": 1.4, "word": "a", "p": 1, "spk": "f2", "src": "mix"}]})
    m = client.put(f"/api/projects/{proj.id}/voices/merge", json={"from": "f2", "into": "me"}).json()
    assert set(m["speakers"]) == {"me", "f1"} and m["speakers"]["me"]["seconds"] == 13
    saved = pipeline.load(proj)
    assert saved["words"][0]["spk"] == "me" and saved["hints"][0]["spk"] == "me" and "f2" not in saved["names"]
    n = client.put(f"/api/projects/{proj.id}/voices/names", json={"names": {"f1": "Efe", "zz": "no"}}).json()
    assert n["names"] == {"f1": "Efe"}
    peaks = client.get(f"/api/projects/{proj.id}/peaks?start=0&end=5&n=50").json()
    assert len(peaks["peaks"]) == 50
    r = client.put(f"/api/projects/{proj.id}/facecam", json={"facecam": {"x": 0, "y": 0.74, "w": 0.27, "h": 0.26,
                                                                          "source": "manual"}}).json()
    assert r["facecam"]["x"] == 0 and r["facecam_checked"]
    a = client.get(f"/api/projects/{proj.id}/facecam/analysis").json()
    assert a["candidates"] == [] and a["layout"] is not None and a["layout"]["confirmed"]
    client.delete("/api/facecam/layouts")
    snd = client.get("/api/bleep/preview?sound=boop")
    assert snd.status_code == 200 and snd.content[:4] == b"RIFF"
    assert client.get("/api/bleep").json()["custom"] is False
    shutil.rmtree(proj.dir, ignore_errors=True)
