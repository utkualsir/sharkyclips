"""Mode presets: which signals matter, and what a good clip looks like.

Weights reference signals by name. A weight for a signal that doesn't exist yet
(or one that can't run here, e.g. no chat replay) is skipped and the rest re-normalized.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from ..errors import SharkyClipsError


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
        # 1.2.77 (phase D8): "voice" (pitch / scream / silence broken by a burst) and the funny / fail
        # lines find the moments that aren't kills; setup_max = how far back the smart pre-roll may
        # look for the start of the fight / the setup.
        weights={"loudness": 0.30, "laughter": 0.25, "keywords": 0.25, "speech": 0.20, "chat": 0.30,
                 "game": 0.6, "voice": 0.22},
        keyword_categories=("reaction", "funny", "fail"),
        clip_min=15, clip_ideal=38, clip_max=60,
        pre_roll=(6, 10), post_roll=3, min_gap=45, smooth_sigma=2.0,
        boundary="reaction", extra={"setup_max": 22},
    ),
    "study": ModePreset(
        name="study",
        # The local LLM reads the transcript and finds self-contained explanations: it's
        # the main signal here. Without Ollama the other signals still work.
        weights={"llm": 0.55, "keywords": 0.20, "steady_speech": 0.15, "speech": 0.05,
                 "loudness": 0.02, "laughter": 0.01, "chat": 0.05, "voice": 0.02},
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


# 1.2.77: Just Chatting / IRL / podcast streams inside Gaming mode ("talk" profile). No game HUD,
# no kills: laughter, the voice, funny lines and chat carry the clip, and a story needs a longer
# setup before its punchline.
TALK_WEIGHTS = {"laughter": 0.35, "voice": 0.30, "keywords": 0.30, "speech": 0.22, "chat": 0.40,
                "loudness": 0.12}
PROFILES = ("auto", "game", "talk")
TALK_WORDS = ("just chatting", "justchatting", "irl", "sohbet", "muhabbet", "chatting", "talk show",
              "podcast", "q&a", "soru cevap", "reacting", "react ", "tepki", "watch party", "plaudern",
              "beszélget", "болтаем", "общение", "دردشة", "闲聊", "聊天", "charla", "charlando", "discussion",
              "conversa", "papo", "雑談")


def with_profile(preset: ModePreset, profile: str) -> ModePreset:
    """The gaming preset tuned for talk streams; any other mode / profile is returned unchanged."""
    if preset.name != "gaming" or profile != "talk":
        return preset
    return replace(preset, weights=dict(TALK_WEIGHTS), pre_roll=(8, 14), clip_ideal=42, min_gap=40,
                   smooth_sigma=2.5, extra={**preset.extra, "setup_max": 28, "setup_sentences": 2, "profile": "talk"})


def _has_word(text: str, word: str) -> bool:
    if not word.isascii():  # CJK etc.: no spaces between words
        return word in text
    return re.search(r"(?<![\w])" + re.escape(word) + r"(?![\w])", text) is not None


def detect_profile(meta: dict, game: str | None = None) -> tuple[str, str]:
    """("game" | "talk", why). The user's pick (meta "profile") wins; else the stream's category /
    title: a talk word and no recognised game -> talk."""
    choice = meta.get("profile") or "auto"
    if choice in ("game", "talk"):
        return choice, "your choice"
    if game:
        return "game", f"game: {game}"
    src = meta.get("source") or {}
    text = " ".join(str(x) for x in (src.get("category"), meta.get("title"), src.get("title")) if x).casefold()
    hit = next((w.strip() for w in TALK_WORDS if _has_word(text, w.strip())), None)
    return ("talk", f"title / category: {hit}") if hit else ("game", "default")


def get_mode(name: str) -> ModePreset:
    try:
        return MODES[name]
    except KeyError:
        raise SharkyClipsError(f"Unknown mode '{name}'.", f"Use one of: {', '.join(MODES)}") from None
