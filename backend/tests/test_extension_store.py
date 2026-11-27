"""1.2.74: the SharkyClips Helper as a store package (Edge Add-ons, Firefox Add-ons) + pairing."""

from __future__ import annotations

import importlib.util
import json
import re
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sharkyclips import assist

ROOT = Path(__file__).resolve().parents[2]
EXT = ROOT / "backend" / "sharkyclips" / "assist_ext"


@pytest.fixture(autouse=True)
def _fresh_pair():
    assist._pair.clear()
    yield
    assist._pair.clear()


def _client():
    from sharkyclips.web.app import app

    return TestClient(app)  # no `with`: startup would install the real governor


# ===================================================================== pairing rules


def test_a_code_works_once_and_gives_the_helper_key():
    code = assist.pair_code(now=1000.0)["code"]
    assert re.fullmatch(r"\d{6}", code)
    assert assist.pair(code, now=1001.0) == assist.token()
    assert assist.pair(code, now=1002.0) is None  # used up


def test_wrong_codes_end_the_code_and_old_codes_expire():
    code = assist.pair_code(now=0.0)["code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(assist.PAIR_TRIES):
        assert assist.pair(wrong, now=1.0) is None
    assert assist.pair(code, now=2.0) is None  # 5 wrong tries: the right one doesn't work any more
    code = assist.pair_code(now=0.0)["code"]
    assert assist.pair(code, now=assist.PAIR_TTL + 1.0) is None  # too late
    code = assist.pair_code(now=0.0)["code"]
    assert assist.pair(f"{code[:3]} {code[3:]}", now=5.0) == assist.token()  # "123 456" as shown
    assert assist.pair("", now=5.0) is None and assist.pair(None, now=5.0) is None


def test_a_new_code_replaces_the_old_one():
    first = assist.pair_code()["code"]
    second = assist.pair_code()["code"]
    if first != second:
        assert assist.pair(first) is None
    assert assist.pair(second) == assist.token() or first == second


# ===================================================================== the doors


def test_pair_endpoint_only_answers_an_extension_origin():
    c = _client()
    code = c.post("/api/assist/pair-code").json()["code"]
    page = c.post("/api/assist/ext/pair", json={"code": code}, headers={"Origin": "https://evil.example"})
    assert page.status_code == 403 and "token" not in page.text
    none = c.post("/api/assist/ext/pair", json={"code": code})  # no Origin at all (curl, a page's no-cors form)
    assert none.status_code == 403
    ok = c.post("/api/assist/ext/pair", json={"code": code, "ua": "Mozilla/5.0 Firefox/140.0"},
                headers={"Origin": "moz-extension://1234-abcd"})
    assert ok.status_code == 200 and ok.json()["token"] == assist.token() and ok.json()["app"] == "sharkyclips"
    again = c.post("/api/assist/ext/pair", json={"code": code}, headers={"Origin": "chrome-extension://abc"})
    assert again.status_code == 403  # once only


def test_other_extension_paths_still_need_the_key():
    c = _client()
    r = c.get("/api/assist/ext/hello", headers={"Origin": "chrome-extension://abc"})
    assert r.status_code == 403
    r = c.get("/api/assist/ext/hello", headers={"X-SharkyClips-Assist": assist.token()})
    assert r.status_code == 200


def test_pair_code_needs_the_ui_token():
    r = _client().post("/api/assist/pair-code", headers={"X-SharkyClips-Token": "wrong"})  # overrides conftest's
    assert r.status_code == 403


def test_firefox_fills_once_the_store_helper_spoke_from_there(monkeypatch):
    monkeypatch.setattr(assist, "seen", lambda key=None: 0.0)
    assert assist.can_fill("firefox") is False
    monkeypatch.setattr(assist, "seen", lambda key=None: 123.0 if key == "firefox" else 0.0)
    assert assist.can_fill("firefox") is True
    assert assist.can_fill("edge") is True and assist.can_fill(None) is False
    from sharkyclips.web import assist_api

    assert assist_api._browser_of("Mozilla/5.0 (Windows NT 10.0; rv:140.0) Gecko/20100101 Firefox/140.0") == "firefox"


# ===================================================================== the packages


def _build(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("build_extension", ROOT / "installer" / "build_extension.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "OUT", tmp_path)
    return mod, mod.build()


def test_store_packages_are_complete_and_hold_no_install_key(tmp_path, monkeypatch):
    mod, paths = _build(tmp_path, monkeypatch)
    names = sorted(p.name for p in paths)
    assert [n.rsplit("-", 1)[1] for n in names] == ["edge.zip", "firefox.zip", "source.zip"]
    locales = {d.name for d in (EXT / "_locales").iterdir()}
    assert locales == {"en", "tr", "es", "pt_BR", "de", "fr", "hu", "ru", "ar", "zh_CN", "ja"}
    for p in paths[:2]:
        with zipfile.ZipFile(p) as z:
            files = set(z.namelist())
            m = json.loads(z.read("manifest.json"))
            assert "config.js" not in files  # an install's key never ships
            for f in (*assist.EXT_FILES, *[f"icons/icon-{n}.png" for n in assist.EXT_ICON_SIZES]):
                assert f in files, f
            assert {f"_locales/{loc}/messages.json" for loc in locales} <= files
            assert m["manifest_version"] == 3 and m["default_locale"] == "en"
            assert m["host_permissions"] == ["http://127.0.0.1/*", "http://localhost/*"]
            assert m["permissions"] == ["storage"] and m["action"]["default_popup"] == "popup.html"
            matches = [x for cs in m["content_scripts"] for x in cs["matches"]]
            assert matches == ["https://www.tiktok.com/*", "https://www.instagram.com/*"]
            if p.name.endswith("firefox.zip"):
                g = m["browser_specific_settings"]["gecko"]
                assert g["id"] == assist.GECKO_ID and g["data_collection_permissions"] == {"required": ["none"]}
                assert m["background"] == {"scripts": ["bg.js"]}
            else:
                assert m["background"] == {"service_worker": "bg.js"} and "browser_specific_settings" not in m
    assert mod.check(mod.files_for("edge")) == []


def test_locale_texts_fit_the_store_limits():
    for d in (EXT / "_locales").iterdir():
        msgs = json.loads((d / "messages.json").read_text(encoding="utf-8"))
        assert len(msgs["name"]["message"]) <= 45 and len(msgs["description"]["message"]) <= 132, d.name
        assert set(msgs) == set(json.loads((EXT / "_locales" / "en" / "messages.json").read_text(encoding="utf-8")))


def test_popup_has_no_inline_script_and_store_copy_reads_its_key():
    html = (EXT / "popup.html").read_text(encoding="utf-8")
    assert re.search(r"<script(?![^>]*\bsrc=)", html) is None  # MV3 pages allow no inline script
    bg = (EXT / "bg.js").read_text(encoding="utf-8")
    assert 'typeof importScripts === "function"' in bg  # Firefox background scripts have no importScripts
    assert "chrome.storage.local" in bg and "/api/assist/ext/pair" in bg


def test_two_copies_never_fill_one_page_twice():
    common = (EXT / "common.js").read_text(encoding="utf-8")
    assert "data-sharkyclips-helper" in common and "async function claim()" in common
    for name in ("tiktok.js", "instagram.js"):
        text = (EXT / name).read_text(encoding="utf-8")
        claim = text.index("SCX.claim()")
        assert claim < text.index('SCX.send({ type: "task"'), name


def test_unpacked_copy_gets_popup_icons_and_locales(tmp_path, monkeypatch):
    monkeypatch.setattr(assist, "ext_dir", lambda: tmp_path / "ext")
    d = assist.write_extension("http://127.0.0.1:8000")
    for f in (*assist.EXT_FILES, "manifest.json", "config.js", "icons/icon-48.png", "_locales/tr/messages.json"):
        assert (d / f).is_file(), f
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert m["action"]["default_popup"] == "popup.html"
    # Chromium refuses an extension with _locales/ but no default_locale (1.2.74: the Helper didn't load)
    assert (d / "_locales").is_dir() and m["default_locale"] == "en"
    assert (d / "_locales" / m["default_locale"] / "messages.json").is_file()
