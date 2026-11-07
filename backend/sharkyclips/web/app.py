"""SharkyClips web UI: REST API + live job events (SSE) + the built React app.

Start it with `python cli.py serve` (see cli.py). Everything stays on this computer;
with --lan other devices on the same network can use it too.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, config, governor, languages, startup
from ..clips import LAYOUTS, SUBTITLE_STYLES, ClipOptions, Facecam, first_sentence, render_clip
from ..errors import SharkyClipsError, require_tool
from ..highlights.modes import MODES as MODE_PRESETS
from ..project import MODES, Project, get_project, list_projects, read_json, slugify
from ..procs import no_window
from ..render import ENCODERS, pick_encoder
from . import state
from .auth import LOCAL_HOSTS, LanGuard
from .auth import router as _auth_router
from .jobs import ACTIVE, Job, JobManager
from .power import ShutdownTimer

FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"
REASON_CODES = ["loudness_spike", "keyword", "laughter", "shouting", "cheering", "fast_speech",
                "pause_then_burst", "steady_explanation", "chorus", "drop", "chat_spike", "chat_reactions",
                "llm_explanation", "marker"]
BROWSER_CODECS = {"h264", "av1", "vp9", "vp8"}
BROWSER_CONTAINERS = {".mp4", ".webm", ".m4v", ".mov"}

jobs = JobManager(store=config.workspace_dir() / "_queue.json")
power = ShutdownTimer(busy=jobs.busy, changed=jobs.bump)
jobs.on_finished.append(lambda _job: power.job_finished())
app = FastAPI(title="SharkyClips", version=__version__, docs_url="/api/docs", redoc_url=None)
app.state.lan_url = None
app.add_middleware(LanGuard)  # optional access PIN for other devices (--lan)


@app.exception_handler(SharkyClipsError)
async def _sharkyclips_error(_req: Request, exc: SharkyClipsError):
    body = {"error": exc.message, "hint": exc.hint}
    if getattr(exc, "code", None):
        body["code"] = exc.code  # type: ignore[attr-defined]
    return JSONResponse(body, status_code=400)


def _is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in LOCAL_HOSTS


def _project(project_id: str) -> Project:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", project_id):
        raise HTTPException(404, "No such project")
    try:
        project = get_project(project_id)
    except SharkyClipsError:
        raise HTTPException(404, "No such project") from None
    if project.id != project_id:
        raise HTTPException(404, "No such project")
    return project


# ===================================================================== pipeline


def _playable(project: Project) -> bool:
    src = project.source_path
    meta = project.load_meta()
    return bool(src and src.suffix.lower() in BROWSER_CONTAINERS
                and (meta.get("video_codec") or "").lower() in BROWSER_CODECS)


def _proxy_path(project: Project) -> Path:
    return project.dir / "cache" / "proxy.mp4"


def submit_transcribe(project_id: str, language: str = "auto", force: bool = False,
                      chain: bool = True) -> Job:
    def run(job: Job):
        from ..transcribe import transcribe_project

        jobs.update(job, stage="loading_model", progress=None)
        t = transcribe_project(get_project(project_id), lang=language,
                               model=config.get("transcribe_model") or "auto", force=force)
        return {"language": t.get("language"), "words": t["stats"]["words"]}

    then = (lambda _j: submit_highlights(project_id)) if chain else None
    return jobs.submit("transcribe", "gpu", project_id, {"language": language, "force": force},
                       run, then)


def submit_highlights(project_id: str, mode: str | None = None, force: bool = False) -> Job:
    def run(job: Job):
        from ..highlights import run_highlights

        project = get_project(project_id)
        jobs.update(job, stage="analyzing", progress=None)
        if mode:
            meta = project.load_meta()
            meta["mode"] = mode
            project.save_meta(meta)
        res = run_highlights(project, mode=mode, force=force, fetch_chat=False)
        return {"candidates": len(res["candidates"]), "mode": res["mode"]}

    def then(_job: Job):
        review = state.load_review(get_project(project_id))
        if not review["facecam_checked"]:
            submit_facecam(project_id)
        if llm_available() and config.get("auto_analyze") is not False:
            submit_analyze(project_id)  # titles, viral score, ... (cached per clip)

    return jobs.submit("highlights", "gpu", project_id, {"mode": mode, "force": force}, run, then)


def llm_available() -> bool:
    from .. import llm

    return config.get("llm_enabled") is not False and (llm.ollama_exe() is not None
                                                        or llm.server_version(0.3) is not None)


def submit_analyze(project_id: str, lang: str | None = None, force: bool = False,
                   job_id: str | None = None, attempt: int = 1, ranks: list[int] | None = None) -> Job:
    def run(job: Job):
        from ..analyze import analyze_project

        jobs.update(job, stage="loading_llm", progress=None)

        def progress(i: int, n: int, _c: dict) -> None:
            jobs.update(job, stage="llm_analyzing", progress=i / n, detail={"index": i, "count": n})

        res = analyze_project(get_project(project_id), out_lang=lang, force=force, on_progress=progress,
                              ranks=ranks)
        return {"language": res["language"], "model": res["model"], "seconds": res["total_seconds"],
                "count": len(res["candidates"]), "failed": res["failed"]}

    # persistent: a pause, restart or crash must not silently lose the publish packages
    key = f"analyze:{project_id}" + (f":{','.join(map(str, ranks))}" if ranks else "")
    return jobs.submit("analyze", "gpu", project_id, {"lang": lang, "force": force, "ranks": ranks}, run,
                       key=key, persist=True, job_id=job_id, attempt=attempt)


def submit_titles(project_id: str, cid: str) -> Job:
    def run(job: Job):
        from ..analyze import regenerate_titles

        jobs.update(job, stage="writing_titles", progress=None)
        return {"titles": regenerate_titles(get_project(project_id), cid)["titles"], "clip_id": cid}

    # interactive: goes ahead of a long render batch (it doesn't interrupt the running job)
    return jobs.submit("titles", "gpu", project_id, {"clip_id": cid}, run, front=True)


def submit_facecam(project_id: str, fresh: bool = False) -> Job:
    """Facecam: the layout remembered for this channel + resolution (checked on a few frames),
    else a full detection. fresh=True ("Detect again") ignores the remembered layout."""
    def run(job: Job):
        from ..facecam import detect_for_project

        project = get_project(project_id)
        jobs.update(job, stage="detecting_facecam", progress=None)
        res = detect_for_project(project, use_memory=not fresh)
        state.save_review(project, {"facecam": res["facecam"]})
        return res

    return jobs.submit("facecam", "io", project_id, {"fresh": fresh}, run)


def submit_chat(project_id: str, force: bool = False) -> Job:
    """Chat replay download (downloads lane: it can take minutes and needs no GPU)."""
    def run(job: Job):
        from ..chat import ensure_chat

        jobs.update(job, stage="downloading_chat", progress=None)
        data = ensure_chat(get_project(project_id), force=force)
        return {"status": data["status"], "count": data["count"], "reason": data.get("reason")}

    return jobs.submit("chat", "io", project_id, {"force": force}, run)


def submit_proxy(project_id: str) -> Job:
    def run(job: Job):
        from ..render import export_preview

        project = get_project(project_id)
        duration = float(project.load_meta().get("duration") or 0)
        jobs.update(job, stage="preparing_preview", progress=0)
        export_preview(project.source_path, 0, duration, _proxy_path(project),
                       on_progress=lambda s: jobs.update(job, progress=s / max(duration, 1)))

    return jobs.submit("proxy", "gpu", project_id, {}, run)


def submit_import(source: str, mode: str, language: str, title: str,
                  cleanup: Path | None = None, extra: dict | None = None) -> Job:
    def run(job: Job):
        from ..ingest import ingest

        jobs.update(job, stage="starting", progress=None)
        try:
            project = ingest(source, mode=mode)
        finally:
            if cleanup is not None:
                cleanup.unlink(missing_ok=True)  # the project keeps its own (hard-linked) copy
        job.project_id = project.id
        return {"project_id": project.id}

    def then(job: Job):
        pid = job.result["project_id"]
        project = get_project(pid)
        if not _playable(project) and not _proxy_path(project).is_file():
            submit_proxy(pid)
        if (project.load_meta().get("source") or {}).get("type") == "url":
            submit_chat(pid)  # runs alongside transcription
        if not project.transcript_path.is_file():
            submit_transcribe(pid, language)
        elif not (project.dir / "highlights.json").is_file():
            submit_highlights(pid)

    return jobs.submit("import", "io", None,
                       {"source": source, "title": title, "mode": mode, "language": language, **(extra or {})},
                       run, then, dedupe=False)


def submit_render_clip(project_id: str, cid: str, options: dict, hook: str = "",
                       batch: dict | None = None, job_id: str | None = None, attempt: int = 1) -> Job:
    """One 9:16 clip = one queue entry (so the queue can be reordered / retried per clip)."""
    project = get_project(project_id)
    hl = state.load_highlights(project) or {}
    cand = next((c for c in hl.get("candidates", []) if c["id"] == cid), None)
    if cand is None:
        raise SharkyClipsError(f"Clip {cid} doesn't exist any more.", "Re-run the highlight analysis.")
    opts = ClipOptions.from_dict({**options, "hook_text": hook})

    def run(job: Job):
        project = get_project(project_id)
        hl = state.load_highlights(project) or {}
        cand = next((c for c in hl.get("candidates", []) if c["id"] == cid), None)
        if cand is None:
            raise SharkyClipsError("This clip doesn't exist any more.",
                                   "Re-run the highlight analysis and pick clips again.")
        review = state.load_review(project, hl)
        facecam = Facecam.from_dict(review.get("facecam"))
        edit_fp = state.edit_fingerprint(cand, review, opts.to_dict())
        cand = state.effective_cand(cand, review)  # trims, transcript cuts, music choice
        name = f"{cand['rank']:02d}_{cand['id']}.mp4"
        if opts.loop:  # the local AI picks the seam and writes a loop hook (cached; optional)
            from .retention import polish_loop

            jobs.update(job, stage="loop_seam", progress=None)
            polish_loop(project, cand, opts)
        if opts.memes != "off":  # the meme captions in the output language (local AI, cached)
            from .retention import polish_memes

            jobs.update(job, stage="meme_captions", progress=None)
            polish_memes(project, cand, opts)
        jobs.update(job, stage="rendering", progress=0.0)
        res = render_clip(project, cand, opts, facecam, project.dir / "clips" / name,
                          on_progress=lambda s: jobs.update(job, progress=min(1.0, s / max(cand["duration"], 0.1))))
        warns: list[str] = []
        if verify_bleeps(job, project, cand, opts, project.dir / "clips" / name, warns):  # a bleep is off: once more
            jobs.update(job, stage="rendering_again", progress=0.0)
            res = render_clip(project, cand, opts, facecam, project.dir / "clips" / name,
                              on_progress=lambda s: jobs.update(job, progress=min(1.0, s / max(cand["duration"], 0.1))))
            if "bleep_missing" in warns:
                from ..voices import swearscan

                try:
                    if not swearscan.missing_bleeps(project, cand, opts, project.dir / "clips" / name):
                        warns.remove("bleep_missing")
                except Exception:  # noqa: BLE001
                    pass
        entry = {"file": name, "id": cand["id"], "rank": cand["rank"], "start": cand["start"],
                 "end": cand["end"], "duration": res.info.get("duration") or cand["duration"],
                 "options": opts.to_dict(), "edit_fp": edit_fp, "dub": opts.dub or cand.get("dub") or "",
                 "facecam": facecam.to_dict() if facecam else None,
                 "rendered_at": state.now_iso(), "size_bytes": res.size_bytes,
                 "render_seconds": round(res.seconds, 2), "encoder": res.encoder,
                 "edits": res.info or None,
                 "warnings": sorted(set(warns + list((res.info or {}).get("warnings") or []))) or None}
        state.save_clip(project, cand["id"], entry)
        speeds.record("render", res.seconds, cand["duration"])
        return {"clips": [cand["id"]], "encoder": res.encoder, "seconds": round(res.seconds, 1)}

    pub = cand.get("publish") or {}
    params = {"clip_id": cid, "rank": cand["rank"], "options": options, "hook": hook,
              "duration": cand["duration"], "title": (pub.get("titles") or [None])[0] or cand.get("text", "")[:90],
              "project_title": project.load_meta().get("title") or project_id, **(batch or {})}
    return jobs.submit("render", "gpu", project_id, params, run, key=f"render:{project_id}:{cid}",
                       persist=True, job_id=job_id, attempt=attempt)


def verify_bleeps(job: Job, project, cand: dict, opts: ClipOptions, path, warnings: list | None = None) -> bool:
    """After a render with bleeps: (1) every bleep must really be in the file (the tone / the
    silence), (2) Strict / Paranoid: no swear may still be heard (Whisper listens again). True
    when the clip must be rendered again (once). Problems go into `warnings` (shown on the clip);
    this never fails the render."""
    from ..edit import swears

    if config.get("swear_verify_render") is False or os.environ.get("SHARKYCLIPS_NO_BLEEP_CHECK"):
        return False
    if opts.profanity == "off":
        return False
    warnings = warnings if warnings is not None else []
    try:
        from ..voices import swearscan

        jobs.update(job, stage="checking_bleeps", progress=None)
        if swearscan.missing_bleeps(project, cand, opts, path):
            warnings.append("bleep_missing")
            return True
        if swears.resolve_strictness(opts.swear_strict, True) == "normal":
            return False
        if swearscan.verify_render(project, cand, opts, path):
            warnings.append("bleep_widened")
            return True
        return False
    except Exception as exc:  # noqa: BLE001 - the clip is fine as rendered
        from ..ui import console

        console.print(f"[yellow]Bleep check skipped: {exc}[/]")
        warnings.append("bleep_check_skipped")
        return False


def submit_render(project_id: str, clip_ids: list[str], options: ClipOptions,
                  hooks: dict[str, str]) -> list[Job]:
    opts = options.to_dict()
    opts.pop("hook_text", None)
    batch = f"b{int(time.time() * 1000)}"
    out = []
    for i, cid in enumerate(clip_ids):
        out.append(submit_render_clip(project_id, cid, opts, hooks.get(cid, ""),
                                      {"batch": batch, "batch_index": i + 1, "batch_count": len(clip_ids)}))
    return out


def submit_montage(project_id: str, clip_ids: list[str], intro: bool = True, outro: bool = True,
                   cards: bool = True, lang: str | None = None, job_id: str | None = None,
                   attempt: int = 1) -> Job:
    from .. import montage

    project = get_project(project_id)
    hl = state.load_highlights(project) or {}
    by_id = {c["id"]: c for c in hl.get("candidates", [])}
    ids = [c for c in clip_ids if c in by_id][: montage.MAX_CLIPS]
    if len(ids) < 2:
        raise SharkyClipsError("Pick at least two clips for a best-of video.")
    video_s = (sum(by_id[c]["duration"] for c in ids) + len(ids) * montage.CARD_S * cards
               + montage.INTRO_S * intro + montage.OUTRO_S * outro)

    def run(job: Job):
        def progress(stage: str, frac: float | None) -> None:
            jobs.update(job, stage=stage, progress=frac)

        info = montage.render_montage(get_project(project_id), ids, lang=lang, intro=intro, outro=outro,
                                      cards=cards, on_progress=progress)
        speeds.record("montage", info["render_seconds"], info["duration"])
        return {"export": info["name"], "duration": info["duration"], "encoder": info["encoder"]}

    params = {"clip_ids": ids, "intro": intro, "outro": outro, "cards": cards, "lang": lang,
              "count": len(ids), "duration": round(video_s, 1),
              "project_title": project.load_meta().get("title") or project_id}
    return jobs.submit("montage", "gpu", project_id, params, run, dedupe=False, persist=True,
                       job_id=job_id, attempt=attempt)


def submit_benchmark() -> Job:
    def run(job: Job):
        from ..analyze import benchmark

        project = next((p for p in sorted(list_projects(), key=lambda p: p.load_meta().get("updated_at") or "",
                                          reverse=True)
                        if (p.dir / "highlights.json").is_file() and p.transcript_path.is_file()), None)
        if project is None:
            raise SharkyClipsError("Import a video and find its highlights first; the speed test uses its best clip.")

        def progress(profile: str, i: int, n: int) -> None:
            jobs.update(job, stage=f"benchmark_{profile}", progress=i / n)

        return benchmark(project, progress)

    return jobs.submit("benchmark", "gpu", None, {}, run, key="benchmark")


def _cand(project: Project, cid: str) -> dict:
    hl = state.load_highlights(project) or {}
    cand = next((c for c in hl.get("candidates", []) if c["id"] == cid), None)
    if cand is None:
        raise SharkyClipsError("This clip doesn't exist any more.", "Re-run the highlight analysis and pick clips again.")
    return cand


def submit_export(project_id: str, cid: str, request: dict, batch: dict | None = None,
                  job_id: str | None = None, attempt: int = 1) -> Job:
    """One clip in one export format / preset (+ subtitle files, editor timelines)."""
    from .. import export

    project = get_project(project_id)
    cand = _cand(project, cid)
    req = export.ExportRequest.from_dict(request)

    def run(job: Job):
        from ..analyze import translate_clip

        project = get_project(project_id)
        review = state.load_review(project)
        cand = state.effective_cand(_cand(project, cid), review)
        opts = ClipOptions.from_dict({**review["options"], "hook_text": review["hooks"].get(cid, "")})
        facecam = Facecam.from_dict(review.get("facecam"))

        def progress(stage: str, frac: float | None) -> None:
            jobs.update(job, stage=stage, progress=frac)

        def translate(lang: str) -> list[dict]:
            if not llm_available():
                raise SharkyClipsError(f"Subtitles in {lang} need the local AI to translate them.",
                                       "Install it with: python cli.py doctor")
            jobs.update(job, stage="translating", progress=None)
            return translate_clip(project, cid, lang)

        entry = export.run_export(project, cand, opts, facecam, req, progress, translate)
        if req.format:
            speeds.record("export", entry["seconds"], cand["duration"])
        return {"export": entry["id"], "files": [f["name"] for f in entry["files"]],
                "bytes": sum(f["size_bytes"] for f in entry["files"]), "seconds": entry["seconds"],
                "encoder": entry["encoder"], "warnings": entry["warnings"]}

    pub = cand.get("publish") or {}
    params = {"clip_id": cid, "rank": cand["rank"], "request": req.to_dict(), "duration": cand["duration"],
              "title": (pub.get("titles") or [None])[0] or cand.get("text", "")[:90],
              "project_title": project.load_meta().get("title") or project_id, **(batch or {})}
    key = f"export:{project_id}:{cid}:{export.export_stem(cand, req)}"
    return jobs.submit("export", "gpu", project_id, params, run, key=key, persist=True, job_id=job_id,
                       attempt=attempt)


def _upload_source(project: Project, cid: str, source: str) -> Path:
    """'clip' = the rendered 9:16 clip, 'ab:A' / 'ab:B' = a hook variant, else the name of an
    export file of this clip."""
    from .. import export
    from .retention import upload_source

    ab = upload_source(project, cid, source)
    if ab is not None:
        return ab[0]
    if source == "clip":
        clip = state.load_clips(project).get(cid)
        if not clip:
            raise SharkyClipsError("Render this clip first (or export it with a YouTube preset).")
        return project.dir / "clips" / clip["file"]
    path = export.file_path(project, source)
    if path is None or path.suffix.lower() not in (".mp4", ".mov", ".webm"):
        raise SharkyClipsError("Pick a video file of this clip to upload.")
    return path


def submit_upload(project_id: str, cid: str, body: dict, job_id: str | None = None, attempt: int = 1) -> Job:
    """YouTube upload (network lane: runs while the GPU renders)."""
    from .. import youtube

    from .. import abtest
    from .retention import upload_source

    project = get_project(project_id)
    cand = _cand(project, cid)
    source = str(body.get("source") or "clip")
    path = _upload_source(project, cid, source)
    _never_twice(project, cid, job_id)
    mode = project.load_meta().get("mode") or "gaming"
    # The hook style this upload tests (A/B variant, or the plain clip's own style).
    ab = upload_source(project, cid, source)
    if ab is not None:
        hook = {**ab[1], "hook_chosen_by": str(body.get("ab_how") or "manual")[:12]}
    elif isinstance(body.get("hook_override"), dict):  # a variant with the cover burned in (Library)
        o = body["hook_override"]
        hook = {"hook_style": o.get("hook_style"), "hook_variant": o.get("hook_variant"),
                "hook_chosen_by": str(o.get("hook_chosen_by") or "manual")[:12]}
    else:
        review = state.load_review(project)
        clip = state.load_clips(project).get(cid) or {}
        o = clip.get("options") or review["options"]
        text = (o.get("hook_text") if clip else None) or review["hooks"].get(cid) or (cand.get("publish") or {}).get("hook_text") or ""
        hook = {"hook_style": abtest.style_of(o, text), "hook_variant": None, "hook_chosen_by": "clip"}
    ai_voice = ai_voice_disclosure(project, cid, source, body)
    yt = youtube.build_body(str(body.get("title") or ""),
                            youtube.with_note(str(body.get("description") or ""), ai_voice["line"] if ai_voice["note"] else None),
                            [str(t) for t in body.get("tags") or []], str(body.get("privacy") or "private"),
                            body.get("publish_at") or None, bool(body.get("made_for_kids")),
                            str(body.get("category")) if str(body.get("category") or "") in youtube.CATEGORIES
                            else youtube.CATEGORY.get(mode, "20"), body.get("language") or None,
                            synthetic=bool(ai_voice["synthetic"]))
    thumb = str(body.get("thumbnail") or "none")  # none | auto | custom
    plan_key = body.get("plan_key")  # a clip of the publishing plan (Library / scheduler)

    def run(job: Job):
        if not plan_key:
            return _run(job)
        from . import publishing

        try:
            return _run(job)
        except BaseException as exc:
            publishing.on_failed(plan_key, exc)
            raise

    def _run(job: Job):
        from .. import youtube

        project = get_project(project_id)
        live = state.live_upload(project, cid)
        if live:  # e.g. the other A/B variant was uploaded meanwhile
            raise SharkyClipsError("This clip is already on YouTube: SharkyClips uploads each clip once.",
                                   f"It is here: {live.get('url')}")
        jobs.update(job, stage="uploading", progress=0.0)
        key = f"{project_id}:{cid}:{path.name}:{path.stat().st_size}"
        video = youtube.upload(path, yt, key, on_progress=lambda f: jobs.update(job, progress=f),
                               checkpoint=governor.checkpoint)
        vid = video.get("id")
        if not vid:
            raise SharkyClipsError("YouTube didn't return a video ID.")
        thumb_note = None
        if thumb != "none":
            jobs.update(job, stage="thumbnail", progress=None)
            try:
                img = _thumbnail_file(project, cid, cand, thumb)
                youtube.set_thumbnail(vid, img)
            except SharkyClipsError as exc:  # the video is up; a missing thumbnail is only a note
                thumb_note = exc.message + (f" {exc.hint}" if exc.hint else "")
        st = video.get("status") or {}
        requested = yt["status"]["privacyStatus"]
        got = st.get("privacyStatus") or requested
        if requested in ("public", "unlisted") and not yt["status"].get("publishAt"):
            if got == "private":
                youtube.mark_locked(vid)  # Google keeps uploads of an unaudited project private
            else:
                youtube.mark_unlocked(vid)
        entry = {"video_id": vid, "url": f"https://youtu.be/{vid}", "title": yt["snippet"]["title"],
                 "privacy": got, "requested_privacy": requested,
                 "publish_at": yt["status"].get("publishAt"), "file": path.name, "uploaded_at": state.now_iso(),
                 "made_for_kids": yt["status"]["selfDeclaredMadeForKids"], "thumbnail_error": thumb_note, **hook}
        if ai_voice["dub"]:  # kept when the description is edited later (Library)
            entry["ai_voice"] = ai_voice
        state.save_upload(project, cid, entry)
        if plan_key:
            from . import publishing

            extra = publishing.on_uploaded(plan_key, entry, body)
            if extra:
                state.patch_upload(project, cid, vid, extra)
                entry.update(extra)
        return {**entry, "clip_id": cid}

    params = {"clip_id": cid, "rank": cand["rank"], "body": body, "duration": cand["duration"],
              "title": yt["snippet"]["title"], "file": path.name, "size_bytes": path.stat().st_size,
              "project_title": project.load_meta().get("title") or project_id,
              "publish_at": yt["status"].get("publishAt")}
    if plan_key:
        params["plan_key"] = plan_key
    return jobs.submit("upload", "net", project_id, params, run, key=f"upload:{project_id}:{cid}:{path.name}",
                       persist=True, job_id=job_id, attempt=attempt)


def ai_voice_disclosure(project: Project, cid: str, source: str, body: dict | None = None) -> dict:
    """1.2.19: a dubbed video (the user's voice made by AI in another language) says so: a line in
    the description (in the dub language) and YouTube's altered / synthetic content flag. Both on
    unless the upload switched them off ("ai_voice_note" / "synthetic_media": false)."""
    from .. import dub

    body = body or {}
    lang = state.file_dub(project, cid, source)
    return {"dub": lang, "line": dub.disclosure_line(lang) if lang else None,
            "note": bool(lang) and body.get("ai_voice_note") is not False,
            "synthetic": bool(lang) and body.get("synthetic_media") is not False}


@app.get("/api/projects/{project_id}/clips/{cid}/ai_voice")
def api_ai_voice(project_id: str, cid: str, source: str = "clip") -> dict:
    """What an upload of this file says about its AI voice (the upload screen shows it)."""
    project = get_project(project_id)
    _cand(project, cid)
    return ai_voice_disclosure(project, cid, source)


def _never_twice(project: Project, cid: str, job_id: str | None) -> None:
    """A clip goes to YouTube once: not again, and not its other A/B variant."""
    live = state.live_upload(project, cid)
    if live:
        raise SharkyClipsError("This clip is already on YouTube: SharkyClips uploads each clip once.",
                               f"It is here: {live.get('url')} (the A/B test compares hook styles across different clips).")
    for j in jobs.jobs():
        if (j.kind == "upload" and j.project_id == project.id and j.params.get("clip_id") == cid
                and j.status in ("queued", "running") and j.id != job_id):
            raise SharkyClipsError("This clip is already being uploaded.", "See the queue.")


def _thumbnail_file(project: Project, cid: str, cand: dict, kind: str) -> Path:
    custom = project.cache_dir / "thumbnails" / f"{cid}.jpg"
    if kind == "custom" and custom.is_file():
        return custom
    if kind == "cover":  # Easy mode: the 9:16 cover (best facecam face, else the peak) with the title
        from .. import publishing as P
        from .publishing import default_cover_kind, make_cover_for

        review = state.load_review(project)
        meta = (P.get(P.key_of(project.id, cid)) or {}).get("meta") or {}
        text = (cand.get("publish") or {}).get("cover_text") or meta.get("title") or ""
        return make_cover_for(project, state.effective_cand(cand, review), review,
                              default_cover_kind(project, cid, review), text, "tall", meta.get("language"))
    t = round(float(cand.get("peak") or cand["start"]), 1)
    return _frame(project, t, 1280, project.cache_dir / "frames" / f"1280_{t:.1f}.jpg")


STATS_MIN_AGE_H = 48  # calibration learns from public videos that had two days to find viewers


def submit_youtube_stats(force: bool = False) -> Job:
    """Fetch views of every uploaded clip; public ones older than 2 days calibrate the score."""
    from .. import calibration, youtube

    def run(job: Job):
        jobs.update(job, stage="fetching_stats", progress=None)
        ids: dict[str, tuple[Project, str]] = {}
        for p in list_projects():
            for cid, ups in state.load_uploads(p).items():
                for u in ups:
                    if u.get("video_id"):
                        ids[u["video_id"]] = (p, cid)
        if not ids:
            return {"videos": 0, "calibrated": 0}
        stats = youtube.video_stats(list(ids))
        now = datetime.now(timezone.utc)
        for vid, (p, cid) in ids.items():
            if vid not in stats:  # deleted on YouTube: the clip may be uploaded again
                state.patch_upload(p, cid, vid, {"missing": True})
                continue
            # Is Google still keeping this project's uploads private? (unaudited API project)
            u = next((x for x in state.load_uploads(p).get(cid, []) if x.get("video_id") == vid), {})
            got = stats[vid].get("privacy")
            try:
                pa = datetime.fromisoformat(str(u.get("publish_at")).replace("Z", "+00:00")) if u.get("publish_at") else None
            except ValueError:
                pa = None
            wanted_now = (u.get("requested_privacy") or "") in ("public", "unlisted") and pa is None
            if got in ("public", "unlisted") and (wanted_now or pa is not None):
                youtube.mark_unlocked(vid)
            elif got == "private" and (wanted_now or (pa is not None and now - pa > timedelta(minutes=10))):
                youtube.mark_locked(vid)
        calibrated = 0
        by_project: dict[str, dict] = {}
        for vid, s in stats.items():
            p, cid = ids[vid]
            by_project.setdefault(p.id, {})[vid] = s
            if s["privacy"] != "public" or not s.get("published_at"):
                continue
            try:
                published = datetime.fromisoformat(s["published_at"].replace("Z", "+00:00"))
            except ValueError:
                continue
            if datetime.now(timezone.utc) - published < timedelta(hours=STATS_MIN_AGE_H):
                continue
            try:
                cand = _cand(p, cid)
            except SharkyClipsError:
                continue
            calibration.set_entry(p, cand, s["views"], s["likes"], s["published_at"], video_id=vid)
            calibrated += 1
        for pid, st in by_project.items():
            state.update_upload_stats(get_project(pid), st)
        youtube.mark_synced()
        return {"videos": len(stats), "calibrated": calibrated}

    return jobs.submit("yt_stats", "net", None, {"force": force}, run, key="yt_stats")


# ------------------------------------------------------------- queue helpers


class Speeds:
    """Measured render speed (seconds of work per second of video) for the queue's ETA."""
    DEFAULTS = {"render": 0.3, "montage": 0.4, "export": 0.35}

    def __init__(self):
        self.path: Path | None = None
        self.data: dict[str, dict] = {}

    def load(self, path: Path) -> None:
        self.path = path
        try:
            self.data = read_json(path) if path.is_file() else {}
        except Exception:  # noqa: BLE001
            self.data = {}

    def get(self, kind: str) -> float:
        return float((self.data.get(kind) or {}).get("per_second") or self.DEFAULTS.get(kind, 0.4))

    def record(self, kind: str, seconds: float, video_seconds: float) -> None:
        if video_seconds <= 0:
            return
        old = self.data.get(kind) or {}
        n = int(old.get("samples") or 0)
        rate = seconds / video_seconds
        avg = rate if n == 0 else float(old["per_second"]) + (rate - float(old["per_second"])) / min(n + 1, 10)
        self.data[kind] = {"per_second": round(avg, 4), "samples": n + 1}
        if self.path:
            try:
                from ..project import write_json_atomic

                write_json_atomic(self.path, self.data)
            except OSError:
                pass


speeds = Speeds()


def estimate(job: dict) -> float | None:
    """Expected total seconds for a job (None = unknown)."""
    p = job.get("params") or {}
    if job["kind"] == "render":
        return 2.0 + float(p.get("duration") or 25) * speeds.get("render")
    if job["kind"] == "montage":
        return 25.0 + float(p.get("duration") or 120) * speeds.get("montage")
    if job["kind"] == "titles":
        return 30.0
    if job["kind"] == "export":
        return 3.0 + float(p.get("duration") or 25) * speeds.get("export")
    if job["kind"] == "upload":  # assume ~2 MB/s up until measured
        return 5.0 + float(p.get("size_bytes") or 0) / 2_000_000
    return None


def remaining(job: dict, now: float) -> float | None:
    est = estimate(job)
    if job["status"] == "running" and job.get("started"):
        elapsed = max(0.0, now - job["started"] - float(job.get("paused_seconds") or 0))  # work time only
        prog = job.get("progress")
        if prog and prog > 0.03:
            measured = elapsed / prog - elapsed
            if est is None:
                return max(0.0, measured)
            w = min(1.0, prog * 2)  # trust the measured rate more as the job advances
            return max(0.0, w * measured + (1 - w) * (est - elapsed))
        return None if est is None else max(1.0, est - elapsed)
    return est


def rebuild_job(saved: dict, attempt: int | None = None) -> Job | None:
    """Re-submit a job from its saved dict (queue restore after a restart, and Retry)."""
    kind, pid, p = saved["kind"], saved.get("project_id"), saved.get("params") or {}
    keep_id = saved["id"] if attempt is None else None
    attempt = attempt or saved.get("attempt") or 1
    if kind == "render":
        batch = {k: p[k] for k in ("batch", "batch_index", "batch_count") if k in p}
        return submit_render_clip(pid, p["clip_id"], p.get("options") or {}, p.get("hook") or "", batch,
                                  job_id=keep_id, attempt=attempt)
    if kind == "export":
        batch = {k: p[k] for k in ("batch", "batch_index", "batch_count") if k in p}
        return submit_export(pid, p["clip_id"], p.get("request") or {}, batch, job_id=keep_id, attempt=attempt)
    if kind == "upload":
        return submit_upload(pid, p["clip_id"], p.get("body") or {}, job_id=keep_id, attempt=attempt)
    if kind == "yt_stats":
        return submit_youtube_stats()
    if kind == "cover_burn":
        from .publishing import submit_cover_burn

        if p.get("plan_key") and p.get("info"):
            return submit_cover_burn(p["plan_key"], p["info"], job_id=keep_id, attempt=attempt)
        return None
    if kind == "montage":
        return submit_montage(pid, p.get("clip_ids") or [], bool(p.get("intro", True)), bool(p.get("outro", True)),
                              bool(p.get("cards", True)), p.get("lang"), job_id=keep_id, attempt=attempt)
    if kind == "transcribe":
        return submit_transcribe(pid, p.get("language") or "auto", bool(p.get("force")))
    if kind == "highlights":
        return submit_highlights(pid, p.get("mode"), bool(p.get("force")))
    if kind == "analyze":
        return submit_analyze(pid, p.get("lang"), bool(p.get("force")), job_id=keep_id, attempt=attempt,
                              ranks=p.get("ranks") or None)
    if kind == "titles":
        return submit_titles(pid, p["clip_id"])
    if kind in ("platform_export", "platform_upload"):
        from . import platforms_api

        try:
            return platforms_api.rebuild(kind, saved, keep_id, attempt)
        except (SharkyClipsError, KeyError):
            return None
    if kind == "dub":
        from . import dub_api

        try:
            return dub_api.submit(pid, p["clip_id"], p["lang"], job_id=keep_id, attempt=attempt)
        except (SharkyClipsError, KeyError):
            return None
    if kind == "ai_cover":
        from . import covers_api

        try:
            return covers_api.submit(pid, p["clip_id"], list(p.get("frames") or ["tall"]), bool(p.get("new", True)),
                                     job_id=keep_id, attempt=attempt)
        except SharkyClipsError:
            return None
    if kind == "facecam":
        return submit_facecam(pid, bool(p.get("fresh")))
    if kind == "swearscan":
        from . import voices_api

        return voices_api.submit_swearscan(pid, bool(p.get("find_all")), list(p.get("clip_ids") or []) or None)
    if kind in ("voices", "proofread"):
        from . import voices_api

        return (voices_api.submit_voices(pid, bool(p.get("whole"))) if kind == "voices"
                else voices_api.submit_proofread(pid, bool(p.get("force"))))
    if kind == "proxy":
        return submit_proxy(pid)
    if kind == "chat":
        return submit_chat(pid, bool(p.get("force")))
    if kind == "benchmark":
        return submit_benchmark()
    if kind == "music":
        from .studio import submit_music_analysis

        return submit_music_analysis()
    if kind in ("ab", "story_render", "story", "hook_fetch"):
        from . import retention

        if kind == "ab":
            return retention.submit_ab(pid, p["clip_id"], job_id=keep_id, attempt=attempt)
        if kind == "story_render":
            return retention.submit_story_render(pid, p["story_id"], job_id=keep_id, attempt=attempt)
        if kind == "story":
            return retention.submit_story(pid, p.get("lang"))
        return retention.submit_hook_fetch()
    if kind == "import":
        from ..ingest import is_url

        if is_url(p.get("source") or ""):
            return submit_import(p["source"], p.get("mode") or "gaming", p.get("language") or "auto",
                                 p.get("title") or p["source"])
    return None


# ========================================================================= API


@app.get("/api/meta")
def api_meta(request: Request) -> dict:
    return {
        "version": __version__,
        "languages": [lang.to_dict() for lang in languages.LANGUAGES.values()],
        "default_language": languages.DEFAULT_UI_LANGUAGE,
        "modes": list(MODES),
        "layouts": list(LAYOUTS),
        "subtitle_styles": list(SUBTITLE_STYLES),
        "encoders": [{"name": e.name, "label": e.label, "hardware": e.hardware}
                     for e in ENCODERS.values()],
        "reason_codes": REASON_CODES,
        "is_local": _is_local(request),
        "lan_url": app.state.lan_url,
        "workspace": str(config.workspace_dir()) if _is_local(request) else None,
        "llm": {"available": llm_available()},
    }


# ------------------------------------------------------------------ app shell (welcome.py)


@app.get("/api/app")
def api_app_state() -> dict:
    """Onboarding needed?, "What's new" to show, dev banner (polled by the UI)."""
    from .. import welcome

    return welcome.app_state()


@app.get("/api/licenses")
def api_licenses() -> dict:
    """About & licenses: the app and the optional AI models it downloads (with credit links)."""
    from .. import dub, imagegen
    from ..voices import align

    return {"app": {"name": "SharkyClips", "version": __version__, "license": "MIT"},
            "groups": [{"id": "voice", "items": dub.LICENSES}, {"id": "covers", "items": imagegen.LICENSES},
                       {"id": "swears", "items": align.LICENSES}]}


@app.get("/api/changelog/{version}")
def api_changelog(version: str, lang: str = "en") -> dict:
    from .. import welcome

    entry = welcome.changelog_entry(version, lang)
    if entry is None:
        raise HTTPException(404, f"No changelog entry for {version}")
    return entry


@app.post("/api/app/whats-new-seen")
def api_whats_new_seen(body: dict | None = None) -> dict:
    from .. import welcome

    welcome.mark_seen(str((body or {}).get("version") or __version__))
    return welcome.app_state()


@app.post("/api/app/onboarding")
def api_onboarding(body: dict | None = None) -> dict:
    from .. import welcome

    changes = welcome.finish_onboarding(body or {})
    g = governor.get()
    if g is not None and "performance_mode" in changes:
        g.tick()
    return {**welcome.app_state(), "settings": _settings_view()}


@app.get("/api/app/hardware")
def api_hardware_check() -> dict:
    from .. import welcome

    return welcome.hardware_check()


@app.delete("/api/app/dev")
def api_dev_clear(request: Request) -> dict:
    """Remove a stale "under construction" flag (Settings). This computer only."""
    from .. import welcome

    if not _is_local(request):
        raise HTTPException(403, "Only the computer running SharkyClips can do this.")
    welcome.clear_dev_flag()
    return welcome.app_state()


# ------------------------------------------------------------------ settings


def _settings_view() -> dict:
    cfg = config.load()
    triggers = {}
    for lang, val in (cfg.get("custom_triggers") or {}).items():
        if isinstance(val, dict):
            words = []
            for lst in val.values():
                words += [w for w in lst if w not in words]
            triggers[lang] = words
        elif isinstance(val, list):
            triggers[lang] = [str(w) for w in val]
    glossary = cfg.get("glossary") or []
    if isinstance(glossary, dict):  # per-language form: the UI edits the shared list
        glossary = list(glossary.get("all") or [])
    return {"ui_language": cfg.get("ui_language") or languages.DEFAULT_UI_LANGUAGE,
            "default_mode": cfg.get("default_mode") or "gaming",
            "video_encoder": cfg.get("video_encoder") or "auto",
            "output_language": cfg.get("output_language") or languages.DEFAULT_OUTPUT_LANGUAGE,
            "custom_triggers": triggers,
            "llm_model": str(cfg.get("llm_model") or "auto"),
            "auto_analyze": cfg.get("auto_analyze") is not False,
            "fast_analysis": bool(cfg.get("fast_analysis")),
            "glossary": [str(t) for t in glossary],
            "ui_motion": cfg.get("ui_motion") if cfg.get("ui_motion") in MOTION else "full",
            "youtube_daily_quota": int(cfg.get("youtube_daily_quota") or 10000),
            **_perf_view(cfg)}


MOTION = ("full", "reduced", "off")


PERF_BOOLS = ("perf_pause_fullscreen", "perf_pause_video", "perf_pause_busy", "perf_idle_only")


def _perf_view(cfg: dict) -> dict:
    mode = str(cfg.get("performance_mode") or "silent")
    out = {"performance_mode": mode if mode in governor.MODES else "silent",
           "ollama_autostart": startup.ollama_autostart_enabled(),
           "perf_idle_minutes": float(cfg.get("perf_idle_minutes") or 3),
           "perf_gpu_temp_limit": float(cfg.get("perf_gpu_temp_limit") or 85),
           "perf_vram_headroom_mb": int(cfg.get("perf_vram_headroom_mb") or 0),
           "perf_games": list(cfg.get("perf_games") or governor.DEFAULT_GAMES),
           "perf_games_default": governor.DEFAULT_GAMES}
    for k in PERF_BOOLS:
        out[k] = bool(cfg.get(k, config.DEFAULTS[k]))
    return out


def _perf_changes(body: dict) -> dict:
    changes: dict[str, Any] = {}
    if "performance_mode" in body:
        mode = str(body["performance_mode"])
        if mode not in governor.MODES:
            raise SharkyClipsError(f"Unknown performance mode '{mode}'.")
        changes["performance_mode"] = mode
    if "perf_idle_minutes" in body:
        changes["perf_idle_minutes"] = max(0.5, min(120.0, float(body["perf_idle_minutes"])))
    if "perf_gpu_temp_limit" in body:
        changes["perf_gpu_temp_limit"] = max(60.0, min(100.0, float(body["perf_gpu_temp_limit"])))
    if "perf_vram_headroom_mb" in body:
        changes["perf_vram_headroom_mb"] = max(0, min(32768, int(body["perf_vram_headroom_mb"])))
    for k in PERF_BOOLS:
        if k in body:
            changes[k] = bool(body[k])
    if "ollama_autostart" in body:
        changes["ollama_autostart"] = bool(body["ollama_autostart"])
    if "perf_games" in body:
        names: list[str] = []
        for n in body["perf_games"] if isinstance(body["perf_games"], list) else []:
            n = str(n).strip().lower().removesuffix(".exe")[:80]
            if n and n not in names:
                names.append(n)
        changes["perf_games"] = None if names == governor.DEFAULT_GAMES else names[:300]
    return changes


@app.get("/api/settings")
def api_settings() -> dict:
    return _settings_view()


@app.put("/api/settings")
def api_settings_put(body: dict) -> dict:
    changes: dict[str, Any] = {}
    if "ui_language" in body:
        changes["ui_language"] = languages.require(str(body["ui_language"])).code
    if "output_language" in body:
        changes["output_language"] = languages.require(str(body["output_language"])).code
    if "default_mode" in body:
        if body["default_mode"] not in MODES:
            raise SharkyClipsError(f"Unknown mode '{body['default_mode']}'.")
        changes["default_mode"] = body["default_mode"]
    if "video_encoder" in body:
        enc = str(body["video_encoder"])
        if enc != "auto" and enc not in ENCODERS:
            raise SharkyClipsError(f"Unknown encoder '{enc}'.")
        changes["video_encoder"] = enc
    if "custom_triggers" in body:
        triggers = {}
        for lang, words in (body["custom_triggers"] or {}).items():
            languages.require(lang)
            clean = []
            for w in words if isinstance(words, list) else []:
                w = " ".join(str(w).split())[:60]
                if w and w not in clean:
                    clean.append(w)
            if clean:
                triggers[lang] = clean[:300]
        changes["custom_triggers"] = triggers
    if "llm_model" in body:
        from .. import llm

        name = str(body["llm_model"]).strip()
        if name != "auto" and name not in llm.installed_models():
            raise SharkyClipsError(f"The model '{name}' isn't installed in Ollama.",
                                   f"Install it with: ollama pull {name}")
        changes["llm_model"] = name
    if "auto_analyze" in body:
        changes["auto_analyze"] = bool(body["auto_analyze"])
    if "fast_analysis" in body:
        changes["fast_analysis"] = bool(body["fast_analysis"])
    if "glossary" in body:
        terms: list[str] = []
        for t in body["glossary"] if isinstance(body["glossary"], list) else []:
            t = " ".join(str(t).split())[:60]
            if t and t not in terms:
                terms.append(t)
        old = config.get("glossary")
        changes["glossary"] = {**old, "all": terms[:500]} if isinstance(old, dict) else terms[:500]
    if "ui_motion" in body:
        if body["ui_motion"] not in MOTION:
            raise SharkyClipsError(f"Unknown animation setting '{body['ui_motion']}'.")
        changes["ui_motion"] = body["ui_motion"]
    if "ui_theme" in body:
        changes["ui_theme"] = "light" if body["ui_theme"] == "light" else "dark"
    if "youtube_daily_quota" in body:
        changes["youtube_daily_quota"] = max(100, min(10_000_000, int(body["youtube_daily_quota"])))
    changes.update(_perf_changes(body))
    if changes:
        config.update(**changes)
        if "video_encoder" in changes:
            pick_encoder.cache_clear()
        g = governor.get()
        if g is not None and any(k.startswith("perf") for k in changes):
            g.tick()  # apply a new mode right away
        if "ollama_autostart" in changes:
            startup.apply_ollama_autostart(changes["ollama_autostart"])
    return _settings_view()


# ------------------------------------------------------------------ governor


def _governor_view(history: bool = False) -> dict:
    g = governor.get()
    if g is None:
        return {"mode": _perf_view(config.load())["performance_mode"], "state": "off", "sample": None}
    if history:  # the UI just opened
        g.watched()
    return g.view(history=history)


@app.get("/api/governor")
def api_governor(history: bool = False) -> dict:
    """Governor state + the latest resource sample (history=true: the last 5 minutes)."""
    return _governor_view(history)


@app.post("/api/governor/watch")
def api_governor_watch() -> dict:
    """Heartbeat from a visible UI tab: live sensor samples every 2 s while someone looks.
    Without it (and without a job) the governor samples only CPU / RAM every 10 s."""
    g = governor.get()
    if g is not None:
        g.watched()
    return {"ok": True}


@app.put("/api/governor")
def api_governor_put(body: dict) -> dict:
    """Quick mode switch from the top bar: {"mode": "silent" | "balanced" | "turbo"}."""
    config.update(**_perf_changes({"performance_mode": body.get("mode")}))
    g = governor.get()
    if g is not None:
        g.tick()
    return _governor_view()


@app.post("/api/quit")
def api_quit(request: Request) -> dict:
    """Tray icon "Quit SharkyClips" (this computer only): unload the AI model, then exit.
    Child processes (ffmpeg, Ollama started by us) die with the server's job object."""
    host = request.client.host if request.client else ""
    # The custom header can't be sent by other web pages (CORS preflight), only by the tray.
    if host not in ("127.0.0.1", "::1", "localhost", "testclient") or (request.headers.get("x-sharkyclips") or request.headers.get("x-clipforge")) != "quit":
        raise HTTPException(403, "Only this computer can quit SharkyClips.")
    if jobs.busy():
        try:
            from .. import llm

            llm.unload_all()
        except Exception:  # noqa: BLE001
            pass

    def bye() -> None:
        from .. import procs

        procs.kill_children()
        os._exit(0)

    threading.Timer(0.3, bye).start()
    return {"ok": True}


@app.post("/api/governor/resume")
def api_governor_resume() -> dict:
    """'Resume anyway': ignore the current pause reason until it goes away."""
    g = governor.get()
    if g is not None:
        g.resume_anyway()
    return _governor_view()


@app.get("/api/llm")
def api_llm() -> dict:
    """Installed Ollama models for the Settings picker."""
    from .. import llm

    version = llm.server_version(1.0)
    models = []
    if version:
        try:
            import requests

            r = requests.get(f"{llm.base_url()}/api/tags", timeout=5)
            for m in r.json().get("models", []):
                details = m.get("details") or {}
                models.append({"name": m["name"], "size_gb": round((m.get("size") or 0) / 1e9, 1),
                               "params": details.get("parameter_size"),
                               "family": details.get("family"), "quant": details.get("quantization_level")})
        except Exception:
            pass
    models.sort(key=lambda m: m["name"])
    try:
        auto = llm.choose_model(ignore_fast=True) if str(config.get("llm_model") or "auto") == "auto" else None
    except Exception:
        auto = None
    if auto is None:
        from .. import hardware

        hw = hardware.detect_hardware()
        big = (hw.best_nvidia and hw.best_nvidia.vram_gb >= 7.5) or (hw.apple_silicon and hw.ram_total_gb >= 15)
        auto = llm.DEFAULT_MODEL if big else str(config.get("llm_fallback_model") or llm.SMALL_MODEL)
    from ..analyze import speed_stats

    normal = str(config.get("llm_model") or "auto")
    return {"available": llm_available(), "server": version, "installed": models,
            "selected": normal, "auto": auto, "normal_model": auto if normal == "auto" else normal,
            "fast_model": llm.fast_model(), "fast_installed": llm.fast_model() in {m["name"] for m in models},
            "speed": speed_stats()}


@app.post("/api/llm/benchmark")
def api_llm_benchmark() -> dict:
    """Speed test: the best clip of the latest project, once normal and once fast."""
    if not llm_available():
        raise SharkyClipsError("The local LLM isn't installed.", "Run: python cli.py doctor")
    return submit_benchmark().to_dict()


# ------------------------------------------------------------------ jobs


@app.get("/api/jobs")
def api_jobs() -> list[dict]:
    return jobs.list()


@app.post("/api/jobs/{job_id}/cancel")
def api_job_cancel(job_id: str) -> dict:
    job = jobs.cancel(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return job.to_dict()


@app.post("/api/jobs/{job_id}/move")
def api_job_move(job_id: str, body: dict) -> dict:
    job = jobs.move(job_id, int(body.get("to") or 0))
    if not job:
        raise HTTPException(404, "No such job")
    return job.to_dict()


@app.post("/api/jobs/{job_id}/retry")
def api_job_retry(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    if job.status in ACTIVE:
        return job.to_dict()
    new = rebuild_job(job.to_dict(), attempt=job.attempt + 1)
    if new is None:
        raise SharkyClipsError("This task can't be retried.")
    jobs.forget(job_id)
    return new.to_dict()


@app.delete("/api/jobs/{job_id}")
def api_job_forget(job_id: str) -> dict:
    return {"removed": jobs.forget(job_id)}


def _queue_view() -> dict:
    now = time.time()
    lanes = {}
    for lane in ("gpu", "io", "net"):
        t = 0.0
        known = True
        out = []
        for j in jobs.lane_order(lane):
            d = j.to_dict()
            left = remaining(d, now)
            d["eta_seconds"] = None if left is None else round(left, 1)
            if left is None:
                known = False
            else:
                t += left
            d["eta_finish_seconds"] = round(t, 1) if known else None
            out.append(d)
        lanes[lane] = out
    history = sorted((j.to_dict() for j in jobs.jobs() if j.status not in ACTIVE),
                     key=lambda d: d["finished"] or 0, reverse=True)
    gpu = lanes["gpu"]
    return {"lanes": lanes, "history": history[:60],
            "eta_total_seconds": gpu[-1]["eta_finish_seconds"] if gpu else 0,
            "shutdown": power.state(), "speeds": {k: speeds.get(k) for k in Speeds.DEFAULTS}}


@app.get("/api/queue")
def api_queue() -> dict:
    return _queue_view()


def _render_is_current(clip: dict | None, cand: dict, options: dict, hook: str, review: dict | None = None) -> bool:
    """Already rendered with the same cut, edits and settings? (Clips rendered before an
    option existed count as rendered with its default.)"""
    if not clip:
        return False
    defaults = ClipOptions().to_dict()
    old = {**defaults, **(clip.get("options") or {})}
    want = {**options, "hook_text": hook}
    same_opts = all(old.get(k) == v for k, v in want.items() if k in defaults)
    if review is not None:
        if (clip.get("edit_fp") or "") != state.edit_fingerprint(cand, review, options):
            return False
        cand = state.effective_cand(cand, review)
    return same_opts and abs(clip["start"] - cand["start"]) < 0.05 and abs(clip["end"] - cand["end"]) < 0.05


def _accepted_overview(project: Project) -> dict | None:
    hl = state.load_highlights(project)
    if not hl:
        return None
    review = state.load_review(project, hl)
    by_id = {c["id"]: c for c in hl.get("candidates", [])}
    clips = state.load_clips(project)
    opts = dict(review["options"])
    accepted = [c for c in review["accepted"] if c in by_id]
    current = [c for c in accepted
               if _render_is_current(clips.get(c), by_id[c], opts, review["hooks"].get(c, ""), review)]
    return {"project_id": project.id, "title": project.load_meta().get("title") or project.id,
            "accepted": len(accepted), "rendered": len(current), "to_render": len(accepted) - len(current),
            "seconds": round(sum(by_id[c]["duration"] for c in accepted if c not in current), 1)}


@app.get("/api/queue/accepted")
def api_queue_accepted() -> list[dict]:
    """Per project: accepted clips and how many still need rendering ("Render all accepted")."""
    out = [o for p in list_projects() if (o := _accepted_overview(p)) and o["accepted"]]
    return out


@app.post("/api/queue/render")
def api_queue_render(body: dict) -> dict:
    """Render all accepted clips of these projects (one queue entry per clip)."""
    ids = [str(x) for x in body.get("project_ids") or []]
    include_current = bool(body.get("rerender"))
    if not ids:
        raise SharkyClipsError("Choose at least one project.")
    out: list[Job] = []
    for pid in ids:
        project = _project(pid)
        hl = state.load_highlights(project)
        if not hl:
            continue
        review = state.load_review(project, hl)
        by_id = {c["id"]: c for c in hl.get("candidates", [])}
        clips = state.load_clips(project)
        opts = dict(review["options"])
        todo = [c for c in review["accepted"] if c in by_id and
                (include_current or not _render_is_current(clips.get(c), by_id[c], opts, review["hooks"].get(c, ""),
                                                            review))]
        if todo:
            out += submit_render(project.id, todo, ClipOptions.from_dict(opts), review["hooks"])
    return {"queued": len(out), "jobs": [j.to_dict() for j in out]}


@app.post("/api/queue/cancel")
def api_queue_cancel(body: dict | None = None) -> dict:
    """Cancel every active job, or only those of one project / kind / batch."""
    body = body or {}
    n = 0
    for j in jobs.jobs():
        if j.status not in ACTIVE:
            continue
        if body.get("project_id") and j.project_id != body["project_id"]:
            continue
        if body.get("kind") and j.kind != body["kind"]:
            continue
        if body.get("batch") and j.params.get("batch") != body["batch"]:
            continue
        jobs.cancel(j.id)
        n += 1
    return {"cancelled": n}


@app.post("/api/queue/clear")
def api_queue_clear() -> dict:
    n = sum(jobs.forget(j.id) for j in jobs.jobs() if j.status not in ACTIVE)
    return {"removed": n}


@app.put("/api/queue/shutdown")
def api_shutdown(body: dict, request: Request) -> dict:
    enabled = bool(body.get("enabled"))
    if enabled and not _is_local(request):
        raise SharkyClipsError("Only the computer running SharkyClips can turn on automatic shutdown.")
    return power.set_enabled(enabled)


@app.post("/api/queue/shutdown/cancel")
def api_shutdown_cancel() -> dict:
    return power.cancel()


@app.get("/api/events")
async def api_events(request: Request):
    """Server-sent events: the full job list whenever anything changes."""

    async def stream():
        last = -1
        last_gov = -1
        idle = 0.0
        yield "retry: 2000\n\n"
        while True:
            if await request.is_disconnected():
                break
            if jobs.rev != last:
                last = jobs.rev
                idle = 0.0
                yield f"event: jobs\ndata: {json.dumps(jobs.list(), ensure_ascii=False)}\n\n"
                yield f"event: shutdown\ndata: {json.dumps(power.state())}\n\n"
            g = governor.get()
            if g is not None and g.rev != last_gov:  # one sample every ~2 s (the governor's own)
                last_gov = g.rev
                idle = 0.0
                yield f"event: governor\ndata: {json.dumps(g.view(), ensure_ascii=False)}\n\n"
            elif idle > 15:
                idle = 0.0
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.25)
            idle += 0.25

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ projects


def _summary(project: Project) -> dict:
    pj = sorted(jobs.for_project(project.id), key=lambda j: j.created)
    active = jobs.active_for(project.id)
    last = pj[-1].to_dict() if pj else None
    return state.project_summary(project, active.to_dict() if active else None, last)


@app.get("/api/projects")
def api_projects() -> list[dict]:
    out = [_summary(p) for p in list_projects()]
    out.sort(key=lambda p: p.get("created_at") or "", reverse=True)
    return out


@app.post("/api/projects")
def api_create(body: dict, request: Request) -> dict:
    source = str(body.get("url") or body.get("path") or "").strip()
    mode = body.get("mode") or config.get("default_mode") or "gaming"
    language = body.get("language") or "auto"
    if mode not in MODES:
        raise SharkyClipsError(f"Unknown mode '{mode}'.")
    if language != "auto":
        languages.require(language)
    if not source:
        raise SharkyClipsError("Paste a video URL or choose a file.")
    from ..ingest import is_url

    if not is_url(source):
        if not _is_local(request):
            raise SharkyClipsError("Local file paths only work on the computer running SharkyClips.",
                                   "Upload the file instead.")
        if not Path(source).expanduser().is_file():
            raise SharkyClipsError(f"File not found: {source}")
    title = source if is_url(source) else Path(source).name
    return submit_import(source, mode, language, title).to_dict()


@app.put("/api/uploads")
async def api_upload(request: Request, filename: str = Query(...), mode: str = Query("gaming"),
                     language: str = Query("auto"), easy: bool = Query(False)) -> dict:
    """Raw file upload (streamed straight to disk - works for multi-GB stream files).
    easy=true: an Easy mode project (mode "auto" = detect the content type)."""
    mode_auto = mode == "auto"
    if mode_auto:
        mode = config.get("default_mode") or "gaming"
    if mode not in MODES:
        raise SharkyClipsError(f"Unknown mode '{mode}'.")
    if language != "auto":
        languages.require(language)
    name = Path(filename).name
    stem, suffix = Path(name).stem, Path(name).suffix.lower()
    if suffix not in {".mp4", ".mkv", ".mov", ".webm", ".m4v", ".avi", ".flv", ".ts", ".wmv",
                      ".mpg", ".mpeg", ".mp3", ".m4a", ".wav"}:
        raise SharkyClipsError(f"Unsupported file type '{suffix}'.", "Use a video file such as .mp4 or .mkv.")
    up_dir = config.workspace_dir() / "_uploads"
    up_dir.mkdir(parents=True, exist_ok=True)
    # Keep the original name (it becomes the project title), but make it filesystem-safe.
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")[:120] or slugify(stem)
    dest = up_dir / f"{safe}{suffix}"
    part = dest.with_name(dest.name + ".uploading")
    size = 0
    try:
        with open(part, "wb") as f:
            async for chunk in request.stream():
                f.write(chunk)
                size += len(chunk)
    except Exception:
        part.unlink(missing_ok=True)
        raise
    if size == 0:
        part.unlink(missing_ok=True)
        raise SharkyClipsError("The uploaded file is empty.")
    part.replace(dest)
    extra = {"easy": True, "mode_auto": mode_auto} if easy else None
    return submit_import(str(dest), mode, language, name, cleanup=dest, extra=extra).to_dict()


@app.get("/api/projects/{project_id}")
def api_project(project_id: str) -> dict:
    project = _project(project_id)
    meta = project.load_meta()
    hl = state.load_highlights(project)
    review = state.load_review(project, hl)
    transcript_lang = (meta.get("transcript") or {}).get("language")
    cands = [state.candidate_view(c) for c in (hl or {}).get("candidates", [])]
    from ..titles import feedback

    from .. import calibration
    from ..montage import list_exports

    votes = feedback.votes_for([t for c in cands for t in c["publish"]["titles"]], None)
    chat_stats = state.chat_stats(project, (hl or {}).get("candidates", []))
    cal_model = calibration.load().get("model")
    raw = {c["id"]: c for c in (hl or {}).get("candidates", [])}
    for c in cands:
        c["default_hook"] = c["publish"].get("hook_text") or first_sentence(c.get("text") or "")
        c["publish"]["title_votes"] = {t: votes[t] for t in c["publish"]["titles"] if t in votes}
        c["publish"]["calibrated"] = calibration.adjust(raw[c["id"]], cal_model) if cal_model else None
        c["chat"] = chat_stats.get(c["id"])
    performance = calibration.entries_for(project.id)
    clips = state.load_clips(project)
    for cid, clip in clips.items():
        e = performance.get(cid)
        clip["performance"] = None if not e else {k: e.get(k) for k in ("views", "likes", "published_at",
                                                                         "updated_at")}
    signals = {k: {"status": v.get("status"), "weight": v.get("weight"), "share": v.get("share"),
                   "reason": v.get("reason")}
               for k, v in ((hl or {}).get("signals") or {}).items()}
    return {
        **_summary(project),
        "meta": {k: meta.get(k) for k in ("width", "height", "fps", "video_codec", "audio_codec",
                                           "source_size_bytes")},
        "playable": _playable(project) or _proxy_path(project).is_file(),
        "is_rtl": languages.is_rtl(transcript_lang),
        "highlights": None if not hl else {
            "mode": hl.get("mode"), "created_at": hl.get("created_at"), "signals": signals,
            "settings": hl.get("settings"), "candidates": cands},
        "review": review,
        "clips": clips,
        "calibration": calibration.status(),
        "exports": len(list_exports(project)),
        "chat": _chat_summary(project),
        "game": _game_summary(project),
        "analysis": (hl or {}).get("analysis"),
        "output_language": ((hl or {}).get("analysis") or {}).get("language")
                           or config.get("output_language") or languages.DEFAULT_OUTPUT_LANGUAGE,
        "jobs": [j.to_dict() for j in jobs.for_project(project.id)][-10:],
    }


@app.get("/api/projects/{project_id}/hype")
def api_hype(project_id: str):
    project = _project(project_id)
    path = project.dir / "hype_curve.json"
    if not path.is_file():
        raise HTTPException(404, "No hype curve yet")
    return FileResponse(path, media_type="application/json")


@app.get("/api/projects/{project_id}/words")
def api_words(project_id: str, start: float, end: float) -> list[dict]:
    project = _project(project_id)
    if not project.transcript_path.is_file():
        return []
    if end - start > 900:
        raise HTTPException(400, "Range too long (max 15 minutes)")
    from ..edit.plan import transcript_words

    found, _lang = transcript_words(project, start, end)  # voice-pass words (with speakers) where it ran
    return [{"start": round(w["start"], 3), "end": round(w["end"], 3), "word": w["word"],
             **({"spk": w["spk"]} if w.get("spk") else {})} for w in found]


@app.post("/api/projects/{project_id}/transcribe")
def api_transcribe(project_id: str, body: dict | None = None) -> dict:
    project = _project(project_id)
    body = body or {}
    language = body.get("language") or "auto"
    if language != "auto":
        languages.require(language)
    return submit_transcribe(project.id, language, bool(body.get("force"))).to_dict()


@app.post("/api/projects/{project_id}/highlights")
def api_highlights(project_id: str, body: dict | None = None) -> dict:
    project = _project(project_id)
    body = body or {}
    mode = body.get("mode")
    if mode and mode not in MODE_PRESETS:
        raise SharkyClipsError(f"Unknown mode '{mode}'.")
    if not project.transcript_path.is_file():
        raise SharkyClipsError("Transcribe the video first.")
    return submit_highlights(project.id, mode, bool(body.get("force"))).to_dict()


# ------------------------------------------------------------------ game awareness


@app.get("/api/projects/{project_id}/game")
def api_game(project_id: str, reads: bool = False) -> dict:
    """Which game, its HUD regions, and what the last scan found (debug / calibration view)."""
    from .. import game as game_mod
    from ..game import presets

    project = _project(project_id)
    info = game_mod.resolve(project)
    sc = game_mod.load_scan(project)
    gid = info["game"] or (sc or {}).get("game")
    ev = game_mod.game_events(project) if sc else None
    out = {
        **info,
        "choices": list(game_mod.CHOICES),
        "games": presets.GAMES,
        "base_size": [presets.BASE_W, presets.BASE_H],
        "regions": presets.regions(gid) if gid else {},
        "scan": None if not sc else {
            "game": sc["game"], "stats": sc.get("stats"), "champion": sc.get("champion"),
            "frame_size": sc.get("frame_size"), "boxes": sc.get("boxes"),
            "current": sc.get("key") == (game_mod.scan_key(project, sc["game"]) if project.source_path else None),
        },
        "events": (ev or {}).get("events", []),
        "sounds": (ev or {}).get("sounds") or _sounds_info(gid),
        "event_codes": game_mod.known_codes(),
    }
    if reads and sc:
        out["reads"] = sc.get("reads", [])[-4000:]
    return out


def _sounds_info(gid: str | None) -> dict:
    if not gid:
        return {}
    from ..game import events as game_events
    from ..game import sounds

    files = sounds.reference_files(gid)
    known = set(game_events.STRENGTH)
    return {"folder": str(sounds.sounds_dir(gid)),
            "clips": [p.name for p in files if sounds.event_code(p, known)],
            "ignored": [p.name for p in files if not sounds.event_code(p, known)]}


@app.put("/api/projects/{project_id}/game")
def api_game_set(project_id: str, body: dict) -> dict:
    """Pick the game (auto / delta_force / lol / other) and re-run the highlight analysis."""
    from .. import game as game_mod

    project = _project(project_id)
    choice = body.get("choice")
    if choice not in game_mod.CHOICES:
        raise SharkyClipsError(f"Unknown game '{choice}'.", f"Use one of: {', '.join(game_mod.CHOICES)}")
    game_mod.save_choice(project, choice)
    job = None
    if project.transcript_path.is_file() and body.get("reanalyze", True):
        job = submit_highlights(project.id, None, False).to_dict()
    return {"game": game_mod.resolve(project), "job": job}


@app.post("/api/projects/{project_id}/game/rescan")
def api_game_rescan(project_id: str) -> dict:
    """Read the HUD again (after fixing a region) and re-run the analysis."""
    project = _project(project_id)
    (project.cache_dir / "game" / "scan.json").unlink(missing_ok=True)
    if not project.transcript_path.is_file():
        raise SharkyClipsError("Transcribe the video first.")
    return submit_highlights(project.id, None, False).to_dict()


@app.post("/api/projects/{project_id}/game/probe")
def api_game_probe(project_id: str, body: dict) -> dict:
    """Read every HUD region of one frame, to check a region box."""
    from .. import game as game_mod

    project = _project(project_id)
    gid = body.get("game") or game_mod.resolve(project)["game"]
    if gid not in game_mod.presets.GAMES:
        raise SharkyClipsError("Pick the game first (Delta Force or League of Legends).")
    if project.source_path is None:
        raise SharkyClipsError("This project has no video file.")
    try:
        return game_mod.probe(project, float(body.get("t") or 0), gid)
    except RuntimeError as exc:
        raise SharkyClipsError(str(exc)) from None


@app.put("/api/game/regions")
def api_game_region(body: dict) -> dict:
    """Move a HUD region (1920x1080 pixel box) on this computer; null resets it."""
    from ..game import presets

    try:
        return presets.save_override(body.get("game", ""), body.get("region", ""), body.get("box"))
    except KeyError:
        raise SharkyClipsError("Unknown game or region.") from None
    except ValueError as exc:
        raise SharkyClipsError(f"Invalid box: {exc}") from None


@app.put("/api/projects/{project_id}/review")
def api_review(project_id: str, body: dict) -> dict:
    return state.save_review(_project(project_id), body)


@app.post("/api/projects/{project_id}/facecam/detect")
def api_facecam_detect(project_id: str, body: dict | None = None) -> dict:
    return submit_facecam(_project(project_id).id, fresh=bool((body or {}).get("fresh"))).to_dict()


@app.post("/api/projects/{project_id}/render")
def api_render(project_id: str, body: dict) -> dict:
    project = _project(project_id)
    clip_ids = [str(c) for c in body.get("clip_ids") or []]
    if not clip_ids:
        raise SharkyClipsError("Accept at least one clip first.")
    review = state.load_review(project)
    options = ClipOptions.from_dict({**review["options"], **(body.get("options") or {})})
    hooks = {**review["hooks"], **(body.get("hooks") or {})}
    return {"jobs": [j.to_dict() for j in submit_render(project.id, clip_ids, options, hooks)]}


@app.post("/api/projects/{project_id}/candidates/{cid}/publish")
def api_publish_regenerate(project_id: str, cid: str) -> dict:
    """New title suggestions for one clip (local LLM, runs in the GPU lane)."""
    project = _project(project_id)
    if not llm_available():
        raise SharkyClipsError("The local LLM isn't installed.", "Run: python cli.py doctor")
    return submit_titles(project.id, cid).to_dict()


@app.post("/api/projects/{project_id}/candidates/{cid}/titles/vote")
def api_title_vote(project_id: str, cid: str, body: dict) -> dict:
    """Thumbs up / down on one title. Liked titles become few-shot examples next time."""
    from ..titles import feedback

    project = _project(project_id)
    hl = state.load_highlights(project) or {}
    c = next((x for x in hl.get("candidates", []) if x["id"] == cid), None)
    pub = (c or {}).get("publish") or {}
    text = str(body.get("text") or "")
    if c is None or text not in (pub.get("titles") or []):
        raise HTTPException(404, "No such title")
    value = int(body.get("vote") or 0)
    feedback.vote(text, pub.get("language") or "tr", max(-1, min(1, value)),
                  mode=hl.get("mode") or "", topic=(c.get("llm") or {}).get("game_or_topic") or "",
                  project=project.id, clip=cid)
    return {"text": text, "vote": max(-1, min(1, value))}


@app.post("/api/projects/{project_id}/analyze")
def api_analyze(project_id: str, body: dict | None = None) -> dict:
    project = _project(project_id)
    body = body or {}
    lang = body.get("lang")
    if lang:
        languages.require(lang)
    if not (project.dir / "highlights.json").is_file():
        raise SharkyClipsError("Find highlights first.")
    if not llm_available():
        raise SharkyClipsError("The local LLM isn't installed.", "Run: python cli.py doctor")
    return submit_analyze(project.id, lang, bool(body.get("force"))).to_dict()


# ------------------------------------------------------------------ best-of video


@app.post("/api/projects/{project_id}/montage")
def api_montage(project_id: str, body: dict) -> dict:
    project = _project(project_id)
    lang = body.get("lang") or None
    if lang:
        languages.require(lang)
    return submit_montage(project.id, [str(c) for c in body.get("clip_ids") or []],
                          intro=bool(body.get("intro", True)), outro=bool(body.get("outro", True)),
                          cards=bool(body.get("cards", True)), lang=lang).to_dict()


@app.get("/api/projects/{project_id}/exports")
def api_exports(project_id: str) -> list[dict]:
    from ..montage import list_exports

    return list_exports(_project(project_id))


def _export_file(project: Project, name: str) -> Path:
    from ..montage import exports_dir

    if not re.fullmatch(r"bestof_[0-9-]+", name):
        raise HTTPException(404, "No such export")
    path = exports_dir(project) / f"{name}.mp4"
    if not path.is_file():
        raise HTTPException(404, "No such export")
    return path


@app.get("/api/projects/{project_id}/exports/{name}/video")
def api_export_video(project_id: str, name: str, download: bool = False):
    project = _project(project_id)
    path = _export_file(project, name)
    title = slugify(project.load_meta().get("title") or project.id, 50)
    return FileResponse(path, media_type="video/mp4", filename=f"{title}-{name}.mp4" if download else None,
                        content_disposition_type="attachment" if download else "inline")


@app.get("/api/projects/{project_id}/exports/{name}/poster.jpg")
def api_export_poster(project_id: str, name: str):
    project = _project(project_id)
    path = _export_file(project, name)
    dest = project.cache_dir / "frames" / f"{name}_poster.jpg"
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [require_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-ss", "1.6", "-i", str(path),
               "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(dest)]
        subprocess.run(cmd, capture_output=True, timeout=60, **no_window())
    if not dest.is_file():
        raise HTTPException(500, "Could not extract a frame")
    return FileResponse(dest, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


@app.delete("/api/projects/{project_id}/exports/{name}")
def api_export_delete(project_id: str, name: str) -> dict:
    from ..montage import delete_export

    return {"removed": delete_export(_project(project_id), name)}


# ------------------------------------------------------------------ calibration


@app.put("/api/projects/{project_id}/clips/{cid}/performance")
def api_performance(project_id: str, cid: str, body: dict) -> dict:
    """Real YouTube numbers for a published clip (calibrates the viral score)."""
    from .. import calibration

    project = _project(project_id)
    if cid not in state.load_clips(project):
        raise SharkyClipsError("Render this clip first; views can only be added to rendered clips.")
    hl = state.load_highlights(project) or {}
    cand = next((c for c in hl.get("candidates", []) if c["id"] == cid), None)
    if cand is None:
        raise HTTPException(404, "No such clip")
    try:
        views = int(str(body.get("views")).replace(",", "").replace(".", "").strip())
        likes = body.get("likes")
        likes = None if likes in (None, "") else int(str(likes).replace(",", "").replace(".", "").strip())
    except ValueError:
        raise SharkyClipsError("Views and likes must be whole numbers.") from None
    if views < 0 or views > 10_000_000_000 or (likes is not None and likes < 0):
        raise SharkyClipsError("That view count doesn't look right.")
    published = str(body.get("published_at") or "").strip() or None
    if published:
        from datetime import datetime

        try:
            datetime.fromisoformat(published)
        except ValueError:
            raise SharkyClipsError("Unknown date format for 'published'.") from None
    entry = calibration.set_entry(project, cand, views, likes, published)
    return {"entry": entry, "calibration": calibration.status()}


@app.delete("/api/projects/{project_id}/clips/{cid}/performance")
def api_performance_delete(project_id: str, cid: str) -> dict:
    from .. import calibration

    project = _project(project_id)
    return {"removed": calibration.delete_entry(calibration.entry_key(project.id, cid)),
            "calibration": calibration.status()}


@app.get("/api/calibration")
def api_calibration() -> dict:
    from .. import calibration

    return calibration.stats()


@app.delete("/api/calibration")
def api_calibration_clear() -> dict:
    from .. import calibration

    return {"removed": calibration.clear(), "calibration": calibration.status()}


@app.delete("/api/calibration/{key}")
def api_calibration_delete(key: str) -> dict:
    from .. import calibration

    return {"removed": calibration.delete_entry(key), "calibration": calibration.status()}


# ------------------------------------------------------------------ export (Phase 9)

_formats_cache: dict[str, Any] = {}


@app.get("/api/export/options")
def api_export_options() -> dict:
    """Formats this PC can make (test-encodes once), platform presets, editor formats."""
    from .. import export

    if "formats" in _formats_cache:
        formats = _formats_cache["formats"]
    else:
        formats = export.available_formats()
        if shutil.which("ffmpeg"):  # without ffmpeg, check again once the user installs it
            _formats_cache["formats"] = formats
    return {"formats": formats,
            "presets": [export.preset_view(p) for p in export.PRESETS.values()],
            "gif_default_mb": export.DEFAULT_GIF_MB, "subtitle_kinds": list(export.SUB_KINDS),
            "editors": ["fcpxml", "premiere"]}


@app.post("/api/projects/{project_id}/export/estimate")
def api_export_estimate(project_id: str, body: dict) -> dict:
    from .. import export

    project = _project(project_id)
    hl = state.load_highlights(project) or {}
    by_id = {c["id"]: c for c in hl.get("candidates", [])}
    fmt = body.get("format") or None
    preset = body.get("preset") or None
    if fmt is not None and fmt not in export.FORMATS:
        raise SharkyClipsError(f"Unknown export format '{fmt}'.")
    if preset is not None and preset not in export.PRESETS:
        raise SharkyClipsError(f"Unknown platform preset '{preset}'.")
    fps = float(project.load_meta().get("fps") or 30)
    flash = bool(state.load_review(project, hl)["options"].get("hook_flash"))
    out = []
    for cid in [str(c) for c in body.get("clip_ids") or []]:
        c = by_id.get(cid)
        if c is None:
            continue
        size = export.estimate_bytes(fmt, preset, c["duration"], fps, body.get("gif_max_mb"), flash) if fmt else 0
        out.append({"clip_id": cid, "bytes": size, "warnings": export.check_length(preset, c["duration"]),
                    "seconds": round(3.0 + c["duration"] * speeds.get("export"), 1) if fmt else 2.0})
    return {"clips": out, "bytes": sum(x["bytes"] for x in out), "seconds": round(sum(x["seconds"] for x in out), 1)}


@app.post("/api/projects/{project_id}/export")
def api_export(project_id: str, body: dict) -> dict:
    """Export clips (one queue entry per clip): format, platform preset, subtitles, editor files."""
    project = _project(project_id)
    clip_ids = [str(c) for c in body.get("clip_ids") or []]
    if not clip_ids:
        raise SharkyClipsError("Choose at least one clip.")
    request = {k: body.get(k) for k in ("format", "preset", "burn_captions", "subtitles", "subtitle_lang",
                                        "editors", "gif_max_mb")}
    batch = f"x{int(time.time() * 1000)}"
    out = [submit_export(project.id, cid, request, {"batch": batch, "batch_index": i + 1,
                                                    "batch_count": len(clip_ids)})
           for i, cid in enumerate(clip_ids)]
    return {"jobs": [j.to_dict() for j in out]}


@app.get("/api/projects/{project_id}/clip-exports")
def api_clip_exports(project_id: str) -> list[dict]:
    from .. import export

    return sorted(export.load_registry(_project(project_id)), key=lambda e: e["created_at"], reverse=True)


@app.get("/api/projects/{project_id}/clip-exports/file/{name}")
def api_clip_export_file(project_id: str, name: str, download: bool = False):
    from .. import export

    project = _project(project_id)
    path = export.file_path(project, name)
    if path is None:
        raise HTTPException(404, "No such export file")
    mime = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".gif": "image/gif",
            ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".srt": "application/x-subrip", ".vtt": "text/vtt",
            ".fcpxml": "application/xml", ".xml": "application/xml"}.get(path.suffix.lower(),
                                                                        "application/octet-stream")
    title = slugify(project.load_meta().get("title") or project.id, 50)
    return FileResponse(path, media_type=mime, filename=f"{title}-{name}" if download else None,
                        content_disposition_type="attachment" if download else "inline")


@app.delete("/api/projects/{project_id}/clip-exports/{export_id}")
def api_clip_export_delete(project_id: str, export_id: str) -> dict:
    from .. import export

    return {"removed": export.delete_export(_project(project_id), export_id)}


# ------------------------------------------------------------------ YouTube (Phase 9)


def _yt_view() -> dict:
    from .. import youtube

    return {**youtube.status(), "last_synced": youtube.last_synced() or None}


@app.get("/api/youtube")
def api_youtube() -> dict:
    return _yt_view()


@app.put("/api/youtube/client")
async def api_youtube_client(request: Request) -> dict:
    """The user's own OAuth client JSON (raw body: the dropped file or pasted text). This PC only."""
    from .. import youtube

    if not _is_local(request):
        raise HTTPException(403, "Only the computer running SharkyClips can do this.")
    raw = await request.body()
    if len(raw) > 64 * 1024:
        raise SharkyClipsError("That file is too big for an OAuth client JSON.",
                               "Use the client_secret_....json file Google downloads (about 400 bytes).")
    youtube.set_client(raw)
    return _yt_view()


@app.post("/api/youtube/client/check")
async def api_youtube_client_check(request: Request) -> dict:
    """Validate a client JSON without saving it (the wizard checks a paste as you type)."""
    from .. import youtube

    raw = await request.body()
    try:
        c = youtube.check_client_text(youtube.decode_client_bytes(raw[:64 * 1024]))
    except SharkyClipsError as exc:
        return {"ok": False, "error": exc.message, "hint": exc.hint, "reason": getattr(exc, "reason", None)}
    return {"ok": True, "project_id": c.get("project_id"), "client_id": c["client_id"]}


@app.delete("/api/youtube/client")
def api_youtube_client_delete(request: Request) -> dict:
    from .. import youtube

    if not _is_local(request):
        raise HTTPException(403, "Only the computer running SharkyClips can do this.")
    youtube.remove_client()
    return _yt_view()


@app.post("/api/youtube/connect")
def api_youtube_connect(request: Request, body: dict | None = None) -> dict:
    """Start "Connect with Google": a one-shot listener on a random 127.0.0.1 port, and the
    sign-in page in the system browser. Poll GET /api/youtube/connect/{id}."""
    from .. import ytconnect

    if not _is_local(request):
        raise SharkyClipsError("Connect YouTube on the computer running SharkyClips.",
                               "Google sends the sign-in back to that computer's own address.")
    return ytconnect.start(open_browser=(body or {}).get("open", True) is not False)


@app.get("/api/youtube/connect/{flow_id}")
def api_youtube_connect_state(flow_id: str) -> dict:
    from .. import ytconnect

    flow = ytconnect.get(flow_id)
    return {**flow, "youtube": _yt_view() if flow["status"] != "waiting" else None}


@app.delete("/api/youtube/connect/{flow_id}")
def api_youtube_connect_cancel(flow_id: str, request: Request) -> dict:
    from .. import ytconnect

    if not _is_local(request):
        raise HTTPException(403, "Only the computer running SharkyClips can do this.")
    ytconnect.cancel(flow_id)
    return ytconnect.get(flow_id)


@app.post("/api/youtube/channel")
def api_youtube_channel(body: dict, request: Request) -> dict:
    from .. import youtube

    if not _is_local(request):
        raise HTTPException(403, "Only the computer running SharkyClips can do this.")
    youtube.select_channel(str(body.get("id") or ""))
    return _yt_view()


@app.post("/api/youtube/recheck")
def api_youtube_recheck() -> dict:
    from .. import youtube

    youtube.recheck_channel()
    return _yt_view()


@app.post("/api/youtube/signed-out/dismiss")
def api_youtube_signed_out_dismiss() -> dict:
    from .. import youtube

    youtube.dismiss_signed_out()
    return _yt_view()


@app.post("/api/youtube/disconnect")
def api_youtube_disconnect(request: Request) -> dict:
    from .. import youtube

    if not _is_local(request):
        raise HTTPException(403, "Only the computer running SharkyClips can do this.")
    youtube.disconnect()
    return _yt_view()


@app.post("/api/youtube/stats")
def api_youtube_stats() -> dict:
    from .. import youtube

    if not youtube.connected():
        raise SharkyClipsError("Connect YouTube first (Settings > YouTube).")
    return submit_youtube_stats(force=True).to_dict()


@app.get("/api/projects/{project_id}/uploads")
def api_uploads(project_id: str) -> dict:
    return state.load_uploads(_project(project_id))


@app.post("/api/projects/{project_id}/clips/{cid}/upload")
def api_upload_clip(project_id: str, cid: str, body: dict) -> dict:
    from .. import youtube

    project = _project(project_id)
    if not youtube.connected():
        raise SharkyClipsError("Connect YouTube first (Settings > YouTube).")
    youtube.check_quota(youtube.COST["upload"])
    return submit_upload(project.id, cid, body).to_dict()


@app.put("/api/projects/{project_id}/clips/{cid}/thumbnail")
async def api_thumbnail_upload(project_id: str, cid: str, request: Request) -> dict:
    """A custom YouTube thumbnail (JPEG/PNG, max 2 MB - YouTube's limit)."""
    project = _project(project_id)
    _cand(project, cid)
    raw = await request.body()
    if len(raw) > 2 * 1024 * 1024:
        raise SharkyClipsError("YouTube thumbnails can be at most 2 MB.")
    if not (raw[:3] == b"\xff\xd8\xff" or raw[:8] == b"\x89PNG\r\n\x1a\n"):
        raise SharkyClipsError("Use a JPEG or PNG image.")
    dest = project.cache_dir / "thumbnails" / f"{cid}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if raw[:4] == b"\x89PNG":  # store as JPEG (smaller, one name)
        src = dest.with_suffix(".png")
        src.write_bytes(raw)
        cmd = [require_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
               "-q:v", "3", str(dest)]
        # in a worker thread: ffmpeg must not stall the event loop (live progress, other tabs)
        await asyncio.to_thread(subprocess.run, cmd, capture_output=True, timeout=60, **no_window())
        src.unlink(missing_ok=True)
    else:
        dest.write_bytes(raw)
    return {"ok": dest.is_file()}


@app.get("/api/projects/{project_id}/clips/{cid}/thumbnail.jpg")
def api_thumbnail(project_id: str, cid: str, kind: str = "auto"):
    project = _project(project_id)
    path = _thumbnail_file(project, cid, _cand(project, cid), kind)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


def _chat_summary(project: Project) -> dict | None:
    from ..chat import load_chat

    c = load_chat(project)
    return None if c is None else {k: c.get(k) for k in ("status", "source", "reason", "count", "authors")}


def _game_summary(project: Project) -> dict | None:
    from .. import game as game_mod

    try:
        info = game_mod.resolve(project)
    except Exception:
        return None
    sc = game_mod.load_scan(project)
    return {**info, "scanned": bool(sc), "champion": game_mod.champion_name(sc) if sc else None}


@app.post("/api/projects/{project_id}/chat/download")
def api_chat_download(project_id: str) -> dict:
    return submit_chat(_project(project_id).id, force=True).to_dict()


@app.put("/api/projects/{project_id}/chat")
async def api_chat_import(project_id: str, request: Request, filename: str = Query("chat.txt")) -> dict:
    """Import a chat log file (raw body). Re-analyze afterwards to use it."""
    from ..chat import import_file

    project = _project(project_id)
    dest_dir = project.cache_dir / "chat"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / ("import" + (Path(filename).suffix.lower()[:8] or ".txt"))
    size = 0
    with open(dest, "wb") as f:
        async for chunk in request.stream():
            size += len(chunk)
            if size > 500 * 1024**2:
                raise SharkyClipsError("Chat file too large (max 500 MB).")
            f.write(chunk)
    await asyncio.to_thread(import_file, project, dest)  # big logs: don't block the event loop
    return _chat_summary(project) or {}


# ------------------------------------------------------------------ media


@app.get("/api/projects/{project_id}/media/source")
def api_media_source(project_id: str):
    project = _project(project_id)
    proxy = _proxy_path(project)
    if not _playable(project) and proxy.is_file():
        return FileResponse(proxy, media_type="video/mp4")
    src = project.source_path
    if src is None:
        raise HTTPException(404, "Source video missing")
    media = {".webm": "video/webm", ".mov": "video/quicktime"}.get(src.suffix.lower(), "video/mp4")
    return FileResponse(src, media_type=media)


@app.get("/api/projects/{project_id}/clips/{cid}/video")
def api_clip_video(project_id: str, cid: str, download: bool = False):
    project = _project(project_id)
    clip = state.load_clips(project).get(cid)
    if not clip:
        raise HTTPException(404, "Clip not rendered")
    path = project.dir / "clips" / clip["file"]
    title = slugify(project.load_meta().get("title") or project.id, 50)
    return FileResponse(path, media_type="video/mp4",
                        filename=f"{title}-{clip['file']}" if download else None,
                        content_disposition_type="attachment" if download else "inline")


def _frame(project: Project, t: float, width: int, dest: Path) -> Path:
    if dest.is_file():
        return dest
    src = project.source_path
    if src is None:
        raise HTTPException(404, "Source video missing")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".tmp.jpg")
    cmd = [require_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}",
           "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "4", str(tmp)]
    res = subprocess.run(cmd, capture_output=True, timeout=60, **no_window())
    if res.returncode != 0 or not tmp.is_file():
        raise HTTPException(500, "Could not extract a frame")
    tmp.replace(dest)
    return dest


@app.get("/api/projects/{project_id}/thumb.jpg")
def api_thumb(project_id: str):
    project = _project(project_id)
    meta = project.load_meta()
    hl = state.load_highlights(project)
    t = (hl["candidates"][0]["peak"] if hl and hl.get("candidates")
         else float(meta.get("duration") or 0) * 0.3)
    path = _frame(project, t, 640, project.cache_dir / "thumb.jpg")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=300"})


@app.get("/api/projects/{project_id}/frame.jpg")
def api_frame(project_id: str, t: float = 0.0, w: int = 1280):
    project = _project(project_id)
    w = 640 if w <= 640 else 1280
    t = max(0.0, round(t, 1))
    path = _frame(project, t, w, project.cache_dir / "frames" / f"{w}_{t:.1f}.jpg")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=86400"})


# ------------------------------------------------------------------ frontend


# ------------------------------------------------------------------ updates


def _supervised() -> bool:
    """True when `cli.py serve` watches this process and starts it again after an update."""
    return os.environ.get("SHARKYCLIPS_SUPERVISED") == "1"


@app.get("/api/update")
def api_update_status(fetch: bool = True) -> dict:
    from .. import updater

    return {**updater.status(fetch=fetch), "can_restart": _supervised()}


@app.post("/api/update")
def api_update_apply(request: Request) -> dict:
    from .. import updater

    if not _is_local(request):
        raise SharkyClipsError("Updates can only be started on the computer running SharkyClips.")
    if any(j.kind != "update" for j in jobs.jobs() if j.status in ACTIVE):
        raise SharkyClipsError("SharkyClips is busy.", "Wait until the running jobs are finished (or cancel them), "
                                                   "then update.")

    def run(job: Job):
        return updater.apply(lambda s: jobs.update(job, stage=s, progress=None))

    return jobs.submit("update", "io", None, {}, run, key="update").to_dict()


@app.post("/api/update/restart")
def api_update_restart(request: Request) -> dict:
    import threading

    from .. import updater

    if not _is_local(request):
        raise SharkyClipsError("Only the computer running SharkyClips can restart it.")
    if not _supervised():
        return {"restarting": False}
    threading.Timer(0.4, lambda: os._exit(updater.RESTART_CODE)).start()
    return {"restarting": True}


from .studio import router as _studio_router  # noqa: E402 - editing tools API (1.2.4)
from .voices_api import router as _voices_router  # noqa: E402 - voices, bleeps, facecam picker (1.2.15)
from .retention import router as _retention_router  # noqa: E402 - stories, A/B hooks, loops (1.2.5)
from .publishing import router as _publishing_router  # noqa: E402 - Library + scheduled publishing (1.2.7)
from .easy import router as _easy_router  # noqa: E402 - Easy mode (1.2.16)
from .live import router as _live_router  # noqa: E402 - auto clips, live markers (1.2.17)
from .phone_api import router as _phone_router  # noqa: E402 - Telegram bot + approval page (1.2.17)
from .covers_api import router as _covers_router  # noqa: E402 - cover studio (1.2.18)
from .platforms_api import router as _platforms_router  # noqa: E402 - TikTok / Reels (1.2.18)
from .dub_api import router as _dub_router  # noqa: E402 - my-voice dubbing (1.2.18)

app.include_router(_auth_router)
app.include_router(_studio_router)
app.include_router(_voices_router)
app.include_router(_retention_router)
app.include_router(_publishing_router)
app.include_router(_easy_router)
app.include_router(_live_router)
app.include_router(_phone_router)
app.include_router(_covers_router)
app.include_router(_platforms_router)
app.include_router(_dub_router)


@app.get("/api/{rest:path}")
def api_404(rest: str):
    raise HTTPException(404, f"Unknown API path /api/{rest}")


if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{rest:path}", include_in_schema=False)
def spa(rest: str, request: Request):
    candidate = (FRONTEND_DIST / rest).resolve()
    if rest and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        return Response("The web UI isn't built yet. Run: cd frontend && npm install && npm run build",
                        media_type="text/plain", status_code=503)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


def _cleanup_uploads() -> None:
    """Remove half-finished uploads from an earlier run."""
    up = config.workspace_dir() / "_uploads"
    if up.is_dir():
        for p in up.glob("*.uploading"):
            if time.time() - p.stat().st_mtime > 3600:
                p.unlink(missing_ok=True)


_cleanup_uploads()


@app.on_event("startup")
def _restore_queue() -> None:
    """Unfinished renders / best-of videos from the last run go back into the queue."""
    speeds.load(config.workspace_dir() / "_speeds.json")
    if os.environ.get("SHARKYCLIPS_NO_GOVERNOR") != "1":
        startup.apply_ollama_autostart()  # Ollama's updater puts its Startup shortcut back
        g = governor.install(busy=jobs.busy)
        last_state = {"paused": None}

        def _jobs_follow() -> None:  # running jobs show "paused" in the job list
            if g.paused != last_state["paused"]:
                last_state["paused"] = g.paused
                jobs.bump()

        g.on_change.append(_jobs_follow)
    n = jobs.restore(rebuild_job)
    _start_publishing()
    if n:
        from ..ui import console

        console.print(f"Resumed [bold]{n}[/] queued job(s) from the last run.")


def _start_publishing() -> None:
    """The publish loop (web/publishing.py): uploads scheduled clips in advance, fetches views
    every 6 hours (calibration, the hook bandit, the private lock) and the hook test results."""
    from .easy import install as install_easy
    from .publishing import install

    install(jobs)
    install_easy(jobs)
    from .live import install as install_live

    install_live()  # auto clips after a stream, live markers (1.2.17)
    from .phone_api import install as install_phone

    install_phone()  # the Telegram bot's Upload / Plan / Skip buttons (1.2.17)
