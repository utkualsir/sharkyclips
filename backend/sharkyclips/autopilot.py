"""Easy mode 2.0: Autopilot - one switch for the whole chain.

new recording (watch folder) -> clips (Easy 2.0 smart cuts) -> bleeps -> titles / description in
"My style" -> covers -> planned on YouTube at the daily limit (the publish plan). Everything it
does is written to an event log, so nothing fails silently: a failed or blocked upload becomes a
notice (tray + paired phone) with what to do, and the morning summary says it in one line:
"4 clips ready, 3 planned".

Upload reliability: health() is green / amber / red with a plain message and a one-tap fix. The
background tick refreshes the YouTube sign-in every 30 minutes (free, no quota), so a revoked
sign-in shows up as "Reconnect" before an upload fails, not after.

State: ~/.sharkyclips/autopilot.json {"events": [...], "summary_day": "YYYY-MM-DD", "checked": {...}}
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from . import config
from .project import read_json, write_json_atomic

SUMMARY_HOUR = 9  # local time of the morning summary
CHECK_EVERY_S = 30 * 60
KEEP_EVENTS = 300
EVENT_KINDS = ("ready", "planned", "uploading", "failed", "blocked")

_lock = threading.RLock()

TEXT = {
    "title": {"en": "Autopilot", "tr": "Otopilot", "de": "Autopilot", "hu": "Robotpilóta", "ru": "Автопилот",
              "ar": "الطيار الآلي", "zh": "自动驾驶"},
    "summary": {"en": "{ready} clips ready, {planned} planned.", "tr": "{ready} klip hazır, {planned} tanesi planlandı.",
                "de": "{ready} Clips fertig, {planned} geplant.", "hu": "{ready} klip kész, {planned} ütemezve.",
                "ru": "Готово клипов: {ready}, запланировано: {planned}.", "ar": "{ready} مقاطع جاهزة، {planned} مجدولة.",
                "zh": "{ready} 个片段已就绪，{planned} 个已排期。"},
    "waiting": {"en": " {n} need you: open SharkyClips.", "tr": " {n} tanesi seni bekliyor: SharkyClips'i aç.",
                "de": " {n} brauchen dich: öffne SharkyClips.", "hu": " {n} rád vár: nyisd meg a SharkyClipst.",
                "ru": " {n} ждут тебя: открой SharkyClips.", "ar": " {n} بانتظارك: افتح SharkyClips.",
                "zh": " {n} 个需要你处理：打开 SharkyClips。"},
    "blocked": {"en": "YouTube isn't connected: {n} clips are waiting.", "tr": "YouTube bağlı değil: {n} klip bekliyor.",
                "de": "YouTube ist nicht verbunden: {n} Clips warten.", "hu": "A YouTube nincs csatlakoztatva: {n} klip vár.",
                "ru": "YouTube не подключён: ждут {n} клипов.", "ar": "YouTube غير متصل: {n} مقاطع بالانتظار.",
                "zh": "YouTube 未连接：{n} 个片段在等待。"},
    "disconnected": {"en": "YouTube signed SharkyClips out. Tap to reconnect.", "tr": "YouTube oturumu kapandı. Yeniden bağlanmak için dokun.",
                     "de": "YouTube hat SharkyClips abgemeldet. Tippe zum Neuverbinden.", "hu": "A YouTube kijelentkeztette a SharkyClipst. Koppints az újracsatlakozáshoz.",
                     "ru": "YouTube разлогинил SharkyClips. Нажми, чтобы переподключить.", "ar": "سجّل YouTube خروج SharkyClips. اضغط لإعادة الاتصال.",
                     "zh": "YouTube 已退出 SharkyClips 登录，点按重新连接。"},
    "failed": {"en": "Couldn't plan “{title}”: {why}", "tr": "“{title}” planlanamadı: {why}",
               "de": "„{title}“ konnte nicht geplant werden: {why}", "hu": "„{title}” nem ütemezhető: {why}",
               "ru": "Не удалось запланировать «{title}»: {why}", "ar": "تعذّرت جدولة “{title}”: {why}",
               "zh": "无法排期“{title}”：{why}"},
}


def _lang() -> str:
    lang = str(config.get("ui_language") or "en")
    return lang if lang in TEXT["title"] else "en"


def _t(key: str, **kw) -> str:
    return TEXT[key].get(_lang(), TEXT[key]["en"]).format(**kw)


def path():
    return config.config_dir() / "autopilot.json"


def _load() -> dict:
    p = path()
    try:
        data = read_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        data = {}
    return {"events": list(data.get("events") or []), "summary_day": data.get("summary_day"),
            "checked": dict(data.get("checked") or {})}


def _save(data: dict) -> None:
    data["events"] = data["events"][-KEEP_EVENTS:]
    write_json_atomic(path(), data)


# ===================================================================== the switch


def enabled() -> bool:
    return config.get("easy_autopilot") is True


def enable(on: bool) -> dict:
    """On: auto clips from the recordings folder + plan the ready clips on YouTube."""
    from .easy import SHOWN

    if on:
        from .web.live import enable_auto

        enable_auto(True)  # raises a plain error when no recordings folder is known
        config.update(easy_autopilot=True, watch_publish="plan",
                      watch_publish_top=max(int(config.get("watch_publish_top") or 3), SHOWN))
    else:
        config.update(easy_autopilot=False, watch_publish="off")
    return view()


# ===================================================================== events


def record(kind: str, project_id: str | None = None, clip_id: str | None = None, title: str | None = None,
           message: str | None = None, at: float | None = None) -> dict:
    ev = {"at": at or time.time(), "kind": kind, "project_id": project_id, "clip_id": clip_id,
          "title": (title or "")[:100], "message": (message or "")[:300]}
    with _lock:
        data = _load()
        data["events"].append(ev)
        _save(data)
    return ev


def on_clips_ready(project, ready: list[dict], upload, when: str = "auto") -> dict:
    """Auto clips are rendered: plan them (Autopilot) and log every outcome. upload(cid, when)
    = web.easy.upload. Returns counts."""
    from . import easy as E, youtube
    from .errors import SharkyClipsError

    title = project.load_meta().get("title") or project.id
    counts = {"ready": len(ready), "planned": 0, "failed": 0, "blocked": 0}
    for c in ready:
        record("ready", project.id, c["id"], (c.get("publish") or {}).get("titles", [None])[0] or title)
    if not youtube.connected():
        counts["blocked"] = len(ready)
        for c in ready:
            record("blocked", project.id, c["id"], message="not_connected")
        if ready:
            E.push_notice("autopilot", _t("title"), _t("blocked", n=len(ready)), "/#/settings")
        return counts
    for c in ready:
        name = ((c.get("publish") or {}).get("titles") or [None])[0] or c.get("text", "")[:60] or c["id"]
        try:
            res = upload(c["id"], when)
            kind = "planned" if res.get("status") in ("scheduled", "published") else "uploading"
            record(kind, project.id, c["id"], name, res.get("publish_at") or "")
            counts["planned"] += 1
        except SharkyClipsError as exc:
            counts["failed"] += 1
            why = exc.message + (f" {exc.hint}" if exc.hint else "")
            record("failed", project.id, c["id"], name, why)
            E.push_notice("autopilot", _t("title"), _t("failed", title=name[:60], why=exc.message), f"/#/p/{project.id}")
    return counts


# ===================================================================== health


def health(probe: bool = False) -> dict:
    """{"state": ok|warn|error, "code", "fix": connect|reconnect|library|None, ...} for the pill.
    probe=True refreshes the sign-in now (free) instead of trusting the stored token."""
    from . import publishing as P, youtube
    from .errors import SharkyClipsError

    out: dict = {"state": "ok", "code": "connected", "fix": None, "channel": None,
                 "checked_at": _load()["checked"].get("at")}
    if not youtube.connected():
        so = youtube.signed_out()
        out.update(state="error", code="signed_out" if so else "not_connected", fix="reconnect" if so else "connect")
        return out
    st = youtube.status()
    out["channel"] = (st.get("channel") or {}).get("title") if isinstance(st.get("channel"), dict) else st.get("channel")
    if probe:
        try:
            youtube._expire_access()
            youtube.access_token()
            _mark_checked(True, None)
            out["checked_at"] = time.time()
        except SharkyClipsError as exc:
            reason = getattr(exc, "reason", None)
            _mark_checked(False, exc.message)
            if reason in ("signed_out", "not_connected"):
                out.update(state="error", code="signed_out", fix="reconnect")
                return out
            out.update(state="warn", code="offline", message=exc.message, fix=None)
            return out
        except Exception as exc:  # noqa: BLE001 - no network
            _mark_checked(False, str(exc)[:200])
            out.update(state="warn", code="offline", fix=None)
            return out
    else:
        last = _load()["checked"]
        if last and last.get("ok") is False and last.get("at", 0) > time.time() - 2 * CHECK_EVERY_S:
            out.update(state="warn", code="offline", message=last.get("error"))
    try:
        attention = [it for it in P.load().values() if it.get("attention")]
    except Exception:  # noqa: BLE001
        attention = []
    if attention:
        out.update(state="warn" if out["state"] == "ok" else out["state"], code="attention",
                   count=len(attention), fix="library")
    elif (st.get("lock") or {}).get("state") == "locked":
        out.update(code="locked")
    return out


def _mark_checked(ok: bool, error: str | None) -> None:
    with _lock:
        data = _load()
        data["checked"] = {"at": time.time(), "ok": ok, "error": error}
        _save(data)


# ===================================================================== summary + tick


def summary(now: datetime | None = None, hours: float = 24.0) -> dict:
    now = now or datetime.now()
    since = now.timestamp() - hours * 3600
    evs = [e for e in _load()["events"] if float(e.get("at") or 0) >= since]
    ready = {(e["project_id"], e["clip_id"]) for e in evs if e["kind"] == "ready"}
    planned = {(e["project_id"], e["clip_id"]) for e in evs if e["kind"] in ("planned", "uploading")}
    stuck = {(e["project_id"], e["clip_id"]) for e in evs if e["kind"] in ("failed", "blocked")} - planned
    text = _t("summary", ready=len(ready), planned=len(planned))
    if stuck:
        text += _t("waiting", n=len(stuck))
    return {"ready": len(ready), "planned": len(planned), "waiting": len(stuck), "text": text}


def tick(now: datetime | None = None) -> list[str]:
    """Called by the publish scheduler's loop (about once a minute)."""
    if not enabled():
        return []
    acts: list[str] = []
    now = now or datetime.now()
    data = _load()
    if time.time() - float(data["checked"].get("at") or 0) >= CHECK_EVERY_S:
        before = data["checked"].get("code")
        h = health(probe=True)
        acts.append(f"health:{h['code']}")
        with _lock:
            d = _load()
            d["checked"]["code"] = h["code"]
            _save(d)
        if h["state"] == "error" and before != h["code"]:  # said once, not every 30 minutes
            from . import easy as E

            E.push_notice("autopilot", _t("title"), _t("disconnected"), "/#/settings")
    today = now.date().isoformat()
    if now.hour >= SUMMARY_HOUR and data.get("summary_day") != today:
        s = summary(now)
        with _lock:
            d = _load()
            d["summary_day"] = today
            _save(d)
        if s["ready"] or s["waiting"]:
            send_summary(s["text"])
            acts.append("summary")
    return acts


def send_summary(text: str) -> None:
    from . import easy as E

    E.push_notice("autopilot_summary", _t("title"), text, "/#/library")
    try:
        from . import phone

        d = phone._load()
        if d.get("chat_id") and config.get("phone_send") is not False:
            phone.call("sendMessage", chat_id=d["chat_id"], text=f"🦈 {_t('title')}: {text}")
    except Exception:  # noqa: BLE001 - the phone is a bonus; the tray notice is already there
        pass


def view() -> dict:
    s = summary()
    evs = _load()["events"][-20:]
    return {"enabled": enabled(), "summary": s, "events": list(reversed(evs)), "health": health(),
            "summary_hour": SUMMARY_HOUR,
            "next_summary": (datetime.now().replace(hour=SUMMARY_HOUR, minute=0, second=0, microsecond=0)
                             + (timedelta(days=1) if datetime.now().hour >= SUMMARY_HOUR else timedelta())).isoformat()}
