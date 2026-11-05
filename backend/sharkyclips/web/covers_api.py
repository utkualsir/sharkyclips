"""Cover studio API (1.2.18): AI cover pictures made on this computer (aicovers.py / imagegen.py)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from .. import aicovers, config, imagegen
from ..errors import SharkyClipsError
from . import state
from .jobs import ACTIVE

router = APIRouter()


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


def active_job(project_id: str, cid: str):
    for j in _app().jobs.for_project(project_id):
        if j.kind == "ai_cover" and j.params.get("clip_id") == cid and j.status in ACTIVE:
            return j
    return None


def submit(project_id: str, cid: str, frames: list[str], new: bool = True, job_id: str | None = None,
           attempt: int = 1):
    A = _app()
    p = imagegen.plan()
    if p["use"] == "fallback":
        e = SharkyClipsError("This computer can't make AI covers.",
                             "The facecam frame is used as the cover instead.")
        e.code = "fallback"  # type: ignore[attr-defined]
        raise e
    project = A.get_project(project_id)
    cand = A._cand(project, cid)

    def run(job):
        project = A.get_project(project_id)
        cand = state.effective_cand(A._cand(project, cid), state.load_review(project))

        def progress(stage: str, frac) -> None:
            A.jobs.update(job, stage=stage, progress=frac)

        v = aicovers.make(project, cand, frames, progress, new=new)
        return {"options": v["options"], "made_with": v["made_with"]}

    params = {"clip_id": cid, "rank": cand["rank"], "frames": frames, "new": new,
              "title": ((cand.get("publish") or {}).get("titles") or [None])[0] or (cand.get("text") or "")[:90]}
    return A.jobs.submit("ai_cover", "gpu", project_id, params, run, key=f"ai_cover:{project_id}:{cid}",
                         persist=True, job_id=job_id, attempt=attempt)


@router.get("/api/covers/ai")
def api_status() -> dict:
    return imagegen.plan()


@router.put("/api/covers/ai")
def api_settings(body: dict) -> dict:
    if body.get("device") in imagegen.DEVICES:
        config.update(cover_ai_device=body["device"])
    return imagegen.plan()


@router.delete("/api/covers/ai/model")
def api_remove_model() -> dict:
    if any(j.kind == "ai_cover" and j.status in ACTIVE for j in _app().jobs.jobs()):
        raise SharkyClipsError("AI covers are being made right now.", "Remove the model when they're done.")
    return {"freed_bytes": imagegen.remove_model(), **imagegen.plan()}


@router.get("/api/library/{project_id}/{cid}/ai-covers")
def api_view(project_id: str, cid: str) -> dict:
    project = _app().get_project(project_id)
    _app()._cand(project, cid)
    j = active_job(project_id, cid)
    return {**aicovers.view(project, cid), "job": j.to_dict() if j is not None else None}


@router.post("/api/library/{project_id}/{cid}/ai-covers")
def api_make(project_id: str, cid: str, body: dict | None = None) -> dict:
    frames = [f for f in (body or {}).get("frames") or ["tall", "wide"] if f in aicovers.FRAMES]
    job = submit(project_id, cid, frames or ["tall"], new=(body or {}).get("new", True) is not False)
    return {"job": job.to_dict()}


@router.post("/api/library/{project_id}/{cid}/ai-covers/choose")
def api_choose(project_id: str, cid: str, body: dict) -> dict:
    project = _app().get_project(project_id)
    try:
        seed = int(body.get("seed"))
    except (TypeError, ValueError):
        raise SharkyClipsError("Pick one of the cover pictures.") from None
    return aicovers.choose(project, cid, str(body.get("frame") or "tall"), seed)


@router.get("/api/library/{project_id}/{cid}/ai-covers/{seed}/{frame}.jpg")
def api_option(project_id: str, cid: str, seed: int, frame: str, text: str = "", lang: str | None = None,
               v: str | None = None):
    """One option with the cover text on it (the picker's preview)."""
    from .. import cover
    from ..clips import Facecam

    A = _app()
    project = A.get_project(project_id)
    cand = A._cand(project, cid)
    img = aicovers.option_file(project, cid, frame, seed)
    if img is None:
        raise SharkyClipsError("This cover picture doesn't exist any more.")
    review = state.load_review(project)
    path = cover.make_cover(project, state.effective_cand(cand, review), Facecam.from_dict(review.get("facecam")),
                            "ai", text, frame, lang, ai_image=img)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
