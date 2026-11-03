"""Automation + live (1.2.17): auto clips after a stream and live markers.

The background service (one per server; the server lock makes sure there is only one):
- watcher: every few seconds a cheap look at the recording folder(s) (watch.py); a finished
  recording starts the Easy pipeline (import -> clips -> top N rendered -> AI package)
- hotkey: Ctrl+Alt+C (configurable) adds a live marker (markers.py)
- chat readers: Twitch / YouTube "!clip" from you or your mods (livechat.py)

The phone side (Telegram bot, approval page) is web/phone_api.py.
SHARKYCLIPS_LIVE_LOOP=0 keeps the threads off (tests drive the service by hand).
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request

from .. import config, livechat, markers, watch
from .. import easy as E
from ..errors import SharkyClipsError
from ..project import Project
from . import state
from .jobs import Job

router = APIRouter()
WATCH_EVERY_S = 6.0


def _app():
    from . import app as appmod

    return appmod


def _ez():
    from . import easy as ezmod

    return ezmod


# ===================================================================== after an import / when clips are ready


def on_imported(job: Job, project: Project) -> None:
    """A recording from the watched folder is imported: its live markers + live chat go in
    before the highlights run; the grid renders the top N."""
    src = job.params.get("auto_watch")
    if not src:
        return
    start = float(job.params.get("rec_start") or 0)
    end = float(job.params.get("rec_end") or start)
    got = []
    if start:
        got = markers.attach(project, start, end)
        rec_start = start
        mk = markers.project_path(project)
        if mk.is_file():
            from ..project import read_json

            rec_start = float(read_json(mk).get("recording_start") or start)
        try:
            livechat.attach(project, rec_start, end)
        except Exception:  # noqa: BLE001 - the chat is a bonus
            pass
    nice = job.params.get("nice_title")
    meta = project.load_meta()
    if nice and meta.get("title") in (None, "", Path(src).stem, Path(src).name):
        meta["title"] = nice
        project.save_meta(meta)
    E.save(project, auto=True, shown=watch.settings()["render_top"])
    watch.mark(Path(src), status="imported", project_id=project.id, markers=len(got))


def on_clips_ready(project: Project, top: list[dict]) -> None:
    """The grid is rendered: auto publish (when it was chosen for auto clips)."""
    data = E.load(project)
    clips = state.load_clips(project)
    ready = [c for c in top if c["id"] in clips]
    if data.get("auto"):
        s = watch.settings()
        if s["publish"] in ("plan", "now"):
            from .. import youtube

            if youtube.connected():
                for c in ready[: s["publish_top"]]:
                    try:
                        _ez().upload(project, c["id"], "now" if s["publish"] == "now" else "auto")
                    except SharkyClipsError:
                        pass


# ===================================================================== background service


class LiveService:
    def __init__(self):
        self.pending: dict = {}
        self.hotkey = markers.Hotkey(self._hotkey_pressed)
        self.twitch: livechat.TwitchReader | None = None
        self.youtube: livechat.YoutubeReader | None = None
        self.last_scan: float | None = None
        self.last_error: str | None = None
        self.last_marker: dict | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    # ---- lifecycle
    def start(self) -> None:
        if self._thread is not None:
            return
        self.reconfigure()
        self.resume()
        self._thread = threading.Thread(target=self._loop, name="sharkyclips-watch", daemon=True)
        self._thread.start()
        livechat.prune()

    def reconfigure(self) -> None:
        """Apply the settings: hotkey, chat readers."""
        with self._lock:
            want_key = config.get("marker_hotkey_enabled") is not False
            combo = str(config.get("marker_hotkey") or markers.DEFAULT_HOTKEY)
            if want_key and (self.hotkey.status != "on" or self.hotkey.combo != combo):
                self.hotkey.start(combo)
            elif not want_key:
                self.hotkey.stop()
            channel = str(config.get("live_twitch_channel") or "").strip().lstrip("#").lower()
            if self.twitch is not None and (not channel or self.twitch.channel != channel):
                self.twitch.stop()
                self.twitch = None
            if channel and self.twitch is None:
                self.twitch = livechat.TwitchReader(channel, self.on_chat).start()
            yt = bool(config.get("live_youtube_chat"))
            if self.youtube is not None and not yt:
                self.youtube.stop()
                self.youtube = None
            if yt and self.youtube is None:
                self.youtube = livechat.YoutubeReader(self.on_chat).start()

    def stop(self) -> None:
        self._stop.set()
        self.hotkey.stop()
        for r in (self.twitch, self.youtube):
            if r is not None:
                r.stop()

    def _loop(self) -> None:
        while not self._stop.wait(WATCH_EVERY_S):
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - never let the watcher die
                self.last_error = str(exc)[:200]

    # ---- watcher
    def resume(self) -> list[Path]:
        """Imports cut short by a restart / crash start again (the import finds the project it
        already made: the project id comes from the file path + size, so nothing is doubled)."""
        from .jobs import ACTIVE

        running = {str(j.params.get("auto_watch")) for j in _app().jobs.jobs()
                   if j.kind == "import" and j.status in ACTIVE and j.params.get("auto_watch")}
        out = []
        for key, f in watch.load_state()["files"].items():
            if f.get("status") != "importing" or key in running:
                continue
            p = Path(key)
            if not p.is_file():
                watch.mark(p, status="error", error="The recording isn't there any more.")
            elif self.start_import(p):
                out.append(p)
        return out

    def tick(self, now: float | None = None) -> list[Path]:
        if not config.get("auto_clip_enabled"):
            self.pending.clear()
            return []
        ready, _st = watch.candidates_now(now, self.pending)
        self.last_scan = time.time()
        started = []
        for p in ready:
            if self.start_import(p):
                started.append(p)
        return started

    def start_import(self, path: Path) -> bool:
        st = watch.load_state()["files"].get(str(path)) or {}
        dur = _duration(path)
        min_s = watch.settings()["min_minutes"] * 60
        if dur is not None and dur < min_s:
            watch.mark(path, status="skipped", reason="too_short", duration=dur)
            return False
        A = _app()
        born = float(st.get("born") or path.stat().st_mtime)
        end = float(st.get("mtime") or path.stat().st_mtime)
        title = _title_for(path, born)
        try:
            job = A.submit_import(str(path), str(config.get("default_mode") or "gaming"), "auto", title,
                                  extra={"easy": True, "mode_auto": True, "auto_watch": str(path),
                                         "rec_start": born, "rec_end": end, "nice_title": title})
        except SharkyClipsError as exc:
            watch.mark(path, status="error", error=exc.message)
            return False
        watch.mark(path, status="importing", job_id=job.id)
        return True

    # ---- markers
    def _hotkey_pressed(self) -> None:
        m = markers.add("hotkey")
        if m is not None:
            self.last_marker = m
            markers.confirm_sound()

    def on_chat(self, msg: dict) -> None:
        livechat.record(msg.get("platform") or "chat", msg["user"], msg["text"], msg.get("color"), msg.get("at"))
        cmd = str(config.get("live_clip_command") or markers.DEFAULT_COMMAND)
        hit, note = livechat.is_command(msg["text"], cmd)
        if hit and (msg.get("owner") or msg.get("mod")):
            m = markers.add("chat", by=msg["user"], at=float(msg.get("at") or time.time()), note=note or None)
            if m is not None:
                self.last_marker = m

    def view(self) -> dict:
        return {"hotkey": self.hotkey.status, "twitch": None if self.twitch is None else
                {"status": self.twitch.status, "error": self.twitch.error, "channel": self.twitch.channel},
                "youtube": None if self.youtube is None else {"status": self.youtube.status, "error": self.youtube.error},
                "last_scan": self.last_scan, "error": self.last_error}


_service = LiveService()


def service() -> LiveService:
    return _service


def install() -> None:
    if os.environ.get("SHARKYCLIPS_LIVE_LOOP") == "0":
        return
    _service.start()


def _duration(path: Path) -> float | None:
    import json
    import subprocess

    from ..procs import no_window

    try:
        from ..errors import require_tool

        probe = require_tool("ffprobe")
        r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=30, **no_window())
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:  # noqa: BLE001 - unreadable: let the import say why
        return None


def _title_for(path: Path, born: float) -> str:
    when = datetime.fromtimestamp(born).strftime("%d.%m.%Y %H:%M")
    return f"Stream {when}"


# ===================================================================== API


def _live_view(request: Request | None = None) -> dict:
    from .. import obs

    o = obs.settings()
    return {"watch": {**watch.settings(), "recent": watch.recent()},
            "markers": {"hotkey": str(config.get("marker_hotkey") or markers.DEFAULT_HOTKEY),
                        "hotkey_enabled": config.get("marker_hotkey_enabled") is not False,
                        "command": str(config.get("live_clip_command") or markers.DEFAULT_COMMAND),
                        "twitch_channel": str(config.get("live_twitch_channel") or ""),
                        "youtube_chat": bool(config.get("live_youtube_chat")),
                        "obs_websocket": str(config.get("obs_websocket") or "auto"),
                        "recent": markers.recent(10), "hotkey_supported": os.name == "nt"},
            "obs": {"found": o["found"], "record_dir": o["record_dir"], "format": o["format"],
                    "websocket": None if o["websocket"] is None else {"enabled": o["websocket"]["enabled"],
                                                                     "port": o["websocket"]["port"]}},
            "service": _service.view()}


@router.get("/api/live")
def api_live(request: Request) -> dict:
    return _live_view(request)


@router.put("/api/live/watch")
def api_watch_put(body: dict, request: Request) -> dict:
    changes: dict = {}
    if "folders" in body:
        if not _app()._is_local(request):
            raise SharkyClipsError("Folders can only be changed on the computer running SharkyClips.")
        fl = [str(f).strip() for f in body.get("folders") or [] if str(f).strip()]
        for f in fl:
            if not Path(f).expanduser().is_dir():
                raise SharkyClipsError(f"Folder not found: {f}", "Pick the folder OBS records into.")
        changes["watch_folders"] = fl or None
    if "render_top" in body:
        n = int(body["render_top"])
        if not 1 <= n <= 30:
            raise SharkyClipsError("Render between 1 and 30 clips.")
        changes["watch_render_top"] = n
    if body.get("publish") in watch.PUBLISH:
        changes["watch_publish"] = body["publish"]
    if "publish_top" in body:
        changes["watch_publish_top"] = max(1, min(10, int(body["publish_top"])))
    if "min_minutes" in body:
        changes["watch_min_minutes"] = max(0.0, min(120.0, float(body["min_minutes"])))
    if changes:
        config.update(**changes)
    if "enabled" in body:
        enable_auto(bool(body["enabled"]))
    return _live_view(request)


def enable_auto(on: bool) -> None:
    if on and not watch.folders():
        raise SharkyClipsError("SharkyClips doesn't know where your recordings go.",
                               "Pick the folder OBS records into (Settings > Automation).")
    if on and config.get("auto_clip_enabled"):
        return  # already on: keep the baseline
    watch.enable(on)
    _service.pending.clear()


@router.post("/api/live/watch/scan")
def api_watch_scan() -> dict:
    started = _service.tick()
    return {"started": [str(p) for p in started], "recent": watch.recent()}


@router.get("/api/live/obs/check")
def api_obs_check() -> dict:
    from .. import obs

    return obs.check()


@router.put("/api/live/markers")
def api_markers_put(body: dict, request: Request) -> dict:
    changes: dict = {}
    if "hotkey" in body:
        try:
            changes["marker_hotkey"] = markers.normalize_hotkey(str(body["hotkey"]))
        except ValueError as exc:
            raise SharkyClipsError("That shortcut can't be used.", "Use Ctrl / Alt / Shift + a letter, e.g. Ctrl+Alt+C.") \
                from exc
    if "hotkey_enabled" in body:
        changes["marker_hotkey_enabled"] = bool(body["hotkey_enabled"])
    if "command" in body:
        cmd = str(body["command"] or "").strip()
        if not cmd.startswith("!") or " " in cmd or len(cmd) > 20:
            raise SharkyClipsError("A chat command starts with ! and has no spaces, e.g. !clip.")
        changes["live_clip_command"] = cmd
    if "twitch_channel" in body:
        ch = str(body["twitch_channel"] or "").strip().lstrip("#@").lower()
        if "twitch.tv/" in ch:
            ch = ch.rsplit("twitch.tv/", 1)[1].split("/")[0]
        import re

        if ch and not re.fullmatch(r"[a-z0-9_]{3,25}", ch):
            raise SharkyClipsError("That isn't a Twitch channel name.", "Just the name, e.g. utkualsir.")
        changes["live_twitch_channel"] = ch
    if "youtube_chat" in body:
        changes["live_youtube_chat"] = bool(body["youtube_chat"])
    if body.get("obs_websocket") in ("auto", "off"):
        changes["obs_websocket"] = body["obs_websocket"]
    if changes:
        config.update(**changes)
        _service.reconfigure()
    return _live_view(request)


@router.post("/api/live/markers")
def api_marker_add(body: dict | None = None) -> dict:
    """A marker from the UI / the phone page ("mark now")."""
    m = markers.add(str((body or {}).get("source") or "button"))
    return {"marker": m, "recent": markers.recent(10)}


@router.delete("/api/live/markers/{mid}")
def api_marker_delete(mid: str) -> dict:
    markers.remove(mid)
    return {"recent": markers.recent(10)}
