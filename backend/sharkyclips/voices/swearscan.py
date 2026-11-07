"""Deep swear check (1.2.21): recall first - almost no swear gets through.

The normal transcript is one Whisper pass with VAD: short bursts ("aq!"), quiet friends and
words at chunk edges are often lost, and Whisper mishears or censors swears. This check
listens to every clip range again:

1. All audio, not only VAD speech: a low-threshold VAD on the separated voices plus loudness
   bursts down to 100 ms; overlapping windows (6 s, hop 3 s) so no word sits only at an edge.
2. Quiet voices boosted first (per speaker where the voice pass knows who speaks, per burst
   otherwise).
3. Several decoding passes with the full Whisper large-v3 (beam search): the swear words of the
   language (+ the user's learned words) as initial prompt at temperatures 0 and 0.4, and one
   pass without any prompt (it keeps the prompted ones honest). Hits are voted over passes.
4. Every hit goes through the lexicon (edit/swearlex.py: stems + suffixes, letter variants,
   censored output, phonetic near-misses), borderline ones through the local AI with context.
5. Exact times by forced alignment (voices/align.py), padded (~80 ms before, ~120 ms after),
   then a bleep check: the bleep is mixed in and the region transcribed again; if any part of
   the swear is still heard the bleep widens (up to 3 rounds).

Result: <project>/swearscan.json, read by edit/plan.py (swear_review) for every render.
Engines are injectable (tests mock Whisper, the aligner and the LLM).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .. import governor
from ..edit import swearlex, swears
from ..edit.words import token
from ..errors import SharkyClipsError
from ..project import Project, read_json, write_json_atomic
from . import engines as E
from . import tracks

VERSION = 1
WIN, HOP = 6.0, 3.0
EDGE = 0.4  # a word this close to a window edge doesn't count for that window
MIN_BURST = 0.1
MAX_WINDOWS = 400
PRE, POST = 0.08, 0.12  # bleep padding around an aligned word
PRE_RAW, POST_RAW = 0.14, 0.2  # around Whisper's own times (not aligned)
MERGE_GAP = 0.15
MAX_WIDEN = 0.35
JUDGE_LO, JUDGE_HI = 0.3, 0.8

# pass name -> (prompted, temperature, weight in the vote)
PASSES = {"hint0": (True, 0.0, 0.8), "hint4": (True, 0.4, 0.6), "plain": (False, 0.0, 1.2)}
BASE_WEIGHT = 1.0
UNBIASED = ("base", "plain", "mix")

# Initial prompts: a natural line full of the language's swears (Whisper copies the style
# of the prompt, so it writes swears out instead of censoring or "cleaning" them).
PROMPTS = {
    "tr": "Lan amına koyayım, siktir git! Orospu çocuğu, sikeyim, piç, yarrak, göt, amk, aq, amcık, kahpe.",
    "en": "Fuck, fucking shit, motherfucker, bitch, asshole, dick, bullshit, damn.",
    "de": "Scheiße, verdammt, fick dich, Arschloch, Hurensohn, Wichser, Fotze.",
    "hu": "Kurva anyád, bazdmeg, baszd meg, geci, fasz, picsába, kibaszott.",
    "ru": "Блять, сука, нахуй, пиздец, ебать, хуй, мудак, пидор.",
    "ar": "كس امك، شرموطة، منيوك، يلعن، ابن الكلب، زب، طيز.",
    "zh": "我操，卧槽，他妈的，傻逼，操你妈，妈的，鸡巴。",
}

ProgressFn = Callable[[str, float], None]


@dataclass
class ScanEngines:
    asr: Callable[..., list[dict]] | None = None  # (x16, lang, prompt, temperature, hotwords) -> segments
    aligner: Any = None  # .align(x16, words, lang) -> [Span | None]
    separator: Any = None  # x44 (2, n) -> vocals 16 kHz
    judge: Callable[[list[dict], str | None], dict[int, str]] | None = None  # LLM: {idx: yes|no|unsure}
    release: Callable[[], None] | None = None


def scan_path(project: Project) -> Path:
    return project.dir / "swearscan.json"


def load(project: Project) -> dict | None:
    p = scan_path(project)
    if not p.is_file():
        return None
    try:
        data = read_json(p)
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) and data.get("version") == VERSION else None


def prompt_for(lang: str | None, learned: list[str] | None = None) -> str | None:
    base = PROMPTS.get(lang or "")
    if not base:
        return None
    extra = [w for w in (learned or []) if w and w.lower() not in base.lower()][:12]
    return base + (" " + ", ".join(extra) + "." if extra else "")


# ------------------------------------------------------------------------------ audio

def speech_regions(x: np.ndarray, vad: bool = True) -> list[tuple[float, float]]:
    """Everything that could be a voice: a low-threshold Silero VAD (short bursts kept) plus
    loudness bursts >= 100 ms above the noise floor. Seconds from x's start, merged."""
    out: list[tuple[float, float]] = []
    if vad and len(x) > E.SR // 4:
        try:
            from faster_whisper.vad import VadOptions, get_speech_timestamps

            opts = VadOptions(threshold=0.2, neg_threshold=0.1, min_speech_duration_ms=80,
                              min_silence_duration_ms=150, speech_pad_ms=120)
            for r in get_speech_timestamps(np.asarray(x, np.float32), opts):
                out.append((r["start"] / E.SR, r["end"] / E.SR))
        except Exception:  # noqa: BLE001 - VAD missing: loudness only
            pass
    hop = 0.02
    db = E.frame_db(x, hop)
    if len(db):
        floor = float(np.percentile(db, 20))
        on = db > max(floor + 6.0, -58.0)
        start = None
        for i, v in enumerate(list(on) + [False]):
            if v and start is None:
                start = i
            elif not v and start is not None:
                if (i - start) * hop >= MIN_BURST:
                    out.append((max(0.0, start * hop - 0.08), i * hop + 0.08))
                start = None
    out.sort()
    merged: list[list[float]] = []
    for a, b in out:
        if merged and a <= merged[-1][1] + 0.25:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    dur = len(x) / E.SR
    return [(round(a, 3), round(min(b, dur), 3)) for a, b in merged if min(b, dur) > a]


def boost(x: np.ndarray, regions: list[tuple[float, float]], spans: dict[str, list[tuple[float, float]]] | None = None,
          target_db: float = -20.0, max_gain_db: float = 24.0) -> np.ndarray:
    """Quiet voices up: one gain per speaker (spans: {spk: [(s, e)...]} seconds from x's start)
    where known, then every region that is still quiet levelled on its own. Smooth (20 ms
    ramps), peaks limited."""
    y = np.asarray(x, np.float32).copy()
    if len(y) == 0:
        return y

    def rms_db(seg: np.ndarray) -> float:
        return 10 * np.log10(float(np.mean(seg.astype(np.float64) ** 2)) + 1e-12)

    gain = np.ones(len(y), np.float32)
    ramp = int(0.02 * E.SR)

    def apply(a: float, b: float, g_db: float) -> None:
        i0, i1 = max(0, int(a * E.SR)), min(len(y), int(b * E.SR))
        if i1 - i0 < 2:
            return
        g = np.full(i1 - i0, 10 ** (g_db / 20), np.float32)
        r = min(ramp, (i1 - i0) // 2)
        if r:
            up = np.linspace(1.0, g[0], r, dtype=np.float32)
            g[:r], g[-r:] = up, up[::-1]
        gain[i0:i1] = np.maximum(gain[i0:i1], g)

    for ss in (spans or {}).values():
        segs = [y[int(a * E.SR):int(b * E.SR)] for a, b in ss if b > a]
        segs = [s for s in segs if len(s) > E.SR // 20]
        if not segs:
            continue
        g = float(np.clip(target_db - rms_db(np.concatenate(segs)), 0.0, max_gain_db))
        for a, b in ss:
            apply(a - 0.1, b + 0.1, g)
    y = y * gain
    for a, b in regions:
        seg = y[int(a * E.SR):int(b * E.SR)]
        if len(seg) < E.SR // 20:
            continue
        lvl = rms_db(seg)
        if lvl < target_db - 6:
            g = float(np.clip(target_db - 3 - lvl, 0.0, max_gain_db))
            i0, i1 = int(a * E.SR), int(b * E.SR)
            y[i0:i1] = y[i0:i1] * (10 ** (g / 20))
    peak = float(np.abs(y).max())
    if peak > 0.98:  # soft limit only the loud peaks
        y = np.tanh(y / 0.98 * 1.1) * 0.98 / np.tanh(1.1)
    return y.astype(np.float32)


def windows(regions: list[tuple[float, float]], centers: list[float], dur: float) -> list[tuple[float, float]]:
    """Overlapping windows over the speech (each word lands in two, away from the edges)
    plus one centred window per point of interest (unsure / swear words of the transcript)."""
    out: list[tuple[float, float]] = []
    spans: list[list[float]] = []
    for a, b in regions:  # speech close together -> one span
        if spans and a - spans[-1][1] < 1.0:
            spans[-1][1] = b
        else:
            spans.append([a, b])
    for a, b in spans:
        a = max(0.0, a - 0.5)
        b = min(dur, b + 0.5)
        if b - a <= WIN:
            mid = (a + b) / 2
            out.append((max(0.0, mid - WIN / 2), min(dur, mid + WIN / 2)))
            if b - a > WIN / 2:  # two overlapping windows still
                out.append((max(0.0, a - HOP / 2), min(dur, a - HOP / 2 + WIN)))
            continue
        t = a
        while t < b:
            out.append((t, min(dur, t + WIN)))
            if t + WIN >= b:
                break
            t += HOP
    for c in centers:
        out.append((max(0.0, c - WIN / 2), min(dur, c + WIN / 2)))
    out = sorted({(round(a, 2), round(b, 2)) for a, b in out if b - a >= 0.3})
    return out


def bleep_into(x: np.ndarray, a: float, b: float, offset: float = 0.0) -> np.ndarray:
    """The render's bleep (1 kHz, 3 dB under the voice, 12 ms fades) mixed into x (16 kHz)."""
    y = np.asarray(x, np.float32).copy()
    i0, i1 = max(0, int((a - offset) * E.SR)), min(len(y), int((b - offset) * E.SR))
    if i1 - i0 < 2:
        return y
    seg = y[i0:i1]
    ctx = y[max(0, i0 - int(0.6 * E.SR)):min(len(y), i1 + int(0.6 * E.SR))]
    rms = max(float(np.sqrt(np.mean(seg ** 2) + 1e-12)), float(np.percentile(np.abs(ctx), 90)) * 0.6)
    target = min(0.25, max(0.02, rms * 0.71))
    tt = np.arange(i1 - i0) / E.SR
    tone = np.sin(2 * np.pi * 1000.0 * tt).astype(np.float32) * np.sqrt(2) * target
    env = np.ones(i1 - i0, np.float32)
    r = min(int(0.012 * E.SR), (i1 - i0) // 2)
    if r:
        c = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, r))).astype(np.float32)
        env[:r], env[-r:] = c, c[::-1]
    y[i0:i1] = seg * (1 - env) + tone * env
    return y


# ------------------------------------------------------------------------------ words

def words_of(segs: list[dict], offset: float, lo: float, hi: float) -> list[dict]:
    """Segments of one window -> absolute words. Unlike the voice pass, garbage segments stay
    (recall first) but obvious outro hallucinations go."""
    from .pipeline import HALLUCINATIONS

    out = []
    for s in segs:
        if HALLUCINATIONS.search(s.get("text", "")):
            continue
        for w in s.get("words", []):
            a, b = offset + float(w["start"]), offset + float(w["end"])
            if not str(w["word"]).strip() or b < lo or a > hi:
                continue
            out.append({"start": round(a, 3), "end": round(max(b, a + 0.05), 3), "word": str(w["word"]).strip(),
                        "p": round(float(w.get("probability", 0.0)), 3)})
    return out


def _detect(ws: list[dict], lang: str | None, learned: dict | None) -> list[dict]:
    if not ws:
        return []
    return swears.detect(ws, lang, entries=None, learned=learned)


def prompt_tokens(lang: str | None, learned: list[str] | None = None) -> set[str]:
    """The words of the swear prompt (as tokens): Whisper sometimes reads the prompt back on
    silence or music ("Orospu çocuğu, sikeyim, piç, yarrak, göt...")."""
    text = PROMPTS.get(lang or "", "") + " " + " ".join(learned or [])
    return {t for t in (token(w, lang) for w in text.replace(",", " ").split()) if t}


def strip_echo(words: list[dict], lang: str | None, ptoks: set[str], run: int = 3) -> list[dict]:
    """Drop prompt echoes: 3+ prompt words in a row (and lone prompt words right next to such
    a run). Real speech rarely strings three list swears together; a read-back prompt does."""
    if not words or not ptoks:
        return words
    flag = [token(w["word"], lang) in ptoks for w in words]
    drop = [False] * len(words)
    i = 0
    while i < len(words):
        if not flag[i]:
            i += 1
            continue
        j = i
        while j < len(words) and flag[j] and (j == i or words[j]["start"] - words[j - 1]["end"] < 0.8):
            j += 1
        if j - i >= run:
            for k in range(i, j):
                drop[k] = True
            for k in (i - 1, j):  # a prompt word glued to the run ("çocuğu")
                if 0 <= k < len(words) and flag[k]:
                    drop[k] = True
        i = max(j, i + 1)
    return [w for w, d in zip(words, drop) if not d]


def combine(base: list[dict], readings: list[dict], lang: str | None, learned: dict | None = None,
            find_all: bool = False) -> list[dict]:
    """Vote the hits of every reading. base: the clip words (main transcript / voice pass,
    absolute times, "p"). readings: [{"pass", "w": [s, e], "words": [...]}].
    Returns items {"start", "end", "word", "heard": [...], "spk", "status", "score", "why",
    "votes": "k/n", "src": [...]} sorted by time.

    Unprompted readings (the main transcript, the plain pass, the plain mix) are honest: a
    swear form there is sure. A swear heard only with the swear prompt is a "maybe" whose
    score grows with the share of prompted passes that heard it and with an unprompted pass
    hearing something that sounds like it (e.g. "sigdir" for "siktir")."""
    ptoks = prompt_tokens(lang, list((learned or {}).get("add") or []))
    hits: list[dict] = []
    for it in _detect(base, lang, learned):
        hits.append({**it, "src": "base", "w": None})
    clean: list[dict] = []
    for r in readings:
        prompted = PASSES.get(r["pass"], (False,))[0]
        ws = strip_echo(r["words"], lang, ptoks) if prompted else r["words"]
        found = _detect(ws, lang, learned)
        if prompted:
            toks = [token(h["word"], lang) for h in found if h["status"] == "sure"]
            if toks and max(toks.count(t) for t in toks) >= 3:
                found = []  # "siktir, siktir, siktir": the prompt made Whisper loop
        clean.append({**r, "words": ws})
        for it in found:
            hits.append({**it, "src": r["pass"], "w": tuple(r["w"])})
    readings = clean
    hits.sort(key=lambda h: h["start"])
    clusters: list[list[dict]] = []
    for h in hits:
        for c in clusters[-4:]:
            if any(h["start"] < x["end"] + 0.12 and h["end"] > x["start"] - 0.12 for x in c):
                c.append(h)
                break
        else:
            clusters.append([h])
    items = []
    for c in clusters:
        t0 = min(h["start"] for h in c)
        t1 = max(h["end"] for h in c)
        mid = (t0 + t1) / 2
        covering = [r for r in readings if r["w"][0] + EDGE <= mid <= r["w"][1] - EDGE
                    or (r["w"][0] <= mid <= r["w"][1] and (r["w"][1] - r["w"][0]) < 2 * EDGE + 0.3)]
        best: dict[tuple, float] = {}
        for h in c:
            k = (h["src"], h["w"])
            conf = 1.0 if h["status"] == "sure" else float(h["score"])
            best[k] = max(best.get(k, 0.0), conf)
        sure_keys = {(h["src"], h["w"]) for h in c if h["status"] == "sure"}
        unbiased_sure = any(src in UNBIASED for src, _w in sure_keys)
        prompted_cov = [r for r in covering if PASSES.get(r["pass"], (False,))[0]]
        prompted_hit = {k for k in best if PASSES.get(k[0], (False,))[0]}
        prompted_sure = {k for k in sure_keys if PASSES.get(k[0], (False,))[0]}
        frac = len(prompted_sure) / max(2, len(prompted_cov))  # one edge window alone is no majority
        rep = sorted(c, key=lambda h: (h["status"] != "sure", h["src"] not in UNBIASED, -float(h.get("score") or 0)))[0]
        alike = any(_alike_near(rep, r["words"], lang) for r in readings if r["pass"] in UNBIASED) or \
            _alike_near(rep, base, lang)
        unbiased_maybe = max((v for k, v in best.items() if k[0] in UNBIASED), default=0.0)
        if unbiased_sure:
            status, score = "sure", 1.0
        elif prompted_sure:
            # heard as a swear only with the prompt
            score = 0.12 + 0.4 * frac + (0.3 if alike else 0.0) + (0.08 if len(prompted_sure) >= 3 else 0.0)
            score = max(score, unbiased_maybe + 0.15 * frac)
            status = "sure" if (alike and frac >= 0.75 and len(prompted_sure) >= 2) else "maybe"
            score = 1.0 if status == "sure" else min(0.9, score)
        else:  # only "maybe" forms (sound-alikes, ı for i...)
            n_src = len({k for k in best})
            score = min(0.85, max(float(h["score"]) for h in c) + 0.08 * (n_src - 1)
                        - (0.15 if not unbiased_maybe and prompted_hit else 0.0))
            status = "maybe"
        if not find_all and status == "maybe" and score < 0.2:
            continue
        spk = next((w.get("spk") for w in base if w["start"] < rep["end"] and w["end"] > rep["start"] and w.get("spk")),
                   rep.get("spk"))
        heard = sorted({h["word"] for h in c})
        items.append({"start": round(float(rep["start"]), 3), "end": round(float(rep["end"]), 3),
                      "word": rep["word"], "heard": heard[:6], "spk": spk, "status": status,
                      "score": round(float(score), 2), "why": "scan:" + "+".join(sorted({h["src"] for h in c})),
                      "votes": f"{len(best)}/{1 + len(covering)}", "src": sorted({h["src"] for h in c}),
                      "lex": rep["why"]})
    items.sort(key=lambda it: it["start"])
    return items


def _alike_near(hit: dict, words: list[dict], lang: str | None) -> bool:
    for w in words:
        if w["start"] < hit["end"] + 0.15 and w["end"] > hit["start"] - 0.15:
            if not swears.sounds_alike(w["word"], hit["word"], lang):
                continue
            # a clearly heard normal word ("Orası" = there) is no evidence for "Orospu"
            tok = token(w["word"], lang)
            if float(w.get("p", w.get("probability", 1.0)) or 0.0) >= 0.6 and swearlex.common_word(tok, lang) \
                    and not swearlex.classify(w["word"], lang):
                continue
            return True
    return False


# ------------------------------------------------------------------------------ leaks

def leak(item_word: str, ws: list[dict], a: float, b: float, lang: str | None) -> str | None:
    """Is any part of the swear still heard around the bleep [a, b]? "left" (the start is
    audible: "si-"), "right" ("-na"), "both" (the word itself), or None."""
    tok = token(item_word, lang)
    side = None
    for w in ws:
        if w["end"] < a - 0.15 or w["start"] > b + 0.15:
            continue
        wt = token(w["word"], lang)
        if not wt:
            continue
        lex = swearlex.classify(w["word"], lang, float(w.get("p", 1.0)))
        if (lex and (lex[0] == "sure" or lex[1] >= 0.5)) or (len(wt) >= 3 and swears.sounds_alike(w["word"], item_word, lang)
                                                             and a <= (w["start"] + w["end"]) / 2 <= b):
            return "both"
        if len(wt) >= 2 and len(tok) >= 4:
            if tok.startswith(wt[:3]) and w["start"] < a + 0.05 and len(wt) <= len(tok) - 1:
                side = "both" if side == "right" else "left"
            elif tok.endswith(wt[-3:]) and w["end"] > b - 0.05 and len(wt) <= len(tok) - 1:
                side = "both" if side == "left" else "right"
    return side


# ------------------------------------------------------------------------------ main

def _base_words(project: Project, ranges: list[tuple[float, float]]) -> tuple[list[dict], str | None]:
    from ..edit.plan import transcript_words

    out, lang = [], None
    for a, b in ranges:
        ws, lang_ = transcript_words(project, a, b)
        lang = lang or lang_
        for w in ws:
            out.append({"start": float(w["start"]), "end": float(w["end"]), "word": w["word"],
                        "p": float(w.get("probability", w.get("p", 1.0)) or 0.0), "spk": w.get("spk")})
    out.sort(key=lambda w: w["start"])
    return out, lang


def _default_engines(need_sep: bool) -> ScanEngines:
    from . import align, models

    eng = ScanEngines()
    if need_sep and models.sherpa_ok():
        try:
            eng.separator = E.Separator()
        except Exception:  # noqa: BLE001 - offline / broken model: the mix only
            eng.separator = None
    try:
        eng.aligner = align.Aligner(threads=E._threads())
    except Exception:  # noqa: BLE001 - no aligner: Whisper's times + wider padding
        eng.aligner = None
    return eng


def run_scan(project: Project, *, engines: ScanEngines | None = None, on_progress: ProgressFn | None = None,
             find_all: bool = False, ranges: list[tuple[float, float]] | None = None,
             verify: bool = True, judge: bool = True) -> dict:
    """The deep check over the clip ranges. find_all: keep every weak candidate (evaluation)."""
    from ..edit import swearlearn
    from . import pipeline

    t_start = time.time()
    meta = project.load_meta()
    src = project.source_path
    if src is None:
        raise SharkyClipsError("The source video is missing.")
    if not project.transcript_path.is_file():
        raise SharkyClipsError("Transcribe the video first.")
    duration = float(meta.get("duration") or 0)
    ranges = ranges if ranges is not None else pipeline.clip_ranges(project, duration)
    if not ranges:
        raise SharkyClipsError("No clips yet: find highlights first.")
    progress = on_progress or (lambda stage, f: None)
    base, lang = _base_words(project, ranges)
    learned = {"add": swearlearn.entries(lang), "ignore": swearlearn.ignored(lang)}
    prompt = prompt_for(lang, swearlearn.hotwords(lang))
    hot = ", ".join(swearlearn.hotwords(lang, 10)) or None
    streams = tracks.audio_streams(src)
    mix_pos = 0
    if streams:
        labels, _src = tracks.labels_for(meta, streams)
        mix_pos = next((s["pos"] for s, lab in zip(streams, labels) if lab == "mixed"), streams[0]["pos"])
    vdata = pipeline.load(project)
    cached_sep = all((project.cache_dir / "voices" / f"voc_{a:.2f}_{b:.2f}.npy").is_file() for a, b in ranges)
    eng = engines if engines is not None else _default_engines(need_sep=not cached_sep)

    # ---- 1. CPU: audio, voices, speech regions, boost, windows
    audio: list[dict] = []
    for ri, (a, b) in enumerate(ranges):
        governor.checkpoint()
        progress("listening", ri / len(ranges))
        mix16 = tracks.read_track(src, mix_pos, a, b)
        if mix16.size == 0:
            continue
        voc = None
        cache = project.cache_dir / "voices" / f"voc_{a:.2f}_{b:.2f}.npy"
        if cache.is_file() and engines is None:
            try:
                voc = np.load(cache).astype(np.float32)
            except Exception:  # noqa: BLE001
                voc = None
        if voc is None and eng.separator is not None:
            try:
                voc = eng.separator(tracks.read_track(src, mix_pos, a, b, sr=44100, channels=2))
                if engines is None:
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    np.save(cache, voc.astype(np.float16))
            except Exception:  # noqa: BLE001
                voc = None
        n = len(mix16) if voc is None else min(len(mix16), len(voc))
        mix16 = mix16[:n]
        voc = voc[:n] if voc is not None else None
        src16 = voc if voc is not None else mix16
        regions = speech_regions(src16)
        spans: dict[str, list[tuple[float, float]]] = {}
        for w in (vdata or {}).get("words", []) if vdata else []:
            if a <= w["start"] and w["end"] <= b and w.get("spk"):
                spans.setdefault(w["spk"], []).append((w["start"] - a, w["end"] - a))
        boosted = boost(src16, regions, spans)
        centers = [((w["start"] + w["end"]) / 2) - a for w in base
                   if a <= w["start"] <= b and (w["p"] < 0.6 or swearlex.classify(w["word"], lang, w["p"]))]
        wins = windows(regions, centers, n / E.SR)
        audio.append({"a": a, "b": b, "mix": mix16, "voc": voc, "boosted": boosted, "regions": regions,
                      "windows": wins})
    n_windows = sum(len(r["windows"]) for r in audio)
    if n_windows > MAX_WINDOWS:  # keep the most interesting ones (centred ones come last: keep all)
        step = n_windows / MAX_WINDOWS
        for r in audio:
            r["windows"] = r["windows"][::max(1, int(round(step)))]

    # ---- 2. GPU: the passes
    own_asr = eng.asr is None
    engine = None
    model_used = "mock"
    if own_asr:
        from .. import transcribe

        progress("loading_whisper", 0.0)
        engine = transcribe.load_whisper("check")
        model_used = getattr(getattr(engine, "plan", None), "model", "?")

        def _asr(x, lang_, prompt_=None, temperature=0.0, hotwords=None):
            return transcribe.transcribe_check(engine, x, lang_, prompt_, temperature, hotwords)

        eng.asr = _asr
    readings: list[dict] = []
    items: list[dict] = []
    try:
        total = max(1, sum(len(r["windows"]) for r in audio))
        done = 0
        for r in audio:
            for s, e in r["windows"]:
                if done % 6 == 0:
                    governor.checkpoint()
                    progress("rechecking", done / total)
                done += 1
                i0, i1 = int(s * E.SR), int(e * E.SR)
                seg = E.level(r["boosted"][i0:i1])
                if len(seg) < E.SR * 0.25:
                    continue
                for name, (prompted, temp, _w) in PASSES.items():
                    segs = eng.asr(seg, lang, prompt if prompted else None, temp, hot if prompted else None)
                    readings.append({"pass": name, "w": [round(r["a"] + s, 3), round(r["a"] + e, 3)],
                                     "words": words_of(segs, r["a"] + s, r["a"] + s, r["a"] + e)})
                if find_all and r["voc"] is not None:  # the plain mix too (separation can eat a word)
                    segs = eng.asr(E.level(r["mix"][i0:i1]), lang, None, 0.0, None)
                    readings.append({"pass": "mix", "w": [round(r["a"] + s, 3), round(r["a"] + e, 3)],
                                     "words": words_of(segs, r["a"] + s, r["a"] + s, r["a"] + e)})
        items = combine(base, readings, lang, learned, find_all=find_all)

        # ---- 3. exact times (CPU aligner) + the bleep check (Whisper again)
        progress("aligning", 0.0)
        for k, it in enumerate(items):
            if k % 10 == 0:
                governor.checkpoint()
            _align_item(it, readings, base, audio, lang, eng.aligner)
        if verify:
            for k, it in enumerate(items):
                if k % 4 == 0:
                    governor.checkpoint()
                    progress("checking_bleeps", k / max(1, len(items)))
                if it["status"] == "sure" or it["score"] >= swears.STRICTNESS["strict"] or find_all:
                    _verify_item(it, audio, lang, eng.asr, prompt)
    finally:
        if own_asr:
            from .. import memory

            engine = None
            eng.asr = None
            memory.release_current()
        if eng.release:
            eng.release()

    # ---- 4. the local AI on borderline words (after Whisper is gone: never both on the GPU)
    if judge:
        _judge(items, base, readings, lang, eng.judge)

    data = {
        "version": VERSION, "language": lang, "ranges": [[a, b] for a, b in ranges],
        "find_all": find_all, "model": model_used, "aligned": eng.aligner is not None,
        "passes": list(PASSES) + (["mix"] if find_all else []),
        "windows": sum(len(r["windows"]) for r in audio),
        "items": items,
        "seconds": round(time.time() - t_start, 1),
        "transcript_created_at": pipeline._transcript_stamp(project),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if find_all:
        data["readings"] = readings
    write_json_atomic(scan_path(project), data)
    progress("done", 1.0)
    return data


def _range_of(audio: list[dict], t: float) -> dict | None:
    return next((r for r in audio if r["a"] <= t <= r["b"]), None)


def _align_item(it: dict, readings: list[dict], base: list[dict], audio: list[dict], lang: str | None,
                aligner) -> None:
    """Exact start / end of the swear by forced alignment of the words heard around it."""
    pre, post = PRE_RAW, POST_RAW
    it["aligned"] = False
    r = _range_of(audio, (it["start"] + it["end"]) / 2)
    if aligner is not None and r is not None:
        # the reading that heard this word, else the base words
        srcs = [rd["words"] for rd in readings if rd["pass"] in it["src"]
                and rd["w"][0] + 0.3 <= it["start"] and it["end"] <= rd["w"][1] - 0.3]
        srcs.append(base)
        for ws in srcs:
            idx = next((i for i, w in enumerate(ws) if abs(w["start"] - it["start"]) < 0.05
                        and token(w["word"], lang) == token(it["word"], lang)), None)
            if idx is None:
                idx = next((i for i, w in enumerate(ws) if w["start"] < it["end"] and w["end"] > it["start"]
                            and swears.sounds_alike(w["word"], it["word"], lang)), None)
            if idx is None:
                continue
            lo, hi = max(0, idx - 3), min(len(ws), idx + 4)
            ctx = [w for w in ws[lo:hi] if abs(w["start"] - ws[idx]["start"]) < 2.5]
            j = ctx.index(ws[idx])
            s = max(r["a"], ctx[0]["start"] - 0.3)
            e = min(r["b"], ctx[-1]["end"] + 0.3)
            x = r["boosted"][int((s - r["a"]) * E.SR):int((e - r["a"]) * E.SR)]
            try:
                spans = aligner.align(x, [w["word"] for w in ctx], lang)
            except Exception:  # noqa: BLE001
                spans = []
            sp = spans[j] if j < len(spans) else None
            if sp is None or sp.conf < 0.08:
                continue
            a2, b2 = s + sp.start, s + sp.end
            if abs(a2 - it["start"]) > 0.6 or abs(b2 - it["end"]) > 0.6 or b2 - a2 < 0.06:
                continue  # the alignment went somewhere else: keep Whisper's times
            it["start"], it["end"] = round(min(a2, it["start"] + 0.1), 3), round(b2, 3)
            it["aligned"] = True
            it["align_conf"] = sp.conf
            pre, post = PRE, POST
            break
    # adaptive padding: a fast talker / short word gets a bit less, an unsure alignment more
    dur = it["end"] - it["start"]
    if it["aligned"] and it.get("align_conf", 1) < 0.25:
        pre, post = pre + 0.03, post + 0.05
    if dur < 0.15:
        pre, post = pre + 0.02, post + 0.03
    it["bleep"] = [round(max(0.0, it["start"] - pre), 3), round(it["end"] + post, 3)]


def _verify_item(it: dict, audio: list[dict], lang: str | None, asr, prompt: str | None) -> None:
    """Bleep it, transcribe again (no prompt, then with the swear prompt); still heard -> wider."""
    r = _range_of(audio, (it["start"] + it["end"]) / 2)
    if r is None or asr is None:
        return
    a, b = it["bleep"]
    rounds = 0
    first = None
    while True:
        s, e = max(r["a"], a - 1.5), min(r["b"], b + 1.5)
        x = bleep_into(r["mix"], a, b, r["a"])[int((s - r["a"]) * E.SR):int((e - r["a"]) * E.SR)]
        if len(x) < E.SR * 0.3:
            return
        side = None
        for prompted in (False, True):
            ws = words_of(asr(E.level(x), lang, prompt if prompted else None, 0.0, None), s, s, e)
            side = leak(it["word"], ws, a, b, lang)
            if side:
                break
        if first is None:
            first = side
        if not side or rounds >= 3 or (b - a) - (it["bleep"][1] - it["bleep"][0]) >= MAX_WIDEN:
            break
        rounds += 1
        if side in ("left", "both"):
            a = max(r["a"], a - 0.06)
        if side in ("right", "both"):
            b = min(r["b"], b + 0.08)
    it["leak_first"] = first  # heard with the first bleep (measurement)
    it["leak"] = side  # still heard after widening (None = clean)
    it["rounds"] = rounds
    it["bleep"] = [round(a, 3), round(b, 3)]


def _judge(items: list[dict], base: list[dict], readings: list[dict], lang: str | None, judge) -> None:
    """Borderline "maybe" words: the local AI reads the sentence and says swear or not."""
    todo = [k for k, it in enumerate(items) if it["status"] == "maybe" and JUDGE_LO <= it["score"] < JUDGE_HI]
    if not todo:
        return
    for k in todo:
        it = items[k]
        ctx = [w for w in base if it["start"] - 4 <= w["start"] <= it["end"] + 4]
        it["context"] = " ".join(w["word"] for w in ctx)[:300] or it["word"]
    if judge is None:
        judge = _llm_judge
    try:
        answers = judge([items[k] for k in todo], lang)
    except Exception:  # noqa: BLE001 - no LLM: the votes decide
        return
    for j, k in enumerate(todo):
        ans = (answers or {}).get(j)
        it = items[k]
        if ans == "yes":
            it["score"] = round(min(0.95, it["score"] + 0.3), 2)
            it["why"] += "+ai"
        elif ans == "no":
            it["score"] = round(max(0.05, it["score"] - 0.3), 2)
            it["why"] += "-ai"


def _llm_judge(batch: list[dict], lang: str | None) -> dict[int, str]:
    from .. import config, languages
    from .. import llm as llm_mod

    if config.get("llm_enabled") is False:
        return {}
    reg = languages.get(lang or "") if lang else None
    lang_label = reg.english_name if reg else (lang or "the spoken language")
    listing = "\n".join(f'{i + 1}. word "{it["word"]}" (also heard as: {", ".join(it.get("heard") or [])}) in: '
                        f'"{it.get("context", "")}"' for i, it in enumerate(batch[:40]))
    system = ("You check speech-to-text output of gaming streams for swear words (profanity, vulgar "
              "insults). Speech recognition often mishears swears as similar normal words and the other "
              "way round. Answer for each item: yes = the speaker most likely said a swear word there, "
              "no = a normal word, unsure.")
    schema = {"type": "object", "properties": {"answers": {"type": "array", "items": {
        "type": "string", "enum": ["yes", "no", "unsure"]}, "minItems": len(batch[:40]), "maxItems": len(batch[:40])}},
        "required": ["answers"]}
    with llm_mod.lazy_session() as llm:
        data = llm.json(system, f"Language: {lang_label}.\n{listing}", schema, temperature=0.1,
                        num_predict=40 + 8 * len(batch))
    return {i: str(a) for i, a in enumerate(data.get("answers") or [])}


# ------------------------------------------------------------------------------ readers

def items_for(data: dict | None, start: float, end: float) -> list[dict]:
    if not data:
        return []
    return [dict(it) for it in data.get("items", []) if start - 0.05 <= (it["start"] + it["end"]) / 2 <= end + 0.05]


def covers(data: dict | None, start: float, end: float) -> bool:
    """The deep check ran over (most of) this clip."""
    if not data:
        return False
    cov = sum(max(0.0, min(end, b) - max(start, a)) for a, b in data.get("ranges", []))
    return cov >= 0.8 * max(0.01, end - start)


# ------------------------------------------------------------------------------ after the render

def fixes_path(project: Project) -> Path:
    return project.dir / "bleep_fixes.json"


def load_fixes(project: Project) -> dict[str, list[list[float]]]:
    p = fixes_path(project)
    try:
        return dict(read_json(p)) if p.is_file() else {}
    except Exception:  # noqa: BLE001
        return {}


def verify_render(project: Project, cand: dict, opts, out_path: Path, asr=None) -> list[tuple[float, float]]:
    """Listen to the rendered clip's bleeps (no prompt, then the swear prompt): where part of a
    swear is still heard, the bleep gets wider (saved in bleep_fixes.json, read by the plan).
    Returns the widened source ranges ([] = all clean: the render can stay)."""
    from .. import clips as clips_mod
    from ..edit import swearlearn

    plan = clips_mod.edit_plan(project, cand, opts, None, 30)
    if plan is None or not plan.bleep_src or plan.bleep_mode == "off":
        return []
    lang = plan.lang
    offset = clips_mod.FLASH_SECONDS if getattr(opts, "hook_flash", False) and not getattr(opts, "loop", False) else 0.0
    offset += float(getattr(plan, "intro_s", 0.0) or 0.0)
    prompt = prompt_for(lang, swearlearn.hotwords(lang))
    own = asr is None
    engine = None
    if own:
        from .. import transcribe

        engine = transcribe.load_whisper("check" if transcribe.check_model_ready() else "auto")

        def asr(x, lang_, prompt_=None, temperature=0.0, hotwords=None):
            return transcribe.transcribe_check(engine, x, lang_, prompt_, temperature, hotwords)
    widened: list[tuple[float, float]] = []
    try:
        for a, b in plan.bleep_src:
            governor.checkpoint()
            outs = plan.out_ranges([(a, b)])
            if not outs:
                continue
            oa, ob = outs[0][0] + offset, outs[-1][1] + offset
            s = max(0.0, oa - 1.5)
            x = tracks.read_track(out_path, 0, s, ob + 1.5)
            if len(x) < E.SR * 0.3:
                continue
            names = [it["word"] for it in plan.swears
                     if it.get("bleep") and a - 0.05 <= it["start"] <= b + 0.05] or [""]
            side = None
            for prompted in (False, True):
                segs = asr(E.level(x), lang, prompt if prompted else None, 0.0, None)
                ws = words_of(segs, s, s, s + len(x) / E.SR)
                for name in names:
                    side = leak(name, ws, oa, ob, lang) if name else None
                    if side:
                        break
                if side:
                    break
            if side:
                widened.append((round(a - (0.08 if side in ("left", "both") else 0.0), 3),
                                round(b + (0.1 if side in ("right", "both") else 0.0), 3)))
    finally:
        if own:
            from .. import memory

            engine = None
            memory.release_current()
    if widened:
        fx = load_fixes(project)
        cur = [tuple(r) for r in fx.get(str(cand["id"]), [])]
        fx[str(cand["id"])] = [[x, y] for x, y in sorted(set(cur) | set(widened))][:200]
        write_json_atomic(fixes_path(project), fx)
    return widened
