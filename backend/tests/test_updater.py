"""The self-update flow against a local "GitHub" (a bare repository in a temp folder)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from sharkyclips import __version__, updater

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def run(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit_version(repo: Path, version: str, message: str) -> None:
    (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
    (repo / "backend").mkdir(exist_ok=True)
    (repo / "backend" / "requirements.txt").write_text("rich\n", encoding="utf-8")
    run(repo, "add", "-A")
    run(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", message)


@pytest.fixture
def repos(tmp_path):
    remote = tmp_path / "remote.git"
    author = tmp_path / "author"
    user = tmp_path / "user"
    run(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    run(tmp_path, "clone", "-q", str(remote), str(author))
    run(author, "checkout", "-q", "-b", "main")
    commit_version(author, __version__, "First release")
    run(author, "push", "-q", "-u", "origin", "main")
    run(tmp_path, "clone", "-q", str(remote), str(user))
    return author, user


def test_parse_version():
    assert updater.parse_version('__version__ = "1.2.3"') == "1.2.3"
    assert updater.parse_version("1.2.1\n") == "1.2.1"
    assert updater.parse_version("nothing") is None
    assert updater.version_tuple("1.10.0") > updater.version_tuple("1.9.9")


def test_not_a_checkout(tmp_path):
    st = updater.status(root=tmp_path)
    assert st["supported"] is False and st["reason"] == "not_git_checkout"
    assert st["current"] == __version__


def test_up_to_date(repos):
    _, user = repos
    st = updater.status(root=user)
    assert st["supported"] and not st["available"] and st["behind"] == 0


def test_update_available_and_apply(repos):
    author, user = repos
    commit_version(author, "9.9.9", "Faster rendering")
    run(author, "push", "-q")
    st = updater.status(root=user)
    assert st["available"] and st["behind"] == 1
    assert st["latest"] == "9.9.9"
    assert st["changes"] == ["Faster rendering"]

    stages = []
    res = updater.apply(stages.append, root=user)
    assert res["changed"] and res["version"] == "9.9.9" and not res["packages_updated"]
    assert stages == ["update_download"]
    assert updater.status(root=user)["available"] is False


def test_apply_refuses_conflicting_local_changes(repos):
    author, user = repos
    commit_version(author, "9.9.9", "New version")
    run(author, "push", "-q")
    (user / "VERSION").write_text("# edited by hand\n", encoding="utf-8")
    updater.status(root=user)
    with pytest.raises(updater.SharkyClipsError):
        updater.apply(root=user)
