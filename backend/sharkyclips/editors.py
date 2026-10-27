"""Editor timelines for one clip: everything the render does, as an editable timeline.

  fcpxml    FCPXML 1.9 - DaVinci Resolve (File > Import > Timeline) and Final Cut Pro.
  premiere  Final Cut Pro 7 XML (xmeml 4), which Premiere Pro imports (File > Import).

Both come from the SAME EditPlan the renderer uses (edit/plan.py), on the render's frame
grid, so every cut sits on the frame the MP4 cuts on:

  V1 / spine   [intro card] [hook flash] [kept part 1] [kept part 2] ... [outro card]
               each kept part is its own clip on the ORIGINAL video (full quality, handles
               to trim); transcript cuts and silence / filler cuts alike
  dialogue     the parts' sound, crossfaded at every join (FCPXML: split edit + fades;
               Premiere: "Cross Fade (+3dB)" centered on the cut = the render's equal-power
               crossfade, rounded to whole frames), muted under bleeped words (volume keyframes)
  bleeps       <name>.editor-bleeps.wav: the 1 kHz tones on their own audio track
  music        the song from the music library, from the same offset, with volume keyframes
               that duck it under speech like the render (the render also normalizes the
               whole mix to -14 LUFS; editors leave the final loudness to you)
  zoom         scale keyframes on the parts (the render zooms the 9:16 picture; the timeline
               is the 16:9 original, so the punch-ins zoom around its center)
  brand kit    separate video tracks: logo watermark, @handle, hook text (full-frame PNGs with
               transparency), intro / outro cards (PNGs on the main track)
  captions     FCPXML: a caption track; Premiere: the .srt next to it (File > Import, drag onto
               the timeline = caption track)
  markers      detected events, bleeps, the hook flash, the loop point

All times sit on frame boundaries, which Final Cut requires. CapCut is not supported (its
project format is undocumented and encrypted); it can import the .srt file.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

from .procs import no_window
from .project import Project

MARKER_TEXT = {
    "loudness_spike": "Loud moment", "keyword": "Reaction word", "laughter": "Laughter", "shouting": "Shouting",
    "cheering": "Cheering", "fast_speech": "Fast talking", "pause_then_burst": "Silence then outburst",
    "steady_explanation": "Explanation", "chorus": "Chorus", "drop": "Drop", "chat_spike": "Chat spike",
    "chat_reactions": "Chat reactions", "llm_explanation": "Explanation",
    "lol_pentakill": "Pentakill", "lol_quadrakill": "Quadra kill", "lol_triplekill": "Triple kill",
    "lol_doublekill": "Double kill", "lol_kill": "Kill", "lol_assist": "Assist", "lol_death": "Death",
    "lol_first_blood": "First blood", "lol_shutdown": "Shutdown", "lol_ace": "Ace", "lol_baron_steal": "Baron steal",
    "lol_dragon_steal": "Dragon steal", "lol_baron": "Baron", "lol_dragon": "Dragon", "lol_victory": "Victory",
    "lol_defeat": "Defeat", "df_multikill": "Multikill", "df_kill": "Kill", "df_revenge": "Revenge kill",
    "df_knock": "Knock", "df_revive": "Revive", "df_assist": "Assist", "df_death": "Death",
    "df_extracted": "Extracted", "df_extract_failed": "Extraction failed",
}
BLEEP_AMP = 0.18  # the editor's bleep track level (~ -15 dBFS); the render follows the speech level
SR = 48000


def frame_rate(fps: float) -> tuple[int, int]:
    """(numerator, denominator) of the frame rate: 29.97 -> 30000/1001."""
    for nominal in (24, 30, 60, 120):
        if abs(fps - nominal * 1000 / 1001) < 0.02:
            return nominal * 1000, 1001
    return max(1, round(fps)), 1


class Clock:
    def __init__(self, fps: float):
        self.num, self.den = frame_rate(fps)
        self.timebase = round(self.num / self.den)
        self.ntsc = self.den == 1001

    def frames(self, t: float) -> int:
        return int(round(t * self.num / self.den))

    def rt_frames(self, n: int) -> str:
        f = Fraction(n * self.den, self.num)
        return "0s" if f == 0 else (f"{f.numerator}s" if f.denominator == 1 else f"{f.numerator}/{f.denominator}s")

    def rt(self, t: float) -> str:
        """FCPXML rational time on a frame boundary, e.g. '1001/30000s' or '45/30s'."""
        return self.rt_frames(self.frames(t))

    @property
    def frame_duration(self) -> str:
        return f"{self.den}/{self.num}s"


def markers(cand: dict) -> list[dict]:
    """Detected events inside the clip: [{t (source seconds), name, note}], one per second at most."""
    out: list[dict] = []
    for r in sorted(cand.get("reasons", []), key=lambda r: r.get("t", 0)):
        t = float(r.get("t", -1))
        if not cand["start"] <= t <= cand["end"]:
            continue
        name = MARKER_TEXT.get(r["code"], r["code"].replace("_", " ").capitalize())
        if r.get("value") and (r["code"] in ("keyword", "df_multikill", "chat_reactions") or r["code"].startswith("lol_")):
            name = f"{name}: {r['value']}"
        if out and abs(out[-1]["t"] - t) < 1.0 and out[-1]["name"] == name:
            continue
        out.append({"t": t, "name": name[:60], "note": f"{r['code']} · strength {round(float(r.get('strength') or 0), 2)}"})
    return out


# ===================================================================== the timeline


@dataclass
class Piece:
    """One item on the main video track (frames on the timeline grid)."""
    kind: str  # card | flash | main
    frame: int
    frames: int
    src: float | None = None  # source seconds where it starts (flash / main)
    image: Path | None = None  # card PNG
    name: str = ""
    audio_in: int = 0  # frames of sound before the picture (crossfade handle)
    audio_out: int = 0  # ... after it
    fade_in: int = 0  # sound fade-in frames (crossfade)
    fade_out: int = 0


@dataclass
class Layer:
    """A connected item on its own track (overlay PNG or sound file)."""
    kind: str  # hook | logo | handle | hook_end | bleeps | music
    frame: int
    frames: int
    file: Path
    offset: float = 0.0  # where in the file it starts (music)
    gain_db: float = 0.0
    keys: list[tuple[float, float]] = field(default_factory=list)  # (seconds from the layer start, dB)
    fade_in: float = 0.0
    fade_out: float = 0.0
    name: str = ""


@dataclass
class Timeline:
    fps: float  # the timeline frame rate (= the render's)
    width: int
    height: int
    media: dict
    pieces: list[Piece]
    layers: list[Layer]
    lead: int  # frames before the first kept part (intro + flash)
    main: int  # frames of the kept parts
    total: int
    name: str
    zoom_level: float = 0.0
    zoom: list[tuple[float, float]] = field(default_factory=list)  # pulses in timeline seconds
    mutes: list[tuple[float, float]] = field(default_factory=list)  # dialogue muted (timeline seconds)
    cues: list[dict] = field(default_factory=list)  # captions in timeline seconds
    marks: list[dict] = field(default_factory=list)  # {"t" (timeline seconds), "name", "note"}
    loop: bool = False
    files: list[Path] = field(default_factory=list)  # sidecar files written next to the XML

    def piece_at(self, frame: int) -> Piece:
        for p in self.pieces:
            if p.frame <= frame < p.frame + p.frames:
                return p
        return self.pieces[-1]


def _media(project: Project) -> dict:
    meta = project.load_meta()
    src = project.source_path
    assert src is not None
    return {"path": src.resolve(), "name": src.name, "width": int(meta.get("width") or 1920),
            "height": int(meta.get("height") or 1080), "fps": float(meta.get("fps") or 30),
            "duration": float(meta.get("duration") or 0), "audio": meta.get("audio_codec") is not None,
            "title": meta.get("title") or project.id}


def render_fps(src_fps: float, spec_fps: float | None = None) -> int:
    """The render's frame grid (clips.render_clip)."""
    return max(1, round(min(60.0, float(src_fps or 30), float(spec_fps or 60))))


def factor_out(t: float, pulses_out: list[tuple[float, float]], zmax: float) -> float:
    """Zoom factor at output time t (mirrors zoom.factor_expr, which the renderer draws)."""
    from .edit import zoom

    acc = 0.0
    for t0, t1 in pulses_out:
        ri = min(zoom.RAMP_IN, (t1 - t0) / 3)
        ro = min(zoom.RAMP_OUT, (t1 - t0) / 3)
        s = min(min(1.0, max(0.0, (t - t0) / ri)), min(1.0, max(0.0, (t1 - t) / ro)))
        acc += s * s * (3 - 2 * s)
    return 1 + (zmax - 1) * acc


# --------------------------------------------------------------------- side files


def _ass_layer(ass: str, w: int, h: int, bg: str) -> np.ndarray | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-ed-"))
    try:
        (work / "t.ass").write_text(ass, encoding="utf-8")
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={bg}:s={w}x{h}:d=1",
               "-vf", "ass=t.ass", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
        out = subprocess.run(cmd, capture_output=True, cwd=work, timeout=60, **no_window()).stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)
    if len(out) != w * h * 3:
        return None
    return np.frombuffer(out, np.uint8).reshape(h, w, 3).astype(np.float32) / 255.0


def text_rgba(ass: str, w: int, h: int) -> np.ndarray | None:
    """Text drawn by libass with real transparency: drawn once on black and once on white,
    alpha = 1 - (white - black) (difference matting; exact for normal blending)."""
    black = _ass_layer(ass, w, h, "black")
    white = _ass_layer(ass, w, h, "white")
    if black is None or white is None:
        return None
    alpha = np.clip(1.0 - (white - black).mean(axis=2), 0.0, 1.0)
    rgb = np.where(alpha[..., None] > 1e-3, black / np.maximum(alpha[..., None], 1e-3), 0.0)
    return np.dstack([np.clip(rgb, 0, 1), alpha])


def _over(base: np.ndarray, top: np.ndarray, x: int, y: int) -> np.ndarray:
    """Alpha-composite top (RGBA float) over base (RGBA float) at (x, y)."""
    h, w = top.shape[:2]
    H, W = base.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return base
    t = top[y0 - y: y1 - y, x0 - x: x1 - x]
    b = base[y0:y1, x0:x1]
    a = t[..., 3:4]
    out_a = a + b[..., 3:4] * (1 - a)
    rgb = np.where(out_a > 1e-6, (t[..., :3] * a + b[..., :3] * b[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-6), 0)
    base[y0:y1, x0:x1] = np.dstack([rgb, out_a])
    return base


def _write_png(path: Path, rgba: np.ndarray) -> Path:
    import cv2

    img = (np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8)
    bgra = img[..., [2, 1, 0, 3]]
    ok, buf = cv2.imencode(".png", bgra)
    if not ok:
        raise OSError("PNG encode failed")
    path.write_bytes(buf.tobytes())
    return path


def _logo_rgba(path: Path, w: int, h: int, opacity: float) -> np.ndarray | None:
    import cv2

    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    img = cv2.resize(img, (max(1, w), max(1, h)), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    rgba = img[..., [2, 1, 0, 3]]
    rgba[..., 3] *= opacity
    return rgba


def _ass_doc(geo, events: list[str], lang: str | None, style: dict | None) -> str:
    """An .ass document with SharkyClips' styles (clips.build_ass) and these Dialogue lines."""
    from .clips import ClipOptions, build_ass

    head = build_ass([], 1.0, ClipOptions.from_dict({"hook": False, "subtitles": "none"}), "fit", lang, "",
                     geo=geo, style=style)
    return head + "\n".join(events) + "\n"


def _write_bleeps(path: Path, total_s: float, ranges: list[tuple[float, float]]) -> Path:
    n = int(round(total_s * SR))
    y = np.zeros(n, np.float32)
    r = int(0.006 * SR)
    for a, b in ranges:
        ia, ib = max(0, int(round(a * SR))), min(n, int(round(b * SR)))
        if ib - ia < 4:
            continue
        tt = np.arange(ib - ia, dtype=np.float32) / SR
        tone = BLEEP_AMP * np.sin(2 * np.pi * 1000.0 * tt)
        env = np.ones(ib - ia, np.float32)
        k = min(r, (ib - ia) // 2)
        env[:k] = np.linspace(0, 1, k)
        env[-k:] = np.linspace(1, 0, k)
        y[ia:ib] = tone * env
    pcm = (np.clip(np.repeat(y[:, None], 2, axis=1), -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


# --------------------------------------------------------------------- building it


def build(project: Project, cand: dict, opts, stem: Path, *, vertical: bool = True, spec_fps: float | None = None,
          max_len: float | None = None, cues_for=None, plan=None) -> Timeline:
    """The timeline of one clip, with its side files written next to `stem`.
    cues_for(plan, lead_seconds) -> captions in timeline seconds (export.clip_cues).
    plan: an EditPlan to use (tests); else built like the render builds it."""
    from .clips import (FLASH_SECONDS, Geometry, OutputSpec, _brand_layers, _even, _logo_size, clip_text,
                        flash_from)
    from .edit import audiomix, brand, loudness
    from .edit import plan as plan_mod
    from .edit.music import decode, path_of

    m = _media(project)
    F = render_fps(m["fps"], spec_fps)
    if plan is None:
        plan = plan_mod.build(project, cand, opts, vertical=vertical, fps=F, max_len=max_len)
    W, H = m["width"], m["height"]
    seam = plan.loop
    flash = FLASH_SECONDS if getattr(opts, "hook_flash", False) and seam is None else 0.0
    src_dur = m["duration"] or plan.end
    peak = float(cand.get("peak") or (plan.start + plan.end) / 2)
    flash_start = flash_from(peak, src_dur, m["fps"])
    preset = plan.brand
    intro_f, outro_f = round(plan.intro_s * F), round(plan.outro_s * F)
    flash_f = round(flash * F)
    lead = intro_f + flash_f
    files: list[Path] = []
    stem.parent.mkdir(parents=True, exist_ok=True)

    # The picture and text on the 16:9 canvas (the render's "wide" layout), scaled to the source size.
    geo = Geometry.for_spec(OutputSpec(frame="wide"), "fit")
    CW, CH = geo.w, geo.h
    style = None
    if preset:
        style = {"font": preset.get("caption_font"), "primary": preset.get("caption_color"),
                 "highlight": preset.get("caption_highlight"), "outline": preset.get("caption_outline")}

    def scaled(rgba: np.ndarray) -> np.ndarray:
        if (CW, CH) == (W, H):
            return rgba
        import cv2

        return cv2.resize(rgba, (W, H), interpolation=cv2.INTER_AREA)

    pieces: list[Piece] = []
    frame = 0

    def card_png(kind: str, text: str, ev_style: str) -> Path | None:
        color = (preset or {}).get("card_color", "#0E1A33").lstrip("#")
        base = np.zeros((CH, CW, 4), np.float32)
        base[..., 0], base[..., 1], base[..., 2] = (int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
        base[..., 3] = 1.0
        logo = brand.logo_path(preset)
        if logo is not None:  # like the render's card: logo 36% of the width, a bit above the middle
            iw, ih = _logo_size(logo)
            lw = _even(CW * 0.36)
            lh = _even(lw * ih / max(1, iw))
            lg = _logo_rgba(logo, lw, lh, 1.0)
            if lg is not None:
                base = _over(base, lg, (CW - lw) // 2, (CH - lh) // 2 - int(CH * 0.06))
        if text:
            from .clips import _ass_escape

            y = int(CH * (0.64 if logo is not None else 0.5))
            ass = _ass_doc(geo, [f"Dialogue: 2,0:00:00.00,0:00:05.00,{ev_style},,0,0,0,,"
                                 f"{{\\an5\\pos({CW // 2},{y})}}{_ass_escape(text)}"], plan.lang, style)
            txt = text_rgba(ass, CW, CH)
            if txt is not None:
                base = _over(base, txt, 0, 0)
        path = stem.with_name(f"{stem.name}.editor-{kind}.png")
        files.append(_write_png(path, scaled(base)))
        return path

    if intro_f:
        img = card_png("intro", brand.intro_text(preset), "card")
        pieces.append(Piece("card", frame, intro_f, image=img, name="Intro card"))
        frame += intro_f
    if flash_f:
        pieces.append(Piece("flash", frame, flash_f, src=flash_start, name="Hook flash",
                            fade_in=max(1, round(0.05 * F)), fade_out=max(1, round(0.12 * F))))
        frame += flash_f
    kept = plan.frames()
    h = max(1, round(audiomix.XFADE / 2 * F))
    for k, (fa, fb) in enumerate(kept):
        first, last = k == 0, k == len(kept) - 1
        pieces.append(Piece("main", frame, fb - fa, src=plan.start + fa / F, name=f"Part {k + 1}",
                            audio_in=0 if first else h, audio_out=0 if last else h,
                            fade_in=0 if first else 2 * h, fade_out=0 if last else 2 * h))
        frame += fb - fa
    main = frame - lead
    if outro_f:
        img = card_png("outro", brand.outro_text(preset), "card")
        pieces.append(Piece("card", frame, outro_f, image=img, name="Outro card"))
        frame += outro_f
    total = frame
    lead_s, main_s, total_s = lead / F, main / F, total / F

    layers: list[Layer] = []
    # ---- hook text (+ the loop's second appearance at the end)
    words, lang, hook_text, hook_lang = clip_text(project, {**cand, "start": plan.start, "end": plan.end}, opts)
    if seam is not None and seam.hook_text and not getattr(opts, "hook_text", ""):
        hook_text = seam.hook_text
    if getattr(opts, "hook", False) and hook_text:
        from .clips import _ass_escape
        from .languages import is_rtl

        text = _ass_escape(hook_text)
        if is_rtl(hook_lang or lang):
            text = "‫" + text + "‬"
        ass = _ass_doc(geo, [f"Dialogue: 1,0:00:00.00,0:00:05.00,hook,,0,0,0,,{{\\an8\\pos({geo.cap_x},{geo.hook_y})}}{text}"],
                       hook_lang or lang, style)
        rgba = text_rgba(ass, CW, CH)
        if rgba is not None:
            path = stem.with_name(f"{stem.name}.editor-hook.png")
            files.append(_write_png(path, scaled(rgba)))
            a = intro_f
            b = intro_f + round((min(3.2, main_s) + flash * 0.6) * F)
            layers.append(Layer("hook", a, max(1, b - a), path, name="Hook text"))
            if seam is not None:
                a2 = max(0, total - round(0.8 * F))
                layers.append(Layer("hook_end", a2, total - a2, path, name="Hook text (loop)"))
    # ---- brand watermark + handle
    if preset:
        info, _lines = _brand_layers(preset, geo, OutputSpec(frame="wide"), (CW, CH), lead_s, lead_s + main_s,
                                     total_s, plan.intro_s, plan.outro_s)
        if info.get("logo") is not None:
            lg = _logo_rgba(info["logo"], info["w"], info["h"], float(preset["logo_opacity"]))
            if lg is not None:
                base = _over(np.zeros((CH, CW, 4), np.float32), lg, info["x"], info["y"])
                path = stem.with_name(f"{stem.name}.editor-logo.png")
                files.append(_write_png(path, scaled(base)))
                layers.append(Layer("logo", lead, main, path, name="Logo"))
        handle_lines = [ln for ln in _lines if ",handle," in ln]
        if handle_lines:
            ass = _ass_doc(geo, [re.sub(r"^Dialogue: (\d+),[^,]*,[^,]*,", r"Dialogue: \1,0:00:00.00,0:00:05.00,", ln)
                                 for ln in handle_lines], plan.lang, style)
            rgba = text_rgba(ass, CW, CH)
            if rgba is not None:
                path = stem.with_name(f"{stem.name}.editor-handle.png")
                files.append(_write_png(path, scaled(rgba)))
                layers.append(Layer("handle", lead, main, path, name="Handle"))
    # ---- bleeps
    bleeps_tl = [(lead_s + a, lead_s + b) for a, b in plan.bleeps] if plan.bleep_mode != "off" else []
    if bleeps_tl and plan.bleep_mode == "bleep":
        path = _write_bleeps(stem.with_name(f"{stem.name}.editor-bleeps.wav"), total_s, bleeps_tl)
        files.append(path)
        layers.append(Layer("bleeps", 0, total, path, name="Bleeps"))
    # ---- music with ducking keyframes (same levels as audiomix)
    mpath = path_of(plan.music["name"]) if plan.music else None
    if mpath is not None:
        dur = float(plan.music.get("duration") or 0)
        off = float(plan.music.get("best_start") or 0)
        if dur and dur - off < total_s:
            off = max(0.0, dur - total_s)
        speech_ref = -20.0
        if m["audio"]:
            t0 = max(0.0, plan.start - 0.1)
            src = decode(m["path"], t0, plan.end - t0 + 0.1, sr=SR, channels=2)
            speech_ref = loudness.integrated_lufs(audiomix.cut_and_join(src, t0, plan))
            speech_ref = speech_ref if speech_ref > -60 else -20.0
        m_lufs = loudness.integrated_lufs(decode(mpath, off, total_s + 0.1, sr=SR, channels=2))
        base_db = (speech_ref + audiomix.MUSIC_IN_PAUSES_DB - m_lufs) if m_lufs > -69 else -60.0
        duck = audiomix.MUSIC_UNDER_SPEECH_DB - audiomix.MUSIC_IN_PAUSES_DB
        keys: list[tuple[float, float]] = [(0.0, base_db)]
        for a, b in plan.speech_out():
            a, b = a + lead_s, b + lead_s
            pts = [(max(0.0, a - 0.12), base_db), (max(0.0, a), base_db + duck), (b, base_db + duck),
                   (min(total_s, b + 0.6), base_db)]
            for t, v in pts:
                if keys and t <= keys[-1][0] + 1e-3:
                    keys[-1] = (keys[-1][0], min(keys[-1][1], v)) if v < keys[-1][1] else keys[-1]
                    continue
                keys.append((t, v))
        looped = seam is not None
        layers.append(Layer("music", 0, total, mpath, offset=off, gain_db=base_db, keys=keys,
                            fade_in=0.0 if looped else 0.3,
                            fade_out=0.0 if looped else min(2.0, max(0.6, total_s * 0.12)),
                            name=f"Music: {plan.music.get('title') or mpath.stem}"))

    # ---- markers (timeline seconds)
    marks = []
    for mk in markers({**cand, "start": plan.start, "end": plan.end}):
        t = plan.to_out(mk["t"])
        if t is not None:
            marks.append({"t": lead_s + t, "name": mk["name"], "note": mk["note"]})
    for i, (a, _b) in enumerate(bleeps_tl):
        marks.append({"t": a, "name": "Bleep" if plan.bleep_mode == "bleep" else "Muted word",
                      "note": f"swear word {i + 1}"})
    if flash_f:
        marks.append({"t": intro_f / F, "name": "Hook flash", "note": f"peak moment from {flash_start:.2f} s"})
    if seam is not None:
        marks.append({"t": max(0.0, total_s - 1 / F), "name": "Loop point",
                      "note": f"loops back to the start; seam {seam.audio_xfade * 1000:.0f} ms sound crossfade"})
    marks.sort(key=lambda x: x["t"])

    zoom_pulses: list[tuple[float, float]] = []
    if plan.zooms:
        from .edit.plan import merge

        zoom_pulses = [(lead_s + a, lead_s + b) for a, b in merge(plan.out_pulses("scene") + plan.out_pulses("cam"))]
    cues = cues_for(plan, lead_s) if cues_for is not None else []
    name = f"SharkyClips #{cand['rank']:02d} - {m['title']}"[:120]
    return Timeline(fps=F, width=W, height=H, media=m, pieces=pieces, layers=layers, lead=lead, main=main,
                    total=total, name=name, zoom_level=plan.zoom_level if plan.zooms else 0.0, zoom=zoom_pulses,
                    mutes=bleeps_tl, cues=cues, marks=marks, loop=seam is not None, files=files)


# ===================================================================== FCPXML


def _pretty(root: ET.Element, doctype: str) -> str:
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + doctype + "\n" + ET.tostring(root, encoding="unicode") + "\n"


def _db(v: float) -> str:
    return f"{max(-96.0, min(12.0, v)):.1f}dB"


def fcpxml(tl: Timeline, lang: str | None = None) -> str:
    """FCPXML 1.9. Element order follows Apple's DTD (adjustments, then anchored items, then markers)."""
    m = tl.media
    seq_clk = Clock(tl.fps)
    src_clk = Clock(m["fps"])
    F = tl.fps

    def sec(n_frames: int) -> str:
        return seq_clk.rt_frames(n_frames)

    def src_t(t: float) -> str:  # source time on the SOURCE frame grid
        return src_clk.rt(t)

    root = ET.Element("fcpxml", version="1.9")
    res = ET.SubElement(root, "resources")
    ET.SubElement(res, "format", id="r1", frameDuration=seq_clk.frame_duration, width=str(tl.width),
                  height=str(tl.height), colorSpace="1-1-1 (Rec. 709)")
    src_fmt = "r1"
    if frame_rate(m["fps"]) != frame_rate(F):
        ET.SubElement(res, "format", id="r1s", frameDuration=src_clk.frame_duration, width=str(m["width"]),
                      height=str(m["height"]), colorSpace="1-1-1 (Rec. 709)")
        src_fmt = "r1s"
    ET.SubElement(res, "format", id="rstill", name="FFVideoFormatRateUndefined", width=str(tl.width),
                  height=str(tl.height))
    asset = ET.SubElement(res, "asset", id="r2", name=m["name"], start="0s",
                          duration=src_clk.rt(m["duration"] or 3600), hasVideo="1", format=src_fmt, videoSources="1")
    if m["audio"]:
        asset.set("hasAudio", "1")
        asset.set("audioSources", "1")
        asset.set("audioChannels", "2")
        asset.set("audioRate", "48000")
    ET.SubElement(asset, "media-rep", kind="original-media", src=m["path"].as_uri())
    ids: dict[Path, str] = {}

    def file_asset(path: Path, *, audio: bool, seconds: float | None = None) -> str:
        if path in ids:
            return ids[path]
        rid = f"r{10 + len(ids)}"
        ids[path] = rid
        attrs = {"id": rid, "name": path.name, "start": "0s"}
        if audio:
            attrs.update(hasAudio="1", audioSources="1", audioChannels="2", audioRate="48000",
                         duration=seq_clk.rt(seconds or 0))
        else:
            attrs.update(hasVideo="1", format="rstill", videoSources="1", duration="0s")
        a = ET.SubElement(res, "asset", **attrs)
        ET.SubElement(a, "media-rep", kind="original-media", src=path.resolve().as_uri())
        return rid

    lib = ET.SubElement(root, "library")
    event = ET.SubElement(lib, "event", name="SharkyClips")
    proj = ET.SubElement(event, "project", name=tl.name)
    seq = ET.SubElement(proj, "sequence", format="r1", duration=sec(tl.total), tcStart="0s", tcFormat="NDF",
                        audioLayout="stereo", audioRate="48k")
    spine = ET.SubElement(seq, "spine")

    elems: list[tuple[Piece, ET.Element, float]] = []  # (piece, element, local start seconds)
    for p in tl.pieces:
        if p.kind == "card":
            e = ET.SubElement(spine, "video", ref=file_asset(p.image, audio=False), offset=sec(p.frame), name=p.name,
                              start="0s", duration=sec(p.frames))
            elems.append((p, e, 0.0))
            continue
        e = ET.SubElement(spine, "asset-clip", ref="r2", offset=sec(p.frame), name=f"{p.name} · {m['name']}",
                          start=src_t(p.src), duration=sec(p.frames), tcFormat="NDF")
        if m["audio"]:
            e.set("audioRole", "dialogue")
            if p.audio_in or p.audio_out:  # split edit: the sound reaches into the neighbours (crossfade)
                e.set("audioStart", src_t(p.src - p.audio_in / F))
                e.set("audioDuration", sec(p.frames + p.audio_in + p.audio_out))
        elems.append((p, e, round(p.src * src_clk.num / src_clk.den) * src_clk.den / src_clk.num))

    def local(p: Piece, start_local: float, t_tl: float) -> float:
        return start_local + (t_tl - p.frame / F)

    # Intrinsic adjustments first (DTD order: adjust-transform, adjust-volume), per clip.
    for p, e, s0 in elems:
        if p.kind == "card":
            continue
        p_a, p_b = p.frame / F, (p.frame + p.frames) / F
        if tl.zoom_level > 1 and p.kind == "main":
            keys = []
            for z0, z1 in tl.zoom:
                if z1 <= p_a or z0 >= p_b:
                    continue
                from .edit import zoom as zoom_mod

                ri = min(zoom_mod.RAMP_IN, (z1 - z0) / 3)
                ro = min(zoom_mod.RAMP_OUT, (z1 - z0) / 3)
                for t in (z0, z0 + ri, z1 - ro, z1, p_a, p_b - 1 / F):
                    if p_a - 1e-6 <= t <= p_b - 1 / F + 1e-6 and z0 - 1e-6 <= t <= z1 + 1e-6:
                        keys.append(t)
            if keys:
                at = ET.SubElement(e, "adjust-transform")
                prm = ET.SubElement(at, "param", name="scale")
                ka = ET.SubElement(prm, "keyframeAnimation")
                for t in sorted(set(round(k * F) for k in keys)):
                    v = factor_out(t / F - tl.lead / F, [(a - tl.lead / F, b - tl.lead / F) for a, b in tl.zoom],
                                   tl.zoom_level)
                    ET.SubElement(ka, "keyframe", time=src_t(local(p, s0, t / F)), value=f"{v:.4f} {v:.4f}",
                                  interp="ease", curve="smooth")
        if not m["audio"]:
            continue
        mutes = [(a, b) for a, b in tl.mutes if b > p_a and a < p_b]
        if p.fade_in or p.fade_out or mutes:
            av = ET.SubElement(e, "adjust-volume")
            prm = ET.SubElement(av, "param", name="amount")
            if p.fade_in:
                ET.SubElement(prm, "fadeIn", type="easeIn", duration=sec(p.fade_in))
            if p.fade_out:
                ET.SubElement(prm, "fadeOut", type="easeOut", duration=sec(p.fade_out))
            if mutes:
                ka = ET.SubElement(prm, "keyframeAnimation")
                for a, b in mutes:
                    a, b = max(a, p_a), min(b, p_b)
                    for t, v in ((a - 0.006, 0.0), (a, -96.0), (b, -96.0), (b + 0.006, 0.0)):
                        ET.SubElement(ka, "keyframe", time=src_t(local(p, s0, t)), value=_db(v), interp="linear",
                                      curve="linear")

    # Anchored items (lanes), each on the piece where it starts.
    lanes = {"hook": 2, "hook_end": 2, "logo": 3, "handle": 4, "bleeps": -1, "music": -2}
    for ly in tl.layers:
        p = tl.piece_at(ly.frame)
        _pp, e, s0 = next(x for x in elems if x[0] is p)
        off = src_t(local(p, s0, ly.frame / F)) if p.kind != "card" else sec(ly.frame - p.frame)
        if ly.kind in ("bleeps", "music"):
            a = ET.SubElement(e, "asset-clip", ref=file_asset(ly.file, audio=True, seconds=ly.offset + ly.frames / F + 1),
                              lane=str(lanes[ly.kind]), offset=off, name=ly.name, start=seq_clk.rt(ly.offset),
                              duration=sec(ly.frames), audioRole="effects" if ly.kind == "bleeps" else "music")
            if ly.kind == "music":
                av = ET.SubElement(a, "adjust-volume", amount=_db(ly.gain_db))
                prm = ET.SubElement(av, "param", name="amount")
                if ly.fade_in:
                    ET.SubElement(prm, "fadeIn", type="easeIn", duration=seq_clk.rt(ly.fade_in))
                if ly.fade_out:
                    ET.SubElement(prm, "fadeOut", type="easeOut", duration=seq_clk.rt(ly.fade_out))
                if ly.keys:
                    ka = ET.SubElement(prm, "keyframeAnimation")
                    for t, v in ly.keys:  # relative to the base level (adjust-volume amount)
                        ET.SubElement(ka, "keyframe", time=seq_clk.rt(ly.offset + t), value=_db(v - ly.gain_db),
                                      interp="ease", curve="smooth")
        else:
            ET.SubElement(e, "video", ref=file_asset(ly.file, audio=False), lane=str(lanes[ly.kind]), offset=off,
                          name=ly.name, start="0s", duration=sec(ly.frames))
    role = f"SRT?captionFormat=SRT.{lang or 'en'}"
    for i, c in enumerate(tl.cues, 1):
        fa, fb = seq_clk.frames(max(0.0, c["start"])), seq_clk.frames(min(c["end"], tl.total / F))
        if fb <= fa:
            continue
        p = tl.piece_at(fa)
        _pp, e, s0 = next(x for x in elems if x[0] is p)
        off = src_t(local(p, s0, fa / F)) if p.kind != "card" else sec(fa - p.frame)
        cap = ET.SubElement(e, "caption", lane="1", offset=off, name=c["text"][:40], start="3600s",
                            duration=sec(fb - fa), role=role)
        text = ET.SubElement(cap, "text", placement="bottom")
        ts = ET.SubElement(text, "text-style", ref=f"ts{i}")
        ts.text = c["text"]
        tdef = ET.SubElement(cap, "text-style-def", id=f"ts{i}")
        ET.SubElement(tdef, "text-style", font=".AppleSystemUIFont", fontSize="13", fontFace="Regular",
                      fontColor="1 1 1 1", backgroundColor="0 0 0 1")
    # Markers last (DTD: after the anchored items).
    for mk in tl.marks:
        fr = min(tl.total - 1, seq_clk.frames(mk["t"]))
        p = tl.piece_at(fr)
        _pp, e, s0 = next(x for x in elems if x[0] is p)
        start = src_t(local(p, s0, fr / F)) if p.kind != "card" else sec(fr - p.frame)
        ET.SubElement(e, "marker", start=start, duration=seq_clk.frame_duration, value=mk["name"], note=mk["note"])
    return _pretty(root, "<!DOCTYPE fcpxml>")


# ===================================================================== Premiere (xmeml 4)


def _rate(parent: ET.Element, clk: Clock) -> None:
    rate = ET.SubElement(parent, "rate")
    ET.SubElement(rate, "timebase").text = str(clk.timebase)
    ET.SubElement(rate, "ntsc").text = "TRUE" if clk.ntsc else "FALSE"


def _pathurl(path: Path) -> str:
    return path.resolve().as_uri().replace("file:///", "file://localhost/")


def premiere_xml(tl: Timeline) -> str:
    """FCP7 xmeml (Premiere Pro imports it). Frames at the timeline's rate; keyframe <when>
    counts frames from the clip item's own start."""
    m = tl.media
    clk = Clock(tl.fps)
    F = tl.fps
    src_frames = Clock(m["fps"])  # source file frame counts (in/out are in the SEQUENCE rate)
    root = ET.Element("xmeml", version="4")
    seq = ET.SubElement(root, "sequence", id="sequence-1")
    ET.SubElement(seq, "name").text = tl.name
    ET.SubElement(seq, "duration").text = str(tl.total)
    _rate(seq, clk)
    tc = ET.SubElement(seq, "timecode")
    _rate(tc, clk)
    ET.SubElement(tc, "string").text = "00:00:00:00"
    ET.SubElement(tc, "frame").text = "0"
    ET.SubElement(tc, "displayformat").text = "NDF"
    media = ET.SubElement(seq, "media")
    video = ET.SubElement(media, "video")
    fmt = ET.SubElement(video, "format")
    sc = ET.SubElement(fmt, "samplecharacteristics")
    _rate(sc, clk)
    ET.SubElement(sc, "width").text = str(tl.width)
    ET.SubElement(sc, "height").text = str(tl.height)
    ET.SubElement(sc, "pixelaspectratio").text = "square"
    total_src = round((m["duration"] or 3600) * F)
    defined: set[str] = set()
    n_item = [0]

    def file_el(parent: ET.Element, fid: str, path: Path, *, kind: str, frames: int) -> None:
        """kind: av (the source video), still (PNG), audio (WAV / song)."""
        f = ET.SubElement(parent, "file", id=fid)
        if fid in defined:
            return
        defined.add(fid)
        ET.SubElement(f, "name").text = path.name
        ET.SubElement(f, "pathurl").text = _pathurl(path)
        _rate(f, clk)
        ET.SubElement(f, "duration").text = str(frames)
        fm = ET.SubElement(f, "media")
        if kind in ("av", "still"):
            fv = ET.SubElement(ET.SubElement(fm, "video"), "samplecharacteristics")
            _rate(fv, clk)
            ET.SubElement(fv, "width").text = str(m["width"] if kind == "av" else tl.width)
            ET.SubElement(fv, "height").text = str(m["height"] if kind == "av" else tl.height)
        if kind == "audio" or (kind == "av" and m["audio"]):
            fa = ET.SubElement(fm, "audio")
            ET.SubElement(fa, "channelcount").text = "2"

    def clipitem(track: ET.Element, name: str, start: int, frames: int, in_f: int, dur: int) -> ET.Element:
        n_item[0] += 1
        ci = ET.SubElement(track, "clipitem", id=f"clipitem-{n_item[0]}")
        ET.SubElement(ci, "name").text = name
        ET.SubElement(ci, "enabled").text = "TRUE"
        ET.SubElement(ci, "duration").text = str(dur)
        _rate(ci, clk)
        ET.SubElement(ci, "start").text = str(start)
        ET.SubElement(ci, "end").text = str(start + frames)
        ET.SubElement(ci, "in").text = str(in_f)
        ET.SubElement(ci, "out").text = str(in_f + frames)
        return ci

    def effect(ci: ET.Element, name: str, eid: str, cat: str, mtype: str, pid: str, pname: str, base: float,
               vmax: float, keys: list[tuple[int, float]]) -> None:
        flt = ET.SubElement(ci, "filter")
        eff = ET.SubElement(flt, "effect")
        ET.SubElement(eff, "name").text = name
        ET.SubElement(eff, "effectid").text = eid
        ET.SubElement(eff, "effectcategory").text = cat
        ET.SubElement(eff, "effecttype").text = cat
        ET.SubElement(eff, "mediatype").text = mtype
        prm = ET.SubElement(eff, "parameter")
        ET.SubElement(prm, "parameterid").text = pid
        ET.SubElement(prm, "name").text = pname
        ET.SubElement(prm, "valuemin").text = "0"
        ET.SubElement(prm, "valuemax").text = f"{vmax:g}"
        ET.SubElement(prm, "value").text = f"{base:.4f}"
        for when, v in keys:
            kf = ET.SubElement(prm, "keyframe")
            ET.SubElement(kf, "when").text = str(when)
            ET.SubElement(kf, "value").text = f"{v:.4f}"

    def gain(db: float) -> float:
        return 0.0 if db <= -96 else 10 ** (db / 20)

    def in_point(t: float) -> int:  # source seconds -> sequence-rate frames of the source file
        return round(round(t * src_frames.num / src_frames.den) * src_frames.den / src_frames.num * F)

    v1 = ET.SubElement(video, "track")
    vitems: dict[int, ET.Element] = {}
    for i, p in enumerate(tl.pieces):
        if p.kind == "card":
            ci = clipitem(v1, p.name, p.frame, p.frames, 0, p.frames)
            file_el(ci, f"file-{p.image.name}", p.image, kind="still", frames=p.frames)
            continue
        ci = clipitem(v1, f"{p.name} · {m['name']}", p.frame, p.frames, in_point(p.src), total_src)
        file_el(ci, "file-1", m["path"], kind="av", frames=total_src)
        if tl.zoom_level > 1 and p.kind == "main":
            keys = []
            p_a, p_b = p.frame / F, (p.frame + p.frames) / F
            from .edit import zoom as zoom_mod

            for z0, z1 in tl.zoom:
                if z1 <= p_a or z0 >= p_b:
                    continue
                ri, ro = min(zoom_mod.RAMP_IN, (z1 - z0) / 3), min(zoom_mod.RAMP_OUT, (z1 - z0) / 3)
                for t in (z0, z0 + ri, z1 - ro, z1, p_a, p_b - 1 / F):
                    if p_a - 1e-6 <= t <= p_b - 1 / F + 1e-6 and z0 - 1e-6 <= t <= z1 + 1e-6:
                        keys.append(round(t * F) - p.frame)
            pul = [(a - tl.lead / F, b - tl.lead / F) for a, b in tl.zoom]
            if keys:
                effect(ci, "Basic Motion", "basic", "motion", "video", "scale", "Scale", 100, 1000,
                       [(k, 100 * factor_out((p.frame + k) / F - tl.lead / F, pul, tl.zoom_level))
                        for k in sorted(set(keys))])
        vitems[i] = ci
    for kind, label in (("hook", "Hook text"), ("logo", "Logo"), ("handle", "Handle")):
        items = [ly for ly in tl.layers if ly.kind == kind or (kind == "hook" and ly.kind == "hook_end")]
        if not items:
            continue
        tr = ET.SubElement(video, "track")
        for ly in sorted(items, key=lambda x: x.frame):
            ci = clipitem(tr, label, ly.frame, ly.frames, 0, ly.frames)
            file_el(ci, f"file-{ly.file.name}", ly.file, kind="still", frames=max(ly.frames, tl.total))

    audio = ET.SubElement(media, "audio")
    if m["audio"]:
        a1 = ET.SubElement(audio, "track")
        prev_end = None
        for i, p in enumerate(tl.pieces):
            if p.kind == "card":
                continue
            if prev_end is not None and p.kind == "main" and p.audio_in and prev_end == p.frame:
                ti = ET.SubElement(a1, "transitionitem")
                ET.SubElement(ti, "start").text = str(p.frame - p.audio_in)
                ET.SubElement(ti, "end").text = str(p.frame + p.audio_in)
                ET.SubElement(ti, "alignment").text = "center"
                _rate(ti, clk)
                eff = ET.SubElement(ti, "effect")
                ET.SubElement(eff, "name").text = "Cross Fade (+3dB)"
                ET.SubElement(eff, "effectid").text = "KGAudioTransCrossFade3dB"
                ET.SubElement(eff, "effectcategory").text = "Dissolve"
                ET.SubElement(eff, "effecttype").text = "transition"
                ET.SubElement(eff, "mediatype").text = "audio"
            ci = clipitem(a1, f"{p.name} · {m['name']}", p.frame, p.frames, in_point(p.src), total_src)
            file_el(ci, "file-1", m["path"], kind="av", frames=total_src)
            st = ET.SubElement(ci, "sourcetrack")
            ET.SubElement(st, "mediatype").text = "audio"
            ET.SubElement(st, "trackindex").text = "1"
            p_a, p_b = p.frame / F, (p.frame + p.frames) / F
            keys: list[tuple[int, float]] = []
            if p.kind == "flash":
                keys += [(0, 0.0), (p.fade_in, 1.0), (p.frames - p.fade_out, 1.0), (p.frames - 1, 0.0)]
            for a, b in tl.mutes:
                if b <= p_a or a >= p_b:
                    continue
                fa, fb = max(0, round(a * F) - p.frame), min(p.frames - 1, round(b * F) - p.frame)
                keys += [(max(0, fa - 1), 1.0), (fa, 0.0), (fb, 0.0), (min(p.frames - 1, fb + 1), 1.0)]
            if keys:
                effect(ci, "Audio Levels", "audiolevels", "audiolevels", "audio", "level", "Level", 1.0, 3.98109,
                       sorted(keys))
            if i in vitems:  # link picture + sound
                for cid, mt in ((vitems[i].get("id"), "video"), (ci.get("id"), "audio")):
                    for host in (vitems[i], ci):
                        link = ET.SubElement(host, "link")
                        ET.SubElement(link, "linkclipref").text = cid
                        ET.SubElement(link, "mediatype").text = mt
            prev_end = p.frame + p.frames
    for ly in tl.layers:
        if ly.kind not in ("bleeps", "music"):
            continue
        tr = ET.SubElement(audio, "track")
        file_frames = round((ly.offset + ly.frames / F + 1) * F)
        ci = clipitem(tr, ly.name, ly.frame, ly.frames, round(ly.offset * F), file_frames)
        file_el(ci, f"file-{ly.file.name}", ly.file, kind="audio", frames=file_frames)
        st = ET.SubElement(ci, "sourcetrack")
        ET.SubElement(st, "mediatype").text = "audio"
        ET.SubElement(st, "trackindex").text = "1"
        if ly.kind == "music":
            keys = [(min(ly.frames - 1, round(t * F)), gain(v)) for t, v in ly.keys]
            if ly.fade_in:
                keys = [(0, 0.0)] + [k if k[0] > 0 else (round(ly.fade_in * F), k[1]) for k in keys]
            if ly.fade_out:
                cut = ly.frames - 1 - round(ly.fade_out * F)
                last = next((v for w, v in reversed(keys) if w <= cut), gain(ly.gain_db))
                keys = [k for k in keys if k[0] < cut] + [(cut, last), (ly.frames - 1, 0.0)]
            dedup: dict[int, float] = {}
            for w, v in keys:
                dedup[w] = v
            effect(ci, "Audio Levels", "audiolevels", "audiolevels", "audio", "level", "Level", gain(ly.gain_db),
                   3.98109, sorted(dedup.items()))
    for mk in tl.marks:
        mel = ET.SubElement(seq, "marker")
        ET.SubElement(mel, "name").text = mk["name"]
        ET.SubElement(mel, "comment").text = mk["note"]
        ET.SubElement(mel, "in").text = str(min(tl.total - 1, round(mk["t"] * F)))
        ET.SubElement(mel, "out").text = "-1"
    return _pretty(root, "<!DOCTYPE xmeml>")


def write(kinds: list[str], tl: Timeline, stem: Path, lang: str | None) -> list[Path]:
    out = []
    for kind in kinds:
        if kind == "fcpxml":
            path = stem.with_name(stem.name + ".fcpxml")
            path.write_text(fcpxml(tl, lang), encoding="utf-8")
        else:
            path = stem.with_name(stem.name + ".premiere.xml")
            path.write_text(premiere_xml(tl), encoding="utf-8")
        out.append(path)
    return out


# ===================================================================== checks


def _t(v: str) -> Fraction:
    return Fraction(v[:-1]) if v != "0s" else Fraction(0)


def validate(text: str, kind: str) -> list[str]:
    """Format rules that the importers enforce (no DTD on Windows; tests also run Apple's
    content model through lxml). Returns problems, [] = looks importable."""
    problems: list[str] = []
    try:
        root = ET.fromstring(text.split("\n", 2)[2] if text.startswith("<?xml") else text)
    except ET.ParseError as exc:
        return [f"not well-formed XML: {exc}"]
    if kind == "fcpxml":
        if root.tag != "fcpxml" or not root.get("version"):
            problems.append("root must be <fcpxml version=...>")
        ids = {e.get("id") for e in root.iter() if e.get("id")}
        for e in root.iter():
            for attr in ("ref", "format"):
                if e.get(attr) and e.tag not in ("text-style",) and e.get(attr) not in ids:
                    problems.append(f"<{e.tag} {attr}={e.get(attr)}> points at nothing")
            for attr in ("offset", "start", "duration", "time", "audioStart", "audioDuration"):
                val = e.get(attr)
                if val is not None and not (val == "0s" or val.endswith("s")):
                    problems.append(f"<{e.tag} {attr}={val}> is not a rational time")
        seq = root.find(".//sequence")
        fmt = {f.get("id"): f for f in root.iter("format")}
        spine = root.find(".//spine")
        if seq is None or spine is None or not len(spine):
            return problems + ["no clip in the timeline"]
        fd = _t(fmt[seq.get("format")].get("frameDuration"))
        pos = Fraction(0)
        for c in spine:
            off, dur = _t(c.get("offset", "0s")), _t(c.get("duration", "0s"))
            if off != pos:
                problems.append(f"spine gap/overlap at {c.get('name')}: offset {off} != {pos}")
            for v in (off, dur):
                if (v / fd).denominator != 1:
                    problems.append(f"{c.get('name')}: {v}s is not on the sequence frame grid")
            if dur <= 0:
                problems.append(f"{c.get('name')}: empty clip")
            pos = off + dur
            # Keyframes live in their own clip's local time (anchored clips have their own).
            for clip in [c] + [ch for ch in c if ch.get("lane")]:
                start, cdur = _t(clip.get("start", "0s")), _t(clip.get("duration", "0s"))
                for adj in clip:
                    if not adj.tag.startswith("adjust-"):
                        continue
                    for kf in adj.iter("keyframe"):
                        if not start - fd <= _t(kf.get("time")) <= start + cdur + fd:
                            problems.append(f"{clip.get('name')}: keyframe at {kf.get('time')} outside the clip")
            for child in c:
                if child.tag in ("video", "asset-clip", "caption", "audio") and child.get("lane") in (None, "0"):
                    problems.append(f"{c.get('name')}: anchored <{child.tag}> without a lane")
            order = [ch.tag for ch in c]
            rank = {"adjust-transform": 0, "adjust-volume": 1, "video": 2, "asset-clip": 2, "caption": 2,
                    "audio": 2, "marker": 3}
            ranks = [rank.get(t, 2) for t in order]
            if ranks != sorted(ranks):
                problems.append(f"{c.get('name')}: children out of DTD order: {order}")
        if seq.get("duration") and _t(seq.get("duration")) != pos:
            problems.append(f"sequence duration {seq.get('duration')} != spine length {pos}s")
        for a in root.iter("asset"):
            src = a.find("media-rep")
            if src is None or not (src.get("src") or "").startswith("file:"):
                problems.append(f"asset {a.get('id')}: media file reference missing")
    else:
        if root.tag != "xmeml":
            problems.append("root must be <xmeml>")
        seq = root.find("sequence")
        if seq is None or root.find(".//clipitem") is None:
            return problems + ["no clip in the sequence"]
        total = int(seq.findtext("duration") or 0)
        defined = set()
        for f in root.iter("file"):
            if len(f):
                defined.add(f.get("id"))
        for f in root.iter("file"):
            if f.get("id") not in defined:
                problems.append(f"file {f.get('id')} used but never described")
        if root.find(".//pathurl") is None:
            problems.append("media file reference missing")
        for tr in root.iter("track"):
            pos = None
            for it in tr:
                if it.tag != "clipitem":
                    continue
                a, b = int(it.findtext("start")), int(it.findtext("end"))
                i, o = int(it.findtext("in")), int(it.findtext("out"))
                if not 0 <= i < o or b - a != o - i:
                    problems.append(f"{it.get('id')}: in/out don't match start/end")
                if pos is not None and a < pos:
                    problems.append(f"{it.get('id')}: overlaps the clip before it")
                if b > total:
                    problems.append(f"{it.get('id')}: ends after the sequence")
                for kf in it.iter("keyframe"):
                    w = int(kf.findtext("when"))
                    if not 0 <= w <= b - a:
                        problems.append(f"{it.get('id')}: keyframe at {w} outside the clip")
                pos = b
            items = list(tr)
            for k, it in enumerate(items):
                if it.tag == "transitionitem":
                    s, e = int(it.findtext("start")), int(it.findtext("end"))
                    nxt = items[k + 1] if k + 1 < len(items) else None
                    cut = int(nxt.findtext("start")) if nxt is not None and nxt.tag == "clipitem" else None
                    if cut is None or it.findtext("alignment") != "center" or s + e != 2 * cut:
                        problems.append("audio crossfade is not centered on a cut")
        for mk in seq.findall("marker"):
            if not 0 <= int(mk.findtext("in")) < max(1, total):
                problems.append("marker outside the sequence")
    return problems
