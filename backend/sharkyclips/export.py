"""Export & publishing (Phase 9): file formats, platform presets, subtitle files.

  formats   MP4 H.264 / HEVC / AV1 (hardware AV1 only), MOV, WebM VP9, GIF (palette + size
            limit), MP3 / M4A (audio only). Hardware encoders first, CPU fallback (render.py).
  presets   YouTube Shorts, TikTok, Instagram Reels, X, YouTube 16:9: size, fps, bitrate, max
            length and the "safe zone" (the platform's own buttons / captions cover the edges;
            our subtitles and hook text stay out of it).
  sidecars  SRT / VTT in any of the 7 languages (translated by the local LLM when needed);
            editor timelines (editors.py: FCPXML for DaVinci Resolve + Final Cut, Premiere XML).

Exports of a clip live in <project>/exports/clips/, listed in exports/clips.json.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from . import config, languages
from .clips import (FLASH_SECONDS, NO_SPACE_LANGS, ClipOptions, Facecam, OutputSpec, clip_text,
                    group_words, render_clip, translated_words)
from .errors import SharkyClipsError, require_tool
from .procs import no_window
from .project import Project, read_json, write_json_atomic
from .render import RenderResult, run_ffmpeg


@dataclass(frozen=True)
class Format:
    id: str
    label: str
    kind: str  # video | gif | audio
    codec: str | None  # video codec (render.pick_codec)
    container: str
    ext: str
    mime: str
    audio: str = "aac"  # aac | opus | mp3 | none


FORMATS: dict[str, Format] = {f.id: f for f in (
    Format("mp4_h264", "MP4 · H.264", "video", "h264", "mp4", ".mp4", "video/mp4"),
    Format("mp4_hevc", "MP4 · HEVC", "video", "hevc", "mp4", ".mp4", "video/mp4"),
    Format("mp4_av1", "MP4 · AV1", "video", "av1", "mp4", ".mp4", "video/mp4"),
    Format("mov", "MOV · H.264", "video", "h264", "mov", ".mov", "video/quicktime"),
    Format("webm_vp9", "WebM · VP9", "video", "vp9", "webm", ".webm", "video/webm", "opus"),
    Format("gif", "GIF", "gif", None, "gif", ".gif", "image/gif", "none"),
    Format("mp3", "MP3", "audio", None, "mp3", ".mp3", "audio/mpeg", "mp3"),
    Format("m4a", "M4A", "audio", None, "m4a", ".m4a", "audio/mp4", "aac"),
)}


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    frame: str  # vertical | wide
    width: int
    height: int
    fps: int
    bitrate_k: int
    audio_k: int
    max_seconds: float | None
    safe: tuple[int, int, int, int]  # top, right, bottom, left - canvas pixels (1080x1920 / 1920x1080)
    format: str = "mp4_h264"
    thumbnail: bool = False  # the platform takes a custom thumbnail through its API


# Safe zones: where each app draws its own buttons, captions and progress bar (measured on
# 1080x1920 screenshots of the apps in 2025/2026, rounded up a little).
PRESETS: dict[str, Preset] = {p.id: p for p in (
    Preset("youtube_shorts", "YouTube Shorts", "vertical", 1080, 1920, 60, 12000, 192, 180,
           (140, 140, 380, 40)),
    Preset("tiktok", "TikTok", "vertical", 1080, 1920, 60, 10000, 192, 600, (160, 150, 440, 60)),
    Preset("instagram_reels", "Instagram Reels", "vertical", 1080, 1920, 30, 8000, 192, 180,
           (220, 130, 420, 60)),
    Preset("x", "X / Twitter", "vertical", 720, 1280, 60, 6000, 160, 140, (0, 0, 180, 0)),
    Preset("youtube_16x9", "YouTube 16:9", "wide", 1920, 1080, 60, 12000, 192, None, (0, 0, 90, 0),
           thumbnail=True),
)}

# GIF size limit: (width, fps) steps, tried in order until the file fits.
GIF_LADDER = ((480, 15), (420, 12), (360, 12), (320, 10), (270, 10), (240, 8))
GIF_LADDER_WIDE = ((640, 15), (560, 12), (480, 12), (400, 10), (320, 10), (256, 8))
DEFAULT_GIF_MB = 10.0
SUB_KINDS = ("srt", "vtt")


def exports_root(project: Project) -> Path:
    return project.dir / "exports" / "clips"


def registry_path(project: Project) -> Path:
    return project.dir / "exports" / "clips.json"


_lock = threading.RLock()


# ------------------------------------------------------------------ capabilities


def available_formats() -> list[dict]:
    """Which formats this PC can make, and with which encoder (first call test-encodes)."""
    from .render import pick_codec

    have_ffmpeg = shutil.which("ffmpeg") is not None
    out = []
    for f in FORMATS.values():
        enc = None
        if f.codec and have_ffmpeg:
            try:
                enc = pick_codec(f.codec)
            except SharkyClipsError:  # e.g. an ffmpeg build without any H.264 encoder
                enc = None
        ok = f.codec is None or enc is not None
        out.append({"id": f.id, "label": f.label, "kind": f.kind, "ext": f.ext, "available": ok,
                    "encoder": enc.label if enc else None, "hardware": bool(enc and enc.hardware)})
    return out


def preset_view(p: Preset) -> dict:
    d = asdict(p)
    d["safe"] = list(p.safe)
    return d


def check_length(preset_id: str | None, duration: float) -> list[dict]:
    """Warnings for one clip with this preset (the UI shows them before rendering)."""
    p = PRESETS.get(preset_id or "")
    if p and p.max_seconds and duration > p.max_seconds + 0.05:
        return [{"code": "too_long", "max": p.max_seconds, "duration": round(duration, 1)}]
    return []


# ------------------------------------------------------------------ size estimate

# Bytes per second of 1080x1920 30 fps video in constant-quality mode, by codec (measured
# on gameplay; refined from this PC's own exports in ~/.sharkyclips/export_stats.json).
QUALITY_BPS = {"h264": 520_000, "hevc": 375_000, "av1": 345_000, "vp9": 460_000}


def _stats_path() -> Path:
    return config.config_dir() / "export_stats.json"


def _load_stats() -> dict:
    try:
        return read_json(_stats_path()) if _stats_path().is_file() else {}
    except Exception:  # noqa: BLE001
        return {}


def _record_stats(key: str, bytes_per_s_norm: float) -> None:
    with _lock:
        data = _load_stats()
        old = data.get(key) or {}
        n = int(old.get("samples") or 0)
        avg = bytes_per_s_norm if n == 0 else old["bps"] + (bytes_per_s_norm - old["bps"]) / min(n + 1, 10)
        data[key] = {"bps": round(avg), "samples": n + 1}
        try:
            write_json_atomic(_stats_path(), data)
        except OSError:
            pass


def _pixels_factor(w: int, h: int, fps: float) -> float:
    """Relative to 1080x1920 at 30 fps (bitrate grows ~ with pixels^0.85, fps^0.6)."""
    return ((w * h) / (1080 * 1920)) ** 0.85 * (fps / 30) ** 0.6


def resolve_spec(fmt: Format, preset: Preset | None, src_fps: float, burn: bool) -> OutputSpec:
    if preset:
        return OutputSpec(frame=preset.frame, width=preset.width, height=preset.height, fps=preset.fps,
                          codec=fmt.codec or "h264", bitrate_k=preset.bitrate_k,
                          audio="opus" if fmt.audio == "opus" else "aac", audio_k=preset.audio_k,
                          container=fmt.container if fmt.kind == "video" else "mp4", burn_captions=burn,
                          safe=preset.safe, max_seconds=preset.max_seconds)
    return OutputSpec(codec=fmt.codec or "h264", audio="opus" if fmt.audio == "opus" else "aac",
                      container=fmt.container if fmt.kind == "video" else "mp4", burn_captions=burn,
                      fps=min(60.0, src_fps or 30))


def estimate_bytes(fmt_id: str, preset_id: str | None, duration: float, src_fps: float = 30,
                   gif_max_mb: float | None = None, flash: bool = False) -> int:
    fmt = FORMATS[fmt_id]
    preset = PRESETS.get(preset_id or "")
    total = duration + (FLASH_SECONDS if flash and fmt.kind != "audio" else 0)
    if fmt.kind == "audio":
        return int(192_000 / 8 * total)
    if fmt.kind == "gif":
        w, fps = (GIF_LADDER_WIDE if preset and preset.frame == "wide" else GIF_LADDER)[0]
        h = w * 9 / 16 if preset and preset.frame == "wide" else w * 16 / 9
        raw = w * h * fps * total * 0.11  # bytes: gameplay GIFs are ~0.1 byte/pixel/frame
        limit = (gif_max_mb or DEFAULT_GIF_MB) * 1024 * 1024
        return int(min(raw, limit))
    spec = resolve_spec(fmt, preset, src_fps, True)
    audio = spec.audio_k * 1000 / 8 * total
    if spec.bitrate_k:
        # VBR overshoots the target a little on fast gameplay (measured 1.05-1.10) + container
        return int(spec.bitrate_k * 1000 / 8 * total * 1.07 + audio)
    w, h = (spec.width, spec.height) if spec.width and spec.height else spec.canvas
    fps = min(spec.fps or 30, src_fps or 30)
    learned = (_load_stats().get(f"q:{spec.codec}") or {}).get("bps")
    bps = float(learned or QUALITY_BPS.get(spec.codec, 520_000))
    return int(bps * _pixels_factor(w, h, fps) * total + audio)


# ------------------------------------------------------------------ subtitle files


def _ts(t: float, sep: str) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def subtitle_cues(words: list[dict], duration: float, lang: str | None, offset: float = 0.0) -> list[dict]:
    """Words -> readable cues (max ~42 characters, broken at pauses / sentence ends)."""
    joiner = "" if lang in NO_SPACE_LANGS else " "
    groups = group_words(words, 18 if lang in NO_SPACE_LANGS else 42, 12, lang)
    cues = []
    for gi, g in enumerate(groups):
        start = g[0]["start"]
        nxt = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else duration
        end = min(max(g[-1]["end"] + 0.3, start + 0.8), nxt, duration)
        if end <= start:
            continue
        cues.append({"start": start + offset, "end": end + offset, "text": joiner.join(w["word"] for w in g)})
    return cues


def to_srt(cues: list[dict]) -> str:
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{_ts(c['start'], ',')} --> {_ts(c['end'], ',')}\n{c['text']}\n")
    return "\n".join(out)


def to_vtt(cues: list[dict], lang: str | None = None) -> str:
    out = ["WEBVTT" + (f"\nLanguage: {lang}" if lang else ""), ""]
    for c in cues:
        out.append(f"{_ts(c['start'], '.')} --> {_ts(c['end'], '.')}\n{c['text']}\n")
    return "\n".join(out)


def clip_cues(project: Project, cand: dict, opts: ClipOptions, lang: str | None,
              translate: Callable[[str], list[dict]] | None = None, offset: float = 0.0,
              plan=None) -> tuple[list[dict], str | None]:
    """Cues of one clip in `lang` ("" / None = the spoken language). `translate(lang)` returns
    translated subtitle lines when the clip has none in that language yet (local LLM).
    plan: the render's EditPlan - the cues then follow its cuts (and a moved loop end), so
    they match the finished video; `offset` = what comes before its main part."""
    start, end = (plan.start, plan.end) if plan is not None else (float(cand["start"]), float(cand["end"]))
    duration = max(0.5, plan.out_duration if plan is not None else end - start)
    spoken = None
    if project.transcript_path.is_file():
        spoken = read_json(project.transcript_path).get("language")
    want = lang or spoken
    if want and want != spoken and not (cand.get("translations") or {}).get(want):
        if translate is None:
            raise SharkyClipsError(f"This clip has no {want} subtitles yet.",
                                   "The local AI translates them; install it with: python cli.py doctor")
        lines = translate(want)
        cand = {**cand, "translations": {**(cand.get("translations") or {}), want: lines}}
    o = ClipOptions.from_dict({**opts.to_dict(), "subtitle_lang": want if want != spoken else ""})
    if want and want != spoken:
        words = translated_words(cand["translations"][want], start, end, want)
        w_lang = want
        if plan is not None:  # evenly timed pseudo-words: map them through the cuts
            mapped = []
            for w in words:
                s0, e0 = plan.to_out(w["start"] + start, "fwd"), plan.to_out(w["end"] + start, "back")
                if s0 is not None and e0 is not None and e0 > s0:
                    mapped.append({**w, "start": s0, "end": e0})
            words = mapped
    elif plan is not None:
        words, w_lang = plan.out_words(), plan.lang or spoken
    else:
        words, w_lang, _h, _hl = clip_text(project, cand, o)
    return subtitle_cues(words, duration, w_lang, offset), w_lang


def write_subtitles(dest_stem: Path, cues: list[dict], lang: str | None, kinds: list[str]) -> list[Path]:
    out = []
    suffix = f".{lang}" if lang else ""
    for k in kinds:
        path = dest_stem.with_name(dest_stem.name + f"{suffix}.{k}")
        path.write_text(to_srt(cues) if k == "srt" else to_vtt(cues, lang), encoding="utf-8")
        out.append(path)
    return out


# ------------------------------------------------------------------ audio + GIF


def _render_audio(project: Project, cand: dict, fmt: Format, dest: Path,
                  on_progress: Callable[[float], None] | None, opts: ClipOptions | None = None) -> RenderResult:
    ffmpeg = require_tool("ffmpeg")
    if project.source_path is None:
        raise SharkyClipsError("The project's source video is missing.")
    start, end = float(cand["start"]), float(cand["end"])
    duration = max(0.5, end - start)
    tmp = dest.with_name(dest.stem + ".partial" + dest.suffix)
    codec = ["-c:a", "libmp3lame", "-b:a", "192k", "-f", "mp3"] if fmt.audio == "mp3" else \
        ["-c:a", "aac", "-b:a", "192k", "-f", "ipod", "-movflags", "+faststart"]
    info: dict = {}
    work = None
    plan = None
    if opts is not None:  # cuts / bleeps / music: the same sound as the video export
        from .edit import plan as plan_mod

        plan = plan_mod.build(project, cand, opts, vertical=False, fps=100)
        plan.brand, plan.intro_s, plan.outro_s = None, 0.0, 0.0
    if plan is not None and plan.audio_active:
        from .edit import audiomix

        work = Path(tempfile.mkdtemp(prefix="sharkyclips-audio-"))
        mix = audiomix.build(project.source_path, plan, work / "mix.wav")
        info = {"music": mix.music, "lufs": mix.lufs, "duration": round(mix.seconds, 2)}
        duration = mix.seconds
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-i", str(work / "mix.wav"),
               *codec, "-progress", "pipe:1", str(tmp)]
    else:
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", "-ss", f"{start:.3f}",
               "-t", f"{duration:.3f}", "-i", str(project.source_path.resolve()), "-vn", "-map", "0:a:0",
               "-af", f"afade=t=in:d=0.12,afade=t=out:st={max(0.0, duration - 0.2):.3f}:d=0.2",
               *codec, "-progress", "pipe:1", str(tmp)]
    t0 = time.perf_counter()
    try:
        code, err = run_ffmpeg(cmd, duration, on_progress)
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)
    if code != 0:
        tmp.unlink(missing_ok=True)
        raise SharkyClipsError(f"ffmpeg could not export the audio: {err.strip()[-400:]}",
                               "Does this video have a sound track?")
    os.replace(tmp, dest)
    return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, "CPU", info)


def _gif_pass(src: Path, dest: Path, width: int, fps: int) -> int:
    ffmpeg = require_tool("ffmpeg")
    vf = (f"fps={fps},scale={width}:-2:flags=lanczos,split[a][b];"
          "[a]palettegen=max_colors=128:stats_mode=diff[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-filter_complex", vf,
           "-loop", "0", "-f", "gif", str(dest)]
    from . import procs

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", **no_window())
    procs.track(proc)
    try:
        _out, err = proc.communicate(timeout=900)
    except BaseException:
        proc.kill()
        proc.wait()
        raise
    finally:
        procs.untrack(proc)
    if proc.returncode != 0:
        raise SharkyClipsError(f"ffmpeg could not make the GIF: {(err or '').strip()[-400:]}")
    return dest.stat().st_size


def _render_gif(project: Project, cand: dict, opts: ClipOptions, facecam: Facecam | None,
                preset: Preset | None, burn: bool, dest: Path, max_mb: float,
                on_progress: Callable[[float], None] | None) -> tuple[RenderResult, dict]:
    """Optimized-palette GIF: render a small clean video once, then palette passes, stepping
    down size / frame rate until the file fits the limit."""
    from . import governor

    frame = preset.frame if preset else "vertical"
    steps = GIF_LADDER if frame == "vertical" else GIF_LADDER_WIDE
    w0, fps0 = steps[0]
    h0 = (w0 * 16 // 9) // 2 * 2 if frame == "vertical" else (w0 * 9 // 16) // 2 * 2
    spec = OutputSpec(frame=frame, width=w0, height=h0, fps=fps0, codec="h264", audio="none",
                      burn_captions=burn, safe=preset.safe if preset else (0, 0, 0, 0))
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-gif-"))
    t0 = time.perf_counter()
    try:
        inter = work / "gif.mp4"
        res = render_clip(project, cand, opts, facecam, inter,
                          on_progress=(lambda s: on_progress(s * 0.6)) if on_progress else None, spec=spec)
        limit = max_mb * 1024 * 1024
        tmp = dest.with_name(dest.stem + ".partial.gif")
        tried = []
        size = 0
        for i, (w, fps) in enumerate(steps):
            governor.checkpoint()
            size = _gif_pass(inter, tmp, w, fps)
            tried.append({"width": w, "fps": fps, "bytes": size})
            if on_progress:
                on_progress(0.6 + 0.4 * (i + 1) / len(steps))
            if size <= limit:
                break
        os.replace(tmp, dest)
        info = {"gif_steps": tried, "gif_limit_mb": max_mb, "gif_over_limit": size > limit}
        return RenderResult(dest, time.perf_counter() - t0, dest.stat().st_size, res.encoder), info
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------ one export


@dataclass
class ExportRequest:
    format: str | None = "mp4_h264"  # None = sidecar files only (subtitles / editor timelines)
    preset: str | None = None
    burn_captions: bool = True
    subtitles: tuple[str, ...] = ()  # "srt", "vtt"
    subtitle_lang: str = ""  # "" = spoken language
    editors: tuple[str, ...] = ()  # "fcpxml", "premiere"
    gif_max_mb: float = DEFAULT_GIF_MB

    @classmethod
    def from_dict(cls, d: dict) -> "ExportRequest":
        fmt = d.get("format") or None
        if fmt is not None and fmt not in FORMATS:
            raise SharkyClipsError(f"Unknown export format '{fmt}'.", f"Use one of: {', '.join(FORMATS)}")
        preset = d.get("preset") or None
        if preset is not None and preset not in PRESETS:
            raise SharkyClipsError(f"Unknown platform preset '{preset}'.")
        subs = tuple(k for k in (d.get("subtitles") or []) if k in SUB_KINDS)
        eds = tuple(k for k in (d.get("editors") or []) if k in ("fcpxml", "premiere"))
        lang = str(d.get("subtitle_lang") or "")
        if lang:
            languages.require(lang)
        if fmt is None and not subs and not eds:
            raise SharkyClipsError("Choose a format, subtitle files or an editor timeline.")
        try:
            gif_mb = float(d.get("gif_max_mb") or DEFAULT_GIF_MB)
        except (TypeError, ValueError):
            gif_mb = DEFAULT_GIF_MB
        return cls(fmt, preset, d.get("burn_captions") is not False, subs, lang, eds,
                   max(0.5, min(100.0, gif_mb)))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["subtitles"], d["editors"] = list(self.subtitles), list(self.editors)
        return d


def export_stem(cand: dict, req: ExportRequest) -> str:
    tag = req.preset or "custom"
    fmt = req.format or "files"
    return f"{cand['rank']:02d}_{cand['id']}_{tag}_{fmt}"


def load_registry(project: Project) -> list[dict]:
    path = registry_path(project)
    try:
        items = (read_json(path).get("exports") or []) if path.is_file() else []
    except Exception:  # noqa: BLE001
        items = []
    root = exports_root(project)
    out = []
    for e in items:
        files = [f for f in e.get("files", []) if (root / f["name"]).is_file()]
        if files:
            out.append({**e, "files": files})
    return out


def _save_entry(project: Project, entry: dict) -> None:
    with _lock:
        items = [e for e in load_registry(project) if e["id"] != entry["id"]]
        items.append(entry)
        write_json_atomic(registry_path(project), {"version": 1, "exports": items})


def delete_export(project: Project, export_id: str) -> bool:
    with _lock:
        items = load_registry(project)
        hit = next((e for e in items if e["id"] == export_id), None)
        if hit is None:
            return False
        for f in hit["files"]:
            (exports_root(project) / f["name"]).unlink(missing_ok=True)
        write_json_atomic(registry_path(project),
                          {"version": 1, "exports": [e for e in items if e["id"] != export_id]})
        return True


def file_path(project: Project, name: str) -> Path | None:
    """A file of an export, by name (only names the registry knows)."""
    for e in load_registry(project):
        for f in e["files"]:
            if f["name"] == name:
                return exports_root(project) / name
    return None


def _file_entry(path: Path, role: str, mime: str, extra: dict | None = None) -> dict:
    return {"name": path.name, "role": role, "mime": mime, "size_bytes": path.stat().st_size, **(extra or {})}


def run_export(project: Project, cand: dict, opts: ClipOptions, facecam: Facecam | None, req: ExportRequest,
               on_progress: Callable[[str, float | None], None] | None = None,
               translate: Callable[[str], list[dict]] | None = None) -> dict:
    """Make every file of one export request for one clip. Returns its registry entry."""
    meta = project.load_meta()
    src_fps = float(meta.get("fps") or 30)
    fmt = FORMATS.get(req.format or "")
    preset = PRESETS.get(req.preset or "")
    root = exports_root(project)
    root.mkdir(parents=True, exist_ok=True)
    stem = export_stem(cand, req)
    files: list[dict] = []
    extra: dict = {}
    duration = float(cand["duration"])
    flash = bool(opts.hook_flash) and not opts.loop and (fmt is None or fmt.kind != "audio")

    def stage(name: str, frac: float | None = None) -> None:
        if on_progress:
            on_progress(name, frac)

    t0 = time.perf_counter()
    encoder = None
    if fmt is not None:
        dest = root / f"{stem}{fmt.ext}"
        stage("exporting", 0.0)

        def prog(s: float) -> None:
            stage("exporting", min(1.0, s / max(duration + (FLASH_SECONDS if flash else 0), 0.1)))

        if fmt.kind == "audio":
            res = _render_audio(project, cand, fmt, dest, prog, opts)
        elif fmt.kind == "gif":
            res, extra = _render_gif(project, cand, opts, facecam, preset, req.burn_captions, dest, req.gif_max_mb,
                                     lambda f: stage("exporting", f))
        else:
            spec = resolve_spec(fmt, preset, src_fps, req.burn_captions)
            res = render_clip(project, cand, opts, facecam, dest, on_progress=prog, spec=spec)
            if not spec.bitrate_k:  # learn this PC's constant-quality sizes for the estimate
                w, h = (spec.width, spec.height) if spec.width and spec.height else spec.canvas
                fps = min(spec.fps or 30, src_fps)
                total = duration + (FLASH_SECONDS if flash else 0)
                video_bytes = max(1.0, res.size_bytes - spec.audio_k * 1000 / 8 * total)
                _record_stats(f"q:{spec.codec}", video_bytes / total / _pixels_factor(w, h, fps))
        encoder = res.encoder
        if res.info:
            extra["edits"] = res.info
            if res.info.get("music"):
                extra["music"] = res.info["music"]
        files.append(_file_entry(dest, "media", fmt.mime))

    sub_lang = None
    if req.subtitles or req.editors:
        from . import editors
        from .edit import plan as plan_mod

        stage("subtitles", None)
        # The cues follow the render's plan: its cuts, the intro card, the flash, a moved loop end.
        vertical = (preset.frame != "wide") if preset else True
        spec_fps = preset.fps if preset else None
        max_len = preset.max_seconds if preset else None
        fps = editors.render_fps(src_fps, spec_fps)
        plan = plan_mod.build(project, cand, opts, vertical=vertical, fps=fps, max_len=max_len)
        if fmt is not None and fmt.kind == "audio":
            plan.brand, plan.intro_s, plan.outro_s = None, 0.0, 0.0
        lead = (plan.intro_s if plan.active else 0.0) + (FLASH_SECONDS if flash else 0.0)
        cues, sub_lang = clip_cues(project, cand, opts, req.subtitle_lang or None, translate, lead, plan=plan)
        for p in write_subtitles(root / stem, cues, sub_lang, list(req.subtitles)):
            files.append(_file_entry(p, p.suffix[1:], "text/vtt" if p.suffix == ".vtt" else "application/x-subrip",
                                     {"language": sub_lang}))
        if req.editors:
            stage("editor_files", None)
            # The same plan as the render, rebuilt for the editor (brand cards on, like the video).
            ed_plan = plan_mod.build(project, cand, opts, vertical=vertical, fps=fps, max_len=max_len)
            tl = editors.build(project, cand, opts, root / stem, vertical=vertical, spec_fps=spec_fps,
                               max_len=max_len, plan=ed_plan,
                               cues_for=lambda pl, lead_s: clip_cues(project, cand, opts, req.subtitle_lang or None,
                                                                     translate, lead_s, plan=pl)[0])
            for path in editors.write(list(req.editors), tl, root / stem, sub_lang):
                files.append(_file_entry(path, path.suffix[1:] if path.suffix == ".fcpxml" else "premiere",
                                         "application/xml"))
            for path in tl.files:  # the timeline's own media: overlays, cards, bleep track
                files.append(_file_entry(path, "editor_media", "image/png" if path.suffix == ".png" else "audio/wav",
                                         {"editor": True}))
            if "srt" not in req.subtitles:  # Premiere / Resolve import captions from an SRT next to it
                srt = write_subtitles(root / (stem + ".editor"), tl.cues, sub_lang, ["srt"])[0]
                files.append(_file_entry(srt, "srt", "application/x-subrip", {"language": sub_lang, "editor": True}))
            extra["editor_timeline"] = {"fps": tl.fps, "frames": tl.total, "parts": sum(p.kind == "main" for p in tl.pieces),
                                        "layers": sorted({ly.kind for ly in tl.layers}), "loop": tl.loop}

    if (extra.get("edits") or {}).get("duration"):
        duration = float(extra["edits"]["duration"])
    warnings = check_length(req.preset, duration)
    if extra.get("gif_over_limit"):
        warnings.append({"code": "gif_over_limit", "max_mb": req.gif_max_mb})
    entry = {"id": stem, "clip_id": cand["id"], "rank": cand["rank"], "format": req.format, "preset": req.preset,
             "request": req.to_dict(), "files": files, "duration": duration, "encoder": encoder,
             "seconds": round(time.perf_counter() - t0, 2), "created_at": _now(),
             "frame": (preset.frame if preset else "vertical") if fmt and fmt.kind != "audio" else None,
             "subtitle_language": sub_lang, "warnings": warnings, **extra}
    _save_entry(project, entry)
    return entry


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
