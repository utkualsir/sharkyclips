"""My style template API (1.2.63): Settings > My style (toggle, social block, channel tag, title
words, series numbers), Regenerate per field, and a project's episode number."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from ..errors import SharkyClipsError
from ..project import get_project
from ..titles import mytemplate

router = APIRouter()
FIELDS = ("title", "description", "hashtags")


def _project(project_id: str):
    try:
        return get_project(project_id)
    except SharkyClipsError:
        raise HTTPException(404, "No such project") from None


def _view() -> dict:
    t = mytemplate.load()
    return {"template": t, "exists": mytemplate.exists(), "strings": mytemplate.STRINGS.get(t["lang"]) or {},
            "games": [{"id": k, "name": v["name"], "story": bool(v.get("story"))} for k, v in mytemplate.GAMES.items()],
            "limits": {"title": mytemplate.TITLE_LIMIT, "options": mytemplate.TITLE_OPTIONS,
                       "hashtags": [mytemplate.HASHTAGS_MIN, mytemplate.HASHTAGS_MAX]}}


@router.get("/api/mystyle/template")
def api_template() -> dict:
    return _view()


@router.put("/api/mystyle/template")
def api_template_put(body: dict | None = Body(default=None)) -> dict:
    mytemplate.save(body or {})
    return _view()


@router.post("/api/projects/{project_id}/candidates/{cid}/regenerate/{field}")
def api_regenerate_field(project_id: str, cid: str, field: str) -> dict:
    """Write one field of a clip's publish package again: title (AI job), description (AI job)
    or hashtags (instant, from the clip's facts)."""
    from .. import analyze
    from . import jobs
    from .app import llm_available, submit_titles

    if field not in FIELDS:
        raise HTTPException(404, "No such field")
    project = _project(project_id)
    if field == "hashtags":
        pub = analyze.regenerate_hashtags(project, cid)
        return {"field": field, "hashtags": pub.get("hashtags") or [], "description": pub.get("description")}
    if not llm_available():
        raise SharkyClipsError("The local LLM isn't installed.", "Run: python cli.py doctor")
    if field == "title":
        return {"field": field, "job": submit_titles(project.id, cid).to_dict()}

    def run(job):
        jobs.update(job, stage="writing_description", progress=None)
        pub = analyze.regenerate_description(get_project(project.id), cid)
        return {"description": pub.get("description"), "clip_id": cid}

    job = jobs.submit("description", "gpu", project.id, {"clip_id": cid}, run, front=True)
    return {"field": field, "job": job.to_dict()}


@router.get("/api/projects/{project_id}/episode")
def api_episode(project_id: str) -> dict:
    from ..titles import banks

    project = _project(project_id)
    game = banks.project_game(project)
    gid = game.get("id") if game.get("known") else None
    ep = mytemplate.episode(project, gid, assign=False)
    return {"story": mytemplate.is_story(gid), "episode": ep, "game": game.get("name") or "",
            "enabled": mytemplate.load()["enabled"]}


@router.put("/api/projects/{project_id}/episode")
def api_episode_put(project_id: str, body: dict | None = Body(default=None)) -> dict:
    """{"n": 9} sets the episode number (null removes it); the series continues from it."""
    from ..titles import banks

    project = _project(project_id)
    game = banks.project_game(project)
    gid = game.get("id") if game.get("known") else None
    n = (body or {}).get("n")
    try:
        n = int(n) if n not in (None, "", 0) else None
    except (TypeError, ValueError):
        raise SharkyClipsError("The episode number must be a whole number.") from None
    ep = mytemplate.set_episode(project, n, gid)
    return {"story": mytemplate.is_story(gid), "episode": ep, "game": game.get("name") or "",
            "enabled": mytemplate.load()["enabled"]}
