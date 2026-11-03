"""Live chat during a stream (read-only): "!clip" markers from you or your moderators, and a
local copy of the chat for the chat bubbles of the clips made from the recording.

- Twitch: IRC as an anonymous reader ("justinfan"): no login, nothing can be posted.
  Badges tell who is the broadcaster / a moderator.
- YouTube: the connected channel's active live stream (Data API, the token SharkyClips already
  has): liveBroadcasts.list finds it, liveChatMessages.list reads it at the pace YouTube asks
  for. isChatOwner / isChatModerator tell who may mark.

Messages are written to <settings>/live/chat-YYYYMMDD.jsonl ({"at", "user", "text", "color",
"platform"}), kept 14 days. A recording that gets imported takes the lines of its time range
as its chat.json (if it has no chat yet).

SHARKYCLIPS_TWITCH_IRC=host:port points the reader at a fake server (tests).
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import config

KEEP_DAYS = 14
TWITCH_HOST, TWITCH_PORT = "irc.chat.twitch.tv", 6667
YT_IDLE_CHECK_S = 90.0  # look for a live broadcast this often
YT_MIN_POLL_S = 8.0


def live_dir() -> Path:
    d = config.config_dir() / "live"
    d.mkdir(parents=True, exist_ok=True)
    return d


_wlock = threading.Lock()


def record(platform: str, user: str, text: str, color: str | None = None, at: float | None = None) -> None:
    if config.get("live_chat_record") is False:
        return
    at = at or time.time()
    day = datetime.fromtimestamp(at).strftime("%Y%m%d")
    row = {"at": round(at, 3), "user": user[:40], "text": text[:300], "platform": platform}
    if color:
        row["color"] = color
    with _wlock:
        with open(live_dir() / f"chat-{day}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def prune(now: float | None = None) -> None:
    cutoff = (now or time.time()) - KEEP_DAYS * 86400
    for p in live_dir().glob("chat-*.jsonl"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def rows_between(start: float, end: float) -> list[dict]:
    out = []
    d = datetime.fromtimestamp(start).date()
    last = datetime.fromtimestamp(end).date()
    while d <= last:
        p = live_dir() / f"chat-{d.strftime('%Y%m%d')}.jsonl"
        if p.is_file():
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if start <= float(r.get("at", 0)) <= end:
                        out.append(r)
        d = datetime.fromordinal(d.toordinal() + 1).date()
    return sorted(out, key=lambda r: r["at"])


def attach(project, rec_start: float, rec_end: float) -> int:
    """The recorded live chat of a recording -> its chat.json (when it has none). Returns count."""
    from . import chat

    if chat.chat_path(project).is_file():
        return 0
    rows = rows_between(rec_start, rec_end)
    if not rows:
        return 0
    colors = {r["user"]: r["color"] for r in rows if r.get("color")}
    data = chat._save(project, "live", [(r["at"] - rec_start, r["text"], r["user"]) for r in rows])
    if colors:
        from .project import write_json_atomic

        data["colors"] = colors
        write_json_atomic(chat.chat_path(project), data, compact=True)
    return int(data.get("count") or 0)


def is_command(text: str, command: str) -> tuple[bool, str]:
    """("!clip nice one", "!clip") -> (True, "nice one")."""
    t = text.strip()
    c = (command or "!clip").strip().lower()
    if t.lower() == c or t.lower().startswith(c + " "):
        return True, t[len(c):].strip()
    return False, ""


# ===================================================================== Twitch (IRC, anonymous)


def parse_irc(line: str) -> dict | None:
    """A PRIVMSG with tags -> {"user", "text", "color", "mod", "owner", "at"}; other lines None."""
    tags: dict[str, str] = {}
    if line.startswith("@"):
        raw, line = line[1:].split(" ", 1)
        for kv in raw.split(";"):
            k, _, v = kv.partition("=")
            tags[k] = v
    parts = line.split(" ", 3)
    if len(parts) < 4 or parts[1] != "PRIVMSG":
        return None
    nick = parts[0].lstrip(":").split("!")[0]
    text = parts[3][1:] if parts[3].startswith(":") else parts[3]
    text = text.split(" :", 1)[1] if text.startswith("#") and " :" in text else text
    badges = tags.get("badges", "")
    ts = tags.get("tmi-sent-ts")
    return {"user": tags.get("display-name") or nick, "text": text.strip(), "color": tags.get("color") or None,
            "owner": "broadcaster/" in badges, "mod": tags.get("mod") == "1" or "moderator/" in badges,
            "at": int(ts) / 1000 if ts and ts.isdigit() else time.time()}


class TwitchReader:
    def __init__(self, channel: str, on_message: Callable[[dict], None]):
        self.channel = channel.strip().lstrip("#").lower()
        self.on_message = on_message
        self.status = "starting"
        self.error: str | None = None
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self.thread = threading.Thread(target=self._run, name="sharkyclips-twitch", daemon=True)

    def start(self) -> "TwitchReader":
        self.thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._sock is not None:
                self._sock.close()
        except OSError:
            pass

    def _addr(self) -> tuple[str, int]:
        env = os.environ.get("SHARKYCLIPS_TWITCH_IRC")
        if env and ":" in env:
            h, p = env.rsplit(":", 1)
            return h, int(p)
        return TWITCH_HOST, TWITCH_PORT

    def _run(self) -> None:
        backoff = 2.0
        while not self._stop.is_set():
            try:
                self._session()
                backoff = 2.0
            except OSError as exc:
                self.status, self.error = "reconnecting", str(exc)[:200]
            if self._stop.wait(backoff):
                break
            backoff = min(60.0, backoff * 2)
        self.status = "off"

    def _session(self) -> None:
        host, port = self._addr()
        s = socket.create_connection((host, port), timeout=15)
        self._sock = s
        s.settimeout(330)  # Twitch pings every ~5 minutes
        nick = f"justinfan{int(time.time()) % 90000 + 10000}"
        s.sendall(f"CAP REQ :twitch.tv/tags twitch.tv/commands\r\nNICK {nick}\r\nJOIN #{self.channel}\r\n".encode())
        buf = b""
        self.status, self.error = "on", None
        while not self._stop.is_set():
            chunk = s.recv(8192)
            if not chunk:
                raise OSError("Twitch closed the connection")
            buf += chunk
            while b"\r\n" in buf:
                raw, buf = buf.split(b"\r\n", 1)
                line = raw.decode("utf-8", errors="replace")
                if line.startswith("PING"):
                    s.sendall(("PONG" + line[4:] + "\r\n").encode())
                    continue
                if " NOTICE " in line and "msg_channel_suspended" in line:
                    self.status, self.error = "error", "channel_not_found"
                msg = parse_irc(line)
                if msg is not None:
                    msg["platform"] = "twitch"
                    self.on_message(msg)


# ===================================================================== YouTube live chat


class YoutubeReader:
    """Reads the connected channel's live chat while a broadcast is live."""

    def __init__(self, on_message: Callable[[dict], None]):
        self.on_message = on_message
        self.status = "idle"
        self.error: str | None = None
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="sharkyclips-ytchat", daemon=True)

    def start(self) -> "YoutubeReader":
        self.thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        from . import youtube
        from .errors import SharkyClipsError

        chat_id: str | None = None
        page: str | None = None
        first = True
        while not self._stop.is_set():
            wait = YT_IDLE_CHECK_S
            try:
                if not youtube.connected():
                    self.status = "not_connected"
                elif chat_id is None:
                    chat_id = self._active_chat()
                    self.status = "waiting" if chat_id is None else "on"
                    page, first = None, True
                    wait = YT_IDLE_CHECK_S if chat_id is None else 0.1
                else:
                    params = {"liveChatId": chat_id, "part": "snippet,authorDetails", "maxResults": 200}
                    if page:
                        params["pageToken"] = page
                    data = youtube._call("GET", "liveChat/messages", params, cost=5, what="live chat")
                    page = data.get("nextPageToken") or page
                    if not first:  # the first page is the backlog from before SharkyClips listened
                        for it in data.get("items") or []:
                            self._handle(it)
                    first = False
                    if data.get("offlineAt"):
                        chat_id = None
                    wait = max(YT_MIN_POLL_S, float(data.get("pollingIntervalMillis") or 10000) / 1000)
                    self.status, self.error = "on", None
            except SharkyClipsError as exc:
                self.error = exc.message[:200]
                reason = getattr(exc, "reason", None) or ""
                if reason in ("liveChatEnded", "liveChatNotFound", "liveChatDisabled"):
                    chat_id = None
                self.status = "error"
                wait = YT_IDLE_CHECK_S
            except Exception as exc:  # noqa: BLE001 - network: try again later
                self.status, self.error = "error", str(exc)[:200]
                wait = YT_IDLE_CHECK_S
            self._stop.wait(wait)
        self.status = "off"

    def _active_chat(self) -> str | None:
        from . import youtube

        data = youtube._get("liveBroadcasts", {"part": "snippet", "broadcastStatus": "active",
                                               "broadcastType": "all", "maxResults": 5})
        for it in data.get("items") or []:
            cid = (it.get("snippet") or {}).get("liveChatId")
            if cid:
                return str(cid)
        return None

    def _handle(self, it: dict) -> None:
        sn, au = it.get("snippet") or {}, it.get("authorDetails") or {}
        text = sn.get("displayMessage") or (sn.get("textMessageDetails") or {}).get("messageText") or ""
        if not text:
            return
        at = time.time()
        try:
            at = datetime.fromisoformat(str(sn.get("publishedAt")).replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()
        except ValueError:
            pass
        self.on_message({"user": au.get("displayName") or "?", "text": text, "color": None,
                         "owner": bool(au.get("isChatOwner")), "mod": bool(au.get("isChatModerator")),
                         "at": at, "platform": "youtube"})
