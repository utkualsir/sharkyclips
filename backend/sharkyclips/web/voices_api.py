"""API of the voice pass (voices/), caption proofreading, bleep sounds and the facecam
picker (1.2.15)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from .. import facecam as fc_mod
from .. import voices
from ..clips import Facecam
from ..errors import SharkyClipsError
from ..voices import models as vmodels
from ..voices import tracks
from . import state

router = APIRouter()


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


# ------------------------------------------------------------------ voices


def submit_voices(project_id: str, whole: bool = False):
    A = _app()

    def run(job):
        project = A.get_project(project_id)

        def progress(stage: str, f: float) -> None:
            A.jobs.update(job, stage=f"voices_{stage}", progress=f)

        data = voices.run_voice_pass(project, whole=whole, on_progress=progress)
        return {"speakers": data["speakers"], "words": len(data["words"]), "hints": len(data["hints"]),
                "mode": data["mode"], "seconds": data["seconds"]}

    def then(_job):
        if A.llm_available():
            submit_proofread(project_id)

    return A.jobs.submit("voices", "gpu", project_id, {"whole": whole}, run, then)


def submit_proofread(project_id: str, force: bool = False):
    A = _app()

    def run(job):
        from ..edit import proof

        def progress(i: int, n: int) -> None:
            A.jobs.update(job, stage="proofreading", progress=i / max(1, n))

        return proof.proofread_project(A.get_project(project_id), progress, force=force)

    return A.jobs.submit("proofread", "gpu", project_id, {"force": force}, run)


def _voices_view(project) -> dict:
    data = voices.load(project)
    meta = project.load_meta()
    src = project.source_path
    streams = tracks.audio_streams(src) if src else []
    labels, label_src = tracks.labels_for(meta, streams)
    view = {
        "tracks": [{**s, "label": lab} for s, lab in zip(streams, labels)],
        "labels_from": label_src,
        "labels": list(tracks.LABELS),
        "models": vmodels.status(),
        "done": data is not None,
    }
    if data:
        stale = data.get("transcript_created_at") != voices.pipeline._transcript_stamp(project)
        view.update({
            "mode": data.get("mode"), "whole": data.get("whole"), "ranges": data.get("ranges"),
            "speakers": data.get("speakers"), "names": data.get("names") or {},
            "separated": data.get("separated"), "diarized": data.get("diarized"),
            "words": len(data.get("words") or []), "hints": len(data.get("hints") or []),
            "created_at": data.get("created_at"), "seconds": data.get("seconds"), "stale": stale,
        })
    return view


@router.get("/api/projects/{project_id}/voices")
def api_voices(project_id: str) -> dict:
    return _voices_view(_app()._project(project_id))


@router.post("/api/projects/{project_id}/voices/run")
def api_voices_run(project_id: str, body: dict | None = None) -> dict:
    project = _app()._project(project_id)
    if not project.transcript_path.is_file():
        raise SharkyClipsError("Transcribe the video first.")
    return submit_voices(project.id, whole=bool((body or {}).get("whole"))).to_dict()


@router.put("/api/projects/{project_id}/voices/tracks")
def api_voices_tracks(project_id: str, body: dict) -> dict:
    project = _app()._project(project_id)
    labels = [str(v) for v in body.get("labels") or []]
    tracks.save_labels(project, labels)
    return _voices_view(project)


@router.put("/api/projects/{project_id}/voices/names")
def api_voices_names(project_id: str, body: dict) -> dict:
    from ..project import write_json_atomic

    project = _app()._project(project_id)
    data = voices.load(project)
    if data is None:
        raise SharkyClipsError("Run 'Hear every speaker' first.")
    names = {str(k): str(v).strip()[:24] for k, v in (body.get("names") or {}).items()
             if str(k) in (data.get("speakers") or {})}
    data["names"] = {k: v for k, v in names.items() if v}
    write_json_atomic(voices.pipeline.voices_path(project), data)
    return _voices_view(project)


@router.put("/api/projects/{project_id}/voices/merge")
def api_voices_merge(project_id: str, body: dict) -> dict:
    """Two ids are the same person ("f4" is really "me"): relabel its words and hints."""
    from ..project import write_json_atomic

    project = _app()._project(project_id)
    data = voices.load(project)
    if data is None:
        raise SharkyClipsError("Run 'Hear every speaker' first.")
    src, dst = str(body.get("from") or ""), str(body.get("into") or "")
    spk = data.get("speakers") or {}
    if src not in spk or dst not in spk or src == dst:
        raise SharkyClipsError("Unknown speaker.")
    for item in [*(data.get("words") or []), *(data.get("hints") or [])]:
        if item.get("spk") == src:
            item["spk"] = dst
    spk[dst]["seconds"] = round(spk[dst].get("seconds", 0) + spk.pop(src).get("seconds", 0), 1)
    data["speakers"] = dict(sorted(spk.items(), key=lambda kv: -kv[1].get("seconds", 0)))
    (data.get("names") or {}).pop(src, None)
    write_json_atomic(voices.pipeline.voices_path(project), data)
    return _voices_view(project)


@router.post("/api/projects/{project_id}/proofread")
def api_proofread(project_id: str, body: dict | None = None) -> dict:
    A = _app()
    project = A._project(project_id)
    if not A.llm_available():
        raise SharkyClipsError("The local LLM isn't installed.", "Run: python cli.py doctor")
    return submit_proofread(project.id, force=bool((body or {}).get("force"))).to_dict()


@router.get("/api/projects/{project_id}/peaks")
def api_peaks(project_id: str, start: float, end: float, n: int = 400) -> dict:
    """Loudness envelope of [start, end] for the bleep waveform (0..1 per bucket)."""
    import numpy as np

    from .. import audio

    project = _app()._project(project_id)
    if end - start > 900 or end <= start:
        raise SharkyClipsError("Range too long (max 15 minutes).")
    n = max(20, min(2000, int(n)))
    if not project.audio_path.is_file():
        return {"start": start, "end": end, "peaks": [0.0] * n}
    x = audio.read_wav_segment(project.audio_path, max(0.0, start), end)
    if len(x) < n:
        return {"start": start, "end": end, "peaks": [0.0] * n}
    k = len(x) // n
    p = np.abs(x[:k * n]).reshape(n, k).max(axis=1)
    top = float(np.percentile(p, 98)) or 1.0
    return {"start": start, "end": end, "peaks": [round(float(v), 3) for v in np.clip(p / top, 0, 1)]}


# ------------------------------------------------------------------ bleep sound


@router.get("/api/bleep")
def api_bleep() -> dict:
    from ..edit.audiomix import custom_bleep_path

    p = custom_bleep_path()
    return {"custom": p.is_file(), "size": p.stat().st_size if p.is_file() else 0}


@router.put("/api/bleep/custom")
async def api_bleep_upload(request: Request) -> dict:
    """Any short audio file; stored as a WAV (first 3 s, mono 48 kHz)."""
    import subprocess

    from ..edit.audiomix import custom_bleep_path
    from ..errors import require_tool
    from ..procs import no_window

    dest = custom_bleep_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = dest.with_name(".upload.part")
    size = 0
    try:
        with open(raw, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise SharkyClipsError("A bleep sound must be smaller than 20 MB.")
                f.write(chunk)
        if size == 0:
            raise SharkyClipsError("The uploaded file is empty.")
        tmp = dest.with_name(".custom.part.wav")
        res = subprocess.run([require_tool("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw),
                              "-t", "3", "-vn", "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(tmp)],
                             capture_output=True, timeout=60, **no_window())
        if res.returncode != 0 or not tmp.is_file():
            tmp.unlink(missing_ok=True)
            raise SharkyClipsError("That file isn't an audio file ffmpeg can read.")
        tmp.replace(dest)
    finally:
        raw.unlink(missing_ok=True)
    return api_bleep()


@router.delete("/api/bleep/custom")
def api_bleep_delete() -> dict:
    from ..edit.audiomix import custom_bleep_path

    custom_bleep_path().unlink(missing_ok=True)
    return api_bleep()


@router.get("/api/bleep/preview")
def api_bleep_preview(sound: str = "classic"):
    """A 0.6 s sample of a bleep sound (Settings / render options "listen")."""
    import numpy as np

    from ..edit import audiomix

    sound = sound if sound in audiomix.BLEEP_SOUNDS else "classic"
    n = int(audiomix.SR * 0.6)
    tone = audiomix._bleep_tone(n, sound, audiomix.load_custom_bleep() if sound == "custom" else None) * 0.12
    r = int(audiomix.SR * audiomix.BLEEP_FADE)
    fade = (0.5 - 0.5 * np.cos(np.linspace(0, np.pi, r))).astype(np.float32)
    tone[:r] *= fade
    tone[-r:] *= fade[::-1]
    y = np.zeros((int(audiomix.SR * 0.8), 2), np.float32)
    y[int(audiomix.SR * 0.1):int(audiomix.SR * 0.1) + n] = tone[:, None]
    path = audiomix.custom_bleep_path().with_name(f".preview-{sound}.wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    audiomix.write_wav(path, y)
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------ facecam picker


@router.get("/api/projects/{project_id}/facecam/analysis")
def api_facecam_analysis(project_id: str) -> dict:
    project = _app()._project(project_id)
    data = fc_mod.load_analysis(project) or {}
    _json, jpg = fc_mod.analysis_paths(project)
    meta = project.load_meta()
    lay = fc_mod.find_layout(meta)
    return {
        "candidates": [{k: v for k, v in c.items() if k != "frames"} for c in data.get("candidates") or []],
        "ask": bool(data.get("ask")), "confidence": data.get("confidence"),
        "frame": jpg.is_file(), "frame_time": data.get("frame_time"),
        "detector": data.get("detector"), "created_at": data.get("created_at"),
        "layout": ({**fc_mod.layout_key(meta), "box": lay["box"], "confirmed": lay.get("confirmed", False)}
                   if lay else None),
        "low": fc_mod.LOW_CONFIDENCE,
    }


@router.get("/api/projects/{project_id}/facecam/frame.jpg")
def api_facecam_frame(project_id: str):
    project = _app()._project(project_id)
    _json, jpg = fc_mod.analysis_paths(project)
    if not jpg.is_file():
        raise SharkyClipsError("No analysis frame yet.")
    return FileResponse(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.put("/api/projects/{project_id}/facecam")
def api_facecam_set(project_id: str, body: dict) -> dict:
    """Pick a candidate / save a drawn box (remembered for this channel + resolution), or
    "none" = no facecam."""
    project = _app()._project(project_id)
    raw = body.get("facecam")
    fc = Facecam.from_dict(raw) if raw else None
    review = state.save_review(project, {"facecam": fc.to_dict() if fc else None})
    meta = project.load_meta()
    if fc is not None and body.get("remember", True):
        fc_mod.remember_layout(meta, fc, confirmed=True)
    elif fc is None and body.get("forget"):
        fc_mod.forget_layout(meta)
    return review


@router.delete("/api/facecam/layouts")
def api_facecam_forget_all() -> dict:
    from ..project import write_json_atomic

    write_json_atomic(fc_mod._layouts_path(), {"layouts": []})
    return {"ok": True}


# ------------------------------------------------------------------ deep swear check (1.2.21)


def submit_swearscan(project_id: str, find_all: bool = False, clip_ids: list[str] | None = None):
    """The deep swear check (voices/swearscan.py) over every clip, or only clip_ids (Easy: the
    clips it renders)."""
    A = _app()

    def run(job):
        from ..voices import pipeline, swearscan

        def progress(stage: str, f: float) -> None:
            A.jobs.update(job, stage=f"swears_{stage}", progress=f)

        project = A.get_project(project_id)
        ranges = None
        if clip_ids:
            hl = state.load_highlights(project) or {}
            dur = float(project.load_meta().get("duration") or 0)
            rs = [(max(0.0, float(c["start"]) - pipeline.PAD), min(dur or 1e9, float(c["end"]) + pipeline.PAD))
                  for c in hl.get("candidates", []) if c["id"] in clip_ids]
            ranges = pipeline.merge_ranges(rs) or None
        data = swearscan.run_scan(project, on_progress=progress, find_all=find_all, ranges=ranges)
        items = data["items"]
        return {"items": len(items), "sure": sum(1 for i in items if i["status"] == "sure"),
                "model": data["model"], "seconds": data["seconds"]}

    return A.jobs.submit("swearscan", "gpu", project_id, {"find_all": find_all, "clip_ids": clip_ids or []}, run,
                         key=f"swearscan:{project_id}")


def _scan_view(project) -> dict:
    from ..edit import swears
    from ..voices import align, swearscan

    data = swearscan.load(project)
    view: dict = {"done": data is not None, "aligner_ready": align.ready()}
    if data:
        items = data.get("items") or []
        view.update({
            "created_at": data.get("created_at"), "model": data.get("model"), "aligned": data.get("aligned"),
            "seconds": data.get("seconds"), "windows": data.get("windows"), "ranges": data.get("ranges"),
            "stale": data.get("transcript_created_at") != voices.pipeline._transcript_stamp(project),
            "count": {lvl: sum(1 for i in items if swears.bleeped(i, lvl)) for lvl in swears.STRICTNESS},
            "items": [{k: i.get(k) for k in ("start", "end", "word", "heard", "spk", "status", "score", "votes",
                                             "why", "bleep", "aligned", "leak", "leak_first", "rounds")}
                      for i in items],
        })
    return view


@router.get("/api/projects/{project_id}/swearscan")
def api_swearscan(project_id: str) -> dict:
    return _scan_view(_app()._project(project_id))


@router.post("/api/projects/{project_id}/swearscan/run")
def api_swearscan_run(project_id: str, body: dict | None = None) -> dict:
    project = _app()._project(project_id)
    if not project.transcript_path.is_file():
        raise SharkyClipsError("Transcribe the video first.")
    return submit_swearscan(project.id, find_all=bool((body or {}).get("find_all"))).to_dict()


@router.get("/api/projects/{project_id}/swearscan/snippet")
def api_swearscan_snippet(project_id: str, start: float, end: float, bleep: str = ""):
    """A short WAV of the main audio (listen back), optionally with a bleep mixed in ("a,b")."""
    import io
    import wave

    import numpy as np
    from fastapi.responses import Response

    from .. import audio
    from ..voices import swearscan

    project = _app()._project(project_id)
    if end <= start or end - start > 30:
        raise SharkyClipsError("Range too long (max 30 seconds).")
    if not project.audio_path.is_file():
        raise SharkyClipsError("The audio of this project is missing.")
    x = audio.read_wav_segment(project.audio_path, max(0.0, start), end)
    for part in [bleep] if bleep else []:
        try:
            a, b = (float(v) for v in part.split(",")[:2])
        except ValueError:
            continue
        x = swearscan.bleep_into(x, a, b, max(0.0, start))
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm)
    return Response(buf.getvalue(), media_type="audio/wav", headers={"Cache-Control": "no-cache"})


@router.get("/api/projects/{project_id}/swearscan/labels")
def api_swear_labels(project_id: str) -> dict:
    from ..edit import swear_eval

    return swear_eval.load_labels(_app()._project(project_id))


@router.put("/api/projects/{project_id}/swearscan/labels")
def api_swear_labels_put(project_id: str, body: dict) -> dict:
    """One item's label from the review page: {"key", "label": yes|no|unsure|null, "note"?}."""
    from ..edit import swear_eval

    return swear_eval.set_label(_app()._project(project_id), str(body.get("key") or ""), body.get("label"),
                                str(body.get("note") or ""), by="user")
