"""The full video on YouTube (1.2.51): an imported video goes up whole, next to its clips.

Which way: the YouTube Data API (the existing resumable uploader, youtube.upload), not a
YouTube Studio browser robot. SharkyClips' Google project uploads public videos (an upload
went public, lock_state "unlocked"), and scheduling is part of the API (status.publishAt).
Should Google ever keep this project's uploads private (lock_state "locked"), the video still
goes up private and the creator gets a "schedule / make it public in YouTube Studio" note
with the Studio link: nothing is published behind their back, nothing breaks.

Flow (all in <project>/full_upload.json):
  wanted     the import asked for it ("Upload the full video to YouTube", on by default)
  preparing  after the AI analysis: title / description (story, chapters from the clips and
             the transcript, the channel's fixed parts), tags + the always-hashtags, category
             (Gaming for games), "not made for kids", a 16:9 thumbnail, the release time
  review     the confirm screen: everything editable, nothing goes out before "Upload"
  uploading  resumable upload (continues where it stopped after a cut / restart), one retry
  scheduled  on YouTube as private + publishAt (ALWAYS a future time, never at once)
  published  publishAt passed: the clips of this project get "Tam video: <link>"
  skipped / failed
Limits: one full video per day (all projects), at most one automatic retry.
Shorts -> related video: the Data API has no field for it (Studio only), so the link goes into
the Shorts' descriptions instead.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, languages
from .errors import SharkyClipsError
from .project import Project, read_json, write_json_atomic

FILE = "full_upload.json"
REGISTRY = "full_uploads.json"   # <settings>/youtube/: every full upload (daily limit, free evenings)
DAILY_LIMIT = 1
DEFAULT_TIME = "20:00"
MIN_LEAD = timedelta(hours=1)    # a release time is at least an hour ahead (upload + processing)
MAX_CHAPTERS = 12
MIN_CHAPTER_GAP = 30.0           # YouTube: chapters at least 10 s; ours at least 30 s apart
STUDIO_URL = "https://studio.youtube.com/video/{id}/edit"
STATES = ("wanted", "preparing", "review", "uploading", "scheduled", "published", "skipped", "failed")
CATEGORY = {"gaming": "20", "study": "27", "music": "10"}
_lock = threading.RLock()


# ------------------------------------------------------------------ settings + storage


def enabled_by_default() -> bool:
    return config.get("full_upload_default") is not False


def release_time() -> str:
    t = str(config.get("full_upload_time") or DEFAULT_TIME)
    return t if re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t) else DEFAULT_TIME


def tz() -> ZoneInfo | timezone:
    name = str((config.get("pubqueue") or {}).get("timezone") or "")
    try:
        return ZoneInfo(name) if name else datetime.now().astimezone().tzinfo  # type: ignore[return-value]
    except Exception:  # noqa: BLE001 - unknown zone name: the computer's own time
        return datetime.now().astimezone().tzinfo  # type: ignore[return-value]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=tz())  # type: ignore[arg-type]


def load(project: Project) -> dict | None:
    p = project.dir / FILE
    try:
        return read_json(p) if p.is_file() else None
    except Exception:  # noqa: BLE001
        return None


def save(project: Project, data: dict) -> dict:
    with _lock:
        data = {**data, "updated_at": _iso(_now())}
        write_json_atomic(project.dir / FILE, data)
        return data


def patch(project: Project, **changes) -> dict:
    with _lock:
        return save(project, {**(load(project) or {}), **changes})


def _registry_path() -> Path:
    from . import youtube

    return youtube.folder() / REGISTRY


def registry() -> list[dict]:
    p = _registry_path()
    try:
        d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        d = {}
    return [x for x in d.get("items") or [] if isinstance(x, dict)]


def _register(item: dict) -> None:
    with _lock:
        items = [x for x in registry() if x.get("project_id") != item.get("project_id")] + [item]
        p = _registry_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"items": items[-200:]}, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)


# ------------------------------------------------------------------ request (import) + rules


def request(project: Project, want: bool | None = None) -> dict | None:
    """The import asked for the full video (want None = the setting's default)."""
    want = enabled_by_default() if want is None else bool(want)
    cur = load(project)
    if cur and cur.get("status") not in (None, "skipped"):
        return cur
    if not want:
        return save(project, {"status": "skipped", "why": "off_at_import"}) if cur is None else cur
    return save(project, {"status": "wanted", "requested_at": _iso(_now())})


def uploaded_today(now: datetime | None = None) -> list[dict]:
    """Full uploads started today (the creator's local day)."""
    now = (now or _now()).astimezone(tz())  # type: ignore[arg-type]
    out = []
    for x in registry():
        t = _parse(x.get("uploaded_at"))
        if t and t.astimezone(tz()).date() == now.date():  # type: ignore[arg-type]
            out.append(x)
    return out


def check_daily_limit(project_id: str, now: datetime | None = None) -> None:
    others = [x for x in uploaded_today(now) if x.get("project_id") != project_id]
    if len(others) >= DAILY_LIMIT:
        raise SharkyClipsError("Only one full video a day goes to YouTube: today's is already up.",
                               "Upload this one tomorrow (it stays ready here).")


def next_free_evening(now: datetime | None = None, at: str | None = None, skip_project: str | None = None) -> datetime:
    """The next evening (default 20:00, Settings) at least an hour ahead without another full
    video on that day."""
    zone = tz()
    now = (now or _now()).astimezone(zone)  # type: ignore[arg-type]
    hh, mm = (int(x) for x in (at or release_time()).split(":"))
    taken: set[date] = set()
    for x in registry():
        if x.get("project_id") == skip_project:
            continue
        t = _parse(x.get("publish_at"))
        if t:
            taken.add(t.astimezone(zone).date())  # type: ignore[arg-type]
    day = now.date()
    for _ in range(60):
        cand = datetime.combine(day, dtime(hh, mm), tzinfo=zone)  # type: ignore[arg-type]
        if cand - now >= MIN_LEAD and day not in taken:
            return cand.astimezone(timezone.utc)
        day += timedelta(days=1)
    return (now + timedelta(days=1)).astimezone(timezone.utc)


def check_time(publish_at: str | None, now: datetime | None = None) -> str:
    """Always a FUTURE release (never at once): at least an hour ahead."""
    t = _parse(publish_at)
    if t is None:
        raise SharkyClipsError("Pick the release date and time.", "A full video is always scheduled.")
    if t - (now or _now()) < MIN_LEAD:
        raise SharkyClipsError("The release time must be at least an hour ahead.",
                               "A full video is always scheduled, never published at once.")
    return _iso(t)


# ------------------------------------------------------------------ chapters


def fmt_ts(sec: float) -> str:
    s = int(max(0, sec))
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _short_label(text: str, n: int = 48) -> str:
    from .titles import lexicon

    t = lexicon.strip_emoji(re.sub(r"#\S+", "", text or "")).strip()
    t = re.sub(r"\s*\([^()]*\)\s*$", "", t).strip(" !?.…,-")
    t = re.sub(r"^[\"“'](.+?)[\"”']\s*", r"\1 ", t).strip().strip(" !?.…,-")
    if len(t) > n:
        t = t[:n].rsplit(" ", 1)[0].rstrip(" ,") + "…"
    return t


def chapters(project: Project, labels: dict[str, str] | None = None, duration: float | None = None,
             intro: str = "Giriş") -> list[dict]:
    """[{t, label}] from the analyzed clips (their moments, in order), else evenly from the
    transcript. Always starts at 00:00; at least 3 entries, or none (YouTube's rule)."""
    from .textutil import sentences
    from .web import state

    hl = state.load_highlights(project) or {}
    cands = sorted([c for c in hl.get("candidates") or [] if c.get("start") is not None],
                   key=lambda c: c.get("rank") or 999)[:MAX_CHAPTERS]
    duration = duration or float(project.load_meta().get("duration") or 0)
    out = [{"t": 0.0, "label": intro}]
    for c in sorted(cands, key=lambda c: c["start"]):
        t = max(0.0, float(c["start"]) - 3)
        if t - out[-1]["t"] < MIN_CHAPTER_GAP or (duration and duration - t < 15):
            continue
        pub = c.get("publish") or {}
        label = (labels or {}).get(c["id"]) or (pub.get("titles") or [""])[0] or pub.get("hook_text") or ""
        label = _short_label(label)
        if label:
            out.append({"t": round(t), "label": label, "clip": c["id"]})
    if len(out) < 3 and project.transcript_path.is_file() and duration > 180:
        tr = project.load_transcript()
        out = [{"t": 0.0, "label": intro}]
        step = max(120.0, duration / 6)
        t = step
        while t < duration - 60 and len(out) < 7:
            lines = sentences(tr, t, t + 40)
            if lines:
                out.append({"t": round(lines[0]["start"]), "label": _short_label(lines[0]["text"], 40)})
            t += step
    return out if len(out) >= 3 else []


def chapters_text(items: list[dict], lang: str = "tr") -> str:
    if not items:
        return ""
    head = "⏱️ Bölümler:" if lang == "tr" else "⏱️ Chapters:"
    return head + "\n" + "\n".join(f"{fmt_ts(x['t'])} {x['label']}" for x in items)


# ------------------------------------------------------------------ the draft


def _mode(project: Project) -> str:
    return project.load_meta().get("mode") or "gaming"


def _kind(project: Project) -> str:
    m = _mode(project)
    return m if m in CATEGORY else "gaming"


def compose_description(body: str, chap: str, hashtags: list[str], lang: str) -> str:
    """The channel's long-video layout: story + CTA, chapters, socials block, hashtags."""
    from .edit import brand
    from .titles import style

    text = "\n\n".join(x for x in (body.strip(), chap.strip()) if x)
    text = style.compose(text, hashtags) if hashtags else text
    return brand.with_socials(text, lang, limit=4800, short=False)


def prepare(project: Project, on_stage=None, force: bool = False) -> dict:
    """Write the draft (LLM: the channel's long-video style) and open the confirm screen."""
    from . import channelstyle, longmeta

    cur = load(project) or {}
    if cur.get("status") in ("uploading", "scheduled", "published") and not force:
        return cur
    patch(project, status="preparing", error=None)
    try:
        lang = languages.content_language(None, project)
        meta = longmeta.write(project, kind="full", lang=lang, force=force, on_stage=on_stage)
        lang = meta.get("language") or lang
        chap = chapters(project, intro="Giriş" if lang == "tr" else "Intro")
        hashtags = channelstyle.ensure_hashtags(list(meta.get("hashtags") or []), 15)
        body = meta.get("body") or ""
        description = compose_description(body, chapters_text(chap, lang), hashtags, lang)
        tags = list(meta.get("tags") or [])
        for h in channelstyle.edits()["always_hashtags"]:
            w = h.lstrip("#")
            if w.casefold() not in {t.casefold() for t in tags}:
                tags.append(w)
        thumb = _thumbnail(project, meta)
        kind = _kind(project)
        draft = {"title": (meta.get("titles") or [project.load_meta().get("title") or ""])[0][:100],
                 "titles": meta.get("titles") or [], "description": description, "body": body,
                 "chapters": chap, "hashtags": hashtags, "tags": tags[:30],
                 "category": CATEGORY.get(kind, "20"), "made_for_kids": False, "language": lang,
                 "privacy": "public", "publish_at": _iso(next_free_evening(skip_project=project.id)),
                 "thumbnail": thumb.get("file"), "cover_text": thumb.get("text"), "style": meta.get("profile")}
        return patch(project, status="review", draft=draft, prepared_at=_iso(_now()), error=None)
    except SharkyClipsError as exc:
        patch(project, status="failed", error={"message": exc.message, "hint": exc.hint, "at": _iso(_now()),
                                               "step": "prepare"})
        raise


def _thumbnail(project: Project, meta: dict) -> dict:
    """A 16:9 thumbnail suggestion: the best moment's frame with a short cover text."""
    from . import cover
    from .web import state

    hl = state.load_highlights(project) or {}
    cands = sorted([c for c in hl.get("candidates") or [] if (c.get("publish") or {}).get("available")],
                   key=lambda c: c.get("rank") or 999) or sorted(hl.get("candidates") or [],
                                                                  key=lambda c: c.get("rank") or 999)
    if not cands:
        return {}
    top = cands[0]
    text = ((top.get("publish") or {}).get("cover_text") or "").strip()
    if not text:
        text = " ".join(_short_label((meta.get("titles") or [""])[0], 30).split()[:4])
    try:
        path = cover.make_cover(project, top, None, "peak", text.upper() if text else "", frame="wide",
                                lang=meta.get("language"))
    except Exception:  # noqa: BLE001 - a thumbnail is a suggestion; the upload works without
        return {"text": text}
    return {"file": str(path), "text": text, "clip": top["id"]}


def clean_draft(old: dict, new: dict) -> dict:
    """What the confirm screen may change."""
    from . import youtube

    d = dict(old or {})
    if "title" in new:
        d["title"] = youtube.clean_text(str(new.get("title") or ""), 100)
    if "description" in new:
        d["description"] = str(new.get("description") or "")[:4900]
    if "tags" in new:
        tags = new.get("tags") or []
        if isinstance(tags, str):
            tags = tags.split(",")
        d["tags"] = [" ".join(str(t).split())[:80] for t in tags if str(t).strip()][:30]
    if "publish_at" in new:
        d["publish_at"] = check_time(new.get("publish_at"))
    if "category" in new and str(new.get("category")) in youtube.CATEGORIES:
        d["category"] = str(new["category"])
    if "use_thumbnail" in new:
        d["use_thumbnail"] = bool(new["use_thumbnail"])
    if not d.get("title"):
        raise SharkyClipsError("The video needs a title.")
    return d


def body_for_upload(draft: dict) -> dict:
    """The Data API body: private + publishAt (YouTube releases it at that time)."""
    from . import youtube

    when = check_time(draft.get("publish_at"))
    return youtube.build_body(draft["title"], draft.get("description") or "", draft.get("tags") or [], "public",
                              when, False, str(draft.get("category") or "20"), draft.get("language") or None)


def source_file(project: Project) -> Path:
    src = project.source_path
    if src is None or not Path(src).is_file():
        raise SharkyClipsError("The original video of this project is missing.",
                               "The full video can only go up while the original file is here.")
    if Path(src).suffix.lower() in (".mp3", ".m4a", ".wav"):
        raise SharkyClipsError("This project is audio only: there is no full video to upload.")
    return Path(src)


def after_upload(project: Project, video: dict, body: dict, draft: dict) -> dict:
    """Bookkeeping after the upload: the registry, the private-lock check, the clip links."""
    from . import youtube

    vid = video["id"]
    st = video.get("status") or {}
    locked = youtube.lock_state()["state"] == "locked" or (
        st.get("privacyStatus") == "private" and body["status"].get("publishAt") and not st.get("publishAt"))
    entry = {"video_id": vid, "url": f"https://youtu.be/{vid}", "studio_url": STUDIO_URL.format(id=vid),
             "title": body["snippet"]["title"], "publish_at": body["status"].get("publishAt"),
             "uploaded_at": _iso(_now()), "locked": bool(locked)}
    _register({"project_id": project.id, **entry})
    return patch(project, status="scheduled", upload=entry, error=None, retries=draft.get("retries", 0))


def link_line(url: str, lang: str | None) -> str:
    return f"Tam video: {url}" if (lang or "en") == "tr" else f"Full video: {url}"


def full_video_url(project: Project) -> str | None:
    d = load(project) or {}
    up = d.get("upload") or {}
    return up.get("url") if up.get("video_id") else None


def with_link(description: str, project: Project, lang: str | None) -> str:
    """A Short of this project: "Tam video: <link>" at the top (once)."""
    url = full_video_url(project)
    if not url or url in (description or ""):
        return description
    return f"{link_line(url, lang)}\n\n{description}".strip()


def link_clips(project: Project) -> dict:
    """The full video is out: add "Tam video: <link>" to this project's Shorts already on
    YouTube (each once; 50 quota units per video)."""
    from . import youtube
    from .web import state

    d = load(project) or {}
    up = d.get("upload") or {}
    if not up.get("video_id"):
        return {"linked": 0}
    done = set(d.get("linked") or [])
    lang = (d.get("draft") or {}).get("language")
    n, errors = 0, []
    for ups in state.load_uploads(project).values():
        for u in ups:
            vid = u.get("video_id")
            if not vid or vid in done or u.get("missing") or vid == up["video_id"]:
                continue
            try:
                cur = youtube._get("videos", {"part": "snippet", "id": vid}).get("items") or []
                if not cur:
                    done.add(vid)
                    continue
                sn = cur[0]["snippet"]
                desc = sn.get("description") or ""
                if up["url"] not in desc:
                    youtube.update_video(vid, snippet={"title": sn.get("title"), "categoryId": sn.get("categoryId"),
                                                       "description": youtube.clean_text(
                                                           f"{link_line(up['url'], lang)}\n\n{desc}", 4900),
                                                       "tags": sn.get("tags") or []})
                    n += 1
                done.add(vid)
            except SharkyClipsError as exc:
                errors.append({"video_id": vid, "message": exc.message})
                if getattr(exc, "reason", None) in ("quotaExceeded", "signed_out"):
                    break
    patch(project, linked=sorted(done), linked_at=_iso(_now()), link_errors=errors[:5])
    return {"linked": n, "errors": errors}


def published_due(project: Project, now: datetime | None = None) -> bool:
    d = load(project) or {}
    if d.get("status") != "scheduled":
        return False
    t = _parse((d.get("upload") or {}).get("publish_at"))
    return t is not None and t + timedelta(minutes=5) <= (now or _now())


def view(project: Project) -> dict:
    from . import youtube

    d = load(project) or {"status": None}
    up = d.get("upload") or {}
    lock = youtube.lock_state()["state"] if youtube.connected() else None
    return {**d, "connected": youtube.connected(), "lock": lock,
            "next_free": _iso(next_free_evening(skip_project=project.id)), "release_time": release_time(),
            "today": len([x for x in uploaded_today() if x.get("project_id") != project.id]),
            "daily_limit": DAILY_LIMIT, "studio_url": up.get("studio_url"),
            "needs_studio": bool(up.get("locked"))}
