"""Keywords: trigger words/phrases in the transcript, per language.

Defaults live in highlights/triggers/<lang>.json:
    {"reaction": {"oha": 1.0, "nasıl ya": 1.0, ...}, "study": {"önemli": 1.0, ...}}
Users add their own in config.json:
    "custom_triggers": {"tr": ["kral", "efsane an"]}                  # all categories
    "custom_triggers": {"tr": {"reaction": ["kral"], "study": ["ezber"]}}
Matching ignores case and diacritics, collapses stretched letters
("nooooo" == "no"), and understands multi-word phrases. Chinese is matched
without word boundaries.

1.2.77 (phase D8): the "funny" and "fail" lists (every language) find moments that aren't kills:
a funny line or a laugh the transcript wrote down ("hahaha", "(laughs)") -> reason "funny_line",
a mistake the streamer says out loud ("what did I just do", "ne yaptım ben") -> "fail_line".
"""

from __future__ import annotations

import functools
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterator

import numpy as np
from scipy.ndimage import gaussian_filter1d

from ... import config
from .base import ReasonEvent, Signal, SignalResult, SignalUnavailable, register

TRIGGERS_DIR = Path(__file__).resolve().parents[1] / "triggers"
NO_SPACE_LANGS = {"zh", "ja", "th"}
# reason code per trigger category (reaction / study keep the old "keyword")
CATEGORY_CODE = {"funny": "funny_line", "fail": "fail_line"}
# Laughter written out by Whisper as one word: "haha", "ahahah", "hehe", "jajaja", "хаха", "ههههه"
# (normalize() already squeezed "ههههه" to one letter: a lone "ه" is that laugh)
LAUGH_TOKEN = re.compile(r"^(?:a?h[aei]){2,}h?$|^(?:ja|je|ji){2,}$|^(?:a?х[аеи]){2,}х?$|^ه$")
LAUGH_WEIGHT = 0.8

_CHAR_MAP = str.maketrans({
    "ı": "i", "ß": "ss", "ø": "o", "æ": "ae", "œ": "oe", "đ": "d", "ł": "l",
    # Arabic: unify letter variants, drop tatweel
    "ٱ": "ا", "ى": "ي", "ة": "ه", "ـ": "",
    "’": "", "'": "", "`": "", "´": "",
})


def _is_cjk(ch: str) -> bool:
    return "㐀" <= ch <= "鿿" or "豈" <= ch <= "﫿"


def normalize(text: str) -> str:
    """Lowercase, strip accents/diacritics/punctuation, collapse stretched letters."""
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c)).translate(_CHAR_MAP)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"(\w)\1{2,}", lambda m: m.group(1) * (2 if _is_cjk(m.group(1)) else 1), text)
    return re.sub(r"\s+", " ", text).strip()


@functools.lru_cache(maxsize=16)
def default_triggers(lang: str) -> dict[str, dict[str, float]]:
    path = TRIGGERS_DIR / f"{lang}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def trigger_phrases(lang: str, categories: tuple[str, ...]) -> dict[str, tuple[str, float]]:
    """normalized phrase -> (display phrase, weight) for one language and mode."""
    out: dict[str, tuple[str, float]] = {}

    def add(phrase: str, weight: float) -> None:
        norm = normalize(phrase)
        if norm and (norm not in out or out[norm][1] < weight):
            out[norm] = (phrase, float(weight))

    defaults = default_triggers(lang)
    for cat in categories:
        for phrase, weight in defaults.get(cat, {}).items():
            add(phrase, weight)
    custom = (config.get("custom_triggers") or {}).get(lang)
    if isinstance(custom, list):
        for phrase in custom:
            add(str(phrase), 1.0)
    elif isinstance(custom, dict):
        for cat in categories:
            for phrase in custom.get(cat, []):
                add(str(phrase), 1.0)
    return out


def find_matches(words: list[dict], lang: str,
                 phrases: dict[str, tuple[str, float]]) -> Iterator[tuple[int, str, float]]:
    """Yield (word_index, display_phrase, weight) for every phrase occurrence."""
    if not phrases or not words:
        return
    if lang in NO_SPACE_LANGS:
        chars: list[str] = []
        owner: list[int] = []
        for i, w in enumerate(words):
            t = normalize(w.text).replace(" ", "")
            chars.extend(t)
            owner.extend([i] * len(t))
        text = "".join(chars)
        for norm, (display, weight) in phrases.items():
            needle = norm.replace(" ", "")
            pos = text.find(needle)
            while pos != -1:
                yield owner[pos], display, weight
                pos = text.find(needle, pos + len(needle))
        return

    tokens: list[str] = []
    owner = []
    for i, w in enumerate(words):
        for tok in normalize(w.text).split():
            tokens.append(tok)
            owner.append(i)
    by_first: dict[str, list[tuple[list[str], str, float]]] = {}
    for norm, (display, weight) in phrases.items():
        parts = norm.split()
        by_first.setdefault(parts[0], []).append((parts, display, weight))
    for j, tok in enumerate(tokens):
        for parts, display, weight in by_first.get(tok, ()):
            if tokens[j:j + len(parts)] == parts:
                yield owner[j], display, weight


def phrase_categories(lang: str, categories: tuple[str, ...]) -> dict[str, str]:
    """display phrase -> its category (the first one that lists it; your own words = "reaction")."""
    out: dict[str, str] = {}
    defaults = default_triggers(lang)
    for cat in categories:
        for phrase in defaults.get(cat, {}):
            out.setdefault(phrase, cat)
    return out


def laugh_tokens(words: list) -> Iterator[int]:
    """Word indexes that are written-out laughter ("hahaha"), in any language."""
    for i, w in enumerate(words):
        if any(LAUGH_TOKEN.match(tok) for tok in normalize(w.text).split()):
            yield i


@register
class KeywordSignal(Signal):
    name = "keywords"
    version = 2

    def check(self, ctx) -> None:
        if not ctx.words:
            raise SignalUnavailable("no transcript (run transcribe first)")
        if not ctx.mode.keyword_categories:
            raise SignalUnavailable(f"not used in {ctx.mode.name} mode")
        if not trigger_phrases(ctx.language or "", ctx.mode.keyword_categories):
            raise SignalUnavailable(f"no trigger words for language '{ctx.language}'")

    def compute(self, ctx) -> SignalResult:
        cats = ctx.mode.keyword_categories
        phrases = trigger_phrases(ctx.language, cats)
        cat_of = phrase_categories(ctx.language, cats)
        impulses = np.zeros(ctx.n)
        events: list[ReasonEvent] = []
        hits: dict[str, int] = {}
        found = list(find_matches(ctx.words, ctx.language, phrases))
        if "funny" in cats:
            found += [(i, "haha", LAUGH_WEIGHT) for i in laugh_tokens(ctx.words)]
        for wi, display, weight in found:
            t = ctx.words[wi].start
            sec = min(ctx.n - 1, int(t))
            impulses[sec] += weight
            code = "funny_line" if display == "haha" else CATEGORY_CODE.get(cat_of.get(display, ""), "keyword")
            events.append(ReasonEvent(t, code, display, weight))
            hits[display] = hits.get(display, 0) + 1
        sigma = 1.5
        spread = gaussian_filter1d(impulses, sigma) * (np.sqrt(2 * np.pi) * sigma)
        scores = 1.0 - np.exp(-1.5 * spread)
        top = sorted(hits.items(), key=lambda kv: -kv[1])[:15]
        return SignalResult(self.name, scores, events,
                            {"language": ctx.language, "triggers": len(phrases),
                             "matches": sum(hits.values()), "top": dict(top)})
