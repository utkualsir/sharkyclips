"""Filler words per language ("ııı", "eee", "um", "äh", "ну" ...).

"sure" fillers are cut at every level; "maybe" fillers are real words too ("şey" = thing,
"ну" = well), so only "strong" cuts them, and only when they stand alone (a pause before or
after). Long letter runs count once ("ıııı" = "ıı"). Config `filler_lists`:
{lang: {"sure": [...], "maybe": [...]}} replaces the built-in lists of a language.
"""

from __future__ import annotations

from .. import config
from .words import compile_entries, find

DEFAULTS: dict[str, dict[str, list[str]]] = {
    "tr": {"sure": ["ı", "ıı", "ıh", "ıhh", "ım", "ımm", "ee", "eh", "ehh", "hm", "hmm", "mm", "öö"],
           "maybe": ["şey", "yani", "işte", "e"]},
    "en": {"sure": ["um", "umm", "uh", "uhh", "uhm", "erm", "er", "hm", "hmm", "mm", "eh"],
           "maybe": ["like", "you know", "i mean"]},
    "de": {"sure": ["äh", "ähh", "ähm", "öh", "öhm", "ehm", "hm", "hmm", "mm"],
           "maybe": ["also", "naja", "halt"]},
    "hu": {"sure": ["ö", "öö", "öh", "őő", "hm", "hmm", "mm", "ee"],
           "maybe": ["hát", "izé", "szóval"]},
    "ru": {"sure": ["э", "ээ", "эм", "ээм", "мм", "хм", "а-а"],
           "maybe": ["ну", "вот", "типа", "короче"]},
    "ar": {"sure": ["امم", "ممم", "مم", "ااا", "اا"],
           "maybe": ["يعني", "يعنى", "طيب"]},
    "zh": {"sure": ["嗯", "呃", "额", "唔"],
           "maybe": ["那个", "就是", "然后"]},
}


def lists(lang: str | None) -> dict[str, list[str]]:
    custom = config.get("filler_lists") or {}
    got = custom.get(lang or "") if isinstance(custom, dict) else None
    base = DEFAULTS.get(lang or "", {"sure": [], "maybe": []})
    if isinstance(got, dict):
        return {k: [str(w) for w in (got.get(k) if isinstance(got.get(k), list) else base[k])]
                for k in ("sure", "maybe")}
    return {k: list(v) for k, v in base.items()}


def find_fillers(words: list[dict], lang: str | None, level: str,
                 custom: dict[str, list[str]] | None = None) -> list[int]:
    """Indices of filler words to cut. words: {"start", "end", "word"} sorted by time."""
    if level not in ("light", "strong") or not words:
        return []
    lst = custom or lists(lang)
    texts = [w["word"] for w in words]
    out: set[int] = set()
    opts = {"squeeze_runs": True, "accents": True}
    for a, b, _e in find(texts, compile_entries(lst["sure"], lang, **opts), lang, **opts):
        out.update(range(a, b + 1))
    if level == "strong":
        for a, b, _e in find(texts, compile_entries(lst["maybe"], lang, **opts), lang, **opts):
            before = words[a]["start"] - words[a - 1]["end"] if a > 0 else 9.0
            after = words[b + 1]["start"] - words[b]["end"] if b + 1 < len(words) else 9.0
            if max(before, after) >= 0.3:  # stands alone: a filler, not part of a sentence
                out.update(range(a, b + 1))
    return sorted(out)
