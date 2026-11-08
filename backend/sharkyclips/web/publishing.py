"""Publishing API (1.2.7): the Library of publishable clips across projects, the publish setup of
one clip, scheduling (a time per clip or an automatic plan at the daily limit), and the loop that
prepares and uploads scheduled clips in advance.

The loop (Scheduler, one background thread, every minute and right after a publish job ends):
  1. a scheduled clip whose time has passed before it could be uploaded (the PC was off) moves
     to the next free slot
  2. the next clip in time order is prepared in the GPU lane (export with the chosen preset,
     optional cover burned into the first frame of a Short), then uploaded in the network lane
     as private with YouTube's publishAt (Publish now: with the chosen privacy)
  3. uploads only start while the governor lets work run (no game / stream / fullscreen video in
     Silent mode) and Google's daily API quota has room; failures retry with backoff, then the
     clip "needs attention" with the reason and a fix button
  4. every 6 hours (and after a release time passed) it fetches views / likes: they calibrate the
     viral score, teach the A/B hook bandit and tell whether uploads are still locked to private
Included by app.py (before its /api 404).
"""

from __future__ import annotations

import os
import shutil
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from .. import config, cover, governor, publishing as P
from ..clips import Facecam
from ..errors import SharkyClipsError
from ..project import Project
from . import state
from .jobs import ACTIVE, CLIP_KINDS, Job, automatic

router = APIRouter()
STATS_EVERY_H = 6
PLAN_KINDS = ("export", "cover_burn", "upload")


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


# ===================================================================== settings + defaults

DEFAULT_META = {
    "title": "", "description": "", "hashtags": [], "tags": [], "category": "20", "language": None,
    "made_for_kids": False, "privacy": "public", "playlist": None,
    "cover": {"kind": "face", "text": "", "burn": False},
    "preset": "youtube_shorts", "format": "mp4_h264", "burn_captions": True, "source": "auto",
    # 1.2.19: a dubbed clip says its voice is AI-made (description line + YouTube's synthetic flag)
    "ai_voice_note": True, "synthetic_media": True,
}
REMEMBER = ("made_for_kids", "privacy", "playlist", "preset", "format", "burn_captions", "source")


def publish_defaults() -> dict:
    saved = config.get("publish_defaults") or {}
    out = {**DEFAULT_META, **{k: v for k, v in saved.items() if k in REMEMBER or k == "cover"}}
    out["cover"] = {**DEFAULT_META["cover"], **({k: v for k, v in (saved.get("cover") or {}).items()
                                                  if k in ("kind", "burn")})}
    return out


def remember(meta: dict) -> None:
    """The next clip's setup starts from these choices (export preset, render options, ...)."""
    keep = {k: meta.get(k) for k in REMEMBER if k in meta}
    keep["cover"] = {"kind": (meta.get("cover") or {}).get("kind") or "face",
                     "burn": bool((meta.get("cover") or {}).get("burn"))}
    config.update(publish_defaults=keep)


def settings_view() -> dict:
    from .. import youtube

    limit = P.daily_limit()
    best = P.best_times()
    return {"daily_limit": limit, "effective_limit": P.effective_limit(), "quota_capacity": P.quota_capacity(),
            "times": P.configured_times(), "best_times": best, "learn_times": config.get("publish_learn_times") is not False,
            "auto": config.get("publish_auto") is not False, "quota": youtube.quota_view()}


# ===================================================================== clip data


def _cands(project: Project) -> dict[str, dict]:
    hl = state.load_highlights(project) or {}
    return {c["id"]: c for c in hl.get("candidates", [])}


def _mode(project: Project) -> str:
    return project.load_meta().get("mode") or "gaming"


def prefill(project: Project, cand: dict) -> dict:
    """A clip's publish setup from its AI publish package and the remembered choices."""
    from .. import youtube

    pub = cand.get("publish") or {}
    d = publish_defaults()
    title = (pub.get("titles") or [None])[0] or (cand.get("text") or "")[:90]
    from ..edit import brand

    text, tags_in_desc = P.split_hashtags(pub.get("description") or "")
    hashtags = tags_in_desc or [h if h.startswith("#") else f"#{h}" for h in (pub.get("hashtags") or [])[:8]]
    from ..titles import style

    if style.layout(pub.get("language")) is None or not tags_in_desc:
        chan = brand.channel_hashtags()  # the channel's own tags always lead (older analyses too)
        hashtags = chan + [h for h in hashtags if h.casefold() not in {c.casefold() for c in chan}]
    # My style: the creator's own order (game first, channel tag near the end) stays
    meta = project.load_meta()
    spoken = None
    if project.transcript_path.is_file():
        try:

            spoken = project.load_transcript().get("language")
        except Exception:  # noqa: BLE001
            spoken = None
    review = state.load_review(project)
    has_face = bool(review.get("facecam"))
    cover_kind = d["cover"]["kind"] if d["cover"]["kind"] != "face" or has_face else "peak"
    return {**d, "title": youtube.clean_text(title, 100), "description": text,
            "hashtags": [h.lstrip("#") for h in hashtags], "tags": P.suggest_tags(pub, meta, _mode(project)),
            "category": youtube.CATEGORY.get(_mode(project), "20"), "language": pub.get("language") or spoken,
            "cover": {**d["cover"], "kind": cover_kind, "text": pub.get("cover_text") or title}}


def learn_corrections(cand: dict, old: dict, new: dict) -> list:
    """My style: words the creator corrected in an AI title / description go into the glossary
    ("iki katil" -> "double kill") and are fixed in all future metadata."""
    from ..titles import style

    pub = cand.get("publish") or {}
    lang = new.get("language") or pub.get("language") or "tr"
    found = []
    try:
        title = new.get("title") or ""
        if title and title != old.get("title") and title not in (pub.get("titles") or []):
            from difflib import SequenceMatcher

            ai = [t for t in [old.get("title") or ""] + list(pub.get("titles") or []) if t]
            if ai:
                base = max(ai, key=lambda t: SequenceMatcher(None, t.casefold(), title.casefold()).ratio())
                found += style.learn_from_edit(base, title, lang)
        desc = new.get("description") or ""
        if desc and desc != (old.get("description") or ""):
            found += style.learn_from_edit(old.get("description") or "", desc, lang)
    except Exception:  # noqa: BLE001 - learning must never block saving
        return []
    return found


def _preset_is_short(meta: dict) -> bool:
    from .. import export

    p = export.PRESETS.get(meta.get("preset") or "")
    return p is None or p.frame == "vertical"


def clean_meta(m: dict, base: dict) -> dict:
    """Validate a publish setup from the UI (unknown keys dropped, limits applied)."""
    from .. import export, languages, youtube

    out = {**base}
    if "title" in m:
        out["title"] = youtube.clean_text(str(m.get("title") or ""), 100)
    if "description" in m:
        out["description"] = youtube.clean_text(str(m.get("description") or ""), 4500)
    if "hashtags" in m:
        tags = [str(h).strip().lstrip("#").replace(" ", "") for h in (m.get("hashtags") or [])]
        out["hashtags"] = [h for h in dict.fromkeys(tags) if h][:15]
    if "tags" in m:
        out["tags"] = youtube.clean_tags([str(t) for t in (m.get("tags") or [])])
    if "category" in m:
        c = str(m.get("category") or "20")
        out["category"] = c if c in youtube.CATEGORIES else "20"
    if "language" in m:
        lang = m.get("language") or None
        out["language"] = lang if lang is None or lang in languages.LANGUAGES else base.get("language")
    if "made_for_kids" in m:
        out["made_for_kids"] = bool(m.get("made_for_kids"))
    for k in ("ai_voice_note", "synthetic_media"):
        if k in m:
            out[k] = m.get(k) is not False
    if "privacy" in m:
        p = str(m.get("privacy") or "public")
        out["privacy"] = p if p in youtube.PRIVACY else "public"
    if "playlist" in m:
        pl = m.get("playlist")
        out["playlist"] = ({"id": str(pl.get("id")), "title": str(pl.get("title") or "")[:150]}
                           if isinstance(pl, dict) and pl.get("id") else None)
    if "cover" in m and isinstance(m.get("cover"), dict):
        c = m["cover"]
        kind = c.get("kind") if c.get("kind") in cover.KINDS else (base.get("cover") or {}).get("kind", "peak")
        out["cover"] = {"kind": kind, "text": " ".join(str(c.get("text") or "").split())[:80],
                        "burn": bool(c.get("burn"))}
    if "preset" in m:
        pr = m.get("preset") or "youtube_shorts"
        if pr not in export.PRESETS:
            raise SharkyClipsError(f"Unknown export preset '{pr}'.")
        out["preset"] = pr
    if "format" in m:
        fmt = m.get("format") or "mp4_h264"
        if fmt not in export.FORMATS or export.FORMATS[fmt].kind != "video":
            raise SharkyClipsError("YouTube needs a video format.")
        out["format"] = fmt
    if "burn_captions" in m:
        out["burn_captions"] = m.get("burn_captions") is not False
    if "source" in m:
        out["source"] = "export" if m.get("source") == "export" else "auto"
    if not out.get("title"):
        raise SharkyClipsError("The video needs a title.")
    return out


def _wide(meta: dict) -> bool:
    from .. import export

    p = export.PRESETS.get(meta.get("preset") or "youtube_shorts")
    return bool(p and p.frame == "wide")


# ===================================================================== library rows


def _plan_jobs() -> dict[str, list[Job]]:
    out: dict[str, list[Job]] = {}
    for j in _app().jobs.jobs():
        k = j.params.get("plan_key")
        if k and j.status in ACTIVE:
            out.setdefault(k, []).append(j)
    return out


def _publishable(project: Project, cands: dict, review: dict, clips: dict, ups: dict, items: dict) -> list[str]:
    from .. import export

    ids = set(review.get("accepted") or []) | set(clips) | set(ups)
    ids |= {e["clip_id"] for e in export.load_registry(project)}
    ids |= {it["clip_id"] for it in items.values() if it["project_id"] == project.id}
    return [c for c in cands if c in ids]


def _upload_view(u: dict | None) -> dict | None:
    if not u:
        return None
    return {k: u.get(k) for k in ("video_id", "url", "privacy", "requested_privacy", "publish_at", "published_at",
                                   "uploaded_at", "views", "likes", "stats_at", "thumbnail_error", "playlist_error")}


def row_status(item: dict | None, live: dict | None, jobs_: list[Job], lock: str, now: datetime) -> dict:
    """status: draft | scheduled | published | failed | locked; step: what the app does next."""
    if live:
        pa = P.parse(live.get("publish_at"))
        privacy = live.get("privacy")
        stats_at = P.parse(live.get("stats_at"))
        wanted = (live.get("requested_privacy") or privacy) in ("public", "unlisted") or pa is not None
        if pa and pa > now:
            return {"status": "scheduled", "step": "uploaded", "date": iso(pa)}
        if privacy in ("public", "unlisted"):
            return {"status": "published", "step": None, "date": live.get("published_at") or iso(pa) or live.get("uploaded_at")}
        if privacy == "private" and wanted:
            # after the release time, only fresh numbers from YouTube say it really stayed private
            checked = pa is None or (stats_at is not None and stats_at > pa + timedelta(minutes=5))
            if checked and lock != "unlocked":
                return {"status": "locked", "step": None, "date": iso(pa) or live.get("uploaded_at")}
            return {"status": "published", "step": "checking", "date": iso(pa) or live.get("uploaded_at")}
        return {"status": "published", "step": None, "date": live.get("uploaded_at")}
    if item and item.get("attention"):
        return {"status": "failed", "step": "attention", "date": item.get("publish_at")}
    if item and (item.get("publish_at") or item.get("now")):
        step = "waiting"
        running = next((j for j in jobs_ if j.status == "running"), None)
        queued = next((j for j in jobs_ if j.status == "queued"), None)
        j = running or queued
        if j is not None:
            step = {"export": "rendering", "cover_burn": "rendering", "upload": "uploading"}.get(j.kind, "waiting")
            if j.status == "queued":
                step = "queued_" + step
        elif item.get("error"):
            step = "retrying"
        return {"status": "scheduled", "step": step, "date": item.get("publish_at") or iso(now)}
    return {"status": "draft", "step": None, "date": None}


def iso(dt: datetime | None) -> str | None:
    return P.iso(dt)


def library_view(now: datetime | None = None) -> dict:
    from .. import youtube

    A = _app()
    now = now or P.now_utc()
    items = P.load()
    pj = _plan_jobs()
    lock = youtube.lock_state()["state"]
    rows: list[dict] = []
    for project in A.list_projects():
        cands = _cands(project)
        if not cands:
            continue
        review = state.load_review(project)
        clips = state.load_clips(project)
        ups = state.load_uploads(project)
        meta = project.load_meta()
        for cid in _publishable(project, cands, review, clips, ups, items):
            c = cands[cid]
            key = P.key_of(project.id, cid)
            item = items.get(key)
            live = state.live_upload(project, cid)
            jobs_ = pj.get(key, [])
            st = row_status(item, live, jobs_, lock, now)
            pub = c.get("publish") or {}
            eff = state.effective_cand(c, review)
            running = next((j for j in jobs_ if j.status == "running"), None)
            rows.append({
                "key": key, "project_id": project.id, "project_title": meta.get("title") or project.id,
                "clip_id": cid, "rank": c["rank"],
                "title": ((item or {}).get("meta") or {}).get("title") or (live or {}).get("title")
                or (pub.get("titles") or [None])[0] or (c.get("text") or "")[:90],
                "duration": eff["duration"], "viral_score": pub.get("viral_score"), "viral_label": pub.get("viral_label"),
                "accepted": cid in (review.get("accepted") or []), "rendered": cid in clips,
                **st, "planned": item is not None, "publish_at": (item or {}).get("publish_at") or (live or {}).get("publish_at"),
                "now": bool((item or {}).get("now")), "moved_from": (item or {}).get("moved_from"),
                "error": (item or {}).get("error"), "next_try_at": (item or {}).get("next_try_at"),
                "upload": _upload_view(live),
                "job": {"kind": running.kind, "stage": running.stage, "progress": running.progress,
                        "paused": running.to_dict().get("paused")} if running else None,
            })
    order = {"failed": 0, "scheduled": 1, "locked": 2, "draft": 3, "published": 4}
    rows.sort(key=lambda r: (order.get(r["status"], 9), r["date"] or "", -(r["viral_score"] or 0)))
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    st = youtube.status()
    return {"rows": rows, "counts": counts, "now": iso(now), **settings_view(),
            "youtube": {"connected": st["connected"], "manage": st["manage"], "channel": st["channel"],
                        "lock": st["lock"], "client": st["client"]}}


# ===================================================================== releases + planning helpers


def _live_uploads() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for project in _app().list_projects():
        for cid, lst in state.load_uploads(project).items():
            u = next((x for x in lst if x.get("video_id") and not x.get("missing")), None)
            if u:
                out[P.key_of(project.id, cid)] = u
    return out


def releases(now: datetime | None = None) -> dict[str, datetime]:
    return P.releases(P.load(), _live_uploads(), now)


def _item_for(project: Project, cid: str) -> dict:
    key = P.key_of(project.id, cid)
    item = P.get(key)
    if item is None:
        cand = _app()._cand(project, cid)
        item = P.new_item(project.id, cid, prefill(project, cand))
    return item


def schedule(clips: list[dict], mode: str, dry_run: bool = False, now: datetime | None = None) -> dict:
    """Schedule clips: mode "auto" spreads them over free slots (daily limit, best times),
    "manual" uses each clip's publish_at (a full day moves it to the next free slot)."""
    A = _app()
    now = now or P.now_utc()
    rel = releases(now)
    planned, skipped = [], []
    todo: list[tuple[str, dict, datetime | None]] = []
    for c in clips:
        pid, cid = str(c.get("project_id") or ""), str(c.get("clip_id") or "")
        key = P.key_of(pid, cid)
        try:
            project = A._project(pid)
            A._cand(project, cid)
        except Exception:  # noqa: BLE001 - HTTPException / SharkyClipsError
            skipped.append({"key": key, "reason": "missing"})
            continue
        if state.live_upload(project, cid):
            skipped.append({"key": key, "reason": "on_youtube"})
            continue
        if any(j.kind == "upload" for j in _plan_jobs().get(key, [])):
            skipped.append({"key": key, "reason": "uploading"})
            continue
        wanted = P.parse(c.get("publish_at")) if mode == "manual" else None
        if mode == "manual" and wanted is None:
            skipped.append({"key": key, "reason": "no_time"})
            continue
        todo.append((key, _item_for(project, cid), wanted))
    if mode == "auto":
        times = P.auto_plan([k for k, _i, _w in todo], rel, now)
        result = [(k, i, times[k], False) for k, i, _w in todo]
    else:
        result = []
        rel = {k: v for k, v in rel.items() if k not in {k2 for k2, _i, _w in todo}}
        for k, i, wanted in todo:
            t, moved = P.place(k, wanted, rel, now=now)
            rel[k] = t
            result.append((k, i, t, moved))
    for k, item, t, moved in result:
        planned.append({"key": k, "publish_at": iso(t), "moved": moved})
        if not dry_run:
            P.put({**P.unschedule(item), "meta": item["meta"], "prep": item.get("prep") or {}, "publish_at": iso(t),
                   "moved_from": None})
    if not dry_run and planned:
        scheduler.poke()
    return {"planned": planned, "skipped": skipped}


# ===================================================================== preparing files


def _prep_sig(project: Project, cand: dict, meta: dict, source: str) -> str:
    review = state.load_review(project)
    opts = dict(review["options"])
    return P.signature(opts, review["hooks"].get(cand["id"], ""), state.edit_fingerprint(cand, review, opts),
                       state.effective_cand(cand, review)["start"], state.effective_cand(cand, review)["end"],
                       meta.get("preset"), meta.get("format"), meta.get("burn_captions"), source,
                       (meta.get("cover") or {}) if (meta.get("cover") or {}).get("burn") and not _wide(meta) else None)


def _ab_choice(project: Project, cid: str, meta: dict) -> dict | None:
    """The A/B hook variant to upload (Thompson sampling when the real test runs)."""
    from .. import abtest

    if meta.get("source") == "export":
        return None
    entry = abtest.load_ab(project).get(cid)
    if not entry or not entry.get("variants"):
        return None
    if not all((project.dir / "clips" / "ab" / v["file"]).is_file() for v in entry["variants"].values()):
        return None
    if _wide(meta):  # variants are 9:16 clips
        return None
    pick = abtest.choose_for_upload(entry)
    return pick if pick.get("label") else None


def _burns(meta: dict) -> bool:
    cv = meta.get("cover") or {}
    return bool(cv.get("burn")) and not _wide(meta) and cv.get("kind") not in (None, "none")


def next_step(project: Project, cand: dict, item: dict) -> tuple[str, dict]:
    """What a scheduled clip needs next: ("export" | "burn" | "upload", info). Restart-safe:
    everything it decides is read back from the item's `prep` and the export registry."""
    from .. import export

    key = P.key_of(project.id, cand["id"])
    meta = item["meta"]
    if state.bleep_hold(project, cand["id"]):  # 1.2.31: a swear is still heard: the user checks first
        return "wait", {"reason": "bleep_check"}
    if meta.get("source") == "clip":  # Easy mode: the rendered 9:16 clip itself
        from .easy import clip_step

        return clip_step(project, cand)
    prep = dict(item.get("prep") or {})
    base = _prep_sig(project, cand, meta, "base")
    if prep.get("ab_for") == base:  # the A/B variant is chosen once (Thompson sampling is random)
        ab = prep.get("ab")
    else:
        ab = _ab_choice(project, cand["id"], meta)
        prep.update(ab=ab, ab_for=base)
        P.patch(key, prep=prep)
    source = f"ab:{ab['label']}" if ab else "export"
    sig = P.signature(base, source)
    burn = _burns(meta)
    pend = prep.get("pending") or {}
    if pend.get("sig") == sig and prep.get("sig") != sig:  # an export finished (maybe before a restart)
        entry = next((e for e in export.load_registry(project) if e["id"] == pend.get("stem")), None)
        media = next((f["name"] for f in (entry or {}).get("files", []) if f.get("role") == "media"), None)
        if media and str(entry.get("created_at") or "") >= str(pend.get("at") or ""):
            prep.update(sig=sig, file=media, cover_file=None, pending=None)
            P.patch(key, prep=prep)

    def ok(f: str | None) -> bool:
        return bool(f) and (f.startswith("ab:") or export.file_path(project, f) is not None)

    info = {"ab": ab, "sig": sig}
    if prep.get("sig") == sig:
        if burn and ok(prep.get("cover_file")):
            return "upload", {**info, "source": prep["cover_file"]}
        if not burn and ok(prep.get("file")):
            return "upload", {**info, "source": prep["file"]}
        if burn and ok(prep.get("file")):
            return "burn", {**info, "input": prep["file"]}
    if ab:
        return ("burn", {**info, "input": source}) if burn else ("upload", {**info, "source": source})
    return "export", info


def _export_request(meta: dict) -> dict:
    return {"format": meta.get("format") or "mp4_h264", "preset": meta.get("preset") or "youtube_shorts",
            "burn_captions": meta.get("burn_captions") is not False}


def submit_export_for(key: str, info: dict) -> Job:
    """The export of a scheduled clip (GPU lane); its result becomes the item's file."""
    from .. import export

    A = _app()
    item = P.get(key)
    pid, cid = item["project_id"], item["clip_id"]
    req = _export_request(item["meta"])
    project = A.get_project(pid)
    cand = A._cand(project, cid)
    stem = export.export_stem(cand, export.ExportRequest.from_dict(req))
    P.patch(key, prep={**(item.get("prep") or {}),
                       "pending": {"stem": stem, "sig": info["sig"], "at": iso(P.now_utc())}})
    job = A.submit_export(pid, cid, req)
    job.params["plan_key"] = key  # saved with the queue: the Library shows it, failures come back here
    A.jobs.bump()
    return job


def submit_cover_burn(key: str, info: dict, job_id: str | None = None, attempt: int = 1) -> Job:
    """A Short's cover as its first ~0.3 s (GPU lane: one re-encode of the clip)."""
    from .. import export
    from ..export import PRESETS

    A = _app()
    item = P.get(key) or {}
    pid, cid = item["project_id"], item["clip_id"]
    project = A.get_project(pid)
    cand = A._cand(project, cid)

    def run(job: Job):
        from .retention import upload_source

        it = P.get(key)
        if it is None:
            raise SharkyClipsError("This clip isn't scheduled any more.")
        meta = it["meta"]
        project = A.get_project(pid)
        review = state.load_review(project)
        cnd = state.effective_cand(A._cand(project, cid), review)
        src_name = info["input"]
        ab = upload_source(project, cid, src_name)
        src = ab[0] if ab else export.file_path(project, src_name)
        if src is None or not src.is_file():
            raise _file_error("The exported clip is missing.")
        A.jobs.update(job, stage="cover", progress=None)
        cv = meta.get("cover") or {}
        img = make_cover_for(project, cnd, review, cv.get("kind") or "peak", cv.get("text") or meta.get("title") or "",
                             "tall", meta.get("language"))
        stem = f"{cand['rank']:02d}_{cid}_publish_cover"
        dest = export.exports_root(project) / f"{stem}.mp4"
        dest.parent.mkdir(parents=True, exist_ok=True)
        A.jobs.update(job, stage="exporting", progress=0.0)
        preset = PRESETS.get(meta.get("preset") or "youtube_shorts")
        cover.burn_first_frame(src, img, dest, bitrate_k=preset.bitrate_k if preset else 12000,
                               on_progress=lambda s: A.jobs.update(job, progress=min(1.0, s / max(cnd["duration"], 0.1))))
        export._save_entry(project, {"id": stem, "clip_id": cid, "rank": cand["rank"], "format": "mp4_h264",
                                     "preset": meta.get("preset"), "request": {"cover_first_frame": True},
                                     "files": [export._file_entry(dest, "media", "video/mp4")],
                                     "duration": cnd["duration"], "encoder": None, "seconds": 0,
                                     "created_at": P.iso(P.now_utc()), "frame": "vertical", "warnings": [],
                                     "publish_cover": True})
        it = P.get(key) or it
        P.patch(key, prep={**(it.get("prep") or {}), "sig": info["sig"], "file": src_name, "cover_file": dest.name},
                attempts=0, error=None)
        return {"file": dest.name}

    params = {"clip_id": cid, "rank": cand["rank"], "plan_key": key, "info": info, "duration": cand["duration"],
              "title": (item.get("meta") or {}).get("title"), "project_title": project.load_meta().get("title") or pid}
    return A.jobs.submit("cover_burn", "gpu", pid, params, run, key=f"cover_burn:{key}", persist=True,
                         job_id=job_id, attempt=attempt)


def make_cover_for(project: Project, cand: dict, review: dict, kind: str, text: str, frame: str,
                   lang: str | None) -> Path:
    from .. import aicovers

    facecam = Facecam.from_dict(review.get("facecam"))
    if kind == "ai" and not aicovers.has_chosen(project, cand["id"], frame):
        kind = "face"  # no AI picture of this size yet: the facecam frame (1.2.18 fallback)
    if kind == "face" and not cover.best_face(project, cand, facecam):
        kind = "peak"  # no face in this clip: the AI idea instead
    return cover.make_cover(project, cand, facecam, kind, text, frame, lang)


def default_cover_kind(project: Project, cid: str, review: dict, frame: str = "tall") -> str:
    """The cover a one-click upload / download uses: the chosen AI picture, else the facecam frame."""
    from .. import aicovers

    if aicovers.has_chosen(project, cid, frame):
        return "ai"
    return "face" if review.get("facecam") else "peak"


def _file_error(msg: str) -> SharkyClipsError:
    e = SharkyClipsError(msg, "SharkyClips renders it again by itself.")
    e.reason = "file"  # type: ignore[attr-defined]
    return e


def upload_body(project: Project, cand: dict, item: dict, source: str, ab: dict | None) -> dict:
    """The upload job's body for a scheduled / publish-now clip."""
    from .. import export

    meta = item["meta"]
    credit = None
    e = next((x for x in export.load_registry(project) if any(f["name"] == source for f in x["files"])), None)
    if e and (e.get("music") or {}).get("credit"):
        credit = e["music"]["credit"]
    body = {"source": source, "title": meta["title"],
            "description": P.compose_description(meta.get("description") or "", meta.get("hashtags") or [], credit,
                                                 lang=meta.get("language") or (cand.get("publish") or {}).get("language"),
                                                 short=_app().is_short_source(project, source)),
            "tags": meta.get("tags") or [], "made_for_kids": bool(meta.get("made_for_kids")),
            "language": meta.get("language"), "category": meta.get("category") or "20",
            "plan_key": P.key_of(project.id, cand["id"]),
            "playlist_id": (meta.get("playlist") or {}).get("id"),
            "ai_voice_note": meta.get("ai_voice_note") is not False,
            "synthetic_media": meta.get("synthetic_media") is not False}
    if item.get("now"):
        body.update(privacy=meta.get("privacy") or "public", publish_at=None)
    else:
        body.update(privacy="private", publish_at=item["publish_at"])
    if ab and not source.startswith("ab:"):  # the variant with the cover burned in: still teaches the bandit
        from .. import abtest

        entry = abtest.load_ab(project).get(cand["id"]) or {}
        v = (entry.get("variants") or {}).get(ab["label"]) or {}
        body["hook_override"] = {"hook_variant": ab["label"], "hook_style": v.get("style"),
                                 "hook_chosen_by": ab.get("how") or "manual"}
    elif ab:
        body["ab_how"] = ab.get("how") or "manual"
    cv = meta.get("cover") or {}
    if _wide(meta) and cv.get("kind") not in (None, "none"):
        review = state.load_review(project)
        if cv.get("kind") != "custom":
            img = make_cover_for(project, state.effective_cand(cand, review), review, cv["kind"],
                                 cv.get("text") or meta["title"], "wide", meta.get("language"))
            dest = project.cache_dir / "thumbnails" / f"{cand['id']}.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(img, dest)
        body["thumbnail"] = "custom"
    elif source == "clip" and cv.get("kind") not in (None, "none"):
        body["thumbnail"] = "cover"  # Easy mode: the 9:16 cover, made in the upload job
    else:
        body["thumbnail"] = "none"
    return body


# ===================================================================== upload results (called by app.submit_upload)


def on_uploaded(key: str, entry: dict, body: dict) -> dict:
    """An upload of a planned clip finished: remember it, put it into its playlist."""
    from .. import youtube

    note = None
    pl = body.get("playlist_id")
    if pl:
        try:
            youtube.add_to_playlist(pl, entry["video_id"])
        except SharkyClipsError as exc:
            note = exc.message
    P.patch(key, video_id=entry["video_id"], uploaded_at=entry.get("uploaded_at"), attempts=0, error=None,
            attention=False, next_try_at=None, now=False)
    return {"playlist_error": note} if note else {}


def on_failed(key: str, exc: BaseException) -> None:
    from .jobs import JobCancelled

    if isinstance(exc, JobCancelled):
        return
    item = P.get(key)
    if item is None:
        return
    nxt = P.after_failure(item, exc)
    if (nxt.get("error") or {}).get("fix") == "reschedule" and item.get("publish_at"):
        try:  # the release time passed meanwhile: the next free slot
            rel = releases()
            t = P.next_free_slot(P.earliest(), rel, skip={key})
            nxt.update(publish_at=iso(t), moved_from=item["publish_at"], attention=False, next_try_at=None)
        except SharkyClipsError:
            pass
    P.put(nxt)


# ===================================================================== the loop


class Scheduler:
    def __init__(self):
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.last_tick: float = 0.0
        self.last_actions: list[str] = []
        self._stats_try = 0.0
        self._hooks_try = 0.0

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="sharkyclips-publish", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def poke(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        self._wake.wait(30)  # let the server start first
        while not self._stop.is_set():
            self._wake.clear()
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - never let the loop die
                from ..ui import console

                console.print(f"[red]Publish scheduler:[/]\n{traceback.format_exc()}")
            self._wake.wait(60)

    def tick(self, now: datetime | None = None) -> list[str]:
        with self._lock, automatic():  # background logic: never restarts what the user cancelled
            acts = self._tick(now or P.now_utc())
            try:  # 1.2.34 Autopilot: sign-in health check + the morning summary
                from .. import autopilot

                acts += autopilot.tick()
            except Exception:  # noqa: BLE001 - never stops the publish loop
                pass
            self.last_tick = time.time()
            self.last_actions = acts
            return acts

    def _tick(self, now: datetime) -> list[str]:
        from .. import youtube

        A = _app()
        acts: list[str] = []
        items = P.load()
        pj = _plan_jobs()
        # 1. keep the plan in line with YouTube / the projects
        for key, it in list(items.items()):
            try:
                project = A.get_project(it["project_id"])
                cand = A._cand(project, it["clip_id"])
            except Exception:  # noqa: BLE001
                if (it.get("publish_at") or it.get("now")) and not it.get("attention"):
                    P.put({**it, "attention": True, "error": {"message": "This clip or its project is gone.",
                                                               "hint": None, "fix": "edit", "at": iso(now)}})
                    acts.append(f"gone:{key}")
                continue
            live = state.live_upload(project, it["clip_id"])
            if it.get("video_id") and (live is None or live.get("video_id") != it["video_id"]):
                if live is None:  # deleted on YouTube (or cancelled elsewhere): a draft again
                    P.put(P.unschedule(it))
                    acts.append(f"vanished:{key}")
                    continue
            if live and not it.get("video_id") and (it.get("publish_at") or it.get("now")):
                P.patch(key, video_id=live["video_id"], uploaded_at=live.get("uploaded_at"), now=False,
                        publish_at=live.get("publish_at"), attention=False, error=None)
                acts.append(f"adopted:{key}")
                continue
            items[key] = it
            it["_cand"] = cand
            it["_project"] = project
        # 2. missed release times (the PC was off): the next free slot
        rel = None
        for key, it in items.items():
            if "_cand" not in it or it.get("video_id") or not it.get("publish_at") or pj.get(key):
                continue
            t = P.parse(it["publish_at"])
            if t is not None and t < P.earliest(now):
                rel = rel if rel is not None else releases(now)
                nt = P.next_free_slot(P.earliest(now), rel, skip={key})
                rel[key] = nt
                P.patch(key, publish_at=iso(nt), moved_from=it.get("moved_from") or it["publish_at"])
                it["publish_at"] = iso(nt)
                acts.append(f"moved:{key}")
        if config.get("publish_auto") is False or not youtube.connected():
            return acts
        # 3. the next steps, earliest release first
        gpu_busy = any(j.lane == "gpu" for js in pj.values() for j in js)
        up_busy = any(j.kind == "upload" for js in pj.values() for j in js)
        g = governor.get()
        may_upload = g is None or not g.paused
        due = sorted((it for it in items.values() if "_cand" in it and P.due(it, now) and not pj.get(P.key_of(it["project_id"], it["clip_id"]))),
                     key=lambda it: (not it.get("now"), it.get("publish_at") or ""))
        for it in due:
            if gpu_busy and up_busy:
                break
            key = P.key_of(it["project_id"], it["clip_id"])
            project, cand = it.pop("_project"), it.pop("_cand")
            if A.jobs.blocks_clip(project.id, cand["id"], key):
                acts.append(f"cancelled:{key}")  # the user cancelled its render / export / upload
                continue
            try:
                step, info = next_step(project, cand, it)
                if step == "wait":  # Easy clip still rendering
                    continue
                if step == "export" and not gpu_busy:
                    submit_export_for(key, info)
                    gpu_busy = True
                    acts.append(f"export:{key}")
                elif step == "burn" and not gpu_busy:
                    submit_cover_burn(key, info)
                    gpu_busy = True
                    acts.append(f"burn:{key}")
                elif step == "upload" and not up_busy:
                    if not may_upload:
                        acts.append(f"governor:{key}")
                        continue
                    need = youtube.COST["upload"] + (youtube.COST["thumbnail"] if _wide(it["meta"]) else 0)
                    if youtube.daily_quota() - youtube.quota_used() < need:
                        P.patch(key, next_try_at=iso(youtube.next_reset()))
                        acts.append(f"quota:{key}")
                        continue
                    if it.get("publish_at"):  # the item's time must still be ahead
                        t = P.parse(it["publish_at"])
                        if t is not None and t < P.earliest(now):
                            continue
                    body = upload_body(project, cand, it, info["source"], info.get("ab"))
                    A.submit_upload(project.id, cand["id"], body)
                    up_busy = True
                    acts.append(f"upload:{key}")
            except SharkyClipsError as exc:
                on_failed(key, exc)
                acts.append(f"failed:{key}")
        # 4. views / likes (calibration, the hook bandit, the private lock)
        acts += self._sync(now)
        return acts

    def _sync(self, now: datetime) -> list[str]:
        from .. import abtest, youtube

        A = _app()
        acts = []
        last = youtube.last_synced()
        ups = _live_uploads()
        if ups and time.time() - self._stats_try > 1800:
            passed = any((t := P.parse(u.get("publish_at"))) is not None and last < t.timestamp() + 600
                         and t + timedelta(minutes=10) <= now for u in ups.values())
            if passed or time.time() - last > STATS_EVERY_H * 3600:
                self._stats_try = time.time()
                A.submit_youtube_stats()
                acts.append("stats")
        if time.time() - self._hooks_try > 3600:
            self._hooks_try = time.time()
            try:
                if abtest.due_uploads(A.list_projects()):
                    from .retention import submit_hook_fetch

                    submit_hook_fetch()
                    acts.append("hooks")
            except Exception:  # noqa: BLE001
                pass
        return acts


scheduler = Scheduler()


_installed: list = []


def install(jobs) -> None:
    """Start the loop (the web server) and wake it when a publish job ends."""
    if jobs in _installed:
        return
    _installed.append(jobs)

    def finished(job: Job) -> None:
        if job.params.get("plan_key") or job.kind in PLAN_KINDS:
            if job.status == "error" and job.params.get("plan_key") and job.kind in ("export", "cover_burn"):
                exc = _file_error((job.error or {}).get("message") or "Rendering failed.")
                on_failed(job.params["plan_key"], exc)
            scheduler.poke()

    jobs.on_finished.append(finished)
    # tests drive scheduler.tick() themselves (conftest sets SHARKYCLIPS_PUBLISH_LOOP=0)
    if os.environ.get("SHARKYCLIPS_PUBLISH_LOOP") != "0" and os.environ.get("SHARKYCLIPS_NO_GOVERNOR") != "1":
        scheduler.start()


# ===================================================================== API


def _key_parts(project_id: str, cid: str) -> tuple[Project, dict, str]:
    A = _app()
    project = A._project(project_id)
    return project, A._cand(project, cid), P.key_of(project.id, cid)


@router.get("/api/library")
def api_library() -> dict:
    return library_view()


@router.get("/api/library/settings")
def api_library_settings() -> dict:
    return settings_view()


@router.put("/api/library/settings")
def api_library_settings_put(body: dict) -> dict:
    changes: dict = {}
    if "daily_limit" in body:
        changes["publish_daily_limit"] = max(1, min(50, int(body["daily_limit"])))
    if "times" in body:
        times = sorted({t for t in (P._hhmm(x) for x in body.get("times") or []) if t})
        if not times:
            raise SharkyClipsError("Add at least one release time.")
        changes["publish_times"] = times
    if "learn_times" in body:
        changes["publish_learn_times"] = bool(body["learn_times"])
    if "auto" in body:
        changes["publish_auto"] = bool(body["auto"])
    if changes:
        config.update(**changes)
        scheduler.poke()
    return settings_view()


@router.get("/api/library/{project_id}/{cid}/setup")
def api_setup(project_id: str, cid: str) -> dict:
    from .. import abtest, export, youtube

    project, cand, key = _key_parts(project_id, cid)
    item = P.get(key)
    meta = (item or {}).get("meta") or prefill(project, cand)
    pub = cand.get("publish") or {}
    review = state.load_review(project)
    eff = state.effective_cand(cand, review)
    text, desc_tags = P.split_hashtags(pub.get("description") or "")
    entry = abtest.load_ab(project).get(cid)
    ab = None
    if entry and entry.get("variants"):
        ab = {"labels": sorted(entry["variants"]), "styles": {k: v.get("style") for k, v in entry["variants"].items()},
              "pick": abtest.choose_for_upload(entry)}
    live = state.live_upload(project, cid)
    st = youtube.status()
    return {
        "key": key, "meta": meta, "item": {k: v for k, v in (item or {}).items() if k != "meta"} if item else None,
        "ai": {"titles": pub.get("titles") or [], "description": text, "hashtags": [h.lstrip("#") for h in (desc_tags or pub.get("hashtags") or [])],
               "tags": P.suggest_tags(pub, project.load_meta(), _mode(project)), "cover_text": pub.get("cover_text"),
               "cover_prompt": pub.get("cover_prompt"), "available": bool(pub.get("available"))},
        "clip": {"rank": cand["rank"], "duration": eff["duration"], "text": cand.get("text"),
                 "viral_score": pub.get("viral_score"), "has_facecam": bool(review.get("facecam")),
                 "has_custom_thumb": (project.cache_dir / "thumbnails" / f"{cid}.jpg").is_file()},
        "presets": [{"id": p.id, "label": p.label, "frame": p.frame, "max_seconds": p.max_seconds}
                    for p in export.PRESETS.values()],
        "warnings": export.check_length(meta.get("preset"), eff["duration"]),
        "categories": list(youtube.CATEGORIES), "ab": ab, "upload": _upload_view(live),
        # not made yet: the file to come follows the clip's dub choice ("" = no file of its own)
        "ai_voice": _app().ai_voice_disclosure(project, cid, "", meta),
        "youtube": {"connected": st["connected"], "manage": st["manage"], "channel": st["channel"], "lock": st["lock"]},
        "limits": settings_view(),
    }


@router.put("/api/library/{project_id}/{cid}")
def api_setup_save(project_id: str, cid: str, body: dict) -> dict:
    """Save a clip's publish setup. When it is already on YouTube, the change goes there too."""
    from .. import youtube

    project, cand, key = _key_parts(project_id, cid)
    item = _item_for(project, cid)
    meta = clean_meta(body.get("meta") or {}, item["meta"])
    learn_corrections(cand, item["meta"], meta)
    live = state.live_upload(project, cid)
    applied = None
    if live:
        note = (live.get("ai_voice") or {}).get("line") if (live.get("ai_voice") or {}).get("note") else None
        snippet = youtube.build_body(meta["title"],
                                     youtube.with_note(P.compose_description(meta.get("description") or "", meta.get("hashtags") or [],
                                                                           lang=meta.get("language"),
                                                                           short=_preset_is_short(meta)), note),
                                     meta.get("tags") or [], "private", None, meta["made_for_kids"],
                                     meta.get("category") or "20", meta.get("language"))["snippet"]
        youtube.update_video(live["video_id"], snippet=snippet)
        state.patch_upload(project, cid, live["video_id"], {"title": snippet["title"]})
        applied = "youtube"
        old_pl = ((item.get("meta") or {}).get("playlist") or {}).get("id")
        new_pl = (meta.get("playlist") or {}).get("id")
        if new_pl and new_pl != old_pl:
            youtube.add_to_playlist(new_pl, live["video_id"])
        cv = meta.get("cover") or {}
        if _wide(meta) and cv != (item["meta"].get("cover") or {}) and cv.get("kind") not in (None, "none"):
            review = state.load_review(project)
            img = make_cover_for(project, state.effective_cand(cand, review), review, cv["kind"],
                                 cv.get("text") or meta["title"], "wide", meta.get("language"))
            youtube.set_thumbnail(live["video_id"], img)
    P.put({**item, "meta": meta})  # next_step compares signatures: a changed preset / cover re-renders
    remember(meta)
    scheduler.poke()
    return {"ok": True, "applied": applied, "meta": meta}


def _restart_clip(project_id: str, cid: str) -> None:
    """The user (re)scheduled or retried this clip: earlier cancels of its work no longer apply."""
    _app().jobs.clear_tombstones(project_id, CLIP_KINDS, clip_id=cid)


@router.post("/api/library/schedule")
def api_schedule(body: dict) -> dict:
    mode = "manual" if body.get("mode") == "manual" else "auto"
    for c in list(body.get("clips") or []):
        if isinstance(c, dict) and c.get("project_id") and c.get("clip_id") and not body.get("dry_run"):
            _restart_clip(str(c["project_id"]), str(c["clip_id"]))
    return schedule(list(body.get("clips") or []), mode, bool(body.get("dry_run")))


@router.post("/api/library/{project_id}/{cid}/reschedule")
def api_reschedule(project_id: str, cid: str, body: dict) -> dict:
    """A new release time (calendar drag: a full day is refused, not moved)."""
    from .. import youtube

    project, cand, key = _key_parts(project_id, cid)
    _restart_clip(project.id, cid)
    wanted = P.parse(body.get("publish_at"))
    if wanted is None:
        raise SharkyClipsError("Pick a date and time.")
    rel = releases()
    t, moved = P.place(key, wanted, rel, strict=bool(body.get("strict", True)))
    live = state.live_upload(project, cid)
    item = _item_for(project, cid)
    if live:
        pa = P.parse(live.get("publish_at"))
        if not pa or pa <= P.now_utc():
            raise SharkyClipsError("This clip is already out; it can't be rescheduled.")
        zulu = t.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        youtube.update_video(live["video_id"], status={"privacyStatus": "private", "publishAt": zulu,
                                                       "selfDeclaredMadeForKids": bool(item["meta"].get("made_for_kids"))})
        state.patch_upload(project, cid, live["video_id"], {"publish_at": iso(t)})
    P.put({**item, "publish_at": iso(t), "now": False, "moved_from": None, "attention": False, "error": None,
           "next_try_at": None, "video_id": live["video_id"] if live else item.get("video_id")})
    scheduler.poke()
    return {"publish_at": iso(t), "moved": moved}


@router.post("/api/library/{project_id}/{cid}/publish-now")
def api_publish_now(project_id: str, cid: str) -> dict:
    from .. import youtube

    project, cand, key = _key_parts(project_id, cid)
    _restart_clip(project.id, cid)
    item = _item_for(project, cid)
    privacy = item["meta"].get("privacy") or "public"
    rel = releases()
    if privacy != "private":
        today = P.day_counts(rel, {key}).get(P.local_day(P.now_utc()), 0)
        if today >= P.effective_limit():
            raise SharkyClipsError(f"Today is full ({today}/{P.effective_limit()} releases).",
                                   "Schedule it for another day, or raise the daily limit in Settings.")
    live = state.live_upload(project, cid)
    if live:
        pa = P.parse(live.get("publish_at"))
        if not pa or pa <= P.now_utc():
            raise SharkyClipsError("This clip is already out.")
        res = youtube.update_video(live["video_id"], status={"privacyStatus": privacy,
                                                             "selfDeclaredMadeForKids": bool(item["meta"].get("made_for_kids"))})
        got = (res.get("status") or {}).get("privacyStatus") or privacy
        if privacy in ("public", "unlisted"):
            (youtube.mark_unlocked if got in ("public", "unlisted") else youtube.mark_locked)(live["video_id"])
        state.patch_upload(project, cid, live["video_id"], {"publish_at": None, "requested_privacy": privacy,
                                                            "privacy": got, "published_at": iso(P.now_utc())})
        P.put({**item, "publish_at": None, "now": False, "video_id": live["video_id"]})
        return {"ok": True, "privacy": got}
    if not youtube.connected():
        raise SharkyClipsError("Connect YouTube first (Settings > YouTube).")
    P.put({**P.unschedule(item), "meta": item["meta"], "prep": item.get("prep") or {}, "now": True})
    scheduler.poke()
    return {"ok": True, "queued": True}


@router.post("/api/library/{project_id}/{cid}/cancel")
def api_cancel(project_id: str, cid: str) -> dict:
    """Unschedule: stops its jobs and deletes a scheduled upload from YouTube."""
    from .. import youtube

    A = _app()
    project, cand, key = _key_parts(project_id, cid)
    for j in _plan_jobs().get(key, []):
        A.jobs.cancel(j.id)
    live = state.live_upload(project, cid)
    deleted = False
    if live:
        pa = P.parse(live.get("publish_at"))
        if not pa or pa <= P.now_utc():
            raise SharkyClipsError("This clip is already out on YouTube.", "Delete it in YouTube Studio if you want it gone.")
        deleted = youtube.delete_video(live["video_id"])
        state.patch_upload(project, cid, live["video_id"], {"missing": True, "cancelled": True,
                                                            "cancelled_at": iso(P.now_utc())})
    item = P.get(key)
    if item:
        P.put(P.unschedule(item))
    scheduler.poke()
    return {"ok": True, "deleted": deleted}


@router.post("/api/library/{project_id}/{cid}/retry")
def api_retry(project_id: str, cid: str) -> dict:
    """The fix button of a clip that needs attention."""
    project, cand, key = _key_parts(project_id, cid)
    _restart_clip(project.id, cid)
    item = P.get(key)
    if item is None:
        raise SharkyClipsError("This clip isn't scheduled.")
    fix = (item.get("error") or {}).get("fix")
    nxt = {**item, "attention": False, "attempts": 0, "next_try_at": None, "error": None}
    if fix == "rerender":
        nxt["prep"] = {}
    if item.get("publish_at"):
        t = P.parse(item["publish_at"])
        if t is not None and t < P.earliest():
            nxt["publish_at"] = iso(P.next_free_slot(P.earliest(), releases(), skip={key}))
            nxt["moved_from"] = item["publish_at"]
    P.put(nxt)
    scheduler.poke()
    return {"ok": True, "publish_at": nxt.get("publish_at")}


@router.delete("/api/library/{project_id}/{cid}")
def api_forget(project_id: str, cid: str) -> dict:
    """Forget a draft's publish setup (back to the AI's suggestions)."""
    project, cand, key = _key_parts(project_id, cid)
    item = P.get(key)
    if item and (item.get("publish_at") or item.get("now") or item.get("video_id")):
        raise SharkyClipsError("Cancel the schedule first.")
    P.remove(key)
    return {"ok": True}


@router.get("/api/library/{project_id}/{cid}/covers")
def api_covers(project_id: str, cid: str) -> dict:
    project, cand, key = _key_parts(project_id, cid)
    review = state.load_review(project)
    eff = state.effective_cand(cand, review)
    best = cover.best_face(project, eff, Facecam.from_dict(review.get("facecam")))
    if best:
        best = {**best, "at": round(max(0.0, best["t"] - float(eff["start"])), 1)}
    return {"face": best, "moments": cover.moments(eff),
            "custom": (project.cache_dir / "thumbnails" / f"{cid}.jpg").is_file()}


@router.get("/api/library/{project_id}/{cid}/cover.jpg")
def api_cover(project_id: str, cid: str, kind: str = "peak", frame: str = "wide", text: str = "",
              lang: str | None = None):
    project, cand, key = _key_parts(project_id, cid)
    review = state.load_review(project)
    path = make_cover_for(project, state.effective_cand(cand, review), review, kind, text, frame, lang)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/api/youtube/playlists")
def api_playlists(refresh: bool = False) -> dict:
    from .. import youtube

    if not youtube.connected():
        return {"items": [], "connected": False}
    return {"items": youtube.playlists(refresh), "connected": True}


@router.post("/api/youtube/playlists")
def api_playlist_create(body: dict) -> dict:
    from .. import youtube

    return youtube.create_playlist(str(body.get("title") or ""), str(body.get("privacy") or "public"))


@router.get("/api/youtube/verification")
def api_verification(request: Request) -> dict:
    """docs/google-verification.md (what to submit to Google so uploads stop being private)."""
    path = config.REPO_ROOT / "docs" / "google-verification.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return {"markdown": text, "url": "https://github.com/utkualsir/sharkyclips/blob/main/docs/google-verification.md"}


@router.post("/api/library/tick")
def api_tick(request: Request) -> dict:
    """Run the publish loop once now (the Library's refresh button)."""
    if not _app()._is_local(request):
        return {"actions": []}
    return {"actions": scheduler.tick()}
