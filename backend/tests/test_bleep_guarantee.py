"""1.2.31 end-to-end bleep guarantee: a real render of a clip with 7 known swears from 2
speakers (Whisper's odd spellings, a two-word swear, one only the main transcript heard, one
inside the hook flash, two inside the slow-motion replay) must bleep every one of them in the
finished file's audio. Runs in CI (ffmpeg is installed there)."""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import clips, config
from sharkyclips.clips import ClipOptions, OutputSpec
from sharkyclips.edit import audiomix, bleepcheck
from sharkyclips.project import Project, write_json_atomic
from sharkyclips.voices import pipeline as vpipe
from sharkyclips.voices import tracks

SR = 48000
# (start, end, word, speaker): the swears, said by "me" and a friend ("f1")
SWEARS = [
    (1.30, 1.70, "siktir", "me"),
    (2.40, 2.75, "amına", "me"), (2.80, 3.20, "koyayım", "me"),  # one swear, two words
    (3.60, 4.00, "Orospu", "f1"),
    (5.00, 5.25, "amk", "me"),
    (6.40, 6.90, "Amanakoyim", "f1"),  # Whisper's spelling, inside the hook flash
    (8.00, 8.40, "iskiyim", "f1"),  # "sikeyim" with the vowel moved
    (9.30, 9.65, "kahpe", "f1"),  # only the main transcript heard this one
]
FILLER = [(0.70, 1.10, "kanka"), (1.90, 2.20, "bak"), (4.30, 4.70, "geldi"), (5.50, 5.90, "oğlum"),
          (7.20, 7.60, "abi"), (8.70, 9.00, "tamam"), (10.0, 10.4, "yaa")]
CAND = {"id": "c01", "rank": 1, "start": 0.5, "end": 11.0, "duration": 10.5, "peak": 6.5, "text": "x",
        "reasons": [{"t": 4.0, "code": "df_kill", "strength": 1.0}]}


def _speech(n: int, rng) -> np.ndarray:
    """Speech-like sound: band-limited noise (200-3000 Hz) with a syllable rhythm."""
    x = rng.standard_normal(n + 64).astype(np.float32)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec[(f < 200) | (f > 3000)] = 0
    y = np.fft.irfft(spec, len(x))[:n].astype(np.float32)
    t = np.arange(n) / SR
    y *= (0.55 + 0.45 * np.sin(2 * np.pi * 5 * t)).astype(np.float32)
    return 0.2 * y / (np.sqrt(np.mean(y ** 2)) + 1e-9)


def _make_project(name: str) -> Project:
    ffmpeg = shutil.which("ffmpeg")
    d = config.workspace_dir() / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    rng = np.random.default_rng(31)
    dur = 12.0
    y = (rng.standard_normal(int(SR * dur)) * 0.003).astype(np.float32)
    for a, b, *_ in SWEARS + FILLER:
        y[int(a * SR):int(b * SR)] += _speech(int(b * SR) - int(a * SR), rng)
    with wave.open(str(d / "voice.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    subprocess.run([ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration={dur}",
                    "-i", str(d / "voice.wav"), "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-shortest", str(d / "source.mp4")],
                   check=True, capture_output=True)
    (d / "voice.wav").unlink()
    write_json_atomic(d / "meta.json", {"title": "bleeps", "duration": dur, "width": 640, "height": 360,
                                        "fps": 30.0, "mode": "gaming", "audio_codec": "aac"})
    words = sorted([(a, b, w) for a, b, w, _s in SWEARS] + FILLER)
    write_json_atomic(d / "transcript.json", {"language": "tr", "created_at": "t", "segments": [
        {"start": 0.5, "end": 11.0, "words": [{"start": a, "end": b, "word": " " + w, "probability": 0.93}
                                              for a, b, w in words]}]})
    # The voice pass: every speaker labelled; it missed "kahpe" (the main transcript has it).
    spk = {w: s for _a, _b, w, s in SWEARS}
    vwords = [{"start": a, "end": b, "word": w, "p": 0.9, "spk": spk.get(w, "me")}
              for a, b, w in words if w != "kahpe"]
    write_json_atomic(d / "voices.json", {"version": vpipe.VERSION, "ranges": [[0.0, 12.0]],
                                          "speakers": {"me": {}, "f1": {}}, "names": {}, "words": vwords, "hints": []})
    return Project(name, d)


def _tone_runs(path: Path) -> list[tuple[float, float]]:
    x = tracks.read_track(path, 0, 0.0, 600.0, sr=16000)
    win, hop = 512, 160
    n = (len(x) - win) // hop
    f = np.fft.rfftfreq(win, 1 / 16000)
    on = []
    for i in range(n):
        s = np.abs(np.fft.rfft(x[i * hop:i * hop + win] * np.hanning(win))) ** 2
        tot = s.sum() + 1e-12
        on.append(tot > 1e-6 and (s[(f > 940) & (f < 1060)].sum() / tot > 0.3 or s[(f > 440) & (f < 560)].sum() / tot > 0.3))
    runs, i = [], 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            if (j - i) * hop / 16000 >= 0.08:
                runs.append((i * hop / 16000, (j * hop + win) / 16000))
            i = j
        else:
            i += 1
    return runs


OPTS = {"profanity": "auto", "hook": False, "hook_flash": True, "replay": "auto", "subtitles": "bold"}
SPEC = OutputSpec(width=540, height=960, fps=30)


@pytest.mark.requires_ffmpeg
def test_every_swear_of_two_speakers_is_bleeped_in_the_rendered_audio(tmp_path):
    proj = _make_project("bleep-e2e")
    opts = ClipOptions.from_dict(OPTS)
    out = tmp_path / "clip.mp4"
    res = clips.render_clip(proj, CAND, opts, None, out, spec=SPEC)
    rep = res.info["bleep_report"]
    # every swear (7, "amına koyayım" counts per word) is in the report, from both speakers
    words = {it["word"].strip(".,!?").lower() for it in rep["items"]}
    assert {"siktir", "amına", "koyayım", "orospu", "amk", "amanakoyim", "iskiyim", "kahpe"} <= words, words
    assert {it["spk"] for it in rep["items"]} >= {"me", "f1"}
    assert rep["ok"] and rep["audible"] == 0 and rep["bleeped"] == rep["expected"] >= 8, rep
    assert "bleep_unresolved" not in (res.info.get("warnings") or [])
    # independent of the checker: the file has a bleep tone at every place a swear plays
    plan, flash, flash_start = clips.bleep_plan(proj, CAND, opts, SPEC)
    rows = bleepcheck.targets(plan, flash, flash_start)
    assert {r["where"] for r in rows} == {"main", "flash", "replay"}  # the flash + the replay copies too
    runs = _tone_runs(out)
    for r in rows:
        a, b = r["out"]
        mid = (a + b) / 2
        assert any(x - 0.02 <= mid <= y + 0.02 for x, y in runs), (r, runs)
    shutil.rmtree(proj.dir, ignore_errors=True)


@pytest.mark.requires_ffmpeg
def test_a_leak_is_caught_rerendered_and_flagged(tmp_path, monkeypatch):
    """If a bleep goes missing (here: the flash and replay copies are never bleeped), the
    guarantee renders again (twice) and then flags the clip instead of passing it."""
    proj = _make_project("bleep-leak")
    calls = []
    real = clips._render_once

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(clips, "_render_once", counting)
    monkeypatch.setattr(audiomix, "bleep_source_chunk", lambda y, t0, plan, custom=None: y)
    out = tmp_path / "clip.mp4"
    res = clips.render_clip(proj, CAND, ClipOptions.from_dict(OPTS), None, out, spec=SPEC)
    rep = res.info["bleep_report"]
    assert len(calls) == 1 + bleepcheck.MAX_RERENDERS
    assert not rep["ok"] and rep["audible"] >= 1 and "bleep_unresolved" in res.info["warnings"]
    bad = [it for it in rep["items"] if not it["ok"]]
    assert all(set(it["where"]) & {"flash", "replay"} for it in bad)
    shutil.rmtree(proj.dir, ignore_errors=True)


def test_old_renders_are_never_reused_when_bleep_inputs_change(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    proj = Project("p", d)
    (d / "transcript.json").write_text("{}", encoding="utf-8")
    cand = {"id": "c01", "edit": {}}
    o = ClipOptions().to_dict()
    fp = bleepcheck.inputs_fingerprint(proj, cand, o)
    assert fp == bleepcheck.inputs_fingerprint(proj, cand, o)
    assert fp != bleepcheck.inputs_fingerprint(proj, {"id": "c01", "edit": {"bleep": [[1, 2]]}}, o)
    assert fp != bleepcheck.inputs_fingerprint(proj, cand, {**o, "swear_strict": "paranoid"})
    write_json_atomic(d / "swearscan.json", {"items": []})  # the deep check ran
    assert fp != bleepcheck.inputs_fingerprint(proj, cand, o)
    from sharkyclips.web import app as A

    clip = {"start": 0, "end": 1, "options": o, "edit_fp": "", "bleep_fp": None}
    assert not A._render_is_current(clip, {"id": "c01", "start": 0, "end": 1}, o, "", None, proj)
