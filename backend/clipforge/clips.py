"""Vertical 9:16 clip rendering: layout + burned-in subtitles + hook text.

Layouts (output is always 1080x1920):
  split  facecam on top (40%), gameplay below - needs a facecam region
  fit    whole frame in the middle, blurred copy of it as the background
  crop   fill the frame (center crop)
  auto   split when the project has a facecam region, else fit

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
from .errors import ClipForgeError, require_tool
from .project import Project, read_json
from .render import ENCODERS, RenderResult, pick_encoder, run_ffmpeg

OUT_W, OUT_H = 1080, 1920
SPLIT_TOP = 768  # facecam height in the split layout (40%)
LAYOUTS = ("auto", "split", "fit", "crop")
SUBTITLE_STYLES = ("bold", "clean", "minimal", "none")
NO_SPACE_LANGS = {"zh", "ja"}

GOLD = "&H006AB5D9"  # #D9B56A as ASS &HAABBGGRR
WHITE = "&H00FFFFFF"
NAVY = "&H00331A0E"  # #0E1A33
BLACK = "&H00000000"


@dataclass
class ClipOptions:
    layout: str = "auto"
    subtitles: str = "bold"
    hook: bool = True
    hook_text: str = ""  # empty -> first sentence of the clip

    @classmethod
    def from_dict(cls, data: dict | None) -> "ClipOptions":
        data = data or {}
        opts = cls(**{k: data[k] for k in ("layout", "subtitles", "hook", "hook_text") if k in data})
        if opts.layout not in LAYOUTS:
            raise ClipForgeError(f"Unknown layout '{opts.layout}'.", f"Use one of: {', '.join(LAYOUTS)}")
        if opts.subtitles not in SUBTITLE_STYLES:
            raise ClipForgeError(f"Unknown subtitle style '{opts.subtitles}'.",
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


def build_ass(words: list[dict], duration: float, opts: ClipOptions, layout: str,
              lang: str | None, hook_text: str) -> str:
    font = _font_for(lang)
    rtl = languages.is_rtl(lang)
    # Caption line position (center of the text block)
    cap_y = SPLIT_TOP if layout == "split" else 1390
    styles = {
        # name: size, primary, outline colour, back colour, bold, border style, outline, shadow
        "bold": (86, WHITE, BLACK, "&H80000000", -1, 1, 7, 2),
        "clean": (62, WHITE, "&H50000000", "&H00000000", -1, 3, 14, 0),
        "minimal": (56, WHITE, "&H70000000", "&HA0000000", 0, 1, 2, 3),
    }
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {OUT_W}", f"PlayResY: {OUT_H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    for name, (size, prim, outl, back, bold, border, outline, shadow) in styles.items():
        lines.append(f"Style: {name},{font},{size},{prim},{GOLD},{outl},{back},{bold},0,0,0,"
                     f"100,100,0,0,{border},{outline},{shadow},5,70,70,0,1")
    lines.append(f"Style: hook,{font},64,{NAVY},{NAVY},{WHITE},&H40000000,-1,0,0,0,"
                 f"100,100,0,0,3,22,0,8,90,90,0,1")
    lines += ["", "[Events]",
              "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]

    def event(start: float, end: float, style: str, text: str, layer: int = 0) -> None:
        lines.append(f"Dialogue: {layer},{_ass_time(start)},{_ass_time(end)},{style},,0,0,0,,{text}")

    if opts.subtitles != "none" and words:
        style = opts.subtitles
        if style == "bold":
            groups = group_words(words, 16, 3, lang)
        else:
            groups = group_words(words, 30, 7, lang)
        joiner = "" if lang in NO_SPACE_LANGS else " "
        pos = f"{{\\an5\\pos({OUT_W // 2},{cap_y})}}"
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
                    pop = "{\\fscx108\\fscy108\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
                    event(w_start, w_end, "bold", pos + pop + joiner.join(parts))
            else:
                event(g_start, g_end, style, pos + "{\\fad(80,80)}" + joiner.join(texts))

    if opts.hook and hook_text:
        hook_y = 120 if layout != "fit" else 330
        text = _ass_escape(hook_text)
        if rtl:
            text = "‫" + text + "‬"  # keep punctuation on the right side
        event(0.0, min(3.2, duration), "hook",
              f"{{\\an8\\pos({OUT_W // 2},{hook_y})\\fad(150,300)}}{text}", layer=1)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- video


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def _filter_graph(layout: str, src_w: int, src_h: int, facecam: Facecam | None) -> str:
    cover = f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase:flags=bicubic,crop={OUT_W}:{OUT_H}"
    if layout == "crop":
        return f"[0:v]{cover},setsar=1[base]"
    if layout == "fit":
        # Blur at quarter size (fast), then scale back up.
        bg = (f"scale={OUT_W // 4}:{OUT_H // 4}:force_original_aspect_ratio=increase,"
              f"crop={OUT_W // 4}:{OUT_H // 4},boxblur=12:2,eq=brightness=-0.10:saturation=1.1,"
              f"scale={OUT_W}:{OUT_H}")
        fg = f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease:flags=bicubic"
        return (f"[0:v]split=2[a][b];[a]{bg}[bg];[b]{fg}[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[base]")
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
    return (f"[0:v]split=2[a][b];[a]{cam}[cam];[b]{game}[game];"
            f"[cam][game]vstack=inputs=2,setsar=1[base]")


def render_clip(project: Project, cand: dict, opts: ClipOptions, facecam: Facecam | None,
                dest: Path, on_progress: Callable[[float], None] | None = None) -> RenderResult:
    ffmpeg = require_tool("ffmpeg")
    source = project.source_path
    if source is None:
        raise ClipForgeError("The project's source video is missing.",
                             "Re-run: python cli.py ingest <url-or-path>")
    meta = project.load_meta()
    src_w, src_h = int(meta.get("width") or 1920), int(meta.get("height") or 1080)
    fps = float(meta.get("fps") or 30)
    start, end = float(cand["start"]), float(cand["end"])
    duration = max(0.5, end - start)

    transcript = read_json(project.transcript_path) if project.transcript_path.is_file() else {}
    lang = transcript.get("language")
    words = clip_words(transcript, start, end) if transcript else []
    layout = resolve_layout(opts.layout, facecam)
    hook_text = opts.hook_text or first_sentence(cand.get("text") or "")
    ass = build_ass(words, duration, opts, layout, lang, hook_text)

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".partial.mp4")
    work = Path(tempfile.mkdtemp(prefix="clipforge-"))
    try:
        # Relative file name + cwd: avoids ffmpeg filter escaping of Windows paths.
        (work / "subs.ass").write_text(ass, encoding="utf-8")
        graph = _filter_graph(layout, src_w, src_h, facecam) + ";[base]ass=subs.ass,format=yuv420p[v]"
        rate = ["-r", "60"] if fps > 61 else []
        fade_out = max(0.0, duration - 0.2)
        audio = f"afade=t=in:d=0.12,afade=t=out:st={fade_out:.3f}:d=0.2"

        def build(e) -> list[str]:
            return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats",
                    "-ss", f"{start:.3f}", "-i", str(source.resolve()), "-t", f"{duration:.3f}",
                    "-filter_complex", graph, "-map", "[v]", "-map", "0:a:0?", *rate,
                    "-c:v", e.name, *e.args, "-c:a", "aac", "-b:a", "192k", "-af", audio,
                    "-movflags", "+faststart", "-progress", "pipe:1", str(tmp.resolve())]

        enc, _ = pick_encoder()
        t0 = time.perf_counter()
        code, err = run_ffmpeg(build(enc), duration, on_progress, cwd=work)
        if code != 0 and enc.hardware:  # e.g. GPU busy: retry on the CPU
            enc = ENCODERS["libx264"]
            code, err = run_ffmpeg(build(enc), duration, on_progress, cwd=work)
        if code != 0:
            tmp.unlink(missing_ok=True)
            raise ClipForgeError(f"ffmpeg could not render the clip: {err.strip()[-500:]}")
        os.replace(tmp, dest)
        return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, enc.label)
    finally:
        shutil.rmtree(work, ignore_errors=True)
