"""YouTube API data retention: 30-day refresh-or-delete, delete on disconnect / revoked sign-in."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sharkyclips import config, abtest, calibration, youtube, ytdata
from sharkyclips.project import project_for_id, read_json, write_json_atomic

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_leftover_projects():
    """Other test files expect an empty shared workspace (test_web.test_projects_empty)."""
    import shutil

    yield
    for pid in ['ytdata-test']:
        shutil.rmtree(project_for_id(pid).dir, ignore_errors=True)
    for p in config.workspace_dir().glob("*"):
        if p.is_dir() and (p / "source.mp4").is_file() and p.name.startswith(("ranked-grind", "kick", "demo", "ace")):
            shutil.rmtree(p, ignore_errors=True)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds")


def _setup():
    p = project_for_id("ytdata-test")
    p.dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(p.dir / "uploads.json", {"version": 1, "uploads": {
        "c01": [{"video_id": "FRESH", "privacy": "public", "views": 900, "likes": 9, "stats_at": _iso(2)}],
        "c02": [{"video_id": "OLD", "privacy": "public", "views": 50, "likes": 1, "retention": 61.0, "stats_at": _iso(40)}],
    }})
    data = calibration.load()
    data["entries"] = {
        "a:c01": {"views": 900, "source": "youtube", "updated_at": _iso(2), "features": {}},
        "a:c02": {"views": 50, "source": "youtube", "updated_at": _iso(45), "features": {}},
        "a:c03": {"views": 77, "source": "manual", "updated_at": _iso(400), "features": {}},
    }
    calibration._save(data)
    abtest._save_store({"version": 1, "observations": [
        {"video_id": "OLD", "style": abtest.STYLES[0], "retention": 61.0, "views": 50, "reward": 0.8, "fetched_at": _iso(40)},
        {"video_id": "FRESH", "style": abtest.STYLES[0], "retention": 70.0, "views": 900, "reward": 0.9, "fetched_at": _iso(1)},
    ]})
    return p


def test_numbers_older_than_30_days_go():
    p = _setup()
    out = ytdata.purge(now=NOW)
    assert out == {"uploads": 1, "calibration": 1, "hook_tests": 1}
    ups = read_json(p.dir / "uploads.json")["uploads"]
    assert ups["c01"][0]["views"] == 900
    assert ups["c02"][0] == {"video_id": "OLD", "privacy": "public"}  # the id stays, the numbers go
    assert set(calibration.load()["entries"]) == {"a:c01", "a:c03"}  # typed-in numbers stay
    old = next(o for o in abtest.load_store()["observations"] if o["video_id"] == "OLD")
    assert "retention" not in old and "views" not in old and old["reward"] == 0.8
    assert ytdata.purge(now=NOW) == {"uploads": 0, "calibration": 0, "hook_tests": 0}


def test_disconnect_deletes_every_fetched_number(monkeypatch):
    p = _setup()
    monkeypatch.setattr(youtube, "_token", lambda: None)
    youtube.disconnect()
    ups = read_json(p.dir / "uploads.json")["uploads"]
    assert all("views" not in u for lst in ups.values() for u in lst)
    assert set(calibration.load()["entries"]) == {"a:c03"}
    assert abtest.load_store()["observations"] == []


def test_revoked_sign_in_is_cleaned_up_after_7_days(monkeypatch):
    _setup()
    monkeypatch.setattr(ytdata, "_last", {"t": 0.0})
    monkeypatch.setattr(youtube, "signed_out", lambda: {"at": _iso(3)})
    assert ytdata.daily(now=NOW)["calibration"] == 1  # within 7 days: only the 30-day rule
    ytdata._last["t"] = 0.0
    monkeypatch.setattr(youtube, "signed_out", lambda: {"at": _iso(8)})
    assert ytdata.daily(now=NOW)["calibration"] == 1  # the fresh one goes too now
    assert set(calibration.load()["entries"]) == {"a:c03"}
    assert ytdata.daily(now=NOW) is None  # once a day
