"""1.2.66 "Share clips" board, 1.2.68 "share now": every clip of a project on one board, batch sharing.

Board (GET /api/share/{project}): all clip candidates (best first, discarded ones out) with a
thumbnail frame, something to play (the rendered 9:16 clip, else the source between its start and
end), duration, viral score, title and one status per clip:

  not_shared  nothing planned or posted anywhere
  scheduled   planned (tomorrow / a date you picked), or a file waiting for you to post by hand
  working     being made / sent right now
  shared      out on at least one platform (links to the live posts)
  failed      a platform failed (Retry redoes only that one)

1.2.68 rules (no own daily limit, no automatic spreading over the next days):
  * every picked clip goes NOW, up to what YouTube really allows today (its upload bucket:
    youtube.uploads_left(), 100 a day by default) - "X uploads left today"
  * more than that: the plan says how many don't fit and Publish needs a choice for them:
      overflow "manual"    YouTube by hand now for those (file saved, texts ready to copy)
      overflow "tomorrow"  uploaded by itself after Google's reset (public at once)
      overflow "date"      + overflow_date YYYY-MM-DD: uploaded that day (only when you pick it)
  * Instagram's 4-hour pace is a warning in the plan (ig_warning), never a delay
  * TikTok's safe number of automatic posts a day: the clips over it are prepared by hand
  * a platform a clip is already shared / planned on is skipped (never twice) and reported

Plan (POST .../plan) and Publish (POST .../publish) take the same body:
  {"clips": [cid, ...], "platforms": [...], "per_clip": {cid: {"platforms": [...]}},
   "overflow": "manual" | "tomorrow" | "date", "overflow_date": "YYYY-MM-DD",
   "consent": bool (TikTok's own post screen, only when TikTok posts through its API)}

Publishing runs in a background thread, one clip after the other through multipost.start (the same
code as the single Publish button and Pro mode), and writes its progress to <project>/share_batch.json.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Body

from .. import easy as E, platforms as PF, publishing as P
from ..errors import SharkyClipsError
from ..project import Project, read_json_shared, write_json_atomic
from . import igpace, multipost as M, state

router = APIRouter()

PLATFORMS = M.PLATFORMS
DONE = ("published",)
PLANNED = ("scheduled", "ready")
BUSY = ("preparing", "uploading", "processing")
OPEN = ("idle", "failed", "cancelled", "paused")
MAX_CLIPS = 200

_batch_lock = threading.Lock()
_running: dict[str, threading.Thread] = {}


def _app():
    return M._app()


def _now() -> datetime:
    return P.now_utc()


# ===================================================================== what YouTube allows today


def _pending_youtube_now() -> int:
    """Clips that will upload today but haven't yet (they use today's room too)."""
    n = 0
    for it in P.load().values():
        if it.get("now") and not it.get("video_id") and not it.get("attention") and not it.get("after"):
            n += 1
    return n


def limit_view(now: datetime | None = None, events=None) -> dict:
    """{"limit", "used", "left", "resets_at", "connected"}: "X uploads left today" (YouTube's real quota)."""
    from .. import youtube

    lim = youtube.daily_uploads()
    used = youtube.uploads_used(now) + _pending_youtube_now()
    return {"limit": lim, "used": min(lim, used), "left": max(0, lim - used), "max": lim,
            "resets_at": youtube.next_reset(now).isoformat(timespec="seconds"),
            "connected": youtube.connected()}


# ===================================================================== the board


def _status(posts: dict) -> dict:
    """One status for a clip from its three platform states."""
    rows = [posts[p] for p in PLATFORMS]
    shared = [{"platform": s["platform"], "url": s.get("url")} for s in rows if s["status"] in DONE]
    planned = [{"platform": s["platform"], "at": s.get("publish_at") or s.get("remind_at"),
                "by_hand": s.get("mode") == "semi" and s["status"] == "ready"} for s in rows if s["status"] in PLANNED]
    failed = [{"platform": s["platform"], "message": (s.get("error") or {}).get("message"),
               "hint": (s.get("error") or {}).get("hint")} for s in rows if s["status"] == "failed"]
    busy = [s["platform"] for s in rows if s["status"] in BUSY]
    # 1.2.68: never silent: why a clip waits, and a YouTube video that came back private
    waits = [{"platform": s["platform"], **s["wait"]} for s in rows if s.get("wait")]
    private = [{"platform": s["platform"], "studio_url": (s.get("private_notice") or {}).get("studio_url")}
               for s in rows if s.get("private_notice")]
    if failed:
        kind = "failed"
    elif busy:
        kind = "working"
    elif shared:
        kind = "shared"
    elif planned:
        kind = "scheduled"
    else:
        kind = "not_shared"
    times = sorted(x["at"] for x in planned if x["at"])
    return {"kind": kind, "shared": shared, "planned": planned, "failed": failed, "busy": busy,
            "waits": waits, "private": private,
            "next_at": times[0] if times else None,
            "progress": next((s.get("progress") for s in rows if s.get("progress") is not None), None)}


def _title(project: Project, cand: dict, data: dict, items: dict) -> str:
    prefs = E.clip_prefs(data, cand["id"])
    meta = (items.get(P.key_of(project.id, cand["id"])) or {}).get("meta") or {}
    pub = cand.get("publish") or {}
    return (prefs.get("title") or meta.get("title") or (pub.get("titles") or [None])[0]
            or (cand.get("text") or "").strip()[:90] or f"#{cand.get('rank')}")


def _platforms_view() -> dict:
    acc = M.accounts()
    modes = M.modes_now()
    out = {}
    for p in PLATFORMS:
        a = acc[p]
        by_hand = modes[p] == "semi"
        usable = by_hand or (a["connected"] and a["health"]["pill"] != "signed_out")
        out[p] = {"platform": p, "name": M.NAMES[p], "usable": bool(usable), "connected": bool(a["connected"]),
                  "mode": modes[p], "by_hand": by_hand, "manual": by_hand,
                  "handle": a.get("handle"), "pill": a["health"]["pill"],
                  # 1.2.68, said honestly: automatic TikTok drives TikTok Studio and can stop at a
                  # TikTok check (CAPTCHA, login); Instagram has no automatic posting at all
                  "auto_note": "tiktok_beta" if p == "tiktok" and modes[p] == "browser" else
                  "tiktok_manual" if p == "tiktok" else "ig_manual" if p == "reels" and not PF.META_AUTOMATION else None}
    return out


def board(project: Project) -> dict:
    from . import easy as WE

    hl = state.load_highlights(project) or {}
    review = state.load_review(project, hl)
    data = E.load(project)
    clips = state.load_clips(project)
    items = P.load()
    cards = []
    has_source = project.source_path is not None and project.source_path.is_file()
    for c in WE.ranked(project, hl, review):
        eff = state.effective_cand(c, review)
        posts = M.clip_states(project, c["id"])
        clip = clips.get(c["id"])
        rendered = bool(clip and (project.dir / "clips" / clip["file"]).is_file())
        pub = c.get("publish") or {}
        cards.append({
            "id": c["id"], "rank": c.get("rank"), "title": _title(project, c, data, items),
            "duration": float(eff["duration"]), "start": float(eff["start"]), "end": float(eff["end"]),
            "peak": float(c.get("peak") or eff["start"]),
            "viral_score": pub.get("viral_score"), "viral_label": state.viral_label(pub.get("viral_score")),
            "video": {"kind": "clip", "stamp": str(clip.get("rendered_at") or clip["file"])} if rendered
            else {"kind": "source"} if has_source else {"kind": "none"},
            "status": _status(posts), "posts": posts,
        })
    meta = project.load_meta()
    from .. import history, languages
    from . import space

    try:
        before = history.for_project(project)
    except Exception:  # noqa: BLE001 - the warning is extra, never breaks the board
        before = None
    return {"project_id": project.id, "title": meta.get("title") or project.id, "clips": cards,
            "limit": limit_view(), "platforms": _platforms_view(), "targets": M.targets(),
            "batch": batch_view(project), "ig_gap_hours": igpace.MIN_GAP_HOURS,
            "history": before, "space": space.view(project, cards),
            "language": languages.content_language(None, project),
            "language_set": bool(meta.get("content_language")), "has_source": has_source}


# ===================================================================== the plan


def _wanted(body: dict, cid: str, default: list[str]) -> list[str]:
    per = ((body.get("per_clip") or {}).get(cid) or {}) if isinstance(body.get("per_clip"), dict) else {}
    raw = per.get("platforms") if isinstance(per.get("platforms"), list) else default
    return [p for p in PLATFORMS if p in raw]


def overflow_time(body: dict, now: datetime | None = None) -> datetime | None:
    """When the clips that don't fit today go up: after Google's reset ("tomorrow") or on the day
    the user picked (12:00 there, never before the reset)."""
    from .. import youtube

    now = now or _now()
    reset = youtube.next_reset(now) + timedelta(minutes=5)
    how = body.get("overflow")
    if how == "tomorrow":
        return reset
    if how == "date":
        try:
            day = date.fromisoformat(str(body.get("overflow_date") or ""))
        except ValueError:
            raise SharkyClipsError("Pick a day for the rest.") from None
        if day <= P.local_day(now):
            raise SharkyClipsError("Pick a day after today for the rest.")
        return max(reset, P.at_local(day, "12:00"))
    return None


def plan(project: Project, body: dict, now: datetime | None = None) -> dict:
    """What goes where (nothing is changed): now, as far as today's YouTube uploads go."""
    from .. import tiktok_browser as TB

    A = _app()
    now = now or _now()
    cids = [str(c) for c in (body.get("clips") or []) if isinstance(c, str | int)][:MAX_CLIPS]
    if not cids:
        raise SharkyClipsError("Pick at least one clip.")
    plats = _platforms_view()
    default = [p for p in PLATFORMS if p in (body.get("platforms") or [])]
    lv = limit_view(now)
    yt_left = lv["left"]
    over_how = body.get("overflow") if body.get("overflow") in ("manual", "tomorrow", "date") else None
    over_at = overflow_time(body, now) if over_how in ("tomorrow", "date") else None
    ig = igpace.events(A, fresh=True)
    ig_batch: list[datetime] = []
    modes = M.modes_now()
    tt_left = None
    if modes["tiktok"] in ("api", "browser"):
        tt_left = max(0, TB.daily_cap() - M._tiktok_day_count(now))
    review = state.load_review(project)
    acc = M.accounts()
    quota = M.quotas(fetch=False)
    data, items = E.load(project), P.load()
    rows, used_today, over = [], 0, 0
    for cid in cids:
        try:
            cand = state.effective_cand(A._cand(project, cid), review)
        except SharkyClipsError:
            rows.append({"clip_id": cid, "skipped": "missing", "platforms": [], "already": []})
            continue
        posts = M.clip_states(project, cid)
        want = _wanted(body, cid, default)
        already = [{"platform": p, "status": posts[p]["status"], "url": posts[p].get("url"),
                    "at": posts[p].get("publish_at")} for p in want if posts[p]["status"] not in OPEN]
        todo = [p for p in want if posts[p]["status"] in OPEN]
        blocked = [p for p in todo if not plats[p]["usable"]]
        todo = [p for p in todo if p not in blocked]
        row = {"clip_id": cid, "title": _title(project, cand, data, items),
               "duration": float(cand["duration"]), "already": already, "not_connected": blocked,
               "platforms": [], "skipped": None, "problems": [], "dropped": [], "warnings": []}
        if todo:
            d = M.drafts(project, cand)
            tt = M._tiktok_view(M.clip_store(project, cid)["tiktok"]) if "tiktok" in todo and modes["tiktok"] == "api" \
                else None
            probs = [x for x in M.problems(project, cand, todo, d, tt, acc, float(cand["duration"]), quota, modes)
                     if x["code"] not in ("quota_full", "not_connected", "signed_out")]
            # too long / too short for a platform: left out for this clip (with the reason)
            row["dropped"] = [x for x in probs if x["fix"] == "turn_off" and x["platform"] in todo]
            gone = {x["platform"] for x in row["dropped"]}
            todo = [p for p in todo if p not in gone]
            row["problems"] = [x for x in probs if x not in row["dropped"] and (x["platform"] in todo or x["platform"] == "all")]
        if not todo:
            row["skipped"] = "already" if already else "cant" if row["dropped"] else "no_platform"
            row["problems"] = []
            rows.append(row)
            continue
        for p in todo:
            entry = {"platform": p, "when": "now", "moved": None, "mode": modes[p],
                     "by_hand": modes[p] == "semi", "manual": modes[p] == "semi", "over": None}
            if p == "youtube":
                if yt_left > 0:
                    yt_left -= 1
                    used_today += 1
                else:
                    over += 1
                    entry["over"] = over_how or "ask"
                    if over_how == "manual":
                        entry.update(by_hand=True, manual=True, mode="semi", force_manual=True)
                    elif over_at is not None:
                        entry["when"] = P.iso(over_at)
            elif p == "reels":  # 1.2.68: a warning only, never a delay
                last = igpace.last_before(ig, (project.id, cid))
                last_t = datetime.fromtimestamp(last["at"]).astimezone() if last and last.get("at") else None
                close = (last_t is not None and abs((now - last_t).total_seconds()) < igpace.MIN_GAP_HOURS * 3600) \
                    or bool(ig_batch)
                if close:
                    row["warnings"].append({"code": "ig_pace", "hours": igpace.MIN_GAP_HOURS,
                                            "last_at": P.iso(last_t) if last_t else None})
                ig_batch.append(now)
            elif p == "tiktok" and tt_left is not None:
                if tt_left > 0:
                    tt_left -= 1
                else:  # over TikTok's safe number of automatic posts today: by hand instead
                    entry.update(by_hand=True, manual=True, mode="semi", moved="tiktok_cap", force_manual=True)
            row["platforms"].append(entry)
        row["when"] = "now"
        row["day"] = P.local_day(now).isoformat()
        row["rolled"] = False
        rows.append(row)
    going = [r for r in rows if r["platforms"]]
    needs_consent = any(p["platform"] == "tiktok" and p["mode"] == "api" for r in going for p in r["platforms"])
    return {"rows": rows, "limit": lv, "uses_today": used_today, "left_after": max(0, lv["left"] - used_today),
            "over": over, "overflow": over_how, "overflow_at": P.iso(over_at) if over_at else None,
            "days": [{"day": P.local_day(now).isoformat(), "count": len(going)}],
            "count": len(going), "skipped": len(rows) - len(going),
            "duplicates": sum(1 for r in rows if r["already"]), "problems": sum(len(r["problems"]) for r in going),
            "warnings": sum(len(r["warnings"]) for r in going),
            "needs_consent": needs_consent, "platforms": plats, "ig_gap_hours": igpace.MIN_GAP_HOURS}


# ===================================================================== publish (background)


def _batch_path(project: Project):
    return project.dir / "share_batch.json"


def load_batch(project: Project) -> dict | None:
    b = read_json_shared(_batch_path(project), None)
    return b if isinstance(b, dict) and b.get("id") else None


def batch_view(project: Project) -> dict | None:
    """The last batch; one that was still running when SharkyClips stopped shows as "stopped"
    (its clips that were not started yet are simply not shared: share them again)."""
    b = load_batch(project)
    if b and b.get("state") == "running":
        t = _running.get(project.id)
        if t is None or not t.is_alive():
            b = {**b, "state": "stopped"}
    return b


def _save_batch(project: Project, b: dict) -> None:
    write_json_atomic(_batch_path(project), b)


def publish(project: Project, body: dict) -> dict:
    """Start a batch: the plan is made again here, then each clip goes through multipost.start."""
    with _batch_lock:
        cur = batch_view(project)
        if cur and cur.get("state") == "running":
            raise SharkyClipsError("A batch of this project is still being sent.", "Wait until it is done.")
        p = plan(project, body)
        going = [r for r in p["rows"] if r["platforms"]]
        if not going:
            raise SharkyClipsError("Nothing to share: these clips are already shared or planned there.")
        if p["problems"]:
            e = SharkyClipsError("Some clips need a fix first.", "Open \"Edit per clip\" to fix them.")
            e.code = "problems"  # type: ignore[attr-defined]
            raise e
        if p["over"] and not p["overflow"]:
            e = SharkyClipsError(f"{p['over']} clip(s) don't fit in today's YouTube uploads.",
                                 "Choose: upload them by hand now, or put them on tomorrow.")
            e.code = "over_limit"  # type: ignore[attr-defined]
            raise e
        if p["needs_consent"] and not body.get("consent"):
            raise SharkyClipsError("Confirm TikTok's Music Usage Confirmation first.")
        chosen = [x for x in PLATFORMS if x in (body.get("platforms") or [])]
        if chosen:
            M.set_targets(chosen)  # remembered for the next time
        b = {"id": uuid.uuid4().hex[:12], "started_at": time.time(), "state": "running", "finished_at": None,
             "rows": [{"clip_id": r["clip_id"], "title": r["title"], "when": r["when"], "state": "queued",
                       "platforms": [x["platform"] for x in r["platforms"]], "plan": r["platforms"],
                       "error": None, "results": {}} for r in going],
             "skipped": [{"clip_id": r["clip_id"], "reason": r["skipped"]} for r in p["rows"] if not r["platforms"]]}
        _save_batch(project, b)
        th = threading.Thread(target=_run_batch, args=(project.id, b["id"], bool(body.get("consent"))),
                              name=f"share-{project.id}", daemon=True)
        _running[project.id] = th
        th.start()
    return {"batch": b, "plan": p}


def _run_batch(project_id: str, batch_id: str, consent: bool) -> None:
    A = _app()
    try:
        project = A.get_project(project_id)
    except Exception:  # noqa: BLE001
        return
    b = load_batch(project)
    if not b or b["id"] != batch_id:
        return
    for row in b["rows"]:
        row["state"] = "starting"
        _save_batch(project, b)
        try:
            # by hand because of a platform's mode (TikTok / Instagram "semi"): multipost makes the
            # file + texts itself; force_manual = over today's limit: the manual-upload files
            now_plats = [x["platform"] for x in row["plan"] if x["when"] == "now" and not x.get("force_manual")]
            hand = [x["platform"] for x in row["plan"] if x.get("force_manual")]
            later = [x for x in row["plan"] if x["platform"] == "youtube" and x["when"] != "now"]
            if now_plats:
                res = M.start(project, row["clip_id"], {"platforms": now_plats, "when": "now", "consent": consent,
                                                        "remember": False})
                row["results"].update(res.get("results") or {})
            for x in later:  # "tomorrow" / a picked day: uploads after Google's reset, public at once
                res = M.start(project, row["clip_id"], {"platforms": ["youtube"], "when": "now",
                                                        "youtube_after": x["when"], "remember": False})
                row["results"].update(res.get("results") or {})
            for plat in hand:  # over today's limit: ready to upload by hand now
                from . import manual

                try:
                    m = manual.prepare(project, row["clip_id"], plat)
                    row["results"][plat] = {"status": "manual", "manual": m.get("status")}
                except SharkyClipsError as exc:
                    row["results"][plat] = {"status": "failed", "error": {"message": exc.message, "hint": exc.hint}}
            bad = {k: v for k, v in row["results"].items() if v.get("status") == "failed"}
            row["state"] = "failed" if bad and len(bad) == len(row["results"]) else "done"
            if bad:
                row["error"] = next(iter(bad.values())).get("error")
        except SharkyClipsError as exc:
            row["state"], row["error"] = "failed", {"message": exc.message, "hint": exc.hint}
        except Exception as exc:  # noqa: BLE001 - one clip never stops the batch
            row["state"], row["error"] = "failed", {"message": str(exc) or type(exc).__name__, "hint": None}
        _save_batch(project, b)
    b["state"], b["finished_at"] = "done", time.time()
    _save_batch(project, b)
    _running.pop(project_id, None)


def wait_batch(project_id: str, timeout: float = 30.0) -> None:
    """Tests: wait for the batch thread of a project."""
    t = _running.get(project_id)
    if t is not None:
        t.join(timeout)


# ===================================================================== unschedule / retry


def unschedule(project: Project, cids: list[str]) -> dict:
    """Take planned posts off the plan and stop posts that are still being made (the UI waits a
    few seconds with Undo before it calls this, so nothing is undone on the server)."""
    from . import publishing as pub

    A = _app()
    done: list[dict] = []
    errors: list[dict] = []
    for cid in cids[:MAX_CLIPS]:
        posts = M.clip_states(project, cid)
        for p in PLATFORMS:
            st = posts[p]["status"]
            try:
                if p == "youtube" and st in ("scheduled", "preparing", "uploading"):
                    pub.api_cancel(project.id, cid)
                    done.append({"clip_id": cid, "platform": p})
                elif p != "youtube" and st == "scheduled":
                    M.unplan(project, cid, p)
                    done.append({"clip_id": cid, "platform": p})
                elif p != "youtube" and st in ("preparing", "uploading", "ready"):
                    j = M.active_job(project.id, cid, p)
                    if j is not None:
                        A.jobs.cancel(j.id)
                    PF.record(project, cid, p, status="cancelled", publish_at=None, remind_at=None)
                    done.append({"clip_id": cid, "platform": p})
            except SharkyClipsError as exc:
                errors.append({"clip_id": cid, "platform": p, "message": exc.message, "hint": exc.hint})
    igpace.forget_cache()
    return {"done": done, "errors": errors}


def retry(project: Project, cids: list[str]) -> dict:
    done, errors = [], []
    for cid in cids[:MAX_CLIPS]:
        posts = M.clip_states(project, cid)
        for p in PLATFORMS:
            if posts[p]["status"] != "failed":
                continue
            try:
                M.retry(project, cid, p)
                done.append({"clip_id": cid, "platform": p})
            except SharkyClipsError as exc:
                errors.append({"clip_id": cid, "platform": p, "message": exc.message, "hint": exc.hint})
    return {"done": done, "errors": errors}


# ===================================================================== API


def _project(pid: str) -> Project:
    return _app()._project(pid)


def _cids(body: dict | None) -> list[str]:
    return [str(c) for c in ((body or {}).get("clips") or []) if isinstance(c, str | int)]


@router.get("/api/share/limit")
def api_limit() -> dict:
    return limit_view()


@router.get("/api/share/{project_id}")
def api_board(project_id: str) -> dict:
    return board(_project(project_id))


@router.post("/api/share/{project_id}/plan")
def api_plan(project_id: str, body: dict | None = Body(default=None)) -> dict:
    return plan(_project(project_id), body or {})


@router.post("/api/share/{project_id}/publish")
def api_publish(project_id: str, body: dict | None = Body(default=None)) -> dict:
    return publish(_project(project_id), body or {})


@router.post("/api/share/{project_id}/unschedule")
def api_unschedule(project_id: str, body: dict | None = Body(default=None)) -> dict:
    return unschedule(_project(project_id), _cids(body))


@router.post("/api/share/{project_id}/retry")
def api_retry(project_id: str, body: dict | None = Body(default=None)) -> dict:
    return retry(_project(project_id), _cids(body))


@router.post("/api/share/{project_id}/batch/dismiss")
def api_dismiss(project_id: str) -> dict:
    project = _project(project_id)
    b = load_batch(project)
    if b and b.get("state") != "running":
        b["dismissed"] = True
        _save_batch(project, b)
    return {"batch": batch_view(project)}
