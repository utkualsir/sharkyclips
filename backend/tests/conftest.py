"""Tests run against a throwaway settings folder and workspace, never the real ones."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_home = Path(tempfile.mkdtemp(prefix="sharkyclips-test-home-"))
(_home / "workspace").mkdir()
(_home / "config.json").write_text(json.dumps({"workspace_dir": str(_home / "workspace"),
                                               "llm_enabled": False}), encoding="utf-8")
os.environ["SHARKYCLIPS_HOME"] = str(_home)
os.environ["SHARKYCLIPS_NO_MIGRATE"] = "1"  # never touch the real shortcuts / ~/.clipforge
os.environ.pop("CLIPFORGE_HOME", None)
os.environ.pop("SHARKYCLIPS_SUPERVISED", None)
