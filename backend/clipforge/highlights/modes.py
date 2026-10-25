"""Mode presets: which signals matter, and what a good clip looks like.

Weights reference signals by name. A weight for a signal that doesn't exist yet
(or one that can't run here, e.g. no chat replay) is skipped and the rest re-normalized.
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
        # "chat" only runs when there's a chat replay, "game" only for games with a HUD preset
        # (Delta Force, League of Legends); missing signals are re-normalized away. "game" is 0
        # most of the time and high at kills/objectives, so it lifts exactly those moments.
        weights={"loudness": 0.30, "laughter": 0.25, "keywords": 0.25, "speech": 0.20, "chat": 0.30,
                 "game": 0.6},
        keyword_categories=("reaction",),
        clip_min=15, clip_ideal=38, clip_max=60,
        pre_roll=(6, 10), post_roll=3, min_gap=45, smooth_sigma=2.0,
        boundary="reaction",
    ),
    "study": ModePreset(
        name="study",
        # The local LLM reads the transcript and finds self-contained explanations: it's
        # the main signal here. Without Ollama the other signals still work.
        weights={"llm": 0.55, "keywords": 0.20, "steady_speech": 0.15, "speech": 0.05,
                 "loudness": 0.02, "laughter": 0.01, "chat": 0.05},
        keyword_categories=("study",),
        clip_min=30, clip_ideal=45, clip_max=60,
        pre_roll=(1, 4), post_roll=1, min_gap=60, smooth_sigma=5.0,
        boundary="sentence", agreement_bonus=0.10,
    ),
    "music": ModePreset(
        name="music",
        weights={"music": 0.80, "loudness": 0.12, "laughter": 0.08,  # laughter -> cheering
                 "chat": 0.10},
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
