"""1.2.68 "Upload manually": for every platform and every clip.

Prepare = the video that fits the platform (shortsfmt) is saved to Downloads/SharkyClips/<stream>/
with a .txt of the texts next to it. The UI then shows the title, the description and the
hashtags with one copy button each, opens the platform's upload page and the file's folder.
"I posted it" (optionally with the post's link) marks the clip shared there: the board shows it,
the upload history keeps it, and SharkyClips never posts it there itself any more.

State per project: <project>/manual.json  {cid: {platform: {status, file, folder, error, made_at,
shared_at, url, job}}}  status: preparing | ready | failed | shared
"""

from __future__ import annotations

import shutil
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Body

from .. import easy as E, platforms as PF, shortsfmt
from ..errors import SharkyClipsError
from ..project import Project, read_json_shared, write_json_atomic
from . import multipost as M, shareevents, state

router = APIRouter()

PLATFORMS = ("youtube", "tiktok", "reels")
UPLOAD_PAGE = {"youtube": "https://www.youtube.com/upload", **PF.UPLOAD_PAGE}
_lock = threading.RLock()


def _app():
    return M._app()


def _path(project: Project) -> Path:
    return project.dir / "manual.json"


def load(project: Project) -> dict:
    d = read_json_shared(_path(project), {})
    return d if isinstance(d, dict) else {}


def get(project: Project, cid: str, platform: str) -> dict:
    return dict((load(project).get(cid) or {}).get(platform) or {})


def _put(project: Project, cid: str, platform: str, **data) -> dict:
    with _lock:
        all_ = load(project)
        cur = {**((all_.get(cid) or {}).get(platform) or {}), **data, "at": time.time()}
        all_.setdefault(cid, {})[platform] = cur
        write_json_atomic(_path(project), all_)
        return cur


def _check(platform: str) -> None:
    if platform not in PLATFORMS:
        raise SharkyClipsError("Unknown platform.")


# ===================================================================== texts


def texts(project: Project, cid: str, platform: str) -> dict:
    """The fields to copy one by one, the newest edit of each."""
    A = _app()
    cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
    d = M.drafts(project, cand)
    if platform == "youtube":
        y = d["youtube"]
        tags = " ".join(f"#{h}" for h in y["hashtags"])
        return {"title": y["title"], "description": y["full_description"], "hashtags": tags,
                "caption": f"{y['title']}\n\n{y['full_description']}"}
    rec = PF.records(project).get(cid, {}).get(platform) or {}
    caption = rec.get("caption") if rec.get("mode") == "semi" and rec.get("caption") else d[platform]["caption"]
    return M.caption_parts(caption)


def view(project: Project, cid: str, platform: str) -> dict:
    _check(platform)
    st = get(project, cid, platform)
    job = _job(project.id, cid, platform)
    status = st.get("status") or "idle"
    if status == "preparing" and job is None:
        status = "failed" if not st.get("file") else "ready"
    file = st.get("file")
    return {"project_id": project.id, "clip_id": cid, "platform": platform, "status": status,
            "file": file if file and Path(file).is_file() else None, "folder": st.get("folder"),
            "error": st.get("error") if status == "failed" else None, "url": st.get("url"),
            "fixed": st.get("fixed") or [], "upload_page": UPLOAD_PAGE[platform],
            "texts": texts(project, cid, platform),
            "progress": job.progress if job is not None else None}


# ===================================================================== prepare (a job)


def _job(project_id: str, cid: str, platform: str):
    from .jobs import ACTIVE

    for j in _app().jobs.for_project(project_id):
        if j.kind == "manual" and j.status in ACTIVE and j.params.get("clip_id") == cid \
                and j.params.get("platform") == platform:
            return j
    return None


def _dest(project: Project, cid: str, platform: str) -> Path:
    A = _app()
    c = A._cand(project, cid)
    folder = E.downloads_root() / E.safe_name(project.load_meta().get("title") or project.id, 80)
    title = texts(project, cid, platform)["title"] or ((c.get("publish") or {}).get("titles") or [None])[0] or cid
    rank = f"{int(c.get('rank') or 0):02d}"
    name = M.NAMES[platform]
    for n in (60, 40, 20):  # Windows paths stop at 260 characters
        dest = folder / f"{rank} {E.safe_name(title, n)} - {name}.mp4"
        if len(str(dest)) <= 240:
            return dest
    return E.downloads_root() / f"{rank} {name} {project.id[-8:]}.mp4"


def run(project_id: str, cid: str, platform: str, job=None) -> dict:
    A = _app()
    project = A.get_project(project_id)
    try:
        src = M._file_for(project, cid, platform, {}, job)
        if job is not None:
            A.jobs.update(job, stage="checking_format", progress=None)
        fixed_file, fixed = shortsfmt.ensure(src, platform, project.cache_dir / "shortsfix")
        dest = _dest(project, cid, platform)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(fixed_file, dest)
        except OSError as exc:
            raise SharkyClipsError(f"Couldn't save the video in {dest.parent}.",
                                   "Check that the Downloads folder exists and has free space.") from exc
        t = texts(project, cid, platform)
        (dest.parent / f"{dest.stem}.txt").write_text(
            "\n\n".join(x for x in (t["title"], t["description"], t["hashtags"]) if x) + "\n", encoding="utf-8")
        _put(project, cid, platform, status="ready", file=str(dest), folder=str(dest.parent), error=None,
             made_at=time.time(), fixed=fixed)
        shareevents.manual_ready(project, cid, platform)
        return {"status": "ready", "file": str(dest)}
    except SharkyClipsError as exc:
        _put(project, cid, platform, status="failed", error={"message": exc.message, "hint": exc.hint})
        shareevents.failed(project, cid, platform, exc.message, exc.hint)
        raise


def prepare(project: Project, cid: str, platform: str) -> dict:
    _check(platform)
    _app()._cand(project, cid)  # 404 for an unknown clip
    st = get(project, cid, platform)
    if st.get("status") == "ready" and st.get("file") and Path(st["file"]).is_file():
        return view(project, cid, platform)
    if _job(project.id, cid, platform) is None:
        _put(project, cid, platform, status="preparing", error=None)
        A = _app()
        pid = project.id
        A.jobs.submit("manual", "net", pid, {"clip_id": cid, "platform": platform,
                                             "title": texts(project, cid, platform)["title"][:90],
                                             "project_title": project.load_meta().get("title") or pid},
                      lambda job: run(pid, cid, platform, job), key=f"manual:{pid}:{cid}:{platform}")
    return view(project, cid, platform)


def done(project: Project, cid: str, platform: str, url: str | None = None) -> dict:
    """"I posted it": shared by hand on that platform."""
    _check(platform)
    u = (url or "").strip()
    u = u if u.startswith("https://") else None
    _put(project, cid, platform, status="shared", shared_at=time.time(), url=u)
    if platform in M.SOCIAL:
        rec = PF.records(project).get(cid, {}).get(platform) or {}
        if rec.get("status") != "published":  # the board shows it shared (record hook: notice + history)
            PF.record(project, cid, platform, status="published", mode="semi", manual=True,
                      posted_at=M._iso(M._now()), url=u or rec.get("url"))
            return view(project, cid, platform)
    shareevents.shared(project, cid, platform, u, manual=True)
    return view(project, cid, platform)


def overlay(project: Project, cid: str, states: dict) -> dict:
    """clip_states + what was prepared / posted by hand (so the board shows it)."""
    m = load(project).get(cid) or {}
    for p, st in m.items():
        if p not in states or not isinstance(st, dict):
            continue
        cur = states[p]
        if cur.get("status") not in ("idle", "failed", "cancelled"):
            continue
        if st.get("status") == "shared":
            states[p] = {**cur, "status": "published", "url": st.get("url") or cur.get("url"), "manual": True}
        elif st.get("status") in ("ready", "preparing"):
            states[p] = {**cur, "status": "ready" if st["status"] == "ready" else "preparing", "mode": "semi",
                         "manual": False, "by_hand_file": st.get("file")}
    return states


# ===================================================================== API


def _project(pid: str) -> Project:
    return _app()._project(pid)


@router.get("/api/manual/{project_id}/{cid}/{platform}")
def api_view(project_id: str, cid: str, platform: str) -> dict:
    return view(_project(project_id), cid, platform)


@router.post("/api/manual/{project_id}/{cid}/{platform}")
def api_prepare(project_id: str, cid: str, platform: str) -> dict:
    return prepare(_project(project_id), cid, platform)


@router.post("/api/manual/{project_id}/{cid}/{platform}/open")
def api_open(project_id: str, cid: str, platform: str) -> dict:
    st = get(_project(project_id), cid, platform)
    f = Path(st["file"]) if st.get("file") else None
    if f is None or not f.is_file():
        raise SharkyClipsError("The video isn't saved yet.", "Press \"Upload manually\" first.")
    return {"ok": bool(E.reveal_file(f)), "folder": str(f.parent)}


@router.post("/api/manual/{project_id}/{cid}/{platform}/done")
def api_done(project_id: str, cid: str, platform: str, body: dict | None = Body(default=None)) -> dict:
    return done(_project(project_id), cid, platform, (body or {}).get("url"))
