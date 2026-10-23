"""Run the highlight engine on a project and write highlights.json."""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone

import numpy as np

from .. import __version__
from ..errors import ClipForgeError
from ..project import Project, write_json_atomic
from .candidates import pick_candidates
from .context import AnalysisContext
from .modes import get_mode
from .scorer import compute_hype

HIGHLIGHTS_VERSION = 1
HYPE_MAP_MAX_POINTS = 1500  # plenty for a timeline, tiny to load even for 6 h streams


def _pool_max(values: np.ndarray, bucket: int) -> list[int]:
    """Max-pool into buckets (peaks survive downsampling), as ints 0..100."""
    n = len(values)
    m = -(-n // bucket)
    padded = np.pad(values, (0, m * bucket - n))
    return [int(round(v * 100)) for v in padded.reshape(m, bucket).max(axis=1)]


def hype_curve_json(project: Project, ctx: AnalysisContext, hype, result: dict) -> dict:
    """Small file for the UI's Hype Map: combined + per-signal curves + clip markers."""
    bucket = max(1, -(-ctx.n // HYPE_MAP_MAX_POINTS))
    return {
        "version": 1,
        "project_id": project.id,
        "mode": result["mode"],
        "duration": result["duration"],
        "resolution_s": bucket,  # seconds per point; point i covers [i*res, (i+1)*res)
        "scale": 100,  # values are 0..100
        "combined": _pool_max(hype.smoothed, bucket),
        "signals": {name: {"share": round(hype.shares[name], 3),
                           "values": _pool_max(res.scores, bucket)}
                    for name, res in hype.results.items()},
        "candidates": [{"rank": c["rank"], "start": c["start"], "end": c["end"],
                        "peak": c["peak"], "hype_score": c["hype_score"]}
                       for c in result["candidates"]],
    }


def run_highlights(project: Project, mode: str | None = None, top: int | None = None,
                   force: bool = False) -> dict:
    meta = project.load_meta()
    mode_name = mode or meta.get("mode") or "gaming"
    preset = get_mode(mode_name)
    if not project.audio_path.is_file():
        raise ClipForgeError(f"Project '{project.id}' has no audio.wav.",
                             "Re-run: python cli.py ingest <url-or-path>")
    if force:
        shutil.rmtree(project.cache_dir / "signals", ignore_errors=True)

    t0 = time.perf_counter()
    ctx = AnalysisContext(project, preset)
    hype = compute_hype(ctx)
    cands = pick_candidates(ctx, hype, top)
    elapsed = time.perf_counter() - t0

    result = {
        "version": HIGHLIGHTS_VERSION,
        "project_id": project.id,
        "mode": preset.name,
        "language": ctx.language,
        "duration": round(ctx.duration, 3),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "clipforge_version": __version__,
        "elapsed_seconds": round(elapsed, 2),
        "settings": {"clip_min": preset.clip_min, "clip_ideal": preset.clip_ideal,
                     "clip_max": preset.clip_max, "pre_roll": list(preset.pre_roll),
                     "min_gap": preset.min_gap, "weights": preset.weights},
        "signals": hype.status,
        "candidates": [
            {
                "rank": i + 1,
                "id": f"c{i + 1:02d}",
                "start": c.start,
                "end": c.end,
                "duration": round(c.duration, 2),
                "peak": c.peak,
                "hype_score": c.hype_score,
                "hype_raw": round(c.raw, 4),
                "hype_raw_unsmoothed": round(c.raw_unsmoothed, 4),
                "reasons": c.reasons,
                "signal_scores": c.signal_scores,
                "text": c.text,
            }
            for i, c in enumerate(cands)
        ],
        # Whole-video hype curve (1 value per second) for the UI timeline / later calibration.
        "curve": {"resolution_s": 1.0, "values": [round(float(v), 3) for v in hype.smoothed]},
    }
    path = project.dir / "highlights.json"
    write_json_atomic(path, result)
    write_json_atomic(project.dir / "hype_curve.json", hype_curve_json(project, ctx, hype, result),
                      compact=True)
    meta["highlights"] = {"file": path.name, "mode": preset.name, "count": len(cands)}
    project.save_meta(meta)
    return result
