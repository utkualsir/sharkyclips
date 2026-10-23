"""Mode presets: which signals matter, and what a good clip looks like.

Weights reference signals by name. A weight for a signal that doesn't exist yet
(e.g. "chat", "llm" in Phase 3) is simply ignored until that signal is registered.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..errors import ClipForgeError


@dataclass(frozen=True)
class ModePreset:
    name: str
    weights: dict[str, float]
    keyword_categories: tuple[str, ...]  # which trigger lists count (see triggers/*.json)
    clip_min: float
    clip_ideal: float
    clip_max: float
    pre_roll: tuple[float, float]  # (min, max) seconds of setup before the peak
    post_roll: float  # seconds kept after the reaction calms down
    min_gap: float  # min seconds between two peaks
    smooth_sigma: float  # smoothing of the hype curve, in seconds
    boundary: str  # "reaction" | "sentence" | "music"
    agreement_bonus: float = 0.15  # boost when several signals fire together
    extra: dict = field(default_factory=dict)


MODES: dict[str, ModePreset] = {
    "gaming": ModePreset(
        name="gaming",
        weights={"loudness": 0.30, "laughter": 0.25, "keywords": 0.25, "speech": 0.20,
                 # Phase 3: "chat": 0.0, "llm": 0.0
                 },
        keyword_categories=("reaction",),
        clip_min=15, clip_ideal=38, clip_max=60,
        pre_roll=(6, 10), post_roll=3, min_gap=45, smooth_sigma=2.0,
        boundary="reaction",
    ),
    "study": ModePreset(
        name="study",
        weights={"keywords": 0.40, "steady_speech": 0.35, "speech": 0.10,
                 "loudness": 0.03, "laughter": 0.02,
                 # Phase 3: the local LLM ("llm") will do the heavy lifting here.
                 },
        keyword_categories=("study",),
        clip_min=30, clip_ideal=45, clip_max=60,
        pre_roll=(1, 4), post_roll=1, min_gap=60, smooth_sigma=5.0,
        boundary="sentence", agreement_bonus=0.10,
    ),
    "music": ModePreset(
        name="music",
        weights={"music": 0.80, "loudness": 0.12, "laughter": 0.08},  # laughter -> cheering
        keyword_categories=(),
        clip_min=15, clip_ideal=25, clip_max=30,
        pre_roll=(0, 2), post_roll=0, min_gap=30, smooth_sigma=3.0,
        boundary="music", agreement_bonus=0.05,
    ),
}


def get_mode(name: str) -> ModePreset:
    try:
        return MODES[name]
    except KeyError:
        raise ClipForgeError(f"Unknown mode '{name}'.", f"Use one of: {', '.join(MODES)}") from None
