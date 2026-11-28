"""Phase D8 / 1.2.77: moments that aren't kills, chat reactions, smart pre-roll + clean ends,
spoken markers ("clip it"), card headlines, talk-stream profile, one-tap trims, the Light preset
translation."""

from __future__ import annotations

import json
import re
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import config, markers, shaping
from sharkyclips.highlights import candidates as C
from sharkyclips.highlights.context import AnalysisContext, Word
from sharkyclips.highlights.modes import TALK_WEIGHTS, detect_profile, get_mode, with_profile
from sharkyclips.highlights.signals.base import ReasonEvent, SignalResult
from sharkyclips.project import Project, write_json_atomic

SR = 16000
REPO = Path(__file__).resolve().parents[2]
LOCALES = REPO / "frontend" / "src" / "i18n" / "locales"
TRIGGERS = REPO / "backend" / "sharkyclips" / "highlights" / "triggers"
APP_LANGS = ("en", "tr", "de", "hu", "ru", "ar", "zh", "es", "fr", "pt", "ja")


@pytest.fixture(autouse=True)
def _clean():
    yield
    config.update(marker_phrases=None, marker_phrases_enabled=None)


@pytest.fixture(autouse=True)
def _no_leftover_projects():
    before = set(config.workspace_dir().iterdir())
    yield
    for d in set(config.workspace_dir().iterdir()) - before:
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


# ============================================================================ helpers


def _voice(f0: float, seconds: float, amp: float) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (amp * sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 6))).astype(np.float32)


def _talk(seconds: float, f0: float = 140.0, amp: float = 0.05, rng=None) -> np.ndarray:
    """Syllables: 0.25 s voiced, 0.1 s pause, the pitch moving a little like real speech."""
    rng = rng or np.random.default_rng(1)
    out, t = [], 0.0
    while t < seconds:
        out.append(_voice(f0 * 2 ** (rng.normal(0, 0.6) / 12), 0.25, amp))
        out.append(np.zeros(int(0.1 * SR), np.float32))
        t += 0.35
    return np.concatenate(out)[: int(seconds * SR)]


def _project(pid: str, audio: np.ndarray, words: list[tuple[float, float, str]], meta: dict | None = None,
             lang: str = "en") -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    dur = len(audio) / SR
    write_json_atomic(d / "meta.json", {"title": "T", "duration": dur, "mode": "gaming", **(meta or {})})
    noise = np.random.default_rng(2).normal(0, 0.0005, len(audio)).astype(np.float32)
    with wave.open(str(d / "audio.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(audio + noise, -1, 1) * 32767).astype("<i2").tobytes())
    ws = [{"start": a, "end": b, "word": f" {x}"} for a, b, x in words]
    write_json_atomic(d / "transcript.json", {"language": lang, "created_at": "x", "model": "test",
                                              "segments": [{"start": 0, "end": dur, "text": "", "words": ws}]})
    return Project(pid, d)


def _words_every(a: float, b: float, step: float = 0.6, text: str = "a", sentence_every: int = 0):
    out, t, i = [], a, 0
    while t + 0.3 < b:
        i += 1
        end_sentence = sentence_every and i % sentence_every == 0
        out.append((round(t, 2), round(t + 0.3, 2), text + ("." if end_sentence else "")))
        t += step
    return out


class _Hype:
    def __init__(self, curve, results=None, shares=None):
        self.smoothed = curve
        self.combined = curve
        self.results = results or {"loudness": SignalResult("loudness", curve, [])}
        self.shares = shares or {k: 1.0 / len(self.results) for k in self.results}


# ============================================================================ 1. voice signal


def test_pitch_tracker_finds_the_voice_pitch_without_octave_errors():
    from sharkyclips.highlights.signals.voice import frame_pitch

    for f in (85, 120, 150, 220, 320, 450, 600):
        f0, _r, _db = frame_pitch(_voice(f, 2.0, 0.2))
        assert abs(np.nanmedian(f0) - f) / f < 0.02, f
    f0, _, _ = frame_pitch(np.random.default_rng(0).normal(0, 0.05, SR * 2).astype(np.float32))
    assert np.isfinite(f0).mean() < 0.05  # noise is not a voice


def test_voice_signal_finds_a_scream_and_a_silence_broken_by_a_reaction():
    from sharkyclips.highlights.signals.voice import VoiceSignal

    quiet = np.zeros(SR * 12, np.float32)
    audio = np.concatenate([_talk(100), quiet, _voice(300, 2.0, 0.4), _talk(56),
                            _voice(560, 2.0, 0.5), _talk(68)])
    words = (_words_every(0, 100) + [(112.0, 113.8, "what!")] + _words_every(114.2, 169.5)
             + _words_every(172.5, 240))
    p = _project("d8-voice", audio, words)
    res = VoiceSignal().compute(AnalysisContext(p, get_mode("gaming")))
    codes = {(e.code, int(e.t)) for e in res.events}
    assert any(c == "silence_break" and 111 <= t <= 114 for c, t in codes), codes
    assert any(c == "scream" and 169 <= t <= 173 for c, t in codes), codes
    assert res.scores[112] >= 0.5 and res.scores[171] >= 0.9
    brk = next(e for e in res.events if e.code == "silence_break")
    assert brk.value == "12s"


def test_steady_talk_gives_no_false_alarms():
    from sharkyclips.highlights.signals.voice import VoiceSignal

    rng = np.random.default_rng(5)
    parts, words, t = [], [], 0.0
    while t < 300:  # talk with short pauses (< 8 s): never a "silence break"
        n = float(rng.uniform(5, 15))
        parts.append(_talk(n, rng=rng))
        words += _words_every(t, t + n)
        gap = float(rng.uniform(0.5, 4))
        parts.append(np.zeros(int(gap * SR), np.float32))
        t += n + gap
    p = _project("d8-steady", np.concatenate(parts), words)
    res = VoiceSignal().compute(AnalysisContext(p, get_mode("gaming")))
    assert not [e for e in res.events if e.code in ("scream", "silence_break")]
    assert float(res.scores.max()) < 0.45


# ============================================================================ 1. funny / fail lines


def test_keywords_find_funny_and_fail_lines_and_written_laughter():
    from sharkyclips.highlights.signals.keywords import KeywordSignal

    words = _words_every(0, 30) + [(31.0, 31.5, "Hahaha!"), (32, 32.3, "what"), (32.3, 32.5, "did"), (32.5, 32.6, "I"),
                                   (32.6, 32.8, "just"), (32.8, 33.0, "do?"), (40, 40.3, "no"), (40.3, 40.6, "way")]
    words += _words_every(41, 60)
    p = _project("d8-kw", np.zeros(SR * 60, np.float32), words)
    res = KeywordSignal().compute(AnalysisContext(p, get_mode("gaming")))
    got = {(e.code, e.value) for e in res.events}
    assert ("funny_line", "haha") in got and ("fail_line", "what did i just do") in got
    assert ("keyword", "no way") in got


def test_every_app_language_has_reaction_study_funny_and_fail_triggers():
    from sharkyclips.highlights.signals.keywords import LAUGH_TOKEN, normalize

    for lang in APP_LANGS:
        data = json.loads((TRIGGERS / f"{lang}.json").read_text(encoding="utf-8"))
        for cat in ("reaction", "study", "funny", "fail"):
            assert len(data.get(cat) or {}) >= 6, (lang, cat)
    for laugh in ("hahaha", "Ahahah", "hehe", "jajaja", "хахаха", "ههههه"):
        assert LAUGH_TOKEN.match(normalize(laugh)), laugh
    for word in ("aha", "hello", "ohio", "haha" * 0 + "ha", "jaguar"):
        assert not LAUGH_TOKEN.match(normalize(word)), word


def test_gaming_uses_the_new_signals_and_categories():
    g = get_mode("gaming")
    assert g.weights.get("voice") and {"reaction", "funny", "fail"} <= set(g.keyword_categories)


# ============================================================================ 2. chat


def test_chat_reactions_cover_goal_spam_laughs_and_new_emotes():
    from sharkyclips.highlights.signals.chat import is_reaction

    for m in ("GOOOOL", "gol", "goal", "ahaha", "KEKW KEKW", "ICANT", "jajaja", "kkkkk", "mdr", "www", "草",
              "ㅋㅋㅋ", "OMEGALUL", "LUL"):
        assert is_reaction(m), m
    for m in ("gl", "golf", "hello there", "what", "goals for today"):
        assert not is_reaction(m), m


# ============================================================================ 4. spoken markers


def _w(items):
    return [Word(a, b, f" {t}") for a, b, t in items]


def test_find_spoken_markers_default_phrases_variants_and_settings():
    words = _w([(10, 10.4, "that"), (10.4, 10.8, "was"), (10.8, 11.2, "great."), (12.0, 12.3, "Clip"),
                (12.3, 12.6, "it."), (13.0, 13.4, "okay"), (80.0, 80.5, "Klipal!"), (200, 200.4, "clip"),
                (205, 205.4, "it")])
    got = markers.find_spoken(words)
    assert [(m["t"], m["by"]) for m in got] == [(12.0, "clip it"), (80.0, "klip al")]  # "clip ... it" 5 s apart: no
    assert all(m["source"] == "voice" for m in got) and got[0]["end"] == 12.6
    config.update(marker_phrases=["bunu kes"])
    assert markers.find_spoken(_w([(5, 5.3, "Bunu"), (5.3, 5.6, "kes!")]))[0]["by"] == "bunu kes"
    assert markers.find_spoken(words) == []
    config.update(marker_phrases_enabled=False)
    assert markers.marker_phrases() == [] and markers.marker_phrases(even_if_off=True) == ["bunu kes"]


def test_spoken_marker_always_becomes_a_clip_that_ends_before_the_phrase():
    words = _words_every(0, 299.5, 1.0, "a", sentence_every=4) + [(300.0, 300.3, "clip"), (300.3, 300.6, "it.")]
    words += _words_every(301, 600, 1.0, "b", sentence_every=4)
    p = _project("d8-said", np.zeros(SR * 600, np.float32), words)
    ctx = AnalysisContext(p, get_mode("gaming"))
    curve = np.zeros(600)
    curve[100] = 1.0  # a loud moment elsewhere is the top of the hype curve
    cands = C.pick_candidates(ctx, _Hype(curve), top=3)
    said = [c for c in cands if c.marker is not None]
    assert len(said) == 1 and cands[0] is said[0]  # marked moments come first, always
    c = said[0]
    assert c.marker["source"] == "voice" and c.end <= 300.0 - 0.1 and c.start <= 300 - 15
    assert c.headline == {"code": "said", "value": "clip it"}
    assert any(x.marker is None and x.start <= 100 <= x.end for x in cands)


# ============================================================================ 3. context


def test_smart_pre_roll_starts_where_the_build_up_began():
    words = _words_every(0, 400, 1.0, "a", sentence_every=3)
    p = _project("d8-pre", np.zeros(SR * 400, np.float32), words)
    ctx = AnalysisContext(p, get_mode("gaming"))
    curve = np.full(400, 0.05)
    curve[182:200] = np.linspace(0.35, 0.9, 18)  # the fight starts at 182 and builds up
    curve[200] = 1.0
    curve[201:205] = 0.6
    c = C.pick_candidates(ctx, _Hype(curve), top=1)[0]
    assert 200 - 22 - 1.5 <= c.start <= 181.0  # the setup is in (the old 6-10 s pre-roll started at ~191)
    assert c.end >= 205


def test_a_laugh_that_is_still_going_is_not_cut():
    words = _words_every(0, 400, 1.0, "a", sentence_every=3)
    p = _project("d8-tail", np.zeros(SR * 400, np.float32), words)
    ctx = AnalysisContext(p, get_mode("gaming"))
    curve = np.full(400, 0.05)
    curve[198:203] = [0.6, 0.9, 1.0, 0.9, 0.6]
    laugh = np.zeros(400)
    laugh[200:214] = 0.9  # 14 s of laughing after the moment
    hype = _Hype(curve, {"loudness": SignalResult("loudness", curve, []),
                         "laughter": SignalResult("laughter", laugh, [ReasonEvent(201, "laughter", None, 0.9)])})
    c = C.pick_candidates(ctx, hype, top=1)[0]
    assert c.end >= 213.5 and c.headline == {"code": "big_laugh"}


def test_clean_sentence_end_never_stops_mid_sentence():
    ws = _w([(10, 10.3, "we"), (10.3, 10.6, "won."), (11.5, 11.8, "and"), (11.8, 12.1, "then"), (12.1, 12.4, "he"),
             (12.4, 12.7, "said"), (12.7, 13.0, "it."), (15, 15.3, "next")])
    starts = np.array([w.start for w in ws])
    # an end on "then" (mid-sentence): back to the last finished sentence ("won.") ...
    assert C.clean_sentence_end(ws, starts, 0.0, 12.15, 10.0, 60, 4) == pytest.approx(10.95)
    # ... unless that would cut the payoff: then forward to the end of this sentence ("it.")
    assert C.clean_sentence_end(ws, starts, 0.0, 12.15, 11.6, 60, 4) == pytest.approx(13.35)
    # a clean end stays
    assert C.clean_sentence_end(ws, starts, 0.0, 10.95, 10.0, 60, 4) == 10.95


def test_sentences_back_takes_the_setup_line_of_a_joke():
    words = [(0, 0.3, "intro."), (6, 6.3, "So"), (6.3, 6.6, "my"), (6.6, 6.9, "dog."), (7.5, 7.8, "It"),
             (7.8, 8.1, "barked."), (8.8, 9.1, "Then"), (9.1, 9.4, "it"), (9.4, 9.7, "fell!"), (10, 10.3, "haha")]
    p = _project("d8-setup", np.zeros(SR * 30, np.float32), words)
    ctx = AnalysisContext(p, with_profile(get_mode("gaming"), "talk"))
    assert C.sentences_back(ctx, 8.6, 2, 0.0) == pytest.approx(5.8)  # "So my dog." + "It barked."
    assert C.sentences_back(ctx, 8.6, 2, 7.0) == pytest.approx(7.3)  # not before `earliest`
    assert C.sentences_back(ctx, 5.8, 2, 0.0) == pytest.approx(5.8)  # a 5 s pause before: a new topic


# ============================================================================ headline


def _cand(reasons, marker=None):
    c = C.Candidate(peak=10, start=0, end=20, raw=1, raw_unsmoothed=1, marker=marker)
    c.reasons = [{"code": code, "strength": s, **({"value": v} if v else {})} for code, s, v in reasons]
    return c


def test_headline_priorities():
    h = C.headline
    assert h(_cand([("laughter", 1, None)], marker={"source": "hotkey"})) == {"code": "marked"}
    assert h(_cand([], marker={"source": "voice", "by": "klip al"})) == {"code": "said", "value": "klip al"}
    assert h(_cand([("loudness_spike", 1, None), ("keyword", 0.9, "clutch")])) == {"code": "clutch"}
    assert h(_cand([("lol_baron_steal", 1, None)])) == {"code": "clutch"}
    assert h(_cand([("chat_spike", 0.9, "5x"), ("lol_quadrakill", 1, "Yasuo")])) == {"code": "game",
                                                                                      "value": "lol_quadrakill"}
    assert h(_cand([("df_multikill", 1, "4")])) == {"code": "game", "value": "df_multikill", "n": "4"}
    assert h(_cand([("chat_spike", 0.8, "6x"), ("loudness_spike", 0.9, None)])) == {"code": "chat_wild"}
    assert h(_cand([("chat_spike", 0.3, "2x"), ("laughter", 0.7, None)])) == {"code": "big_laugh"}
    assert h(_cand([("silence_break", 0.9, "12s"), ("fail_line", 0.6, "oops")])) == {"code": "fail"}
    assert h(_cand([("silence_break", 0.9, "12s"), ("loudness_spike", 1, None)])) == {"code": "out_of_nowhere"}
    assert h(_cand([("loudness_spike", 1, None)])) == {"code": "big_reaction"}
    assert h(_cand([])) is None


def test_every_headline_and_new_reason_has_a_text_in_every_language():
    codes = set(C.HEADLINE_OF.values()) | {"clutch", "marked", "said"}
    reasons = {"scream", "voice_excited", "silence_break", "funny_line", "fail_line"}
    for lang in APP_LANGS:
        src = (LOCALES / f"{lang}.ts").read_text(encoding="utf-8")
        keys = set(re.findall(r'^\s*"([^"]+)":', src, re.M))
        assert {f"headline.{c}" for c in codes} <= keys, (lang, {f"headline.{c}" for c in codes} - keys)
        assert {f"reason.{r}" for r in reasons} <= keys, lang
        assert {"easy2.start_later", "easy2.end_sooner", "mark.phrases"} <= keys, lang


# ============================================================================ talk profile


def test_talk_profile_from_the_stream_category_or_title():
    assert detect_profile({"source": {"category": "Just Chatting"}})[0] == "talk"
    assert detect_profile({"title": "IRL walk in Tokyo"})[0] == "talk"
    assert detect_profile({"title": "sohbet ediyoruz"})[0] == "talk"
    assert detect_profile({"title": "雑談配信"})[0] == "talk"
    assert detect_profile({"title": "girl talk"})[0] == "game"  # "irl" inside a word doesn't count
    assert detect_profile({"title": "Just Chatting"}, game="lol")[0] == "game"  # a recognised game wins
    assert detect_profile({"title": "ranked games", "profile": "talk"})[0] == "talk"  # your choice wins
    talk = with_profile(get_mode("gaming"), "talk")
    assert talk.weights == TALK_WEIGHTS and "game" not in talk.weights and talk.pre_roll[1] > 10
    assert with_profile(get_mode("study"), "talk") is get_mode("study")


def test_highlights_json_records_the_profile_and_headlines():
    from sharkyclips.highlights.pipeline import run_highlights

    audio = np.concatenate([_talk(100), np.zeros(SR * 12, np.float32), _voice(300, 2.0, 0.4), _talk(130)])
    words = _words_every(0, 100, sentence_every=5) + [(112.0, 113.8, "what!")] + _words_every(114.2, 244, sentence_every=5)
    p = _project("d8-talkrun", audio, words, meta={"source": {"category": "Just Chatting"}})
    res = run_highlights(p, fetch_chat=False)
    assert res["profile"]["name"] == "talk" and "voice" in res["settings"]["weights"]
    assert res["signals"]["voice"]["status"] == "ok"
    assert any(c.get("headline") for c in res["candidates"])
    assert any(r["code"] == "silence_break" for c in res["candidates"] for r in c["reasons"])


# ============================================================================ one-tap trims (Easy)


SENT = [(10.0, 10.3, "so"), (10.35, 10.5, "I"), (10.55, 10.8, "go"), (10.85, 11.0, "in"), (11.05, 11.8, "there."),
        (12.0, 12.4, "and"), (12.45, 13.0, "then"), (13.05, 14.0, "wait"), (14.1, 14.5, "boom"), (14.55, 15.0, "he's"),
        (15.05, 15.5, "dead!"), (30.0, 30.5, "okay."), (31.0, 31.4, "nice"), (31.5, 32.0, "one"), (32.05, 32.6, "right")]


def _around(events=None):
    ws = [{"start": a, "end": b, "word": f" {w}"} for a, b, w in SENT]
    db = np.full(800, -30.0, np.float32)
    return shaping.Around(ws, 0.0, db, None, float(np.median(db)), 200.0, "gaming", events or [])


def test_easy_nudges_start_later_and_end_sooner_on_word_edges():
    tgt = {"kind": "action", "min": 15, "max": 45}
    ar = _around()
    s, e = shaping.nudge(ar, {}, 9.9, 32.9, "start_later", tgt, 0.0, 200.0)
    assert e == 32.9 and 12.0 <= s <= 13.1 and s > 9.9  # ~3 s later, just before a word
    assert not any(w[0] < s < w[1] for w in SENT)  # never inside a word
    s, e = shaping.nudge(ar, {}, 9.9, 32.9, "end_sooner", tgt, 0.0, 200.0)
    assert s == 9.9 and 29.5 <= e <= 31.0
    assert not any(w[0] < e < w[1] for w in SENT)
    # never into the big moment: the kill at 14.2 keeps its 2.5 s lead-in
    ar = _around(events=[{"t": 14.2, "code": "df_kill"}])
    s, _ = shaping.nudge(ar, {}, 9.9, 32.9, "start_later", tgt, 0.0, 200.0)
    assert s <= 14.2 - 2.5 + 0.3
    assert "start_later" in shaping.NUDGES and "end_sooner" in shaping.NUDGES


# ============================================================================ settings API


def test_marker_phrases_setting_api():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app
    from sharkyclips.web.live import service

    client = TestClient(app)
    try:
        v = client.get("/api/live").json()["markers"]
        assert v["phrases"] == ["clip it", "klip al"] and v["phrases_enabled"] is True
        v = client.put("/api/live/markers", json={"phrases": " Clip it,  bunu kes , clip IT,"}).json()["markers"]
        assert v["phrases"] == ["Clip it", "bunu kes"]
        assert client.put("/api/live/markers", json={"phrases": "this phrase has far too many words"}).status_code == 400
        v = client.put("/api/live/markers", json={"phrases_enabled": False}).json()["markers"]
        assert v["phrases_enabled"] is False and v["phrases"] == ["Clip it", "bunu kes"]
        assert markers.marker_phrases() == []
    finally:
        service().reconfigure()


# ============================================================================ translation fix


def test_light_performance_preset_is_never_the_colour_light():
    """Hungarian / Russian (and es / fr / pt in a few texts) said the colour "light" for the
    Light preset (fewer, smaller models). The preset is about weight / speed."""
    colour = {"hu": "Világos", "ru": "Светл", "es": "claro", "fr": "clair", "pt": "claro", "ja": "ライト"}
    for lang in APP_LANGS:
        src = (LOCALES / f"{lang}.ts").read_text(encoding="utf-8")
        val = dict(re.findall(r'^\s*"([^"]+)":\s*"((?:[^"\\]|\\.)*)"', src, re.M))
        light = val["perf.preset.light"]
        if lang != "en":
            assert light != val["theme.light"], lang
        for k, v in val.items():
            if (k.startswith("perf.") and "light" in k) or k in ("perf.preset_desc",):
                if lang in colour:
                    assert colour[lang].casefold() not in v.casefold(), (lang, k, v)
