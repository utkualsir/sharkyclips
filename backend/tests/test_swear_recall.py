"""1.2.21: swear detection with maximum recall - lexicon (stems + suffixes, letter variants,
censored output), the deep check (all audio, quiet voices boosted, voted passes, forced
alignment, bleep check), strictness levels, learning from manual bleeps, and the recall
regression on the labelled fixtures (text + times only). All models are mocked."""

from __future__ import annotations

import json
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import config
from sharkyclips.clips import ClipOptions
from sharkyclips.errors import SharkyClipsError
from sharkyclips.edit import plan, swear_eval, swearlearn, swearlex, swears
from sharkyclips.project import Project, write_json_atomic
from sharkyclips.voices import align, swearscan

FIXTURES = Path(__file__).parent / "data" / "swear_eval"
SR = 16000


# ------------------------------------------------------------------ lexicon

@pytest.mark.parametrize("word,lang,kind", [
    ("amına", "tr", "sure"), ("Amını,", "tr", "sure"), ("amk", "tr", "sure"), ("A.Q.", "tr", "sure"),
    ("siktir", "tr", "sure"), ("siiiiiktir", "tr", "sure"), ("s.i.k.t.i.r", "tr", "sure"),
    ("sikerler", "tr", "sure"), ("hassiktir", "tr", "sure"), ("orosbu", "tr", "sure"), ("oruspu", "tr", "sure"),
    ("piçlik", "tr", "sure"), ("yarrağı", "tr", "sure"), ("götünü", "tr", "sure"), ("amcık", "tr", "sure"),
    ("s**yim", "tr", "sure"), ("a***", "tr", "sure"), ("****", "tr", "sure"), ("f*ck", "en", "sure"),
    ("sıkeyim", "tr", "maybe"), ("amanak", "tr", "maybe"), ("got", "tr", "maybe"),
    ("FUUUCK", "en", "sure"), ("sh1t", "en", "sure"), ("motherfucker", "en", "sure"), ("dumbass", "en", "sure"),
    ("Scheiße", "de", "sure"), ("verfickt", "de", "sure"), ("bazdmeg", "hu", "sure"), ("kibaszott", "hu", "sure"),
    ("заебал", "ru", "sure"), ("сyка", "ru", "sure"), ("пиздец", "ru", "sure"),
    ("شرموطة", "ar", "sure"), ("كسمك", "ar", "sure"), ("卧槽", "zh", "sure"), ("我操你妈", "zh", "sure"), ("nmsl", "zh", "sure"),
])
def test_lexicon_finds_forms_variants_and_censored(word, lang, kind):
    got = swearlex.classify(word, lang, 0.6)
    assert got is not None and got[0] == kind, (word, got)


@pytest.mark.parametrize("word,lang", [
    ("sıkıntı", "tr"), ("sıktım", "tr"), ("sıkıyo", "tr"), ("götür", "tr"), ("götürdü", "tr"), ("amaç", "tr"),
    ("aman", "tr"), ("amca", "tr"), ("amin", "tr"), ("sikke", "tr"), ("yaram", "tr"), ("yaramaz", "tr"),
    ("sürekli", "tr"), ("piknik", "tr"), ("class", "en"), ("assassin", "en"), ("cockpit", "en"), ("Haus", "de"),
    ("szép", "hu"), ("ребята", "ru"), ("хлеб", "ru"), ("مرحبا", "ar"), ("你好", "zh"),
])
def test_lexicon_leaves_normal_words_alone(word, lang):
    assert swearlex.classify(word, lang, 0.4) is None, word


def test_turkish_phonetic_distance_is_sound_aware():
    assert swearlex.wdist("aminak", "amanak") < 1.0  # vowel swap: half a step
    assert swearlex.wdist("siktir", "sigdir") <= 1.0  # k/g, t/d pairs
    assert swearlex.wdist("siktir", "surekli", 1.5) > 1.5


# ------------------------------------------------------------------ strictness + learning

def test_strictness_levels():
    maybe = {"status": "maybe", "score": 0.45}
    weak = {"status": "maybe", "score": 0.1}
    assert not swears.bleeped(maybe, "normal") and swears.bleeped(maybe, "strict")
    assert not swears.bleeped(weak, "strict") and swears.bleeped(weak, "paranoid")
    assert swears.resolve_strictness("auto", True) == "strict" and swears.resolve_strictness("auto", False) == "normal"
    assert ClipOptions.from_dict({}).swear_strict == "auto"
    with pytest.raises(SharkyClipsError):
        ClipOptions.from_dict({"swear_strict": "nuclear"})


def test_learned_words_from_manual_bleeps_and_unbleeps():
    swearlearn.path().unlink(missing_ok=True)
    swearlearn.learn("tr", [{"word": "Hıyar!", "spk": "f1"}], "add")
    swearlearn.learn("tr", [{"word": "amanak", "spk": "me"}], "ignore")
    words = [{"start": 0, "end": 0.4, "word": "hıyar", "probability": 0.9},
             {"start": 0.5, "end": 0.9, "word": "amanak", "probability": 0.4}]
    got = {it["word"]: it for it in swears.detect(words, "tr")}
    assert got["hıyar"]["status"] == "sure" and got["hıyar"]["why"] == "learned"
    assert "amanak" not in got  # the user said: not a swear
    assert "hıyar" in swearlearn.hotwords("tr") and swearlearn.words("tr")["hıyar"]["spk"] == {"f1": 1}
    # a list word unbleeped twice drops to "maybe" (Strict still bleeps it, Normal doesn't)
    swearlearn.learn("tr", [{"word": "kahpe"}], "ignore")
    swearlearn.learn("tr", [{"word": "kahpe"}], "ignore")
    it = swears.detect([{"start": 0, "end": 0.4, "word": "kahpe", "probability": 0.9}], "tr")[0]
    assert it["status"] == "maybe" and swears.bleeped(it, "strict") and not swears.bleeped(it, "normal")
    swearlearn.remove("tr", "kahpe", "ignore")
    swearlearn.path().unlink(missing_ok=True)


def test_review_edits_teach_the_learned_list():
    swearlearn.path().unlink(missing_ok=True)
    d = config.workspace_dir() / "learn-proj"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": 30.0})
    write_json_atomic(d / "transcript.json", {"language": "tr", "segments": [{"start": 1, "end": 3, "words": [
        {"start": 1.0, "end": 1.4, "word": " yuh", "probability": 0.9},
        {"start": 1.5, "end": 1.9, "word": " dangalak", "probability": 0.8},
        {"start": 2.0, "end": 2.4, "word": " tamam", "probability": 0.9}]}]})
    proj = Project("learn-proj", d)
    n = swearlearn.from_edits(proj, {}, {"c01": {"bleep": [[1.48, 1.92]], "unbleep": [[2.0, 2.4]]}})
    assert n == 2
    assert "dangalak" in swearlearn.entries("tr") and "tamam" in swearlearn.ignored("tr")
    shutil.rmtree(d, ignore_errors=True)
    swearlearn.path().unlink(missing_ok=True)


# ------------------------------------------------------------------ voting

def _r(name, w, *words):
    return {"pass": name, "w": list(w), "words": [{"start": a, "end": b, "word": t, "p": p} for a, b, t, p in words]}


def test_votes_across_passes():
    base = [{"start": 1.0, "end": 1.3, "word": "abi", "p": 0.9}]
    readings = [
        _r("hint0", (0, 6), (2.0, 2.3, "siktir", 0.8), (4.0, 4.3, "siktir", 0.7)),
        _r("hint4", (0, 6), (2.0, 2.3, "siktir", 0.6)),
        _r("plain", (0, 6), (2.0, 2.3, "sigdir", 0.4), (4.0, 4.3, "sürekli", 0.9)),
        # an unprompted pass hears a short burst nobody else heard: sure (it's a list form)
        _r("plain", (3, 9), (7.0, 7.15, "aq", 0.7)),
    ]
    items = {round(it["start"], 1): it for it in swearscan.combine(base, readings, "tr", learned={})}
    assert items[2.0]["status"] == "maybe" and items[2.0]["score"] >= 0.6  # prompts + a sound-alike: bleep
    assert items[4.0]["score"] < items[2.0]["score"]  # only one prompt heard it, the plain pass heard "sürekli"
    assert not swears.bleeped(items[4.0], "normal")
    assert items[7.0]["status"] == "sure"
    # a prompt that made Whisper loop is ignored
    loop = [_r("hint0", (0, 6), (1.0, 1.3, "siktir", 0.9), (1.4, 1.7, "siktir", 0.9), (1.8, 2.1, "siktir", 0.9))]
    assert not swearscan.combine([], loop, "tr", learned={})


# ------------------------------------------------------------------ audio helpers

def _speechy(n, rng, amp):
    """Noise shaped like syllables (Silero may or may not call it speech: loudness decides)."""
    t = np.arange(n) / SR
    return (rng.standard_normal(n) * amp * (0.6 + 0.4 * np.sin(2 * np.pi * 5 * t))).astype(np.float32)


def test_speech_regions_keep_short_bursts_and_boost_quiet_voices():
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(SR * 6) * 0.001).astype(np.float32)
    x[SR * 1:SR * 2] += _speechy(SR, rng, 0.2)
    x[int(SR * 4.0):int(SR * 4.15)] += _speechy(int(SR * 0.15), rng, 0.02)  # a quiet 150 ms "aq"
    regs = swearscan.speech_regions(x, vad=False)
    assert any(a <= 1.05 and b >= 1.95 for a, b in regs)
    assert any(a <= 4.02 and b >= 4.12 for a, b in regs)
    y = swearscan.boost(x, regs)
    quiet = lambda z: float(np.sqrt(np.mean(z[int(SR * 4.0):int(SR * 4.15)] ** 2)))  # noqa: E731
    assert quiet(y) > 4 * quiet(x)
    assert np.abs(y).max() <= 1.0
    wins = swearscan.windows(regs, [4.07], 6.0)
    assert sum(1 for a, b in wins if a + swearscan.EDGE <= 1.5 <= b - swearscan.EDGE) >= 1
    assert sum(1 for a, b in wins if a <= 4.07 <= b) >= 2  # overlapping: never only at an edge


def test_viterbi_alignment_on_synthetic_emissions():
    # 30 frames, vocab {0 blank, 1 a, 2 b}: "a" at frames 5-8, "b" at 20-23
    lp = np.full((30, 3), np.log(0.02), np.float32)
    lp[:, 0] = np.log(0.96)
    lp[5:9] = np.log([0.02, 0.96, 0.02])
    lp[20:24] = np.log([0.02, 0.02, 0.96])
    path = align.viterbi(lp, [1, 2])
    a_frames = [t for t, li in enumerate(path) if li == 0]
    b_frames = [t for t, li in enumerate(path) if li == 1]
    assert min(a_frames) == 5 and max(a_frames) == 8 and min(b_frames) == 20 and max(b_frames) == 23
    assert align.viterbi(lp[:1], [1, 2]) is None  # too short


def test_letters_follow_turkish_case_rules():
    vocab = {"ı": 1, "i": 2, "a": 3, "s": 4, "ş": 5}
    assert align.letters("Iİ", "tr", vocab) == [1, 2]
    assert align.letters("aş", "tr", vocab) == [3, 5]
    assert align.letters("aş", "tr", {"a": 3, "s": 4}) == [3, 4]  # unknown accent -> base letter


def test_leak_check_sides():
    ws = [{"start": 1.0, "end": 1.08, "word": "si", "p": 0.5}, {"start": 1.5, "end": 1.9, "word": "git", "p": 0.9}]
    assert swearscan.leak("siktir", ws, 1.05, 1.45, "tr") == "left"
    assert swearscan.leak("siktir", [{"start": 1.4, "end": 1.5, "word": "tir", "p": 0.5}], 1.0, 1.42, "tr") == "right"
    assert swearscan.leak("siktir", [{"start": 1.1, "end": 1.4, "word": "siktir", "p": 0.9}], 1.0, 1.45, "tr") == "both"
    assert swearscan.leak("siktir", ws[1:], 1.0, 1.45, "tr") is None


# ------------------------------------------------------------------ the deep check (mocked)

def _tone_share(x):
    if len(x) < 64:
        return 0.0
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return float(spec[(f > 950) & (f < 1050)].sum() / (spec.sum() + 1e-12))


class FakeASR:
    """Hears the synthetic audio: a long burst = "siktir" (Whisper times 200 ms late at the
    start), a short burst = "aq", what's left next to a bleep tone = "si" / "tir"."""

    def __init__(self):
        self.calls = []

    def __call__(self, x, lang, prompt=None, temperature=0.0, hotwords=None):
        self.calls.append((len(x), bool(prompt), temperature))
        hop = int(SR * 0.01)
        k = len(x) // hop
        e = np.sqrt(np.mean(x[:k * hop].reshape(k, hop) ** 2, axis=1))
        loud = e > max(0.02, float(np.percentile(e, 50)) * 3)
        # a frame is bleep tone when 1 kHz dominates its 20 ms neighbourhood
        tonef = np.array([_tone_share(x[max(0, (f - 1) * hop):(f + 1) * hop]) > 0.3 for f in range(k)])
        on = loud & ~tonef
        words, i = [], 0
        while i < k:
            if not on[i]:
                i += 1
                continue
            j = i
            while j < k and on[j]:
                j += 1
            seg = x[i * hop:j * hop]
            a, b = i / 100, j / 100
            del seg
            if True:
                left_tone = i > 0 and bool(tonef[max(0, i - 3):i].any())
                right_tone = j < k and bool(tonef[j:j + 3].any())
                if b - a >= 0.3:
                    words.append({"start": a + 0.2, "end": b, "word": " siktir", "probability": 0.8})
                elif b - a >= 0.03 and right_tone:
                    words.append({"start": a, "end": b, "word": " si", "probability": 0.4})
                elif b - a >= 0.03 and left_tone:
                    words.append({"start": a, "end": b, "word": " tir", "probability": 0.4})
                elif b - a >= 0.08:
                    words.append({"start": a, "end": b, "word": " aq", "probability": 0.7})
            i = j
        return [{"start": 0, "end": len(x) / SR, "text": " ".join(w["word"] for w in words), "avg_logprob": -0.3,
                 "no_speech_prob": 0.1, "compression_ratio": 1.2, "words": words}]


def _wav(path, x):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def _scan_project(pid):
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    rng = np.random.default_rng(3)
    x = (rng.standard_normal(SR * 8) * 0.002).astype(np.float32)
    x[int(SR * 1.9):int(SR * 2.4)] += _speechy(int(SR * 0.5), rng, 0.25)  # "siktir" (missed by the transcript)
    x[int(SR * 5.0):int(SR * 5.15)] += _speechy(int(SR * 0.15), rng, 0.012)  # a quiet "aq" burst
    _wav(d / "source.wav", x)
    write_json_atomic(d / "meta.json", {"title": "T", "duration": 8.0, "mode": "gaming"})
    write_json_atomic(d / "highlights.json", {"mode": "gaming", "created_at": "x", "candidates": [
        {"rank": 1, "id": "c01", "start": 1.5, "end": 6.5, "duration": 5.0, "peak": 2.0, "hype_score": 80,
         "reasons": [], "signal_scores": {}, "text": "hi"}]})
    write_json_atomic(d / "transcript.json", {"language": "tr", "created_at": "t1", "segments": []})
    return Project(pid, d)


class FakeAligner:
    """Forced alignment: the real burst of "siktir" is 1.90-2.40 (Whisper says 2.10)."""

    def align(self, x, words, lang):
        hop = SR // 100
        e = np.sqrt(np.mean(x[:len(x) // hop * hop].reshape(-1, hop) ** 2, axis=1))
        on = np.flatnonzero(e > 0.05)
        span = align.Span(on[0] / 100, (on[-1] + 1) / 100, 0.6) if len(on) else None
        return [span if "siktir" in w else None for w in words]


@pytest.mark.requires_ffmpeg
def test_deep_check_finds_missed_swears_and_bleeps_them_completely():
    proj = _scan_project("scan-e2e")
    asr = FakeASR()
    judged = []

    def judge(batch, lang):
        judged.extend(batch)
        return {i: "yes" for i in range(len(batch))}

    data = swearscan.run_scan(proj, engines=swearscan.ScanEngines(asr=asr, aligner=None, judge=judge))
    items = data["items"]
    sik = next(it for it in items if it["word"] == "siktir")
    assert sik["status"] == "sure" and int(sik["votes"].split("/")[0]) >= 3
    aq = [it for it in items if it["word"] == "aq"]
    assert aq and aq[0]["status"] == "sure"  # 150 ms, quiet: still found
    # Whisper said 2.1 but the word starts at 1.9: the first bleep left "si" audible -> widened
    assert sik["leak_first"] == "left" and sik["leak"] is None and sik["bleep"][0] <= 1.9
    assert any(p for _n, p, _t in asr.calls) and any(not p for _n, p, _t in asr.calls)
    assert {t for _n, _p, t in asr.calls} >= {0.0, 0.4}
    # the render uses the checked range and Strict
    p = plan.build(proj, {"id": "c01", "start": 1.5, "end": 6.5}, ClipOptions.from_dict({"profanity": "bleep"}), fps=30)
    assert p.strictness == "strict"
    assert any(a <= 0.4 + 1e-6 and b >= 0.9 for a, b in p.bleeps)  # 1.9..2.4 in clip time
    assert sum(1 for a, b in p.bleeps if a <= 3.55 <= b) == 1  # the "aq" burst
    # with the aligner, the first bleep is already right
    data2 = swearscan.run_scan(proj, engines=swearscan.ScanEngines(asr=FakeASR(), aligner=FakeAligner()), judge=False)
    sik2 = next(it for it in data2["items"] if it["word"] == "siktir")
    assert sik2["aligned"] and sik2["leak_first"] is None and sik2["bleep"][0] <= 1.83
    shutil.rmtree(proj.dir, ignore_errors=True)


@pytest.mark.requires_ffmpeg
def test_verify_render_widens_a_bleep_that_was_still_heard(tmp_path):
    proj = _scan_project("scan-verify")
    rng = np.random.default_rng(5)
    out = (rng.standard_normal(SR * 5) * 0.002).astype(np.float32)
    out[int(SR * 0.4):int(SR * 0.9)] += _speechy(int(SR * 0.5), rng, 0.25)
    out = swearscan.bleep_into(out, 0.5, 0.9)  # the render's bleep started 100 ms late
    _wav(tmp_path / "clip.wav", out)
    write_json_atomic(proj.dir / "transcript.json", {"language": "tr", "created_at": "t1", "segments": [
        {"start": 2.0, "end": 2.4, "words": [{"start": 2.12, "end": 2.28, "word": " siktir", "probability": 0.9}]}]})
    opts = ClipOptions.from_dict({"profanity": "bleep", "swear_strict": "strict"})
    cand = {"id": "c01", "start": 1.5, "end": 6.5}
    got = swearscan.verify_render(proj, cand, opts, tmp_path / "clip.wav", asr=FakeASR())
    assert got and got[0][0] < 2.0
    p = plan.build(proj, cand, opts, fps=30)
    assert p.bleep_src[0][0] <= got[0][0] + 1e-6  # the next render uses the wider bleep
    shutil.rmtree(proj.dir, ignore_errors=True)


def test_merge_scan_maps_items_to_caption_words():
    words = [{"start": 1.0, "end": 1.4, "word": "abi"}, {"start": 1.5, "end": 1.9, "word": "sıkeyim", "probability": 0.3}]
    scanned = [{"start": 1.52, "end": 1.88, "word": "sikeyim", "status": "sure", "score": 1.0, "bleep": [1.44, 2.0],
                "votes": "3/4", "why": "scan:hint0+plain"}]
    items = plan.merge_scan(swears.detect(words, "tr", learned={}), scanned, words, "tr")
    assert len(items) == 1 and items[0]["i"] == 1 and items[0]["status"] == "sure" and items[0]["bleep_at"] == [1.44, 2.0]


# ------------------------------------------------------------------ recall regression (labelled fixtures)

def _fixtures():
    return sorted(FIXTURES.glob("*.json")) if FIXTURES.is_dir() else []


@pytest.mark.parametrize("path", _fixtures(), ids=lambda p: p.stem)
def test_recall_on_labelled_streams_does_not_drop(path):
    """Text + times of real streams (the user's Delta Force / LoL projects), labelled from a
    "find everything" run. Fails when detection loses recall (or gets much less precise)."""
    fx = json.loads(path.read_text(encoding="utf-8"))
    floors = fx["floors"]
    m = swear_eval.fixture_metrics(fx, "strict")
    assert m["recall"] >= floors["recall_strict"], m
    assert m["precision"] >= floors["precision_strict"], m
    n = swear_eval.fixture_metrics(fx, "normal")
    assert n["recall"] >= floors["recall_normal"], n
    p = swear_eval.fixture_metrics(fx, "paranoid")
    assert p["recall"] >= m["recall"] >= n["recall"]
