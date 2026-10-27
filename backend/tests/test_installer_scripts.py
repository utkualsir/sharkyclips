"""Static checks of the macOS shell scripts (they can't run on the Windows / Linux CI)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [ROOT / "install.sh", ROOT / "installer" / "macos" / "uninstall.sh",
           ROOT / "installer" / "macos" / "SharkyClips.command"]
# Environment variables that may be unset on a normal Mac.
OPTIONAL_ENV = ("SHARKYCLIPS_HOME", "HF_HOME", "LANG")


def test_optional_env_vars_have_defaults_under_set_u():
    """`set -u` aborts the script on an unset variable: optional ones need ${VAR:-...}."""
    for script in SCRIPTS:
        text = script.read_text(encoding="utf-8")
        if "set -u" not in text:
            continue
        for var in OPTIONAL_ENV:
            bare = re.findall(rf"\$(?:{var}\b|\{{{var}\}})", text)
            assert not bare, f"{script.name}: ${var} without a default under set -u"


def test_launcher_matches_the_uninstallers_process_pattern():
    """The uninstaller stops SharkyClips with `pkill -f "$APP_DIR/.venv/bin/python"`, so the
    launcher must start Python by its absolute path."""
    launcher = (ROOT / "installer" / "macos" / "SharkyClips.command").read_text(encoding="utf-8")
    uninstall = (ROOT / "installer" / "macos" / "uninstall.sh").read_text(encoding="utf-8")
    assert 'pkill -f "$APP_DIR/.venv/bin/python"' in uninstall
    assert '"$APP_DIR/.venv/bin/python" "$APP_DIR/backend/cli.py" launch' in launcher


def test_launcher_finds_homebrew_tools():
    launcher = (ROOT / "installer" / "macos" / "SharkyClips.command").read_text(encoding="utf-8")
    assert "/opt/homebrew/bin/brew" in launcher and "shellenv" in launcher


def test_scripts_use_lf_line_endings():
    for script in SCRIPTS:
        assert b"\r\n" not in script.read_bytes(), f"{script.name} has CRLF line endings (breaks bash)"
