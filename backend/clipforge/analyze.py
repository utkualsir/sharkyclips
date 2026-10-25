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
from .errors import ClipForgeError
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


def has_profanity(text: str) -> bool:
    # Not re.I: it would treat Turkish dotless ı as i ("sıkıştı" = "got stuck" is fine).
    t = "".join(ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch))
    return bool(PROFANITY.search(t.replace("ß", "ss")))
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


def clean_hashtags(tags: list[str], topic: str) -> list[str]:
    out: list[str] = []

    def add(tag: str) -> None:
        tag = re.sub(r"[^\w]", "", tag.replace("#", "").strip(), flags=re.UNICODE)
        if tag and tag.casefold() not in {t[1:].casefold() for t in out}:
            out.append("#" + tag)

    add("shorts")
    topic_tag = re.sub(r"[^\w]", "", topic.split("(")[0], flags=re.UNICODE)
    if 2 < len(topic_tag) <= 30:
        add(topic_tag)
    for t in tags:
        add(t)
    return out[:10]


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
    return round(start, 2), round(end, 2)


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


def _context_block(meta: dict, mode: str, c: dict, transcript: dict) -> str:
    """Shared start of the judge and the titles prompt (Ollama reuses the cached prefix)."""
    spoken = transcript.get("language") or "unknown"
    return f"""Video title: {meta.get('title', '')}
Channel: {(meta.get('source') or {}).get('uploader') or 'unknown'}
Content type: {mode}
Spoken language: {lang_name(spoken)}
Clip: {c['duration']:.1f} s long (hype rank #{c['rank']}, hype {c['hype_score']}/100)
{_signals_text(c)}

Transcript around the clip (times are relative to the clip start; CLIP lines are inside the clip, ctx lines are context before/after):
{_context(transcript, c['start'], c['end'])}"""


def _prompt(meta: dict, mode: str, c: dict, transcript: dict, out_lang: str) -> str:
    return _context_block(meta, mode, c, transcript) + f"""

TASK: judge this clip and write its publish package.
1. game_or_topic: the game or topic, from the video title and transcript (e.g. "Delta Force").
2. what_happens (English): what actually happens in the CLIP lines, 1-2 sentences. Not the whole video. Mention names, places and items only as they are said.
3. Judge it: self_contained (understandable without the rest of the video?), moment_type, funny/exciting/useful 0-10.
4. hook_score: how strong the first 3 seconds are. retention_score: will people watch to the end. trend_fit_score: how well it fits what does well on Shorts/TikTok for this game/topic right now. Use the full 0-100 range honestly.
5. start_shift_s / end_shift_s (-10..10): move the start earlier (negative) to include needed setup, or later to cut dead air; move the end so the clip ends right after the payoff/reaction. 0 if the cut is already good.
6. hashtags: 6-10 hashtags: a few general ones (the game/topic, gaming or study, etc.), the rest specific to this clip; mix {lang_name(out_lang)} and universal English tags. No channel or person names.
7. hook_text: max 6 words in {lang_name(out_lang)}, correct spelling, shown on screen in the first seconds to make people stay. Casual, about this clip, no swearing, no emojis.
8. cover_scene (English): describe one striking image for the thumbnail based on what really happens (subject, action, emotion, setting). cover_text: 1-4 punchy words in {lang_name(out_lang)} for the thumbnail.
"""


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


def analyze_project(project: Project, out_lang: str | None = None, force: bool = False,
                    refine: bool = True, ranks: list[int] | None = None, translate: bool = True,
                    on_progress: Callable[[int, int, dict], None] | None = None) -> dict:
    from . import llm

    hl_path = project.dir / "highlights.json"
    if not hl_path.is_file():
        raise ClipForgeError("No highlights yet for this project.",
                             f"Run: python cli.py highlights {project.id}")
    if not project.transcript_path.is_file():
        raise ClipForgeError("No transcript yet.", f"Run: python cli.py transcribe {project.id}")
    out_lang = languages.require(out_lang or config.get("output_language") or "tr").code
    hl = read_json(hl_path)
    transcript = read_json(project.transcript_path)
    meta = project.load_meta()
    mode = hl.get("mode") or meta.get("mode") or "gaming"
    preset = get_mode(mode)
    spoken = transcript.get("language")
    cands = sorted(hl["candidates"], key=lambda c: c["rank"])
    todo = [c for c in cands if ranks is None or c["rank"] in ranks]
    cache_dir = project.cache_dir / "llm"
    cache_dir.mkdir(parents=True, exist_ok=True)
    duration = float(hl.get("duration") or meta.get("duration") or 0)

    t_start = time.perf_counter()
    timings = []
    failed: list[dict] = []
    used_titles: list[str] = []
    glossaries: dict = {}

    def glossary_for(topic: str):
        game = titles_mod.glossary.detect_game(meta.get("title", ""), topic) or ""
        if game not in glossaries:
            glossaries[game] = titles_mod.glossary.build(transcript, out_lang, meta.get("title", ""), topic)
        return glossaries[game]

    style = titles_mod.style_digest(out_lang, mode)
    fast = llm.fast_analysis()
    profile = "fast" if fast else "normal"
    gl = None
    with llm.lazy_session() as model:
        for i, c in enumerate(todo):
            t0 = time.perf_counter()
            calls0 = model.calls
            orig = c.get("llm", {}).get("original") or {"start": c["start"], "end": c["end"]}
            # always judge the original cut, so results don't drift between runs
            c["start"], c["end"] = orig["start"], orig["end"]
            c["duration"] = round(c["end"] - c["start"], 2)
            key = _cache_key(model.model, out_lang, c, mode, transcript)
            cache_file = cache_dir / f"judge_{key}.json"
            cached = True
            try:
                if cache_file.is_file() and not force:
                    j = read_json(cache_file)
                else:
                    j = model.json(SYSTEM, _prompt(meta, mode, c, transcript, out_lang),
                                   _schema(lang_name(out_lang)), check=_hard_checker(out_lang),
                                   soft=_checker(out_lang))
                    j = _repair(j)
                    write_json_atomic(cache_file, j)
                    cached = False
                gl = glossary_for(j["game_or_topic"])
                gdig = hashlib.sha1(gl.digest().encode()).hexdigest()[:10]
                tkey = _cache_key(model.model, out_lang, c, mode, transcript,
                                  extra=f"titles:{style}:{gdig}" + (":fast" if fast else ""))
                tfile = cache_dir / f"titles_{tkey}.json"
                if tfile.is_file() and not force:
                    tw = read_json(tfile)
                else:
                    tw = _write_titles(model, meta, mode, c, transcript, out_lang, j, gl, used_titles, fast=fast)
                    write_json_atomic(tfile, tw)
                    cached = False
                if not cached:
                    record_speed(profile, model.model, time.perf_counter() - t0, "analysis")
                tw = titles_mod.refilter(tw, out_lang, has_profanity)  # cached answers meet today's filters
            except ClipForgeError as exc:  # one bad clip must not stop the batch
                console.print(f"[yellow]#{c['rank']}: skipped ({exc.message[:160]})[/]")
                failed.append({"rank": c["rank"], "error": exc.message})
                continue
            used_titles += [t["text"] for t in tw["titles"]]

            # neighbours limit how far the boundaries may move (no overlaps)
            others = [o for o in cands if o is not c]
            lo = max([0.0] + [o["end"] for o in others if o["end"] <= orig["start"] + 0.01])
            hi = min([duration or orig["end"] + MAX_SHIFT] + [o["start"] for o in others
                                                              if o["start"] >= orig["end"] - 0.01])
            lo, hi = max(lo, orig["start"] - MAX_SHIFT), min(hi, orig["end"] + MAX_SHIFT)
            if refine:
                start, end = snap_boundaries(
                    transcript, orig["start"] + j["start_shift_s"], orig["end"] + j["end_shift_s"],
                    lo, hi, preset.clip_min * 0.8, preset.clip_max)
            else:
                start, end = orig["start"], orig["end"]
            c["start"], c["end"], c["duration"] = start, end, round(end - start, 2)
            lines = sentences(transcript, start, end)
            joiner = "" if spoken in NO_SPACE_LANGS else " "
            c["text"] = joiner.join(x["text"] for x in lines) or c.get("text", "")

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
                "hashtags": clean_hashtags(j["hashtags"], j["game_or_topic"]),
                "hook_text": tw["hook_text"] or " ".join(j["hook_text"].split()[:6]),
                "cover_text": tw["cover_text"] or j["cover_text"].strip(),
                "cover_prompt": f"{j['cover_scene'].strip().rstrip('.')}. "
                                + COVER_STYLE.format(text=tw["cover_text"] or j["cover_text"].strip()),
                "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            c["llm"] = {"game_or_topic": j["game_or_topic"], "what_happens": j["what_happens"],
                        "self_contained": j["self_contained"], "moment_type": j["moment_type"],
                        "funny": j["funny"], "exciting": j["exciting"], "useful": j["useful"],
                        "start_shift_s": j["start_shift_s"], "end_shift_s": j["end_shift_s"],
                        "original": orig, "refined": refine and (start, end) != (orig["start"], orig["end"])}

            # subtitles in the output language (segment timing kept)
            if translate and spoken and out_lang != spoken and lines:
                tkey = _cache_key(model.model, out_lang, c, mode, transcript, extra=f"tr:{start}:{end}")
                tfile = cache_dir / f"translate_{tkey}.json"
                if tfile.is_file() and not force:
                    tr_lines = read_json(tfile)
                else:
                    tr_lines = translate_lines(model, lines, spoken, out_lang, j["what_happens"])
                    write_json_atomic(tfile, tr_lines)
                c.setdefault("translations", {})[out_lang] = tr_lines

            hl["analysis"] = {"language": out_lang, "model": model.model, "fast": fast,
                              "prompt_version": PROMPT_VERSION,
                              "titles_version": titles_mod.TITLES_VERSION, "glossary": gl.terms if gl else [],
                              "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            write_json_atomic(hl_path, hl)  # after every clip: an interrupted run keeps its work
            took = time.perf_counter() - t0
            timings.append({"rank": c["rank"], "seconds": round(took, 1), "cached": cached,
                            "llm_calls": model.calls - calls0})
            if on_progress:
                on_progress(i + 1, len(todo), c)
        stats = {"calls": model.calls, "retries": model.retries, "llm_seconds": round(model.seconds, 1),
                 "load_seconds": round(model.load_seconds or 0.0, 1), "model": model.model,
                 "tokens_per_second": round(model.tokens_per_second, 1)}

    _sync_hype_curve(project, hl)
    meta["analysis"] = {"language": out_lang, "model": stats["model"], "count": len(todo)}
    project.save_meta(meta)
    done = {t["rank"] for t in timings}
    return {"language": out_lang, "candidates": [c for c in todo if c["rank"] in done],
            "failed": failed, "timings": timings, **stats,
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
                  fast: bool = False) -> dict:
    return titles_mod.write(
        model, fast=fast, system=SYSTEM, context=_context_block(meta, mode, c, transcript), lang=out_lang,
        lang_label=lang_name(out_lang), mode=mode, what_happens=j["what_happens"], topic=j["game_or_topic"],
        glossary=gl, used_titles=used_titles, hook_text=j.get("hook_text") or "",
        cover_text=j.get("cover_text") or "", clip_lines=_clip_lines(transcript, c),
        too_similar=too_similar, has_profanity=has_profanity, avoid=avoid, temperature=temperature,
        script_check=_titles_script_checker(out_lang))


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


def regenerate_titles(project: Project, cid: str) -> dict:
    """Six fresh titles for one candidate (the UI's "New suggestions")."""
    from . import llm

    hl_path = project.dir / "highlights.json"
    hl = read_json(hl_path)
    c = next((x for x in hl["candidates"] if x["id"] == cid), None)
    if c is None or not (c.get("publish") or {}).get("available") or not c.get("llm"):
        raise ClipForgeError("Analyze this clip with the LLM first.", f"python cli.py analyze {project.id}")
    pub = c["publish"]
    out_lang = pub["language"]
    transcript = read_json(project.transcript_path)
    meta = project.load_meta()
    mode = hl.get("mode") or meta.get("mode") or "gaming"
    others = [t for o in hl["candidates"] if o is not c for t in (o.get("publish") or {}).get("titles", [])]
    gl = titles_mod.glossary.build(transcript, out_lang, meta.get("title", ""), c["llm"].get("game_or_topic", ""))
    j = {"what_happens": c["llm"]["what_happens"], "game_or_topic": c["llm"].get("game_or_topic", ""),
         "hook_text": pub.get("hook_text") or "", "cover_text": pub.get("cover_text") or ""}
    with llm.session() as model:
        tw = _write_titles(model, meta, mode, c, transcript, out_lang, j, gl, others,
                           avoid=list(pub["titles"]), temperature=0.95, fast=llm.fast_analysis())
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
    transcript = read_json(project.transcript_path)
    meta = project.load_meta()
    mode = hl.get("mode") or meta.get("mode") or "gaming"
    out_lang = languages.require(config.get("output_language") or "tr").code
    c = dict(min(hl["candidates"], key=lambda x: x["rank"]))
    orig = (c.get("llm") or {}).get("original") or {"start": c["start"], "end": c["end"]}
    c["start"], c["end"] = orig["start"], orig["end"]
    c["duration"] = round(c["end"] - c["start"], 2)
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
            tw = _write_titles(model, meta, mode, c, transcript, out_lang, j, gl, [], fast=fast)
            took = time.perf_counter() - t0
            record_speed(profile, name, took, "benchmark")
            out[profile] = {"model": name, "seconds": round(took, 1), "titles": len(tw["titles"]),
                            "load_seconds": round(model.load_seconds or 0.0, 1),
                            "tokens_per_second": round(model.tokens_per_second, 1)}
    if on_progress:
        on_progress("done", len(profiles), len(profiles))
    return out
