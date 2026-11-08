"""Title writing: few-shot + glossary -> LLM draft -> local checks -> LLM proofread -> pick.

  1. draft      the LLM writes 9 title ideas, shown 10-15 natural example titles for the
                language and content type (examples/<lang>.json, game-specific ones first) plus
                the creator's liked titles (feedback.py), and the glossary of names to spell right.
  2. checks     emoji / Title Case / diacritics / Turkish "mı-mi" fixed locally; words that are
                neither in the transcript, the glossary nor the dictionary are flagged.
  3. proofread  a second, short LLM pass fixes spelling and grammar in the output language,
                gets the flagged words, and drops duplicates and repeated patterns.
  4. pick       titles that still contain unknown words, swearing, another game's name, or repeat
                other clips are rejected; 6 are picked.

Gaming ("punchy", 1.2.25): 6 formulas (shock, question, nobody_expected, number, story, punchy),
1-2 KEY WORDS IN CAPITALS, at most one "!", optionally one fitting emoji at the very end,
40-60 characters with the key word in the first 40. Study / music keep the calm rules.
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
TITLES_VERSION = 3
N_TITLES = 6
N_DRAFT = 9
N_DRAFT_FAST = 6  # "Fast analysis": fewer drafts, and a second round only when too few survive
MAX_BANG = 2
STYLES = ["question", "story", "calm", "punchy", "funny", "curiosity", "hype"]
FORMULAS = ["shock", "question", "nobody_expected", "number", "story", "punchy"]
QUESTION_END = ("?", "؟", "？")
# Emojis that fit a gaming title (one, at the very end).
FIT_EMOJI = ["😱", "💀", "🔥", "😂", "🤯", "😳", "👀", "🏆", "⚡", "🎯", "😭", "🤣", "😤", "🫡", "💥", "🧠", "😎", "🙃", "😅", "🥶"]
NO_CAPS_LANGS = ("ar", "zh", "ja")
TITLE_MIN, TITLE_MAX, KEY_WITHIN = 40, 60, 40

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
FORMULA_HINTS = {
    "shock": "the most shocking moment, said hard and short",
    "question": 'a real question to the viewer, ending with "?"',
    "nobody_expected": '"nobody expected this" angle, in your own words',
    "number": "a number or challenge that is REALLY in the clip (1v4, 3 kills, 8k, last 10 seconds); never the clip times from the transcript list (+7s)",
    "story": "a mini story with a twist: what happened first, then what",
    "punchy": "very short and hard, 3-6 words",
}


def draft_schema(n: int = N_DRAFT, punchy: bool = False) -> dict:
    return {"type": "object", "properties": {"titles": {
        "type": "array", "minItems": n - 2, "maxItems": n + 1, "items": {
            "type": "object",
            "properties": {"style": {"type": "string", "enum": FORMULAS if punchy else STYLES},
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


def examples(lang: str, mode: str, n: int = 15, game: str | None = None) -> list[dict]:
    """Style references. Game-specific ones ("gaming.lol") come first and never reach other
    games' prompts (no PENTAKILL examples on a Delta Force clip)."""
    data = _examples_file(lang)
    own = list(data.get(f"{mode}.{game}") or []) if game else []
    out = own + list(data.get(mode) or data.get("gaming") or [])
    return out[:n]


def style_digest(lang: str, mode: str, game: str | None = None) -> str:
    """Changes when the examples or the creator's likes change (part of the cache key)."""
    liked, disliked = feedback.examples(lang, mode)
    payload = [TITLES_VERSION, [e["text"] for e in examples(lang, mode, game=game)], liked, disliked]
    return hashlib.sha1(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()[:12]


# ------------------------------------------------------------------ checks


def is_question(t: str) -> bool:
    return t.rstrip().rstrip("".join(FIT_EMOJI) + " ️").endswith(QUESTION_END)


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


MILD = re.compile(r"(?<!\w)(?:u?lan|len)(?!\w)", re.I)


def is_rude(text: str, lang: str, mild_ok: bool = False) -> bool:
    """mild_ok: "lan" / "ulan" are fine (My style: the creator's own titles use them)."""
    rx = RUDE.get(lang)
    if mild_ok:
        text = MILD.sub(" ", text)
    return bool(rx and rx.search(text))


def unbang(text: str) -> str:
    emoji = _end_emoji(text)
    text = lexicon.strip_emoji(text) if emoji else text
    text = text.replace("?!", "?").replace("!?", "?").replace("？！", "？")
    text = re.sub(r"\s*[!！]+\s*$", "", text)
    text = re.sub(r"[!！]+", ",", text).strip(" ,")
    return f"{text} {emoji}" if emoji else text


def _first_word(t: str) -> str:
    m = re.findall(r"\w+", t.casefold())
    return m[0] if m else ""


# ------------------------------------------------------------------ punchy style


def _end_emoji(text: str) -> str:
    """The one emoji a title keeps: the first fitting one it has."""
    for ch in lexicon.EMOJI_RE.findall(text or ""):
        if ch in FIT_EMOJI:
            return ch
    return ""


def _fold(text: str) -> str:
    """Lowercase that ignores Turkish dotted / dotless i and keeps the length."""
    return "".join(ch.lower() if len(ch.lower()) == 1 else ch for ch in
                   text.replace("İ", "i").replace("I", "i").replace("ı", "i"))


def caps_words(text: str) -> list[str]:
    """Words written in CAPITALS (key words like CLUTCH, 1v4 counts too)."""
    out = []
    for w in re.findall(r"[^\W_]+(?:['’][^\W_]+)?", text):
        core = re.split(r"['’]", w)[0]
        letters = [ch for ch in core if ch.isalpha()]
        if (len(letters) >= 3 and all(ch.isupper() for ch in letters)) or re.fullmatch(r"1v[1-5]", core, re.I):
            out.append(core)
    return out


def style_title(text: str, lang: str, keywords: list[str] | None = None, keep: set[str] | frozenset[str] = frozenset()) -> str:
    """Local fixes for a punchy title: at most 2 CAPS words (acronyms like AWP don't count), one
    "!", one fitting emoji at the very end. A title without a CAPS word gets its key word
    capitalized when it has one (a fact word like "pentakill" or "clutch")."""
    emoji = _end_emoji(text)
    body = lexicon.strip_emoji(text).strip()
    if lang not in NO_CAPS_LANGS:
        seen = 0
        acronyms = {k for k in keep}

        def fix(m: re.Match) -> str:
            nonlocal seen
            w = m.group(0)
            letters = [ch for ch in w if ch.isalpha()]
            if len(letters) < 3 or not all(ch.isupper() for ch in letters) or lexicon.lower(w, lang) in acronyms and len(w) <= 4:
                return w
            seen += 1
            return w if seen <= 2 else lexicon.lower(w, lang)

        body = re.sub(r"[^\W\d_]+", fix, body)
        if not caps_words(body) and keywords:
            low = _fold(body)
            for k in keywords:
                kl = _fold(k)
                if len(kl) < 3 or len(low) != len(body):
                    continue
                m = re.search(rf"(?<!\w){re.escape(kl)}(?![^\W\d_])", low)
                if m and m.start() < KEY_WITHIN:
                    body = body[:m.start()] + k + body[m.end():]  # bank key words are written in CAPS
                    break
    if body.count("!") + body.count("！") > 1:  # keep the last "!" only
        last = max(body.rfind("!"), body.rfind("！"))
        body = re.sub(r"[!！]", "", body[:last]).rstrip() + body[last:]
        body = re.sub(r"\s+([!?,.])", r"\1", body)
    body = body.strip()
    return f"{body} {emoji}" if emoji else body


def punchy_problems(titles: list[dict], lang: str, keywords: list[str] | None = None) -> list[str]:
    errs = []
    texts = [t["text"] for t in titles]
    if any(t.count("!") + t.count("！") > 1 for t in texts):
        errs.append('at most one "!" in a title')
    if sum(has_bang(t) for t in texts) > MAX_BANG:
        errs.append(f'at most {MAX_BANG} titles may contain "!"')
    if not any(is_question(t) for t in texts):
        errs.append("at least one title must be a real question ending with '?'")
    if lang not in NO_CAPS_LANGS:
        flat = [t for t in texts if not caps_words(t)]
        if len(flat) > 1:
            errs.append(f"every title needs 1-2 KEY WORDS IN CAPITALS (CLUTCH, 1v4, ACE...): {flat[:3]}")
        loud = [t for t in texts if len(caps_words(t)) > 2]
        if loud:
            errs.append(f"at most 2 words in CAPITALS per title: {loud[:2]}")
        late = [t for t in texts if caps_words(t) and lexicon.strip_emoji(t).find(caps_words(t)[0]) > KEY_WITHIN]
        if late:
            errs.append(f"put the CAPS key word in the first {KEY_WITHIN} characters: {late[:2]}")
    if lang not in ("zh", "ja"):
        long = [t for t in texts if len(lexicon.strip_emoji(t)) > TITLE_MAX + 5]
        short = [t for t in titles if len(lexicon.strip_emoji(t["text"])) < 25 and t.get("style") != "punchy"]
        if long:
            errs.append(f"titles must be {TITLE_MIN}-{TITLE_MAX} characters, these are too long: {long[:3]}")
        if len(short) > 1:
            errs.append(f"titles are too short, write {TITLE_MIN}-{TITLE_MAX} characters: {[t['text'] for t in short[:3]]}")
    if sum(bool(_end_emoji(t)) for t in texts) > 4:
        errs.append("not every title needs an emoji: at most half of them")
    styles = {t.get("style") for t in titles}
    missing = [f for f in FORMULAS if f not in styles]
    if len(missing) > 2:
        errs.append("use all 6 formulas (" + ", ".join(FORMULAS) + "); missing: " + ", ".join(missing))
    firsts = [_first_word(t) for t in texts]
    for w in set(firsts):
        if w and firsts.count(w) > 2:
            errs.append(f"too many titles start with '{w}'; vary the openings")
    return errs


def variety_problems(titles: list[dict], punchy: bool = False, lang: str = "en") -> list[str]:
    if punchy:
        return punchy_problems(titles, lang)
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


def _fit_score(t: dict, lang: str) -> int:
    """How well a punchy title meets the format (higher = better)."""
    x = lexicon.strip_emoji(t["text"])
    s = 0
    if lang in ("zh", "ja") or TITLE_MIN - 6 <= len(x) <= TITLE_MAX + 2 or (t.get("style") == "punchy" and len(x) >= 18):
        s += 2
    if lang in NO_CAPS_LANGS or 1 <= len(caps_words(x)) <= 2:
        s += 2
    return s


def pick(titles: list[dict], n: int = N_TITLES, slang: set[str] | None = None, punchy: bool = False,
         lang: str = "en") -> list[dict]:
    """Best n titles (input is strongest first) with the variety rules applied. Titles using the
    streamer's own words ("kanka") are limited to two, so it stays a flavour, not a pattern.
    Punchy: one title per formula first (strongest well-formed one), then the rest."""
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
    if punchy:
        for f in FORMULAS:
            cands = [i for i, t in enumerate(titles) if t.get("style") == f and i not in chosen]
            if cands:
                chosen.append(max(cands, key=lambda i: (_fit_score(titles[i], lang), -i)))
        if not any(is_question(titles[i]["text"]) for i in chosen):
            q = next((i for i, t in enumerate(titles) if is_question(t["text"]) and i not in chosen), None)
            if q is not None:
                if len(chosen) >= n:
                    chosen.pop()
                chosen.append(q)
        chosen = chosen[:n]
    else:
        q = next((i for i, t in enumerate(titles) if is_question(t["text"])), None)
        c = next((i for i, t in enumerate(titles) if is_calm(t)), None)
        for i in (q, c):
            if i is not None and i not in chosen:
                chosen.append(i)
    firsts: dict[str, int] = {}
    for i in chosen:
        firsts[_first_word(titles[i]["text"])] = firsts.get(_first_word(titles[i]["text"]), 0) + 1
    order = sorted(range(len(titles)), key=lambda i: (-_fit_score(titles[i], lang), i)) if punchy else range(len(titles))
    for i in order:
        t = titles[i]
        if len(chosen) >= n:
            break
        fw = _first_word(t["text"])
        if i in chosen or firsts.get(fw, 0) >= 2:
            continue
        chosen.append(i)
        firsts[fw] = firsts.get(fw, 0) + 1
    for i, _t in enumerate(titles):  # still short: relax the opening-word rule
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
    if punchy:  # at most 3 of the 6 end with an emoji (variety)
        emo = 0
        for t in out:
            if _end_emoji(t["text"]):
                emo += 1
                if emo > 3:
                    t["text"] = lexicon.strip_emoji(t["text"])
    return out


# ------------------------------------------------------------------ prompts


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items)


def draft_task(*, lang: str, lang_label: str, mode: str, what_happens: str, topic: str,
               glossary: Glossary, used_titles: list[str], avoid: list[str] | None = None,
               problems: list[str] | None = None, n_draft: int = N_DRAFT, punchy: bool = False,
               keywords: list[str] | None = None, vocab: list[str] | None = None, facts: str = "",
               game: str | None = None) -> str:
    ex = examples(lang, mode, game=game)
    liked, disliked = feedback.examples(lang, mode)
    parts = [
        "TASK: write title ideas for THIS clip.",
        f"What happens in the clip: {what_happens}",
        f"Game / topic: {topic or 'unknown'}",
    ]
    if facts:
        parts.append(f"Clip facts (reliable): {facts}")
    parts += [
        "",
        f"How real {lang_label} creators title clips like this (style references only: copy the tone, "
        "length and wording style, NEVER their content"
        + ("):" if punchy else "; most of them have no \"!\"):"),
        _bullets([e["text"] for e in ex]),
    ]
    if liked:
        parts += ["", "Titles THIS creator liked before (match this style most closely, but not the content):",
                  _bullets(liked)]
    if disliked:
        parts += ["", "Titles this creator disliked (avoid this style):", _bullets(disliked)]
    if glossary.terms:
        parts += ["", "Names and terms: if you use one, spell it exactly like this: " + ", ".join(glossary.terms)]
    if punchy and keywords and lang not in NO_CAPS_LANGS:
        parts += ["KEY WORDS for CAPITALS (use one only if it matches what really happens): " + ", ".join(keywords)]
    if punchy and vocab:
        parts += ["Words players of this game use (only where they fit): " + ", ".join(vocab)]
    if glossary.streamer_words:
        parts += ["Words the streamer often says (at most 2 titles may use one, only where it sounds natural): "
                  + ", ".join(glossary.streamer_words[:8])]
    others = (avoid or []) + used_titles[-30:]
    if punchy:
        caps = ("- 1-2 KEY WORDS IN CAPITALS (like CLUTCH, PENTAKILL, 1v4, ACE), the key word within the first "
                f"{KEY_WITHIN} characters; every other word in normal sentence case (no Title Case)"
                if lang not in NO_CAPS_LANGS else "- one strong key word near the start")
        parts += [
            "",
            f"Write {n_draft} different titles in {lang_label}, strongest first. Label each with its formula and "
            "use every formula at least once:",
            _bullets([f"{f}: {h}" for f, h in FORMULA_HINTS.items()]),
            "Rules:",
            f"- {TITLE_MIN}-{TITLE_MAX} characters (punchy may be shorter), never over 65",
            caps,
            "- curiosity or emotion: make people NEED to see what happens; true to the CLIP lines and facts",
            "- optional: ONE fitting emoji at the very end (" + " ".join(FIT_EMOJI[:8]) + "); at most half of the titles",
            '- at most one "!" in a title and at most 2 titles with "!"; no hashtags',
            f"- only about {topic}: never name another game; never name a map, weapon, character or person that is "
            "not in the clip facts, the transcript or the list above" if topic and topic != "Gaming"
            else "- the game is unknown: never name a game; never name a map, weapon, character or person that is "
                 "not in the transcript or the list above",
            "- no swearing or rude fillers (even if the streamer says them)",
            f"- {GRAMMAR_HINTS.get(lang, 'correct spelling and grammar')}",
            "- every title starts differently and is built differently",
        ]
    else:
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
                 titles: list[dict], suspects: dict[int, list[str]], hook_text: str, cover_text: str,
                 punchy: bool = False) -> str:
    listing = "\n".join(f"{i + 1}. {t['text']}" for i, t in enumerate(titles))
    sus = "\n".join(f"- title {i}: {', '.join(repr(w) for w in ws)}" for i, ws in suspects.items())
    style = ("- keep the words in CAPITALS and the emoji at the end exactly where they are; don't add new ones\n"
             if punchy else "")
    hook = ("Also return the corrected hook_text and cover_text: each 2-4 punchy words, one key word may be in "
            "CAPITALS, no emoji." if punchy else
            "Also return the corrected hook_text (max 6 words) and cover_text (1-4 words).")
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
{style}- do not add "!" and do not add facts
- keep=false only if the title clearly makes no sense, or says almost the same as an earlier title in this list (keep the better one); otherwise keep=true
- return the title text only, without numbers or labels
{('A dictionary check found words that may be misspelled or invented; correct them or set keep=false:' + chr(10) + sus) if sus else ''}
{hook}"""


# ------------------------------------------------------------------ main


def _polish_all(items: list[dict], lang: str, g: Glossary, punchy: bool = False,
                keywords: list[str] | None = None) -> list[dict]:
    out = []
    for t in items:
        emoji = _end_emoji(t["text"]) if punchy else ""
        text, _fixes = lexicon.polish(g.canonicalize(t["text"]), lang, keep=g.keep_case, protected=g.allowed)
        text = g.canonicalize(text)
        if punchy and text:
            text = style_title(f"{text} {emoji}" if emoji else text, lang, keywords, keep=g.keep_case)
        if text:
            out.append({**t, "text": text})
    return out


def refilter(tw: dict, lang: str, has_profanity, forbidden=None, mild_ok: bool = False) -> dict:
    """Drop titles / texts that the current swear, rude-word and other-game filters reject."""
    bad = lambda x: has_profanity(x) or is_rude(x, lang, mild_ok) or bool(forbidden and forbidden(x))  # noqa: E731
    keep = [t for t in tw.get("titles", []) if not bad(t["text"])]
    return {**tw, "titles": keep,
            "hook_text": "" if bad(tw.get("hook_text", "")) else tw.get("hook_text", ""),
            "cover_text": "" if bad(tw.get("cover_text", "")) else tw.get("cover_text", "")}


def _short_text(text: str, n: int) -> str:
    return " ".join(lexicon.strip_emoji(text).split()[:n])


def write(model, *, system: str, context: str, lang: str, lang_label: str, mode: str, what_happens: str,
          topic: str, glossary: Glossary, used_titles: list[str], hook_text: str, cover_text: str,
          clip_lines: str, too_similar, has_profanity, avoid: list[str] | None = None,
          temperature: float = 0.75, script_check=None, fast: bool = False, forbidden=None,
          keywords: list[str] | None = None, vocab: list[str] | None = None, facts: str = "",
          punchy: bool = False, game: str | None = None) -> dict:
    """One clip's titles. `context` is the same prompt prefix the judge call used (so Ollama
    can reuse its prompt cache); returns {titles, hook_text, cover_text, checks}.
    fast=True: fewer drafts and usually a single draft + proofread round.
    forbidden(text) -> the other game a text names (rejected), punchy=True: the gaming format."""
    n_draft = N_DRAFT_FAST if fast else N_DRAFT
    avoid = list(avoid or [])
    example_texts = [e["text"] for e in examples(lang, mode, game=game)] + feedback.examples(lang, mode)[0]
    checks: dict = {"rejected": [], "fixed": [], "rounds": 0}
    pool: list[dict] = []
    problems: list[str] = []
    other = forbidden or (lambda _t: None)

    def draft_soft(d: dict) -> list[str]:
        errs = variety_problems(d["titles"], punchy=punchy, lang=lang)
        for t in d["titles"]:
            if has_profanity(t["text"]) or is_rude(t["text"], lang):
                errs.append(f"title '{t['text']}' contains swearing or a rude word")
            if g := other(t["text"]):
                errs.append(f"title '{t['text']}' names {g}, but this clip is from {topic or 'another game'}")
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
                                                problems=problems, n_draft=n_draft, punchy=punchy,
                                                keywords=keywords, vocab=vocab, facts=facts, game=game)
        d = model.json(system, prompt, draft_schema(n_draft, punchy), temperature=temperature, check=script_check,
                       soft=draft_soft, num_predict=900)
        d.pop("_soft_errors", None)
        drafts = _polish_all(d["titles"], lang, glossary, punchy, keywords)
        suspects = {i + 1: ws for i, t in enumerate(drafts)
                    if (ws := lexicon.unknown_words(t["text"], lang, glossary.allowed))}

        proof = model.json(PROOF_SYSTEM, proof_prompt(
            lang_label=lang_label, lang=lang, what_happens=what_happens, clip_lines=clip_lines,
            glossary=glossary, titles=drafts, suspects=suspects, hook_text=hook_text, cover_text=cover_text,
            punchy=punchy), PROOF_SCHEMA, temperature=0.2, num_predict=900)
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
            if punchy and not _end_emoji(new) and _end_emoji(t["text"]):
                new = f"{new} {_end_emoji(t['text'])}"  # proofreaders like to drop emojis
            polished = _polish_all([{**t, "text": new}], lang, glossary, punchy, keywords)
            if not polished:
                continue
            final = polished[0]
            if final["text"] != t["text"]:
                checks["fixed"].append([t["text"], final["text"]])
            reason = None
            unknown = lexicon.unknown_words(final["text"], lang, glossary.allowed)
            plain = lexicon.strip_emoji(final["text"])
            if unknown:
                reason = "unknown words: " + ", ".join(unknown)
            elif has_profanity(final["text"]) or is_rude(final["text"], lang):
                reason = "swearing or rude word"
            elif g := other(final["text"]):
                reason = f"not allowed: {g}"
            elif any(too_similar(final["text"], e, phrases=False) for e in example_texts):
                reason = "copies an example title"
            elif len(plain) > 80 or (punchy and lang not in ("zh", "ja") and len(plain) > 70):
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

    titles = pick(pool, slang={w.casefold() for w in glossary.streamer_words}, punchy=punchy, lang=lang) if pool else []
    hook, _f = lexicon.polish(glossary.canonicalize(hook_text), lang, keep=glossary.keep_case,
                              protected=glossary.allowed)
    max_hook = 5 if punchy else 6
    if (lexicon.unknown_words(hook, lang, glossary.allowed) or has_profanity(hook) or is_rude(hook, lang)
            or other(hook)):
        short = [t["text"] for t in titles if len(t["text"].split()) <= max_hook]
        checks["rejected"].append({"text": hook, "reason": "hook text: unknown words, swearing or another game"})
        hook = short[0] if short else ""
    cover, _f = lexicon.polish(glossary.canonicalize(cover_text), lang, keep=glossary.keep_case,
                               protected=glossary.allowed)
    if has_profanity(cover) or is_rude(cover, lang) or other(cover):
        cover = ""
    if punchy:
        hook = style_title(hook, lang, keywords, keep=glossary.keep_case)
        cover = style_title(_short_text(cover, 4), lang, keywords, keep=glossary.keep_case)
    checks["variety"] = variety_problems(titles, punchy=punchy, lang=lang)
    return {"titles": titles, "hook_text": _short_text(hook, max_hook), "cover_text": lexicon.strip_emoji(cover),
            "checks": checks}
