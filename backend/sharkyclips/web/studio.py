"""API of the editing tools (1.2.4): edit plans for the live preview, manual clips, the
music library, the brand kit and the word lists. Included by app.py (before its /api 404)."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from .. import config, languages
from .. import clips as clips_mod
from ..clips import ClipOptions, Facecam
from ..edit import brand, fillers, manual, music, profanity
from ..edit import plan as plan_mod
from ..errors import SharkyClipsError
from ..procs import no_window
from . import state

router = APIRouter()


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


# ------------------------------------------------------------------ live preview


@router.post("/api/projects/{project_id}/candidates/{cid}/plan")
def api_plan(project_id: str, cid: str, body: dict | None = None) -> dict:
    """What the render would do to this clip (cuts, bleeps, zoom, music), in source time,
    for the live preview. body: {"options": {...}, "edit": {...}} override the saved ones."""
    body = body or {}
    A = _app()
    project = A._project(project_id)
    review = state.load_review(project)
    cand = A._cand(project, cid)
    if "edit" in body:
        review = {**review, "edits": {**review["edits"], cid: state.clean_edit(body["edit"]) or {}}}
    if "music" in body:  # None = the AI's suggestion, "" = no music, else a song
        m = dict(review["music"])
        if body["music"] is None:
            m.pop(cid, None)
        else:
            m[cid] = str(body["music"])
        review = {**review, "music": m}
    eff = state.effective_cand(cand, review)
    opts = ClipOptions.from_dict({**review["options"], **(body.get("options") or {})})
    fps = max(1, round(min(60.0, float(project.load_meta().get("fps") or 30))))
    plan = plan_mod.build(project, eff, opts, vertical=body.get("frame") != "wide", fps=fps)
    out = plan.to_dict()
    out["clip_id"] = cid
    out["suggestion"] = music.suggest(eff, project.load_meta().get("mode"))
    out["brand_preset"] = plan.brand
    if body.get("frame") != "wide":
        fc = body["facecam"] if "facecam" in body else review.get("facecam")
        w, h = _source_size(project)
        out["geometry"] = clips_mod.preview_geometry(opts.layout, w, h, Facecam.from_dict(fc))
        if body.get("samples"):  # the render's zoom at these source times (preview check)
            lay = out["geometry"]["layout"]
            out["samples"] = [clips_mod.picture_at(plan, lay, float(t)) for t in list(body["samples"])[:200]]
    return out


_SIZES: dict[tuple[str, float], tuple[int, int]] = {}


def _source_size(project) -> tuple[int, int]:
    """The picture size the renderer works with (clips.source_size, cached per file)."""
    meta = project.load_meta()
    src = project.source_path
    if src is None:
        return int(meta.get("width") or 1920), int(meta.get("height") or 1080)
    key = (str(src), src.stat().st_mtime)
    if key not in _SIZES:
        w, h, _ = clips_mod.source_size(src, meta)
        _SIZES[key] = (w, h)
    return _SIZES[key]


# ------------------------------------------------------------------ manual clips


@router.post("/api/projects/{project_id}/candidates")
def api_manual_add(project_id: str, body: dict) -> dict:
    """A clip marked by hand (I/O). It gets the AI analysis like the others."""
    A = _app()
    project = A._project(project_id)
    if not (project.dir / "highlights.json").is_file():
        raise SharkyClipsError("Find the highlights first; manual clips are added next to them.")
    try:
        start, end = float(body["start"]), float(body["end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SharkyClipsError("Mark an in point (I) and an out point (O) first.") from exc
    cand = manual.add(project, start, end)
    job = None
    if A.llm_available() and config.get("auto_analyze") is not False:
        hl = state.load_highlights(project) or {}
        lang = (hl.get("analysis") or {}).get("language")
        job = A.submit_analyze(project.id, lang=lang, ranks=[cand["rank"]]).to_dict()
    return {"candidate": state.candidate_view(cand), "job": job}


@router.delete("/api/projects/{project_id}/candidates/{cid}")
def api_manual_delete(project_id: str, cid: str) -> dict:
    project = _app()._project(project_id)
    if not manual.remove(project, cid):
        raise SharkyClipsError("Only clips you marked yourself can be removed.")
    review = state.load_review(project)
    state.save_review(project, {"accepted": [c for c in review["accepted"] if c != cid],
                                "rejected": [c for c in review["rejected"] if c != cid]})
    return {"removed": True}


# ------------------------------------------------------------------ music library


def _music_view() -> dict:
    return {"folder": str(music.folder()), "tracks": music.library(), "moods": list(music.MOODS),
            "credit_template": str(config.get("music_credit") or "Music: {title} by {artist}"),
            "credit_enabled": config.get("music_credit_enabled") is not False}


@router.get("/api/music")
def api_music() -> dict:
    return _music_view()


@router.put("/api/music/settings")
def api_music_settings(body: dict) -> dict:
    changes: dict[str, Any] = {}
    if "credit_template" in body:
        tpl = " ".join(str(body["credit_template"] or "").split())[:160]
        changes["music_credit"] = tpl or None
    if "credit_enabled" in body:
        changes["music_credit_enabled"] = bool(body["credit_enabled"])
    if changes:
        config.update(**changes)
    return _music_view()


def submit_music_analysis():
    A = _app()

    def run(job):
        def progress(i: int, n: int, name: str) -> None:
            A.jobs.update(job, stage="analyzing_music", progress=i / max(n, 1), detail={"name": name})

        return music.analyze_pending(progress)

    # CPU work in the downloads lane: it never waits for a long render batch. Governed like any job.
    return A.jobs.submit("music", "io", None, {}, run, key="music")


@router.put("/api/music/upload")
async def api_music_upload(request: Request, filename: str) -> dict:
    dest = music.upload_target(filename)
    part = dest.with_name("." + dest.name + ".part")
    size = 0
    try:
        with open(part, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > music.MAX_BYTES:
                    raise SharkyClipsError("This file is larger than 200 MB.")
                f.write(chunk)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    if size == 0:
        part.unlink(missing_ok=True)
        raise SharkyClipsError("The uploaded file is empty.")
    part.replace(dest)
    t = music.finish_upload(dest)
    submit_music_analysis()
    return t


@router.post("/api/music/analyze")
def api_music_analyze() -> dict:
    return submit_music_analysis().to_dict()


@router.put("/api/music/{name}")
def api_music_update(name: str, body: dict) -> dict:
    return music.update(name, body)


@router.delete("/api/music/{name}")
def api_music_delete(name: str) -> dict:
    return {"removed": music.delete(name)}


@router.get("/api/music/{name}/audio")
def api_music_audio(name: str):
    path = music.path_of(name)
    if path is None:
        raise SharkyClipsError("This song isn't in the music folder any more.")
    return FileResponse(path)


@router.post("/api/music/open")
def api_music_open(request: Request) -> dict:
    """Open the music folder in Explorer / Finder (only from this computer)."""
    if not _app()._is_local(request):
        raise SharkyClipsError("The folder can only be opened on the computer running SharkyClips.")
    path = str(music.folder())
    opener = {"win32": "explorer", "darwin": "open"}.get(sys.platform, "xdg-open")
    subprocess.Popen([opener, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **no_window())  # noqa: S603
    return {"ok": True, "folder": path}


# ------------------------------------------------------------------ brand kit


def _brand_view() -> dict:
    data = brand.load()
    return {**data, "positions": list(brand.POSITIONS)}


@router.get("/api/brand")
def api_brand() -> dict:
    return _brand_view()


@router.put("/api/brand")
def api_brand_put(body: dict) -> dict:
    presets = body.get("presets")
    if not isinstance(presets, list):
        raise SharkyClipsError("Send the list of brand presets.")
    brand.save(presets, body.get("active"))
    return _brand_view()


@router.get("/api/brand/channel")
def api_brand_channel() -> dict:
    """Brand kit > Channel text: channel hashtags, tag names and the socials block."""
    return _channel_view()


@router.put("/api/brand/channel")
def api_brand_channel_put(body: dict) -> dict:
    brand.save_channel_text(body or {})
    return _channel_view()


def _channel_view() -> dict:
    from .. import config

    lang = config.get("output_language") or "tr"
    return {**brand.channel_text(), "default_headings": brand.SOCIAL_HEADINGS,
            "preview": brand.socials_block(lang), "preview_lang": lang}


# ------------------------------------------------------------------ game banks (titles / hashtags / tags)


@router.get("/api/studio/games")
def api_games() -> dict:
    from ..titles import banks

    return {"games": [_game_view(g) for g in banks.ids()]}


def _game_view(gid: str) -> dict:
    from ..titles import banks

    bank = banks.get(gid)
    if gid != banks.GENERIC:  # show the game's own events / moments, not the generic fallback ones
        own = banks.merge(banks._builtin(gid), banks._user_all().get(gid) or {})
        bank = {**bank, "events": own.get("events", {}), "moments": own.get("moments", {})}
    return {"id": gid, "name": bank.get("name") or "", "custom": banks.is_custom(gid),
            "builtin": gid in banks.BUILTIN, "bank": {k: v for k, v in bank.items() if not k.startswith("_")}}


@router.put("/api/studio/games/{gid}")
def api_game_put(gid: str, body: dict) -> dict:
    from ..titles import banks

    data = body.get("bank") if isinstance(body, dict) else None
    errs = banks.validate(data)
    if errs:
        raise SharkyClipsError("This game bank can't be saved.", " ".join(errs[:4]))
    try:
        banks.save_user(gid, data)
    except ValueError as exc:
        raise SharkyClipsError("Use a short id: lowercase letters, numbers and _.") from exc
    return _game_view(gid)


@router.delete("/api/studio/games/{gid}")
def api_game_reset(gid: str) -> dict:
    """Back to the built-in bank (a game the user added is removed)."""
    from ..titles import banks

    banks.save_user(gid, None)
    return {"games": [_game_view(g) for g in banks.ids()]}


@router.put("/api/brand/{pid}/logo")
async def api_brand_logo(pid: str, request: Request, filename: str = "logo.png") -> dict:
    data = await request.body()
    brand.store_logo(pid, data, filename)
    return _brand_view()


@router.delete("/api/brand/{pid}/logo")
def api_brand_logo_delete(pid: str) -> dict:
    brand.remove_logo(pid)
    return _brand_view()


@router.get("/api/brand/{pid}/logo")
def api_brand_logo_file(pid: str):
    path = brand.logo_path(brand.get(pid))
    if path is None:
        raise SharkyClipsError("This preset has no logo.")
    return FileResponse(path, headers={"Cache-Control": "no-cache"})


# ------------------------------------------------------------------ word lists


def _lists_view() -> dict:
    custom_p = config.get("profanity_lists") or {}
    custom_f = config.get("filler_lists") or {}
    out: dict[str, Any] = {"profanity": {}, "fillers": {},
                           "silence_ms": {k: plan_mod.silence_ms(k) for k in ("light", "strong")},
                           "silence_default_ms": plan_mod.CUT_DEFAULT_MS}
    for code in languages.codes():
        out["profanity"][code] = {"words": profanity.word_list(code), "default": profanity.DEFAULTS.get(code, []),
                                  "custom": isinstance(custom_p.get(code), list)}
        out["fillers"][code] = {**fillers.lists(code), "default": fillers.DEFAULTS.get(code, {"sure": [], "maybe": []}),
                                "custom": isinstance(custom_f.get(code), dict)}
    out["learned"] = _learned_view()
    return out


def _learned_view() -> dict:
    """Swears learned from manual bleeps / unbleeps (edit/swearlearn.py), per language."""
    from ..edit import swearlearn

    out: dict[str, Any] = {}
    for code in languages.codes():
        add, ign = swearlearn.words(code, "add"), swearlearn.words(code, "ignore")
        if add or ign:
            def row(k: str, v: dict) -> dict:
                return {"word": k, "n": int(v.get("n", 0)), "spk": dict(v.get("spk") or {}), "last": v.get("last")}

            out[code] = {"add": sorted((row(k, v) for k, v in add.items()), key=lambda r: -r["n"]),
                         "ignore": sorted((row(k, v) for k, v in ign.items()), key=lambda r: -r["n"])}
    return out


@router.delete("/api/wordlists/learned")
def api_learned_delete(lang: str, word: str, kind: str = "add") -> dict:
    from ..edit import swearlearn

    languages.require(lang)
    if kind not in ("add", "ignore"):
        raise SharkyClipsError("Unknown list.")
    swearlearn.remove(lang, word, kind)
    return _lists_view()


def _words(v) -> list[str]:
    out: list[str] = []
    for w in v if isinstance(v, list) else []:
        w = " ".join(str(w).split())[:60]
        if w and w not in out:
            out.append(w)
    return out[:500]


@router.get("/api/wordlists")
def api_wordlists() -> dict:
    return _lists_view()


@router.put("/api/wordlists")
def api_wordlists_put(body: dict) -> dict:
    changes: dict[str, Any] = {}
    if isinstance(body.get("profanity"), dict):
        cur = dict(config.get("profanity_lists") or {})
        for code, words in body["profanity"].items():
            languages.require(code)
            if words is None:  # back to the built-in list
                cur.pop(code, None)
            else:
                cur[code] = _words(words)
        changes["profanity_lists"] = cur
    if isinstance(body.get("fillers"), dict):
        cur = dict(config.get("filler_lists") or {})
        for code, val in body["fillers"].items():
            languages.require(code)
            if val is None:
                cur.pop(code, None)
            elif isinstance(val, dict):
                cur[code] = {"sure": _words(val.get("sure")), "maybe": _words(val.get("maybe"))}
        changes["filler_lists"] = cur
    if isinstance(body.get("silence_ms"), dict):
        cur = dict(config.get("cut_silence_ms") or {})
        for k in ("light", "strong"):
            if k in body["silence_ms"]:
                cur[k] = int(max(150, min(5000, int(body["silence_ms"][k]))))
        changes["cut_silence_ms"] = cur
    if changes:
        config.update(**changes)
    return _lists_view()


def music_credit_for(clip_info: dict | None) -> str | None:
    """Credit line for a rendered clip / export that used a song (when the setting is on)."""
    m = (clip_info or {}).get("music")
    if not m or config.get("music_credit_enabled") is False:
        return None
    return music.credit_line(m)


__all__ = ["router", "music_credit_for", "submit_music_analysis"]
