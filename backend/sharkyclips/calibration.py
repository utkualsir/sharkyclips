"""Channel calibration: learn which clips do well on YOUR channel.

After publishing, the creator types a rendered clip's real YouTube views (and optionally
likes / when it was published). Each entry stores a snapshot of the clip's signal features
and viral score. With MIN_POINTS or more entries a ridge regression on log10(views) is fitted
(plain numpy, closed form, the penalty picked by leave-one-out error). It turns the default
viral score into a "calibrated" one:

  model score  = where the predicted views fall among this channel's real views (0..100)
  calibrated   = default + w * (model score - default),  w = n / (n + 10)

so with few data points the default score still counts most. Everything is stored in
~/.sharkyclips/calibration.json (shared by all projects: it is about the channel).
"""

from __future__ import annotations

import math
import threading
from datetime import datetime, timezone
from statistics import median
from typing import Any

import numpy as np

from . import config
from .project import read_json, write_json_atomic

MIN_POINTS = 10
ALPHAS = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
SIGNALS = ("loudness", "laughter", "keywords", "speech", "chat", "llm", "music")
LENGTH_BUCKETS = ((0, 20, "lt20"), (20, 30, "20_30"), (30, 45, "30_45"), (45, 1e9, "gt45"))
HOUR_BUCKETS = ((5, 12, "morning"), (12, 17, "afternoon"), (17, 22, "evening"))  # else night
STREAM_BUCKETS = ((0, 1 / 3, "early"), (1 / 3, 2 / 3, "middle"), (2 / 3, 1.01, "late"))

_lock = threading.RLock()
_cache: dict[str, Any] = {"mtime": None, "data": None}


def path():
    return config.config_dir() / "calibration.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> dict:
    with _lock:
        p = path()
        mtime = p.stat().st_mtime if p.is_file() else None
        if _cache["data"] is not None and _cache["mtime"] == mtime:
            return _cache["data"]
        data = {"version": 1, "entries": {}, "model": None}
        if mtime is not None:
            try:
                data.update(read_json(p))
            except Exception:  # noqa: BLE001 - broken file: start over (it is rewritten on save)
                pass
        _cache.update(mtime=mtime, data=data)
        return data


def _save(data: dict) -> None:
    with _lock:
        write_json_atomic(path(), data)
        _cache.update(mtime=path().stat().st_mtime, data=data)


# ------------------------------------------------------------------ features


def features(c: dict) -> dict[str, float]:
    """Numbers the model learns from, taken from a highlights.json candidate."""
    pub = c.get("publish") or {}
    sub = pub.get("sub_scores") or {}
    llm = c.get("llm") or {}
    sig = c.get("signal_scores") or {}
    viral = pub.get("viral_score")
    f = {
        "viral_score": float(viral if viral is not None else c.get("hype_score") or 0),
        "hype_score": float(c.get("hype_score") or 0),
        "hook": float(sub.get("hook", 50)),
        "retention": float(sub.get("retention", 50)),
        "trend_fit": float(sub.get("trend_fit", 50)),
        "length_fit": float(sub.get("length_fit", 50)),
        "duration": float(c.get("duration") or 0),
        "funny": float(llm.get("funny", 5)),
        "exciting": float(llm.get("exciting", 5)),
        "useful": float(llm.get("useful", 5)),
        "self_contained": 1.0 if llm.get("self_contained", True) else 0.0,
    }
    for s in SIGNALS:
        f[f"sig_{s}"] = float(sig.get(s, 0.0))
    return f


# ------------------------------------------------------------------ entries


def entry_key(project_id: str, clip_id: str) -> str:
    return f"{project_id}:{clip_id}"


def set_entry(project, cand: dict, views: int, likes: int | None = None,
              published_at: str | None = None) -> dict:
    meta = project.load_meta()
    pub = cand.get("publish") or {}
    duration_stream = float(meta.get("duration") or 0)
    with _lock:
        data = load()
        key = entry_key(project.id, cand["id"])
        old = data["entries"].get(key) or {}
        entry = {
            "project_id": project.id, "clip_id": cand["id"], "project_title": meta.get("title") or project.id,
            "title": (pub.get("titles") or [None])[0] or (cand.get("text") or "")[:80],
            "views": max(0, int(views)), "likes": None if likes is None else max(0, int(likes)),
            "published_at": published_at or None,
            "entered_at": old.get("entered_at") or now_iso(), "updated_at": now_iso(),
            "mode": (meta.get("mode") or "gaming"),
            "moment_type": (cand.get("llm") or {}).get("moment_type"),
            "duration": float(cand.get("duration") or 0),
            "stream_pos": round(float(cand.get("start") or 0) / duration_stream, 3) if duration_stream else None,
            "viral_score": pub.get("viral_score"), "hype_score": cand.get("hype_score"),
            "features": features(cand),
        }
        data["entries"][key] = entry
        data["model"] = fit(data["entries"])
        _save(data)
        return entry


def delete_entry(key: str) -> bool:
    with _lock:
        data = load()
        if data["entries"].pop(key, None) is None:
            return False
        data["model"] = fit(data["entries"])
        _save(data)
        return True


def clear() -> int:
    with _lock:
        data = load()
        n = len(data["entries"])
        data["entries"], data["model"] = {}, None
        _save(data)
        return n


def entries_for(project_id: str) -> dict[str, dict]:
    return {e["clip_id"]: e for e in load()["entries"].values() if e["project_id"] == project_id}


# ------------------------------------------------------------------ model


def _ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, np.ndarray]:
    """Coefficients + leave-one-out predictions (X standardized, y centered)."""
    n, p = X.shape
    A = X.T @ X + alpha * np.eye(p)
    inv = np.linalg.inv(A)
    beta = inv @ X.T @ y
    h = np.einsum("ij,jk,ik->i", X, inv, X) + 1.0 / n  # + intercept leverage
    resid = y - X @ beta
    loo = y - resid / np.clip(1.0 - h, 1e-6, None)
    return beta, loo


def fit(entries: dict[str, dict]) -> dict | None:
    rows = [e for e in entries.values() if e.get("features") and e.get("views") is not None]
    if len(rows) < MIN_POINTS:
        return None
    names = sorted(rows[0]["features"])
    X = np.array([[float(e["features"].get(k, 0.0)) for k in names] for e in rows])
    y = np.log10(np.array([e["views"] for e in rows], dtype=float) + 1.0)
    mean, std = X.mean(axis=0), X.std(axis=0)
    keep = std > 1e-9  # features that never change can't teach anything
    names = [k for k, ok in zip(names, keep) if ok]
    if not names:
        return None
    Xs = (X[:, keep] - mean[keep]) / std[keep]
    y_mean, y_std = float(y.mean()), float(y.std()) or 1.0
    yc = y - y_mean
    best = None
    for a in ALPHAS:
        beta, loo = _ridge(Xs, yc, a)
        sse = float(((yc - loo) ** 2).sum())
        if best is None or sse < best[0]:
            best = (sse, a, beta, loo)
    sse, alpha, beta, loo = best
    sst = float((yc ** 2).sum()) or 1e-9
    order = np.argsort(-np.abs(beta))
    return {
        "n": len(rows), "alpha": alpha, "r2_loo": round(1.0 - sse / sst, 3),
        "features": names, "mean": [float(m) for m in mean[keep]], "std": [float(s) for s in std[keep]],
        "coef": [float(b) for b in beta], "y_mean": y_mean, "y_std": y_std,
        "top_features": [{"name": names[i], "effect": round(float(beta[i]), 3)} for i in order[:5]],
        "loo": {f"{e['project_id']}:{e['clip_id']}": round(float(10 ** (v + y_mean) - 1), 1)
                for e, v in zip(rows, loo)},
        "fitted_at": now_iso(),
    }


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def weight(n: int) -> float:
    return n / (n + 10.0)


def adjust(cand: dict, model: dict | None = None) -> dict | None:
    """Calibrated viral score for one candidate, or None while not calibrated."""
    model = model if model is not None else load().get("model")
    pub = cand.get("publish") or {}
    default = pub.get("viral_score")
    if not model or default is None:
        return None
    f = features(cand)
    x = np.array([(f.get(k, 0.0) - m) / s for k, m, s in zip(model["features"], model["mean"], model["std"])])
    pred = float(x @ np.array(model["coef"])) + model["y_mean"]
    model_score = 100.0 * _phi((pred - model["y_mean"]) / (model["y_std"] or 1.0))
    w = weight(model["n"])
    score = int(round(min(100, max(0, default + w * (model_score - default)))))
    return {"score": score, "default": int(default), "model_score": int(round(model_score)),
            "predicted_views": int(round(10 ** pred - 1)), "weight": round(w, 2), "n": model["n"]}


def status() -> dict:
    data = load()
    model = data.get("model")
    n = len(data["entries"])
    return {"calibrated": bool(model), "n": n, "needed": MIN_POINTS,
            "model_points": model["n"] if model else 0,
            "r2_loo": model["r2_loo"] if model else None,
            "weight": weight(model["n"]) if model else 0.0,
            "top_features": model["top_features"] if model else [],
            "fitted_at": model["fitted_at"] if model else None}


# ------------------------------------------------------------------ stats


def _bucket(value: float | None, buckets) -> str | None:
    if value is None:
        return None
    for lo, hi, name in buckets:
        if lo <= value < hi:
            return name
    return None


def _hour_bucket(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return _bucket(dt.hour, HOUR_BUCKETS) or "night"


def _groups(rows: list[dict], key) -> list[dict]:
    groups: dict[str, list[int]] = {}
    for e in rows:
        k = key(e)
        if k is not None:
            groups.setdefault(k, []).append(int(e["views"]))
    out = [{"key": k, "count": len(v), "median_views": int(median(v)), "mean_views": int(sum(v) / len(v))}
           for k, v in groups.items()]
    out.sort(key=lambda g: -g["median_views"])
    return out


def stats() -> dict:
    data = load()
    model = data.get("model")
    rows = sorted(data["entries"].values(), key=lambda e: e.get("entered_at") or "")
    loo = (model or {}).get("loo") or {}
    points = []
    for e in rows:
        k = entry_key(e["project_id"], e["clip_id"])
        points.append({"key": k, "project_id": e["project_id"], "clip_id": e["clip_id"],
                       "title": e.get("title"), "project_title": e.get("project_title"),
                       "views": e["views"], "likes": e.get("likes"), "published_at": e.get("published_at"),
                       "predicted": loo.get(k), "viral_score": e.get("viral_score"),
                       "mode": e.get("mode"), "duration": e.get("duration")})
    with_time = [e for e in rows if _hour_bucket(e.get("published_at"))]
    time_basis = "published" if len(with_time) >= 3 else "stream"
    return {
        "status": status(),
        "points": points,
        "best": {
            "mode": _groups(rows, lambda e: e.get("mode")),
            "length": _groups(rows, lambda e: _bucket(e.get("duration"), LENGTH_BUCKETS)),
            "moment": _groups(rows, lambda e: e.get("moment_type")),
            "time": _groups(with_time, lambda e: _hour_bucket(e.get("published_at")))
            if time_basis == "published" else _groups(rows, lambda e: _bucket(e.get("stream_pos"), STREAM_BUCKETS)),
            "time_basis": time_basis,
        },
    }
