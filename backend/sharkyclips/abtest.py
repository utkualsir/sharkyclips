"""A/B hooks: two openings per clip, a predicted winner right away, and a real test on YouTube.

Hook styles (the "arms"):
  flash      the clip's peak moment for 1 s first, then the clip (+ the hook text)
  question   no flash; the hook text is a question
  cold_open  starts later, right before the action (the slow lead-in is skipped)
  statement  no flash; the AI's hook text as a statement

Variants: any clip gets two (A, B) with different styles, picked by Thompson sampling, so over
many clips every style is tried fairly; both are rendered (clips/ab/<id>_A.mp4, _B.mp4).

Pre-test (offline, immediately): a hook model scores the first 3 seconds of each rendered
variant: motion, loudness punch, face + smile on the facecam (OpenCV), on-screen text, trigger
words, the local AI's judgment (optional) and what this channel's real results say about the
style. The higher score is the predicted winner; the reasons are shown.

Real test (when YouTube is connected and uploads aren't locked to private): uploading from the
app picks the variant by Thompson sampling (and plain clips record their own style), 48 hours
after publishing the app fetches views + average view percentage by itself (YouTube
Analytics), and that becomes the style's reward. A clip is uploaded once, never twice.
Results: ~/.sharkyclips/hook_tests.json.
"""

from __future__ import annotations

import hashlib
import json
import random
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from . import config
from .procs import no_window
from .project import Project, read_json, write_json_atomic

STYLES = ("flash", "question", "cold_open", "statement")
FIRST = 3.0  # seconds of the opening that the hook model looks at
MIN_AGE_H = 48
REWARD_CAP = 150.0  # average view percentage that counts as a full reward (Shorts loop past 100 %)
MIN_SAMPLES = 3  # per style before the stats call a style better
COLD_OPEN_LEAD = 2.5  # the cold open starts this long before the peak
QUESTION_FALLBACK = {"en": "What happens next?", "tr": "Sonra ne oluyor?", "de": "Was passiert als Nächstes?",
                     "hu": "Mi történik ezután?", "ru": "Что будет дальше?", "ar": "ماذا سيحدث بعد ذلك؟",
                     "zh": "接下来会发生什么？"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ===================================================================== results store


def store_path() -> Path:
    return config.config_dir() / "hook_tests.json"


def load_store() -> dict:
    p = store_path()
    try:
        data = read_json(p) if p.is_file() else {}
    except Exception:  # noqa: BLE001
        data = {}
    return {"version": 1, "observations": [o for o in data.get("observations") or [] if o.get("style") in STYLES]}


def _save_store(data: dict) -> None:
    write_json_atomic(store_path(), data)


def reward_of(avg_view_percentage: float) -> float:
    return float(min(1.0, max(0.0, avg_view_percentage / REWARD_CAP)))


def record(obs: dict) -> bool:
    """One real result: {video_id, project_id, clip_id, variant, style, retention (avg view %),
    views, reward, published_at, simulated?}. Each video counts once."""
    data = load_store()
    if any(o["video_id"] == obs["video_id"] for o in data["observations"]):
        return False
    obs = {**obs, "reward": round(float(obs.get("reward", reward_of(obs.get("retention") or 0))), 4),
           "fetched_at": obs.get("fetched_at") or _now().isoformat(timespec="seconds")}
    data["observations"].append(obs)
    _save_store(data)
    return True


def clear_simulated() -> int:
    data = load_store()
    keep = [o for o in data["observations"] if not o.get("simulated")]
    n = len(data["observations"]) - len(keep)
    data["observations"] = keep
    _save_store(data)
    return n


def posterior(style: str, observations: list[dict]) -> tuple[float, float, int]:
    """Beta(a, b) of the style's reward (fractional successes), and the sample size."""
    a = b = 1.0
    n = 0
    for o in observations:
        if o["style"] == style:
            r = float(o["reward"])
            a += r
            b += 1.0 - r
            n += 1
    return a, b, n


def thompson(styles: list[str], observations: list[dict], rng: random.Random) -> dict[str, float]:
    return {s: rng.betavariate(*posterior(s, observations)[:2]) for s in styles}


def stats(observations: list[dict] | None = None, draws: int = 20000, seed: int = 7) -> dict:
    """Per style: sample size, mean retention, the reward's 90 % credible interval and the
    probability that it is the best style (Monte Carlo over the posteriors)."""
    from scipy.stats import beta

    obs = load_store()["observations"] if observations is None else observations
    rng = np.random.default_rng(seed)
    samples = {}
    rows = []
    for s in STYLES:
        a, b, n = posterior(s, obs)
        samples[s] = rng.beta(a, b, draws)
        ret = [float(o.get("retention") or 0) for o in obs if o["style"] == s]
        views = [int(o.get("views") or 0) for o in obs if o["style"] == s]
        rows.append({"style": s, "n": n, "mean_reward": round(a / (a + b), 4),
                     "ci90": [round(float(beta.ppf(0.05, a, b)), 4), round(float(beta.ppf(0.95, a, b)), 4)],
                     "mean_retention": round(float(np.mean(ret)), 1) if ret else None,
                     "median_views": int(np.median(views)) if views else None})
    stack = np.vstack([samples[s] for s in STYLES])
    best = np.bincount(np.argmax(stack, axis=0), minlength=len(STYLES)) / draws
    for row, p in zip(rows, best):
        row["p_best"] = round(float(p), 3)
    total = len(obs)
    leader = max(rows, key=lambda r: r["p_best"])
    enough = all(r["n"] >= MIN_SAMPLES for r in rows if r["n"]) and sum(1 for r in rows if r["n"] >= MIN_SAMPLES) >= 2
    verdict = None
    if enough and leader["p_best"] >= 0.9:
        verdict = {"style": leader["style"], "confidence": leader["p_best"]}
    return {"styles": sorted(rows, key=lambda r: -r["p_best"]), "observations": total, "verdict": verdict,
            "min_samples": MIN_SAMPLES, "reward_cap": REWARD_CAP}


# ===================================================================== variants


def style_of(opts: dict, hook_text: str) -> str:
    """The hook style of a plain rendered clip (so ordinary uploads teach the test too)."""
    if opts.get("hook_flash"):
        return "flash"
    t = (hook_text or "").strip()
    if t.endswith(("?", "？", "؟")):
        return "question"
    return "statement"


def applicable(cand: dict) -> list[str]:
    out = ["flash", "question", "statement"]
    peak = float(cand.get("peak") or cand["start"])
    if peak - float(cand["start"]) >= COLD_OPEN_LEAD + 3.5 and float(cand["end"]) - peak >= 4.0:
        out.insert(2, "cold_open")
    return out


def pick_pair(cand: dict, observations: list[dict] | None = None, seed: str | None = None) -> list[str]:
    """Two different styles for this clip: the top two Thompson samples (seeded per clip and
    per amount of data, so asking again gives the same pair until new results arrive)."""
    obs = load_store()["observations"] if observations is None else observations
    styles = applicable(cand)
    rng = random.Random(f"{seed or cand['id']}:{len(obs)}")
    draw = thompson(styles, obs, rng)
    pair = sorted(styles, key=lambda s: -draw[s])[:2]
    return pair


def question_text(cand: dict, lang: str | None) -> str:
    """A question hook: one of the AI's question titles, else a neutral one."""
    pub = cand.get("publish") or {}
    for t, st in zip(pub.get("titles") or [], pub.get("title_styles") or []):
        t = " ".join(str(t).split())
        if st == "question" and len(t) <= 60:
            return t
    for t in pub.get("titles") or []:
        t = " ".join(str(t).split())
        if t.endswith(("?", "？", "؟")) and len(t) <= 60:
            return t
    return QUESTION_FALLBACK.get(lang or "en", QUESTION_FALLBACK["en"])


def cold_open_start(cand: dict, words: list[dict]) -> float:
    from .story import snap

    peak = float(cand.get("peak") or cand["start"])
    t = max(float(cand["start"]), peak - COLD_OPEN_LEAD)
    s, _e = snap(words, t, float(cand["end"]), float(cand["start"]), float(cand["end"]))
    return s


def variant_spec(style: str, cand: dict, statement: str, lang: str | None, words: list[dict]) -> dict:
    spec = {"style": style, "hook": True, "hook_flash": style == "flash", "start": float(cand["start"]),
            "hook_text": statement}
    if style == "question":
        spec["hook_text"] = question_text(cand, lang)
    if style == "cold_open":
        spec["start"] = cold_open_start(cand, words)
    return spec


def ab_path(project: Project) -> Path:
    return project.dir / "ab.json"


def load_ab(project: Project) -> dict:
    p = ab_path(project)
    try:
        return (read_json(p).get("clips") or {}) if p.is_file() else {}
    except Exception:  # noqa: BLE001
        return {}


def save_ab(project: Project, cid: str, entry: dict | None) -> None:
    clips = load_ab(project)
    if entry is None:
        clips.pop(cid, None)
    else:
        clips[cid] = entry
    write_json_atomic(ab_path(project), {"version": 1, "clips": clips})


# ===================================================================== the hook model (pre-test)


def _gray(path: Path, a: float, b: float | None, fps: int = 8, w: int = 27, h: int = 48) -> np.ndarray | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostats", "-ss", f"{a:.3f}"]
    if b is not None:
        cmd += ["-t", f"{b - a:.3f}"]
    cmd += ["-i", str(path), "-an", "-vf", f"fps={fps},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "pipe:1"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=300, **no_window()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    n = len(out) // (w * h)
    return np.frombuffer(out[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32) / 255 if n else None


def _frame(path: Path, t: float, box: tuple[float, float, float, float] | None, width: int = 320) -> np.ndarray | None:
    """One BGR frame of the source at t (optionally only the facecam box, normalized x y w h)."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    vf = f"crop=iw*{box[2]:.4f}:ih*{box[3]:.4f}:iw*{box[0]:.4f}:ih*{box[1]:.4f}," if box else ""
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(path), "-frames:v", "1",
           "-vf", vf + f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "pipe:1"]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=60, **no_window()).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    import cv2

    return cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)


def face_emotion(frames: list[np.ndarray]) -> dict | None:
    """Share of frames with a face, and with a smile on it (OpenCV's bundled Haar models)."""
    import cv2

    base = Path(cv2.data.haarcascades)
    face_m = cv2.CascadeClassifier(str(base / "haarcascade_frontalface_default.xml"))
    smile_m = cv2.CascadeClassifier(str(base / "haarcascade_smile.xml"))
    if face_m.empty() or not frames:
        return None
    faces = smiles = 0
    for img in frames:
        g = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        found = face_m.detectMultiScale(g, 1.15, 5, minSize=(max(24, g.shape[1] // 10),) * 2)
        if len(found):
            faces += 1
            x, y, w, h = max(found, key=lambda f: f[2] * f[3])
            mouth = g[y + h // 2: y + h, x: x + w]
            if len(smile_m.detectMultiScale(mouth, 1.7, 18, minSize=(max(12, w // 5), max(8, h // 10)))):
                smiles += 1
    return {"face": round(faces / len(frames), 2), "smile": round(smiles / len(frames), 2)}


def opening_source_times(spec: dict, cand: dict, flash_start: float) -> list[tuple[float, float]]:
    """Source ranges shown in the first 3 seconds of a variant."""
    if spec["hook_flash"]:
        return [(flash_start, flash_start + 1.0), (spec["start"], spec["start"] + FIRST - 1.0)]
    return [(spec["start"], spec["start"] + FIRST)]


def features(project: Project, video: Path, spec: dict, cand: dict, facecam: dict | None,
             lang: str | None, mode: str | None, flash_start: float) -> dict:
    """What the hook model looks at, measured on the rendered variant (+ its source moments)."""
    from .edit import loudness
    from .edit.music import decode
    from .edit.plan import transcript_words
    from .highlights.modes import get_mode
    from .highlights.signals.keywords import normalize, trigger_phrases

    f: dict = {}
    allf = _gray(video, 0.0, None, fps=6)
    if allf is not None and len(allf) > 3:
        steps = np.mean(np.abs(np.diff(allf, axis=0)), axis=(1, 2))
        k = max(1, int(FIRST * 6))
        f["motion"] = round(float(np.mean(steps[:k]) / (np.mean(steps) + 1e-4)), 3)
    try:
        y = decode(video, 0.0, None, sr=48000, channels=2)
        if len(y) > 48000 * FIRST:
            f["loudness"] = round(loudness.integrated_lufs(y[: int(48000 * FIRST)]) - loudness.integrated_lufs(y), 2)
    except Exception:  # noqa: BLE001
        pass
    ranges = opening_source_times(spec, cand, flash_start)
    if facecam and project.source_path is not None:
        box = (float(facecam["x"]), float(facecam["y"]), float(facecam["w"]), float(facecam["h"]))
        times = [a + (b - a) * q for a, b in ranges for q in (0.15, 0.5, 0.85)]
        frames = [fr for t in times if (fr := _frame(project.source_path, t, box)) is not None]
        fe = face_emotion(frames)
        if fe is not None:
            f.update(fe)
    text = (spec.get("hook_text") or "").strip() if spec.get("hook") else ""
    nwords = len(text.split()) if lang not in ("zh", "ja") else max(1, len(text) // 2)
    f["text"] = {"present": bool(text), "words": nwords if text else 0,
                 "question": text.endswith(("?", "？", "؟")), "number": any(ch.isdigit() for ch in text)}
    spoken = []
    for a, b in ranges:
        ws, _l = transcript_words(project, a, b)
        spoken += [w["word"] for w in ws]
    f["opening_words"] = " ".join(spoken)[:300]
    phrases = trigger_phrases(lang or "en", get_mode(mode or "gaming").keyword_categories) if lang else {}
    norm = f" {normalize(' '.join(spoken))} "
    hits = [(p, w) for k, (p, w) in phrases.items() if f" {k} " in norm]
    f["triggers"] = sorted({p for p, _w in hits})[:5]
    f["trigger_weight"] = round(max([w for _p, w in hits] or [0.0]), 2)
    react = {"laughter", "scream", "shouting", "cheering", "loudness_spike", "keyword"}
    f["emotion_events"] = sorted({str(r.get("code")) for r in cand.get("reasons") or []
                                  if str(r.get("code")) in react
                                  and any(a - 0.3 <= float(r.get("t", -9)) <= b + 0.3 for a, b in ranges)})
    return f


JUDGE_SCHEMA = {"type": "object", "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 10},
                                                 "why": {"type": "string", "maxLength": 160}},
                "required": ["score", "why"]}


def llm_judge(model, project: Project, cand: dict, spec: dict, feats: dict, lang: str | None) -> dict | None:
    """The local AI rates the first 3 seconds (cached per opening)."""
    from .analyze import SYSTEM, lang_name

    what = (cand.get("llm") or {}).get("what_happens") or ""
    opening = ("It starts with a 1-second flash of the peak moment, then the clip from its start. "
               if spec["hook_flash"] else "")
    if spec["style"] == "cold_open":
        opening += "It skips the slow lead-in and starts right before the action. "
    key = hashlib.sha1(json.dumps([model.model, what, opening, spec.get("hook_text"), feats.get("opening_words")],
                                  ensure_ascii=False).encode()).hexdigest()[:16]
    path = project.cache_dir / "llm" / f"hook_{key}.json"
    if path.is_file():
        return read_json(path)
    prompt = (f"A short vertical video. What happens in it: {what}\n{opening}On-screen hook text for the first "
              f"seconds: \"{spec.get('hook_text') or '(none)'}\". Words heard in the first 3 seconds: "
              f"\"{feats.get('opening_words') or '(none)'}\".\nRate 0-10 how likely a viewer scrolling Shorts keeps "
              f"watching after these first 3 seconds. why: one short reason in {lang_name(lang or 'en')}.")
    d = model.json(SYSTEM, prompt, JUDGE_SCHEMA, temperature=0.3, num_predict=200)
    write_json_atomic(path, d)
    return d


def score(feats: dict, style: str, observations: list[dict], judge: dict | None = None) -> dict:
    """0-100 and the reasons (each feature's points, biggest first)."""
    parts: list[dict] = []

    def add(code: str, pts: float, value=None) -> None:
        if abs(pts) >= 0.5:
            parts.append({"code": code, "points": round(pts, 1), "value": value})

    if feats.get("motion") is not None:
        add("motion", float(np.clip((feats["motion"] - 1.0) * 14, -10, 12)), feats["motion"])
    if feats.get("loudness") is not None:
        add("loudness", float(np.clip(feats["loudness"] * 1.6, -8, 10)), feats["loudness"])
    if feats.get("face") is not None:
        add("face", 6 * feats["face"], feats["face"])
        add("smile", 9 * feats.get("smile", 0.0), feats.get("smile"))
    t = feats.get("text") or {}
    if t.get("present"):
        add("text_length", 6.0 if 2 <= t["words"] <= 7 else (2.0 if t["words"] <= 10 else -3.0), t["words"])
        add("text_question", 3.0 if t.get("question") else 0.0)
        add("text_number", 2.0 if t.get("number") else 0.0)
    else:
        add("no_text", -6.0)
    if feats.get("triggers"):
        add("trigger_words", 8 * min(1.0, feats.get("trigger_weight") or 0.5), ", ".join(feats["triggers"]))
    if feats.get("emotion_events"):
        add("reaction", 4.0 + 2.0 * min(2, len(feats["emotion_events"]) - 1), ", ".join(feats["emotion_events"]))
    if judge is not None:
        add("ai_judgment", (float(judge["score"]) - 5.0) * 3.0, judge["score"])
    a, b, n = posterior(style, observations)
    if n:
        everyone = [float(o["reward"]) for o in observations]
        conf = n / (n + 5.0)
        add("channel", (a / (a + b) - float(np.mean(everyone))) * 80 * conf, n)
    total = float(np.clip(50 + sum(p["points"] for p in parts), 0, 100))
    return {"score": round(total, 1), "reasons": sorted(parts, key=lambda p: -abs(p["points"]))}


# ===================================================================== real test


def real_test_status() -> dict:
    """Whether uploads can be tested for real, or only the pre-test is used (and why)."""
    from . import youtube

    if not youtube.connected():
        return {"active": False, "reason": "not_connected"}
    lock = youtube.uploads_locked()
    if lock:
        return {"active": False, "reason": "locked_private", "since": lock.get("at")}
    if not youtube.has_analytics():
        return {"active": False, "reason": "no_analytics"}
    return {"active": True, "reason": None}


def choose_for_upload(entry: dict, observations: list[dict] | None = None, rng: random.Random | None = None,
                      active: bool | None = None) -> dict:
    """Which variant to upload: Thompson sampling between the two styles when the real test runs
    (each style keeps getting tried while it might be the best), else the pre-test's winner."""
    obs = load_store()["observations"] if observations is None else observations
    if active is None:
        active = real_test_status()["active"]
    labels = [k for k in ("A", "B") if k in (entry.get("variants") or {})]
    if not labels:
        return {"label": None, "how": None}
    if not active or len(labels) < 2:
        return {"label": entry.get("winner") or labels[0], "how": "pretest"}
    rng = rng or random.Random()
    draws = {k: rng.betavariate(*posterior(entry["variants"][k]["style"], obs)[:2]) for k in labels}
    return {"label": max(labels, key=lambda k: draws[k]), "how": "bandit"}


def due_uploads(projects: list[Project], now: datetime | None = None) -> list[tuple[Project, str, dict]]:
    """App uploads with a hook style, public for 48 h or more, not learned from yet."""
    from .web import state

    now = now or _now()
    out = []
    for p in projects:
        for cid, ups in state.load_uploads(p).items():
            for u in ups:
                if not u.get("hook_style") or u.get("hook_learned") or not u.get("video_id") or u.get("missing"):
                    continue
                try:  # a video that wasn't public yet is asked again once a day, not every hour
                    checked = datetime.fromisoformat(str(u.get("hook_checked_at")).replace("Z", "+00:00"))
                    if now - checked < timedelta(hours=24):
                        continue
                except ValueError:
                    pass
                when = u.get("published_at") or u.get("publish_at") or u.get("uploaded_at")
                try:
                    t = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if now - t >= timedelta(hours=MIN_AGE_H):
                    out.append((p, cid, u))
    return out


def fetch_and_learn(projects: list[Project], now: datetime | None = None, api=None) -> dict:
    """Fetch views + retention of the due uploads and teach the bandit. api: the YouTube module
    (tests pass a fake). Uploads still private after their publish time = locked by Google."""
    from . import youtube as yt_mod
    from .web import state

    api = api or yt_mod
    due = due_uploads(projects, now)
    if not due:
        return {"due": 0, "learned": 0, "locked": False}
    ids = [u["video_id"] for _p, _c, u in due]
    st = api.video_stats(ids)
    public = [v for v in ids if (st.get(v) or {}).get("privacy") == "public"]
    locked = False
    stamp = (now or _now()).isoformat(timespec="seconds")
    for p, cid, u in due:
        s = st.get(u["video_id"])
        state.patch_upload(p, cid, u["video_id"], {"hook_checked_at": stamp})
        if s is None:
            state.patch_upload(p, cid, u["video_id"], {"missing": True})
            continue
        wanted = (u.get("requested_privacy") or u.get("privacy")) in ("public", "unlisted") or u.get("publish_at")
        if s.get("privacy") == "private" and wanted:
            locked = True
            api.mark_locked(u["video_id"])
    learned = 0
    if public:
        start = min((st[v].get("published_at") or "")[:10] for v in public) or (now or _now()).date().isoformat()
        ret = api.retention(public, start)
        for p, cid, u in due:
            v = u["video_id"]
            if v not in public or v not in ret:
                continue
            r = ret[v]
            if record({"video_id": v, "project_id": p.id, "clip_id": cid, "variant": u.get("hook_variant"),
                       "style": u["hook_style"], "retention": r["avg_view_percentage"], "views": r["views"],
                       "reward": reward_of(r["avg_view_percentage"]), "published_at": st[v].get("published_at"),
                       "simulated": bool(u.get("simulated"))}):
                learned += 1
            state.patch_upload(p, cid, v, {"hook_learned": True, "retention": r["avg_view_percentage"],
                                           "views": r["views"]})
    return {"due": len(due), "learned": learned, "locked": locked}
