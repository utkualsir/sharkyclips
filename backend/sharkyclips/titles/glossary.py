"""Names and words the titles must spell right.

Three sources, merged:
  1. built-in game terms (games.json): only terms the streamer actually says (fuzzy match
     against the transcript, so Whisper's "zero dem" still finds "Zero Dam") or that appear in
     the video title; the game name itself always.
  2. the user's glossary in config.json:  "glossary": ["Zero Dam", "kanka", ...]
     (or per language: {"all": [...], "tr": [...]})
  3. the streamer's own words: words they use far more often than normal speech does
     ("kanka", nicknames, game slang), found by comparing transcript counts with wordfreq.
"""

from __future__ import annotations

import functools
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from .. import config
from . import lexicon

GAMES_FILE = Path(__file__).resolve().parent / "games.json"
FUZZY = 0.85
# Casual but rude-ish fillers: fine on stream, not in a title.
NOT_FOR_TITLES = {"lan", "ulan", "len", "amk", "aq", "lol", "lmao", "bro"}


@dataclass
class Glossary:
    lang: str
    game: str | None = None
    terms: list[str] = field(default_factory=list)          # canonical spellings
    streamer_words: list[str] = field(default_factory=list)
    allowed: set[str] = field(default_factory=set)          # lowercased tokens that count as real words
    keep_case: set[str] = field(default_factory=set)        # lowercased tokens to keep capitalized

    def digest(self) -> str:
        return "|".join([self.game or "", *self.terms, "#", *self.streamer_words])

    def canonicalize(self, text: str) -> str:
        """Spell every glossary term the canonical way ("zero dam" / "zerodam" -> "Zero Dam")."""
        for term in sorted(self.terms, key=len, reverse=True):
            if _common_word(term, self.lang):
                continue  # "Cracked" (a map) must not capitalize "cracked" in a sentence
            parts = term.split()
            pat = r"[\s-]*".join(re.escape(p) for p in parts) if len(parts) > 1 else re.escape(term)
            # a key word in CAPITALS ("PENTAKILL") keeps its style
            text = re.sub(rf"(?<![\w]){pat}(?![\w])",
                          lambda m, term=term: m.group(0) if m.group(0).isupper() and len(m.group(0)) > 3 else term,
                          text, flags=re.I)
            if len(term) >= 6:  # close misspellings of longer names ("Brakesh" -> "Brakkesh")
                n = len(parts)
                toks = list(re.finditer(r"[^\W_]+(?:[-'][^\W_]+)*", text))
                for i in range(len(toks) - n + 1):
                    a, b = toks[i].start(), toks[i + n - 1].end()
                    chunk = text[a:b]
                    # keep a suffix after an apostrophe: "Delta Force'ta" stays "...'ta"
                    m = re.search(r"'[^\W_]{1,5}$", chunk)
                    if m:
                        chunk, b = chunk[: m.start()], a + m.start()
                    if chunk != term and not (chunk.isupper() and len(chunk) > 3) and _similar(chunk, term):
                        text = text[:a] + term + text[b:]
                        break
        return text


@functools.lru_cache(maxsize=1)
def _games() -> dict:
    data = json.loads(GAMES_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _common_word(term: str, lang: str) -> bool:
    return " " not in term and lexicon.zipf(lexicon.lower(term, lang), lang) >= 3.0


def _norm(s: str) -> str:
    return re.sub(r"[^\w]", "", s.casefold())


def _similar(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if not na or not nb or abs(len(na) - len(nb)) > 2 or na[0] != nb[0]:
        return False
    return na == nb or SequenceMatcher(None, na, nb).ratio() >= FUZZY


def detect_game(*texts: str) -> str | None:
    hay = " ".join(t for t in texts if t).casefold()
    for name, g in _games().items():
        for alias in g.get("aliases", []) + [name.casefold()]:
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", hay):
                return name
    return None


def user_terms(lang: str) -> list[str]:
    g = config.get("glossary") or []
    out: list[str] = []
    if isinstance(g, dict):
        raw = list(g.get("all") or []) + list(g.get(lang) or [])
    else:
        raw = list(g)
    for t in raw:
        t = " ".join(str(t).split())[:60]
        if t and t not in out:
            out.append(t)
    return out


def _transcript_words(transcript: dict) -> list[str]:
    return [w["word"].strip() for seg in transcript.get("segments", []) for w in seg.get("words", [])
            if w.get("word", "").strip()]


def _found_in(term: str, ngrams: dict[int, set[str]], buckets: dict[tuple, list[str]]) -> bool:
    nt = _norm(term)
    if nt in ngrams.get(len(term.split()), set()) or any(nt in g for g in ngrams.values()):
        return True
    if len(nt) < 5:
        return False
    cands = [g for d in (-2, -1, 0, 1, 2) for g in buckets.get((nt[0], len(nt) + d), [])]
    return any(SequenceMatcher(None, g, nt).ratio() >= FUZZY for g in cands)


_DETECT = object()


def build(transcript: dict, lang: str, video_title: str = "", topic: str = "",
          extra_terms: list[str] | None = None, game=_DETECT, game_terms: list[str] | None = None,
          extra_allowed: list[str] | None = None) -> Glossary:
    """game: the project's game name ("" = unknown: no game terms at all); left out, it is
    detected from the title / topic. game_terms: the game bank's names, added to the built-in ones
    (still only when the streamer says them). extra_allowed: words that always count as real
    (the bank's CAPS key words like "PENTAKILL")."""
    from ..analyze import has_profanity

    spoken = transcript.get("language") or lang
    raw = _transcript_words(transcript)
    clean = [re.sub(r"^[^\w]+|[^\w]+$", "", w) for w in raw]
    clean = [w for w in clean if w]
    lower = [lexicon.lower(w, spoken) for w in clean]
    ngrams = {n: {_norm("".join(lower[i:i + n])) for i in range(len(lower) - n + 1)} for n in (1, 2, 3)}
    buckets: dict[tuple, list[str]] = {}
    for grams in ngrams.values():
        for g in grams:
            if g:
                buckets.setdefault((g[0], len(g)), []).append(g)
    title_norm = _norm(video_title)

    game = detect_game(video_title, topic) if game is _DETECT else (game or None)
    terms: list[str] = []
    if game:
        terms.append(game)
        known = list((_games().get(game) or {}).get("terms", [])) + list(game_terms or [])
        for term in dict.fromkeys(known):
            if _norm(term) in title_norm or _found_in(term, ngrams, buckets):
                terms.append(term)
    for t in user_terms(lang) + list(extra_terms or []):
        if t not in terms:
            terms.append(t)

    # Proper nouns: words Whisper writes capitalized in the middle of sentences.
    caps, total = Counter(), Counter(lower)
    for i, w in enumerate(clean):
        prev = raw[i - 1] if i else "."
        if w[:1].isupper() and not prev.endswith((".", "!", "?", "…")):
            caps[lexicon.lower(w, spoken)] += 1
    proper = {w for w, n in caps.items() if n >= 2 and n / total[w] >= 0.6 and len(w) >= 3
              and lexicon.zipf(w, spoken) < 3.5}

    # Streamer words: much more frequent here than in the language in general (keyness).
    streamer: list[tuple[float, str]] = []
    n_words = max(1, len(lower))
    if lexicon.available() and spoken not in ("zh", "ja"):
        for w, n in total.items():
            if (n < 4 or len(w) < 3 or len(set(w)) <= 2 or any(ch.isdigit() for ch in w)
                    or has_profanity(w) or w in NOT_FOR_TITLES):
                continue
            z = lexicon.zipf(w, spoken)
            if z == 0 and lexicon.known_score(w, spoken) > 0:
                continue  # a normal inflected word the small word list just doesn't have
            freq = 10 ** (z - 9) if z else 1e-8
            if freq > 1e-4:  # everyday words ("bir", "şey") never count
                continue
            score = math.log((n / n_words) / freq)
            if score > 4.5:
                streamer.append((score * math.log(n), w))
    streamer_words = [w for _s, w in sorted(streamer, reverse=True)[:15]]

    allowed = set(lower)
    for w in extra_allowed or []:
        for p in lexicon.words(w):
            allowed.add(lexicon.lower(p, lang))
    keep_case = set(proper)
    for t in terms:
        for p in lexicon.words(t):
            allowed.add(lexicon.lower(p, lang))
            if p[:1].isupper() and not _common_word(p, lang):
                keep_case.add(lexicon.lower(p, lang))
    return Glossary(lang=lang, game=game, terms=terms, streamer_words=streamer_words,
                    allowed=allowed, keep_case=keep_case)
