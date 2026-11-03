"""Phone approval (1.2.17): your own Telegram bot and the approval page on the Wi-Fi.

- Telegram (phone.py): setup / pairing endpoints; the poller thread runs the Upload / Plan / Skip
  buttons; ready clips are sent as cards when an Easy project's clips are ready.
- the approval page (#/approve, frontend/src/pages/Approve.tsx): /api/approve lists the rendered
  clips waiting for a decision; swipe right = upload, left = skip. On the LAN it needs the
  access PIN (LanGuard); "phone_lan" makes the supervisor start the server with --lan.

Both use act(): upload now (the next free slot when today is full), plan, or skip.
SHARKYCLIPS_LIVE_LOOP=0 keeps the poller off (tests).
"""

from __future__ import annotations

import os
import socket
import threading
from pathlib import Path

from fastapi import APIRouter, Request

from .. import config, phone
from .. import easy as E
from .. import publishing as P
from ..errors import SharkyClipsError
from ..project import Project, get_project
from . import state

router = APIRouter()
_poller: list = []
_poller_state: dict = {"error": None}


def _app():
    from . import app as appmod

    return appmod


def _ez():
    from . import easy as ezmod

    return ezmod


# ===================================================================== actions (phone + approve page)


RESULT = {
    "en": {"uploading": "Uploading now", "scheduled": "Planned for {when}", "skipped": "Skipped",
           "not_connected": "Connect YouTube in SharkyClips first (Settings).", "gone": "This clip is gone."},
    "tr": {"uploading": "Şimdi yükleniyor", "scheduled": "{when} için planlandı", "skipped": "Atlandı",
           "not_connected": "Önce SharkyClips'te YouTube'u bağla (Ayarlar).", "gone": "Bu klip artık yok."},
    "de": {"uploading": "Wird jetzt hochgeladen", "scheduled": "Geplant für {when}", "skipped": "Übersprungen",
           "not_connected": "Verbinde zuerst YouTube in SharkyClips (Einstellungen).", "gone": "Dieser Clip ist weg."},
    "hu": {"uploading": "Feltöltés most", "scheduled": "Ütemezve: {when}", "skipped": "Kihagyva",
           "not_connected": "Előbb csatlakoztasd a YouTube-ot a SharkyClipsben (Beállítások).",
           "gone": "Ez a klip már nincs meg."},
    "ru": {"uploading": "Загружается", "scheduled": "Запланировано на {when}", "skipped": "Пропущено",
           "not_connected": "Сначала подключите YouTube в SharkyClips (Настройки).", "gone": "Этого клипа больше нет."},
    "ar": {"uploading": "يتم الرفع الآن", "scheduled": "مجدول في {when}", "skipped": "تم التخطي",
           "not_connected": "اربط YouTube في SharkyClips أولًا (الإعدادات).", "gone": "هذا المقطع لم يعد موجودًا."},
    "zh": {"uploading": "正在上传", "scheduled": "已排期：{when}", "skipped": "已跳过",
           "not_connected": "请先在 SharkyClips 中连接 YouTube（设置）。", "gone": "这个剪辑已经不在了。"},
}


def _r(key: str, **kw) -> str:
    lang = str(config.get("ui_language") or "en")
    return (RESULT.get(lang, RESULT["en"]).get(key) or RESULT["en"][key]).format(**kw)


def _when(iso: str | None) -> str:
    dt = P.parse(iso) if iso else None
    if dt is None:
        return "?"
    return dt.astimezone().strftime("%d.%m %H:%M")


def discard(project: Project, cid: str) -> None:
    review = state.load_review(project)
    state.save_review(project, {"rejected": list(dict.fromkeys([*review["rejected"], cid])),
                                "accepted": [c for c in review["accepted"] if c != cid]})


def act(action: str, project_id: str, cid: str) -> dict:
    """upload (now, or the next free slot when today is full) | plan | skip -> {"status", "text"}."""
    try:
        project = get_project(project_id)
        _app()._cand(project, cid)
    except Exception as exc:  # noqa: BLE001 - deleted project / clip
        raise SharkyClipsError(_r("gone")) from exc
    if action == "skip":
        discard(project, cid)
        return {"status": "skipped", "text": _r("skipped")}
    if action not in ("upload", "plan"):
        raise SharkyClipsError(f"Unknown action '{action}'.")
    try:
        res = _ez().upload(project, cid, "now" if action == "upload" else "auto")
    except SharkyClipsError as exc:
        if getattr(exc, "code", None) == "not_connected":
            raise SharkyClipsError(_r("not_connected")) from exc
        raise
    if res.get("status") == "scheduled":
        return {**res, "text": _r("scheduled", when=_when(res.get("publish_at")))}
    if res.get("status") == "published":
        return {**res, "text": phone.t("done")}
    return {**res, "text": _r("uploading")}


def _phone_act(action: str, pid: str, cid: str) -> str:
    return act(action, pid, cid)["text"]


def _video_for(pid: str, cid: str) -> Path | None:
    try:
        project = get_project(pid)
    except SharkyClipsError:
        return None
    clip = state.load_clips(project).get(cid)
    return project.dir / "clips" / clip["file"] if clip else None


# ===================================================================== ready clips -> phone cards


def on_clips_ready(project: Project, top: list[dict]) -> None:
    """The grid of an Easy project is rendered: send its best clips to the paired phone."""
    st = phone.status()
    if not (st["paired"] and st["send"]):
        return
    clips = state.load_clips(project)
    ready = [c["id"] for c in top if c["id"] in clips][: st["send_top"]]
    if ready:
        threading.Thread(target=_send_cards, args=(project.id, ready), name="sharkyclips-phone-send",
                         daemon=True).start()


def _send_cards(pid: str, cids: list[str]) -> None:
    try:
        project = get_project(pid)
    except SharkyClipsError:
        return
    hl = state.load_highlights(project) or {}
    by = {c["id"]: c for c in hl.get("candidates", [])}
    clips = state.load_clips(project)
    title = project.load_meta().get("title") or pid
    data = E.load(project)
    for cid in cids:
        c, clip = by.get(cid), clips.get(cid)
        if c is None or clip is None:
            continue
        pub = c.get("publish") or {}
        name = E.clip_prefs(data, cid)["title"] or (pub.get("titles") or [None])[0] or (c.get("text") or "")[:90]
        peak = max(0.5, float(c.get("peak") or c["start"]) - float(clip.get("start") or c["start"]))
        try:
            phone.send_clip(pid, cid, project.dir / "clips" / clip["file"], name,
                            state.viral_label(pub.get("viral_score")), pub.get("viral_score"), title, peak)
        except SharkyClipsError as exc:
            _poller_state["error"] = exc.message


def install() -> None:
    """Start the Telegram button poller (idle while no phone is paired)."""
    if os.environ.get("SHARKYCLIPS_LIVE_LOOP") == "0" or _poller:
        return
    _poller.append(phone.Poller(_phone_act, _video_for).start())


def poller_view() -> dict | None:
    if not _poller:
        return None
    p = _poller[0]
    return {"status": p.status, "error": p.error or _poller_state["error"]}


# ===================================================================== LAN (phone page)


def lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent: just picks the LAN interface
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def lan_view(request: Request | None = None) -> dict:
    from .. import lanauth

    A = _app()
    url = getattr(A.app.state, "lan_url", None)
    port = request.url.port if request is not None and request.url.port else None
    ip = lan_ip()
    return {"enabled": bool(config.get("phone_lan")), "active": bool(url), "pin": lanauth.enabled(),
            "url": (url or (f"http://{ip}:{port}" if ip and port else None)),
            "approve_url": ((url or (f"http://{ip}:{port}" if ip and port else "")) + "/#/approve") or None,
            "busy": A.jobs.busy()}


# ===================================================================== approve page


def approve_queue() -> list[dict]:
    """Rendered clips of Easy projects that wait for a decision (best first)."""
    from .. import youtube
    from . import publishing as pub

    A = _app()
    ez = _ez()
    items = P.load()
    pj = pub._plan_jobs()
    lock = youtube.lock_state()["state"]
    now = P.now_utc()
    out = []
    for project in A.list_projects():
        data = E.load(project)
        if not data["easy"]:
            continue
        hl = ez._hl(project)
        if not hl.get("candidates"):
            continue
        review = state.load_review(project, hl)
        clips = state.load_clips(project)
        title = project.load_meta().get("title") or project.id
        for c in ez.ranked(project, hl, review)[: data["shown"]]:
            clip = clips.get(c["id"])
            if not clip or not (project.dir / "clips" / clip["file"]).is_file():
                continue
            up = ez._upload_state(project, c["id"], items.get(P.key_of(project.id, c["id"])), pj, lock, now)
            if up["status"] != "draft" or up.get("step") not in (None, "waiting", "ready", "draft"):
                continue
            pubd = c.get("publish") or {}
            out.append({"project_id": project.id, "project_title": title, "clip_id": c["id"],
                        "title": E.clip_prefs(data, c["id"])["title"] or (pubd.get("titles") or [None])[0]
                        or (c.get("text") or "")[:90],
                        "viral_score": pubd.get("viral_score"), "viral_label": state.viral_label(pubd.get("viral_score")),
                        "duration": clip.get("duration"), "marked": bool(c.get("marked")),
                        "video": f"/api/projects/{project.id}/clips/{c['id']}/video",
                        "created": data.get("created_at") or "", "rendered_at": clip.get("rendered_at")})
    out.sort(key=lambda r: (r["created"], r["rendered_at"] or ""), reverse=True)
    return out


# ===================================================================== API


@router.get("/api/phone")
def api_phone(request: Request) -> dict:
    return {**phone.status(), "lan": lan_view(request), "poller": poller_view()}


@router.post("/api/phone/telegram")
def api_tg_set(body: dict, request: Request) -> dict:
    if not _app()._is_local(request):
        raise SharkyClipsError("Set up the bot on the computer running SharkyClips.")
    return phone.set_token(str(body.get("token") or ""))


@router.post("/api/phone/telegram/pair")
def api_tg_pair() -> dict:
    return phone.pair_check()


@router.delete("/api/phone/telegram")
def api_tg_delete(request: Request) -> dict:
    if not _app()._is_local(request):
        raise SharkyClipsError("Only the computer running SharkyClips can do this.")
    phone.disconnect()
    return phone.status()


@router.post("/api/phone/test")
def api_tg_test() -> dict:
    phone.send_test()
    return {"ok": True}


@router.put("/api/phone")
def api_phone_put(body: dict, request: Request) -> dict:
    changes: dict = {}
    if "send" in body:
        changes["phone_send"] = bool(body["send"])
    if "send_top" in body:
        changes["phone_send_top"] = max(1, min(10, int(body["send_top"])))
    if "lan" in body:
        from .. import lanauth

        if not _app()._is_local(request):
            raise SharkyClipsError("Only the computer running SharkyClips can do this.")
        if body["lan"] and not lanauth.enabled():
            e = SharkyClipsError("Set an access PIN first.", "Without a PIN anyone on your Wi-Fi could use it.")
            e.code = "needs_pin"  # type: ignore[attr-defined]
            raise e
        changes["phone_lan"] = bool(body["lan"])
    if changes:
        config.update(**changes)
    return {**phone.status(), "lan": lan_view(request), "poller": poller_view()}


@router.get("/api/approve")
def api_approve() -> dict:
    return {"clips": approve_queue(), "youtube": _yt_connected()}


def _yt_connected() -> bool:
    from .. import youtube

    return youtube.connected()


@router.post("/api/approve/{project_id}/{cid}")
def api_approve_act(project_id: str, cid: str, body: dict) -> dict:
    res = act(str(body.get("action") or ""), project_id, cid)
    tok = phone.card_for(project_id, cid)
    if tok:  # the phone card of this clip is done too
        from ..project import write_json_atomic

        cards = phone._cards()
        if tok in cards:
            cards[tok]["state"] = res["status"]
            write_json_atomic(phone.cards_path(), cards)
    return {**res, "clips": approve_queue()}
