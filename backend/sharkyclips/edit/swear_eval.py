"""Measuring swear detection (1.2.21): labels, recall / precision, fixtures.

Labels come from a "find everything" deep check (voices/swearscan.py, find_all=True): every
candidate any pass heard is a row in <project>/swear_labels.json, marked yes (a swear was
said), no (a false hit) or unsure, by Claude ("by": "claude") or the user on the review page
(Studio > Word lists > Swear check). Only times + text, never audio.

Metrics (a swear counts as caught when a bleep covers its middle):
  recall     caught true swears / all true swears        (recall first)
  precision  bleeps on true swears / all bleeps
  partial    caught swears where a re-listen of the bleeped audio still hears part of it

export_fixture() writes the text a test needs to recompute the vote (base words + every pass's
words near a labelled item); fixture_metrics() recomputes recall / precision from it, so a
regression test fails when detection loses recall.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ..project import Project, read_json, write_json_atomic

VERSION = 1
LABELS = ("yes", "no", "unsure")
_lock = threading.Lock()


def labels_path(project: Project) -> Path:
    return project.dir / "swear_labels.json"


def item_key(it: dict) -> str:
    return f"{float(it['start']):.2f}"


def load_labels(project: Project) -> dict:
    p = labels_path(project)
    try:
        data = read_json(p) if p.is_file() else {}
    except Exception:  # noqa: BLE001
        data = {}
    if data.get("version") != VERSION:
        data = {"version": VERSION, "items": {}}
    return data


def set_label(project: Project, key: str, label: str | None, note: str = "", by: str = "user",
              item: dict | None = None) -> dict:
    with _lock:
        data = load_labels(project)
        row = dict(data["items"].get(key) or {})
        if item:
            row.update({k: item.get(k) for k in ("start", "end", "word", "heard", "spk")})
        if label in LABELS:
            row.update(label=label, by=by, at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        elif label is None and key in data["items"]:
            row.pop("label", None)
        if note:
            row["note"] = note[:300]
        data["items"][key] = row
        write_json_atomic(labels_path(project), data)
        return data


# ------------------------------------------------------------------------------ metrics

def truth(labels: dict, unsure_as: str = "yes") -> list[dict]:
    """The true swears: label yes (and unsure counted as `unsure_as`)."""
    out = []
    for row in (labels.get("items") or {}).values():
        lab = row.get("label")
        if lab == "unsure":
            lab = unsure_as
        if lab == "yes":
            out.append(row)
    return sorted(out, key=lambda r: float(r["start"]))


def _covers(r: tuple[float, float], s: dict, slack: float = 0.05) -> bool:
    mid = (float(s["start"]) + float(s["end"])) / 2
    return r[0] - slack <= mid <= r[1] + slack


def metrics(true_items: list[dict], bleeps: list[tuple[float, float]], partial: dict | None = None) -> dict:
    """bleeps: the bleep ranges (source time) the pipeline would render.
    partial: {item_key: True/False} = still audible after the bleep (re-listen)."""
    caught = [t for t in true_items if any(_covers(b, t) for b in bleeps)]
    on_true = [b for b in bleeps if any(_covers(b, t, 0.1) or (b[0] < t["end"] and b[1] > t["start"]) for t in true_items)]
    out = {"true": len(true_items), "caught": len(caught), "bleeps": len(bleeps),
           "recall": round(len(caught) / len(true_items), 3) if true_items else 1.0,
           "precision": round(len(on_true) / len(bleeps), 3) if bleeps else 1.0,
           "missed": [f"{float(t['start']):.2f} {t.get('word')}" for t in true_items if t not in caught]}
    if partial is not None:
        heard = [t for t in caught if partial.get(item_key(t))]
        out["partial"] = len(heard)
        out["partial_rate"] = round(len(heard) / len(caught), 3) if caught else 0.0
    return out


# ------------------------------------------------------------------------------ fixtures

def export_fixture(project: Project, scan: dict, base: list[dict], dest: Path, name: str,
                   ctx: float = 3.0) -> dict:
    """Text + times only: the labels, the base words and every pass's words within ctx seconds
    of a labelled item (enough to recompute the vote)."""
    labels = load_labels(project)
    rows = [r for r in labels["items"].values() if r.get("label") in LABELS]
    pts = [(float(r["start"]) - ctx, float(r["end"]) + ctx) for r in rows]

    def near(w: dict) -> bool:
        return any(a <= float(w["start"]) <= b for a, b in pts)

    def slim(w: dict) -> dict:
        return {"start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3), "word": w["word"],
                "p": round(float(w.get("p", w.get("probability", 1.0)) or 0.0), 3), **({"spk": w["spk"]} if w.get("spk") else {})}

    readings = []
    for r in scan.get("readings") or []:
        ws = [slim(w) for w in r["words"] if near(w)]
        if any(a < r["w"][1] and b > r["w"][0] for a, b in pts):
            readings.append({"pass": r["pass"], "w": r["w"], "words": ws})
    data = {"version": VERSION, "name": name, "language": scan.get("language"),
            "labels": [{k: r.get(k) for k in ("start", "end", "word", "heard", "label", "note")} for r in
                       sorted(rows, key=lambda r: float(r["start"]))],
            "base": [slim(w) for w in base if near(w)], "readings": readings,
            "items": [{k: it.get(k) for k in ("start", "end", "word", "status", "score", "bleep", "aligned",
                                               "leak_first", "leak")} for it in scan.get("items", [])]}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
    return data


def fixture_metrics(fx: dict, strictness: str = "strict", learned: dict | None = None) -> dict:
    """Recompute detection from a fixture's text (no audio, no models) and score it."""
    from ..voices import swearscan
    from . import swears
    from .plan import BLEEP_MERGE_GAP, BLEEP_PAD, merge

    lang = fx.get("language")
    items = swearscan.combine(fx["base"], fx["readings"], lang, learned if learned is not None else {})
    pre, post = BLEEP_PAD[strictness]
    ranges = [(it["start"] - pre, it["end"] + post) for it in items if swears.bleeped(it, strictness)]
    return metrics(truth({"items": {str(i): r for i, r in enumerate(fx["labels"])}}), merge(ranges, BLEEP_MERGE_GAP))
