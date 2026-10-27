"""1.2.1: changelog popup, dev banner flag, onboarding, AI results kept on re-runs, descriptions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sharkyclips import __version__, analyze, config, welcome
from sharkyclips.highlights.pipeline import carry_over_ai

CHANGELOG = """# Changelog

## [9.9.9] - 2030-01-02

Intro.

### Added
- **Thing** one

<!-- lang:tr -->
**Türkçe**

### Eklendi
- **Şey** bir

<details><summary>Deutsch</summary>

<!-- lang:de -->
- Neu

</details>

## [9.9.8] - 2030-01-01

- old
"""


def test_changelog_entry_per_language(tmp_path):
    p = tmp_path / "CHANGELOG.md"
    p.write_text(CHANGELOG, encoding="utf-8")
    en = welcome.changelog_entry("9.9.9", "en", p)
    assert en["date"] == "2030-01-02" and en["lang"] == "en" and "**Thing** one" in en["markdown"]
    assert "Eklendi" not in en["markdown"]
    tr = welcome.changelog_entry("9.9.9", "tr", p)
    assert tr["lang"] == "tr" and tr["markdown"].startswith("### Eklendi")  # "**Türkçe**" label dropped
    assert "details" not in tr["markdown"] and "Deutsch" not in tr["markdown"]
    assert welcome.changelog_entry("9.9.9", "de", p)["markdown"] == "- Neu"
    assert welcome.changelog_entry("9.9.9", "zh", p)["lang"] == "en"  # fallback
    assert welcome.changelog_entry("9.9.8", "tr", p)["markdown"] == "- old"
    assert welcome.changelog_entry("1.0.0", "en", p) is None


def test_this_version_has_a_changelog_entry_in_every_language():
    for lang in ("en", "tr", "de", "hu", "ru", "ar", "zh"):
        entry = welcome.changelog_entry(__version__, lang)
        assert entry and entry["lang"] == lang and len(entry["markdown"]) > 100, lang


def test_dev_flag_fresh_and_stale():
    path = welcome.dev_flag_path()
    path.write_text(json.dumps({"started_at": datetime.now(timezone.utc).isoformat(), "task": "x"}), encoding="utf-8")
    try:
        st = welcome.app_state()
        assert st["dev"]["task"] == "x" and not st["dev"]["stale"] and st["dev_stale"] is None
        old = datetime.now(timezone.utc) - timedelta(hours=13)
        path.write_text(json.dumps({"started_at": old.isoformat().replace("+00:00", "Z")}), encoding="utf-8")
        st = welcome.app_state()
        assert st["dev"] is None and st["dev_stale"]["stale"]
    finally:
        welcome.clear_dev_flag()
    assert welcome.app_state()["dev"] is None


def test_onboarding_then_whats_new():
    cfg = config.load()
    try:
        config.update(onboarding_done=False, seen_version=None)
        st = welcome.app_state()
        assert st["onboarding"] and st["whats_new"] is None  # a new user isn't shown "What's new"
        welcome.finish_onboarding({"ui_language": "en", "content_types": ["study", "bogus"],
                                   "performance_mode": "balanced"})
        c = config.load()
        assert c["content_types"] == ["study"] and c["default_mode"] == "study"
        assert c["performance_mode"] == "balanced" and c["seen_version"] == __version__
        assert welcome.app_state()["onboarding"] is False and welcome.app_state()["whats_new"] is None
        config.update(seen_version="1.0.0")  # an update happened
        assert welcome.app_state()["whats_new"] == __version__
        welcome.mark_seen()
        assert welcome.app_state()["whats_new"] is None
    finally:
        config.save(cfg)


def test_app_api():
    import pytest

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    r = client.get("/api/app")
    assert r.status_code == 200 and r.json()["version"] == __version__
    assert client.get(f"/api/changelog/{__version__}?lang=tr").json()["lang"] == "tr"
    assert client.get("/api/changelog/0.0.1").status_code == 404


def _cand(rank, start, end, publish=None, llm=None):
    c = {"rank": rank, "id": f"c{rank:02d}", "start": start, "end": end, "duration": end - start, "text": "new"}
    if publish:
        c["publish"] = publish
    if llm:
        c["llm"] = llm
    return c


def test_rerun_keeps_ai_results_for_unchanged_cuts(tmp_path):
    path = tmp_path / "highlights.json"
    old = {"mode": "gaming", "analysis": {"language": "tr"}, "candidates": [
        _cand(1, 102.0, 128.0, {"available": True, "titles": ["T"]},
              {"original": {"start": 100.0, "end": 125.0}, "what_happens": "w"}),
        _cand(2, 300.0, 320.0, {"available": True, "titles": ["U"]}),
    ]}
    old["candidates"][0]["translations"] = {"en": []}
    path.write_text(json.dumps(old), encoding="utf-8")
    new = {"mode": "gaming", "candidates": [_cand(1, 100.0, 125.0), _cand(2, 500.0, 520.0)]}
    assert carry_over_ai(path, new) == 1
    a, b = new["candidates"]
    assert a["publish"]["titles"] == ["T"] and a["llm"]["what_happens"] == "w" and "translations" in a
    assert (a["start"], a["end"]) == (102.0, 128.0)  # the AI-refined cut comes along
    assert "publish" not in b and new["analysis"] == {"language": "tr"}
    other_mode = {"mode": "study", "candidates": [_cand(1, 100.0, 125.0)]}
    assert carry_over_ai(path, other_mode) == 0


def test_description_finishing_and_hashtags():
    tags = analyze.clean_hashtags(["#SharkyStreamer", "fps", "#FPS"], "Delta Force", exclude=["sharky streamer"])
    assert tags == ["#shorts", "#DeltaForce", "#fps"]
    out = analyze.finish_description("“Bu klipte üç kişiyi indirdim #wow 🔥 . Sizce nasıl ?”", "tr", None, tags)
    assert out == "Bu klipte üç kişiyi indirdim. Sizce nasıl?\n\n#shorts #DeltaForce #fps"
    soft = analyze._description_soft_checker("tr", ["sharky streamer"])
    assert soft({"description": "Sharky Streamer burada düşmektedir."})  # name + news style
    assert soft({"description": "Lobiye daldım, üç kişiyi indirdim."}) == []
    hard = analyze._description_checker("en")
    assert hard({"description": "One sentence only."})
    assert hard({"description": "I went in. I won. #gg"})
    assert hard({"description": "I went in alone. Three down in five seconds."}) == []
