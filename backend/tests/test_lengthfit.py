"""1.2.35: the Easy mode length target follows the channel's own views."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from sharkyclips import config, lengthfit, shaping

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def no_saved_target():
    old = config.get("length_targets")
    config.update(length_targets={})
    yield
    config.update(length_targets=old)


def _row(duration, views, days=5, mode="gaming"):
    return {"duration": duration, "views": views, "at": NOW - timedelta(days=days), "mode": mode}


def test_not_enough_clips_learns_nothing():
    rows = [_row(35, 900), _row(33, 800), _row(40, 1000), _row(22, 100), _row(25, 120)]
    assert lengthfit.learn(rows, "gaming", NOW) is None  # 5 < MIN_SAMPLE


def test_the_best_length_band_is_learned():
    rows = [_row(35, 900), _row(33, 800), _row(40, 1000), _row(22, 100), _row(25, 120), _row(27, 90),
            _row(18, 150), _row(16, 110), _row(21, 130)]
    got = lengthfit.learn(rows, "gaming", NOW)
    assert got["min"] == 30 and got["max"] == 45 and got["source"] == "learned"
    assert got["n"] == 9 and got["band_n"] == 3 and got["ratio"] > 2
    assert lengthfit.band_name(got) == "30_45"
    # another mode's clips don't count, nor do clips still collecting views
    assert lengthfit.learn(rows, "study", NOW) is None
    young = [{**r, "at": NOW - timedelta(hours=10)} if r["duration"] >= 30 else r for r in rows]
    assert lengthfit.learn(young, "gaming", NOW) is None


def test_one_viral_clip_does_not_decide():
    rows = [_row(35, 20000), _row(33, 80), _row(40, 90), _row(22, 300), _row(25, 320), _row(27, 280),
            _row(18, 150), _row(16, 110), _row(21, 330)]
    assert lengthfit.learn(rows, "gaming", NOW) is None  # the 30-45 median is below the channel's


def test_generic_targets_without_channel_data(no_saved_target):
    funny = {"llm": {"moment_type": "funny", "funny": 8, "exciting": 4}}
    assert shaping.target("gaming", funny) == {"kind": "funny", "min": 18.0, "max": 28.0}


def test_saved_channel_target_is_used_until_enough_data(no_saved_target):
    config.update(length_targets={"gaming": {"min": 30, "max": 45, "ratio": 1.79}})
    lengthfit.clear_cache()
    funny = {"llm": {"moment_type": "funny", "funny": 8, "exciting": 4}}
    tgt = shaping.target("gaming", funny)
    assert (tgt["min"], tgt["max"], tgt["source"], tgt["kind"]) == (30.0, 45.0, "channel", "funny")
    assert shaping.target("study", {}).get("source") is None  # other modes keep the built-in one
    # a broken entry is ignored
    config.update(length_targets={"gaming": {"min": "x"}})
    lengthfit.clear_cache()
    assert shaping.target("gaming", funny)["max"] == 28.0


def test_a_new_target_reshapes_the_clip():
    cand = {"start": 10.0, "end": 30.0}
    shape = {"v": shaping.SHAPE_VERSION, "base": [10.0, 30.0], "target": {"kind": "action", "min": 20.0, "max": 35.0}}
    assert not shaping.needs_shape(shape, cand)
    assert not shaping.needs_shape(shape, cand, {"kind": "action", "min": 20.0, "max": 35.0})
    assert shaping.needs_shape(shape, cand, {"kind": "action", "min": 30.0, "max": 45.0, "source": "channel"})


def _talk(t0, t1):
    """A sentence every 4 s ("word word word word." each 0.6 s apart)."""
    out, t = [], t0
    while t < t1:
        for k in range(4):
            a = t + k * 0.8
            out.append({"start": round(a, 2), "end": round(a + 0.6, 2), "word": "end." if k == 3 else "word"})
        t += 4.0
    return out


def _ar(duration=200.0):
    words = _talk(0.0, duration)
    db = np.full(int(duration * 4), -30.0, np.float32)
    return shaping.Around(words, 0.0, db, None, -30.0, duration, "gaming", [])


def test_stretch_reaches_the_target_on_sentence_boundaries():
    ar = _ar()
    s, e = shaping.stretch(ar, 60.0, 78.2, 30.0, 0.0, 200.0, 60.0)
    assert 29.0 <= e - s <= 36.0
    assert s < 60.0 and e > 78.2
    starts = {w["start"] for w in ar.words}
    assert any(abs(s - (x - 0.2)) < 0.05 or abs(s - x) < 0.05 for x in starts)  # just before a word


def test_stretch_never_crosses_a_neighbour_or_the_limit():
    ar = _ar()
    s, e = shaping.stretch(ar, 60.0, 78.2, 30.0, 55.0, 80.0, 60.0)
    assert s >= 55.0 and e <= 80.0
    s, e = shaping.stretch(ar, 60.0, 78.2, 30.0, 0.0, 200.0, 22.0)
    assert e - s <= 22.0 + 0.01
    assert shaping.stretch(ar, 60.0, 92.0, 30.0, 0.0, 200.0, 60.0) == (60.0, 92.0)  # long enough


def test_digest_says_the_target_follows_the_winning_length(monkeypatch, no_saved_target):
    from sharkyclips import digest, youtube

    rows = [{"project_id": "p", "clip_id": f"c{i}", "title": "t", "url": None, "views": v, "likes": 0,
             "at": NOW - timedelta(days=3), "length": digest._length(d), "duration": d, "hook": "statement",
             "game": None, "private": False, "mode": "gaming"}
            for i, (d, v) in enumerate([(35, 900), (33, 800), (22, 100), (25, 120)])]
    monkeypatch.setattr(digest, "shorts", lambda now: rows)
    monkeypatch.setattr(youtube, "connected", lambda: True)
    d = digest.weekly(NOW)
    assert d["suggestion"]["code"] == "length" and d["length_target"] is None
    config.update(length_targets={"gaming": {"min": 30, "max": 45}})
    lengthfit.clear_cache()
    d = digest.weekly(NOW)
    assert d["suggestion"] == {"code": "length_auto", "value": "30_45", "ratio": d["suggestion"]["ratio"]}
    assert d["length_target"]["min"] == 30 and d["length_target"]["source"] == "channel"
