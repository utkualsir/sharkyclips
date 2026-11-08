"""1.2.34 Easy mode 2.0: context guard, length targets, nudges, hook check, reasons, taste,
autopilot, phone preview, action tracking, caption fixes, weekly digest."""

from __future__ import annotations

import numpy as np

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
