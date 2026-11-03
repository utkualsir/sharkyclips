from __future__ import annotations

import pytest

from sharkyclips import __version__, config, languages
from sharkyclips.chat import parse_file
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import make_project_id, slugify
from sharkyclips.textutil import mmss
from sharkyclips.titles.lexicon import fix_tr_question_particle, strip_emoji


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


def test_languages_registry():
    assert {"tr", "en", "ru", "hu", "de", "ar", "zh"} <= set(languages.codes())
    assert languages.is_rtl("ar") and not languages.is_rtl("tr")
    with pytest.raises(SharkyClipsError):
        languages.require("xx")


def test_config_uses_test_home(tmp_path):
    assert "sharkyclips-test-home" in str(config.config_dir())
    cfg = config.update(default_mode="study")
    assert cfg["default_mode"] == "study"
    assert config.get("default_mode") == "study"
    config.update(default_mode="gaming")


def test_slugify_turkish_and_ids():
    assert slugify("Toplam 55 Kill, Lobiyi Tek Başıma Sildim!") == "toplam-55-kill-lobiyi-tek-basima-sildim"
    assert slugify("!!!") == "video"
    a = make_project_id("Same title", "https://example.com/1")
    assert a == make_project_id("Same title", "https://example.com/1")
    assert a != make_project_id("Same title", "https://example.com/2")


def test_mmss():
    assert mmss(65) == "1:05"


def test_turkish_question_particle_harmony():
    fixed, changes = fix_tr_question_particle("pompalı mi bu")
    assert fixed == "pompalı mı bu"
    assert changes == [("mi", "mı")]


def test_strip_emoji():
    assert strip_emoji("GG 🔥").strip() == "GG"


def test_chat_text_log(tmp_path):
    log = tmp_path / "chat.txt"
    log.write_text("[0:00:05] ali: KEKW\nnot a chat line\n[1:02:03.5] veli: ahahah\n", encoding="utf-8")
    source, rows = parse_file(log)
    assert source == "text-file"
    assert rows == [(5, "KEKW", "ali"), (3723.5, "ahahah", "veli")]


def test_chat_unknown_json(tmp_path):
    bad = tmp_path / "chat.json"
    bad.write_text('{"something": 1}', encoding="utf-8")
    with pytest.raises(SharkyClipsError):
        parse_file(bad)


def test_ai_boundaries_never_leave_the_allowed_range():
    """The AI's start shift with no word nearby must not move a clip before 0 s (1.2.17 fix)."""
    from sharkyclips.analyze import snap_boundaries

    tr = {"segments": [{"start": 8.0, "end": 9.0, "words": [{"start": 8.0, "end": 9.0, "word": " hi"}]}]}
    s, e = snap_boundaries(tr, -1.5, 30.0, 0.0, 40.0, 5.0, 60.0)
    assert s == 0.0 and e == 30.0
    s, e = snap_boundaries(tr, 10.0, 55.0, 2.0, 40.0, 5.0, 60.0)
    assert 2.0 <= s and e <= 40.0
