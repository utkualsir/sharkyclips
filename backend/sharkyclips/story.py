"""Story clips: 2-4 moments from across the whole stream, cut into ONE 30-60 s Short.

  propose()   the local AI reads every candidate (what happens, type, scores, the words) and
              proposes 2-3 mini stories: "fail -> comeback", "setup -> payoff", "running joke",
              "escalation". Without the AI, simple rules find the same shapes from the
              moment types and game events. Each story: a title, a one-line pitch, 2-4 segments
              in the order they happened, optional short text cards between the acts.
  finalize()  the rules every story keeps: segments start and end on word boundaries, never
              overlap and never repeat a moment, the whole story is 30-60 s. A stream with
              fewer than two good moments gets no story, with the reason.
  publish     its own titles, description, hashtags, cover prompt and hook text.
  render()    one 9:16 Short: quick transitions (a short white flash between moments, a fade
              into a text card), captions that continue across the segments, every segment
              brought to the same loudness before the mix is normalized to -14 LUFS.

Stories live in <project>/stories.json; renders in <project>/stories/<id>.mp4.
"""

from __future__ import annotations

import os
import secrets
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from . import config
from .errors import SharkyClipsError, require_tool
from .project import Project, read_json, write_json_atomic

ARCS = ("fail_comeback", "setup_payoff", "running_joke", "escalation", "other")
MIN_TOTAL, MAX_TOTAL = 30.0, 60.0
SEG_MIN, SEG_MAX = 5.0, 25.0
GOOD = 30  # a moment counts when its viral score (or, before the AI ran, its hype score) reaches this
TRANSITION = 0.25  # seconds of overlap between two pieces
CARD_SECONDS = 0.9
MAX_STORIES = 3
STORY_VERSION = 1
MAX_GAIN_DB = 15.0  # per-segment loudness correction (quieter / louder moments meet in the middle)

FAIL_CODES = ("df_death", "df_extract_failed", "lol_death", "lol_defeat")
WIN_CODES = ("df_multikill", "df_kill", "df_revenge", "df_extracted", "lol_pentakill", "lol_quadrakill",
             "lol_triplekill", "lol_doublekill", "lol_kill", "lol_shutdown", "lol_ace", "lol_victory",
             "lol_baron_steal", "lol_dragon_steal")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path_of(project: Project) -> Path:
    return project.dir / "stories.json"


def load(project: Project) -> dict:
    p = path_of(project)
    try:
        data = read_json(p) if p.is_file() else {}
    except Exception:  # noqa: BLE001
        data = {}
    return {"version": STORY_VERSION, "stories": list(data.get("stories") or []), "reason": data.get("reason"),
            "good": data.get("good"), "created_at": data.get("created_at"), "source": data.get("source")}


def save(project: Project, data: dict) -> dict:
    write_json_atomic(path_of(project), {**data, "version": STORY_VERSION})
    return load(project)


def get(project: Project, sid: str) -> dict:
    s = next((x for x in load(project)["stories"] if x["id"] == sid), None)
    if s is None:
        raise SharkyClipsError("This story doesn't exist any more.", "Ask for new story ideas.")
    return s


# --------------------------------------------------------------------- moments


def quality(c: dict) -> float:
    pub = c.get("publish") or {}
    if pub.get("viral_score") is not None:
        return float(pub["viral_score"])
    return float(c.get("hype_score") or 0)


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def good_moments(cands: list[dict]) -> list[dict]:
    """Candidates worth putting in a story, in stream order. Of two that overlap by more than
    a third, only the better one stays (a moment is never used twice)."""
    out: list[dict] = []
    for c in sorted(cands, key=lambda c: -quality(c)):
        if quality(c) < GOOD:
            continue
        rng = (float(c["start"]), float(c["end"]))
        if any(_overlap(rng, (o["start"], o["end"])) > (rng[1] - rng[0]) / 3 for o in out):
            continue
        out.append(c)
    return sorted(out, key=lambda c: c["start"])


def snap(words: list[dict], start: float, end: float, lo: float, hi: float) -> tuple[float, float]:
    """Start right before a word, end right after one: never inside a word."""
    words = sorted(words, key=lambda w: w["start"])
    prev_end = lo
    for w in words:
        if w["start"] < start < w["end"]:
            start = max(prev_end + 0.02, w["start"] - 0.08)
            break
        if w["end"] <= start:
            prev_end = w["end"]
    for i, w in enumerate(words):
        if w["start"] < end < w["end"]:
            nxt = words[i + 1]["start"] if i + 1 < len(words) else hi
            end = min(w["end"] + 0.12, nxt - 0.02) if nxt > w["end"] + 0.04 else w["end"] + 0.01
            break
    start, end = max(lo, start), min(hi, end)
    return round(start, 3), round(end, 3)


def inside_word(words: list[dict], t: float) -> bool:
    return any(w["start"] + 0.02 < t < w["end"] - 0.02 for w in words)


def _fit(c: dict, budget: float, words: list[dict], src_dur: float) -> tuple[float, float]:
    """The part of a candidate that fits `budget` seconds, around its peak, on word boundaries."""
    s, e = float(c["start"]), float(c["end"])
    if e - s > budget:
        peak = float(c.get("peak") or (s + e) / 2)
        s = max(s, peak - 0.45 * budget)
        e = s + budget
        if e > float(c["end"]):
            e = float(c["end"])
            s = e - budget
    return snap(words, s, e, max(0.0, float(c["start"]) - 2.0), min(src_dur or e + 2.0, float(c["end"]) + 2.0))


def finalize(raw: dict, cands: dict[str, dict], words: list[dict], src_dur: float,
             keep_order: bool = False) -> dict | None:
    """Apply the story rules to a proposal ({"title", "arc", "pitch", "segments": [{"clip",
    "card", "role"}]}). Returns None when no valid story is left."""
    segs: list[dict] = []
    seen: set[str] = set()
    for s in raw.get("segments") or []:
        cid = str(s.get("clip") or s.get("cid") or "")
        if cid in seen or cid not in cands:
            continue
        seen.add(cid)
        c = cands[cid]
        segs.append({"cid": cid, "start": float(s.get("start", c["start"])), "end": float(s.get("end", c["end"])),
                     "card": " ".join(str(s.get("card") or "").split())[:40], "role": str(s.get("role") or "")[:60],
                     "rank": c.get("rank")})
    if not keep_order:
        segs.sort(key=lambda s: s["start"])
    # Lengths: each segment is its candidate, capped; then the whole story into 30-60 s.
    n = len(segs)
    if n < 2:
        return None
    cards = sum(1 for k, s in enumerate(segs) if k and s["card"])
    room = MAX_TOTAL - cards * CARD_SECONDS + (n - 1 + cards) * TRANSITION
    natural = [min(SEG_MAX, s["end"] - s["start"]) for s in segs]
    scale = min(1.0, room / max(1e-6, sum(natural)))
    for s, nat in zip(segs, natural):
        budget = max(SEG_MIN, nat * scale)
        if s["end"] - s["start"] > budget + 0.01 or inside_word(words, s["start"]) or inside_word(words, s["end"]):
            c = {**cands[s["cid"]], "start": s["start"], "end": s["end"]}
            s["start"], s["end"] = _fit(c, budget, words, src_dur)
    # No overlaps, no repeated moments (in time order, whatever the play order is).
    by_time = sorted(segs, key=lambda s: s["start"])
    drop: set[int] = set()
    for a, b in zip(by_time, by_time[1:]):
        if id(a) in drop:
            continue
        if b["start"] < a["end"]:
            b["start"], _e = snap(words, a["end"] + 0.05, b["end"], a["end"] + 0.02, b["end"])
            if b["end"] - b["start"] < SEG_MIN:
                drop.add(id(b))
    segs = [s for s in segs if id(s) not in drop]
    if len(segs) < 2:
        return None
    total = duration_of(segs)
    if total < MIN_TOTAL:  # a little more of each moment, within its candidate (+-4 s)
        need = MIN_TOTAL - total + 0.3
        for s in segs:
            c = cands[s["cid"]]
            lo, hi = max(0.0, float(c["start"]) - 4.0), min(src_dur or 1e9, float(c["end"]) + 4.0)
            others = [o for o in segs if o is not s]
            for o in others:  # never grow into another segment
                if o["end"] <= s["start"]:
                    lo = max(lo, o["end"] + 0.05)
                if o["start"] >= s["end"]:
                    hi = min(hi, o["start"] - 0.05)
            grow = need / len(segs)
            s["start"], s["end"] = snap(words, max(lo, s["start"] - grow / 2), min(hi, s["end"] + grow / 2), lo, hi)
        total = duration_of(segs)
    if total < MIN_TOTAL - 0.5 or total > MAX_TOTAL + 0.5:
        return None
    arc = raw.get("arc") if raw.get("arc") in ARCS else "other"
    return {"id": raw.get("id") or "s" + secrets.token_hex(3), "title": " ".join(str(raw.get("title") or "").split())[:80],
            "arc": arc, "pitch": " ".join(str(raw.get("pitch") or "").split())[:160],
            "segments": [{k: s[k] for k in ("cid", "start", "end", "card", "role", "rank")} for s in segs],
            "cards": bool(raw.get("cards", True)), "duration": round(total, 2),
            "publish": raw.get("publish"), "created_at": raw.get("created_at") or _now(),
            "render": raw.get("render")}


def duration_of(segs: list[dict], cards: bool = True) -> float:
    """Length of the finished story: segments + cards - the transition overlaps."""
    pieces = [s["end"] - s["start"] for s in segs]
    n_cards = sum(1 for k, s in enumerate(segs) if k and cards and s.get("card"))
    return round(sum(pieces) + n_cards * CARD_SECONDS - (len(pieces) + n_cards - 1) * TRANSITION, 2)


# --------------------------------------------------------------------- proposals


def _codes(c: dict) -> set[str]:
    return {str(r.get("code")) for r in c.get("reasons") or []}


def _type(c: dict) -> str:
    return str((c.get("llm") or {}).get("moment_type") or "")


def heuristic(good: list[dict]) -> list[dict]:
    """Stories without the AI: fail -> comeback, setup -> payoff, escalation."""
    out: list[dict] = []
    fails = [c for c in good if _type(c) == "fail" or _codes(c) & set(FAIL_CODES)]
    wins = [c for c in good if _type(c) in ("skill", "exciting") or _codes(c) & set(WIN_CODES)]
    for f in fails:
        later = [w for w in wins if w["start"] > f["end"]]
        if later:
            w = max(later, key=quality)
            out.append({"arc": "fail_comeback", "title": "From fail to comeback", "pitch": "",
                        "segments": [{"clip": f["id"], "card": ""}, {"clip": w["id"], "card": "Later…"}]})
            break
    best = max(good, key=quality)
    before = [c for c in good if c["end"] <= best["start"] and c is not best]
    if before:
        setup = before[-1]
        out.append({"arc": "setup_payoff", "title": "It all pays off", "pitch": "",
                    "segments": [{"clip": setup["id"], "card": ""}, {"clip": best["id"], "card": ""}]})
    if len(good) >= 3:
        top = sorted(sorted(good, key=lambda c: -quality(c))[:3], key=lambda c: c["start"])
        out.append({"arc": "escalation", "title": "It only gets better", "pitch": "",
                    "segments": [{"clip": c["id"], "card": ""} for c in top]})
    return out


def _schema(ids: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "stories": {"type": "array", "minItems": 0, "maxItems": MAX_STORIES, "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 3, "maxLength": 80},
                    "arc": {"type": "string", "enum": list(ARCS)},
                    "pitch": {"type": "string", "minLength": 10, "maxLength": 160},
                    "segments": {"type": "array", "minItems": 2, "maxItems": 4, "items": {
                        "type": "object",
                        "properties": {"clip": {"type": "string", "enum": ids},
                                       "role": {"type": "string", "maxLength": 60},
                                       "card": {"type": "string", "maxLength": 40}},
                        "required": ["clip", "role", "card"]}},
                },
                "required": ["title", "arc", "pitch", "segments"]}},
            "none_reason": {"type": "string", "maxLength": 240},
        },
        "required": ["stories", "none_reason"],
    }


def _moment_line(c: dict) -> str:
    from .textutil import mmss

    llm = c.get("llm") or {}
    events = ", ".join(sorted({str(r.get("code")) for r in c.get("reasons") or []
                               if str(r.get("code", "")).startswith(("df_", "lol_"))}))
    return (f"- {c['id']} · at {mmss(c['start'])} · {round(c['end'] - c['start'])} s · "
            f"{llm.get('moment_type') or 'unknown'} · score {round(quality(c))}"
            + (f" · events: {events}" if events else "")
            + f"\n  what happens: {(llm.get('what_happens') or '-')[:260]}"
            + f"\n  says: {(c.get('text') or '')[:220]}")


def ai_proposals(model, project: Project, good: list[dict], lang: str) -> tuple[list[dict], str]:
    from .analyze import SYSTEM, has_profanity, lang_name

    meta = project.load_meta()
    ids = [c["id"] for c in good]
    order = {c["id"]: i for i, c in enumerate(good)}
    prompt = (f"Stream: {meta.get('title') or project.id}\n\nThe best moments of this stream, in the order they "
              f"happened:\n" + "\n".join(_moment_line(c) for c in good) + "\n\n"
              "Find up to 3 mini stories. A story connects 2-4 of these moments from different parts of the "
              "stream into ONE 30-60 second Short with a beginning, a turn and a payoff that a viewer understands "
              "without the rest of the stream. Arcs: fail_comeback (a failure, later redemption), setup_payoff "
              "(something said or done early pays off later), running_joke (the same joke, phrase or bit comes "
              "back), escalation (it keeps getting bigger). Use only the listed ids, each at most once per story, "
              "in the order they happened. No two stories with the same moments. "
              f"title and pitch (one line: why this is a story) in {lang_name(lang)}. "
              f"card: an optional 1-4 word text card shown BEFORE that segment in {lang_name(lang)} "
              "(like 'Ten minutes later'), empty for the first segment and when not needed. role: the segment's "
              "part in the story (setup, fail, turn, payoff...). Only real stories from what the lines show; "
              "if there is none, return fewer (or zero) and say why in none_reason.")

    def check(d: dict) -> list[str]:
        problems = []
        for i, s in enumerate(d["stories"]):
            seq = [x["clip"] for x in s["segments"]]
            if len(set(seq)) != len(seq):
                problems.append(f"story {i + 1} uses a moment twice")
            if [order[x] for x in seq] != sorted(order[x] for x in seq):
                problems.append(f"story {i + 1}: segments must be in the order they happened")
            if has_profanity(s["title"]) or has_profanity(s["pitch"]):
                problems.append(f"story {i + 1}: title / pitch must be advertiser-friendly")
        sets = [frozenset(x["clip"] for x in s["segments"]) for s in d["stories"]]
        if len(set(sets)) != len(sets):
            problems.append("two stories use the same moments")
        return problems

    # Soft rules: the model gets one chance to fix them; what is left is cleaned up here and by
    # finalize() (stream order, no repeated moments). One bad story never sinks the others.
    d = model.json(SYSTEM, prompt, _schema(ids), soft=check, temperature=0.5, num_predict=1400)
    d.pop("_soft_errors", None)
    stories = []
    for st in d["stories"]:
        # Blank only the field with the swear word; the publish package writes a clean title.
        st = {**st, **{k: "" for k in ("title", "pitch") if has_profanity(st[k])}}
        stories.append(st)
    return stories, d.get("none_reason") or ""


PUBLISH_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {"type": "array", "minItems": 4, "maxItems": 6, "items": {"type": "string", "minLength": 8, "maxLength": 90}},
        "description": {"type": "string", "minLength": 40, "maxLength": 600},
        "hashtags": {"type": "array", "minItems": 5, "maxItems": 10, "items": {"type": "string", "minLength": 2, "maxLength": 40}},
        "hook_text": {"type": "string", "minLength": 2, "maxLength": 60},
        "cover_scene": {"type": "string", "minLength": 10, "maxLength": 350},
        "cover_text": {"type": "string", "minLength": 1, "maxLength": 32},
    },
    "required": ["titles", "description", "hashtags", "hook_text", "cover_scene", "cover_text"],
}


def ai_publish(model, project: Project, story: dict, cands: dict[str, dict], lang: str) -> dict:
    from .analyze import COVER_STYLE, SYSTEM, clean_hashtags, has_profanity, lang_name

    meta = project.load_meta()
    acts = "\n".join(f"{k + 1}. ({s.get('role') or 'part'}) {((cands[s['cid']].get('llm') or {}).get('what_happens') or '')[:240]}"
                     for k, s in enumerate(story["segments"]))
    prompt = (f"Stream: {meta.get('title') or project.id}\nThis Short tells a story ({story['arc'].replace('_', ' ')}): "
              f"{story['pitch']}\nIts parts:\n{acts}\n\nWrite in {lang_name(lang)}: 4-6 different titles for the "
              "Short (YouTube Shorts / TikTok, curious but honest, no clickbait lies), a 2-3 sentence description "
              "that teases the story without spoiling the payoff, 5-10 hashtags, an on-screen hook text for the "
              "first seconds (max 6 words), and a thumbnail: the scene and a short cover text.")

    def check(d: dict) -> list[str]:
        bad = [t for t in d["titles"] + d["hashtags"] + [d["hook_text"], d["cover_text"]] if has_profanity(t)]
        return [f"not advertiser-friendly: {b}" for b in bad[:3]]

    d = model.json(SYSTEM, prompt, PUBLISH_SCHEMA, check=check, temperature=0.6, num_predict=1200)
    topic = next(((cands[s["cid"]].get("llm") or {}).get("game_or_topic") for s in story["segments"]
                  if (cands[s["cid"]].get("llm") or {}).get("game_or_topic")), "") or ""
    return {"titles": [" ".join(t.split()) for t in d["titles"]], "description": d["description"].strip(),
            "hashtags": clean_hashtags(d["hashtags"], topic), "hook_text": " ".join(d["hook_text"].split()),
            "cover_text": d["cover_text"].strip(),
            "cover_prompt": f"{d['cover_scene'].strip().rstrip('.')}. " + COVER_STYLE.format(text=d["cover_text"].strip()),
            "language": lang, "source": "ai"}


def fallback_publish(story: dict, cands: dict[str, dict], lang: str) -> dict:
    """A package from the segments' own ones (no AI): honest, maybe less polished."""
    pubs = [cands[s["cid"]].get("publish") or {} for s in story["segments"]]
    titles = []
    for p in pubs:
        for t in p.get("titles") or []:
            if t not in titles:
                titles.append(t)
    tags: list[str] = []
    for p in pubs:
        for h in p.get("hashtags") or []:
            if h not in tags:
                tags.append(h)
    best = max(story["segments"], key=lambda s: quality(cands[s["cid"]]))
    bp = cands[best["cid"]].get("publish") or {}
    title = story.get("title") or (titles[0] if titles else "")
    return {"titles": ([title] if title else []) + [t for t in titles if t != title][:4],
            "description": " ".join(x for x in [story.get("pitch") or "", " ".join(tags[:3])] if x).strip(),
            "hashtags": tags[:10], "hook_text": (pubs[0].get("hook_text") or title)[:60],
            "cover_text": bp.get("cover_text") or "", "cover_prompt": bp.get("cover_prompt") or "",
            "language": pubs[0].get("language") or lang, "source": "clips"}


def propose(project: Project, model=None, lang: str | None = None,
            on_progress: Callable[[str], None] | None = None) -> dict:
    """New story ideas for the project (replaces the old ones; rendered ones are kept)."""
    from . import languages
    from .web import state

    hl = state.load_highlights(project)
    if not hl:
        raise SharkyClipsError("Find the highlights first; stories are built from them.")
    lang = languages.require(lang or (hl.get("analysis") or {}).get("language") or config.get("output_language") or "en").code
    cands = {c["id"]: c for c in hl.get("candidates", [])}
    good = good_moments(list(cands.values()))
    old = load(project)
    kept = [s for s in old["stories"] if s.get("render")]  # rendered stories stay
    if len(good) < 2:
        return save(project, {"stories": kept, "reason": "too_few_moments", "good": len(good), "created_at": _now(),
                              "source": "rules"})
    material = sum(min(SEG_MAX, c["end"] - c["start"]) for c in good)
    if material + 8 * len(good) < MIN_TOTAL:
        return save(project, {"stories": kept, "reason": "too_short", "good": len(good), "created_at": _now(),
                              "source": "rules"})
    words = _all_words(project)
    src_dur = float(project.load_meta().get("duration") or 0)
    none_reason = ""
    source = "rules"
    raw: list[dict] = []
    if model is not None:
        if on_progress:
            on_progress("story_ideas")
        try:
            raw, none_reason = ai_proposals(model, project, good, lang)
            source = "ai"
        except SharkyClipsError:  # the AI kept failing: the rules still find the classic shapes
            raw, model = heuristic(good), None
    else:
        raw = heuristic(good)
    stories: list[dict] = []
    sets: list[frozenset] = [frozenset(s["cid"] for s in k["segments"]) for k in kept]
    for r in raw:
        st = finalize(r, cands, words, src_dur)
        if st is None:
            continue
        key = frozenset(s["cid"] for s in st["segments"])
        if key in sets:
            continue
        sets.append(key)
        stories.append(st)
        if len(stories) >= MAX_STORIES:
            break
    for st in stories:
        if on_progress:
            on_progress("story_publish")
        try:
            st["publish"] = ai_publish(model, project, st, cands, lang) if model is not None else None
        except SharkyClipsError:
            st["publish"] = None
        if not st["publish"]:
            st["publish"] = fallback_publish(st, cands, lang)
        if not st["title"]:
            st["title"] = (st["publish"]["titles"] or [""])[0]
    reason = None if stories else "no_arc"
    return save(project, {"stories": kept + stories, "reason": reason, "none_reason": none_reason or None,
                          "good": len(good), "created_at": _now(), "source": source})


def _all_words(project: Project) -> list[dict]:
    if not project.transcript_path.is_file():
        return []
    tr = read_json(project.transcript_path)
    return [{"start": float(w["start"]), "end": float(w["end"]), "word": w["word"].strip()}
            for seg in tr.get("segments", []) for w in seg.get("words", []) if w["word"].strip()]


def update(project: Project, sid: str, changes: dict) -> dict:
    """Reorder / remove segments, cards on/off, title. Keeps the story rules (else an error)."""
    data = load(project)
    from .web import state

    hl = state.load_highlights(project) or {}
    cands = {c["id"]: c for c in hl.get("candidates", [])}
    words = _all_words(project)
    src_dur = float(project.load_meta().get("duration") or 0)
    out = []
    found = None
    for s in data["stories"]:
        if s["id"] != sid:
            out.append(s)
            continue
        new = dict(s)
        if "segments" in changes:
            by_cid = {x["cid"]: x for x in s["segments"]}
            segs = []
            for x in changes["segments"] or []:
                cid = str(x.get("cid") if isinstance(x, dict) else x)
                if cid in by_cid:
                    segs.append({**by_cid[cid], **({"card": " ".join(str(x.get("card") or "").split())[:40]}
                                                   if isinstance(x, dict) and "card" in x else {})})
            new["segments"] = [{"clip": x["cid"], **x} for x in segs]
        else:
            new["segments"] = [{"clip": x["cid"], **x} for x in s["segments"]]
        if "cards" in changes:
            new["cards"] = bool(changes["cards"])
        if "title" in changes:
            new["title"] = " ".join(str(changes["title"] or "").split())[:80]
        fixed = finalize(new, cands, words, src_dur, keep_order=True)
        if fixed is None:
            raise SharkyClipsError("A story needs at least two moments and 30-60 seconds.",
                                   "Put a moment back, or ask for new story ideas.")
        fixed["render"] = None  # changed: the old render no longer matches
        found = fixed
        out.append(fixed)
    if found is None:
        raise SharkyClipsError("This story doesn't exist any more.")
    save(project, {**data, "stories": out})
    return found


def delete(project: Project, sid: str) -> bool:
    data = load(project)
    keep = [s for s in data["stories"] if s["id"] != sid]
    if len(keep) == len(data["stories"]):
        return False
    (project.dir / "stories" / f"{sid}.mp4").unlink(missing_ok=True)
    save(project, {**data, "stories": keep})
    return True


def cut_text(project: Project, story: dict, lang: str | None = None) -> list[dict]:
    """What the finished story says, segment by segment (to read whether it makes sense)."""
    words = _all_words(project)
    joiner = "" if lang in ("zh", "ja") else " "
    out = []
    for s in story["segments"]:
        ws = [w["word"] for w in words if s["start"] <= (w["start"] + w["end"]) / 2 <= s["end"]]
        out.append({"cid": s["cid"], "card": s.get("card") or "", "text": joiner.join(ws)})
    return out


# --------------------------------------------------------------------- render


def _pieces(story: dict, F: int) -> list[dict]:
    """Segments and text cards in play order, with frame lengths and timeline offsets."""
    pieces = []
    for k, s in enumerate(story["segments"]):
        if k and story.get("cards", True) and s.get("card"):
            pieces.append({"kind": "card", "text": s["card"], "frames": round(CARD_SECONDS * F)})
        pieces.append({"kind": "seg", "seg": s})
    return pieces


def render(project: Project, story: dict, opts, facecam, dest: Path,
           on_progress: Callable[[float], None] | None = None):
    """One 9:16 Short of the story (H.264 MP4). Returns a RenderResult with info."""
    from . import editors, governor
    from .clips import (ClipOptions, Geometry, OutputSpec, _ass_escape, _filter_graph, build_ass, resolve_layout,
                        seek_at, video_args)
    from .edit import audiomix, loudness
    from .edit import plan as plan_mod
    from .edit.music import decode
    from .render import RenderResult, cpu_fallback, pick_codec, run_ffmpeg
    from .web import state

    ffmpeg = require_tool("ffmpeg")
    source = project.source_path
    if source is None:
        raise SharkyClipsError("The project's source video is missing.")
    meta = project.load_meta()
    src_w, src_h = int(meta.get("width") or 1920), int(meta.get("height") or 1080)
    src_fps = float(meta.get("fps") or 30)
    F = editors.render_fps(src_fps)
    has_audio = "audio_codec" not in meta or bool(meta.get("audio_codec"))
    spec = OutputSpec()
    W, H = spec.canvas
    layout = resolve_layout(opts.layout, facecam)
    geo = Geometry.for_spec(spec, layout)
    hl = state.load_highlights(project) or {}
    cands = {c["id"]: c for c in hl.get("candidates", [])}
    seg_opts = ClipOptions.from_dict({**opts.to_dict(), "cuts": "off", "zoom": "off", "music": False, "brand": False,
                                      "loop": False, "hook_flash": False})
    tf = round(TRANSITION * F)
    T = tf / F
    pieces = _pieces(story, F)
    plans = []
    for p in pieces:
        if p["kind"] != "seg":
            continue
        s = p["seg"]
        c = cands.get(s["cid"]) or {"id": s["cid"], "reasons": []}
        plan = plan_mod.build(project, {"id": s["cid"], "start": s["start"], "end": s["end"],
                                        "reasons": c.get("reasons") or []}, seg_opts, vertical=True, fps=F)
        p["plan"] = plan
        p["frames"] = sum(fb - fa for fa, fb in plan.frames())
        plans.append(plan)
    off = 0
    for k, p in enumerate(pieces):
        p["offset"] = off
        off += p["frames"] - (tf if k < len(pieces) - 1 else 0)
    total_f = off
    total = total_f / F

    # ---- sound: each segment to the same loudness, crossfaded, normalized
    governor.checkpoint()
    SR = audiomix.SR
    mix = np.zeros((int(round(total * SR)) + SR, 2), np.float32)
    seg_lufs = []
    tracks = []
    for p in pieces:
        n = int(round(p["frames"] / F * SR))
        if p["kind"] == "seg" and has_audio:
            plan = p["plan"]
            t0 = max(0.0, plan.start - 0.1)
            y = audiomix.cut_and_join(decode(source, t0, plan.end - t0 + 0.1, sr=SR, channels=2), t0, plan)
            y = audiomix.apply_bleeps(y, plan.bleeps, plan.bleep_mode)
            y = np.concatenate([y, np.zeros((max(0, n - len(y)), 2), np.float32)])[:n]
            lufs = loudness.integrated_lufs(y)
            seg_lufs.append(lufs)
        else:
            y = np.zeros((n, 2), np.float32)
        tracks.append(y)
    loud = [x for x in seg_lufs if x > -60]
    target = float(np.median(loud)) if loud else -20.0
    gains = []
    seg_i = 0
    for p, y in zip(pieces, tracks):
        if p["kind"] == "seg" and has_audio:
            lufs = seg_lufs[seg_i]
            seg_i += 1
            g = float(np.clip(target - lufs, -MAX_GAIN_DB, MAX_GAIN_DB)) if lufs > -60 else 0.0
            gains.append(round(g, 2))
            y *= 10 ** (g / 20)
    nT = int(round(T * SR))
    theta = np.linspace(0, np.pi / 2, max(1, nT), dtype=np.float32)[:, None]
    for k, (p, y) in enumerate(zip(pieces, tracks)):
        y = y.copy()
        if k > 0 and nT:
            y[:nT] *= np.sin(theta)
        if k < len(pieces) - 1 and nT:
            y[-nT:] *= np.cos(theta)
        if k == 0:
            y = audiomix._fade(y, 0.08, 0.0)
        if k == len(pieces) - 1:
            y = audiomix._fade(y, 0.0, 0.2)
        a = int(round(p["offset"] / F * SR))
        mix[a: a + len(y)] += y[: max(0, len(mix) - a)]
    mix = mix[: int(round(total * SR))]
    mix, _ = loudness.normalize(mix, audiomix.TARGET_LUFS)
    final_lufs = round(loudness.integrated_lufs(mix), 1)
    loud_after = []
    for p in pieces:
        if p["kind"] == "seg":
            a = int(round(p["offset"] / F * SR))
            b = a + int(round(p["frames"] / F * SR))
            loud_after.append(round(loudness.integrated_lufs(mix[a + nT: max(a + nT + 1, b - nT)]), 1))

    # ---- text: captions continue across the segments, cards between acts, the story's hook
    words: list[dict] = []
    for p in pieces:
        if p["kind"] != "seg":
            continue
        o = p["offset"] / F
        for w in p["plan"].out_words():
            words.append({**w, "start": round(w["start"] + o, 3), "end": round(w["end"] + o, 3)})
    words.sort(key=lambda w: w["start"])
    lang = plans[0].lang if plans else None
    pub = story.get("publish") or {}
    hook_text = (pub.get("hook_text") or story.get("title") or "") if opts.hook else ""
    extra = []
    for p in pieces:
        if p["kind"] == "card":
            a, b = p["offset"] / F + T * 0.5, (p["offset"] + p["frames"]) / F - T * 0.5
            from .clips import _ass_time

            extra.append(f"Dialogue: 2,{_ass_time(a)},{_ass_time(b)},card,,0,0,0,,"
                         f"{{\\an5\\pos({W // 2},{H // 2})\\fad(120,120)}}{_ass_escape(p['text'])}")
    ass = build_ass(words, total, ClipOptions.from_dict({**opts.to_dict(), "hook": bool(hook_text)}), layout, lang,
                    hook_text, hook_lang=pub.get("language") or lang, geo=geo, extra=extra)

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".partial" + dest.suffix)
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-story-"))
    try:
        (work / "subs.ass").write_text(ass, encoding="utf-8")
        audiomix.write_wav(work / "mix.wav", mix)
        src = str(source.resolve())
        inputs: list[str] = []
        g: list[str] = []
        labels = []
        for k, p in enumerate(pieces):
            if p["kind"] == "seg":
                plan = p["plan"]
                inputs += ["-ss", seek_at(plan.start, src_fps), "-t", f"{plan.end - plan.start + 0.1:.3f}", "-i", src]
                g.append(f"[{k}:v]fps={F},trim=end_frame={p['frames']},setpts=N/({F}*TB)[r{k}]")
                g.append(_filter_graph(layout, src_w, src_h, facecam, f"r{k}", f"b{k}", (W, H)))
                g.append(f"[b{k}]setsar=1,format=yuv420p[p{k}]")
            else:
                inputs += ["-f", "lavfi", "-i", f"color=c=0x0E1A33:s={W}x{H}:r={F}:d={p['frames'] / F + 0.1:.3f}"]
                g.append(f"[{k}:v]trim=end_frame={p['frames']},setpts=N/({F}*TB),format=yuv420p,setsar=1[p{k}]")
            labels.append(f"p{k}")
        inputs += ["-i", "mix.wav"]
        a_i = len(pieces)
        cur = labels[0]
        for k in range(1, len(pieces)):
            both_segs = pieces[k]["kind"] == "seg" and pieces[k - 1]["kind"] == "seg"
            trans = "fadewhite" if both_segs else "fade"
            g.append(f"[{cur}][{labels[k]}]xfade=transition={trans}:duration={T:.4f}:offset={pieces[k]['offset'] / F:.4f}[x{k}]")
            cur = f"x{k}"
        g.append(f"[{cur}]ass=subs.ass,format=yuv420p[v]")
        graph = ";".join(g)
        mux = ["-f", "mp4", "-movflags", "+faststart"]

        def build(e) -> list[str]:
            return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", *inputs, "-filter_complex", graph,
                    "-map", "[v]", "-map", f"{a_i}:a", *video_args(e, spec), "-c:a", "aac", "-b:a", f"{spec.audio_k}k",
                    "-t", f"{total:.3f}", *mux, "-progress", "pipe:1", str(tmp.resolve())]

        enc = pick_codec("h264")
        if enc is None:
            raise SharkyClipsError("This computer can't encode H.264 video.")
        t0 = time.perf_counter()
        code, err = run_ffmpeg(build(enc), total, on_progress, cwd=work)
        fallback = cpu_fallback("h264")
        if code != 0 and enc.hardware and fallback is not None:
            enc = fallback
            code, err = run_ffmpeg(build(enc), total, on_progress, cwd=work)
        if code != 0:
            tmp.unlink(missing_ok=True)
            raise SharkyClipsError(f"ffmpeg could not render the story: {err.strip()[-500:]}")
        os.replace(tmp, dest)
        segs_out = []
        for p in pieces:
            if p["kind"] == "seg":
                segs_out.append({"cid": p["seg"]["cid"], "start": p["plan"].start, "end": p["plan"].end,
                                 "out_start": round(p["offset"] / F, 3), "out_end": round((p["offset"] + p["frames"]) / F, 3)})
        info = {"duration": round(total, 2), "segments": segs_out, "cards": sum(p["kind"] == "card" for p in pieces),
                "lufs": final_lufs, "segment_lufs_before": [round(x, 1) for x in seg_lufs], "segment_gain_db": gains,
                "segment_lufs_after": loud_after, "transition_s": round(T, 3),
                "bleeps": sum(len(pl.bleeps) for pl in plans if pl.bleep_mode != "off")}
        return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, enc.label, info)
    finally:
        shutil.rmtree(work, ignore_errors=True)
