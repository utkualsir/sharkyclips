"""One "Publish" button, three platforms (1.2.36): YouTube + Instagram Reels + TikTok.

Same clip, same idea everywhere, adapted per platform:
  youtube  title + description + tags (the 1.2.7 publish plan does the upload, with publishAt)
  reels    caption = title (hook line) + short description + hashtags (channel tag first, max 30)
           + the socials block where it fits, through the Instagram API with Instagram Login
  tiktok   the same caption through the Content Posting API (Direct Post), with TikTok's
           required post screen: creator info, privacy picked by the user (no default),
           comments / Duet / Stitch off until switched on, commercial-content disclosure and
           the Music Usage Confirmation line. Until TikTok audits the app, posts are "Only me".

Posting engine (TikTok / Instagram): one "post" job per platform in the network lane (each
platform has its own worker, so they run side by side). Every step is written down before
the next one starts (<project>/platform_uploads.json): the TikTok publish_id, the Instagram
container id, "bytes sent", "publish sent", the final post id. A job that dies halfway
(crash, power cut, restart) continues from the last step it wrote: it asks the platform
where that post stands instead of posting again, and an Instagram publish whose answer got
lost is found among the account's newest posts. A failure stays on its platform: the others
carry on, and Retry only redoes the failed one.

Planned posts: YouTube gets publishAt; TikTok / Instagram are posted by this app at that time
(the PC must be on; a time missed while it was off is caught up at the next start).

1.2.42: TikTok "automatic" = TikTok Studio in SharkyClips' own browser (tiktok_browser.py, mode
"browser"): a planned time inside TikTok's window (20 min .. ~10 days) goes into TikTok's own
planner, so the PC needn't be on then; other times are posted by the publish loop at that time.
At most `tiktok_auto_daily` posts a day (a full day moves to the next one). A stop (CAPTCHA,
verification, login wall, unknown screen) falls back to "by hand" for that clip.
"""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse, HTMLResponse

from .. import config, easy as E, platforms as PF, publishing as P
from ..errors import SharkyClipsError
from ..project import Project, write_json_atomic
from . import state
from .jobs import ACTIVE, Job, JobCancelled

router = APIRouter()

PLATFORMS = ("youtube", "tiktok", "reels")
SOCIAL = ("tiktok", "reels")
NAMES = {"youtube": "YouTube", "tiktok": "TikTok", "reels": "Instagram"}
LIMITS = {
    "youtube": {"title": 100, "description": 5000, "max_seconds": 180, "min_seconds": 1},
    "tiktok": {"caption": PF.CAPTION_MAX["tiktok"], "max_seconds": 600, "min_seconds": 3},
    "reels": {"caption": PF.CAPTION_MAX["reels"], "hashtags": 30, "max_seconds": 900, "min_seconds": 3},
}
LEAD_S = 120  # a planned TikTok / Instagram time must be at least this far ahead
POLL_S = 3.0
PROCESS_WAIT_S = 600  # wait this long inside the job; after that the publish loop checks back
MAX_TRIES = 6
STATS_EVERY_S = 6 * 3600
TIKTOK_PRIVACY = ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
TIKTOK_DEFAULTS = {"privacy": None, "allow_comment": False, "allow_duet": False, "allow_stitch": False,
                   "disclose": False, "brand_organic": False, "brand_content": False}
MUSIC_URL = "https://www.tiktok.com/legal/page/global/music-usage-confirmation/en"
BRANDED_URL = "https://www.tiktok.com/legal/page/global/bc-policy/en"
TIKTOK_STUDIO = "https://www.tiktok.com/tiktokstudio/content"

_start_lock = threading.Lock()
_stats_at = {"t": 0.0}


def _app():
    from . import app as appmod  # lazy: app.py imports this module

    return appmod


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return P.iso(dt)


# ===================================================================== stored choices


def targets() -> list[str]:
    """The platform switches, remembered (all three on until changed)."""
    t = config.get("publish_targets")
    if not isinstance(t, list):
        return list(PLATFORMS)
    return [p for p in PLATFORMS if p in t]


def set_targets(value: list[str]) -> list[str]:
    config.update(publish_targets=[p for p in PLATFORMS if p in (value or [])])
    return targets()


def _store_path(project: Project) -> Path:
    return project.dir / "multipost.json"


_slock = threading.RLock()


def _store(project: Project) -> dict:
    from ..project import read_json_shared

    data = read_json_shared(_store_path(project), {})
    return data if isinstance(data, dict) else {}


def clip_store(project: Project, cid: str) -> dict:
    d = _store(project).get(cid) or {}
    return {"drafts": dict(d.get("drafts") or {}), "tiktok": {**TIKTOK_DEFAULTS, **(d.get("tiktok") or {})}}


def save_clip_store(project: Project, cid: str, drafts: dict | None = None, tiktok: dict | None = None) -> dict:
    with _slock:
        all_ = _store(project)
        cur = all_.get(cid) or {}
        if drafts is not None:
            d = dict(cur.get("drafts") or {})
            for plat, v in drafts.items():
                if plat in PLATFORMS and isinstance(v, dict):
                    keep = {k: x for k, x in {**(d.get(plat) or {}), **v}.items() if x is not None}
                    d[plat] = keep
            cur["drafts"] = d
        if tiktok is not None:
            t = {**TIKTOK_DEFAULTS, **(cur.get("tiktok") or {})}
            for k in TIKTOK_DEFAULTS:
                if k in tiktok:
                    t[k] = tiktok[k] if k == "privacy" else bool(tiktok[k])
            if t["privacy"] not in TIKTOK_PRIVACY:
                t["privacy"] = None
            cur["tiktok"] = t
        all_[cid] = cur
        write_json_atomic(_store_path(project), all_)
    return clip_store(project, cid)


# ===================================================================== content per platform


def _lang(project: Project, cand: dict, meta: dict) -> str | None:
    return meta.get("language") or (cand.get("publish") or {}).get("language")


def _youtube_meta(project: Project, cand: dict) -> dict:
    """The YouTube meta the upload uses: a Library setup if the user made one, else the prefill
    (Easy: with the card's chosen title)."""
    from . import publishing as pub

    item = P.get(P.key_of(project.id, cand["id"]))
    meta = dict((item or {}).get("meta") or pub.prefill(project, cand))
    prefs = E.clip_prefs(E.load(project), cand["id"])
    if prefs.get("title") and not item:
        from .. import youtube

        meta["title"] = youtube.clean_text(prefs["title"], 100)
    return meta


def _hashtags_first(tags: list[str]) -> list[str]:
    """The channel's own hashtags (e.g. #mychannel) lead every social caption."""
    from ..edit import brand

    chan = [h.lstrip("#") for h in brand.channel_hashtags()]
    seen = {c.casefold() for c in chan}
    return chan + [h.lstrip("#") for h in tags if h.lstrip("#").casefold() not in seen]


def ai_voice(project: Project, cid: str) -> dict:
    from .platforms_api import ai_flags, ai_voice_for

    return ai_voice_for(state.file_dub(project, cid, ""), ai_flags(None))


def social_caption(project: Project, cand: dict, platform: str, meta: dict | None = None) -> str:
    from ..edit import brand

    meta = meta or _youtube_meta(project, cand)
    ai = ai_voice(project, cand["id"])
    return PF.caption(platform, meta.get("title") or "", meta.get("description") or "",
                      _hashtags_first(meta.get("hashtags") or []), ai["line"] if ai["note"] else None,
                      socials=brand.socials_block(_lang(project, cand, meta)))


def drafts(project: Project, cand: dict) -> dict:
    """What each platform gets: generated, or the user's edit (kept per clip)."""
    from .. import youtube

    meta = _youtube_meta(project, cand)
    saved = clip_store(project, cand["id"])["drafts"]
    yt = saved.get("youtube") or {}
    title = yt.get("title") if yt.get("title") is not None else meta.get("title") or ""
    desc = yt.get("description") if yt.get("description") is not None else meta.get("description") or ""
    lang = _lang(project, cand, meta)
    full = P.compose_description(desc, meta.get("hashtags") or [], None, lang=lang, short=True)
    out = {"youtube": {"title": youtube.censor_text(title, lang), "description": desc,
                       "full_description": youtube.censor_text(full, lang),
                       "hashtags": meta.get("hashtags") or [], "tags": meta.get("tags") or [],
                       "edited": bool(yt)}}
    for p in SOCIAL:
        mine = (saved.get(p) or {}).get("caption")
        out[p] = {"caption": youtube.censor_text(mine, lang) if mine is not None
                  else social_caption(project, cand, p, {**meta, "title": title, "description": desc}),
                  "edited": mine is not None}
    return out


def hashtag_count(text: str) -> int:
    return len(re.findall(r"(?<![\w#])#[^\s#]+", text or ""))


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: max(0, limit - 1)]
    if " " in cut[-20:]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:-–") + "…"


def _shorten_caption(text: str, limit: int) -> str:
    """Keeps the hashtag line and the AI-voice line, shortens the body, drops socials first."""
    if len(text) <= limit:
        return text
    parts = text.split("\n\n")
    tags = [x for x in parts if x.strip().startswith("#")]
    body = [x for x in parts if not x.strip().startswith("#")]
    while body and len("\n\n".join(body + tags)) > limit and len(body) > 1:
        body.pop()
    head = "\n\n".join(body)
    tail = ("\n\n" + "\n\n".join(tags)) if tags else ""
    return (_shorten(head, max(10, limit - len(tail))) + tail)[:limit]


def _trim_hashtags(text: str, keep: int) -> str:
    seen = 0

    def one(m):
        nonlocal seen
        seen += 1
        return m.group(0) if seen <= keep else ""

    out = re.sub(r"(?<![\w#])#[^\s#]+", one, text or "")
    return re.sub(r"[ \t]{2,}", " ", out).replace(" \n", "\n").strip()


# ===================================================================== state per platform


def _rec(project: Project, cid: str, platform: str) -> dict:
    return (PF.records(project).get(cid) or {}).get(platform) or {}


def active_job(project_id: str, cid: str, platform: str) -> Job | None:
    for j in _app().jobs.for_project(project_id):
        if j.status in ACTIVE and j.params.get("clip_id") == cid and (
                (j.kind == "post" and j.params.get("platform") == platform)
                or (j.kind in ("platform_export", "platform_upload") and j.params.get("platform") == platform)):
            return j
    return None


def _social_state(project: Project, cid: str, platform: str) -> dict:
    rec = _rec(project, cid, platform)
    j = active_job(project.id, cid, platform)
    st = rec.get("status")
    status = {"error": "failed", "exported": "idle", None: "idle"}.get(st, st)
    if j is not None:
        status = {"exporting": "preparing", "preparing": "preparing"}.get(j.stage or "", None) or (
            "uploading" if j.status == "running" and j.kind != "platform_export" else
            "preparing" if j.kind == "platform_export" else status if status in ("processing",) else "uploading")
        if rec.get("mode") == "semi":  # by hand: the job only makes the file
            status = "preparing"
    return {"platform": platform, "status": status, "progress": j.progress if j is not None and j.status == "running" else None,
            "url": rec.get("url"), "privacy": rec.get("privacy"), "publish_at": rec.get("publish_at"),
            "posted_at": rec.get("posted_at"), "late": bool(rec.get("late")), "error": rec.get("error") if status == "failed" else None,
            "views": rec.get("views"), "likes": rec.get("likes"), "stats_at": rec.get("stats_at"),
            "next_try_at": rec.get("next_try_at") if status == "failed" else None,
            "make_public_url": TIKTOK_STUDIO if platform == "tiktok" and rec.get("privacy") == "self_only"
            and status in ("published", "processing") else None,
            "job": j.id if j is not None else None, "mode": rec.get("mode"), "manual": bool(rec.get("manual")),
            "remind_at": rec.get("remind_at") if status == "ready" else None,
            "remote": bool(rec.get("remote")), "fallback": rec.get("fallback"),
            "shot": (rec.get("fallback") or {}).get("shot") or (rec.get("auto_error") or {}).get("shot")}


def _youtube_state(project: Project, cid: str) -> dict:
    from .. import youtube
    from . import publishing as pub

    key = P.key_of(project.id, cid)
    item = P.get(key)
    live = state.live_upload(project, cid)
    js = pub._plan_jobs().get(key, [])
    st = pub.row_status(item, live, js, youtube.lock_state()["state"], P.now_utc())
    up = next((j for j in js if j.kind == "upload"), None)
    mapping = {"draft": "idle", "published": "published", "locked": "published", "failed": "failed"}
    status = mapping.get(st["status"], "scheduled")
    if st["status"] == "scheduled":
        step = st.get("step") or ""
        if "uploading" in step:
            status = "uploading"
        elif item and item.get("now"):
            status = "preparing"
        elif step == "uploaded":
            status = "scheduled"
    return {"platform": "youtube", "status": status,
            "progress": up.progress if up is not None and up.status == "running" else None,
            "url": (live or {}).get("url"), "privacy": "private" if st["status"] == "locked" else (live or {}).get("privacy"),
            "publish_at": (item or {}).get("publish_at") or (live or {}).get("publish_at"),
            "posted_at": (live or {}).get("uploaded_at"), "late": False,
            "error": (item or {}).get("error") if status == "failed" else None,
            "views": (live or {}).get("views"), "likes": (live or {}).get("likes"),
            "stats_at": (live or {}).get("stats_at"), "next_try_at": (item or {}).get("next_try_at"),
            "locked": st["status"] == "locked", "make_public_url": None, "job": up.id if up else None}


def clip_states(project: Project, cid: str) -> dict:
    """{"youtube": {...}, "tiktok": {...}, "reels": {...}, "total_views", "everywhere"}"""
    out = {"youtube": _youtube_state(project, cid)}
    for p in SOCIAL:
        out[p] = _social_state(project, cid, p)
    views = [s.get("views") for s in (out[p] for p in PLATFORMS) if isinstance(s.get("views"), int)]
    want = targets()
    return {**out, "total_views": sum(views) if views else None,
            "everywhere": bool(want) and all(out[p]["status"] == "published" for p in want)}


# ===================================================================== accounts + quotas


def accounts() -> dict:
    from .. import youtube

    st = youtube.status()
    so = st.get("signed_out")
    tok_channels = st.get("channels") or []
    yt_pill = "ok" if st["connected"] and st.get("channel") else (
        "attention" if st["connected"] else "signed_out")
    reason = None if yt_pill == "ok" else ("no_channel" if st["connected"] else "signed_out" if so else "not_connected")
    if st["connected"] and not st.get("manage"):
        yt_pill, reason = "attention", "scope"
    ch = st.get("channel") if isinstance(st.get("channel"), dict) else {}
    yt = {"platform": "youtube", "connected": st["connected"], "handle": ch.get("title"), "name": ch.get("title"),
          "avatar": bool(ch.get("thumbnail") or next((c.get("thumbnail") for c in tok_channels if c.get("thumbnail")), None)),
          "health": {"pill": yt_pill, "reason": reason, "message": (so or {}).get("reason") if so else None},
          "audited": True, "has_app": bool(st.get("ready")), "connected_at": st.get("connected_at"),
          "encrypted": True, "stats": bool(st.get("analytics")) or st["connected"], "mode": "api"}
    return {"youtube": yt, "tiktok": PF.account("tiktok"), "reels": PF.account("reels")}


def _posts_last_day(platform: str) -> int:
    since = time.time() - 86400
    n = 0
    for project in _app().list_projects():
        for plats in PF.records(project).values():
            r = (plats or {}).get(platform) or {}
            if (r.get("publish_id") or r.get("media_id") or r.get("post_id")) and float(r.get("init_at") or 0) > since:
                n += 1
    return n


def quotas(fetch: bool = True) -> dict:
    from .. import youtube

    q = youtube.quota_view()
    tt = _posts_last_day("tiktok")
    ig = PF.ig_quota() if fetch and PF.connected("reels") else None
    from .. import tiktok_browser as TB

    browser = PF.mode("tiktok") == "browser"
    return {"youtube": {"used": q["used"], "total": q["limit"], "uploads_left": q["uploads_left"],
                        "resets_at": q["resets_at"]},
            "tiktok": {"used": _tiktok_day_count(_now()), "total": TB.daily_cap(), "approx": False, "auto": True}
            if browser else {"used": tt, "total": PF.TIKTOK_DAILY_CAP, "approx": True},
            "reels": ig and {"used": ig["used"], "total": ig["total"]} or {"used": _posts_last_day("reels"),
                                                                           "total": 50, "approx": True}}


# ===================================================================== checks + one-tap fixes


def _problem(platform: str, code: str, fix: str | None = None, **params) -> dict:
    return {"platform": platform, "code": code, "fix": fix, "params": params}


def _tiktok_view(settings: dict, fresh: bool = False) -> dict:
    """creator info + the rules the post screen needs (or why it isn't available)."""
    if not PF.connected("tiktok"):
        return {"ok": False, "audited": False}
    audited = bool((PF.load_app("tiktok") or {}).get("audited"))
    try:
        info = PF.tiktok_creator_info(fresh=fresh)  # fresh: the post screen opens (TikTok's rule)
    except SharkyClipsError as exc:
        return {"ok": False, "audited": audited, "error": {"message": exc.message, "hint": exc.hint,
                                                            "code": getattr(exc, "code", None)}}
    opts = info["privacy_options"] if audited else ["SELF_ONLY"]
    return {"ok": True, "audited": audited, "creator": {k: info[k] for k in ("username", "nickname")},
            "privacy_options": opts, "comment_disabled": info["comment_disabled"],
            "duet_disabled": info["duet_disabled"], "stitch_disabled": info["stitch_disabled"],
            "max_seconds": info["max_seconds"], "settings": settings,
            "privacy": settings.get("privacy") if audited else "SELF_ONLY",
            "music_url": MUSIC_URL, "branded_url": BRANDED_URL}


def problems(project: Project, cand: dict, want: list[str], d: dict, tt: dict | None, acc: dict,
             duration: float, quota: dict | None = None, modes: dict | None = None) -> list[dict]:
    out: list[dict] = []
    for p in want:
        a = acc[p]
        semi = (modes or {}).get(p) in ("semi", "browser")  # by hand / TikTok Studio: no API account,
        # no API quota, no API post screen (the browser lane keeps its own daily limit)
        if semi:
            pass
        elif not a["connected"]:  # (the content checks still run: fix everything in one go)
            out.append(_problem(p, "not_connected", "connect"))
        elif a["health"]["pill"] == "signed_out":
            out.append(_problem(p, "signed_out", "connect"))
        lim = LIMITS[p]
        top = (tt or {}).get("max_seconds") if p == "tiktok" and (tt or {}).get("ok") else lim["max_seconds"]
        if duration > (top or lim["max_seconds"]) + 0.05:
            out.append(_problem(p, "too_long", "turn_off", max=int(top or lim["max_seconds"]), dur=round(duration)))
        if duration < lim["min_seconds"]:
            out.append(_problem(p, "too_short", "turn_off", min=lim["min_seconds"]))
        if p == "youtube":
            t = d["youtube"]["title"].strip()
            if not t:
                out.append(_problem(p, "title_empty", "edit"))
            elif len(t) > lim["title"]:
                out.append(_problem(p, "title_too_long", "shorten_title", n=len(t), max=lim["title"]))
            if len(d["youtube"]["full_description"]) > lim["description"]:
                out.append(_problem(p, "description_too_long", "shorten_description",
                                    n=len(d["youtube"]["full_description"]), max=lim["description"]))
            continue
        cap = d[p]["caption"]
        if len(cap) > lim["caption"]:
            out.append(_problem(p, "caption_too_long", "shorten_caption", n=len(cap), max=lim["caption"]))
        if p == "reels" and hashtag_count(cap) > lim["hashtags"]:
            out.append(_problem(p, "too_many_hashtags", "trim_hashtags", n=hashtag_count(cap), max=lim["hashtags"]))
        if semi:
            continue
        q = (quota or {}).get(p) or {}
        if q.get("total") and q.get("used", 0) >= q["total"]:
            out.append(_problem(p, "quota_full", "plan", used=q["used"], total=q["total"]))
        if p == "tiktok" and tt is not None:
            if not tt.get("ok"):
                if tt.get("error"):
                    out.append(_problem(p, "cannot_post", None, message=tt["error"]["message"]))
                continue
            s = tt["settings"]
            if tt["audited"] and not s.get("privacy"):
                out.append(_problem(p, "privacy_missing", "choose_privacy"))
            elif tt["audited"] and s.get("privacy") not in tt["privacy_options"]:
                out.append(_problem(p, "privacy_missing", "choose_privacy"))
            if s.get("disclose") and not (s.get("brand_organic") or s.get("brand_content")):
                out.append(_problem(p, "disclosure_incomplete", "choose_disclosure"))
            if s.get("disclose") and s.get("brand_content") and tt["privacy"] == "SELF_ONLY":
                out.append(_problem(p, "branded_private", "fix_branded" if tt["audited"] else "no_branded"))
    held = state.bleep_hold(project, cand["id"])
    if held and want:
        out.insert(0, _problem("all", "bleep_hold", "bleep_check", n=held))
    return out


def apply_fix(project: Project, cid: str, platform: str, code: str) -> dict:
    """The one-tap fixes the server can make (the rest are buttons in the UI)."""
    A = _app()
    cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
    d = drafts(project, cand)
    if code == "shorten_title":
        save_clip_store(project, cid, drafts={"youtube": {"title": _shorten(d["youtube"]["title"], LIMITS["youtube"]["title"])}})
    elif code == "shorten_description":
        room = LIMITS["youtube"]["description"] - (len(d["youtube"]["full_description"]) - len(d["youtube"]["description"]))
        save_clip_store(project, cid, drafts={"youtube": {"description": _shorten(d["youtube"]["description"], max(50, room))}})
    elif code == "shorten_caption" and platform in SOCIAL:
        save_clip_store(project, cid, drafts={platform: {"caption": _shorten_caption(d[platform]["caption"], LIMITS[platform]["caption"])}})
    elif code == "trim_hashtags" and platform == "reels":
        save_clip_store(project, cid, drafts={"reels": {"caption": _trim_hashtags(d["reels"]["caption"], LIMITS["reels"]["hashtags"])}})
    elif code == "no_branded":
        save_clip_store(project, cid, tiktok={"brand_content": False})
    elif code == "fix_branded":
        tt = clip_store(project, cid)["tiktok"]
        if tt.get("privacy") == "SELF_ONLY":
            save_clip_store(project, cid, tiktok={"privacy": None})
    else:
        raise SharkyClipsError("This fix isn't available here.")
    return view(project, cid)


def _source_info(project: Project, cid: str) -> dict:
    """Which file TikTok / Instagram get: the rendered 9:16 clip (ready / still rendering) or an
    export with the platform preset made first (clips that were never rendered)."""
    from .easy import _render_jobs

    j = _render_jobs(project.id).get(cid)
    clip = state.load_clips(project).get(cid)
    if j is not None and j.status in ACTIVE:
        return {"kind": "rendering", "file": None}
    if clip and (project.dir / "clips" / clip["file"]).is_file():
        return {"kind": "clip", "file": str(project.dir / "clips" / clip["file"]), "stamp": clip.get("rendered_at")}
    return {"kind": "export", "file": None}


def cover_ms(cand: dict) -> int:
    """The frame TikTok / Instagram show as the cover: the clip's peak moment."""
    peak = cand.get("peak")
    start, dur = float(cand.get("start") or 0), float(cand.get("duration") or 0)
    if peak is None:
        return 0
    return int(max(0.0, min(dur - 0.2, float(peak) - start)) * 1000)


def view(project: Project, cid: str, want: list[str] | None = None, fresh: bool = False) -> dict:
    """Everything the publish preview shows for one clip."""
    A = _app()
    review = state.load_review(project)
    cand = state.effective_cand(A._cand(project, cid), review)
    want = [p for p in (want if want is not None else targets()) if p in PLATFORMS]
    d = drafts(project, cand)
    acc = accounts()
    store = clip_store(project, cid)
    modes = modes_now()
    tt = _tiktok_view(store["tiktok"], fresh) if modes["tiktok"] == "api" else None
    q = quotas()
    states = clip_states(project, cid)
    todo = [p for p in want if states[p]["status"] in ("idle", "failed", "cancelled")]
    probs = problems(project, cand, todo, d, tt, acc, float(cand["duration"]), q, modes)
    src = _source_info(project, cid)
    from . import publishing as pub

    return {"project_id": project.id, "clip_id": cid, "targets": want, "drafts": d, "accounts": acc,
            "states": states, "problems": probs, "tiktok": tt, "quota": q, "limits": LIMITS,
            "duration": float(cand["duration"]), "cover_ms": cover_ms(cand), "source": src["kind"],
            "ai_voice": ai_voice(project, cid), "cover_kind": pub.default_cover_kind(project, cid, review),
            "bleep_hold": state.bleep_hold(project, cid), "lead_s": LEAD_S,
            "ready": src["kind"] != "rendering", "modes": modes}


def modes_now() -> dict:
    """semi (default): SharkyClips makes the file, copies the caption and opens the upload page,
    you paste and post; api: posted by itself (automatic posting on + a working token)."""
    return {"youtube": "api", "tiktok": PF.mode("tiktok"), "reels": PF.mode("reels")}


# ===================================================================== start


def _youtube_start(project: Project, cand: dict, when: datetime | None, d: dict) -> dict:
    """Through the 1.2.7 publish plan: publishAt for a planned time, now = upload right away."""
    from .. import youtube
    from . import easy as WE, publishing as pub

    A = _app()
    key = P.key_of(project.id, cand["id"])
    if state.live_upload(project, cand["id"]):
        return {"status": "published"}
    if any(j.kind == "upload" for j in pub._plan_jobs().get(key, [])):
        return {"status": "uploading"}
    item = P.get(key)
    if item is None:
        easy = E.load(project)["easy"] and _source_info(project, cand["id"])["kind"] != "export"
        item = WE._plan_meta(project, cand, E.clip_prefs(E.load(project), cand["id"])) if easy \
            else pub._item_for(project, cand["id"])
    meta = {**item["meta"], "title": youtube.clean_text(d["youtube"]["title"], 100),
            "description": d["youtube"]["description"]}
    pub._restart_clip(project.id, cand["id"])
    if when is None:
        P.put({**P.unschedule(item), "meta": meta, "prep": item.get("prep") or {}, "now": True})
        it = P.get(key)
        step, info = pub.next_step(project, A._cand(project, cand["id"]), it)
        if step == "upload":
            body = pub.upload_body(project, A._cand(project, cand["id"]), it, info["source"], info.get("ab"))
            if info["source"] == "clip":
                body["thumbnail"] = "cover"
            A.submit_upload(project.id, cand["id"], body)
            return {"status": "uploading"}
        if step == "export":
            pub.submit_export_for(key, info)
        elif step == "burn":
            pub.submit_cover_burn(key, info)
        pub.scheduler.poke()
        return {"status": "preparing"}
    P.put({**item, "meta": meta})
    res = pub.schedule([{"project_id": project.id, "clip_id": cand["id"], "publish_at": _iso(when)}], "manual")
    if not res["planned"]:
        raise SharkyClipsError("Couldn't plan this clip on YouTube.", (res["skipped"] or [{}])[0].get("reason"))
    return {"status": "scheduled", "publish_at": res["planned"][0]["publish_at"], "moved": res["planned"][0]["moved"]}


def start(project: Project, cid: str, body: dict) -> dict:
    """POST /api/publish/{project}/{clip}. body: {platforms, when: "now" | ISO time, consent (TikTok),
    drafts?: {youtube: {title, description}, tiktok: {caption}, reels: {caption}}, tiktok?: {...}}."""
    A = _app()
    want = [p for p in (body.get("platforms") or []) if p in PLATFORMS]
    if not want:
        raise SharkyClipsError("Switch on at least one platform.")
    if body.get("remember", True):
        set_targets(want)
    if isinstance(body.get("drafts"), dict) or isinstance(body.get("tiktok"), dict):
        save_clip_store(project, cid, drafts=body.get("drafts") if isinstance(body.get("drafts"), dict) else None,
                        tiktok=body.get("tiktok") if isinstance(body.get("tiktok"), dict) else None)
    when_raw = body.get("when") or "now"
    if when_raw == "auto":  # Easy's "Auto": the next free slot of the plan (daily limit, best times)
        from . import publishing as pub

        when_raw = _iso(P.next_free_slot(P.earliest(), pub.releases(), skip={P.key_of(project.id, cid)}))
    when = None if when_raw == "now" else P.parse(when_raw)
    if when_raw != "now" and when is None:
        raise SharkyClipsError("Pick a date and time for the plan.")
    if when is not None and when < _now() + timedelta(seconds=LEAD_S - 5):
        raise SharkyClipsError("The planned time has to be a few minutes ahead.", "Pick a later time, or post now.")
    with _start_lock:
        v = view(project, cid, want)
        todo = [p for p in want if v["states"][p]["status"] in ("idle", "failed", "cancelled")]
        if "tiktok" in todo and v["modes"]["tiktok"] == "api" and not body.get("consent"):
            raise SharkyClipsError("Confirm TikTok's Music Usage Confirmation first.")
        if v["problems"]:
            e = SharkyClipsError("Fix the marked problems first.", None)
            e.code = "problems"  # type: ignore[attr-defined]
            e.problems = v["problems"]  # type: ignore[attr-defined]
            raise e
        if not v["ready"] and any(p in todo for p in SOCIAL):
            pass  # still rendering: the post job waits for the clip (status "preparing")
        cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
        results: dict[str, dict] = {p: {"status": v["states"][p]["status"], "skipped": True}
                                    for p in want if p not in todo}
        # YouTube first: a full day moves its time, and TikTok / Instagram follow that time
        if "youtube" in todo:
            try:
                results["youtube"] = _youtube_start(project, cand, when, v["drafts"])
                if results["youtube"].get("publish_at"):
                    when = P.parse(results["youtube"]["publish_at"]) or when
            except SharkyClipsError as exc:
                results["youtube"] = {"status": "failed", "error": {"message": exc.message, "hint": exc.hint}}
        for p in (x for x in todo if x in SOCIAL):
            try:
                results[p] = _social_start(project, cand, p, when, v)
            except SharkyClipsError as exc:
                PF.record(project, cid, p, status="failed", error={"message": exc.message, "hint": exc.hint,
                                                                   "kind": "fatal"})
                results[p] = {"status": "failed", "error": {"message": exc.message, "hint": exc.hint}}
    return {"results": results, "view": view(project, cid, want)}


def _social_start(project: Project, cand: dict, platform: str, when: datetime | None, v: dict) -> dict:
    cid = cand["id"]
    rec = _rec(project, cid, platform)
    if rec.get("status") in ("published", "processing") or rec.get("media_id") or \
            (rec.get("publish_id") and rec.get("status") not in ("failed", "cancelled")):
        return {"status": rec.get("status") or "processing", "skipped": True}  # never twice
    if rec.get("status") == "scheduled" and (rec.get("via") == "chrome" or rec.get("remote")):
        return {"status": "scheduled", "skipped": True}  # planned on the platform already
    if rec.get("submitted_at") and rec.get("status") not in ("cancelled",) and not rec.get("cleared"):
        return {"status": rec.get("status") or "processing", "skipped": True}  # pressed "Post" once: look it up
    try:
        from . import pubqueue_api

        live = pubqueue_api.live_elsewhere(project.id, cid, platform)
    except Exception:  # noqa: BLE001
        live = None
    if live:  # posted / planned through the publish queue (Claude in Chrome): not again
        return {"status": live, "skipped": True}
    if active_job(project.id, cid, platform) is not None:
        return {"status": "uploading", "skipped": True}
    ai = v["ai_voice"]
    caption = v["drafts"][platform]["caption"]
    if v["modes"][platform] == "semi":  # by hand: make the file now, whatever the planned time
        PF.record(project, cid, platform, mode="semi", caption=caption, ai_voice=ai if ai["dub"] else None,
                  error=None, attempts=0, next_try_at=None, late=False, status="preparing",
                  publish_at=None, remind_at=_iso(when) if when else None, file=None, folder=None,
                  shared_at=None, manual=None, url=None)
        submit(project.id, cid, platform)
        return {"status": "preparing", "mode": "semi", "upload_page": PF.UPLOAD_PAGE[platform]}
    if v["modes"][platform] == "browser":
        return _browser_start(project, cand, when, v, caption)
    settings = dict(v["tiktok"]["settings"]) if platform == "tiktok" and v.get("tiktok") else None
    if platform == "tiktok" and settings is not None and not v["tiktok"]["audited"]:
        settings["privacy"] = "SELF_ONLY"
    PF.record(project, cid, platform, mode="api", caption=caption, settings=settings, ai_label=bool(ai["label"]),
              error=None, attempts=0, next_try_at=None, late=False, cover_ms=v["cover_ms"],
              intent=f"{int(time.time() * 1000)}", consent_at=time.time() if platform == "tiktok" else None,
              status="scheduled" if when else "preparing", publish_at=_iso(when) if when else None,
              file=None if rec.get("status") != "failed" else rec.get("file"))
    if when:
        return {"status": "scheduled", "publish_at": _iso(when)}
    submit(project.id, cid, platform)
    return {"status": "uploading"}


# ===================================================================== the post job


def submit(project_id: str, cid: str, platform: str, job_id: str | None = None, attempt: int = 1) -> Job:
    A = _app()
    project = A.get_project(project_id)
    cand = A._cand(project, cid)
    title = ((cand.get("publish") or {}).get("titles") or [None])[0] or (cand.get("text") or "")[:90]

    def run(job: Job):
        return run_post(project_id, cid, platform, job)

    return A.jobs.submit("post", "net", project_id,
                         {"clip_id": cid, "platform": platform, "rank": cand.get("rank"), "title": title,
                          "project_title": project.load_meta().get("title") or project_id},
                         run, key=f"post:{project_id}:{cid}:{platform}", persist=True, job_id=job_id, attempt=attempt)


def rebuild(d: dict, keep_id: str | None, attempt: int):
    p = d.get("params") or {}
    return submit(d["project_id"], p["clip_id"], p["platform"], job_id=keep_id, attempt=attempt)


def _check_cancel(job: Job | None) -> None:
    if job is not None and job.cancel_requested:
        raise JobCancelled()


def _wait(job: Job | None, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        _check_cancel(job)
        time.sleep(min(0.25, max(0.0, end - time.time())))


def _file_for(project: Project, cid: str, platform: str, rec: dict, job: Job | None) -> Path:
    """The video this post sends: the one an earlier step of this post used, else the rendered
    clip, else a fresh export with the platform preset (made here, in the job)."""
    if rec.get("file") and Path(rec["file"]).is_file() and (rec.get("publish_id") or rec.get("container_id")
                                                             or rec.get("submitted_at") or rec.get("remote")):
        return Path(rec["file"])  # resuming: exactly the bytes TikTok / Instagram already got
    A = _app()
    src = _source_info(project, cid)
    while src["kind"] == "rendering":
        if job is not None:
            A.jobs.update(job, stage="waiting_render", progress=None)
        _wait(job, 3.0)
        src = _source_info(project, cid)
    if state.bleep_hold(project, cid):
        raise SharkyClipsError("A swear in this clip is still heard.",
                               "Listen to the clip (Bleep report), then press \"I checked it\".")
    if src["kind"] == "clip":
        return Path(src["file"])
    from .. import export
    from ..clips import ClipOptions, Facecam
    from .platforms_api import _render_options

    review = state.load_review(project)
    c = state.effective_cand(A._cand(project, cid), review)
    opts, hook = _render_options(project, c)
    req = export.ExportRequest.from_dict({"format": "mp4_h264", "preset": PF.PRESET[platform]})
    if job is not None:
        A.jobs.update(job, stage="exporting", progress=0.0)
    entry = export.run_export(project, c, ClipOptions.from_dict({**opts, "hook_text": hook}),
                              Facecam.from_dict(review.get("facecam")), req,
                              lambda _s, f: job is not None and A.jobs.update(job, stage="exporting", progress=f))
    return export.exports_root(project) / next(f["name"] for f in entry["files"] if f.get("role") == "media")


def run_post(project_id: str, cid: str, platform: str, job: Job | None = None) -> dict:
    A = _app()
    project = A.get_project(project_id)
    rec = _rec(project, cid, platform)
    if rec.get("status") == "published":
        return {"status": "published", "url": rec.get("url")}
    try:
        if rec.get("mode") == "browser" and (rec.get("remote") or rec.get("submitted_at")):
            return _browser_verify(project, cid, rec)  # sent before: look it up, never post twice
        file = _file_for(project, cid, platform, rec, job)
        if rec.get("mode") == "semi":
            return _run_semi(project, cid, platform, file, rec)
        if rec.get("mode") == "browser":
            return _run_browser(project, cid, file, rec, job)
        rec = PF.record(project, cid, platform, status="uploading", file=str(file), error=None)
        if job is not None:
            A.jobs.update(job, stage="uploading", progress=0.0)
        res = (_run_tiktok if platform == "tiktok" else _run_reels)(project, cid, file, rec, job)
        return res
    except JobCancelled:
        PF.record(project, cid, platform, status="cancelled", error=None)
        raise
    except SharkyClipsError as exc:
        _failed(project, cid, platform, exc)
        raise
    except Exception as exc:  # noqa: BLE001 - network trouble: a transient failure, tried again
        import requests

        if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
            e = PF.PlatformError("The connection dropped.", "SharkyClips tries again by itself.", platform,
                                 "network", "transient", 60.0)
            _failed(project, cid, platform, e)
            raise e from exc
        if rec.get("mode") == "semi":  # by hand: say so on the clip (Retry), never stuck "preparing"
            _failed(project, cid, platform, SharkyClipsError(f"{type(exc).__name__}: {exc}", None))
        raise


def _run_semi(project: Project, cid: str, platform: str, file: Path, rec: dict) -> dict:
    """By hand: the file goes to Downloads/SharkyClips/<stream> with the caption next to it
    (.txt); the UI copies the caption, opens the upload page and shows the file."""
    import shutil

    A = _app()
    c = A._cand(project, cid)
    folder = E.downloads_root() / E.safe_name(project.load_meta().get("title") or project.id, 80)
    folder.mkdir(parents=True, exist_ok=True)
    title = (clip_store(project, cid)["drafts"].get("youtube") or {}).get("title") or \
        ((c.get("publish") or {}).get("titles") or [None])[0] or (c.get("text") or "")[:60] or cid
    rank = f"{int(c.get('rank') or 0):02d}"
    dest = folder / f"{rank} {E.safe_name(title, 60)} - {NAMES[platform]}.mp4"
    for n in (40, 20):  # Windows paths stop at 260 characters (the .txt next to it is as long)
        if len(str(dest)) <= 240:
            break
        dest = folder / f"{rank} {E.safe_name(title, n)} - {NAMES[platform]}.mp4"
    if len(str(dest)) > 240:
        folder = E.downloads_root()
        folder.mkdir(parents=True, exist_ok=True)
        import hashlib

        tag = hashlib.sha1(project.id.encode()).hexdigest()[:6]  # short, still one per stream
        dest = folder / f"{rank} {NAMES[platform]} {tag}.mp4"
    try:
        shutil.copyfile(file, dest)
    except OSError as exc:
        raise SharkyClipsError(f"Couldn't save the {NAMES[platform]} file in {folder}.",
                               "Check that the Downloads folder exists and there's free space, then press Retry.") from exc
    caption = rec.get("caption") or ""
    (folder / f"{dest.stem}.txt").write_text(caption + "\n", encoding="utf-8")
    PF.record(project, cid, platform, status="ready", file=str(dest), folder=str(folder), error=None,
              ready_at=time.time())
    return {"status": "ready", "file": str(dest), "folder": str(folder), "mode": "semi"}


def shared(project: Project, cid: str, platform: str, url: str | None = None) -> dict:
    """By hand: "I shared it" (the post is out; SharkyClips didn't post it, so no link unless given)."""
    if platform not in SOCIAL:
        raise SharkyClipsError("Unknown platform.")
    rec = _rec(project, cid, platform)
    if rec.get("mode") != "semi" or rec.get("status") not in ("ready", "published"):
        raise SharkyClipsError("This post isn't waiting for you.", "Press Publish first.")
    u = (url or "").strip()
    PF.record(project, cid, platform, status="published", manual=True, posted_at=_iso(_now()),
              shared_at=time.time(), url=u if u.startswith("https://") else rec.get("url"))
    return clip_states(project, cid)


def handoff(project: Project, cid: str, platforms: list[str] | None = None) -> dict:
    """What the "post it yourself" steps need: per platform its state, the file, the caption to
    copy (the newest edit) and the upload page."""
    A = _app()
    cand = state.effective_cand(A._cand(project, cid), state.load_review(project))
    d = drafts(project, cand)
    ai = ai_voice(project, cid)
    out = {}
    for p in [x for x in (platforms or list(SOCIAL)) if x in SOCIAL]:
        rec = _rec(project, cid, p)
        out[p] = {**_social_state(project, cid, p),
                  "file": rec.get("file") if rec.get("status") in ("ready", "published") else None,
                  "caption": d[p]["caption"], "upload_page": PF.UPLOAD_PAGE[p],
                  "ai_label": bool(ai["dub"]) and bool(ai["label"])}
    return {"project_id": project.id, "clip_id": cid, "platforms": out}


def _failed(project: Project, cid: str, platform: str, exc: SharkyClipsError) -> None:
    rec = _rec(project, cid, platform)
    kind = getattr(exc, "kind", "fatal")
    tries = int(rec.get("attempts") or 0) + 1
    retry = getattr(exc, "retry_after", None)
    nxt = None
    if kind in ("transient", "rate_limit", "quota") and tries < MAX_TRIES and retry:
        nxt = time.time() + float(retry) * (1 if kind == "quota" else min(8, 2 ** (tries - 1)))
    if kind == "auth":  # Meta's 190: the token was revoked (or the password changed): connect again
        revoked = platform == "reels" and str(getattr(exc, "code", "")).split(":")[0] == "190"
        PF.note_problem(platform, "signed_out" if revoked else "attention", exc.message)
    PF.record(project, cid, platform, status="failed", attempts=tries, next_try_at=nxt,
              error={"message": exc.message, "hint": exc.hint, "code": getattr(exc, "code", None), "kind": kind})


def _progress(job: Job | None, lo: float, hi: float):
    A = _app()
    return lambda f: job is not None and A.jobs.update(job, stage="uploading", progress=lo + (hi - lo) * f)


def _run_tiktok(project: Project, cid: str, file: Path, rec: dict, job: Job | None) -> dict:
    A = _app()
    pid = rec.get("publish_id")
    if pid:  # resuming: where does this post stand?
        st = PF.tiktok_status(pid)
        if st["status"] in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return _tiktok_done(project, cid, rec, st)
        if st["status"] == "FAILED":  # that attempt is dead on TikTok's side: a new one is safe
            rec = PF.record(project, cid, "tiktok", publish_id=None, upload=None, upload_done=False,
                            last_fail=st.get("fail_reason"))
            pid = None
        elif not rec.get("upload_done") and rec.get("upload") and time.time() - float(rec.get("init_at") or 0) < 3000:
            PF.tiktok_send(file, rec["upload"], _progress(job, 0.05, 0.9))
            rec = PF.record(project, cid, "tiktok", upload_done=True)
    if not pid:
        info = PF.tiktok_creator_info(fresh=True)
        dur = float(state.effective_cand(A._cand(project, cid), state.load_review(project))["duration"])
        if dur > info["max_seconds"]:
            raise PF.PlatformError(f"TikTok takes videos up to {info['max_seconds']} s on this account.", None,
                                   "tiktok", "too_long", "fatal")
        audited = bool((PF.load_app("tiktok") or {}).get("audited"))
        post_info = PF.tiktok_post_info(rec.get("caption") or "", rec.get("settings") or {}, audited, info,
                                        bool(rec.get("ai_label")), rec.get("cover_ms"))
        _check_cancel(job)
        up = PF.tiktok_init(file, post_info)
        _check_cancel(job)  # (the init is written down before anything else can stop us)
        rec = PF.record(project, cid, "tiktok", publish_id=up["publish_id"], upload=up, init_at=time.time(),
                        upload_done=False, privacy=post_info["privacy_level"].lower(),
                        handle=info.get("username"))
        PF.tiktok_send(file, up, _progress(job, 0.05, 0.9))
        rec = PF.record(project, cid, "tiktok", upload_done=True)
    return _tiktok_poll(project, cid, rec, job)


def _tiktok_poll(project: Project, cid: str, rec: dict, job: Job | None) -> dict:
    A = _app()
    if job is not None:
        A.jobs.update(job, stage="processing", progress=0.95)
    end = time.time() + PROCESS_WAIT_S
    while True:
        st = PF.tiktok_status(rec["publish_id"])
        if st["status"] in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return _tiktok_done(project, cid, rec, st)
        if st["status"] == "FAILED":
            reason = st.get("fail_reason") or "unknown"
            PF.record(project, cid, "tiktok", publish_id=None, upload=None, upload_done=False, last_fail=reason)
            raise PF.PlatformError(f"TikTok couldn't publish the video ({reason}).", PF._tiktok_hint(reason),
                                   "tiktok", reason, "transient" if reason in ("internal_error", "file_format_check_failed") else "fatal", 60.0)
        if time.time() > end:
            PF.record(project, cid, "tiktok", status="processing", checked_at=time.time())
            return {"status": "processing"}
        _wait(job, POLL_S)


def _tiktok_done(project: Project, cid: str, rec: dict, st: dict) -> dict:
    handle = rec.get("handle") or (PF.load_token("tiktok") or {}).get("handle")
    ids = st.get("post_ids") or []
    url = f"https://www.tiktok.com/@{handle}/video/{ids[0]}" if ids and handle else (
        f"https://www.tiktok.com/@{handle}" if handle else "https://www.tiktok.com/")
    out = PF.record(project, cid, "tiktok", status="published", url=url, post_id=ids[0] if ids else None,
                    posted_at=rec.get("posted_at") or _iso(_now()), error=None, next_try_at=None)
    _calendar(project, cid, "tiktok", "published", out.get("url"))
    return {"status": "published", "url": out.get("url"), "privacy": out.get("privacy")}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().casefold()[:80]


def _find_published(rec: dict) -> dict | None:
    """An Instagram post of this caption made after the container (a lost publish answer)."""
    since = float(rec.get("container_at") or 0) - 120
    want = _norm(rec.get("caption") or "")
    for m in PF.ig_recent():
        try:
            ts = datetime.fromisoformat(str(m.get("timestamp")).replace("+0000", "+00:00").replace("Z", "+00:00")).timestamp()
        except ValueError:
            ts = 0
        if ts >= since and _norm(m.get("caption") or "") == want:
            return m
    return None


def _run_reels(project: Project, cid: str, file: Path, rec: dict, job: Job | None) -> dict:
    A = _app()
    if rec.get("media_id"):
        return _reels_done(project, cid, rec, rec["media_id"], rec.get("url"))
    container = rec.get("container_id")
    st = None
    if container:
        st = PF.ig_container_status(container)
        if st in ("ERROR", "EXPIRED"):
            rec = PF.record(project, cid, "reels", container_id=None, bytes_sent=False, publish_sent=False)
            container, st = None, None
        elif st == "PUBLISHED" or (rec.get("publish_sent") and st == "FINISHED"):
            m = _find_published(rec)
            if m:
                return _reels_done(project, cid, rec, str(m["id"]), m.get("permalink"))
    if not container:
        _check_cancel(job)
        container = PF.ig_container(rec.get("caption") or "", bool(rec.get("ai_label")), rec.get("cover_ms"))
        rec = PF.record(project, cid, "reels", container_id=container, container_at=time.time(), init_at=time.time(),
                        bytes_sent=False, publish_sent=False)
    if not rec.get("bytes_sent") and st != "FINISHED":
        _progress(job, 0, 1)(0.05)
        PF.ig_send(file, container)
        rec = PF.record(project, cid, "reels", bytes_sent=True)
    if job is not None:
        A.jobs.update(job, stage="processing", progress=0.85)
    end = time.time() + PROCESS_WAIT_S
    while True:
        st = PF.ig_container_status(container)
        if st == "FINISHED":
            break
        if st == "PUBLISHED":
            m = _find_published(rec)
            if m:
                return _reels_done(project, cid, rec, str(m["id"]), m.get("permalink"))
            break
        if st in ("ERROR", "EXPIRED"):
            PF.record(project, cid, "reels", container_id=None, bytes_sent=False, publish_sent=False)
            raise PF.PlatformError("Instagram couldn't process the video.",
                                   "Reels need MP4 H.264, 3 s to 15 min. SharkyClips tries again with a fresh upload.",
                                   "reels", st, "transient", 60.0)
        if time.time() > end:
            PF.record(project, cid, "reels", status="processing", checked_at=time.time())
            return {"status": "processing"}
        _wait(job, POLL_S)
    if rec.get("publish_sent"):
        m = _find_published(rec)
        if m:
            return _reels_done(project, cid, rec, str(m["id"]), m.get("permalink"))
    rec = PF.record(project, cid, "reels", publish_sent=True)
    media = PF.ig_publish(container)
    return _reels_done(project, cid, rec, media, None)


def _reels_done(project: Project, cid: str, rec: dict, media: str, url: str | None) -> dict:
    url = url or PF.ig_permalink(media)
    PF.record(project, cid, "reels", status="published", media_id=media, url=url, privacy="public",
              posted_at=rec.get("posted_at") or _iso(_now()), error=None, next_try_at=None)
    _calendar(project, cid, "reels", "published", url)
    return {"status": "published", "url": url, "media_id": media}



# ===================================================================== 1.2.42: TikTok Studio (browser)


def _post_day(r: dict):
    at = P.parse(r.get("publish_at")) or P.parse(r.get("posted_at"))
    return at.astimezone().date() if at is not None else None


def _tiktok_day_count(day_of: datetime, skip: tuple[str, str] | None = None) -> int:
    """TikTok posts that go live on this (local) day: planned, being posted or out, any way."""
    day = day_of.astimezone().date()
    n = 0
    for project in _app().list_projects():
        for cid, plats in PF.records(project).items():
            if skip and (project.id, cid) == skip:
                continue
            r = (plats or {}).get("tiktok") or {}
            if r.get("status") not in ("scheduled", "preparing", "uploading", "processing", "published"):
                continue
            if r.get("mode") == "semi" and r.get("status") != "published" and r.get("via") != "chrome":
                continue
            if _post_day(r) == day or (_post_day(r) is None and r.get("status") != "scheduled"
                                       and float(r.get("init_at") or r.get("auto_started_at") or 0) > time.time() - 86400
                                       and day == _now().astimezone().date()):
                n += 1
    return n


def browser_slot(when: datetime | None, skip: tuple[str, str] | None = None) -> datetime | None:
    """The daily limit: None (post now) / the planned time if that day has room, else the same
    time on the next day with room."""
    from .. import tiktok_browser as TB

    cap = TB.daily_cap()
    base = when or _now()
    for i in range(60):
        at = base + timedelta(days=i)
        if _tiktok_day_count(at, skip) < cap:
            return when if i == 0 else at
    raise SharkyClipsError("Every day of the next two months is full on TikTok.", "Raise the daily limit in Settings > Accounts.")


def _clip_title(project: Project, cid: str, rec: dict | None = None) -> str:
    """The first caption line (what TikTok Studio's content list shows)."""
    from .. import tiktok_browser as TB

    body, _ = TB.split_caption((rec or _rec(project, cid, "tiktok")).get("caption") or "")
    return (body.split("\n")[0] if body else "").strip() or cid


def _log(project: Project, cid: str, step: str, message: str, shot: str | None = None) -> None:
    rec = _rec(project, cid, "tiktok")
    log = list(rec.get("auto_log") or [])[-19:]
    log.append({"at": _iso(_now()), "step": step, "message": message[:300], "shot": shot})
    PF.record(project, cid, "tiktok", auto_log=log)


def _calendar(project: Project, cid: str, platform: str, status: str, url: str | None, when: str | None = None) -> None:
    try:
        from . import pubqueue_api

        pubqueue_api.note_auto(project.id, cid, platform, status, url, when)
    except Exception:  # noqa: BLE001 - the calendar is a mirror: never fails a post
        pass


def _browser_start(project: Project, cand: dict, when: datetime | None, v: dict, caption: str) -> dict:
    cid = cand["id"]
    ai = v["ai_voice"]
    at = browser_slot(when, (project.id, cid))
    PF.record(project, cid, "tiktok", mode="browser", caption=caption, ai_label=bool(ai["dub"]) and bool(ai["label"]),
              error=None, attempts=0, next_try_at=None, late=False, status="scheduled" if at else "preparing",
              publish_at=_iso(at) if at else None, remote=False, native=None, submitted_at=None, cleared=None,
              verify_tries=0, fallback=None, auto_error=None, url=None, remind_at=None, manual=None, via=None,
              file=None, scheduled_text=None)
    from .. import tiktok_browser as TB

    if at is None or TB.in_window(at) or at <= _now():
        submit(project.id, cid, "tiktok")
    out = {"status": "scheduled" if at else "uploading", "mode": "browser"}
    if at:
        out.update(publish_at=_iso(at), moved=bool(when is None or at != when))
    return out


def _run_browser(project: Project, cid: str, file: Path, rec: dict, job: Job | None) -> dict:
    from .. import tiktok_browser as TB

    A = _app()
    now = _now()
    at = P.parse(rec.get("publish_at"))
    native = at is not None and rec.get("native") is not False and TB.in_window(at, now)
    if at is not None and not native and at > now + timedelta(seconds=30):
        PF.record(project, cid, "tiktok", status="scheduled")  # the publish loop posts it at that time
        return {"status": "scheduled", "publish_at": rec.get("publish_at")}
    title = _clip_title(project, cid, rec)

    def step(name: str, frac: float) -> None:
        if job is not None:
            A.jobs.update(job, stage=name if name in ("uploading", "processing") else "uploading", progress=frac)
        _check_cancel(job)

    PF.record(project, cid, "tiktok", status="uploading", file=str(file), auto_started_at=time.time(), error=None)
    try:
        from . import pubqueue_api

        if pubqueue_api.unsure(project.id, cid, "tiktok"):  # maybe posted by hand already: look first
            row = TB.find_posts([title])[0]
            if row.get("found"):
                PF.record(project, cid, "tiktok", submitted_at=time.time(), remote=bool(row.get("scheduled")))
                return _browser_verify(project, cid, _rec(project, cid, "tiktok"))
    except TB.Blocked as exc:
        return _browser_blocked(project, cid, file, exc, title)
    except Exception:  # noqa: BLE001 - the look-up is extra care: the post itself decides
        pass
    try:
        res = TB.post(file, rec.get("caption") or "", when=at if native else None, ai_label=bool(rec.get("ai_label")),
                      title=title, shots_dir=project.dir / "logs" / "tiktok", tag=cid, on_step=step,
                      on_submit=lambda: PF.record(project, cid, "tiktok", submitted_at=time.time()))
    except TB.ScheduleUnavailable as exc:
        _log(project, cid, "schedule", exc.message)
        PF.record(project, cid, "tiktok", status="scheduled", native=False)
        if at is not None and at <= _now() + timedelta(minutes=1):
            return _run_browser(project, cid, file, _rec(project, cid, "tiktok"), job)
        return {"status": "scheduled", "publish_at": rec.get("publish_at")}
    except TB.Blocked as exc:
        return _browser_blocked(project, cid, file, exc, title)
    except JobCancelled:
        raise
    except Exception as exc:  # noqa: BLE001 - browser trouble (closed, timed out): stop, never loop
        sent = bool(_rec(project, cid, "tiktok").get("submitted_at"))
        return _browser_blocked(project, cid, file, TB.Blocked(
            "error", f"TikTok Studio: {type(exc).__name__}: {str(exc).splitlines()[0][:160] if str(exc) else ''}",
            "The clip is ready for you to post by hand.", None, sent, "browser"), title)
    handle = res.get("username") or (TB.status().get("username"))
    if res["status"] == "scheduled":
        PF.record(project, cid, "tiktok", status="scheduled", remote=True, scheduled_text=res.get("row"),
                  confirmed=res.get("confirmed"), handle=handle, privacy="public", error=None, checked_at=time.time(),
                  init_at=time.time())
        _log(project, cid, "scheduled", res.get("row") or "planned in TikTok Studio")
        _calendar(project, cid, "tiktok", "scheduled", None, rec.get("publish_at"))
        return {"status": "scheduled", "publish_at": rec.get("publish_at"), "row": res.get("row")}
    url = res.get("url") or (f"https://www.tiktok.com/@{handle}" if handle else None)
    PF.record(project, cid, "tiktok", status="published", url=url, posted_at=_iso(_now()), handle=handle,
              privacy="public", error=None, next_try_at=None, init_at=time.time(),
              verify_tries=0 if res.get("url") else 1)
    _log(project, cid, "published", res.get("row") or "posted")
    _calendar(project, cid, "tiktok", "published", url)
    return {"status": "published", "url": url}


def _browser_blocked(project: Project, cid: str, file: Path, exc, title: str) -> dict:
    from .. import tiktok_browser as TB

    TB.note_block(exc.reason, exc.message, exc.shot)
    _log(project, cid, exc.step or exc.reason, exc.message, exc.shot)
    err = {"reason": exc.reason, "message": exc.message, "hint": exc.hint, "shot": exc.shot, "at": time.time()}
    TB.notify(exc.reason, title)
    if exc.submitted:  # "Post" was pressed: never again by itself; the publish loop looks it up
        PF.record(project, cid, "tiktok", status="processing", checked_at=time.time(), auto_error=err)
        return {"status": "processing"}
    rec = PF.record(project, cid, "tiktok", mode="semi", fallback=err, status="preparing", error=None,
                    remind_at=_rec(project, cid, "tiktok").get("publish_at"), publish_at=None, remote=False)
    return _run_semi(project, cid, "tiktok", file, rec)


def _browser_verify(project: Project, cid: str, rec: dict) -> dict:
    """A post sent through TikTok Studio before: is it planned / live? (never posts again)"""
    from .. import tiktok_browser as TB

    at = P.parse(rec.get("publish_at"))
    if rec.get("remote") and at is not None and at > _now():
        PF.record(project, cid, "tiktok", status="scheduled")
        return {"status": "scheduled"}
    title = _clip_title(project, cid, rec)
    try:
        row = TB.find_posts([title])[0]
    except TB.Blocked as exc:
        _log(project, cid, "check", exc.message)
        PF.record(project, cid, "tiktok", checked_at=time.time())
        return {"status": rec.get("status")}
    tries = int(rec.get("verify_tries") or 0) + 1
    handle = rec.get("handle") or TB.status().get("username")
    if row.get("found") and row.get("scheduled") and (at is None or at > _now() - timedelta(hours=1)):
        PF.record(project, cid, "tiktok", status="scheduled", remote=True, checked_at=time.time(), verify_tries=tries,
                  scheduled_text=row.get("text", "")[:300])
        return {"status": "scheduled"}
    if row.get("found"):
        url = row.get("href") or rec.get("url") or (f"https://www.tiktok.com/@{handle}" if handle else None)
        PF.record(project, cid, "tiktok", status="published", url=url, verify_tries=tries, checked_at=time.time(),
                  posted_at=rec.get("posted_at") or _iso(at or _now()), remote=False, error=None)
        _calendar(project, cid, "tiktok", "published", url)
        return {"status": "published", "url": url}
    if tries < 3:
        PF.record(project, cid, "tiktok", verify_tries=tries, checked_at=time.time(),
                  status="scheduled" if rec.get("remote") else "processing")
        return {"status": "processing"}
    if rec.get("remote"):  # TikTok showed it as planned: it went out (the list didn't show it yet)
        url = rec.get("url") or (f"https://www.tiktok.com/@{handle}" if handle else None)
        PF.record(project, cid, "tiktok", status="published", url=url, unverified=True, verify_tries=tries,
                  posted_at=rec.get("posted_at") or _iso(at or _now()), remote=False)
        _calendar(project, cid, "tiktok", "published", url)
        return {"status": "published", "url": url}
    PF.record(project, cid, "tiktok", status="failed", verify_tries=tries, error={
        "message": "TikTok Studio didn't show this post after \"Post\" was pressed.",
        "hint": "Look in TikTok Studio. If it isn't there, press Retry to post it again.", "kind": "fatal",
        "code": "not_found"})
    return {"status": "failed"}


def _browser_tick(project: Project, cid: str, r: dict, now: datetime) -> str | None:
    """What the publish loop does for a TikTok Studio post (None: nothing now)."""
    from .. import tiktok_browser as TB

    st = r.get("status")
    t = now.timestamp()
    at = P.parse(r.get("publish_at"))
    if st == "scheduled" and r.get("remote"):
        if at is not None and at <= now - timedelta(minutes=5) and t - float(r.get("checked_at") or 0) > 600:
            return "check"
        return None
    if st == "scheduled":
        if at is None or at <= now:
            if at is not None and (now - at).total_seconds() > 600:
                PF.record(project, cid, "tiktok", late=True)
            return "due" if TB.ready() else None
        if r.get("native") is not False and TB.in_window(at, now) and TB.ready():
            return "plan"
        return None
    if st == "processing" and t - float(r.get("checked_at") or 0) > 600:
        return "check"
    if st in ("uploading", "preparing"):
        return "resume"
    if st == "failed" and r.get("next_try_at") and float(r["next_try_at"]) <= t             and int(r.get("attempts") or 0) < MAX_TRIES:
        return "retry"
    return None

# ===================================================================== retry / cancel


def retry(project: Project, cid: str, platform: str) -> dict:
    if platform == "youtube":
        from . import publishing as pub

        return pub.api_retry(project.id, cid)
    rec = _rec(project, cid, platform)
    if rec.get("status") == "published":
        raise SharkyClipsError("This clip is already out there.")
    if active_job(project.id, cid, platform) is not None:
        return {"status": "uploading"}
    if not rec:
        raise SharkyClipsError("Nothing to try again here.", "Press Publish.")
    if rec.get("mode") == "browser":  # your Retry: post again (also after "not found")
        PF.record(project, cid, platform, submitted_at=None, remote=False, verify_tries=0, cleared=True)
    PF.record(project, cid, platform, status="preparing", error=None, next_try_at=None)
    submit(project.id, cid, platform)
    return {"status": "uploading"}


def unplan(project: Project, cid: str, platform: str) -> dict:
    """Take a planned TikTok / Instagram post off the plan (YouTube: the Library's Cancel)."""
    rec = _rec(project, cid, platform)
    if rec.get("status") != "scheduled":
        raise SharkyClipsError("This post isn't planned.")
    if rec.get("remote"):
        raise SharkyClipsError("This post is planned in TikTok Studio.",
                               "Delete it there (TikTok Studio > Posts > Scheduled); SharkyClips sees it at the next check.")
    PF.record(project, cid, platform, status="idle", publish_at=None)
    return clip_states(project, cid)


# ===================================================================== the publish loop's part


def tick(now: datetime | None = None) -> list[str]:
    """Called every minute by the publish loop (inside jobs.automatic()): planned posts whose time
    has come (caught up if the PC was off), posts interrupted by a crash, posts still processing
    on the platform, failures that may be retried, token refresh, views / likes."""
    A = _app()
    now = now or _now()
    acts = PF.keep_fresh()
    t = now.timestamp()
    for project in A.list_projects():
        recs = PF.records(project)
        for cid, plats in recs.items():
            for p in SOCIAL:
                r = (plats or {}).get(p) or {}
                st = r.get("status")
                if not st or r.get("mode") == "semi" or active_job(project.id, cid, p) is not None:
                    continue
                go = None
                if r.get("mode") == "browser":
                    go = _browser_tick(project, cid, r, now)
                    if go in ("due", "plan"):
                        PF.record(project, cid, p, status="preparing" if go == "due" else "scheduled")
                elif st == "scheduled":
                    at = P.parse(r.get("publish_at"))
                    if at is not None and at <= now:
                        late = (now - at).total_seconds() > 600
                        PF.record(project, cid, p, status="preparing", late=late)
                        go = "late" if late else "due"
                elif st in ("uploading", "preparing"):
                    go = "resume"
                elif st == "processing" and t - float(r.get("checked_at") or 0) > 90:
                    go = "check"
                elif st == "failed" and r.get("next_try_at") and float(r["next_try_at"]) <= t \
                        and int(r.get("attempts") or 0) < MAX_TRIES:
                    go = "retry"
                if go:
                    try:
                        job = submit(project.id, cid, p)
                        if job.status == "cancelled":  # the user cancelled it: final
                            PF.record(project, cid, p, status="cancelled")
                            continue
                        acts.append(f"{go}:{p}:{project.id}:{cid}")
                    except Exception:  # noqa: BLE001 - a gone project / clip
                        continue
    try:  # 1.2.41: posts planned in the browser (Claude in Chrome) turn "published" when due
        from . import pubqueue_api

        if pubqueue_api.link_soon():
            acts.append("chrome:linked")
        from .. import trash

        if trash.purge_soon():  # 1.2.41: trash items older than 30 days
            acts.append("trash:purged")
    except Exception:  # noqa: BLE001
        pass
    if time.time() - _stats_at["t"] > STATS_EVERY_S:
        _stats_at["t"] = time.time()
        if PF.connected("tiktok") or PF.connected("reels"):
            submit_stats()
            acts.append("stats:social")
    return acts


# ===================================================================== views / likes


def submit_stats() -> Job:
    A = _app()

    def run(job: Job):
        return sync_stats()

    return A.jobs.submit("social_stats", "net", None, {"platform": "stats"}, run, key="social_stats")


def sync_stats() -> dict:
    """Views / likes from TikTok (video.list: public posts) and Instagram (insights) -> the
    records, the Library, and calibration (the views a clip got everywhere it went out)."""
    from .. import calibration

    A = _app()
    got = {"tiktok": 0, "reels": 0}
    tt_videos = None
    for project in A.list_projects():
        recs = PF.records(project)
        for cid, plats in recs.items():
            changed = False
            for p in SOCIAL:
                r = (plats or {}).get(p) or {}
                if r.get("status") != "published":
                    continue
                try:
                    if p == "reels" and r.get("media_id") and PF.connected("reels"):
                        s = PF.ig_stats(r["media_id"])
                        PF.record(project, cid, p, views=s.get("views"), likes=s.get("likes"), stats_at=time.time(),
                                  url=r.get("url") or s.get("url"))
                        got[p] += 1
                        changed = True
                    elif p == "tiktok" and PF.connected("tiktok"):
                        if tt_videos is None:
                            tt_videos = PF.tiktok_video_stats(time.time() - 120 * 86400)
                        v = _match_tiktok(r, tt_videos)
                        if v:
                            PF.record(project, cid, p, views=int(v.get("view_count") or 0),
                                      likes=int(v.get("like_count") or 0), stats_at=time.time(),
                                      post_id=str(v.get("id")), url=v.get("share_url") or r.get("url"),
                                      privacy="public_to_everyone")
                            got[p] += 1
                            changed = True
                except SharkyClipsError:
                    continue
            if changed:
                try:
                    _calibrate(project, cid, calibration)
                except Exception:  # noqa: BLE001
                    pass
    return got


def _match_tiktok(rec: dict, videos: list[dict]) -> dict | None:
    if rec.get("post_id"):
        return next((v for v in videos if str(v.get("id")) == str(rec["post_id"])), None)
    since = float(rec.get("init_at") or 0) - 600
    want = _norm(rec.get("caption") or "")[:40]
    for v in videos:
        if int(v.get("create_time") or 0) >= since and want and _norm(v.get("title") or "")[:40] == want:
            return v
    return None


def _calibrate(project: Project, cid: str, calibration) -> None:
    """Calibration learns from the views a clip got everywhere (YouTube + TikTok + Instagram),
    once the oldest post is 48 h old."""
    A = _app()
    cand = A._cand(project, cid)
    sts = clip_states(project, cid)
    total = sum(int(sts[p]["views"]) for p in PLATFORMS if isinstance(sts[p].get("views"), int))
    first = min((P.parse(sts[p].get("posted_at")) for p in PLATFORMS if sts[p].get("posted_at")
                 and P.parse(sts[p].get("posted_at"))), default=None)
    if first is None or _now() - first < timedelta(hours=48) or total <= 0:
        return
    likes = sum(int(sts[p]["likes"]) for p in PLATFORMS if isinstance(sts[p].get("likes"), int))
    yt = sts["youtube"]
    calibration.set_entry(project, cand, total, likes, _iso(first), video_id=None)
    data = calibration.load()
    e = data["entries"].get(calibration.entry_key(project.id, cid))
    if e is not None:
        e["platforms"] = {p: {"views": sts[p].get("views"), "likes": sts[p].get("likes")} for p in PLATFORMS}
        e["source"] = "platforms" if not yt.get("views") else "youtube+"
        calibration._save(data)


# ===================================================================== library extras


def library_extras(rows: list[dict]) -> None:
    """Adds per-platform badges to the Library rows (in place)."""
    A = _app()
    cache: dict[str, Project] = {}
    for r in rows:
        try:
            project = cache.get(r["project_id"]) or A.get_project(r["project_id"])
            cache[r["project_id"]] = project
            r["platforms"] = clip_states(project, r["clip_id"])
        except Exception:  # noqa: BLE001
            r["platforms"] = None


# ===================================================================== routes


def _project(pid: str) -> Project:
    return _app().get_project(pid)


@router.get("/api/publish/targets")
def api_targets() -> dict:
    return {"targets": targets()}


@router.put("/api/publish/targets")
def api_targets_put(body: dict) -> dict:
    return {"targets": set_targets(list(body.get("targets") or []))}


@router.get("/api/publish/{project_id}/{cid}")
def api_view(project_id: str, cid: str, platforms: str | None = None) -> dict:
    want = [p for p in platforms.split(",") if p] if platforms is not None else None
    return view(_project(project_id), cid, want, fresh=True)  # opening the post screen: new creator_info


@router.put("/api/publish/{project_id}/{cid}")
def api_save(project_id: str, cid: str, body: dict, platforms: str | None = None) -> dict:
    project = _project(project_id)
    dr = body.get("drafts") if isinstance(body.get("drafts"), dict) else None
    if dr and dr.get("reset"):
        with _slock:
            all_ = _store(project)
            (all_.get(cid) or {}).pop("drafts", None)
            write_json_atomic(_store_path(project), all_)
        dr = None
    save_clip_store(project, cid, drafts=dr, tiktok=body.get("tiktok") if isinstance(body.get("tiktok"), dict) else None)
    want = [p for p in platforms.split(",") if p] if platforms is not None else None
    return view(project, cid, want)


@router.post("/api/publish/{project_id}/{cid}/fix")
def api_fix(project_id: str, cid: str, body: dict) -> dict:
    return apply_fix(_project(project_id), cid, str(body.get("platform") or ""), str(body.get("code") or ""))


@router.post("/api/publish/{project_id}/{cid}")
def api_start(project_id: str, cid: str, body: dict | None = Body(default=None)) -> dict:
    return start(_project(project_id), cid, body or {})


@router.post("/api/publish/{project_id}/{cid}/retry/{platform}")
def api_retry(project_id: str, cid: str, platform: str) -> dict:
    if platform not in PLATFORMS:
        raise SharkyClipsError("Unknown platform.")
    project = _project(project_id)
    retry(project, cid, platform)
    return view(project, cid)


@router.get("/api/publish/{project_id}/{cid}/handoff")
def api_handoff(project_id: str, cid: str, platforms: str | None = None) -> dict:
    want = [p for p in platforms.split(",") if p] if platforms else None
    return handoff(_project(project_id), cid, want)


@router.post("/api/publish/{project_id}/{cid}/shared/{platform}")
def api_shared(project_id: str, cid: str, platform: str, body: dict | None = Body(default=None)) -> dict:
    project = _project(project_id)
    shared(project, cid, platform, str((body or {}).get("url") or "") or None)
    return handoff(project, cid)


@router.post("/api/publish/{project_id}/{cid}/unplan/{platform}")
def api_unplan(project_id: str, cid: str, platform: str) -> dict:
    if platform not in SOCIAL:
        raise SharkyClipsError("Use the Library's Cancel for YouTube.")
    project = _project(project_id)
    unplan(project, cid, platform)
    return view(project, cid)


@router.get("/api/accounts")
def api_accounts(fresh: bool = False) -> dict:
    out = accounts()
    out["quota"] = quotas(fetch=fresh or True)
    return out


@router.get("/api/accounts/{platform}/avatar")
def api_avatar(platform: str):
    if platform == "youtube":
        from .. import youtube

        url = next((c.get("thumbnail") for c in (youtube.status().get("channels") or []) if c.get("thumbnail")), None)
        p = PF.avatar_path("youtube")
        if url and not p.is_file():
            PF.save_avatar("youtube", url)
    elif platform not in SOCIAL:
        raise SharkyClipsError("Unknown platform.")
    p = PF.avatar_path(platform)
    if not p.is_file():
        raise SharkyClipsError("No picture yet.")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.post("/api/accounts/{platform}/check")
def api_account_check(platform: str) -> dict:
    """Reconnect test: refresh the token now and read the profile again."""
    if platform == "tiktok" and PF.connected("tiktok"):
        PF.refresh_tiktok()
        PF.tiktok_creator_info(fresh=True)
    elif platform == "reels" and PF.connected("reels"):
        PF.refresh_ig()
    return accounts()


@router.delete("/api/accounts/{platform}")
def api_account_disconnect(platform: str) -> dict:
    if platform not in SOCIAL:
        raise SharkyClipsError("Disconnect YouTube in its own card.")
    PF.forget(platform, everything=False)
    PF.note_problem(platform, None)
    return accounts()


@router.post("/api/platforms/reels/oauth")
def api_ig_oauth(body: dict, request: Request) -> dict:
    if not _app()._is_local(request):
        raise SharkyClipsError("Connect Instagram on the computer running SharkyClips.")
    port = request.url.port or 8000
    url = PF.ig_start(str(body.get("app_id") or ""), str(body.get("app_secret") or ""), port,
                      str(body.get("redirect") or "") or None)
    return {"url": url, "redirect_uri": (PF.load_app("reels") or {}).get("redirect")}


@router.post("/api/platforms/reels/oauth/finish")
def api_ig_oauth_finish(body: dict) -> dict:
    PF.ig_finish(str(body.get("code") or body.get("url") or ""), body.get("state"))
    return accounts()


@router.get("/api/platforms/reels/redirect")
def api_ig_redirect(request: Request) -> dict:
    return {"redirect_uri": (PF.load_app("reels") or {}).get("redirect") or PF.ig_redirect(request.url.port or 8000)}


@router.get("/api/platforms/reels/callback", response_class=HTMLResponse)
def api_ig_callback(code: str = "", state: str = "", error: str = "", error_description: str = "") -> HTMLResponse:
    """Only reached when the redirect address is plain http (Meta usually wants https)."""
    import html

    if error or not code:
        msg, ok = (error_description or error or "Instagram didn't connect."), False
    else:
        try:
            PF.ig_finish(code, state)
            msg, ok = "Instagram is connected. You can close this tab.", True
        except SharkyClipsError as exc:
            msg, ok = f"{exc.message} {exc.hint or ''}", False
    color = "#2e9e6a" if ok else "#c0392b"
    return HTMLResponse(f"<!doctype html><meta charset='utf-8'><title>SharkyClips</title>"
                        f"<body style='font-family:system-ui;background:#0e1a33;color:#fff;display:grid;place-items:center;height:100vh;margin:0'>"
                        f"<div style='max-width:460px;text-align:center'><h1 style='color:{color}'>{'✓' if ok else '!'}</h1>"
                        f"<p>{html.escape(msg)}</p><p><a style='color:#d9b56a' href='/#/settings'>SharkyClips</a></p></div>")


# ===================================================================== 1.2.42: TikTok Studio login


def _tb():
    from .. import tiktok_browser

    return tiktok_browser


def _after_login(d: dict) -> None:
    """The first TikTok Studio login turns automatic TikTok on (unless you chose by hand before)
    and checks the publish calendar's overdue TikTok posts."""
    modes = dict(config.get("platform_modes") or {})
    if "tiktok" not in modes:
        modes["tiktok"] = "browser"
        config.update(platform_modes=modes)
    try:
        from . import pubqueue_api

        pubqueue_api.submit_reconcile()
    except Exception:  # noqa: BLE001
        pass


def _local_only(request: Request) -> None:
    if not _app()._is_local(request):
        raise SharkyClipsError("Only the computer running SharkyClips can open the TikTok window.")


@router.get("/api/accounts/tiktok/browser")
def api_tb_status() -> dict:
    return _tb().status()


@router.post("/api/accounts/tiktok/browser/login")
def api_tb_login(request: Request) -> dict:
    _local_only(request)
    _tb().on_login(_after_login)
    return _tb().login_start()


@router.post("/api/accounts/tiktok/browser/login/cancel")
def api_tb_login_cancel() -> dict:
    return _tb().login_cancel()


@router.post("/api/accounts/tiktok/browser/check")
def api_tb_check() -> dict:
    TB = _tb()
    if TB.status()["busy"]:
        return TB.status()  # a post (or the login window) has the browser now
    if not TB.status()["login_at"] and not TB.status()["profile"]:  # profile: a login window closed after a restart
        raise SharkyClipsError("Log in to TikTok first.")
    TB.clear_block()
    return TB.check()


@router.post("/api/accounts/tiktok/browser/logout")
def api_tb_logout() -> dict:
    modes = dict(config.get("platform_modes") or {})
    if modes.get("tiktok") == "browser":
        modes["tiktok"] = "semi"
        config.update(platform_modes=modes)
    return _tb().logout()


@router.put("/api/accounts/tiktok/browser/settings")
def api_tb_settings(body: dict) -> dict:
    TB = _tb()
    if body.get("daily_cap") is not None:
        TB.set_daily_cap(int(body["daily_cap"]))
    if body.get("auto") is not None:
        PF.set_mode("tiktok", "browser" if body["auto"] else "semi")
    return TB.status()
