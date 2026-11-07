"""Tests run against a throwaway settings folder and workspace, never the real ones."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_home = Path(tempfile.mkdtemp(prefix="sharkyclips-test-home-"))
(_home / "workspace").mkdir()
(_home / "config.json").write_text(json.dumps({"workspace_dir": str(_home / "workspace"),
                                               "llm_enabled": False}), encoding="utf-8")
os.environ["SHARKYCLIPS_HOME"] = str(_home)
os.environ["SHARKYCLIPS_NO_MIGRATE"] = "1"  # never touch the real shortcuts / ~/.clipforge
os.environ["SHARKYCLIPS_PUBLISH_LOOP"] = "0"  # tests tick the publish scheduler themselves
os.environ["SHARKYCLIPS_LIVE_LOOP"] = "0"  # no watcher / hotkey / chat / Telegram threads in tests
os.environ.pop("SHARKYCLIPS_TG_ENDPOINT", None)
os.environ.pop("SHARKYCLIPS_TWITCH_IRC", None)
os.environ["OBS_HOME"] = str(_home / "no-obs")  # never read the real OBS settings
os.environ["SHARKYCLIPS_NO_KEYCHAIN"] = "1"  # macOS: never touch the real login Keychain
os.environ.pop("SHARKYCLIPS_YT_ENDPOINT", None)
os.environ["SHARKYCLIPS_NO_BROWSER"] = "1"  # "Connect with Google" must not open a real browser
os.environ["SHARKYCLIPS_NO_BLEEP_CHECK"] = "1"  # renders never load Whisper to re-listen to bleeps (tested directly)
# no built-in Google client unless a test sets one (the shipped google_client.json may be filled in)
os.environ["SHARKYCLIPS_SHARED_CLIENT"] = str(_home / "no-shared-client.json")
os.environ.pop("CLIPFORGE_HOME", None)
os.environ.pop("SHARKYCLIPS_SUPERVISED", None)


def pytest_collection_modifyitems(config, items):
    """Skip tests that need ffmpeg when it is not installed (CI installs it, so they run there)."""
    if shutil.which("ffmpeg"):
        return
    skip = pytest.mark.skip(reason="ffmpeg is not installed")
    for item in items:
        if "requires_ffmpeg" in item.keywords:
            item.add_marker(skip)
