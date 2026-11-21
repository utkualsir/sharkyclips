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
