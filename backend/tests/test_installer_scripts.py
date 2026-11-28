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


def test_every_release_gets_install_sh():
    """Issue #20: the README tells Mac users to download install.sh from the latest release, so
    the tag workflow must attach it, in a job that doesn't wait for the Windows installer."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "**`install.sh`** from the [latest release]" in readme
    flow = (ROOT / ".github" / "workflows" / "installer.yml").read_text(encoding="utf-8")
    assert re.search(r'push:\s*\n\s*tags: \["v\*"\]', flow)
    # the jobs are the 2-space-indented keys under `jobs:`
    jobs = dict(re.findall(r"(?m)^  ([\w-]+):\n((?:(?:    .*)?\n)+)", flow.split("\njobs:\n", 1)[1]))
    job = jobs["macos-script"]
    assert "needs:" not in job and "contents: write" in job
    assert 'gh release upload "v$v" install.sh install.sh.sha256' in job


def test_scripts_use_lf_line_endings():
    for script in SCRIPTS:
        assert b"\r\n" not in script.read_bytes(), f"{script.name} has CRLF line endings (breaks bash)"
