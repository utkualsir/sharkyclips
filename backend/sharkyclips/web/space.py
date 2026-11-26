"""1.2.68 "Free up space": after sharing, delete the stream video and the rendered files.

GET  /api/space/{project}       how many GB it frees, whether every clip is shared, what still waits
POST /api/space/{project}/free  {"confirm": true, "original": bool} -> trash.free_space (for good)

Never while something of this project is still being made or sent, or planned and not on the
platform yet (those posts need the files). The upload history and the posts stay.
"""

from __future__ import annotations

from fastapi import APIRouter, Body

from .. import trash
from ..errors import SharkyClipsError
from ..project import Project

router = APIRouter()

WAITING = ("scheduled", "preparing", "uploading", "processing")


def _cards(project: Project) -> list[dict]:
    from . import share

    return share.board(project)["clips"]


def view(project: Project, cards: list[dict] | None = None) -> dict:
    parts = trash.free_parts(project)
    cards = cards if cards is not None else _cards(project)
    waiting = []
    for c in cards:
        for p, st in (c.get("posts") or {}).items():
            if isinstance(st, dict) and st.get("status") in WAITING and not st.get("remote"):
                if p == "youtube" and st.get("status") == "scheduled" and st.get("url"):
                    continue  # already on YouTube with its release time: needs no file any more
                waiting.append({"clip_id": c["id"], "platform": p, "status": st["status"]})
    shared = [c for c in cards if (c.get("status") or {}).get("shared")]
    meta = project.load_meta()
    return {"bytes": parts["source_bytes"] + parts["render_bytes"], "source_bytes": parts["source_bytes"],
            "render_bytes": parts["render_bytes"], "original": parts["original"],
            "clips": len(cards), "shared": len(shared), "all_shared": bool(cards) and len(shared) == len(cards),
            "any_shared": bool(shared), "waiting": waiting, "freed_at": meta.get("space_freed_at"),
            "freed_bytes": meta.get("space_freed_bytes")}


def _project(pid: str) -> Project:
    from . import multipost as M

    return M._app()._project(pid)


@router.get("/api/space/{project_id}")
def api_view(project_id: str) -> dict:
    return view(_project(project_id))


@router.post("/api/space/{project_id}/free")
def api_free(project_id: str, body: dict | None = Body(default=None)) -> dict:
    body = body or {}
    if body.get("confirm") is not True:
        raise SharkyClipsError("Confirm first: this deletes the video files for good.")
    project = _project(project_id)
    v = view(project)
    if v["waiting"]:
        raise SharkyClipsError(f"{len(v['waiting'])} post(s) of this video still need its files.",
                               "Wait until they are sent, or cancel them, then free up the space.")
    res = trash.free_space(project.id, with_original=bool(body.get("original")))
    return {**res, "space": view(project)}
