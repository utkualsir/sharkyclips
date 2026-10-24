"""Title writing: few-shot + glossary -> LLM draft -> local checks -> LLM proofread -> pick.

  1. draft      the LLM writes 9 title ideas, shown 10-15 natural example titles for the
                language and content type (examples/<lang>.json) plus the creator's liked
                titles (feedback.py), and the glossary of names to spell right (glossary.py).
  2. checks     emoji / Title Case / diacritics / Turkish "mı-mi" fixed locally; words that are
                neither in the transcript, the glossary nor the dictionary are flagged.
  3. proofread  a second, short LLM pass fixes spelling and grammar in the output language,
                gets the flagged words, and drops duplicates and repeated patterns.
  4. pick       titles that still contain unknown words, swearing, or repeat other clips are
                rejected; 6 are picked so that at most 2 have "!", at least one is a question
                and at least one is a calm / story title.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from pathlib import Path

from . import feedback, lexicon
from .glossary import Glossary

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"
TITLES_VERSION = 1
N_TITLES = 6
N_DRAFT = 9
N_DRAFT_FAST = 6  # "Fast analysis": fewer drafts, and a second round only when too few survive
MAX_BANG = 2
STYLES = ["question", "story", "calm", "punchy", "funny", "curiosity", "hype"]
QUESTION_END = ("?", "؟", "？")

GRAMMAR_HINTS = {
    "tr": "Turkish: use ç ğ ı İ ö ş ü correctly; the question particle mı/mi/mu/mü is a separate word "
          "and follows vowel harmony (\"geldi mi\", \"pompalı mı\"); suffixes on names take an "
          "apostrophe (\"Darius'a\"); normal sentence case, not Title Case.",
    "en": "English: sentence case (only the first word and names capitalized), natural spoken English.",
    "de": "German: nouns are capitalized, use ä ö ü ß correctly, natural spoken German.",
    "hu": "Hungarian: use á é í ó ö ő ú ü ű correctly, natural spoken Hungarian, sentence case.",
    "ru": "Russian: correct cases and agreement, natural spoken Russian, sentence case.",
    "ar": "Arabic: correct spelling, light colloquial tone is fine, no diacritics (tashkeel).",
    "zh": "Chinese: Simplified Chinese, full-width punctuation (，？！), natural short-video wording.",
}


def draft_schema(n: int = N_DRAFT) -> dict:
    return {"type": "object", "properties": {"titles": {
        "type": "array", "minItems": n - 2, "maxItems": n + 1, "items": {
            "type": "object",
            "properties": {"style": {"type": "string", "enum": STYLES},
                           "text": {"type": "string", "minLength": 3, "maxLength": 90}},
            "required": ["style", "text"]}}},
        "required": ["titles"]}


PROOF_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {"type": "array", "items": {
            "type": "object",
            "properties": {"i": {"type": "integer", "minimum": 1},
                           "text": {"type": "string", "minLength": 1, "maxLength": 90},
                           "keep": {"type": "boolean"}},
            "required": ["i", "text", "keep"]}},
        "hook_text": {"type": "string", "minLength": 1, "maxLength": 60},
        "cover_text": {"type": "string", "minLength": 1, "maxLength": 32},
    },
    "required": ["titles", "hook_text", "cover_text"],
}

PROOF_SYSTEM = ("You are a meticulous native-speaker proofreader and editor for short video titles. "
                "You fix spelling and grammar, keep the casual tone, never add facts, and answer only with JSON.")


# ------------------------------------------------------------------ examples


@functools.lru_cache(maxsize=16)
def _examples_file(lang: str) -> dict:
    p = EXAMPLES_DIR / f"{lang}.json"
    if not p.is_file():
        p = EXAMPLES_DIR / "en.json"
    return json.loads(p.read_text(encoding="utf-8"))


def examples(lang: str, mode: str, n: int = 15) -> list[dict]:
    data = _examples_file(lang)
    out = list(data.get(mode) or data.get("gaming") or [])
    return out[:n]


def style_digest(lang: str, mode: str) -> str:
    """Changes when the examples or the creator's likes change (part of the cache key)."""
    liked, disliked = feedback.examples(lang, mode)
    payload = [TITLES_VERSION, [e["text"] for e in examples(lang, mode)], liked, disliked]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:12]


# ------------------------------------------------------------------ checks


def is_question(t: str) -> bool:
    return t.rstrip().endswith(QUESTION_END)


def has_bang(t: str) -> bool:
    return "!" in t or "！" in t


def is_calm(t: dict) -> bool:
    """A plain statement: no "!", no question, no "..." cliffhanger (the style tag is ignored,
    the model labels styles loosely)."""
    x = t["text"].rstrip()
    return not has_bang(x) and not is_question(x) and not x.endswith(("...", "…"))


# Fine on stream, not in a title (mild swearing / rude fillers the swear filter lets through).
RUDE = {
    "tr": re.compile(r"(?<!\w)(?:u?lan|len|lavuk\w*|kahretsin|kahrolsun|allah kahretsin|lanet olsun|salak|gerizekal\w*|aptal\w*|mal)(?!\w)", re.I),
    "en": re.compile(r"(?<!\w)(?:damn|wtf|stupid|idiot|retard\w*|hell no)(?!\w)", re.I),
    "de": re.compile(r"(?<!\w)(?:verdammt|scheiß\w*|idiot\w*|digga)(?!\w)", re.I),
    "ru": re.compile(r"(?<!\w)(?:блин|чёрт|черт|идиот\w*|дурак\w*)(?!\w)", re.I),
    "hu": re.compile(r"(?<!\w)(?:a francba|hülye\w*|idióta\w*)(?!\w)", re.I),
}


def is_rude(text: str, lang: str) -> bool:
    rx = RUDE.get(lang)
    return bool(rx and rx.search(text))


def unbang(text: str) -> str:
    text = text.replace("?!", "?").replace("!?", "?").replace("？！", "？")
    text = re.sub(r"\s*[!！]+\s*$", "", text)
    return re.sub(r"[!！]+", ",", text).strip(" ,")


def _first_word(t: str) -> str:
    m = re.findall(r"\w+", t.casefold())
    return m[0] if m else ""


def variety_problems(titles: list[dict]) -> list[str]:
    errs = []
    texts = [t["text"] for t in titles]
    if sum(has_bang(t) for t in texts) > MAX_BANG:
        errs.append(f'at most {MAX_BANG} titles may contain "!"; write the others as calm statements or questions')
    if not any(is_question(t) for t in texts):
        errs.append("at least two titles must be real questions ending with '?'")
    if not any(is_calm(t) for t in titles):
        errs.append('at least two titles must be calm statements that simply tell what happened (no "!", no "?")')
    long = [t for t in texts if len(t) > 65]
    if len(long) > 1:
        errs.append(f"titles are too long, keep them under 55 characters: {long[:3]}")
    firsts = [_first_word(t) for t in texts]
    for w in set(firsts):
        if w and firsts.count(w) > 2:
            errs.append(f"too many titles start with '{w}'; vary the openings")
    return errs


def pick(titles: list[dict], n: int = N_TITLES, slang: set[str] | None = None) -> list[dict]:
    """Best n titles (input is strongest first) with the variety rules applied. Titles using the
    streamer's own words ("kanka") are limited to two, so it stays a flavour, not a pattern."""
    slang = slang or set()

    def slangy(t: dict) -> bool:
        return bool(slang & {w.casefold() for w in re.findall(r"\w+", t["text"])})

    if slang:
        keep, n_slang = [], 0
        for t in titles:
            if slangy(t):
                n_slang += 1
                if n_slang > 2 and len(titles) - (n_slang - 2) >= n:
                    continue
            keep.append(t)
        titles = keep
    chosen: list[int] = []
    q = next((i for i, t in enumerate(titles) if is_question(t["text"])), None)
    c = next((i for i, t in enumerate(titles) if is_calm(t)), None)
    for i in (q, c):
        if i is not None and i not in chosen:
            chosen.append(i)
    firsts: dict[str, int] = {}
    for i in chosen:
        firsts[_first_word(titles[i]["text"])] = firsts.get(_first_word(titles[i]["text"]), 0) + 1
    for i, t in enumerate(titles):
        if len(chosen) >= n:
            break
        fw = _first_word(t["text"])
        if i in chosen or firsts.get(fw, 0) >= 2:
            continue
        chosen.append(i)
        firsts[fw] = firsts.get(fw, 0) + 1
    for i, t in enumerate(titles):  # still short: relax the opening-word rule
        if len(chosen) >= n:
            break
        if i not in chosen:
            chosen.append(i)
    out = [dict(titles[i]) for i in sorted(chosen)]
    bangs = 0
    for t in out:
        if has_bang(t["text"]):
            bangs += 1
            if bangs > MAX_BANG:
                t["text"] = unbang(t["text"])
    return out


# ------------------------------------------------------------------ prompts


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items)


def draft_task(*, lang: str, lang_label: str, mode: str, what_happens: str, topic: str,
               glossary: Glossary, used_titles: list[str], avoid: list[str] | None = None,
               problems: list[str] | None = None, n_draft: int = N_DRAFT) -> str:
    ex = examples(lang, mode)
    liked, disliked = feedback.examples(lang, mode)
    parts = [
        "TASK: write title ideas for THIS clip.",
        f"What happens in the clip: {what_happens}",
        f"Game / topic: {topic or 'unknown'}",
        "",
        f"How real {lang_label} creators title clips like this (style references only: copy the tone, "
        "length and casual wording, NEVER their content; most of them have no \"!\"):",
        _bullets([e["text"] for e in ex]),
    ]
    if liked:
        parts += ["", "Titles THIS creator liked before (match this style most closely, but not the content):",
                  _bullets(liked)]
    if disliked:
        parts += ["", "Titles this creator disliked (avoid this style):", _bullets(disliked)]
    if glossary.terms:
        parts += ["", "Names and terms: if you use one, spell it exactly like this: " + ", ".join(glossary.terms)]
    if glossary.streamer_words:
        parts += ["Words the streamer often says (at most 2 titles may use one, only where it sounds natural): "
                  + ", ".join(glossary.streamer_words[:8])]
    others = (avoid or []) + used_titles[-30:]
    parts += [
        "",
        f"Write {n_draft} different titles in {lang_label}, ordered from strongest to weakest:",
        "- casual and natural, how a real creator in this language writes; mostly 25-55 characters, never over 65",
        "- tell viewers who haven't seen the stream what the moment is; don't just quote the streamer's sentences",
        "- about what really happens in the CLIP lines; never name a map, weapon, character or person "
        "that is not in the transcript or the list above",
        f'- at least 2 questions ending with "?"; at least 2 calm or story titles that simply tell what '
        f'happened; at most {MAX_BANG} titles with "!" in total; not every title is clickbait',
        "- every title starts differently and is built differently",
        "- no emojis, no hashtags, no ALL CAPS, no Title Case, no swearing or rude fillers (even if the streamer says them)",
        f"- {GRAMMAR_HINTS.get(lang, 'correct spelling and grammar')}",
        "- style: one of " + ", ".join(STYLES),
    ]
    if others:
        parts += ["Do NOT reuse words, phrases or patterns from these titles (they are other moments or "
                  "already used):", _bullets(others)]
    if problems:
        parts += ["", "Problems with your earlier ideas, avoid them:", _bullets(problems[:10])]
    return "\n".join(parts)


def proof_prompt(*, lang_label: str, lang: str, what_happens: str, clip_lines: str, glossary: Glossary,
                 titles: list[dict], suspects: dict[int, list[str]], hook_text: str, cover_text: str) -> str:
    listing = "\n".join(f"{i + 1}. {t['text']}" for i, t in enumerate(titles))
    sus = "\n".join(f"- title {i}: {', '.join(repr(w) for w in ws)}" for i, ws in suspects.items())
    return f"""Proofread these short-video titles written in {lang_label}.

What happens in the clip: {what_happens}
What is said in the clip (names and words are spelled as heard):
{clip_lines}
Names and terms (correct spelling): {', '.join(glossary.terms) or '(none)'}

Titles:
{listing}

Hook text (on screen in the first seconds): {hook_text}
Cover text (on the thumbnail): {cover_text}

For every title return i, the corrected text and keep:
- fix spelling, grammar, word order and punctuation so it reads like a native {lang_label} speaker wrote it; keep it short, casual and close to the original
- {GRAMMAR_HINTS.get(lang, '')}
- do not add "!" and do not add facts
- keep=false only if the title clearly makes no sense, or says almost the same as an earlier title in this list (keep the better one); otherwise keep=true
- return the title text only, without numbers or labels
{('A dictionary check found words that may be misspelled or invented; correct them or set keep=false:' + chr(10) + sus) if sus else ''}
Also return the corrected hook_text (max 6 words) and cover_text (1-4 words)."""


# ------------------------------------------------------------------ main


def _polish_all(items: list[dict], lang: str, g: Glossary) -> list[dict]:
    out = []
    for t in items:
        text, _fixes = lexicon.polish(g.canonicalize(t["text"]), lang, keep=g.keep_case, protected=g.allowed)
        text = g.canonicalize(text)
        if text:
            out.append({**t, "text": text})
    return out


def refilter(tw: dict, lang: str, has_profanity) -> dict:
    """Drop titles / texts that the current swear and rude-word filters reject."""
    bad = lambda x: has_profanity(x) or is_rude(x, lang)  # noqa: E731
    keep = [t for t in tw.get("titles", []) if not bad(t["text"])]
    return {**tw, "titles": keep,
            "hook_text": "" if bad(tw.get("hook_text", "")) else tw.get("hook_text", ""),
            "cover_text": "" if bad(tw.get("cover_text", "")) else tw.get("cover_text", "")}


def write(model, *, system: str, context: str, lang: str, lang_label: str, mode: str, what_happens: str,
          topic: str, glossary: Glossary, used_titles: list[str], hook_text: str, cover_text: str,
          clip_lines: str, too_similar, has_profanity, avoid: list[str] | None = None,
          temperature: float = 0.75, script_check=None, fast: bool = False) -> dict:
    """One clip's titles. `context` is the same prompt prefix the judge call used (so Ollama
    can reuse its prompt cache); returns {titles, hook_text, cover_text, checks}.
    fast=True: fewer drafts and usually a single draft + proofread round."""
    n_draft = N_DRAFT_FAST if fast else N_DRAFT
    avoid = list(avoid or [])
    example_texts = [e["text"] for e in examples(lang, mode)] + feedback.examples(lang, mode)[0]
    checks: dict = {"rejected": [], "fixed": [], "rounds": 0}
    pool: list[dict] = []
    problems: list[str] = []

    def draft_soft(d: dict) -> list[str]:
        errs = variety_problems(d["titles"])
        for t in d["titles"]:
            if has_profanity(t["text"]) or is_rude(t["text"], lang):
                errs.append(f"title '{t['text']}' contains swearing or a rude word")
            for u in used_titles + avoid:
                if too_similar(t["text"], u):
                    errs.append(f"title '{t['text']}' is too similar to '{u}'")
                    break
        return errs

    for _round in range(2):
        checks["rounds"] += 1
        prompt = context + "\n\n" + draft_task(lang=lang, lang_label=lang_label, mode=mode,
                                                what_happens=what_happens, topic=topic, glossary=glossary,
                                                used_titles=used_titles, avoid=avoid + [p["text"] for p in pool],
                                                problems=problems, n_draft=n_draft)
        d = model.json(system, prompt, draft_schema(n_draft), temperature=temperature, check=script_check,
                       soft=draft_soft, num_predict=900)
        d.pop("_soft_errors", None)
        drafts = _polish_all(d["titles"], lang, glossary)
        suspects = {i + 1: ws for i, t in enumerate(drafts)
                    if (ws := lexicon.unknown_words(t["text"], lang, glossary.allowed))}

        proof = model.json(PROOF_SYSTEM, proof_prompt(
            lang_label=lang_label, lang=lang, what_happens=what_happens, clip_lines=clip_lines,
            glossary=glossary, titles=drafts, suspects=suspects, hook_text=hook_text, cover_text=cover_text),
            PROOF_SCHEMA, temperature=0.2, num_predict=900)
        by_i = {x["i"]: x for x in proof["titles"]}
        if _round == 0:
            hook_text, cover_text = proof["hook_text"].strip() or hook_text, proof["cover_text"].strip() or cover_text

        for i, t in enumerate(drafts, start=1):
            p = by_i.get(i)
            if p is not None and not p["keep"]:
                checks["rejected"].append({"text": t["text"], "reason": "proofread: duplicate or nonsense"})
                continue
            new = (p["text"].strip() if p else t["text"]) or t["text"]
            if has_bang(new) and not has_bang(t["text"]):
                new = unbang(new)  # the proofreader may not add hype
            polished = _polish_all([{**t, "text": new}], lang, glossary)
            if not polished:
                continue
            final = polished[0]
            if final["text"] != t["text"]:
                checks["fixed"].append([t["text"], final["text"]])
            reason = None
            unknown = lexicon.unknown_words(final["text"], lang, glossary.allowed)
            if unknown:
                reason = "unknown words: " + ", ".join(unknown)
            elif has_profanity(final["text"]) or is_rude(final["text"], lang):
                reason = "swearing or rude word"
            elif any(too_similar(final["text"], e, phrases=False) for e in example_texts):
                reason = "copies an example title"
            elif len(final["text"]) > 80:
                reason = "too long"
            elif any(too_similar(final["text"], u) for u in used_titles + avoid):
                reason = "repeats another clip's title"
            elif any(too_similar(final["text"], k["text"], phrases=False) for k in pool):
                reason = "duplicate"
            if reason:
                checks["rejected"].append({"text": final["text"], "reason": reason})
                problems.append(f"'{final['text']}': {reason}")
                continue
            pool.append(final)
        if len(pool) >= (3 if fast else N_TITLES - 1):
            break

    titles = pick(pool, slang={w.casefold() for w in glossary.streamer_words}) if pool else []
    hook, _f = lexicon.polish(glossary.canonicalize(hook_text), lang, keep=glossary.keep_case,
                              protected=glossary.allowed)
    if lexicon.unknown_words(hook, lang, glossary.allowed) or has_profanity(hook) or is_rude(hook, lang):
        short = [t["text"] for t in titles if len(t["text"].split()) <= 6]
        checks["rejected"].append({"text": hook, "reason": "hook text: unknown words or swearing"})
        hook = short[0] if short else ""
    cover, _f = lexicon.polish(glossary.canonicalize(cover_text), lang, keep=glossary.keep_case,
                               protected=glossary.allowed)
    if has_profanity(cover) or is_rude(cover, lang):
        cover = ""
    checks["variety"] = variety_problems(titles)
    return {"titles": titles, "hook_text": " ".join(hook.split()[:6]), "cover_text": cover, "checks": checks}
