"""Safe cleanup for tests: deletes only inside throwaway temp folders (CLAUDE.md, "Safe deletes").

Every delete resolves the target to an absolute path (symlinks / junctions followed), prints it and
refuses it unless it lies strictly INSIDE the system temp folder. The real settings folder
(~/.sharkyclips), the projects workspace, the user's videos and the repo are never valid targets,
even when a test points SHARKYCLIPS_HOME at them by mistake.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


class UnsafeDelete(RuntimeError):
    """A cleanup tried to delete something outside the throwaway temp folders."""


_REAL_RMTREE = shutil.rmtree


def _resolve(path: str | os.PathLike) -> Path:
    raw = os.fspath(path)
    if isinstance(raw, bytes):
        raw = os.fsdecode(raw)
    # Windows long-path forms (pytest's own cleanup uses them): \\?\C:\... and \\?\UNC\server\...
    if raw.startswith("\\\\?\\UNC\\"):
        raw = "\\\\" + raw[8:]
    elif raw.startswith("\\\\?\\"):
        raw = raw[4:]
    return Path(os.path.abspath(raw)).resolve()


def temp_roots() -> list[Path]:
    """The folders whose CONTENTS tests may delete (the folders themselves never)."""
    roots = {_resolve(tempfile.gettempdir())}
    for var in ("TMP", "TEMP", "TMPDIR"):
        if os.environ.get(var):
            roots.add(_resolve(os.environ[var]))
    return sorted(roots)


def _forbidden() -> list[Path]:
    home = Path.home()
    return [_resolve(p) for p in (home / ".sharkyclips", home / ".clipforge", home / "Videos",
                                  home / "Downloads", home / "SharkyClips",
                                  Path(__file__).resolve().parents[2])]


def _inside(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def check_target(path: str | os.PathLike, *, quiet: bool = False) -> Path:
    """Resolve ``path``, print it, and raise UnsafeDelete unless it is strictly inside a temp root.
    Returns the resolved path."""
    target = _resolve(path)
    if not quiet:
        print(f"[safe_delete] target: {target}")
    roots = temp_roots()
    if not any(_inside(target, r) and target != r for r in roots):
        raise UnsafeDelete(f"refusing to delete {target}: not inside a temp folder "
                           f"({', '.join(map(str, roots))})")
    for bad in _forbidden():
        # a temp folder that happens to sit inside one of these (or contain it) is still refused
        if _inside(target, bad) or _inside(bad, target):
            raise UnsafeDelete(f"refusing to delete {target}: protected folder {bad}")
    return target


def safe_rmtree(path: str | os.PathLike, *, missing_ok: bool = True) -> None:
    """shutil.rmtree for tests, limited to temp folders. Errors while deleting are ignored (like
    ignore_errors=True); an unsafe target always raises."""
    target = check_target(path)
    if not target.exists():
        if missing_ok:
            return
        raise FileNotFoundError(target)
    _REAL_RMTREE(target, ignore_errors=True)


def safe_unlink(path: str | os.PathLike, *, missing_ok: bool = True) -> None:
    """Path.unlink for tests, limited to temp folders."""
    check_target(path)
    Path(path).unlink(missing_ok=missing_ok)


def guarded_rmtree(path, *args, **kwargs):
    """Drop-in for shutil.rmtree, installed for the whole test session by conftest.py: anything a
    test (or the code it runs) removes with rmtree must be inside a temp folder."""
    check_target(path, quiet=True)
    return _REAL_RMTREE(path, *args, **kwargs)


guarded_rmtree.avoids_symlink_attacks = getattr(_REAL_RMTREE, "avoids_symlink_attacks", False)  # type: ignore[attr-defined]
