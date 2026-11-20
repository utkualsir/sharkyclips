"""1.2.58: the Updates page (release history) and the CHANGELOG.md rules it depends on.

- every version: a short simple-English summary and details grouped as New / Improved / Fixed
- every version: a summary in all 11 UI languages; Turkish details grouped too
- the English text has no file names, code or developer jargon
- /api/releases (newest first, UI language, English fallback) and the "New" badge on the menu
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sharkyclips import __version__, config, welcome

ROOT = Path(__file__).resolve().parents[2]
LANGS = ("en", "tr", "es", "pt", "ru", "de", "fr", "ar", "zh", "ja", "hu")


def _semver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def test_every_version_has_a_summary_and_groups():
    hist = welcome.release_history("en")
    assert len(hist) >= 60 and hist[0]["version"] == __version__
    assert [_semver(e["version"]) for e in hist] == sorted((_semver(e["version"]) for e in hist), reverse=True)
    for e in hist:
        assert e["date"] and re.match(r"\d{4}-\d{2}-\d{2}$", e["date"]), e["version"]
        s = e["summary"]
        assert 20 <= len(s) <= 260, (e["version"], s)
        assert len(re.findall(r"[.!?](\s|$)", s)) <= 2, (e["version"], s)  # 1-2 sentences
        kinds = [g["kind"] for g in e["groups"]]
        assert kinds and set(kinds) <= {"new", "improved", "fixed"}, (e["version"], kinds)


JARGON = re.compile(
    r"`|\b[\w./<>-]+\.(py|tsx?|mjs|json|md|bat|sh|ps1|yml|exe|ico|icns)\b|\bAPI\b|\bCLI\b|\bJSON\b|SHA-256|"
    r"ffmpeg|FFmpeg|Ollama|Whisper|\bLLM\b|VRAM|NVDEC|OAuth|pythonw|DPAPI|Thompson|semver|~/\.", re.I)


def test_english_notes_have_no_file_names_or_jargon():
    for e in welcome.release_history("en"):
        text = e["summary"] + "\n" + "\n".join(g["markdown"] for g in e["groups"])
        bad = sorted({m.group(0) for m in JARGON.finditer(text)})
        assert not bad, (e["version"], bad)


@pytest.mark.parametrize("lang", LANGS[1:])
def test_every_version_has_a_translated_summary(lang):
    for e in welcome.release_history(lang):
        assert e["summary_lang"] == lang and e["summary"], (lang, e["version"])


def test_turkish_details_are_grouped():
    for e in welcome.release_history("tr"):
        if e["details_lang"] == "tr":
            assert {g["kind"] for g in e["groups"]} <= {"new", "improved", "fixed"}, e["version"]
    # newest versions: Turkish details for sure
    assert all(e["details_lang"] == "tr" for e in welcome.release_history("tr")[:10])


def test_parse_release_reads_headings_in_every_language():
    md = "Kurz gesagt.\n\n### Neu\n- a\n\n### Verbessert\n- b\n\n### Behoben\n- c\n"
    r = welcome.parse_release(md)
    assert r["summary"] == "Kurz gesagt." and set(r["groups"]) == {"new", "improved", "fixed"}
    tr = welcome.parse_release("Özet.\n\n### İyileştirmeler\n- x\n### Düzeltmeler\n- y")
    assert set(tr["groups"]) == {"improved", "fixed"}
    assert welcome.parse_release("### Something\n- x")["groups"] == {"other": "- x"}


def test_unknown_language_falls_back_to_english(tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text("# C\n\n## [9.9.9] - 2030-01-01\nSimple words.\n\n### New\n- **A** thing\n\n"
                 "<!-- lang:tr -->\n**Türkçe**\n\nBasit.\n", encoding="utf-8")
    [en] = welcome.release_history("en", p)
    assert en["summary"] == "Simple words." and en["groups"] == [{"kind": "new", "markdown": "- **A** thing"}]
    [tr] = welcome.release_history("tr", p)
    assert tr["summary"] == "Basit." and tr["summary_lang"] == "tr"
    assert tr["details_lang"] == "en" and tr["groups"][0]["kind"] == "new"  # no Turkish details: English
    [zh] = welcome.release_history("zh", p)
    assert zh["summary_lang"] == "en" and zh["details_lang"] == "en"


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    (h / "workspace").mkdir(parents=True)
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(h))
    return h


def test_api_and_new_badge(home):
    from sharkyclips.web.app import app

    # an existing user who updated: the badge shows until the page is opened
    (home / "config.json").write_text(json.dumps({"workspace_dir": str(home / "workspace"), "onboarding_done": True,
                                                  "seen_version": "1.2.56", "ui_language": "tr"}), encoding="utf-8")
    with TestClient(app) as c:
        assert c.get("/api/app").json()["updates_new"] is True
        r = c.get("/api/releases?lang=tr").json()
        assert r["current"] == __version__ and r["lang"] == "tr" and r["entries"][0]["version"] == __version__
        assert c.get("/api/releases?lang=xx").json()["lang"] == "en"
        st = c.post("/api/app/updates-seen", json={}).json()
        assert st["updates_new"] is False and config.load()["updates_seen"] == __version__
    # a new user: no badge after the onboarding
    (home / "config.json").write_text(json.dumps({"workspace_dir": str(home / "workspace")}), encoding="utf-8")
    assert welcome.updates_new() is False  # onboarding first
    welcome.finish_onboarding({})
    assert welcome.updates_new() is False


def test_ui_has_the_page_the_menu_item_and_the_about_link():
    src = ROOT / "frontend" / "src"
    app = (src / "App.tsx").read_text(encoding="utf-8")
    assert app.count("<UpdatesNavLink") == 2  # Easy + Pro top bars
    assert 'route.name === "updates" && <Updates />' in app
    assert 'updates: "#/updates"' in (src / "router.ts").read_text(encoding="utf-8")
    assert "href.updates" in (src / "components" / "Licenses.tsx").read_text(encoding="utf-8")  # Settings > About
    page = (src / "pages" / "Updates.tsx").read_text(encoding="utf-8")
    assert "api.updatesSeen" in page and 'type="search"' in page
