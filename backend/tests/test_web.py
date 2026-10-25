from __future__ import annotations

import socket

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import cli  # noqa: E402
from clipforge import __version__  # noqa: E402
from clipforge.web.app import app  # noqa: E402

client = TestClient(app)


def test_meta():
    r = client.get("/api/meta")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == __version__
    assert "tr" in [lang["code"] for lang in data["languages"]]


def test_settings_roundtrip():
    r = client.put("/api/settings", json={"default_mode": "music"})
    assert r.status_code == 200 and r.json()["default_mode"] == "music"
    assert client.get("/api/settings").json()["default_mode"] == "music"
    client.put("/api/settings", json={"default_mode": "gaming"})


def test_settings_reject_unknown_mode():
    r = client.put("/api/settings", json={"default_mode": "cooking"})
    assert r.status_code >= 400


def test_projects_empty():
    assert client.get("/api/projects").json() == []


def test_update_status_without_fetch():
    data = client.get("/api/update", params={"fetch": "false"}).json()
    assert data["current"] == __version__
    assert data["can_restart"] is False
    assert {"available", "supported", "reason", "releases_url"} <= set(data)


def test_restart_needs_supervisor():
    assert client.post("/api/update/restart").json() == {"restarting": False}


def test_unknown_api_path():
    assert client.get("/api/nope").status_code == 404


def test_cli_parser_has_launch_and_model_download():
    p = cli.build_parser()
    assert p.parse_args(["launch"]).func is cli.cmd_launch
    assert p.parse_args(["doctor", "--download-models"]).download_models is True


def test_port_helpers():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        busy = s.getsockname()[1]
        assert cli._port_free(busy) is False
        assert cli._clipforge_version_at(busy, timeout=0.3) is None


def test_performance_settings():
    data = client.get("/api/settings").json()
    assert data["performance_mode"] == "silent" and "deltaforce*" in data["perf_games"]
    r = client.put("/api/settings", json={"performance_mode": "turbo", "perf_idle_minutes": 0.1,
                                          "perf_games": ["CS2.exe", "mygame"]})
    body = r.json()
    assert body["performance_mode"] == "turbo" and body["perf_idle_minutes"] == 0.5
    assert body["perf_games"] == ["cs2", "mygame"]
    assert client.put("/api/settings", json={"performance_mode": "warp"}).status_code >= 400
    assert client.put("/api/governor", json={"mode": "balanced"}).json()["mode"] == "balanced"
    client.put("/api/settings", json={"performance_mode": "silent", "perf_idle_minutes": 3,
                                      "perf_games": data["perf_games_default"]})
    assert client.get("/api/settings").json()["perf_games"] == data["perf_games_default"]
    assert client.get("/api/governor").json()["state"] == "off"  # tests run without the governor
