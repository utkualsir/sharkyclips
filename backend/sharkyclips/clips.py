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

import os
import platform
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import languages
from .errors import SharkyClipsError, require_tool
from .project import Project, read_json
from .render import Encoder, RenderResult, run_ffmpeg

OUT_W, OUT_H = 1080, 1920
SPLIT_TOP = 768  # facecam height in the split layout (40%)
LAYOUTS = ("auto", "split", "fit", "crop")
SUBTITLE_STYLES = ("bold", "clean", "minimal", "none")
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

    @classmethod
    def from_dict(cls, data: dict | None) -> "ClipOptions":
        data = data or {}
        keys = ("layout", "subtitles", "hook", "hook_text", "hook_flash", "subtitle_lang")
        opts = cls(**{k: data[k] for k in keys if k in data})
        opts.hook_flash = bool(opts.hook_flash)
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
              hook_lang: str | None = None, geo: Geometry | None = None) -> str:
    """offset: seconds of hook flash before the clip (subtitles start after it).
    geo: canvas size and text positions (default: the 1080x1920 clip)."""
    geo = geo or Geometry()
    font = _font_for(lang)
    rtl = languages.is_rtl(hook_lang or lang)
    # Caption line position (center of the text block)
    cap_y = geo.cap_y if geo.cap_y is not None else (SPLIT_TOP if layout == "split" else 1390)

    def sz(v: float) -> int:
        return max(1, int(round(v * geo.scale)))

    styles = {
        # name: size, primary, outline colour, back colour, bold, border style, outline, shadow
        "bold": (sz(86), WHITE, BLACK, "&H80000000", -1, 1, sz(7), sz(2)),
        "clean": (sz(62), WHITE, "&H50000000", "&H00000000", -1, 3, sz(14), 0),
        "minimal": (sz(56), WHITE, "&H70000000", "&HA0000000", 0, 1, sz(2), sz(3)),
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
        lines.append(f"Style: {name},{font},{size},{prim},{GOLD},{outl},{back},{bold},0,0,0,"
                     f"100,100,0,0,{border},{outline},{shadow},5,{geo.margin_l},{geo.margin_r},0,1")
    lines.append(f"Style: hook,{font},{sz(64)},{NAVY},{NAVY},{WHITE},&H40000000,-1,0,0,0,"
                 f"100,100,0,0,3,{sz(22)},0,8,{geo.margin_l + 20},{geo.margin_r + 20},0,1")
    lines += ["", "[Events]",
              "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]

    def event(start: float, end: float, style: str, text: str, layer: int = 0, shift: bool = True) -> None:
        if shift:
            start, end = start + offset, end + offset
        lines.append(f"Dialogue: {layer},{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{text}")

    if opts.subtitles != "none" and words:
        style = opts.subtitles
        if style == "bold":
            groups = group_words(words, 16, 3, lang)
        else:
            groups = group_words(words, 30, 7, lang)
        joiner = "" if lang in NO_SPACE_LANGS else " "
        pos = f"{{\\an5\\pos({geo.cap_x},{cap_y})}}"
        for gi, group in enumerate(groups):
            g_start = group[0]["start"]
            nxt = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else duration
            g_end = min(max(group[-1]["end"] + 0.35, g_start + 0.4), nxt, duration)
            texts = [_ass_escape(_upper(w["word"], lang) if style == "bold" else w["word"])
                     for w in group]
            if style == "bold":
                # One event per word: the word being spoken is gold ("karaoke" look).
                for wi, w in enumerate(group):
                    w_start = g_start if wi == 0 else w["start"]
                    w_end = group[wi + 1]["start"] if wi + 1 < len(group) else g_end
                    if w_end <= w_start:
                        continue
                    parts = [(f"{{\\c{GOLD}}}{t}{{\\c{WHITE}}}" if i == wi else t)
                             for i, t in enumerate(texts)]
                    if languages.is_rtl(lang):
                        # libass lays out runs split by override tags left-to-right, so the
                        # word order of right-to-left text must be reversed here (measured).
                        parts.reverse()
                    pop ="{\\fscx108\\fscy108\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
                    event(w_start, w_end, "bold", pos + pop + joiner.join(parts))
            else:
                event(g_start, g_end, style, pos + "{\\fad(80,80)}" + joiner.join(texts))

    if opts.hook and hook_text:
        hook_y = geo.hook_y if geo.hook_y is not None else (120 if layout != "fit" else 330)
        text = _ass_escape(hook_text)
        if rtl:
            text = "‫" + text + "‬"  # keep punctuation on the right side
        event(0.0, min(3.2, duration) + offset * 0.6, "hook",
              f"{{\\an8\\pos({geo.cap_x},{hook_y})\\fad(150,300)}}{text}", layer=1, shift=False)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- video


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _filter_graph(layout: str, src_w: int, src_h: int, facecam: Facecam | None,
                  inp: str = "0:v", out: str = "base", size: tuple[int, int] = (OUT_W, OUT_H)) -> str:
    """Layout filter chain from input pad `inp` to output pad `out` (labels are unique per out).
    size: canvas (1080x1920, or 1920x1080 for 16:9 exports, which always use fit / crop)."""
    W, H = size
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=bicubic,crop={W}:{H}"
    a, b, bg_, fg_, cam_, game_ = (f"{out}_{x}" for x in ("a", "b", "bg", "fg", "cam", "game"))
    if layout == "crop":
        return f"[{inp}]{cover},setsar=1[{out}]"
    if layout == "fit" and abs(src_w / max(src_h, 1) - W / H) < 0.02:  # same shape: just scale
        return f"[{inp}]scale={W}:{H}:flags=bicubic,setsar=1[{out}]"
    if layout == "fit":
        # Blur at quarter size (fast), then scale back up.
        bg = (f"scale={W // 4}:{H // 4}:force_original_aspect_ratio=increase,"
              f"crop={W // 4}:{H // 4},boxblur=12:2,eq=brightness=-0.10:saturation=1.1,"
              f"scale={W}:{H}")
        fg = f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=bicubic"
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
    return (f"[{inp}]split=2[{a}][{b}];[{a}]{cam}[{cam_}];[{b}]{game}[{game_}];"
            f"[{cam_}][{game_}]vstack=inputs=2,setsar=1[{out}]")


def clip_text(project: Project, cand: dict, opts: ClipOptions) -> tuple[list[dict], str | None, str, str | None]:
    """(words relative to the clip start, their language, hook text, hook language)."""
    start, end = float(cand["start"]), float(cand["end"])
    transcript = read_json(project.transcript_path) if project.transcript_path.is_file() else {}
    lang = transcript.get("language")
    translated = (cand.get("translations") or {}).get(opts.subtitle_lang) if opts.subtitle_lang else None
    if translated and opts.subtitle_lang != lang:
        words = translated_words(translated, start, end, opts.subtitle_lang)
        lang = opts.subtitle_lang
    else:
        words = clip_words(transcript, start, end) if transcript else []
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

    # Hook flash: ~1 s around the peak, shown first.
    flash = FLASH_SECONDS if opts.hook_flash else 0.0
    src_dur = float(meta.get("duration") or end)
    peak = float(cand.get("peak") or (start + end) / 2)
    flash_start = min(max(0.0, peak - 0.45), max(0.0, src_dur - FLASH_SECONDS))
    ass = build_ass(words, duration, opts, layout, lang, hook_text, offset=flash, hook_lang=hook_lang, geo=geo)

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
        os.replace(tmp, dest)
        return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, enc.label)
    finally:
        shutil.rmtree(work, ignore_errors=True)
