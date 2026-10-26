"""Smart zoom: a subtle punch-in on the clip's peak moments.

Pulses come from what made the moment interesting (game events, loudness spikes, trigger
words, laughter, chat spikes) and, for the facecam, from reactions (laughs, shouts,
trigger words). Each pulse eases in, holds and eases out (smoothstep), drawn with ffmpeg's
`perspective` filter: sub-pixel smooth, no zoompan jitter, and switched off between pulses.
"""

from __future__ import annotations

from dataclasses import dataclass

INTENSITY = {"off": 0.0, "subtle": 1.15, "strong": 1.3}
LEVELS = tuple(INTENSITY)
RAMP_IN, RAMP_OUT, HOLD = 0.35, 0.55, 1.1
MIN_GAP = 3.5  # seconds between two pulses on the same picture

GAME_CODES_PREFIX = ("df_", "lol_")
SCENE_CODES = {"loudness_spike", "chat_spike", "keyword", "laughter", "pause_then_burst"}
REACT_CODES = {"laughter", "keyword", "loudness_spike", "scream", "chat_reactions"}


@dataclass
class Pulse:
    t0: float  # zoom starts (eases in)
    t1: float  # back to normal
    target: str  # "scene" (gameplay / whole picture) or "cam" (facecam panel)
    code: str = ""

    def to_dict(self) -> dict:
        return {"t0": round(self.t0, 3), "t1": round(self.t1, 3), "target": self.target, "code": self.code}


def moments(cand: dict, laughs: list[float] | None = None) -> list[tuple[float, str, float, str]]:
    """(time, target, strength, code) inside the clip, strongest first."""
    start, end = float(cand["start"]), float(cand["end"])
    out = []
    for r in cand.get("reasons") or []:
        t, code = float(r.get("t", -1)), str(r.get("code", ""))
        if not (start + 0.3 <= t <= end - 0.8):
            continue
        s = float(r.get("strength") or 0.5)
        if code.startswith(GAME_CODES_PREFIX) or code in SCENE_CODES:
            out.append((t, "scene", s + (0.3 if code.startswith(GAME_CODES_PREFIX) else 0), code))
        if code in REACT_CODES:
            out.append((t, "cam", s, code))
    for t in laughs or []:
        if start + 0.3 <= t <= end - 0.8:
            out.append((t, "cam", 0.8, "laughter"))
            out.append((t, "scene", 0.4, "laughter"))
    return sorted(out, key=lambda m: -m[2])


def pulses(cand: dict, laughs: list[float] | None = None, max_pulses: int = 6) -> list[Pulse]:
    """Non-overlapping pulses per target, in source time."""
    chosen: list[Pulse] = []
    for t, target, _s, code in moments(cand, laughs):
        t0, t1 = t - RAMP_IN - 0.1, t + HOLD + RAMP_OUT
        if sum(p.target == target for p in chosen) >= max_pulses:
            continue
        if any(p.target == target and t0 < p.t1 + MIN_GAP and t1 > p.t0 - MIN_GAP for p in chosen):
            continue
        chosen.append(Pulse(max(float(cand["start"]), t0), min(float(cand["end"]), t1), target, code))
    return sorted(chosen, key=lambda p: p.t0)


def factor_expr(pulses_out: list[tuple[float, float]], zmax: float, fps: float) -> str:
    """ffmpeg expression for the zoom factor at frame `in` (perspective has no `t`)."""
    terms = []
    for t0, t1 in pulses_out:
        ri = min(RAMP_IN, (t1 - t0) / 3)
        ro = min(RAMP_OUT, (t1 - t0) / 3)
        tt = f"(in/{fps:g})"
        s = f"min(clip(({tt}-{t0:.3f})/{ri:.3f},0,1),clip(({t1:.3f}-{tt})/{ro:.3f},0,1))"
        terms.append(f"st(1,{s});st(0,ld(0)+ld(1)*ld(1)*(3-2*ld(1)))")
    if not terms:
        return "1"
    return "st(0,0);" + ";".join(terms) + f";1+{zmax - 1:.3f}*ld(0)"


def perspective_filter(pulses_out: list[tuple[float, float]], zmax: float, fps: float,
                       cy: float = 0.5) -> str:
    """Zoom toward the picture's center (cy: vertical focus 0..1)."""
    if not pulses_out or zmax <= 1.0:
        return ""
    z = f"({factor_expr(pulses_out, zmax, fps)})"
    left, right = f"W/2-W/2/{z}", f"W/2+W/2/{z}"
    top, bottom = f"H*{cy:g}-H*{cy:g}/{z}", f"H*{cy:g}+H*{1 - cy:g}/{z}"
    enable = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in pulses_out)
    return (f"perspective=x0='{left}':y0='{top}':x1='{right}':y1='{top}':x2='{left}':y2='{bottom}':"
            f"x3='{right}':y3='{bottom}':interpolation=linear:eval=frame:enable='{enable}'")


def factor_at(t: float, pulses_src: list[Pulse], target: str, zmax: float) -> float:
    """Zoom factor at source time t (tests + mirrored by the live preview)."""
    for p in pulses_src:
        if p.target != target or not (p.t0 <= t <= p.t1):
            continue
        d = p.t1 - p.t0
        ri, ro = min(RAMP_IN, d / 3), min(RAMP_OUT, d / 3)
        s = min(max(0.0, min(1.0, (t - p.t0) / ri)), max(0.0, min(1.0, (p.t1 - t) / ro)))
        return 1 + (zmax - 1) * s * s * (3 - 2 * s)
    return 1.0
