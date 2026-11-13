"""Publish queue API (1.2.40): see pubqueue.py. The uploads happen in the browser (Claude in
Chrome); this only prepares files, texts and the calendar."""

from __future__ import annotations

import json
import re
import shutil
import threading
import time
from datetime import timezone
from pathlib import Path

from fastapi import APIRouter, Body, Request

from .. import easy as E, platforms as PF, pubqueue as PQ
from ..errors import SharkyClipsError
from ..project import Project, get_project, list_projects, write_json_atomic
from . import state
from .jobs import ACTIVE, Job

router = APIRouter()
_dlock = threading.Lock()
MAX_PROJECTS = 25


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


YT_ID = re.compile(r"(?:youtu\.be/|/shorts/|[?&]v=|/live/|/video/)([A-Za-z0-9_-]{11})")
SOCIAL_KEY = {"tiktok": "tiktok", "instagram": "reels"}  # the calendar's name -> the clip records' name
_link_at = {"t": 0.0}


def _utc(dt) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source(e: dict) -> tuple[Project, str] | None:
    src = str(e.get("source") or "")
    if ":" not in src:
        return None
    pid, cid = src.rsplit(":", 1)
    try:
        return get_project(pid), cid
    except Exception:  # noqa: BLE001 - the project is gone (or in the trash)
        return None


def link_library(entries: list[dict] | None = None) -> int:
    """Posts made in the browser (Claude in Chrome) become the clip's own records, so the Library,
    the digest, the views sync and "already posted" all know them:
      YouTube   -> uploads.json (video id from the link; views / privacy come from YouTube later)
      TikTok /  -> platform_uploads.json (by hand, via "chrome"; never posted again by SharkyClips)
      Instagram
    A planned post counts as published once its time has passed. Idempotent. -> records written"""
    n = 0
    now = PQ.now_local()
    for e in (entries if entries is not None else PQ.load_calendar()["entries"]):
        if e.get("status") not in PQ.LIVE:
            continue
        found = _source(e)
        if found is None:
            continue
        project, cid = found
        when = PQ.parse_time(e.get("scheduled_at"))
        past = e.get("status") == "published" or when is None or when <= now
        try:
            if e["platform"] == "youtube":
                m = YT_ID.search(str(e.get("url") or ""))
                if not m:
                    continue
                vid = m.group(1)
                if any(u.get("video_id") == vid for u in state.load_uploads(project).get(cid, [])):
                    continue  # linked before: YouTube's own numbers keep it up to date
                stamp = PQ.parse_time(e.get("reported_at") or e.get("updated_at")) or now
                state.save_upload(project, cid, {
                    "video_id": vid, "url": f"https://youtu.be/{vid}", "title": e.get("title"),
                    "privacy": "public" if past else "private", "requested_privacy": "public",
                    "publish_at": None if past or when is None else _utc(when),
                    "published_at": _utc(when or stamp) if past else None,
                    "file": Path(str(e.get("file") or "")).name or None, "uploaded_at": _utc(stamp),
                    "made_for_kids": False, "thumbnail_error": None, "hook_style": None, "via": "chrome",
                    "batch": e.get("batch")})
                n += 1
            elif e["platform"] in SOCIAL_KEY:
                key = SOCIAL_KEY[e["platform"]]
                rec = (PF.records(project).get(cid) or {}).get(key) or {}
                if rec.get("via") != "chrome" and rec.get("status") in ("published", "scheduled", "uploading",
                                                                         "processing", "preparing"):
                    continue  # posted (or being posted) another way: that record wins
                want = {"status": "published" if past else "scheduled", "mode": "semi", "manual": True,
                        "via": "chrome", "url": e.get("url") or rec.get("url"), "batch": e.get("batch"),
                        "publish_at": None if past or when is None else _utc(when),
                        "posted_at": _utc(when or now) if past else None, "account": e.get("account")}
                if all(rec.get(k) == v for k, v in want.items()):
                    continue
                PF.record(project, cid, key, **want, error=None)
                n += 1
        except Exception:  # noqa: BLE001 - one broken project never stops the others
            continue
    return n


def link_soon(every: float = 600.0) -> int:
    """From the publish loop: planned browser posts turn "published" when their time comes."""
    if time.time() - _link_at["t"] < every:
        return 0
    _link_at["t"] = time.time()
    try:
        return link_library()
    except Exception:  # noqa: BLE001
        return 0


def _store_path(project: Project) -> Path:
    return project.dir / "pubqueue.json"


def _store(project: Project) -> dict:
    try:
        return json.loads(_store_path(project).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def source_key(project_id: str, cid: str) -> str:
    return f"{project_id}:{cid}"


def clip_uid(project_id: str, cid: str) -> str:
    return PQ.safe_id(f"{project_id}_{cid}")


def suggested(project: Project, cand: dict) -> dict:
    """The AI's texts (the same ones the Publish button uses), brand hashtag included."""
    from . import multipost as MP

    d = MP.drafts(project, cand)["youtube"]
    return {"title": d["title"], "description": d["description"], "tags": list(d.get("tags") or []),
            "hashtags": PQ.with_brand(list(d.get("hashtags") or []), PQ.settings()["brand_hashtag"])}


def draft(project: Project, cand: dict) -> dict:
    mine = _store(project).get(cand["id"]) or {}
    base = suggested(project, cand)
    out = {k: mine[k] if mine.get(k) is not None else base[k] for k in ("title", "description", "tags", "hashtags")}
    out["hashtags"] = PQ.with_brand(out["hashtags"], PQ.settings()["brand_hashtag"])
    out["platforms"] = mine.get("platforms")
    out["times"] = mine.get("times") or {}
    out["instagram_account"] = mine.get("instagram_account")
    out["edited"] = any(mine.get(k) is not None for k in ("title", "description", "tags", "hashtags"))
    return out


def save_draft(project: Project, cid: str, body: dict) -> dict:
    with _dlock:
        data = _store(project)
        cur = data.get(cid) or {}
        for k in ("title", "description"):
            if k in body:
                cur[k] = None if body[k] is None else str(body[k])[:5000]
        for k in ("tags", "hashtags"):
            if k in body:
                v = body[k]
                if isinstance(v, str):
                    v = [x for x in (v.replace(",", " ").split() if k == "hashtags" else v.split(",")) if x.strip()]
                cur[k] = None if v is None else [str(x).strip() for x in v if str(x).strip()][:60]
        if "platforms" in body:
            cur["platforms"] = [p for p in (body["platforms"] or []) if p in PQ.PLATFORMS] if body["platforms"] is not None else None
        if "times" in body:
            t = {p: v for p, v in (body["times"] or {}).items() if p in PQ.PLATFORMS and v}
            for v in t.values():
                if PQ.parse_time(v) is None:
                    raise SharkyClipsError(f"\"{v}\" isn't a date and time.")
            cur["times"] = t
        if "instagram_account" in body:
            cur["instagram_account"] = body["instagram_account"] or None
        data[cid] = cur
        write_json_atomic(_store_path(project), data)
    return cur


def _candidates(project: Project) -> list[dict]:
    """Approved clips: accepted (Pro), or rendered and not thrown away (Easy)."""
    hl = state.load_highlights(project) or {}
    review = state.load_review(project)
    rendered = state.load_clips(project)
    acc, rej = set(review["accepted"]), set(review["rejected"])
    out = []
    for c in hl.get("candidates") or []:
        if c["id"] in rej:
            continue
        if c["id"] in acc or c["id"] in rendered:
            out.append(state.effective_cand(c, review))
    return sorted(out, key=lambda c: c.get("rank") or 999)


def _status_map() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for e in PQ.load_calendar()["entries"]:
        src = e.get("source")
        if not src:
            continue
        cur = out.setdefault(src, {}).get(e["platform"])
        if cur is None or (e.get("created_at") or "") >= (cur.get("created_at") or ""):
            out[src][e["platform"]] = {**{k: e.get(k) for k in ("status", "scheduled_at", "url", "note", "batch",
                                                               "created_at", "account")},
                                       "overdue": PQ.is_overdue(e)}
    return out


def overview() -> dict:
    s = PQ.settings()
    status = _status_map()
    rows = []
    projects = sorted(list_projects(), key=lambda p: p.load_meta().get("updated_at") or "", reverse=True)[:MAX_PROJECTS]
    for project in projects:
        try:
            cands = _candidates(project)
        except Exception:  # noqa: BLE001 - a half-made project
            continue
        if not cands:
            continue
        meta = project.load_meta()
        rendered = state.load_clips(project)
        for c in cands:
            try:
                d = draft(project, c)
            except Exception:  # noqa: BLE001
                continue
            rows.append({"project_id": project.id, "project_title": meta.get("title") or project.id,
                         "mode": meta.get("mode") or "gaming", "clip_id": c["id"], "rank": c.get("rank"),
                         "duration": float(c.get("duration") or 0), "rendered": c["id"] in rendered,
                         "uid": clip_uid(project.id, c["id"]), "draft": d,
                         "instagram_account": d.get("instagram_account") or PQ.instagram_account(meta.get("mode"), s),
                         "status": status.get(source_key(project.id, c["id"]), {})})
    cal = PQ.upcoming()
    return {"settings": s, "caps": {p: PQ.cap(p, s) for p in PQ.PLATFORMS}, "timezone": PQ.zone_name(s),
            "root": str(PQ.root()), "clips": rows, "calendar": cal, "batches": PQ.batches(),
            "overdue": sum(1 for e in cal if e.get("overdue")),
            "job": _job_view(), "now": PQ.iso(PQ.now_local())}


def _job_view() -> dict | None:
    jobs = [j for j in _app().jobs.jobs() if j.kind == "pubqueue"]
    if not jobs:
        return None
    j = max(jobs, key=lambda x: x.created)
    return j.to_dict()


def _items(body: dict) -> list[tuple[Project, dict, dict]]:
    out = []
    for it in (body or {}).get("items") or []:
        project = get_project(str(it.get("project_id") or ""))
        cand = state.effective_cand(_app()._cand(project, str(it.get("clip_id") or "")), state.load_review(project))
        out.append((project, cand, draft(project, cand)))
    if not out:
        raise SharkyClipsError("Pick at least one clip.")
    return out


def _plan_item(project: Project, cand: dict, d: dict, **extra) -> dict:
    meta = project.load_meta()
    return {"id": clip_uid(project.id, cand["id"]), "source": source_key(project.id, cand["id"]),
            "title": d["title"], "description": d["description"], "tags": d["tags"], "hashtags": d["hashtags"],
            "platforms": d.get("platforms"), "times": d.get("times") or {}, "mode": meta.get("mode"),
            "instagram_account": d.get("instagram_account"), **extra}


def preview(body: dict) -> dict:
    """Dry run: which time each clip would get on each platform (nothing is saved)."""
    s = PQ.settings()
    items = [_plan_item(p, c, d) for p, c, d in _items(body)]
    try:
        clips = PQ.plan_batch(items, s, write=False)
    except SharkyClipsError as exc:
        return {"ok": False, "error": {"message": exc.message, "hint": exc.hint}, "clips": []}
    return {"ok": True, "clips": [{"id": c["id"], "platforms": c["platforms"]} for c in clips]}


def submit_prepare(body: dict, local: bool) -> Job:
    """"Prepare for Chrome": compress every picked clip, write queue.json + CHROME.md, plan the
    calendar, open the folder."""
    from . import multipost as MP

    A = _app()
    picked = [(p.id, c["id"]) for p, c, _ in _items(body)]
    pv = preview(body)  # a bad time or setting fails here, before minutes of compressing
    if not pv["ok"]:
        raise SharkyClipsError(pv["error"]["message"], pv["error"]["hint"])

    def run(job: Job):
        s = PQ.settings()
        n = len(picked)
        folder = PQ.new_batch_dir()
        items, errors = [], []
        try:
            for i, (pid, cid) in enumerate(picked):
                project = A.get_project(pid)
                cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
                d = draft(project, cand)
                uid = clip_uid(pid, cid)

                def prog(stage: str, frac, i=i):
                    A.jobs.update(job, stage=stage, progress=min(0.99, (i + (frac or 0)) / n))

                try:
                    src = MP._file_for(project, cid, "youtube", {}, job)
                    res = PQ.compress(src, folder / f"{uid}.mp4", prog)
                except SharkyClipsError as exc:
                    errors.append({"id": uid, "title": d["title"], "message": exc.message, "hint": exc.hint})
                    continue
                items.append(_plan_item(project, cand, d, file=res["file"], sha256=PQ.sha256(Path(res["file"])),
                                        size_mb=res["size_mb"], duration_s=res["duration_s"]))
            if not items:
                raise SharkyClipsError("No clip could be prepared.", (errors[0]["message"] if errors else None))
            A.jobs.update(job, stage="scheduling", progress=0.99)
            clips = PQ.plan_batch(items, s, batch=folder.name)
            PQ.write_queue(folder, clips, s)
        except BaseException:
            if not any(folder.glob("*.mp4")) or not (folder / "queue.json").is_file():
                shutil.rmtree(folder, ignore_errors=True)
            raise
        if local and body.get("open", True):
            E.open_folder(folder)
        return {"batch": folder.name, "folder": str(folder), "queue": str(folder / "queue.json"),
                "clips": [{"id": c["id"], "title": c["title"], "size_mb": c["size_mb"], "duration_s": c["duration_s"],
                           "platforms": c["platforms"]} for c in clips], "errors": errors}

    for j in A.jobs.jobs():
        if j.kind == "pubqueue" and j.status in ACTIVE:
            return j
    return A.jobs.submit("pubqueue", "gpu", None, {"clips": len(picked), "title": f"{len(picked)} clips"}, run,
                         dedupe=False)


def brief(batch: str | None) -> dict:
    """What to paste into Claude in Chrome: CHROME.md with the whole queue.json inside."""
    rows = PQ.batches(50)
    if not rows:
        raise SharkyClipsError("Nothing prepared yet.", "Press \"Prepare for Chrome\" first.")
    pick = next((b for b in rows if b["batch"] == batch), rows[0]) if batch else rows[0]
    folder = Path(pick["folder"])
    text = (folder / "CHROME.md").read_text(encoding="utf-8")
    queue = (folder / "queue.json").read_text(encoding="utf-8")
    return {"batch": pick["batch"], "folder": str(folder),
            "text": f"{text}\n## queue.json\n\n```json\n{queue.strip()}\n```\n"}


# ===================================================================== routes


@router.get("/api/pubqueue")
def api_overview() -> dict:
    return overview()


@router.put("/api/pubqueue/settings")
def api_settings(body: dict) -> dict:
    PQ.save_settings(body or {})
    return overview()


@router.put("/api/pubqueue/clips/{project_id}/{cid}")
def api_draft(project_id: str, cid: str, body: dict) -> dict:
    project = get_project(project_id)
    _app()._cand(project, cid)
    if body.get("reset"):
        with _dlock:
            data = _store(project)
            data.pop(cid, None)
            write_json_atomic(_store_path(project), data)
    else:
        save_draft(project, cid, body or {})
    cand = state.effective_cand(_app()._cand(project, cid), state.load_review(project))
    return {"draft": draft(project, cand)}


@router.post("/api/pubqueue/preview")
def api_preview(body: dict) -> dict:
    return preview(body or {})


@router.post("/api/pubqueue/prepare")
def api_prepare(request: Request, body: dict | None = Body(default=None)) -> dict:
    job = submit_prepare(body or {}, _app()._is_local(request))
    return {"job": job.to_dict()}


@router.post("/api/pubqueue/import")
def api_import(body: dict) -> dict:
    payload = body.get("text") if isinstance(body.get("text"), str) else body.get("data")
    if payload is None:
        raise SharkyClipsError("Paste the status JSON first.")
    res = PQ.import_status(payload)
    res["linked"] = link_library()
    return {**res, "overview": overview()}


@router.post("/api/pubqueue/mark")
def api_mark(body: dict) -> dict:
    """By hand: what really happened to one post."""
    e = PQ.mark(str(body.get("id") or ""), str(body.get("platform") or ""), str(body.get("status") or ""),
                body.get("url"), body.get("note"), body.get("batch"))
    link_library([e])
    return {"entry": e, "overview": overview()}


@router.post("/api/pubqueue/replan")
def api_replan(body: dict | None = Body(default=None)) -> dict:
    """Overdue posts (or the given ones) get the next free times."""
    rows = PQ.replan((body or {}).get("items") or None)
    return {"replanned": len(rows), "entries": rows, "overview": overview()}


@router.get("/api/pubqueue/verify")
def api_verify() -> dict:
    """The brief for Claude in Chrome: check the overdue posts on the platforms."""
    return PQ.verify_brief()


@router.get("/api/pubqueue/brief")
def api_brief(batch: str | None = None) -> dict:
    return brief(batch)


@router.post("/api/pubqueue/open")
def api_open(request: Request, body: dict | None = Body(default=None)) -> dict:
    if not _app()._is_local(request):
        return {"opened": False}
    batch = (body or {}).get("batch")
    folder = PQ.queue_root() / PQ.safe_id(batch) if batch else PQ.root()
    if not folder.is_dir():
        folder = PQ.root()
        folder.mkdir(parents=True, exist_ok=True)
    return {"opened": E.open_folder(folder), "folder": str(folder)}
