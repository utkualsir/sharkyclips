"""Background jobs for the web UI.

Two lanes, each with one worker thread:
  gpu  transcription, highlight analysis, LLM, rendering, best-of videos - heavy work, strictly
       one at a time (Whisper, the local LLM and the video encoder never fight over the GPU)
  io   downloads/imports and facecam detection - can run while the GPU is busy

Each lane is an ordered list: queued jobs can be moved up and down (the Queue screen).
Batch jobs (renders, best-of videos) are "persistent": they are written to
<workspace>/_queue.json, so a server restart puts unfinished ones back in the queue.

Progress comes from the pipeline's normal progress bars (see ui.set_progress_sink),
so the CLI and the web UI share the exact same code paths.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .. import governor
from ..errors import SharkyClipsError
from ..governor import JobCancelled  # noqa: F401 - re-exported, raised from governor checkpoints
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
    "Reading the game HUD": "reading_hud",
}

ACTIVE = ("queued", "running")


def _release_gpu() -> None:
    """After a GPU job: no model may stay in VRAM (Ollama keep_alive 0)."""
    try:
        from .. import llm, memory

        memory.release_current()
        if governor.get() is not None:  # the web server; tests run without one
            llm.unload_all()
    except Exception:  # noqa: BLE001
        pass
HISTORY_KEEP = 40  # finished persistent jobs kept in _queue.json (the Queue screen's history)


@dataclass
class Job:
    id: str
    kind: str  # import | transcribe | highlights | render | montage | facecam | ...
    lane: str
    project_id: str | None
    params: dict
    fn: Callable[["Job"], Any] | None = field(repr=False)
    then: Callable[["Job"], None] | None = field(default=None, repr=False)
    key: str | None = None  # dedupe key (default: kind + project)
    persist: bool = False
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
    attempt: int = 1
    paused: bool = False  # waiting at a governor checkpoint right now
    pause_base: float = 0.0  # governor.paused_total() when the job started

    def paused_seconds(self) -> float:
        g = governor.get()
        if g is None or self.status != "running":
            return 0.0
        return max(0.0, g.paused_total() - self.pause_base)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "lane": self.lane, "project_id": self.project_id,
                "params": self.params, "status": self.status, "stage": self.stage,
                "progress": None if self.progress is None else round(self.progress, 4),
                "detail": self.detail, "error": self.error, "result": self.result,
                "created": self.created, "started": self.started, "finished": self.finished,
                "persist": self.persist, "attempt": self.attempt,
                **self._pause_view()}

    def _pause_view(self) -> dict:
        g = governor.get()
        if g is None or self.status != "running":
            return {"paused": None, "paused_seconds": 0}
        # Running jobs stop at their next safe point while the governor pauses.
        reason = (g.decision.reason or "paused") if (g.paused or self.paused) else None
        return {"paused": reason, "paused_seconds": round(self.paused_seconds(), 1)}


class JobManager:
    KEEP_FINISHED = 60

    def __init__(self, store: Path | None = None):
        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)
        self._jobs: dict[str, Job] = {}
        self._lanes: dict[str, list[Job]] = {"gpu": [], "io": []}
        self._next_id = 1
        self.store = store
        self.rev = 0  # bumped on every change; SSE clients watch it
        self.on_finished: list[Callable[[Job], None]] = []
        for lane in self._lanes:
            threading.Thread(target=self._worker, args=(lane,), name=f"sharkyclips-{lane}",
                             daemon=True).start()

    # ------------------------------------------------------------------ public

    def submit(self, kind: str, lane: str, project_id: str | None, params: dict,
               fn: Callable[[Job], Any], then: Callable[[Job], None] | None = None,
               dedupe: bool = True, key: str | None = None, persist: bool = False,
               job_id: str | None = None, attempt: int = 1, front: bool = False) -> Job:
        with self._lock:
            if dedupe:
                for j in self._jobs.values():
                    if j.status not in ACTIVE:
                        continue
                    if key is not None and j.key == key:
                        return j
                    if (key is None and j.key is None and j.kind == kind and j.project_id == project_id
                            and project_id is not None):
                        return j
            if job_id is None or job_id in self._jobs:
                job_id = f"j{self._next_id}"
                self._next_id += 1
            job = Job(job_id, kind, lane, project_id, params, fn, then, key=key, persist=persist,
                      attempt=attempt)
            self._jobs[job.id] = job
            if front:  # interactive work (e.g. one clip's titles) goes before a long batch
                queued = [i for i, j in enumerate(self._lanes[lane]) if j.status == "queued"]
                self._lanes[lane].insert(queued[0] if queued else len(self._lanes[lane]), job)
            else:
                self._lanes[lane].append(job)
            self._trim()
            self._changed(job)
            self._cv.notify_all()
        return job

    def cancel(self, job_id: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status in ACTIVE:
                job.cancel_requested = True
                g = governor.get()
                if g is not None and job.status == "running":
                    g.job_cancelled()
                if job.status == "queued":
                    job.status = "cancelled"
                    job.finished = time.time()
                    self._remove_from_lane(job)
                self._changed(job)
            return job

    def move(self, job_id: str, to: int) -> Job | None:
        """Move a queued job to position `to` among the queued jobs of its lane."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != "queued":
                return job
            lane = self._lanes[job.lane]
            queued = [j for j in lane if j.status == "queued" and j is not job]
            to = max(0, min(int(to), len(queued)))
            queued.insert(to, job)
            others = [j for j in lane if j.status != "queued"]
            self._lanes[job.lane] = others + queued
            self._changed(job)
            return job

    def forget(self, job_id: str) -> bool:
        """Remove a finished job from the list (Queue screen: clear history)."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in ACTIVE:
                return False
            self._jobs.pop(job_id, None)
            self._changed(job)
            return True

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[dict]:
        with self._lock:
            return [j.to_dict() for j in self._jobs.values()]

    def lane_order(self, lane: str) -> list[Job]:
        """Running job first, then the queued ones in the order they will run."""
        with self._lock:
            lst = [j for j in self._lanes[lane] if j.status in ACTIVE]
            return sorted(lst, key=lambda j: j.status != "running")

    def jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def busy(self) -> bool:
        with self._lock:
            return any(j.status in ACTIVE for j in self._jobs.values())

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

    def bump(self) -> None:
        with self._lock:
            self._bump()

    # ------------------------------------------------------------ persistence

    def restore(self, rebuild: Callable[[dict], Job | None]) -> int:
        """Load _queue.json: finished jobs come back as history, unfinished ones are
        re-submitted through `rebuild(saved_job_dict)`. Returns how many were re-queued."""
        if self.store is None or not self.store.is_file():
            return 0
        try:
            data = json.loads(self.store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        saved = data.get("jobs") or []
        with self._lock:
            nums = [int(s["id"][1:]) for s in saved if str(s.get("id", "")).startswith("j")
                    and str(s["id"][1:]).isdigit()]
            self._next_id = max([self._next_id - 1, *nums]) + 1
            for s in saved:
                if s.get("status") in ACTIVE:
                    continue
                job = Job(s["id"], s["kind"], s.get("lane") or "gpu", s.get("project_id"),
                          s.get("params") or {}, None, persist=True, status=s["status"],
                          stage=s.get("stage"), progress=s.get("progress"), detail=s.get("detail") or {},
                          error=s.get("error"), result=s.get("result"), created=s.get("created") or 0,
                          started=s.get("started"), finished=s.get("finished"), attempt=s.get("attempt") or 1)
                self._jobs[job.id] = job
        n = 0
        for s in sorted((s for s in saved if s.get("status") in ACTIVE),
                        key=lambda s: (s.get("status") != "running", s.get("order", 0))):
            try:
                job = rebuild(s)
            except Exception as exc:  # noqa: BLE001 - a broken entry must not stop the server
                console.print(f"[yellow]Could not restore queued job {s.get('id')}: {exc}[/]")
                job = None
            if job is not None:
                job.created = s.get("created") or job.created
                job.detail = {**job.detail, "resumed": True}
                n += 1
        self._save()
        return n

    def _save(self) -> None:
        if self.store is None:
            return
        with self._lock:
            order = {j.id: i for lane in self._lanes.values() for i, j in enumerate(lane)}
            persistent = [j for j in self._jobs.values() if j.persist]
            done = sorted((j for j in persistent if j.status not in ACTIVE), key=lambda j: j.finished or 0)
            keep = [j for j in persistent if j.status in ACTIVE] + done[-HISTORY_KEEP:]
            out = []
            for j in keep:
                d = j.to_dict()
                d["order"] = order.get(j.id, 0)
                out.append(d)
            payload = json.dumps({"version": 1, "jobs": out}, ensure_ascii=False, indent=1)
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store.with_suffix(".json.tmp")
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, self.store)
        except OSError as exc:
            console.print(f"[yellow]Could not save the job queue: {exc}[/]")

    # ----------------------------------------------------------------- worker

    def _bump(self) -> None:
        self.rev += 1

    def _changed(self, job: Job) -> None:
        self._bump()
        if job.persist:
            self._save()

    def _remove_from_lane(self, job: Job) -> None:
        lane = self._lanes.get(job.lane, [])
        if job in lane:
            lane.remove(job)

    def _trim(self) -> None:
        done = sorted((j for j in self._jobs.values() if j.status not in ACTIVE), key=lambda j: j.finished or 0)
        for j in done[: max(0, len(done) - self.KEEP_FINISHED)]:
            self._jobs.pop(j.id, None)

    def _sink_for(self, job: Job):
        last = {"t": 0.0, "stage": None}

        def sink(description: str, completed: float, total: float | None) -> None:
            governor.checkpoint()  # raises JobCancelled; waits here while the governor pauses
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

    def _next(self, lane: str) -> Job:
        with self._cv:
            while True:
                for j in self._lanes[lane]:
                    if j.status == "queued":
                        j.status = "running"
                        j.started = time.time()
                        self._changed(j)
                        return j
                self._cv.wait()

    def _worker(self, lane: str) -> None:
        while True:
            job = self._next(lane)
            set_progress_sink(self._sink_for(job))
            governor.set_current_job(job)
            g = governor.get()
            job.pause_base = g.paused_total() if g else 0.0
            try:
                if job.fn is None:
                    raise SharkyClipsError("This job can't run any more.")
                governor.checkpoint()  # don't even start while the governor pauses
                job.result = job.fn(job)
                job.status = "done"
                job.progress = 1.0
            except JobCancelled:
                job.status = "cancelled"
            except SharkyClipsError as exc:
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
                governor.set_current_job(None)
                job.paused = False
                if lane == "gpu":  # after every GPU job: no model stays in VRAM (keep_alive 0)
                    _release_gpu()
                with self._lock:
                    job.finished = time.time()
                    self._remove_from_lane(job)
                    self._changed(job)
            if job.status == "done" and job.then:
                try:
                    job.then(job)
                except Exception:  # noqa: BLE001
                    console.print(f"[red]Follow-up of {job.kind} failed:[/]\n{traceback.format_exc()}")
            for cb in list(self.on_finished):
                try:
                    cb(job)
                except Exception:  # noqa: BLE001
                    console.print(f"[red]Job listener failed:[/]\n{traceback.format_exc()}")
