"""ClipForge web UI: REST API + live job events (SSE) + the built React app.

Start it with `python cli.py serve` (see cli.py). Everything stays on this computer;
with --lan other devices on the same network can use it too.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__, config, languages
from ..clips import LAYOUTS, SUBTITLE_STYLES, ClipOptions, Facecam, clip_words, first_sentence, render_clip
from ..errors import ClipForgeError, require_tool
from ..highlights.modes import MODES as MODE_PRESETS
from ..project import MODES, Project, get_project, list_projects, read_json, slugify
from ..render import ENCODERS, _flags, pick_encoder
from . import state
from .jobs import Job, JobManager

FRONTEND_DIST = config.REPO_ROOT / "frontend" / "dist"
REASON_CODES = ["loudness_spike", "keyword", "laughter", "shouting", "cheering", "fast_speech",
                "pause_then_burst", "steady_explanation", "chorus", "drop", "chat_spike", "chat_reactions",
                "llm_explanation"]
BROWSER_CODECS = {"h264", "av1", "vp9", "vp8"}
BROWSER_CONTAINERS = {".mp4", ".webm", ".m4v", ".mov"}

jobs = JobManager()
app = FastAPI(title="ClipForge", version=__version__, docs_url="/api/docs", redoc_url=None)
app.state.lan_url = None


@app.exception_handler(ClipForgeError)
async def _clipforge_error(_req: Request, exc: ClipForgeError):
    return JSONResponse({"error": exc.message, "hint": exc.hint}, status_code=400)


def _is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


def _project(project_id: str) -> Project:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", project_id):
        raise HTTPException(404, "No such project")
    try:
        project = get_project(project_id)
    except ClipForgeError:
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


def submit_analyze(project_id: str, lang: str | None = None, force: bool = False) -> Job:
    def run(job: Job):
        from ..analyze import analyze_project

        jobs.update(job, stage="loading_llm", progress=None)

        def progress(i: int, n: int, _c: dict) -> None:
            jobs.update(job, stage="llm_analyzing", progress=i / n, detail={"index": i, "count": n})

        res = analyze_project(get_project(project_id), out_lang=lang, force=force, on_progress=progress)
        return {"language": res["language"], "model": res["model"], "seconds": res["total_seconds"],
                "count": len(res["candidates"])}

    return jobs.submit("analyze", "gpu", project_id, {"lang": lang, "force": force}, run)


def submit_titles(project_id: str, cid: str) -> Job:
    def run(job: Job):
        from ..analyze import regenerate_titles

        jobs.update(job, stage="writing_titles", progress=None)
        return {"titles": regenerate_titles(get_project(project_id), cid)["titles"], "clip_id": cid}

    return jobs.submit("titles", "gpu", project_id, {"clip_id": cid}, run)


def submit_facecam(project_id: str) -> Job:
    def run(job: Job):
        from ..facecam import detect_facecam

        project = get_project(project_id)
        jobs.update(job, stage="detecting_facecam", progress=None)
        fc = detect_facecam(project.source_path, float(project.load_meta().get("duration") or 0))
        state.save_review(project, {"facecam": fc.to_dict() if fc else None})
        return {"facecam": fc.to_dict() if fc else None}

    return jobs.submit("facecam", "io", project_id, {}, run)


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
                  cleanup: Path | None = None) -> Job:
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
                       {"source": source, "title": title, "mode": mode, "language": language},
                       run, then, dedupe=False)


def submit_render(project_id: str, clip_ids: list[str], options: ClipOptions,
                  hooks: dict[str, str]) -> Job:
    def run(job: Job):
        project = get_project(project_id)
        hl = state.load_highlights(project) or {}
        by_id = {c["id"]: c for c in hl.get("candidates", [])}
        chosen = [by_id[c] for c in clip_ids if c in by_id]
        if not chosen:
            raise ClipForgeError("None of the selected clips exist any more.",
                                 "Re-run the highlight analysis and pick clips again.")
        review = state.load_review(project, hl)
        facecam = Facecam.from_dict(review.get("facecam"))
        total = sum(c["duration"] for c in chosen)
        done = 0.0
        out = []
        for i, cand in enumerate(chosen):
            name = f"{cand['rank']:02d}_{cand['id']}.mp4"
            opts = ClipOptions.from_dict({**options.to_dict(), "hook_text": hooks.get(cand["id"], "")})
            detail = {"index": i + 1, "count": len(chosen), "clip_id": cand["id"]}
            jobs.update(job, stage="rendering", progress=done / total, detail=detail)
            res = render_clip(project, cand, opts, facecam, project.dir / "clips" / name,
                              on_progress=lambda s, d=done: jobs.update(job, progress=(d + s) / total))
            done += cand["duration"]
            entry = {"file": name, "id": cand["id"], "rank": cand["rank"], "start": cand["start"],
                     "end": cand["end"], "duration": cand["duration"], "options": opts.to_dict(),
                     "facecam": facecam.to_dict() if facecam else None,
                     "rendered_at": state.now_iso(), "size_bytes": res.size_bytes,
                     "render_seconds": round(res.seconds, 2), "encoder": res.encoder}
            state.save_clip(project, cand["id"], entry)
            out.append(entry)
        return {"clips": [c["id"] for c in out]}

    return jobs.submit("render", "gpu", project_id,
                       {"clip_ids": clip_ids, "options": options.to_dict()}, run)


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
            "glossary": [str(t) for t in glossary]}


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
            raise ClipForgeError(f"Unknown mode '{body['default_mode']}'.")
        changes["default_mode"] = body["default_mode"]
    if "video_encoder" in body:
        enc = str(body["video_encoder"])
        if enc != "auto" and enc not in ENCODERS:
            raise ClipForgeError(f"Unknown encoder '{enc}'.")
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
            raise ClipForgeError(f"The model '{name}' isn't installed in Ollama.",
                                 f"Install it with: ollama pull {name}")
        changes["llm_model"] = name
    if "auto_analyze" in body:
        changes["auto_analyze"] = bool(body["auto_analyze"])
    if "glossary" in body:
        terms: list[str] = []
        for t in body["glossary"] if isinstance(body["glossary"], list) else []:
            t = " ".join(str(t).split())[:60]
            if t and t not in terms:
                terms.append(t)
        old = config.get("glossary")
        changes["glossary"] = {**old, "all": terms[:500]} if isinstance(old, dict) else terms[:500]
    if changes:
        config.update(**changes)
        if "video_encoder" in changes:
            pick_encoder.cache_clear()
    return _settings_view()


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
        auto = llm.choose_model() if str(config.get("llm_model") or "auto") == "auto" else None
    except Exception:
        auto = None
    if auto is None:
        from .. import hardware

        hw = hardware.detect_hardware()
        big = (hw.best_nvidia and hw.best_nvidia.vram_gb >= 7.5) or (hw.apple_silicon and hw.ram_total_gb >= 15)
        auto = llm.DEFAULT_MODEL if big else str(config.get("llm_fallback_model") or llm.SMALL_MODEL)
    return {"available": llm_available(), "server": version, "installed": models,
            "selected": str(config.get("llm_model") or "auto"), "auto": auto}


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


@app.get("/api/events")
async def api_events(request: Request):
    """Server-sent events: the full job list whenever anything changes."""

    async def stream():
        last = -1
        idle = 0.0
        yield "retry: 2000\n\n"
        while True:
            if await request.is_disconnected():
                break
            if jobs.rev != last:
                last = jobs.rev
                idle = 0.0
                yield f"event: jobs\ndata: {json.dumps(jobs.list(), ensure_ascii=False)}\n\n"
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
        raise ClipForgeError(f"Unknown mode '{mode}'.")
    if language != "auto":
        languages.require(language)
    if not source:
        raise ClipForgeError("Paste a video URL or choose a file.")
    from ..ingest import is_url

    if not is_url(source):
        if not _is_local(request):
            raise ClipForgeError("Local file paths only work on the computer running ClipForge.",
                                 "Upload the file instead.")
        if not Path(source).expanduser().is_file():
            raise ClipForgeError(f"File not found: {source}")
    title = source if is_url(source) else Path(source).name
    return submit_import(source, mode, language, title).to_dict()


@app.put("/api/uploads")
async def api_upload(request: Request, filename: str = Query(...), mode: str = Query("gaming"),
                     language: str = Query("auto")) -> dict:
    """Raw file upload (streamed straight to disk - works for multi-GB stream files)."""
    if mode not in MODES:
        raise ClipForgeError(f"Unknown mode '{mode}'.")
    if language != "auto":
        languages.require(language)
    name = Path(filename).name
    stem, suffix = Path(name).stem, Path(name).suffix.lower()
    if suffix not in {".mp4", ".mkv", ".mov", ".webm", ".m4v", ".avi", ".flv", ".ts", ".wmv",
                      ".mpg", ".mpeg", ".mp3", ".m4a", ".wav"}:
        raise ClipForgeError(f"Unsupported file type '{suffix}'.", "Use a video file such as .mp4 or .mkv.")
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
        raise ClipForgeError("The uploaded file is empty.")
    part.replace(dest)
    return submit_import(str(dest), mode, language, name, cleanup=dest).to_dict()


@app.get("/api/projects/{project_id}")
def api_project(project_id: str) -> dict:
    project = _project(project_id)
    meta = project.load_meta()
    hl = state.load_highlights(project)
    review = state.load_review(project, hl)
    transcript_lang = (meta.get("transcript") or {}).get("language")
    cands = [state.candidate_view(c) for c in (hl or {}).get("candidates", [])]
    from ..titles import feedback

    votes = feedback.votes_for([t for c in cands for t in c["publish"]["titles"]], None)
    chat_stats = state.chat_stats(project, (hl or {}).get("candidates", []))
    for c in cands:
        c["default_hook"] = c["publish"].get("hook_text") or first_sentence(c.get("text") or "")
        c["publish"]["title_votes"] = {t: votes[t] for t in c["publish"]["titles"] if t in votes}
        c["chat"] = chat_stats.get(c["id"])
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
        "clips": state.load_clips(project),
        "chat": _chat_summary(project),
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
    return [{"start": round(w["start"] + start, 3), "end": round(w["end"] + start, 3), "word": w["word"]}
            for w in clip_words(read_json(project.transcript_path), start, end)]


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
        raise ClipForgeError(f"Unknown mode '{mode}'.")
    if not project.transcript_path.is_file():
        raise ClipForgeError("Transcribe the video first.")
    return submit_highlights(project.id, mode, bool(body.get("force"))).to_dict()


@app.put("/api/projects/{project_id}/review")
def api_review(project_id: str, body: dict) -> dict:
    return state.save_review(_project(project_id), body)


@app.post("/api/projects/{project_id}/facecam/detect")
def api_facecam_detect(project_id: str) -> dict:
    return submit_facecam(_project(project_id).id).to_dict()


@app.post("/api/projects/{project_id}/render")
def api_render(project_id: str, body: dict) -> dict:
    project = _project(project_id)
    clip_ids = [str(c) for c in body.get("clip_ids") or []]
    if not clip_ids:
        raise ClipForgeError("Accept at least one clip first.")
    review = state.load_review(project)
    options = ClipOptions.from_dict({**review["options"], **(body.get("options") or {})})
    hooks = {**review["hooks"], **(body.get("hooks") or {})}
    return submit_render(project.id, clip_ids, options, hooks).to_dict()


@app.post("/api/projects/{project_id}/candidates/{cid}/publish")
def api_publish_regenerate(project_id: str, cid: str) -> dict:
    """New title suggestions for one clip (local LLM, runs in the GPU lane)."""
    project = _project(project_id)
    if not llm_available():
        raise ClipForgeError("The local LLM isn't installed.", "Run: python cli.py doctor")
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
        raise ClipForgeError("Find highlights first.")
    if not llm_available():
        raise ClipForgeError("The local LLM isn't installed.", "Run: python cli.py doctor")
    return submit_analyze(project.id, lang, bool(body.get("force"))).to_dict()


def _chat_summary(project: Project) -> dict | None:
    from ..chat import load_chat

    c = load_chat(project)
    return None if c is None else {k: c.get(k) for k in ("status", "source", "reason", "count", "authors")}


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
                raise ClipForgeError("Chat file too large (max 500 MB).")
            f.write(chunk)
    import_file(project, dest)
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
    res = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=_flags())
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


@app.get("/api/{rest:path}")
def api_404(rest: str):
    raise HTTPException(404, f"Unknown API path /api/{rest}")


if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{rest:path}", include_in_schema=False)
def spa(rest: str):
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
