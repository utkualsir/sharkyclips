"""More ClipForge -> SharkyClips migration cases: merging, fallbacks, shortcuts, the macOS app."""

from __future__ import annotations

import json
import plistlib

from sharkyclips import migrate


def _old_home(tmp_path):
    old = tmp_path / ".clipforge"
    old.mkdir()
    (old / "config.json").write_text(json.dumps({"ui_language": "tr"}), encoding="utf-8")
    return old


def test_config_in_both_folders_is_merged_old_wins(tmp_path, monkeypatch):
    old, new = _old_home(tmp_path), tmp_path / ".sharkyclips"
    new.mkdir()
    (new / "config.json").write_text(json.dumps({"ui_language": "en", "only_new": 1}), encoding="utf-8")
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(new))
    monkeypatch.setenv("CLIPFORGE_HOME", str(old))
    info = migrate.migrate_home()
    cfg = json.loads((new / "config.json").read_text(encoding="utf-8"))
    assert cfg["ui_language"] == "tr" and cfg["only_new"] == 1
    assert "config.json (merged)" in info["moved"]
    assert (new / migrate.MARKER).is_file()


def test_old_log_is_renamed(tmp_path, monkeypatch):
    old, new = _old_home(tmp_path), tmp_path / ".sharkyclips"
    (old / "logs").mkdir()
    (old / "logs" / "clipforge.log").write_text("old log", encoding="utf-8")
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(new))
    monkeypatch.setenv("CLIPFORGE_HOME", str(old))
    migrate.migrate_home()
    assert (new / "logs" / "clipforge.old.log").read_text(encoding="utf-8") == "old log"


def test_move_falls_back_to_copy(tmp_path, monkeypatch):
    src, dst = tmp_path / "a.json", tmp_path / "out" / "a.json"
    src.write_text("x", encoding="utf-8")
    dst.parent.mkdir()

    def locked(*_a, **_k):
        raise OSError("file in use")

    monkeypatch.setattr(migrate.shutil, "move", locked)
    moved: list[str] = []
    kept: list[str] = []
    migrate._merge_move(src, dst, moved, kept)
    assert dst.read_text(encoding="utf-8") == "x" and moved == ["a.json (copied)"] and kept == []


def test_rewrite_paths_everywhere():
    old, new = "/h/.clipforge", "/h/.sharkyclips"
    data = {"a": "/h/.clipforge/ws", "b": ["x /h/.clipforge/music/y.mp3"], "c": 3, "d": "/elsewhere/.clipforge"}
    out = migrate._rewrite_paths(data, old, new)
    assert out == {"a": "/h/.sharkyclips/ws", "b": ["x /h/.sharkyclips/music/y.mp3"], "c": 3,
                   "d": "/elsewhere/.clipforge"}


def test_run_all_is_off_in_tests(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_NO_MIGRATE", "1")
    assert migrate.run_all() == {}


def test_run_all_reports_failures_without_raising(monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_NO_MIGRATE", raising=False)

    def boom():
        raise RuntimeError("disk")

    monkeypatch.setattr(migrate, "migrate_home", boom)
    for name in ("rebrand_windows", "rebrand_macos", "cleanup_old_package"):
        monkeypatch.setattr(migrate, name, lambda *a, **k: [])
    assert migrate.run_all() == {"home": {"error": "disk"}}


def _fake_windows_home(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    monkeypatch.setattr(migrate, "_apps_value", lambda name, value: None)


def test_rebrand_windows_does_nothing_without_old_shortcuts(tmp_path, monkeypatch):
    if migrate.os.name != "nt":
        assert migrate.rebrand_windows(tmp_path) == []
        return
    _fake_windows_home(tmp_path, monkeypatch)

    def no_powershell(*_a, **_k):
        raise AssertionError("PowerShell must not start when there is nothing to rename")

    monkeypatch.setattr(migrate.subprocess, "run", no_powershell)
    assert migrate.rebrand_windows(tmp_path, "9.9.9") == []


def test_rebrand_windows_runs_hidden_powershell_for_old_shortcuts(tmp_path, monkeypatch):
    if migrate.os.name != "nt":
        return
    (tmp_path / "Desktop").mkdir()
    (tmp_path / "Desktop" / "ClipForge.lnk").write_bytes(b"lnk")
    _fake_windows_home(tmp_path, monkeypatch)
    seen: dict = {}

    class Done:
        stdout = "shortcut:Desktop\n\napps:renamed\n"

    def fake_run(cmd, **kw):
        seen.update(cmd=cmd, kw=kw)
        return Done()

    monkeypatch.setattr(migrate.subprocess, "run", fake_run)
    assert migrate.rebrand_windows(tmp_path, "9.9.9") == ["shortcut:Desktop", "apps:renamed"]
    assert seen["cmd"][0] == "powershell.exe" and seen["kw"]["env"]["SC_VERSION"] == "9.9.9"
    assert seen["kw"].get("creationflags")  # hidden: CREATE_NO_WINDOW


def test_rebrand_macos_renames_the_app(tmp_path, monkeypatch):
    app = tmp_path / "Applications" / "ClipForge.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    (app / "MacOS" / "ClipForge").write_text("#!/bin/bash\nexec ClipForge\n", encoding="utf-8")
    (app / "Info.plist").write_bytes(plistlib.dumps({"CFBundleName": "ClipForge", "CFBundleExecutable": "ClipForge"}))
    monkeypatch.setattr(migrate.sys, "platform", "darwin")
    monkeypatch.setattr(migrate.Path, "home", classmethod(lambda cls: tmp_path))
    assert migrate.rebrand_macos()
    new = tmp_path / "Applications" / "SharkyClips.app" / "Contents"
    assert not (tmp_path / "Applications" / "ClipForge.app").exists()
    info = plistlib.loads((new / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "SharkyClips" and info["CFBundleIdentifier"].endswith(".sharkyclips")
    assert "SharkyClips" in (new / "MacOS" / "SharkyClips").read_text(encoding="utf-8")
    assert migrate.rebrand_macos() == []  # done once
