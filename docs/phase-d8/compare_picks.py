"""Phase D8 measurement: which clip picks did the new engine add or drop?

    python docs/phase-d8/compare_picks.py shadow <workspace_project_dir> <shadow_dir>
    python docs/phase-d8/compare_picks.py run <code_root/backend> <shadow_dir> <out.json>
    python docs/phase-d8/compare_picks.py diff <before.json> <after.json> [anchors.json]

shadow  copies what the highlight engine reads (meta, transcript, audio, the laughter and HUD-scan
        caches) into a throwaway folder. The real project is only READ: nothing is ever written there.
run     runs the engine of one code tree (the old release or the new one) on a shadow copy, in
        memory: no highlights.json is written. The game signal may only use the cached HUD scan
        (it never re-reads the video). Needs SHARKYCLIPS_HOME pointing at a throwaway folder.
diff    matches the clips of two runs (overlap) and lists kept / added / dropped, how much
        earlier or later the kept ones start and end, and their reasons.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

COPY = ("meta.json", "transcript.json", "audio.wav", "markers.json", "chat.json",
        "cache/signals/laughter.npz", "cache/game/scan.json", "cache/game/sounds.json")


def shadow(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for rel in COPY:
        a = src / rel
        if a.is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(a, dst / rel)
    srcs = sorted(p for p in src.glob("source.*") if p.is_file())
    (dst / "original_source.txt").write_text(str(srcs[0]) if srcs else "", encoding="utf-8")


def run(backend: Path, sdir: Path, out: Path, top: int | None = None) -> None:
    import psutil

    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)  # the owner's own jobs come first
    sys.path.insert(0, str(backend))
    from sharkyclips import game
    from sharkyclips.highlights import pipeline
    from sharkyclips.highlights.candidates import pick_candidates
    from sharkyclips.highlights.context import AnalysisContext
    from sharkyclips.highlights.modes import get_mode
    from sharkyclips.highlights.scorer import compute_hype
    from sharkyclips.project import Project

    orig = (sdir / "original_source.txt").read_text(encoding="utf-8").strip() if (sdir / "original_source.txt").is_file() else ""

    class Shadow(Project):
        @property
        def source_path(self):  # the real video, read-only (only its size is used: HUD cache key)
            return Path(orig) if orig else None

    def cached_scan(project, gid, on_progress=None, force=False):
        c = game.load_scan(project)
        if c and c.get("key") == game.scan_key(project, gid):
            return c
        raise RuntimeError("no cached HUD scan (the measurement never re-reads the video)")

    game.scan = cached_scan
    p = Shadow(sdir.name, sdir)
    meta = p.load_meta()
    preset = get_mode(meta.get("mode") or "gaming")
    profile = None
    if hasattr(pipeline, "_profile"):  # the new engine: game or talk stream
        from sharkyclips.highlights.modes import with_profile

        profile = pipeline._profile(p, meta, preset)
        preset = with_profile(preset, profile[0])
    t0 = time.perf_counter()
    ctx = AnalysisContext(p, preset)
    hype = compute_hype(ctx)
    cands = pick_candidates(ctx, hype, top)
    res = {"project": sdir.name, "seconds": round(time.perf_counter() - t0, 1), "duration": round(ctx.duration, 1),
           "profile": profile, "signals": {k: v.get("status") + (f" ({v.get('reason')})" if v.get("reason") else "")
                                           for k, v in hype.status.items()},
           "clips": [{"start": c.start, "end": c.end, "peak": c.peak, "hype": c.hype_score,
                      "reasons": [r["code"] for r in c.reasons],
                      "headline": getattr(c, "headline", None),
                      "marker": (c.marker or {}).get("source") if c.marker else None} for c in cands]}
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{sdir.name}: {len(cands)} clips in {res['seconds']} s")


def _overlap(a: dict, b: dict) -> float:
    inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    return inter / max(1e-6, min(a["end"] - a["start"], b["end"] - b["start"]))


def diff(before: dict, after: dict, anchors: dict | None = None) -> dict:
    used = set()
    kept, dropped = [], []
    for b in before["clips"]:
        best, bi = 0.0, None
        for i, a in enumerate(after["clips"]):
            if i not in used and _overlap(a, b) > best:
                best, bi = _overlap(a, b), i
        if bi is not None and best >= 0.5:
            used.add(bi)
            a = after["clips"][bi]
            kept.append({"before": b, "after": a, "start_shift": round(a["start"] - b["start"], 1),
                         "end_shift": round(a["end"] - b["end"], 1)})
        else:
            dropped.append(b)
    added = [a for i, a in enumerate(after["clips"]) if i not in used]
    out = {"project": after["project"], "before": len(before["clips"]), "after": len(after["clips"]),
           "kept": len(kept), "added": added, "dropped": dropped,
           "mean_start_shift": round(sum(k["start_shift"] for k in kept) / len(kept), 1) if kept else None,
           "mean_end_shift": round(sum(k["end_shift"] for k in kept) / len(kept), 1) if kept else None,
           "mean_len_before": round(sum(c["end"] - c["start"] for c in before["clips"]) / max(1, len(before["clips"])), 1),
           "mean_len_after": round(sum(c["end"] - c["start"] for c in after["clips"]) / max(1, len(after["clips"])), 1),
           "headlines": {}, "seconds": [before["seconds"], after["seconds"]], "profile": after.get("profile")}
    for c in after["clips"]:
        h = (c.get("headline") or {}).get("code") or "-"
        out["headlines"][h] = out["headlines"].get(h, 0) + 1
    if anchors:  # synthetic sample: which planted moments does each run find?
        def hit(clips, t, name):
            if name == "marker":  # a spoken marker's clip ends just BEFORE the phrase
                return any(c.get("marker") == "voice" and abs(c["peak"] - t) < 2 for c in clips)
            return any(c["start"] - 1 <= t <= c["end"] + 1 for c in clips)
        out["moments"] = {k: {"before": hit(before["clips"], t, k), "after": hit(after["clips"], t, k)}
                          for k, t in anchors.items()}
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "shadow":
        shadow(Path(sys.argv[2]), Path(sys.argv[3]))
    elif cmd == "run":
        run(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), int(sys.argv[5]) if len(sys.argv) > 5 else None)
    else:
        b = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        a = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        anc = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8")) if len(sys.argv) > 4 else None
        print(json.dumps(diff(b, a, anc), indent=1, ensure_ascii=False))
