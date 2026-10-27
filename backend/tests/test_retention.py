"""1.2.5 retention features: editor timelines that match the render, seamless loops."""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import config, editors
from sharkyclips.clips import ClipOptions, OutputSpec, render_clip
from sharkyclips.edit import brand, loop, music
from sharkyclips.edit import plan as plan_mod
from sharkyclips.project import Project, write_json_atomic

DATA = Path(__file__).resolve().parent / "data"
FPS = 30


def _wav(path: Path, seconds: float, freq: float = 440.0, amp: float = 0.3, sr: int = 48000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(seconds * sr)) / sr
    y = (amp * np.sin(2 * np.pi * freq * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * t))).astype(np.float32)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype("<i2").tobytes())


WORDS = [(0.5, 1.0, "this"), (1.0, 1.6, "shit"), (1.7, 2.2, "works."), (3.0, 3.6, "look"), (3.6, 4.1, "here"),
         (5.0, 5.5, "and"), (5.5, 6.2, "there."), (7.4, 7.9, "end")]


def _project(pid: str, seconds: float = 9.0, coded: bool = True) -> Project:
    """A source whose every frame says its own number: luma = 24 + (frame mod 32) * 6 (TV range)."""
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    ff = shutil.which("ffmpeg")
    video = (f"color=c=gray:s=320x180:r={FPS}:d={seconds},geq=lum='24+mod(N\\,32)*6':cb=128:cr=128" if coded
             else f"testsrc2=size=320x180:rate={FPS}:duration={seconds}")
    subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", video, "-f", "lavfi", "-i",
                    f"sine=frequency=300:sample_rate=48000:duration={seconds}", "-c:v", "libx264", "-qp", "0",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "source.mp4")],
                   check=True, capture_output=True)
    subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(d / "source.mp4"), "-ac", "1", "-ar",
                    "16000", str(d / "audio.wav")], check=True, capture_output=True)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": seconds, "width": 320, "height": 180, "fps": FPS,
                                        "audio_codec": "aac", "mode": "gaming"})
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [
        {"start": 0.5, "end": 7.9, "words": [{"start": a, "end": b, "word": " " + w} for a, b, w in WORDS]}]})
    return Project(pid, d)


def _gray_frames(path: Path, w: int = 28, h: int = 48) -> np.ndarray:
    """The raw Y plane (no TV -> PC range stretch, so the coded frame numbers read back exactly)."""
    out = subprocess.run([shutil.which("ffmpeg"), "-loglevel", "error", "-i", str(path), "-vf",
                          f"scale={w}:{h}:flags=area", "-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1"],
                         capture_output=True, check=True).stdout
    size = w * h * 3 // 2
    n = len(out) // size
    return np.frombuffer(out[: n * size], np.uint8).reshape(n, size)[:, : w * h].reshape(n, h, w).astype(np.float32)


def _t(v: str) -> Fraction:
    return Fraction(v[:-1]) if v != "0s" else Fraction(0)


@pytest.fixture
def kit(tmp_path):
    """Music track + brand preset with logo, handle, intro and outro (removed afterwards)."""
    _wav(music.folder() / "Song.wav", 30.0, 440.0)
    music.analyze("Song.wav")
    data = brand.save([{"name": "B", "handle": "me", "intro": {"enabled": True, "seconds": 1.0},
                        "outro": {"enabled": True, "seconds": 1.0}}], None)
    import cv2

    logo = tmp_path / "logo.png"
    cv2.imwrite(str(logo), np.full((40, 80, 4), 255, np.uint8))
    brand.store_logo(data["active"], logo.read_bytes(), "logo.png")
    yield
    brand.save([], None)
    shutil.rmtree(music.folder(), ignore_errors=True)
    (config.config_dir() / "music_library.json").unlink(missing_ok=True)


# ===================================================================== editor timelines


def _all_tools(**over) -> ClipOptions:
    d = {"profanity": "bleep", "zoom": "strong", "music": True, "brand": True, "layout": "fit", "hook": True,
         "hook_flash": True, "subtitles": "bold"}
    d.update(over)
    return ClipOptions.from_dict(d)


CAND = {"id": "c01", "rank": 1, "start": 0.2, "end": 8.4, "duration": 8.2, "peak": 4.0,
        "reasons": [{"code": "loudness_spike", "t": 3.2, "strength": 1}, {"code": "keyword", "t": 5.2, "value": "and",
                                                                          "strength": 0.6}],
        "publish": {"hook_text": "Watch this"}, "edit": {"deleted": [[3.0, 4.1]], "music": "Song.wav"}}


@pytest.mark.requires_ffmpeg
def test_editor_timelines_match_the_render_to_the_frame(tmp_path, kit):
    from lxml import etree

    from sharkyclips import export

    proj = _project("ed-match")
    try:
        # The render: every tool on (captions / hook off only so the picture can be read back).
        opts = _all_tools(subtitles="none", hook=False)
        dest = tmp_path / "clip.mp4"
        res = render_clip(proj, CAND, opts, None, dest, spec=OutputSpec())
        frames = _gray_frames(dest)
        # The export: FCPXML + Premiere XML with the same options (captions / hook on there).
        req = export.ExportRequest.from_dict({"format": None, "editors": ["fcpxml", "premiere"], "subtitles": ["srt"]})
        entry = export.run_export(proj, CAND, _all_tools(), None, req)
        names = {f["name"]: f for f in entry["files"]}
        root_dir = export.exports_root(proj)
        fx = next(root_dir / n for n in names if n.endswith(".fcpxml"))
        px = next(root_dir / n for n in names if n.endswith(".premiere.xml"))
        text = fx.read_text(encoding="utf-8")
        assert editors.validate(text, "fcpxml") == []
        dtd = etree.DTD(str(DATA / "fcpxml_subset.dtd"))
        doc = etree.fromstring(text.split("\n", 2)[2].encode())
        assert dtd.validate(doc), dtd.error_log.filter_from_errors()
        assert editors.validate(px.read_text(encoding="utf-8"), "premiere") == []

        # Timeline pieces vs the rendered MP4, frame by frame.
        spine = doc.find(".//spine")
        pieces = []
        for c in spine:
            off, dur = int(_t(c.get("offset")) * FPS), int(_t(c.get("duration")) * FPS)
            src = int(_t(c.get("start")) * FPS) if c.tag == "asset-clip" else None
            pieces.append((c.get("name"), off, dur, src))
        assert sum(p[2] for p in pieces) == len(frames), (pieces, len(frames))
        assert [p[0].split(" · ")[0] for p in pieces] == ["Intro card", "Hook flash", "Part 1", "Part 2", "Outro card"]
        assert res.info["duration"] == pytest.approx(len(frames) / FPS, abs=0.04)
        luma = frames[:, 21:27, 6:22].mean(axis=(1, 2))  # the picture's middle (not the blurred background)
        checked = 0
        for name, off, dur, src in pieces:
            if src is None or name.startswith("Hook flash"):
                continue
            for j in range(dur):
                if name.startswith("Part 1") and j < 7:
                    continue  # the white flash fades into the first frames
                want = 24 + ((src + j) % 32) * 6
                got = luma[off + j]
                assert abs(got - want) <= 2.5, (name, j, got, want)
                checked += 1
        assert checked > 150

        # Everything the render has is on the timeline.
        fdoc = doc
        audio_clips = [e for e in fdoc.iter("asset-clip") if e.get("lane")]
        assert {e.get("name") for e in audio_clips} >= {"Bleeps", "Music: Song"}
        assert any(e.get("audioStart") for e in spine)  # crossfaded split edit at the cut
        assert fdoc.find(".//adjust-transform/param[@name='scale']/keyframeAnimation") is not None
        music_kf = [e for e in audio_clips if e.get("name", "").startswith("Music")][0].findall(".//keyframe")
        assert len(music_kf) >= 4  # ducking under speech
        assert any(k.get("value") == "-96.0dB" for k in fdoc.iter("keyframe"))  # the swear word is muted
        vals = [m.get("value") for m in fdoc.iter("marker")]
        assert {"Bleep", "Hook flash", "Reaction word: and"} <= set(vals) and "Loud moment" not in vals  # 3.2 s was cut
        lanes = {e.get("name") for e in fdoc.iter("video") if e.get("lane")}
        assert {"Logo", "Handle", "Hook text"} <= lanes
        assert len(list(fdoc.iter("caption"))) >= 2
        roles = {f["role"] for f in entry["files"]}
        assert {"fcpxml", "premiere", "srt", "editor_media"} <= roles
        import cv2

        logo_png = next(root_dir / n for n in names if n.endswith("editor-logo.png"))
        rgba = cv2.imread(str(logo_png), cv2.IMREAD_UNCHANGED)
        assert rgba.shape[:2] == (180, 320) and rgba[..., 3].max() > 150 and rgba[..., 3].min() == 0
        hook_png = next(root_dir / n for n in names if n.endswith("editor-hook.png"))
        assert cv2.imread(str(hook_png), cv2.IMREAD_UNCHANGED)[..., 3].max() > 200  # visible text, transparent around

        # Premiere: the same cut points; the crossfade is centered on the cut.
        pdoc = etree.fromstring(px.read_text(encoding="utf-8").split("\n", 2)[2].encode())
        v1 = pdoc.find(".//video/track")
        starts = [(int(ci.findtext("start")), int(ci.findtext("in"))) for ci in v1.findall("clipitem")]
        assert [s for s, _ in starts] == [p[1] for p in pieces]
        tr = pdoc.find(".//audio/track/transitionitem")
        assert tr is not None and tr.findtext("effect/effectid") == "KGAudioTransCrossFade3dB"
        cut = pieces[3][1]
        assert int(tr.findtext("start")) + int(tr.findtext("end")) == 2 * cut
        # The SRT follows the cut too (no words from the deleted range, shifted by intro + flash).
        srt = next(root_dir / n for n in names if n.endswith(".srt") and ".editor" not in n).read_text(encoding="utf-8")
        assert "look" not in srt.lower() and "00:00:02" in srt
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)


def test_fcpxml_rules_catch_order_and_gaps():
    bad_order = ('<fcpxml version="1.9"><resources><format id="r1" frameDuration="1/30s"/><asset id="r2">'
                 '<media-rep src="file:///x.mp4"/></asset></resources><library><event><project><sequence format="r1" '
                 'duration="2s"><spine><asset-clip ref="r2" offset="0s" duration="1s" name="a"><marker start="0s" '
                 'value="m"/><caption lane="1" offset="0s" duration="1s"/></asset-clip><asset-clip ref="r2" '
                 'offset="31/30s" duration="1s" name="b"/></spine></sequence></project></event></library></fcpxml>')
    problems = editors.validate(bad_order, "fcpxml")
    assert any("DTD order" in p for p in problems)
    assert any("gap" in p for p in problems)
    assert editors.validate("<fcpxml", "fcpxml")


@pytest.mark.requires_ffmpeg
def test_editor_timeline_without_tools_and_at_60fps(tmp_path):
    """A plain clip: one part, no side files; frame math also on a 60 fps source."""
    proj = _project("ed-plain", seconds=4.0)
    try:
        meta = proj.load_meta()
        proj.save_meta({**meta, "fps": 60})
        cand = {"id": "c01", "rank": 1, "start": 0.5, "end": 3.5, "duration": 3.0, "peak": 2.0, "reasons": []}
        opts = ClipOptions.from_dict({"profanity": "off", "hook": False})
        tl = editors.build(proj, cand, opts, tmp_path / "x")
        assert tl.fps == 60 and [p.kind for p in tl.pieces] == ["main"] and tl.files == [] and tl.total == 180
        assert editors.validate(editors.fcpxml(tl), "fcpxml") == []
        assert editors.validate(editors.premiere_xml(tl), "premiere") == []
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)


# ===================================================================== seamless loop

W = [{"start": a, "end": b, "word": w} for a, b, w in WORDS]


def test_seam_moves_the_end_into_a_pause_never_mid_word():
    s = loop.find_seam(0.3, 5.2, W, src_duration=9.0)  # 5.2 is inside "and" (5.0-5.5)
    assert not any(w["start"] < s.end < w["end"] for w in W)
    assert s.end > 4.1 and abs(s.end - 5.2) <= loop.SEARCH_BACK
    assert "pause" in s.reasons or "sentence_end" in s.reasons
    s2 = loop.find_seam(0.75, 6.0, W, src_duration=9.0)  # the start inside "this" snaps before it
    assert s2.start <= 0.5 and s2.first_word == "this"


def test_seam_respects_length_limit_deleted_words_and_bleeps():
    s = loop.find_seam(0.3, 7.9, W, src_duration=9.0, max_len=5.0)
    assert s.end - s.start <= 5.0 + 1e-6
    s = loop.find_seam(0.3, 6.4, W, src_duration=9.0, deleted=[(6.15, 6.6)])  # the pause after "there." is cut
    assert not 6.15 - 0.02 <= s.end <= 6.6 + 0.02
    plain = loop.find_seam(0.3, 2.3, W, src_duration=9.0)
    swear = loop.find_seam(0.3, 2.3, W, src_duration=9.0, bleeps=[(1.0, 1.6)])
    assert plain.end == swear.end or swear.score <= plain.score  # never prefers ending on a bleep


def test_seam_on_music_and_very_short_clips():
    db = np.full(600, -18.0, np.float32) + np.random.default_rng(1).normal(0, 1.0, 600).astype(np.float32)
    s = loop.find_seam(1.0, 9.0, [], db=db, db_t0=0.0, src_duration=12.0)  # steady sound, no words
    assert s.music_like and s.audio_xfade == loop.MUSIC_XFADE
    short = loop.find_seam(0.3, 3.8, W, src_duration=9.0)
    assert short.end - short.start >= 2.5 and short.video_xfade <= 0.35
    at_end = loop.find_seam(4.0, 7.95, W, src_duration=8.0)  # the source ends right after the last word
    assert at_end.end > 7.9
    assert not at_end.tail_ok and at_end.video_xfade == 0.0


def _speechy(seconds: float, sr: int = 48000, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    env = 0.25 + 0.2 * np.abs(np.sin(2 * np.pi * 2.3 * t))
    y = env * (0.5 * np.sin(2 * np.pi * 180 * t) + 0.3 * np.sin(2 * np.pi * 523 * t)) + 0.002 * rng.normal(size=len(t))
    return np.repeat(y[:, None], 2, axis=1).astype(np.float32)


def test_loop_crossfade_removes_the_click_and_meter_sees_it():
    sr = 48000
    src = _speechy(6.0)
    a, b = int(0.5 * sr), int(4.3 * sr)
    naive = src[a:b].copy()
    m_naive = loop.measure_audio(naive, sr)
    fixed = loop.crossfade_head(src[a:b].copy(), src[b: b + int(0.06 * sr)], 0.06, sr)
    m_fixed = loop.measure_audio(fixed, sr)
    assert m_naive["click_ratio"] > 2.0 and not m_naive["ok"]
    assert m_fixed["click_ratio"] < 1.5 and m_fixed["hf_burst_db"] < 6 and m_fixed["ok"]
    # The level ramp meets the opening level without a step.
    quiet_end = src[a:b].copy()
    quiet_end[-int(1.5 * sr):] *= 0.5
    ramped = loop.match_level(quiet_end.copy(), 6.0, sr)
    assert loop.measure_audio(ramped, sr)["loudness_step_lu"] < loop.measure_audio(quiet_end, sr)["loudness_step_lu"]


def test_loud_end_and_quiet_start_meet_in_the_middle():
    """The Delta Force clip ended on loud gunfire (-12.5 LUFS) and started quietly (-27.6)."""
    sr = 48000
    y = _speechy(8.0)
    y[: int(2 * sr)] *= 0.12  # a quiet start (about -18 dB)
    before = loop.measure_audio(y.copy(), sr)
    fixed, end_gain = loop.meet_levels(y.copy(), sr)
    after = loop.measure_audio(fixed, sr)
    assert before["loudness_step_lu"] > 12 and end_gain < -5
    assert after["loudness_step_lu"] < 3 and after["click_ratio"] < 1.5


def test_plan_in_loop_mode_drops_cards_and_seam_zooms(tmp_path):
    proj = Project("loop-plan", config.workspace_dir() / "loop-plan")
    proj.dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(proj.dir / "meta.json", {"title": "T", "duration": 9.0, "fps": 30, "mode": "gaming"})
    try:
        cand = {"id": "c01", "start": 0.3, "end": 7.0, "peak": 6.4,
                "reasons": [{"code": "loudness_spike", "t": 6.3, "strength": 1}]}
        opts = ClipOptions.from_dict({"loop": True, "zoom": "strong", "profanity": "off"})
        plan = plan_mod.build(proj, cand, opts, fps=30, words=W, lang="en")
        assert plan.loop is not None and plan.active and plan.intro_s == 0 and plan.outro_s == 0
        assert not any(w["start"] < plan.end < w["end"] for w in W)
        assert all(b <= plan.out_duration - 0.35 for _a, b in plan.out_pulses("scene"))
        assert plan.to_dict()["loop"]["end"] == plan.end
        assert ClipOptions.from_dict({"loop": 1}).loop is True
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)


@pytest.mark.requires_ffmpeg
def test_loop_render_seam_is_seamless(tmp_path, kit):
    proj = _project("loop-render", coded=False)
    try:
        cand = {**CAND, "edit": {"music": "Song.wav"}, "end": 7.2}
        opts = ClipOptions.from_dict({"loop": True, "layout": "fit", "hook": True, "hook_flash": True,
                                      "music": True, "brand": True, "profanity": "bleep", "zoom": "subtle"})
        dest = tmp_path / "loop.mp4"
        res = render_clip(proj, cand, opts, None, dest, spec=OutputSpec(max_seconds=60))
        lp = res.info["loop"]
        assert res.info["intro"] == 0 and res.info["outro"] == 0  # no cards, no flash in a loop
        assert lp["audio_seam"]["ok"], lp["audio_seam"]
        assert lp["audio_seam"]["click_ratio"] < 1.5 and lp["audio_seam"]["loudness_step_lu"] < 3
        assert not any(w["start"] < lp["end"] < w["end"] for w in W)
        assert lp["dissolve"] and lp["video_seam"]["seam_step"] <= 1.5 * lp["video_seam"]["typical_step"] + 0.005
        out = json.loads(subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                                         "-of", "json", str(dest)], capture_output=True, text=True).stdout)
        assert float(out["format"]["duration"]) == pytest.approx(lp["duration"], abs=0.08) and lp["duration"] <= 60
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)
