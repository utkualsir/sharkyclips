"""Delete + trash (1.2.41).

Deleting never removes anything at once: clips and whole projects move into
<workspace>/_trash/<id>/ (a rename on the same disk, instant) with a trash.json that says what was
where. For 30 days everything comes back with Restore (or the undo toast); after that, or with
"Empty trash", it is deleted for good.

  project   the whole project folder moves (workspace/<pid> -> _trash/<id>/<pid>). The original
            video it was made from stays where it is, unless "delete the original too" is ticked
            (then it moves into the trash as well, and Restore puts it back).
  clips     one or several clips of a project: the candidate (highlights.json, manual.json),
            its accept / reject marks, clips.json and every file of the clip (rendered MP4s,
            covers, thumbnails, exports) move; the YouTube plan, planned TikTok / Instagram posts
            and pending publish-queue posts are taken off (and put back on Restore when their
            time is still ahead).
  cleanup   the "Temizlik" helper: rendered files of rejected clips and old preview folders also
            go to the trash; regenerable caches (frames, tracking, loops) are deleted right away.

Posts on YouTube / Instagram / TikTok are never touched unless "also delete the posts" is ticked
(that can't be undone). TikTok has no delete in its API: those links are returned for doing it
by hand. Jobs of the deleted things are cancelled first (a running render would hold files).

1.2.47:
  keep days   setting "trash_keep_days" (default 30, 0 = deleted for good at once). The expiry is
              deleted_at + the setting, so a change applies to what is in the trash already.
  pending     planned posts that are NOT on the platform yet (Instagram has no scheduling in its
              API: SharkyClips uploads them at their time from the project's files; a YouTube clip
              still being prepared / uploaded). Posts already waiting on the platform (YouTube
              publishAt, TikTok Studio's own schedule, planned by hand in the browser) are not
              touched by a delete at all: they go out by themselves.
  keep posts  deleting a project with pending posts asks: cancel them, or keep them. Kept, the
              project shrinks to a "posts only" rest (meta "posts_only"): its JSON files and the exact
              video of each pending post (pinned in the post's record, "file_fixed"). Everything else
              (stream video, audio, caches, the other clips) goes to the trash. The rest is hidden
              from the project lists, the publish loop posts from it, and after its last post it
              joins its trash item by itself (finish_rests). Restore puts the whole project back.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config
from .errors import SharkyClipsError
from .project import Project, get_project, list_projects, read_json_shared, write_json_atomic

KEEP_DAYS = 30  # the default of the setting "trash_keep_days"
MAX_KEEP_DAYS = 365
DIR = "_trash"
CACHE_DIRS = ("frames", "track", "loop")  # regenerable on demand, cheap to make again
OLD_PREVIEW_DIRS = ("previews",)  # ClipForge-era preview renders nothing reads any more
_lock = threading.RLock()
_purge_at = {"t": 0.0}


# ===================================================================== basics


def root() -> Path:
    return config.workspace_dir() / DIR


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse(v) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def size_of(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.stat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def _inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except (ValueError, OSError):
        return False


def _move(src: Path, dest: Path, seconds: float = 8.0) -> None:
    """A rename where possible (same disk), else copy + delete. Windows: waits out a file that
    a preview player or the indexer holds for a moment."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    end = time.monotonic() + seconds
    delay = 0.05
    while True:
        try:
            os.replace(src, dest)
            return
        except PermissionError:
            if time.monotonic() >= end:
                raise SharkyClipsError(f"\"{src.name}\" is in use.",
                                       "Close the video player or the folder that shows it, then try again.") from None
            time.sleep(delay)
            delay = min(0.5, delay * 2)
        except OSError as exc:  # another disk: EXDEV / WinError 17
            if getattr(exc, "errno", None) in (18,) or getattr(exc, "winerror", None) == 17:
                shutil.move(str(src), str(dest))
                return
            raise


def _move_dir(src: Path, dest: Path) -> None:
    """A whole project folder. 1.2.47: when the folder itself is held open (an indexer, a virus
    scanner, a window on it) but its contents aren't, they move one by one (meta.json last) and
    the empty folder stays behind: without meta.json it is no project any more. All or nothing."""
    try:
        _move(src, dest, seconds=4)
        return
    except SharkyClipsError:
        if not src.is_dir():
            raise
    dest.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    try:
        for e in sorted(src.iterdir(), key=lambda e: e.name == "meta.json"):
            _move(e, dest / e.name)
            moved.append(e.name)
    except BaseException:
        for n in reversed(moved):
            try:
                _move(dest / n, src / n)
            except (OSError, SharkyClipsError):
                pass
        raise
    try:
        src.rmdir()
    except OSError:
        pass  # still held: an empty folder, removed when it can be


def _place_back(src: Path, dest: Path) -> None:
    """Restore a project folder to dest; an empty folder left there by _move_dir is reused."""
    if dest.is_dir() and not any(dest.iterdir()):
        for e in sorted(src.iterdir(), key=lambda e: e.name == "meta.json"):
            _move(e, dest / e.name)
        shutil.rmtree(src, ignore_errors=True)
        return
    if dest.exists():
        raise SharkyClipsError("A project with the same name is back in the workspace.",
                               "Delete or rename that one first, then restore this one.")
    _move(src, dest)


def keep_days() -> int:
    """How long the trash keeps things (setting "trash_keep_days"; 0 = deleted for good at once)."""
    try:
        n = int(config.get("trash_keep_days"))
    except (TypeError, ValueError):
        n = KEEP_DAYS
    return max(0, min(MAX_KEEP_DAYS, n))


def set_keep_days(n) -> int:
    try:
        n = int(n)
    except (TypeError, ValueError):
        raise SharkyClipsError("The number of days must be a whole number.") from None
    if not 0 <= n <= MAX_KEEP_DAYS:
        raise SharkyClipsError(f"Pick 0 to {MAX_KEEP_DAYS} days.", "0 deletes for good at once (no undo).")
    config.update(trash_keep_days=n)
    return n


def _expires(rec: dict) -> datetime:
    deleted = _parse(rec.get("deleted_at")) or _now()
    days = keep_days()
    if isinstance(rec.get("keep_days"), int):  # 1.2.57: a channel VOD's source stays shorter
        days = min(days, max(0, rec["keep_days"]))
    return deleted + timedelta(days=days)


def _new_id() -> str:
    return _now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def _record_path(tid: str) -> Path:
    return root() / _safe(tid) / "trash.json"


def _safe(tid: str) -> str:
    t = re.sub(r"[^A-Za-z0-9_-]", "", str(tid or ""))
    if not t:
        raise SharkyClipsError("Unknown trash item.")
    return t


def _save(rec: dict) -> None:
    write_json_atomic(_record_path(rec["id"]), rec)


def load(tid: str) -> dict:
    rec = read_json_shared(_record_path(tid), None)
    if not isinstance(rec, dict):
        raise SharkyClipsError("That item isn't in the trash any more.")
    return rec


def items() -> list[dict]:
    base = root()
    if not base.is_dir():
        return []
    out = []
    for d in base.iterdir():
        rec = read_json_shared(d / "trash.json", None) if d.is_dir() else None
        if isinstance(rec, dict) and rec.get("id") == d.name:
            out.append(rec)
    return sorted(out, key=lambda r: r.get("deleted_at") or "", reverse=True)


def view(rec: dict, now: datetime | None = None) -> dict:
    now = now or _now()
    exp = _expires(rec)
    keep = {k: rec.get(k) for k in ("id", "kind", "project_id", "project_title", "clip_ids", "titles", "deleted_at",
                                    "bytes", "original", "posts", "purged", "kept_posts")}
    keep["expires_at"] = _iso(exp)
    keep["days_left"] = max(0, int((exp - now).total_seconds() // 86400) + (1 if (exp - now).total_seconds() % 86400 else 0))
    keep["restorable"] = rec.get("kind") != "cleanup" or bool(rec.get("files"))
    return keep


def summary() -> dict:
    rows = items()
    return {"items": [view(r) for r in rows], "count": len(rows), "bytes": sum(int(r.get("bytes") or 0) for r in rows),
            "keep_days": keep_days()}


# ===================================================================== jobs + plans


def _cancel_jobs(project_id: str, cids: set[str] | None = None) -> int:
    """Cancel the queued / running jobs of a project (all of them, or the ones of these clips)."""
    try:
        from .web import app as A
        from .web.jobs import ACTIVE
    except Exception:  # noqa: BLE001 - no web app (CLI)
        return 0
    n = 0
    for j in list(A.jobs.for_project(project_id)) + [j for j in A.jobs.jobs() if j.project_id is None]:
        if j.status not in ACTIVE:
            continue
        p = j.params or {}
        if j.project_id != project_id and p.get("project_id") != project_id:
            continue
        if cids is not None:
            one = p.get("clip_id")
            many = p.get("clip_ids") or p.get("cids")
            if not ((one and one in cids) or (many and set(many) <= cids)):
                continue
        A.jobs.cancel(j.id)
        n += 1
    if n:
        time.sleep(0.3)  # a killed ffmpeg lets go of its files
    return n


def _take_plans(project: Project, cids: list[str]) -> dict:
    """Takes the clips off every plan (YouTube schedule, planned TikTok / Instagram posts,
    pending publish-queue posts) and returns what was there, for Restore."""
    from . import platforms as PF, publishing as P

    out: dict = {"youtube": {}, "social": {}, "calendar": []}
    for cid in cids:
        key = P.key_of(project.id, cid)
        item = P.get(key)
        if item and not item.get("video_id"):
            out["youtube"][cid] = item
            P.remove(key)
    try:
        recs = PF.records(project)
    except Exception:  # noqa: BLE001
        recs = {}
    for cid in cids:
        for p, r in ((recs.get(cid) or {}).items()):
            if (r or {}).get("status") in ("scheduled", "preparing", "ready", "paused") and not _on_platform(r):
                out["social"].setdefault(cid, {})[p] = dict(r)
                PF.record(project, cid, p, status="idle", publish_at=None)
    try:
        from . import pubqueue as PQ

        srcs = {f"{project.id}:{cid}" for cid in cids}
        with PQ._lock:
            cal = PQ.load_calendar()
            keep = [e for e in cal["entries"] if not (e.get("source") in srcs and e.get("status") == "pending")]
            if len(keep) != len(cal["entries"]):
                out["calendar"] = [e for e in cal["entries"] if e not in keep]
                cal["entries"] = keep
                PQ.save_calendar(cal)
    except Exception:  # noqa: BLE001
        pass
    return out


def _put_plans_back(project: Project, plans: dict) -> None:
    from . import platforms as PF, publishing as P

    now = _now()
    for item in (plans.get("youtube") or {}).values():
        at = P.parse(item.get("publish_at"))
        if item.get("now") or (at is not None and at > now):
            P.put(item)
    for cid, plats in (plans.get("social") or {}).items():
        for p, r in plats.items():
            at = _parse(r.get("publish_at"))
            if r.get("status") == "scheduled" and (at is None or at <= now):
                continue  # its time has passed while it was in the trash: plan it again yourself
            PF.record(project, cid, p, **{k: v for k, v in r.items() if k != "at"})
    if plans.get("calendar"):
        try:
            from . import pubqueue as PQ

            with PQ._lock:
                cal = PQ.load_calendar()
                cal["entries"].extend(plans["calendar"])
                PQ.save_calendar(cal)
        except Exception:  # noqa: BLE001
            pass


# ===================================================================== posts on the platforms


def posts_of(project: Project, cids: list[str] | None = None) -> list[dict]:
    """Every post of these clips that is out there: [{platform, clip_id, url, can_delete}]."""
    from . import platforms as PF
    from .web import state

    out = []
    ups = state.load_uploads(project)
    for cid, lst in ups.items():
        if cids is not None and cid not in cids:
            continue
        for u in lst:
            if u.get("video_id") and not u.get("missing") and not u.get("cancelled"):
                out.append({"platform": "youtube", "clip_id": cid, "id": u["video_id"], "url": u.get("url"),
                            "title": u.get("title"), "can_delete": True})
    try:
        recs = PF.records(project)
    except Exception:  # noqa: BLE001
        recs = {}
    for cid, plats in recs.items():
        if cids is not None and cid not in cids:
            continue
        for p, r in (plats or {}).items():
            if (r or {}).get("status") not in ("published", "processing", "scheduled") or r.get("deleted"):
                continue
            if r.get("status") == "scheduled" and not _on_platform(r):
                continue  # planned by SharkyClips itself: not out there yet (taken off the plan)
            out.append({"platform": p, "clip_id": cid, "id": r.get("media_id") or r.get("post_id"), "url": r.get("url"),
                        "title": None, "can_delete": p == "reels" and bool(r.get("media_id"))})
    return out


def _delete_posts(project: Project, cids: list[str] | None) -> dict:
    """Ticked "also delete the posts": YouTube videos and Instagram posts through their APIs.
    TikTok (no delete in its API) and posts SharkyClips can't reach come back as `by_hand`."""
    from . import platforms as PF, youtube
    from .web import state

    done, by_hand, failed = [], [], []
    for post in posts_of(project, cids):
        try:
            if post["platform"] == "youtube":
                youtube.delete_video(post["id"])
                state.patch_upload(project, post["clip_id"], post["id"], {"missing": True, "deleted_at": _iso(_now())})
                done.append(post)
            elif post["platform"] == "reels" and post["can_delete"] and PF.connected("reels"):
                if PF.ig_delete(post["id"]):
                    PF.record(project, post["clip_id"], "reels", deleted=True, status="deleted")
                    done.append(post)
                else:
                    by_hand.append(post)
            else:
                by_hand.append(post)
        except SharkyClipsError as exc:
            failed.append({**post, "error": exc.message})
    return {"deleted": done, "by_hand": by_hand, "failed": failed}


# ===================================================================== 1.2.47: pending posts

LIVE = ("scheduled", "preparing", "uploading", "processing", "paused")  # 1.2.50 paused: kept for Manual mode


def _on_platform(r: dict) -> bool:
    """A planned post that waits on the platform itself (TikTok Studio's schedule, or planned by
    hand in the browser): it goes out by itself, whatever happens to the project here."""
    return (r or {}).get("status") == "scheduled" and bool(r.get("remote") or r.get("via") == "chrome")


def _title(cand: dict) -> str:
    return ((cand.get("publish") or {}).get("titles") or [None])[0] or (cand.get("text") or "")[:80] or cand["id"]


def pending_posts(project: Project, cids: list[str] | None = None) -> list[dict]:
    """Every planned post of these clips that hasn't gone out yet:
    [{platform, clip_id, title, publish_at, on_platform, file, needs_export, no_file}].
    on_platform: it waits on YouTube / TikTok Studio already (a delete doesn't touch it). The rest
    is uploaded by SharkyClips later, from this project's files (file: the video it would send,
    needs_export: none is ready, no_file: only the last step is left, e.g. an Instagram upload
    that is processing)."""
    from . import platforms as PF, publishing as P

    now = _now()
    cands = {c["id"]: c for c in _candidates(project)}
    want = list(cands) if cids is None else [c for c in cids if c in cands]
    out = []
    for cid in want:
        item = P.get(P.key_of(project.id, cid))
        if not item or item.get("cancelled"):
            continue
        at = P.parse(item.get("publish_at"))
        row = {"platform": "youtube", "clip_id": cid, "title": _title(cands[cid]), "publish_at": _iso(at) if at else None,
               "file": None, "needs_export": False, "no_file": False}
        if item.get("video_id"):
            if at is not None and at > now:
                out.append({**row, "on_platform": True})
        else:
            out.append({**row, "on_platform": False})
    try:
        recs = PF.records(project)
    except Exception:  # noqa: BLE001
        recs = {}
    for cid in want:
        for plat, r in (recs.get(cid) or {}).items():
            r = r or {}
            st = r.get("status")
            if (r.get("mode") == "semi" and st != "preparing") or r.get("deleted"):
                continue  # by hand: its file is in Downloads already
            retry = st == "failed" and r.get("next_try_at") and int(r.get("attempts") or 0) < _max_tries()
            if st not in LIVE and not retry:
                continue
            row = {"platform": plat, "clip_id": cid, "title": _title(cands[cid]), "publish_at": r.get("publish_at"),
                   "on_platform": _on_platform(r) or (st == "processing" and plat == "tiktok"),
                   "file": None, "needs_export": False, "no_file": st == "processing"}
            if not row["on_platform"] and not row["no_file"]:
                row["file"], row["needs_export"] = _post_file(project, cid, r)
            out.append(row)
    return out


def _max_tries() -> int:
    try:
        from .web.multipost import MAX_TRIES

        return MAX_TRIES
    except Exception:  # noqa: BLE001
        return 6


def _post_file(project: Project, cid: str, rec: dict) -> tuple[str | None, bool]:
    """(the video this post would send, an export is needed first)."""
    f = rec.get("file")
    if f and Path(f).is_file() and (rec.get("file_fixed") or rec.get("container_id") or rec.get("publish_id")
                                    or rec.get("submitted_at")):
        return f, False
    try:
        from .web import multipost as M

        src = M._source_info(project, cid)
    except Exception:  # noqa: BLE001
        return None, True
    return (src["file"], False) if src.get("kind") == "clip" and src.get("file") else (None, True)


def pending_summary(project: Project, cids: list[str] | None = None) -> dict:
    rows = pending_posts(project, cids)
    local = [r for r in rows if not r["on_platform"]]
    youtube_wait = [r for r in local if r["platform"] == "youtube"]
    files = {r["file"] for r in local if r["file"]}
    return {"pending": rows, "pending_local": len(local), "pending_on_platform": len(rows) - len(local),
            "keep_possible": bool(local) and not youtube_wait and cids is None,
            "keep_needs_export": sum(1 for r in local if r["needs_export"]),
            "keep_bytes": sum(size_of(Path(f)) for f in files)}


# ===================================================================== delete


def _original(project: Project) -> Path | None:
    src = (project.load_meta().get("source") or {})
    if src.get("type") != "file" or not src.get("value"):
        return None
    p = Path(str(src["value"]))
    if not p.is_absolute():  # a relative name would be looked up next to wherever the app runs
        return None
    return p if p.is_file() else None


def _finish(rec: dict) -> dict:
    """Saves a trash item; with 0 keep days it is deleted for good right away."""
    _save(rec)
    if keep_days() == 0:
        try:
            purge(rec["id"])
            rec["purged"] = True
        except SharkyClipsError:
            pass  # a file in use: the hourly purge takes it
    return view(rec)


def delete_project(project_id: str, with_original: bool = False, with_posts: bool = False,
                   pending: str = "cancel", job=None) -> dict:
    """pending: what happens to planned posts that aren't on the platform yet: "cancel" (taken
    off the plan, back on Restore) or "keep" (see keep_posts)."""
    project = get_project(project_id)
    if pending == "keep":
        return keep_posts(project, with_original, with_posts, job)
    with _lock:
        if project.load_meta().get("posts_only"):  # the rest of an earlier "keep the posts": all of it now
            _take_plans(project, [c["id"] for c in _candidates(project)])
            return _join_rest(project, cancel=True)
        _cancel_jobs(project.id)
        posts = _delete_posts(project, None) if with_posts else None
        plans = _take_plans(project, [c["id"] for c in (_candidates(project))])
        meta = project.load_meta()
        tid = _new_id()
        home = root() / tid
        home.mkdir(parents=True)
        nbytes = size_of(project.dir)
        original = None
        orig = _original(project)
        if orig is not None and not _inside(orig, project.dir):
            original = {"path": str(orig), "moved": False, "bytes": orig.stat().st_size,
                        "outside_workspace": not _inside(orig, config.workspace_dir())}
        rec = {"id": tid, "kind": "project", "project_id": project.id, "project_title": meta.get("title") or project.id,
               "clip_ids": [], "titles": [], "deleted_at": _iso(_now()),
               "expires_at": _iso(_now() + timedelta(days=keep_days())), "bytes": nbytes, "plans": plans,
               "original": original, "posts": posts, "files": [{"from": str(project.dir), "to": project.id}]}
        try:
            _move_dir(project.dir, home / project.id)
        except BaseException:
            shutil.rmtree(home, ignore_errors=True)
            _put_plans_back(project, plans)
            raise
        if with_original and original is not None:
            try:
                _move(Path(original["path"]), home / "original" / Path(original["path"]).name, seconds=4)
                original.update(moved=True, to=f"original/{Path(original['path']).name}")
                rec["bytes"] += original["bytes"]
            except (OSError, SharkyClipsError) as exc:
                original["error"] = str(getattr(exc, "message", exc))
        return _finish(rec)


def _move_rest(base: Path, keep: set[Path], dest: Path) -> list[dict]:
    """Moves everything of a project folder into dest except its top-level JSON files and the
    `keep` files (and the folders on their way). All or nothing."""
    keep = {k.resolve() for k in keep}
    keep_dirs = {a for k in keep for a in k.parents}
    moved: list[dict] = []

    def walk(d: Path) -> None:
        for e in sorted(d.iterdir()):
            rel = e.relative_to(base)
            r = e.resolve()
            if r in keep or (d == base and e.is_file() and e.suffix.lower() == ".json"):
                continue
            if e.is_dir() and r in keep_dirs:
                walk(e)
                continue
            _move(e, dest / rel)
            moved.append({"from": str(rel), "to": str(Path("files") / rel)})

    try:
        walk(base)
    except BaseException:
        for m in reversed(moved):
            try:
                _move(dest.parent / m["to"], base / m["from"])
            except (OSError, SharkyClipsError):
                pass
        raise
    return moved


def _cancel_jobs_but_posts(project_id: str) -> int:
    """Like _cancel_jobs, but an upload running right now goes on (it is one of the kept posts)."""
    try:
        from .web import app as A
        from .web.jobs import ACTIVE
    except Exception:  # noqa: BLE001 - no web app (CLI)
        return 0
    n = 0
    for j in list(A.jobs.for_project(project_id)):
        if j.status in ACTIVE and j.kind != "post":
            A.jobs.cancel(j.id)
            n += 1
    if n:
        time.sleep(0.3)
    return n


def keep_posts(project: Project, with_original: bool = False, with_posts: bool = False, job=None) -> dict:
    """Delete a project but keep its planned posts that aren't on the platform yet (Instagram:
    SharkyClips uploads them at their time). The video of each one is pinned to its post (an
    export is made first when no up-to-date render exists: slow, run it in a job), then all the
    rest goes to the trash. The "posts only" rest is hidden and goes by itself after its last post."""
    from . import platforms as PF

    def existing() -> dict | None:
        po = project.load_meta().get("posts_only")
        if not po:
            return None
        try:
            return view(load(po.get("trash_id") or "-"))
        except SharkyClipsError:
            return None

    if (done := existing()) is not None:
        return done
    info = pending_summary(project)
    local = [r for r in info["pending"] if not r["on_platform"]]
    if not local:
        return delete_project(project.id, with_original, with_posts, "cancel")
    if not info["keep_possible"]:
        raise SharkyClipsError("A YouTube upload of this project isn't finished yet.",
                               "Try again once the Library shows it planned on YouTube, or cancel the posts.")
    _cancel_jobs_but_posts(project.id)
    from .web import multipost as M

    keep: set[Path] = set()
    for r in local:  # outside the trash lock: an export takes minutes
        if r["no_file"]:
            continue
        rec = (PF.records(project).get(r["clip_id"]) or {}).get(r["platform"]) or {}
        f = M._file_for(project, r["clip_id"], r["platform"], rec, job)  # may export (needs the stream video)
        PF.record(project, r["clip_id"], r["platform"], file=str(f), file_fixed=True)
        keep.add(Path(f))
    with _lock:
        if (done := existing()) is not None:
            return done
        meta = project.load_meta()
        posts = _delete_posts(project, None) if with_posts else None
        original = None
        orig = _original(project)
        if orig is not None and not _inside(orig, project.dir):
            original = {"path": str(orig), "moved": False, "bytes": orig.stat().st_size,
                        "outside_workspace": not _inside(orig, config.workspace_dir())}
        tid = _new_id()
        home = root() / tid
        home.mkdir(parents=True)
        try:
            moved = _move_rest(project.dir, keep, home / "files")
        except BaseException:
            shutil.rmtree(home, ignore_errors=True)
            raise
        kept = [{k: r[k] for k in ("platform", "clip_id", "title", "publish_at")} for r in local]
        rec = {"id": tid, "kind": "project", "partial": True, "project_id": project.id,
               "project_title": meta.get("title") or project.id, "clip_ids": [], "titles": [],
               "deleted_at": _iso(_now()), "expires_at": _iso(_now() + timedelta(days=keep_days())),
               "bytes": sum(size_of(home / m["to"]) for m in moved), "plans": {}, "original": original,
               "posts": posts, "files": moved, "kept_posts": kept, "kept_bytes": size_of(project.dir)}
        if with_original and original is not None:
            try:
                _move(Path(original["path"]), home / "original" / Path(original["path"]).name, seconds=4)
                original.update(moved=True, to=f"original/{Path(original['path']).name}")
                rec["bytes"] += original["bytes"]
            except (OSError, SharkyClipsError) as exc:
                original["error"] = str(getattr(exc, "message", exc))
        meta["posts_only"] = {"since": rec["deleted_at"], "trash_id": tid,
                              "posts": [f"{r['clip_id']}:{r['platform']}" for r in local]}
        project.save_meta(meta)
        return _finish(rec)


def _join_rest(project: Project, cancel: bool = False) -> dict:
    """The "posts only" rest of a project goes after its trash item (Restore brings all back)."""
    with _lock:
        meta = project.load_meta()
        po = meta.get("posts_only") or {}
        _cancel_jobs(project.id)
        try:
            rec = load(po.get("trash_id") or "-")
        except SharkyClipsError:
            rec = None
        if rec is None:  # that item is deleted for good already: this rest is all that's left
            meta.pop("posts_only", None)
            project.save_meta(meta)
            if keep_days() == 0:
                n = size_of(project.dir)
                shutil.rmtree(project.dir, ignore_errors=True)
                return {"id": None, "kind": "project", "project_id": project.id, "bytes": n, "purged": True}
            return delete_project(project.id)
        home = root() / rec["id"]
        _move_dir(project.dir, home / "rest" / project.id)
        rec.update(rest_moved=True, bytes=int(rec.get("bytes") or 0) + size_of(home / "rest"),
                   rest_at=_iso(_now()), rest_cancelled=bool(cancel))
        return _finish(rec)


def finish_rests() -> int:
    """From the publish loop: a "posts only" rest whose last post went out (or was cancelled /
    failed for good) joins its trash item."""
    from .web import multipost as M

    n = 0
    for project in list_projects():
        try:
            if not project.load_meta().get("posts_only"):
                continue
            if any(not r["on_platform"] for r in pending_posts(project)):
                continue
            cids = [c["id"] for c in _candidates(project)]
            if any(M.active_job(project.id, cid, p) is not None for cid in cids for p in ("tiktok", "reels")):
                continue
            _join_rest(project)
            n += 1
        except Exception:  # noqa: BLE001 - next minute
            continue
    return n


def _candidates(project: Project) -> list[dict]:
    from .web import state

    return list((state.load_highlights(project) or {}).get("candidates") or [])


def _clip_files(project: Project, cids: set[str]) -> list[Path]:
    """Every file of these clips in the project folder (not the stream's own files): the name
    holds the clip id between separators (01_c03.mp4, c03_face_tall_x.jpg, face_c03_x.json)."""
    pat = re.compile(r"(?:^|[ _.\-])(" + "|".join(re.escape(c) for c in sorted(cids)) + r")(?=$|[ _.\-])")
    out = []
    for dirpath, _dirs, files in os.walk(project.dir):
        d = Path(dirpath)
        if d == project.dir:
            continue  # top level: source, audio, the JSON files
        for f in files:
            if pat.search(Path(f).stem) or pat.search(f):
                out.append(d / f)
    return out


def delete_clips(project_id: str, cids: list[str], with_posts: bool = False, kind: str = "clips") -> dict:
    from .edit import manual
    from .web import state

    project = get_project(project_id)
    want = [str(c) for c in dict.fromkeys(cids or [])]
    if not want:
        raise SharkyClipsError("Pick at least one clip.")
    with _lock:
        hl = state.load_highlights(project) or {}
        cands = {c["id"]: c for c in hl.get("candidates") or []}
        missing = [c for c in want if c not in cands]
        if missing:
            raise SharkyClipsError(f"No clip {missing[0]} in this project.")
        cset = set(want)
        _cancel_jobs(project.id, cset)
        posts = _delete_posts(project, want) if with_posts else None
        plans = _take_plans(project, want)
        tid = _new_id()
        home = root() / tid
        files = _clip_files(project, cset)
        moved = []
        try:
            for f in files:
                rel = f.relative_to(project.dir)
                _move(f, home / "files" / rel)
                moved.append({"from": str(rel), "to": str(Path("files") / rel)})
        except BaseException:
            for m in moved:  # all or nothing
                _move(home / m["to"], project.dir / m["from"])
            shutil.rmtree(home, ignore_errors=True)
            _put_plans_back(project, plans)
            raise
        review = state.load_review(project, hl)
        all_clips = (json.loads((project.dir / "clips.json").read_text(encoding="utf-8")).get("clips") or {}) \
            if (project.dir / "clips.json").is_file() else {}
        manual_entries = [m for m in manual.load(project) if m["id"] in cset]
        data = {"candidates": [cands[c] for c in want],
                "positions": {c: i for i, c in enumerate(x["id"] for x in hl.get("candidates") or []) if c in cset},
                "accepted": [c for c in review["accepted"] if c in cset],
                "rejected": [c for c in review["rejected"] if c in cset],
                "clips_json": {c: all_clips[c] for c in want if c in all_clips}, "manual": manual_entries}
        for m in manual_entries:
            manual.remove(project, m["id"])
        hl = state.load_highlights(project) or hl
        hl["candidates"] = [c for c in hl.get("candidates") or [] if c["id"] not in cset]
        write_json_atomic(project.dir / "highlights.json", hl)
        state.save_review(project, {"accepted": [c for c in review["accepted"] if c not in cset],
                                    "rejected": [c for c in review["rejected"] if c not in cset]})
        if all_clips and any(c in all_clips for c in want):
            write_json_atomic(project.dir / "clips.json",
                              {"version": 1, "clips": {k: v for k, v in all_clips.items() if k not in cset}})
        titles = [((cands[c].get("publish") or {}).get("titles") or [None])[0] or (cands[c].get("text") or "")[:80]
                  or c for c in want]
        rec = {"id": tid, "kind": kind, "project_id": project.id,
               "project_title": project.load_meta().get("title") or project.id, "clip_ids": want, "titles": titles,
               "deleted_at": _iso(_now()), "expires_at": _iso(_now() + timedelta(days=keep_days())),
               "bytes": sum(size_of(home / m["to"]) for m in moved), "files": moved, "data": data, "plans": plans,
               "posts": posts, "original": None}
        return _finish(rec)


# ===================================================================== restore


def restore(tid: str) -> dict:
    with _lock:
        rec = load(tid)
        home = root() / _safe(tid)
        if rec["kind"] == "project" and rec.get("partial"):
            _restore_partial(rec, home)
        elif rec["kind"] == "project":
            dest = config.workspace_dir() / rec["project_id"]
            _place_back(home / rec["project_id"], dest)
            orig = rec.get("original") or {}
            if orig.get("moved"):
                target = Path(orig["path"])
                if not target.exists():
                    try:
                        _move(home / orig["to"], target, seconds=4)
                    except (OSError, SharkyClipsError):
                        pass
            project = Project(rec["project_id"], dest)
            _put_plans_back(project, rec.get("plans") or {})
        else:
            project = get_project(rec["project_id"])
            _restore_clips(project, rec, home)
        shutil.rmtree(home, ignore_errors=True)
        return {"restored": rec["id"], "kind": rec["kind"], "project_id": rec["project_id"],
                "clip_ids": rec.get("clip_ids") or []}


def _restore_partial(rec: dict, home: Path) -> None:
    """A "keep the posts" delete: the rest (still in the workspace, or joined the item later)
    gets its files back and is a normal project again."""
    from . import platforms as PF

    dest = config.workspace_dir() / rec["project_id"]
    if rec.get("rest_moved"):
        _place_back(home / "rest" / rec["project_id"], dest)
    if not dest.is_dir():
        raise SharkyClipsError("The rest of this project is gone.", "Delete this item for good.")
    for m in rec.get("files") or []:
        src, to = home / m["to"], dest / m["from"]
        if src.exists() and not to.exists():
            _move(src, to)
    orig = rec.get("original") or {}
    if orig.get("moved") and not Path(orig["path"]).exists():
        try:
            _move(home / orig["to"], Path(orig["path"]), seconds=4)
        except (OSError, SharkyClipsError):
            pass
    project = Project(rec["project_id"], dest)
    meta = project.load_meta()
    meta.pop("posts_only", None)
    project.save_meta(meta)
    try:  # posts not sent yet follow your edits again (not the pinned file)
        for cid, plats in PF.records(project).items():
            for plat, r in (plats or {}).items():
                if (r or {}).get("file_fixed") and r.get("status") == "scheduled" and not r.get("container_id"):
                    PF.record(project, cid, plat, file_fixed=None, file=None)
    except Exception:  # noqa: BLE001
        pass


def _restore_clips(project: Project, rec: dict, home: Path) -> None:
    from .edit import manual
    from .web import state

    data = rec.get("data") or {}
    hl = state.load_highlights(project) or {"candidates": []}
    have = {c["id"] for c in hl.get("candidates") or []}
    clash = [c["id"] for c in data.get("candidates") or [] if c["id"] in have]
    if clash:
        raise SharkyClipsError(f"This project has a clip {clash[0]} again (the clips were found anew).",
                               "These clips can't come back next to the new ones; delete them for good instead.")
    for m in rec.get("files") or []:
        src, dest = home / m["to"], project.dir / m["from"]
        if src.exists() and not dest.exists():
            _move(src, dest)
    cands = list(hl.get("candidates") or [])
    pos = data.get("positions") or {}
    for c in sorted(data.get("candidates") or [], key=lambda c: pos.get(c["id"], 10_000)):
        cands.insert(min(int(pos.get(c["id"], len(cands))), len(cands)), c)
    hl["candidates"] = cands
    write_json_atomic(project.dir / "highlights.json", hl)
    if data.get("manual"):
        with manual._lock:
            cur = manual.load(project)
            ids = {m["id"] for m in cur}
            manual._save(project, cur + [m for m in data["manual"] if m["id"] not in ids])
    review = state.load_review(project, hl)
    state.save_review(project, {"accepted": review["accepted"] + [c for c in data.get("accepted") or [] if c not in review["accepted"]],
                                "rejected": review["rejected"] + [c for c in data.get("rejected") or [] if c not in review["rejected"]]})
    if data.get("clips_json"):
        path = project.dir / "clips.json"
        cur = (json.loads(path.read_text(encoding="utf-8")).get("clips") or {}) if path.is_file() else {}
        cur.update(data["clips_json"])
        write_json_atomic(path, {"version": 1, "clips": cur})
    _put_plans_back(project, rec.get("plans") or {})


# ===================================================================== delete for good


def purge(tid: str) -> int:
    with _lock:
        rec = load(tid)
        home = root() / _safe(tid)
        n = int(rec.get("bytes") or 0)
        shutil.rmtree(home, ignore_errors=True)
        if home.exists():
            raise SharkyClipsError("Some files couldn't be deleted (in use).", "Close the video player, then try again.")
        return n


def empty() -> dict:
    rows = items()
    freed, left = 0, 0
    for r in rows:
        try:
            freed += purge(r["id"])
        except SharkyClipsError:
            left += 1
    return {"deleted": len(rows) - left, "bytes": freed, "left": left}


def purge_expired(now: datetime | None = None) -> int:
    now = now or _now()
    n = 0
    for r in items():
        if _expires(r) <= now:
            try:
                purge(r["id"])
                n += 1
            except SharkyClipsError:
                pass
    return n


def purge_soon(every: float = 3600.0) -> int:
    """From the publish loop: items older than the keep days go (once an hour is plenty; with
    0 keep days everything goes at once anyway)."""
    if time.time() - _purge_at["t"] < every:
        return 0
    _purge_at["t"] = time.time()
    try:
        return purge_expired()
    except Exception:  # noqa: BLE001
        return 0


# ===================================================================== disk usage + "Temizlik"


def usage(project: Project) -> dict:
    """{"total", "source", "clips", "exports", "cache", "other", "cleanable": {...}}"""
    from .web import state

    total = size_of(project.dir)
    src = project.source_path
    parts = {"source": size_of(src) if src else 0, "audio": size_of(project.audio_path),
             "clips": size_of(project.dir / "clips"), "exports": size_of(project.dir / "exports"),
             "cache": size_of(project.cache_dir)}
    parts["other"] = max(0, total - sum(parts.values()))
    review = state.load_review(project)
    rejected = set(review.get("rejected") or [])
    rej_files = _clip_files(project, rejected) if rejected else []
    cleanable = {"rejected": {"bytes": sum(size_of(f) for f in rej_files), "files": len(rej_files), "clips": len(rejected)},
                 "previews": {"bytes": sum(size_of(project.dir / d) for d in OLD_PREVIEW_DIRS)},
                 "caches": {"bytes": sum(size_of(project.cache_dir / d) for d in CACHE_DIRS)}}
    return {"project_id": project.id, "total": total, **parts, "cleanable": cleanable,
            "cleanable_bytes": sum(v["bytes"] for v in cleanable.values())}


def all_usage() -> dict:
    rows = []
    for p in list_projects():
        if p.posts_only:
            continue
        try:
            u = usage(p)
        except Exception:  # noqa: BLE001
            continue
        rows.append({**u, "title": p.load_meta().get("title") or p.id})
    rows.sort(key=lambda r: r["total"], reverse=True)
    t = summary()
    return {"projects": rows, "total": sum(r["total"] for r in rows), "trash_bytes": t["bytes"], "trash_count": t["count"],
            "cleanable_bytes": sum(r["cleanable_bytes"] for r in rows)}


def cleanup(project_id: str, what: list[str]) -> dict:
    """The "Temizlik" helper for one project. rejected / previews -> the trash (restorable),
    caches -> deleted (they are made again when needed)."""
    from .web import state

    project = get_project(project_id)
    what = [w for w in what if w in ("rejected", "previews", "caches")]
    if not what:
        raise SharkyClipsError("Pick what to clean up.")
    freed_now = 0
    trashed = None
    with _lock:
        if "caches" in what:
            for d in CACHE_DIRS:
                p = project.cache_dir / d
                n = size_of(p)
                shutil.rmtree(p, ignore_errors=True)
                freed_now += n - (size_of(p) if p.exists() else 0)
        moves: list[tuple[Path, Path]] = []
        if "rejected" in what:
            rejected = set(state.load_review(project).get("rejected") or [])
            if rejected:
                _cancel_jobs(project.id, rejected)
                moves += [(f, f.relative_to(project.dir)) for f in _clip_files(project, rejected)]
        if "previews" in what:
            for d in OLD_PREVIEW_DIRS:
                if (project.dir / d).is_dir():
                    moves.append((project.dir / d, Path(d)))
        if moves:
            tid = _new_id()
            home = root() / tid
            done = []
            for src, rel in moves:
                _move(src, home / "files" / rel)
                done.append({"from": str(rel), "to": str(Path("files") / rel)})
            if "rejected" in what:  # the rendered entries of rejected clips point at nothing now
                path = project.dir / "clips.json"
                if path.is_file():
                    cur = json.loads(path.read_text(encoding="utf-8")).get("clips") or {}
                    gone = {k: v for k, v in cur.items() if not (project.dir / "clips" / v.get("file", "")).is_file()}
                    if gone:
                        write_json_atomic(path, {"version": 1, "clips": {k: v for k, v in cur.items() if k not in gone}})
                        done_json = gone
                    else:
                        done_json = {}
                else:
                    done_json = {}
            else:
                done_json = {}
            rec = {"id": tid, "kind": "cleanup", "project_id": project.id,
                   "project_title": project.load_meta().get("title") or project.id, "clip_ids": [], "titles": what,
                   "deleted_at": _iso(_now()), "expires_at": _iso(_now() + timedelta(days=keep_days())),
                   "bytes": sum(size_of(home / m["to"]) for m in done), "files": done,
                   "data": {"clips_json": done_json, "candidates": []}, "plans": {}, "posts": None, "original": None}
            trashed = _finish(rec)
    return {"freed_now": freed_now, "trashed": trashed, "usage": usage(project)}


def trash_source(project_id: str, keep: int | None = None) -> dict | None:
    """1.2.57 channel monitoring: the downloaded VOD of a finished stream -> the trash (restorable
    like any cleanup item; `keep` days at most there, the clips stay). None = nothing to move."""
    project = get_project(project_id)
    with _lock:
        src = project.source_path
        if src is None:
            return None
        moves = [src] + [p for p in (project.cache_dir / "proxy.mp4",) if p.is_file()]  # the browser copy too
        tid = _new_id()
        home = root() / tid
        done = []
        for f in moves:
            rel = f.relative_to(project.dir)
            _move(f, home / "files" / rel)
            done.append({"from": str(rel), "to": str(Path("files") / rel)})
        rec = {"id": tid, "kind": "cleanup", "project_id": project.id,
               "project_title": project.load_meta().get("title") or project.id, "clip_ids": [], "titles": ["source"],
               "deleted_at": _iso(_now()), "bytes": sum(size_of(home / m["to"]) for m in done), "files": done,
               "data": {"clips_json": {}, "candidates": []}, "plans": {}, "posts": None, "original": None}
        if keep is not None:
            rec["keep_days"] = int(keep)
        rec["expires_at"] = _iso(_expires(rec))
        return _finish(rec)
