"""Music visualizer (1.2.18): in music mode (switch: off / auto) a clip becomes a beat-synced
visualizer instead of the plain video.

  background  the clip's cover art (the chosen AI cover, else a frame of the clip), blurred + dark
  art         the cover art, sharp, pulsing on every beat (librosa beat tracking)
  spectrum    9:16: a ring of bars around the art; 16:9: bars next to it (log-spaced, smoothed)
  lyrics      the transcript's words as karaoke (ASS \\kf sweep, gold over white), in clip time
  colours     the brand's navy / gold, or the active brand kit's caption colours

Frames are drawn with PIL and piped to ffmpeg together with the finished clip's sound (so cuts,
music and loudness from the main render are kept). The visualizer runs at 30 fps.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .errors import SharkyClipsError, require_tool
from .procs import no_window

FPS = 30
BANDS = 64
NAVY, GOLD, WHITE = (14, 26, 51), (217, 181, 106), (255, 255, 255)


def colours() -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """(accent, text) - the brand kit's highlight / caption colour when one is active."""
    try:
        from .edit import brand

        p = brand.active_preset()
        if p:
            def rgb(h: str, d):
                h = (h or "").lstrip("#")
                return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else d
            return rgb(p.get("caption_highlight"), GOLD), rgb(p.get("caption_color"), WHITE)
    except Exception:  # noqa: BLE001
        pass
    return GOLD, WHITE


# ===================================================================== analysis


def analyse(y: np.ndarray, sr: int, frames: int) -> dict:
    """Per video frame: spectrum bands (0..1), beat pulse (0..1), loudness (0..1)."""
    import librosa

    hop = max(1, int(round(sr / FPS)))
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    edges = np.geomspace(40, min(16000, sr / 2 - 1), BANDS + 1)
    bands = np.zeros((BANDS, S.shape[1]), np.float32)
    for i in range(BANDS):
        sel = (freqs >= edges[i]) & (freqs < edges[i + 1])
        if not sel.any():
            sel = np.argmin(np.abs(freqs - edges[i]))
            bands[i] = S[sel]
        else:
            bands[i] = S[sel].mean(axis=0)
    db = 10 * np.log10(bands + 1e-10)
    lo, hi = np.percentile(db, 20), np.percentile(db, 99.5)
    norm = np.clip((db - lo) / max(1e-6, hi - lo), 0, 1)
    # attack fast, fall slowly (looks musical)
    sm = np.zeros_like(norm)
    for t in range(norm.shape[1]):
        prev = sm[:, t - 1] if t else norm[:, 0]
        sm[:, t] = np.where(norm[:, t] > prev, 0.6 * norm[:, t] + 0.4 * prev, 0.86 * prev + 0.14 * norm[:, t])
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop, units="frames")
    pulse = np.zeros(sm.shape[1], np.float32)
    for b in beats:
        n = np.arange(0, min(12, len(pulse) - b))
        pulse[b + n] = np.maximum(pulse[b + n], np.exp(-n / 3.5))
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    rms = np.clip(rms / max(1e-6, np.percentile(rms, 98)), 0, 1)

    def fit(a: np.ndarray) -> np.ndarray:
        if a.shape[-1] >= frames:
            return a[..., :frames]
        pad = [(0, 0)] * (a.ndim - 1) + [(0, frames - a.shape[-1])]
        return np.pad(a, pad, mode="edge")

    return {"bands": fit(sm), "pulse": fit(pulse), "rms": fit(rms.astype(np.float32)),
            "tempo": float(np.atleast_1d(tempo)[0]), "beats": [float(b) / FPS for b in beats]}


# ===================================================================== drawing


def _art(project, cand: dict, frame: str, video: Path, at: float):
    """Cover art: the chosen AI cover of this size (else the other size), else the source video at
    the clip's peak, else (a flat / black frame: a still image, an audio-only upload) a brand tile."""
    from PIL import Image

    from . import aicovers

    p = aicovers.chosen_file(project, cand["id"], frame) or aicovers.chosen_file(
        project, cand["id"], "wide" if frame == "tall" else "tall")
    if p is not None:
        return Image.open(p).convert("RGB")
    src = project.source_path or video
    t = float(cand.get("peak") or at) if project.source_path else at
    ffmpeg = require_tool("ffmpeg")
    r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(src),
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"],
                       capture_output=True, timeout=60, **no_window())
    if r.returncode == 0 and r.stdout:
        import io

        img = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        if float(np.asarray(img.convert("L"), dtype=np.float32).std()) > 12:
            return img
    return brand_tile()


def brand_tile(size: int = 900):
    """Navy-to-gold gradient with a big music note: the art when there's no picture to use."""
    from PIL import Image, ImageDraw

    y = np.linspace(0, 1, size, dtype=np.float32)[:, None, None]
    x = np.linspace(0, 1, size, dtype=np.float32)[None, :, None]
    k = np.clip(0.65 * y + 0.35 * x, 0, 1)
    arr = (np.array(NAVY, np.float32) * (1 - k) + np.array(GOLD, np.float32) * k * 0.85).astype(np.uint8)
    img = Image.fromarray(np.broadcast_to(arr, (size, size, 3)).copy())
    d = ImageDraw.Draw(img)
    c = size // 2
    r = size // 9
    d.ellipse((c - 2 * r, c + r - r // 2, c - 2 * r + 2 * r, c + r + r + r // 2), fill=WHITE)  # note head
    d.ellipse((c + r // 2, c + r // 2 - r // 2, c + r // 2 + 2 * r, c + r // 2 + r + r // 2), fill=WHITE)
    d.rectangle((c - r // 4 - 8, c - 2 * r, c - r // 4 + 8, c + r + r // 2), fill=WHITE)  # stems
    d.rectangle((c + 2 * r + r // 2 - 16, c - 2 * r - r // 2, c + 2 * r + r // 2, c + r), fill=WHITE)
    d.polygon([(c - r // 4 - 8, c - 2 * r), (c + 2 * r + r // 2, c - 2 * r - r // 2 - 20),
               (c + 2 * r + r // 2, c - 2 * r + r // 3), (c - r // 4 - 8, c - 2 * r + r // 2)], fill=WHITE)
    return img


def _square(img, size: int, radius: int):
    from PIL import Image, ImageDraw

    w, h = img.size
    s = min(w, h)
    sq = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s)).resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(sq, (0, 0), mask)
    return out


def _background(img, W: int, H: int):
    from PIL import Image, ImageEnhance, ImageFilter

    w, h = img.size
    k = max(W / w, H / h)
    bg = img.resize((int(w * k) + 1, int(h * k) + 1), Image.LANCZOS)
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=max(W, H) // 40))
    bg = ImageEnhance.Brightness(bg).enhance(0.42)
    tint = Image.new("RGB", (W, H), NAVY)
    return Image.blend(bg, tint, 0.35)


class Painter:
    def __init__(self, art, W: int, H: int, frame: str, accent):
        from PIL import Image

        self.W, self.H, self.frame, self.accent = W, H, frame, accent
        self.bg = _background(art, W, H).convert("RGBA")
        if frame == "wide":
            self.size = int(H * 0.56)
            self.center = (int(W * 0.27), int(H * 0.44))
        else:
            self.size = int(W * 0.62)
            self.center = (W // 2, int(H * 0.36))
        base = _square(art, self.size, self.size // 14)
        # a few pre-scaled arts for the beat pulse (scaling every frame is slow)
        self.scales = {}
        for k in range(9):
            f = 1.0 + 0.07 * k / 8
            s = int(self.size * f)
            self.scales[k] = base.resize((s, s), Image.LANCZOS)
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        from PIL import ImageDraw, ImageFilter

        cx, cy = self.center
        r = self.size // 2 + 20
        ImageDraw.Draw(shadow).rounded_rectangle((cx - r, cy - r + 24, cx + r, cy + r + 24), radius=self.size // 12,
                                                 fill=(0, 0, 0, 150))
        self.bg.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))

    def frame_image(self, bands: np.ndarray, pulse: float, level: float):
        from PIL import ImageDraw

        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        cx, cy = self.center
        acc = self.accent
        if self.frame == "wide":
            x0, x1 = int(self.W * 0.52), int(self.W * 0.95)
            base_y = int(self.H * 0.62)
            n = BANDS
            bw = (x1 - x0) / n
            for i in range(n):
                v = float(bands[i])
                h = int(8 + v * self.H * 0.36)
                x = int(x0 + i * bw)
                d.rounded_rectangle((x, base_y - h, int(x + bw * 0.62), base_y), radius=3, fill=acc + (230,))
                d.rectangle((x, base_y + 6, int(x + bw * 0.62), base_y + 6 + h // 4), fill=acc + (60,))
        else:
            r0 = self.size * 0.5 * (1.0 + 0.07 * pulse) + 26
            n = BANDS
            for i in range(n):
                v = float(bands[i if i < n // 2 else n - 1 - i])  # mirrored: bass at top and bottom
                ang = -math.pi / 2 + 2 * math.pi * i / n
                ln = 14 + v * self.size * 0.26
                c, s = math.cos(ang), math.sin(ang)
                w = max(4.0, self.size * 0.012)
                pa = (cx + c * r0 - s * w, cy + s * r0 + c * w)
                pb = (cx + c * r0 + s * w, cy + s * r0 - c * w)
                pc = (cx + c * (r0 + ln) + s * w, cy + s * (r0 + ln) - c * w)
                pd = (cx + c * (r0 + ln) - s * w, cy + s * (r0 + ln) + c * w)
                d.polygon([pa, pb, pc, pd], fill=acc + (int(150 + 100 * v),))
        art = self.scales[int(round(min(1.0, pulse) * 8))]
        img.alpha_composite(art, (cx - art.width // 2, cy - art.height // 2))
        # a glow line that breathes with the loudness
        gy = int(self.H * (0.88 if self.frame == "wide" else 0.62))
        half = int(self.W * 0.3 * (0.3 + 0.7 * level))
        d.rounded_rectangle((self.W // 2 - half, gy, self.W // 2 + half, gy + 4), radius=2, fill=acc + (200,))
        return img.convert("RGB")


# ===================================================================== lyrics


def lyrics_ass(words: list[dict], W: int, H: int, frame: str, lang: str | None, accent, text_col) -> str:
    """Karaoke lines: words light up (\\kf) from white to the accent colour."""
    from .clips import _ass_escape, _ass_time, _font_for, group_words

    def ass(c) -> str:
        return f"&H00{c[2]:02X}{c[1]:02X}{c[0]:02X}"

    size = int((64 if frame != "wide" else 56) * W / (1080 if frame != "wide" else 1920))
    y = int(H * (0.74 if frame != "wide" else 0.86))
    out = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0",
           "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
           "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
           "MarginR, MarginV, Encoding",
           f"Style: lyr,{_font_for(lang)},{size},{ass(accent)},{ass(text_col)},&H00331A0E,&H96000000,-1,0,0,0,100,100,0,0,1,"
           f"{max(3, size // 14)},{max(2, size // 28)},5,60,60,0,1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    groups = group_words(words, 26 if frame != "wide" else 40, 5 if frame != "wide" else 7, lang)
    prev_end = 0.0
    for gi, g in enumerate(groups):
        a, b = g[0]["start"], g[-1]["end"]
        nxt = groups[gi + 1][0]["start"] - 0.25 if gi + 1 < len(groups) else None
        parts = []
        t = a
        for w in g:
            pre = max(0, int(round((w["start"] - t) * 100)))
            if pre:
                parts.append(f"{{\\k{pre}}}")
            dur = max(1, int(round((w["end"] - w["start"]) * 100)))
            parts.append(f"{{\\kf{dur}}}{_ass_escape(w['word'])} ")
            t = w["end"]
        show_a, show_b = max(prev_end, a - 0.25), b + 0.35  # never two lines on screen at once
        if nxt is not None:
            show_b = max(b, min(show_b, nxt))
        prev_end = show_b
        out.append(f"Dialogue: 0,{_ass_time(show_a)},{_ass_time(show_b)},lyr,,0,0,0,,"
                   f"{{\\pos({W // 2},{y})\\fad(120,150)}}" + "".join(parts).rstrip())
    return "\n".join(out) + "\n"


# ===================================================================== render


def render(project, cand: dict, words: list[dict], lang: str | None, video: Path, dest: Path, *, frame: str,
           size: tuple[int, int], enc_args: list[str], on_progress=None) -> dict:
    """`video` (the finished clip) -> `dest`: visualizer picture + the clip's own sound."""
    from . import governor, procs
    from .edit.music import decode

    ffmpeg = require_tool("ffmpeg")
    W, H = size
    y = decode(video, 0.0, None, sr=22050, channels=1)
    if y.size < 22050:
        raise SharkyClipsError("This clip has no sound for a visualizer.")
    dur = len(y) / 22050
    frames = int(math.ceil(dur * FPS))
    gov_threads = max(1, governor.cpu_threads())
    feats = analyse(y, 22050, frames)
    accent, text_col = colours()
    painter = Painter(_art(project, cand, "wide" if frame == "wide" else "tall", video, dur / 2), W, H, frame, accent)
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-viz-"))
    try:
        (work / "lyrics.ass").write_text(lyrics_ass(words, W, H, frame, lang, accent, text_col), encoding="utf-8")
        vf = "ass=lyrics.ass,format=yuv420p" if words else "format=yuv420p"
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-i", str(video), "-map", "0:v", "-map", "1:a?",
               "-vf", vf, *enc_args, "-c:a", "copy", "-shortest", "-movflags", "+faststart",
               "-threads", str(gov_threads), str(dest)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(work), **no_window())
        procs.track(proc)
        try:
            for i in range(frames):
                if i % 15 == 0:
                    governor.gate()
                    if on_progress:
                        on_progress(i / frames)
                img = painter.frame_image(feats["bands"][:, i], float(feats["pulse"][i]), float(feats["rms"][i]))
                proc.stdin.write(img.tobytes())
            proc.stdin.close()
            err = proc.stderr.read().decode(errors="replace")
            code = proc.wait()
        except (BrokenPipeError, OSError):
            proc.kill()
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            code = proc.wait()
        finally:
            procs.untrack(proc)
        if code != 0:
            raise SharkyClipsError(f"Could not make the music visualizer: {err.strip()[-300:]}")
    finally:
        import shutil

        shutil.rmtree(work, ignore_errors=True)
    if on_progress:
        on_progress(1.0)
    return {"tempo": round(feats["tempo"], 1), "beats": len(feats["beats"]), "frames": frames}
