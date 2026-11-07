"""Cancel is final (1.2.24).

A cancelled job is stored as cancelled, its child processes die at once, a half-written file is
removed, and nothing automatic brings it back: not Easy's auto renders, not the publish loop,
not the queue restore after a restart. Only an explicit request (Retry / a Render button)
starts it again. Plus "Pause queue" and "Cancel all".
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time

import psutil
import pytest
from test_jobs import Gate, wait_for
from test_publishing import _client, _idle, _project, _wait, cfg, yt  # noqa: F401, F811 - fixtures

from sharkyclips import governor, procs, render
from sharkyclips.web import state
from sharkyclips.web.jobs import JobManager, automatic, explicit

SLEEPER = [sys.executable, "-c", "import time\nfor _ in range(600):\n    print('out_time_us=1000000', flush=True)\n    time.sleep(0.1)"]


@pytest.fixture
def jm(tmp_path):
    return JobManager(store=tmp_path / "_queue.json")


def _saved(jm) -> dict:
    return json.loads(jm.store.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ queued


def test_cancel_queued_is_final_until_explicit(jm):
    gate = Gate()
    jm.submit("render", "gpu", "p1", {"clip_id": "c00"}, gate, key="render:p1:c00", persist=True)
    ran: list[str] = []
    q = jm.submit("render", "gpu", "p1", {"clip_id": "c01"}, lambda j: ran.append("c01"), key="render:p1:c01",
                  persist=True)
    jm.cancel(q.id)
    assert q.status == "cancelled" and q.finished
    # automatic code (Easy, the publish loop, a dub's follow-up) gets the cancelled job back
    again = jm.submit("render", "gpu", "p1", {"clip_id": "c01"}, lambda j: ran.append("auto"), key="render:p1:c01",
                      persist=True)
    assert again is q and again.blocked and again.status == "cancelled"
    assert jm.is_cancelled("render", "p1", "render:p1:c01")
    gate.go.set()
    wait_for(lambda: not jm.busy())
    assert ran == []
    assert _saved(jm)["cancelled"]["render:p1:c01"]["job"] == q.id
    # the user's Retry / Render button
    with explicit():
        retry = jm.submit("render", "gpu", "p1", {"clip_id": "c01"}, lambda j: ran.append("retry"),
                          key="render:p1:c01", persist=True)
    wait_for(lambda: retry.status == "done")
    assert ran == ["retry"] and not jm.is_cancelled("render", "p1", "render:p1:c01")


# ------------------------------------------------------------------ running


def test_cancel_running_kills_its_process_at_once(jm, tmp_path):
    partial = tmp_path / "01_c01.partial.mp4"
    started = threading.Event()
    seen: dict = {}

    def body(job):
        partial.write_bytes(b"half")
        started.set()
        # the renderer's pattern: hardware encode, and on failure a CPU retry
        code, _ = render.run_ffmpeg([*SLEEPER, str(partial)], 60.0, None)
        seen["first"] = code
        render.run_ffmpeg([*SLEEPER, str(partial)], 60.0, None)  # must never run
        seen["second"] = True

    job = jm.submit("render", "gpu", "p1", {"clip_id": "c01"}, body, key="render:p1:c01", persist=True)
    assert started.wait(10)
    wait_for(lambda: any(procs._owner.get(p.pid) == job.id for p in list(procs._tracked)), 10)
    pids = [p.pid for p in list(procs._tracked) if procs._owner.get(p.pid) == job.id]
    t0 = time.monotonic()
    jm.cancel(job.id)
    assert job.status == "cancelled"  # shown and stored as cancelled right away
    assert _saved(jm)["jobs"][0]["status"] == "cancelled"
    wait_for(lambda: not any(psutil.pid_exists(p) and psutil.Process(p).status() != psutil.STATUS_ZOMBIE
                             for p in pids), 5)
    assert time.monotonic() - t0 < 5
    wait_for(lambda: job.finished is not None, 10)
    assert job.status == "cancelled" and "second" not in seen  # no CPU fallback after a cancel
    assert not partial.exists()  # no half-written file left behind


def test_cancel_while_the_process_is_suspended(jm):
    """The governor suspends ffmpeg while a game runs: Cancel must still kill it now."""
    started = threading.Event()

    def body(job):
        started.set()
        render.run_ffmpeg([*SLEEPER, "out.partial.mp4"], 60.0, None)

    job = jm.submit("render", "gpu", "p1", {}, body, key="render:p1:c09")
    assert started.wait(10)
    wait_for(lambda: any(procs._owner.get(p.pid) == job.id for p in list(procs._tracked)), 10)
    pid = next(p.pid for p in list(procs._tracked) if procs._owner.get(p.pid) == job.id)
    procs.suspend_all()
    try:
        jm.cancel(job.id)
        wait_for(lambda: job.finished is not None, 10)
    finally:
        procs.resume_all()
    assert job.status == "cancelled" and not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_cancel_after_the_last_safe_point_stays_cancelled(jm):
    gate = Gate(result="rendered")
    then_ran: list[int] = []
    job = jm.submit("render", "gpu", "p1", {}, gate, then=lambda j: then_ran.append(1), key="render:p1:c02")
    assert gate.started.wait(5)
    jm.cancel(job.id)  # the body doesn't check again before it returns
    gate.go.set()
    wait_for(lambda: job.finished is not None)
    assert job.status == "cancelled" and then_ran == []


def test_cancel_all_and_listeners_see_cancelled(jm):
    gate = Gate()
    seen: list[tuple[str, str]] = []
    jm.on_finished.append(lambda j: seen.append((j.id, j.status)))
    jobs = [jm.submit("render", "gpu", "p1", {}, gate, key=f"render:p1:c{i}") for i in range(3)]
    assert gate.started.wait(5)
    assert jm.cancel_all() == 3
    gate.go.set()
    wait_for(lambda: not jm.busy())
    assert all(j.status == "cancelled" for j in jobs)
    assert (jobs[0].id, "cancelled") in seen


# ------------------------------------------------------------------ retry / restart / pause


def test_retry_after_error_is_not_blocked(jm):
    def boom(job):
        raise RuntimeError("encoder crashed")

    j = jm.submit("render", "gpu", "p1", {}, boom, key="render:p1:c03")
    wait_for(lambda: j.status == "error")
    again = jm.submit("render", "gpu", "p1", {}, lambda job: 1, key="render:p1:c03")  # errors aren't tombstoned
    wait_for(lambda: again.status == "done")


def test_restart_never_revives_a_cancelled_job(jm, tmp_path):
    gate = Gate()
    running = jm.submit("render", "gpu", "p1", {"clip_id": "c01"}, gate, key="render:p1:c01", persist=True)
    assert gate.started.wait(5)
    queued = jm.submit("render", "gpu", "p1", {"clip_id": "c02"}, gate, key="render:p1:c02", persist=True)
    keep = jm.submit("render", "gpu", "p1", {"clip_id": "c03"}, gate, key="render:p1:c03", persist=True)
    jm.cancel(queued.id)
    jm.cancel(running.id)  # the app quits before its thread unwinds
    jm.set_paused(True)
    saved = _saved(jm)
    # simulate an older file where the running job was still marked "running" + cancel_requested
    for s in saved["jobs"]:
        if s["id"] == running.id:
            s["status"] = "running"
    (tmp_path / "copy.json").write_text(json.dumps(saved), encoding="utf-8")
    gate.go.set()

    jm2 = JobManager(store=tmp_path / "copy.json")
    rebuilt: list[str] = []

    def rebuild(s):
        rebuilt.append(s["id"])
        return jm2.submit("render", "gpu", s["project_id"], s["params"], lambda j: 1, key=s.get("key"),
                          persist=True, job_id=s["id"])

    n = jm2.restore(rebuild)
    assert rebuilt == [keep.id] and n == 1
    assert jm2.get(running.id).status == "cancelled" and jm2.get(queued.id).status == "cancelled"
    assert jm2.paused  # still paused after the restart: the restored job waits
    time.sleep(0.3)
    assert jm2.get(keep.id).status == "queued"
    assert jm2.submit("render", "gpu", "p1", {}, lambda j: 1, key="render:p1:c02").blocked
    jm2.set_paused(False)
    wait_for(lambda: jm2.get(keep.id).status == "done")


def test_pause_queue(jm):
    jm.set_paused(True)
    j = jm.submit("render", "gpu", "p1", {}, lambda job: 1, key="render:p1:c05")
    time.sleep(0.3)
    assert j.status == "queued" and _saved(jm)["paused"] is True
    jm.set_paused(False)
    wait_for(lambda: j.status == "done")


def test_new_clips_and_library_actions_clear_tombstones(jm):
    gate = Gate()
    j = jm.submit("render", "gpu", "p1", {"clip_id": "c01"}, gate, key="render:p1:c01")
    jm.cancel(j.id)
    gate.go.set()
    assert jm.blocks_clip("p1", "c01") and not jm.blocks_clip("p1", "c02")
    assert jm.clear_tombstones("p1", ("render",), clip_id="c01") == 1
    assert not jm.is_cancelled("render", "p1", "render:p1:c01")


def test_track_kills_a_process_started_after_cancel(jm):
    started = threading.Event()
    out: dict = {}

    def body(job):
        started.set()
        assert job.cancel_requested or True
        wait_for(lambda: job.cancel_requested, 5)
        p = subprocess.Popen(SLEEPER, stdout=subprocess.DEVNULL, **procs.no_window())
        procs.track(p)
        out["code"] = p.wait(10)
        procs.untrack(p)

    job = jm.submit("render", "gpu", "p1", {}, body, key="render:p1:c07")
    assert started.wait(5)
    jm.cancel(job.id)
    wait_for(lambda: job.finished is not None, 15)
    assert "code" in out and out["code"] != 0


def test_automatic_block_overrides_explicit():
    from sharkyclips.web import jobs as J

    with explicit():
        assert J.is_explicit()
        with automatic():
            assert not J.is_explicit()
        assert J.is_explicit()
    assert not J.is_explicit()
    assert governor.current_job() is None


# ------------------------------------------------------------------ the real bug: Easy re-queued it


def test_easy_never_requeues_a_cancelled_render(yt):  # noqa: F811
    """1.2.23 bug: Cancel on the Queue screen, and Easy's listener queued the clip again."""
    from sharkyclips.web import app as A

    project = _project("pub-cancel-easy", 3)
    with _client() as client:
        assert client.post("/api/queue/pause", json={"paused": True}).json() == {"paused": True}
        assert client.get("/api/queue").json()["paused"] is True
        v = client.post(f"/api/easy/projects/{project.id}/prepare").json()
        assert sorted(v["queued"]) == ["c01", "c02", "c03"]
        renders = {j.params["clip_id"]: j for j in A.jobs.for_project(project.id) if j.kind == "render"}
        for cid in ("c02", "c03"):
            r = client.post(f"/api/jobs/{renders[cid].id}/cancel").json()
            assert r["status"] == "cancelled"
        client.post("/api/queue/pause", json={"paused": False})
        _wait(_idle, 300)
        mine = [j for j in A.jobs.for_project(project.id) if j.kind == "render"]
        assert sorted((j.params["clip_id"], j.status) for j in mine) == [
            ("c01", "done"), ("c02", "cancelled"), ("c03", "cancelled")]
        assert set(state.load_clips(project)) == {"c01"}
        # opening the project again (Easy page) doesn't restart them either
        v = client.post(f"/api/easy/projects/{project.id}/prepare").json()
        assert v["queued"] == []
        _wait(_idle, 60)
        assert len([j for j in A.jobs.for_project(project.id) if j.kind == "render"]) == 3
        # the user's Retry does
        r = client.post(f"/api/jobs/{renders['c02'].id}/retry").json()
        assert r["status"] in ("queued", "running") and r["id"] != renders["c02"].id
        _wait(_idle, 300)
        assert set(state.load_clips(project)) == {"c01", "c02"}
        # "Cancel all" (with the Queue screen's confirm) cancels whatever is left
        client.post("/api/queue/pause", json={"paused": True})
        v = client.post(f"/api/easy/projects/{project.id}/retry").json()  # "Try again": explicit
        assert any(j.status == "queued" for j in A.jobs.for_project(project.id) if j.params.get("clip_id") == "c03")
        assert client.post("/api/queue/cancel", json={}).json()["cancelled"] >= 1
        client.post("/api/queue/pause", json={"paused": False})
        _wait(_idle, 60)
        assert set(state.load_clips(project)) == {"c01", "c02"}
        A.jobs.clear_tombstones(project.id)

