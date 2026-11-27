"""Photo slideshow API (1.2.72), see slideshow.py.

  GET    /api/slideshow                         the slideshows (newest first)
  POST   /api/slideshow                         a new, empty one {title?}
  GET    /api/slideshow/{id}                    everything the editor shows
  PUT    /api/slideshow/{id}                    settings: {order, sort: "date", seconds, transition,
                                                labels, outro, subject, title, texts: {photo: text}}
  PUT    /api/slideshow/{id}/photos?filename=&modified=   one photo (raw body)
  POST   /api/slideshow/{id}/photos/{pid}/remove | restore   (restore = Undo)
  GET    /api/slideshow/{id}/photos/{pid}/thumb
  POST   /api/slideshow/{id}/preview | export   jobs (the preview is small and fast)
  GET    /api/slideshow/{id}/preview.mp4 | video.mp4
  POST   /api/slideshow/{id}/save               MP4 + a .txt (title, description, hashtags) into
                                                Downloads/SharkyClips/<title>/
  POST   /api/slideshow/{id}/open-folder        that folder in Explorer / Finder (this PC only)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .. import easy as E, slideshow as S
from ..errors import SharkyClipsError
from ..project import Project, get_project

router = APIRouter()


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


def _project(pid: str) -> Project:
    if not S.file_url_safe(pid):
        raise HTTPException(404, "No such slideshow")
    try:
        project = get_project(pid)
    except SharkyClipsError:
        raise HTTPException(404, "No such slideshow") from None
    if project.id != pid or not S.is_slideshow(project):
        raise HTTPException(404, "No such slideshow")
    return project


def _jobs(project: Project) -> dict:
    A = _app()
    out = {}
    for j in sorted(A.jobs.list(), key=lambda j: j.get("created") or 0):
        if j.get("project_id") == project.id and j.get("kind") in ("slideshow_preview", "slideshow_export"):
            out[j["kind"]] = j  # the newest one of each kind
    return out


def _clip(project: Project) -> dict | None:
    from . import state

    clip = state.load_clips(project).get(S.CID)
    return clip if clip and (project.dir / "clips" / clip["file"]).is_file() else None


def _share_status(project: Project) -> dict | None:
    try:
        from . import multipost as M, share

        return share._status(M.clip_states(project, S.CID))
    except Exception:  # noqa: BLE001 - extra information only
        return None


def view(project: Project) -> dict:
    data = S.load(project)
    meta = project.load_meta()
    lang = S.language_of(project, data)
    live = S.active(data)
    words = S.texts(data, lang)
    autos = S.label_texts(len(live), lang)
    tl = S.timeline(len(live), data["seconds"], bool(data.get("outro")))
    photos = []
    for i, p in enumerate(live):
        photos.append({"id": p["id"], "name": p.get("name"), "width": p.get("width"), "height": p.get("height"),
                       "taken_at": p.get("taken_at"), "date_source": p.get("date_source"),
                       "text": p.get("text") or "", "shown_text": words[i], "label": autos[i],
                       "start": tl["segments"][i]["start"],
                       "shape": "portrait" if (p.get("height") or 0) > (p.get("width") or 0) * 1.05 else
                       "landscape" if (p.get("width") or 0) > (p.get("height") or 0) * 1.05 else "square"})
    removed = [{"id": p["id"], "name": p.get("name")} for p in data["photos"] if p.get("removed")]
    clip = _clip(project)
    prev = project.cache_dir / "slideshow_preview.mp4"
    prev_meta = meta.get("preview") or {}
    fp_prev = S.fingerprint(data, lang, S.W // S.PREVIEW_SCALE)
    fp_full = S.fingerprint(data, lang, S.W)
    return {
        "id": project.id, "title": meta.get("title") or project.id, "created_at": meta.get("created_at"),
        "language": lang, "settings": {k: data.get(k) for k in ("seconds", "transition", "labels", "outro",
                                                                 "order_mode", "subject")},
        "photos": photos, "removed": removed, "timeline": tl,
        "limits": {"min_photos": S.MIN_PHOTOS, "max_photos": S.MAX_PHOTOS, "seconds": [S.SECONDS_MIN, S.SECONDS_MAX],
                   "text_max": S.TEXT_MAX, "outro_s": S.OUTRO_S, "exts": sorted(S.EXTS),
                   "max_bytes": S.MAX_PHOTO_BYTES},
        "transitions": list(S.TRANSITIONS), "labels_words": list(S.LABELS.get(lang) or S.LABELS["en"]),
        "ready": S.MIN_PHOTOS <= len(live) <= S.MAX_PHOTOS,
        "preview": {"stamp": prev_meta.get("stamp"), "fresh": prev_meta.get("fingerprint") == fp_prev}
        if prev.is_file() else None,
        "export": {"stamp": clip.get("rendered_at"), "size_bytes": (project.dir / "clips" / clip["file"]).stat().st_size,
                   "duration": clip.get("duration"), "encoder": clip.get("encoder"),
                   "fresh": clip.get("fingerprint") == fp_full, "folder": meta.get("saved_folder")}
        if clip else None,
        "package": S.package(project, data), "share": _share_status(project) if clip else None,
        "jobs": _jobs(project),
    }


def row(project: Project) -> dict:
    data = S.load(project)
    meta = project.load_meta()
    live = S.active(data)
    clip = _clip(project)
    return {"id": project.id, "title": meta.get("title") or project.id, "created_at": meta.get("created_at"),
            "photos": len(live), "first": live[0]["id"] if live else None,
            "duration": S.duration(len(live), data["seconds"], bool(data.get("outro"))) if live else 0.0,
            "exported": bool(clip), "share": _share_status(project) if clip else None}


# ===================================================================== routes


@router.get("/api/slideshow")
def api_list() -> list[dict]:
    out = [row(p) for p in S.list_slideshows()]
    out.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    return out


@router.post("/api/slideshow")
def api_create(body: dict | None = Body(default=None)) -> dict:
    return view(S.create(str((body or {}).get("title") or "")))


@router.get("/api/slideshow/{pid}")
def api_view(pid: str) -> dict:
    return view(_project(pid))


@router.put("/api/slideshow/{pid}")
def api_settings(pid: str, body: dict | None = Body(default=None)) -> dict:
    project = _project(pid)
    body = body or {}
    data = S.load(project)
    if isinstance(body.get("order"), list):
        S.apply_order(data, [str(x) for x in body["order"]])
    if body.get("sort") == "date":
        S.sort_by_date(data)
    if "seconds" in body:
        data["seconds"] = S.clean_seconds(body["seconds"])
    if body.get("transition") in S.TRANSITIONS:
        data["transition"] = body["transition"]
    for k in ("labels", "outro"):
        if k in body:
            data[k] = bool(body[k])
    if "subject" in body:
        data["subject"] = S.clean_text(body["subject"])[:S.TEXT_MAX * 2]
    if isinstance(body.get("texts"), dict):
        for p in data["photos"]:
            if p["id"] in body["texts"]:
                p["text"] = S.clean_text(body["texts"][p["id"]])
    S.save(project, data)
    if isinstance(body.get("title"), str) and body["title"].strip():
        meta = project.load_meta()
        meta["title"] = " ".join(body["title"].split())[:80]
        project.save_meta(meta)
    return view(project)


@router.put("/api/slideshow/{pid}/photos")
async def api_add_photo(pid: str, request: Request, filename: str = Query(...),
                        modified: float | None = Query(None)) -> dict:
    project = _project(pid)
    try:
        declared = int(request.headers.get("content-length") or 0)
    except ValueError:
        declared = 0
    if declared > S.MAX_PHOTO_BYTES:
        raise SharkyClipsError("This photo is too big.", "Use a photo under 60 MB.")
    body = await request.body()
    photo = S.add_photo(project, filename, body, modified)
    return {"photo": photo["id"], "view": view(project)}


@router.post("/api/slideshow/{pid}/photos/{photo}/remove")
def api_remove(pid: str, photo: str) -> dict:
    project = _project(pid)
    S.remove_photo(project, photo, True)
    return view(project)


@router.post("/api/slideshow/{pid}/photos/{photo}/restore")
def api_restore(pid: str, photo: str) -> dict:
    project = _project(pid)
    S.remove_photo(project, photo, False)
    return view(project)


@router.get("/api/slideshow/{pid}/photos/{photo}/thumb")
def api_thumb(pid: str, photo: str):
    project = _project(pid)
    if not S.file_url_safe(photo):
        raise HTTPException(404)
    p = S.photos_dir(project) / f"{photo}.thumb.jpg"
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


def _submit(project: Project, preview: bool):
    A = _app()
    from . import jobs as J

    data = S.load(project)
    live = S.active(data)
    if len(live) < S.MIN_PHOTOS:
        raise SharkyClipsError(f"Add at least {S.MIN_PHOTOS} photos.")
    pid = project.id
    kind = "slideshow_preview" if preview else "slideshow_export"

    def run(job):
        project = get_project(pid)

        def prog(stage: str, frac: float) -> None:
            A.jobs.update(job, stage=stage, progress=frac)

        if preview:
            dest = project.cache_dir / "slideshow_preview.mp4"
            res = S.render(project, dest, preview=True, on_progress=prog)
            meta = project.load_meta()
            meta["preview"] = {"stamp": res["fingerprint"] + str(int(Path(dest).stat().st_mtime)),
                               "fingerprint": res["fingerprint"]}
            project.save_meta(meta)
            return {"duration": res["duration"], "seconds": res["seconds"]}
        dest = project.dir / "clips" / S.export_name(project)
        res = S.render(project, dest, on_progress=prog)
        S.write_clip(project, res)
        return {"duration": res["duration"], "encoder": res["encoder"], "seconds": res["seconds"],
                "size_bytes": res["size_bytes"]}

    with J.explicit():  # asked for by the user: a cancelled one may start again
        return A.jobs.submit(kind, "gpu", pid, {"photos": len(live)}, run,
                             key=f"{kind}:{pid}", front=preview)


@router.post("/api/slideshow/{pid}/preview")
def api_preview(pid: str) -> dict:
    return _submit(_project(pid), True).to_dict()


@router.post("/api/slideshow/{pid}/export")
def api_export(pid: str) -> dict:
    return _submit(_project(pid), False).to_dict()


@router.get("/api/slideshow/{pid}/preview.mp4")
def api_preview_file(pid: str):
    p = _project(pid).cache_dir / "slideshow_preview.mp4"
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4", headers={"Cache-Control": "no-store"})


@router.get("/api/slideshow/{pid}/video.mp4")
def api_video(pid: str):
    project = _project(pid)
    clip = _clip(project)
    if not clip:
        raise HTTPException(404)
    return FileResponse(project.dir / "clips" / clip["file"], media_type="video/mp4",
                        headers={"Cache-Control": "no-store"})


def _folder(project: Project) -> Path:
    return E.downloads_root() / E.safe_name(project.load_meta().get("title") or project.id, 80)


def save_copy(project: Project) -> dict:
    """The MP4 + a .txt with the title, description and hashtags, in Downloads/SharkyClips/<title>/."""
    clip = _clip(project)
    if not clip:
        raise SharkyClipsError("Export the slideshow first.")
    from .multipost import drafts
    from . import state

    A = _app()
    cand = state.effective_cand(A._cand(project, S.CID), state.load_review(project))
    d = drafts(project, cand)["youtube"]
    folder = _folder(project)
    folder.mkdir(parents=True, exist_ok=True)
    stem = E.safe_name(project.load_meta().get("title") or "slideshow", 60)
    mp4 = folder / f"{stem}.mp4"
    tmp = mp4.with_name(mp4.name + ".part")
    shutil.copyfile(project.dir / "clips" / clip["file"], tmp)
    from ..project import replace_retry

    replace_retry(tmp, mp4)
    txt = folder / f"{stem}.txt"
    from ..edit import brand

    txt.write_text(E.post_text(d["title"], d["description"], d["hashtags"],
                               brand.socials_block(S.language_of(project))), encoding="utf-8")
    meta = project.load_meta()
    meta["saved_folder"] = str(folder)
    project.save_meta(meta)
    return {"folder": str(folder), "files": [mp4.name, txt.name]}


@router.post("/api/slideshow/{pid}/save")
def api_save(pid: str) -> dict:
    return save_copy(_project(pid))


@router.post("/api/slideshow/{pid}/open-folder")
def api_open_folder(pid: str, request: Request) -> dict:
    project = _project(pid)
    folder = _folder(project)
    if not folder.is_dir():
        folder = Path(save_copy(project)["folder"])
    opened = E.open_folder(folder) if _app()._is_local(request) else False
    return {"folder": str(folder), "opened": opened}
