"""Clips the user marks by hand (I/O on the player or the Hype Map).

They are stored in manual.json (the source of truth) and live in highlights.json next to
the found clips, with ids m01, m02... and the reason "manual", so everything else (review,
AI analysis, render, export, upload) treats them like any other candidate. Re-running the
highlight analysis keeps them (and their AI results).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import numpy as np

from ..errors import SharkyClipsError
from ..project import Project, read_json, write_json_atomic

MIN_S, MAX_S = 2.0, 300.0
_lock = threading.RLock()


def _path(project: Project):
    return project.dir / "manual.json"


def load(project: Project) -> list[dict]:
    try:
        return list(read_json(_path(project)).get("clips") or []) if _path(project).is_file() else []
    except Exception:  # noqa: BLE001
        return []


def _save(project: Project, clips: list[dict]) -> None:
    write_json_atomic(_path(project), {"version": 1, "clips": clips})


def _text(project: Project, start: float, end: float) -> str:
    if not project.transcript_path.is_file():
        return ""
    tr = read_json(project.transcript_path)
    joiner = "" if tr.get("language") in ("zh", "ja") else " "
    words = []
    for seg in tr.get("segments", []):
        if seg["end"] < start or seg["start"] > end:
            continue
        for w in seg.get("words", []):
            if start <= (w["start"] + w["end"]) / 2 <= end:
                words.append(w["word"].strip())
    return joiner.join(w for w in words if w)[:1000]


def _scores(project: Project, start: float, end: float) -> tuple[int, float, dict]:
    """(hype score 0..100, peak time, per-signal scores) from the hype curve."""
    path = project.dir / "hype_curve.json"
    if not path.is_file():
        return 50, (start + end) / 2, {}
    curve = read_json(path)
    res = float(curve.get("resolution_s") or 1)
    a, b = int(start / res), max(int(start / res) + 1, int(np.ceil(end / res)))
    comb = curve.get("combined") or []
    part = comb[a:b] or [50]
    peak = start + (int(np.argmax(part)) + 0.5) * res
    sig = {name: round(max((s.get("values") or [0])[a:b] or [0]) / 100, 3)
           for name, s in (curve.get("signals") or {}).items()}
    return int(max(part)), round(min(end, max(start, peak)), 2), sig


def candidate(project: Project, m: dict, rank: int, old: dict | None = None) -> dict:
    """highlights.json candidate for a manual clip (AI results kept from `old`)."""
    start, end = float(m["start"]), float(m["end"])
    hype, peak, sig = _scores(project, start, end)
    c = {"rank": rank, "id": m["id"], "start": start, "end": end, "duration": round(end - start, 2),
         "peak": peak, "hype_score": hype, "hype_raw": hype / 100, "hype_raw_unsmoothed": hype / 100,
         "reasons": [{"code": "manual", "t": round(start, 2), "strength": 1.0, "signal": "manual"}],
         "signal_scores": sig, "text": _text(project, start, end), "manual": True,
         "created_at": m.get("created_at")}
    for k in ("publish", "llm", "translations"):
        if old and k in old:
            c[k] = old[k]
    if old and old.get("text"):
        c["text"] = old["text"]
    return c


def merge_into(project: Project, hl: dict, previous: list[dict] | None = None) -> dict:
    """Add the manual clips to a highlights dict (after the found ones). Returns hl.
    previous: the old candidates (a re-run keeps the manual clips' AI results)."""
    clips = load(project)
    if not clips:
        return hl
    cands = hl.setdefault("candidates", [])
    have = {c["id"]: c for c in (previous or []) if c.get("manual")}
    have.update({c["id"]: c for c in cands if c.get("manual")})
    auto = [c for c in cands if not c.get("manual")]
    rank = max([c["rank"] for c in auto] + [0])
    out = list(auto)
    for m in clips:
        rank += 1
        out.append(candidate(project, m, rank, have.get(m["id"])))
    hl["candidates"] = out
    return hl


def add(project: Project, start: float, end: float) -> dict:
    """New manual clip. Returns its candidate."""
    from ..web import state

    start, end = round(float(start), 2), round(float(end), 2)
    if end < start:
        start, end = end, start
    duration = float(project.load_meta().get("duration") or 0)
    if duration:
        start, end = max(0.0, start), min(duration, end)
    if end - start < MIN_S:
        raise SharkyClipsError(f"A clip needs at least {MIN_S:g} seconds.", "Set the in point (I) and the out point (O) further apart.")
    if end - start > MAX_S:
        raise SharkyClipsError("A clip can be at most 5 minutes long.")
    with _lock:
        clips = load(project)
        n = max([int(c["id"][1:]) for c in clips if c["id"][1:].isdigit()] + [0]) + 1
        m = {"id": f"m{n:02d}", "start": start, "end": end,
             "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        clips.append(m)
        _save(project, clips)
        hl_path = project.dir / "highlights.json"
        if hl_path.is_file():
            with state._lock:
                hl = merge_into(project, read_json(hl_path))
                write_json_atomic(hl_path, hl)
        return next((c for c in (state.load_highlights(project) or {}).get("candidates", []) if c["id"] == m["id"]), m)


def remove(project: Project, cid: str) -> bool:
    from ..web import state

    with _lock:
        clips = load(project)
        if not any(c["id"] == cid for c in clips):
            return False
        _save(project, [c for c in clips if c["id"] != cid])
        hl_path = project.dir / "highlights.json"
        if hl_path.is_file():
            with state._lock:
                hl = read_json(hl_path)
                hl["candidates"] = [c for c in hl.get("candidates", []) if c["id"] != cid]
                write_json_atomic(hl_path, merge_into(project, hl))
        return True
