"""The voice pass (see __init__.py for the idea). Engines are injectable for the tests."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .. import governor
from ..edit import swears
from ..edit.words import token
from ..errors import SharkyClipsError
from ..project import Project, read_json, write_json_atomic
from . import engines as E
from . import tracks

VERSION = 1
PAD = 1.5  # seconds around every clip
TURN_PAD = 0.25
MAX_TURN = 20.0
MAX_KWS = 80  # re-listen windows per run
ProgressFn = Callable[[str, float], None]

# Whisper's well-known inventions on noise / silence (YouTube outros, subtitle credits).
HALLUCINATIONS = re.compile(
    r"izledi[gğ]iniz i[cç]in|te[sş]ekk[uü]r eder|abone ol|altyaz[ıi]|m\s*\.\s*k\s*\.|amara\.org|"
    r"thanks? for watching|subscribe|like and|bir sonraki videoda|g[oö]r[uü][sş]mek [uü]zere|"
    r"untertitel|субтитры|продолжение следует|字幕", re.I)

SWEAR_HINTS = {  # decoder hints for the acoustic re-listen
    "tr": "amına koyayım, siktir, sikeyim, orospu, piç, yarrak, göt, amk, aq, kahpe, şerefsiz",
    "en": "fuck, fucking, shit, bitch, asshole, dick, motherfucker",
    "de": "Scheiße, fick, Arschloch, Hurensohn, Wichser",
}


@dataclass
class Engines:
    separator: Any = None  # x44 (2, n) -> vocals 16 kHz
    diarizer: Any = None  # .turns(x16) / .embed(x16)
    asr: Callable[..., list[dict]] | None = None  # (x16, lang, hotwords) -> segments
    release: Callable[[], None] | None = None


def voices_path(project: Project) -> Path:
    return project.dir / "voices.json"


def load(project: Project) -> dict | None:
    p = voices_path(project)
    if not p.is_file():
        return None
    try:
        data = read_json(p)
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) and data.get("version") == VERSION else None


# ------------------------------------------------------------------------------ ranges

def merge_ranges(ranges: list[tuple[float, float]], gap: float = 3.0) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in out]


def clip_ranges(project: Project, duration: float) -> list[tuple[float, float]]:
    """Every clip candidate (found + manual), padded."""
    from ..web import state

    hl = state.load_highlights(project) or {}
    rs = [(max(0.0, float(c["start"]) - PAD), min(duration, float(c["end"]) + PAD))
          for c in hl.get("candidates", [])]
    return merge_ranges([r for r in rs if r[1] > r[0]])


def whole_ranges(duration: float, step: float = 60.0) -> list[tuple[float, float]]:
    out, t = [], 0.0
    while t < duration - 0.5:
        out.append((round(t, 3), round(min(duration, t + step), 3)))
        t += step
    return out


# ------------------------------------------------------------------------------ words

def base_words(project: Project) -> tuple[list[dict], str | None]:
    if not project.transcript_path.is_file():
        return [], None
    tr = project.load_transcript()
    out = []
    for seg in tr.get("segments", []):
        for w in seg.get("words", []):
            if w["word"].strip():
                out.append({"start": float(w["start"]), "end": float(w["end"]), "word": w["word"].strip(),
                            "p": float(w.get("probability", 1.0) or 0.0)})
    return out, tr.get("language")


def clean_segments(segs: list[dict], offset: float, lo: float, hi: float) -> list[dict]:
    """Segments -> absolute words, without hallucinated / garbage segments."""
    out = []
    for s in segs:
        text = s.get("text", "")
        if HALLUCINATIONS.search(text):
            continue
        lp, nsp = float(s.get("avg_logprob", 0.0)), float(s.get("no_speech_prob", 0.0))
        if lp < -1.0 or (nsp > 0.6 and lp < -0.4) or float(s.get("compression_ratio", 1.0)) > 2.4:
            continue
        for w in s.get("words", []):
            a, b = offset + float(w["start"]), offset + float(w["end"])
            if not w["word"].strip() or b < lo or a > hi:
                continue
            out.append({"start": round(a, 3), "end": round(max(b, a + 0.05), 3), "word": w["word"].strip(),
                        "p": round(float(w.get("probability", 0.0)), 3)})
    return out


def _score(ws: list[dict]) -> float:
    return sum(w["p"] for w in ws if len(token(w["word"], None)) > 0)


def dedupe(words: list[dict]) -> list[dict]:
    """Same word twice (two passes / overlapping turns) -> the surer one. Two different words
    at the same time from different speakers stay only when both are clearly heard
    (overlapping speech); otherwise they're two readings of one voice and the surer wins."""
    words = sorted(words, key=lambda w: (w["start"], -w["p"]))
    kept: list[dict] = []
    for w in words:
        tw = token(w["word"], None)
        dup = None
        for k in reversed(kept[-8:]):
            if k["end"] <= w["start"] - 0.05:
                continue
            ov = min(k["end"], w["end"]) - max(k["start"], w["start"])
            if ov <= 0.4 * min(k["end"] - k["start"], w["end"] - w["start"]):
                continue
            same = token(k["word"], None) == tw
            both_clear = k.get("spk") != w.get("spk") and min(k["p"], w["p"]) >= 0.75
            if same or not both_clear:
                dup = k
                break
        if dup is None:
            kept.append(w)
        elif w["p"] > dup["p"]:
            kept[kept.index(dup)] = w
    return kept


def smooth_speakers(words: list[dict], gap: float = 0.35) -> list[dict]:
    """One or two words of another voice in the middle of someone's sentence are overlapping
    turns reading the same speech: they get the surrounding speaker."""
    w = [dict(x) for x in words]
    for _ in range(2):
        runs: list[list[int]] = []
        for i, x in enumerate(w):
            if runs and x.get("spk") and w[runs[-1][-1]].get("spk") == x["spk"]                     and x["start"] - w[runs[-1][-1]]["end"] < gap:
                runs[-1].append(i)
            else:
                runs.append([i])
        for r, run in enumerate(runs):
            spk = w[run[0]].get("spk")
            if not spk or len(run) > 2:
                continue
            prev = runs[r - 1] if r > 0 else None
            nxt = runs[r + 1] if r + 1 < len(runs) else None
            p_ok = prev and w[prev[-1]].get("spk") and w[run[0]]["start"] - w[prev[-1]]["end"] < gap
            n_ok = nxt and w[nxt[0]].get("spk") and w[nxt[0]]["start"] - w[run[-1]]["end"] < gap
            target = None
            if p_ok and n_ok and w[prev[-1]]["spk"] == w[nxt[0]]["spk"]:
                target = w[prev[-1]]["spk"]
            elif p_ok and not n_ok and len(prev) > len(run):
                target = w[prev[-1]]["spk"]
            elif n_ok and not p_ok and len(nxt) > len(run):
                target = w[nxt[0]]["spk"]
            if target and target != spk:
                for k in run:
                    w[k]["spk"] = target
    return w


def _normalize_turns(turns: list[tuple[float, float, int]]) -> list[tuple[float, float, int]]:
    merged: list[list[float]] = []
    for s, e, spk in sorted(turns):
        if merged and merged[-1][2] == spk and s - merged[-1][1] < 0.3 and e - merged[-1][0] < MAX_TURN:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e, spk])
    out = []
    for s, e, spk in merged:
        while e - s > MAX_TURN:
            out.append((s, s + MAX_TURN * 0.75, int(spk)))
            s += MAX_TURN * 0.75 - 0.5
        if e - s >= 0.25:
            out.append((s, e, int(spk)))
    return out


# ------------------------------------------------------------------------------ main

def default_engines(mode: str, need_sep: bool) -> Engines:
    from . import models

    eng = Engines()
    if models.sherpa_ok():
        try:
            if need_sep and mode == "separate":
                eng.separator = E.Separator()
        except Exception:  # noqa: BLE001 - offline / broken model: no separation
            eng.separator = None
        try:
            eng.diarizer = E.Diarizer()
        except Exception:  # noqa: BLE001
            eng.diarizer = None
    return eng


def run_voice_pass(project: Project, *, whole: bool = False, engines: Engines | None = None,
                   on_progress: ProgressFn | None = None, separate: bool = True) -> dict:
    t_start = time.time()
    meta = project.load_meta()
    src = project.source_path
    if src is None:
        raise SharkyClipsError("The source video is missing.")
    duration = float(meta.get("duration") or 0)
    base, lang = base_words(project)
    if not base and not project.transcript_path.is_file():
        raise SharkyClipsError("Transcribe the video first.")
    ranges = whole_ranges(duration) if whole else clip_ranges(project, duration)
    if not ranges:
        raise SharkyClipsError("No clips yet: find highlights first, or run it on the whole video.")
    progress = on_progress or (lambda stage, f: None)

    streams = tracks.audio_streams(src)
    labels, label_src = tracks.labels_for(meta, streams)
    voice_tracks = [(s["pos"], lab) for s, lab in zip(streams, labels) if lab in ("me", "friends")]
    mode = "tracks" if voice_tracks else "separate"
    mix_pos = next((s["pos"] for s, lab in zip(streams, labels) if lab == "mixed"), 0)
    eng = engines if engines is not None else default_engines(mode, separate)

    # ---- 1. CPU: audio, separation, who speaks when (+ a voice fingerprint per turn)
    pieces: list[dict] = []  # one per turn: {"s", "e", "src": {name: (array, offset)}, "emb", "spk"...}
    audio_by_range: list[dict] = []
    for ri, (a, b) in enumerate(ranges):
        governor.checkpoint()
        progress("separating" if mode == "separate" else "reading_tracks", ri / len(ranges))
        if mode == "tracks":
            kws_src = []
            for pos, lab in voice_tracks:
                x = tracks.read_track(src, pos, a, b)
                kws_src.append(x)
                if lab == "friends" and eng.diarizer is not None:
                    turns = _normalize_turns(eng.diarizer.turns(x))
                else:
                    turns = _normalize_turns(E.energy_turns(x))
                for s, e, local in turns:
                    emb = eng.diarizer.embed(x[int(s * E.SR):int(e * E.SR)]) \
                        if (lab == "friends" and eng.diarizer is not None) else None
                    pieces.append({"s": a + s, "e": a + e, "range": ri, "local": f"{pos}:{local}", "emb": emb,
                                   "track": lab, "src": {"track": (x, a)}})
            n = min(len(k) for k in kws_src)
            audio_by_range.append({"a": a, "b": b, "kws": np.sum([k[:n] for k in kws_src], axis=0)})
        else:
            x44 = tracks.read_track(src, mix_pos, a, b, sr=44100, channels=2)
            if x44.size == 0:
                continue
            mix16 = E.resample(x44.mean(axis=0), 44100)
            voc16 = None
            cache = project.cache_dir / "voices" / f"voc_{a:.2f}_{b:.2f}.npy"
            if eng.separator is not None and cache.is_file() and engines is None:
                try:
                    voc16 = np.load(cache).astype(np.float32)  # separated before (the slow part)
                except Exception:  # noqa: BLE001
                    voc16 = None
            if voc16 is None and eng.separator is not None:
                try:
                    voc16 = eng.separator(x44)
                    if engines is None:
                        cache.parent.mkdir(parents=True, exist_ok=True)
                        np.save(cache, voc16.astype(np.float16))
                except Exception:  # noqa: BLE001 - keep going with the mix only
                    voc16 = None
            del x44
            progress("diarizing", (ri + 0.5) / len(ranges))
            turns = _normalize_turns(eng.diarizer.turns(mix16) if eng.diarizer is not None
                                     else E.energy_turns(voc16 if voc16 is not None else mix16))
            srcs = {"mix": (mix16, a)}
            if voc16 is not None:
                srcs["voc"] = (voc16, a)
            fp_src = voc16 if voc16 is not None else mix16  # fingerprints: the voices without game sound
            for s, e, local in turns:
                emb = eng.diarizer.embed(fp_src[int(s * E.SR):int(e * E.SR)]) if eng.diarizer is not None else None
                pieces.append({"s": a + s, "e": a + e, "range": ri, "local": str(local), "emb": emb,
                               "track": "mixed", "src": srcs, "fp": "voc" if voc16 is not None else "mix"})
            audio_by_range.append({"a": a, "b": b, "kws": voc16 if voc16 is not None else mix16})

    # ---- 2. one speaker id per voice over the whole video
    _assign_speakers(pieces, mode)
    seconds: dict[str, float] = {}
    for p in pieces:
        seconds[p["spk"]] = seconds.get(p["spk"], 0.0) + (p["e"] - p["s"])

    # ---- 3. GPU: transcribe every turn from every source, keep the best reading
    own_asr = eng.asr is None
    engine = None
    if own_asr:
        from .. import transcribe

        progress("loading_whisper", 0.0)
        engine = transcribe.load_whisper()
        eng.asr = lambda x, lang_, hot=None: transcribe.transcribe_short(engine, x, lang_, hot)
    final: list[dict] = []
    alts: list[dict] = []
    hints: list[dict] = []
    try:
        for pi, p in enumerate(pieces):
            if pi % 8 == 0:
                governor.checkpoint()
                progress("transcribing", pi / max(1, len(pieces)))
            readings: dict[str, list[dict]] = {}
            for name, (x, off) in p["src"].items():
                i0, i1 = int(max(0.0, p["s"] - TURN_PAD - off) * E.SR), int((p["e"] + TURN_PAD - off) * E.SR)
                seg = x[i0:i1]
                if len(seg) < E.SR * 0.2:
                    continue
                segs = eng.asr(E.level(seg), lang)
                readings[name] = clean_segments(segs, off + i0 / E.SR, p["s"] - 0.15, p["e"] + 0.15)
            in_turn = [dict(w) for w in base if p["s"] - 0.1 <= (w["start"] + w["end"]) / 2 <= p["e"] + 0.1]
            if mode == "separate":
                readings["base"] = in_turn
            scores = {k: _score(v) * (1.15 if k == "base" else 1.0) for k, v in readings.items()}
            best = max(scores, key=scores.get) if scores else None
            for k, ws in readings.items():
                for w in ws:
                    w["spk"], w["src"] = p["spk"], k
                (final if k == best else alts).extend(ws)
            if mode == "tracks":
                alts.extend({**w, "spk": p["spk"], "src": "base"} for w in in_turn)
        # Main-transcript words no turn covered (the diarization missed them) stay.
        covered_turns = [(p["s"] - 0.1, p["e"] + 0.1, p["spk"]) for p in pieces]
        if mode == "separate":
            for w in base:
                mid = (w["start"] + w["end"]) / 2
                if not any(a - 0.01 <= mid <= b + 0.01 for a, b in ranges):
                    continue
                if any(s <= mid <= e for s, e, _ in covered_turns):
                    continue
                near = min(covered_turns, key=lambda t: min(abs(mid - t[0]), abs(mid - t[1])), default=None)
                spk = near[2] if near and min(abs(mid - near[0]), abs(mid - near[1])) < 1.0 else _top(seconds)
                final.append({**w, "spk": spk, "src": "base"})
        final = smooth_speakers(dedupe(final))

        # ---- 4. swear hints: other passes + an acoustic re-listen of unsure words
        hints += _pass2_hints(final, alts, lang)
        progress("checking_swears", 0.0)
        hints += _acoustic_hints(final, audio_by_range, lang, eng.asr)
    finally:
        if own_asr:
            from .. import memory

            engine = None
            eng.asr = None
            memory.release_current()
        if eng.release:
            eng.release()

    old = load(project) or {}
    names = {k: v for k, v in (old.get("names") or {}).items() if k in seconds}
    data = {
        "version": VERSION, "mode": mode, "whole": whole, "language": lang,
        "ranges": [[a, b] for a, b in ranges],
        "tracks": [{**s, "label": lab} for s, lab in zip(streams, labels)], "labels_from": label_src,
        "speakers": {k: {"seconds": round(v, 1)} for k, v in sorted(seconds.items(), key=lambda kv: -kv[1])},
        "names": names,
        "separated": mode == "separate" and eng.separator is not None,
        "diarized": eng.diarizer is not None,
        "words": [{k: w[k] for k in ("start", "end", "word", "p", "spk", "src")} for w in final],
        "hints": hints,
        "seconds": round(time.time() - t_start, 1),
        "transcript_created_at": _transcript_stamp(project),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    write_json_atomic(voices_path(project), data)
    progress("done", 1.0)
    return data


def _top(seconds: dict[str, float]) -> str:
    return max(seconds, key=seconds.get) if seconds else "me"


def _transcript_stamp(project: Project) -> str | None:
    try:
        return project.load_transcript().get("created_at")
    except Exception:  # noqa: BLE001
        return None


def _assign_speakers(pieces: list[dict], mode: str) -> None:
    """p["spk"]: "me", "f1", "f2"... The mic track is "me"; otherwise the voice that talks most.

    The diarization separates the speakers of each range; their mean voice fingerprints are
    then matched across ranges (engines.cluster_speakers), so a friend keeps one id."""
    pool = [p for p in pieces if not (mode == "tracks" and p["track"] == "me")]
    locals_: dict[tuple, list[dict]] = {}
    for p in pool:
        locals_.setdefault((p["range"], p["local"]), []).append(p)
    units, keys = [], []
    for k, ps in locals_.items():
        embs = [(p["emb"], p["e"] - p["s"]) for p in ps if p.get("emb") is not None]
        if not embs:
            continue
        v = np.sum([e * d for e, d in embs], axis=0)
        n = float(np.linalg.norm(v))
        if n == 0:
            continue
        units.append((k[0], v / n, sum(d for _e, d in embs)))
        keys.append(k)
    noisy = any(p.get("fp") == "mix" for p in pool)
    gid_of = dict(zip(keys, E.cluster_speakers(units, E.SAME_VOICE_MIX if noisy else E.SAME_VOICE)))
    for p in pool:
        p["gid"] = gid_of.get((p["range"], p["local"]), -1)
    talk: dict[int, float] = {}
    for p in pool:
        talk[p["gid"]] = talk.get(p["gid"], 0.0) + p["e"] - p["s"]
    order = sorted((g for g in talk if g != -1), key=lambda g: -talk[g])
    if mode == "tracks":
        names = {g: f"f{i + 1}" for i, g in enumerate(order)}
        for p in pieces:
            p["spk"] = "me" if p["track"] == "me" else names.get(p.get("gid"), "f1")
    else:
        names = {g: ("me" if i == 0 else f"f{i}") for i, g in enumerate(order)}
        for p in pieces:
            p["spk"] = names.get(p.get("gid"), "me")


def _pass2_hints(final: list[dict], alts: list[dict], lang: str | None) -> list[dict]:
    """Swears another reading heard where the kept words have none."""
    if not alts:
        return []
    found = [it for it in swears.detect(sorted(alts, key=lambda w: w["start"]), lang) if it["status"] == "sure"]
    have = [it for it in swears.detect(final, lang) if it["status"] == "sure"]
    out = []
    for it in found:
        if any(h["start"] < it["end"] + 0.2 and h["end"] > it["start"] - 0.2 for h in have + out):
            continue
        out.append({"start": it["start"], "end": it["end"], "word": it["word"], "spk": it["spk"],
                    "src": "pass2", "score": 0.6})
    return out


def _acoustic_hints(final: list[dict], audio_by_range: list[dict], lang: str | None,
                    asr: Callable[..., list[dict]]) -> list[dict]:
    """Listen again (separated voices, swear words as decoder hints) around unsure words."""
    hot = SWEAR_HINTS.get(lang or "")
    if not hot:
        return []
    maybe = [it for it in swears.detect(final, lang) if it["status"] == "maybe"]
    targets = [(it["start"], it["end"], it.get("spk")) for it in maybe]
    targets += [(w["start"], w["end"], w.get("spk")) for w in final
                if w["p"] < 0.5 and len(token(w["word"], lang)) >= 2]
    targets.sort()
    windows: list[list] = []
    for s, e, spk in targets:
        if windows and s - 0.9 <= windows[-1][1]:
            windows[-1][1] = max(windows[-1][1], e + 0.9)
        else:
            windows.append([s - 0.9, e + 0.9, spk])
    out = []
    for s, e, spk in windows[:MAX_KWS]:
        r = next((r for r in audio_by_range if r["a"] <= s and e <= r["b"] + 0.5), None)
        if r is None:
            continue
        i0, i1 = int(max(0.0, s - r["a"]) * E.SR), int(max(0.0, e - r["a"]) * E.SR)
        seg = r["kws"][i0:i1]
        if len(seg) < E.SR * 0.3:
            continue
        ws = clean_segments(asr(E.level(seg), lang, hot), r["a"] + i0 / E.SR, s, e)
        hits = [it for it in swears.detect(ws, lang) if it["status"] == "sure"]
        if len(hits) > 1 and len({token(h["word"], lang) for h in hits}) < len(hits):
            continue  # "siktir, siktir, siktir": the hint words made Whisper loop
        for it in hits:
            if not _heard_alike(it, final, ws, lang):
                continue
            out.append({"start": it["start"], "end": it["end"], "word": it["word"], "spk": spk,
                        "src": "acoustic", "score": 0.75})
    return out


def _heard_alike(hit: dict, final: list[dict], window_words: list[dict], lang: str | None) -> bool:
    """Trust a re-listen hit only if it sounds like what the first pass heard there (a misheard
    swear: "sıkeyim", "Sikir" -> "sikeyim", "siktir"), or nothing was heard there at all and
    the re-listen is short and sure. Hint words bias Whisper, so "sürekli" -> "siktir" is no."""
    under = [w for w in final if w["start"] < hit["end"] + 0.1 and w["end"] > hit["start"] - 0.1]
    if not under:
        w = next((w for w in window_words if w["start"] == hit["start"]), None)
        return bool(w) and w["p"] >= 0.6 and len(window_words) <= 4
    hk = swears._phon(token(hit["word"], lang))
    for w in under:
        wk = swears._phon(token(w["word"], lang))
        if wk and hk and wk[0] == hk[0] and swears._dist(wk[:4], hk[:4], 2) <= 1:
            return True
    return False


# ------------------------------------------------------------------------------ readers

def covered(data: dict | None, start: float, end: float) -> list[tuple[float, float]]:
    if not data:
        return []
    return [(max(start, a), min(end, b)) for a, b in data.get("ranges", []) if min(end, b) > max(start, a)]


def words_for(project: Project, start: float, end: float, base: list[dict],
              data: dict | None = None) -> list[dict]:
    """The clip's words: voice-pass words where it ran (with speakers), the main transcript
    elsewhere. base: main-transcript words of [start, end] (absolute times)."""
    data = data if data is not None else load(project)
    cov = covered(data, start, end)
    if not cov:
        return base

    def inside(w: dict) -> bool:
        mid = (w["start"] + w["end"]) / 2
        return any(a <= mid <= b for a, b in cov)

    out = [w for w in base if not inside(w)]
    for w in data.get("words", []):
        mid = (w["start"] + w["end"]) / 2
        if start <= mid <= end and inside(w):
            out.append({"start": float(w["start"]), "end": float(w["end"]), "word": w["word"],
                        "probability": w.get("p", 1.0), "spk": w.get("spk")})
    out.sort(key=lambda w: w["start"])
    return smooth_speakers(out)


def hints_for(project: Project, start: float, end: float, data: dict | None = None) -> list[dict]:
    data = data if data is not None else load(project)
    return [h for h in (data or {}).get("hints", []) if start <= (h["start"] + h["end"]) / 2 <= end]


def speaker_names(data: dict | None) -> dict[str, str]:
    return dict((data or {}).get("names") or {})
