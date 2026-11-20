"""Phase A (1.2.58): English is the default for NEW users; a language someone already chose stays.

- a fresh settings folder starts in English (config, /api/settings, the splash page)
- an existing config with another language keeps it: loading, saving other settings, skipping
  the onboarding and the What's new / Updates "seen" calls never reset it
- the UI falls back to English (i18n DEFAULT) and shows the language switcher in both top bars
  and on the Easy home screen
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sharkyclips import config, languages, welcome

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    (h / "workspace").mkdir()
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(h))
    return h


def _write(home: Path, data: dict) -> None:
    (home / "config.json").write_text(json.dumps({"workspace_dir": str(home / "workspace"), **data}), encoding="utf-8")


def test_new_user_gets_english(home):
    assert languages.DEFAULT_UI_LANGUAGE == "en"
    assert config.load()["ui_language"] == "en"  # no config.json at all
    _write(home, {})  # a config without the key (only the workspace)
    assert config.load()["ui_language"] == "en"
    from sharkyclips.web.app import app

    with TestClient(app) as c:
        assert c.get("/api/settings").json()["ui_language"] == "en"


def test_existing_choice_is_kept(home):
    _write(home, {"ui_language": "tr", "onboarding_done": True, "seen_version": "1.2.56"})
    assert config.load()["ui_language"] == "tr"
    config.update(performance_mode="balanced")
    assert config.load()["ui_language"] == "tr"
    welcome.finish_onboarding({})  # "Skip" sends nothing: the language stays
    welcome.mark_seen()
    welcome.mark_updates_seen()
    assert config.load()["ui_language"] == "tr"
    from sharkyclips.web.app import app

    with TestClient(app) as c:
        assert c.get("/api/settings").json()["ui_language"] == "tr"
        c.post("/api/app/whats-new-seen", json={})
        c.post("/api/app/updates-seen", json={})
        assert c.get("/api/settings").json()["ui_language"] == "tr"


def test_splash_follows_the_config(home):
    out = welcome.write_splash("http://127.0.0.1:8000/")
    assert out is not None and '"en"' in out.read_text(encoding="utf-8")
    _write(home, {"ui_language": "tr"})
    out = welcome.write_splash("http://127.0.0.1:8000/")
    assert '"tr"' in out.read_text(encoding="utf-8")


def test_ui_defaults_to_english_and_shows_the_switcher():
    i18n = (SRC / "i18n" / "index.tsx").read_text(encoding="utf-8")
    assert re.search(r'const DEFAULT = "en";', i18n)
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    # both top bars (Easy + Pro) carry the switcher
    assert app.count("<LanguageSwitcher />") >= 2
    assert "<LanguageSwitcher big />" in (SRC / "pages" / "EasyHome.tsx").read_text(encoding="utf-8")
    assert "<LanguageSwitcher" in (SRC / "pages" / "Library.tsx").read_text(encoding="utf-8")
    # the server's choice wins unless this browser picked one itself (meta.tsx)
    assert 'localStorage.getItem("cf-lang-set") === "1"' in (SRC / "meta.tsx").read_text(encoding="utf-8")
