"""ClipForge -> SharkyClips: the old settings folder moves over, nothing is lost or overwritten."""

from __future__ import annotations

import json

from sharkyclips import config, migrate


def _old_home(tmp_path):
    old = tmp_path / ".clipforge"
    (old / "fonts").mkdir(parents=True)
    (old / "fonts" / "InstrumentSerif.ttf").write_bytes(b"font")
    (old / "config.json").write_text(json.dumps({
        "ui_language": "tr", "glossary": ["Delta Force"], "workspace_dir": str(old / "ws"),
        "launcher_version": 2}), encoding="utf-8")
    (old / "title_feedback.json").write_text('{"votes": {"x": 1}}', encoding="utf-8")
    (old / "calibration.json").write_text('{"entries": []}', encoding="utf-8")
    return old


def test_moves_old_settings_and_rewrites_paths(tmp_path, monkeypatch):
    old, new = _old_home(tmp_path), tmp_path / ".sharkyclips"
    new.mkdir()
    (new / "dev_in_progress.json").write_text("{}", encoding="utf-8")  # created before the migration
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(new))
    monkeypatch.setenv("CLIPFORGE_HOME", str(old))
    info = migrate.migrate_home()
    assert info and info["old_folder_removed"]
    assert not old.exists()
    cfg = json.loads((new / "config.json").read_text(encoding="utf-8"))
    assert cfg["ui_language"] == "tr" and cfg["glossary"] == ["Delta Force"]
    assert cfg["workspace_dir"] == str(new / "ws")
    assert (new / "fonts" / "InstrumentSerif.ttf").read_bytes() == b"font"
    assert json.loads((new / "title_feedback.json").read_text(encoding="utf-8"))["votes"] == {"x": 1}
    assert (new / "calibration.json").is_file() and (new / "dev_in_progress.json").is_file()
    assert migrate.migrate_home() is None  # only once


def test_existing_files_in_new_folder_are_kept(tmp_path, monkeypatch):
    old, new = _old_home(tmp_path), tmp_path / ".sharkyclips"
    (new / "fonts").mkdir(parents=True)
    (new / "fonts" / "InstrumentSerif.ttf").write_bytes(b"newer")
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(new))
    monkeypatch.setenv("CLIPFORGE_HOME", str(old))
    migrate.migrate_home()
    assert (new / "fonts" / "InstrumentSerif.ttf").read_bytes() == b"newer"
    assert (old / "fonts" / "InstrumentSerif.ttf").is_file()  # left where it was, not lost
    assert (old / "MOVED_TO_SHARKYCLIPS.txt").is_file()


def test_never_touches_real_home_when_custom_home_is_set(tmp_path, monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(tmp_path / "x"))
    monkeypatch.delenv("CLIPFORGE_HOME", raising=False)
    assert migrate.old_home() is None and migrate.migrate_home() is None


def test_old_env_var_still_works(tmp_path, monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_HOME", raising=False)
    monkeypatch.setenv("CLIPFORGE_HOME", str(tmp_path / "legacy"))
    assert config.config_dir() == tmp_path / "legacy"
    assert migrate.old_home() is None  # nothing to move: the old folder stays in use


def test_cleanup_old_package(tmp_path):
    cache = tmp_path / "backend" / "clipforge" / "web" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "app.cpython-312.pyc").write_bytes(b"x")
    assert migrate.cleanup_old_package(tmp_path)
    assert not (tmp_path / "backend" / "clipforge").exists()
    (tmp_path / "backend" / "clipforge").mkdir()
    (tmp_path / "backend" / "clipforge" / "mine.py").write_text("x", encoding="utf-8")
    assert not migrate.cleanup_old_package(tmp_path)
