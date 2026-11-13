"""Tests never touch the user's real folders: settings, workspace, Downloads, publish queue."""

from __future__ import annotations

from pathlib import Path


def _inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def test_every_output_folder_is_the_throwaway_home():
    from sharkyclips import config, easy, pubqueue

    home = config.config_dir()
    assert not _inside(home, Path.home() / ".sharkyclips") and home != Path.home() / ".sharkyclips"
    for p in (config.workspace_dir(), easy.downloads_root(), pubqueue.root(), pubqueue.queue_root()):
        assert _inside(p, home), p
    assert not _inside(easy.downloads_root(), Path.home() / "Downloads")
    assert not _inside(pubqueue.root(), Path.home() / "SharkyClips")
