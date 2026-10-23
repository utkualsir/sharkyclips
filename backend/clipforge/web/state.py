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
EMPTY_PUBLISH = {"available": False, "viral_score": None, "viral_label": None, "titles": [],
                 "hashtags": [], "cover_prompt": None}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def viral_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 80:
        return "very_high"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


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


# ------------------------------------------------------------------ status


def candidate_view(c: dict) -> dict:
    """A highlights.json candidate plus the UI fields (publish package etc.)."""
    publish = {**EMPTY_PUBLISH, **(c.get("publish") or {})}
    if publish.get("viral_score") is not None:
        publish["available"] = True
        publish["viral_label"] = publish.get("viral_label") or viral_label(publish["viral_score"])
    return {k: c.get(k) for k in ("id", "rank", "start", "end", "duration", "peak", "hype_score",
                                  "reasons", "signal_scores", "text")} | {"publish": publish}


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
