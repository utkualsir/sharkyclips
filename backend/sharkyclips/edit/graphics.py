"""Animated graphics on clips (1.2.58): a kill counter, multikill / ace / clutch banners, score and
round changes from the game events, and big spoken numbers from the transcript ("21 KILL", "1v4"),
with simple icons, in the brand colours.

Rules
- options.graphics: "minimal" (default) | "bold" | "off". Gaming clips only.
- At most one graphic at a time, each at most MAX_S (1.5 s), never in the first moment of the clip,
  never across an instant replay / freeze frame (it would be cut in two).
- Never over the facecam, the captions, the hook / banner, the key action (the middle of the
  gameplay picture), chat bubbles, the game's own HUD (kill feed, score, minimap: `hud_areas` in the
  game profile, 1.2.59) or the platform's own buttons (safe zones): `place()` tries
  spots in a fixed order and skips the graphic when none is free.
- Per game, the event -> graphic mapping lives in the game profile (`graphics` in
  game/profiles/<id>/profile.json, see docs/ADDING_A_GAME.md):
      {"kills": ["lol_kill", ...],                       events that count on the kill counter
       "events": {"lol_pentakill": {"type": "banner", "text": "PENTAKILL", "icon": "crown"}, ...}}
  type: banner | score; text may hold "{n}" (the event's number, e.g. a 3-kill multikill).
- Light preset (perf.light): simple fades instead of the per-frame motion (cheaper to draw).
- Captions, bleeps and the timeline are never touched: this is a layer on top.

Times: items are in main time (EditPlan.to_out, after the cuts), like fx.py. The renderer draws
one ASS event per output frame from `state_at()`; the live preview (frontend/src/previewMath.ts
gfxStateAt) evaluates the same function at the same frame, so both show the same thing.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

STYLES = ("off", "minimal", "bold")
MAX_S = 1.5
MIN_GAP = 0.35  # seconds between two graphics
START_GUARD = 0.4  # nothing in the very first moment (the hook reads first)
END_GUARD = 0.3
MAX_ITEMS = 6
COUNTER_STEP_S = 0.18  # the pop when the kill counter goes up
PRIORITY = {"banner": 3, "score": 2, "number": 1, "counter": 0}
KEY_ACTION = (0.3, 0.7)
FIT_SCALES = (1.0, 0.88, 0.76)  # 1.2.59: tried in order when a graphic has no free spot
SIDE_COST = 400  # px of height a side spot must save to beat the centre  # the middle 40 % of the gameplay picture (both ways) stays free

# Look per style: font size, padding, icon size, gap, height, radius (1080-wide canvas px)
LOOK = {
    "minimal": {"font": 50, "pad": 26, "icon": 50, "gap": 14, "h": 92, "r": 46, "bg_alpha": 0.86},
    "bold": {"font": 84, "pad": 36, "icon": 82, "gap": 18, "h": 146, "r": 30, "bg_alpha": 1.0},
}
IN_S = {"minimal": 0.2, "bold": 0.26}
OUT_S = 0.22
SIMPLE_IN, SIMPLE_OUT = 0.15, 0.2
GOLD, NAVY, WHITE = "#D9B56A", "#0E1A33", "#FFFFFF"

# ------------------------------------------------------------------ icons (100 x 100 grid)
# Each icon: layers of (path, tone); tone "fg" = the accent colour, "bg" = the pill colour (cut-outs).
# Paths use the ASS drawing commands m / l / b, which map 1:1 to SVG M / L / C.


def _circle(cx: float, cy: float, r: float) -> str:
    k = r * 0.5523
    return (f"m {cx} {cy - r} b {cx + k} {cy - r} {cx + r} {cy - k} {cx + r} {cy} "
            f"b {cx + r} {cy + k} {cx + k} {cy + r} {cx} {cy + r} "
            f"b {cx - k} {cy + r} {cx - r} {cy + k} {cx - r} {cy} "
            f"b {cx - r} {cy - k} {cx - k} {cy - r} {cx} {cy - r}")


def _star(cx: float, cy: float, r1: float, r2: float, n: int = 5) -> str:
    pts = []
    for i in range(2 * n):
        r = r1 if i % 2 == 0 else r2
        a = -math.pi / 2 + i * math.pi / n
        pts.append((round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2)))
    return "m " + " l ".join(f"{x} {y}" for x, y in pts)


ICONS: dict[str, list[tuple[str, str]]] = {
    "skull": [
        ("m 50 4 b 76 4 94 22 94 46 b 94 60 87 70 78 76 l 78 92 l 22 92 l 22 76 b 13 70 6 60 6 46 "
         "b 6 22 24 4 50 4", "fg"),
        (_circle(32, 48, 11), "bg"), (_circle(68, 48, 11), "bg"),
        ("m 50 60 l 57 72 l 43 72 l 50 60", "bg"),
        ("m 38 80 l 42 80 l 42 92 l 38 92 l 38 80", "bg"), ("m 58 80 l 62 80 l 62 92 l 58 92 l 58 80", "bg"),
    ],
    "crown": [("m 6 84 l 6 26 l 30 50 l 50 14 l 70 50 l 94 26 l 94 84 l 6 84", "fg"),
              ("m 6 90 l 94 90 l 94 98 l 6 98 l 6 90", "fg")],
    "star": [(_star(50, 52, 48, 20), "fg")],
    "flag": [("m 10 4 l 18 4 l 18 98 l 10 98 l 10 4", "fg"),
             ("m 18 8 l 92 8 l 74 32 l 92 56 l 18 56 l 18 8", "fg")],
    "flame": [("m 50 2 b 60 26 86 38 86 64 b 86 84 70 98 50 98 b 30 98 14 84 14 64 b 14 48 26 38 32 26 "
               "b 36 40 42 46 48 46 b 48 30 44 16 50 2", "fg"),
              ("m 50 58 b 58 68 64 74 64 82 b 64 90 58 96 50 96 b 42 96 36 90 36 82 b 36 74 42 68 50 58", "bg")],
    "trophy": [("m 22 6 l 78 6 l 78 34 b 78 52 66 62 56 64 l 56 76 l 70 76 l 70 86 l 30 86 l 30 76 l 44 76 "
                "l 44 64 b 34 62 22 52 22 34 l 22 6", "fg"),
               ("m 4 12 l 22 12 l 22 22 l 13 22 b 13 34 18 40 24 42 l 22 48 b 12 46 4 36 4 22 l 4 12", "fg"),
               ("m 96 12 l 78 12 l 78 22 l 87 22 b 87 34 82 40 76 42 l 78 48 b 88 46 96 36 96 22 l 96 12", "fg"),
               ("m 24 90 l 76 90 l 76 98 l 24 98 l 24 90", "fg")],
    "target": [(_circle(50, 50, 48), "fg"), (_circle(50, 50, 34), "bg"), (_circle(50, 50, 22), "fg"),
               (_circle(50, 50, 10), "bg")],
}


def path_points(path: str) -> list[tuple[float, float]]:
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", path)]
    return list(zip(nums[0::2], nums[1::2]))


def to_svg(path: str) -> str:
    """ASS drawing commands -> an SVG path (canvas Path2D)."""
    out = []
    for cmd, args in re.findall(r"([mlb])\s+([-\d.\s]+)", path):
        out.append({"m": "M", "l": "L", "b": "C"}[cmd] + " " + " ".join(args.split()))
    return " ".join(out) + " Z"


# ------------------------------------------------------------------ the plan


@dataclass
class Gfx:
    a: float  # main time
    b: float
    kind: str  # banner | score | number | counter
    text: str
    icon: str = ""
    code: str = ""
    steps: list[tuple[float, str]] = field(default_factory=list)  # counter: (seconds after a, text)
    box: dict | None = None  # place(): {"x", "y" (centre), "w", "h", ...}

    def text_at(self, rel: float) -> str:
        cur = self.text
        for at, txt in self.steps:
            if rel + 1e-9 >= at:
                cur = txt
        return cur

    def to_dict(self) -> dict:
        return {"a": round(self.a, 3), "b": round(self.b, 3), "kind": self.kind, "text": self.text,
                "icon": self.icon, "code": self.code, "steps": [[round(t, 3), s] for t, s in self.steps],
                "box": self.box}


@dataclass
class GfxPlan:
    items: list[Gfx]
    style: str = "minimal"
    simple: bool = False  # Light preset: fades only
    fps: float = 30.0
    colors: dict = field(default_factory=lambda: {"bg": NAVY, "fg": GOLD, "ink": WHITE})
    # 1.2.59: the game's HUD areas (fractions of the source frame, x0 y0 x1 y1): never covered
    hud: list = field(default_factory=list)

    def fingerprint(self) -> list:
        return [self.style, self.simple, [(round(i.a, 2), i.kind, i.text, i.steps) for i in self.items],
                self.colors, [[round(v, 4) for v in b] for b in self.hud]]

    def to_dict(self) -> dict:
        look = LOOK[self.style]
        return {"style": self.style, "simple": self.simple, "fps": self.fps, "colors": self.colors,
                "bg_alpha": look["bg_alpha"], "in_s": SIMPLE_IN if self.simple else IN_S[self.style],
                "out_s": SIMPLE_OUT if self.simple else OUT_S,
                "icons": {k: [{"d": to_svg(p), "tone": t} for p, t in v] for k, v in ICONS.items()
                          if any(i.icon == k for i in self.items)},
                "items": [i.to_dict() for i in self.items if i.box is not None]}


# ------------------------------------------------------------------ game mapping


def mapping() -> tuple[set[str], dict[str, dict]]:
    """(kill codes, {event code: {"type", "text", "icon"}}) from every game profile."""
    from ..game import gameprofiles

    kills: set[str] = set()
    events: dict[str, dict] = {}
    for p in gameprofiles.all_profiles().values():
        g = p.get("graphics") or {}
        kills.update(str(c) for c in g.get("kills") or [])
        for code, ev in (g.get("events") or {}).items():
            events[str(code)] = dict(ev)
    return kills, events


def _num(value) -> int | None:
    m = re.search(r"\d+", str(value or ""))
    return int(m.group(0)) if m else None


# ------------------------------------------------------------------ spoken numbers

NUMBER_WORDS = {
    "en": {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
           "ten": 10},
    "tr": {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10},
}
KILL_WORDS = {"kill", "kills", "kil", "frag", "frags", "kıll", "килл", "киллов", "кила"}
VS_WORDS = {"v", "vs", "versus", "vs.", "против"}


def _as_int(tok: str, lang: str | None) -> int | None:
    t = tok.strip(".,!?;:\"'()").casefold()
    t = re.sub(r"['’](e|a|ye|ya)$", "", t)  # Turkish "1'e 4"
    if t.isdigit():
        return int(t)
    for table in (NUMBER_WORDS.get(lang or "", {}), NUMBER_WORDS["en"]):
        if t in table:
            return table[t]
    return None


def spoken(words: list[dict], lang: str | None) -> list[tuple[float, str]]:
    """Big numbers said in the clip: [(main time, "21 KILL" | "1v4")] (words in main time)."""
    out: list[tuple[float, str]] = []
    toks = [str(w.get("word", "")) for w in words]
    i = 0
    while i < len(toks):
        t = toks[i].strip(".,!?;:\"'()").casefold()
        m = re.fullmatch(r"(\d)\s*(?:v|vs)\s*(\d)", t)
        if m and 1 <= int(m.group(1)) <= 5 and 1 <= int(m.group(2)) <= 5:  # "1v4" in one word
            out.append((float(words[i]["start"]), f"{m.group(1)}v{m.group(2)}"))
            i += 1
            continue
        n = _as_int(toks[i], lang)
        if n is not None and i + 1 < len(toks):
            nxt = toks[i + 1].strip(".,!?;:\"'()").casefold()
            if nxt in KILL_WORDS and 2 <= n <= 99:
                out.append((float(words[i]["start"]), f"{n} KILL"))
                i += 2
                continue
            if nxt in VS_WORDS and i + 2 < len(toks):
                k = _as_int(toks[i + 2], lang)
                if k is not None and 1 <= n <= 5 and 1 <= k <= 5:
                    out.append((float(words[i]["start"]), f"{n}v{k}"))
                    i += 3
                    continue
            k = _as_int(toks[i + 1], lang) if re.search(r"['’](e|a|ye|ya)$", toks[i]) else None
            if k is not None and 1 <= n <= 5 and 1 <= k <= 5:  # Turkish "1'e 4"
                out.append((float(words[i]["start"]), f"{n}v{k}"))
                i += 2
                continue
        i += 1
    return out


# ------------------------------------------------------------------ choosing


def wanted_style(opts) -> str:
    s = str(getattr(opts, "graphics", "off") or "off")
    return s if s in STYLES else "off"


def build(project, cand: dict, opts, plan, mode: str | None = None) -> GfxPlan | None:
    """The clip's graphics (None when off / nothing to show). plan: the EditPlan (cuts decided)."""
    style = wanted_style(opts)
    if style == "off":
        return None
    if mode is None and project is not None:
        try:
            mode = project.load_meta().get("mode")
        except Exception:  # noqa: BLE001
            mode = None
    if (mode or "gaming") != "gaming":
        return None
    dur = plan.out_duration
    kill_codes, events = mapping()
    cands: list[Gfx] = []
    kills: list[float] = []
    for r in cand.get("reasons") or []:
        code, t = str(r.get("code", "")), float(r.get("t", -1))
        o = plan.to_out(t) if plan.start <= t <= plan.end else None
        if o is None:
            continue
        if code in kill_codes:
            kills.append(o)
        ev = events.get(code)
        if ev and ev.get("type") in ("banner", "score"):
            n = _num(r.get("value"))
            text = str(ev.get("text") or "").replace("{n}", str(n) if n else "").strip()
            if text:
                cands.append(Gfx(max(0.0, o - 0.1), 0.0, ev["type"], text, str(ev.get("icon") or ""), code))
    # the kill counter: one graphic per burst of kills, counting up
    kills.sort()
    total = 0
    i = 0
    while i < len(kills):
        a = kills[i]
        total += 1
        steps: list[tuple[float, str]] = []
        first = total
        j = i + 1
        while j < len(kills) and kills[j] - a <= MAX_S - 0.6:
            total += 1
            steps.append((round(kills[j] - a, 3), f"{total} KILL"))
            j += 1
        cands.append(Gfx(a, 0.0, "counter", f"{first} KILL", "skull", "kill_counter", steps))
        i = j
    # big numbers said in the clip
    lang = getattr(plan, "lang", None)
    for t, text in spoken(plan.out_words(), lang):
        cands.append(Gfx(t, 0.0, "number", text.upper() if "KILL" in text else text,
                         "skull" if "KILL" in text else "target", "spoken"))
    for g in cands:
        g.b = g.a + (MAX_S if g.kind in ("banner", "score") else 1.2)
        if g.steps:
            g.b = g.a + min(MAX_S, max(1.2, g.steps[-1][0] + 0.9))
    # no graphic across an effect insert (replay / freeze): it would be cut in two
    fxp = getattr(plan, "fx", None)
    cuts = [i.at for i in getattr(fxp, "inserts", [])] if fxp is not None else []
    chosen: list[Gfx] = []
    for g in sorted(cands, key=lambda g: (-PRIORITY[g.kind], g.a)):
        g.b = min(g.b, dur - END_GUARD)
        if g.a < START_GUARD or g.b - g.a < 0.8 or any(g.a < c < g.b for c in cuts):
            continue
        if any(g.a < o.b + MIN_GAP and o.a < g.b + MIN_GAP for o in chosen):
            continue
        # a counter right on a banner / spoken number of the same moment says the same thing twice
        chosen.append(g)
        if len(chosen) >= MAX_ITEMS:
            break
    chosen.sort(key=lambda g: g.a)
    if not chosen:
        return None
    from .. import perf

    colors = {"bg": NAVY, "fg": GOLD, "ink": WHITE}
    if plan.brand:
        colors["fg"] = str(plan.brand.get("caption_highlight") or GOLD)
        colors["bg"] = str(plan.brand.get("card_color") or NAVY)
    if style == "bold":  # the accent becomes the pill, the dark colour the ink
        colors = {"bg": colors["fg"], "fg": colors["bg"], "ink": colors["bg"]}
    try:
        simple = bool(perf.light())
    except Exception:  # noqa: BLE001
        simple = False
    return GfxPlan(chosen, style, simple, float(plan.fps), colors, hud_of(project))


def hud_of(project) -> list:
    """The HUD areas of the project's game (fractions of the frame); [] when the game is unknown."""
    if project is None:
        return []
    try:
        from ..game import gameprofiles, resolve

        return gameprofiles.hud_boxes(resolve(project).get("game"))
    except Exception:  # noqa: BLE001 - no game info: the other rules still apply
        return []


# ------------------------------------------------------------------ placement (safe zones)


def _hit(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def size(g: Gfx, style: str, scale: float = 1.0, max_w: float | None = None) -> dict:
    """The box of g (canvas px); a long text is made smaller until it fits max_w."""
    s = _size(g, style, scale)
    if max_w and s["w"] > max_w:
        s = _size(g, style, scale * max_w / s["w"] * 0.98)
    return s


def _size(g: Gfx, style: str, scale: float) -> dict:
    from .bubbles import text_width

    look = LOOK[style]
    font = look["font"] * scale
    longest = max([g.text] + [s for _t, s in g.steps], key=lambda s: text_width(s, round(font), True))
    tw = text_width(longest, round(font), True)
    icon = look["icon"] * scale if g.icon else 0.0
    pad, gap = look["pad"] * scale, (look["gap"] * scale if g.icon else 0.0)
    w = 2 * pad + icon + gap + tw
    return {"w": round(w), "h": round(look["h"] * scale), "r": round(look["r"] * scale), "font": round(font),
            "icon": round(icon), "icon_x": round(pad), "text_x": round(pad + icon + gap)}


def exclusions(geo, layout: str, safe: tuple, *, captions: bool, hook: bool, banner: bool,
               facecam_rect: tuple | None = None, bubbles_zone: dict | None = None,
               picture: tuple | None = None, bleep_icon: tuple | None = None,
               hud: list[tuple] | None = None) -> list[tuple]:
    """Canvas rects (x0, y0, x1, y1) no graphic may touch."""
    from ..clips import SPLIT_TOP, banner_y

    W, H = geo.w, geo.h
    top, right, bottom, left = safe
    m = 12
    ex = [(0, 0, W, top + m), (0, H - bottom - m, W, H), (W - right - m, 0, W, H), (0, 0, left + m, H)]
    ex.append((0, 0, W, 24))  # never glued to the edge
    ex.append((0, H - 24, W, H))
    cap_y = geo.cap_y if geo.cap_y is not None else (SPLIT_TOP if layout == "split" else 1390)
    if captions:
        half = 130 * geo.scale  # two caption lines are ~210 px tall
        ex.append((0, cap_y - half, W, cap_y + half))
    if banner or hook:
        y = banner_y(geo, layout) if banner else (geo.hook_y if geo.hook_y is not None else (120 if layout != "fit" else 330))
        ex.append((0, y - 10, W, y + 200 * geo.scale))
    if layout == "split" and geo.h > geo.w:
        ex.append((0, 0, W, SPLIT_TOP))  # the facecam panel
    elif facecam_rect is not None:
        x0, y0, x1, y1 = facecam_rect
        ex.append((x0 - 20, y0 - 20, x1 + 20, y1 + 20))
    # the key action: the middle of the gameplay picture
    if picture is None:
        picture = (0, SPLIT_TOP, W, H) if layout == "split" and geo.h > geo.w else (0, 0, W, H)
    px0, py0, px1, py1 = picture
    pw, ph = px1 - px0, py1 - py0
    ex.append((px0 + pw * KEY_ACTION[0], py0 + ph * KEY_ACTION[0], px0 + pw * KEY_ACTION[1], py0 + ph * KEY_ACTION[1]))
    if bubbles_zone is not None:
        bz = bubbles_zone
        ex.append((bz["x"], bz["bottom"] - 560 * bz.get("scale", 1.0), bz["x"] + bz["w"], bz["bottom"]))
    if bleep_icon is not None:
        ex.append(bleep_icon)
    ex.extend(hud or [])  # 1.2.59: the game's own HUD (canvas rects from clips.hud_rects)
    return ex


def max_scale(g: Gfx, style: str) -> float:
    """The largest scale the item reaches while it animates (bold overshoot / fade-out grow, the
    counter's pop)."""
    s = 1.08 if style == "bold" else 1.0
    return round(s * (1.16 if g.steps else 1.0), 3)


def place(items: list[Gfx], style: str, geo, layout: str, excl: list[tuple]) -> None:
    """Give every item a box in a free spot (or none: then it isn't shown)."""
    from ..clips import SPLIT_TOP

    W, H = geo.w, geo.h
    if layout == "split" and H > W:
        anchor = SPLIT_TOP + 300
    elif layout == "fit" and H > W:
        anchor = (H - W * 9 / 16) / 2 - 60  # above the picture band
    else:
        anchor = H * 0.24
    for g in items:
        box = None
        # 1.2.59: full size first; when no spot is free (e.g. Bold in the split layout, with the game's
        # own HUD at the bottom), the same graphic a bit smaller before giving up
        for shrink in FIT_SCALES:
            s = size(g, style, geo.scale * shrink, max_w=W - 200)
            w, h = s["w"], s["h"]
            if w > W - 120:
                break
            grow = max_scale(g, style)  # the whole animated extent: pop / overshoot and the slide-in
            aw, ah = w * grow, h * grow
            xs = [W / 2, 40 + aw / 2, W - 40 - aw / 2]
            ys = range(int(ah / 2) + 24, int(H - ah / 2 - 24 - 28), 10)
            # nearest to the anchor height first; the centre wins unless a side spot is much nearer
            spots = sorted(((x, y) for y in ys for x in xs),
                           key=lambda p: (abs(p[1] - anchor) + (0 if p[0] == W / 2 else SIDE_COST), p[1], p[0]))
            for x, y in spots:
                r = (x - aw / 2 - 8, y - ah / 2 - 18, x + aw / 2 + 8, y + ah / 2 + 36)
                if r[0] < 0 or r[2] > W or r[1] < 0 or r[3] > H:
                    continue
                if not any(_hit(r, e) for e in excl):
                    box = {"x": round(x), "y": round(y), **s}
                    break
            if box is not None:
                break
        g.box = box


# ------------------------------------------------------------------ animation (mirrored in previewMath.ts)


def ease_out_cubic(p: float) -> float:
    return 1 - (1 - p) ** 3


def ease_out_back(p: float) -> float:
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def frame_time(tm: float, fps: float) -> float:
    """The main time of the output frame shown at tm (the renderer draws per frame)."""
    return math.floor(tm * fps + 1e-6) / fps


def state_at(g: dict, tm: float, style: str, simple: bool, fps: float) -> dict | None:
    """{"alpha", "scale", "dy", "text"} of item g (to_dict form) at main time tm, None when hidden."""
    t = frame_time(tm, fps)
    a, b = float(g["a"]), float(g["b"])
    if t < a - 1e-9 or t >= b - 1e-9:
        return None
    e, r = t - a, b - t
    text = g["text"]
    for at, txt in g.get("steps") or []:
        if e + 1e-9 >= at:
            text = txt
    if simple:
        alpha = max(0.0, min(1.0, e / SIMPLE_IN, r / SIMPLE_OUT))
        return {"alpha": round(alpha, 4), "scale": 1.0, "dy": 0.0, "text": text}
    q = max(0.0, min(1.0, r / OUT_S))
    if style == "bold":
        p = min(1.0, e / IN_S["bold"])
        scale = 0.6 + 0.4 * ease_out_back(p)
        alpha = min(1.0, e / 0.1, q)
        scale *= 1 + 0.08 * (1 - q)
        dy = 0.0
    else:
        p = min(1.0, e / IN_S["minimal"])
        alpha = min(ease_out_cubic(p), q)
        scale = 1.0
        dy = (1 - ease_out_cubic(p)) * 28 + (1 - q) * -10
    for at, _txt in g.get("steps") or []:  # the counter pops when it goes up
        k = (e - at) / COUNTER_STEP_S
        if 0 <= k < 1:
            scale *= 1 + 0.16 * math.sin(math.pi * k)
    return {"alpha": round(max(0.0, alpha), 4), "scale": round(scale, 4), "dy": round(dy, 2), "text": text}


# ------------------------------------------------------------------ ASS (the renderer)


def _ass_color(hex_color: str) -> str:
    h = (hex_color.lstrip("#") + "FFFFFF")[:6]
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _alpha(a: float) -> str:
    return f"&H{max(0, min(255, round((1 - a) * 255))):02X}&"


def _rounded(w: float, h: float, r: float) -> str:
    r = min(r, h / 2, w / 2)
    return (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")


def rounded_path(w: float, h: float, r: float) -> str:
    """The pill's outline (preview: the same path)."""
    return _rounded(w, h, r)


def _drawing(path: str, k: float, ox: float, oy: float) -> tuple[str, float, float]:
    """Scale an ASS drawing by k, shift it so its control box starts at (0, 0); \\p3 coordinates
    (quarter pixels). Returns (drawing, x of the box, y of the box) in canvas px."""
    pts = path_points(path)
    minx = min(x for x, _y in pts) * k
    miny = min(y for _x, y in pts) * k

    def conv(m: re.Match) -> str:
        nums = [float(v) for v in m.group(2).split()]
        out = []
        for i in range(0, len(nums), 2):
            out += [str(round((nums[i] * k - minx) * 4)), str(round((nums[i + 1] * k - miny) * 4))]
        return m.group(1) + " " + " ".join(out) + " "

    d = re.sub(r"([mlb])\s+([-\d.\s]+)", conv, path).strip()
    return d, ox + minx, oy + miny


def style_lines() -> list[str]:
    return ["Style: gfx,Arial,50,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,"
            "100,100,0,0,1,0,0,7,0,0,0,1"]


def ass_lines(gp: GfxPlan, final, lead: float, ts) -> list[str]:
    """One Dialogue set per output frame (a still part is one line). final: main -> timeline time
    (fx.FxPlan.final or identity); ts: seconds -> ASS time."""
    out: list[str] = []
    F = gp.fps
    half = 0.5 / F
    look = LOOK[gp.style]
    bg_c, fg_c, ink_c = (_ass_color(gp.colors[k]) for k in ("bg", "fg", "ink"))
    for g in gp.items:
        if g.box is None:
            continue
        d = g.to_dict()
        box = g.box
        shift = final(g.a) - g.a + lead  # no insert inside an item: one shift for all of it
        n0, n1 = math.ceil(g.a * F - 1e-6), math.ceil(g.b * F - 1e-6)
        runs: list[tuple[int, int, dict]] = []
        for n in range(n0, n1):
            st = state_at(d, n / F, gp.style, gp.simple, F)
            if st is None:
                continue
            if runs and runs[-1][2] == st and runs[-1][1] == n:
                runs[-1] = (runs[-1][0], n + 1, st)
            else:
                runs.append((n, n + 1, st))
        for na, nb, st in runs:
            t0, t1 = ts(na / F + shift - half), ts(nb / F + shift - half)
            if t0 == t1:
                continue
            s = st["scale"]
            w, h = box["w"] * s, box["h"] * s
            x0 = box["x"] - w / 2
            y0 = box["y"] + st["dy"] - h / 2
            a = st["alpha"]
            pill, px, py = _drawing(_rounded(box["w"], box["h"], box["r"]), s, x0, y0)
            out.append(f"Dialogue: 6,{t0},{t1},gfx,,0,0,0,,{{\\an7\\pos({px:.2f},{py:.2f})\\p3\\bord0\\shad0"
                       f"\\1c{bg_c}\\1a{_alpha(a * look['bg_alpha'])}}}{pill}")
            if g.icon and box["icon"]:
                k = box["icon"] * s / 100
                ix = x0 + box["icon_x"] * s
                iy = y0 + (h - box["icon"] * s) / 2
                for path, tone in ICONS.get(g.icon, []):
                    dr, dx, dy = _drawing(path, k, ix, iy)
                    col = fg_c if tone == "fg" else bg_c
                    out.append(f"Dialogue: 7,{t0},{t1},gfx,,0,0,0,,{{\\an7\\pos({dx:.2f},{dy:.2f})\\p3\\bord0"
                               f"\\shad0\\1c{col}\\1a{_alpha(a)}}}{dr}")
            tx = x0 + box["text_x"] * s
            text = st["text"].replace("\\", "").replace("{", "(").replace("}", ")")
            out.append(f"Dialogue: 8,{t0},{t1},gfx,,0,0,0,,{{\\an4\\pos({tx:.2f},{y0 + h / 2:.2f})\\fs{box['font']}"
                       f"\\fscx{s * 100:.2f}\\fscy{s * 100:.2f}\\b1\\bord0\\shad0\\1c{ink_c}\\1a{_alpha(a)}}}{text}")
    return out
