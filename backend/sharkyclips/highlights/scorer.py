"""Combine signals with mode weights into one hype curve (one value per second).

Signals that can't run are skipped and the remaining weights re-normalized, so
the scorer never needs to know which signals exist.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import gaussian_filter1d

from ..errors import SharkyClipsError
from ..ui import console
from .context import AnalysisContext
from .signals import REGISTRY, SignalResult, SignalUnavailable

MIN_SHARE_FOR_AGREEMENT = 0.08  # tiny-weight signals don't count as "agreeing"


@dataclass
class HypeCurve:
    smoothed: np.ndarray
    combined: np.ndarray
    results: dict[str, SignalResult]
    shares: dict[str, float]  # normalized weights of the signals that ran
    status: dict[str, dict] = field(default_factory=dict)


def compute_hype(ctx: AnalysisContext) -> HypeCurve:
    weights = {k: float(v) for k, v in ctx.mode.weights.items() if v and v > 0}
    results: dict[str, SignalResult] = {}
    status: dict[str, dict] = {}
    for name, w in weights.items():
        cls = REGISTRY.get(name)
        if cls is None:
            status[name] = {"status": "skipped", "weight": w, "reason": "not available yet"}
            continue
        t0 = time.perf_counter()
        try:
            res = cls().run(ctx)
        except SignalUnavailable as exc:
            status[name] = {"status": "skipped", "weight": w, "reason": str(exc)}
            console.print(f"[yellow]Signal '{name}' skipped:[/] {exc}")
            continue
        except Exception as exc:  # noqa: BLE001  - one broken signal must not kill the run
            status[name] = {"status": "error", "weight": w, "reason": f"{type(exc).__name__}: {exc}"}
            console.print(f"[red]Signal '{name}' failed:[/] {exc}")
            continue
        res.scores = np.clip(np.asarray(res.scores, dtype=np.float64)[: ctx.n], 0, 1)
        if len(res.scores) < ctx.n:
            res.scores = np.pad(res.scores, (0, ctx.n - len(res.scores)))
        results[name] = res
        status[name] = {"status": "ok", "weight": w, "seconds": round(time.perf_counter() - t0, 2),
                        "events": len(res.events), **({"meta": res.meta} if res.meta else {})}

    total = sum(weights[n] for n in results)
    if total <= 0:
        reasons = "; ".join(f"{k}: {v.get('reason')}" for k, v in status.items())
        raise SharkyClipsError(f"No highlight signal could run ({reasons}).",
                               "Run `python cli.py transcribe <id>` first, and `python cli.py doctor`.")
    shares = {n: weights[n] / total for n in results}
    for n, s in shares.items():
        status[n]["share"] = round(s, 3)

    combined = np.zeros(ctx.n)
    agreeing = np.zeros(ctx.n)
    for n, res in results.items():
        combined += shares[n] * res.scores
        if shares[n] >= MIN_SHARE_FOR_AGREEMENT:
            agreeing += res.scores >= 0.5
    combined *= 1.0 + ctx.mode.agreement_bonus * np.maximum(0, agreeing - 1)
    combined = np.clip(combined, 0, 1)
    smoothed = gaussian_filter1d(combined, ctx.mode.smooth_sigma) if ctx.n > 3 else combined
    return HypeCurve(smoothed, combined, results, shares, status)
