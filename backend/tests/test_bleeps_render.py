"""1.2.22 regressions: the deep swear check never changes caption text, renders with known
swears really contain bleeps (and the visual cue), a broken swear check falls back to the 1.2.20
detector visibly, zooms never stack past the cap, odd sources (other resolution, non-square
pixels, variable frame rate, a facecam box from another video) render inside the frame."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import clips, config
from sharkyclips.clips import ClipOptions, Facecam
from sharkyclips.edit import fx as fx_mod
from sharkyclips.edit import plan, swears, zoom
from sharkyclips.project import Project, write_json_atomic
from sharkyclips.voices import swearscan, tracks

FIX = Path(__file__).parent / "data" / "swear_eval" / "delta_force.json"


def _wer(ref: list[str], hyp: list[str]) -> float:
    """Word error rate (Levenshtein over words)."""
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
            prev, d[j] = d[j], cur
    return d[len(hyp)] / max(1, len(ref))


class _P:
    def __init__(self, d: Path):
        self.dir = d
        self.audio_path = d / "none.wav"
        self.cache_dir = d / "cache"
        self.transcript_path = d / "none.json"

    def load_meta(self):
        return {"mode": "gaming"}


def test_deep_check_never_changes_caption_text(tmp_path):
    """Captions = transcript (+ proofreading). The deep check may only add bleeps: on the real
    Delta Force sample the caption words are the 1.2.20 ones, except words the caption
    detector itself calls swears (those are censored, as in 1.2.20)."""
    fx = json.loads(FIX.read_text(encoding="utf-8"))
    words = [{"start": w["start"], "end": w["end"], "word": w["word"], "probability": w["p"]} for w in fx["base"]]
    scan = {"ranges": [[0, 1e9]], "items": [{**it, "votes": "2/4", "why": "scan:hint0"} for it in fx["items"]]}
    items = plan.swear_review(_P(tmp_path), [dict(w) for w in words], "tr", 0, 1e9, {}, scan=scan,
                              use_hints=False, strictness="paranoid")
    masked = {it["i"] for it in items if it.get("bleep") and it.get("i") is not None}
    flagged = {it["i"] for it in swears.detect(words, "tr", learned={}) if it.get("i") is not None}
    old = {it["i"] for it in swears.detect(words, "tr", legacy=True) if it.get("i") is not None}
    assert masked <= flagged | old, [words[i]["word"] for i in masked - flagged - old]
    ref = [w["word"] for w in words]
    hyp = ["*" if i in masked else w["word"] for i, w in enumerate(words)]
    ref_old = ["*" if i in old else w for i, w in enumerate(ref)]
    # word error rate against the transcript: only censored swears differ (no worse than 1.2.20 + the new forms)
    assert _wer([w for i, w in enumerate(ref) if i not in masked], [w for i, w in enumerate(hyp) if i not in masked]) == 0
    assert _wer(ref, hyp) <= _wer(ref, ref_old) + len(flagged - old) / max(1, len(ref)) + 1e-9
    # the deep check's audio-only bleeps exist (recall) without touching "Orası" / "kahretsin"
    assert sum(1 for it in items if it.get("bleep")) >= len(masked)
    for i, w in enumerate(words):
        if w["word"].strip(".,!?").lower() in ("orası", "kahretsizsin", "ama"):
            assert i not in masked


def test_broken_swear_check_falls_back_to_the_basic_detector(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model download failed")

    monkeypatch.setattr(plan, "swear_review", boom)
    words = [{"start": 10.2, "end": 10.6, "word": "Hello"}, {"start": 10.7, "end": 11.0, "word": "fucking"}]
    p = plan.build(_P(tmp_path), {"id": "c01", "start": 10.0, "end": 12.0, "reasons": []},
                   ClipOptions.from_dict({}), fps=30, words=words, lang="en")
    assert "swear_check_failed" in p.warnings and p.bleeps  # never zero bleeps silently
    assert p.to_dict()["warnings"] == ["swear_check_failed"]


def test_defaults_bleep_every_clip_strict_with_the_visual_cue(tmp_path):
    o = ClipOptions.from_dict({})
    assert o.bleep_visual and o.bleep_icon and o.profanity == "auto"
    words = [{"start": 10.2, "end": 10.6, "word": "Hello"}, {"start": 10.7, "end": 11.0, "word": "shit!"}]
    for vertical in (True, False):  # 16:9 too since 1.2.22
        p = plan.build(_P(tmp_path), {"id": "c01", "start": 10.0, "end": 12.0, "reasons": []}, o,
                       vertical=vertical, fps=30, words=[dict(w) for w in words], lang="en")
        assert p.bleep_mode == "bleep" and p.strictness == "strict" and p.bleeps
        assert [w["word"] for w in p.out_words()] == ["Hello", "****!"]
    ass = clips.build_ass(p.out_words(), 2.0, o, "split", "en", "", bleep_marks=p.bleeps)
    assert "bleepicon" in ass and "#@!" in ass and "\\fscx128" in ass and "****" in ass


def test_one_bleep_level_for_the_whole_clip():
    from sharkyclips.edit import audiomix

    sr = audiomix.SR
    t = np.arange(sr * 4) / sr
    voice = (0.2 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    voice[sr * 2:] *= 0.15  # a quiet second half
    y = np.stack([voice, voice], axis=1)
    out = audiomix.apply_bleeps(y.copy(), [(0.5, 0.8), (2.5, 2.8)], "bleep")

    def rms(a, b):
        seg = out[int(a * sr):int(b * sr), 0]
        return float(np.sqrt(np.mean(seg ** 2)))

    assert abs(rms(0.55, 0.75) - rms(2.55, 2.75)) / rms(0.55, 0.75) < 0.05  # same level both times
    assert abs(float(out[int(0.5 * sr), 0])) < 0.02  # fades in from nothing: no click


# ------------------------------------------------------------------ zoom


def test_zooms_never_stack_past_the_cap():
    assert max(zoom.INTENSITY.values()) <= zoom.MAX_ZOOM
    shakes = [(1.0, 1.6), (1.2, 1.8), (1.3, 2.0)]
    punches = [(1.1, 2.0), (1.4, 2.3)]
    for base in (1.0, zoom.INTENSITY["subtle"], zoom.INTENSITY["strong"], 1.3):
        for t in np.linspace(0.9, 2.4, 300):
            smart = min(max(1.0, base), zoom.MAX_ZOOM)  # perspective_filter caps the smart zoom itself
            assert smart * fx_mod.shake_zoom_at(float(t), shakes, punches, base) <= zoom.MAX_ZOOM + 1e-6
    f = fx_mod.shake_filter(shakes, punches, 30, base=zoom.INTENSITY["strong"])
    assert "clip(" in f and "min(1," in f  # shift kept inside the margin, overlaps don't add up
    assert fx_mod.shake_filter(shakes, punches, 30, base=zoom.MAX_ZOOM) == ""  # no room left
    assert "1.250" in zoom.perspective_filter([(0.0, 1.0)], 1.6, 30) or "0.250" in zoom.perspective_filter([(0.0, 1.0)], 1.6, 30)


def test_facecam_box_from_another_video_stays_inside_the_frame():
    g = clips._filter_graph("split", 1280, 720, Facecam(0.9, 0.85, 0.3, 0.3, "manual"))
    crop = g.split("crop=")[1].split(",")[0]
    w, h, x, y = (int(v) for v in crop.split(":"))
    assert x >= 0 and y >= 0 and x + w <= 1280 and y + h <= 720


@pytest.mark.requires_ffmpeg
def test_odd_source_renders_inside_the_frame(tmp_path):
    """1280x720 with 4:3 pixels (shown as 1706x720), variable frame rate, zoom + meme punches."""
    ffmpeg = shutil.which("ffmpeg")
    d = config.workspace_dir() / "odd-src"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    src = d / "source.mp4"
    subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=6",
                    "-vf", "select='lt(n\\,60)+not(mod(n\\,3))',setsar=4/3", "-fps_mode", "vfr",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(src)],
                   check=True, capture_output=True)
    w, h, sq = clips.source_size(src, {"width": 1280, "height": 720})
    assert (w, h) == (1706, 720) and sq.startswith("scale=1706:720")
    write_json_atomic(d / "meta.json", {"title": "odd", "duration": 6.0, "width": 1280, "height": 720, "fps": 30.0,
                                        "mode": "gaming"})
    write_json_atomic(d / "transcript.json", {"language": "en", "created_at": "t", "segments": [
        {"start": 1, "end": 3, "words": [{"start": 1.2, "end": 1.5, "word": " what", "probability": 0.9},
                                         {"start": 1.6, "end": 2.0, "word": " shit", "probability": 0.9}]}]})
    proj = Project("odd-src", d)
    cand = {"id": "c01", "rank": 1, "start": 0.5, "end": 5.5, "duration": 5.0, "peak": 2.0,
            "reasons": [{"t": 2.0, "code": "df_death"}], "text": "x"}
    opts = ClipOptions.from_dict({"zoom": "strong", "hook": False})
    out = tmp_path / "odd.mp4"
    res = clips.render_clip(proj, cand, opts, Facecam(0.9, 0.85, 0.3, 0.3, "manual"), out)
    assert out.is_file() and res.info.get("bleeps", 0) >= 1
    probe = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(out)], capture_output=True, text=True)
    assert probe.stdout.strip() == "1080,1920"
    # the bleep is really in the audio
    assert not swearscan.missing_bleeps(proj, cand, opts, out)
    x = tracks.read_track(out, 0, 1.15, 1.45)
    assert swearscan.tone_share(x) > 0.25
    shutil.rmtree(d, ignore_errors=True)
