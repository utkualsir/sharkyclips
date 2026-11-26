"""1.2.68: Upload history API, the "already shared" check, the video language, one-time migrations.

GET  /api/history?q=&platform=        every shared post (date, game, clip, platform, link), newest first
GET  /api/history/project/{project}   what was shared before from this project's source video
PUT  /api/projects/{project}/content-language  {"language": "tr"}  titles + descriptions in that
                                      language for this video (writes them again with the AI)
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, Body

from .. import config, history, languages
from ..errors import SharkyClipsError

router = APIRouter()


def _app():
    from . import app as appmod

    return appmod


@router.get("/api/history")
def api_history(q: str = "", platform: str | None = None, limit: int = 500) -> dict:
    return history.search(q, platform if platform in ("youtube", "tiktok", "reels") else None, limit)


@router.get("/api/history/project/{project_id}")
def api_history_project(project_id: str) -> dict:
    return history.for_project(_app()._project(project_id))


@router.put("/api/projects/{project_id}/content-language")
def api_content_language(project_id: str, body: dict | None = Body(default=None)) -> dict:
    A = _app()
    project = A._project(project_id)
    lang = str((body or {}).get("language") or "").strip()
    if languages.get(lang) is None:
        raise SharkyClipsError("This language isn't available for titles.")
    meta = project.load_meta()
    if not meta:
        raise SharkyClipsError("This project isn't ready yet.")
    lang = languages.get(lang).code
    meta["content_language"] = lang
    project.save_meta(meta)
    job = None
    if (project.dir / "highlights.json").is_file():  # write titles / descriptions again in that language
        job = A.submit_analyze(project.id, lang, meta_only=True)
    return {"language": lang, "job": job.to_dict() if job is not None else None}


# ===================================================================== start-up (once, in the background)


def migrate_tiktok_manual() -> bool:
    """1.2.68: automatic TikTok (TikTok Studio driven by SharkyClips) can stop at a TikTok check, so
    "by hand" is the default now. Done once; switching automatic back on stays one click."""
    if config.get("tiktok_manual_default_v1"):
        return False
    modes = dict(config.get("platform_modes") or {})
    changed = modes.get("tiktok") in ("browser", "api")
    if changed:
        modes["tiktok"] = "semi"
    config.update(platform_modes=modes, tiktok_manual_default_v1=True,
                  tiktok_was_auto=bool(changed))
    return changed


def startup() -> None:
    import os

    if os.environ.get("SHARKYCLIPS_PUBLISH_LOOP") == "0":  # tests call these themselves
        return

    def run() -> None:
        try:
            migrate_tiktok_manual()
        except Exception:  # noqa: BLE001
            pass
        try:
            history.backfill(_app().list_projects())
        except Exception:  # noqa: BLE001 - the history fills on the next start then
            pass

    threading.Thread(target=run, name="sharkyclips-history", daemon=True).start()
