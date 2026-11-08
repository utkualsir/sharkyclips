"""1.2.34 Easy mode 2.0: context guard, length targets, nudges, hook check, reasons, taste,
autopilot, phone preview, action tracking, caption fixes, weekly digest."""

from __future__ import annotations

import numpy as np
import pytest

from sharkyclips import shaping


def _words(spec: list[tuple[float, float, str]]) -> list[dict]:
    return [{"start": a, "end": b, "word": w} for a, b, w in spec]


def _around(words, db=None, laugh=None, events=None, mode="gaming", t0=0.0, duration=200.0):
    db = np.full(800, -30.0, np.float32) if db is None else db
    return shaping.Around(_words(words), t0, db, laugh, float(np.median(db)), duration, mode, events or [])


# a sentence "so I go in there." 10.0-11.8, "and then" 12.0-14.0 (no end), "boom he's dead!" 14.1-15.5
SENT = [(10.0, 10.3, "so"), (10.35, 10.5, "I"), (10.55, 10.8, "go"), (10.85, 11.0, "in"), (11.05, 11.8, "there."),
        (12.0, 12.4, "and"), (12.45, 13.0, "then"), (13.05, 14.0, "wait"), (14.1, 14.5, "boom"), (14.55, 15.0, "he's"),
        (15.05, 15.5, "dead!"), (30.0, 30.5, "okay."), (31.0, 31.4, "nice"), (31.5, 32.0, "one"), (32.05, 32.6, "right")]


def test_guard_moves_a_mid_sentence_start_to_the_sentence_start():
    ar = _around(SENT)
    s, e, why = shaping.guard(ar, {}, 12.9, 30.6, 0.0, 200.0, 60.0)
    assert "setup_sentence" in why
    assert 11.8 < s <= 12.0  # "and then ..." - right before "and", after "there."


def test_guard_keeps_the_build_up_before_a_big_moment():
    ar = _around(SENT, events=[{"t": 14.2, "code": "df_kill"}])
    s, _e, why = shaping.guard(ar, {}, 14.05, 30.6, 0.0, 200.0, 60.0)
    assert "setup_lead" in why and s <= 14.2 - 2.0


def test_guard_waits_for_the_laugh_and_finishes_the_sentence():
    laugh = np.zeros(200, np.float32)
    laugh[30:34] = 0.8  # laughing from 30 s to 34 s
    ar = _around(SENT, laugh=laugh)
    s, e, why = shaping.guard(ar, {}, 9.9, 30.6, 0.0, 200.0, 60.0)
    assert "payoff_reaction" in why and e >= 34.0
    # without the laugh, a sentence cut in the middle ("nice one | right") is finished
    ar = _around(SENT)
    _s, e2, why2 = shaping.guard(ar, {}, 9.9, 31.45, 0.0, 200.0, 60.0)
    assert "payoff_sentence" in why2 and e2 >= 32.6


def test_guard_never_crosses_the_neighbours_or_the_mode_limit():
    laugh = np.ones(200, np.float32)  # "laughing" all the time: the guard still stops
    ar = _around(SENT, laugh=laugh, events=[{"t": 14.2, "code": "df_kill"}])
    s, e, _why = shaping.guard(ar, {}, 14.05, 30.6, 13.0, 33.0, 60.0)
    assert s >= 13.0 and e <= 33.0
    s, e, _why = shaping.guard(ar, {}, 14.05, 30.6, 0.0, 200.0, 18.0)
    assert e - s <= 18.01  # never longer than the mode limit (or the found cut, if that was longer)
    assert s <= 14.2 - 2.0  # and the reaction tail goes first: the build-up stays


def test_the_ai_judgement_adds_setup():
    ar = _around(SENT)
    cand = {"llm": {"self_contained": False, "start_shift_s": 0, "end_shift_s": 0}}
    s, _e, why = shaping.guard(ar, cand, 30.9, 60.0, 0.0, 200.0, 60.0)
    assert "ai_setup" in why and s < 30.9


def test_targets_per_content_type():
    assert shaping.target("gaming", {"llm": {"moment_type": "funny", "funny": 8, "exciting": 4}})["max"] == 28
    assert shaping.target("gaming", {"llm": {"moment_type": "skill", "funny": 3, "exciting": 8}})["max"] == 35
    assert shaping.target("study", {}) == {"kind": "study", "min": 30.0, "max": 45.0}
    assert shaping.target("music", {})["max"] == 30
    tgt = shaping.target("gaming", {"llm": {"moment_type": "skill", "funny": 3, "exciting": 8}})
    assert shaping.length_note(30, tgt) is None and shaping.length_note(40, tgt) == "long"
    assert shaping.length_note(50, tgt) == "very_long"


def test_nudges_move_by_about_three_seconds_on_word_boundaries():
    ar = _around(SENT)
    tgt = shaping.TARGETS["action"]
    tgt = {"kind": "action", "min": tgt[0], "max": tgt[1]}
    s, e = shaping.nudge(ar, {}, 14.05, 30.6, "earlier", tgt, 0.0, 200.0)
    assert e == 30.6 and 9.75 <= s <= 11.9  # ~3 s back, snapped to the sentence start ("so I go in there.")
    s, e = shaping.nudge(ar, {}, 9.9, 30.6, "later", tgt, 0.0, 200.0)
    assert s == 9.9 and 32.6 <= e <= 33.7  # ~3 s later (after "nice one right")
    s, e = shaping.nudge(ar, {}, 9.9, 60.0, "short", tgt, 0.0, 200.0)
    assert e - s < 50.1 and e - s >= tgt["min"]
    s, e = shaping.nudge(ar, {}, 14.05, 30.6, "long", tgt, 0.0, 200.0)
    assert s < 14.05 and e > 30.6
    # a neighbour right behind: can't go later
    assert shaping.nudge(ar, {}, 9.9, 30.6, "later", tgt, 0.0, 30.6) == (9.9, 30.6)


def test_auto_trim_detection():
    cand = {"start": 10.0, "end": 30.0}
    shape = {"start": 9.0, "end": 31.0}
    assert shaping.is_auto_trim(None, None, cand)
    assert shaping.is_auto_trim({"start": 9.0, "end": 31.0}, shape, cand)
    assert not shaping.is_auto_trim({"start": 8.0, "end": 31.0}, shape, cand)  # the user moved it
    assert not shaping.is_auto_trim(None, shape, cand)  # the user went back to the found cut
    e = shaping.edit_for(cand, 10.01, 31.0, {"deleted": [[12, 13]]})
    assert e == {"deleted": [[12, 13]], "start": None, "end": 31.0}


# ===================================================================== pacing: slow parts at 1.2x


def _talk_project(pid: str, seconds: float = 24.0):
    """Words in 0.5-5 s and 15-23 s only: 5-15 s is a quiet walk (nobody talks)."""
    import shutil

    from sharkyclips import config
    from sharkyclips.project import Project, write_json_atomic

    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": seconds, "width": 640, "height": 360, "fps": 30,
                                        "audio_codec": "aac", "mode": "gaming"})
    words = [{"start": 0.5 + i * 0.5, "end": 0.9 + i * 0.5, "word": f" a{i}"} for i in range(9)]
    words += [{"start": 15.0 + i * 0.5, "end": 15.4 + i * 0.5, "word": f" b{i}"} for i in range(16)]
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [
        {"start": 0.5, "end": seconds, "words": words}]})
    return Project(pid, d)


def test_time_stretch_keeps_the_length_asked_for():
    from sharkyclips.edit import fx

    sr = 48000
    t = np.arange(sr * 2) / sr
    x = np.stack([np.sin(2 * np.pi * 440 * t)] * 2, 1).astype(np.float32) * 0.5
    y = fx.time_stretch(x, int(len(x) / 1.2), sr)
    assert len(y) == int(len(x) / 1.2) and y.shape[1] == 2
    # the pitch stays (zero crossings per second ~ 880 for 440 Hz)
    zc = np.sum(np.abs(np.diff(np.sign(y[sr // 4: -sr // 4, 0])))) / 2 / (len(y) / sr - 0.5)
    assert 800 < zc < 960


@pytest.mark.requires_ffmpeg
def test_slow_parts_play_faster_and_never_hold_speech(tmp_path):
    import shutil

    from sharkyclips.clips import ClipOptions, OutputSpec, render_clip
    from sharkyclips.edit import plan as plan_mod
    from test_fx import _probe, _source

    proj = _talk_project("easy2-speed")
    try:
        _source(proj, 24.0)
        cand = {"id": "c01", "rank": 1, "start": 0.0, "end": 24.0, "duration": 24.0, "peak": 20.0,
                "reasons": [{"code": "df_kill", "t": 20.0, "strength": 0.8}], "text": "x"}
        opts = ClipOptions.from_dict({"speedup": "auto", "profanity": "off", "layout": "fit"})
        plan = plan_mod.build(proj, cand, opts, fps=30)
        assert plan.speed, "the quiet walk 5-15 s is sped up"
        for a, b, f in plan.speed:
            assert f == plan_mod.SPEED and a >= 5.0 and b <= 15.0 and b - a >= plan_mod.SPEED_MIN_S
        assert all(not w.get("removed") for w in plan.words)  # no word is touched
        sp = [i for i in plan.fx.inserts if i.kind == "speed"]
        saved = sum((i.src_end - i.src) - i.dur for i in sp)
        assert saved > 1.0
        dest = tmp_path / "out.mp4"
        res = render_clip(proj, cand, opts, None, dest, spec=OutputSpec())
        assert res.info["fx"]["sped_up"] == pytest.approx(saved, abs=0.05)
        got = _probe(dest)
        assert got["video"] == pytest.approx(24.0 - saved, abs=0.12)
        assert got["audio"] == pytest.approx(24.0 - saved, abs=0.12)
        # off: nothing changes
        assert not plan_mod.build(proj, cand, ClipOptions.from_dict({"profanity": "off"}), fps=30).speed
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)


# ===================================================================== hook check + banner


def test_banner_takes_the_quote_or_the_first_sentence():
    from sharkyclips import hooks

    c = {"publish": {"titles": ['"CB\'YE GİDİYOR LAN" DEDİKTEN SONRA ÇOK GÜZEL PUSLUDUM! 🚨💀 (DELTA FORCE)'], "language": "tr"}}
    assert hooks.banner_text(c, "tr") == '"CB\'YE GİDİYOR LAN" 🚨💀'
    c = {"publish": {"titles": ["herkese bastık herkese! düğünden gelen görmez sanıklar 🚨😂"]}}
    assert hooks.banner_text(c, "tr") == "HERKESE BASTIK HERKESE! 🚨😂"  # Turkish capitals (İ / I right)
    c = {"publish": {"titles": [], "hook_text": "insane clutch"}, "llm": {"moment_type": "clutch"}}
    assert hooks.banner_text(c, "en") == "INSANE CLUTCH 🔥"
    long = {"publish": {"titles": ["a very long title that goes on and on without any stop at all here"]}}
    b = hooks.banner_text(long, "en")
    assert len(b) <= hooks.BANNER_MAX + 3 and not b.endswith(" A")  # cut at a word
    assert hooks.banner_text({"publish": {}}, "en") == ""


def test_banner_never_shows_a_swear():
    from sharkyclips import hooks

    c = {"publish": {"titles": ['"siktir git" dedi! 😂']}}
    assert "SİKTİR" not in hooks.banner_text(c, "tr")


@pytest.mark.requires_ffmpeg
def test_easy2_project_is_shaped_then_rendered_and_nudged():
    from sharkyclips import config, easy as E
    from sharkyclips.web import state
    from test_publishing import _client, _idle, _project, _wait

    from sharkyclips.web import app as A, easy as WE

    WE.install(A.jobs)  # what the server's startup does: the shape job's end queues the renders
    config.update(easy_banner=None, easy_speedup=None)
    project = _project("easy2-flow", 2)
    E.save(project, easy=True, v2=True)
    with _client() as c:
        v = c.post(f"/api/easy/projects/{project.id}/prepare").json()
        assert v["smart"] is True
        _wait(_idle, 300)
        v = c.get(f"/api/easy/projects/{project.id}").json()
        assert all(x["render"]["status"] == "ready" for x in v["clips"])
        sh = v["clips"][0]["shape"]
        assert sh["shaped"] and sh["target"]["kind"] in ("funny", "action") and "hook" in sh
        assert sh["banner"] == "HUGE PLAY 1"  # the title, in capitals
        clip = state.load_clips(project)["c01"]
        o = clip["options"]
        assert o["safe_zone"] == "shorts" and o["cuts"] == "light" and o["banner"] == "HUGE PLAY 1"
        assert o["speedup"] == "off"  # off until switched on
        before = (v["clips"][0]["start"], v["clips"][0]["end"])
        v = c.post(f"/api/easy/clips/{project.id}/c01/nudge", json={"action": "earlier"}).json()
        cl = next(x for x in v["clips"] if x["id"] == "c01")
        assert cl["start"] < before[0] and cl["end"] == before[1] and cl["shape"]["auto"] is False
        v = c.post(f"/api/easy/clips/{project.id}/c01/nudge", json={"action": "auto"}).json()
        cl = next(x for x in v["clips"] if x["id"] == "c01")
        assert (cl["start"], cl["end"]) == before and cl["shape"]["auto"] is True
        assert c.post(f"/api/easy/clips/{project.id}/c01/nudge", json={"action": "x"}).status_code == 400
        # own banner text, then none
        c.post(f"/api/easy/clips/{project.id}/c01/edit", json={"banner": "MY TEXT"})
        assert E.clip_prefs(E.load(project), "c01")["banner"] == "MY TEXT"
        c.post(f"/api/easy/clips/{project.id}/c01/edit", json={"banner": ""})
        v = c.get(f"/api/easy/projects/{project.id}").json()
        assert v["clips"][0]["shape"]["banner"] == ""
        _wait(_idle, 300)


def test_reason_chips_are_plain_and_strongest_first():
    cand = {"reasons": [{"code": "loudness_spike", "t": 1, "strength": 1.0, "count": 4},
                        {"code": "keyword", "value": "oha", "t": 2, "strength": 0.5},
                        {"code": "laughter", "t": 3, "strength": 0.8},
                        {"code": "lol_kill", "t": 4, "strength": 0.4},
                        {"code": "lol_pentakill", "t": 5, "strength": 1.0},
                        {"code": "chat_spike", "t": 6, "strength": 0.9}]}
    chips = shaping.reason_chips(cand)
    assert [c["code"] for c in chips] == ["lol_pentakill", "laughter", "chat_spike"]
    assert shaping.reason_chips(cand, 2)[1]["code"] == "laughter"
    df = {"reasons": [{"code": "df_kill", "t": 1, "strength": 0.5}, {"code": "df_multikill", "value": "3", "t": 2, "strength": 0.7},
                      {"code": "keyword", "value": "nasıl ya", "t": 3, "strength": 0.5}]}
    assert shaping.reason_chips(df) == [{"code": "df_multikill", "value": "3"}, {"code": "keyword", "value": "nasıl ya"}]
    assert shaping.reason_chips({}) == []
