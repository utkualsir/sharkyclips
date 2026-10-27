"""LAN access PIN: hashing, sessions, rate limit, and the guard in front of the API."""

from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sharkyclips import lanauth  # noqa: E402
from sharkyclips.errors import SharkyClipsError  # noqa: E402
from sharkyclips.web.app import app  # noqa: E402

local = TestClient(app)


def phone() -> TestClient:
    return TestClient(app, client=("192.168.1.50", 50000))


@pytest.fixture(autouse=True)
def _clean():
    lanauth.clear_secret()
    lanauth.limiter = lanauth.Limiter()
    yield
    lanauth.clear_secret()
    lanauth.limiter = lanauth.Limiter()


def test_hash_is_salted_and_verifies():
    a, b = lanauth.hash_secret("1234", n=2 ** 10), lanauth.hash_secret("1234", n=2 ** 10)
    assert a != b and a.startswith("scrypt$1024$")
    assert lanauth.check_hash("1234", a) and not lanauth.check_hash("1235", a)
    assert not lanauth.check_hash("1234", "md5$x") and not lanauth.check_hash("1234", "garbage")


def test_secret_rules_and_storage():
    with pytest.raises(SharkyClipsError):
        lanauth.validate("12")
    with pytest.raises(SharkyClipsError):
        lanauth.validate(" 1234")
    assert lanauth.set_secret("482913") == "pin"
    assert lanauth.kind() == "pin" and lanauth.enabled()
    stored = lanauth.auth_path().read_text(encoding="utf-8")
    assert "482913" not in stored and json.loads(stored)["hash"].startswith("scrypt$")
    assert lanauth.verify("482913") and not lanauth.verify("482914")
    assert lanauth.set_secret("correct horse") == "password"
    assert not lanauth.verify("482913")


def test_sessions_store_only_a_hash_and_reset_with_a_new_pin():
    lanauth.set_secret("1234")
    token = lanauth.new_session()
    assert lanauth.session_valid(token) and not lanauth.session_valid("nope")
    assert token not in lanauth.sessions_path().read_text(encoding="utf-8")
    assert not lanauth.session_valid(token, now=9e12)  # expired
    lanauth.set_secret("5678")
    assert not lanauth.session_valid(token)
    t2 = lanauth.new_session()
    lanauth.end_session(t2)
    assert not lanauth.session_valid(t2)


def test_limiter_locks_and_doubles():
    lim = lanauth.Limiter(free=3, base_lock=30, max_lock=100, global_per_min=1000)
    for i in range(2):
        assert lim.fail("a", now=100 + i) == 0
    assert lim.fail("a", now=102) == pytest.approx(30)  # 3rd miss: locked
    assert lim.wait("a", now=110) == pytest.approx(22)
    assert lim.wait("b", now=110) == 0  # other devices aren't affected
    assert lim.fail("a", now=140) == pytest.approx(60)  # doubles
    assert lim.fail("a", now=300) == pytest.approx(100)  # capped
    lim.success("a")
    assert lim.wait("a", now=301) == 0


def test_limiter_global_cap():
    lim = lanauth.Limiter(free=100, global_per_min=5)
    for i in range(5):
        lim.fail(f"10.0.0.{i}", now=1000)
    assert lim.wait("10.0.0.99", now=1010) == pytest.approx(50)
    assert lim.wait("10.0.0.99", now=1061) == 0


def test_no_pin_means_open_and_local_never_needs_login():
    assert phone().get("/api/meta").status_code == 200
    lanauth.set_secret("1234")
    assert local.get("/api/meta").status_code == 200
    s = local.get("/api/auth/status").json()
    assert s["enabled"] and not s["required"] and s["authenticated"]


def test_guard_blocks_other_devices_until_login():
    lanauth.set_secret("1234")
    p = phone()
    for path in ("/api/meta", "/api/projects", "/api/settings", "/api/docs", "/openapi.json"):
        r = p.get(path)
        assert r.status_code == 401 and r.json()["code"] == "auth_required", path
    assert p.get("/").status_code in (200, 503)  # the UI shell loads, so the login screen can show
    st = p.get("/api/auth/status").json()
    assert st["required"] and not st["authenticated"] and st["kind"] == "pin"

    r = p.post("/api/auth/login", json={"secret": "0000"})
    assert r.status_code == 401 and r.json()["code"] == "wrong"
    r = p.post("/api/auth/login", json={"secret": "1234"})
    assert r.status_code == 200 and r.json()["authenticated"]
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert p.get("/api/meta").status_code == 200

    p.post("/api/auth/logout")
    assert p.get("/api/meta").status_code == 401


def test_login_is_rate_limited():
    lanauth.set_secret("1234")
    p = phone()
    codes = [p.post("/api/auth/login", json={"secret": "9999"}).status_code for _ in range(5)]
    assert codes == [401] * 5
    r = p.post("/api/auth/login", json={"secret": "1234"})  # even the right PIN waits now
    assert r.status_code == 429 and r.json()["retry_after"] > 0 and "retry-after" in r.headers


def test_only_this_computer_can_change_the_pin():
    p = phone()
    assert p.put("/api/auth/secret", json={"secret": "1234"}).status_code == 403
    r = local.put("/api/auth/secret", json={"secret": "1234"})
    assert r.status_code == 200 and r.json()["enabled"]
    assert local.put("/api/auth/secret", json={"secret": "1"}).status_code == 400
    lanauth.limiter = lanauth.Limiter()
    p.post("/api/auth/login", json={"secret": "1234"})
    assert p.delete("/api/auth/secret").status_code == 403
    assert local.delete("/api/auth/secret").json()["enabled"] is False


def test_settings_never_expose_the_hash():
    lanauth.set_secret("1234")
    text = local.get("/api/settings").text + local.get("/api/meta").text
    assert "scrypt$" not in text
