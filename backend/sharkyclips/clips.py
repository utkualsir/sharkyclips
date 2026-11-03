"""Vertical 9:16 clip rendering: layout + burned-in subtitles + hook text.

Layouts (output is always 1080x1920):
  split  facecam on top (40%), gameplay below - needs a facecam region
  fit    whole frame in the middle, blurred copy of it as the background
  crop   fill the frame (center crop)
  auto   split when the project has a facecam region, else fit

Hook options: a hook text on screen for the first seconds, and/or a "flash": the
clip's peak moment shown for ~1 s at the very start, then the clip from its start.
Subtitles can use the LLM translation (analyze --lang) instead of the spoken words.

Subtitles come from the word timestamps in transcript.json and are drawn by
libass (ffmpeg's `ass` filter), which also handles right-to-left Arabic and
CJK text. All text (subtitles and the hook) goes through one .ass file.
"""

from __future__ import annotations

import platform
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import languages
from .errors import SharkyClipsError, require_tool
from .project import Project, read_json, replace_retry
from .render import Encoder, RenderResult, run_ffmpeg

OUT_W, OUT_H = 1080, 1920
SPLIT_TOP = 768  # facecam height in the split layout (40%)
LAYOUTS = ("auto", "split", "fit", "crop")
SUBTITLE_STYLES = ("bold", "karaoke", "speakers", "clean", "minimal", "none")
NO_SPACE_LANGS = {"zh", "ja"}
FLASH_SECONDS = 1.0

GOLD = "&H006AB5D9"  # #D9B56A as ASS &HAABBGGRR
WHITE = "&H00FFFFFF"
NAVY = "&H00331A0E"  # #0E1A33
BLACK = "&H00000000"


@dataclass
class ClipOptions:
    layout: str = "auto"
    subtitles: str = "bold"
    hook: bool = True
    hook_text: str = ""  # empty -> the LLM's hook text, else the clip's first sentence
    hook_flash: bool = False  # show the peak moment for ~1 s before the clip
    subtitle_lang: str = ""  # "" = spoken language; a code = use that translation if available
    # Editing tools (1.2.4, edit/): swear words, silence / filler cuts, zoom, music, brand kit
    profanity: str = "auto"  # auto (bleep in vertical videos) | bleep | mute | off
    profanity_captions: bool = True  # "a**" in the captions
    bleep_sound: str = "classic"  # classic | boop | custom (profanity "mute" = silence instead)
    speaker_colors: bool = True  # captions: one colour per speaker (after the voice pass)
    speaker_names: bool = False  # captions: "Me:" / "Efe:" tag when the speaker changes
    cuts: str = "off"  # off | light | strong
    zoom: str = "off"  # off | subtle | strong
    music: bool = False  # background music from the user's library
    brand: bool = False  # the active brand kit preset
    loop: bool = False  # seamless loop (1.2.5): the end flows back into the start
    # Fun effects (1.2.17, edit/fx.py): instant replay, chat bubbles, meme effects
    replay: str = "off"  # off | auto (slow-motion replay of the key event)
    chat_bubbles: bool = False  # real chat messages from the moment as bubbles
    memes: str = "off"  # off | light | strong

    @classmethod
    def from_dict(cls, data: dict | None) -> "ClipOptions":
        data = data or {}
        keys = ("layout", "subtitles", "hook", "hook_text", "hook_flash", "subtitle_lang", "profanity",
                "profanity_captions", "bleep_sound", "speaker_colors", "speaker_names", "cuts", "zoom",
                "music", "brand", "loop", "replay", "chat_bubbles", "memes")
        opts = cls(**{k: data[k] for k in keys if k in data})
        opts.chat_bubbles = bool(opts.chat_bubbles)
        opts.hook_flash = bool(opts.hook_flash)
        opts.profanity_captions = bool(opts.profanity_captions)
        opts.music, opts.brand, opts.loop = bool(opts.music), bool(opts.brand), bool(opts.loop)
        opts.speaker_colors, opts.speaker_names = bool(opts.speaker_colors), bool(opts.speaker_names)
        for name, allowed in (("profanity", ("auto", "bleep", "mute", "off")), ("cuts", ("off", "light", "strong")),
                              ("zoom", ("off", "subtle", "strong")), ("replay", ("off", "auto")),
                              ("memes", ("off", "light", "strong")),
                              ("bleep_sound", ("classic", "boop", "custom"))):
            if getattr(opts, name) not in allowed:
                raise SharkyClipsError(f"Unknown {name} setting '{getattr(opts, name)}'.",
                                       f"Use one of: {', '.join(allowed)}")
        opts.subtitle_lang = str(opts.subtitle_lang or "")
        if opts.subtitle_lang and not languages.get(opts.subtitle_lang):
            raise SharkyClipsError(f"Unknown subtitle language '{opts.subtitle_lang}'.")
        if opts.layout not in LAYOUTS:
            raise SharkyClipsError(f"Unknown layout '{opts.layout}'.", f"Use one of: {', '.join(LAYOUTS)}")
        if opts.subtitles not in SUBTITLE_STYLES:
            raise SharkyClipsError(f"Unknown subtitle style '{opts.subtitles}'.",
                                   f"Use one of: {', '.join(SUBTITLE_STYLES)}")
        opts.hook_text = str(opts.hook_text or "").strip()[:120]
        return opts

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Facecam:
    """Facecam region, normalized 0..1 relative to the source frame."""
    x: float
    y: float
    w: float
    h: float
    source: str = "manual"  # "auto" | "manual"
    confidence: float | None = None
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Facecam | None":
        if not data:
            return None
        x, y = min(max(float(data["x"]), 0.0), 0.98), min(max(float(data["y"]), 0.0), 0.98)
        w = min(max(float(data["w"]), 0.02), 1.0 - x)
        h = min(max(float(data["h"]), 0.02), 1.0 - y)
        return cls(x, y, w, h, str(data.get("source") or "manual"), data.get("confidence"))

    def to_dict(self) -> dict:
        return {"x": round(self.x, 4), "y": round(self.y, 4), "w": round(self.w, 4),
                "h": round(self.h, 4), "source": self.source, "confidence": self.confidence}


@dataclass
class OutputSpec:
    """What the encoder makes (export formats + platform presets, export.py).

    frame: "vertical" (9:16, 1080x1920 canvas) or "wide" (16:9, 1920x1080 canvas: the whole
    picture, no facecam split). Subtitles are laid out on the canvas, then the picture is
    scaled to width x height. safe = (top, right, bottom, left) canvas pixels that the
    platform's own buttons and captions cover: our subtitles and hook stay out of them."""
    frame: str = "vertical"
    width: int | None = None
    height: int | None = None
    fps: float | None = None  # max frame rate (None = source, capped at 60)
    codec: str = "h264"  # h264 | hevc | av1 | vp9
    bitrate_k: int | None = None  # video target kbit/s (None = constant quality)
    audio: str = "aac"  # aac | opus | none
    audio_k: int = 192
    container: str = "mp4"  # mp4 | mov | webm
    burn_captions: bool = True
    safe: tuple[int, int, int, int] = (0, 0, 0, 0)
    max_seconds: float | None = None  # the platform's length limit (a seamless loop stays under it)

    @property
    def canvas(self) -> tuple[int, int]:
        return (OUT_H, OUT_W) if self.frame == "wide" else (OUT_W, OUT_H)


@dataclass
class Geometry:
    """Where text goes on the canvas."""
    w: int = OUT_W
    h: int = OUT_H
    cap_x: int = OUT_W // 2
    cap_y: int | None = None  # None = layout default
    hook_y: int | None = None
    scale: float = 1.0  # font sizes
    margin_l: int = 70
    margin_r: int = 70

    @classmethod
    def for_spec(cls, spec: OutputSpec | None, layout: str) -> "Geometry":
        if spec is None:
            return cls()
        w, h = spec.canvas
        top, right, bottom, left = spec.safe
        if spec.frame == "wide":
            geo = cls(w, h, w // 2, h - 150 - bottom, 70 + top, 0.72, 120 + left, 120 + right)
        else:
            cap = SPLIT_TOP if layout == "split" else 1390
            hook = 120 if layout != "fit" else 330
            # Two caption lines are ~210 px tall: the block's bottom must stay above the zone.
            if bottom and layout != "split":
                cap = min(cap, h - bottom - 120)
            geo = cls(w, h, (left + w - right) // 2, cap, max(hook, top + 30), 1.0, 70 + left, 70 + right)
        return geo


def flash_from(peak: float, src_duration: float, src_fps: float) -> float:
    """Where the hook flash starts: just before the peak, on a source frame."""
    t = min(max(0.0, peak - 0.45), max(0.0, src_duration - FLASH_SECONDS))
    return round(t * src_fps) / src_fps if src_fps > 0 else t


def seek_at(t: float, src_fps: float) -> str:
    """-ss value whose first kept frame is the source frame NEAREST to t (the editors' timelines
    round the same way), so every piece starts exactly where its timeline clip does."""
    return f"{max(0.0, t - 0.45 / max(1.0, src_fps)):.4f}"


def resolve_layout(layout: str, facecam: Facecam | None) -> str:
    if layout == "auto":
        return "split" if facecam else "fit"
    if layout == "split" and not facecam:
        return "fit"  # can't split without knowing where the facecam is
    return layout


# --------------------------------------------------------------------- text


def _upper(text: str, lang: str | None) -> str:
    if lang == "tr":  # Turkish dotted/dotless i
        text = text.replace("i", "İ").replace("ı", "I")
    if lang in ("ar", "zh", "ja"):
        return text
    return text.upper()


def _ass_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
            .replace("\n", " ").strip())


def _ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _font_for(lang: str | None) -> str:
    system = platform.system()
    if lang == "zh":
        return {"Windows": "Microsoft YaHei", "Darwin": "PingFang SC"}.get(system, "Noto Sans CJK SC")
    if lang == "ar":
        return {"Darwin": "Geeza Pro"}.get(system, "Arial")
    return {"Windows": "Arial", "Darwin": "Helvetica Neue"}.get(system, "DejaVu Sans")


def clip_words(transcript: dict, start: float, end: float) -> list[dict]:
    """Words fully or mostly inside [start, end], times relative to the clip start."""
    out = []
    for seg in transcript.get("segments", []):
        if seg["end"] < start or seg["start"] > end:
            continue
        for w in seg.get("words", []):
            mid = (w["start"] + w["end"]) / 2
            if start <= mid <= end and w["word"].strip():
                out.append({"start": max(0.0, w["start"] - start),
                            "end": min(end - start, w["end"] - start), "word": w["word"].strip()})
    return out


def group_words(words: list[dict], max_chars: int, max_words: int,
                lang: str | None) -> list[list[dict]]:
    """Split words into caption lines: short, and broken after sentence ends / pauses."""
    joiner = "" if lang in NO_SPACE_LANGS else " "
    groups: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if cur:
            text = joiner.join(x["word"] for x in cur + [w])
            gap = w["start"] - cur[-1]["end"]
            ended = cur[-1]["word"].endswith(tuple(".!?。！？…؟,，"))
            if len(text) > max_chars or len(cur) >= max_words or gap > 0.7 or ended:
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def first_sentence(text: str, limit: int = 70, min_len: int = 24) -> str:
    """Default hook text: the clip's opening sentence(s), long enough to say something."""
    text = " ".join(text.split())
    out = ""
    i = 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] not in ".!?。！？؟":
            j += 1
        out = text[: j + 1].strip()
        if len(out) >= min_len or j >= len(text):
            break
        i = j + 1
    if len(out) > limit:
        cut = out[:limit].rsplit(" ", 1)[0]
        out = (cut if len(cut) > limit // 2 else out[:limit]).rstrip(",;:") + "…"
    return out[:1].upper() + out[1:] if out else out


def translated_words(lines: list[dict], start: float, end: float, lang: str) -> list[dict]:
    """Subtitle lines (segment timing) -> evenly timed pseudo-words, so the translated
    subtitles get the same word-by-word look. Times relative to the clip start."""
    out = []
    for ln in lines:
        a, b = max(start, ln["start"]), min(end, ln["end"])
        if b <= a:
            continue
        tokens = list(ln["text"].replace(" ", "")) if lang in NO_SPACE_LANGS else ln["text"].split()
        if not tokens:
            continue
        total = sum(len(t) + 1 for t in tokens)
        t = a
        for tok in tokens:
            d = (b - a) * (len(tok) + 1) / total
            out.append({"start": t - start, "end": t + d - start, "word": tok})
            t += d
    return out


def build_ass(words: list[dict], duration: float, opts: ClipOptions, layout: str,
              lang: str | None, hook_text: str, offset: float = 0.0,
              hook_lang: str | None = None, geo: Geometry | None = None,
              style: dict | None = None, hook_start: float = 0.0, extra: list[str] | None = None,
              hook_fade_in: int = 150, speakers: dict | None = None, extra_styles: list[str] | None = None,
              pauses: list[tuple[float, float]] | None = None) -> str:
    """offset: seconds before the clip's main part (intro card + hook flash); subtitles start
    after it. geo: canvas size and text positions (default: the 1080x1920 clip).
    style: brand kit caption look {"font", "primary", "highlight", "outline"} (#RRGGBB).
    hook_start: when the hook text appears (after an intro card). extra: more Dialogue lines.
    speakers: {"me": "custom name" | "", "f1": ...}: words with "spk" get speaker colours /
    name tags (options speaker_colors / speaker_names, or the "speakers" style).
    extra_styles: more Style lines (effects). pauses: (start, end) canvas times with no captions
    (an instant replay / freeze frame): a caption never runs into one."""
    geo = geo or Geometry()
    font = _font_for(lang)
    prim_c, gold_c, black_c = WHITE, GOLD, BLACK
    if style:
        from .edit.brand import ass_color

        font = style.get("font") or font
        prim_c = ass_color(style.get("primary") or "#FFFFFF")
        gold_c = ass_color(style.get("highlight") or "#D9B56A")
        black_c = ass_color(style.get("outline") or "#000000")
    rtl = languages.is_rtl(hook_lang or lang)
    # Caption line position (center of the text block)
    cap_y = geo.cap_y if geo.cap_y is not None else (SPLIT_TOP if layout == "split" else 1390)

    def sz(v: float) -> int:
        return max(1, int(round(v * geo.scale)))

    styles = {
        # name: size, primary, outline colour, back colour, bold, border style, outline, shadow
        "bold": (sz(86), prim_c, black_c, "&H80000000", -1, 1, sz(7), sz(2)),
        "karaoke": (sz(72), gold_c, black_c, "&H80000000", -1, 1, sz(6), sz(2)),
        "speakers": (sz(66), prim_c, black_c, "&H80000000", -1, 1, sz(6), sz(2)),
        "clean": (sz(62), prim_c, "&H50000000", "&H00000000", -1, 3, sz(14), 0),
        "minimal": (sz(56), prim_c, "&H70000000", "&HA0000000", 0, 1, sz(2), sz(3)),
    }
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {geo.w}", f"PlayResY: {geo.h}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    for name, (size, prim, outl, back, bold, border, outline, shadow) in styles.items():
        second = prim_c if name == "karaoke" else gold_c  # karaoke: not yet sung = plain colour
        lines.append(f"Style: {name},{font},{size},{prim},{second},{outl},{back},{bold},0,0,0,"
                     f"100,100,0,0,{border},{outline},{shadow},5,{geo.margin_l},{geo.margin_r},0,1")
    lines.append(f"Style: hook,{font},{sz(64)},{NAVY},{NAVY},{WHITE},&H40000000,-1,0,0,0,"
                 f"100,100,0,0,3,{sz(22)},0,8,{geo.margin_l + 20},{geo.margin_r + 20},0,1")
    lines.append(f"Style: card,{font},{sz(80)},{WHITE},{WHITE},&H00000000,&H00000000,-1,0,0,0,"
                 f"100,100,0,0,1,0,0,5,{geo.margin_l},{geo.margin_r},0,1")
    lines.append(f"Style: handle,{font},{sz(38)},{WHITE},{WHITE},&H60000000,&H80000000,-1,0,0,0,"
                 f"100,100,0,0,1,{sz(3)},{sz(1)},7,0,0,0,1")
    lines += extra_styles or []
    lines += ["", "[Events]",
              "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]

    def event(start: float, end: float, style: str, text: str, layer: int = 0, shift: bool = True) -> None:
        if shift:
            start, end = start + offset, end + offset
        if style != "hook":
            for pa, _pb in pauses or []:
                if start < pa < end:
                    end = pa
            if any(pa <= start < pb for pa, pb in pauses or []) or end - start < 0.02:
                return
        lines.append(f"Dialogue: {layer},{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{text}")

    if opts.subtitles != "none" and words:
        from . import captions
        from .edit.brand import ass_color

        style = opts.subtitles
        spks = {w.get("spk") for w in words if w.get("spk")}
        multi = len(spks) >= 2
        colored = multi and (opts.speaker_colors or style == "speakers")
        tags = multi and (opts.speaker_names or style == "speakers")

        def color_of(spk: str | None) -> str:
            if colored and spk in captions.SPEAKER_COLORS:
                return ass_color(captions.SPEAKER_COLORS[spk])
            return prim_c

        joiner = "" if lang in NO_SPACE_LANGS else " "
        y = cap_y - (sz(22) if tags else 0)
        pos = f"{{\\an5\\pos({geo.cap_x},{y})}}"
        size = styles[style][0]
        last_spk: list = [None]

        def tag_for(spk: str | None) -> str:
            """Name tag line above the caption when the speaker changes."""
            if not tags or not spk or spk == last_spk[0]:
                return ""
            last_spk[0] = spk
            name = _ass_escape(captions.speaker_label(spk, speakers, lang))
            return f"{{\\fs{sz(40)}\\c{color_of(spk)}\\b1}}{name}{{\\fs{size}}}\\N"

        if style == "bold":
            groups = captions.cards(words, lang, 16, max_lines=1, max_words=3)
        elif style == "karaoke":
            groups = captions.cards(words, lang, 22, max_lines=2, max_words=9)
        else:
            groups = captions.cards(words, lang, 26 if style != "minimal" else 30, max_lines=2, max_words=12)
        for gi, group in enumerate(groups):
            g_start = group[0]["start"]
            nxt = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else duration
            g_end = min(max(group[-1]["end"] + 0.35, g_start + 0.4), nxt, duration)
            spk = group[0].get("spk")
            base_c = color_of(spk)
            tag = tag_for(spk)
            if style == "bold":
                texts = [_ass_escape(_upper(w["word"], lang)) for w in group]
                # One event per word: the word being spoken is gold ("karaoke" look).
                for wi, w in enumerate(group):
                    w_start = g_start if wi == 0 else w["start"]
                    w_end = group[wi + 1]["start"] if wi + 1 < len(group) else g_end
                    if w_end <= w_start:
                        continue
                    parts = [(f"{{\\c{gold_c}}}{t}{{\\c{base_c}}}" if i == wi else t)
                             for i, t in enumerate(texts)]
                    if languages.is_rtl(lang):
                        # libass lays out runs split by override tags left-to-right, so the
                        # word order of right-to-left text must be reversed here (measured).
                        parts.reverse()
                    pop = "{\\fscx108\\fscy108\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
                    event(w_start, w_end, "bold", pos + pop + tag + f"{{\\c{base_c}}}" + joiner.join(parts))
                continue
            lines_ = captions.split_lines(group, lang, 22 if style == "karaoke" else
                                          (26 if style != "minimal" else 30))
            if style == "karaoke":
                # Words fill in as they're spoken (\\kf), the not-yet-sung part in the speaker colour.
                out_lines = []
                t = g_start
                for ln in lines_:
                    parts = []
                    for w in ln:
                        lead = max(0.0, w["start"] - t)
                        pre = f"{{\\k{int(round(lead * 100))}}}" if lead >= 0.02 else ""
                        dur = max(0.05, w["end"] - max(t, w["start"]))
                        parts.append(pre + f"{{\\2c{base_c}\\kf{int(round(dur * 100))}}}" + _ass_escape(w["word"]))
                        t = max(t, w["start"]) + dur
                    out_lines.append(joiner.join(parts))
                event(g_start, g_end, "karaoke", pos + "{\\fad(60,60)}" + tag + "\\N".join(out_lines))
            else:
                text = "\\N".join(joiner.join(_ass_escape(w["word"]) for w in ln) for ln in lines_)
                event(g_start, g_end, style, pos + "{\\fad(80,80)}" + tag + f"{{\\c{base_c}}}" + text)

    if opts.hook and hook_text:
        hook_y = geo.hook_y if geo.hook_y is not None else (120 if layout != "fit" else 330)
        text = _ass_escape(hook_text)
        if rtl:
            text = "‫" + text + "‬"  # keep punctuation on the right side
        event(hook_start, hook_start + min(3.2, duration) + (offset - hook_start) * 0.6, "hook",
              f"{{\\an8\\pos({geo.cap_x},{hook_y})\\fad({hook_fade_in},300)}}{text}", layer=1, shift=False)
    lines += extra or []
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- video


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _filter_graph(layout: str, src_w: int, src_h: int, facecam: Facecam | None,
                  inp: str = "0:v", out: str = "base", size: tuple[int, int] = (OUT_W, OUT_H),
                  fx: dict | None = None) -> str:
    """Layout filter chain from input pad `inp` to output pad `out` (labels are unique per out).
    size: canvas (1080x1920, or 1920x1080 for 16:9 exports, which always use fit / crop).
    fx: extra filters (smart zoom) per picture: "full" (crop / fit), "cam" and "game" (split)."""
    W, H = size
    zfx = fx or {}

    def add(key: str) -> str:
        return f",{zfx[key]}" if zfx.get(key) else ""

    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=bicubic,crop={W}:{H}"
    a, b, bg_, fg_, cam_, game_ = (f"{out}_{x}" for x in ("a", "b", "bg", "fg", "cam", "game"))
    if layout == "crop":
        return f"[{inp}]{cover},setsar=1{add('full')}[{out}]"
    if layout == "fit" and abs(src_w / max(src_h, 1) - W / H) < 0.02:  # same shape: just scale
        return f"[{inp}]scale={W}:{H}:flags=bicubic,setsar=1{add('full')}[{out}]"
    if layout == "fit":
        # Blur at quarter size (fast), then scale back up.
        bg = (f"scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,"
              f"crop={W // 4}:{H // 4},boxblur=12:2,eq=brightness=-0.10:saturation=1.1,"
              f"scale={W}:{H}")
        fg = f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=bicubic{add('full')}"
        return (f"[{inp}]split=2[{a}][{b}];[{a}]{bg}[{bg_}];[{b}]{fg}[{fg_}];"
                f"[{bg_}][{fg_}]overlay=(W-w)/2:(H-h)/2,setsar=1[{out}]")
    assert facecam is not None
    bottom_h = OUT_H - SPLIT_TOP
    # Facecam: cut the region, then center-crop it to the top panel's aspect ratio.
    fx, fy = facecam.x * src_w, facecam.y * src_h
    fw, fh = facecam.w * src_w, facecam.h * src_h
    target = OUT_W / SPLIT_TOP
    if fw / fh > target:  # too wide -> trim the sides
        nw = fh * target
        fx += (fw - nw) / 2
        fw = nw
    else:  # too tall -> trim top/bottom
        nh = fw / target
        fy += (fh - nh) / 2
        fh = nh
    cam = (f"crop={_even(fw)}:{_even(fh)}:{_even(fx)}:{_even(fy)},"
           f"scale={OUT_W}:{SPLIT_TOP}:flags=bicubic")
    # Gameplay: full-height center crop to the bottom panel's aspect ratio, nudged away
    # from the facecam so the camera doesn't show up twice.
    gw = min(src_w, src_h * OUT_W / bottom_h)
    gx = (src_w - gw) / 2
    cam_l, cam_r = facecam.x * src_w, (facecam.x + facecam.w) * src_w
    if cam_r <= src_w / 2 and cam_r > gx:  # facecam on the left
        gx = min(cam_r, src_w - gw) if cam_r - gx < gw * 0.25 else gx
    elif cam_l >= src_w / 2 and cam_l < gx + gw:  # facecam on the right
        gx = max(cam_l - gw, 0) if gx + gw - cam_l < gw * 0.25 else gx
    game = (f"crop={_even(gw)}:{_even(src_h)}:{_even(gx)}:0,"
            f"scale={OUT_W}:{bottom_h}:force_original_aspect_ratio=increase:flags=bicubic,"
            f"crop={OUT_W}:{bottom_h}")
    return (f"[{inp}]split=2[{a}][{b}];[{a}]{cam}{add('cam')}[{cam_}];[{b}]{game}{add('game')}[{game_}];"
            f"[{cam_}][{game_}]vstack=inputs=2,setsar=1[{out}]")


def speaker_names(project: Project) -> dict:
    """Custom speaker names from the voice pass ({} = default "Me" / "Friend" labels)."""
    from . import voices

    return voices.speaker_names(voices.load(project))


def clip_text(project: Project, cand: dict, opts: ClipOptions) -> tuple[list[dict], str | None, str, str | None]:
    """(words relative to the clip start, their language, hook text, hook language)."""
    start, end = float(cand["start"]), float(cand["end"])
    transcript = read_json(project.transcript_path) if project.transcript_path.is_file() else {}
    lang = transcript.get("language")
    translated = (cand.get("translations") or {}).get(opts.subtitle_lang) if opts.subtitle_lang else None
    if translated and opts.subtitle_lang != lang:
        words = translated_words(translated, start, end, opts.subtitle_lang)
        lang = opts.subtitle_lang
    elif transcript:
        from .edit.plan import transcript_words

        # The voice pass's words where it ran (every speaker, "spk"), else the transcript's.
        from .edit import proof

        found, _l = transcript_words(project, start, end)
        found = proof.fix_words(found, lang, proof.cached_fixes(project, cand.get("id")))
        words =[{"start": max(0.0, w["start"] - start), "end": min(end - start, w["end"] - start),
                  "word": w["word"], **({"spk": w["spk"]} if w.get("spk") else {})} for w in found]
    else:
        words = []
    publish = cand.get("publish") or {}
    hook_text = opts.hook_text or publish.get("hook_text") or first_sentence(cand.get("text") or "")
    # The hook text's language decides its direction (Arabic hook = right-to-left).
    hook_lang = publish.get("language") if (publish.get("hook_text") and not opts.hook_text) else lang
    return words, lang, hook_text, hook_lang


def bitrate_args(enc: Encoder, kbps: int) -> tuple[str, ...]:
    """Target-bitrate settings (platform presets) instead of the encoder's constant quality."""
    b, mx, buf = f"{kbps}k", f"{int(kbps * 1.5)}k", f"{kbps * 2}k"
    name = enc.name
    if name.endswith("_nvenc"):
        return ("-preset", "p5", "-tune", "hq", "-rc", "vbr", "-b:v", b, "-maxrate", mx, "-bufsize", buf)
    if name.endswith("_videotoolbox"):
        return ("-b:v", b, "-maxrate", mx, "-allow_sw", "0")
    if name.endswith("_qsv"):
        return ("-preset", "faster", "-b:v", b, "-maxrate", mx, "-bufsize", buf)
    if name.endswith("_amf"):
        return ("-quality", "speed", "-rc", "vbr_peak", "-b:v", b, "-maxrate", mx)
    if name == "libvpx-vp9":
        return ("-deadline", "good", "-cpu-used", "4", "-row-mt", "1", "-b:v", b, "-maxrate", mx, "-bufsize", buf)
    preset = "fast" if name == "libx265" else "veryfast"
    return ("-preset", preset, "-b:v", b, "-maxrate", mx, "-bufsize", buf)


def video_args(enc: Encoder, spec: OutputSpec) -> list[str]:
    args = ["-c:v", enc.name, *(bitrate_args(enc, spec.bitrate_k) if spec.bitrate_k else enc.args)]
    if spec.codec == "hevc" and spec.container in ("mp4", "mov"):
        args += ["-tag:v", "hvc1"]  # plays on Apple devices / QuickTime
    return args


def render_clip(project: Project, cand: dict, opts: ClipOptions, facecam: Facecam | None,
                dest: Path, on_progress: Callable[[float], None] | None = None,
                spec: OutputSpec | None = None) -> RenderResult:
    """Render one clip. Without `spec`: the 1080x1920 H.264 MP4 of the Clips tab."""
    from .render import cpu_fallback, pick_codec

    ffmpeg = require_tool("ffmpeg")
    source = project.source_path
    if source is None:
        raise SharkyClipsError("The project's source video is missing.",
                               "Re-run: python cli.py ingest <url-or-path>")
    spec = spec or OutputSpec()
    meta = project.load_meta()
    src_w, src_h = int(meta.get("width") or 1920), int(meta.get("height") or 1080)
    fps = float(meta.get("fps") or 30)
    start, end = float(cand["start"]), float(cand["end"])
    duration = max(0.5, end - start)

    if not spec.burn_captions:
        opts = ClipOptions.from_dict({**opts.to_dict(), "subtitles": "none"})
    words, lang, hook_text, hook_lang = clip_text(project, cand, opts)
    canvas = spec.canvas
    wide = spec.frame == "wide"
    # 16:9: the whole picture (fit), or filled (crop) - never the facecam split.
    layout = ("crop" if opts.layout == "crop" else "fit") if wide else resolve_layout(opts.layout, facecam)
    geo = Geometry.for_spec(spec, layout)
    has_audio = (bool(meta.get("audio_codec")) or meta.get("audio_codec") is None) and spec.audio != "none"

    # Hook flash: ~1 s around the peak, shown first (never in a seamless loop: it would repeat).
    flash = FLASH_SECONDS if opts.hook_flash and not opts.loop else 0.0
    src_dur = float(meta.get("duration") or end)
    peak = float(cand.get("peak") or (start + end) / 2)
    flash_start = flash_from(peak, src_dur, fps)
    plan = edit_plan(project, cand, opts, spec, max(1, round(min(60.0, fps, float(spec.fps or 60)))))
    if plan is not None:  # editing tools at work: cuts, bleeps, zoom, music, brand kit
        return _render_planned(project, cand, opts, facecam, dest, on_progress, spec, plan, layout=layout,
                               geo=geo, has_audio=has_audio, flash=flash, flash_start=flash_start,
                               src_w=src_w, src_h=src_h, fps=fps)
    ass = build_ass(words, duration, opts, layout, lang, hook_text, offset=flash, hook_lang=hook_lang, geo=geo,
                    speakers=speaker_names(project))

    out_fps = min(60.0, fps, float(spec.fps or 60))
    fps_i = max(1, round(out_fps))
    # Final picture size (after the text is drawn on the canvas).
    final = ""
    if spec.width and spec.height and (spec.width, spec.height) != canvas:
        final = f",scale={spec.width}:{spec.height}:flags=lanczos"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".partial" + dest.suffix)
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-"))
    try:
        # Relative file name + cwd: avoids ffmpeg filter escaping of Windows paths.
        (work / "subs.ass").write_text(ass, encoding="utf-8")
        rate = ["-r", f"{out_fps:g}"] if fps > out_fps + 1 else []
        total = duration + flash
        fade_out = max(0.0, total - 0.2)
        src = str(source.resolve())
        W, H = canvas
        if flash:
            # [1] = flash (slight punch-in zoom), [0] = the clip, which starts with a white flash.
            punch = (f"scale={int(W * 1.08) // 2 * 2}:{int(H * 1.08) // 2 * 2},"
                     f"crop={W}:{H}")
            graph = (_filter_graph(layout, src_w, src_h, facecam, "1:v", "fl", canvas) + ";"
                     + _filter_graph(layout, src_w, src_h, facecam, "0:v", "main", canvas) + ";"
                     f"[fl]{punch},setsar=1,fps={min(60, fps_i)},format=yuv420p[flv];"
                     f"[main]fade=t=in:st=0:d=0.18:color=white,setsar=1,fps={min(60, fps_i)},format=yuv420p[mainv];")
            if has_audio:
                graph += (f"[1:a]aresample=48000,afade=t=in:d=0.05,afade=t=out:st={flash - 0.12:.3f}:d=0.12[fla];"
                          f"[0:a]aresample=48000[maina];"
                          f"[flv][fla][mainv][maina]concat=n=2:v=1:a=1[cv][ca];"
                          f"[ca]afade=t=out:st={fade_out:.3f}:d=0.2[a];")
            else:
                graph += "[flv][mainv]concat=n=2:v=1:a=0[cv];"
            graph += f"[cv]ass=subs.ass{final},format=yuv420p[v]"
            inputs = ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", src,
                      "-ss", f"{flash_start:.3f}", "-t", f"{flash:.3f}", "-i", src]
            maps = ["-map", "[v]"] + (["-map", "[a]"] if has_audio else [])
            audio_filter: list[str] = []
        else:
            graph = (_filter_graph(layout, src_w, src_h, facecam, size=canvas)
                     + f";[base]ass=subs.ass{final},format=yuv420p[v]")
            inputs = ["-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", src]
            maps = ["-map", "[v]"] + (["-map", "0:a:0?"] if has_audio else [])
            audio_filter = ["-af", f"afade=t=in:d=0.12,afade=t=out:st={fade_out:.3f}:d=0.2"] if has_audio else []
        if has_audio:
            acodec = ["-c:a", "libopus", "-b:a", f"{spec.audio_k}k"] if spec.audio == "opus" else \
                ["-c:a", "aac", "-b:a", f"{spec.audio_k}k"]
            audio_args = [*acodec, *audio_filter]
        else:
            audio_args = ["-an"]
        mux = ["-f", "webm"] if spec.container == "webm" else \
            ["-f", "mov" if spec.container == "mov" else "mp4", "-movflags", "+faststart"]

        def build(e: Encoder) -> list[str]:
            return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", *inputs,
                    "-filter_complex", graph, *maps, *rate, *video_args(e, spec), *audio_args,
                    *mux, "-progress", "pipe:1", str(tmp.resolve())]

        enc = pick_codec(spec.codec)
        if enc is None:
            raise SharkyClipsError(f"This computer can't encode {spec.codec.upper()} video.",
                                   "Pick another format (MP4 H.264 works everywhere).")
        t0 = time.perf_counter()
        code, err = run_ffmpeg(build(enc), total, on_progress, cwd=work)
        fallback = cpu_fallback(spec.codec)
        if code != 0 and enc.hardware and fallback is not None:  # e.g. GPU busy: retry on the CPU
            enc = fallback
            code, err = run_ffmpeg(build(enc), total, on_progress, cwd=work)
        if code != 0:
            tmp.unlink(missing_ok=True)
            raise SharkyClipsError(f"ffmpeg could not render the clip: {err.strip()[-500:]}")
        replace_retry(tmp, dest)
        return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, enc.label)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------- editing tools (1.2.4)


def edit_plan(project: Project, cand: dict, opts: ClipOptions, spec: OutputSpec | None, fps: int):
    """The clip's EditPlan when an editing tool changes something, else None (plain render)."""
    from .edit import plan as plan_mod

    spec = spec or OutputSpec()
    plan = plan_mod.build(project, cand, opts, vertical=spec.frame != "wide", fps=fps, max_len=spec.max_seconds)
    return plan if plan.active else None


def loop_hook_line(hook_text: str, geo: Geometry, layout: str, total: float, rtl: bool) -> str:
    """In a seamless loop the hook text is also on screen for the last moment, so it is
    already there when the clip starts over (no pop at the seam)."""
    hook_y = geo.hook_y if geo.hook_y is not None else (120 if layout != "fit" else 330)
    text = _ass_escape(hook_text)
    if rtl:
        text = "\u202b" + text + "\u202c"
    a = max(0.0, total - 0.8)
    return (f"Dialogue: 1,{_ass_time(a)},{_ass_time(total + 0.05)},hook,,0,0,0,,"
            f"{{\\an8\\pos({geo.cap_x},{hook_y})\\fad(300,0)}}{text}")


def _logo_size(path: Path) -> tuple[int, int]:
    import cv2
    import numpy as np

    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        return 1, 1
    return int(img.shape[1]), int(img.shape[0])


def _brand_layers(preset: dict, geo: Geometry, spec: OutputSpec, canvas: tuple[int, int], lead: float,
                  main_end: float, total: float, intro: float, outro: float) -> tuple[dict, list[str]]:
    """Watermark placement + the ASS lines for the handle and the intro / outro cards."""
    from .edit import brand

    W, H = canvas
    top, right, bottom, left = spec.safe
    m = 40
    logo = brand.logo_path(preset)
    info: dict = {"logo": logo}
    lw = lh = 0
    if logo is not None:
        iw, ih = _logo_size(logo)
        lw = _even(W * float(preset["logo_size"]) / 100)
        lh = _even(lw * ih / max(1, iw))
        pos = preset["logo_pos"]
        x = m + left if pos in ("tl", "bl") else W - lw - m - right
        y = m + top if pos in ("tl", "tr") else H - lh - m - bottom
        info.update(w=lw, h=lh, x=x, y=y)
    lines = []

    def ev(a: float, b: float, style: str, text: str) -> None:
        lines.append(f"Dialogue: 2,{_ass_time(a)},{_ass_time(b)},{style},,0,0,0,,{text}")

    handle = f"@{preset['handle']}" if preset.get("handle") else ""
    if handle and preset.get("show_handle"):
        pos = preset["logo_pos"]
        an = {"tl": 7, "tr": 9, "bl": 1, "br": 3}[pos]
        hx = m + left if pos in ("tl", "bl") else W - m - right
        hy = (m + top + lh + (10 if lh else 0)) if pos in ("tl", "tr") else (H - m - bottom - lh - (10 if lh else 0))
        ev(lead, main_end, "handle", f"{{\\an{an}\\pos({hx},{hy})}}{_ass_escape(handle)}")
    card_y = int(H * (0.64 if logo is not None else 0.5))
    if intro:
        text = brand.intro_text(preset)
        if text:
            ev(0.0, intro, "card", f"{{\\an5\\pos({W // 2},{card_y})\\fad(200,250)}}{_ass_escape(text)}")
    if outro:
        text = brand.outro_text(preset)
        if text:
            ev(total - outro, total, "card", f"{{\\an5\\pos({W // 2},{card_y})\\fad(250,200)}}{_ass_escape(text)}")
    return info, lines


def _fx_video(g: list[str], fxp, fx_in: list[int], layout: str, src_w: int, src_h: int,
              facecam: Facecam | None, size: tuple[int, int], F: int, main_frames: int) -> str:
    """Effects on the main picture: shakes, then the replays / freeze frames spliced in.
    Returns the pad that carries the result."""
    from .edit import fx as fx_mod

    cur = "mainv"
    sh = fx_mod.shake_filter(fxp.shakes, fxp.punches, F)
    if sh:
        g.append(f"[mainv]{sh}[mainsh]")
        cur = "mainsh"
    if not fxp.inserts:
        return f"[{cur}]"
    split = layout == "split"
    pieces: list[tuple[str, str]] = []  # ("main", "fa:fb") or ("ins", label)
    prev = 0
    for k, ins in enumerate(fxp.inserts):
        fr = min(main_frames, round(ins.at * F))
        if fr > prev:
            pieces.append(("main", f"{prev}:{fr}"))
        prev = max(prev, fr)
        lbl = f"fxi{k}"
        n_out = max(1, round(ins.dur * F))
        if ins.kind == "replay":
            n_src = max(1, round((ins.src_end - ins.src) * F))
            g.append(f"[{fx_in[k]}:v]{fx_mod.slowmo_chain(F, n_src, n_out, fxp.smooth, (src_w, src_h))}[{lbl}s]")
            z = fx_mod.zoom_filter(fx_mod.zoom_expr(1.06, 1.16, n_out), 0.5)
            g.append(_filter_graph(layout, src_w, src_h, facecam, f"{lbl}s", f"{lbl}b", size,
                                   fx={"game": z} if split else {"full": z}))
            g.append(f"[{lbl}b]setsar=1,eq=saturation=0.86:contrast=1.06,vignette=PI/5,format=yuv420p[{lbl}]")
        else:
            g.append(f"[{fx_in[k]}:v]fps={F},trim=end_frame=1,setpts=N/({F}*TB)[{lbl}s]")
            g.append(_filter_graph(layout, src_w, src_h, facecam, f"{lbl}s", f"{lbl}b", size))
            z = fx_mod.zoom_filter(fx_mod.zoom_expr(1.0, 1.2, max(2, round(n_out * 0.6)), "out"), 0.5)
            g.append(f"[{lbl}b]loop=loop={n_out - 1}:size=1:start=0,setpts=N/({F}*TB),{z},"
                     f"fade=t=in:st=0:d=0.06:color=white,setsar=1,format=yuv420p[{lbl}]")
        pieces.append(("ins", lbl))
    if main_frames > prev:
        pieces.append(("main", f"{prev}:{main_frames}"))
    mains = [p for p in pieces if p[0] == "main"]
    if len(mains) > 1:
        g.append(f"[{cur}]split={len(mains)}" + "".join(f"[fxm{k}]" for k in range(len(mains))))
        src_pads = [f"fxm{k}" for k in range(len(mains))]
    elif mains:
        src_pads = [cur]
    else:
        src_pads = []
        g.append(f"[{cur}]nullsink")
    seq = []
    mi = 0
    for kind, val in pieces:
        if kind == "main":
            fa, fb = val.split(":")
            g.append(f"[{src_pads[mi]}]trim=start_frame={fa}:end_frame={fb},setpts=PTS-STARTPTS[fxs{mi}]")
            seq.append(f"[fxs{mi}]")
            mi += 1
        else:
            seq.append(f"[{val}]")
    if len(seq) == 1:
        return seq[0]
    g.append("".join(seq) + f"concat=n={len(seq)}:v=1:a=0[mainfx]")
    return "[mainfx]"


def _render_planned(project: Project, cand: dict, opts: ClipOptions, facecam: Facecam | None, dest: Path,
                    on_progress: Callable[[float], None] | None, spec: OutputSpec, plan, *, layout: str,
                    geo: Geometry, has_audio: bool, flash: float, flash_start: float, src_w: int, src_h: int,
                    fps: float) -> RenderResult:
    """Render with an EditPlan: frame-accurate cuts, smart zoom, the numpy sound mix (bleeps,
    music, crossfades), brand watermark / handle / caption style and intro / outro cards."""
    from .edit import audiomix, zoom
    from .render import cpu_fallback, pick_codec

    ffmpeg = require_tool("ffmpeg")
    source = project.source_path
    start, end = plan.start, plan.end  # the plan may move them (seamless loop)
    duration = max(0.5, end - start)
    F = int(plan.fps)
    W, H = spec.canvas
    fxp = plan.fx  # instant replay / meme effects / chat bubbles (edit/fx.py)
    main = plan.out_duration + (fxp.extra if fxp is not None else 0.0)
    intro, outro = plan.intro_s, plan.outro_s
    lead = intro + flash
    total = lead + main + outro

    # Text: captions in output time (translated subtitles too), hook after the intro card.
    words, lang, hook_text, hook_lang = clip_text(project, {**cand, "start": start, "end": end}, opts)
    seam = plan.loop
    if seam is not None and seam.hook_text and not opts.hook_text:  # the AI's loop hook
        hook_text, hook_lang = seam.hook_text, (cand.get("publish") or {}).get("language") or lang
    if opts.subtitle_lang and lang == opts.subtitle_lang and lang != plan.lang:
        mapped = []
        for w in words:  # translated pseudo-words (relative to the clip start)
            s0, e0 = plan.to_out(w["start"] + start, "fwd"), plan.to_out(w["end"] + start, "back")
            if s0 is not None and e0 is not None and e0 > s0:
                mapped.append({**w, "start": s0, "end": e0})
        words = mapped
    else:
        words = plan.out_words()
    if fxp is not None:
        from .edit import fx as fx_mod

        words = fx_mod.map_words(words, fxp)
    style = None
    extra: list[str] = []
    brand_info: dict = {}
    if plan.brand:
        p = plan.brand
        style = {"font": p.get("caption_font"), "primary": p.get("caption_color"),
                 "highlight": p.get("caption_highlight"), "outline": p.get("caption_outline")}
        brand_info, extra = _brand_layers(p, geo, spec, (W, H), lead, lead + main, total, intro, outro)
    if not spec.burn_captions:
        opts = ClipOptions.from_dict({**opts.to_dict(), "subtitles": "none"})
    if seam is not None and opts.hook and hook_text:
        extra = extra + [loop_hook_line(hook_text, geo, layout, total, languages.is_rtl(hook_lang or lang))]
    fx_styles: list[str] = []
    pauses: list[tuple[float, float]] = []
    if fxp is not None:
        zone = fx_mod.bubble_zone(geo, layout, spec.safe, spec.frame == "wide")
        extra = extra + fx_mod.ass_lines(fxp, lead, geo, layout, _ass_time, lang, zone)
        fx_styles = fx_mod.ass_styles(lang, geo.scale)
        pauses = [(a + lead, b + lead) for a, b, _i in fxp.insert_ranges()]
    ass = build_ass(words, main, opts, layout, lang, hook_text, offset=lead, hook_lang=hook_lang, geo=geo,
                    style=style, hook_start=intro, extra=extra, hook_fade_in=0 if seam is not None else 150,
                    speakers=plan.speakers, extra_styles=fx_styles, pauses=pauses)

    final = ""
    if spec.width and spec.height and (spec.width, spec.height) != (W, H):
        final = f",scale={spec.width}:{spec.height}:flags=lanczos"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".partial" + dest.suffix)
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-"))
    try:
        (work / "subs.ass").write_text(ass, encoding="utf-8")
        src = str(source.resolve())
        mix = None
        if (has_audio or plan.music) and spec.audio != "none":
            mix = audiomix.build(source, plan, work / "mix.wav", has_audio=has_audio,
                                 flash=(flash_start, flash) if flash else None)

        inputs = ["-ss", seek_at(start, fps), "-t", f"{duration + 0.05:.3f}", "-i", src]
        n_in = 1
        fl_i = logo_i = in_i = out_i = a_i = None
        if flash:
            inputs += ["-ss", seek_at(flash_start, fps), "-t", f"{flash + 0.1:.3f}", "-i", src]
            fl_i, n_in = n_in, n_in + 1
        if brand_info.get("logo") is not None:
            inputs += ["-i", str(brand_info["logo"])]
            logo_i, n_in = n_in, n_in + 1
        card = (plan.brand or {}).get("card_color", "#0E1A33").lstrip("#")
        if intro:
            inputs += ["-f", "lavfi", "-i", f"color=c=0x{card}:s={W}x{H}:r={F}:d={intro:.3f}"]
            in_i, n_in = n_in, n_in + 1
        if outro:
            inputs += ["-f", "lavfi", "-i", f"color=c=0x{card}:s={W}x{H}:r={F}:d={outro:.3f}"]
            out_i, n_in = n_in, n_in + 1
        if mix is not None:
            inputs += ["-i", "mix.wav"]
            a_i, n_in = n_in, n_in + 1
        tail_i = None
        tail_frames = 0
        if seam is not None and seam.tail_ok and seam.video_xfade > 0:
            # The picture right after the end point: it dissolves into the first frames.
            tail_frames = max(2, round(seam.video_xfade * F))
            tail_at = start + plan.frames()[-1][1] / F
            inputs += ["-ss", seek_at(tail_at, fps), "-t", f"{tail_frames / F + 0.2:.3f}", "-i", src]
            tail_i, n_in = n_in, n_in + 1
        fx_in: list[int] = []
        for ins in (fxp.inserts if fxp is not None else []):
            if ins.kind == "replay":
                inputs += ["-ss", seek_at(ins.src, fps), "-t", f"{ins.src_end - ins.src + 0.2:.3f}", "-i", src]
            else:
                inputs += ["-ss", seek_at(ins.src, fps), "-t", "0.4", "-i", src]
            fx_in.append(n_in)
            n_in += 1

        g: list[str] = []
        sel = ""
        if plan.cuts:
            expr = "+".join(f"between(n,{fa},{fb - 1})" for fa, fb in plan.frames())
            sel = f"select='{expr}',"
        main_frames = sum(fb - fa for fa, fb in plan.frames())
        g.append(f"[0:v]fps={F},{sel}setpts=N/({F}*TB),trim=end_frame={main_frames}[src]")
        fx: dict = {}
        if plan.zooms:
            z = plan.zoom_level
            if layout == "split":
                fx["game"] = zoom.perspective_filter(plan.out_pulses("scene"), z, F)
                fx["cam"] = zoom.perspective_filter(plan.out_pulses("cam"), z, F, cy=0.45)
            else:
                from .edit.plan import merge

                fx["full"] = zoom.perspective_filter(merge(plan.out_pulses("scene") + plan.out_pulses("cam")), z, F)
        g.append(_filter_graph(layout, src_w, src_h, facecam, "src", "base", (W, H), fx=fx))
        white = ",fade=t=in:st=0:d=0.18:color=white" if flash else ""
        if tail_i is not None:
            g.append("[base]setsar=1,format=yuv420p[mainv0]")
            g.append(f"[{tail_i}:v]fps={F},trim=end_frame={tail_frames},setpts=N/({F}*TB)[tlsrc]")
            g.append(_filter_graph(layout, src_w, src_h, facecam, "tlsrc", "tlb", (W, H)))
            g.append("[tlb]setsar=1,format=yuv420p[tlv]")
            g.append(f"[tlv][mainv0]xfade=transition=fade:duration={tail_frames / F:.4f}:offset=0[mainv]")
        else:
            g.append(f"[base]setsar=1{white},format=yuv420p[mainv]")
        main_pad = "[mainv]"
        if fxp is not None:
            main_pad = _fx_video(g, fxp, fx_in, layout, src_w, src_h, facecam, (W, H), F, main_frames)
        logos: list[str] = []
        if logo_i is not None:
            n_logo = 1 + bool(intro) + bool(outro)
            logos = [f"lg{k}" for k in range(n_logo)]
            g.append(f"[{logo_i}:v]format=rgba,split={n_logo}" + "".join(f"[{x}]" for x in logos))
        seq = []

        def card_chain(idx: int, name: str, d: float, logo_pad: str | None) -> None:
            base = f"[{idx}:v]trim=end_frame={round(d * F)},format=yuv420p,setsar=1"
            if logo_pad:
                cw = _even(W * 0.36)
                g.append(f"[{logo_pad}]scale={cw}:-2[{name}_l]")
                g.append(f"{base}[{name}_b];[{name}_b][{name}_l]overlay=(W-w)/2:(H-h)/2-{int(H * 0.06)}[{name}_c]")
                base = f"[{name}_c]"
            g.append(f"{base}{'' if logo_pad else ','}fade=t=in:st=0:d=0.25,fade=t=out:st={max(0.0, d - 0.3):.3f}:d=0.3,"
                     f"format=yuv420p,setsar=1[{name}]")

        if intro:
            card_chain(in_i, "introv", intro, logos[1] if logos else None)
            seq.append("[introv]")
        if flash:
            punch = f"scale={int(W * 1.08) // 2 * 2}:{int(H * 1.08) // 2 * 2},crop={W}:{H}"
            g.append(_filter_graph(layout, src_w, src_h, facecam, f"{fl_i}:v", "fl", (W, H)))
            g.append(f"[fl]{punch},setsar=1,fps={F},trim=end_frame={round(flash * F)},setpts=N/({F}*TB),"
                     f"format=yuv420p[flv]")
            seq.append("[flv]")
        seq.append(main_pad)
        if outro:
            card_chain(out_i, "outrov", outro, logos[-1] if logos else None)
            seq.append("[outrov]")
        if len(seq) > 1:
            g.append("".join(seq) + f"concat=n={len(seq)}:v=1:a=0[cv]")
        else:
            g.append(f"{main_pad}null[cv]")
        g.append("[cv]ass=subs.ass[sv]")
        last = "sv"
        if logos:
            op = float(plan.brand["logo_opacity"])
            g.append(f"[{logos[0]}]scale={brand_info['w']}:{brand_info['h']},colorchannelmixer=aa={op:.2f}[wm]")
            g.append(f"[sv][wm]overlay=x={brand_info['x']}:y={brand_info['y']}:"
                     f"enable='between(t,{lead:.3f},{lead + main:.3f})'[wv]")
            last = "wv"
        g.append(f"[{last}]null{final},format=yuv420p[v]")
        graph = ";".join(g)

        maps = ["-map", "[v]"] + (["-map", f"{a_i}:a"] if a_i is not None else [])
        if a_i is not None and spec.audio != "none":
            audio_args = ["-c:a", "libopus", "-b:a", f"{spec.audio_k}k"] if spec.audio == "opus" else \
                ["-c:a", "aac", "-b:a", f"{spec.audio_k}k"]
        else:
            maps = ["-map", "[v]"]
            audio_args = ["-an"]
        mux = ["-f", "webm"] if spec.container == "webm" else \
            ["-f", "mov" if spec.container == "mov" else "mp4", "-movflags", "+faststart"]

        def build(e: Encoder) -> list[str]:
            return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", *inputs,
                    "-filter_complex", graph, *maps, *video_args(e, spec), *audio_args,
                    "-t", f"{total:.3f}", *mux, "-progress", "pipe:1", str(tmp.resolve())]

        ref = duration + flash  # callers measure progress against the clip (+ flash)

        def progress(sec: float) -> None:
            if on_progress:
                on_progress(min(ref, sec * ref / max(total, 0.1)))

        enc = pick_codec(spec.codec)
        if enc is None:
            raise SharkyClipsError(f"This computer can't encode {spec.codec.upper()} video.",
                                   "Pick another format (MP4 H.264 works everywhere).")
        t0 = time.perf_counter()
        code, err = run_ffmpeg(build(enc), total, progress, cwd=work)
        fallback = cpu_fallback(spec.codec)
        if code != 0 and enc.hardware and fallback is not None:
            enc = fallback
            code, err = run_ffmpeg(build(enc), total, progress, cwd=work)
        if code != 0:
            tmp.unlink(missing_ok=True)
            raise SharkyClipsError(f"ffmpeg could not render the clip: {err.strip()[-500:]}")
        replace_retry(tmp, dest)
        info = {"plan": plan.fingerprint(), "duration": round(total, 2), "main": round(main, 2),
                "cut_seconds": max(0.0, round(duration - main, 2)), "cuts": len(plan.removed),
                "bleeps": len(plan.bleeps) if plan.bleep_mode != "off" else 0, "bleep_mode": plan.bleep_mode,
                "zoom_pulses": len(plan.out_pulses("scene")) + len(plan.out_pulses("cam")) if plan.zooms else 0,
                "music": mix.music if mix else None, "lufs": mix.lufs if mix else None,
                "brand": (plan.brand or {}).get("name"), "intro": intro, "outro": outro}
        if fxp is not None:
            info["fx"] = {"replays": sum(i.kind == "replay" for i in fxp.inserts),
                          "freezes": sum(i.kind == "freeze" for i in fxp.inserts),
                          "shakes": len(fxp.shakes) + len(fxp.punches), "bubbles": len(fxp.bubbles),
                          "smooth": fxp.smooth, "extra": round(fxp.extra, 2),
                          "inserts": [{**i.to_dict(), "at_out": round(lead + fxp.final(i.at, end=True), 3)}
                                      for i in fxp.inserts]}
        if seam is not None:
            from .edit import loop as loop_mod

            # The picture band without text: the gameplay part of a split, else between hook and captions.
            rows = (0.46, 0.97) if layout == "split" else (0.27, 0.66)
            info["loop"] = {**seam.to_dict(), "duration": round(total, 2),
                            "audio_seam": mix.seam if mix is not None else None,
                            "file_audio_seam": loop_mod.measure(dest) if mix is not None else None,
                            "video_seam": loop_mod.video_seam(dest, rows), "dissolve": tail_i is not None}
        return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, enc.label, info)
    finally:
        shutil.rmtree(work, ignore_errors=True)
