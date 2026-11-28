"""Turn the hype curve into clip candidates.

1. Peak picking on the smoothed curve (min distance between peaks).
2. A window per peak: pre-roll for the setup, the reaction, a short tail.
3. Boundaries snapped to WORD timestamps: never mid-word, prefer sentence edges.
4. Non-maximum suppression: clips never overlap.

1.2.77 (phase D8) context:
  * smart pre-roll: the clip starts where the build-up began (the hype was still calm, e.g. before
    the fight started), up to `setup_max` seconds back, and never in the middle of a sentence
  * clean ending: a laugh / scream that is still going isn't cut, and without a word nearby the
    clip ends at the quietest half second (not mid-sound)
  * spoken markers ("clip it", markers.find_spoken) become clips like hotkey markers, ending just
    before the phrase
  * headline: one short reason per clip for the card ("Chat went wild", "Big laugh", "Clutch")
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import find_peaks

from .context import AnalysisContext, Word
from .modes import ModePreset
from .scorer import HypeCurve

MAX_REASONS = 6
# Reasons whose value names *what* happened stay separate per value ("keyword: oha",
# "keyword: nasıl ya"); for the rest one entry per code is enough (strongest + count).
DISTINCT_BY_VALUE = {"keyword"}


@dataclass
class Candidate:
    peak: float
    start: float
    end: float
    raw: float  # smoothed hype at the peak (absolute, 0..1)
    raw_unsmoothed: float
    hype_score: int = 0  # 0..100, relative within this video
    reasons: list[dict] = field(default_factory=list)
    signal_scores: dict[str, float] = field(default_factory=dict)
    text: str = ""
    marker: dict | None = None  # live marker (hotkey / "!clip" / spoken phrase) this clip was made for
    headline: dict | None = None  # {"code", "value"?}: the one reason shown on the card

    @property
    def duration(self) -> float:
        return self.end - self.start


# --------------------------------------------------------------- windows


def _initial_window(curve: np.ndarray, p: int, mode: ModePreset, duration: float) -> tuple[float, float]:
    n = len(curve)
    thr = curve[p] * 0.5
    left = p
    while left > 0 and curve[left - 1] >= thr and p - left < mode.clip_max:
        left -= 1
    right = p
    while right < n - 1 and curve[right + 1] >= thr and right - p < mode.clip_max:
        right += 1

    pre_min, pre_max = mode.pre_roll
    if mode.boundary == "music":
        start = left - 1.0
        end = start + mode.clip_ideal
    elif mode.boundary == "sentence":
        start = min(left - pre_min, p - pre_max)
        end = right + 1 + mode.post_roll
    else:  # reaction
        start = float(np.clip(left - 2, p - pre_max, p - pre_min))
        end = right + 1 + mode.post_roll

    length = end - start
    if length < mode.clip_min:
        extra = (mode.clip_min + mode.clip_ideal) / 2 - length
        before = 0.0 if mode.boundary == "reaction" else 0.35
        start -= extra * before
        end += extra * (1 - before)
    if end - start > mode.clip_max:
        end = start + mode.clip_max
        if end < p + 2:  # always keep the peak itself
            end = p + 2
            start = end - mode.clip_max

    # Keep inside the video, preserving length where possible.
    if start < 0:
        end, start = min(duration, end - start), 0.0
    if end > duration:
        start, end = max(0.0, start - (end - duration)), duration
    return start, end


MUST_HAVE_STRENGTH = 0.8  # game events this big always become a candidate
SPAN_BUILD_UP = 4.0  # seconds of build-up kept before a game event
SPAN_AFTER = 2.0  # and after its last moment (the reaction)


def fit_spans(start: float, end: float, peak: int, spans: list[tuple], mode: ModePreset,
              duration: float) -> tuple[float, float, tuple[float, float] | None]:
    """Grow the window so every game event it touches fits whole (all kills of a multikill),
    with build-up before it. Returns (start, end, must) where must = (latest start, earliest
    end) for word snapping, or None when no event is involved."""
    hits = [(a, b) for a, b, *_ in spans if a <= end and b >= start]
    if not hits:
        return start, end, None
    a = min(x for x, _ in hits)
    b = max(y for _, y in hits)
    need_s, need_e = max(0.0, a - SPAN_BUILD_UP), min(duration, b + SPAN_AFTER)
    if need_e - need_s > mode.clip_max:
        # Events too far apart for one clip: keep the ones around the peak.
        near = [(x, y) for x, y in hits if x - SPAN_BUILD_UP <= peak <= y + SPAN_AFTER + mode.clip_max / 2]
        a = min((x for x, _ in near), default=peak)
        b = max((y for _, y in near), default=peak)
        need_s, need_e = max(0.0, a - SPAN_BUILD_UP), min(duration, b + SPAN_AFTER)
        if need_e - need_s > mode.clip_max:
            need_e = need_s + mode.clip_max
    s, e = min(start, need_s), max(end, need_e)
    if e - s > mode.clip_max:  # trim the extra context, never the event
        extra = (e - s) - mode.clip_max
        cut_front = min(extra, need_s - s)
        s += cut_front
        e -= extra - cut_front
    return round(s, 2), round(e, 2), (round(need_s + 1.0, 2), round(min(need_e, s + mode.clip_max), 2))


# ------------------------------------------------------- smart pre-roll / tail

SETUP_CALM = 0.3  # the setup starts where the hype was still below this share of the peak
SETUP_CALM_PAD = 2.0  # seconds of the calm kept before the rise (context)
SENTENCE_BACK_S = 6.0  # how far back a start may move to reach its sentence's first word
TAIL_SIGNALS = ("laughter", "voice")
TAIL_MAX_S = 20.0  # a reaction is kept going at most this long after the peak


def sentence_start_before(ctx: AnalysisContext, t: float, max_back: float, floor: float = 0.0) -> float:
    """t, or the start of the sentence that is still running at t (when it began <= max_back
    earlier). Starting mid-sentence loses the setup of a joke or a story."""
    words, starts = ctx.words, ctx.word_starts
    if not words:
        return t
    i = int(np.searchsorted(starts, t, side="right")) - 1
    if i < 0:
        return t
    w = words[i]
    nxt_gap = words[i + 1].start - w.end if i + 1 < len(words) else 99.0
    if w.end < t - 0.3 and (w.ends_sentence or nxt_gap >= 0.8):
        return t  # t is in a pause between sentences
    j = i
    while j > 0 and not words[j - 1].ends_sentence and words[j].start - words[j - 1].end < 0.8:
        j -= 1
        if words[j].start < max(t - max_back, floor):
            return t  # a very long sentence (or no punctuation): word snapping decides
    return max(0.0, min(t, words[j].start - 0.2))


def sentences_back(ctx: AnalysisContext, t: float, n: int, earliest: float, pause_s: float = 2.5) -> float:
    """Move a start that sits on a sentence start back by up to n whole sentences (the setup of a
    joke / story), never past `earliest` and never across a long pause (a new topic)."""
    words, starts = ctx.words, ctx.word_starts
    if not words or n <= 0:
        return t
    i = int(np.searchsorted(starts, t))  # the first word of the clip
    for _ in range(n):
        if i <= 0 or i >= len(words):
            break
        if words[i].start - words[i - 1].end >= pause_s:
            break
        j = i - 1  # back to the first word of the sentence before
        while j > 0 and not words[j - 1].ends_sentence and words[j].start - words[j - 1].end < 0.8:
            j -= 1
        if words[j].start < earliest:
            break
        i = j
    return max(0.0, min(t, words[i].start - 0.2)) if i < len(words) else t


def smart_window(ctx: AnalysisContext, hype: HypeCurve, curve: np.ndarray, p: int, s: float,
                 e: float) -> tuple[float, float]:
    """Reaction clips: start at the build-up, keep the reaction to its end, trim the setup (never
    the payoff) when it gets too long."""
    mode = ctx.mode
    if mode.boundary != "reaction":
        return s, e
    pre_min, pre_max = mode.pre_roll
    setup_max = float(mode.extra.get("setup_max", pre_max))
    floor = float(np.median(curve))
    thr = floor + SETUP_CALM * (float(curve[p]) - floor)
    onset = p
    lim = max(0, int(p - setup_max))
    while onset > lim and curve[onset - 1] > thr:
        onset -= 1
    start = max(min(s, onset - SETUP_CALM_PAD), p - setup_max, 0.0)
    start = sentence_start_before(ctx, start, SENTENCE_BACK_S, floor=p - setup_max - 4)
    # talk streams: the line(s) before the punchline are the setup
    start = sentences_back(ctx, start, int(mode.extra.get("setup_sentences", 0)), p - setup_max)
    end = e
    stop = min(ctx.duration, p + TAIL_MAX_S)
    for name in TAIL_SIGNALS:
        r = hype.results.get(name)
        if r is None:
            continue
        while end < stop and int(end) < len(r.scores) and r.scores[int(end)] >= 0.5:
            end += 1.0
    if end - start > mode.clip_max:
        start = min(max(start, end - mode.clip_max), p - pre_min)
        if end - start > mode.clip_max:
            end = start + mode.clip_max
    return round(max(0.0, start), 2), round(min(ctx.duration, end), 2)


# ----------------------------------------------------------- word snapping


def _inside_word(words: list[Word], starts: np.ndarray, t: float) -> int | None:
    i = int(np.searchsorted(starts, t, side="right")) - 1
    if 0 <= i < len(words) and words[i].start < t < words[i].end:
        return i
    return None


def _snap_start(words, starts, t: float, back: float, fwd: float, latest: float) -> float:
    lo, hi = t - back, min(t + fwd, latest)
    i0, i1 = int(np.searchsorted(starts, lo)), int(np.searchsorted(starts, hi, side="right"))
    best, best_q = None, -1e9
    for i in range(i0, i1):
        prev = words[i - 1] if i > 0 else None
        gap = words[i].start - prev.end if prev else 99.0
        q = 0.0
        if prev is None or prev.ends_sentence:
            q += 2.0
        q += 1.5 if gap >= 0.8 else (0.7 if gap >= 0.3 else 0.0)
        q -= abs(words[i].start - t) / max(1.0, back + fwd) * 1.5
        if q > best_q:
            best, best_q = i, q
    if best is None:
        j = _inside_word(words, starts, t)
        if j is None:
            return t
        best = j
    prev_end = words[best - 1].end + 0.02 if best > 0 else 0.0
    return max(words[best].start - 0.25, prev_end, 0.0)


def _snap_end(words, starts, t: float, back: float, fwd: float, earliest: float,
              duration: float) -> float:
    lo, hi = max(t - back, earliest), t + fwd
    best, best_q = None, -1e9
    i0 = max(0, int(np.searchsorted(starts, lo)) - 1)
    for i in range(i0, len(words)):
        w = words[i]
        if w.start > hi:
            break
        if not lo <= w.end <= hi:
            continue
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = nxt.start - w.end if nxt else 99.0
        q = 0.0
        if w.ends_sentence:
            q += 2.0
        q += 1.5 if gap >= 0.8 else (0.7 if gap >= 0.3 else 0.0)
        q -= abs(w.end - t) / max(1.0, back + fwd) * 1.5
        if q > best_q:
            best, best_q = i, q
    if best is None:
        j = _inside_word(words, starts, t)
        if j is None:
            return t
        best = j
    nxt_start = words[best + 1].start - 0.02 if best + 1 < len(words) else duration
    return min(words[best].end + 0.35, nxt_start, duration)


def _near_word_edge(words, starts, t: float, tol: float = 0.5) -> bool:
    i = int(np.searchsorted(starts, t, side="right")) - 1
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(words) and words[j].start - 0.05 <= t <= words[j].end + tol:
            return True
    return False


def quiet_end(ctx: AnalysisContext, t: float, lo: float, hi: float) -> float:
    """The quietest half second in [lo, hi] (the end of a sound, not the middle of it)."""
    try:
        db = ctx.rms_db
    except Exception:  # noqa: BLE001 - no audio level: keep t
        return t
    a, b = int(max(0.0, lo) * 2), int(min(ctx.duration, hi) * 2)
    if b <= a or a >= len(db):
        return t
    k = a + int(np.argmin(db[a:min(b + 1, len(db))]))
    return float(min(hi, max(lo, k / 2 + 0.25)))


CLEAN_GAP_S = 0.6  # a pause this long after a word is a clean place to end
CLEAN_BACK_S, CLEAN_FWD_S = 8.0, 6.0


def clean_sentence_end(words, starts, s: float, e: float, earliest: float, latest: float,
                       clip_min: float) -> float:
    """An end on a word in the middle of a sentence (no full stop, no pause after it) moves to the
    last finished sentence before it, or else to the end of the sentence that is running. Never
    before `earliest` (the payoff), never after `latest`."""
    i = int(np.searchsorted(starts, e, side="right")) - 1
    if i < 0:
        return e
    w = words[i]
    if e > w.end + 0.5:
        return e  # already in a pause
    gap = words[i + 1].start - w.end if i + 1 < len(words) else 99.0
    if w.ends_sentence or gap >= CLEAN_GAP_S:
        return e
    floor = max(earliest, e - CLEAN_BACK_S, s + 0.8 * clip_min)
    for j in range(i - 1, -1, -1):
        wj = words[j]
        if wj.end < floor:
            break
        if wj.ends_sentence or words[j + 1].start - wj.end >= CLEAN_GAP_S:
            return min(wj.end + 0.35, words[j + 1].start - 0.02)
    for j in range(i + 1, len(words)):
        wj = words[j]
        if wj.end > min(latest, e + CLEAN_FWD_S):
            break
        nxt = words[j + 1].start if j + 1 < len(words) else None
        if wj.ends_sentence or nxt is None or nxt - wj.end >= CLEAN_GAP_S:
            return min(wj.end + 0.35, nxt - 0.02) if nxt is not None else wj.end + 0.35
    return e


DEAD_TAIL_S = 2.5  # this much silence after the last word ...
DEAD_TAIL_DB = 10.0  # ... this much quieter than the clip's speech is dead air
DEAD_TAIL_KEEP = 0.8


def trim_dead_tail(ctx: AnalysisContext, s: float, e: float, earliest: float) -> float:
    """Seconds of near-silence after the last word (nothing happens, no game sound, no laugh) are
    cut down to a short breath."""
    words, starts = ctx.words, ctx.word_starts
    k = int(np.searchsorted(starts, e)) - 1
    if k < 0:
        return e
    last = words[k].end
    if e - last < DEAD_TAIL_S or last + DEAD_TAIL_KEEP < earliest or last <= s:
        return e
    try:
        db = ctx.rms_db
    except Exception:  # noqa: BLE001
        return e
    a, b, c = int(s * 2), int(last * 2), int(e * 2)
    if c > len(db) or b - a < 2 or c - b < 2:
        return e
    speech = float(np.percentile(db[a:b], 75))  # the level while somebody talks
    tail = float(np.percentile(db[b + 1:c], 90))
    return last + DEAD_TAIL_KEEP if tail < speech - DEAD_TAIL_DB else e


def refine(ctx: AnalysisContext, start: float, end: float, peak: float,
           must: tuple[float, float] | None = None, max_end: float | None = None) -> tuple[float, float]:
    """Snap to word boundaries. `must` = (latest start, earliest end) that keep a whole game
    event (e.g. every kill of a multikill) inside the clip. `max_end`: the clip never runs past
    it (a spoken "clip it" right after the moment)."""
    words = ctx.words
    if not words:
        e = quiet_end(ctx, end, max(peak + 1, end - 1.0), min(ctx.duration, end + 1.0))
        if max_end is not None:
            e = min(e, max_end)
        return round(start, 2), round(e, 2)
    starts = ctx.word_starts
    mode = ctx.mode
    if mode.boundary == "sentence":
        sb, sf, eb, ef = 8.0, 3.0, 4.0, 8.0
    elif mode.boundary == "music":
        sb, sf, eb, ef = 2.0, 2.0, 2.0, 2.0
    else:
        sb, sf, eb, ef = 3.0, 2.0, 3.0, 4.0
    latest_start = peak - mode.pre_roll[0] if mode.boundary == "reaction" else peak
    earliest_end = peak + 1
    if must:
        latest_start = min(latest_start, must[0])
        earliest_end = max(earliest_end, must[1])
    s = _snap_start(words, starts, start, sb, sf, latest_start)
    e = _snap_end(words, starts, end, eb, ef, earliest_end, ctx.duration)
    if e - s > mode.clip_max:  # too long: look for an earlier word end only
        e = _snap_end(words, starts, s + mode.clip_max - 0.4, eb, 0.0, min(earliest_end, s + mode.clip_max),
                      ctx.duration)
        if e - s > mode.clip_max:  # last word that still fits, else a hard cut
            limit = s + mode.clip_max
            window = words[int(np.searchsorted(starts, s)):int(np.searchsorted(starts, limit))]
            fits = [w.end for w in window if w.end <= limit][-1:]
            e = min(fits[0] + 0.1, limit) if fits and fits[0] > peak else limit
    elif e - s < mode.clip_min and ctx.duration >= mode.clip_min:  # too short: later end only
        e = _snap_end(words, starts, s + mode.clip_min + 0.4, 0.0, ef, s + mode.clip_min,
                      ctx.duration)
    e = clean_sentence_end(words, starts, s, e, earliest_end, min(ctx.duration, s + mode.clip_max), mode.clip_min)
    e = trim_dead_tail(ctx, s, e, max(earliest_end, s + mode.clip_min * 0.8))
    if not _near_word_edge(words, starts, e):  # no word to end on: end where the sound stops
        k = int(np.searchsorted(starts, e))  # the next word: the quiet point never runs into it
        prev_end = words[k - 1].end + 0.05 if k > 0 else 0.0
        nxt = words[k].start - 0.05 if k < len(words) else ctx.duration
        e = quiet_end(ctx, e, max(earliest_end, e - 1.0, prev_end),
                      min(ctx.duration, e + 1.0, s + mode.clip_max, nxt))
    if max_end is not None and e > max_end:
        inside = words[int(np.searchsorted(starts, s)):int(np.searchsorted(starts, max_end))]
        ends = [w.end for w in inside if w.end <= max_end]
        e = min(max_end, ends[-1] + 0.3) if ends and ends[-1] > s + 1 else max_end
    return round(max(0.0, s), 2), round(min(ctx.duration, e), 2)


# ---------------------------------------------------------------- reasons


def _reasons(hype: HypeCurve, start: float, end: float) -> list[dict]:
    best: dict[tuple, dict] = {}
    counts: dict[tuple, int] = {}
    for name, res in hype.results.items():
        share = hype.shares[name]
        for ev in res.events:
            if not start <= ev.t <= end:
                continue
            key = (ev.code, ev.value if ev.code in DISTINCT_BY_VALUE else None)
            counts[key] = counts.get(key, 0) + 1
            rank = ev.strength * share
            if key not in best or rank > best[key]["_rank"]:
                best[key] = {**ev.to_dict(), "signal": name, "_rank": rank, "_key": key}
    out = sorted(best.values(), key=lambda r: -r["_rank"])[:MAX_REASONS]
    for r in out:
        if counts[r["_key"]] > 1:
            r["count"] = counts[r["_key"]]
        del r["_rank"], r["_key"]
    return out


# ------------------------------------------------------------------- main


def default_count(duration: float) -> int:
    return int(np.clip(round(duration / 240), 3, 40))  # ~1 per 4 minutes, 3..40


def pick_candidates(ctx: AnalysisContext, hype: HypeCurve, top: int | None = None) -> list[Candidate]:
    curve = hype.smoothed
    mode = ctx.mode
    top = top or default_count(ctx.duration)
    if len(curve) < 3 or curve.max() <= 0:
        return []
    floor = float(np.median(curve))
    threshold = floor + 0.1 * (float(curve.max()) - floor)
    peaks, _ = find_peaks(np.concatenate([[0.0], curve, [0.0]]), height=threshold,
                          distance=max(1, int(mode.min_gap / 3)), prominence=0.01)
    peaks = sorted((int(p) - 1 for p in peaks), key=lambda p: -curve[p])
    spans = [tuple(x) for r in hype.results.values() for x in (r.meta or {}).get("spans", [])]

    # Live markers first: the streamer said "this one!" - each becomes a clip with its build-up.
    chosen: list[Candidate] = marker_candidates(ctx, curve, hype, spans)
    n_marked = len(chosen)
    for p in peaks:
        if len(chosen) - n_marked >= top:
            break
        if any(abs(p - c.peak) < mode.min_gap for c in chosen):
            continue
        s, e = _initial_window(curve, p, mode, ctx.duration)
        s, e = smart_window(ctx, hype, curve, p, s, e)
        s, e, must = fit_spans(s, e, p, spans, mode, ctx.duration)
        s, e = refine(ctx, s, e, p, must)
        if e - s < min(mode.clip_min * 0.5, ctx.duration * 0.5):
            continue
        if any(s < c.end + 1.0 and e > c.start - 1.0 for c in chosen):  # NMS: no overlap
            continue
        chosen.append(Candidate(peak=float(p), start=s, end=e, raw=float(curve[p]),
                                raw_unsmoothed=float(hype.combined[p])))

    # Big game moments (triple kill and up, steals, extractions) are always offered, even when
    # nobody reacted loudly enough to put them in the top N.
    for a, b, strength in sorted(spans, key=lambda x: -x[2]):
        if strength < MUST_HAVE_STRENGTH or any(c.start <= a and b <= c.end for c in chosen):
            continue
        p = int(min(len(curve) - 1, max(0, round(b))))
        s, e = _initial_window(curve, p, mode, ctx.duration)
        s, e, must = fit_spans(s, e, p, spans, mode, ctx.duration)
        s, e = refine(ctx, s, e, p, must)
        if any(s < c.end + 1.0 and e > c.start - 1.0 for c in chosen):
            continue
        chosen.append(Candidate(peak=float(p), start=s, end=e, raw=float(curve[p]),
                                raw_unsmoothed=float(hype.combined[p])))

    if not chosen:
        return []
    top_raw = max(c.raw for c in chosen)
    for c in chosen:
        rel = (c.raw - floor) / (top_raw - floor) if top_raw > floor else 1.0
        c.hype_score = int(np.clip(round(100 * rel), 1, 100))
        c.reasons = _reasons(hype, c.start, c.end)
        a, b = int(c.start), max(int(c.start) + 1, int(np.ceil(c.end)))
        c.signal_scores = {n: round(float(r.scores[a:b].max()), 3) for n, r in hype.results.items()}
        c.text = ctx.text_between(c.start, c.end)
        if c.marker is not None:
            r = {"code": "marker", "value": c.marker.get("by") or c.marker.get("source"), "t": round(c.peak, 2),
                 "strength": 1.0, "signal": "marker"}
            c.reasons = [r] + c.reasons[: MAX_REASONS - 1]
        c.headline = headline(c)
    chosen.sort(key=lambda c: (c.marker is None, -c.hype_score, c.start))
    return chosen


def marker_candidates(ctx: AnalysisContext, curve: np.ndarray, hype: HypeCurve, spans: list[tuple]) -> list[Candidate]:
    """Clips around the user's live markers: the build-up before the mark, a short tail after.
    Markers close together share one clip."""
    from ..markers import AFTER_S, BUILD_UP_S, MERGE_S, VOICE_END_GAP_S, find_spoken, load_project

    marks = [m for m in load_project(ctx.project) if 0 <= float(m.get("t", -1)) <= ctx.duration]
    try:
        marks += find_spoken(ctx.words)  # "clip it" said while recording
    except Exception:  # noqa: BLE001 - a bad phrase setting must not stop the highlights
        pass
    marks.sort(key=lambda m: float(m["t"]))
    mode = ctx.mode
    # Marks a few seconds apart are one moment (you pressed the hotkey, a mod typed !clip).
    groups: list[list[dict]] = []
    for m in marks:
        if groups and float(m["t"]) - float(groups[-1][-1]["t"]) <= MERGE_S:
            groups[-1].append(m)
        else:
            groups.append([m])
    out: list[Candidate] = []
    for g in groups:
        t0, t1 = float(g[0]["t"]), float(g[-1]["t"])
        spoken = g[-1].get("source") == "voice"  # the moment came just BEFORE the phrase
        max_end = t1 - VOICE_END_GAP_S if spoken else None
        p = int(min(len(curve) - 1, max(0, round(t1 - (1 if spoken else 0)))))
        after = 0.0 if spoken else AFTER_S
        build = min(BUILD_UP_S, max(mode.clip_min, mode.clip_max - after - (t1 - t0)))
        s, e = max(0.0, t0 - build), min(ctx.duration, max_end if spoken else t1 + after)
        s, e, must = fit_spans(s, e, p, spans, mode, ctx.duration)
        keep_end = max_end if spoken else min(ctx.duration, t1 + 1.5)
        keep = (round(t0 - min(10.0, build), 2), round(keep_end, 2))
        must = keep if must is None else (min(must[0], keep[0]), max(must[1], keep[1]))
        if spoken:
            must = (must[0], min(must[1], max_end))
        s, e = refine(ctx, s, e, float(min(p, keep_end - 1)), must, max_end=max_end)
        if e - s < 3 or any(s < c.end + 1.0 and e > c.start - 1.0 for c in out):
            continue
        marker = next((m for m in g if m.get("source") == "voice"), g[0]) if spoken else g[0]
        out.append(Candidate(peak=round(t1, 2), start=s, end=e, raw=float(curve[p]),
                             raw_unsmoothed=float(hype.combined[p]), marker=marker))
    return out


# ---------------------------------------------------------------- headline

# reason code -> the card's headline (frontend: "headline.<code>")
HEADLINE_OF = {
    "chat_spike": "chat_wild", "chat_reactions": "chat_wild",
    "laughter": "big_laugh", "funny_line": "funny",
    "scream": "scream", "voice_excited": "hype_voice",
    "silence_break": "out_of_nowhere", "pause_then_burst": "big_reaction",
    "fail_line": "fail", "lol_death": "fail", "df_death": "fail", "df_extract_failed": "fail", "lol_defeat": "fail",
    "shouting": "big_reaction", "loudness_spike": "big_reaction", "keyword": "big_reaction",
    "cheering": "big_reaction", "fast_speech": "big_reaction",
    "steady_explanation": "explanation", "llm_explanation": "explanation",
    "chorus": "music_peak", "drop": "music_peak",
}
# game events big enough to be the headline themselves (shown with the game's own label)
BIG_GAME = {"lol_pentakill", "lol_quadrakill", "lol_triplekill", "lol_ace", "lol_shutdown", "df_multikill",
            "df_extracted", "df_revenge"}
CLUTCH_GAME = {"lol_baron_steal", "lol_dragon_steal"}
CLUTCH_WORDS = ("clutch", "klač", "клатч")
# specific (what happened) > context (how it sounded) > "Big reaction"
HEADLINE_TIER = {"chat_wild": 0, "big_laugh": 0, "funny": 0, "scream": 0, "fail": 0, "explanation": 0, "music_peak": 0,
                 "hype_voice": 1, "out_of_nowhere": 1, "big_reaction": 2}
# a headline this specific needs a reason at least this strong (else the next reason is tried)
HEADLINE_MIN = {"chat_wild": 0.55, "out_of_nowhere": 0.5, "hype_voice": 0.5, "scream": 0.6}


def headline(c: Candidate) -> dict | None:
    """The one reason the card shows first. Your own marker > clutch > a big game event > the
    strongest specific reason (chat going wild, a laugh, a scream, a fail, ...) > "Big reaction"."""
    if c.marker is not None:
        if c.marker.get("source") == "voice":
            return {"code": "said", "value": c.marker.get("by")}
        return {"code": "marked"}
    rs = c.reasons
    said = any(r["code"] in ("keyword", "chat_reactions")
               and any(w in str(r.get("value") or "").casefold() for w in CLUTCH_WORDS) for r in rs)
    if said or any(r["code"] in CLUTCH_GAME for r in rs):
        return {"code": "clutch"}
    big = [r for r in rs if r["code"] in BIG_GAME]
    if big:
        b = max(big, key=lambda r: r.get("strength", 0))
        out = {"code": "game", "value": b["code"]}
        if b["code"] == "df_multikill" and b.get("value"):
            out["n"] = b["value"]
        return out
    best: tuple[int, int, str] | None = None
    for i, r in enumerate(rs):  # strongest first; a more specific kind wins over a stronger vague one
        h = HEADLINE_OF.get(r["code"])
        if h is None or float(r.get("strength") or 0) < HEADLINE_MIN.get(h, 0.0):
            continue
        key = (HEADLINE_TIER.get(h, 2), i, h)
        if best is None or key < best:
            best = key
    return {"code": best[2]} if best else None
