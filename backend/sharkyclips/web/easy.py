"""Easy mode API (1.2.16): drop a video -> the best clips, rendered with smart defaults ->
one click to YouTube or to the Downloads folder. Pro mode keeps every screen it had.

Everything here drives the jobs Pro mode uses (render, upload, the publish plan); the only
new state is <project>/easy.json (easy.py). Included by app.py (before its /api 404).
"""

from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, Request

from .. import config, easy as E, publishing as P
from ..errors import SharkyClipsError
from ..project import MODES, Project
from . import state
from .jobs import ACTIVE, Job

router = APIRouter()
# Jobs that belong to "finding the clips" (the grid renders once they are all done)
PIPE = {"import", "transcribe", "highlights", "facecam", "voices", "proofread", "analyze", "proxy"}


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


# ===================================================================== clips of a project


def _hl(project: Project) -> dict:
    return state.load_highlights(project) or {}


def ranked(project: Project, hl: dict | None = None, review: dict | None = None) -> list[dict]:
    """Candidates, best first (the AI's viral score, else the highlight rank); discarded ones out."""
    hl = hl if hl is not None else _hl(project)
    review = review if review is not None else state.load_review(project, hl)
    rejected = set(review.get("rejected") or [])
    out = [c for c in hl.get("candidates", []) if c["id"] not in rejected]

    def key(c):  # the clips you marked live come first
        s = (c.get("publish") or {}).get("viral_score")
        return (not c.get("marked"), -(s if s is not None else -1), c["rank"])

    return sorted(out, key=key)


def _top(project: Project, data: dict, hl: dict | None = None, review: dict | None = None) -> list[dict]:
    return ranked(project, hl, review)[: data["shown"]]


_style_cache: dict = {"at": 0.0, "style": "statement"}


def _hook_style() -> str:
    if time.time() - _style_cache["at"] > 600:
        _style_cache.update(at=time.time(), style=E.hook_style())
    return _style_cache["style"]


def _music_ok() -> bool:
    try:
        from ..edit import music

        return bool(music.library())
    except Exception:  # noqa: BLE001
        return False


def _lang(project: Project) -> str | None:
    try:
        from ..project import read_json

        return read_json(project.transcript_path).get("language") if project.transcript_path.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def wanted(project: Project, cand: dict, data: dict, review: dict, style: str, music_ok: bool,
           lang: str | None) -> tuple[dict, str]:
    """(render options, hook text) Easy mode wants for this clip."""
    opts, hk = E.render_options(E.clip_prefs(data, cand["id"]), style, music_ok, E.fx_options(data))
    if hk == "question":
        from .. import abtest

        return opts, abtest.question_text(cand, lang)
    return opts, review["hooks"].get(cand["id"], "")


def _render_jobs(project_id: str) -> dict[str, Job]:
    """Latest render job per clip of this project."""
    out: dict[str, Job] = {}
    for j in sorted(_app().jobs.for_project(project_id), key=lambda j: j.created):
        if j.kind == "render":
            out[j.params.get("clip_id")] = j
    return out


def pipeline_busy(project_id: str) -> bool:
    return any(j.kind in PIPE and j.status in ACTIVE for j in _app().jobs.for_project(project_id))


def ensure_renders(project: Project, auto: bool = True, only: str | None = None) -> list[str]:
    """Queue a 9:16 render for every clip on the grid that isn't rendered with the Easy settings.
    auto=True (after a job ended) leaves clips whose last render failed alone (no retry loop)."""
    A = _app()
    hl = _hl(project)
    if not hl.get("candidates"):
        return []
    review = state.load_review(project, hl)
    data = E.load(project)
    clips = state.load_clips(project)
    rj = _render_jobs(project.id)
    style, music_ok, lang = _hook_style(), _music_ok(), _lang(project)
    out = []
    for c in _top(project, data, hl, review):
        if only and c["id"] != only:
            continue
        opts, hook = wanted(project, c, data, review, style, music_ok, lang)
        if A._render_is_current(clips.get(c["id"]), c, opts, hook, review):
            continue
        j = rj.get(c["id"])
        if j is not None and j.status in ACTIVE:
            continue  # it re-checks when this one ends
        if auto and j is not None and j.status == "error":
            continue
        A.submit_render_clip(project.id, c["id"], opts, hook, {"easy": True})
        out.append(c["id"])
    return out


def render_state(project: Project, cand: dict, data: dict, review: dict, clips: dict, rj: dict, style: str,
                 music_ok: bool, lang: str | None) -> dict:
    A = _app()
    j = rj.get(cand["id"])
    clip = clips.get(cand["id"])
    opts, hook = wanted(project, cand, data, review, style, music_ok, lang)
    current = A._render_is_current(clip, cand, opts, hook, review)
    st = {"status": "ready" if current else "waiting", "progress": None, "stamp": (clip or {}).get("rendered_at"),
          "has_video": bool(clip and (project.dir / "clips" / clip["file"]).is_file()), "error": None}
    if j is not None and j.status in ACTIVE:
        st.update(status="rendering" if j.status == "running" else "queued", progress=j.progress)
    elif not current and j is not None and j.status == "error":
        st.update(status="error", error=(j.error or {}).get("message"))
    return st


# ===================================================================== the upload side


def _plan_meta(project: Project, cand: dict, prefs: dict) -> dict:
    from .. import youtube
    from . import publishing as pub

    item = pub._item_for(project, cand["id"])
    review = state.load_review(project)
    meta = {**item["meta"], "source": "clip", "privacy": "public",
            "cover": {"kind": pub.default_cover_kind(project, cand["id"], review), "text": "", "burn": False}}
    if prefs.get("title"):
        meta["title"] = youtube.clean_text(prefs["title"], 100)
    return {**item, "meta": meta}


def clip_step(project: Project, cand: dict) -> tuple[str, dict]:
    """The publish loop's next step for an Easy clip: upload the rendered 9:16 clip itself."""
    j = _render_jobs(project.id).get(cand["id"])
    if j is not None and j.status in ACTIVE:
        return "wait", {}
    clip = state.load_clips(project).get(cand["id"])
    if clip and (project.dir / "clips" / clip["file"]).is_file():
        return "upload", {"source": "clip", "ab": None, "sig": "clip"}
    ensure_renders(project, auto=False, only=cand["id"])
    return "wait", {}


def _upload_state(project: Project, cid: str, item: dict | None, plan_jobs: dict, lock: str, now) -> dict:
    from . import publishing as pub

    key = P.key_of(project.id, cid)
    live = state.live_upload(project, cid)
    js = plan_jobs.get(key, [])
    st = pub.row_status(item, live, js, lock, now)
    up = next((j for j in js if j.kind == "upload"), None)
    return {**st, "url": (live or {}).get("url"), "views": (live or {}).get("views"),
            "publish_at": (item or {}).get("publish_at") or (live or {}).get("publish_at"),
            "progress": up.progress if up is not None and up.status == "running" else None,
            "error": (item or {}).get("error")}


def upload(project: Project, cid: str, when: str) -> dict:
    """One click: upload now (today's limit allowing) or put it on the automatic plan."""
    from .. import youtube
    from . import publishing as pub

    A = _app()
    cand = A._cand(project, cid)
    key = P.key_of(project.id, cid)
    live = state.live_upload(project, cid)
    if live:
        return {"status": "published", "url": live.get("url")}
    if any(j.kind == "upload" for j in pub._plan_jobs().get(key, [])):
        return {"status": "uploading"}
    if not youtube.connected():
        e = SharkyClipsError("Connect YouTube first.")
        e.code = "not_connected"  # type: ignore[attr-defined]
        raise e
    prefs = E.clip_prefs(E.load(project), cid)
    item = _plan_meta(project, cand, prefs)
    if when == "now":
        step, info = clip_step(project, cand)
        if step != "upload":
            raise SharkyClipsError("This clip is still being prepared.", "It uploads as soon as it's ready: try again in a moment.")
        rel = pub.releases()
        today = P.day_counts(rel, {key}).get(P.local_day(P.now_utc()), 0)
        if today < P.effective_limit():
            P.put({**P.unschedule(item), "meta": item["meta"], "prep": {}, "now": True})
            body = pub.upload_body(project, cand, P.get(key), "clip", None)
            body["thumbnail"] = "cover"
            A.submit_upload(project.id, cid, body)
            return {"status": "uploading"}
        when = "auto"  # today is full: the next free slot instead (said in the answer)
        P.put(item)
        res = pub.schedule([{"project_id": project.id, "clip_id": cid}], "auto")
        return {"status": "scheduled", "publish_at": (res["planned"] or [{}])[0].get("publish_at"), "today_full": True}
    P.put(item)
    res = pub.schedule([{"project_id": project.id, "clip_id": cid}], "auto")
    if not res["planned"]:
        raise SharkyClipsError("Couldn't plan this clip.", (res["skipped"] or [{}])[0].get("reason"))
    return {"status": "scheduled", "publish_at": res["planned"][0]["publish_at"]}


# ===================================================================== downloads


def download(project: Project, cid: str, folder: Path | None = None) -> dict:
    """MP4 + a .txt with title, description and hashtags + the cover as PNG."""
    from . import publishing as pub

    A = _app()
    cand = A._cand(project, cid)
    clip = state.load_clips(project).get(cid)
    src = project.dir / "clips" / clip["file"] if clip else None
    if src is None or not src.is_file():
        raise SharkyClipsError("This clip is still being prepared.", "Try again when its preview plays.")
    prefs = E.clip_prefs(E.load(project), cid)
    meta = pub.prefill(project, cand)
    title = prefs.get("title") or meta["title"]
    folder = folder or E.downloads_root() / E.safe_name(project.load_meta().get("title") or project.id, 80)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{cand['rank']:02d} {E.safe_name(title, 60)}"
    files = []
    mp4 = folder / f"{stem}.mp4"
    shutil.copyfile(src, mp4)
    files.append(mp4.name)
    txt = folder / f"{stem}.txt"
    txt.write_text(E.post_text(title, meta.get("description") or "", meta.get("hashtags") or []), encoding="utf-8")
    files.append(txt.name)
    note = None
    try:
        review = state.load_review(project)
        kind = pub.default_cover_kind(project, cid, review)
        img = pub.make_cover_for(project, state.effective_cand(cand, review), review, kind,
                                 (cand.get("publish") or {}).get("cover_text") or title, "tall", meta.get("language"))
        png = E.to_png(img, folder / f"{stem} - cover.png")
        files.append(png.name)
        from .. import aicovers

        if aicovers.has_chosen(project, cid, "wide"):  # the 16:9 version of the AI cover too
            wide = pub.make_cover_for(project, state.effective_cand(cand, review), review, "ai",
                                      (cand.get("publish") or {}).get("cover_text") or title, "wide",
                                      meta.get("language"))
            files.append(E.to_png(wide, folder / f"{stem} - cover 16x9.png").name)
    except SharkyClipsError as exc:
        note = exc.message
    return {"folder": str(folder), "files": files, "cover_error": note}


# ===================================================================== job listener


def _mark_import(job: Job) -> None:
    from ..project import get_project

    project = get_project(job.project_id)
    meta = project.load_meta()
    auto = bool(job.params.get("mode_auto"))
    if auto:
        src = meta.get("source") or {}
        mode = E.detect_mode(meta.get("title"), src.get("uploader"), src.get("description"))
        if mode != meta.get("mode"):
            meta["mode"] = mode
            project.save_meta(meta)
    E.save(project, easy=True, mode_auto=auto, created_at=state.now_iso(), fx=True)
    from .live import on_imported

    on_imported(job, project)


def _voices_ok() -> bool:
    try:
        from ..voices import models as vmodels

        return bool(vmodels.sherpa_ok())
    except Exception:  # noqa: BLE001
        return False


def on_job_finished(job: Job) -> None:
    """Keeps an Easy project moving: the voice pass after the highlights, then the renders of
    the best clips, then a "your clips are ready" notice (the tray shows it)."""
    pid = job.project_id
    if not pid:
        return
    from ..project import get_project

    if job.kind == "import" and job.status == "done" and job.params.get("easy"):
        _mark_import(job)
    try:
        project = get_project(pid)
    except SharkyClipsError:
        return
    data = E.load(project)
    if not data["easy"]:
        return
    if job.kind == "highlights" and job.status == "done" and _voices_ok():
        from .voices_api import submit_voices

        submit_voices(pid)  # every speaker in the captions (only the clip ranges)
    if job.kind not in PIPE | {"render"} or pipeline_busy(pid):
        return
    ensure_renders(project)
    hl = _hl(project)
    if not hl.get("candidates"):
        return
    rj = _render_jobs(pid)
    top = _top(project, data, hl)
    if any(rj.get(c["id"]) is not None and rj[c["id"]].status in ACTIVE for c in top):
        return
    if data.get("notified_for") == hl.get("created_at"):
        return
    clips = state.load_clips(project)
    n = sum(1 for c in top if c["id"] in clips)
    if n:
        E.save(project, notified_for=hl.get("created_at"))
        E.ready_notice(project.load_meta().get("title") or pid, n, f"/#/p/{pid}")
        from .live import on_clips_ready
        from .phone_api import on_clips_ready as phone_cards

        on_clips_ready(project, top)  # auto publish (auto clips)
        phone_cards(project, top)  # the paired phone gets the best ones


_installed: list = []


def install(jobs) -> None:
    if jobs in _installed:
        return
    _installed.append(jobs)
    jobs.on_finished.append(on_job_finished)


# ===================================================================== project view


STEP_KEYS = ("download", "transcribe", "find", "titles", "render")


def _steps(project: Project, hl: dict, top: list[dict], rstates: list[dict]) -> tuple[list[dict], float | None]:
    A = _app()
    js = [j for j in A.jobs.for_project(project.id) if j.status in ACTIVE]
    by = {}
    for j in js:
        by.setdefault(j.kind, j)
    has_t = project.transcript_path.is_file()
    has_h = bool(hl.get("candidates")) or (project.dir / "highlights.json").is_file()
    llm = A.llm_available()
    analyzed = not llm or any((c.get("publish") or {}).get("viral_score") is not None for c in hl.get("candidates", []))
    rendered = bool(top) and all(r["status"] in ("ready", "error") for r in rstates)

    def st(done: bool, *kinds: str) -> tuple[str, float | None]:
        j = next((by[k] for k in kinds if k in by), None)
        if j is not None:
            return "active", (j.progress if j.status == "running" else None)
        return ("done" if done else "todo"), None

    steps = []
    for key, done, kinds in (("download", True, ("import", "proxy")),
                             ("transcribe", has_t, ("transcribe",)),
                             ("find", has_h, ("highlights", "facecam", "voices", "proofread")),
                             ("titles", analyzed, ("analyze",)),
                             ("render", rendered, ("render",))):
        s, prog = st(done, *kinds)
        if key == "render" and s == "todo" and any(r["status"] in ("rendering", "queued") for r in rstates):
            s = "active"
        if key == "titles" and s == "todo" and has_h and not js:
            s = "done"  # the AI step ended without scores (it failed or was skipped): not blocking
        steps.append({"key": key, "status": s, "progress": prog})
    # a rough time estimate (whatever is left of each step)
    dur = float(project.load_meta().get("duration") or 0)
    speed = A.speeds.get("render")
    left = 0.0
    for s in steps:
        if s["status"] == "done":
            continue
        frac = 1 - (s["progress"] or 0)
        if s["key"] == "transcribe":
            left += max(20.0, dur * 0.12) * frac
        elif s["key"] == "find":  # + the voice pass: ~1.5x the clips' length on the CPU
            voices = _voices_ok() and not (project.dir / "voices.json").is_file()
            left += (40.0 + (1.5 * sum(float(c["duration"]) for c in top) if voices else 0)) * frac
        elif s["key"] == "titles":
            left += (25.0 * max(6, len(top))) * frac
        elif s["key"] == "render":
            todo = [r for r in rstates if r["status"] != "ready"] or top
            left += sum(2.0 + 30 * speed for _ in todo)
    busy = any(s["status"] == "active" for s in steps)
    return steps, (round(left) if busy or not rendered else None)


def view(project: Project) -> dict:
    from .. import youtube
    from . import publishing as pub

    A = _app()
    hl = _hl(project)
    review = state.load_review(project, hl)
    data = E.load(project)
    meta = project.load_meta()
    clips = state.load_clips(project)
    rj = _render_jobs(project.id)
    style, music_ok, lang = _hook_style(), _music_ok(), _lang(project)
    allc = ranked(project, hl, review)
    top = allc[: data["shown"]]
    items = P.load()
    pj = pub._plan_jobs()
    lock = youtube.lock_state()["state"]
    now = P.now_utc()
    dur = float(meta.get("duration") or 0)
    cards = []
    rstates = []
    for c in top:
        rs = render_state(project, c, data, review, clips, rj, style, music_ok, lang)
        rstates.append(rs)
        eff = state.effective_cand(c, review)
        prefs = E.clip_prefs(data, c["id"])
        pubd = c.get("publish") or {}
        key = P.key_of(project.id, c["id"])
        cards.append({
            "id": c["id"], "rank": c["rank"],
            "title": prefs["title"] or ((items.get(key) or {}).get("meta") or {}).get("title")
            or (pubd.get("titles") or [None])[0] or (c.get("text") or "")[:90],
            "titles": [t for t in (pubd.get("titles") or [])][:6], "text": (c.get("text") or "")[:200],
            "viral_score": pubd.get("viral_score"), "viral_label": state.viral_label(pubd.get("viral_score")),
            "start": eff["start"], "end": eff["end"], "duration": eff["duration"],
            "found": {"start": c["start"], "end": c["end"]},
            "bounds": {"start": max(0.0, c["start"] - 15), "end": min(dur or c["end"] + 15, c["end"] + 15)},
            "prefs": prefs, "render": rs,
            "upload": _upload_state(project, c["id"], items.get(key), pj, lock, now),
        })
    steps, eta = _steps(project, hl, top, rstates)
    active = [j for j in A.jobs.for_project(project.id) if j.status in ACTIVE]
    last = sorted(A.jobs.for_project(project.id), key=lambda j: j.created)
    err = None
    if not active and last and last[-1].status == "error" and last[-1].kind in PIPE:
        err = {"kind": last[-1].kind, **(last[-1].error or {})}
    working = any(s["status"] == "active" for s in steps)
    st = youtube.status()
    return {
        "id": project.id, "title": meta.get("title") or project.id, "mode": meta.get("mode") or "gaming",
        "mode_auto": data["mode_auto"], "duration": dur, "easy": data["easy"],
        "state": "working" if working else ("error" if err and not top else "ready" if top else "empty"),
        "steps": steps, "eta_seconds": eta, "error": err,
        "clips": cards, "total": len(allc), "shown": data["shown"], "music_available": music_ok,
        "youtube": {"connected": st["connected"], "lock": st["lock"]["state"], "channel": st["channel"]},
        "settings": E.settings(), "daily_limit": P.effective_limit(),
    }


def _project(pid: str) -> Project:
    return _app()._project(pid)


# ===================================================================== API


@router.get("/api/easy/settings")
def api_settings() -> dict:
    return E.settings()


@router.put("/api/easy/settings")
def api_settings_put(body: dict) -> dict:
    body = body or {}
    if "auto_clip" in body:
        from .live import enable_auto

        enable_auto(bool(body["auto_clip"]))
    return E.save_settings(body)


@router.get("/api/notices")
def api_notices(after: int = 0) -> dict:
    return E.notices(after)


@router.post("/api/easy/projects")
def api_create(body: dict, request: Request) -> dict:
    """Paste a link (or a local path): the whole pipeline starts; mode "auto" = detect it."""
    A = _app()
    source = str(body.get("url") or body.get("path") or "").strip()
    mode = body.get("mode") or "auto"
    language = body.get("language") or "auto"
    if mode != "auto" and mode not in MODES:
        raise SharkyClipsError(f"Unknown mode '{mode}'.")
    if not source:
        raise SharkyClipsError("Paste a video link or drop a file.")
    from ..ingest import is_url

    if not is_url(source):
        if not A._is_local(request):
            raise SharkyClipsError("Local file paths only work on the computer running SharkyClips.",
                                   "Drop the file instead.")
        if not Path(source).expanduser().is_file():
            raise SharkyClipsError(f"File not found: {source}")
    real = mode if mode != "auto" else (config.get("default_mode") or "gaming")
    title = source if is_url(source) else Path(source).name
    job = A.submit_import(source, real, language, title, extra={"easy": True, "mode_auto": mode == "auto"})
    return job.to_dict()


@router.get("/api/easy/projects")
def api_projects() -> list[dict]:
    A = _app()
    out = []
    for p in A.list_projects():
        meta = p.load_meta()
        data = E.load(p)
        hl = _hl(p)
        out.append({"id": p.id, "title": meta.get("title") or p.id, "created_at": meta.get("created_at"),
                    "duration": meta.get("duration"), "mode": meta.get("mode"), "easy": data["easy"],
                    "clips": len(hl.get("candidates") or []), "busy": pipeline_busy(p.id)})
    out.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return out


@router.get("/api/easy/projects/{project_id}")
def api_view(project_id: str) -> dict:
    return view(_project(project_id))


@router.post("/api/easy/projects/{project_id}/prepare")
def api_prepare(project_id: str) -> dict:
    """Open a project in Easy mode: it becomes an Easy project; missing renders are queued."""
    project = _project(project_id)
    if not E.load(project)["easy"]:
        E.save(project, easy=True, notified_for=_hl(project).get("created_at"))
    queued = [] if pipeline_busy(project.id) else ensure_renders(project, auto=False)
    return {"queued": queued, **view(project)}


@router.post("/api/easy/projects/{project_id}/more")
def api_more(project_id: str) -> dict:
    project = _project(project_id)
    data = E.load(project)
    E.save(project, shown=data["shown"] + E.SHOWN)
    if not pipeline_busy(project.id):
        ensure_renders(project, auto=False)
    return view(project)


@router.post("/api/easy/projects/{project_id}/mode")
def api_mode(project_id: str, body: dict) -> dict:
    """The content-type chip: find the clips again for gaming / study / music."""
    A = _app()
    project = _project(project_id)
    mode = body.get("mode")
    if mode not in MODES:
        raise SharkyClipsError(f"Unknown mode '{mode}'.")
    E.save(project, mode_auto=False, easy=True)
    if project.transcript_path.is_file():
        A.submit_highlights(project.id, mode=mode, force=True)
    else:
        meta = project.load_meta()
        meta["mode"] = mode
        project.save_meta(meta)
    return view(project)


@router.post("/api/easy/projects/{project_id}/retry")
def api_retry(project_id: str) -> dict:
    A = _app()
    project = _project(project_id)
    if not project.transcript_path.is_file():
        A.submit_transcribe(project.id)
    elif not (project.dir / "highlights.json").is_file():
        A.submit_highlights(project.id)
    else:
        ensure_renders(project, auto=False)
    return view(project)


@router.post("/api/easy/clips/{project_id}/{cid}/edit")
def api_edit(project_id: str, cid: str, body: dict) -> dict:
    """The simple edit sheet: title (from the AI's ideas or typed), trim, captions, music."""
    from .. import youtube

    A = _app()
    project = _project(project_id)
    cand = A._cand(project, cid)
    changes: dict = {}
    if "title" in body:
        t = youtube.clean_text(str(body.get("title") or ""), 100)
        changes["title"] = t or None
        item = P.get(P.key_of(project.id, cid))
        if item and t:
            P.put({**item, "meta": {**item["meta"], "title": t}})
    if "subtitles" in body:
        changes["subtitles"] = bool(body["subtitles"])
    if "music" in body:
        changes["music"] = bool(body["music"])
    if changes:
        E.set_clip_prefs(project, cid, **changes)
    if "start" in body or "end" in body:
        review = state.load_review(project)
        cur = dict(review["edits"].get(cid) or {})
        start = float(body.get("start", cur.get("start") or cand["start"]))
        end = float(body.get("end", cur.get("end") or cand["end"]))
        dur = float(project.load_meta().get("duration") or end)
        start, end = max(0.0, start), min(dur, end)
        if end - start < 3:
            raise SharkyClipsError("A clip needs at least 3 seconds.")
        if end - start > 180:
            raise SharkyClipsError("Shorts can be up to 3 minutes long.")
        cur["start"] = None if abs(start - cand["start"]) < 0.05 else round(start, 2)
        cur["end"] = None if abs(end - cand["end"]) < 0.05 else round(end, 2)
        state.save_review(project, {"edits": {**review["edits"], cid: cur}})
    ensure_renders(project, auto=False, only=cid)
    return view(project)


@router.post("/api/easy/clips/{project_id}/{cid}/discard")
def api_discard(project_id: str, cid: str) -> dict:
    A = _app()
    project = _project(project_id)
    A._cand(project, cid)
    review = state.load_review(project)
    state.save_review(project, {"rejected": list(dict.fromkeys([*review["rejected"], cid])),
                                "accepted": [c for c in review["accepted"] if c != cid]})
    if not pipeline_busy(project.id):
        ensure_renders(project, auto=False)  # the next best clip moves up into the grid
    return view(project)


@router.post("/api/easy/clips/{project_id}/{cid}/upload")
def api_upload(project_id: str, cid: str, body: dict | None = None) -> dict:
    when = (body or {}).get("when")
    when = when if when in E.WHEN else E.settings()["upload_when"]
    if (body or {}).get("remember") is not False:
        E.save_settings({"upload_when": when})
    return upload(_project(project_id), cid, when)


@router.post("/api/easy/upload")
def api_upload_many(body: dict) -> dict:
    """"Upload selected": now while today has room, the rest on the automatic plan."""
    when = body.get("when") if body.get("when") in E.WHEN else E.settings()["upload_when"]
    results = []
    for c in body.get("clips") or []:
        pid, cid = str(c.get("project_id") or ""), str(c.get("clip_id") or "")
        try:
            results.append({"project_id": pid, "clip_id": cid, **upload(_project(pid), cid, when)})
        except SharkyClipsError as exc:
            if getattr(exc, "code", None) == "not_connected":
                raise
            results.append({"project_id": pid, "clip_id": cid, "status": "error", "error": exc.message})
    return {"results": results}


@router.post("/api/easy/clips/{project_id}/{cid}/download")
def api_download(project_id: str, cid: str, request: Request) -> dict:
    res = download(_project(project_id), cid)
    if E.settings()["open_folder"] and _app()._is_local(request):
        res["opened"] = E.open_folder(Path(res["folder"]))
    return res


@router.post("/api/easy/projects/{project_id}/download")
def api_download_all(project_id: str, request: Request, body: dict | None = None) -> dict:
    """"Download all": every ready clip on the grid (+ one .zip when asked)."""
    project = _project(project_id)
    data = E.load(project)
    clips = state.load_clips(project)
    folder = None
    files: list[str] = []
    done = 0
    for c in _top(project, data):
        if c["id"] not in clips:
            continue
        res = download(project, c["id"])
        folder = Path(res["folder"])
        files += res["files"]
        done += 1
    if not done or folder is None:
        raise SharkyClipsError("No clip is ready yet.")
    zip_name = None
    if (body or {}).get("zip"):
        zp = folder / f"{E.safe_name(project.load_meta().get('title') or project.id, 60)}.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:  # MP4s don't compress
            for name in files:
                z.write(folder / name, name)
        zip_name = zp.name
    out = {"folder": str(folder), "files": files, "count": done, "zip": zip_name}
    if E.settings()["open_folder"] and _app()._is_local(request):
        out["opened"] = E.open_folder(folder)
    return out


@router.get("/api/easy/library")
def api_library() -> dict:
    """Three tabs: ready (rendered, not planned), planned, live (with views)."""
    from . import publishing as pub

    lib = pub.library_view()
    tabs: dict[str, list] = {"ready": [], "planned": [], "live": []}
    for r in lib["rows"]:
        row = {k: r.get(k) for k in ("key", "project_id", "project_title", "clip_id", "title", "duration",
                                     "viral_label", "status", "step", "date", "publish_at", "error")}
        row["url"] = (r.get("upload") or {}).get("url")
        row["views"] = (r.get("upload") or {}).get("views")
        row["job"] = r.get("job")
        if r["status"] in ("published", "locked"):
            tabs["live"].append(row)
        elif r["status"] in ("scheduled", "failed"):
            tabs["planned"].append(row)
        elif r.get("rendered"):
            tabs["ready"].append(row)
    tabs["live"].sort(key=lambda r: r.get("date") or "", reverse=True)
    return {"tabs": tabs, "youtube": lib["youtube"]}

