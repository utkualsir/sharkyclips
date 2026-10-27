"""Governor safe points in hot loops: gate(), deferred() and throttling."""

from __future__ import annotations

import threading
import time

import pytest

from sharkyclips import governor


class _Job:
    cancel_requested = False
    paused = False


@pytest.fixture
def gov():
    g = governor.Governor()  # not started: driven by hand
    old = governor._gov
    governor._gov = g
    try:
        yield g
    finally:
        g._go.set()
        governor._gov = old
        governor.set_current_job(None)


def _run(fn):
    out: list = []

    def body():
        try:
            fn()
            out.append("passed")
        except governor.JobCancelled:
            out.append("cancelled")

    th = threading.Thread(target=body)
    th.start()
    return th, out


def test_gate_waits_while_paused(gov):
    gov._go.clear()
    th, out = _run(governor.gate)
    time.sleep(0.3)
    assert out == []
    gov._go.set()
    th.join(3)
    assert out == ["passed"]


def test_gate_returns_when_its_stop_event_is_set(gov):
    gov._go.clear()
    stop = threading.Event()
    th, out = _run(lambda: governor.gate(stop))
    stop.set()
    th.join(3)
    assert out == ["passed"]


def test_gate_releases_helper_threads_of_a_cancelled_job(gov):
    gov._go.clear()
    th, out = _run(governor.gate)
    time.sleep(0.2)
    gov.cancel_epoch += 1  # what job_cancelled() does
    th.join(3)
    assert out == ["passed"]


def test_gate_raises_for_the_cancelled_job_itself(gov):
    gov._go.clear()
    job = _Job()

    def body():
        governor.set_current_job(job)
        governor.gate()

    th, out = _run(body)
    time.sleep(0.2)
    job.cancel_requested = True
    th.join(3)
    assert out == ["cancelled"]


def test_deferred_never_pauses(gov):
    gov._go.clear()

    def body():
        with governor.deferred():
            governor.gate()
            assert governor.checkpoint() is False

    th, out = _run(body)
    th.join(3)
    assert out == ["passed"]


def test_throttle_sleeps_in_proportion_to_work(gov, monkeypatch):
    slept: list[float] = []
    monkeypatch.setattr(governor.time, "sleep", slept.append)
    clock = [100.0]
    monkeypatch.setattr(governor.time, "monotonic", lambda: clock[0])
    gov.decision = governor.Decision(state="throttled", throttle=0.5)
    governor._tls.t = None
    governor._throttle(gov)  # first call only starts the clock
    clock[0] += 1.0
    governor._throttle(gov)
    assert slept == [pytest.approx(0.5)]
    clock[0] += 0.1  # too little work since the last sleep: no pause yet
    governor._throttle(gov)
    assert len(slept) == 1
    gov.decision = governor.Decision(state="run", throttle=0.0)
    clock[0] += 2
    governor._throttle(gov)
    assert len(slept) == 1
