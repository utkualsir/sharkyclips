"""Easy mode 2.0: every Easy clip is shaped before it is rendered.

1. Context guard: a clip has its setup AND its payoff. The start moves back to the start of
   the sentence (and far enough before the first big moment); the end waits until the laugh /
   the reaction calms down and the sentence is finished. The local AI's judgement ("needs the
   setup") from the analysis is used too. Always on word boundaries.
2. Length target per content type (funny gaming 18-28 s, clutch / action 20-35 s, study
   30-45 s, music 15-30 s) and a plain-words warning when a clip is longer.
3. One-tap nudges: start 3 s earlier, end 3 s later, short / long version.

The result lives in two places: the trim in review.json "edits" (so the renderer, the preview
and Pro mode all use it) and the reasons in easy.json clips[cid]["shape"]. A trim the user made
(Easy sheet, nudges, Pro) is never overwritten: shaping only touches a clip whose trim is still
the one shaping wrote.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

import numpy as np

from .project import Project

SHAPE_VERSION = 1
SENTENCE_END = tuple(".!?。！？…؟")

# Content type -> (shortest good, longest good) seconds. Shorts data: 15-30 s is best,
# retention drops a lot after 45 s.
TARGETS = {"funny": (18.0, 28.0), "action": (20.0, 35.0), "study": (30.0, 45.0), "music": (15.0, 30.0)}
FUNNY_MOMENTS = {"funny", "fail", "reaction", "rage", "banter", "troll", "joke", "meme"}
LONG_WARN_S = 45.0  # above this: "a lot of viewers leave" (said in plain words)

MAX_BACK = 8.0  # the guard moves a boundary at most this far
MAX_FWD = 6.0
LEAD = {"gaming": 2.5, "study": 1.0, "music": 0.0}  # seconds of setup before the first big moment
TAIL = {"gaming": 1.5, "study": 0.8, "music": 0.0}  # and after the last one
NUDGE_S = 3.0
EVENT_CODES_MIN = 0.5  # reasons at least this strong count as "a big moment"
# Reasons that are the moment itself (not just "it got loud")
MOMENT_PREFIXES = ("df_", "lol_", "marker", "keyword", "laughter", "scream", "shouting", "cheering",
                   "chat_spike", "chat_reactions", "loudness_spike", "llm")


def content_kind(mode: str, cand: dict) -> str:
    if mode in ("study", "music"):
        return mode
    llm = cand.get("llm") or {}
    mt = str(llm.get("moment_type") or "").lower()
    try:
        funny, exciting = float(llm.get("funny") or 0), float(llm.get("exciting") or 0)
    except (TypeError, ValueError):
        funny = exciting = 0.0
    if mt in FUNNY_MOMENTS or (llm and funny > exciting):
        return "funny"
    if not llm:  # no AI judgement: laughter decides
        codes = {str(r.get("code")) for r in cand.get("reasons") or []}
        if "laughter" in codes and not any(c.startswith(("df_", "lol_")) for c in codes):
            return "funny"
    return "action"


def target(mode: str, cand: dict) -> dict:
    kind = content_kind(mode, cand)
    lo, hi = TARGETS[kind]
    return {"kind": kind, "min": lo, "max": hi}


def length_note(duration: float, tgt: dict) -> str | None:
    """None when the length is fine, else "long" (over the target) / "very_long" (over 45 s)."""
    if duration > max(LONG_WARN_S, tgt["max"] + 3):
        return "very_long"
    if duration > tgt["max"] + 3:
        return "long"
    return None


# ===================================================================== what is around a clip


@dataclass
class Around:
    words: list[dict]
    t0: float  # db[0] is at this time
    db: np.ndarray  # loudness every 0.25 s
    laugh: np.ndarray | None  # laughter score per second of the whole video
    baseline: float
    duration: float
    mode: str
    events: list[dict] = field(default_factory=list)  # strong reasons (t, code)
    _starts: list[float] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._starts = [w["start"] for w in self.words]

    # ---- words
    def index_at_or_after(self, t: float) -> int:
        return bisect.bisect_left(self._starts, t - 1e-6)

    def word_at(self, t: float) -> int | None:
        i = bisect.bisect_right(self._starts, t) - 1
        if 0 <= i < len(self.words) and self.words[i]["start"] <= t < self.words[i]["end"]:
            return i
        return None

    @staticmethod
    def ends(w: dict) -> bool:
        return str(w["word"]).strip().endswith(SENTENCE_END)

    # ---- sound
    def loud_at(self, a: float, b: float) -> float:
        i, j = int((a - self.t0) / 0.25), int(np.ceil((b - self.t0) / 0.25))
        i, j = max(0, i), min(len(self.db), max(i + 1, j))
        return float(self.db[i:j].max()) if j > i else -99.0

    def laughing(self, a: float, b: float) -> bool:
        if self.laugh is None:
            return False
        i, j = max(0, int(a)), min(len(self.laugh), int(np.ceil(b)))
        return bool(j > i and float(self.laugh[i:j].max()) >= 0.35)


def _laughter(project: Project) -> np.ndarray | None:
    path = project.cache_dir / "signals" / "laughter.npz"
    if not path.is_file():
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            return np.array(data["scores"], dtype=np.float32)
    except Exception:  # noqa: BLE001
        return None


def around(project: Project, cand: dict, start: float, end: float, mode: str, pad: float = 20.0) -> Around:
    from . import audio as audio_mod
    from .edit.plan import transcript_words

    meta = project.load_meta()
    duration = float(meta.get("duration") or end + pad)
    a, b = max(0.0, start - pad), min(duration, end + pad)
    words, _lang = transcript_words(project, a, b, voices=False)
    db = np.full(1, -60.0, np.float32)
    if project.audio_path.is_file():
        x = audio_mod.read_wav_segment(project.audio_path, a, b)
        hop = int(audio_mod.SAMPLE_RATE * 0.25)
        m = len(x) // hop
        if m:
            fr = x[: m * hop].reshape(m, hop)
            db = (10 * np.log10(np.mean(fr ** 2, axis=1) + 1e-10)).astype(np.float32)
    base = float(np.median(db)) if len(db) else -60.0
    events = []
    for r in cand.get("reasons") or []:
        code = str(r.get("code") or "")
        try:
            t, s = float(r.get("t")), float(r.get("strength") or 0)
        except (TypeError, ValueError):
            continue
        if s >= EVENT_CODES_MIN and code.startswith(MOMENT_PREFIXES):
            events.append({"t": t, "code": code})
    events.sort(key=lambda e: e["t"])
    return Around(words, a, db, _laughter(project), base, duration, mode, events)


# ===================================================================== snapping


def snap_start(ar: Around, t: float) -> float:
    """t -> just before a word starts (never inside a word)."""
    i = ar.word_at(t)
    if i is None:
        j = ar.index_at_or_after(t)
        if j < len(ar.words) and ar.words[j]["start"] - t < 0.25:
            i = j
    if i is None:
        prev = ar.index_at_or_after(t) - 1
        lo = ar.words[prev]["end"] + 0.02 if prev >= 0 else 0.0
        return round(max(t, lo, 0.0), 2)
    w = ar.words[i]
    prev_end = ar.words[i - 1]["end"] + 0.02 if i > 0 else 0.0
    return round(max(w["start"] - 0.2, prev_end, 0.0), 2)


def snap_end(ar: Around, t: float) -> float:
    """t -> just after a word ends."""
    i = ar.word_at(t)
    if i is None:
        j = ar.index_at_or_after(t) - 1
        if j >= 0 and t - ar.words[j]["end"] < 0.2:
            i = j
    if i is None:
        nxt = ar.index_at_or_after(t)
        hi = ar.words[nxt]["start"] - 0.02 if nxt < len(ar.words) else ar.duration
        return round(min(t, hi, ar.duration), 2)
    w = ar.words[i]
    nxt = ar.words[i + 1]["start"] - 0.02 if i + 1 < len(ar.words) else ar.duration
    return round(min(w["end"] + 0.3, max(nxt, w["end"]), ar.duration), 2)


def sentence_start(ar: Around, t: float, max_back: float) -> float:
    """The start of the sentence that is running at t (or t when it starts there)."""
    i = ar.word_at(t)
    if i is None:
        i = ar.index_at_or_after(t)
    if i >= len(ar.words):
        return t
    j = i
    while j > 0:
        prev = ar.words[j - 1]
        gap = ar.words[j]["start"] - prev["end"]
        if ar.ends(prev) or gap >= 1.2 or t - prev["start"] > max_back:
            break
        j -= 1
    return min(t, ar.words[j]["start"])


def sentence_end(ar: Around, t: float, max_fwd: float) -> float:
    """The end of the sentence that is running at t."""
    i = ar.word_at(t)
    if i is None:
        i = ar.index_at_or_after(t) - 1
    if i < 0:
        return t
    j = i
    while j + 1 < len(ar.words):
        w, nxt = ar.words[j], ar.words[j + 1]
        if ar.ends(w) or nxt["start"] - w["end"] >= 1.2 or nxt["end"] - t > max_fwd:
            break
        j += 1
    return max(t, ar.words[j]["end"])


def _mid_sentence_start(ar: Around, s: float) -> bool:
    i = ar.word_at(s + 0.05)
    if i is None:
        i = ar.index_at_or_after(s)
    if i <= 0 or i >= len(ar.words):
        return False
    w, prev = ar.words[i], ar.words[i - 1]
    if w["start"] - s > 1.5:  # the clip starts in a pause: nobody is talking
        return False
    return not ar.ends(prev) and w["start"] - prev["end"] < 0.7


def _mid_sentence_end(ar: Around, e: float) -> bool:
    i = ar.index_at_or_after(e) - 1
    if i < 0 or i + 1 >= len(ar.words):
        return False
    w, nxt = ar.words[i], ar.words[i + 1]
    if e - w["end"] > 1.5:
        return False
    return not ar.ends(w) and nxt["start"] - w["end"] < 0.5 and nxt["start"] < e + 1.0


# ===================================================================== the context guard


def guard(ar: Around, cand: dict, start: float, end: float, lo: float, hi: float, clip_max: float) -> tuple[float, float, list[str]]:
    """(start, end, reasons) with the setup and the payoff inside. lo / hi: how far it may go
    (the neighbouring clips, the video)."""
    why: list[str] = []
    s, e = float(start), float(end)
    mode = ar.mode
    lo, hi = max(lo, s - MAX_BACK), min(hi, e + MAX_FWD)
    llm = cand.get("llm") or {}
    if mode != "music":
        # -- setup
        if _mid_sentence_start(ar, s):
            ns = sentence_start(ar, s + 0.05, 6.0)
            if lo <= ns < s - 0.2:
                s = ns
                why.append("setup_sentence")
        first = next((ev["t"] for ev in ar.events if s - 1.0 <= ev["t"] <= e), None)
        need = LEAD.get(mode, 2.0)
        if first is not None and first - s < need:
            ns = sentence_start(ar, max(lo, first - need), 3.0)
            ns = max(lo, ns)
            if ns < s - 0.2:
                s = ns
                why.append("setup_lead")
        if llm and llm.get("self_contained") is False and float(llm.get("start_shift_s") or 0) >= 0 \
                and "setup_sentence" not in why:
            ns = max(lo, sentence_start(ar, max(lo, s - 4.0), 3.0))
            if ns < s - 0.5:
                s = ns
                why.append("ai_setup")
        # -- payoff
        last = next((ev["t"] for ev in reversed(ar.events) if s <= ev["t"] <= e + 1.0), None)
        tail = TAIL.get(mode, 1.0)
        if last is not None and e - last < tail:
            ne = min(hi, last + tail)
            if ne > e + 0.2:
                e = ne
                why.append("payoff_event")
        # the laugh / the reaction calms down first
        loud_thr = ar.baseline + 8.0
        reacting = ar.laughing(e - 1.0, e + 0.25) or ar.loud_at(e - 0.75, e) > loud_thr
        if reacting:
            ne = e
            while ne < hi and (ar.laughing(ne - 0.5, ne + 0.5) or ar.loud_at(ne - 0.5, ne + 0.25) > loud_thr):
                ne += 0.5
            ne = min(hi, ne + 0.5)  # a moment of calm after it
            if ne > e + 0.4:
                e = ne
                why.append("payoff_reaction")
        if _mid_sentence_end(ar, e):
            ne = min(hi, sentence_end(ar, e - 0.05, 5.0))
            if ne > e + 0.2:
                e = ne
                why.append("payoff_sentence")
        if llm and llm.get("self_contained") is False and float(llm.get("end_shift_s") or 0) <= 0 \
                and not any(w.startswith("payoff") for w in why):
            ne = min(hi, sentence_end(ar, e + 2.0, 3.0))
            if ne > e + 0.5:
                e = ne
                why.append("ai_payoff")
    s, e = snap_start(ar, max(lo, s)), snap_end(ar, min(hi, e))
    limit = max(clip_max, end - start)
    if e - s > limit:  # the guard never makes a clip longer than the mode allows:
        # the reaction tail goes first (never before the last big moment + a beat), then the start
        last = next((ev["t"] for ev in reversed(ar.events) if s <= ev["t"] <= e), None)
        goal = s + limit
        if last is not None and mode != "music":
            goal = max(goal, last + TAIL.get(mode, 1.0))
        e = snap_end(ar, min(e, goal))
        if e - s > limit:
            s = snap_start(ar, e - limit)
    s, e = max(lo, s), min(hi, e)
    if e - s < 3.0:
        return round(start, 2), round(end, 2), []
    return round(s, 2), round(e, 2), why


def limits(project: Project, cand: dict, hl: dict, duration: float) -> tuple[float, float]:
    """How far a clip may grow: up to its neighbours (0.5 s apart) and the video's ends."""
    lo, hi = 0.0, duration
    for o in hl.get("candidates") or []:
        if o["id"] == cand["id"]:
            continue
        if o["end"] <= cand["start"] + 0.01:
            lo = max(lo, float(o["end"]) + 0.5)
        elif o["start"] >= cand["end"] - 0.01:
            hi = min(hi, float(o["start"]) - 0.5)
    return lo, hi


# ===================================================================== one-tap nudges


NUDGES = ("earlier", "later", "short", "long")


def nudge(ar: Around, cand: dict, start: float, end: float, action: str, tgt: dict,
          lo: float, hi: float) -> tuple[float, float]:
    """The card's one-tap buttons: start 3 s earlier, end 3 s later, short / long version."""
    s, e = float(start), float(end)
    lo, hi = max(0.0, lo), min(ar.duration, hi)
    if action == "earlier":
        t = max(lo, s - NUDGE_S)
        ns = sentence_start(ar, t + 0.05, 1.5)  # a sentence start nearby, if there is one
        s = snap_start(ar, max(lo, ns if t - ns <= 1.5 else t))
    elif action == "later":
        t = min(hi, e + NUDGE_S)
        ne = sentence_end(ar, t - 0.05, 1.5)
        e = snap_end(ar, min(hi, ne if ne - t <= 1.5 else t))
    elif action == "short":
        dur = e - s
        goal = min(tgt["max"], max(tgt["min"], dur - 6.0)) if dur > tgt["min"] + 2 else max(6.0, dur - 4.0)
        first = next((ev["t"] for ev in ar.events if s <= ev["t"] <= e), None)
        last = next((ev["t"] for ev in reversed(ar.events) if s <= ev["t"] <= e), None)
        need = LEAD.get(ar.mode, 2.0)
        # cut the slow lead-in first (keep the setup before the first big moment) ...
        latest_start = (first - need) if first is not None else s + (dur - goal)
        ns = min(max(s, e - goal), max(s, latest_start))
        if ns > s + 0.3:
            s = snap_start(ar, ns)
        # ... then the end (never before the last big moment + its reaction)
        if e - s > goal + 0.5:
            floor_e = (last + TAIL.get(ar.mode, 1.0)) if last is not None else s + goal
            e = snap_end(ar, max(s + goal, min(e, floor_e)) if floor_e > s + goal else s + goal)
    elif action == "long":
        t = max(lo, s - 5.0)
        s = snap_start(ar, max(lo, sentence_start(ar, t + 0.05, 2.0)))
        te = min(hi, e + 3.0)
        e = snap_end(ar, min(hi, sentence_end(ar, te - 0.05, 2.0)))
    s, e = max(lo, s), min(hi, e)  # a snapped word end may not run into the neighbour
    if e - s > 180:
        e = s + 180
    if e - s < 3.0:
        return round(start, 2), round(end, 2)
    return round(s, 2), round(e, 2)


# ===================================================================== per clip


def base_of(cand: dict) -> list[float]:
    return [round(float(cand["start"]), 2), round(float(cand["end"]), 2)]


def needs_shape(shape: dict | None, cand: dict) -> bool:
    return not shape or shape.get("v") != SHAPE_VERSION or shape.get("base") != base_of(cand)


def _close(a, b) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) < 0.05


def is_auto_trim(edit: dict | None, shape: dict | None, cand: dict) -> bool:
    """Is the clip's current trim still the one shaping wrote (or none at all)?"""
    edit = edit or {}
    cs, ce = edit.get("start"), edit.get("end")
    if not shape:
        return cs is None and ce is None
    s = cs if cs is not None else cand["start"]
    e = ce if ce is not None else cand["end"]
    return _close(s, shape.get("start")) and _close(e, shape.get("end"))


def shape_clip(project: Project, cand: dict, hl: dict, mode: str) -> dict:
    """The context guard + length target for one clip (the hook check adds to it)."""
    from .highlights.modes import get_mode

    duration = float(project.load_meta().get("duration") or cand["end"])
    lo, hi = limits(project, cand, hl, duration)
    ar = around(project, cand, float(cand["start"]), float(cand["end"]), mode)
    s, e, why = guard(ar, cand, float(cand["start"]), float(cand["end"]), lo, hi, get_mode(mode).clip_max)
    tgt = target(mode, cand)
    return {"v": SHAPE_VERSION, "base": base_of(cand), "start": s, "end": e, "why": why, "target": tgt,
            "guard": {"start": round(s - float(cand["start"]), 2), "end": round(e - float(cand["end"]), 2)}}


def edit_for(cand: dict, start: float, end: float, old: dict | None) -> dict:
    """review.json edit with this trim (None = the found cut), the rest of the edit kept."""
    cur = dict(old or {})
    cur["start"] = None if _close(start, cand["start"]) else round(float(start), 2)
    cur["end"] = None if _close(end, cand["end"]) else round(float(end), 2)
    return cur


# ===================================================================== explainable picks


CHIP_ORDER = ("marker", "lol_pentakill", "lol_quadrakill", "lol_baron_steal", "df_extracted", "lol_triplekill",
              "lol_dragon_steal", "df_multikill", "lol_ace", "lol_shutdown", "lol_doublekill", "df_revenge",
              "lol_first_blood", "laughter", "chat_spike", "chat_reactions", "df_kill", "lol_kill", "keyword",
              "scream", "shouting", "cheering", "llm_explanation", "steady_explanation", "chorus", "drop",
              "pause_then_burst", "loudness_spike", "fast_speech", "df_death", "lol_death", "df_extract_failed")


def reason_chips(cand: dict, n: int = 3) -> list[dict]:
    """1-3 plain reasons why this clip was picked (strongest kind first): {"code", "value", "count"}."""
    best: dict[str, dict] = {}
    for r in cand.get("reasons") or []:
        code = str(r.get("code") or "")
        if code not in CHIP_ORDER:
            continue
        cur = best.get(code)
        if cur is None or float(r.get("strength") or 0) > float(cur.get("strength") or 0):
            best[code] = r
    if "lol_kill" in best and any(k in best for k in ("lol_doublekill", "lol_triplekill", "lol_quadrakill", "lol_pentakill")):
        best.pop("lol_kill")
    if "df_kill" in best and "df_multikill" in best:
        best.pop("df_kill")
    if "loudness_spike" in best and ("shouting" in best or "scream" in best):
        best.pop("loudness_spike")
    out = []
    for code in sorted(best, key=CHIP_ORDER.index)[:n]:
        r = best[code]
        chip: dict = {"code": code}
        if code in ("keyword", "df_multikill") and r.get("value"):
            chip["value"] = str(r["value"])[:24]
        if r.get("count") and int(r["count"]) > 1 and code not in ("keyword",):
            chip["count"] = int(r["count"])
        out.append(chip)
    return out
