"""Game awareness: read the game's HUD (and optionally its sounds) to find kills, multikills,
objectives and result screens. Used by the "game" highlight signal.

    resolve(project)        -> which game (auto-detected from title/transcript, or the user's pick)
    scan(project, game)     -> raw HUD observations (cached per video + preset)
    game_events(project)    -> events [{t, code, value, strength, start, end, source}]
    probe(project, t, game) -> OCR every region of one frame (calibration in the UI)
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable

from ..project import Project, read_json, write_json_atomic
from . import events as events_mod
from . import presets

SCAN_VERSION = 6
DETECT_VERSION = 2  # bump when detect() changes (results are remembered per project)
CHOICES = ("auto", "delta_force", "lol", "other")
_GLOSSARY_NAMES = {"Delta Force": "delta_force", "League of Legends": "lol"}
# Words streamers say while playing (EN + TR), used only to recognize the game (not for titles).
# Matched as word starts, so Turkish suffixes still count ("minyonlari", "kuleye").
HINTS = {
    "lol": ["lane", "minyon", "minion", "totem", "ward", "nexus", "inhib", "kule", "jungle", "ormanci",
            "baron", "ejder", "drake", "herald", "sampiyon", "champion", "teemo", "alistar", "yasuo",
            "smite", "ignite", "flash", "farm", "gank"],
    "delta_force": ["operator", "operasyon", "tahliye", "extract", "warfare", "havoc", "zero dam",
                    "layali", "space city", "brakkesh", "revive", "kurtar", "zirh", "armor", "dron"],
}


# ------------------------------------------------------------------ which game


def _norm_words(text: str) -> list[str]:
    return presets.normalize(text).split()


def detect(title: str, transcript: dict | None) -> tuple[str | None, str]:
    """(game id or None, why). Title aliases first, then game terms the streamer says."""
    from ..titles import glossary

    g = glossary.detect_game(title)
    if g in _GLOSSARY_NAMES:
        return _GLOSSARY_NAMES[g], f"title: {g}"
    if g:
        return None, f"title: {g} (no HUD preset)"
    text = " ".join(s.get("text", "") for s in (transcript or {}).get("segments", []))
    words = _norm_words(title) + _norm_words(text)
    vocab = set(words)
    games = glossary._games()
    counts: dict[str, set[str]] = {}
    for name, gid in _GLOSSARY_NAMES.items():
        hits = set()
        for term in games.get(name, {}).get("terms", []) + games.get(name, {}).get("aliases", []) + HINTS[gid]:
            t = presets.normalize(term)
            if len(t) < 4 or " " in t:
                if " " in t and f" {t} " in f" {' '.join(words)} ":
                    hits.add(t)
                continue
            # Turkish adds suffixes ("dariusa", "baronu"): a word that starts with the term counts.
            if t in vocab or any(w.startswith(t) and len(w) - len(t) <= 4 for w in vocab):
                hits.add(t)
        counts[gid] = hits
    best = max(counts, key=lambda k: len(counts[k]))
    other = max((len(v) for k, v in counts.items() if k != best), default=0)
    if len(counts[best]) >= 4 and len(counts[best]) >= 2 * other:
        return best, "transcript: " + ", ".join(sorted(counts[best])[:6])
    return None, "not recognized"


def _mentioned(project: Project, name: str) -> bool:
    words = _norm_words(project.load_meta().get("title", ""))
    if project.transcript_path.is_file():
        words += _norm_words(" ".join(s.get("text", "") for s in read_json(project.transcript_path).get("segments", [])))
    n = presets.normalize(name).replace(" ", "")
    return any(w.startswith(n) and len(w) - len(n) <= 4 for w in words)


def champion_name(scan_result: dict) -> str | None:
    c = scan_result.get("champion") or {}
    return None if c.get("unconfirmed") else c.get("name")


def resolve(project: Project) -> dict:
    meta = project.load_meta()
    choice = meta.get("game") or "auto"
    # Detection reads the whole transcript: remember it per transcript version.
    tkey = f"{DETECT_VERSION}|{(meta.get('transcript') or {}).get('words')}|{meta.get('title')}"
    cached = meta.get("game_detect") or {}
    if cached.get("key") == tkey:
        detected, why = cached.get("game"), cached.get("why", "")
    else:
        transcript = read_json(project.transcript_path) if project.transcript_path.is_file() else None
        detected, why = detect(meta.get("title", ""), transcript)
        if transcript is not None:
            meta["game_detect"] = {"key": tkey, "game": detected, "why": why}
            project.save_meta(meta)
    game = detected if choice == "auto" else (None if choice == "other" else choice)
    return {"choice": choice, "game": game, "detected": detected, "why": why,
            "name": presets.GAMES.get(game or "", None)}


# ------------------------------------------------------------------ scanning


def _cache_path(project: Project) -> Path:
    return project.cache_dir / "game" / "scan.json"


def scan_key(project: Project, game: str) -> str:
    if project.source_path is None:
        raise RuntimeError("the project has no video file")
    st = project.source_path.stat()
    return f"{SCAN_VERSION}|{game}|{st.st_size}|{presets.digest(game)}"


def load_scan(project: Project) -> dict | None:
    path = _cache_path(project)
    if not path.is_file():
        return None
    try:
        return read_json(path)
    except Exception:
        return None


def scan(project: Project, game: str, on_progress: Callable[[float, float], None] | None = None,
         force: bool = False) -> dict:
    """Read the HUD of the whole video (cached). on_progress(done_seconds, duration)."""
    from .. import memory
    from . import champions, frames, ocr
    from .hud import Scanner

    key = scan_key(project, game)
    cached = load_scan(project)
    if cached and cached.get("key") == key and not force:
        return cached
    if not ocr.installed():
        raise RuntimeError("OCR is not installed (python -m pip install rapidocr)")
    meta = project.load_meta()
    width, height = int(meta.get("width") or 0), int(meta.get("height") or 0)
    duration = float(meta.get("duration") or 0)
    if not (width and height and duration):
        raise RuntimeError("video size unknown")
    w, h = frames.out_size(width, height)
    boxes = presets.scaled_boxes(game, w, h)
    templates = presets.load_templates(game, h)

    try:  # free the GPU for the decoder (the LLM may still sit there from an earlier step)
        from .. import llm

        llm.unload_all()
    except Exception:
        pass

    t0 = time.perf_counter()
    scanners: list[Scanner] = []
    lock = threading.Lock()
    workers = int(os.environ.get("CLIPFORGE_GAME_WORKERS") or 0) or (3 if frames.cuda_decode_available() else 2)
    cores = os.cpu_count() or 4
    processes = max(1, min(4, cores // 4))

    def load_reader():
        return ocr.PoolReader(processes=processes, threads=2 if cores >= 8 else 1)

    with memory.exclusive_model("game-ocr", load_reader, lambda r: r.close()) as reader:
        def make_worker(i: int, start: float, end: float):
            sc = Scanner(game, boxes, reader, start, end, templates)
            with lock:
                scanners.append(sc)
            return sc.handle

        info = frames.scan_parallel(str(project.source_path), duration, width, height, make_worker,
                                    on_progress=(lambda d: on_progress(d, duration)) if on_progress else None,
                                    workers=workers)
        ocr_calls, ocr_seconds = reader.calls, reader.seconds

    obs = sorted((o for sc in scanners for o in sc.obs), key=lambda o: o["t"])
    reads = sorted((r for sc in scanners for r in sc.reads), key=lambda r: r["t"])
    champion = None
    if game == "lol":
        try:
            champion = champions.identify([p for sc in scanners for p in sc.portraits])
        except Exception:
            champion = None
        # Skins change the portrait a lot, so a match is only trusted when the name is also in
        # the title or said in the stream: a wrong champion in a title is worse than none.
        if champion and not _mentioned(project, champion["name"]):
            champion = {**champion, "unconfirmed": True}
    elapsed = time.perf_counter() - t0
    result = {
        "key": key, "version": SCAN_VERSION, "game": game, "duration": duration,
        "frame_size": [w, h], "boxes": {k: [b.x, b.y, b.w, b.h] for k, b in boxes.items()},
        "obs": obs, "reads": reads, "champion": champion,
        "stats": {**info, "seconds": round(elapsed, 1), "frames": int(duration * frames.FPS),
                  "ocr_calls": ocr_calls, "ocr_seconds": round(ocr_seconds, 1), "speed": round(duration / max(elapsed, 0.01), 1)},
    }
    path = _cache_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, result, compact=True)
    return result


def sound_matches(project: Project, game: str) -> tuple[list[dict], dict]:
    """Reference-clip matches (cached separately: adding a clip doesn't rescan the video)."""
    from . import sounds

    if not sounds.reference_files(game):
        return [], {"folder": str(sounds.sounds_dir(game)), "clips": [], "ignored": []}
    key = f"{game}|{sounds.digest(game)}|{project.audio_path.stat().st_size}"
    path = project.cache_dir / "game" / "sounds.json"
    try:
        c = read_json(path)
        if c.get("key") == key:
            return c["matches"], c["info"]
    except Exception:
        pass
    meta = project.load_meta()
    matches, info = sounds.find(game, project.audio_path, float(meta.get("duration") or 0),
                                set(events_mod.STRENGTH))
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, {"key": key, "matches": matches, "info": info})
    return matches, info


def combine(game: str, scan_result: dict, sound_hits: list[dict]) -> list[dict]:
    evs = events_mod.build_events(game, scan_result.get("obs", []))
    for m in sound_hits:
        # A sound confirms a screen event of the same kind nearby; otherwise it is its own event.
        near = [e for e in evs if e["code"] == m["code"] and abs(e["t"] - m["t"]) <= 6]
        if near:
            for e in near:
                e["source"] = e["source"] + "+sound"
            continue
        strength = events_mod.STRENGTH.get(m["code"], 0.3)
        evs.append({"t": m["t"], "code": m["code"], "strength": strength, "start": m["t"], "end": m["t"],
                    "source": "sound", "value": m["file"]})
    champ = champion_name(scan_result)
    if champ:
        for e in evs:
            if e["code"].startswith("lol_") and e["code"] not in ("lol_victory", "lol_defeat"):
                e["champion"] = champ
    return sorted(evs, key=lambda e: e["t"])


def game_events(project: Project) -> dict | None:
    """Events of the last scan (for the UI); None if the project was never scanned."""
    sc = load_scan(project)
    if not sc:
        return None
    try:
        hits, info = sound_matches(project, sc["game"])
    except Exception:
        hits, info = [], {}
    return {"game": sc["game"], "events": combine(sc["game"], sc, hits), "sounds": info}


# ------------------------------------------------------------------ calibration


def probe(project: Project, t: float, game: str) -> dict:
    """OCR every region of the frame at t (with this computer's current boxes)."""
    import subprocess

    import cv2
    import numpy as np

    from . import frames, ocr

    meta = project.load_meta()
    w, h = frames.out_size(int(meta["width"]), int(meta["height"]))
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i",
                        str(project.source_path), "-frames:v", "1", "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                        "-pix_fmt", "gray", "-"], capture_output=True, timeout=60)
    if r.returncode != 0 or len(r.stdout) < w * h:
        raise RuntimeError("could not read that frame")
    img = np.frombuffer(r.stdout[: w * h], np.uint8).reshape(h, w)
    from .hud import read_lines

    reader = ocr.Reader(threads=4)
    templates = presets.load_templates(game, h)
    out = {}
    for name, box in presets.scaled_boxes(game, w, h).items():
        if name in ("portrait", "hud"):
            continue
        crop = box.crop(img)
        if name == "icons":  # template matches, not text
            scores = {k: float(cv2.matchTemplate(crop, tm, cv2.TM_CCOEFF_NORMED).max())
                      for k, tm in templates.items() if crop.shape[0] >= tm.shape[0] and crop.shape[1] >= tm.shape[1]}
            out[name] = {"text": ", ".join(f"{k} {v:.2f}" for k, v in scores.items()),
                         "events": [f"df_{k}" if k != "skull" else "df_kill" for k, v in scores.items() if v >= 0.8]}
            continue
        if name in ("kda", "team"):
            big = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC) if crop.shape[0] < 24 else crop
            texts = [reader.line(big)[0]]
        elif name in ("lines", "announce"):
            texts = read_lines(reader, crop)
        else:
            texts = reader.area(crop, min_score=0.5)
        joined = " ".join(texts)
        out[name] = {"text": joined, "events": presets.match_rules(game, name, joined)}
    return {"t": t, "regions": out}


def save_choice(project: Project, choice: str) -> None:
    if choice not in CHOICES:
        raise ValueError(choice)
    meta = project.load_meta()
    meta["game"] = choice
    project.save_meta(meta)


def known_codes() -> list[str]:
    return sorted(events_mod.STRENGTH)


__all__ = ["CHOICES", "detect", "resolve", "scan", "game_events", "probe", "save_choice", "combine",
           "sound_matches", "load_scan", "known_codes"]
