"""Cover studio (1.2.18): four AI cover pictures per clip, in 9:16 and 16:9, one click to choose.

State per clip: <project>/cache/covers/ai/<clip>/state.json
  {"prompt", "seeds": [4 ints], "files": {"tall": {seed: name}, "wide": {...}},
   "chosen": {"tall": seed, "wide": seed}, "made_with": "gpu"|"cpu", "made_at"}
The pictures have no text: the cover text is drawn by cover.make_cover(kind="ai") in the app style,
so changing the text never needs a new picture.
"""

from __future__ import annotations

import random
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import imagegen
from .errors import SharkyClipsError
from .project import Project, read_json, write_json_atomic

FRAMES = ("tall", "wide")
_lock = threading.RLock()


def folder(project: Project, cid: str) -> Path:
    return project.cache_dir / "covers" / "ai" / cid


def load(project: Project, cid: str) -> dict:
    p = folder(project, cid) / "state.json"
    try:
        data = read_json(p) if p.is_file() else {}
    except (OSError, ValueError):
        data = {}
    files = {f: {str(k): v for k, v in ((data.get("files") or {}).get(f) or {}).items()} for f in FRAMES}
    chosen = {f: v for f, v in (data.get("chosen") or {}).items() if f in FRAMES and v is not None}
    return {"prompt": data.get("prompt") or "", "seeds": [int(s) for s in data.get("seeds") or []],
            "files": files, "chosen": chosen, "made_with": data.get("made_with"), "made_at": data.get("made_at")}


def save(project: Project, cid: str, data: dict) -> None:
    folder(project, cid).mkdir(parents=True, exist_ok=True)
    write_json_atomic(folder(project, cid) / "state.json", data)


def chosen_file(project: Project, cid: str, frame: str) -> Path | None:
    data = load(project, cid)
    seed = data["chosen"].get(frame)
    name = data["files"].get(frame, {}).get(str(seed)) if seed is not None else None
    path = folder(project, cid) / name if name else None
    return path if path is not None and path.is_file() else None


def has_chosen(project: Project, cid: str, frame: str) -> bool:
    return chosen_file(project, cid, frame) is not None


def option_file(project: Project, cid: str, frame: str, seed: int) -> Path | None:
    name = load(project, cid)["files"].get(frame, {}).get(str(seed))
    path = folder(project, cid) / name if name else None
    return path if path is not None and path.is_file() else None


def prompt_for(project: Project, cand: dict) -> str:
    """The AI's cover idea (analysis), else a plain description of the clip."""
    pub = cand.get("publish") or {}
    if pub.get("cover_prompt"):
        return str(pub["cover_prompt"])
    info = cand.get("llm") or {}
    meta = project.load_meta()
    topic = info.get("game_or_topic") or meta.get("game") or meta.get("title") or ""
    what = info.get("what_happens") or (cand.get("text") or "")[:160]
    mode = meta.get("mode") or "gaming"
    kind = {"study": "a study / lesson video", "music": "a music performance"}.get(mode, "a gaming stream highlight")
    return (f"Cinematic key art for {kind}: {topic}. {what}. dramatic lighting, high contrast, "
            "deep navy and gold color grade, sharp focus on the subject")


def view(project: Project, cid: str) -> dict:
    data = load(project, cid)
    opts = {f: [s for s in data["seeds"] if str(s) in data["files"].get(f, {})
                and (folder(project, cid) / data["files"][f][str(s)]).is_file()] for f in FRAMES}
    return {**data, "options": opts, "plan": imagegen.plan()}


def make(project: Project, cand: dict, frames: list[str], on_progress=None, new: bool = True,
         use: str | None = None, build: str | None = None) -> dict:
    """Make OPTIONS pictures per frame (new seeds unless new=False and some exist). Chooses the
    first option of a frame that had none chosen yet."""
    frames = [f for f in FRAMES if f in frames] or ["tall"]
    cid = cand["id"]
    p = imagegen.plan()
    use = use or p["use"]
    build = build or p["build"]
    if use == "fallback" or not build:
        raise SharkyClipsError("This computer can't make AI covers.", "The facecam frame is used as the cover.")
    with _lock:
        data = load(project, cid)
        if new or len(data["seeds"]) < imagegen.OPTIONS:
            base = random.randrange(1, 2**31 - 1 - imagegen.OPTIONS)
            data["seeds"] = [base + i for i in range(imagegen.OPTIONS)]  # consecutive: one sd-cli batch
            data["files"] = {f: {} for f in FRAMES}
        data["prompt"] = prompt_for(project, cand)
        save(project, cid, data)
    total = len(frames)
    for i, frame in enumerate(frames):
        def prog(stage: str, frac, i=i) -> None:
            if on_progress:
                on_progress(stage, None if frac is None else (i + frac) / total if stage == "making_covers" else frac)

        prompt = imagegen.image_prompt(data["prompt"], frame)
        files = imagegen.generate(prompt, frame, data["seeds"], folder(project, cid), use=use, build=build,
                                  on_progress=prog)
        with _lock:
            cur = load(project, cid)
            cur["files"][frame] = {str(s): f.name for s, f in zip(data["seeds"], files)}
            if cur["chosen"].get(frame) not in data["seeds"]:
                cur["chosen"][frame] = data["seeds"][0]
            cur.update(made_with=use, made_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            save(project, cid, cur)
    _prune(project, cid)
    return view(project, cid)


def choose(project: Project, cid: str, frame: str, seed: int) -> dict:
    if frame not in FRAMES:
        raise SharkyClipsError(f"Unknown cover size '{frame}'.")
    with _lock:
        data = load(project, cid)
        if str(seed) not in data["files"].get(frame, {}):
            raise SharkyClipsError("This cover picture doesn't exist any more.", "Make the AI covers again.")
        data["chosen"][frame] = int(seed)
        save(project, cid, data)
    return view(project, cid)


def _prune(project: Project, cid: str) -> None:
    """Pictures of older rounds go, except the chosen ones."""
    data = load(project, cid)
    keep = {n for f in FRAMES for n in data["files"].get(f, {}).values()} | {"state.json"}
    for f in FRAMES:  # a chosen picture from an older round stays until another one is chosen
        seed = data["chosen"].get(f)
        for p in folder(project, cid).glob(f"{seed}_{f}.png"):
            keep.add(p.name)
            data["files"].setdefault(f, {})[str(seed)] = p.name
    for p in folder(project, cid).iterdir():
        if p.name not in keep:
            p.unlink(missing_ok=True)
    save(project, cid, data)
