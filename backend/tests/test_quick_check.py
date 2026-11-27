"""1.2.75 test speed (docs/test-speed.md): the local quick check and the CI split stay in step."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import conftest

ROOT = Path(__file__).resolve().parents[2]


def _qc():
    spec = importlib.util.spec_from_file_location("quick_check", ROOT / "scripts" / "quick-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_serial_lists_match_and_exist():
    assert _qc().SERIAL == conftest.SERIAL_FILES
    for name in conftest.SERIAL_FILES:
        assert (ROOT / "backend" / "tests" / name).is_file(), name


def test_changed_module_picks_its_tests():
    qc = _qc()
    picked = qc.tests_for(["backend/sharkyclips/poolcounter.py", "frontend/src/previewMath.ts", "VERSION"])
    assert "backend/tests/test_upload_stats.py" in picked
    assert "backend/tests/test_preview_math.py" in picked and "backend/tests/test_updates_page.py" in picked
    assert qc.tests_for(["docs/phase-d5.md"]) == []


def test_ci_runs_the_split_and_the_layout_shards():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert ci.count('pytest -n auto --dist loadfile -m "not serial"') == 2 and ci.count("pytest -m serial") == 2
    assert "shard: [1, 2, 3, 4]" in ci and "LAYOUT_SHARD=${{ matrix.shard }}/4" in ci
    assert "LAYOUT_SHARD" in (ROOT / "frontend" / "scripts" / "layout-check.mjs").read_text(encoding="utf-8")
