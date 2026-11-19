"""First-run downloads + diagnostics API (1.2.56, see components.py and diag.py).

  GET  /api/setup              the plan: what this PC needs, sizes, what is already there
  POST /api/setup/download     {"ids": [...]}: one "setup" job (net lane, own slot) with progress
                               in job.detail (bytes, speed, time left, per-item status)
  GET  /api/diag               the diagnostic report (redacted; the error screen and Settings copy it)
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Request

from .. import components
from ..errors import SharkyClipsError
from .jobs import ACTIVE, Job

router = APIRouter()


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


@router.get("/api/setup")
def api_setup_plan() -> dict:
    A = _app()
    running = next((j for j in A.jobs.jobs() if j.kind == "setup" and j.status in ACTIVE), None)
    return {**components.plan(), "job": running.to_dict() if running else None}


@router.post("/api/setup/download")
def api_setup_download(request: Request, body: dict | None = Body(default=None)) -> dict:
    A = _app()
    if not A._is_local(request):
        raise SharkyClipsError("Downloads can only be started on the computer running SharkyClips.")
    ids = [str(i) for i in ((body or {}).get("ids") or []) if isinstance(i, str)]
    known = {"whisper", "whisper_tiny", "cuda", "deno", "ollama", "llm"}
    ids = [i for i in ids if i in known]
    if not ids:
        raise SharkyClipsError("Nothing to download was picked.")

    def run(job: Job):
        def report(d: dict) -> None:
            A.jobs.update(job, stage="setup_download", progress=d.get("fraction"), detail=d)

        def cancelled() -> bool:
            return job.cancel_requested

        try:
            return components.install(ids, report, cancelled)
        finally:
            components.forget_ready()

    with A.explicit():
        job = A.jobs.submit("setup", "net", None, {"platform": "setup", "ids": ids}, run, key="setup")
    return job.to_dict()


@router.get("/api/diag")
def api_diag(request: Request) -> dict:
    from .. import diag

    A = _app()
    if not A._is_local(request):
        raise SharkyClipsError("The diagnostic report is only shown on the computer running SharkyClips.")
    return {"text": diag.report_text()}
