"""API of the retention features (1.2.5): story clips, A/B hook variants + the hook test, and
the AI's polish of a seamless loop. Included by app.py (before its /api 404)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from .. import abtest, config, governor
from .. import story as story_mod
from ..clips import ClipOptions, Facecam, first_sentence, flash_from, render_clip
from ..errors import SharkyClipsError
from . import state
from .jobs import Job

router = APIRouter()


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ===================================================================== stories


def submit_story(project_id: str, lang: str | None = None) -> Job:
    A = _app()
    jobs = A.jobs

    def run(job: Job):
        from .. import llm

        project = A.get_project(project_id)
        jobs.update(job, stage="story_ideas", progress=None)

        def progress(stage: str) -> None:
            jobs.update(job, stage=stage, progress=None)

        if A.llm_available():
            with llm.lazy_session() as model:
                data = story_mod.propose(project, model, lang, on_progress=progress)
        else:
            data = story_mod.propose(project, None, lang, on_progress=progress)
        return {"stories": len(data["stories"]), "reason": data.get("reason")}

    return jobs.submit("story", "gpu", project_id, {"lang": lang}, run, key=f"story:{project_id}", front=True)


def submit_story_render(project_id: str, sid: str, job_id: str | None = None, attempt: int = 1) -> Job:
    A = _app()
    jobs = A.jobs
    project = A.get_project(project_id)
    st = story_mod.get(project, sid)

    def run(job: Job):
        project = A.get_project(project_id)
        st = story_mod.get(project, sid)
        review = state.load_review(project)
        opts = ClipOptions.from_dict(review["options"])
        facecam = Facecam.from_dict(review.get("facecam"))
        dest = project.dir / "stories" / f"{sid}.mp4"
        jobs.update(job, stage="rendering", progress=0.0)
        res = story_mod.render(project, st, opts, facecam, dest,
                               on_progress=lambda s: jobs.update(job, progress=min(1.0, s / max(st["duration"], 0.1))))
        data = story_mod.load(project)
        for s in data["stories"]:
            if s["id"] == sid:
                s["render"] = {"file": dest.name, "rendered_at": _now(), "size_bytes": res.size_bytes,
                               "encoder": res.encoder, "seconds": round(res.seconds, 1), "info": res.info}
        story_mod.save(project, data)
        return {"story": sid, "duration": res.info["duration"], "lufs": res.info["lufs"]}

    params = {"story_id": sid, "title": st.get("title") or sid, "duration": st["duration"],
              "project_title": project.load_meta().get("title") or project_id}
    return jobs.submit("story_render", "gpu", project_id, params, run, key=f"story_render:{project_id}:{sid}",
                       persist=True, job_id=job_id, attempt=attempt)


def _story_view(project, s: dict, lang: str | None) -> dict:
    out = {**s, "cut_text": story_mod.cut_text(project, s, lang)}
    r = s.get("render")
    if r and not (project.dir / "stories" / r["file"]).is_file():
        out["render"] = None
    return out


@router.get("/api/projects/{project_id}/stories")
def api_stories(project_id: str) -> dict:
    A = _app()
    project = A._project(project_id)
    data = story_mod.load(project)
    lang = project.load_meta().get("language")
    if project.transcript_path.is_file():
        from ..project import read_json

        lang = read_json(project.transcript_path).get("language") or lang
    active = next((j.to_dict() for j in A.jobs.for_project(project_id)
                   if j.kind in ("story", "story_render") and j.status in ("queued", "running")), None)
    return {**data, "stories": [_story_view(project, s, lang) for s in data["stories"]],
            "llm": A.llm_available(), "job": active, "limits": {"min": story_mod.MIN_TOTAL, "max": story_mod.MAX_TOTAL}}


@router.post("/api/projects/{project_id}/stories")
def api_story_propose(project_id: str, body: dict | None = None) -> dict:
    A = _app()
    project = A._project(project_id)
    if not (project.dir / "highlights.json").is_file():
        raise SharkyClipsError("Find the highlights first; stories are built from them.")
    return submit_story(project_id, (body or {}).get("lang") or None).to_dict()


@router.put("/api/projects/{project_id}/stories/{sid}")
def api_story_update(project_id: str, sid: str, body: dict) -> dict:
    project = _app()._project(project_id)
    s = story_mod.update(project, sid, body or {})
    return _story_view(project, s, None)


@router.delete("/api/projects/{project_id}/stories/{sid}")
def api_story_delete(project_id: str, sid: str) -> dict:
    return {"removed": story_mod.delete(_app()._project(project_id), sid)}


@router.post("/api/projects/{project_id}/stories/{sid}/render")
def api_story_render(project_id: str, sid: str) -> dict:
    return submit_story_render(project_id, sid).to_dict()


@router.get("/api/projects/{project_id}/stories/{sid}/video")
def api_story_video(project_id: str, sid: str, download: bool = False):
    project = _app()._project(project_id)
    s = story_mod.get(project, sid)
    path = project.dir / "stories" / f"{sid}.mp4"
    if not s.get("render") or not path.is_file():
        raise SharkyClipsError("Render this story first.")
    name = f"{project.id}_story_{sid}.mp4" if download else None
    return FileResponse(path, media_type="video/mp4", filename=name)


# ===================================================================== A/B hooks


def _clip_words(project, start: float, end: float) -> list[dict]:
    from ..edit.plan import transcript_words

    return transcript_words(project, start, end)[0]


def submit_ab(project_id: str, cid: str, job_id: str | None = None, attempt: int = 1) -> Job:
    """Render the clip's two hook variants and run the pre-test (hook model)."""
    A = _app()
    jobs = A.jobs
    project = A.get_project(project_id)
    cand0 = A._cand(project, cid)

    def run(job: Job):
        from ..project import read_json

        project = A.get_project(project_id)
        review = state.load_review(project)
        cand = state.effective_cand(A._cand(project, cid), review)
        opts = ClipOptions.from_dict(review["options"])
        facecam = review.get("facecam")
        meta = project.load_meta()
        spoken = read_json(project.transcript_path).get("language") if project.transcript_path.is_file() else None
        pub = cand.get("publish") or {}
        statement = review["hooks"].get(cid) or pub.get("hook_text") or first_sentence(cand.get("text") or "")
        words = _clip_words(project, cand["start"], cand["end"])
        obs = abtest.load_store()["observations"]
        pair = abtest.pick_pair({**cand, "id": cid}, obs)
        if opts.loop and "flash" in pair:  # no flash in a seamless loop: another style instead
            rest = [s for s in abtest.applicable(cand) if s not in pair]
            pair = [s for s in pair if s != "flash"] + rest[:1]
        flash_start = flash_from(float(cand.get("peak") or cand["start"]), float(meta.get("duration") or cand["end"]),
                                 float(meta.get("fps") or 30))
        variants: dict[str, dict] = {}
        for i, (label, style) in enumerate(zip("AB", pair)):
            spec = abtest.variant_spec(style, cand, statement, pub.get("language") or spoken, words)
            c2 = {**cand, "start": spec["start"], "duration": round(cand["end"] - spec["start"], 2)}
            o2 = ClipOptions.from_dict({**opts.to_dict(), "hook": True, "hook_text": spec["hook_text"],
                                        "hook_flash": spec["hook_flash"]})
            dest = project.dir / "clips" / "ab" / f"{cid}_{label}.mp4"
            jobs.update(job, stage="rendering_variant", progress=i / 2, detail={"variant": label})
            res = render_clip(project, c2, o2, Facecam.from_dict(facecam), dest,
                              on_progress=lambda s, i=i: jobs.update(job, progress=(i + min(1.0, s / max(c2["duration"], 0.1))) / 2))
            governor.checkpoint()
            jobs.update(job, stage="pretest", progress=None)
            feats = abtest.features(project, dest, spec, cand, facecam, spoken, meta.get("mode"), flash_start)
            variants[label] = {**spec, "file": dest.name, "features": feats, "rendered_at": _now(),
                               "dub": o2.dub or c2.get("dub") or "",
                               "size_bytes": res.size_bytes, "duration": res.info.get("duration") or c2["duration"]}
        judges: dict[str, dict | None] = {k: None for k in variants}
        if A.llm_available():
            from .. import llm

            try:
                with llm.lazy_session() as model:
                    for k, v in variants.items():
                        judges[k] = abtest.llm_judge(model, project, cand, v, v["features"], pub.get("language") or spoken)
            except SharkyClipsError:
                pass
        for k, v in variants.items():
            sc = abtest.score(v["features"], v["style"], obs, judges[k])
            v.update(score=sc["score"], reasons=sc["reasons"], judge=judges[k])
        winner = max(variants, key=lambda k: variants[k]["score"])
        other = "B" if winner == "A" else "A"
        entry = {"variants": variants, "winner": winner,
                 "margin": round(variants[winner]["score"] - variants[other]["score"], 1),
                 "created_at": _now(), "edit_fp": state.edit_fingerprint(A._cand(project, cid), review, opts.to_dict()),
                 "start": cand["start"], "end": cand["end"]}
        abtest.save_ab(project, cid, entry)
        return {"clip_id": cid, "winner": winner, "scores": {k: v["score"] for k, v in variants.items()},
                "styles": {k: v["style"] for k, v in variants.items()}}

    pubd = cand0.get("publish") or {}
    params = {"clip_id": cid, "rank": cand0["rank"], "duration": cand0["duration"] * 2,
              "title": (pubd.get("titles") or [None])[0] or cand0.get("text", "")[:90],
              "project_title": project.load_meta().get("title") or project_id}
    return jobs.submit("ab", "gpu", project_id, params, run, key=f"ab:{project_id}:{cid}", persist=True,
                       job_id=job_id, attempt=attempt)


def submit_hook_fetch() -> Job:
    A = _app()

    def run(job: Job):
        A.jobs.update(job, stage="fetching_stats", progress=None)
        return abtest.fetch_and_learn(A.list_projects())

    return A.jobs.submit("hook_fetch", "net", None, {}, run, key="hook_fetch")


def ab_view(project, cid: str, entry: dict, active: bool, obs: list[dict]) -> dict:
    review = state.load_review(project)
    try:
        cand = _app()._cand(project, cid)
        stale = entry.get("edit_fp") != state.edit_fingerprint(cand, review, review["options"])
    except SharkyClipsError:
        stale = True
    files_ok = all((project.dir / "clips" / "ab" / v["file"]).is_file() for v in entry["variants"].values())
    pick = abtest.choose_for_upload(entry, obs, active=active)
    upload = state.live_upload(project, cid)
    return {**entry, "stale": stale, "files_ok": files_ok, "upload_pick": pick,
            "uploaded": {"video_id": upload["video_id"], "variant": upload.get("hook_variant"),
                         "style": upload.get("hook_style"), "url": upload.get("url")} if upload else None}


@router.get("/api/projects/{project_id}/ab")
def api_ab(project_id: str) -> dict:
    project = _app()._project(project_id)
    rt = abtest.real_test_status()
    obs = abtest.load_store()["observations"]
    return {"clips": {cid: ab_view(project, cid, e, rt["active"], obs) for cid, e in abtest.load_ab(project).items()},
            "real_test": rt}


@router.post("/api/projects/{project_id}/clips/{cid}/ab")
def api_ab_create(project_id: str, cid: str) -> dict:
    A = _app()
    A._cand(A._project(project_id), cid)
    return submit_ab(project_id, cid).to_dict()


@router.delete("/api/projects/{project_id}/clips/{cid}/ab")
def api_ab_delete(project_id: str, cid: str) -> dict:
    project = _app()._project(project_id)
    entry = abtest.load_ab(project).get(cid)
    if entry:
        for v in entry["variants"].values():
            (project.dir / "clips" / "ab" / v["file"]).unlink(missing_ok=True)
    abtest.save_ab(project, cid, None)
    return {"removed": bool(entry)}


@router.get("/api/projects/{project_id}/clips/{cid}/ab/{label}/video")
def api_ab_video(project_id: str, cid: str, label: str, download: bool = False):
    project = _app()._project(project_id)
    entry = abtest.load_ab(project).get(cid) or {}
    v = (entry.get("variants") or {}).get(label.upper())
    path = project.dir / "clips" / "ab" / v["file"] if v else None
    if path is None or not path.is_file():
        raise SharkyClipsError("This hook variant isn't rendered (any more).")
    name = f"{project.id}_{cid}_{label.upper()}.mp4" if download else None
    return FileResponse(path, media_type="video/mp4", filename=name)


@router.get("/api/hooks")
def api_hooks() -> dict:
    from .. import youtube

    obs = abtest.load_store()["observations"]
    real = [o for o in obs if not o.get("simulated")]
    return {**abtest.stats(real), "real_test": abtest.real_test_status(), "youtube": {
        "connected": youtube.connected(), "analytics": youtube.has_analytics(), "locked": youtube.uploads_locked()},
        "min_age_hours": abtest.MIN_AGE_H, "styles_all": list(abtest.STYLES)}


@router.post("/api/hooks/fetch")
def api_hooks_fetch() -> dict:
    from .. import youtube

    if not youtube.connected():
        raise SharkyClipsError("Connect YouTube first (Settings > YouTube).")
    return submit_hook_fetch().to_dict()


def upload_source(project, cid: str, source: str) -> tuple[Path, dict] | None:
    """'ab:A' / 'ab:B' -> the rendered variant and its info, else None (not a variant)."""
    if not source.startswith("ab:"):
        return None
    label = source[3:].upper()
    entry = abtest.load_ab(project).get(cid) or {}
    v = (entry.get("variants") or {}).get(label)
    path = project.dir / "clips" / "ab" / v["file"] if v else None
    if path is None or not path.is_file():
        raise SharkyClipsError("This hook variant isn't rendered (any more).", "Make the A/B variants again.")
    return path, {"hook_variant": label, "hook_style": v["style"]}


# ===================================================================== seamless loop: the AI's polish


def polish_memes(project, cand: dict, opts: ClipOptions) -> None:
    """Before a render with meme effects: the local AI writes the short captions in the output
    language (cached per clip). Without the AI the built-in phrases are used."""
    if getattr(opts, "memes", "off") == "off" or config.get("llm_enabled") is False or not _app().llm_available():
        return
    from .. import llm
    from ..edit import fx

    if not fx.needs_captions(project, cand) or fx.cached_captions(project, cand):
        return
    try:
        with llm.lazy_session() as model:
            fx.write_captions(project, cand, model)
    except SharkyClipsError:
        pass


def polish_loop(project, cand: dict, opts: ClipOptions, max_len: float | None = None) -> None:
    """Before a loop render: let the local AI pick the seam and write a loop hook (cached;
    without the AI, or when it fails, the signal-based seam is used)."""
    A = _app()
    if not opts.loop or config.get("llm_enabled") is False or not A.llm_available():
        return
    from .. import llm
    from ..edit import loop
    from ..project import read_json

    spoken = read_json(project.transcript_path).get("language") if project.transcript_path.is_file() else None
    pub = cand.get("publish") or {}
    hook = opts.hook_text or pub.get("hook_text") or first_sentence(cand.get("text") or "")
    deleted = [(float(a), float(b)) for a, b in (cand.get("edit") or {}).get("deleted") or []]
    try:
        with llm.lazy_session() as model:
            loop.ai_polish(project, float(cand["start"]), float(cand["end"]), model, lang=pub.get("language") or spoken or "en",
                           hook_text=hook, max_len=float(max_len or loop.DEFAULT_MAX_SECONDS), deleted=deleted)
    except SharkyClipsError:
        pass
