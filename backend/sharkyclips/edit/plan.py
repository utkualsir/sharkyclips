"""EditPlan: everything the editing tools do to one clip, decided once and used by the
renderer, the exports and the live preview.

Times are seconds in the SOURCE video unless a name says "out" (the finished clip's main
part, after cuts, before any intro card / hook flash).

Cuts: words the user deleted in the transcript editor, plus (cuts "light"/"strong")
silences and filler words - never inside a laugh or a reaction. Cut points sit on the
output frame grid, so the picture (frame select) and the sound (sample cut + crossfade)
stay in sync to the sample.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

import numpy as np

from .. import config
from ..errors import SharkyClipsError
from ..project import Project
from . import fillers, profanity, silence, zoom
from .loop import Seam

CUT_DEFAULT_MS = {"light": 800, "strong": 450}
CUT_PAD = {"light": 0.18, "strong": 0.10}  # silence kept next to speech
MIN_CUT = 0.10
MIN_KEEP = 0.15
MAX_SEGMENTS = 40
PROTECT_CODES = {"laughter", "keyword", "loudness_spike", "scream", "chat_spike", "chat_reactions"}


def silence_ms(level: str) -> int:
    got = config.get("cut_silence_ms") or {}
    try:
        return int(max(150, min(5000, int(got.get(level, CUT_DEFAULT_MS[level])))))
    except (TypeError, ValueError, AttributeError):
        return CUT_DEFAULT_MS[level]


def merge(ranges: list[tuple[float, float]], gap: float = 0.0) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(ranges):
        if b <= a:
            continue
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def subtract(ranges: list[tuple[float, float]], holes: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out = []
    holes = merge(holes)
    for a, b in ranges:
        cur = a
        for ha, hb in holes:
            if hb <= cur or ha >= b:
                continue
            if ha > cur:
                out.append((cur, ha))
            cur = max(cur, hb)
        if cur < b:
            out.append((cur, b))
    return out


def laugh_times(project: Project, start: float, end: float) -> list[float]:
    """Seconds with laughter (the laughter signal's cached per-second scores)."""
    path = project.cache_dir / "signals" / "laughter.npz"
    if not path.is_file():
        return []
    try:
        with np.load(path, allow_pickle=False) as data:
            scores = np.array(data["scores"])
    except Exception:  # noqa: BLE001
        return []
    a, b = max(0, int(start)), min(len(scores), int(np.ceil(end)))
    return [float(i) + 0.5 for i in range(a, b) if scores[i] >= 0.35]


def transcript_words(project: Project, start: float, end: float,
                     voices: bool = True) -> tuple[list[dict], str | None]:
    """Words (absolute times) whose middle is inside [start, end], and the spoken language.
    Where the voice pass ran (voices/), its words replace the main transcript's: every
    speaker, with a speaker id ("spk")."""
    if not project.transcript_path.is_file():
        return [], None
    tr = project.load_transcript()
    out = []
    for seg in tr.get("segments", []):
        if seg["end"] < start - 1 or seg["start"] > end + 1:
            continue
        for w in seg.get("words", []):
            mid = (w["start"] + w["end"]) / 2
            if start <= mid <= end and w["word"].strip():
                out.append({"start": float(w["start"]), "end": float(w["end"]), "word": w["word"].strip(),
                            "probability": float(w.get("probability", 1.0) or 0.0)})
    out.sort(key=lambda w: w["start"])
    if voices:
        from .. import voices as voices_mod

        from ..textutil import clean_words

        out = [{**w, "word": w["word"].strip()} for w in clean_words(voices_mod.words_for(project, start, end, out))]
    return out, tr.get("language")


@dataclass
class EditPlan:
    start: float
    end: float
    fps: float
    keep: list[tuple[float, float]]
    removed: list[dict] = field(default_factory=list)  # {"a", "b", "kind": deleted|silence|filler}
    words: list[dict] = field(default_factory=list)  # clip words + flags (removed / bleep / filler)
    lang: str | None = None
    bleep_mode: str = "off"  # bleep | mute | off
    bleep_sound: str = "classic"  # classic | boop | custom
    bleeps: list[tuple[float, float]] = field(default_factory=list)
    bleep_src: list[tuple[float, float]] = field(default_factory=list)  # the same, in source time
    strictness: str = "normal"
    censor_full: bool = False  # captions: "****" instead of "a***" (bleep_visual)
    warnings: list[str] = field(default_factory=list)  # e.g. "swear_check_failed", "swear_safety_net"
    swears: list[dict] = field(default_factory=list)  # review list: edit/swears.py items + "bleep"
    speakers: dict = field(default_factory=dict)  # {"me": "custom name" | "", "f1": ...} (voice pass)
    mask_captions: bool = False
    zoom_level: float = 0.0
    pulses: list[zoom.Pulse] = field(default_factory=list)
    music: dict | None = None
    brand: dict | None = None
    intro_s: float = 0.0
    outro_s: float = 0.0
    loop: Seam | None = None  # seamless loop: the seam (end flows back into the start)
    fx: object | None = None  # fx.FxPlan: instant replay, meme effects, chat bubbles (1.2.17)
    dub: dict | None = None  # dub.track_for(): the clip's sound in the user's own voice (1.2.18)
    _starts: list[float] = field(default_factory=list, repr=False)
    _offsets: list[float] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self._index()

    def _index(self) -> None:
        self._starts = [a for a, _b in self.keep]
        self._offsets, acc = [], 0.0
        for a, b in self.keep:
            self._offsets.append(acc)
            acc += b - a

    # ---------------------------------------------------------------- shape

    @property
    def out_duration(self) -> float:
        return sum(b - a for a, b in self.keep)

    @property
    def cuts(self) -> bool:
        return len(self.keep) != 1 or abs(self.keep[0][0] - self.start) > 1e-3 or abs(self.keep[0][1] - self.end) > 1e-3

    @property
    def zooms(self) -> bool:
        return self.zoom_level > 1.0 and bool(self.pulses)

    @property
    def audio_active(self) -> bool:
        return (self.cuts or bool(self.bleeps and self.bleep_mode != "off") or self.music is not None
                or self.loop is not None or self.dub is not None)

    @property
    def active(self) -> bool:
        return (self.audio_active or self.zooms or self.brand is not None or self.loop is not None
                or self.fx is not None or self.dub is not None)

    def frames(self) -> list[tuple[int, int]]:
        """Kept frame ranges [fa, fb) counted from the clip start."""
        return [(round((a - self.start) * self.fps), round((b - self.start) * self.fps)) for a, b in self.keep]

    # ---------------------------------------------------------------- time mapping

    def to_out(self, t: float, snap: str = "none") -> float | None:
        """Source time -> output time. Inside a cut: None, or the next ("fwd") / previous
        ("back") kept moment."""
        i = bisect.bisect_right(self._starts, t) - 1
        if i >= 0 and t <= self.keep[i][1]:
            return self._offsets[i] + (t - self.keep[i][0])
        if snap == "fwd":
            j = i + 1
            return self._offsets[j] if j < len(self.keep) else None
        if snap == "back" and i >= 0:
            return self._offsets[i] + (self.keep[i][1] - self.keep[i][0])
        return None

    def out_words(self) -> list[dict]:
        """Caption words in output time (cut words dropped, swear words masked if asked)."""
        out = []
        for w in self.words:
            if w.get("removed"):
                continue
            mid = (w["start"] + w["end"]) / 2
            i = bisect.bisect_right(self._starts, mid) - 1
            if i < 0 or mid > self.keep[i][1]:
                continue
            a, b = self.keep[i]
            s = self.to_out(max(w["start"], a))
            e = self.to_out(min(w["end"], b))
            if s is None or e is None:
                continue
            masked = bool(w.get("bleep") and self.mask_captions)
            text = (profanity.censor(w["word"]) if self.censor_full else profanity.mask(w["word"])) if masked else w["word"]
            item = {"start": round(s, 3), "end": round(max(e, s + 0.05), 3), "word": text}
            if masked:
                item["censored"] = True
            if w.get("spk"):
                item["spk"] = w["spk"]
            out.append(item)
        return out

    def out_ranges(self, ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Source ranges -> output ranges (the parts that survive the cuts)."""
        out = []
        for a, b in ranges:
            for (ka, kb), off in zip(self.keep, self._offsets):
                lo, hi = max(a, ka), min(b, kb)
                if hi > lo:
                    out.append((off + lo - ka, off + hi - ka))
        return merge(out, gap=0.001)

    def out_pulses(self, target: str) -> list[tuple[float, float]]:
        out = []
        for p in self.pulses:
            if p.target != target:
                continue
            a, b = self.to_out(p.t0, "fwd"), self.to_out(p.t1, "back")
            if self.loop is not None and a is not None and b is not None \
                    and (a < 0.35 or b > self.out_duration - 0.35):
                continue  # a zoom across the loop seam would jump
            if a is not None and b is not None and b - a >= 0.6:
                out.append((a, b))
        return merge(out)

    def speech_out(self) -> list[tuple[float, float]]:
        """Output ranges where someone speaks (for music ducking)."""
        return merge([(w["start"] - 0.15, w["end"] + 0.25) for w in self.out_words()], gap=0.4)

    def fingerprint(self) -> str:
        import hashlib
        import json

        d = {"keep": [(round(a, 2), round(b, 2)) for a, b in self.keep], "bleep": self.bleep_mode,
             "snd": self.bleep_sound,
             "b": [(round(a, 2), round(b, 2)) for a, b in self.bleeps], "mask": self.mask_captions,
             "z": self.zoom_level, "p": [p.to_dict() for p in self.pulses],
             "m": (self.music or {}).get("name"), "brand": f"{(self.brand or {}).get('id')}:{(self.brand or {}).get('rev')}",
             "loop": None if self.loop is None else [self.loop.start, self.loop.end, self.loop.hook_text],
             "fx": self.fx.fingerprint() if self.fx is not None else None}
        return hashlib.sha1(json.dumps(d, sort_keys=True).encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "start": self.start, "end": self.end, "fps": self.fps,
            "keep": [[round(a, 3), round(b, 3)] for a, b in self.keep],
            "removed": [{**r, "a": round(r["a"], 3), "b": round(r["b"], 3)} for r in self.removed],
            "duration": round(self.out_duration, 2),
            "words": [{"start": w["start"], "end": w["end"], "word": w["word"],
                       **({"spk": w["spk"]} if w.get("spk") else {}),
                       **{k: True for k in ("removed", "bleep", "filler", "maybe") if w.get(k)}}
                      for w in self.words],
            "bleep_mode": self.bleep_mode, "bleep_sound": self.bleep_sound,
            "bleeps": [[round(a, 3), round(b, 3)] for a, b in self.bleeps],
            "swears": self.swears, "speakers": self.speakers, "warnings": self.warnings,
            "mask_captions": self.mask_captions,
            "zoom_level": self.zoom_level, "pulses": [p.to_dict() for p in self.pulses],
            "music": self.music, "brand": self.brand is not None,
            "intro_s": self.intro_s, "outro_s": self.outro_s,
            "loop": self.loop.to_dict() if self.loop is not None else None,
            "fx": self.fx.to_dict() if self.fx is not None else None,
        }


def swear_review(project: Project, words: list[dict], lang: str | None, start: float, end: float,
                 edit: dict, vdata: dict | None = None, use_hints: bool = True,
                 strictness: str = "normal", scan: dict | None = None) -> list[dict]:
    """Every detected / "maybe" swear of the clip with "bleep" = what the render does, plus
    the user's manual bleeps (time ranges, status "manual"). Where the deep check
    (voices/swearscan.py) ran, its voted, aligned items replace the transcript's own."""
    from . import swears

    hints = []
    if use_hints:
        from .. import voices as voices_mod
        from ..voices import swearscan

        hints = voices_mod.hints_for(project, start, end, vdata)
        scan = scan if scan is not None else swearscan.load(project)
    items = [it for it in swears.detect(words, lang, hints) if start - 0.05 <= it["start"] <= end + 0.05]
    if use_hints:  # 1.2.31: the main transcript too, where the voice pass replaced its words
        items = _add_main_transcript(project, items, words, lang, start, end)
    if scan is not None:
        from ..voices import swearscan

        if swearscan.covers(scan, start, end):
            items = merge_scan(items, swearscan.items_for(scan, start, end), words, lang)
    add = [(float(a), float(b)) for a, b in (edit.get("bleep") or [])]
    remove = [(float(a), float(b)) for a, b in (edit.get("unbleep") or [])]
    for it in items:
        it["bleep"] = swears.bleeped(it, strictness)
        if swears.in_ranges(it["start"], it["end"], remove):
            it["bleep"] = False
        elif swears.in_ranges(it["start"], it["end"], add):
            it["bleep"] = True
    for a, b in add:
        if b <= a or b < start or a > end:
            continue
        inside = [i for i, w in enumerate(words) if a - 0.02 <= w["start"] and w["end"] <= b + 0.02]
        if any(swears.in_ranges(it["start"], it["end"], [(a, b)]) for it in items) and \
                all(any(it.get("i") == i for it in items) for i in inside):
            continue  # a detected swear the user switched on again
        text = " ".join(words[i]["word"] for i in inside)
        spk = words[inside[0]].get("spk") if inside else None
        items.append({"i": inside[0] if len(inside) == 1 else None, "start": round(a, 3), "end": round(b, 3),
                      "word": text, "spk": spk, "status": "manual", "why": "manual", "score": 1.0,
                      "bleep": True})
        for i in inside:
            words[i]["bleep"] = True
    items.sort(key=lambda it: it["start"])
    return items


def _add_main_transcript(project: Project, items: list[dict], words: list[dict], lang: str | None,
                         start: float, end: float) -> list[dict]:
    """Swears the main transcript has that the clip's words (the voice pass) don't: every
    speaker, every reading. Added as their own items (same "sure" / "maybe" as found)."""
    from . import swears

    try:
        base, _l = transcript_words(project, start, end, voices=False)
    except Exception:  # noqa: BLE001 - no transcript: nothing to add
        return items
    if not base or [w["word"] for w in base] == [w["word"] for w in words]:
        return items
    out = list(items)
    for it in swears.detect(base, lang):
        if not (start - 0.05 <= it["start"] <= end + 0.05):
            continue
        if any(o["start"] < it["end"] + 0.1 and o["end"] > it["start"] - 0.1 for o in out):
            continue
        under = [i for i, w in enumerate(words) if w["start"] < it["end"] + 0.05 and w["end"] > it["start"] - 0.05]
        alike = [i for i in under if swears.sounds_alike(words[i]["word"], it["word"], lang)]
        out.append({**it, "i": alike[0] if alike else None, "why": it["why"] + "+main",
                    "spk": words[under[0]].get("spk") if under else it.get("spk")})
    out.sort(key=lambda it: it["start"])
    return out


def merge_scan(items: list[dict], scanned: list[dict], words: list[dict], lang: str | None) -> list[dict]:
    """The deep check's items (voted over passes, exact times, checked bleep ranges) + the
    transcript's own items it has nothing for (learned words, edits made since)."""
    from .words import token

    out = []
    for s in scanned:
        it = {"i": None, "start": s["start"], "end": s["end"], "word": s["word"], "spk": s.get("spk"),
              "status": s["status"], "why": s.get("why", "scan"), "score": float(s.get("score", 0.5)),
              "votes": s.get("votes"), "heard": s.get("heard"), "aligned": bool(s.get("aligned"))}
        if s.get("bleep"):
            it["bleep_at"] = [float(s["bleep"][0]), float(s["bleep"][1])]
        # 1.2.22: the deep check only ADDS bleeps. A caption word is censored only when the
        # caption itself says a swear there (the same word, or one the caption detector flags);
        # a "maybe" from a prompted pass never masks "Orası" or "kahretsin".
        under = [i for i, w in enumerate(words) if w["start"] < s["end"] + 0.05 and w["end"] > s["start"] - 0.05]
        flagged = {d["i"] for d in items if d.get("i") is not None}
        pick = [i for i in under if i in flagged or token(words[i]["word"], lang) == token(s["word"], lang)]
        if pick:
            it["i"] = pick[0]
        if under and not it["spk"]:
            it["spk"] = words[under[0]].get("spk")
        out.append(it)
    for it in items:
        twin = next((s for s in out if s["start"] < it["end"] + 0.1 and s["end"] > it["start"] - 0.1), None)
        if twin is None:
            out.append(it)
            continue
        if it["status"] == "sure" and twin["status"] != "sure":
            twin.update(status="sure", score=1.0, why=twin["why"] + "+" + it["why"])
        if twin.get("i") is None and it.get("i") is not None:
            twin["i"] = it["i"]
    out.sort(key=lambda it: it["start"])
    return out


def legacy_review(words: list[dict], lang: str | None, start: float, end: float, edit: dict,
                  strictness: str) -> list[dict]:
    """The 1.2.20 detector (word list + fuzzy) with the user's review choices."""
    from . import swears

    items = [it for it in swears.detect(words, lang, legacy=True) if start - 0.05 <= it["start"] <= end + 0.05]
    remove = [(float(a), float(b)) for a, b in (edit.get("unbleep") or [])]
    add = [(float(a), float(b)) for a, b in (edit.get("bleep") or [])]
    for it in items:
        it["bleep"] = swears.bleeped(it, strictness) and not swears.in_ranges(it["start"], it["end"], remove)
    for a, b in add:
        if b > a and not any(swears.in_ranges(it["start"], it["end"], [(a, b)]) for it in items):
            items.append({"i": None, "start": a, "end": b, "word": "", "spk": None, "status": "manual",
                          "why": "manual", "score": 1.0, "bleep": True})
    return sorted(items, key=lambda it: it["start"])


def _safety_net(plan, words: list[dict], lang: str | None, start: float, end: float, edit: dict) -> None:
    """Never fewer bleeps than 1.2.20: a sure swear of the old detector that nothing covers (and
    the user didn't unbleep) is added back, with a warning."""
    from . import swears

    try:
        old = [it for it in swears.detect(words, lang, legacy=True) if it["status"] == "sure"
               and start - 0.05 <= it["start"] <= end + 0.05]
    except Exception:  # noqa: BLE001
        return
    remove = [(float(a), float(b)) for a, b in (edit.get("unbleep") or [])]
    on = [it for it in plan.swears if it.get("bleep")]
    added = False
    for it in old:
        if swears.in_ranges(it["start"], it["end"], remove):
            continue
        mid = (it["start"] + it["end"]) / 2
        if any(o["start"] - 0.1 <= mid <= o["end"] + 0.1 for o in on):
            continue
        twin = next((o for o in plan.swears if o.get("i") == it["i"] and it["i"] is not None), None)
        if twin is not None:
            twin["bleep"] = True
        else:
            plan.swears.append({**it, "bleep": True, "why": it["why"] + "+safety"})
        added = True
    if added:
        plan.swears.sort(key=lambda it: it["start"])
        plan.warnings.append("swear_safety_net")


# Bleep padding (seconds before, after) around a swear without a checked range from the deep
# check: Whisper's word times are often 50-200 ms off, so a little more for vertical videos.
BLEEP_PAD = {"normal": (0.08, 0.12), "strict": (0.12, 0.18), "paranoid": (0.15, 0.22)}
BLEEP_MERGE_GAP = 0.15


def build(project: Project, cand: dict, opts, *, vertical: bool = True, fps: float = 30.0,
          edit: dict | None = None, words: list[dict] | None = None, lang: str | None = None,
          max_len: float | None = None) -> EditPlan:
    """opts: clips.ClipOptions. edit: {"deleted": [[a, b]...], "music": name | "" | None}
    (default: cand["edit"]). words / lang: transcript words (tests), else read from disk.
    max_len: the platform's length limit (seamless loop: the end never moves past it)."""
    start, end = float(cand["start"]), float(cand["end"])
    edit = edit if edit is not None else (cand.get("edit") or {})
    given = words is not None
    if words is None:
        words, lang = transcript_words(project, start, end)
    fps = max(1.0, float(fps))
    raw_deleted = [(float(a), float(b)) for a, b in (edit.get("deleted") or []) if float(b) > float(a)]

    # ---- seamless loop: move the end (and a start inside a word) to the best seam first
    seam = None
    if getattr(opts, "loop", False):
        from . import loop

        swear = []
        if profanity.resolve(getattr(opts, "profanity", "off"), vertical) != "off":
            near, _l = (words, lang) if given else transcript_words(project, end - loop.SEARCH_BACK - 1,
                                                                    end + loop.SEARCH_FWD + 1)
            swear = [(near[i]["start"], near[i]["end"]) for i in profanity.find_words(near, lang)]
        seam = loop.seam_for(project, start, end, max_len=float(max_len or loop.DEFAULT_MAX_SECONDS),
                             deleted=raw_deleted, bleeps=swear, words=words if given else None)
        start, end = seam.start, seam.end
        if given:
            words = [w for w in words if start <= (w["start"] + w["end"]) / 2 <= end]
        else:
            words, lang = transcript_words(project, start, end)
    words = [dict(w) for w in words]

    # ---- cuts
    deleted = merge([(max(start, a), min(end, b)) for a, b in raw_deleted])
    auto: list[tuple[float, float, str]] = []
    level = getattr(opts, "cuts", "off")
    if level in ("light", "strong"):
        for i in fillers.find_fillers(words, lang, level):
            auto.append((words[i]["start"] - 0.02, words[i]["end"] + 0.02, "filler"))
            words[i]["filler"] = True
        if project.audio_path.is_file():
            db = silence.frame_db(project.audio_path, start, end)
            speech = [(w["start"], w["end"]) for w in words if not w.get("filler")]
            pad = CUT_PAD[level]
            for a, b in silence.find_silences(db, speech, silence_ms(level) / 1000, start):
                a2, b2 = (a + pad if a > start + 0.05 else a), (b - pad if b < end - 0.05 else b)
                if b2 - a2 >= MIN_CUT:
                    auto.append((a2, b2, "silence"))
        protect = [(t - 0.8, t + 1.6) for t in laugh_times(project, start, end)]
        protect += [(float(r["t"]) - 0.8, float(r["t"]) + 1.6) for r in cand.get("reasons") or []
                    if str(r.get("code")) in PROTECT_CODES or str(r.get("code", "")).startswith(("df_", "lol_"))]
        kept_auto = []
        for a, b, kind in auto:
            for x, y in subtract([(a, b)], protect):
                if y - x >= MIN_CUT:
                    kept_auto.append((x, y, kind))
        auto = kept_auto

    removed = [{"a": a, "b": b, "kind": "deleted"} for a, b in deleted]
    for a, b, kind in auto:
        for x, y in subtract([(max(start, a), min(end, b))], deleted):
            if y - x >= MIN_CUT:
                removed.append({"a": x, "b": y, "kind": kind})
    removed.sort(key=lambda r: r["a"])
    if len(removed) > MAX_SEGMENTS:  # too many tiny cuts: keep the longest
        removed = sorted(sorted(removed, key=lambda r: -(r["b"] - r["a"]))[:MAX_SEGMENTS], key=lambda r: r["a"])

    # Kept ranges on the frame grid.
    def q(t: float) -> float:
        return start + round((t - start) * fps) / fps

    keep = []
    for a, b in subtract([(start, end)], [(r["a"], r["b"]) for r in removed]):
        a, b = q(a), q(b)
        if b - a >= MIN_KEEP - 1e-6:
            keep.append((a, b))
    if not keep:
        raise SharkyClipsError("Nothing is left of this clip after the cuts.",
                               "Restore some words in the transcript editor.")
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        if not any(a <= mid <= b for a, b in keep):
            w["removed"] = True

    plan = EditPlan(start, end, fps, keep, removed, words, lang)
    if getattr(opts, "dub", ""):
        from .. import dub as dub_mod

        plan.dub = dub_mod.track_for(project, cand, opts.dub)
    plan.loop = seam

    # ---- speakers (voice pass)
    vdata = None
    if not given:
        from .. import voices as voices_mod

        vdata = voices_mod.load(project)
        if vdata and any(w.get("spk") for w in words):
            names = voices_mod.speaker_names(vdata)
            plan.speakers = {k: names.get(k, "") for k in (vdata.get("speakers") or {})}

    # ---- swear words: every speaker, misheard ones, other passes (edit/swears.py) + the user's
    # own choices in the review list (edit "bleep" = add, "unbleep" = remove)
    mode = profanity.resolve(getattr(opts, "profanity", "off"), vertical)
    from . import swears as swears_mod

    strictness = swears_mod.resolve_strictness(getattr(opts, "swear_strict", "auto"), vertical)
    plan.strictness = strictness
    try:
        plan.swears = swear_review(project, words, lang, start, end, edit, vdata,
                                   use_hints=not given, strictness=strictness)
    except Exception as exc:  # noqa: BLE001 - the newer detection broke: the 1.2.20 detector, visibly
        from ..ui import console

        console.print(f"[yellow]Swear check failed ({exc!r}): using the basic detector.[/]")
        plan.warnings.append("swear_check_failed")
        plan.swears = legacy_review(words, lang, start, end, edit, strictness)
    _safety_net(plan, words, lang, start, end, edit)
    if mode != "off":
        ranges = []
        pre, post = BLEEP_PAD.get(strictness, BLEEP_PAD["normal"])
        for it in plan.swears:
            if not it["bleep"]:
                continue
            if it.get("i") is not None:
                words[it["i"]]["bleep"] = True
                if words[it["i"]].get("removed"):
                    continue
            if it.get("bleep_at"):  # aligned + checked by the deep check (+ the word's own time:
                # 1.2.31, a misaligned check range never leaves the word itself unbleeped)
                ranges.append((float(it["bleep_at"][0]), float(it["bleep_at"][1])))
                ranges.append((it["start"] - pre, it["end"] + post))
            elif it["status"] == "manual":
                ranges.append((it["start"], it["end"]))
            else:
                ranges.append((it["start"] - pre, it["end"] + post))
        plan.bleep_mode = mode
        plan.bleep_sound = getattr(opts, "bleep_sound", "classic") or "classic"
        plan.mask_captions = bool(getattr(opts, "profanity_captions", True))
        plan.censor_full = bool(getattr(opts, "bleep_visual", True))
        if not given and ranges:  # widened after a render where part of a swear was still heard
            from ..voices import swearscan

            fixes = [(float(x), float(y)) for x, y in swearscan.load_fixes(project).get(str(cand.get("id")), [])]
            ranges += [f for f in fixes if any(f[0] < b + 0.2 and f[1] > a - 0.2 for a, b in ranges)]
        plan.bleep_src = merge(ranges, BLEEP_MERGE_GAP)
        plan.bleeps = plan.out_ranges(plan.bleep_src)
    for it in plan.swears:
        if it.get("i") is not None and it["status"] == "maybe" and not it["bleep"]:
            words[it["i"]]["maybe"] = True

    # ---- caption proofreading (text only: times and bleeps stay; swears were found above)
    if not given:
        from . import proof

        fixed = proof.fix_words(words, lang, proof.cached_fixes(project, cand.get("id")))
        for w, f in zip(words, fixed):
            if f["word"] != w["word"]:
                w["orig"], w["word"] = w["word"], f["word"]

    # ---- zoom
    plan.zoom_level = zoom.INTENSITY.get(getattr(opts, "zoom", "off"), 0.0)
    if plan.zoom_level > 1.0:
        laughs = laugh_times(project, start, end)
        plan.pulses = zoom.pulses(cand, laughs)  # pulses lost to cuts drop out in out_pulses()

    # ---- music + brand
    if getattr(opts, "music", False):
        from . import music

        choice = edit.get("music")
        if choice:  # chosen by hand
            t = music.track(choice)
            plan.music = None if t is None else {"name": t["name"], "title": t["title"], "artist": t["artist"],
                                                 "best_start": t["best_start"], "duration": t["duration"],
                                                 "lufs": t["lufs"], "why": "manual"}
        elif choice is None:  # "" = no music for this clip
            mode_name = project.load_meta().get("mode")
            s = music.suggest({**cand, "duration": plan.out_duration}, mode_name)
            t = music.track(s["name"]) if s else None
            if s and t:
                plan.music = {"name": t["name"], "title": t["title"], "artist": t["artist"],
                              "best_start": t["best_start"], "duration": t["duration"], "lufs": t["lufs"],
                              "why": s["why"], "mood": s["mood"]}
        if plan.music and config.get("music_credit_enabled") is not False:
            plan.music["credit"] = music.credit_line(plan.music)
    if getattr(opts, "brand", False):
        from . import brand

        plan.brand = brand.active_preset()
        plan.intro_s, plan.outro_s = brand.card_seconds(plan.brand)
        if seam is not None:  # a card would break the loop (the watermark / handle stay)
            plan.intro_s = plan.outro_s = 0.0

    # ---- fun effects: instant replay, meme effects, chat bubbles (never in a seamless loop)
    if seam is None:
        from . import fx

        plan.fx = fx.build(project, cand, opts, plan, max_len=max_len)
    if plan.dub is not None and plan.bleeps:  # a dubbed line is new speech: the swears were translated away
        dubbed = plan.out_ranges([(float(x["start"]), float(x["end"])) for x in plan.dub.get("lines") or [] if x.get("dub")])
        plan.bleeps = [(a, b) for a, b in plan.bleeps if not any(a < y and b > x for x, y in dubbed)]
    return plan
