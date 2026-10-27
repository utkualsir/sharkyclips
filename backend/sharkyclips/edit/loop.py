"""Seamless loop: the clip's end flows back into its start, so viewers rewatch without noticing.

1. The seam: the end point moves (a few seconds at most) to the pause after a word where the
   sound level, the picture and the motion match the clip's opening best, and the last words
   lead naturally into the first ones (sentence ends, real pauses). Never inside a word, never
   past the platform's length limit. The start snaps out of a word too. The local AI may pick
   among the best few ends and rewrite the hook text so it works as an ending AND an opening.
2. The render (audiomix + clips): no fades, no outro card, no fade to black. What the source
   says right AFTER the end point is crossfaded under the clip's first ~60 ms (equal power),
   and the picture after the end point dissolves into the first frames, so the last sample /
   frame of the file continues straight into the first one when the player loops. The last
   second is gently gained to the opening's level.
3. measure(): reads the finished file and reports the seam: sample jump (click), high
   frequency burst and the loudness step, compared with the clip's own normal steps.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from ..procs import no_window
from ..project import Project, read_json, write_json_atomic

VERSION = 1
AUDIO_XFADE = 0.06  # seconds: the "tiny" seam crossfade for speech / game sound
MUSIC_XFADE = 0.25  # longer when the clip ends on music (no beat click)
VIDEO_XFADE = 0.2
LEVEL_RAMP = 1.2  # seconds at the end that are gained toward the opening's level
MAX_GAIN_DB = 9.0  # per side: the end and the start each move up to this far toward each other
SEARCH_BACK = 6.0
SEARCH_FWD = 3.0
MIN_SECONDS = 3.0
DEFAULT_MAX_SECONDS = 180.0  # YouTube Shorts (the strictest of the vertical platforms)
SENTENCE_END = tuple(".!?…。！？؟")
FRAME_RATE = 10  # frames per second for the picture match
THUMB = (48, 27)


@dataclass
class Seam:
    start: float
    end: float
    orig_start: float
    orig_end: float
    audio_xfade: float = AUDIO_XFADE
    video_xfade: float = VIDEO_XFADE
    music_like: bool = False
    tail_ok: bool = True  # the source continues after the end (continuation crossfade)
    gain_db: float = 0.0
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    last_word: str | None = None
    first_word: str | None = None
    options: list[dict] = field(default_factory=list)  # best ends: {"end", "score", "text"}
    hook_text: str | None = None  # the AI's hook that works as ending + opening
    source: str = "signals"  # signals | ai

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("start", "end", "orig_start", "orig_end", "audio_xfade", "video_xfade", "gain_db", "score"):
            d[k] = round(float(d[k]), 3)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Seam":
        keys = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in keys})


# --------------------------------------------------------------------- features


def _level(db: np.ndarray, t0: float, a: float, b: float, hop: float = 0.02) -> float:
    """Mean power (dB) of the 20 ms frames in [a, b]."""
    i, j = max(0, int((a - t0) / hop)), max(0, int((b - t0) / hop))
    seg = db[i:j]
    if len(seg) == 0:
        return -90.0
    return float(10 * np.log10(np.mean(10 ** (seg / 10)) + 1e-12))


def _frames(source: Path, a: float, b: float) -> np.ndarray | None:
    """Small gray frames of [a, b] at FRAME_RATE fps: array (n, h, w) float32 0..1."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or not source.is_file() or b <= a:
        return None
    w, h = THUMB
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats", "-ss", f"{max(0.0, a):.3f}",
           "-t", f"{b - a:.3f}", "-i", str(source), "-an",
           "-vf", f"fps={FRAME_RATE},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "pipe:1"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60, **no_window()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    n = len(out) // (w * h)
    if n == 0:
        return None
    return np.frombuffer(out[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32) / 255.0


def _frame_at(frames: np.ndarray | None, t0: float, t: float) -> np.ndarray | None:
    if frames is None:
        return None
    i = int(round((t - t0) * FRAME_RATE))
    return frames[min(len(frames) - 1, max(0, i))]


def _motion_at(frames: np.ndarray | None, t0: float, t: float) -> float | None:
    if frames is None or len(frames) < 2:
        return None
    i = min(len(frames) - 1, max(1, int(round((t - t0) * FRAME_RATE))))
    return float(np.mean(np.abs(frames[i] - frames[i - 1])))


# --------------------------------------------------------------------- the seam


def snap_start(start: float, words: list[dict]) -> float:
    """Move a start that falls inside a word to just before that word."""
    prev_end = 0.0
    for w in words:
        if w["start"] + 0.03 < start < w["end"] - 0.03:
            return round(max(prev_end, w["start"] - 0.06, 0.0), 3)
        if w["end"] <= start:
            prev_end = w["end"]
    return start


def _inside(t: float, ranges: list[tuple[float, float]], pad: float = 0.0) -> bool:
    return any(a - pad <= t <= b + pad for a, b in ranges)


def find_seam(start: float, end: float, words: list[dict], *, db: np.ndarray | None = None, db_t0: float = 0.0,
              frames_end: np.ndarray | None = None, frames_t0: float = 0.0, frames_head: np.ndarray | None = None,
              src_duration: float | None = None, max_len: float = DEFAULT_MAX_SECONDS,
              deleted: list[tuple[float, float]] | None = None, bleeps: list[tuple[float, float]] | None = None,
              quiet_db: float = -45.0, force_end: float | None = None) -> Seam:
    """Pure decision (tests feed it directly). words: absolute times, sorted, may reach past `end`.
    db: 20 ms frame levels from db_t0. frames_end: picture frames from frames_t0 (FRAME_RATE fps)
    covering the search window; frames_head: the clip's first frames."""
    deleted = deleted or []
    bleeps = bleeps or []
    words = sorted((w for w in words if str(w.get("word", "")).strip()), key=lambda w: w["start"])
    orig_start, orig_end = start, end
    start = snap_start(start, words)
    src_end = float(src_duration) if src_duration else end + SEARCH_FWD
    dur = end - start
    if dur < 8.0:  # very short clip: stay close to its own end
        lo = max(start + min(MIN_SECONDS, dur * 0.8), end - 0.3 * dur)
        hi = min(end + 1.5, start + max_len, src_end - 0.02)
    else:
        lo = max(start + max(MIN_SECONDS, 0.55 * dur), end - SEARCH_BACK)
        hi = min(end + SEARCH_FWD, start + max_len, src_end - 0.02)
    if hi < lo:
        lo = hi = max(start + 0.5, min(end, start + max_len, src_end - 0.02))

    head_db = _level(db, db_t0, start, start + 0.4) if db is not None else None
    head_frame = frames_head[0] if frames_head is not None and len(frames_head) else None
    head_motion = _motion_at(frames_head, start, start + 0.15) if frames_head is not None else None

    cands: list[dict] = []
    for i, w in enumerate(words):
        if w["end"] > hi or w["end"] < lo - 0.3:
            continue
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt["start"] - w["end"]) if nxt else 10.0
        if gap < 0.12:
            continue
        e = min(w["end"] + min(0.25, 0.4 * gap), hi)  # right before the source / length limit is fine
        if e < w["end"] + 0.03 or not lo <= e <= hi or _inside(e, deleted, 0.02) or _inside(e + AUDIO_XFADE, deleted):
            continue
        cands.append({"end": e, "gap": gap, "word": w, "next": nxt, "sentence": w["word"].rstrip().endswith(SENTENCE_END)})
    spoken = [w for w in words if lo - 1.0 <= w["end"] and w["start"] <= hi]
    if not spoken:  # no speech near the end (music, quiet gameplay): any moment may do
        t = lo
        while t <= hi + 1e-6:
            if not _inside(t, deleted, 0.02):
                cands.append({"end": t, "gap": 10.0, "word": None, "next": None, "sentence": False})
            t += 0.25
    if not cands:  # talking without a pause in the window: the longest pause before it
        best = None
        for i, w in enumerate(words[:-1]):
            gap = words[i + 1]["start"] - w["end"]
            if start + MIN_SECONDS <= w["end"] <= hi and gap > 0.04 and (best is None or gap > best[0]):
                best = (gap, i)
        if best is not None:
            gap, i = best
            w = words[i]
            cands.append({"end": w["end"] + gap * 0.4, "gap": gap, "word": w, "next": words[i + 1],
                          "sentence": w["word"].rstrip().endswith(SENTENCE_END), "forced": True})
        else:
            cands.append({"end": min(end, hi), "gap": 0.0, "word": None, "next": None, "sentence": False,
                          "forced": True})

    for c in cands:
        e = c["end"]
        reasons = []
        level = visual = motion = 0.0
        if db is not None and head_db is not None:
            c["tail_db"] = _level(db, db_t0, e - 0.4, e)
            level = min(1.0, abs(c["tail_db"] - head_db) / 12.0)
            if level < 0.25:
                reasons.append("level_match")
        f = _frame_at(frames_end, frames_t0, e)
        if f is not None and head_frame is not None:
            visual = min(1.0, float(np.mean(np.abs(f - head_frame))) / 0.25)
            if visual < 0.3:
                reasons.append("picture_match")
            m = _motion_at(frames_end, frames_t0, e)
            if m is not None and head_motion is not None:
                motion = min(1.0, abs(m - head_motion) / 0.08)
                if motion < 0.3:
                    reasons.append("motion_match")
        dist = min(1.0, abs(e - end) / SEARCH_BACK)
        bleep = 0.15 if c["word"] is not None and _inside((c["word"]["start"] + c["word"]["end"]) / 2, bleeps) else 0.0
        if c["sentence"]:
            reasons.append("sentence_end")
        if c["gap"] >= 0.35:
            reasons.append("pause")
        c["score"] = round(1.0 - 0.3 * level - 0.25 * visual - 0.1 * motion - 0.2 * dist
                           + 0.15 * c["sentence"] + 0.1 * min(1.0, c["gap"] / 0.6) - bleep
                           - (0.5 if c.get("forced") else 0.0), 4)
        c["reasons"] = reasons + (["mid_speech"] if c.get("forced") else [])
    cands.sort(key=lambda c: -c["score"])
    if force_end is not None:  # the AI's pick among the options
        cands = ([c for c in cands if abs(c["end"] - force_end) < 1e-3]
                 + [c for c in cands if abs(c["end"] - force_end) >= 1e-3])
    best = cands[0]
    e = round(best["end"], 3)

    # Crossfade lengths: the continuation must stay inside the pause (no clipped next word).
    music_like = False
    if db is not None and not any(e - 1.5 <= w["end"] and w["start"] <= e + 0.3 for w in words):
        i0, i1 = int((e - 1.5 - db_t0) / 0.02), int((e - db_t0) / 0.02)
        seg = db[max(0, i0):max(0, i1)]
        music_like = len(seg) > 10 and float(np.std(seg)) < 5.0 and float(np.mean(seg)) > quiet_db + 12
    axf = MUSIC_XFADE if music_like else AUDIO_XFADE
    nxt = best.get("next")
    if nxt is not None:
        axf = max(0.02, min(axf, (nxt["start"] - e) * 0.9))
    tail_ok = e + max(axf, VIDEO_XFADE) + 0.02 <= src_end and not _inside(e + axf, deleted)
    vxf = min(VIDEO_XFADE, 0.1 * (e - start)) if tail_ok else 0.0
    gain = 0.0
    if db is not None and head_db is not None and best.get("tail_db") is not None:
        if head_db > -60 and best["tail_db"] > -60:
            gain = float(np.clip(head_db - best["tail_db"], -MAX_GAIN_DB, MAX_GAIN_DB))

    def text_before(t: float) -> str:
        return " ".join(w["word"].strip() for w in words if t - 6.0 <= w["start"] and w["end"] <= t + 0.01)[-160:]

    first = next((w for w in words if w["start"] >= start - 0.01), None)
    return Seam(start=round(start, 3), end=e, orig_start=orig_start, orig_end=orig_end,
                audio_xfade=round(axf, 3), video_xfade=round(vxf, 3), music_like=music_like, tail_ok=tail_ok,
                gain_db=round(gain, 2), score=best["score"], reasons=best["reasons"],
                last_word=best["word"]["word"].strip() if best.get("word") else None,
                first_word=first["word"].strip() if first else None,
                options=[{"end": round(c["end"], 3), "score": c["score"], "text": text_before(c["end"])}
                         for c in cands[:3]])


def _cache_path(project: Project, start: float, end: float, max_len: float,
                deleted: list[tuple[float, float]]) -> Path:
    key = json.dumps([VERSION, round(start, 2), round(end, 2), round(max_len, 1),
                      [(round(a, 2), round(b, 2)) for a, b in deleted]])
    return project.cache_dir / "loop" / f"{hashlib.sha1(key.encode()).hexdigest()[:16]}.json"


def seam_for(project: Project, start: float, end: float, *, max_len: float = DEFAULT_MAX_SECONDS,
             deleted: list[tuple[float, float]] | None = None, bleeps: list[tuple[float, float]] | None = None,
             words: list[dict] | None = None, force_end: float | None = None) -> Seam:
    """The seam of one clip (cached per project: same cut -> same seam, also the AI's choice)."""
    from . import silence
    from .plan import transcript_words

    deleted = deleted or []
    path = _cache_path(project, start, end, max_len, deleted)
    if path.is_file() and force_end is None:
        try:
            return Seam.from_dict(read_json(path))
        except Exception:  # noqa: BLE001
            pass
    if words is None:
        words, _lang = transcript_words(project, max(0.0, start - 3), end + SEARCH_FWD + 3)
    meta = project.load_meta()
    src_dur = float(meta.get("duration") or 0) or None
    t0 = max(0.0, start - 0.5)
    t1 = end + SEARCH_FWD + 0.5
    db = silence.frame_db(project.audio_path, t0, t1) if project.audio_path.is_file() else None
    quiet = silence.quiet_threshold(db) if db is not None and len(db) else -45.0
    fe = fh = None
    fe_t0 = max(0.0, end - SEARCH_BACK - 0.3)
    if project.source_path is not None:
        fe = _frames(project.source_path, fe_t0, end + SEARCH_FWD + 0.3)
        fh = _frames(project.source_path, start, start + 0.4)
    seam = find_seam(start, end, words, db=db if db is not None and len(db) else None, db_t0=t0,
                     frames_end=fe, frames_t0=fe_t0, frames_head=fh, src_duration=src_dur, max_len=max_len,
                     deleted=deleted, bleeps=bleeps, quiet_db=quiet, force_end=force_end)
    if force_end is not None:
        return seam
    try:
        write_json_atomic(path, seam.to_dict())
    except OSError:
        pass
    return seam


# --------------------------------------------------------------------- the local AI (optional)

LOOP_SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "integer", "minimum": 1, "maximum": 3},
        "hook_text": {"type": "string", "minLength": 2, "maxLength": 60},
        "why": {"type": "string", "maxLength": 200},
    },
    "required": ["choice", "hook_text", "why"],
}


def ai_polish(project: Project, start: float, end: float, model, *, lang: str, hook_text: str,
              max_len: float = DEFAULT_MAX_SECONDS, deleted: list[tuple[float, float]] | None = None) -> Seam:
    """Let the LLM pick the most natural of the best ends and write a hook that works as the
    clip's ending AND its opening. Saved into the seam cache (the render then uses it)."""
    from ..analyze import SYSTEM, has_profanity, lang_name
    from .plan import transcript_words

    seam = seam_for(project, start, end, max_len=max_len, deleted=deleted)
    if seam.source == "ai" or len(seam.options) == 0:
        return seam
    words, _ = transcript_words(project, seam.start, seam.start + 8)
    opening = " ".join(w["word"] for w in words)[:200]
    opts = "\n".join(f"{i + 1}. ...{o['text']}" for i, o in enumerate(seam.options))
    prompt = (f"This short video loops: when it ends, it starts again immediately. Choose the ending "
              f"that flows most naturally back into the opening line, so a viewer doesn't notice the "
              f"restart. Then write an on-screen hook text in {lang_name(lang)} (max 6 words) that reads "
              f"well both as the last thing before the restart and as the first thing on screen.\n\n"
              f"Opening line: {opening}\n\nPossible endings (last words before the cut):\n{opts}\n\n"
              f"Current hook text: {hook_text}")

    def check(d: dict) -> list[str]:
        out = []
        if d["choice"] > len(seam.options):
            out.append(f"choice must be 1..{len(seam.options)}")
        if has_profanity(d["hook_text"]):
            out.append("hook_text must be advertiser-friendly")
        return out

    d = model.json(SYSTEM, prompt, LOOP_SCHEMA, check=check, temperature=0.4, num_predict=300)
    pick = seam.options[int(d["choice"]) - 1]
    if abs(pick["end"] - seam.end) > 1e-3:  # crossfades / level for the chosen end
        seam = seam_for(project, start, end, max_len=max_len, deleted=deleted, force_end=pick["end"])
    seam.hook_text = " ".join(d["hook_text"].split())[:60]
    seam.source = "ai"
    write_json_atomic(_cache_path(project, start, end, max_len, deleted or []), seam.to_dict())
    return seam


# --------------------------------------------------------------------- sound at the seam


def crossfade_head(main: np.ndarray, continuation: np.ndarray | None, xfade_s: float, sr: int) -> np.ndarray:
    """Equal-power crossfade of what follows the end point under the first samples, so the
    file's last sample continues into its first one. Without a continuation: a 5 ms fade at
    both ends (no click, a barely audible dip)."""
    n = int(round(xfade_s * sr))
    if continuation is None or n < 2 or len(continuation) < n or len(main) < 2 * n:
        r = min(len(main) // 4, int(0.005 * sr))
        if r > 1:
            ramp = np.linspace(0.0, 1.0, r, dtype=np.float32)[:, None]
            main[:r] *= ramp
            main[-r:] *= ramp[::-1]
        return main
    theta = np.linspace(0, np.pi / 2, n, dtype=np.float32)[:, None]
    main[:n] = main[:n] * np.sin(theta) + continuation[:n] * np.cos(theta)
    return main


def match_level(main: np.ndarray, gain_db: float, sr: int, ramp_s: float = LEVEL_RAMP) -> np.ndarray:
    """Ramp the end toward the opening's level (smooth, from 0 dB to gain_db)."""
    if abs(gain_db) < 0.2:
        return main
    n = min(len(main) // 2, int(ramp_s * sr))
    if n < 2:
        return main
    g = 10 ** (np.linspace(0.0, gain_db, n, dtype=np.float32) / 20)
    main[-n:] *= g[:, None]
    return main


def meet_levels(main: np.ndarray, sr: int, ramp_s: float = LEVEL_RAMP,
                max_db: float = MAX_GAIN_DB) -> tuple[np.ndarray, float]:
    """The end and the start meet in the middle: the last second ramps toward the opening's
    loudness and the first second ramps toward the end's (measured on the actual mix, K-weighted).
    Returns the mix and the gain the end got (the continuation under the start gets it too)."""
    b = int(0.4 * sr)
    if len(main) < 4 * b:
        return main, 0.0
    xk = _kweighted(main, sr)
    l_tail, l_head = _momentary(xk[-b:]), _momentary(xk[:b])
    if l_tail < -60 or l_head < -60 or abs(l_head - l_tail) < 1.0:
        return main, 0.0
    half = float(np.clip((l_head - l_tail) / 2, -max_db, max_db))
    n = min(len(main) // 3, int(ramp_s * sr))
    hold = min(n // 3, b)  # full gain right at the seam, a smooth ramp before / after it
    curve = np.concatenate([np.linspace(0.0, 1.0, n - hold, dtype=np.float32), np.ones(hold, np.float32)])
    main[-n:] *= (10 ** (half * curve / 20))[:, None]
    main[:n] *= (10 ** (-half * curve[::-1] / 20))[:, None]
    return main, half


def periodic(speech: list[tuple[float, float]], total: float) -> list[tuple[float, float]]:
    """Speech ranges of a looped timeline (one copy before and after), for music ducking."""
    return [(a - total, b - total) for a, b in speech] + speech + [(a + total, b + total) for a, b in speech]


# --------------------------------------------------------------------- measuring the result


def _kweighted(x: np.ndarray, sr: int) -> np.ndarray:
    from scipy.signal import lfilter

    from .loudness import _HIGHPASS, _SHELF

    return lfilter(*_HIGHPASS, lfilter(*_SHELF, x, axis=0), axis=0)


def _momentary(xk: np.ndarray) -> float:
    p = float(np.mean(np.sum(xk ** 2, axis=1)))
    return -0.691 + 10 * np.log10(p + 1e-12)


def measure_audio(y: np.ndarray, sr: int = 48000) -> dict:
    """Seam of a looped sound track (samples, channels): click, HF burst, loudness step."""
    if y.ndim == 1:
        y = y[:, None]
    w = min(len(y) // 2, int(0.5 * sr))
    joined = np.concatenate([y[-w:], y[:w]])  # end -> start, the seam at index w
    mono = joined.mean(axis=1)
    d = np.abs(np.diff(mono))
    seam_jump = float(d[w - 1])
    mask = np.ones(len(d), bool)
    mask[max(0, w - 3): w + 2] = False
    ref = float(np.percentile(d[mask], 99.5)) if mask.any() else 0.0
    click = seam_jump / (ref + 1e-9)
    hp = np.diff(mono, 2)
    win = int(0.005 * sr)
    energy = np.array([np.mean(hp[i:i + win] ** 2) for i in range(0, len(hp) - win, win)])
    k = min(len(energy) - 1, max(0, (w - win // 2) // win))
    # Compared with the clip's own sharp moments (shots, claps): above its 95th percentile = a burst.
    others = np.delete(energy, [i for i in (k - 1, k, k + 1) if 0 <= i < len(energy)])
    ref_hf = float(np.percentile(others, 95)) if len(others) else 0.0
    hf_db = float(10 * np.log10((energy[k] + 1e-15) / (ref_hf + 1e-15))) if len(energy) else 0.0
    xk = _kweighted(y, sr)
    b = int(0.4 * sr)
    l_tail, l_head = _momentary(xk[-b:]), _momentary(xk[:b])
    jump = abs(l_tail - l_head)
    # The clip's own step size at 24 points (its normal ups and downs, for comparison).
    steps = []
    for t in np.linspace(b, len(y) - b, 26)[1:-1]:
        i = int(t)
        steps.append(abs(_momentary(xk[i - b:i]) - _momentary(xk[i:i + b])))
    typical = float(np.percentile(steps, 90)) if steps else 0.0
    ok = click < 2.0 and hf_db < 3.0 and jump <= max(3.0, typical)
    return {"click_ratio": round(click, 3), "hf_burst_db": round(hf_db, 2), "lufs_end": round(l_tail, 2),
            "lufs_start": round(l_head, 2), "loudness_step_lu": round(jump, 2),
            "typical_step_lu": round(typical, 2), "ok": bool(ok)}


def measure(path: Path) -> dict | None:
    """measure_audio() of a rendered file (None without sound). Lossy codecs (AAC, Opus) add
    their own start-up noise to the first and last ~20 ms of ANY file, and the platforms
    re-encode uploads anyway: the seam we are responsible for is measured on the mix
    (audiomix.MixResult.seam); this is extra information."""
    from .music import decode

    try:
        y = decode(path, 0.0, None, sr=48000, channels=2)
    except Exception:  # noqa: BLE001
        return None
    if len(y) < 48000:
        return None
    return measure_audio(y, 48000)


def video_seam(path: Path, rows: tuple[float, float] = (0.0, 1.0)) -> dict | None:
    """Picture step at the seam (last frame -> first frame) vs. the clip's normal frame steps.
    rows: the band of the picture to compare (0..1, top to bottom): leave out the captions and
    the hook text, which change with the words."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    w, h = 27, 48  # vertical clips
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats", "-i", str(path), "-an",
           "-vf", f"scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "pipe:1"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=300, **no_window()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    n = len(out) // (w * h)
    if n < 4:
        return None
    f = np.frombuffer(out[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32) / 255.0
    f = f[:, int(rows[0] * h): max(int(rows[0] * h) + 1, int(rows[1] * h))]
    steps = np.mean(np.abs(np.diff(f, axis=0)), axis=(1, 2))
    seam = float(np.mean(np.abs(f[0] - f[-1])))
    return {"seam_step": round(seam, 4), "typical_step": round(float(np.percentile(steps, 90)), 4),
            "max_step": round(float(steps.max()), 4)}
