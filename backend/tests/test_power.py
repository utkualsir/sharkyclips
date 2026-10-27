"""Shut down when the queue is finished: countdown logic only, never a real shutdown."""

from __future__ import annotations

import time

import pytest

from sharkyclips.web import power


def _never(*_a, **_k):
    raise AssertionError("tests must never run a shutdown command")


@pytest.fixture
def timer(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_DRY_SHUTDOWN", "1")
    monkeypatch.setattr(power.subprocess, "run", _never)
    monkeypatch.setattr(power, "COUNTDOWN_S", 0.3)
    state = {"busy": False, "changes": 0}

    def changed():
        state["changes"] += 1

    t = power.ShutdownTimer(busy=lambda: state["busy"], changed=changed)
    assert t.dry_run
    return t, state


def _wait(cond, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not cond():
        time.sleep(0.05)
    return cond()


def test_countdown_fires_once_when_the_queue_is_empty(timer):
    t, state = timer
    t.job_finished()
    assert t.deadline is None  # not armed: nothing happens
    t.set_enabled(True)
    t.job_finished()
    assert t.state()["countdown"] is not None
    assert _wait(lambda: t.fired_at is not None)
    assert not t.enabled and t.deadline is None and state["changes"] >= 3


def test_new_work_stops_the_countdown(timer):
    t, state = timer
    t.set_enabled(True)
    t.job_finished()
    state["busy"] = True
    assert _wait(lambda: t.deadline is None)
    assert t.enabled and t.fired_at is None  # still armed, waits for the queue again


def test_cancel_switches_it_off(timer):
    t, _ = timer
    t.set_enabled(True)
    t.job_finished()
    s = t.cancel()
    assert not s["enabled"] and s["countdown"] is None
    time.sleep(0.6)
    assert t.fired_at is None


def test_shutdown_command_per_os(monkeypatch):
    monkeypatch.setattr(power.platform, "system", lambda: "Windows")
    assert power.shutdown_command()[0] == "shutdown" and power.supported()
    monkeypatch.setattr(power.platform, "system", lambda: "Darwin")
    assert power.shutdown_command()[0] == "osascript" and power.supported()
    monkeypatch.setattr(power.platform, "system", lambda: "Linux")
    assert not power.supported()


def test_failed_shutdown_is_reported(monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_DRY_SHUTDOWN", raising=False)

    def denied(*_a, **_k):
        raise PermissionError("not allowed")

    monkeypatch.setattr(power.subprocess, "run", denied)
    t = power.ShutdownTimer(busy=lambda: False, changed=lambda: None)
    assert not t.dry_run
    t._shutdown()
    assert "not allowed" in t.state()["error"]
