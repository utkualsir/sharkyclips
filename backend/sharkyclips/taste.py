"""Easy mode 2.0: learn the creator's taste from 👍 / 👎 on whole clips (and from what really
performs on their channel), and let it move future picks.

Each vote keeps a small snapshot of the clip: its kind (funny / action / study / music), the
AI's moment type, the game, the reasons it was picked (pentakill, laughter, chat, ...), its
length bucket and its strongest signals. A feature's preference is the smoothed mean of the
votes on clips that had it (prior 0, so a single vote moves little). Published clips with real
views count as half a vote each: above this channel's median views = 👍, below = 👎.

taste(cand) is in -1..1; the Easy grid adds up to TASTE_POINTS to the viral score once there are
MIN_VOTES votes. Stored in ~/.sharkyclips/clip_taste.json (about the channel, all projects).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from . import config
from .project import read_json, write_json_atomic

MIN_VOTES = 3
TASTE_POINTS = 12.0  # most the taste moves a clip's score (0..100)
PRIOR = 2.0  # smoothing: a feature needs a few votes before it counts fully
VIEWS_WEIGHT = 0.5
SIGNALS = ("laughter", "chat", "game", "loudness", "keywords", "speech", "llm", "music")
MAX_VOTES = 2000

_lock = threading.RLock()


def path() -> Path:
    return config.config_dir() / "clip_taste.json"


def _load() -> dict:
    p = path()
    try:
        data = read_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        data = {}
    return {"version": 1, "votes": dict(data.get("votes") or {})}


def _length_bucket(d: float) -> str:
    return "lt20" if d < 20 else "20_30" if d < 30 else "30_45" if d < 45 else "gt45"


def snapshot(cand: dict, mode: str) -> list[str]:
    """The clip's features as tokens ("kind:funny", "reason:laughter", "game:delta_force", ...)."""
    from .shaping import content_kind

    toks = [f"kind:{content_kind(mode, cand)}", f"len:{_length_bucket(float(cand.get('duration') or 0))}"]
    mt = str((cand.get("llm") or {}).get("moment_type") or "").lower()
    if mt:
        toks.append(f"moment:{mt}")
    game = ((cand.get("publish") or {}).get("game") or {}).get("id")
    if game:
        toks.append(f"game:{game}")
    for code in sorted({str(r.get("code")) for r in cand.get("reasons") or [] if r.get("code")}):
        toks.append(f"reason:{code}")
    for s in SIGNALS:
        if float((cand.get("signal_scores") or {}).get(s) or 0) >= 0.5:
            toks.append(f"sig:{s}")
    return toks


def key(project_id: str, clip_id: str) -> str:
    return f"{project_id}:{clip_id}"


def vote(project_id: str, cand: dict, mode: str, value: int) -> dict:
    """value 1 (👍), -1 (👎) or 0 (take the vote back)."""
    value = 1 if value > 0 else -1 if value < 0 else 0
    with _lock:
        data = _load()
        k = key(project_id, cand["id"])
        if value == 0:
            data["votes"].pop(k, None)
        else:
            data["votes"][k] = {"value": value, "tokens": snapshot(cand, mode),
                                "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            if len(data["votes"]) > MAX_VOTES:
                for old in sorted(data["votes"], key=lambda x: data["votes"][x].get("at") or "")[: len(data["votes"]) - MAX_VOTES]:
                    data["votes"].pop(old, None)
        write_json_atomic(path(), data)
        _model_cache.clear()
        return {"vote": value, **status(data)}


def votes_for(project_id: str) -> dict[str, int]:
    pre = f"{project_id}:"
    return {k[len(pre):]: int(v.get("value") or 0) for k, v in _load()["votes"].items() if k.startswith(pre)}


def _view_samples() -> list[tuple[list[str], float]]:
    """Published clips with real views: (tokens, +-VIEWS_WEIGHT) around this channel's median."""
    from . import calibration
    from .project import get_project

    try:
        entries = list(calibration.load()["entries"].values())
    except Exception:  # noqa: BLE001
        return []
    entries = [e for e in entries if e.get("views") is not None]
    if len(entries) < 3:
        return []
    mid = median(float(e["views"]) for e in entries)
    out = []
    for e in entries:
        v = float(e["views"])
        if v == mid:
            continue
        try:
            hl = read_json(get_project(e["project_id"]).dir / "highlights.json")
        except Exception:  # noqa: BLE001 - the project was deleted
            continue
        cand = next((c for c in hl.get("candidates") or [] if c["id"] == e["clip_id"]), None)
        if cand is None:
            continue
        out.append((snapshot(cand, e.get("mode") or hl.get("mode") or "gaming"), VIEWS_WEIGHT if v > mid else -VIEWS_WEIGHT))
    return out


_model_cache: dict = {}


def model(data: dict | None = None) -> dict:
    """{"weights": {token: -1..1}, "votes": n, "views": n} (cached until the next vote)."""
    import time

    if data is None and _model_cache and time.time() - _model_cache.get("at", 0) < 600:
        return _model_cache["m"]
    data = data or _load()
    samples = [(v["tokens"], float(v["value"])) for v in data["votes"].values() if v.get("tokens")]
    views = _view_samples()
    sums: dict[str, float] = {}
    counts: dict[str, float] = {}
    for toks, val in samples + views:
        w = abs(val)
        for t in set(toks):
            sums[t] = sums.get(t, 0.0) + val
            counts[t] = counts.get(t, 0.0) + w
    weights = {t: round(sums[t] / (counts[t] + PRIOR), 3) for t in sums}
    m = {"weights": weights, "votes": len(samples), "views": len(views)}
    _model_cache.update(m=m, at=time.time())
    return m


def taste(cand: dict, mode: str, m: dict | None = None) -> float | None:
    """-1..1 how well the clip fits the creator's taste; None before MIN_VOTES votes."""
    m = m or model()
    if m["votes"] < MIN_VOTES:
        return None
    ws = [m["weights"][t] for t in snapshot(cand, mode) if t in m["weights"]]
    if not ws:
        return 0.0
    # the strongest likes / dislikes matter most (a mean of many weak tokens says little)
    ws.sort(key=abs, reverse=True)
    top = ws[:5]
    return round(max(-1.0, min(1.0, sum(top) / len(top) * 1.6)), 3)


def adjust(score: float | None, t: float | None) -> float | None:
    if score is None or t is None:
        return score
    return max(0.0, min(100.0, float(score) + TASTE_POINTS * t))


def status(data: dict | None = None) -> dict:
    m = model(data) if data is not None else model()
    return {"votes": m["votes"], "views": m["views"], "active": m["votes"] >= MIN_VOTES,
            "need": max(0, MIN_VOTES - m["votes"])}
