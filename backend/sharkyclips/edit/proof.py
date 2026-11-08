"""Caption proofreading: spelling, names, capitalisation and punctuation of the clip words.

1. LLM pass (optional, cached per clip in <project>/cache/proof/<clip>.json): the local
   LLM gets the clip's words with the glossary and returns the same number of words with
   spelling, Turkish letters (ı/i, ş, ğ...), capitalisation and punctuation fixed. Answers
   that rewrite instead of correct (different word count, a word changed too much) are
   rejected word by word.
2. Every time (cheap, no LLM): glossary spellings (Settings > glossary), a capital letter
   at each sentence start (Turkish-aware: i -> İ), and a question mark after a Turkish
   question particle that ends a sentence ("geliyor musun" -> "geliyor musun?").

Fixes are keyed by the word's start time + original text, so trims and cuts don't matter.
Swear detection runs on the original words (a "correction" can't hide a swear).
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from ..project import Project, read_json, write_json_atomic
from .words import fold, token

SENTENCE_END = tuple(".!?…؟。！？")
QUESTION_TR = {"mı", "mi", "mu", "mü", "mısın", "misin", "musun", "müsün", "mıyım", "miyim", "muyum",
               "müyüm", "mıyız", "miyiz", "muyuz", "müyüz", "mısınız", "misiniz", "musunuz", "müsünüz",
               "acaba", "niye", "neden", "nasıl", "nerede", "nereye", "kim", "hangisi"}
PAUSE = 0.7


def key(w: dict) -> str:
    return f"{float(w['start']):.2f}|{w['word']}"


def _cap(word: str, lang: str | None) -> str:
    m = re.match(r"^([\W_]*)(\w)(.*)$", word, re.S)
    if not m:
        return word
    lead, first, rest = m.groups()
    if lang == "tr":
        first = {"i": "İ", "ı": "I"}.get(first, first.upper())
    else:
        first = first.upper()
    return lead + first + rest


def _user_terms(lang: str | None) -> list[str]:
    try:
        from ..titles.glossary import user_terms

        return user_terms(lang or "")
    except Exception:  # noqa: BLE001
        return []


def corrections() -> dict[str, str]:
    """1.2.34: caption words the user retyped once, fixed everywhere after ({wrong: right},
    the wrong word lower-cased; config "caption_corrections")."""
    from .. import config

    got = config.get("caption_corrections") or {}
    return {str(k): str(v) for k, v in got.items() if str(k).strip() and str(v).strip()} if isinstance(got, dict) else {}


def _lower(text: str, lang: str | None) -> str:
    if lang == "tr":
        text = text.replace("I", "ı").replace("İ", "i")
    return text.lower()


def learn(old: str, new: str, lang: str | None) -> dict | None:
    """Remember a retyped caption word: the same mistake is fixed in every later clip; a word
    the dictionary doesn't know (a name, a game term) also goes into the glossary."""
    from .. import config

    core_old = re.sub(r"^[\W_]+|[\W_]+$", "", old or "")
    core_new = re.sub(r"^[\W_]+|[\W_]+$", "", new or "")
    if not core_old or not core_new or _lower(core_old, lang) == _lower(core_new, lang):
        return None  # only punctuation / case: nothing to learn
    if len(core_old) <= 2:
        return None  # "o", "ya": too short to fix everywhere (this clip keeps its fix)
    corr = dict(config.get("caption_corrections") or {})
    corr[_lower(core_old, lang)] = core_new
    corr = dict(list(corr.items())[-500:])
    changes: dict = {"caption_corrections": corr}
    glossary_added = False
    try:
        from ..titles import lexicon

        unknown = " " not in core_new and lexicon.zipf(_lower(core_new, lang), lang or "en") == 0
    except Exception:  # noqa: BLE001
        unknown = False
    if unknown:
        g = config.get("glossary") or []
        if isinstance(g, dict):
            allt = list(g.get("all") or [])
            if core_new not in allt:
                changes["glossary"] = {**g, "all": allt + [core_new]}
                glossary_added = True
        elif core_new not in g:
            changes["glossary"] = list(g) + [core_new]
            glossary_added = True
    config.update(**changes)
    return {"from": _lower(core_old, lang), "to": core_new, "glossary": glossary_added}


def fix_words(words: list[dict], lang: str | None, fixes: dict[str, str] | None = None,
              terms: list[str] | None = None, corr: dict[str, str] | None = None) -> list[dict]:
    """Corrected copies of the words (times untouched; "orig" keeps the old text)."""
    out = [dict(w) for w in words]
    fixes = fixes or {}
    corr = corr if corr is not None else corrections()
    for w in out:
        new = fixes.get(key(w))
        if new and new != w["word"]:
            w["orig"] = w["word"]
            w["word"] = new
        elif corr:  # a mistake the user fixed before, in another clip
            core = re.sub(r"^[\W_]+|[\W_]+$", "", w["word"])
            right = corr.get(_lower(core, lang))
            if core and right and right != core:
                w["orig"] = w["word"]
                w["word"] = w["word"].replace(core, right)
    terms = terms if terms is not None else _user_terms(lang)
    single = {fold(t, lang): t for t in terms if " " not in t.strip() and len(t) >= 2}
    for w in out:
        core = re.sub(r"^[\W_]+|[\W_]+$", "", w["word"])
        canon = single.get(fold(core, lang))
        if canon and canon != core:
            w.setdefault("orig", w["word"])
            w["word"] = w["word"].replace(core, canon)
    for i, w in enumerate(out):
        prev = out[i - 1] if i else None
        starts = prev is None or prev["word"].rstrip().endswith(SENTENCE_END) or \
            (w["start"] - prev["end"] > PAUSE * 1.6 and not prev["word"].rstrip().endswith(","))
        if starts and w["word"][:1].isalpha() and w["word"][:1].islower():
            w.setdefault("orig", w["word"])
            w["word"] = _cap(w["word"], lang)
        nxt = out[i + 1] if i + 1 < len(out) else None
        ends = nxt is None or nxt["start"] - w["end"] > PAUSE
        if lang == "tr" and ends and token(w["word"], lang) in QUESTION_TR \
                and not re.search(r"[.!?…,;:]$", w["word"]):
            w.setdefault("orig", w["word"])
            w["word"] += "?"
    return out


# ------------------------------------------------------------------------------ LLM pass

SYSTEM = ("You proofread automatic speech-to-text subtitles. Fix spelling, letters with diacritics, "
          "capitalisation and punctuation ONLY. Never change, add, remove, translate, merge or "
          "split words, never censor swear words, never change slang or the meaning.")


def _schema(n: int) -> dict:
    return {"type": "object", "properties": {"words": {"type": "array", "items": {"type": "string"},
                                                       "minItems": n, "maxItems": n}},
            "required": ["words"]}


def _close(a: str, b: str, lang: str | None) -> bool:
    fa, fb = token(a, lang), token(b, lang)
    if fa == fb:
        return True
    if not fa or not fb:
        return False
    from .swears import _dist

    return _dist(fa, fb, 2) <= max(1, min(2, len(fa) // 4))


def proofread_words(llm, words: list[dict], lang: str | None, terms: list[str]) -> dict[str, str]:
    """{key(word): corrected} from one LLM call per ~60 words."""
    from .. import languages

    reg = languages.get(lang or "") if lang else None
    lang_label = reg.english_name if reg else (lang or "the spoken language")
    fixes: dict[str, str] = {}
    for i in range(0, len(words), 60):
        chunk = words[i:i + 60]
        listing = "\n".join(f"{j + 1}. {w['word']}" for j, w in enumerate(chunk))
        prompt = (f"Language: {lang_label}.\n"
                  + (f"Names and terms (spell exactly like this): {', '.join(terms[:40])}\n" if terms else "")
                  + f"Here are {len(chunk)} subtitle words in order. Return exactly {len(chunk)} words, the "
                  "same words in the same order, each corrected (punctuation stays attached to its word).\n"
                  + listing)

        def check(data: dict, n=len(chunk)) -> list[str]:
            return [] if len(data.get("words") or []) == n else [f"return exactly {n} words"]

        data = llm.json(SYSTEM, prompt, _schema(len(chunk)), temperature=0.2, check=check,
                        num_predict=60 + 12 * len(chunk))
        for w, new in zip(chunk, data.get("words") or []):
            new = str(new).strip()
            if new and new != w["word"] and " " not in new and _close(w["word"], new, lang):
                fixes[key(w)] = new
    return fixes


def cache_path(project: Project, cid: str) -> Path:
    return project.cache_dir / "proof" / f"{cid}.json"


def text_hash(words: list[dict]) -> str:
    return hashlib.sha1("|".join(key(w) for w in words).encode("utf-8")).hexdigest()[:16]


def cached_fixes(project: Project, cid: str | None) -> dict[str, str]:
    if not cid:
        return {}
    p = cache_path(project, cid)
    if not p.is_file():
        return {}
    try:
        return dict(read_json(p).get("fixes") or {})
    except Exception:  # noqa: BLE001
        return {}


def proofread_project(project: Project, on_progress=None, force: bool = False) -> dict:
    """LLM proofreading of every clip's words (cached; unchanged clips are skipped)."""
    from .. import llm as llm_mod
    from ..web import state
    from .plan import transcript_words

    hl = state.load_highlights(project) or {}
    cands = hl.get("candidates", [])
    done, changed, t0 = 0, 0, time.time()
    with llm_mod.lazy_session() as llm:
        for i, c in enumerate(cands):
            if on_progress:
                on_progress(i, len(cands))
            words, lang = transcript_words(project, float(c["start"]) - 1, float(c["end"]) + 1)
            if not words:
                continue
            h = text_hash(words)
            p = cache_path(project, c["id"])
            if p.is_file() and not force:
                try:
                    if read_json(p).get("hash") == h:
                        continue
                except Exception:  # noqa: BLE001
                    pass
            terms = _user_terms(lang)
            fixes = proofread_words(llm, words, lang, terms)
            write_json_atomic(p, {"hash": h, "fixes": fixes, "model": getattr(llm, "model", None),
                                  "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
            done += 1
            changed += len(fixes)
    return {"clips": done, "fixes": changed, "seconds": round(time.time() - t0, 1)}
