"""Per-project UI state on disk, next to the pipeline's own files:

  review.json  what the user decided: accepted clips, hook texts, render options, facecam
  clips.json   finished 9:16 clips (clips/<rank>_<id>.mp4)
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ..clips import ClipOptions, Facecam
from ..project import Project, read_json, write_json_atomic

_lock = threading.RLock()

DEFAULT_OPTIONS = ClipOptions().to_dict()
DEFAULT_OPTIONS.pop("hook_text")

# Phase 3 fills these (viral score, titles, hashtags, cover prompt) per candidate.
EMPTY_PUBLISH = {"available": False, "viral_score": None, "viral_label": None, "sub_scores": None,
                 "titles": [], "hashtags": [], "cover_prompt": None, "hook_text": None,
                 "description": None, "language": None}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def viral_label(score: float | None) -> str | None:
    if score is None:
        return None
    from ..analyze import viral_label as label

    return label(int(score))


def load_highlights(project: Project) -> dict | None:
    path = project.dir / "highlights.json"
    return read_json(path) if path.is_file() else None


# ------------------------------------------------------------------ review


def load_review(project: Project, highlights: dict | None = None) -> dict:
    with _lock:
        path = project.dir / "review.json"
        data = read_json(path) if path.is_file() else {}
        hl = highlights if highlights is not None else load_highlights(project)
        hl_stamp = (hl or {}).get("created_at")
        review = {
            "highlights_created_at": data.get("highlights_created_at"),
            "accepted": list(data.get("accepted") or []),
            "hooks": dict(data.get("hooks") or {}),
            "options": {**DEFAULT_OPTIONS, **(data.get("options") or {})},
            "facecam": data.get("facecam"),
            "facecam_checked": bool(data.get("facecam_checked")),
        }
        # Candidates were recomputed: old accept/hook choices point at other moments.
        if hl_stamp and review["highlights_created_at"] != hl_stamp:
            if review["highlights_created_at"] is not None:
                review["accepted"], review["hooks"] = [], {}
            review["highlights_created_at"] = hl_stamp
        return review


def save_review(project: Project, changes: dict[str, Any]) -> dict:
    with _lock:
        review = load_review(project)
        if "accepted" in changes:
            review["accepted"] = [str(c) for c in changes["accepted"]][:500]
        if "hooks" in changes:
            review["hooks"] = {str(k): str(v)[:120] for k, v in (changes["hooks"] or {}).items()
                               if str(v).strip()}
        if "options" in changes:
            opts = ClipOptions.from_dict({**review["options"], **(changes["options"] or {})}).to_dict()
            opts.pop("hook_text", None)
            review["options"] = opts
        if "facecam" in changes:
            fc = Facecam.from_dict(changes["facecam"])
            review["facecam"] = fc.to_dict() if fc else None
            review["facecam_checked"] = True
        write_json_atomic(project.dir / "review.json", review)
        return review


# ------------------------------------------------------------------- clips


def load_clips(project: Project) -> dict[str, dict]:
    path = project.dir / "clips.json"
    clips = (read_json(path).get("clips") or {}) if path.is_file() else {}
    # Drop entries whose file was deleted by hand.
    return {cid: c for cid, c in clips.items() if (project.dir / "clips" / c["file"]).is_file()}


def save_clip(project: Project, cid: str, entry: dict) -> None:
    with _lock:
        clips = load_clips(project)
        old = clips.get(cid)
        if old and old["file"] != entry["file"]:
            (project.dir / "clips" / old["file"]).unlink(missing_ok=True)
        clips[cid] = entry
        write_json_atomic(project.dir / "clips.json", {"version": 1, "clips": clips})


# ----------------------------------------------------------------- uploads


def load_uploads(project: Project) -> dict[str, list[dict]]:
    """YouTube uploads per clip id (uploads.json): video id, privacy, latest numbers."""
    path = project.dir / "uploads.json"
    try:
        return (read_json(path).get("uploads") or {}) if path.is_file() else {}
    except Exception:  # noqa: BLE001
        return {}


def save_upload(project: Project, cid: str, entry: dict) -> None:
    with _lock:
        ups = load_uploads(project)
        lst = [u for u in ups.get(cid, []) if u.get("video_id") != entry.get("video_id")]
        lst.append(entry)
        ups[cid] = lst
        write_json_atomic(project.dir / "uploads.json", {"version": 1, "uploads": ups})


def update_upload_stats(project: Project, stats: dict[str, dict]) -> int:
    """Store fetched views/likes on the matching uploads. Returns how many changed."""
    with _lock:
        ups = load_uploads(project)
        n = 0
        for lst in ups.values():
            for u in lst:
                s = stats.get(u.get("video_id"))
                if s:
                    u.update({"views": s["views"], "likes": s["likes"], "privacy": s["privacy"] or u.get("privacy"),
                              "published_at": s.get("published_at") or u.get("published_at"),
                              "stats_at": now_iso()})
                    n += 1
        if n:
            write_json_atomic(project.dir / "uploads.json", {"version": 1, "uploads": ups})
        return n


# -------------------------------------------------------------------- chat

_chat_cache: dict[str, tuple[float, dict]] = {}


def _chat_index(project: Project) -> dict | None:
    """Message times (sorted) + texts, cached until chat.json changes."""
    from ..chat import chat_path

    path = chat_path(project)
    if not path.is_file():
        return None
    mtime = path.stat().st_mtime
    hit = _chat_cache.get(str(path))
    if hit and hit[0] == mtime:
        return hit[1]
    data = read_json(path)
    if data.get("status") != "ok" or not data.get("messages"):
        idx = None
    else:
        msgs = data["messages"]
        idx = {"times": [m[0] for m in msgs], "texts": [m[1] for m in msgs], "authors": [m[2] for m in msgs],
               "count": len(msgs)}
    _chat_cache[str(path)] = (mtime, idx)
    return idx


def chat_stats(project: Project, candidates: list[dict]) -> dict[str, dict]:
    """Per clip: chat messages in the clip (shifted by chat_delay), per minute, compared with
    the video's average, plus the chat_spike / chat_reactions reasons."""
    import bisect

    from .. import config

    idx = _chat_index(project)
    if not idx or not candidates:
        return {}
    delay = float(config.get("chat_delay") or 5)
    times = idx["times"]
    duration = max(float(project.load_meta().get("duration") or 0), times[-1], 1.0)
    avg = idx["count"] / (duration / 60)
    out = {}
    for c in candidates:
        a = bisect.bisect_left(times, c["start"] + delay)
        b = bisect.bisect_right(times, c["end"] + delay)
        n = b - a
        per_min = n / max(c["end"] - c["start"], 1) * 60
        spikes = [{"t": r["t"], "value": r.get("value"), "strength": r.get("strength")}
                  for r in c.get("reasons", []) if r.get("code") == "chat_spike"]
        reactions = []
        for r in c.get("reasons", []):
            if r.get("code") == "chat_reactions" and r.get("value") and r["value"] not in reactions:
                reactions.append(r["value"])
        out[c["id"]] = {"messages": n, "authors": len(set(idx["authors"][a:b])), "per_minute": round(per_min, 1),
                        "average_per_minute": round(avg, 1), "ratio": round(per_min / avg, 2) if avg else None,
                        "spikes": spikes, "reactions": reactions[:5],
                        "score": round(float((c.get("signal_scores") or {}).get("chat", 0)), 3)}
    return out


# ------------------------------------------------------------------ status


def candidate_view(c: dict) -> dict:
    """A highlights.json candidate plus the UI fields (publish package etc.)."""
    publish = {**EMPTY_PUBLISH, **(c.get("publish") or {})}
    if publish.get("viral_score") is not None:
        publish["available"] = True
        publish["viral_label"] = publish.get("viral_label") or viral_label(publish["viral_score"])
    llm = c.get("llm") or {}
    return {k: c.get(k) for k in ("id", "rank", "start", "end", "duration", "peak", "hype_score",
                                  "reasons", "signal_scores", "text")} | {
        "publish": {k: publish.get(k) for k in (*EMPTY_PUBLISH, "title_styles", "cover_text")},
        "llm": {k: llm.get(k) for k in ("what_happens", "self_contained", "moment_type", "game_or_topic",
                                         "refined", "original")} if llm else None,
        "subtitle_languages": sorted((c.get("translations") or {}).keys()),
    }


def project_summary(project: Project, active_job: dict | None, last_job: dict | None) -> dict:
    meta = project.load_meta()
    hl = meta.get("highlights") or {}
    tr = meta.get("transcript") or {}
    clips = load_clips(project) if (project.dir / "clips.json").is_file() else {}
    if active_job:
        state = active_job["status"]  # running | queued
    elif last_job and last_job["status"] == "error":
        state = "error"
    elif hl:
        state = "ready"
    elif tr:
        state = "transcribed"
    elif meta:
        state = "imported"
    else:
        state = "importing"
    src = meta.get("source") or {}
    return {
        "id": project.id,
        "title": meta.get("title") or project.id,
        "mode": meta.get("mode"),
        "duration": meta.get("duration"),
        "resolution": meta.get("resolution"),
        "source": {"type": src.get("type"), "value": src.get("webpage_url") or src.get("value"),
                   "extractor": src.get("extractor"), "uploader": src.get("uploader")},
        "language": tr.get("language"),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "state": state,
        "candidates": hl.get("count"),
        "clips": len(clips),
        "job": active_job,
        "last_error": last_job["error"] if (last_job and last_job["status"] == "error") else None,
        "last_error_kind": last_job["kind"] if (last_job and last_job["status"] == "error") else None,
    }
