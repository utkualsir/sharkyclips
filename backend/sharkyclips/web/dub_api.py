"""My-voice dubbing API (1.2.18): the voice profile (consent + sample) and dubbing a clip."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from .. import dub
from ..errors import SharkyClipsError
from . import state
from .jobs import ACTIVE

router = APIRouter()
MAX_SAMPLE_BYTES = 40 * 1024 * 1024


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


@router.get("/api/voice")
def api_profile() -> dict:
    return dub.profile()


@router.post("/api/voice/consent")
def api_consent(body: dict, request: Request) -> dict:
    if not _app()._is_local(request):
        raise SharkyClipsError("Set up your voice on the computer running SharkyClips.")
    if body.get("own_voice") is not True or body.get("no_others") is not True:
        raise SharkyClipsError("Tick both boxes to confirm.")
    return dub.give_consent(str(body.get("name") or ""))


@router.put("/api/voice/sample")
async def api_sample(request: Request, source: str = "file") -> dict:
    """The user's own recording (browser microphone) or a file they picked: raw body."""
    if not _app()._is_local(request):
        raise SharkyClipsError("Record your voice on the computer running SharkyClips.")
    data = await request.body()
    if not data:
        raise SharkyClipsError("The recording is empty.", "Allow the microphone and speak for 10-20 seconds.")
    if len(data) > MAX_SAMPLE_BYTES:
        raise SharkyClipsError("This file is too big for a voice sample.", "Use 10-30 seconds of audio.")
    with tempfile.TemporaryDirectory(prefix="sharkyclips-voice-") as d:
        p = Path(d) / "upload.bin"
        p.write_bytes(data)
        return dub.save_sample(p, source)


@router.get("/api/voice/sample.wav")
def api_sample_audio(request: Request):
    if not _app()._is_local(request) or not dub.sample_path().is_file():
        raise SharkyClipsError("No voice sample yet.")
    return FileResponse(dub.sample_path(), media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.delete("/api/voice")
def api_revoke() -> dict:
    return dub.revoke()


# ------------------------------------------------------------------ dubbing a clip


def active_job(project_id: str, cid: str):
    for j in _app().jobs.for_project(project_id):
        if j.kind == "dub" and j.params.get("clip_id") == cid and j.status in ACTIVE:
            return j
    return None


def submit(project_id: str, cid: str, lang: str, job_id: str | None = None, attempt: int = 1):
    A = _app()
    dub.require_ready(lang)
    project = A.get_project(project_id)
    cand = A._cand(project, cid)

    def run(job):
        project = A.get_project(project_id)
        review = state.load_review(project)
        c = state.effective_cand(A._cand(project, cid), review)

        def progress(stage: str, frac) -> None:
            A.jobs.update(job, stage=stage, progress=frac)

        def translate():
            if not A.llm_available():
                raise SharkyClipsError("Dubbing needs the local AI to translate the clip.",
                                       "Install it with: python cli.py doctor")
            from ..analyze import translate_clip

            return translate_clip(project, cid, lang)

        info = dub.make(project, c, lang, progress, translate=translate)
        return {"dubbed": info["dubbed"], "kept": info["kept"], "lang": lang}

    def then(job):
        if job.status != "done":
            return
        project = A.get_project(project_id)
        state.save_review(project, {"dub": {**state.load_review(project)["dub"], cid: lang}})
        _rerender(project, cid)

    params = {"clip_id": cid, "rank": cand["rank"], "lang": lang,
              "title": ((cand.get("publish") or {}).get("titles") or [None])[0] or (cand.get("text") or "")[:90]}
    return A.jobs.submit("dub", "gpu", project_id, params, run, then, key=f"dub:{project_id}:{cid}:{lang}",
                         persist=True, job_id=job_id, attempt=attempt)


def _rerender(project, cid: str) -> None:
    """The clip again with (or without) the dub: Easy's smart defaults, else Pro's options."""
    from .. import easy as E
    from . import easy as WE

    A = _app()
    if E.load(project)["easy"]:
        WE.ensure_renders(project, auto=False, only=cid)
        return
    if cid in state.load_clips(project):
        review = state.load_review(project)
        A.submit_render_clip(project.id, cid, dict(review["options"]), review["hooks"].get(cid, ""))


@router.get("/api/projects/{project_id}/clips/{cid}/dub")
def api_clip(project_id: str, cid: str) -> dict:
    A = _app()
    project = A.get_project(project_id)
    review = state.load_review(project)
    cand = state.effective_cand(A._cand(project, cid), review)
    lang = review["dub"].get(cid) or ""
    info = dub.track_for(project, cand, lang) if lang else None
    j = active_job(project_id, cid)
    return {"lang": lang, "targets": list(dub.TARGETS), "profile": dub.profile(),
            "info": {k: info[k] for k in ("lines", "dubbed", "kept", "made_at", "voice_pass")} if info else None,
            "job": j.to_dict() if j is not None else None}


@router.post("/api/projects/{project_id}/clips/{cid}/dub")
def api_dub(project_id: str, cid: str, body: dict) -> dict:
    """{"lang": "en"} dubs the clip (then re-renders it); {"lang": ""} goes back to the original voice."""
    A = _app()
    project = A.get_project(project_id)
    lang = str(body.get("lang") or "")
    if not lang:
        review = state.load_review(project)
        d = dict(review["dub"])
        if d.pop(cid, None) is not None:
            state.save_review(project, {"dub": d})
            _rerender(project, cid)
        return api_clip(project_id, cid)
    j = active_job(project_id, cid) or submit(project_id, cid, lang)
    return {**api_clip(project_id, cid), "job": j.to_dict()}
