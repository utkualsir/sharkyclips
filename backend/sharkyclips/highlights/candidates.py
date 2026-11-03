"""Turn the hype curve into clip candidates.

1. Peak picking on the smoothed curve (min distance between peaks).
2. A window per peak: pre-roll for the setup, the reaction, a short tail.
3. Boundaries snapped to WORD timestamps: never mid-word, prefer sentence edges.
4. Non-maximum suppression: clips never overlap.
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
    marker: dict | None = None  # live marker (hotkey / "!clip") this clip was made for

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


def refine(ctx: AnalysisContext, start: float, end: float, peak: float,
           must: tuple[float, float] | None = None) -> tuple[float, float]:
    """Snap to word boundaries. `must` = (latest start, earliest end) that keep a whole game
    event (e.g. every kill of a multikill) inside the clip."""
    words = ctx.words
    if not words:
        return start, end
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
    chosen.sort(key=lambda c: (c.marker is None, -c.hype_score, c.start))
    return chosen


def marker_candidates(ctx: AnalysisContext, curve: np.ndarray, hype: HypeCurve, spans: list[tuple]) -> list[Candidate]:
    """Clips around the user's live markers: the build-up before the mark, a short tail after.
    Markers close together share one clip."""
    from ..markers import AFTER_S, BUILD_UP_S, MERGE_S, load_project

    marks = sorted((m for m in load_project(ctx.project) if 0 <= float(m.get("t", -1)) <= ctx.duration),
                   key=lambda m: float(m["t"]))
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
        p = int(min(len(curve) - 1, max(0, round(t1))))
        build = min(BUILD_UP_S, max(mode.clip_min, mode.clip_max - AFTER_S - (t1 - t0)))
        s, e = max(0.0, t0 - build), min(ctx.duration, t1 + AFTER_S)
        s, e, must = fit_spans(s, e, p, spans, mode, ctx.duration)
        keep = (round(t0 - min(10.0, build), 2), round(min(ctx.duration, t1 + 1.5), 2))
        must = keep if must is None else (min(must[0], keep[0]), max(must[1], keep[1]))
        s, e = refine(ctx, s, e, float(p), must)
        if e - s < 3 or any(s < c.end + 1.0 and e > c.start - 1.0 for c in out):
            continue
        out.append(Candidate(peak=round(t1, 2), start=s, end=e, raw=float(curve[p]),
                             raw_unsmoothed=float(hype.combined[p]), marker=g[0]))
    return out
