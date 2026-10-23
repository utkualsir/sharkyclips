"""Background jobs for the web UI.

Two lanes, each with one worker thread:
  gpu  transcription, highlight analysis, rendering - heavy work, strictly one at a time
       (so Whisper, a later local LLM and the video encoder never fight over the GPU)
  io   downloads/imports and facecam detection - can run while the GPU is busy

Progress comes from the pipeline's normal progress bars (see ui.set_progress_sink),
so the CLI and the web UI share the exact same code paths.
"""

from __future__ import annotations

import itertools
import queue
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from ..errors import ClipForgeError
from ..ui import console, set_progress_sink

# Progress bar descriptions in the pipeline -> stable stage keys the UI translates.
STAGES = {
    "Downloading": "downloading",
    "Merging": "merging",
    "Copying video": "copying",
    "Extracting audio": "extracting_audio",
    "Transcribing": "transcribing",
    "Audio event model": "downloading_model",
    "Listening for laughter": "listening",
    "LLM reading": "llm_reading",
    "Downloading LLM": "downloading_llm",
    "Downloading chat": "downloading_chat",
}

ACTIVE = ("queued", "running")


class JobCancelled(Exception):
    pass


@dataclass
class Job:
    id: str
    kind: str  # import | transcribe | highlights | render | facecam
    lane: str
    project_id: str | None
    params: dict
    fn: Callable[["Job"], Any] = field(repr=False)
    then: Callable[["Job"], None] | None = field(default=None, repr=False)
    status: str = "queued"  # queued | running | done | error | cancelled
    stage: str | None = None
    progress: float | None = None  # 0..1, None = indeterminate
    detail: dict = field(default_factory=dict)
    error: dict | None = None
    result: Any = None
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    cancel_requested: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "lane": self.lane, "project_id": self.project_id,
                "params": self.params, "status": self.status, "stage": self.stage,
                "progress": None if self.progress is None else round(self.progress, 4),
                "detail": self.detail, "error": self.error, "result": self.result,
                "created": self.created, "started": self.started, "finished": self.finished}


class JobManager:
    KEEP_FINISHED = 60

    def __init__(self):
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._queues = {"gpu": queue.Queue(), "io": queue.Queue()}
        self._ids = itertools.count(1)
        self.rev = 0  # bumped on every change; SSE clients watch it
        for lane, q in self._queues.items():
            threading.Thread(target=self._worker, args=(q,), name=f"clipforge-{lane}",
                             daemon=True).start()

    # ------------------------------------------------------------------ public

    def submit(self, kind: str, lane: str, project_id: str | None, params: dict,
               fn: Callable[[Job], Any], then: Callable[[Job], None] | None = None,
               dedupe: bool = True) -> Job:
        with self._lock:
            if dedupe:
                for j in self._jobs.values():
                    if (j.kind == kind and j.project_id == project_id and j.status in ACTIVE
                            and project_id is not None):
                        return j
            job = Job(f"j{next(self._ids)}", kind, lane, project_id, params, fn, then)
            self._jobs[job.id] = job
            self._trim()
            self._bump()
        self._queues[lane].put(job)
        return job

    def cancel(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status in ACTIVE:
                job.cancel_requested = True
                if job.status == "queued":
                    job.status = "cancelled"
                    job.finished = time.time()
                self._bump()
            return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[dict]:
        with self._lock:
            return [j.to_dict() for j in self._jobs.values()]

    def for_project(self, project_id: str) -> list[Job]:
        with self._lock:
            return [j for j in self._jobs.values() if j.project_id == project_id]

    def active_for(self, project_id: str) -> Job | None:
        """The running job for a project, else the first queued one."""
        jobs = [j for j in self.for_project(project_id) if j.status in ACTIVE]
        jobs.sort(key=lambda j: (j.status != "running", j.created))
        return jobs[0] if jobs else None

    def update(self, job: Job, *, stage: str | None = None, progress: float | None = ...,
               detail: dict | None = None) -> None:
        """Called from the job's own thread. Raises JobCancelled when cancel was requested."""
        if job.cancel_requested:
            raise JobCancelled()
        with self._lock:
            if stage is not None:
                job.stage = stage
            if progress is not ...:
                job.progress = None if progress is None else min(1.0, max(0.0, progress))
            if detail is not None:
                job.detail = {**job.detail, **detail}
            self._bump()

    # ----------------------------------------------------------------- worker

    def _bump(self) -> None:
        self.rev += 1

    def _trim(self) -> None:
        done = [j for j in self._jobs.values() if j.status not in ACTIVE]
        for j in done[: max(0, len(done) - self.KEEP_FINISHED)]:
            self._jobs.pop(j.id, None)

    def _sink_for(self, job: Job):
        last = {"t": 0.0, "stage": None}

        def sink(description: str, completed: float, total: float | None) -> None:
            if job.cancel_requested:
                raise JobCancelled()
            stage = STAGES.get(description, description)
            now = time.monotonic()
            # Throttle: progress bars can fire hundreds of times a second.
            if stage == last["stage"] and now - last["t"] < 0.25 and not (total and completed >= total):
                return
            last["t"], last["stage"] = now, stage
            detail = {"completed": completed, "total": total}
            self.update(job, stage=stage, progress=(completed / total) if total else None,
                        detail=detail)

        return sink

    def _worker(self, q: queue.Queue) -> None:
        while True:
            job: Job = q.get()
            if job.status != "queued":
                continue  # cancelled while waiting
            with self._lock:
                job.status = "running"
                job.started = time.time()
                self._bump()
            set_progress_sink(self._sink_for(job))
            try:
                job.result = job.fn(job)
                job.status = "done"
                job.progress = 1.0
            except JobCancelled:
                job.status = "cancelled"
            except ClipForgeError as exc:
                job.status = "cancelled" if job.cancel_requested else "error"
                job.error = {"message": exc.message, "hint": exc.hint}
            except Exception as exc:  # noqa: BLE001 - shown in the UI, full trace in the terminal
                if job.cancel_requested:
                    job.status = "cancelled"
                else:
                    job.status = "error"
                    job.error = {"message": f"{type(exc).__name__}: {exc}"[:600], "hint": None}
                    console.print(f"[red]Job {job.kind} failed:[/]\n{traceback.format_exc()}")
            finally:
                set_progress_sink(None)
                with self._lock:
                    job.finished = time.time()
                    self._bump()
            if job.status == "done" and job.then:
                try:
                    job.then(job)
                except Exception:  # noqa: BLE001
                    console.print(f"[red]Follow-up of {job.kind} failed:[/]\n{traceback.format_exc()}")
