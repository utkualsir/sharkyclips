"""LLM analysis of highlight candidates (`python cli.py analyze <id>`).

Per candidate, one structured LLM call judges the moment and writes the publish
package; a second call translates the subtitles when the output language differs
from the spoken one. Results are cached per candidate (cache/llm/), so re-running
is instant and an interrupted run resumes.

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
from .errors import ClipForgeError
from .highlights.modes import get_mode
from .project import Project, read_json, write_json_atomic
from .textutil import NO_SPACE_LANGS, mmss, sentences, words_between
from .ui import console

PROMPT_VERSION = 7
MAX_SHIFT = 10.0
# Short-form sweet spot per mode (seconds): full length-fit score inside this range.
SWEET_SPOT = {"gaming": (18, 40), "study": (30, 55), "music": (15, 30)}
TITLE_STYLES = ["question", "shock", "story", "punchy", "curiosity", "emotional"]

REASON_TEXT = {
    "loudness_spike": "sudden loud moment", "keyword": "reaction word", "laughter": "laughter",
    "shouting": "shouting", "cheering": "cheering", "fast_speech": "excited fast talking",
    "pause_then_burst": "silence then outburst", "steady_explanation": "calm explanation",
    "chorus": "music chorus", "drop": "music drop", "chat_spike": "chat exploded",
    "chat_reactions": "chat spammed reactions", "llm_explanation": "self-contained explanation",
}

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
    r"\b(?:s[i1]k(?:im|iyim|eyim|ey[iı]m|tir|tim|t[iı]g|is|ik|er|me|ecek)\w*|amk|aq|amina|orospu\w*|"
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
            "titles": {"type": "array", "minItems": 6, "maxItems": 6, "items": {
                "type": "object",
                "properties": {"style": {"type": "string", "enum": TITLE_STYLES},
                               "text": {"type": "string", "minLength": 3, "maxLength": 100}},
                "required": ["style", "text"]}},
            "hashtags": {"type": "array", "minItems": 6, "maxItems": 10,
                         "items": {"type": "string", "minLength": 2, "maxLength": 40}},
            "hook_text": {"type": "string", "minLength": 2, "maxLength": 60},
            "cover_scene": {"type": "string", "minLength": 10, "maxLength": 350},
            "cover_text": {"type": "string", "minLength": 1, "maxLength": 32},
        },
        "required": ["game_or_topic", "what_happens", "self_contained", "moment_type", "funny", "exciting",
                     "useful", "hook_score", "retention_score", "trend_fit_score", "start_shift_s",
                     "end_shift_s", "titles", "hashtags", "hook_text", "cover_scene", "cover_text"],
    }


TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {
        "type": "object",
        "properties": {"i": {"type": "integer", "minimum": 1}, "text": {"type": "string"}},
        "required": ["i", "text"]}}},
    "required": ["lines"],
}

TITLES_SCHEMA = {
    "type": "object",
    "properties": {"titles": _schema("")["properties"]["titles"]},
    "required": ["titles"],
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
        txt = REASON_TEXT.get(r["code"], r["code"]) + (f" \"{r['value']}\"" if r.get("value") else "")
        if txt not in seen:
            seen.add(txt)
            reasons.append(f"{txt} at {r['t'] - c['start']:+.0f}s")
    return f"Signal strengths: {sig}\nDetected: {'; '.join(reasons[:8]) or 'nothing specific'}"


def _prompt(meta: dict, mode: str, c: dict, transcript: dict, out_lang: str, used_titles: list[str]) -> str:
    spoken = transcript.get("language") or "unknown"
    used = "\n".join(f"- {t}" for t in used_titles[-30:]) or "(none yet)"
    return f"""Video title: {meta.get('title', '')}
Channel: {(meta.get('source') or {}).get('uploader') or 'unknown'}
Content type: {mode}
Spoken language: {lang_name(spoken)}
Clip: {c['duration']:.1f} s long (hype rank #{c['rank']}, hype {c['hype_score']}/100)
{_signals_text(c)}

Transcript around the clip (times are relative to the clip start; CLIP lines are inside the clip, ctx lines are context before/after):
{_context(transcript, c['start'], c['end'])}

Tasks:
1. game_or_topic: the game or topic, from the video title and transcript (e.g. "Delta Force").
2. what_happens (English): what actually happens in the CLIP lines, 1-2 sentences. Not the whole video.
3. Judge it: self_contained (understandable without the rest of the video?), moment_type, funny/exciting/useful 0-10.
4. hook_score: how strong the first 3 seconds are. retention_score: will people watch to the end. trend_fit_score: how well it fits what does well on Shorts/TikTok for this game/topic right now. Use the full 0-100 range honestly.
5. start_shift_s / end_shift_s (-10..10): move the start earlier (negative) to include needed setup, or later to cut dead air; move the end so the clip ends right after the payoff/reaction. 0 if the cut is already good.
6. titles: 6 titles in {lang_name(out_lang)}, each a different style from {TITLE_STYLES}, ordered from strongest to weakest. Short (max ~60 characters), correct spelling, normal capitalization (not ALL CAPS), natural, how a real creator in that language would write. Each title must be about what happens in THIS clip; do not copy claims from the video title. No hashtags, no swearing. Do NOT reuse words, phrases or patterns from the titles below - they belong to OTHER, different moments of the video, so never describe their content:
{used}
7. hashtags: 6-10 hashtags: a few general ones (the game/topic, gaming or study, etc.), the rest specific to this clip; mix {lang_name(out_lang)} and universal English tags. No channel or person names.
8. hook_text: max 6 words in {lang_name(out_lang)}, correct spelling, shown on screen in the first seconds to make people stay. About this clip, no swearing.
9. cover_scene (English): describe one striking image for the thumbnail based on what really happens (subject, action, emotion, setting). cover_text: 1-4 punchy words in {lang_name(out_lang)} for the thumbnail.
"""


def _hard_checker(out_lang: str) -> Callable[[dict], list[str]]:
    """Problems that make an answer unusable: wrong language/script, too long hook."""
    script = SCRIPT.get(out_lang)

    def check(d: dict) -> list[str]:
        errs = []
        titles = [t["text"] for t in d.get("titles", [])]
        if len(d.get("hook_text", "").split()) > 8:
            errs.append("hook_text must be at most 6 words")
        if script:
            for field in ("hook_text", "cover_text"):
                if not script.search(d.get(field, "")):
                    errs.append(f"{field} must be written in {lang_name(out_lang)}")
            if sum(bool(script.search(t)) for t in titles) < 5:
                errs.append(f"titles must be written in {lang_name(out_lang)}")
        return errs

    return check


def _checker(out_lang: str, used_titles: list[str]) -> Callable[[dict], list[str]]:
    """Soft problems: repetition and swearing (fixed by dropping titles if retries run out)."""

    def check(d: dict) -> list[str]:
        errs = []
        titles = [t["text"] for t in d.get("titles", [])]
        styles = {t["style"] for t in d.get("titles", [])}
        if len(styles) < 4:
            errs.append("titles: use at least 4 different styles")
        for t in titles:
            for u in used_titles:
                if too_similar(t, u):
                    errs.append(f"title '{t}' is too similar to an already used title '{u}'")
                    break
        for i, a in enumerate(titles):
            for b in titles[i + 1:]:
                if too_similar(a, b, phrases=False):
                    errs.append(f"titles '{a}' and '{b}' are too similar")
        for field, texts in (("titles", titles), ("hashtags", d.get("hashtags", [])),
                             ("hook_text", [d.get("hook_text", "")]), ("cover_text", [d.get("cover_text", "")])):
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
    with llm.lazy_session() as model:
        for i, c in enumerate(todo):
            t0 = time.perf_counter()
            calls0 = model.calls
            orig = c.get("llm", {}).get("original") or {"start": c["start"], "end": c["end"]}
            # always judge the original cut, so results don't drift between runs
            c["start"], c["end"] = orig["start"], orig["end"]
            c["duration"] = round(c["end"] - c["start"], 2)
            key = _cache_key(model.model, out_lang, c, mode, transcript)
            cache_file = cache_dir / f"analyze_{key}.json"
            if cache_file.is_file() and not force:
                j = read_json(cache_file)
                cached = True
            else:
                try:
                    j = model.json(SYSTEM, _prompt(meta, mode, c, transcript, out_lang, used_titles),
                                   _schema(lang_name(out_lang)), check=_hard_checker(out_lang),
                                   soft=_checker(out_lang, used_titles))
                except ClipForgeError as exc:  # one bad clip must not stop the batch
                    console.print(f"[yellow]#{c['rank']}: skipped ({exc.message[:160]})[/]")
                    failed.append({"rank": c["rank"], "error": exc.message})
                    continue
                j = _repair(j, used_titles)
                write_json_atomic(cache_file, j)
                cached = False
            used_titles += [t["text"] for t in j["titles"]]

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
                "titles": [t["text"].strip() for t in j["titles"]],
                "title_styles": [t["style"] for t in j["titles"]],
                "hashtags": clean_hashtags(j["hashtags"], j["game_or_topic"]),
                "hook_text": " ".join(j["hook_text"].split()[:6]),
                "cover_text": j["cover_text"].strip(),
                "cover_prompt": f"{j['cover_scene'].strip().rstrip('.')}. "
                                + COVER_STYLE.format(text=j["cover_text"].strip()),
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

            hl["analysis"] = {"language": out_lang, "model": model.model, "prompt_version": PROMPT_VERSION,
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


def _repair(j: dict, used_titles: list[str]) -> dict:
    """Answer with leftover soft problems: drop sweary / repeated titles and tags."""
    soft = j.pop("_soft_errors", None)
    if not soft:
        return j
    keep: list[dict] = []
    for t in j["titles"]:
        txt = t["text"]
        if has_profanity(txt) or any(too_similar(txt, u) for u in used_titles) \
                or any(too_similar(txt, k["text"], phrases=False) for k in keep):
            continue
        keep.append(t)
    j["titles"] = keep or j["titles"][:1]
    j["hashtags"] = [h for h in j["hashtags"] if not has_profanity(h)]
    if has_profanity(j["hook_text"]):
        j["hook_text"] = ""
    if has_profanity(j["cover_text"]):
        j["cover_text"] = ""
    return j


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
    if c is None or not (c.get("publish") or {}).get("available"):
        raise ClipForgeError("Analyze this clip with the LLM first.", f"python cli.py analyze {project.id}")
    out_lang = c["publish"]["language"]
    transcript = read_json(project.transcript_path)
    avoid = list(c["publish"]["titles"]) + [t for o in hl["candidates"] if o is not c
                                            for t in (o.get("publish") or {}).get("titles", [])]
    prompt = (f"Video title: {project.load_meta().get('title')}\nWhat happens: {c['llm']['what_happens']}\n"
              f"Transcript:\n{_context(transcript, c['start'], c['end'])}\n\n"
              f"Write 6 NEW short titles in {lang_name(out_lang)}, each a different style from "
              f"{TITLE_STYLES}. They must not repeat phrases from these existing titles:\n"
              + "\n".join(f"- {t}" for t in avoid[-40:]))
    check = _checker(out_lang, avoid)

    def titles_only(d: dict) -> list[str]:
        return check({**d, "hook_text": c["publish"]["hook_text"], "cover_text": c["publish"]["cover_text"]})

    with llm.session() as model:
        data = model.json(SYSTEM, prompt, TITLES_SCHEMA, temperature=0.9, soft=titles_only, num_predict=600)
    data = _repair({**data, "hashtags": [], "hook_text": "", "cover_text": ""}, avoid)
    c["publish"]["titles"] = [t["text"].strip() for t in data["titles"]]
    c["publish"]["title_styles"] = [t["style"] for t in data["titles"]]
    write_json_atomic(hl_path, hl)
    return c["publish"]
