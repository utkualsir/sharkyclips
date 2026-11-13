"""Easy mode 2.0: the weekly digest at the top of the Library.

- shorts published in the last 7 days and their views,
- the best performer,
- what worked (length, hook type, game): groups of the last 30 days whose average views beat
  the channel's average by at least 15 % (two clips per group at least),
- one suggestion in plain words, the most useful first.

Everything comes from the real upload records (uploads.json: views / likes are fetched from
YouTube every 6 hours) and the clips themselves. The UI words it (codes + numbers here).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

WEEK = 7
WINDOW = 30  # days "what worked" looks back
MIN_GROUP = 2
MIN_RATIO = 1.15
LENGTHS = ((0, 20, "lt20"), (20, 30, "20_30"), (30, 45, "30_45"), (45, 1e9, "gt45"))


def _when(u: dict) -> datetime | None:
    for k in ("published_at", "publish_at", "uploaded_at"):
        v = u.get(k)
        if not v:
            continue
        try:
            t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _length(d: float) -> str:
    return next(name for lo, hi, name in LENGTHS if lo <= d < hi)


def shorts(now: datetime) -> list[dict]:
    """Every live upload of every project (not cancelled / deleted), with what it was."""
    from .project import list_projects
    from .web import state

    out = []
    for project in list_projects():
        ups = state.load_uploads(project)
        if not ups:
            continue
        hl = state.load_highlights(project) or {}
        cands = {c["id"]: c for c in hl.get("candidates") or []}
        review = state.load_review(project, hl)
        mode = project.load_meta().get("mode") or hl.get("mode") or "gaming"
        for cid, lst in ups.items():
            u = next((x for x in lst if x.get("video_id") and not x.get("missing") and not x.get("cancelled")), None)
            if u is None:
                continue
            when = _when(u)
            if when is None or when > now:
                continue  # planned for later: not published yet
            c = cands.get(cid) or {}
            eff = state.effective_cand(c, review) if c else {"duration": 0}
            pub = c.get("publish") or {}
            out.append({"project_id": project.id, "clip_id": cid, "title": u.get("title") or (pub.get("titles") or [cid])[0],
                        "url": u.get("url"), "views": u.get("views"), "likes": u.get("likes"), "at": when,
                        "length": _length(float(eff.get("duration") or 0)), "duration": float(eff.get("duration") or 0),
                        "hook": u.get("hook_style") or "statement",
                        "game": ((pub.get("game") or {}).get("name")) or None,
                        "private": u.get("privacy") == "private", "mode": mode})
    return out


def social(now: datetime, days: int = WEEK) -> dict:
    """TikTok / Instagram posts of the last days (by SharkyClips, by hand or in the browser):
    {"tiktok": n, "reels": n, "views": known views or None}."""
    from . import platforms as PF
    from .project import list_projects

    since = now - timedelta(days=days)
    out = {"tiktok": 0, "reels": 0, "views": None}
    for project in list_projects():
        try:
            recs = PF.records(project)
        except Exception:  # noqa: BLE001
            continue
        for plats in recs.values():
            for p in ("tiktok", "reels"):
                r = (plats or {}).get(p) or {}
                if r.get("status") != "published":
                    continue
                at = _when({"published_at": r.get("posted_at")})
                if at is None and r.get("at"):
                    at = datetime.fromtimestamp(float(r["at"]), timezone.utc)
                if at is None or not (since <= at <= now):
                    continue
                out[p] += 1
                if isinstance(r.get("views"), int):
                    out["views"] = (out["views"] or 0) + r["views"]
    return out


def _worked(items: list[dict]) -> list[dict]:
    known = [s for s in items if s.get("views") is not None]
    if len(known) < 3:
        return []
    avg = sum(s["views"] for s in known) / len(known)
    if avg <= 0:
        return []
    out = []
    for dim in ("length", "hook", "game"):
        groups: dict[str, list[int]] = {}
        for s in known:
            if s.get(dim):
                groups.setdefault(str(s[dim]), []).append(int(s["views"]))
        best = None
        for value, vs in groups.items():
            if len(vs) < MIN_GROUP or len(groups) < 2:
                continue
            ratio = (sum(vs) / len(vs)) / avg
            if ratio >= MIN_RATIO and (best is None or ratio > best["ratio"]):
                best = {"dim": dim, "value": value, "ratio": round(ratio, 2), "n": len(vs),
                        "avg_views": round(sum(vs) / len(vs))}
        if best:
            out.append(best)
    return out


def weekly(now: datetime | None = None) -> dict:
    from . import autopilot, config, lengthfit, publishing as P, youtube

    now = now or datetime.now(timezone.utc)
    allshorts = shorts(now)
    week = [s for s in allshorts if s["at"] >= now - timedelta(days=WEEK)]
    recent = [s for s in allshorts if s["at"] >= now - timedelta(days=WINDOW)]
    with_views = [s for s in week if s.get("views") is not None]
    best = max(with_views, key=lambda s: s["views"], default=None)
    worked = _worked(recent)
    connected = youtube.connected()
    limit = P.effective_limit()
    mode = config.get("default_mode") or "gaming"
    tgt = lengthfit.for_mode(mode)
    # one suggestion, the most useful first
    if not connected:
        sug = {"code": "connect"}
    elif not week:
        sug = {"code": "publish_ready"}
    elif any(w["dim"] == "length" and w["ratio"] >= 1.3 for w in worked):
        w = next(w for w in worked if w["dim"] == "length")
        # the length target already follows it (lengthfit): say so instead of "use the buttons"
        code = "length_auto" if lengthfit.band_name(tgt) == w["value"] else "length"
        sug = {"code": code, "value": w["value"], "ratio": w["ratio"]}
    elif any(w["dim"] == "hook" and w["ratio"] >= 1.3 for w in worked):
        w = next(w for w in worked if w["dim"] == "hook")
        sug = {"code": "hook", "value": w["value"], "ratio": w["ratio"]}
    elif len(week) < limit * WEEK * 0.5 and not autopilot.enabled():
        sug = {"code": "autopilot", "n": len(week), "possible": limit * WEEK}
    elif any(w["dim"] == "game" for w in worked):
        w = next(w for w in worked if w["dim"] == "game")
        sug = {"code": "game", "value": w["value"], "ratio": w["ratio"]}
    else:
        sug = {"code": "keep_going"}
    return {
        "from": (now - timedelta(days=WEEK)).isoformat(timespec="seconds"), "to": now.isoformat(timespec="seconds"),
        "published": len(week), "private": sum(1 for s in week if s["private"]),
        "views": sum(int(s["views"] or 0) for s in with_views), "views_known": len(with_views),
        "likes": sum(int(s["likes"] or 0) for s in with_views if s.get("likes") is not None),
        "best": {k: best[k] for k in ("project_id", "clip_id", "title", "url", "views", "duration", "hook")} if best else None,
        "worked": worked, "suggestion": sug, "daily_limit": limit, "connected": connected,
        "elsewhere": social(now),
        "length_target": {"mode": mode, **tgt} if tgt else None,
    }
