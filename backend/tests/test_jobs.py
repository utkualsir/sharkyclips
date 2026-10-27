"""The job queue (web/jobs.py): lanes, order, dedupe, cancel, errors, persistence."""

from __future__ import annotations

import json
import threading
import time

import pytest

from sharkyclips.errors import SharkyClipsError
from sharkyclips.web.jobs import JobManager


def wait_for(cond, timeout: float = 5.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return
        time.sleep(0.01)
    raise AssertionError("timed out")


class Gate:
    """A job body that blocks until released, so tests control what is 'running'."""

    def __init__(self, result=None):
        self.started = threading.Event()
        self.go = threading.Event()
        self.result = result

    def __call__(self, job):
        self.started.set()
        assert self.go.wait(5)
        return self.result


@pytest.fixture
def jm(tmp_path):
    return JobManager(store=tmp_path / "_queue.json")


def test_runs_in_order_and_records_result(jm):
    order: list[str] = []
    a = jm.submit("render", "gpu", "p1", {}, lambda j: order.append("a") or 1, dedupe=False)
    b = jm.submit("render", "gpu", "p1", {}, lambda j: order.append("b") or 2, dedupe=False)
    wait_for(lambda: b.status == "done")
    assert order == ["a", "b"] and (a.result, b.result) == (1, 2)
    assert a.progress == 1.0 and a.finished >= a.started


def test_dedupe_by_kind_project_and_key(jm):
    gate = Gate()
    first = jm.submit("transcribe", "gpu", "p1", {}, gate)
    assert jm.submit("transcribe", "gpu", "p1", {}, gate) is first
    assert jm.submit("transcribe", "gpu", "p2", {}, gate) is not first
    k1 = jm.submit("render", "gpu", "p1", {}, gate, key="r:c01")
    assert jm.submit("render", "gpu", "p1", {}, gate, key="r:c01") is k1
    assert jm.submit("render", "gpu", "p1", {}, gate, key="r:c02") is not k1
    gate.go.set()
    wait_for(lambda: not jm.busy())


def test_lanes_run_side_by_side(jm):
    gpu = Gate()
    jm.submit("render", "gpu", "p1", {}, gpu)
    assert gpu.started.wait(5)
    io = jm.submit("import", "io", None, {}, lambda j: "ok")
    wait_for(lambda: io.status == "done")  # downloads don't wait for the GPU lane
    gpu.go.set()
    wait_for(lambda: not jm.busy())


def test_move_front_and_cancel_queued(jm):
    gate = Gate()
    running = jm.submit("render", "gpu", None, {}, gate, dedupe=False)
    assert gate.started.wait(5)
    a = jm.submit("render", "gpu", None, {"n": "a"}, lambda j: None, dedupe=False)
    b = jm.submit("render", "gpu", None, {"n": "b"}, lambda j: None, dedupe=False)
    c = jm.submit("titles", "gpu", None, {"n": "c"}, lambda j: None, dedupe=False, front=True)
    assert [j.id for j in jm.lane_order("gpu")] == [running.id, c.id, a.id, b.id]
    jm.move(b.id, 0)
    assert [j.id for j in jm.lane_order("gpu")] == [running.id, b.id, c.id, a.id]
    jm.move(b.id, 99)  # clamped to the end
    assert jm.lane_order("gpu")[-1] is b
    assert jm.move(running.id, 0) is running  # a running job doesn't move
    jm.cancel(a.id)
    assert a.status == "cancelled" and a not in jm.lane_order("gpu")
    assert jm.forget(a.id) and jm.get(a.id) is None
    assert not jm.forget(b.id)  # still queued
    gate.go.set()
    wait_for(lambda: not jm.busy())
    assert a.status == "cancelled" and b.status == "done"


def test_cancel_running_job_at_its_next_update(jm):
    started = threading.Event()

    def body(job):
        started.set()
        for _ in range(500):
            jm.update(job, progress=0.5)
            time.sleep(0.01)
        return "too late"

    job = jm.submit("render", "gpu", None, {}, body)
    assert started.wait(5)
    jm.cancel(job.id)
    wait_for(lambda: job.status == "cancelled")
    assert job.result is None


def test_errors_are_kept_and_follow_ups_only_after_success(jm):
    followed: list[str] = []
    finished: list[str] = []
    jm.on_finished.append(lambda j: finished.append(j.status))

    def nice(job):
        raise SharkyClipsError("No video.", "Import one first.")

    def crash(job):
        raise ValueError("boom")

    a = jm.submit("x", "io", None, {}, nice, then=lambda j: followed.append("a"), dedupe=False)
    b = jm.submit("x", "io", None, {}, crash, then=lambda j: followed.append("b"), dedupe=False)
    c = jm.submit("x", "io", None, {}, lambda j: 1, then=lambda j: followed.append("c"), dedupe=False)
    wait_for(lambda: c.status == "done")
    assert a.error == {"message": "No video.", "hint": "Import one first."} and a.status == "error"
    assert b.status == "error" and b.error["message"] == "ValueError: boom"
    assert followed == ["c"]
    wait_for(lambda: len(finished) == 3)
    assert finished == ["error", "error", "done"]


def test_progress_is_clamped_and_detail_merged(jm):
    gate = Gate()
    job = jm.submit("render", "gpu", None, {}, gate)
    assert gate.started.wait(5)
    rev = jm.rev
    jm.update(job, stage="encoding", progress=1.7, detail={"a": 1})
    jm.update(job, progress=-1, detail={"b": 2})
    assert job.stage == "encoding" and job.progress == 0.0 and job.detail == {"a": 1, "b": 2}
    jm.update(job, progress=None)
    assert job.progress is None and jm.rev > rev
    gate.go.set()
    wait_for(lambda: not jm.busy())


def test_persistent_jobs_survive_a_restart(tmp_path):
    store = tmp_path / "_queue.json"
    jm = JobManager(store=store)
    gate = Gate()
    done = jm.submit("render", "gpu", "p1", {"cid": "c00"}, lambda j: "ok", persist=True, key="r0")
    wait_for(lambda: done.status == "done")
    running = jm.submit("render", "gpu", "p1", {"cid": "c01"}, gate, persist=True, key="r1")
    assert gate.started.wait(5)
    queued = jm.submit("render", "gpu", "p1", {"cid": "c02"}, lambda j: None, persist=True, key="r2")
    jm.submit("titles", "gpu", "p1", {}, lambda j: None, key="t")  # not persistent: not saved
    saved = json.loads(store.read_text(encoding="utf-8"))["jobs"]
    assert {s["params"].get("cid") for s in saved} == {"c00", "c01", "c02"}

    # "restart": a new manager reads the file; unfinished jobs are rebuilt, finished = history
    rebuilt: list[dict] = []
    jm2 = JobManager(store=store)

    def rebuild(s):
        rebuilt.append(s)
        return jm2.submit(s["kind"], s["lane"], s["project_id"], s["params"], lambda j: "again",
                          persist=True, job_id=s["id"], key=f"r:{s['params']['cid']}")

    assert jm2.restore(rebuild) == 2
    assert [s["params"]["cid"] for s in rebuilt] == ["c01", "c02"]  # the running one first
    assert jm2.get(done.id).status == "done" and jm2.get(done.id).fn is None
    wait_for(lambda: not jm2.busy())
    assert jm2.get(queued.id).detail.get("resumed") is True
    new = jm2.submit("x", "io", None, {}, lambda j: None, dedupe=False)
    assert int(new.id[1:]) > int(queued.id[1:])  # ids don't collide with the restored ones
    gate.go.set()
    wait_for(lambda: running.status == "done")


def test_restore_tolerates_a_broken_file_and_broken_entries(tmp_path):
    store = tmp_path / "_queue.json"
    store.write_text("{not json", encoding="utf-8")
    assert JobManager(store=store).restore(lambda s: None) == 0
    store.write_text(json.dumps({"jobs": [
        {"id": "j7", "kind": "render", "lane": "gpu", "status": "queued", "params": {}},
        {"id": "j8", "kind": "render", "lane": "weird", "status": "error", "params": {}}]}), encoding="utf-8")
    jm = JobManager(store=store)

    def explode(_s):
        raise RuntimeError("project gone")

    assert jm.restore(explode) == 0
    assert jm.get("j8").lane == "gpu"  # unknown lane falls back to gpu
    assert int(jm.submit("x", "io", None, {}, lambda j: None).id[1:]) > 8


def test_finished_jobs_are_trimmed(jm):
    jm.KEEP_FINISHED = 3
    jobs = [jm.submit("x", "io", None, {}, lambda j: None, dedupe=False) for _ in range(6)]
    wait_for(lambda: jobs[-1].status == "done")
    jm.submit("x", "io", None, {}, lambda j: None, dedupe=False)  # trimming happens on submit
    assert len([j for j in jm.jobs() if j.status == "done"]) <= 4
    assert jm.get(jobs[0].id) is None


def test_active_for_prefers_the_running_job(jm):
    gate = Gate()
    run = jm.submit("render", "gpu", "p1", {}, gate, dedupe=False)
    assert gate.started.wait(5)
    jm.submit("titles", "gpu", "p1", {}, lambda j: None, dedupe=False)
    assert jm.active_for("p1") is run and jm.active_for("nope") is None
    assert len(jm.for_project("p1")) == 2
    gate.go.set()
    wait_for(lambda: not jm.busy())
