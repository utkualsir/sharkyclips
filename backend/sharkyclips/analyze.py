"""LLM analysis of highlight candidates (`python cli.py analyze <id>`).

Per candidate:
  1. judge      one structured LLM call: scores, what happens, cut changes, hashtags, hook
                text, cover prompt (cache/llm/judge_*.json)
  2. titles     titles.write(): few-shot draft + local checks + proofread pass + variety pick
                (cache/llm/titles_*.json; the key includes the example titles, the creator's
                liked titles and the glossary, so likes change the next run's titles)
  3. translate  subtitles, when the output language differs from the spoken one
The titles prompt starts with the same text as the judge prompt, so Ollama reuses its prompt
cache. Results are cached per candidate, so re-running is instant and an interrupted run resumes.

Written into highlights.json, per candidate:
  publish  viral_score + label + sub-scores, 6 titles, hashtags, cover prompt, hook text
  llm      what happens, self-contained?, funny/exciting/useful, game/topic, boundary change
  translations  {lang: [{start, end, text}]}  (subtitle lines, segment timing kept)
start/end are refined (+-10 s, snapped to word boundaries) unless --no-refine.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Callable

from . import config, languages
from . import titles as titles_mod
from .errors import SharkyClipsError
from .highlights.modes import get_mode
from .project import Project, read_json, write_json_atomic
from .textutil import NO_SPACE_LANGS, sentences, words_between
from .ui import console

PROMPT_VERSION = 8
MAX_SHIFT = 10.0
# Short-form sweet spot per mode (seconds): full length-fit score inside this range.
SWEET_SPOT = {"gaming": (18, 40), "study": (30, 55), "music": (15, 30)}

REASON_TEXT = {
    "loudness_spike": "sudden loud moment", "keyword": "reaction word", "laughter": "laughter",
    "shouting": "shouting", "cheering": "cheering", "fast_speech": "excited fast talking",
    "pause_then_burst": "silence then outburst", "steady_explanation": "calm explanation",
    "chorus": "music chorus", "drop": "music drop", "chat_spike": "chat exploded",
    "chat_reactions": "chat spammed reactions", "llm_explanation": "self-contained explanation",
}
# Game events read from the game screen (game signal). These are facts, not guesses.
GAME_EVENT_TEXT = {
    "lol_pentakill": "Pentakill", "lol_quadrakill": "Quadra kill", "lol_triplekill": "Triple kill",
    "lol_doublekill": "Double kill", "lol_kill": "kill", "lol_assist": "assist", "lol_death": "the streamer died",
    "lol_first_blood": "First blood", "lol_shutdown": "Shutdown", "lol_ace": "Ace (whole enemy team dead)",
    "lol_baron_steal": "Baron steal", "lol_dragon_steal": "Dragon steal", "lol_baron": "Baron secured",
    "lol_dragon": "Dragon secured", "lol_victory": "Victory screen", "lol_defeat": "Defeat screen",
    "df_multikill": "{n} kills in a row (multikill)", "df_kill": "kill", "df_revenge": "revenge kill",
    "df_knock": "knocked an enemy down", "df_revive": "revived a teammate", "df_assist": "assist",
    "df_death": "the streamer died", "df_extracted": "extracted successfully", "df_extract_failed": "extraction failed",
}


def game_events_text(c: dict) -> str:
    """'Game events (read from the game screen): Quadra kill with Yasuo at +12s; ...'"""
    out = []
    for r in sorted(c.get("reasons", []), key=lambda r: r["t"]):
        tmpl = GAME_EVENT_TEXT.get(r["code"])
        if not tmpl or r["code"] in ("lol_assist", "df_assist"):
            continue
        if r["code"] == "df_multikill":
            txt = tmpl.format(n=r.get("value") or "several")
        elif r["code"].startswith("lol_") and r.get("value") and r["code"] not in ("lol_victory", "lol_defeat",
                                                                                     "lol_death"):
            txt = f"{tmpl} with {r['value']}"
        else:
            txt = tmpl
        out.append(f"{txt} at {r['t'] - c['start']:+.0f}s")
    return "; ".join(out)

COVER_STYLE = ("vertical 9:16 thumbnail, cinematic and dramatic, high contrast, deep navy and gold "
               "color grade, sharp focus on the subject, bold short overlay text \"{text}\", "
               "no logos, no watermarks, no UI elements")

SYSTEM = (
    "You are a senior short-form video editor (YouTube Shorts, TikTok, Reels) who also writes "
    "viral titles. You judge stream and video moments honestly and strictly: most clips are "
    "average (scores 40-60), good ones 60-75, and only rare, truly exceptional moments get 80+. "
    "Base everything only on what the CLIP transcript lines and signals show; the video title only "
    "tells you the game/topic, never what happens in this clip. Never invent events. "
    "Titles, hashtags and on-screen texts must be advertiser-friendly: no swearing, slurs or "
    "insults, even if the streamer swears. Answer only with JSON that matches the schema."
)

# Word roots that make a title/hashtag/hook not advertiser-friendly. Matched against
# has_profanity()'s normalized text: lowercase, accents removed (ş->s, ç->c), dotless ı kept.
PROFANITY = re.compile(
    r"\b(?:s[i1]k(?:im|iyim|eyim|ey[iı]m|tir|tim|t[iı]g|is|ik|er|me|ecek)\w*|amk|aq|am[iı]n[aı]\w*|ann?en[iı]n am\w*|orospu\w*|"
    r"pic\b|pici\w*|yarra\w*|kaha?pe\w*|anas[iı]n[iı]|fuck\w*|shit\w*|bitch\w*|cunt|dick\w*|asshole|"
    r"бля\w*|сука|сук[иу]\w*|хуй\w*|пизд\w*|scheisse|fick\w*|kurva\w*|bazdmeg)\b")


# Roots that are never innocent, even glued into a name ("Deepfuck", "#ShitShow").
EMBEDDED_PROFANITY = re.compile(r"fuck|shit|bitch|motherf|orospu|siktir|yarrak|pussy|cunt")
# The clip's own timing in the prompt ("+7s") must never reach a title or description.
TIMESTAMP_RE = re.compile(r"[+＋]\s?\d+(?:[.,]\d+)?\s?(?:s|sn|saniye\w*|sec\w*)?\b|\b\d+[.,]\d+\s?(?:s|sn|saniye\w*|sec\w*)\b", re.I)


def has_profanity(text: str) -> bool:
    # Not re.I: it would treat Turkish dotless ı as i ("sıkıştı" = "got stuck" is fine).
    t = "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))
    t = t.replace("ß", "ss")
    return bool(PROFANITY.search(t) or EMBEDDED_PROFANITY.search(t))


def has_timestamp(text: str) -> bool:
    return bool(TIMESTAMP_RE.search(text or ""))
STOPWORDS = {"the", "and", "this", "that", "with", "for", "bir", "bu", "ve", "ile", "için", "çok",
             "abi", "kanka", "lan", "ya", "der", "die", "das", "und", "это", "как", "что"}


def _schema(lang_name: str) -> dict:
    s100 = {"type": "integer", "minimum": 0, "maximum": 100}
    s10 = {"type": "integer", "minimum": 0, "maximum": 10}
    return {
        "type": "object",
        "properties": {
            "game_or_topic": {"type": "string", "minLength": 2, "maxLength": 50},
            "what_happens": {"type": "string", "minLength": 10, "maxLength": 400},
            "self_contained": {"type": "boolean"},
            "moment_type": {"type": "string", "enum": ["funny", "exciting", "skill", "fail", "emotional",
                                                       "useful", "informative", "other"]},
            "funny": s10, "exciting": s10, "useful": s10,
            "hook_score": s100, "retention_score": s100, "trend_fit_score": s100,
            "start_shift_s": {"type": "number", "minimum": -MAX_SHIFT, "maximum": MAX_SHIFT},
            "end_shift_s": {"type": "number", "minimum": -MAX_SHIFT, "maximum": MAX_SHIFT},
            "hashtags": {"type": "array", "minItems": 6, "maxItems": 10,
                         "items": {"type": "string", "minLength": 2, "maxLength": 40}},
            "hook_text": {"type": "string", "minLength": 2, "maxLength": 60},
            "cover_scene": {"type": "string", "minLength": 10, "maxLength": 350},
            "cover_text": {"type": "string", "minLength": 1, "maxLength": 32},
        },
        "required": ["game_or_topic", "what_happens", "self_contained", "moment_type", "funny", "exciting",
                     "useful", "hook_score", "retention_score", "trend_fit_score", "start_shift_s",
                     "end_shift_s", "hashtags", "hook_text", "cover_scene", "cover_text"],
    }


TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {
        "type": "object",
        "properties": {"i": {"type": "integer", "minimum": 1}, "text": {"type": "string"}},
        "required": ["i", "text"]}}},
    "required": ["lines"],
}

# Characters that prove a text is written in the right script.
SCRIPT = {"ar": re.compile(r"[؀-ۿ]"), "ru": re.compile(r"[Ѐ-ӿ]"),
          "zh": re.compile(r"[一-鿿]")}


# ------------------------------------------------------------------ helpers


def lang_name(code: str) -> str:
    lang = languages.get(code)
    return f"{lang.english_name} ({lang.native_name})" if lang else code


def _words_key(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.casefold()) if len(w) > 2}


def _bigrams(text: str) -> set[tuple[str, str]]:
    w = [x for x in re.findall(r"\w+", text.casefold()) if x not in STOPWORDS]
    return set(zip(w, w[1:]))


def too_similar(a: str, b: str, phrases: bool = True) -> bool:
    """Same idea twice: big word overlap, same opening, or (phrases=True) a shared two-word phrase."""
    wa, wb = _words_key(a), _words_key(b)
    if not wa or not wb:
        return a.casefold() == b.casefold()
    jacc = len(wa & wb) / len(wa | wb)
    first = re.findall(r"\w+", a.casefold())[:3] == re.findall(r"\w+", b.casefold())[:3]
    return jacc >= 0.5 or first or (phrases and bool(_bigrams(a) & _bigrams(b)))


def _name_key(text: str) -> str:
    return re.sub(r"[^\w]", "", text, flags=re.UNICODE).casefold()


def clean_hashtags(tags: list[str], topic: str, exclude: list[str] | None = None) -> list[str]:
    """exclude: names that must not become hashtags (the channel), even if the model wrote them."""
    out: list[str] = []
    banned = {_name_key(x) for x in exclude or [] if len(_name_key(x)) >= 3}

    def add(tag: str) -> None:
        tag = re.sub(r"[^\w]", "", tag.replace("#", "").strip(), flags=re.UNICODE)
        if tag and tag.casefold() not in {t[1:].casefold() for t in out} and tag.casefold() not in banned:
            out.append("#" + tag)

    add("shorts")
    topic_tag = re.sub(r"[^\w]", "", topic.split("(")[0], flags=re.UNICODE)
    if 2 < len(topic_tag) <= 30:
        add(topic_tag)
    for t in tags:
        add(t)
    return out[:10]


def clip_tags(mode: str, game: dict, facts: dict, moment: str | None, lang: str, llm_hashtags: list[str],
              topic: str, exclude: list[str]) -> tuple[list[str], list[str]]:
    """(hashtags, YouTube tags) of one clip. Gaming: built from the game's bank, the clip's facts
    and the channel's own tags; the model's hashtags only fill gaps and must be real words about
    this game. Other modes: the channel's tags + the model's hashtags."""
    from . import youtube
    from .edit import brand
    from .titles import banks

    channel = brand.channel_hashtags()
    names = brand.channel_names()
    if mode == "gaming":
        bank = banks.get(game["id"])
        return (banks.build_hashtags(bank, facts, moment, lang, channel=channel, llm=llm_hashtags, exclude=exclude),
                banks.build_tags(bank, facts, moment, lang, channel=names))
    keep = [h for h in clean_hashtags(llm_hashtags, topic, exclude=exclude)]
    out = list(channel) + [h for h in keep if h.casefold() not in {c.casefold() for c in channel}]
    hashtags = out[:max(8, len(channel) + 3)]
    tags = [h.lstrip("#") for h in keep if h.lower() != "#shorts"] + [topic] + names + [mode, "shorts"]
    return hashtags, youtube.clean_tags([t for t in tags if t])[:20]


def length_fit(duration: float, mode: str) -> int:
    lo, hi = SWEET_SPOT.get(mode, (18, 45))
    if lo <= duration <= hi:
        return 100
    if duration < lo:
        return max(20, int(100 - (lo - duration) * 6))
    return max(20, int(100 - (duration - hi) * 3))


def viral_label(score: int) -> str:
    if score >= 85:
        return "very_high"
    if score >= 65:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def calibrate(x: float) -> int:
    """Local 7-9B models rate almost every clip 70-85; spread that range out (75 -> 50)."""
    return int(round(min(100, max(0, 50 + (x - 75) * 2.0))))


def calibrate_quality(x: int) -> int:
    """funny/exciting/useful 0-10, usually 6-9 from the model -> 0-100 (5 -> 0, 10 -> 100)."""
    return int(min(100, max(0, (x - 5) * 20)))


def viral_score(cand: dict, j: dict, length_score: int) -> int:
    """Signals + LLM judgment -> 0..100.

    signal: half relative (best clip of the video = 100), half absolute hype (0.3 raw = 100),
    so a quiet video's best clip doesn't automatically look viral."""
    raw = cand.get("hype_raw", 0)
    absolute = min(100.0, max(0.0, (raw - 0.15) / 0.45 * 100))  # calm talk ~0.15, wild stream ~0.6
    signal = 0.4 * cand["hype_score"] + 0.6 * absolute
    quality = calibrate_quality(max(j["funny"], j["exciting"], j["useful"]))
    score = (0.22 * signal + 0.22 * calibrate(j["hook_score"]) + 0.22 * calibrate(j["retention_score"])
             + 0.10 * calibrate(j["trend_fit_score"]) + 0.06 * length_score + 0.18 * quality)
    if not j["self_contained"]:
        score *= 0.85
    return int(round(min(100, max(0, score))))


def snap_boundaries(transcript: dict, start: float, end: float, lo: float, hi: float,
                    min_len: float, max_len: float) -> tuple[float, float]:
    """Move start to the nearest word start and end to the nearest word end, inside [lo, hi]."""
    # The AI's shift may point outside the allowed range (before 0 s, into the neighbour clip)
    start, end = min(max(start, lo), hi), min(max(end, lo), hi)
    words = words_between(transcript, lo, hi)
    if words:
        starts = [w["start"] for w in words]
        ends = [w["end"] for w in words]
        s = min(starts, key=lambda x: abs(x - start))
        e = min(ends, key=lambda x: abs(x - end))
        if abs(s - start) <= 2.5:
            start = max(lo, s - 0.15)
        if abs(e - end) <= 2.5:
            end = min(hi, e + 0.25)
    if end - start < min_len:
        end = min(hi, start + min_len)
    if end - start > max_len:
        end = start + max_len
    return round(max(0.0, start), 2), round(end, 2)


def _cache_key(model: str, out_lang: str, c: dict, mode: str, transcript: dict, extra: str = "") -> str:
    """Stable per original cut: c["text"] is rewritten after refining, so the words are taken
    from the transcript for the original start/end instead."""
    base = c.get("llm", {}).get("original") or {"start": c["start"], "end": c["end"]}
    words = " ".join(x["text"] for x in sentences(transcript, base["start"], base["end"]))
    payload = [PROMPT_VERSION, model, out_lang, mode, round(base["start"], 1), round(base["end"], 1),
               hashlib.sha1(words.encode()).hexdigest()[:10], extra]
    game = sorted(f"{r['code']}:{r.get('value') or ''}" for r in c.get("reasons", []) if r["code"] in GAME_EVENT_TEXT)
    if game:  # new game events -> new judgement and titles (other projects keep their cache)
        payload.append(game)
    return hashlib.sha1(json.dumps(payload).encode()).hexdigest()[:20]


# ------------------------------------------------------------------ prompts


def _context(transcript: dict, start: float, end: float) -> str:
    lines = sentences(transcript, max(0, start - 25), end + 15)
    out = []
    for x in lines:
        mid = (x["start"] + x["end"]) / 2
        mark = "CLIP" if start <= mid <= end else "ctx "
        out.append(f"[{mark} {x['start'] - start:+6.1f}s] {x['text']}")
    return "\n".join(out) or "(no speech)"


def _signals_text(c: dict) -> str:
    sig = ", ".join(f"{k} {int(v * 100)}%" for k, v in sorted(c.get("signal_scores", {}).items(),
                                                              key=lambda kv: -kv[1]))
    seen, reasons = set(), []
    for r in c.get("reasons", []):
        if r["code"] in GAME_EVENT_TEXT:
            continue  # listed separately below, as facts
        txt = REASON_TEXT.get(r["code"], r["code"]) + (f" \"{r['value']}\"" if r.get("value") else "")
        if txt not in seen:
            seen.add(txt)
            reasons.append(f"{txt} at {r['t'] - c['start']:+.0f}s")
    out = f"Signal strengths: {sig}\nDetected: {'; '.join(reasons[:8]) or 'nothing specific'}"
    game = game_events_text(c)
    if game:
        out += (f"\nGame events (read from the game screen, reliable; use them in what_happens and titles): "
                f"{game}")
    return out


def game_lines(game: dict | None, facts: dict | None = None) -> str:
    """The project's ONE game (never guessed per clip) + this clip's facts, for every prompt."""
    if not game:
        return ""
    from .titles import banks

    if game.get("known"):
        out = (f"Game: {game['name']} (the whole video is {game['name']}; every clip is from this game. "
               "Never name or hint at any other game.)")
    else:
        out = ("Game: unknown. Never name or guess a game, a game's characters, maps or modes; "
               "write about the moment itself.")
    ft = banks.facts_text(facts or {})
    if ft:
        out += f"\nClip facts (from the game screen and the clip's words, reliable): {ft}"
    return out


def _context_block(meta: dict, mode: str, c: dict, transcript: dict, game: dict | None = None,
                   facts: dict | None = None) -> str:
    """Shared start of the judge and the titles prompt (Ollama reuses the cached prefix)."""
    spoken = transcript.get("language") or "unknown"
    gl = game_lines(game, facts) if mode == "gaming" else ""
    return f"""Video title: {meta.get('title', '')}
Channel: {(meta.get('source') or {}).get('uploader') or 'unknown'}
Content type: {mode}{chr(10) + gl if gl else ''}
Spoken language: {lang_name(spoken)}
Clip: {c['duration']:.1f} s long (hype rank #{c['rank']}, hype {c['hype_score']}/100)
{_signals_text(c)}

Transcript around the clip (times are relative to the clip start; CLIP lines are inside the clip, ctx lines are context before/after):
{_context(transcript, c['start'], c['end'])}"""


def _prompt(meta: dict, mode: str, c: dict, transcript: dict, out_lang: str, game: dict | None = None,
            facts: dict | None = None) -> str:
    if mode == "gaming" and game:
        topic = (f'1. game_or_topic: exactly "{game["name"]}".' if game.get("known")
                 else '1. game_or_topic: exactly "Gaming" (the game is unknown: never guess it).')
    else:
        topic = '1. game_or_topic: the game or topic, from the video title and transcript (e.g. "Delta Force").'
    return _context_block(meta, mode, c, transcript, game, facts) + f"""

TASK: judge this clip and write its publish package.
{topic}
2. what_happens (English): what actually happens in the CLIP lines, 1-2 sentences. Not the whole video. Mention names, places and items only as they are said.
3. Judge it: self_contained (understandable without the rest of the video?), moment_type, funny/exciting/useful 0-10.
4. hook_score: how strong the first 3 seconds are. retention_score: will people watch to the end. trend_fit_score: how well it fits what does well on Shorts/TikTok for this game/topic right now. Use the full 0-100 range honestly.
5. start_shift_s / end_shift_s (-10..10): move the start earlier (negative) to include needed setup, or later to cut dead air; move the end so the clip ends right after the payoff/reaction. 0 if the cut is already good.
6. hashtags: 6-10 hashtags about what happens in THIS clip (moment, event, character, map); mix {lang_name(out_lang)} and universal English tags. Never another game, no channel or person names, no #viral / #fyp.
7. hook_text: 2-4 punchy words in {lang_name(out_lang)}, correct spelling, shown on screen in the first seconds to make people stay; one key word may be in CAPITALS. About this clip, no swearing, no emojis.
8. cover_scene (English): describe one striking image for the thumbnail based on what really happens (subject, action, emotion, setting). cover_text: 2-4 punchy words in {lang_name(out_lang)} for the thumbnail, same style as the hook.
"""


DESCRIPTION_VERSION = 4  # 1.2.26: no clip times; 1.2.25: game-aware, ends with a question
DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {"description": {"type": "string", "minLength": 40, "maxLength": 480}},
    "required": ["description"],
}


def _sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?…。！？؟])\s*", text.strip()) if len(s.strip()) > 2])


def _channel_names(meta: dict) -> list[str]:
    src = meta.get("source") or {}
    return [n for n in (src.get("uploader"), src.get("channel")) if n]


# Turkish written-news register ("düşmektedir", "başarmıştır") sounds wrong in a creator's own words.
TR_FORMAL = re.compile(r"\w+(?:mekte|makta)(?:dır|dir|dırlar|dirler)\b|\w+(?:mış|miş|muş|müş)(?:tır|tir|tur|tür)\b", re.I)


DESCRIPTION_QUESTIONS = {
    "tr": "\"Sen olsan ne yapardın?\", \"Sizce kim haklıydı?\"",
    "en": "\"What would you have done?\", \"Who was right here?\"",
    "de": "\"Was hättest du gemacht?\"", "hu": "\"Te mit csináltál volna?\"", "ru": "\"А ты бы что сделал?\"",
    "ar": "\"ماذا كنت ستفعل؟\"", "zh": "\"换你会怎么做？\"",
}


def _description_prompt(meta: dict, mode: str, c: dict, transcript: dict, out_lang: str, j: dict,
                        title: str, terms: list[str], game: dict | None = None, facts: dict | None = None) -> str:
    names = ", ".join(terms[:20]) or "none"
    tone = {"tr": " Use casual spoken Turkish (\"indirdim\", \"bakın ne oldu\", \"chat çıldırdı\"), never news style like \"-mektedir\" or \"-mıştır\"."}
    gaming = mode == "gaming"
    if gaming:
        where = (f"Write it like a streamer who plays {game['name']}: use the game's own words where they fit "
                 "(only names from the clip facts or the list below)." if game and game.get("known")
                 else "The game is unknown: never name or guess a game.")
        body = (f"- 2-3 short, lively sentences in the creator's own voice (first person: I / we), natural streamer tone: "
                f"what happens in THIS clip and why it's worth watching. {where}\n"
                f"- The LAST sentence is a short question that makes viewers comment, like {DESCRIPTION_QUESTIONS.get(out_lang, DESCRIPTION_QUESTIONS['en'])}.")
    else:
        body = ("- 2-3 short, natural sentences in the creator's own voice (first person: I / we), casual like a streamer "
                "talking to viewers: what happens and why it's worth watching. The last sentence may ask viewers a "
                "question or invite a comment.")
    return _context_block(meta, mode, c, transcript, game, facts) + f"""

What happens in the clip: {j['what_happens']}
Chosen title: {title}

TASK: write the YouTube description of this clip in {lang_name(out_lang)}.
{body}{tone.get(out_lang, "")}
- Never mention the channel or the creator by name, and never describe the creator in the third person.
- Only what the CLIP lines and game events show; never invent events, scores or names. Don't mention swearing.
- Spell these names exactly like this: {names}
- Don't repeat the title word for word. No hashtags, emojis, links or ALL CAPS (the hashtags and links are added later).
- Never mention the times from the transcript list (like "+7s" or "at 14 seconds"): viewers don't see them.
"""


def _description_soft_checker(out_lang: str, channel: list[str], question: bool = False) -> Callable[[dict], list[str]]:
    """Style problems: asked to be fixed, but an answer that still has them is kept."""
    keys = [_name_key(n) for n in channel if len(_name_key(n)) >= 3]

    def check(d: dict) -> list[str]:
        text = d.get("description", "")
        errs = []
        flat = _name_key(text)
        if any(k in flat for k in keys):
            errs.append("don't name the channel/creator: write in the first person (I / we)")
        if out_lang == "tr" and TR_FORMAL.search(text):
            errs.append("write casual spoken Turkish, not news style (-mektedir / -mıştır)")
        if question and not text.rstrip().endswith(titles_mod.QUESTION_END):
            errs.append("end with a short question to the viewers (the last sentence ends with '?')")
        return errs

    return check


def _description_checker(out_lang: str, game_id: str | None = None) -> Callable[[dict], list[str]]:
    script = SCRIPT.get(out_lang)

    def check(d: dict) -> list[str]:
        from .titles import banks

        text = d.get("description", "")
        errs = []
        if has_profanity(text):  # hard: a description with swearing is never used
            errs.append("no swearing or insults in the description, even if the streamer swears")
        if game_id and (other := banks.other_game(text, game_id)):
            errs.append(f"never mention {other}: this clip is not from that game")
        if has_timestamp(text):
            errs.append('never mention the clip times like "+7s" or "5.7 seconds": viewers don\'t see them')
        if "#" in text or "http" in text:
            errs.append("no hashtags or links in the description")
        n = _sentence_count(text)
        if out_lang not in NO_SPACE_LANGS and not 2 <= n <= 4:
            errs.append(f"write 2-3 sentences (you wrote {n})")
        if script and not script.search(text):
            errs.append(f"the description must be written in {lang_name(out_lang)}")
        return errs

    return check


def write_description(model, meta: dict, mode: str, c: dict, transcript: dict, out_lang: str, j: dict,
                      title: str, gl, game: dict | None = None, facts: dict | None = None) -> str:
    """The model's 2-3 sentences (finish_description() cleans them and adds the hashtags)."""
    gaming = mode == "gaming"
    d = model.json(SYSTEM, _description_prompt(meta, mode, c, transcript, out_lang, j, title,
                                               list(gl.terms) if gl else [], game, facts),
                   DESCRIPTION_SCHEMA, temperature=0.65 if gaming else 0.6,
                   check=_description_checker(out_lang, (game or {}).get("id") if gaming else None),
                   soft=_description_soft_checker(out_lang, _channel_names(meta), question=gaming), num_predict=700)
    return d["description"]


def finish_description(text: str, out_lang: str, gl, hashtags: list[str], game_id: str | None = None) -> str:
    """Spelling fixes + the hashtags at the end (YouTube shows the first three above the title).
    game_id: sentences that name another game are dropped."""
    from .titles import banks, lexicon

    out = lexicon.strip_emoji(text).strip().strip("\"'“”«»")
    out = re.sub(r"\s*#\w+", "", out).strip()
    if game_id and banks.other_game(out, game_id):
        parts = re.split(r"(?<=[.!?…。！？؟])\s+", out)
        out = " ".join(p for p in parts if not banks.other_game(p, game_id)).strip()
    if gl is not None:
        out = gl.canonicalize(out)
    out, _f = lexicon.repair_diacritics(out, out_lang, gl.allowed if gl else frozenset())
    if out_lang == "tr":
        out, _f = lexicon.fix_tr_question_particle(out)
    out = re.sub(r"\s+([?!.,…])", r"\1", out)
    if has_profanity(out):
        out = ""
    tags = " ".join(hashtags)
    return f"{out}\n\n{tags}".strip() if out else tags


def _script_ok(out_lang: str, texts: list[str], need: int) -> bool:
    script = SCRIPT.get(out_lang)
    return not script or sum(bool(script.search(t)) for t in texts) >= need


def _hard_checker(out_lang: str) -> Callable[[dict], list[str]]:
    """Problems that make an answer unusable: wrong language/script, too long hook."""
    script = SCRIPT.get(out_lang)

    def check(d: dict) -> list[str]:
        errs = []
        if len(d.get("hook_text", "").split()) > 8:
            errs.append("hook_text must be at most 6 words")
        if script:
            for field in ("hook_text", "cover_text"):
                if not script.search(d.get(field, "")):
                    errs.append(f"{field} must be written in {lang_name(out_lang)}")
        return errs

    return check


def _titles_script_checker(out_lang: str) -> Callable[[dict], list[str]]:
    def check(d: dict) -> list[str]:
        texts = [t["text"] for t in d.get("titles", [])]
        if not _script_ok(out_lang, texts, max(1, len(texts) - 1)):
            return [f"titles must be written in {lang_name(out_lang)}"]
        return []

    return check


def _checker(out_lang: str) -> Callable[[dict], list[str]]:
    """Soft problems: swearing (fixed by dropping it if retries run out)."""

    def check(d: dict) -> list[str]:
        errs = []
        for field, texts in (("hashtags", d.get("hashtags", [])), ("hook_text", [d.get("hook_text", "")]),
                             ("cover_text", [d.get("cover_text", "")])):
            bad = [t for t in texts if has_profanity(t)]
            if bad:
                errs.append(f"{field} contains swearing, rewrite without it: {bad[:3]}")
        return errs

    return check


# ------------------------------------------------------------------ translation


def translate_lines(model, lines: list[dict], src: str, dst: str, context: str) -> list[dict]:
    listing = "\n".join(f"{i + 1}. {x['text']}" for i, x in enumerate(lines))
    prompt = (f"Translate these subtitle lines of a video clip from {lang_name(src)} to {lang_name(dst)}.\n"
              f"Context: {context}\n"
              "Keep the meaning, slang and energy; keep each line short and natural for on-screen "
              "subtitles; keep names and game terms. Return exactly one translated line per input "
              f"line with the same number i.\n\n{listing}")

    def check(d: dict) -> list[str]:
        nums = [x["i"] for x in d["lines"]]
        if nums != list(range(1, len(lines) + 1)):
            return [f"return exactly {len(lines)} lines numbered 1..{len(lines)} in order"]
        empty = [x["i"] for x in d["lines"] if not x["text"].strip()]
        return [f"line {i} is empty" for i in empty]

    data = model.json("You are a professional subtitle translator. Answer only with JSON.", prompt,
                      TRANSLATE_SCHEMA, temperature=0.2, check=check, num_predict=1500)
    return [{"start": x["start"], "end": x["end"], "text": y["text"].strip()}
            for x, y in zip(lines, data["lines"])]


# ------------------------------------------------------------------ main


def _forbidden(gid: str | None) -> Callable[[str], str | None]:
    """Why a title / hook / cover text can't be used: another game's name, or a clip time ("+7s")."""
    from .titles import banks

    def check(text: str) -> str | None:
        if gid and (g := banks.other_game(text, gid)):
            return g
        return "a clip time" if has_timestamp(text) else None

    return check


def _top_up(new: list[dict], old: list[str], lang: str, forbidden, n: int = 4) -> list[dict]:
    """Metadata-only run: too few new titles survived -> add the clip's old titles that pass today's checks."""
    out = list(new)
    for t in old:
        if len(out) >= n:
            break
        if (t and not has_profanity(t) and not titles_mod.is_rude(t, lang) and not forbidden(t)
                and not any(too_similar(t, x["text"], phrases=False) for x in out)):
            out.append({"style": "story", "text": t})
    return out


def _judge_from_saved(c: dict) -> dict | None:
    """A clip's earlier judgement (highlights.json), for a metadata-only run without the judge cache."""
    info, pub = c.get("llm") or {}, c.get("publish") or {}
    if not info.get("what_happens"):
        return None
    return {"game_or_topic": info.get("game_or_topic") or "", "what_happens": info["what_happens"],
            "moment_type": info.get("moment_type") or "other", "hashtags": list(pub.get("hashtags") or []),
            "hook_text": pub.get("hook_text") or "", "cover_text": pub.get("cover_text") or "",
            "cover_scene": "", "start_shift_s": info.get("start_shift_s") or 0, "end_shift_s": info.get("end_shift_s") or 0}


def analyze_project(project: Project, out_lang: str | None = None, force: bool = False,
                    refine: bool = True, ranks: list[int] | None = None, translate: bool = True,
                    on_progress: Callable[[int, int, dict], None] | None = None,
                    meta_only: bool = False) -> dict:
    """meta_only=True: only titles, description, hashtags, tags and cover text are written again
    (cuts, scores, hook texts and subtitles stay, so rendered clips stay valid)."""
    from . import llm
    from .titles import banks

    hl_path = project.dir / "highlights.json"
    if not hl_path.is_file():
        raise SharkyClipsError("No highlights yet for this project.",
                               f"Run: python cli.py highlights {project.id}")
    if not project.transcript_path.is_file():
        raise SharkyClipsError("No transcript yet.", f"Run: python cli.py transcribe {project.id}")
    hl = read_json(hl_path)
    if meta_only:
        out_lang = out_lang or (hl.get("analysis") or {}).get("language")
    out_lang = languages.require(out_lang or config.get("output_language") or "tr").code
    transcript = project.load_transcript()
    meta = project.load_meta()
    mode = hl.get("mode") or meta.get("mode") or "gaming"
    preset = get_mode(mode)
    spoken = transcript.get("language")
    cands = sorted(hl["candidates"], key=lambda c: c["rank"])
    todo = [c for c in cands if ranks is None or c["rank"] in ranks]
    if meta_only:
        todo = [c for c in todo if (c.get("publish") or {}).get("available")]
    cache_dir = project.cache_dir / "llm"
    cache_dir.mkdir(parents=True, exist_ok=True)
    duration = float(hl.get("duration") or meta.get("duration") or 0)

    # ONE game for the whole project (override > HUD pick / detection > title + transcript)
    game = banks.project_game(project)
    bank = banks.get(game["id"])
    gid = game["id"] if mode == "gaming" else None
    game_terms = banks.glossary_terms(bank) if mode == "gaming" else []
    caps_words = banks.caps_words(bank) if mode == "gaming" else []

    t_start = time.perf_counter()
    timings = []
    failed: list[dict] = []
    used_titles: list[str] = []
    glossaries: dict = {}

    def glossary_for(topic: str):
        name = game["name"] if mode == "gaming" else (titles_mod.glossary.detect_game(meta.get("title", ""), topic) or "")
        if name not in glossaries:
            glossaries[name] = titles_mod.glossary.build(
                transcript, out_lang, meta.get("title", ""), topic,
                game=name if mode == "gaming" else None, game_terms=game_terms, extra_allowed=caps_words)
        return glossaries[name]

    style = titles_mod.style_digest(out_lang, mode, gid)
    fast = llm.fast_analysis()
    profile = "fast" if fast else "normal"
    gl = None
    gtag = f"{game['id']}:{banks.BANK_VERSION}" if mode == "gaming" else "-"
    with llm.lazy_session() as model:
        for i, c in enumerate(todo):
            t0 = time.perf_counter()
            calls0 = model.calls
            orig = c.get("llm", {}).get("original") or {"start": c["start"], "end": c["end"]}
            # always judge the original cut, so results don't drift between runs
            # (meta_only: on a copy, the clip keeps its refined cut)
            w = dict(c) if meta_only else c
            w["start"], w["end"] = orig["start"], orig["end"]
            w["duration"] = round(w["end"] - w["start"], 2)
            facts = banks.clip_facts(bank, w, transcript) if mode == "gaming" else {}
            key = _cache_key(model.model, out_lang, w, mode, transcript)
            cache_file = cache_dir / f"judge_{key}.json"
            cached = True
            try:
                if cache_file.is_file() and not force:
                    j = read_json(cache_file)
                elif meta_only:
                    j = _judge_from_saved(c)
                    if j is None:
                        raise SharkyClipsError("No earlier AI judgement for this clip.")
                else:
                    j = model.json(SYSTEM, _prompt(meta, mode, w, transcript, out_lang, game, facts),
                                   _schema(lang_name(out_lang)), check=_hard_checker(out_lang),
                                   soft=_checker(out_lang))
                    j = _repair(j)
                    write_json_atomic(cache_file, j)
                    cached = False
                j = dict(j)
                if mode == "gaming":  # the project's game, never the model's per-clip guess
                    j["game_or_topic"] = game["name"] or "Gaming"
                    j["what_happens"] = banks.scrub(j["what_happens"], gid)
                gl = glossary_for(j["game_or_topic"])
                gdig = hashlib.sha1(gl.digest().encode()).hexdigest()[:10]
                tkey = _cache_key(model.model, out_lang, w, mode, transcript,
                                  extra=f"titles:{style}:{gdig}:{gtag}" + (":fast" if fast else ""))
                tfile = cache_dir / f"titles_{tkey}.json"
                if tfile.is_file() and not force:
                    tw = read_json(tfile)
                else:
                    tw = _write_titles(model, meta, mode, w, transcript, out_lang, j, gl, used_titles, fast=fast,
                                       game=game, facts=facts, bank=bank)
                    write_json_atomic(tfile, tw)
                    cached = False
                if not cached:
                    record_speed(profile, model.model, time.perf_counter() - t0, "analysis")
                tw = titles_mod.refilter(tw, out_lang, has_profanity,
                                         forbidden=_forbidden(gid))
            except SharkyClipsError as exc:  # one bad clip must not stop the batch
                console.print(f"[yellow]#{c['rank']}: skipped ({exc.message[:160]})[/]")
                failed.append({"rank": c["rank"], "error": exc.message})
                continue
            used_titles += [t["text"] for t in tw["titles"]]

            if meta_only:
                start, end = c["start"], c["end"]
            else:
                # neighbours limit how far the boundaries may move (no overlaps)
                others = [o for o in cands if o is not c]
                lo = max([0.0] + [o["end"] for o in others if o["end"] <= orig["start"] + 0.01])
                hi = min([duration or orig["end"] + MAX_SHIFT] + [o["start"] for o in others
                                                                  if o["start"] >= orig["end"] - 0.01])
                lo, hi = max(lo, orig["start"] - MAX_SHIFT), min(hi, orig["end"] + MAX_SHIFT)
                if refine and not c.get("manual"):  # a hand-marked clip keeps its exact cut
                    start, end = snap_boundaries(
                        transcript, orig["start"] + j["start_shift_s"], orig["end"] + j["end_shift_s"],
                        lo, hi, preset.clip_min * 0.8, preset.clip_max)
                else:
                    start, end = orig["start"], orig["end"]
                c["start"], c["end"], c["duration"] = start, end, round(end - start, 2)
            lines = sentences(transcript, start, end)
            if not meta_only:
                joiner = "" if spoken in NO_SPACE_LANGS else " "
                c["text"] = joiner.join(x["text"] for x in lines) or c.get("text", "")

            hashtags, tags = clip_tags(mode, game, facts, j.get("moment_type"), out_lang, j.get("hashtags") or [],
                                       j["game_or_topic"], _channel_names(meta))
            cover_text = tw["cover_text"] or (j.get("cover_text") or "").strip()
            if meta_only:
                pub = c["publish"]
                if len(tw["titles"]) < 4:
                    tw = {**tw, "titles": _top_up(tw["titles"], pub.get("titles") or [], out_lang, _forbidden(gid))}
                old_cover = pub.get("cover_text") or ""
                pub.update({"titles": [t["text"] for t in tw["titles"]], "title_styles": [t["style"] for t in tw["titles"]],
                            "title_checks": tw.get("checks"), "hashtags": hashtags, "tags": tags,
                            "cover_text": cover_text or old_cover, "language": out_lang,
                            "metadata_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                if pub.get("cover_prompt") and old_cover and cover_text:
                    pub["cover_prompt"] = pub["cover_prompt"].replace(f'"{old_cover}"', f'"{cover_text}"')
                c.setdefault("llm", {})["game_or_topic"] = j["game_or_topic"]
                c["llm"]["what_happens"] = j["what_happens"]
            else:
                lf = length_fit(c["duration"], mode)
                score = viral_score(c, j, lf)
                c["publish"] = {
                    "available": True, "language": out_lang, "model": model.model,
                    "viral_score": score, "viral_label": viral_label(score),
                    "sub_scores": {"hook": calibrate(j["hook_score"]), "retention": calibrate(j["retention_score"]),
                                   "trend_fit": calibrate(j["trend_fit_score"]), "length_fit": lf},
                    "titles": [t["text"] for t in tw["titles"]],
                    "title_styles": [t["style"] for t in tw["titles"]],
                    "title_checks": tw.get("checks"),
                    "hashtags": hashtags, "tags": tags,
                    "hook_text": tw["hook_text"] or " ".join(j["hook_text"].split()[:5]),
                    "cover_text": cover_text,
                    "cover_prompt": f"{j['cover_scene'].strip().rstrip('.')}. " + COVER_STYLE.format(text=cover_text),
                    "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                c["llm"] = {"game_or_topic": j["game_or_topic"], "what_happens": j["what_happens"],
                            "self_contained": j["self_contained"], "moment_type": j["moment_type"],
                            "funny": j["funny"], "exciting": j["exciting"], "useful": j["useful"],
                            "start_shift_s": j["start_shift_s"], "end_shift_s": j["end_shift_s"],
                            "original": orig, "refined": (start, end) != (orig["start"], orig["end"])}
            pub = c["publish"]
            if mode == "gaming":
                pub["game"] = {"id": game["id"], "name": game["name"], "source": game["source"]}
                pub["facts"] = {"events": [e["label"] for e in facts.get("events", [])],
                                "terms": [t["term"] for t in facts.get("terms", [])]}

            # YouTube description (own cache: clips analyzed before 1.2.1 only need this call)
            dkey = _cache_key(model.model, out_lang, w, mode, transcript,
                              extra=f"desc{DESCRIPTION_VERSION}:{gdig}:{gtag}:{(pub['titles'] or [''])[0]}")
            dfile = cache_dir / f"desc_{dkey}.json"
            try:
                if dfile.is_file() and not force:
                    raw = read_json(dfile)["text"]
                else:
                    raw = write_description(model, meta, mode, w, transcript, out_lang, j,
                                            (pub["titles"] or [""])[0], gl, game=game, facts=facts)
                    write_json_atomic(dfile, {"text": raw})
                pub["description"] = finish_description(raw, out_lang, gl, pub["hashtags"], game_id=gid)
                if not pub["description"] or pub["description"].startswith("#"):  # no usable text
                    pub["description"] = None
                    dfile.unlink(missing_ok=True)  # try again on the next run
            except SharkyClipsError as exc:
                console.print(f"[yellow]#{c['rank']}: no description ({exc.message[:160]})[/]")
                pub["description"] = None

            # subtitles in the output language (segment timing kept)
            if translate and not meta_only and spoken and out_lang != spoken and lines:
                tkey = _cache_key(model.model, out_lang, c, mode, transcript, extra=f"tr:{start}:{end}")
                tfile = cache_dir / f"translate_{tkey}.json"
                if tfile.is_file() and not force:
                    tr_lines = read_json(tfile)
                else:
                    tr_lines = translate_lines(model, lines, spoken, out_lang, j["what_happens"])
                    write_json_atomic(tfile, tr_lines)
                c.setdefault("translations", {})[out_lang] = tr_lines

            prev = hl.get("analysis") or {}
            hl["analysis"] = {**(prev if meta_only else {}), "language": out_lang, "model": model.model, "fast": fast,
                              "prompt_version": PROMPT_VERSION,
                              "titles_version": titles_mod.TITLES_VERSION, "glossary": gl.terms if gl else [],
                              "game": {"id": game["id"], "name": game["name"], "source": game["source"]},
                              ("metadata_at" if meta_only else "analyzed_at"):
                                  datetime.now(timezone.utc).isoformat(timespec="seconds")}
            write_json_atomic(hl_path, hl)  # after every clip: an interrupted run keeps its work
            took = time.perf_counter() - t0
            timings.append({"rank": c["rank"], "seconds": round(took, 1), "cached": cached,
                            "llm_calls": model.calls - calls0})
            if on_progress:
                on_progress(i + 1, len(todo), c)
        stats = {"calls": model.calls, "retries": model.retries, "llm_seconds": round(model.seconds, 1),
                 "load_seconds": round(model.load_seconds or 0.0, 1), "model": model.model,
                 "tokens_per_second": round(model.tokens_per_second, 1)}

    if not meta_only:
        _sync_hype_curve(project, hl)
        meta = project.load_meta()
        meta["analysis"] = {"language": out_lang, "model": stats["model"], "count": len(todo)}
        project.save_meta(meta)
    done = {t["rank"] for t in timings}
    return {"language": out_lang, "candidates": [c for c in todo if c["rank"] in done],
            "failed": failed, "timings": timings, "game": game, **stats,
            "total_seconds": round(time.perf_counter() - t_start, 1)}


def _repair(j: dict) -> dict:
    """Answer with leftover soft problems: drop sweary tags / texts."""
    if not j.pop("_soft_errors", None):
        return j
    j["hashtags"] = [h for h in j["hashtags"] if not has_profanity(h)]
    if has_profanity(j["hook_text"]):
        j["hook_text"] = ""
    if has_profanity(j["cover_text"]):
        j["cover_text"] = ""
    return j


def _clip_lines(transcript: dict, c: dict) -> str:
    return "\n".join(x["text"] for x in sentences(transcript, c["start"], c["end"]))[:2500] or "(no speech)"


def _write_titles(model, meta: dict, mode: str, c: dict, transcript: dict, out_lang: str, j: dict, gl,
                  used_titles: list[str], avoid: list[str] | None = None, temperature: float = 0.75,
                  fast: bool = False, game: dict | None = None, facts: dict | None = None,
                  bank: dict | None = None) -> dict:
    from .titles import banks

    gaming = mode == "gaming"
    gid = (game or {}).get("id") if gaming else None
    words = banks.title_words(bank or banks.get(gid), facts or {}, out_lang) if gaming else {}
    return titles_mod.write(
        model, fast=fast, system=SYSTEM, context=_context_block(meta, mode, c, transcript, game, facts), lang=out_lang,
        lang_label=lang_name(out_lang), mode=mode, what_happens=j["what_happens"], topic=j["game_or_topic"],
        glossary=gl, used_titles=used_titles, hook_text=j.get("hook_text") or "",
        cover_text=j.get("cover_text") or "", clip_lines=_clip_lines(transcript, c),
        too_similar=too_similar, has_profanity=has_profanity, avoid=avoid, temperature=temperature,
        script_check=_titles_script_checker(out_lang),
        forbidden=_forbidden(gid),
        keywords=words.get("keywords"), vocab=words.get("vocab"), facts=banks.facts_text(facts or {}),
        punchy=gaming, game=gid)


def _sync_hype_curve(project: Project, hl: dict) -> None:
    """Keep the Hype Map's clip markers in line with refined boundaries."""
    path = project.dir / "hype_curve.json"
    if not path.is_file():
        return
    curve = read_json(path)
    by_rank = {c["rank"]: c for c in hl["candidates"]}
    for m in curve.get("candidates", []):
        c = by_rank.get(m["rank"])
        if c:
            m["start"], m["end"] = c["start"], c["end"]
    write_json_atomic(path, curve, compact=True)


def translate_clip(project: Project, cid: str, lang: str) -> list[dict]:
    """Subtitle lines of one clip in `lang` (export: SRT / VTT in any language). Cached in the
    candidate's translations, so a second export needs no LLM."""
    from . import llm

    lang = languages.require(lang).code
    hl_path = project.dir / "highlights.json"
    hl = read_json(hl_path)
    c = next((x for x in hl["candidates"] if x["id"] == cid), None)
    if c is None:
        raise SharkyClipsError("This clip doesn't exist any more.")
    have = (c.get("translations") or {}).get(lang)
    if have:
        return have
    transcript = project.load_transcript()
    spoken = transcript.get("language")
    lines = sentences(transcript, c["start"], c["end"])
    if not lines or not spoken or spoken == lang:
        return lines
    context = (c.get("llm") or {}).get("what_happens") or (c.get("text") or "")[:240]
    with llm.session() as model:
        tr_lines = translate_lines(model, lines, spoken, lang, context)
    hl = read_json(hl_path)  # re-read: the analysis may have saved meanwhile
    c = next((x for x in hl["candidates"] if x["id"] == cid), None)
    if c is not None:
        c.setdefault("translations", {})[lang] = tr_lines
        write_json_atomic(hl_path, hl)
    return tr_lines


def regenerate_titles(project: Project, cid: str) -> dict:
    """Six fresh titles for one candidate (the UI's "New suggestions")."""
    from . import llm

    hl_path = project.dir / "highlights.json"
    hl = read_json(hl_path)
    c = next((x for x in hl["candidates"] if x["id"] == cid), None)
    if c is None or not (c.get("publish") or {}).get("available") or not c.get("llm"):
        raise SharkyClipsError("Analyze this clip with the LLM first.", f"python cli.py analyze {project.id}")
    pub = c["publish"]
    out_lang = pub["language"]
    transcript = project.load_transcript()
    meta = project.load_meta()
    mode = hl.get("mode") or meta.get("mode") or "gaming"
    from .titles import banks

    others = [t for o in hl["candidates"] if o is not c for t in (o.get("publish") or {}).get("titles", [])]
    game = banks.project_game(project)
    bank = banks.get(game["id"])
    gaming = mode == "gaming"
    topic = (game["name"] or "Gaming") if gaming else c["llm"].get("game_or_topic", "")
    gl = titles_mod.glossary.build(
        transcript, out_lang, meta.get("title", ""), topic, game=(game["name"] if gaming else None),
        game_terms=banks.glossary_terms(bank) if gaming else None,
        extra_allowed=banks.caps_words(bank) if gaming else None)
    what = banks.scrub(c["llm"]["what_happens"], game["id"]) if gaming else c["llm"]["what_happens"]
    j = {"what_happens": what, "game_or_topic": topic,
         "hook_text": pub.get("hook_text") or "", "cover_text": pub.get("cover_text") or ""}
    facts = banks.clip_facts(bank, c, transcript) if gaming else {}
    with llm.session() as model:
        tw = _write_titles(model, meta, mode, c, transcript, out_lang, j, gl, others,
                           avoid=list(pub["titles"]), temperature=0.95, fast=llm.fast_analysis(),
                           game=game, facts=facts, bank=bank)
    if tw["titles"]:
        pub["titles"] = [t["text"] for t in tw["titles"]]
        pub["title_styles"] = [t["style"] for t in tw["titles"]]
        pub["title_checks"] = tw["checks"]
    write_json_atomic(hl_path, hl)
    return pub


# ------------------------------------------------------------------ speed (Settings: "Fast analysis")


def _speed_path():
    return config.config_dir() / "llm_speed.json"


def speed_stats() -> dict:
    path = _speed_path()
    try:
        return read_json(path) if path.is_file() else {}
    except Exception:  # noqa: BLE001 - a broken stats file is just reset
        return {}


def record_speed(profile: str, model: str, seconds: float, source: str) -> None:
    """Seconds per clip (judge + titles, LLM already loaded) per profile ("normal" / "fast").
    Kept as a moving average so the Settings page can show the measured difference."""
    data = speed_stats()
    old = data.get(profile) or {}
    if old.get("model") != model:
        old = {}
    n = int(old.get("samples") or 0)
    avg = float(old.get("seconds_per_clip") or seconds)
    avg = seconds if n == 0 else avg + (seconds - avg) / min(n + 1, 8)
    data[profile] = {"model": model, "seconds_per_clip": round(avg, 1), "samples": n + 1, "source": source,
                     "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        write_json_atomic(_speed_path(), data)
    except OSError:
        pass


def benchmark(project: Project, on_progress: Callable[[str, int, int], None] | None = None) -> dict:
    """Speed test: analyze the best clip once with the normal and once with the fast setup
    (nothing is cached or written to the project)."""
    from . import llm

    hl = read_json(project.dir / "highlights.json")
    transcript = project.load_transcript()
    meta = project.load_meta()
    mode = hl.get("mode") or meta.get("mode") or "gaming"
    out_lang = languages.require(config.get("output_language") or "tr").code
    c = dict(min(hl["candidates"], key=lambda x: x["rank"]))
    orig = (c.get("llm") or {}).get("original") or {"start": c["start"], "end": c["end"]}
    c["start"], c["end"] = orig["start"], orig["end"]
    c["duration"] = round(c["end"] - c["start"], 2)
    from .titles import banks

    game = banks.project_game(project)
    profiles = [("normal", llm.choose_model(ignore_fast=True), False), ("fast", llm.fast_model(), True)]
    out = {}
    for i, (profile, name, fast) in enumerate(profiles):
        if on_progress:
            on_progress(profile, i, len(profiles))
        with llm.session(name) as model:
            t0 = time.perf_counter()
            j = model.json(SYSTEM, _prompt(meta, mode, c, transcript, out_lang), _schema(lang_name(out_lang)),
                           check=_hard_checker(out_lang), soft=_checker(out_lang))
            j = _repair(j)
            gl = titles_mod.glossary.build(transcript, out_lang, meta.get("title", ""), j["game_or_topic"])
            tw = _write_titles(model, meta, mode, c, transcript, out_lang, j, gl, [], fast=fast, game=game)
            took = time.perf_counter() - t0
            record_speed(profile, name, took, "benchmark")
            out[profile] = {"model": name, "seconds": round(took, 1), "titles": len(tw["titles"]),
                            "load_seconds": round(model.load_seconds or 0.0, 1),
                            "tokens_per_second": round(model.tokens_per_second, 1)}
    if on_progress:
        on_progress("done", len(profiles), len(profiles))
    return out
