"""TikTok / Instagram Reels API (1.2.18). See platforms.py for the two modes."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse

from .. import config, easy as E, platforms as PF
from ..errors import SharkyClipsError
from . import state
from .jobs import ACTIVE

router = APIRouter()
POSTABLE = ("tiktok", "reels")


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


def _check(platform: str) -> str:
    if platform not in POSTABLE:
        raise SharkyClipsError(f"Unknown platform '{platform}'.", "Use tiktok or reels.")
    return platform


def overview() -> dict:
    from .. import youtube

    yt = youtube.status()
    return {"youtube": {"platform": "youtube", "mode": "api", "connected": yt["connected"], "account": yt.get("channel")},
            "tiktok": PF.status("tiktok"), "reels": PF.status("reels"), "chosen": chosen()}


def chosen() -> str:
    c = config.get("easy_platform")
    return c if c in PF.PLATFORMS else "youtube"


def _render_options(project, cand: dict) -> tuple[dict, str]:
    """The options the clip is rendered with on its screen: Easy's smart defaults or Pro's."""
    from . import easy as WE

    review = state.load_review(project)
    data = E.load(project)
    if data["easy"]:
        opts, hook = WE.wanted(project, cand, data, review, WE._hook_style(), WE._music_ok(), WE._lang(project))
        return opts, hook
    return dict(review["options"]), review["hooks"].get(cand["id"], "")


def ai_flags(body: dict | None) -> dict:
    """1.2.20, dubbed clips: the AI-voice line in the caption, the platform's AI label (automatic
    mode) or a reminder to switch it on (semi-automatic). Both on unless switched off."""
    body = body or {}
    return {"ai_voice_note": body.get("ai_voice_note") is not False, "ai_label": body.get("ai_label") is not False}


def ai_voice_for(dub_lang: str, flags: dict) -> dict:
    from .. import dub

    return {"dub": dub_lang, "line": dub.disclosure_line(dub_lang) if dub_lang else None,
            "note": bool(dub_lang) and flags["ai_voice_note"], "label": bool(dub_lang) and flags["ai_label"]}


def caption_for(project, cand: dict, platform: str, note: str | None = None) -> str:
    from . import publishing as pub

    meta = pub.prefill(project, cand)
    prefs = E.clip_prefs(E.load(project), cand["id"])
    title = prefs.get("title") or meta["title"]
    from ..edit import brand

    lang = meta.get("language") or (cand.get("publish") or {}).get("language")
    return PF.caption(platform, title, meta.get("description") or "", meta.get("hashtags") or [], note,
                      socials=brand.socials_block(lang))


def active_job(project_id: str, cid: str, platform: str):
    for j in _app().jobs.for_project(project_id):
        if j.kind in ("platform_export", "platform_upload") and j.params.get("clip_id") == cid \
                and j.params.get("platform") == platform and j.status in ACTIVE:
            return j
    return None


def submit_export(project_id: str, cid: str, platform: str, flags: dict | None = None, job_id: str | None = None,
                  attempt: int = 1):
    """Export with the platform's preset into Downloads/SharkyClips; then (API mode) upload."""
    from .. import export
    from ..clips import ClipOptions, Facecam

    A = _app()
    project = A.get_project(project_id)
    cand = A._cand(project, cid)
    mode = PF.mode(platform)
    flags = ai_flags(flags)

    def run(job):
        project = A.get_project(project_id)
        review = state.load_review(project)
        c = state.effective_cand(A._cand(project, cid), review)
        opts, hook = _render_options(project, c)
        o = ClipOptions.from_dict({**opts, "hook_text": hook})
        req = export.ExportRequest.from_dict({"format": "mp4_h264", "preset": PF.PRESET[platform]})

        def progress(stage: str, frac) -> None:
            A.jobs.update(job, stage="exporting" if stage in ("rendering", "exporting") else stage, progress=frac)

        entry = export.run_export(project, c, o, Facecam.from_dict(review.get("facecam")), req, progress)
        src = export.exports_root(project) / next(f["name"] for f in entry["files"] if f.get("role") == "media")
        prefs = E.clip_prefs(E.load(project), cid)
        from . import publishing as pub

        title = prefs.get("title") or pub.prefill(project, c)["title"]
        folder = E.downloads_root() / E.safe_name(project.load_meta().get("title") or project.id, 80)
        folder.mkdir(parents=True, exist_ok=True)
        label = {"tiktok": "TikTok", "reels": "Reels"}[platform]
        dest = folder / f"{c['rank']:02d} {E.safe_name(title, 60)} - {label}.mp4"
        shutil.copyfile(src, dest)
        ai = ai_voice_for(str(entry.get("dub") or ""), flags)  # the file just made: dubbed or not
        text = caption_for(project, c, platform, ai["line"] if ai["note"] else None)
        (folder / f"{dest.stem}.txt").write_text(text + "\n", encoding="utf-8")
        PF.record(project, cid, platform, mode=mode, status="exported", file=str(dest), error=None,
                  caption=text, ai_voice=ai if ai["dub"] else None)
        if mode == "api":
            submit_upload(project_id, cid, platform, str(dest), text, ai_label=ai["label"])
        return {"file": str(dest), "folder": str(folder), "caption": text, "mode": mode,
                "upload_page": PF.UPLOAD_PAGE[platform], "ai_voice": ai}

    params = {"clip_id": cid, "rank": cand["rank"], "platform": platform, "mode": mode, **flags,
              "title": ((cand.get("publish") or {}).get("titles") or [None])[0] or (cand.get("text") or "")[:90]}
    return A.jobs.submit("platform_export", "gpu", project_id, params, run,
                         key=f"platform_export:{project_id}:{cid}:{platform}", persist=True, job_id=job_id,
                         attempt=attempt)


def submit_upload(project_id: str, cid: str, platform: str, file: str, text: str, job_id: str | None = None,
                  attempt: int = 1, ai_label: bool = False):
    from pathlib import Path

    A = _app()

    def run(job):
        project = A.get_project(project_id)
        path = Path(file)
        if not path.is_file():
            raise SharkyClipsError("The exported file is gone.", "Post the clip again: it exports a fresh copy.")
        PF.record(project, cid, platform, mode="api", status="uploading", error=None)

        def prog(f: float) -> None:
            A.jobs.update(job, stage="uploading", progress=f)

        try:
            post = PF.tiktok_post if platform == "tiktok" else PF.ig_post
            res = post(path, text, prog, ai_label=ai_label)
        except SharkyClipsError as exc:
            PF.record(project, cid, platform, status="error", error={"message": exc.message, "hint": exc.hint})
            raise
        PF.record(project, cid, platform, **res)
        return res

    return A.jobs.submit("platform_upload", "net", project_id,
                         {"clip_id": cid, "platform": platform, "file": file, "text": text, "ai_label": ai_label}, run,
                         key=f"platform_upload:{project_id}:{cid}:{platform}", persist=True, job_id=job_id,
                         attempt=attempt)


def rebuild(kind: str, d: dict, keep_id: str | None, attempt: int):
    p = d.get("params") or {}
    if kind == "platform_export":
        return submit_export(d["project_id"], p["clip_id"], p["platform"], p, job_id=keep_id, attempt=attempt)
    return submit_upload(d["project_id"], p["clip_id"], p["platform"], p["file"], p.get("text") or "",
                         job_id=keep_id, attempt=attempt, ai_label=bool(p.get("ai_label")))


# ===================================================================== routes


@router.get("/api/platforms")
def api_overview() -> dict:
    return overview()


@router.put("/api/platforms/choice")
def api_choice(body: dict) -> dict:
    p = body.get("platform")
    if p not in PF.PLATFORMS:
        raise SharkyClipsError("Unknown platform.")
    config.update(easy_platform=p)
    return overview()


@router.put("/api/platforms/{platform}/mode")
def api_mode(platform: str, body: dict) -> dict:
    return PF.set_mode(_check(platform), str(body.get("mode") or ""))


@router.put("/api/platforms/{platform}/audited")
def api_audited(platform: str, body: dict) -> dict:
    return PF.set_audited(_check(platform), bool(body.get("audited")))


@router.delete("/api/platforms/{platform}")
def api_forget(platform: str) -> dict:
    PF.forget(_check(platform))
    modes = dict(config.get("platform_modes") or {})
    modes.pop(platform, None)
    config.update(platform_modes=modes)
    return PF.status(platform)


@router.post("/api/platforms/tiktok/connect")
def api_tiktok_connect(body: dict, request: Request) -> dict:
    if not _app()._is_local(request):
        raise SharkyClipsError("Connect TikTok on the computer running SharkyClips.")
    port = request.url.port or 8000
    return {"url": PF.tiktok_start(str(body.get("client_key") or ""), str(body.get("client_secret") or ""), port),
            "redirect_uri": PF.tiktok_redirect(port)}


@router.get("/api/platforms/tiktok/redirect")
def api_tiktok_redirect(request: Request) -> dict:
    return {"redirect_uri": PF.tiktok_redirect(request.url.port or 8000)}


@router.get("/api/platforms/tiktok/callback", response_class=HTMLResponse)
def api_tiktok_callback(code: str = "", state: str = "", error: str = "", error_description: str = "") -> HTMLResponse:
    if error or not code:
        msg, ok = (error_description or error or "TikTok didn't connect."), False
    else:
        try:
            PF.tiktok_finish(code, state)
            msg, ok = "TikTok is connected. You can close this tab.", True
        except SharkyClipsError as exc:
            msg, ok = f"{exc.message} {exc.hint or ''}", False
    import html

    color = "#2e9e6a" if ok else "#c0392b"
    return HTMLResponse(f"<!doctype html><meta charset='utf-8'><title>SharkyClips</title>"
                        f"<body style='font-family:system-ui;background:#0e1a33;color:#fff;display:grid;place-items:center;height:100vh;margin:0'>"
                        f"<div style='max-width:460px;text-align:center'><h1 style='color:{color}'>{'✓' if ok else '!'}</h1>"
                        f"<p>{html.escape(msg)}</p><p><a style='color:#d9b56a' href='/#/settings'>SharkyClips</a></p></div>")


@router.post("/api/platforms/reels/connect")
def api_reels_connect(body: dict) -> dict:
    """token: IGAA... (Instagram Login) or EAA... (Facebook side, 1.2.37); account (optional): the
    Instagram user id or @username it must post to."""
    return PF.ig_connect(str(body.get("token") or ""), str(body.get("account") or "") or None)


@router.get("/api/platforms/{platform}/clips/{project_id}/{cid}")
def api_clip(platform: str, project_id: str, cid: str, ai_voice_note: bool = True, ai_label: bool = True) -> dict:
    A = _app()
    project = A.get_project(project_id)
    cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
    j = active_job(project_id, cid, _check(platform))
    rec = PF.records(project).get(cid, {}).get(platform) or {}
    if rec.get("status") == "exported" and rec.get("caption"):  # the caption made with the exported file
        text, ai = rec["caption"], rec.get("ai_voice") or ai_voice_for("", ai_flags(None))
    else:  # not made yet: the file to come follows the clip's dub choice
        ai = ai_voice_for(state.file_dub(project, cid, ""), ai_flags({"ai_voice_note": ai_voice_note, "ai_label": ai_label}))
        text = caption_for(project, cand, platform, ai["line"] if ai["note"] else None)
    return {"caption": text, "ai_voice": ai, "mode": PF.mode(platform),
            "upload_page": PF.UPLOAD_PAGE[platform], "record": PF.records(project).get(cid, {}).get(platform),
            "job": j.to_dict() if j is not None else None}


@router.post("/api/platforms/{platform}/clips/{project_id}/{cid}")
def api_post(platform: str, project_id: str, cid: str, request: Request,
             body: dict | None = Body(default=None)) -> dict:
    """One click: export with the platform preset; semi mode answers with the caption + upload page
    (the UI copies / opens them), API mode uploads by itself afterwards. body (1.2.20, optional):
    {"ai_voice_note": bool, "ai_label": bool} for a dubbed clip, both on by default."""
    _check(platform)
    flags = ai_flags(body)
    j = active_job(project_id, cid, platform) or submit_export(project_id, cid, platform, flags)
    A = _app()
    project = A.get_project(project_id)
    cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
    if config.get("easy_platform") != platform:
        config.update(easy_platform=platform)
    ai = ai_voice_for(state.file_dub(project, cid, ""), flags)
    return {"job": j.to_dict(), "mode": PF.mode(platform), "ai_voice": ai,
            "caption": caption_for(project, cand, platform, ai["line"] if ai["note"] else None),
            "upload_page": PF.UPLOAD_PAGE[platform], "local": A._is_local(request)}


@router.post("/api/platforms/reveal")
def api_reveal(body: dict, request: Request) -> dict:
    """Show the exported file in Explorer / Finder (this PC only)."""
    from pathlib import Path

    if not _app()._is_local(request):
        return {"opened": False}
    path = Path(str(body.get("file") or ""))
    root = E.downloads_root().resolve()
    try:
        path.resolve().relative_to(root)
    except ValueError:
        raise SharkyClipsError("Only files in the SharkyClips downloads folder can be shown.") from None
    return {"opened": E.reveal_file(path)}
