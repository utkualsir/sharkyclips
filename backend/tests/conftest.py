"""Tests run against a throwaway settings folder and workspace, never the real ones."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_home = Path(tempfile.mkdtemp(prefix="clipforge-test-home-"))
(_home / "workspace").mkdir()
(_home / "config.json").write_text(json.dumps({"workspace_dir": str(_home / "workspace"),
                                               "llm_enabled": False}), encoding="utf-8")
os.environ["CLIPFORGE_HOME"] = str(_home)
os.environ.pop("CLIPFORGE_SUPERVISED", None)
