"""Best-of video: several highlight clips joined into one 16:9 YouTube video.

  1. package   the local LLM writes title options, a description and one chapter name per
               clip in the output language (cached; plain fallbacks without an LLM)
  2. loudness  every clip is measured (ffmpeg loudnorm, pass 1) and later normalized to
               -14 LUFS (YouTube's level), so no clip is much louder than the next
  3. render    one ffmpeg run: [intro card] -> card -> clip -> card -> clip ... [outro card],
               joined with short crossfades (xfade / acrossfade), 1920x1080 at 60 fps,
               NVENC (or the best hardware encoder), CPU x264 as fallback

Title cards use the app's look: deep navy, gold accents, Instrument Serif (downloaded once
into ~/.sharkyclips/fonts; a system serif is used if that fails). Chapter timestamps are the
card start times in the final video, so they line up exactly.

Output: workspace/<id>/exports/bestof_<time>.mp4 + .json (titles, description, chapters).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import config, languages
from .clips import _ass_escape, _ass_time, _upper
from .errors import SharkyClipsError, require_tool
from .project import Project, read_json, replace_retry, write_json_atomic
from .procs import no_window
from .render import ENCODERS, pick_encoder, run_ffmpeg
from .ui import console

W, H, FPS = 1920, 1080, 60
XFADE = 0.5
CARD_S = 1.8
INTRO_S = 3.2
OUTRO_S = 3.4
TARGET_LUFS, TARGET_TP, TARGET_LRA = -14.0, -1.5, 11.0
MAX_CLIPS = 30
PACKAGE_VERSION = 3

NAVY_HEX = "0x0E1A33"
GOLD = "&H006AB5D9"  # #D9B56A (ASS is &HAABBGGRR)
WHITE = "&H00EEF2F3"  # #F3F2EE
MUTED = "&H00CAB7AE"  # #AEB7CA

FONT_URLS = {
    "InstrumentSerif-Regular.ttf":
        "https://github.com/google/fonts/raw/main/ofl/instrumentserif/InstrumentSerif-Regular.ttf",
    "InstrumentSerif-Italic.ttf":
        "https://github.com/google/fonts/raw/main/ofl/instrumentserif/InstrumentSerif-Italic.ttf",
}
# Instrument Serif has Latin letters only; other scripts use a system font.
NON_LATIN = {"ru", "zh", "ar", "ja"}

# Higher quality than the Shorts preset: this is a long 1080p60 upload.
MONTAGE_ARGS = {
    "h264_nvenc": ("-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "23", "-b:v", "0",
                   "-maxrate", "24M", "-bufsize", "48M", "-profile:v", "high"),
    "h264_videotoolbox": ("-b:v", "14M", "-allow_sw", "0", "-profile:v", "high"),
    "h264_qsv": ("-preset", "medium", "-global_quality", "21"),
    "h264_amf": ("-quality", "balanced", "-rc", "cqp", "-qp_i", "21", "-qp_p", "21"),
    "libx264": ("-preset", "veryfast", "-crf", "20", "-profile:v", "high"),
}

LABELS = {  # fallbacks when there is no LLM
    "intro": {"tr": "Giriş", "en": "Intro", "de": "Intro", "ru": "Вступление", "hu": "Bevezető",
              "ar": "مقدمة", "zh": "开场"},
    "outro": {"tr": "İzlediğin için teşekkürler", "en": "Thanks for watching", "de": "Danke fürs Zuschauen",
              "ru": "Спасибо за просмотр", "hu": "Köszönöm, hogy megnézted", "ar": "شكرًا على المشاهدة",
              "zh": "感谢观看"},
    "best_of": {"tr": "En iyi anlar", "en": "Best moments", "de": "Beste Momente", "ru": "Лучшие моменты",
                "hu": "Legjobb pillanatok", "ar": "أفضل اللحظات", "zh": "精彩时刻"},
    "clip": {"tr": "Klip", "en": "Clip", "de": "Clip", "ru": "Клип", "hu": "Klip", "ar": "مقطع", "zh": "片段"},
}


def _label(kind: str, lang: str) -> str:
    return LABELS[kind].get(lang) or LABELS[kind]["en"]


# ------------------------------------------------------------------ fonts


def fonts_dir() -> Path:
    return config.config_dir() / "fonts"


def ensure_fonts() -> bool:
    """Download Instrument Serif (SIL Open Font License) once. False = use a system font."""
    d = fonts_dir()
    if all((d / name).is_file() for name in FONT_URLS):
        return True
    try:
        import requests

        d.mkdir(parents=True, exist_ok=True)
        for name, url in FONT_URLS.items():
            if (d / name).is_file():
                continue
            r = requests.get(url, timeout=30)
            if not r.ok or len(r.content) < 10_000:
                return False
            tmp = d / (name + ".part")
            tmp.write_bytes(r.content)
            os.replace(tmp, d / name)
        return True
    except Exception as exc:  # noqa: BLE001 - offline: system serif instead
        console.print(f"[yellow]Could not download the Instrument Serif font ({exc}); using a system font.[/]")
        return False


def _fonts(lang: str, have_serif: bool) -> tuple[str, str]:
    """(display font, small caps font) for card text in `lang`."""
    system = platform.system()
    sans = {"Windows": "Segoe UI", "Darwin": "Helvetica Neue"}.get(system, "DejaVu Sans")
    if lang == "zh":
        f = {"Windows": "Microsoft YaHei", "Darwin": "PingFang SC"}.get(system, "Noto Sans CJK SC")
        return f, f
    if lang == "ar":
        f = {"Darwin": "Geeza Pro"}.get(system, "Arial")
        return f, f
    if lang in NON_LATIN or not have_serif:
        serif = {"Windows": "Georgia", "Darwin": "Georgia"}.get(system, "DejaVu Serif")
        return serif, sans
    return "Instrument Serif", sans


# ------------------------------------------------------------------ cards


def _wrap(text: str, max_chars: int) -> str:
    """Balanced line breaks (ASS \\N) for long card titles."""
    words = text.split()
    if len(text) <= max_chars or len(words) < 3:
        return text
    best, best_cost = text, 1e9
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        cost = abs(len(a) - len(b)) + (100 if max(len(a), len(b)) > max_chars * 1.15 else 0)
        if cost < best_cost:
            best, best_cost = a + "\\N" + b, cost
    return best


def _rule(x: int, y: int, w: int, dur: float, delay_ms: int = 120) -> str:
    """Thin gold line that grows from the centre."""
    return (f"Dialogue: 1,{_ass_time(0)},{_ass_time(dur)},rule,,0,0,0,,"
            f"{{\\an5\\pos({x},{y})\\p1\\fscx0\\t({delay_ms},{delay_ms + 420},\\fscx100)\\fad(0,250)}}"
            f"m 0 0 l {w} 0 l {w} 4 l 0 4{{\\p0}}")


def card_ass(kind: str, dur: float, title: str, kicker: str, sub: str, lang: str, have_serif: bool) -> str:
    display, small = _fonts(lang, have_serif)
    rtl = languages.is_rtl(lang)
    big = {"intro": 112, "outro": 96, "clip": 92}[kind]
    head = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: title,{display},{big},{WHITE},{WHITE},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,160,160,0,1",
        f"Style: kicker,{small},30,{GOLD},{GOLD},&H00000000,&H00000000,-1,0,0,0,100,100,"
        f"{0 if lang in ('zh', 'ar') else 6},0,1,0,0,5,160,160,0,1",
        f"Style: sub,{small},34,{MUTED},{MUTED},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,160,160,0,1",
        f"Style: rule,Arial,10,{GOLD},{GOLD},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    ev = []
    end = _ass_time(dur)
    fade = f"\\fad(260,{int(XFADE * 1000)})"

    def text(t: str) -> str:
        t = _ass_escape(t)
        return ("‫" + t + "‬") if rtl else t

    cy = H // 2 - 20
    wrapped = _wrap(_ass_escape(title), 30 if kind != "intro" else 26) if title else ""
    block = (wrapped.count("\\N") + 1) * big * 1.08 if title else 0
    if kicker:
        ky = int(cy - block / 2 - 56)
        ev.append(f"Dialogue: 2,{_ass_time(0)},{end},kicker,,0,0,0,,"
                  f"{{\\an5\\move({W // 2},{ky - 10},{W // 2},{ky},0,500){fade}}}"
                  f"{text(_upper(kicker, lang))}")
    if title:
        if rtl:
            wrapped = "‫" + wrapped + "‬"
        ev.append(f"Dialogue: 2,{_ass_time(0.08)},{end},title,,0,0,0,,"
                  f"{{\\an5\\move({W // 2},{cy + 18},{W // 2},{cy},0,600){fade}}}{wrapped}")
    rule_y = int(cy + block / 2 + 44)
    ev.append(_rule(W // 2, rule_y, 220 if kind == "clip" else 320, dur))
    if sub:
        ev.append(f"Dialogue: 2,{_ass_time(0.25)},{end},sub,,0,0,0,,"
                  f"{{\\an5\\pos({W // 2},{rule_y + 64}){fade}}}{text(sub)}")
    return "\n".join(head + ev) + "\n"


# ------------------------------------------------------------------ loudness


def measure_loudness(source: Path, start: float, duration: float) -> dict | None:
    """loudnorm pass 1 for one clip; None when the clip is silent or has no audio."""
    import subprocess

    cmd = [require_tool("ffmpeg"), "-hide_banner", "-nostats", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
           "-i", str(source), "-vn", "-map", "0:a:0?",
           "-af", f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
           "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=300, **no_window())
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr)
    if res.returncode != 0 or not m:
        return None
    data = json.loads(m.group(0))
    try:
        if float(data["input_i"]) < -70:  # silence: nothing to normalize
            return None
    except (ValueError, KeyError):
        return None
    return {k: data[k] for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}


def _loudnorm(m: dict | None) -> str:
    if not m:
        return "anull"
    return (f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}:measured_I={m['input_i']}:"
            f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
            f"offset={m['target_offset']}:linear=true")


# ------------------------------------------------------------------ LLM package


SYSTEM = ("You are a YouTube editor who packages best-of compilation videos from live streams. You write "
          "natural, advertiser-friendly titles and descriptions in the requested language: no swearing, no "
          "insults, no emojis, no invented events. Answer only with JSON that matches the schema.")


def _package_schema(n: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "titles": {"type": "array", "minItems": 4, "maxItems": 6,
                       "items": {"type": "string", "minLength": 8, "maxLength": 95}},
            "description": {"type": "string", "minLength": 60, "maxLength": 1400},
            "chapters": {"type": "array", "minItems": n, "maxItems": n, "items": {
                "type": "object",
                "properties": {"i": {"type": "integer", "minimum": 1},
                               "label": {"type": "string", "minLength": 2, "maxLength": 48}},
                "required": ["i", "label"]}},
            "intro_label": {"type": "string", "minLength": 2, "maxLength": 24},
            "outro_text": {"type": "string", "minLength": 2, "maxLength": 48},
        },
        "required": ["titles", "description", "chapters", "intro_label", "outro_text"],
    }


def _package_prompt(meta: dict, items: list[dict], lang: str) -> str:
    from .analyze import lang_name

    lines = []
    for i, it in enumerate(items, start=1):
        c = it["cand"]
        llm = c.get("llm") or {}
        title = ((c.get("publish") or {}).get("titles") or [""])[0]
        lines.append(f"{i}. ({c['duration']:.0f} s, {llm.get('moment_type') or 'moment'}) "
                     f"{llm.get('what_happens') or (c.get('text') or '')[:200]}"
                     + (f" | short title: {title}" if title else ""))
    topic = next(((it["cand"].get("llm") or {}).get("game_or_topic") for it in items
                  if (it["cand"].get("llm") or {}).get("game_or_topic")), "")
    return f"""Stream / video title: {meta.get('title', '')}
Channel: {(meta.get('source') or {}).get('uploader') or 'unknown'}
Game / topic: {topic or 'unknown'}
Output language: {lang_name(lang)}

The best-of video shows these clips in this order:
{chr(10).join(lines)}

Write in {lang_name(lang)} (correct spelling, casual creator tone):
1. titles: 5 different YouTube titles for the whole best-of video, 35-70 characters, at most one with "!", at least one question; mention the game/topic when it helps.
2. description: 2-3 short paragraphs (what the video is, the highlights in order, a short call to like/subscribe). No timestamps, no links, no hashtags.
3. chapters: for every clip i, a short chapter name (2-6 words) that says what happens in it. They are also shown big on screen before each clip.
4. intro_label: the chapter name for the intro (like "Intro").
5. outro_text: a short end-card line (like "Thanks for watching")."""


def _fallback_package(meta: dict, items: list[dict], lang: str) -> dict:
    topic = next(((it["cand"].get("llm") or {}).get("game_or_topic") for it in items
                  if (it["cand"].get("llm") or {}).get("game_or_topic")), "") or meta.get("title", "")
    chapters = []
    for i, it in enumerate(items, start=1):
        title = ((it["cand"].get("publish") or {}).get("titles") or [""])[0]
        if len(title) > 48:
            title = title[:48].rsplit(" ", 1)[0].rstrip(",;:")
        chapters.append({"i": i, "label": title or f"{_label('clip', lang)} {i}"})
    return {"titles": [meta.get("title") or f"{topic} – {_label('best_of', lang)}"[:95]], "description": "",
            "chapters": chapters, "intro_label": _label("intro", lang), "outro_text": _label("outro", lang),
            "model": None}


def write_package(project: Project, items: list[dict], lang: str,
                  on_stage: Callable[[str], None] | None = None) -> dict:
    """Titles, description and chapter names (LLM, cached per clip list + language)."""
    from . import llm
    from .analyze import has_profanity

    meta = project.load_meta()
    fallback = _fallback_package(meta, items, lang)
    if config.get("llm_enabled") is False or (llm.ollama_exe() is None and llm.server_version(0.5) is None):
        return fallback
    model_name = llm.choose_model()
    payload = [PACKAGE_VERSION, model_name, lang, meta.get("title", ""),
               [[it["cand"]["id"], it["cand"]["start"], it["cand"]["end"]] for it in items]]
    key = hashlib.sha1(json.dumps(payload).encode()).hexdigest()[:20]
    cache = project.cache_dir / "llm" / f"montage_{key}.json"
    if cache.is_file():
        return read_json(cache)
    if on_stage:
        on_stage("montage_writing")

    def soft(d: dict) -> list[str]:
        bad = [t for t in d["titles"] + [d["description"]] + [c["label"] for c in d["chapters"]]
               if has_profanity(t)]
        return [f"rewrite without swearing: {bad[:3]}"] if bad else []

    def check(d: dict) -> list[str]:
        nums = [c["i"] for c in d["chapters"]]
        return [] if nums == list(range(1, len(items) + 1)) else \
            [f"chapters must be numbered 1..{len(items)} in order, one per clip"]

    try:
        with llm.session(model_name) as model:
            d = model.json(SYSTEM, _package_prompt(meta, items, lang), _package_schema(len(items)),
                           temperature=0.6, check=check, soft=soft, num_predict=2200)
    except SharkyClipsError as exc:
        console.print(f"[yellow]Best-of texts: the LLM failed ({exc.message}); using plain names.[/]")
        return fallback
    d.pop("_soft_errors", None)
    # Same local fixes as clip titles: sentence case (no Title Case), diacritics, glossary spelling.
    from .titles import glossary as glossary_mod, lexicon

    transcript = read_json(project.transcript_path) if project.transcript_path.is_file() else {}
    topic = next(((it["cand"].get("llm") or {}).get("game_or_topic") for it in items
                  if (it["cand"].get("llm") or {}).get("game_or_topic")), "")
    gl = glossary_mod.build(transcript, lang, meta.get("title", ""), topic)

    def fix(text: str) -> str:
        text, _ = lexicon.polish(gl.canonicalize(" ".join(text.split())), lang, keep=gl.keep_case,
                                 protected=gl.allowed)
        return gl.canonicalize(text)

    d["titles"] = [fix(t) for t in d["titles"] if not has_profanity(t)] or fallback["titles"]
    d["chapters"] = [{"i": c["i"], "label": fix(c["label"]).rstrip(".")} for c in d["chapters"]]
    d["outro_text"] = fix(d.get("outro_text") or "") or fallback["outro_text"]
    d["model"] = model_name
    write_json_atomic(cache, d)
    return d


# ------------------------------------------------------------------ render


def fmt_ts(t: float) -> str:
    t = int(t)
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def plan(durations: list[float]) -> tuple[list[float], float]:
    """Start time of every piece in the final video (crossfades overlap) + total length."""
    starts, t = [], 0.0
    for i, d in enumerate(durations):
        starts.append(t)
        t += d - (XFADE if i < len(durations) - 1 else 0)
    return starts, t


def youtube_chapters(chapters: list[dict], total: float, min_len: float = 10.0) -> list[dict]:
    """YouTube rules: the first chapter starts at 00:00 and every chapter is >= 10 s.
    A too-short chapter (e.g. a 3 s intro) is merged into the next one."""
    out: list[dict] = []
    carry: float | None = None  # start time of a short chapter waiting to be merged
    for i, c in enumerate(chapters):
        end = chapters[i + 1]["t"] if i + 1 < len(chapters) else total
        start = carry if carry is not None else c["t"]
        if end - start < min_len and i + 1 < len(chapters):
            carry = start
            continue
        carry = None
        out.append({**c, "t": start})
    if out:
        out[0]["t"] = 0.0
        if len(out) > 1 and total - out[-1]["t"] < min_len:  # short last chapter joins the one before
            out.pop()
    return out


def exports_dir(project: Project) -> Path:
    return project.dir / "exports"


def list_exports(project: Project) -> list[dict]:
    d = exports_dir(project)
    out = []
    if d.is_dir():
        for p in sorted(d.glob("bestof_*.json"), reverse=True):
            try:
                info = read_json(p)
            except Exception:  # noqa: BLE001
                continue
            if (d / info.get("file", "")).is_file():
                out.append(info)
    return out


def render_montage(project: Project, clip_ids: list[str], *, lang: str | None = None, intro: bool = True,
                   outro: bool = True, cards: bool = True,
                   on_progress: Callable[[str, float | None], None] | None = None) -> dict:
    ffmpeg = require_tool("ffmpeg")
    source = project.source_path
    if source is None:
        raise SharkyClipsError("The project's source video is missing.")
    hl_path = project.dir / "highlights.json"
    if not hl_path.is_file():
        raise SharkyClipsError("Find highlights first.")
    hl = read_json(hl_path)
    by_id = {c["id"]: c for c in hl["candidates"]}
    items = [{"cand": by_id[c]} for c in clip_ids if c in by_id][:MAX_CLIPS]
    if len(items) < 2:
        raise SharkyClipsError("Pick at least two clips for a best-of video.")
    lang = languages.require(lang or (hl.get("analysis") or {}).get("language")
                             or config.get("output_language") or "tr").code
    meta = project.load_meta()
    has_audio = bool(meta.get("audio_codec")) or meta.get("audio_codec") is None

    def stage(name: str, frac: float | None = None) -> None:
        if on_progress:
            on_progress(name, frac)

    # 1. texts ---------------------------------------------------------------
    stage("montage_writing")
    pkg = write_package(project, items, lang, on_stage=lambda s: stage(s))
    labels = {c["i"]: c["label"] for c in pkg.get("chapters", [])}

    # 2. loudness ------------------------------------------------------------
    measured = []
    for i, it in enumerate(items):
        stage("montage_loudness", i / len(items))
        c = it["cand"]
        measured.append(measure_loudness(source, c["start"], c["end"] - c["start"]) if has_audio else None)

    # 3. timeline ------------------------------------------------------------
    have_serif = ensure_fonts()
    channel = (meta.get("source") or {}).get("uploader") or ""
    main_title = (pkg.get("titles") or [meta.get("title") or ""])[0]
    pieces: list[dict] = []
    if intro:
        pieces.append({"type": "card", "kind": "intro", "dur": INTRO_S, "title": main_title,
                       "kicker": _label("best_of", lang), "sub": channel, "chapter": pkg.get("intro_label")})
    for i, it in enumerate(items, start=1):
        c = it["cand"]
        label = labels.get(i) or f"{_label('clip', lang)} {i}"
        if cards:
            pieces.append({"type": "card", "kind": "clip", "dur": CARD_S, "title": label,
                           "kicker": f"{i:02d} / {len(items):02d}", "sub": "", "chapter": label, "clip": i})
        pieces.append({"type": "clip", "dur": round(c["end"] - c["start"], 3), "cand": c,
                       "loud": measured[i - 1], "chapter": None if cards else label, "clip": i})
    if outro:
        pieces.append({"type": "card", "kind": "outro", "dur": OUTRO_S, "title": pkg.get("outro_text") or
                       _label("outro", lang), "kicker": "", "sub": channel, "chapter": None})
    starts, total = plan([p["dur"] for p in pieces])

    chapters = []
    for p, t in zip(pieces, starts):
        if p.get("chapter"):
            chapters.append({"t": round(t, 2), "label": p["chapter"], "clip": p.get("clip")})
    chapters = youtube_chapters(chapters, total)
    chapters_text = "\n".join(f"{fmt_ts(c['t'])} {c['label']}" for c in chapters)

    # 4. ffmpeg graph ----------------------------------------------------------
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-montage-"))
    out_dir = exports_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = out_dir / f"bestof_{stamp}.mp4"
    tmp = out_dir / f"bestof_{stamp}.partial.mp4"
    try:
        if have_serif:
            shutil.copytree(fonts_dir(), work / "fonts", dirs_exist_ok=True)
        else:
            (work / "fonts").mkdir()
        inputs: list[str] = []
        graph: list[str] = []
        n_in = 0
        src = str(source.resolve())
        vfit = (f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=bicubic,"
                f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={NAVY_HEX},fps={FPS},format=yuv420p,setsar=1,settb=AVTB")
        for k, p in enumerate(pieces):
            if p["type"] == "card":
                (work / f"card{k}.ass").write_text(
                    card_ass(p["kind"], p["dur"], p["title"], p["kicker"], p["sub"], lang, have_serif),
                    encoding="utf-8")
                graph.append(f"color=c={NAVY_HEX}:s={W}x{H}:r={FPS}:d={p['dur']:.3f},vignette=angle=PI/3.2,"
                             f"ass=card{k}.ass:fontsdir=fonts,format=yuv420p,setsar=1,settb=AVTB[v{k}]")
                graph.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{p['dur']:.3f},asetpts=PTS-STARTPTS[a{k}]")
            else:
                c = p["cand"]
                inputs += ["-ss", f"{c['start']:.3f}", "-t", f"{p['dur']:.3f}", "-i", src]
                graph.append(f"[{n_in}:v]{vfit},trim=0:{p['dur']:.3f},setpts=PTS-STARTPTS[v{k}]")
                if has_audio:
                    graph.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,{_loudnorm(p['loud'])},"
                                 f"aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                                 f"apad,atrim=0:{p['dur']:.3f},asetpts=PTS-STARTPTS[a{k}]")
                else:
                    graph.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{p['dur']:.3f},asetpts=PTS-STARTPTS[a{k}]")
                n_in += 1
        # crossfade chain
        vlast, alast = "v0", "a0"
        for k in range(1, len(pieces)):
            vout, aout = f"vx{k}", f"ax{k}"
            offset = starts[k]
            graph.append(f"[{vlast}][v{k}]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}[{vout}]")
            graph.append(f"[{alast}][a{k}]acrossfade=d={XFADE}:c1=tri:c2=tri[{aout}]")
            vlast, alast = vout, aout
        graph.append(f"[{vlast}]fade=t=out:st={max(0.0, total - 0.6):.3f}:d=0.6,format=yuv420p[vout]")
        graph.append(f"[{alast}]afade=t=out:st={max(0.0, total - 0.6):.3f}:d=0.6,"
                     f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aout]")
        graph_text = ";".join(graph)  # ~600 characters per clip: fits the command line limit
        (work / "graph.txt").write_text(graph_text.replace(";", ";\n"), encoding="utf-8")  # for debugging

        def build(e) -> list[str]:
            args = MONTAGE_ARGS.get(e.name, e.args)
            return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", *inputs,
                    "-filter_complex", graph_text, "-map", "[vout]", "-map", "[aout]",
                    "-c:v", e.name, *args, "-g", str(FPS * 2), "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-movflags", "+faststart", "-progress", "pipe:1", str(tmp.resolve())]

        enc, _ = pick_encoder()
        t0 = time.perf_counter()
        stage("montage_rendering", 0.0)
        code, err = run_ffmpeg(build(enc), total, lambda s: stage("montage_rendering", s / total), cwd=work)
        if code != 0 and enc.hardware:
            console.print(f"[yellow]{enc.label} failed for the best-of video, retrying on the CPU: "
                          f"{err.strip()[-300:]}[/]")
            enc = ENCODERS["libx264"]
            code, err = run_ffmpeg(build(enc), total, lambda s: stage("montage_rendering", s / total), cwd=work)
        if code != 0:
            tmp.unlink(missing_ok=True)
            raise SharkyClipsError(f"ffmpeg could not render the best-of video: {err.strip()[-600:]}")
        replace_retry(tmp, dest)
        seconds = time.perf_counter() - t0
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)

    info = {
        "version": 1, "file": dest.name, "name": dest.stem,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duration": round(total, 2), "width": W, "height": H, "fps": FPS,
        "size_bytes": dest.stat().st_size, "render_seconds": round(seconds, 1), "encoder": enc.label,
        "language": lang, "model": pkg.get("model"),
        "settings": {"intro": intro, "outro": outro, "cards": cards, "crossfade": XFADE,
                     "loudness_lufs": TARGET_LUFS},
        "items": [{"clip_id": it["cand"]["id"], "rank": it["cand"]["rank"], "start": it["cand"]["start"],
                   "end": it["cand"]["end"], "label": labels.get(i + 1),
                   "viral_score": (it["cand"].get("publish") or {}).get("viral_score"),
                   "normalized": measured[i] is not None}
                  for i, it in enumerate(items)],
        "titles": pkg.get("titles") or [], "description": pkg.get("description") or "",
        "chapters": chapters, "chapters_text": chapters_text,
    }
    write_json_atomic(out_dir / f"{dest.stem}.json", info)
    return info


def delete_export(project: Project, name: str) -> bool:
    if not re.fullmatch(r"bestof_[0-9-]+", name):
        return False
    d = exports_dir(project)
    found = False
    for p in (d / f"{name}.mp4", d / f"{name}.json"):
        if p.is_file():
            p.unlink()
            found = True
    return found
