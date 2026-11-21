"""The test cleanup helper refuses anything outside the throwaway temp folders."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from safe_delete import UnsafeDelete, check_target, safe_rmtree, safe_unlink


def test_deletes_inside_temp(tmp_path, capsys):
    d = tmp_path / "junk"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "a.txt").write_text("x")
    safe_rmtree(d)
    assert not d.exists()
    assert str(d.resolve()) in capsys.readouterr().out  # the resolved path is printed first
    f = tmp_path / "b.txt"
    f.write_text("x")
    safe_unlink(f)
    assert not f.exists()


@pytest.mark.parametrize("target", [
    Path.home() / ".sharkyclips",
    Path.home() / "Videos",
    Path.home(),
    Path(__file__).resolve().parents[2],  # the repo
    Path(tempfile.gettempdir()),  # the temp root itself
    Path(tempfile.gettempdir()) / ".." / "not-temp",  # escapes with ..
])
def test_refuses_outside_temp(target):
    with pytest.raises(UnsafeDelete):
        check_target(target)
    with pytest.raises(UnsafeDelete):
        safe_rmtree(target)
    with pytest.raises(UnsafeDelete):
        safe_unlink(target)


def test_shutil_rmtree_is_guarded_during_tests(tmp_path):
    with pytest.raises(UnsafeDelete):
        shutil.rmtree(Path.home() / ".sharkyclips" / "does-not-matter")
    d = tmp_path / "ok"
    d.mkdir()
    shutil.rmtree(d)
    assert not d.exists()


def test_pytest_never_writes_its_cache_into_the_repo():
    """1.2.63 CI: every test passed, then pytest's cache writer tried to rmtree a
    "pytest-cache-files-*" folder in the repo root, the guard refused it and the job failed. The
    cache is switched off, so pytest itself never deletes anything in the repo."""
    from pathlib import Path

    ini = (Path(__file__).resolve().parents[2] / "pytest.ini").read_text(encoding="utf-8")
    addopts = next(line for line in ini.splitlines() if line.startswith("addopts"))
    assert "no:cacheprovider" in addopts
