"""Easy mode 2.0: the first 3 seconds of every Easy clip, checked before it is rendered.

Hook score (0-100) = the A/B hook model (abtest.score) on the source moments the opening would
show: motion, loudness punch, the face + smile on the facecam, the on-screen text, trigger words,
reactions, and what this channel's real results say about the style.

When the opening is weak, a few alternatives are scored the same way (a pre-test, nothing is
rendered): starting closer to the action (later starts, never past the build-up the context
guard keeps) and the hook flash (the peak for 1 s first). The strongest one wins.

The headline banner (on by default) is the AI's short hook in the creator's style: capitals and
the emojis "My style" uses, censored, short enough for two lines.
"""

from __future__ import annotations

import numpy as np

from . import abtest
from .project import Project

WEAK = 52.0  # below this the opening is "weak": alternatives are tried
MIN_GAIN = 4.0  # an alternative must beat the found start by this much
MAX_MOVE = 8.0  # a later start skips at most this much
LATER_STEPS = (1.5, 3.0, 4.5, 6.0, 8.0)
BANNER_MAX = 42  # characters (two short lines at the banner's size)
MOMENT_EMOJI = {"funny": "😂", "fail": "💀", "rage": "😡", "skill": "🔥", "clutch": "🔥", "action": "🔥",
                "reaction": "😱", "wholesome": "🥹", "explanation": "💡", "tip": "💡", "music": "🎵"}


# ===================================================================== features on the source


def _clip_motion(project: Project, start: float, end: float) -> tuple[np.ndarray, float] | None:
    """Per-step picture change at 6 fps over [start, end] and its mean (from the source video)."""
    src = project.source_path
    if src is None:
        return None
    g = abtest._gray(src, max(0.0, start), end, fps=6)
    if g is None or len(g) < 4:
        return None
    steps = np.mean(np.abs(np.diff(g, axis=0)), axis=(1, 2))
    return steps, float(np.mean(steps))


def _power_db(project: Project, a: float, b: float) -> float | None:
    from . import audio as audio_mod

    if not project.audio_path.is_file() or b - a < 0.2:
        return None
    x = audio_mod.read_wav_segment(project.audio_path, a, b)
    if len(x) == 0:
        return None
    return float(10 * np.log10(np.mean(x.astype(np.float64) ** 2) + 1e-10))


def features(project: Project, cand: dict, ranges: list[tuple[float, float]], clip: tuple[float, float],
             motion: tuple[np.ndarray, float] | None, facecam: dict | None, lang: str | None, mode: str,
             text: str) -> dict:
    """What abtest.score looks at, measured on the source moments of an opening."""
    from .edit.plan import transcript_words
    from .highlights.modes import get_mode
    from .highlights.signals.keywords import normalize, trigger_phrases

    f: dict = {}
    s0, _e0 = clip
    if motion is not None:
        steps, mean = motion
        vals = []
        for a, b in ranges:
            i, j = int(max(0.0, a - s0) * 6), int(max(0.0, b - s0) * 6)
            vals += list(steps[i:j])
        if vals:
            f["motion"] = round(float(np.mean(vals) / (mean + 1e-4)), 3)
    whole = _power_db(project, *clip)
    first = [p for a, b in ranges if (p := _power_db(project, a, b)) is not None]
    if whole is not None and first:
        f["loudness"] = round(float(10 * np.log10(np.mean([10 ** (p / 10) for p in first]))) - whole, 2)
    if facecam and project.source_path is not None:
        box = (float(facecam["x"]), float(facecam["y"]), float(facecam["w"]), float(facecam["h"]))
        times = [a + (b - a) * q for a, b in ranges for q in (0.2, 0.75)]
        frames = [fr for t in times if (fr := abtest._frame(project.source_path, t, box)) is not None]
        try:
            fe = abtest.face_emotion(frames)
        except Exception:  # noqa: BLE001 - OpenCV missing / broken
            fe = None
        if fe is not None:
            f.update(fe)
    text = (text or "").strip()
    nwords = len(text.split()) if lang not in ("zh", "ja") else max(1, len(text) // 2)
    f["text"] = {"present": bool(text), "words": nwords if text else 0,
                 "question": text.endswith(("?", "？", "؟")), "number": any(ch.isdigit() for ch in text)}
    spoken = []
    for a, b in ranges:
        ws, _l = transcript_words(project, a, b, voices=False)
        spoken += [w["word"] for w in ws]
    f["opening_words"] = " ".join(spoken)[:300]
    phrases = trigger_phrases(lang or "en", get_mode(mode or "gaming").keyword_categories) if lang else {}
    norm = f" {normalize(' '.join(spoken))} "
    hits = [(p, w) for k, (p, w) in phrases.items() if f" {k} " in norm]
    f["triggers"] = sorted({p for p, _w in hits})[:5]
    f["trigger_weight"] = round(max([w for _p, w in hits] or [0.0]), 2)
    react = {"laughter", "scream", "shouting", "cheering", "loudness_spike", "keyword"}
    codes = {str(r.get("code")) for r in cand.get("reasons") or []
             if any(a - 0.3 <= float(r.get("t", -9)) <= b + 0.3 for a, b in ranges)}
    f["emotion_events"] = sorted(c for c in codes if c in react or c.startswith(("df_", "lol_")))
    return f


def _score(feats: dict, style: str, obs: list[dict]) -> dict:
    res = abtest.score(feats, style, obs)
    return {"score": res["score"], "reasons": [{"code": r["code"], "points": r["points"]} for r in res["reasons"][:4]]}


# ===================================================================== the check


def _later_starts(ar, start: float, end: float, first_event: float | None, peak: float | None,
                  min_len: float) -> list[float]:
    from .shaping import LEAD, snap_start

    need = LEAD.get(ar.mode, 2.0)
    anchor = first_event if first_event is not None else peak
    latest = min(start + MAX_MOVE, end - min_len)
    if anchor is not None:
        latest = min(latest, anchor - need)
    out: list[float] = []
    for d in LATER_STEPS:
        t = start + d
        if t > latest:
            break
        s = snap_start(ar, t)
        if s > start + 0.8 and s <= latest + 0.3 and all(abs(s - x) > 0.8 for x in out):
            out.append(s)
    return out


def check(project: Project, cand: dict, start: float, end: float, review: dict, info: dict,
          move: bool = True) -> dict:
    """{"hook": {...}, "flash": bool, "banner": str, maybe a later "start"} for apply_shapes.
    move=False (the user trimmed the clip): only the score and the flash, never a new start."""
    from .clips import flash_from
    from .shaping import around

    mode = (project.load_meta().get("mode") or "gaming")
    lang = ((project.load_transcript() if project.transcript_path.is_file() else {}) or {}).get("language")
    banner = banner_text(cand, (cand.get("publish") or {}).get("language") or lang)
    facecam = review.get("facecam") if isinstance(review.get("facecam"), dict) else None
    obs = abtest.load_store()["observations"]
    motion = _clip_motion(project, start, end)
    text = banner or (cand.get("publish") or {}).get("hook_text") or ""
    first = abtest.FIRST

    def opening(s: float) -> dict:
        return _score(features(project, cand, [(s, s + first)], (start, end), motion, facecam, lang, mode, text),
                      "statement", obs)

    base = opening(start)
    best = {"choice": "start", "start": start, **base}
    options = [{"choice": "start", "at": round(start, 2), "score": base["score"]}]
    if base["score"] < WEAK and mode != "music":
        tgt = info.get("target") or {"min": 15.0}
        ar = around(project, cand, start, end, mode)
        ev = next((e["t"] for e in ar.events if start + 1.0 <= e["t"] <= end), None)
        if move:
            for s in _later_starts(ar, start, end, ev, cand.get("peak"), float(tgt["min"]) * 0.8):
                sc = opening(s)
                options.append({"choice": "later", "at": round(s, 2), "score": sc["score"]})
                if sc["score"] > best["score"] + MIN_GAIN * (best["choice"] == "start"):
                    best = {"choice": "later", "start": s, **sc}
        meta = project.load_meta()
        fs = flash_from(float(cand.get("peak") or (start + end) / 2), float(meta.get("duration") or end),
                        float(meta.get("fps") or 30))
        fl = _score(features(project, cand, [(fs, fs + 1.0), (best["start"], best["start"] + first - 1.0)],
                             (start, end), motion, facecam, lang, mode, text), "flash", obs)
        options.append({"choice": "flash", "at": round(best["start"], 2), "score": fl["score"]})
        if fl["score"] > best["score"] + MIN_GAIN:
            best = {**best, "choice": "flash", **fl}
    out: dict = {"hook": {"score": round(best["score"]), "before": round(base["score"]), "choice": best["choice"],
                          "moved": round(best["start"] - start, 2), "reasons": best["reasons"], "options": options},
                 "flash": best["choice"] == "flash", "banner": banner}
    if move and best["start"] > start + 0.05:
        out["start"] = round(best["start"], 2)
        out["why"] = list(info.get("why") or []) + ["hook_later"]
    return out


# ===================================================================== the headline banner


QUOTES = "\"“”«»„"


def _headline(body: str) -> str:
    """The punchiest short part of a title: the streamer's own words in quotes at the start
    ("CB'YE GİDİYOR LAN"), else its first sentence, else the whole main part when short."""
    body = " ".join(body.split())
    if body[:1] in QUOTES:
        end = next((i for i in range(1, len(body)) if body[i] in QUOTES), -1)
        if 4 <= end <= BANNER_MAX - 2:
            return body[: end + 1]
    for i, ch in enumerate(body):
        if ch in "!?…" or (ch == "." and i + 1 < len(body) and body[i + 1] == " "):
            if 8 <= i + 1 <= BANNER_MAX and body[:1] not in QUOTES:
                return body[: i + 1]
            break
    return body if len(body) <= BANNER_MAX else ""


def banner_text(cand: dict, lang: str | None) -> str:
    """The AI's short punchy hook in the creator's style: CAPITALS + their emojis, no swears."""
    from .titles import style as style_mod

    pub = cand.get("publish") or {}
    titles = [t for t in pub.get("titles") or [] if t]
    lang = lang or pub.get("language") or "en"
    try:
        mine = style_mod.active(lang)
    except Exception:  # noqa: BLE001
        mine = None
    emo = ""
    text = ""
    if titles:  # the title (proofread, in the creator's style) is the best source
        body, _paren, em = style_mod.split_title(titles[0])
        emo = "".join(em[:2])
        text = _headline(body)
    if not text:
        text = style_mod.strip_emojis(pub.get("hook_text") or pub.get("cover_text") or "")
    if not emo and not mine:
        moment = str((cand.get("llm") or {}).get("moment_type") or "").lower()
        emo = MOMENT_EMOJI.get(moment, "")
    text = " ".join(str(text or "").replace("\n", " ").split()).strip(" -–—:|")
    if not text:
        return ""
    try:
        text, _n = style_mod.censor(text, lang)
        text = style_mod.upper(text, lang)
    except Exception:  # noqa: BLE001
        text = text.upper()
    if len(text) > BANNER_MAX:  # cut at a word, never mid-word
        cut = text[:BANNER_MAX + 1].rsplit(" ", 1)[0].rstrip(",.;:-–—")
        text = cut if len(cut) >= 12 else text[:BANNER_MAX]
    return f"{text} {emo}".strip()
