"""1.2.68 "Did I already upload this?": every source video and what was shared from it.

<settings>/history/history.json (kept when a project is deleted or its files are freed):

  sources  {fingerprint: {"name", "size", "title", "game", "first_seen", "projects": [ids]}}
  posts    [{"key", "at", "fingerprint", "project_id", "project_title", "clip_id", "title", "game",
             "platform", "url", "video_id", "manual", "private"}]   (one per clip per platform)

Fingerprint = SHA-256 of the file size plus three 1 MiB samples (start, middle, end): the same
recording gives the same fingerprint under any name or folder, and reading 3 MiB of a 5 GB video
takes milliseconds. The fingerprint of a project's source is cached in its meta ("source_fp").

Projects made before 1.2.68 are added once from their upload records (backfill).
"""

from __future__ import annotations

import hashlib
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .project import read_json, write_json_atomic

VERSION = 1
SAMPLE = 1024 * 1024
MAX_POSTS = 20_000
PLATFORM_NAMES = {"youtube": "YouTube", "tiktok": "TikTok", "reels": "Instagram"}
_lock = threading.RLock()


def path() -> Path:
    return config.config_dir() / "history" / "history.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict:
    p = path()
    try:
        data = read_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", VERSION)
    if not isinstance(data.get("sources"), dict):
        data["sources"] = {}
    if not isinstance(data.get("posts"), list):
        data["posts"] = []
    if not isinstance(data.get("backfilled"), list):
        data["backfilled"] = []
    return data


def _save(data: dict) -> None:
    data["posts"] = data["posts"][-MAX_POSTS:]
    write_json_atomic(path(), data)


# ===================================================================== fingerprints


def fingerprint(file: Path) -> str:
    size = file.stat().st_size
    h = hashlib.sha256(str(size).encode())
    with open(file, "rb") as f:
        for at in sorted({0, max(0, size // 2 - SAMPLE // 2), max(0, size - SAMPLE)}):
            f.seek(at)
            h.update(f.read(SAMPLE))
    return "v1:" + h.hexdigest()[:40]


def _game(project) -> str | None:
    try:
        from .titles import banks

        g = banks.project_game(project)
        return g.get("name") or None
    except Exception:  # noqa: BLE001 - no game known
        return None


def project_fp(project) -> str | None:
    """The source fingerprint of a project (cached in its meta; None: no source file left)."""
    meta = project.load_meta()
    if meta.get("source_fp"):
        return str(meta["source_fp"])
    src = project.source_path
    if src is None or not src.is_file():
        return None
    try:
        fp = fingerprint(src)
    except OSError:
        return None
    try:
        m = project.load_meta()
        if m:
            project.save_meta({**m, "source_fp": fp})
    except Exception:  # noqa: BLE001 - read-only meta: compute it again next time
        pass
    return fp


def note_source(project) -> str | None:
    fp = project_fp(project)
    if not fp:
        return None
    with _lock:
        data = load()
        meta = project.load_meta()
        src = data["sources"].get(fp) or {"first_seen": _now_iso(), "projects": []}
        src.update(name=str(((meta.get("source") or {}).get("value") or "")).replace("\\", "/").rsplit("/", 1)[-1][:200]
                   or src.get("name"), size=meta.get("source_size_bytes") or src.get("size"),
                   title=meta.get("title") or src.get("title"), game=_game(project) or src.get("game"))
        if project.id not in src["projects"]:
            src["projects"].append(project.id)
        data["sources"][fp] = src
        _save(data)
    return fp


# ===================================================================== posts


def _key(project_id: str, cid: str, platform: str) -> str:
    return f"{project_id}:{cid}:{platform}"


def note_post(project, cid: str, platform: str, *, url: str | None = None, title: str | None = None,
              video_id: str | None = None, manual: bool = False, private: bool = False,
              at: str | None = None) -> dict:
    """Remember one shared post (the same clip on the same platform is one row, updated)."""
    fp = None
    try:
        fp = note_source(project)
    except Exception:  # noqa: BLE001 - no fingerprint: the post is still remembered
        fp = (project.load_meta() or {}).get("source_fp")
    meta = project.load_meta()
    if title is None:
        title = _clip_title(project, cid)
    row = {"key": _key(project.id, cid, platform), "at": at or _now_iso(), "fingerprint": fp,
           "project_id": project.id, "project_title": meta.get("title") or project.id, "clip_id": cid,
           "title": (title or cid)[:200], "game": _game(project), "platform": platform, "url": url,
           "video_id": video_id, "manual": bool(manual), "private": bool(private)}
    with _lock:
        data = load()
        old = next((p for p in data["posts"] if p.get("key") == row["key"]), None)
        if old is not None:
            keep_at = old.get("at")
            old.update({k: v for k, v in row.items() if v is not None})
            old["at"] = keep_at or row["at"]
            row = old
        else:
            data["posts"].append(row)
        _save(data)
    return row


def _clip_title(project, cid: str) -> str | None:
    try:
        from .web import state

        hl = state.load_highlights(project) or {}
        c = next((x for x in hl.get("candidates") or [] if x.get("id") == cid), None) or {}
        return ((c.get("publish") or {}).get("titles") or [None])[0] or (c.get("text") or "")[:90] or None
    except Exception:  # noqa: BLE001
        return None


def forget_post(project_id: str, cid: str, platform: str) -> None:
    """A post deleted on the platform through SharkyClips (or a test post): out of the history."""
    with _lock:
        data = load()
        k = _key(project_id, cid, platform)
        data["posts"] = [p for p in data["posts"] if p.get("key") != k]
        _save(data)


# ===================================================================== questions


def summary(posts: list[dict]) -> dict:
    by: dict[str, int] = {}
    for p in posts:
        by[p["platform"]] = by.get(p["platform"], 0) + 1
    ats = sorted(p.get("at") or "" for p in posts)
    return {"count": len(posts), "by_platform": by, "first_at": ats[0] if ats else None,
            "last_at": ats[-1] if ats else None, "clips": len({(p["project_id"], p["clip_id"]) for p in posts})}


def for_project(project) -> dict:
    """What was shared before from this project's source video, in OTHER projects (the import
    warning) and in this one."""
    fp = project_fp(project)
    data = load()
    mine = [p for p in data["posts"] if p.get("project_id") == project.id]
    other = [p for p in data["posts"] if fp and p.get("fingerprint") == fp and p.get("project_id") != project.id]
    src = data["sources"].get(fp) if fp else None
    return {"fingerprint": fp, "before": summary(other) if other else None,
            "before_projects": sorted({p.get("project_title") or p["project_id"] for p in other}),
            "here": summary(mine), "source": src}


def search(q: str = "", platform: str | None = None, limit: int = 500) -> dict:
    data = load()
    rows = list(data["posts"])
    if platform:
        rows = [r for r in rows if r.get("platform") == platform]
    words = [w for w in (q or "").casefold().split() if w]
    if words:
        def hay(r: dict) -> str:
            return " ".join(str(r.get(k) or "") for k in ("title", "game", "project_title", "url", "at")).casefold() \
                + " " + PLATFORM_NAMES.get(r.get("platform") or "", "").casefold()

        rows = [r for r in rows if all(w in hay(r) for w in words)]
    rows.sort(key=lambda r: r.get("at") or "", reverse=True)
    return {"rows": rows[:max(1, min(5000, limit))], "total": len(rows), "all": len(data["posts"])}


# ===================================================================== backfill (projects before 1.2.68)


def backfill(projects) -> int:
    """Add the posts of projects made before 1.2.68 once (YouTube uploads + TikTok / Instagram posts)."""
    from . import platforms as PF
    from .web import state

    done = set(load()["backfilled"])
    n = 0
    for project in projects:
        if project.id in done:
            continue
        try:
            ups = state.load_uploads(project) or {}
            for cid, entries in ups.items():
                for e in entries or []:
                    if e.get("video_id"):
                        note_post(project, cid, "youtube", url=e.get("url"), title=e.get("title"),
                                  video_id=e.get("video_id"), at=e.get("uploaded_at"),
                                  private=e.get("privacy") == "private" and not e.get("publish_at"))
                        n += 1
            for cid, plats in (PF.records(project) or {}).items():
                for p in ("tiktok", "reels"):
                    r = (plats or {}).get(p) or {}
                    if r.get("status") == "published":
                        note_post(project, cid, p, url=r.get("url"), manual=bool(r.get("manual")),
                                  at=r.get("posted_at") or _ts(r.get("at")))
                        n += 1
            note_source(project)
        except Exception:  # noqa: BLE001 - one broken project never stops the rest
            continue
        with _lock:
            data = load()
            if project.id not in data["backfilled"]:
                data["backfilled"].append(project.id)
                _save(data)
    return n


def _ts(v) -> str | None:
    try:
        return datetime.fromtimestamp(float(v), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return None


def wait_free() -> None:  # tests: nothing async here, kept for symmetry with other stores
    time.sleep(0)
