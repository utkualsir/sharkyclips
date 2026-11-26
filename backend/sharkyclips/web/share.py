"""1.2.66 "Share clips": every clip of a project on one board, a daily upload limit, batch sharing.

Board (GET /api/share/{project}): all clip candidates (best first, discarded ones out) with a
thumbnail frame, something to play (the rendered 9:16 clip, else the source between its start and
end), duration, viral score, title and one status per clip:

  not_shared  nothing planned or posted anywhere
  scheduled   planned (with the first time), or a file waiting for you to post by hand
  working     being made / sent right now
  shared      out on at least one platform (links to the live posts)
  failed      a platform failed (Retry redoes only that one)

Daily upload limit (config publish_daily_limit, default 5, at most publishing.DAILY_MAX = 6 so
YouTube's free API quota is enough): counted per CLIP per local day, over every platform and every
project. A clip that goes to YouTube and TikTok on the same day uses one of the day's uploads.

Plan (POST .../plan) and Publish (POST .../publish) take the same body:
  {"clips": [cid, ...], "platforms": [...], "per_clip": {cid: {"platforms": [...]}},
   "consent": bool (TikTok's own post screen, only when TikTok posts through its API)}
The server always makes the plan itself (the client's times are never used): the clips that fit in
what is left today go now, the rest move to the next days at the best release times (the daily
limit, 45 minutes apart). Instagram keeps its 4-hour pace (igpace) and the TikTok daily cap moves a
TikTok post on to the next day with room; the summary shows each of those moves. A platform a clip
is already shared / planned on is skipped (never twice) and reported as a duplicate.

Publishing runs in a background thread, one clip after the other through multipost.start (the same
code as the single Publish button), and writes its progress to <project>/share_batch.json.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Body

from .. import config, easy as E, platforms as PF, publishing as P
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


# ===================================================================== the daily limit


def daily_limit() -> int:
    return P.daily_limit()


def set_daily_limit(n) -> int:
    try:
        value = int(n)
    except (TypeError, ValueError):
        raise SharkyClipsError("The daily limit has to be a number.") from None
    config.update(publish_daily_limit=max(1, min(P.DAILY_MAX, value)))
    return daily_limit()


def _social_time(r: dict) -> float | None:
    """When a TikTok / Instagram post went out or is meant to (None: it doesn't count)."""
    st = r.get("status")
    if st in BUSY and not any(r.get(k) for k in ("posted_at", "publish_at", "remind_at")):
        return float(r.get("at") or time.time())
    return igpace._event_time(r)


def releases_by_clip(now: datetime | None = None) -> list[tuple[str, str, datetime]]:
    """[(project:clip, platform, time)] of every post that counts: planned, being sent or out."""
    from . import publishing as pub

    now = now or _now()
    out: list[tuple[str, str, datetime]] = [(k, "youtube", t) for k, t in pub.releases(now).items()]
    for project in _app().list_projects():
        try:
            recs = PF.records(project)
        except Exception:  # noqa: BLE001 - one broken project never stops the count
            continue
        for cid, plats in (recs or {}).items():
            for p in M.SOCIAL:
                at = _social_time((plats or {}).get(p) or {})
                if at is not None:
                    out.append((P.key_of(project.id, cid), p, datetime.fromtimestamp(at).astimezone()))
    return out


def day_usage(events: list[tuple[str, str, datetime]]) -> dict[date, set[str]]:
    days: dict[date, set[str]] = {}
    for key, _p, t in events:
        days.setdefault(P.local_day(t), set()).add(key)
    return days


def limit_view(now: datetime | None = None, events=None) -> dict:
    """{"limit", "used", "left", "max", "resets_at"}: "3 of 5 left today"."""
    now = now or _now()
    events = releases_by_clip(now) if events is None else events
    used = len(day_usage(events).get(P.local_day(now), set()))
    limit = daily_limit()
    tomorrow = P.local_day(now) + timedelta(days=1)
    return {"limit": limit, "used": used, "left": max(0, limit - used), "max": P.DAILY_MAX,
            "resets_at": P.iso(P.at_local(tomorrow, "00:00"))}


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
                  "mode": modes[p], "by_hand": by_hand, "manual": p == "reels" and not PF.META_AUTOMATION,
                  "handle": a.get("handle"), "pill": a["health"]["pill"]}
    return out


def board(project: Project) -> dict:
    from . import easy as WE

    hl = state.load_highlights(project) or {}
    review = state.load_review(project, hl)
    data = E.load(project)
    clips = state.load_clips(project)
    items = P.load()
    cards = []
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
            else {"kind": "source"},
            "status": _status(posts), "posts": posts,
        })
    meta = project.load_meta()
    events = releases_by_clip()
    return {"project_id": project.id, "title": meta.get("title") or project.id, "clips": cards,
            "limit": limit_view(events=events), "platforms": _platforms_view(), "targets": M.targets(),
            "batch": batch_view(project), "ig_gap_hours": igpace.MIN_GAP_HOURS}


# ===================================================================== the plan


def _gap_ok(t: datetime, taken: list[datetime]) -> bool:
    return all(abs((t - o).total_seconds()) >= P.MIN_GAP_MIN * 60 for o in taken)


def _slot(day: date, taken: list[datetime], times: list[str], earliest: datetime) -> datetime | None:
    """The first release time of `day` that is ahead and 45 minutes from every other release."""
    for hhmm in times:
        t = P.at_local(day, hhmm)
        if t >= earliest and _gap_ok(t, taken):
            return t
    t = max([earliest] + [o + timedelta(minutes=P.MIN_GAP_MIN) for o in taken if P.local_day(o) == day])
    while P.local_day(t) == day:  # all release times taken: the next gap of that day
        if _gap_ok(t, taken):
            return t
        t += timedelta(minutes=P.MIN_GAP_MIN)
    return None


def _wanted(body: dict, cid: str, default: list[str]) -> list[str]:
    per = ((body.get("per_clip") or {}).get(cid) or {}) if isinstance(body.get("per_clip"), dict) else {}
    raw = per.get("platforms") if isinstance(per.get("platforms"), list) else default
    return [p for p in PLATFORMS if p in raw]


def plan(project: Project, body: dict, now: datetime | None = None) -> dict:
    """What goes where and when (nothing is changed)."""
    from .. import tiktok_browser as TB

    A = _app()
    now = now or _now()
    cids = [str(c) for c in (body.get("clips") or []) if isinstance(c, str | int)][:MAX_CLIPS]
    if not cids:
        raise SharkyClipsError("Pick at least one clip.")
    plats = _platforms_view()
    default = [p for p in PLATFORMS if p in (body.get("platforms") or [])]
    limit = daily_limit()
    events = releases_by_clip(now)
    usage = day_usage(events)
    today = P.local_day(now)
    taken = [t for _k, _p, t in events]
    times = P.best_times(limit)["times"]
    earliest = P.earliest(now)
    ig = igpace.events(A, fresh=True)
    modes = M.modes_now()
    tt_cap = TB.daily_cap() if modes["tiktok"] in ("api", "browser") else None
    tt_days: dict[date, int] = {}
    if tt_cap:
        for _k, p, t in events:
            if p == "tiktok":
                tt_days[P.local_day(t)] = tt_days.get(P.local_day(t), 0) + 1
    review = state.load_review(project)
    acc = M.accounts()
    quota = M.quotas(fetch=False)
    data, items = E.load(project), P.load()
    rows, used_today = [], 0
    days_used: dict[date, int] = {}
    for cid in cids:
        try:
            cand = state.effective_cand(A._cand(project, cid), review)
        except SharkyClipsError:
            rows.append({"clip_id": cid, "skipped": "missing", "platforms": [], "already": []})
            continue
        key = P.key_of(project.id, cid)
        posts = M.clip_states(project, cid)
        want = _wanted(body, cid, default)
        already = [{"platform": p, "status": posts[p]["status"], "url": posts[p].get("url"),
                    "at": posts[p].get("publish_at")} for p in want if posts[p]["status"] not in OPEN]
        todo = [p for p in want if posts[p]["status"] in OPEN]
        blocked = [p for p in todo if not plats[p]["usable"]]
        todo = [p for p in todo if p not in blocked]
        row = {"clip_id": cid, "title": _title(project, cand, data, items),
               "duration": float(cand["duration"]), "already": already, "not_connected": blocked,
               "platforms": [], "skipped": None, "problems": [], "dropped": []}
        if todo:
            d = M.drafts(project, cand)
            tt = M._tiktok_view(M.clip_store(project, cid)["tiktok"]) if "tiktok" in todo and modes["tiktok"] == "api" \
                else None
            probs = [x for x in M.problems(project, cand, todo, d, tt, acc, float(cand["duration"]), quota, modes)
                     if x["code"] not in ("quota_full", "not_connected", "signed_out")]
            # too long / too short for a platform: in a batch that platform is left out for this clip
            # (shown with the reason) instead of stopping every other clip
            row["dropped"] = [x for x in probs if x["fix"] == "turn_off" and x["platform"] in todo]
            gone = {x["platform"] for x in row["dropped"]}
            todo = [p for p in todo if p not in gone]
            row["problems"] = [x for x in probs if x not in row["dropped"] and (x["platform"] in todo or x["platform"] == "all")]
        if not todo:
            row["skipped"] = "already" if already else "cant" if row["dropped"] else "no_platform"
            row["problems"] = []
            rows.append(row)
            continue
        # the day: today while there is room, else the next day with room (and a free time)
        day, when = today, None
        for _ in range(400):
            n = len(usage.get(day, set()) - {key})
            if n < limit:
                if day == today:
                    break  # now
                when = _slot(day, taken, times, earliest)
                if when is not None:
                    break
            day += timedelta(days=1)
        usage.setdefault(day, set()).add(key)
        days_used[day] = days_used.get(day, 0) + 1
        if day == today:
            used_today += 1
        base = when or now
        if when is not None:
            taken.append(when)
        for p in todo:
            at, moved = when, None
            if p == "reels":
                safe = igpace.next_safe(base, ig, (project.id, cid))
                if safe > base + timedelta(seconds=30):
                    at, moved = safe, "ig_pace"
                ig.append({"key": (project.id, cid), "at": (at or base).timestamp(), "caption": ""})
            elif p == "tiktok" and tt_cap:
                t0 = at or base
                for i in range(60):
                    dd = P.local_day(t0 + timedelta(days=i))
                    if tt_days.get(dd, 0) < tt_cap:
                        if i:
                            at, moved = t0 + timedelta(days=i), "tiktok_cap"
                        tt_days[dd] = tt_days.get(dd, 0) + 1
                        break
            row["platforms"].append({"platform": p, "when": P.iso(at) if at else "now", "moved": moved,
                                     "mode": modes[p], "by_hand": modes[p] == "semi",
                                     "manual": p == "reels" and not PF.META_AUTOMATION})
        row["day"] = day.isoformat()
        row["when"] = P.iso(when) if when else "now"
        row["rolled"] = day != today
        rows.append(row)
    lv = limit_view(now, events)
    going = [r for r in rows if r["platforms"]]
    needs_consent = any(p["platform"] == "tiktok" and p["mode"] == "api" for r in going for p in r["platforms"])
    return {"rows": rows, "limit": lv, "uses_today": used_today, "left_after": max(0, lv["left"] - used_today),
            "days": [{"day": k.isoformat(), "count": v} for k, v in sorted(days_used.items())],
            "count": len(going), "skipped": len(rows) - len(going),
            "duplicates": sum(1 for r in rows if r["already"]), "problems": sum(len(r["problems"]) for r in going),
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
            # one call per planned time (Instagram / TikTok moves get their own time)
            groups: dict[str, list[str]] = {}
            for x in row["plan"]:
                groups.setdefault(x["when"], []).append(x["platform"])
            # YouTube's group first: its time leads (multipost.start does the same inside)
            order = sorted(groups.items(), key=lambda kv: ("youtube" not in kv[1], kv[0]))
            for when, plats in order:
                if when != "now" and (P.parse(when) or _now()) < _now() + timedelta(seconds=M.LEAD_S):
                    when = "now"  # the batch took a while: a time that has come is "now"
                res = M.start(project, row["clip_id"], {"platforms": plats, "when": when, "consent": consent,
                                                        "remember": False})
                row["results"].update(res.get("results") or {})
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


@router.put("/api/share/limit")
def api_limit_put(body: dict) -> dict:
    set_daily_limit(body.get("limit"))
    from . import publishing as pub

    pub.scheduler.poke()
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
