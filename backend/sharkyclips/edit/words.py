"""Language-aware word matching for word lists (swear words, fillers).

List entries:
  "word"      the whole word
  "stem*"     any word starting with stem
  "two words" consecutive words (each part may end in *)

Matching ignores case and accents, with one exception: Turkish dotless ı. An entry's "ı"
also matches a typed "i" ("amına" finds "amina"), but an entry's "i" never matches "ı"
("sik" must not find "sıkıntı" = trouble). Chinese / Japanese have no spaces: entries are
looked up inside the running text instead.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NO_SPACE_LANGS = {"zh", "ja"}
_PUNCT = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)
_RUNS = re.compile(r"(.)\1{2,}")


def lower(text: str, lang: str | None) -> str:
    if lang == "tr":  # Turkish capitals: I -> ı, İ -> i
        text = text.replace("I", "ı").replace("İ", "i")
    return text.lower()


def fold(text: str, lang: str | None = None, accents: bool = False) -> str:
    """Lowercase, no accents (ş -> s, á -> a, ё -> е, Arabic hamza / harakat), ß -> ss.
    Dotless ı stays ı. accents=True keeps accents (fillers: Hungarian "ő" is not "ö")."""
    t = lower(text, lang).replace("ß", "ss").replace("ـ", "")  # Arabic tatweel
    if accents:
        return unicodedata.normalize("NFC", t)
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", t)


def token(word: str, lang: str | None, accents: bool = False) -> str:
    """A transcript word as a comparable token (no punctuation around it)."""
    return _PUNCT.sub("", fold(word, lang, accents))


def squeeze(text: str) -> str:
    """Long letter runs -> two letters ("ıııı" -> "ıı", "eeeee" -> "ee", "hmmmm" -> "hmm")."""
    return _RUNS.sub(r"\1\1", text)


@dataclass(frozen=True)
class Entry:
    raw: str
    parts: tuple[re.Pattern, ...]  # one per word (spaced languages)
    sub: str | None = None  # no-space languages: folded substring


def _part_regex(part: str) -> re.Pattern:
    prefix = part.endswith("*")
    core = part.rstrip("*")
    out = []
    for ch in core:
        out.append("[ıi]" if ch == "ı" else re.escape(ch))
    return re.compile("^" + "".join(out) + (".*" if prefix else "") + "$")


def compile_entries(entries: list[str], lang: str | None, squeeze_runs: bool = False,
                    accents: bool = False) -> list[Entry]:
    out = []
    for raw in entries:
        e = " ".join(str(raw).split())
        if not e:
            continue
        f = fold(e, lang, accents)
        if squeeze_runs:
            f = squeeze(f)
        if lang in NO_SPACE_LANGS:
            out.append(Entry(e, (), f.replace(" ", "").rstrip("*")))
        else:
            parts = tuple(_part_regex(_PUNCT.sub("", p) + ("*" if p.endswith("*") else ""))
                          for p in f.split(" ") if _PUNCT.sub("", p))
            if parts:
                out.append(Entry(e, parts))
    return out


def find(words: list[str], entries: list[Entry], lang: str | None,
         squeeze_runs: bool = False, accents: bool = False) -> list[tuple[int, int, str]]:
    """Matches as (first word index, last word index, entry). Longest entries win."""
    toks = [token(w, lang, accents) for w in words]
    if squeeze_runs:
        toks = [squeeze(t) for t in toks]
    hits: list[tuple[int, int, str]] = []
    taken = [False] * len(toks)
    if lang in NO_SPACE_LANGS:
        # Running text with the word index of every character.
        text, owner = "", []
        for i, t in enumerate(toks):
            text += t
            owner += [i] * len(t)
        for e in sorted(entries, key=lambda e: -len(e.sub or "")):
            if not e.sub:
                continue
            start = 0
            while (k := text.find(e.sub, start)) >= 0:
                a, b = owner[k], owner[k + len(e.sub) - 1]
                if not any(taken[a:b + 1]):
                    hits.append((a, b, e.raw))
                    for j in range(a, b + 1):
                        taken[j] = True
                start = k + 1
        return sorted(hits)
    for e in sorted(entries, key=lambda e: -len(e.parts)):
        n = len(e.parts)
        for i in range(len(toks) - n + 1):
            if any(taken[i:i + n]):
                continue
            if all(toks[i + j] and e.parts[j].match(toks[i + j]) for j in range(n)):
                hits.append((i, i + n - 1, e.raw))
                for j in range(i, i + n):
                    taken[j] = True
    return sorted(hits)


def mask(word: str) -> str:
    """'ass' -> 'a**', 'Amına,' -> 'A****,' (first letter kept, punctuation kept). CJK: all *."""
    lead = re.match(r"^[\W_]*", word).group(0)
    trail = re.search(r"[\W_]*$", word).group(0)
    core = word[len(lead):len(word) - len(trail)] if trail else word[len(lead):]
    if not core:
        return word
    if any(unicodedata.east_asian_width(ch) in ("W", "F") for ch in core):
        return lead + "*" * len(core) + trail
    return lead + core[0] + "*" * (len(core) - 1) + trail
