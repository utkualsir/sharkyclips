"""TikTok / Instagram Reels API (1.2.18). See platforms.py for the two modes."""

from __future__ import annotations

import shutil

from fastapi import APIRouter, Request
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


def caption_for(project, cand: dict, platform: str) -> str:
    from . import publishing as pub

    meta = pub.prefill(project, cand)
    prefs = E.clip_prefs(E.load(project), cand["id"])
    title = prefs.get("title") or meta["title"]
    return PF.caption(platform, title, meta.get("description") or "", meta.get("hashtags") or [])


def active_job(project_id: str, cid: str, platform: str):
    for j in _app().jobs.for_project(project_id):
        if j.kind in ("platform_export", "platform_upload") and j.params.get("clip_id") == cid \
                and j.params.get("platform") == platform and j.status in ACTIVE:
            return j
    return None


def submit_export(project_id: str, cid: str, platform: str, job_id: str | None = None, attempt: int = 1):
    """Export with the platform's preset into Downloads/SharkyClips; then (API mode) upload."""
    from .. import export
    from ..clips import ClipOptions, Facecam

    A = _app()
    project = A.get_project(project_id)
    cand = A._cand(project, cid)
    mode = PF.mode(platform)

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
        text = caption_for(project, c, platform)
        (folder / f"{dest.stem}.txt").write_text(text + "\n", encoding="utf-8")
        PF.record(project, cid, platform, mode=mode, status="exported", file=str(dest), error=None)
        if mode == "api":
            submit_upload(project_id, cid, platform, str(dest), text)
        return {"file": str(dest), "folder": str(folder), "caption": text, "mode": mode,
                "upload_page": PF.UPLOAD_PAGE[platform]}

    params = {"clip_id": cid, "rank": cand["rank"], "platform": platform, "mode": mode,
              "title": ((cand.get("publish") or {}).get("titles") or [None])[0] or (cand.get("text") or "")[:90]}
    return A.jobs.submit("platform_export", "gpu", project_id, params, run,
                         key=f"platform_export:{project_id}:{cid}:{platform}", persist=True, job_id=job_id,
                         attempt=attempt)


def submit_upload(project_id: str, cid: str, platform: str, file: str, text: str, job_id: str | None = None,
                  attempt: int = 1):
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
            res = PF.tiktok_post(path, text, prog) if platform == "tiktok" else PF.ig_post(path, text, prog)
        except SharkyClipsError as exc:
            PF.record(project, cid, platform, status="error", error={"message": exc.message, "hint": exc.hint})
            raise
        PF.record(project, cid, platform, **res)
        return res

    return A.jobs.submit("platform_upload", "net", project_id,
                         {"clip_id": cid, "platform": platform, "file": file, "text": text}, run,
                         key=f"platform_upload:{project_id}:{cid}:{platform}", persist=True, job_id=job_id,
                         attempt=attempt)


def rebuild(kind: str, d: dict, keep_id: str | None, attempt: int):
    p = d.get("params") or {}
    if kind == "platform_export":
        return submit_export(d["project_id"], p["clip_id"], p["platform"], job_id=keep_id, attempt=attempt)
    return submit_upload(d["project_id"], p["clip_id"], p["platform"], p["file"], p.get("text") or "",
                         job_id=keep_id, attempt=attempt)


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
    return PF.ig_connect(str(body.get("token") or ""))


@router.get("/api/platforms/{platform}/clips/{project_id}/{cid}")
def api_clip(platform: str, project_id: str, cid: str) -> dict:
    A = _app()
    project = A.get_project(project_id)
    cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
    j = active_job(project_id, cid, _check(platform))
    return {"caption": caption_for(project, cand, platform), "mode": PF.mode(platform),
            "upload_page": PF.UPLOAD_PAGE[platform], "record": PF.records(project).get(cid, {}).get(platform),
            "job": j.to_dict() if j is not None else None}


@router.post("/api/platforms/{platform}/clips/{project_id}/{cid}")
def api_post(platform: str, project_id: str, cid: str, request: Request) -> dict:
    """One click: export with the platform preset; semi mode answers with the caption + upload page
    (the UI copies / opens them), API mode uploads by itself afterwards."""
    _check(platform)
    j = active_job(project_id, cid, platform) or submit_export(project_id, cid, platform)
    A = _app()
    project = A.get_project(project_id)
    cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
    if config.get("easy_platform") != platform:
        config.update(easy_platform=platform)
    return {"job": j.to_dict(), "mode": PF.mode(platform), "caption": caption_for(project, cand, platform),
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
