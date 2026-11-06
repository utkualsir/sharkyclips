"""1.2.18 study cards (study mode) and the music visualizer (music mode): detection, math
rendering, card drawing, the second render pass with the right timing, beats + karaoke."""

from __future__ import annotations

import json
import shutil
import subprocess

import numpy as np
import pytest

from sharkyclips import config, studycards, visualizer
from sharkyclips.clips import ClipOptions, mode_extras, out_mapper, render_clip
from sharkyclips.project import Project, write_json_atomic


@pytest.fixture(autouse=True)
def _clean():
    yield
    for d in config.workspace_dir().glob("mx-*"):
        shutil.rmtree(d, ignore_errors=True)


def _frame(path, t: float, w: int = 108, h: int = 192) -> np.ndarray:
    raw = subprocess.run([shutil.which("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(path),
                          "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32)


def _probe(path) -> str:
    return subprocess.run([shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                           "stream=width,height", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()


def _project(pid: str, mode: str, audio: str, segs: list[dict], lang: str = "en", dur: int = 12) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    subprocess.run([shutil.which("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c=0x203040:size=320x180:rate=30:duration={dur}", "-f", "lavfi", "-i", audio, "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "source.mp4")],
                   check=True, capture_output=True)
    write_json_atomic(d / "meta.json", {"title": "Extras", "duration": dur, "width": 320, "height": 180, "fps": 30,
                                        "audio_codec": "aac", "mode": mode})
    write_json_atomic(d / "transcript.json", {"language": lang, "segments": segs})
    cands = [{"id": "c01", "rank": 1, "start": 1.0, "end": dur - 1.0, "duration": dur - 2.0, "peak": 4.0, "text": "x"}]
    write_json_atomic(d / "highlights.json", {"created_at": "2026-11-01T00:00:00+00:00", "candidates": cands})
    write_json_atomic(d / "review.json", {"highlights_created_at": "2026-11-01T00:00:00+00:00", "accepted": ["c01"]})
    return Project(pid, d)


def _seg(a: float, text: str) -> dict:
    ws = text.split()
    return {"start": a, "end": a + 0.4 * len(ws), "text": text,
            "words": [{"start": a + 0.4 * i, "end": a + 0.4 * i + 0.35, "word": w} for i, w in enumerate(ws)]}


# ------------------------------------------------------------------ study cards


def test_rules_find_spoken_formulas_and_definitions():
    lines = [{"start": 0, "end": 3, "text": "Okay let's start."},
             {"start": 3, "end": 7, "text": "Elasticity equals change in quantity divided by change in price."},
             {"start": 7, "end": 10, "text": "Opportunity cost means the value of the next best option you give up."}]
    cards = studycards.heuristic(lines, "en")
    assert [c["kind"] for c in cards] == ["formula", "definition"]
    assert r"\frac" in cards[0]["latex"] and cards[1]["title"].lower() == "opportunity cost"
    tr = studycards.heuristic([{"start": 0, "end": 3, "text": "Talep esnekliği demek fiyat değişince talebin ne kadar değiştiği."}], "tr")
    assert tr and tr[0]["kind"] == "definition"
    assert studycards.heuristic([{"start": 0, "end": 3, "text": "This round was crazy."}], "en") == []


def test_math_renders_and_bad_latex_falls_back_to_text(tmp_path):
    img = studycards.math_image(r"E_d = \frac{\Delta Q / Q}{\Delta P / P}", 80)
    assert img is not None and img.width > 150 and img.height > 40
    assert np.asarray(img)[..., 3].max() == 255  # something drawn
    assert studycards.math_image(r"\frac{", 80) is None
    p = studycards.draw_card({"kind": "formula", "title": "Elasticity", "latex": r"\frac{", "text": "how much demand moves"},
                             900, "en", tmp_path / "bad.png")
    assert p.is_file()
    for kind, extra in (("steps", {"steps": ["Find the price", "Find the quantity", "Divide"]}),
                        ("definition", {"text": "the value of the best option you give up"})):
        out = studycards.draw_card({"kind": kind, "title": "Elasticity", "latex": "", "text": "", **extra},
                                   900, "tr", tmp_path / f"{kind}.png")
        from PIL import Image

        with Image.open(out) as im:
            assert im.mode == "RGBA" and im.width == 900 and 150 < im.height < 900


def test_llm_cards_are_checked_and_placed():
    class FakeLLM:
        def json(self, system, prompt, schema, **kw):
            data = {"cards": [{"kind": "formula", "title": "Elasticity", "latex": r"E=\frac{\%\Delta Q}{\%\Delta P}",
                               "text": "how strongly demand reacts", "line": 2},
                              {"kind": "steps", "title": "Compute it", "text": "", "steps": ["% change Q", "% change P", "divide"],
                               "line": 3}]}
            assert not kw["check"](data)
            assert kw["check"]({"cards": [{"kind": "formula", "title": "x", "text": "", "line": 9}]})
            return data

    lines = [{"start": 1, "end": 3, "text": "Hi."}, {"start": 3, "end": 6, "text": "Elasticity is ..."},
             {"start": 6, "end": 9, "text": "First you ..."}]
    cards = studycards._place(studycards._ask_llm(lines, "en", FakeLLM()), lines, 12.0)
    assert [c["kind"] for c in cards] == ["formula", "steps"]
    assert cards[0]["start"] == 3 and cards[0]["end"] <= cards[1]["start"] and cards[1]["end"] <= 11.8


@pytest.mark.requires_ffmpeg
def test_study_render_shows_the_card_at_the_right_time():
    segs = [_seg(2.0, "Today we look at demand."),
            _seg(5.0, "Elasticity equals change in quantity divided by change in price.")]
    project = _project("mx-study", "study", "sine=frequency=220:sample_rate=48000:duration=12", segs)
    cand = json.loads((project.dir / "highlights.json").read_text())["candidates"][0]
    config.update(llm_enabled=False)
    opts = ClipOptions.from_dict({"subtitles": "none", "hook": False, "study_cards": "auto"})
    assert mode_extras(project, opts) == {"cards": True, "visualizer": False}
    dest = project.dir / "clips" / "c01.mp4"
    render_clip(project, cand, opts, None, dest)
    assert _probe(dest) == "1080,1920" and not (project.dir / "clips" / "c01.base.mp4").exists()
    off = ClipOptions.from_dict({"subtitles": "none", "hook": False, "study_cards": "off"})
    plain = project.dir / "clips" / "plain.mp4"
    render_clip(project, cand, off, None, plain)
    m = out_mapper(project, cand, opts)
    at = m(6.5)  # inside the card's window (the formula sentence starts at 5.0 s)
    before = m(2.5)
    diff_in = np.abs(_frame(dest, at) - _frame(plain, at))[20:80].mean()
    diff_out = np.abs(_frame(dest, before) - _frame(plain, before)).mean()
    assert diff_in > 8 and diff_out < 3
    cache = list((project.cache_dir / "llm").glob("cards_c01_*.json"))
    assert cache and json.loads(cache[0].read_text(encoding="utf-8"))["how"] == "rules"


def test_gaming_mode_has_no_extras():
    project = _project("mx-gaming", "gaming", "sine=frequency=220:sample_rate=48000:duration=6", [], dur=6)
    assert mode_extras(project, ClipOptions.from_dict({"study_cards": "auto", "visualizer": "auto"})) == \
        {"cards": False, "visualizer": False}


def test_mapper_follows_the_hook_flash():
    project = _project("mx-map", "study", "sine=frequency=220:sample_rate=48000:duration=8", [], dur=8)
    cand = json.loads((project.dir / "highlights.json").read_text())["candidates"][0]
    m = out_mapper(project, cand, ClipOptions.from_dict({"hook_flash": True, "subtitles": "none"}))
    assert m(1.0) == pytest.approx(1.0) and m(3.0) == pytest.approx(3.0) and m(0.2) is None
    assert m(0.2, "fwd") == pytest.approx(1.0)


# ------------------------------------------------------------------ visualizer


def test_beats_and_spectrum_follow_the_music():
    sr = 22050
    t = np.arange(int(sr * 8)) / sr
    y = 0.05 * np.sin(2 * np.pi * 440 * t)
    for b in np.arange(0.25, 8, 0.5):  # 120 bpm kicks
        i = int(b * sr)
        n = int(0.08 * sr)
        y[i:i + n] += 0.8 * np.sin(2 * np.pi * 60 * np.arange(n) / sr) * np.exp(-np.arange(n) / (0.02 * sr))
    f = visualizer.analyse(y.astype(np.float32), sr, 8 * visualizer.FPS)
    assert f["bands"].shape == (visualizer.BANDS, 240) and 110 <= f["tempo"] <= 130
    assert len(f["beats"]) >= 12
    on = [int(b * visualizer.FPS) for b in f["beats"]]
    assert f["pulse"][on].mean() > 0.8 and f["pulse"].min() < 0.2


def test_karaoke_lines_sweep_word_by_word():
    words = [{"start": 0.5 + 0.4 * i, "end": 0.85 + 0.4 * i, "word": w} for i, w in enumerate("we sing under the moon".split())]
    ass = visualizer.lyrics_ass(words, 1080, 1920, "tall", "en", (217, 181, 106), (255, 255, 255))
    ev = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert len(ev) == 1 and ev[0].count("\\kf") == 5 and "moon" in ev[0]
    more = words + [{"start": 2.6 + 0.4 * i, "end": 2.95 + 0.4 * i, "word": w} for i, w in enumerate("and we never sleep".split())]
    ev2 = [ln.split(",") for ln in visualizer.lyrics_ass(more, 1080, 1920, "tall", "en", (217, 181, 106),
                                                          (255, 255, 255)).splitlines() if ln.startswith("Dialogue:")]

    def secs(x: str) -> float:
        h, m, s = x.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    assert len(ev2) >= 2 and all(secs(ev2[i][2]) <= secs(ev2[i + 1][1]) + 1e-6 for i in range(len(ev2) - 1))


@pytest.mark.requires_ffmpeg
def test_music_render_is_a_visualizer_with_the_clips_sound():
    segs = [_seg(3.0, "we sing under the moon tonight")]
    audio = "aevalsrc='0.5*sin(2*PI*60*t)*exp(-30*mod(t\\,0.5))+0.1*sin(2*PI*440*t)':s=48000:d=10"
    project = _project("mx-music", "music", audio, segs, dur=10)
    cand = json.loads((project.dir / "highlights.json").read_text())["candidates"][0]
    opts = ClipOptions.from_dict({"subtitles": "bold", "hook": False, "visualizer": "auto"})
    dest = project.dir / "clips" / "c01.mp4"
    render_clip(project, cand, opts, None, dest)
    assert _probe(dest) == "1080,1920"
    a = _frame(dest, 2.0)
    assert a[60:120, 30:80].mean() < 120  # dark, blurred background - not the plain colour video
    frames = [_frame(dest, 1.0 + k * 0.1) for k in range(6)]
    assert max(np.abs(frames[k] - frames[0]).mean() for k in range(1, 6)) > 0.5  # it moves with the beat
    from sharkyclips.edit.music import decode

    snd = decode(dest, 0.0, 8.0, sr=22050, channels=1)
    assert np.sqrt(np.mean(snd ** 2)) > 0.02  # the clip's sound is kept
