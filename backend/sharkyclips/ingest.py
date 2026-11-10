"""Ingest: local path OR URL (YouTube, Twitch, Kick, ...) -> workspace/<id>/.

Creates source.<ext>, audio.wav and meta.json. Re-running on the same source
reuses what is already there.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import __version__, audio, config, kick
from .errors import SharkyClipsError, pip_hint, require_module, require_tool
from .project import MODES, Project, make_project_id, project_for_id
from .ui import console, download_progress, time_progress


def is_url(text: str) -> bool:
    parsed = urlparse(text.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def js_runtimes() -> dict[str, dict]:
    """JavaScript runtimes yt-dlp can use (needed for full YouTube support)."""
    found = {}
    for name in ("deno", "node", "bun"):
        path = shutil.which(name)
        if path:
            found[name] = {"path": path}
    return found


# ------------------------------------------------------------------ local file


def _link_or_copy(src: Path, dest: Path) -> str:
    """Hard-link when possible (instant, no extra disk space), else copy."""
    try:
        os.link(src, dest)
        return "hardlink"
    except OSError:
        size = src.stat().st_size
        with download_progress() as prog:
            task = prog.add_task("Copying video", total=size)
            with open(src, "rb") as fi, open(dest, "wb") as fo:
                while chunk := fi.read(8 * 1024 * 1024):
                    fo.write(chunk)
                    prog.advance(task, len(chunk))
        shutil.copystat(src, dest)
        return "copy"


def _ingest_file(path_text: str) -> tuple[Project, dict]:
    src = Path(path_text).expanduser()
    if not src.is_file():
        raise SharkyClipsError(f"File not found: {src}",
                               "Check the path. Wrap paths that contain spaces in quotes.")
    src = src.resolve()
    st = src.stat()
    project = project_for_id(make_project_id(src.stem, f"file:{src}:{st.st_size}"))
    project.dir.mkdir(parents=True, exist_ok=True)
    existing = project.source_path
    if existing is None:
        dest = project.dir / f"source{src.suffix.lower() or '.mp4'}"
        method = _link_or_copy(src, dest)
        console.print(f"Source {'linked' if method == 'hardlink' else 'copied'} -> {dest}")
    else:
        console.print(f"Source already in workspace: {existing.name}")
    return project, {"type": "file", "value": str(src), "title": src.stem}


# ------------------------------------------------------------------------ URL


def _ydl_opts(project_dir: Path, max_height: int) -> dict:
    ffmpeg = require_tool("ffmpeg")
    opts = {
        "outtmpl": str(project_dir / "source.%(ext)s"),
        "format": (f"bv*[height<={max_height}]+ba/b[height<={max_height}]/bv*+ba/b"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "ffmpeg_location": str(Path(ffmpeg).parent),
        "socket_timeout": 30,  # a stalled connection raises and is retried instead of hanging
        "logger": _YdlLogger(),
        "retries": 10,
        "fragment_retries": 10,
        "continuedl": True,
        "concurrent_fragment_downloads": 4,
    }
    runtimes = js_runtimes()
    if runtimes:
        opts["js_runtimes"] = runtimes
    return opts


_LOGIN_MARKERS = ("sign in", "your age", "age-restricted", "login", "log in", "private video", "members-only",
                  "subscriber", "cookies")


class _YdlLogger:
    """Keep yt-dlp quiet: SharkyClips reports errors itself (once, with a fix hint)."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        from rich.markup import escape

        if "impersonat" in msg:  # Kick works without curl_cffi; the note only worries people
            return

        console.print(f"[dim]yt-dlp: {escape(msg)}[/]")

    def error(self, msg: str) -> None:
        pass


def _download_error(exc: Exception, url: str) -> SharkyClipsError:
    text = str(exc).replace("ERROR:", "").strip()
    first = text.split(". Use --cookies")[0][:300]
    if any(m in text.lower() for m in _LOGIN_MARKERS):
        return SharkyClipsError(
            f"This video needs a signed-in account (age-restricted, private or members-only): {first}",
            "SharkyClips doesn't log in to sites. Download the video yourself, then run: "
            'python cli.py ingest "path/to/video.mp4"')
    hint = "Update yt-dlp (sites change often): " + pip_hint("yt-dlp[default]")
    if kick.is_kick(url):
        hint = ("Kick may have changed its site: " + hint[0].lower() + hint[1:]
                + "\nSubscriber-only VODs can't be downloaded (SharkyClips doesn't log in).")
    if "youtu" in url and not js_runtimes():
        hint += "\nYouTube also needs a JavaScript runtime: install Deno or Node.js."
    return SharkyClipsError(f"Download failed: {text[:500]}", hint)


def _ingest_url(url: str) -> tuple[Project, dict]:
    console.print(f"Looking up [cyan]{url}[/] ...")
    lookup = kick.canonical(url) if kick.is_kick(url) else url  # channel links get a clear message
    yt_dlp = require_module("yt_dlp", "yt-dlp[default]")
    max_height = int(config.get("download_max_height") or 1080)
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "skip_download": True,
                               "socket_timeout": 30, "retries": 5, "logger": _YdlLogger(),
                               **({"js_runtimes": js_runtimes()} if js_runtimes() else {})}) as ydl:
            info = ydl.extract_info(lookup, download=False)
    except Exception as exc:
        if not kick.parse(lookup):
            raise _download_error(exc, url) from exc
        # yt-dlp's Kick extractor breaks now and then when the site changes: Kick's public
        # endpoints give the same VOD / clip (raises its own clear message, e.g. subscriber-only)
        console.print("[dim]yt-dlp couldn't read this Kick link; asking Kick directly.[/]")
        info = kick.resolve(lookup)
    if info.get("_type") == "playlist":
        raise SharkyClipsError("That URL is a playlist/channel.", "Pass a single video or VOD URL.")
    if info.get("is_live"):
        raise SharkyClipsError("This stream is live right now.",
                               "Wait until the stream ends and use the VOD/replay URL.")
    title = info.get("title") or info.get("id") or "video"
    canonical = info.get("webpage_url") or lookup
    media = info.get("media_url") or canonical  # the Kick fallback downloads its HLS playlist
    project = project_for_id(make_project_id(title, f"url:{info.get('extractor_key')}:{info.get('id') or canonical}"))
    project.dir.mkdir(parents=True, exist_ok=True)

    if project.source_path is None:
        console.print(f"Downloading [bold]{title}[/] (up to {max_height}p) ...")
        with download_progress() as prog:
            task = prog.add_task("Downloading", total=None)

            def hook(d: dict) -> None:
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    prog.update(task, completed=d.get("downloaded_bytes") or 0, total=total)
                elif d.get("status") == "finished":
                    prog.update(task, description="Merging")

            opts = _ydl_opts(project.dir, max_height) | {"progress_hooks": [hook]}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([media])
            except Exception as exc:
                raise _download_error(exc, url) from exc
        if project.source_path is None:
            raise SharkyClipsError("Download finished but no video file was found.",
                                   f"Look inside {project.dir}")
    else:
        console.print(f"Already downloaded: {project.source_path.name}")

    return project, {
        "type": "url",
        "value": url,
        "webpage_url": canonical,
        "extractor": info.get("extractor_key"),
        "video_id": info.get("id"),
        "uploader": info.get("uploader") or info.get("channel"),
        "upload_date": info.get("upload_date"),
        "category": next((c for c in info.get("categories") or [] if c), None),  # Kick: the game
        "title": title,
    }


# ----------------------------------------------------------------------- main


def ingest(source: str, mode: str = "gaming") -> Project:
    if mode not in MODES:
        raise SharkyClipsError(f"Unknown mode '{mode}'.", f"Use one of: {', '.join(MODES)}")
    project, src_info = _ingest_url(source) if is_url(source) else _ingest_file(source)
    src_path = project.source_path
    assert src_path is not None

    media = audio.probe(src_path)
    if not media["has_audio"]:
        raise SharkyClipsError("This video has no audio track, so it can't be transcribed.")

    if not (project.audio_path.is_file() and audio.wav_is_valid(project.audio_path)):
        with time_progress() as prog:
            task = prog.add_task("Extracting audio", total=media["duration"] or None)
            audio.extract_audio(src_path, project.audio_path, media["duration"],
                                lambda t: prog.update(task, completed=t))
            prog.update(task, completed=media["duration"] or 0)
    else:
        console.print("audio.wav already extracted.")

    old = project.load_meta()
    meta = {
        "id": project.id,
        "title": src_info.pop("title"),
        "mode": mode,
        "duration": media["duration"],
        "resolution": (f"{media['width']}x{media['height']}" if media["width"] else None),
        "width": media["width"],
        "height": media["height"],
        "fps": media["fps"],
        "video_codec": media["video_codec"],
        "audio_codec": media["audio_codec"],
        "source": src_info,
        "files": {"source": src_path.name, "audio": project.audio_path.name},
        "source_size_bytes": src_path.stat().st_size,
        "created_at": old.get("created_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sharkyclips_version": __version__,
    }
    project.save_meta(meta)
    return project
