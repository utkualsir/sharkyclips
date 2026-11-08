"""The bleep guarantee (1.2.31): after every render, the finished file is checked against the
clip's swears, and a clip that still has an audible swear is fixed or flagged.

Every render path (Easy one-click, Pro, the queue, auto-process, export presets, A/B variants,
story clips, seamless loops) goes through clips.render_clip(), which calls guarantee():

  1. targets()  where each bleeped swear lands in the file: the main part (cuts, intro card,
                hook flash lead, replay inserts moved the timeline), the hook flash itself and
                slow-motion replays (the same swear plays again, an octave lower)
  2. check()    the tone (classic bleep) / the silence (mute) / no trace of the original
                voice (boop / custom) must cover each swear; Strict / Paranoid also let Whisper
                listen to every bleep, with and without the swear words as a hint
  3. widen      a swear that is still (partly) heard gets a wider bleep (bleep_fixes.json) and
                the clip is rendered again, at most MAX_RERENDERS times
  4. report     info["bleep_report"]: expected / bleeped / audible per swear (with its time in
                the file, for the play buttons), warnings "bleep_unresolved" (the clip shows
                "2 swears could not be bleeped" and one-click upload waits for the user)

inputs_fingerprint() changes whenever anything the bleeps depend on changes (the transcript,
the voice pass, the deep check, word lists, learned words, the user's bleep / unbleep edits,
the bleep settings, this pipeline's version): a render with an old fingerprint is never reused.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .. import config

# Bump when detection or bleep placement changes: every clip rendered before is redone.
BLEEP_VERSION = 31
MAX_RERENDERS = 2
SR = 16000
COVER_OK = 0.6  # share of a swear's own time the bleep must cover
TONE_SHARE = 0.3  # share of the energy at the bleep tone in one frame


# ------------------------------------------------------------------------------ fingerprint

def _stamp(p: Path) -> list:
    try:
        st = p.stat()
        return [st.st_mtime_ns, st.st_size]
    except OSError:
        return []


def inputs_fingerprint(project, cand: dict, options: dict) -> str:
    """Changes whenever the clip's bleeps could change (see the module doc)."""
    prof = options.get("profanity", "auto")
    if prof == "off":
        return f"v{BLEEP_VERSION}:off"
    from . import swearlearn

    edit = cand.get("edit") or {}
    parts = {
        "v": BLEEP_VERSION, "p": prof, "s": options.get("swear_strict", "auto"),
        "snd": options.get("bleep_sound", "classic"),
        "files": [_stamp(project.dir / n) for n in ("transcript.json", "voices.json", "swearscan.json")],
        "fix": (_read_json(project.dir / "bleep_fixes.json") or {}).get(str(cand.get("id"))),
        "lists": config.get("profanity_lists") or {},
        "learned": _stamp(swearlearn.path()),
        "custom": _stamp(config.config_dir() / "bleep" / "custom.wav") if options.get("bleep_sound") == "custom" else None,
        "e": [edit.get("bleep") or [], edit.get("unbleep") or []],
    }
    return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------ where the bleeps are

def targets(plan, flash: float = 0.0, flash_start: float = 0.0) -> list[dict]:
    """One row per (bleeped swear, place in the file):
    {"word", "spk", "status", "src": [a, b] (the word, source time), "out": [a, b] (file time),
     "where": main | flash | replay, "hz": the classic tone's pitch there}."""
    if plan is None or plan.bleep_mode == "off":
        return []
    fxp = plan.fx
    lead = plan.intro_s + flash
    dubbed = []
    if plan.dub is not None:
        dubbed = [(float(x["start"]), float(x["end"])) for x in plan.dub.get("lines") or [] if x.get("dub")]
    out = []
    for it in plan.swears:
        if not it.get("bleep"):
            continue
        a, b = float(it["start"]), float(it["end"])
        if b - a < 0.04:
            b = a + 0.04
        if any(a < y and b > x for x, y in dubbed):
            continue  # a dubbed line is new speech: the swear was translated away
        base = {"word": it.get("word") or "", "spk": it.get("spk"), "status": it.get("status"),
                "src": [round(a, 3), round(b, 3)]}
        outs = plan.out_ranges([(a, b)])
        if outs:
            oa, ob = outs[0][0], outs[-1][1]
            if fxp is not None and fxp.inserts:
                oa, ob = fxp.final(oa), fxp.final(ob, end=True)
            out.append({**base, "out": [round(lead + oa, 3), round(lead + ob, 3)], "where": "main", "hz": 1000.0})
        if flash and a < flash_start + flash and b > flash_start:
            fa, fb = max(a, flash_start), min(b, flash_start + flash)
            out.append({**base, "out": [round(plan.intro_s + fa - flash_start, 3), round(plan.intro_s + fb - flash_start, 3)],
                        "where": "flash", "hz": 1000.0})
        for ins in (fxp.inserts if fxp is not None else []):
            if ins.kind != "replay" or not (a < ins.src_end and b > ins.src) or ins.src_end <= ins.src:
                continue
            k = ins.dur / (ins.src_end - ins.src)
            at = lead + fxp.final(ins.at, end=True)
            ra, rb = max(a, ins.src), min(b, ins.src_end)
            out.append({**base, "out": [round(at + (ra - ins.src) * k, 3), round(at + (rb - ins.src) * k, 3)],
                        "where": "replay", "hz": 1000.0 / k})
    return out


# ------------------------------------------------------------------------------ the file's sound

def read_audio(path: Path) -> np.ndarray:
    from ..voices import tracks

    return tracks.read_track(path, 0, 0.0, 36000.0, sr=SR)


def _frames_on(x: np.ndarray, a: float, b: float, hz: float) -> float:
    """Share of 32 ms frames in [a, b] that carry the tone at `hz`."""
    win, hop = 512, 160
    ia, ib = max(0, int(a * SR) - win // 2), min(len(x), int(b * SR) + win // 2)
    seg = x[ia:ib]
    if len(seg) < win:
        return 0.0
    n = 1 + (len(seg) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(seg[idx] * np.hanning(win).astype(np.float32), axis=1)) ** 2
    f = np.fft.rfftfreq(win, 1 / SR)
    band = (f > hz - 60) & (f < hz + 60)
    tot = spec.sum(axis=1) + 1e-12
    on = (spec[:, band].sum(axis=1) / tot >= TONE_SHARE) & (tot > 1e-6)
    return float(on.mean()) if len(on) else 0.0


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0


def _quiet(x: np.ndarray, a: float, b: float) -> bool:
    seg = x[int(a * SR):int(b * SR)]
    ctx = np.concatenate([x[max(0, int((a - 0.6) * SR)):int(a * SR)], x[int(b * SR):int((b + 0.6) * SR)]])
    return _rms(seg) <= max(2e-3, 0.3 * _rms(ctx))


def _voice_left(x: np.ndarray, src: np.ndarray, a: float) -> bool:
    """boop / custom sounds: is the original voice still in the file here? (normalized
    cross-correlation with the source sound, +-40 ms)."""
    seg = x[int(a * SR):int(a * SR) + len(src)]
    if len(seg) < len(src) * 0.8 or _rms(src) < 1e-4:
        return False
    best = 0.0
    lag = int(0.04 * SR)
    for d in range(-lag, lag + 1, 40):
        lo = int(a * SR) + d
        if lo < 0:
            continue
        s = x[lo:lo + len(src)]
        if len(s) != len(src):
            continue
        c = float(np.dot(s, src) / (np.linalg.norm(s) * np.linalg.norm(src) + 1e-9))
        best = max(best, c)
    return best > 0.5


def check_tones(path: Path, plan, rows: list[dict], source: Path | None = None) -> list[dict]:
    """Marks every row ok / not ok from the file's sound (no models). Returns the rows."""
    x = read_audio(path)
    sound = plan.bleep_sound if plan.bleep_mode == "bleep" else "mute"
    for r in rows:
        a, b = r["out"]
        # the middle of the word: Whisper's word edges are often 50-100 ms off
        m = (b - a) * 0.15 if b - a > 0.2 else 0.0
        a2, b2 = a + m, b - m
        if b2 * SR > len(x) + SR * 0.05:
            r.update(ok=False, why="outside")
            continue
        if sound == "classic":
            cov = _frames_on(x, a2, b2, r["hz"])
            r.update(ok=cov >= COVER_OK, cover=round(cov, 2))
        elif sound == "mute":
            r.update(ok=_quiet(x, a2, b2))
        elif r["where"] == "main" and source is not None:
            from ..voices import tracks

            src = tracks.read_track(source, 0, r["src"][0] + m, r["src"][1] - m, sr=SR)
            r.update(ok=not _voice_left(x, src, a2))
        else:
            r.update(ok=True, unchecked=True)
        if not r["ok"]:
            r.setdefault("why", "no_bleep")
    return rows


def listen(path: Path, plan, rows: list[dict], asr=None) -> None:
    """Whisper listens to every bleep in the file (no prompt, then the swear words as a hint):
    where part of a swear is still heard, the row gets ok=False, why="heard", side=left|right|both."""
    from ..voices import engines as E
    from ..voices import swearscan, tracks
    from . import swearlearn

    lang = plan.lang
    prompt = swearscan.prompt_for(lang, swearlearn.hotwords(lang))
    own = asr is None
    if own:
        from .. import transcribe

        engine = transcribe.load_whisper("check" if transcribe.check_model_ready() else "auto")

        def asr(x, lang_, prompt_=None, temperature=0.0, hotwords=None):
            return transcribe.transcribe_check(engine, x, lang_, prompt_, temperature, hotwords)
    try:
        from .. import governor

        for r in rows:
            if r["where"] == "replay" or not r.get("ok", True):
                continue  # slow motion: Whisper can't read it; already failing: re-rendered anyway
            governor.checkpoint()
            oa, ob = r["out"]
            s = max(0.0, oa - 1.5)
            x = tracks.read_track(path, 0, s, ob + 1.5)
            if len(x) < E.SR * 0.3:
                continue
            side = None
            for prompted in (False, True):
                segs = asr(E.level(x), lang, prompt if prompted else None, 0.0, None)
                ws = swearscan.words_of(segs, s, s, s + len(x) / E.SR)
                side = swearscan.leak(r["word"], ws, oa, ob, lang) if r["word"] else None
                if side:
                    break
            if side:
                r.update(ok=False, why="heard", side=side)
    finally:
        if own:
            from .. import memory

            engine = None  # noqa: F841
            memory.release_current()


def widen(project, cand: dict, rows: list[dict], attempt: int) -> list[tuple[float, float]]:
    """Wider bleeps (source time) for the rows that failed, saved for the next render."""
    from ..project import write_json_atomic
    from ..voices import swearscan

    # wider than the plan's own padding (BLEEP_PAD strict: 0.12 / 0.18)
    pre, post = (0.22, 0.28) if attempt <= 1 else (0.35, 0.42)
    out = []
    for r in rows:
        if r.get("ok", True):
            continue
        a, b = r["src"]
        side = r.get("side", "both")
        out.append((round(a - (pre if side in ("left", "both") else 0.04), 3),
                    round(b + (post if side in ("right", "both") else 0.04), 3)))
    if out:
        fx = swearscan.load_fixes(project)
        cur = [tuple(x) for x in fx.get(str(cand["id"]), [])]
        fx[str(cand["id"])] = [[x, y] for x, y in sorted(set(cur) | set(out))][:200]
        write_json_atomic(swearscan.fixes_path(project), fx)
    return out


# ------------------------------------------------------------------------------ the guarantee

def listening_on(opts) -> bool:
    """Whisper re-listens on Strict / Paranoid (Settings can switch it off; tests do)."""
    from . import swears

    if config.get("swear_verify_render") is False or os.environ.get("SHARKYCLIPS_NO_BLEEP_CHECK"):
        return False
    return swears.resolve_strictness(getattr(opts, "swear_strict", "auto"), True) != "normal"


def report(rows: list[dict], plan, attempts: int, listened: bool) -> dict:
    """The clip's bleep report (clips.json "edits"."bleep_report", the UI's "7 bleeps" badge)."""
    words: dict[tuple, dict] = {}
    for r in rows:
        key = tuple(r["src"])
        w = words.setdefault(key, {"word": r["word"], "spk": r.get("spk"), "status": r.get("status"),
                                   "t": r["out"][0], "ok": True, "where": []})
        w["where"].append(r["where"])
        if not r.get("ok", True):
            w["ok"] = False
            w["why"] = r.get("why")
            if r["where"] != "main":
                w["t"] = r["out"][0]
    items = sorted(words.values(), key=lambda w: w["t"])
    maybe_off = sum(1 for it in (plan.swears if plan is not None else []) if not it.get("bleep"))
    audible = [w for w in items if not w["ok"]]
    return {"version": BLEEP_VERSION, "expected": len(items), "bleeped": len(items) - len(audible),
            "audible": len(audible), "items": items, "not_bleeped_by_choice": maybe_off,
            "strictness": getattr(plan, "strictness", None), "mode": getattr(plan, "bleep_mode", None),
            "listened": listened, "attempts": attempts, "ok": not audible}


def applies(opts, spec) -> bool:
    return getattr(opts, "profanity", "auto") != "off" and getattr(spec, "audio", "aac") != "none"


def guarantee(project, cand: dict, opts, spec, dest: Path, res, again, plan_for, on_stage=None):
    """Check the rendered file; widen + render `again()` while a swear is still heard (at most
    MAX_RERENDERS times); put the report and warnings into res.info. plan_for() -> (plan, flash,
    flash_start) as rendered. Never fails the render: a broken check is a visible warning."""
    if not applies(opts, spec):
        return res
    listened = listening_on(opts)
    rep = None
    attempt = 0
    try:
        while True:
            plan, flash, flash_start = plan_for()
            rows = targets(plan, flash, flash_start)
            if rows:
                if on_stage:
                    on_stage("checking_bleeps")
                check_tones(dest, plan, rows, project.source_path)
                if listened:
                    listen(dest, plan, rows)
            rep = report(rows, plan, attempt + 1, listened)
            if rep["ok"] or attempt >= MAX_RERENDERS:
                break
            attempt += 1
            widen(project, cand, rows, attempt)
            if on_stage:
                on_stage("rendering_again")
            res = again()
    except Exception as exc:  # noqa: BLE001 - the clip is fine as rendered; say the check broke
        from ..ui import console

        console.print(f"[yellow]Bleep check failed: {exc!r}[/]")
        rep = {"version": BLEEP_VERSION, "ok": False, "error": str(exc)[:200], "expected": None,
               "bleeped": None, "audible": None, "items": [], "attempts": attempt + 1}
    info = dict(res.info or {})
    info["bleep_report"] = rep
    warns = set(info.get("warnings") or [])
    if rep.get("error"):
        warns.add("bleep_check_skipped")
    elif not rep["ok"]:
        warns.add("bleep_unresolved")
    if attempt and rep.get("ok"):
        warns.add("bleep_widened")
    info["warnings"] = sorted(warns) or None
    res.info = info
    return res


def unresolved(clip: dict | None) -> int:
    """How many swears of a rendered clip are still audible (0 = fine or no report)."""
    rep = ((clip or {}).get("edits") or {}).get("bleep_report") or {}
    if rep.get("error"):
        return 0
    return int(rep.get("audible") or 0)


__all__ = ["BLEEP_VERSION", "MAX_RERENDERS", "check_tones", "guarantee", "inputs_fingerprint", "listen",
           "report", "targets", "unresolved", "widen"]
