"""Fun effects (1.2.17): instant replay, meme effects and chat bubbles.

They add pieces to the clip's timeline ("inserts") and layers on top of it:

- instant replay (options.replay "auto"): the clip's key event (pentakill, multikill,
  extraction, kill, a loud peak, your marker) again in slow motion (0.5x) with frame
  interpolation, a gentle push-in on the action and a small REPLAY badge. It plays at the end
  of the clip, or right after the event when the clip goes on for a while after it. Captions
  and chat bubbles pause during the replay.
- meme effects (options.memes light | strong): on a funny moment (laughter, a reaction word)
  the picture freezes, zooms in and shows a short caption the local AI wrote in the output
  language ("bruh", "NASIL?!"); on a fail (death, failed extraction) a quick zoom (light) or
  a shake (strong). Sounds are synthesized (sfx.py). Light = one of each at most, strong = two.
- chat bubbles (options.chat_bubbles): bubbles.py.

Times: "main" = the main part's output time (after cuts; EditPlan.to_out). Inserts shift
everything after them; `final()` maps main time to the timeline with the inserts.
Nothing here runs in a seamless loop (an insert would break the seam).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np

REPLAY_SPEED = 0.5
REPLAY_BEFORE, REPLAY_AFTER = 2.0, 0.8  # source seconds around the event
REPLAY_MIN_LEFT = 6.0  # the clip goes on this long after the event: replay right after it
FREEZE_S = {"light": 1.0, "strong": 1.2}
SHAKE_S = 0.55
MEME_COUNT = {"light": 1, "strong": 2}
MIN_APART = 2.5  # seconds between effects
HOOK_GUARD = 1.5  # nothing in the first seconds (the hook)

# What deserves a replay, best first (code -> priority). Markers: the user said "this one".
REPLAY_CODES = {
    "lol_pentakill": 100, "lol_quadrakill": 90, "lol_baron_steal": 88, "df_extracted": 85, "lol_triplekill": 80,
    "lol_dragon_steal": 78, "df_multikill": 76, "lol_ace": 70, "lol_shutdown": 62, "lol_doublekill": 60,
    "marker": 58, "df_revenge": 52, "lol_first_blood": 50, "df_kill": 44, "lol_kill": 42,
    "loudness_spike": 30, "shouting": 26, "scream": 26, "cheering": 24,
}
FUNNY_CODES = {"laughter": 1.0, "keyword": 0.6}
FAIL_CODES = {"df_death": 1.0, "lol_death": 1.0, "df_extract_failed": 0.9, "lol_defeat": 0.7}

FALLBACK_CAPTIONS = {
    "en": ["bruh", "NO WAY", "WHAT?!", "bro…"],
    "tr": ["NASIL?!", "bruh", "YOK ARTIK", "kanka…"],
    "de": ["WIE?!", "bruh", "NIEMALS", "Alter…"],
    "hu": ["MI?!", "bruh", "NEM HISZEM", "tesó…"],
    "ru": ["ЧТО?!", "брух", "НЕ МОЖЕТ БЫТЬ", "бро…"],
    "ar": ["ماذا؟!", "bruh", "مستحيل", "يا أخي…"],
    "zh": ["啊？！", "离谱", "不是吧", "绷不住了"],
}


@dataclass
class Insert:
    at: float  # main time where it goes
    dur: float  # output seconds
    kind: str  # replay | freeze
    src: float  # replay: source start / freeze: the frozen frame (source time)
    src_end: float = 0.0  # replay: source end
    text: str = ""  # freeze: the meme caption
    code: str = ""  # what triggered it

    def to_dict(self) -> dict:
        return {"at": round(self.at, 3), "dur": round(self.dur, 3), "kind": self.kind, "src": round(self.src, 3),
                "src_end": round(self.src_end, 3), "text": self.text, "code": self.code}


@dataclass
class FxPlan:
    inserts: list[Insert] = field(default_factory=list)
    shakes: list[tuple[float, float]] = field(default_factory=list)  # main time (strong fails)
    punches: list[tuple[float, float]] = field(default_factory=list)  # main time (light fails: quick zoom)
    sfx: list[tuple[float, str, float]] = field(default_factory=list)  # (main time, sound, gain)
    bubbles: list[dict] = field(default_factory=list)  # main time
    memes: str = "off"
    smooth: str = "blend"  # replay interpolation: "mci" (motion) | "blend"

    @property
    def active(self) -> bool:
        return bool(self.inserts or self.shakes or self.punches or self.bubbles)

    @property
    def extra(self) -> float:
        return sum(i.dur for i in self.inserts)

    def final(self, t: float, end: bool = False) -> float:
        """Main time -> timeline time. A moment exactly at an insert comes after it (end=True:
        a range ending there ends before it)."""
        if end:
            return t + sum(i.dur for i in self.inserts if i.at < t - 1e-6)
        return t + sum(i.dur for i in self.inserts if i.at <= t + 1e-6)

    def insert_ranges(self) -> list[tuple[float, float, Insert]]:
        """(timeline start, timeline end, insert)."""
        out = []
        for ins in sorted(self.inserts, key=lambda i: i.at):
            a = self.final(ins.at, end=True)
            out.append((a, a + ins.dur, ins))
        return out

    def fingerprint(self) -> str:
        d = {"i": [i.to_dict() for i in self.inserts], "s": self.shakes, "p": self.punches,
             "x": [(round(a, 2), n, g) for a, n, g in self.sfx],
             "b": [(b["a"], b["user"], b["text"]) for b in self.bubbles], "m": self.smooth}
        return hashlib.sha1(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()[:10]

    def to_dict(self) -> dict:
        return {"inserts": [i.to_dict() for i in self.inserts], "shakes": [list(s) for s in self.shakes],
                "punches": [list(p) for p in self.punches], "sfx": [list(s) for s in self.sfx],
                "bubbles": self.bubbles, "memes": self.memes, "smooth": self.smooth, "extra": round(self.extra, 3)}


# ===================================================================== choosing the moments


def replay_event(cand: dict, plan) -> dict | None:
    """The clip's key event that survives the cuts: {"t", "code", "priority"} or None."""
    best = None
    for r in cand.get("reasons") or []:
        code, t = str(r.get("code", "")), float(r.get("t", -1))
        pri = REPLAY_CODES.get(code)
        if pri is None or not (plan.start + 0.8 <= t <= plan.end) or plan.to_out(t) is None:
            continue
        if code == "df_multikill":
            try:
                pri += min(20, 5 * int(str(r.get("value") or "2").split()[0]))
            except ValueError:
                pass
        score = pri + 10 * float(r.get("strength") or 0.5)
        if best is None or score > best["score"]:
            best = {"t": t, "code": code, "score": score}
    return best


def _word_gap(words: list[dict], lo: float, hi: float) -> float | None:
    """A main-time moment between two words in [lo, hi] (the longest pause), else None."""
    best, best_gap = None, 0.12
    prev_end = None
    for w in words:
        if prev_end is not None and lo <= (prev_end + w["start"]) / 2 <= hi and w["start"] - prev_end > best_gap:
            best, best_gap = (prev_end + w["start"]) / 2, w["start"] - prev_end
        prev_end = w["end"]
    return best


def _moments(cand: dict, plan, codes: dict, laughs: list[float]) -> list[tuple[float, str, float]]:
    out = []
    for r in cand.get("reasons") or []:
        code, t = str(r.get("code", "")), float(r.get("t", -1))
        if code in codes and plan.start <= t <= plan.end:
            out.append((t, code, codes[code] * float(r.get("strength") or 0.5)))
    if "laughter" in codes:
        out += [(t, "laughter", 0.5) for t in laughs]
    return sorted(out, key=lambda m: -m[2])


def _free(t: float, taken: list[float], dur: float) -> bool:
    return t >= HOOK_GUARD and t <= dur - 0.6 and all(abs(t - x) >= MIN_APART for x in taken)


def build(project, cand: dict, opts, plan, max_len: float | None = None) -> FxPlan | None:
    """The clip's effects (None when none applies). plan: the EditPlan (cuts already decided)."""
    replay = getattr(opts, "replay", "off") == "auto"
    memes = getattr(opts, "memes", "off")
    bubbles_on = bool(getattr(opts, "chat_bubbles", False))
    if plan.loop is not None or not (replay or memes in MEME_COUNT or bubbles_on):
        return None
    fx = FxPlan(memes=memes if memes in MEME_COUNT else "off")
    dur = plan.out_duration
    words = plan.out_words()
    taken: list[float] = []
    limit = float(max_len) if max_len else None

    def room(extra: float) -> bool:
        return limit is None or dur + fx.extra + extra + plan.intro_s + plan.outro_s <= limit - 0.1

    # ---- instant replay
    if replay:
        ev = replay_event(cand, plan)
        if ev is not None:

            meta = project.load_meta() if project is not None else {}
            src_len = float(meta.get("duration") or plan.end + 10)
            a = max(0.0, ev["t"] - REPLAY_BEFORE)
            b = min(src_len, ev["t"] + REPLAY_AFTER)
            src_dur = b - a
            out_dur = round(src_dur / REPLAY_SPEED * plan.fps) / plan.fps
            t_out = plan.to_out(ev["t"]) or 0.0
            at = dur
            if dur - t_out >= REPLAY_MIN_LEFT:  # the clip goes on: right after the reaction
                gap = _word_gap(words, t_out + 1.2, min(dur - 2.0, t_out + 5.0))
                at = gap if gap is not None else dur
            at = round(at * plan.fps) / plan.fps
            if src_dur >= 1.0 and room(out_dur):
                fx.inserts.append(Insert(at, out_dur, "replay", round(a, 3), round(b, 3), code=ev["code"]))
                fx.sfx.append((at, "whoosh", 0.55))
                taken.append(t_out)
                taken.append(at)

    # ---- meme effects
    if fx.memes != "off":
        from .plan import laugh_times

        n = MEME_COUNT[fx.memes]
        laughs = laugh_times(project, plan.start, plan.end) if project is not None else []
        texts = cached_captions(project, cand) if project is not None else []
        lang = meme_language(project, cand)
        fallback = FALLBACK_CAPTIONS.get(lang or "en", FALLBACK_CAPTIONS["en"])
        made = 0
        for t, code, _s in _moments(cand, plan, FUNNY_CODES, laughs):
            o = plan.to_out(t)
            if made >= n or o is None or not _free(o, taken, dur):
                continue
            fd = FREEZE_S[fx.memes]
            if not room(fd):
                break
            at = round(o * plan.fps) / plan.fps
            text = (texts[made] if made < len(texts) else fallback[made % len(fallback)])
            fx.inserts.append(Insert(at, fd, "freeze", round(t, 3), text=text, code=code))
            fx.sfx.append((at, "boom", 0.7 if fx.memes == "strong" else 0.45))
            taken.append(o)
            made += 1
        made = 0
        for t, _code, _s in _moments(cand, plan, FAIL_CODES, []):
            o = plan.to_out(t)
            if made >= n or o is None or not _free(o, taken, dur):
                continue
            a, b = o, min(dur, o + SHAKE_S)
            if fx.memes == "strong":
                fx.shakes.append((round(a, 3), round(b, 3)))
            else:
                fx.punches.append((round(a, 3), round(min(dur, a + 0.9), 3)))
            fx.sfx.append((a, "thud", 0.75 if fx.memes == "strong" else 0.5))
            taken.append(o)
            made += 1

    # ---- chat bubbles
    if bubbles_on and project is not None:
        from ..chat import load_chat
        from . import bubbles

        fx.bubbles = bubbles.pick(load_chat(project), plan, plan.start, plan.end)

    fx.inserts.sort(key=lambda i: i.at)
    rp = next((i for i in fx.inserts if i.kind == "replay"), None)
    fx.smooth = interpolation(project.load_meta() if project is not None else None,
                              (rp.src_end - rp.src) if rp is not None else 2.8)
    return fx if fx.active else None


MCI_WIDTH = 1280  # motion interpolation runs at most this wide (ffmpeg's minterpolate is single-threaded)
MCI_S_PER_MPX = 0.44 * 24  # measured: 0.44 s per megapixel-frame on a 24-thread laptop CPU
MCI_BUDGET_S = 40.0  # "fast enough": one replay may cost this much extra render time


def interpolation(meta: dict | None = None, src_seconds: float = 2.8) -> str:
    """How the slow motion gets its in-between frames (config replay_smooth auto | motion | blend).

    auto: a 50/60 fps recording blends (frames 16 ms apart barely ghost); a 30 fps one gets
    motion interpolation when this PC does it within ~40 s, else frame blending."""
    import os

    from .. import config

    want = str(config.get("replay_smooth") or "auto")
    if want in ("motion", "blend"):
        return "mci" if want == "motion" else "blend"
    meta = meta or {}
    fps = float(meta.get("fps") or 30)
    if fps >= 48:
        return "blend"
    w, h = float(meta.get("width") or 1920), float(meta.get("height") or 1080)
    if w > MCI_WIDTH:
        w, h = MCI_WIDTH, h * MCI_WIDTH / w
    mpx_frames = w * h / 1e6 * src_seconds * fps
    cost = MCI_S_PER_MPX / max(1, os.cpu_count() or 4) * mpx_frames
    return "mci" if cost <= MCI_BUDGET_S else "blend"


# ===================================================================== meme captions (local AI)


def meme_language(project, cand: dict) -> str:
    from .. import config

    pub = cand.get("publish") or {}
    lang = pub.get("language") or config.get("output_language")
    if not lang or lang == "auto":
        try:
            from ..project import read_json

            lang = read_json(project.transcript_path).get("language") if project.transcript_path.is_file() else None
        except Exception:  # noqa: BLE001
            lang = None
    return str(lang or "en")


def needs_captions(project, cand: dict) -> bool:
    """Has the clip a funny moment a freeze frame could go on?"""
    if any(str(r.get("code")) in FUNNY_CODES for r in cand.get("reasons") or []):
        return True
    from .plan import laugh_times

    return bool(laugh_times(project, float(cand["start"]), float(cand["end"])))


def _caption_path(project):
    return project.cache_dir / "memes.json"


def _caption_key(cand: dict, lang: str) -> str:
    return hashlib.sha1(json.dumps([cand.get("id"), cand.get("text", "")[:400], lang]).encode()).hexdigest()[:12]


def cached_captions(project, cand: dict) -> list[str]:
    try:
        from ..project import read_json

        p = _caption_path(project)
        data = read_json(p) if p.is_file() else {}
        got = data.get(str(cand.get("id"))) or {}
        if got.get("key") == _caption_key(cand, meme_language(project, cand)):
            return [str(x) for x in got.get("texts") or []][:4]
    except Exception:  # noqa: BLE001
        pass
    return []


CAPTION_SCHEMA = {"type": "object", "required": ["captions"], "properties": {
    "captions": {"type": "array", "minItems": 2, "maxItems": 4, "items": {"type": "string", "maxLength": 22}}}}


def write_captions(project, cand: dict, model) -> list[str]:
    """Ask the local AI for 2-4 very short meme reactions in the output language (cached)."""
    from .. import languages
    from ..project import write_json_atomic

    lang = meme_language(project, cand)
    have = cached_captions(project, cand)
    if have:
        return have
    info = languages.get(lang)
    name = info.english_name if info else lang
    system = ("You write tiny meme captions for funny gaming clips: 1-3 words, max 18 characters, like a "
              "viewer's reaction (e.g. 'bruh', 'NO WAY', 'NASIL?!'). Write them in the requested language, "
              "natural slang, no hashtags, no emoji, nothing offensive. Answer in JSON.")
    prompt = (f"Language: {name} ({lang}).\nWhat happens in the clip (transcript):\n"
              f"{(cand.get('text') or '')[:900]}\n\nGive 3 different captions.")

    def check(d: dict) -> list[str]:
        bad = [c for c in d.get("captions", []) if not str(c).strip() or len(str(c)) > 22 or "#" in str(c)]
        return [f"caption too long or empty: {c!r}" for c in bad]

    data = model.json(system, prompt, CAPTION_SCHEMA, temperature=0.9, check=check, num_predict=200)
    texts = [" ".join(str(c).split())[:22] for c in data.get("captions", []) if str(c).strip()][:4]
    if texts:
        from ..project import read_json

        p = _caption_path(project)
        try:
            cur = read_json(p) if p.is_file() else {}
        except (OSError, ValueError):
            cur = {}
        cur[str(cand.get("id"))] = {"key": _caption_key(cand, lang), "texts": texts, "lang": lang}
        p.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(p, cur)
    return texts


# ===================================================================== sound


def splice_audio(main: np.ndarray, fx: FxPlan, source, sr: int, has_audio: bool, decode) -> np.ndarray:
    """main (main time, stereo) -> the timeline with the inserts' sound and the effects."""
    from . import sfx as sfx_mod

    def n(t: float) -> int:
        return int(round(t * sr))

    def fade(y: np.ndarray, a: float, b: float) -> np.ndarray:
        y = y.copy()
        ia, ib = min(len(y), n(a)), min(len(y), n(b))
        if ia:
            y[:ia] *= np.linspace(0, 1, ia, dtype=np.float32)[:, None]
        if ib:
            y[len(y) - ib:] *= np.linspace(1, 0, ib, dtype=np.float32)[:, None]
        return y

    parts: list[np.ndarray] = []
    cur = 0
    for ins in sorted(fx.inserts, key=lambda i: i.at):
        cut = min(len(main), n(ins.at))
        seg = main[cur:cut]
        if len(seg):
            parts.append(fade(seg, 0.0 if cur == 0 else 0.012, 0.012))
        k = n(ins.dur)
        if ins.kind == "replay" and has_audio:
            raw = decode(source, ins.src, ins.src_end - ins.src, sr=sr, channels=2)
            if len(raw):
                # Slow motion: twice as long, an octave lower (the classic slow-mo sound).
                x = np.linspace(0, len(raw) - 1, max(2, k))
                slow = np.stack([np.interp(x, np.arange(len(raw)), raw[:, c]) for c in range(2)], 1)
                piece = fade(slow.astype(np.float32) * np.float32(0.8), 0.08, 0.15)
            else:
                piece = np.zeros((k, 2), np.float32)
        else:
            piece = np.zeros((k, 2), np.float32)
        piece = np.concatenate([piece, np.zeros((max(0, k - len(piece)), 2), np.float32)])[:k]
        parts.append(piece)
        cur = cut
    rest = main[cur:]
    if len(rest):
        parts.append(fade(rest, 0.012 if cur else 0.0, 0.0))
    out = np.concatenate(parts) if parts else main.copy()
    for t, name, gain in fx.sfx:
        s = sfx_mod.sound(name) * np.float32(gain)
        a = n(fx.final(t, end=True))
        b = min(len(out), a + len(s))
        if b > a:
            out[a:b] += s[: b - a]
    for ins in fx.inserts:  # the replay ends with a short rewind chirp back into the clip
        if ins.kind == "replay":
            s = sfx_mod.sound("rewind") * np.float32(0.35)
            a = n(fx.final(ins.at, end=True) + ins.dur - 0.3)
            b = min(len(out), a + len(s))
            if b > a > 0:
                out[a:b] += s[: b - a]
    return out


# ===================================================================== picture


def zoom_expr(z0: float, z1: float, frames: int, ease: str = "linear") -> str:
    """Zoom factor at frame `in`: z0 -> z1 over `frames` (perspective has no `t`)."""
    p = f"min(in/{max(1, frames)},1)"
    if ease == "out":
        p = f"(1-pow(1-{p},3))"
    return f"({z0:.4f}+{z1 - z0:.4f}*{p})"


def zoom_filter(z: str, cy: float = 0.5) -> str:
    left, right = f"W/2-W/2/{z}", f"W/2+W/2/{z}"
    top, bottom = f"H*{cy:g}-H*{cy:g}/{z}", f"H*{cy:g}+H*{1 - cy:g}/{z}"
    return (f"perspective=x0='{left}':y0='{top}':x1='{right}':y1='{top}':x2='{left}':y2='{bottom}':"
            f"x3='{right}':y3='{bottom}':interpolation=linear:eval=frame")


def shake_filter(shakes: list[tuple[float, float]], punches: list[tuple[float, float]], fps: int) -> str:
    """Shake (strong fails) and quick punch-in zooms (light fails) on the main picture."""
    if not shakes and not punches:
        return ""
    tt = f"(in/{fps})"
    amp = "+".join(f"between({tt},{a:.3f},{b:.3f})*(1-({tt}-{a:.3f})/{max(0.05, b - a):.3f})" for a, b in shakes) or "0"
    pun = "+".join(f"between({tt},{a:.3f},{b:.3f})*sin(PI*min(1,({tt}-{a:.3f})/{max(0.05, b - a):.3f}))"
                   for a, b in punches) or "0"
    z = f"(1+0.07*({amp})+0.12*({pun}))"
    dx = f"(W*0.018*({amp})*sin({tt}*71))"
    dy = f"(H*0.011*({amp})*cos({tt}*53))"
    left, right = f"W/2-W/2/{z}+{dx}", f"W/2+W/2/{z}+{dx}"
    top, bottom = f"H/2-H/2/{z}+{dy}", f"H/2+H/2/{z}+{dy}"
    enable = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in shakes + punches)
    return (f"perspective=x0='{left}':y0='{top}':x1='{right}':y1='{top}':x2='{left}':y2='{bottom}':"
            f"x3='{right}':y3='{bottom}':interpolation=linear:eval=frame:enable='{enable}'")


def slowmo_chain(fps: int, src_frames: int, out_frames: int, smooth: str, src_size: tuple[int, int]) -> str:
    """Source frames -> 0.5x slow motion at the output frame rate (same picture size: the
    layout crops in source pixels)."""
    if smooth == "mci":
        w, h = src_size
        interp = (f"scale='min({MCI_WIDTH},iw)':-2,"
                  f"minterpolate=fps={fps * 2}:mi_mode=mci:mc_mode=obmc:me_mode=bidir:vsbmc=0")
        if w > MCI_WIDTH:
            interp += f",scale={w}:{h}:flags=bicubic"
    else:
        interp = f"framerate=fps={fps * 2}:interp_start=0:interp_end=255:scene=100"
    return (f"fps={fps},trim=end_frame={src_frames},setpts=N/({fps}*TB),{interp},"
            f"setpts=N/({fps}*TB),trim=end_frame={out_frames}")


# ===================================================================== text (ASS)


def meme_font(lang: str | None) -> str:
    import platform

    if lang in ("zh", "ar", "ja", "ru"):
        from ..clips import _font_for

        return _font_for(lang)
    return {"Windows": "Impact", "Darwin": "Impact"}.get(platform.system(), "DejaVu Sans")


def ass_styles(lang: str | None, scale: float) -> list[str]:
    from .bubbles import style_line

    meme = meme_font(lang)
    s = max(1, round(118 * scale))
    return [
        f"Style: meme,{meme},{s},&H0000F0FF,&H0000F0FF,&H00000000,&H64000000,-1,0,0,0,"
        f"100,100,1,0,1,{max(1, round(8 * scale))},{max(1, round(4 * scale))},5,40,40,0,1",
        f"Style: replay,Arial,{max(1, round(40 * scale))},&H00FFFFFF,&H00FFFFFF,&H002A2AE0,&H00000000,-1,0,0,0,"
        f"100,100,3,0,3,{max(1, round(14 * scale))},0,7,0,0,0,1",
        style_line("Arial"),
    ]


def ass_lines(fx: FxPlan, lead: float, geo, layout: str, ts, lang: str | None, zone: dict | None) -> list[str]:
    """REPLAY badge, meme captions and chat bubbles (timeline times + lead)."""
    from . import bubbles as bubbles_mod
    from ..clips import SPLIT_TOP, _ass_escape

    out = []
    split = layout == "split"
    for a, b, ins in fx.insert_ranges():
        a, b = a + lead, b + lead
        if ins.kind == "replay":
            x = geo.margin_l - 20
            y = (SPLIT_TOP + 40) if split else max(geo.hook_y or 120, 160)
            out.append(f"Dialogue: 5,{ts(a)},{ts(b)},replay,,0,0,0,,{{\\an7\\pos({x},{y})\\fad(120,160)}}"
                       f"● REPLAY")
        elif ins.kind == "freeze" and ins.text:
            y = round((SPLIT_TOP + geo.h) / 2) if split else round(geo.h * 0.42)
            text = _ass_escape(ins.text)
            out.append(f"Dialogue: 5,{ts(a + 0.05)},{ts(b)},meme,,0,0,0,,{{\\an5\\pos({geo.cap_x},{y})\\frz4"
                       f"\\fscx40\\fscy40\\t(0,140,\\fscx112\\fscy112)\\t(140,260,\\fscx100\\fscy100)\\fad(0,120)}}{text}")
    if fx.bubbles and zone is not None:
        hidden = [(a + lead, b + lead) for a, b, _i in fx.insert_ranges()]
        items = []
        for bb in fx.bubbles:
            a, b = fx.final(bb["a"]) + lead, fx.final(bb["b"], end=True) + lead
            if b - a >= 0.8:
                items.append({**bb, "a": round(a, 3), "b": round(b, 3)})
        out += bubbles_mod.ass_lines(items, {**zone, "hidden": hidden}, "Arial", ts)
    return out


def bubble_zone(geo, layout: str, safe: tuple[int, int, int, int], wide: bool) -> dict:
    """Where chat bubbles go: bottom left, clear of the captions, the hook and the platform's
    own buttons (right side / bottom of Shorts, TikTok, Reels)."""
    top, right, bottom, left = safe
    if wide:
        return {"x": 60 + left, "bottom": geo.h - 260 - bottom, "w": 640, "scale": 0.72}
    if layout == "split":
        bottom_y = geo.h - max(380, bottom + 40)
    else:  # captions sit around cap_y (two lines ~210 px tall): stay above them
        bottom_y = min(geo.h - max(380, bottom + 40), (geo.cap_y or 1390) - 150)
    return {"x": 40 + left, "bottom": bottom_y, "w": geo.w - 40 - left - max(200, right + 40), "scale": 1.0}


def map_words(words: list[dict], fx: FxPlan) -> list[dict]:
    """Caption words (main time) -> timeline; a word cut by an insert ends before it."""
    out = []
    for w in words:
        nxt = min((i.at for i in fx.inserts if i.at > w["start"] + 1e-6), default=None)
        end = min(w["end"], nxt) if nxt is not None else w["end"]
        s, e = fx.final(w["start"]), fx.final(end, end=True)
        if e <= s:
            e = s + 0.05
        out.append({**w, "start": round(s, 3), "end": round(e, 3)})
    return out
