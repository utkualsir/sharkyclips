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

from .. import config, easy as E, publishing as P, shaping
from ..errors import SharkyClipsError
from ..project import MODES, Project
from . import state
from .jobs import ACTIVE, Job, automatic

router = APIRouter()
# Jobs that belong to "finding the clips" (the grid renders once they are all done)
PIPE = {"import", "transcribe", "highlights", "facecam", "voices", "proofread", "analyze", "proxy", "swearscan",
        "shape"}


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
    # 1.2.34 Easy 2.0: the creator's taste (👍 / 👎 + real views) moves clips that aren't
    # rendered or voted yet (a clip already on the grid never jumps away)
    fixed: set[str] = set()
    tm = None
    if E.load(project)["v2"]:
        from .. import taste

        tm = taste.model()
        if tm["votes"] >= taste.MIN_VOTES:
            fixed = set(state.load_clips(project)) | set(taste.votes_for(project.id))
        else:
            tm = None
    mode = hl.get("mode") or "gaming"

    def key(c):  # the clips you marked live come first
        s = (c.get("publish") or {}).get("viral_score")
        if tm is not None and c["id"] not in fixed:
            from .. import taste

            s = taste.adjust(s, taste.taste(c, mode, tm))
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

        return project.load_transcript().get("language") if project.transcript_path.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def wanted(project: Project, cand: dict, data: dict, review: dict, style: str, music_ok: bool,
           lang: str | None) -> tuple[dict, str]:
    """(render options, hook text) Easy mode wants for this clip."""
    prefs = E.clip_prefs(data, cand["id"])
    opts, hk = E.render_options(prefs, style, music_ok, E.fx_options(data))
    if data.get("v2"):  # Easy 2.0: pacing, the hook check, the banner, the Shorts safe zone
        from .. import hooks

        mode = project.load_meta().get("mode") or "gaming"
        sh = dict(shape_of(data, cand["id"]) or {})
        if E.v2_settings()["banner"] and prefs.get("banner") is None:  # follows new titles by itself
            sh["banner"] = hooks.banner_text(cand, (cand.get("publish") or {}).get("language") or lang)
        opts.update(E.v2_options(mode, sh, prefs, facecam=bool(review.get("facecam"))))
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


# ===================================================================== Easy 2.0: shaping


def shape_of(data: dict, cid: str) -> dict | None:
    return (data["clips"].get(cid) or {}).get("shape")


def apply_shapes(project: Project, clip_ids: list[str], on_progress=None) -> dict:
    """Context guard + length target (+ the hook check) for these clips: the trim goes into
    review.json (unless the user trimmed the clip), the reasons into easy.json."""
    hl = _hl(project)
    by = {c["id"]: c for c in hl.get("candidates") or []}
    mode = hl.get("mode") or project.load_meta().get("mode") or "gaming"
    data = E.load(project)
    review = state.load_review(project, hl)
    edits = dict(review["edits"])
    changed, shapes = 0, {}
    for k, cid in enumerate(clip_ids):
        cand = by.get(cid)
        if cand is None:
            continue
        old = shape_of(data, cid)
        auto = shaping.is_auto_trim(edits.get(cid), old, cand)
        try:
            info = shaping.shape_clip(project, cand, hl, mode)
        except Exception as exc:  # noqa: BLE001 - a clip that can't be shaped keeps its found cut
            info = {"v": shaping.SHAPE_VERSION, "base": shaping.base_of(cand), "start": cand["start"],
                    "end": cand["end"], "why": [], "target": shaping.target(mode, cand), "error": str(exc)[:200]}
        try:
            from .. import hooks as hookmod

            s, e = (info["start"], info["end"]) if auto else (state.effective_cand(cand, review)["start"],
                                                               state.effective_cand(cand, review)["end"])
            info.update(hookmod.check(project, cand, s, e, review, info, move=auto))
        except ImportError:
            pass
        except Exception as exc:  # noqa: BLE001 - the hook check is a bonus
            info["hook_error"] = str(exc)[:200]
        if auto:
            ne = shaping.edit_for(cand, info["start"], info["end"], edits.get(cid))
            if state.clean_edit(ne) != state.clean_edit(edits.get(cid)):
                changed += 1
            edits[cid] = ne
        shapes[cid] = info
        if on_progress:
            on_progress((k + 1) / max(1, len(clip_ids)))
    if changed:
        state.save_review(project, {"edits": edits})
    with E._lock:
        data = E.load(project)
        for cid, info in shapes.items():
            data["clips"][cid] = {**(data["clips"].get(cid) or {}), "shape": info}
        E.save(project, clips=data["clips"])
    return {"shaped": len(shapes), "trimmed": changed}


def submit_shape(project_id: str, clip_ids: list[str]) -> Job:
    A = _app()

    def run(job: Job):
        project = A.get_project(project_id)
        A.jobs.update(job, stage="shaping", progress=0.0)
        return apply_shapes(project, clip_ids, lambda f: A.jobs.update(job, progress=f))

    with automatic():
        return A.jobs.submit("shape", "io", project_id, {"clip_ids": clip_ids}, run, key=f"shape:{project_id}")


def ensure_renders(project: Project, auto: bool = True, only: str | None = None,
                   explicit: bool = False) -> list[str]:
    """Queue a 9:16 render for every clip on the grid that isn't rendered with the Easy settings.
    auto=True (after a job ended) leaves clips whose last render failed alone (no retry loop).
    A clip whose render the user cancelled stays as it is (1.2.24) unless explicit=True (the
    user pressed Try again / edited that clip)."""
    if not explicit:
        with automatic():
            return _ensure_renders(project, auto, only, False)
    return _ensure_renders(project, auto, only, True)


def _ensure_renders(project: Project, auto: bool, only: str | None, explicit: bool) -> list[str]:
    A = _app()
    hl = _hl(project)
    if not hl.get("candidates"):
        return []
    review = state.load_review(project, hl)
    data = E.load(project)
    top = _top(project, data, hl, review)
    if data["v2"]:  # Easy 2.0: shape the clips first (the renders follow when that job ends)
        mode = hl.get("mode") or project.load_meta().get("mode") or "gaming"
        ups = state.load_uploads(project) or {}
        # a new length target (the channel's views) reshapes the clips that aren't uploaded yet
        todo = [c["id"] for c in top if (not only or c["id"] == only) and shaping.needs_shape(
            shape_of(data, c["id"]), c, None if ups.get(c["id"]) else shaping.target(mode, c))]
        if todo:
            submit_shape(project.id, todo)
            return []
    clips = state.load_clips(project)
    rj = _render_jobs(project.id)
    style, music_ok, lang = _hook_style(), _music_ok(), _lang(project)
    out = []
    for c in top:
        if only and c["id"] != only:
            continue
        opts, hook = wanted(project, c, data, review, style, music_ok, lang)
        if A._render_is_current(clips.get(c["id"]), c, opts, hook, review, project):
            continue
        j = rj.get(c["id"])
        if j is not None and j.status in ACTIVE:
            continue  # it re-checks when this one ends
        if auto and j is not None and j.status == "error":
            continue
        if not explicit and A.jobs.is_cancelled("render", project.id, f"render:{project.id}:{c['id']}"):
            continue  # the user cancelled it: only they start it again
        job = A.submit_render_clip(project.id, c["id"], opts, hook, {"easy": True})
        if not job.blocked:
            out.append(c["id"])
    return out


def render_state(project: Project, cand: dict, data: dict, review: dict, clips: dict, rj: dict, style: str,
                 music_ok: bool, lang: str | None) -> dict:
    A = _app()
    j = rj.get(cand["id"])
    clip = clips.get(cand["id"])
    opts, hook = wanted(project, cand, data, review, style, music_ok, lang)
    current = A._render_is_current(clip, cand, opts, hook, review, project)
    st = {"status": "ready" if current else "waiting", "progress": None, "stamp": (clip or {}).get("rendered_at"),
          "has_video": bool(clip and (project.dir / "clips" / clip["file"]).is_file()), "error": None}
    if j is not None and j.status in ACTIVE:
        st.update(status="rendering" if j.status == "running" else "queued", progress=j.progress)
    elif not current and j is not None and j.status == "error":
        st.update(status="error", error=(j.error or {}).get("message"))
    st["bleeps"] = bleep_summary(clip)
    return st


def bleep_summary(clip: dict | None) -> dict | None:
    """1.2.31: the clip's bleep report in short (the "7 bleeps" badge), None before a check ran."""
    rep = ((clip or {}).get("edits") or {}).get("bleep_report")
    if not rep:
        return None
    audible = 0 if rep.get("error") else int(rep.get("audible") or 0)
    return {"expected": rep.get("expected"), "bleeped": rep.get("bleeped"), "audible": audible,
            "checked": (clip or {}).get("bleep_checked"), "hold": audible if not (clip or {}).get("bleep_checked") else 0,
            "error": bool(rep.get("error"))}


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
        if state.bleep_hold(project, cand["id"]):  # 1.2.31: a swear is still heard: the user checks first
            return "wait", {"reason": "bleep_check"}
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
    held = state.bleep_hold(project, cid)
    if held:
        e = SharkyClipsError(f"{held} swear(s) in this clip could not be bleeped.",
                             "Listen to the clip (Bleep report), then press \"I checked it\" to upload.")
        e.code = "bleep_check"  # type: ignore[attr-defined]
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
    from ..edit import brand

    socials = brand.socials_block(meta.get("language") or (cand.get("publish") or {}).get("language"))
    txt.write_text(E.post_text(title, meta.get("description") or "", meta.get("hashtags") or [], socials), encoding="utf-8")
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
    E.save(project, easy=True, mode_auto=auto, created_at=state.now_iso(), fx=True, v2=True)
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
    # 1.2.21 "Check swears strictly": the deep check on the clips Easy renders, before the renders
    deep = (job.kind == "voices" or (job.kind == "highlights" and not _voices_ok())) and job.status in ("done", "failed")
    if deep and E.extras_settings()["swear_strict"] == "auto":
        from .voices_api import submit_swearscan

        top = _top(project, data, _hl(project))
        if top:
            submit_swearscan(pid, clip_ids=[c["id"] for c in top])
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
                             ("render", rendered, ("shape", "render"))):
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


def _platform_state(project: Project, cid: str, recs: dict) -> dict:
    """TikTok / Reels per clip: the last post and a running export / upload job."""
    from . import platforms_api

    out = {}
    for p in ("tiktok", "reels"):
        j = platforms_api.active_job(project.id, cid, p)
        rec = recs.get(p) or {}
        out[p] = {"status": ("exporting" if j.kind == "platform_export" else "uploading") if j is not None
                  else rec.get("status"), "mode": rec.get("mode"), "file": rec.get("file"), "url": rec.get("url"),
                  "privacy": rec.get("privacy"), "error": rec.get("error"),
                  "progress": j.progress if j is not None and j.status == "running" else None,
                  "job": j.id if j is not None else None, "ai_voice": rec.get("ai_voice")}
    return out


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
    from .. import platforms as PF

    precs = PF.records(project)
    from .. import taste as taste_mod

    votes = taste_mod.votes_for(project.id)
    tm = taste_mod.model()
    mode_name = hl.get("mode") or meta.get("mode") or "gaming"
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
            "vote": votes.get(c["id"], 0), "taste": taste_mod.taste(c, mode_name, tm) if tm else None,
            "chips": shaping.reason_chips(c, 2 if (rs.get("bleeps") or {}).get("bleeped") else 3),
            "prefs": prefs, "render": rs, "shape": shape_card(data, c, eff, review, hl.get("mode") or meta.get("mode") or "gaming"),
            "upload": _upload_state(project, c["id"], items.get(key), pj, lock, now),
            "platforms": _platform_state(project, c["id"], precs.get(c["id"]) or {}),
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
        "settings": E.settings(), "daily_limit": P.effective_limit(), "smart": data["v2"],
        "taste": taste_mod.status(),
    }


def shape_card(data: dict, cand: dict, eff: dict, review: dict, mode: str) -> dict:
    """What the card says about the cut: why it moved, the length target, the hook check."""
    sh = shape_of(data, cand["id"]) or {}
    tgt = sh.get("target") or shaping.target(mode, cand)
    auto = shaping.is_auto_trim((review.get("edits") or {}).get(cand["id"]), sh or None, cand)
    out = {"why": list(sh.get("why") or []) if auto else [], "auto": auto, "target": tgt,
           "length": shaping.length_note(float(eff["duration"]), tgt), "shaped": bool(sh)}
    if sh.get("hook"):
        out["hook"] = sh["hook"]
    prefs = E.clip_prefs(data, cand["id"])
    if prefs.get("banner") is not None:
        out["banner"] = prefs["banner"]
    elif E.v2_settings()["banner"]:
        from .. import hooks

        out["banner"] = hooks.banner_text(cand, (cand.get("publish") or {}).get("language"))
    else:
        out["banner"] = ""
    return out


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
    if "autopilot" in body:
        from .. import autopilot

        autopilot.enable(bool(body["autopilot"]))
    return E.save_settings(body)


@router.get("/api/easy/autopilot")
def api_autopilot() -> dict:
    from .. import autopilot

    return autopilot.view()


@router.get("/api/easy/health")
def api_health(probe: bool = False) -> dict:
    """The YouTube connection pill: green / amber / red, a plain message and a one-tap fix."""
    from .. import autopilot

    return autopilot.health(probe=probe)


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
        ensure_renders(project, auto=False, explicit=True)  # "Try again"
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
    if "banner" in body:  # 1.2.34: None = the AI's headline, "" = no banner, else own text
        b = body.get("banner")
        changes["banner"] = None if b is None else " ".join(str(b).split())[:80]
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
    ensure_renders(project, auto=False, only=cid, explicit=True)  # the user changed this clip
    return view(project)


@router.post("/api/easy/clips/{project_id}/{cid}/nudge")
def api_nudge(project_id: str, cid: str, body: dict) -> dict:
    """One tap: start 3 s earlier / end 3 s later / short / long version / back to the smart cut."""
    A = _app()
    project = _project(project_id)
    cand = A._cand(project, cid)
    action = str((body or {}).get("action") or "")
    if action not in (*shaping.NUDGES, "auto"):
        raise SharkyClipsError(f"Unknown change '{action}'.")
    hl = _hl(project)
    mode = hl.get("mode") or project.load_meta().get("mode") or "gaming"
    review = state.load_review(project, hl)
    data = E.load(project)
    sh = shape_of(data, cid)
    eff = state.effective_cand(cand, review)
    if action == "auto":
        s, e = (sh["start"], sh["end"]) if sh else (cand["start"], cand["end"])
    else:
        duration = float(project.load_meta().get("duration") or eff["end"])
        lo, hi = shaping.limits(project, cand, hl, duration)
        ar = shaping.around(project, cand, eff["start"], eff["end"], mode)
        tgt = (sh or {}).get("target") or shaping.target(mode, cand)
        s, e = shaping.nudge(ar, cand, eff["start"], eff["end"], action, tgt, lo, hi)
        if abs(s - eff["start"]) < 0.05 and abs(e - eff["end"]) < 0.05:
            raise SharkyClipsError("This clip can't move further that way.",
                                   "It already touches the next clip or the end of the video.")
    edits = {**review["edits"], cid: shaping.edit_for(cand, s, e, review["edits"].get(cid))}
    state.save_review(project, {"edits": edits})
    ensure_renders(project, auto=False, only=cid, explicit=True)
    return view(project)


def caption_words(project: Project, cand: dict, review: dict) -> list[dict]:
    """The clip's caption words as the render shows them (AI + your fixes), swears masked."""
    from ..edit import profanity, proof
    from ..edit.plan import transcript_words

    eff = state.effective_cand(cand, review)
    words, lang = transcript_words(project, eff["start"], eff["end"])
    mine = dict(eff["edit"].get("captions") or {})
    fixed = proof.fix_words(words, lang, {**proof.cached_fixes(project, cand["id"]), **mine})
    swear = set(profanity.find_words(words, lang))
    out = []
    for i, (w, f) in enumerate(zip(words, fixed)):
        k = proof.key(w)
        out.append({"key": k, "word": profanity.mask(f["word"]) if i in swear else f["word"],
                    "start": round(w["start"], 2), "mine": k in mine, "swear": i in swear})
    return out


@router.get("/api/easy/clips/{project_id}/{cid}/captions")
def api_captions(project_id: str, cid: str) -> dict:
    A = _app()
    project = _project(project_id)
    cand = A._cand(project, cid)
    return {"words": caption_words(project, cand, state.load_review(project))}


@router.post("/api/easy/clips/{project_id}/{cid}/captions")
def api_caption_fix(project_id: str, cid: str, body: dict) -> dict:
    """Tap a wrong caption word, type it right: this clip is fixed (and made again) and the
    mistake is learned for every later clip."""
    from ..edit import proof
    from ..edit.plan import transcript_words

    A = _app()
    project = _project(project_id)
    cand = A._cand(project, cid)
    key, new = str((body or {}).get("key") or ""), " ".join(str((body or {}).get("word") or "").split())
    if not new:
        raise SharkyClipsError("Type the right word.", "To hide a word, cut it in Pro mode's transcript editor.")
    if len(new) > 40:
        raise SharkyClipsError("That's too long for one caption word.")
    review = state.load_review(project)
    eff = state.effective_cand(cand, review)
    words, lang = transcript_words(project, eff["start"], eff["end"])
    orig = next((w for w in words if proof.key(w) == key), None)
    if orig is None:
        raise SharkyClipsError("This word isn't in the clip any more.", "Close the sheet and open it again.")
    if next((x for x in caption_words(project, cand, review) if x["key"] == key), {}).get("swear"):
        raise SharkyClipsError("Bleeped words can't be retyped here.", "Pro mode's swear list decides what gets bleeped.")
    cur = dict(review["edits"].get(cid) or {})
    caps = dict(cur.get("captions") or {})
    if new == orig["word"]:
        caps.pop(key, None)
        learned = None
    else:
        caps[key] = new
        learned = proof.learn(orig["word"], new, lang)
    cur["captions"] = caps
    state.save_review(project, {"edits": {**review["edits"], cid: cur}})
    ensure_renders(project, auto=False, only=cid, explicit=True)
    return {"words": caption_words(project, cand, state.load_review(project)), "learned": learned}


@router.post("/api/easy/clips/{project_id}/{cid}/vote")
def api_vote(project_id: str, cid: str, body: dict) -> dict:
    """👍 / 👎 on a whole clip (0 = take it back): future picks learn the creator's taste."""
    from .. import taste

    A = _app()
    project = _project(project_id)
    cand = A._cand(project, cid)
    try:
        value = int((body or {}).get("value") or 0)
    except (TypeError, ValueError):
        raise SharkyClipsError("A vote is 1, -1 or 0.") from None
    hl = _hl(project)
    taste.vote(project.id, cand, hl.get("mode") or project.load_meta().get("mode") or "gaming", value)
    return view(project)


@router.post("/api/easy/projects/{project_id}/smart")
def api_smart(project_id: str, body: dict | None = None) -> dict:
    """Older projects: switch Easy 2.0's smart cuts on (or off) for this project."""
    project = _project(project_id)
    E.save(project, v2=(body or {}).get("on") is not False, easy=True)
    if not pipeline_busy(project.id):
        ensure_renders(project, auto=False, explicit=True)
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


@router.get("/api/easy/digest")
def api_digest() -> dict:
    """The weekly digest: published, views, the best one, what worked, one suggestion."""
    from .. import digest

    return digest.weekly()


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

