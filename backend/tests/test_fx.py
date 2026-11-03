"""Fun effects (1.2.17): instant replay, meme effects, chat bubbles, synthesized sounds."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import config
from sharkyclips.clips import ClipOptions, OutputSpec
from sharkyclips.edit import bubbles, fx, sfx
from sharkyclips.edit import plan as plan_mod
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic


@pytest.fixture(autouse=True)
def _no_leftover_projects():
    """Projects made by a test are removed afterwards (other tests expect an empty workspace)."""
    before = set(config.workspace_dir().iterdir())
    yield
    for d in set(config.workspace_dir().iterdir()) - before:
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


def _project(pid: str, seconds: float = 20.0) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": seconds, "width": 640, "height": 360, "fps": 30,
                                        "audio_codec": "aac", "mode": "gaming"})
    words = [{"start": 1.0 + i * 0.8, "end": 1.5 + i * 0.8, "word": f" w{i}"} for i in range(int(seconds) - 2)]
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [
        {"start": 1.0, "end": seconds, "words": words}]})
    return Project(pid, d)


def _chat(proj: Project, rows: list[tuple[float, str, int]], names: list[str]) -> None:
    write_json_atomic(proj.dir / "chat.json", {"version": 2, "status": "ok", "source": "test", "count": len(rows),
                                               "messages": [list(r) for r in rows], "names": names})


CAND = {"id": "c01", "rank": 1, "start": 0.0, "end": 16.0, "duration": 16.0, "peak": 5.0,
        "reasons": [{"code": "df_kill", "t": 5.0, "strength": 0.4},
                    {"code": "lol_pentakill", "t": 6.0, "strength": 1.0},
                    {"code": "laughter", "t": 11.0, "strength": 0.9},
                    {"code": "df_death", "t": 13.5, "strength": 0.6}],
        "text": "what a play"}


def test_options_validate():
    o = ClipOptions.from_dict({"replay": "auto", "chat_bubbles": 1, "memes": "light"})
    assert o.replay == "auto" and o.chat_bubbles is True and o.memes == "light"
    with pytest.raises(SharkyClipsError):
        ClipOptions.from_dict({"memes": "max"})
    with pytest.raises(SharkyClipsError):
        ClipOptions.from_dict({"replay": "always"})


def test_replay_picks_the_biggest_event_and_goes_right_after_it():
    proj = _project("fx-replay")
    p = plan_mod.build(proj, CAND, ClipOptions.from_dict({"replay": "auto"}))
    assert p.fx is not None and p.active
    (ins,) = p.fx.inserts
    assert ins.kind == "replay" and ins.code == "lol_pentakill"
    assert ins.src == pytest.approx(6.0 - fx.REPLAY_BEFORE) and ins.src_end == pytest.approx(6.0 + fx.REPLAY_AFTER)
    assert ins.dur == pytest.approx((fx.REPLAY_BEFORE + fx.REPLAY_AFTER) * 2, abs=0.05)
    # 10 s of clip are left after the event: the replay comes right after the reaction, in a pause
    assert 7.0 <= ins.at <= 11.0
    assert p.fx.final(ins.at - 0.1) == pytest.approx(ins.at - 0.1)
    assert p.fx.final(ins.at + 0.1) == pytest.approx(ins.at + 0.1 + ins.dur)
    # captions: no word runs into the replay
    words = fx.map_words(p.out_words(), p.fx)
    a, b, _i = p.fx.insert_ranges()[0]
    assert not any(w["start"] < b and w["end"] > a for w in words)
    # a short tail after the event: the replay goes at the end
    short = {**CAND, "end": 9.0, "duration": 9.0}
    p2 = plan_mod.build(proj, short, ClipOptions.from_dict({"replay": "auto"}))
    assert p2.fx.inserts[0].at == pytest.approx(p2.out_duration, abs=0.04)
    # nothing to replay / a seamless loop / the platform's length limit: no replay
    calm = {**CAND, "reasons": [{"code": "keyword", "t": 5.0}]}
    assert plan_mod.build(proj, calm, ClipOptions.from_dict({"replay": "auto"})).fx is None
    assert plan_mod.build(proj, CAND, ClipOptions.from_dict({"replay": "auto"}), max_len=17.0).fx is None


def test_memes_light_and_strong():
    proj = _project("fx-memes")
    light = plan_mod.build(proj, CAND, ClipOptions.from_dict({"memes": "light"})).fx
    kinds = [i.kind for i in light.inserts]
    assert kinds == ["freeze"] and light.punches and not light.shakes
    assert light.inserts[0].text in fx.FALLBACK_CAPTIONS[fx.meme_language(proj, CAND)]  # no AI: built-in list
    names = [n for _t, n, _g in light.sfx]
    assert "boom" in names and "thud" in names
    strong = plan_mod.build(proj, CAND, ClipOptions.from_dict({"memes": "strong"})).fx
    assert strong.shakes and not strong.punches
    # the AI's captions are used when cached for this clip
    lang = fx.meme_language(proj, CAND)
    write_json_atomic(proj.cache_dir / "memes.json",
                      {"c01": {"key": fx._caption_key(CAND, lang), "texts": ["NASIL?!"], "lang": lang}})
    assert plan_mod.build(proj, CAND, ClipOptions.from_dict({"memes": "light"})).fx.inserts[0].text == "NASIL?!"


def test_write_captions_with_a_fake_model():
    proj = _project("fx-captions")

    class Fake:
        def json(self, system, prompt, schema, **kw):
            assert "Turkish" in prompt
            return {"captions": ["YOK ARTIK", "  bruh  ", "x" * 30, "Bu ne oldu şimdi kanka.", "Kardeşim kalktı.",
                                 "Amaına koyun", "Kahpe çıktı!", "what a play"]}

    cand = {**CAND, "publish": {"language": "tr"}}
    texts = fx.write_captions(proj, cand, Fake())
    # long ones, sentences, swear words (also misspelled) and quotes of the clip are dropped
    assert texts == ["YOK ARTIK", "bruh"]
    assert fx.cached_captions(proj, cand)[0] == "YOK ARTIK"
    assert fx.cached_captions(proj, {**cand, "text": "other"}) == []  # another clip text: asked again


def test_bubble_filter():
    assert bubbles.clean("KEKW what a shot") == "KEKW what a shot"
    for bad in ("check www.spam.com", "go to discord.gg/abc", "call me +90 555 123 45 67", "mail a@b.co",
                "@someone look", "!clip", "you are a bitch", "siktir git", "сука блять"):
        assert bubbles.clean(bad) is None, bad
    assert bubbles.clean("hi", author="fuckboy99") is None
    assert bubbles.clean("noooooooooo") == "noooo"
    long = bubbles.clean("word " * 30)
    assert bubbles.clean("word " * 40) is None  # a wall of text
    assert long.endswith("…") and len(long) <= bubbles.MAX_CHARS + 1
    assert bubbles.color_for("Efe") == bubbles.color_for("efe")


def test_bubbles_pick_and_layout():
    proj = _project("fx-bubbles")
    _chat(proj, [(2.0, "LETS GO", 0), (2.3, "too soon", 1), (3.5, "www.x.com", 1), (4.0, "nice", 1),
                 (5.0, "wow", 2), (6.0, "insane", 0), (7.0, "gg", 1), (15.5, "late", 0)], ["Efe", "zeynep", "Bob"])
    p = plan_mod.build(proj, CAND, ClipOptions.from_dict({"chat_bubbles": True}))
    texts = [b["text"] for b in p.fx.bubbles]
    assert texts == ["LETS GO", "nice", "wow", "insane", "gg"]  # 1 s apart, no links, not in the last second
    assert p.fx.bubbles[0]["user"] == "Efe" and p.fx.extra == 0
    from sharkyclips.clips import Geometry, _ass_time

    geo = Geometry.for_spec(OutputSpec(), "split")
    zone = fx.bubble_zone(geo, "split", (0, 0, 0, 0), False)
    assert zone["bottom"] <= geo.h - 380 and zone["x"] >= 40 and zone["x"] + zone["w"] <= geo.w - 200
    lines = fx.ass_lines(p.fx, 0.0, geo, "split", _ass_time, "en", zone)
    assert lines and all("bubble" in ln for ln in lines)
    # never more than 3 on screen at once
    for t in np.arange(0, 16, 0.25):
        on = [ln for ln in lines if ln.startswith("Dialogue: 3,")
              and _secs(ln.split(",")[1]) <= t < _secs(ln.split(",")[2])]
        assert len(on) <= 3
    # fit layout: above the captions
    geo_f = Geometry.for_spec(OutputSpec(), "fit")
    assert fx.bubble_zone(geo_f, "fit", (0, 0, 0, 0), False)["bottom"] <= 1390 - 150


def _secs(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def test_sounds_are_synthesized():
    for name in sfx.NAMES:
        y = sfx.sound(name)
        assert y.ndim == 2 and y.shape[1] == 2 and 0.05 < len(y) / sfx.SR < 1.5
        assert 0.3 < float(np.abs(y).max()) <= 0.91
    with pytest.raises(ValueError):
        sfx.sound("airhorn")


def test_splice_audio_lengths():
    p = fx.FxPlan(inserts=[fx.Insert(2.0, 1.5, "freeze", 3.0), fx.Insert(4.0, 2.0, "replay", 1.0, 2.0)],
                  sfx=[(2.0, "boom", 0.5)])
    sr = 48000
    main = np.full((sr * 6, 2), 0.1, np.float32)

    def decode(_src, a, d, sr=48000, channels=2):
        return np.full((int(d * sr), 2), 0.2, np.float32)

    out = fx.splice_audio(main, p, Path("x"), sr, True, decode)
    assert len(out) == sr * (6 + 1.5 + 2)
    assert np.abs(out[int(2.6 * sr): int(3.4 * sr)]).max() > 0.05  # the boom plays in the freeze


def _probe(path: Path) -> dict:
    out = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type,duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return {s["codec_type"]: float(s["duration"]) for s in json.loads(out)["streams"]}


def _source(proj: Project, seconds: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=size=640x360:rate=30:duration={seconds}", "-f", "lavfi", "-i",
                    f"sine=frequency=300:sample_rate=48000:duration={seconds}", "-c:v", "libx264", "-preset",
                    "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(proj.dir / "source.mp4")],
                   check=True, capture_output=True)
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(proj.dir / "source.mp4"),
                    "-ac", "1", "-ar", "16000", str(proj.dir / "audio.wav")], check=True, capture_output=True)


@pytest.mark.requires_ffmpeg
@pytest.mark.parametrize("layout", ["fit", "split"])
def test_render_replay_memes_bubbles(tmp_path, layout):
    from sharkyclips.clips import Facecam, render_clip

    proj = _project(f"fx-render-{layout}", 18.0)
    _source(proj, 18.0)
    _chat(proj, [(2.0, "LETS GO", 0), (4.0, "nice", 1), (8.0, "insane", 0)], ["Efe", "zeynep"])
    config.update(replay_smooth="blend")
    try:
        opts = ClipOptions.from_dict({"replay": "auto", "memes": "strong", "chat_bubbles": True, "layout": layout,
                                      "profanity": "off"})
        cam = Facecam(0.0, 0.0, 0.3, 0.3) if layout == "split" else None
        dest = tmp_path / "out.mp4"
        res = render_clip(proj, CAND, opts, cam, dest, spec=OutputSpec())
        info = res.info["fx"]
        assert info["replays"] == 1 and info["freezes"] == 1 and info["shakes"] == 1 and info["bubbles"] == 3
        want = 16.0 + info["extra"]
        got = _probe(dest)
        assert got["video"] == pytest.approx(want, abs=0.1) and got["audio"] == pytest.approx(want, abs=0.1)
    finally:
        config.update(replay_smooth=None)
        shutil.rmtree(proj.dir, ignore_errors=True)
