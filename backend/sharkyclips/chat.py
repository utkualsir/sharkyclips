"""Chat replay: download it or import a log file -> workspace/<id>/chat.json.

Sources
  * YouTube live chat replay (yt-dlp, "live_chat" subtitle track) - only for videos
    that were live streams
  * Twitch VOD chat (Twitch's public GraphQL API, no login; several parts of the VOD are
    fetched in parallel)
  * Kick VOD / clip chat (Kick's public messages endpoint, no login; ~5 s per call, parallel
    parts like Twitch)
  * a chat log file: chat-downloader JSON, yt-dlp .live_chat.json, TwitchDownloader JSON,
    or plain text lines like "[1:02:03] name: message"

chat.json (compact):
  {"version": 1, "status": "ok" | "none", "source": ..., "reason": ..., "count": N,
   "authors": N, "messages": [[t_seconds, "text", author_index], ...]}
Author names are not stored (only an index, to tell many people from one spammer).
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .errors import SharkyClipsError
from .project import Project, read_json, write_json_atomic
from .ui import console

CHAT_VERSION = 1
# Chat bots post reminders and commands; they're not viewers reacting.
BOTS = {"nightbot", "streamelements", "streamlabs", "moobot", "fossabot", "botrix", "wizebot",
        "sery_bot", "soundalerts", "pokemoncommunitygame", "kofistreambot", "tangiabot",
        "commanderroot", "botrixoficial", "streamstickers", "blerp"}


def chat_path(project: Project) -> Path:
    return project.dir / "chat.json"


def load_chat(project: Project) -> dict | None:
    p = chat_path(project)
    return read_json(p) if p.is_file() else None


def _save(project: Project, source: str, rows: Iterable[tuple[float, str, str]]) -> dict:
    authors: dict[str, int] = {}
    msgs = []
    for t, text, author in rows:
        text = " ".join(str(text).split())
        if not text or t is None or t < 0 or (author or "").casefold().lstrip("@") in BOTS:
            continue
        idx = authors.setdefault(author or f"anon{len(authors)}", len(authors))
        msgs.append([round(float(t), 2), text[:300], idx])
    msgs.sort(key=lambda m: m[0])
    data = {"version": CHAT_VERSION, "status": "ok" if msgs else "none", "source": source,
            "reason": None if msgs else "the chat log has no messages",
            "count": len(msgs), "authors": len(authors),
            "names": list(authors),  # index -> user name (chat bubbles show who wrote it)
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "messages": msgs}
    write_json_atomic(chat_path(project), data, compact=True)
    return data


def _save_none(project: Project, source: str, reason: str) -> dict:
    data = {"version": CHAT_VERSION, "status": "none", "source": source, "reason": reason,
            "count": 0, "authors": 0,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "messages": []}
    write_json_atomic(chat_path(project), data, compact=True)
    return data


# ------------------------------------------------------------------ parsers


def _yt_runs(runs: list[dict]) -> str:
    out = []
    for r in runs:
        if "text" in r:
            out.append(r["text"])
        elif "emoji" in r:
            e = r["emoji"]
            if e.get("isCustomEmoji"):  # channel emote, e.g. ":kekw:" -> "kekw"
                out.append(" " + (e.get("shortcuts") or [":emote:"])[0].strip(":") + " ")
            else:  # standard emoji: the id is the character itself
                out.append(e.get("emojiId", ""))
    return "".join(out)


def parse_ytdlp_live_chat(lines: Iterable[str]) -> list[tuple[float, str, str]]:
    rows = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        replay = obj.get("replayChatItemAction") or {}
        offset = replay.get("videoOffsetTimeMsec")
        for action in replay.get("actions", []):
            item = (action.get("addChatItemAction") or {}).get("item") or {}
            r = item.get("liveChatTextMessageRenderer") or item.get("liveChatPaidMessageRenderer")
            if not r or offset is None:
                continue
            text = _yt_runs((r.get("message") or {}).get("runs", []))
            author = (r.get("authorName") or {}).get("simpleText", "")
            rows.append((int(offset) / 1000.0, text, author))
    return rows


_TIME_LINE = re.compile(
    r"^\s*\[?\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d+))?\s*\]?\s*(?:<?([^:<>\]]{1,40})>?\s*:\s+)?(.*)$")


def parse_file(path: Path) -> tuple[str, list[tuple[float, str, str]]]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    stripped = raw.lstrip()
    # yt-dlp: one JSON object per line
    if stripped.startswith("{") and "replayChatItemAction" in raw[:5000]:
        return "youtube-file", parse_ytdlp_live_chat(raw.splitlines())
    data = None
    if stripped.startswith(("{", "[")):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            if path.suffix.lower() == ".json":
                raise SharkyClipsError(f"{path.name} isn't valid JSON: {exc}") from exc
            # not JSON: a text log whose lines start with "[0:00:05]"
    if data is not None:
        if isinstance(data, dict) and isinstance(data.get("comments"), list):  # TwitchDownloader
            return "twitchdownloader-file", [
                (c.get("content_offset_seconds"), (c.get("message") or {}).get("body", ""),
                 (c.get("commenter") or {}).get("name", "")) for c in data["comments"]]
        if isinstance(data, list):  # chat-downloader
            return "chat-downloader-file", [
                (m.get("time_in_seconds"), m.get("message", ""), (m.get("author") or {}).get("name", ""))
                for m in data if isinstance(m, dict)]
        raise SharkyClipsError(f"Unknown chat JSON format in {path.name}.",
                               "Supported: chat-downloader, yt-dlp live_chat, TwitchDownloader, or text lines "
                               "like '[1:02:03] name: message'.")
    rows = []
    for line in raw.splitlines():
        m = _TIME_LINE.match(line)
        if not m:
            continue
        h, mi, s, frac, author, text = m.groups()
        t = int(h or 0) * 3600 + int(mi) * 60 + int(s) + (float(f"0.{frac}") if frac else 0)
        rows.append((t, text, (author or "").strip()))
    if not rows:
        raise SharkyClipsError(f"No timestamped chat lines found in {path.name}.",
                               "Expected lines like '[1:02:03] name: message'.")
    return "text-file", rows


def import_file(project: Project, path: Path) -> dict:
    if not path.is_file():
        raise SharkyClipsError(f"File not found: {path}")
    source, rows = parse_file(path)
    data = _save(project, f"{source}:{path.name}", rows)
    console.print(f"Chat imported: {data['count']} messages from {data['authors']} people.")
    return data


# ------------------------------------------------------------------ download


def _download_youtube(project: Project, url: str) -> dict:
    from .errors import require_module
    from .ingest import _YdlLogger, js_runtimes

    yt_dlp = require_module("yt_dlp", "yt-dlp[default]")
    opts = {"quiet": True, "skip_download": True, "logger": _YdlLogger(), "socket_timeout": 30,
            **({"js_runtimes": js_runtimes()} if js_runtimes() else {})}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if "live_chat" not in (info.get("subtitles") or {}):
        return _save_none(project, "youtube", "no chat replay (the video wasn't a live stream)")
    out_dir = project.cache_dir / "chat"
    out_dir.mkdir(parents=True, exist_ok=True)
    from .ui import time_progress

    console.print("Downloading YouTube chat replay (YouTube sends it in small pieces; this can "
                  "take a few minutes for long streams) ...")
    duration = float(info.get("duration") or 0)
    with time_progress() as prog:
        task = prog.add_task("Downloading chat", total=duration or None)

        def hook(d: dict) -> None:
            # yt-dlp reports the chat's position as "fragment" progress; use the newest offset
            if d.get("status") == "downloading" and duration:
                frag = d.get("fragment_index") or 0
                prog.update(task, completed=min(duration, frag * 25.0))

        with yt_dlp.YoutubeDL(opts | {"writesubtitles": True, "subtitleslangs": ["live_chat"],
                                      "outtmpl": str(out_dir / "yt.%(ext)s"),
                                      "progress_hooks": [hook]}) as ydl:
            ydl.download([info.get("webpage_url") or url])
        prog.update(task, completed=duration or 1)
    files = list(out_dir.glob("*.live_chat.json"))
    if not files:
        return _save_none(project, "youtube", "chat replay download produced no file")
    with open(files[0], encoding="utf-8", errors="replace") as f:
        rows = parse_ytdlp_live_chat(f)
    return _save(project, "youtube", rows)


TWITCH_GQL = "https://gql.twitch.tv/gql"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Twitch's public web client id
TWITCH_COMMENTS_HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"


def _twitch_page(http, video_id: str, offset: float | None = None, cursor: str | None = None) -> dict:
    variables = {"videoID": video_id}
    if cursor:
        variables["cursor"] = cursor
    else:
        variables["contentOffsetSeconds"] = int(offset or 0)
    body = [{"operationName": "VideoCommentsByOffsetOrCursor", "variables": variables,
             "extensions": {"persistedQuery": {"version": 1, "sha256Hash": TWITCH_COMMENTS_HASH}}}]
    for attempt in range(6):
        try:
            r = http.post(TWITCH_GQL, json=body, timeout=30,
                          headers={"Client-Id": TWITCH_CLIENT_ID})
            data = r.json()[0].get("data") or {}
            video = data.get("video")
            if video is None:
                raise SharkyClipsError("Twitch returned no video (deleted, sub-only or wrong id).")
            return video.get("comments") or {}
        except SharkyClipsError:
            raise
        except Exception:  # noqa: BLE001 - network hiccup / rate limit: back off and retry
            time.sleep(1.5 * (attempt + 1))
    raise SharkyClipsError("Twitch chat download keeps failing (network or rate limit).")


def _twitch_segment(video_id: str, a: float, b: float, on_page) -> list[tuple[float, str, str]]:
    """All messages with a <= t < b."""
    import requests

    # Twitch only allows paging by time offset without an integrity token: each answer holds
    # the next ~60 messages from that second on. Continue from the last message's second
    # (messages already seen are skipped by id); step +1 s when a whole page is one second.
    rows: list[tuple[float, str, str]] = []
    seen: set[str] = set()
    offset = a
    with requests.Session() as http:
        while offset < b:
            edges = _twitch_page(http, video_id, offset=offset).get("edges") or []
            new = 0
            last_t = offset
            for e in edges:
                n = e.get("node") or {}
                t = n.get("contentOffsetSeconds")
                if t is None:
                    continue
                last_t = max(last_t, t)
                if n.get("id") in seen or not (a <= t < b):
                    continue
                seen.add(n.get("id"))
                new += 1
                text = "".join(f.get("text", "") for f in (n.get("message") or {}).get("fragments") or [])
                rows.append((float(t), text, (n.get("commenter") or {}).get("login", "")))
            on_page(last_t)
            if not edges:
                break
            offset = last_t if (new and last_t > offset) else offset + 1
            if not new and last_t <= offset - 1 and len(edges) < 5:
                break  # end of the chat
    return rows


def _download_twitch(project: Project, url: str, duration: float) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    from .ui import time_progress

    m = re.search(r"/videos?/(\d+)", url) or re.search(r"\bv?(\d{6,})\b", url)
    if not m:
        return _save_none(project, "twitch", "only Twitch VODs (twitch.tv/videos/...) have chat replays")
    video_id = m.group(1)
    duration = duration or 6 * 3600
    parts = max(1, min(8, int(duration // 900)))  # ~15+ min per worker, at most 8 in parallel
    bounds = [duration * i / parts for i in range(parts + 1)]
    bounds[-1] = duration + 60
    done = [0.0] * parts
    console.print(f"Downloading Twitch chat replay ({parts} parallel parts) ...")
    with time_progress() as prog:
        task = prog.add_task("Downloading chat", total=duration)

        def run(i: int) -> list:
            def on_page(t: float) -> None:
                done[i] = max(done[i], min(t, bounds[i + 1]) - bounds[i])
                prog.update(task, completed=min(duration, sum(done)))

            return _twitch_segment(video_id, bounds[i], bounds[i + 1], on_page)

        with ThreadPoolExecutor(parts) as pool:
            chunks = list(pool.map(run, range(parts)))
        prog.update(task, completed=duration)
    return _save(project, "twitch", [r for c in chunks for r in c])


def _download_kick(project: Project, url: str, duration: float) -> dict:
    from concurrent.futures import ThreadPoolExecutor

    from . import kick
    from .ui import time_progress

    plan = kick.chat_plan(url, duration)
    if plan is None:
        return _save_none(project, "kick", "Kick has no chat replay for this link")
    chat_id, t0, length = plan
    length = length or duration or 3600
    # ~5 s of chat per call: 15+ min per worker, at most 6 in parallel (polite to Kick)
    parts = max(1, min(6, int(length // 900)))
    bounds = [length * i / parts for i in range(parts + 1)]
    bounds[-1] = length + 5
    done = [0.0] * parts
    console.print(f"Downloading Kick chat replay ({parts} parallel parts) ...")
    with time_progress() as prog:
        task = prog.add_task("Downloading chat", total=length)

        def run(i: int) -> list:
            def on_page(t: float) -> None:
                done[i] = max(done[i], min(t, bounds[i + 1]) - bounds[i])
                prog.update(task, completed=min(length, sum(done)))

            return kick.chat_segment(chat_id, t0, bounds[i], bounds[i + 1], on_page)

        with ThreadPoolExecutor(parts) as pool:
            chunks = list(pool.map(run, range(parts)))
        prog.update(task, completed=length)
    return _save(project, "kick", [r for c in chunks for r in c])


def ensure_chat(project: Project, force: bool = False) -> dict:
    """Download the chat replay once per project. Never raises: no chat = signal skipped."""
    existing = load_chat(project)
    if existing and not force:
        return existing
    meta = project.load_meta()
    src = meta.get("source") or {}
    url = src.get("webpage_url") or src.get("value") or ""
    extractor = (src.get("extractor") or "").lower()
    if src.get("type") != "url":
        return _save_none(project, "file", "local video - import a chat log file to use chat")
    try:
        if "youtube" in extractor or "youtu" in url:
            return _download_youtube(project, url)
        if "twitch" in extractor or "twitch.tv" in url:
            return _download_twitch(project, url, float(meta.get("duration") or 0))
        if "kick" in extractor or "kick.com" in url:
            return _download_kick(project, url, float(meta.get("duration") or 0))
        return _save_none(project, extractor or "url", "chat replay isn't supported for this site")
    except Exception as exc:  # noqa: BLE001 - chat is optional
        console.print(f"[yellow]Chat replay unavailable:[/] {str(exc)[:200]}")
        return _save_none(project, extractor or "url", f"download failed: {str(exc)[:200]}")
