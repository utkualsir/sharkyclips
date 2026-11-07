"""My-voice dubbing (1.2.18): a clip in another language, spoken in the streamer's OWN voice.

Rules (enforced here, not only in the UI):
  * one voice profile only: the user's own, after a one-time consent and a short sample the user
    recorded or picked (<settings>/voice/). Revoking deletes the sample and its fingerprint.
  * only the user's lines are re-voiced: a line is dubbed when the voice pass says it's "me" AND it
    sounds like the sample (WeSpeaker fingerprint), or - without a voice pass - when it clearly
    sounds like the sample. Friends / other speakers keep their own voice (they get subtitles).
  * timing: each translated line starts where the original line started and is fitted into its
    slot (faster speech up to 1.35x, then a gentle time-stretch; never past the next line).
  * the game sound stays: the user's voice is taken out of the mix (UVR separation) only where a
    dubbed line plays, so music / game / friends underneath are kept.

Voice cloning model: Kyutai Pocket TTS (CC-BY-4.0), int8 ONNX in sherpa-onnx, runs on the CPU
(~3x faster than real time), ~100 MB. It speaks English; the target list grows with the engines.
The translation comes from the local LLM (analyze.translate_clip), which is unloaded before the
voice model runs.

Result per clip + language: <project>/cache/dub/<clip>_<lang>_<sig>.wav (48 kHz stereo, source
timeline from `offset`) + .json (lines, what was dubbed and why).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from . import config, languages
from .downloads import Remote, fetch
from .errors import SharkyClipsError, require_tool
from .procs import no_window
from .project import Project, read_json, write_json_atomic

SR = 48000
TTS_SR = 24000
PAD = 3.0  # seconds of track before / after the clip (hook flash, loop tail)
MAX_SPEED = 1.35
MAX_STRETCH = 1.25
SAMPLE_MIN, SAMPLE_MAX = 5.0, 30.0
SAME_ME = 0.35  # with the voice pass saying "me": a sanity check against mislabels
SAME_ALONE = 0.55  # without a voice pass: must clearly sound like the sample
BED_GAIN = 0.5  # the game sound under a dubbed line (-6 dB)
CONSENT_VERSION = 1
TARGETS = ("en",)  # languages the voice model speaks
ProgressFn = Callable[[str, float | None], None]

POCKET = Remote("https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
                "sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2",
                "2f3b88823cbbb9bf0b2477ec8ae7b3fec417b3a87b6bb5f256dba66f2ad967cb", 98336520, "pocket-tts-int8.tar.bz2")
POCKET_DIR = "sherpa-onnx-pocket-tts-int8-2026-01-26"
POCKET_FILES = ("lm_flow.int8.onnx", "lm_main.int8.onnx", "encoder.onnx", "decoder.int8.onnx",
                "text_conditioner.onnx", "vocab.json", "token_scores.json", "LICENSE")
# CC-BY 4.0 asks for credit, a link to the license and a note of changes (1.2.19): exported to
# ONNX by KevinAHM, then packaged and quantized to int8 by k2-fsa/sherpa-onnx (1.2.20).
LICENSES = [{"name": "Pocket TTS", "by": "Kyutai", "license": "CC-BY-4.0",
             "license_url": "https://creativecommons.org/licenses/by/4.0/",
             "source_url": "https://huggingface.co/kyutai/pocket-tts",
             # how the downloaded file was made from the original (1.2.20: the full chain)
             "changes": "onnx_chain",
             "chain": [{"by": "KevinAHM", "url": "https://huggingface.co/KevinAHM/pocket-tts-onnx"},
                       {"by": "k2-fsa/sherpa-onnx", "url": "https://github.com/k2-fsa/sherpa-onnx"}]},
            {"name": "sherpa-onnx", "by": "k2-fsa", "license": "Apache-2.0",
             "license_url": "https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE",
             "source_url": "https://github.com/k2-fsa/sherpa-onnx"}]

# The line a dubbed upload gets in its description, in the language of the dub (1.2.19).
DISCLOSURE = {
    "en": "The English voice in this video is AI-generated from my own voice.",
    "fr": "La voix française de cette vidéo est générée par IA à partir de ma propre voix.",
    "de": "Die deutsche Stimme in diesem Video ist mit KI aus meiner eigenen Stimme erzeugt.",
    "es": "La voz en español de este vídeo está generada con IA a partir de mi propia voz.",
    "it": "La voce italiana di questo video è generata con l'IA a partire dalla mia voce.",
    "pt": "A voz em português deste vídeo foi gerada por IA a partir da minha própria voz.",
    "nl": "De Nederlandse stem in deze video is met AI gemaakt op basis van mijn eigen stem.",
    "tr": "Bu videodaki Türkçe ses, kendi sesimden yapay zekâyla üretildi.",
    "hu": "A videó magyar hangja mesterséges intelligenciával készült a saját hangomból.",
    "ru": "Русский голос в этом видео создан ИИ на основе моего собственного голоса.",
    "ar": "الصوت العربي في هذا الفيديو مولَّد بالذكاء الاصطناعي من صوتي أنا.",
    "zh": "本视频中的中文配音由 AI 根据我本人的声音生成。",
}
DISCLOSURE_FALLBACK = "The voice in this video is AI-generated from my own voice."


def disclosure_line(lang: str) -> str:
    """'This voice is AI-generated from my own voice', in the dub language (English fallback)."""
    return DISCLOSURE.get((lang or "").split("-")[0].lower(), DISCLOSURE_FALLBACK)


# ===================================================================== the voice profile


def voice_dir() -> Path:
    return config.config_dir() / "voice"


def _consent_path() -> Path:
    return voice_dir() / "consent.json"


def sample_path() -> Path:
    return voice_dir() / "sample.wav"


def profile() -> dict:
    c = {}
    try:
        c = read_json(_consent_path()) if _consent_path().is_file() else {}
    except (OSError, ValueError):
        c = {}
    consent = bool(c.get("agreed_at")) and c.get("version") == CONSENT_VERSION
    dur = None
    if sample_path().is_file():
        try:
            import soundfile

            info = soundfile.info(str(sample_path()))
            dur = round(info.frames / info.samplerate, 1)
        except Exception:  # noqa: BLE001
            dur = None
    return {"consent": consent, "agreed_at": c.get("agreed_at") if consent else None, "name": c.get("name"),
            "sample": dur is not None, "sample_seconds": dur, "sample_source": c.get("sample_source"),
            "targets": list(TARGETS), "model_ready": model_ready(), "model_mb": round(POCKET.size / 1e6),
            "licenses": LICENSES, "ready": consent and dur is not None}


def give_consent(name: str) -> dict:
    name = " ".join(str(name or "").split())[:60]
    if not name:
        raise SharkyClipsError("Type your name to confirm it's your own voice.")
    voice_dir().mkdir(parents=True, exist_ok=True)
    old = read_json(_consent_path()) if _consent_path().is_file() else {}
    write_json_atomic(_consent_path(), {**old, "version": CONSENT_VERSION, "name": name,
                                        "agreed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    return profile()


def revoke() -> dict:
    """Forget the voice: consent, sample, fingerprint (dubbed clips already made stay)."""
    shutil.rmtree(voice_dir(), ignore_errors=True)
    return profile()


def save_sample(src: Path, source: str) -> dict:
    """The user's own recording / file -> <settings>/voice/sample.wav (24 kHz mono, 5-30 s, levelled)."""
    if not profile()["consent"]:
        raise SharkyClipsError("Confirm first that it's your own voice.")
    ffmpeg = require_tool("ffmpeg")
    voice_dir().mkdir(parents=True, exist_ok=True)
    tmp = voice_dir() / "sample.partial.wav"
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-vn", "-t", str(SAMPLE_MAX + 5),
           "-af", "highpass=f=70,silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:"
           "stop_duration=0.6:stop_threshold=-45dB,loudnorm=I=-20:TP=-2",
           "-ac", "1", "-ar", str(TTS_SR), str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, **no_window())
    if r.returncode != 0 or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise SharkyClipsError("This file has no sound SharkyClips can read.", "Record again or pick an audio / video file.")
    import soundfile

    x, sr = soundfile.read(str(tmp), dtype="float32")
    secs = len(x) / sr
    if secs < SAMPLE_MIN:
        tmp.unlink(missing_ok=True)
        raise SharkyClipsError(f"The voice sample is too short ({secs:.0f} s of speech).",
                               f"Speak for at least {SAMPLE_MIN:.0f} seconds, alone, without music.")
    if secs > SAMPLE_MAX:
        soundfile.write(str(tmp), x[: int(SAMPLE_MAX * sr)], sr)
    os.replace(tmp, sample_path())
    (voice_dir() / "fingerprint.npy").unlink(missing_ok=True)
    c = read_json(_consent_path())
    write_json_atomic(_consent_path(), {**c, "sample_source": source if source in ("recorded", "file") else "file",
                                        "sample_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    return profile()


def _sample_hash() -> str:
    return hashlib.sha256(sample_path().read_bytes()).hexdigest()[:16]


def sample_stamp() -> str:
    """Changes with a new voice sample (dubbed clips then count as old)."""
    try:
        st = sample_path().stat()
        return f"{st.st_size}-{int(st.st_mtime)}"
    except OSError:
        return ""


def require_ready(lang: str) -> None:
    p = profile()
    if not p["consent"] or not p["sample"]:
        e = SharkyClipsError("Set up your voice first.", "Settings -> My voice: confirm it's you and record a short sample.")
        e.code = "voice_setup"  # type: ignore[attr-defined]
        raise e
    if lang not in TARGETS:
        names = ", ".join(languages.get(t).english_name for t in TARGETS if languages.get(t))
        raise SharkyClipsError(f"Dubbing into this language isn't possible yet (only {names}).")


# ===================================================================== voice model


def model_dir() -> Path:
    return config.config_dir() / "models" / "tts" / "pocket-int8"


def model_ready() -> bool:
    return all((model_dir() / f).is_file() for f in POCKET_FILES[:-1])


def ensure_model(on_progress: ProgressFn | None = None) -> Path:
    if model_ready():
        return model_dir()
    arch = model_dir().parent / POCKET.name

    def prog(done: int, total: int) -> None:
        if on_progress:
            on_progress("downloading_voice_model", done / max(1, total))

    fetch(POCKET, arch, prog, label="voice model")
    tmp = model_dir().with_name(model_dir().name + ".unpack")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(arch, mode="r:bz2") as tar:
        for name in POCKET_FILES:  # only the known files: no paths from the archive
            f = tar.extractfile(f"{POCKET_DIR}/{name}")
            if f is None:
                raise SharkyClipsError("The voice model archive is incomplete.", "Try again later.")
            (tmp / name).write_bytes(f.read())
    shutil.rmtree(model_dir(), ignore_errors=True)
    os.replace(tmp, model_dir())
    arch.unlink(missing_ok=True)
    return model_dir()


class Voice:
    """Pocket TTS with the user's sample as the voice reference (CPU)."""

    def __init__(self, threads: int = 4):
        import sherpa_onnx as so
        import soundfile

        d = ensure_model()
        cfg = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(
            pocket=so.OfflineTtsPocketModelConfig(
                lm_flow=str(d / "lm_flow.int8.onnx"), lm_main=str(d / "lm_main.int8.onnx"),
                encoder=str(d / "encoder.onnx"), decoder=str(d / "decoder.int8.onnx"),
                text_conditioner=str(d / "text_conditioner.onnx"), vocab_json=str(d / "vocab.json"),
                token_scores_json=str(d / "token_scores.json")),
            num_threads=threads, provider="cpu"))
        self.tts = so.OfflineTts(cfg)
        self.so = so
        ref, sr = soundfile.read(str(sample_path()), dtype="float32")
        self.ref = (ref.mean(axis=1) if ref.ndim > 1 else ref).tolist()
        self.ref_sr = sr

    def say(self, text: str, speed: float = 1.0) -> np.ndarray:
        g = self.so.GenerationConfig()
        g.reference_audio = self.ref
        g.reference_sample_rate = self.ref_sr
        g.speed = float(speed)
        a = self.tts.generate(text, g)
        y = np.asarray(a.samples, dtype=np.float32)
        if int(a.sample_rate) != TTS_SR:
            from .voices.engines import resample

            y = resample(y, int(a.sample_rate), TTS_SR)
        return y

    def close(self) -> None:
        self.tts = None


# ===================================================================== whose line is it


def fingerprint() -> np.ndarray | None:
    """WeSpeaker embedding of the sample (cached next to it)."""
    fp = voice_dir() / "fingerprint.npy"
    if fp.is_file():
        try:
            return np.load(fp)
        except (OSError, ValueError):
            pass
    import soundfile

    from .voices import engines

    x, sr = soundfile.read(str(sample_path()), dtype="float32")
    e = engines.Diarizer().embed(engines.resample(x, sr, 16000))
    if e is not None:
        np.save(fp, e)
    return e


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


@dataclass
class Line:
    start: float
    end: float
    text: str  # translated
    source: str  # original
    spk: str | None = None
    sim: float | None = None
    dub: bool = False
    why: str = ""
    speed: float = 1.0


def decide(lines: list[Line], voice_pass: bool) -> None:
    """Dub only the user's own lines (see the module rules)."""
    for ln in lines:
        if ln.sim is None:
            ln.dub, ln.why = False, "no_voice"
        elif voice_pass:
            ok = ln.spk == "me" and ln.sim >= SAME_ME
            ln.dub, ln.why = ok, "me" if ok else ("other_speaker" if ln.spk != "me" else "not_like_sample")
        else:
            ok = ln.sim >= SAME_ALONE
            ln.dub, ln.why = ok, "like_sample" if ok else "not_like_sample"


def _speaker_of(words: list[dict], a: float, b: float) -> str | None:
    tally: dict[str, float] = {}
    for w in words:
        lo, hi = max(a, w["start"]), min(b, w["end"])
        if hi > lo and w.get("spk"):
            tally[w["spk"]] = tally.get(w["spk"], 0.0) + hi - lo
    return max(tally, key=tally.get) if tally else None


# ===================================================================== audio helpers


def _decode(path: Path, start: float, dur: float, sr: int, channels: int) -> np.ndarray:
    from .edit.music import decode

    y = decode(path, max(0.0, start), dur, sr=sr, channels=channels)
    if start < 0:  # before the file: silence
        pad = np.zeros((int(round(-start * sr)),) + y.shape[1:], np.float32)
        y = np.concatenate([pad, y])
    return y


def separate(x44: np.ndarray, threads: int) -> tuple[np.ndarray, np.ndarray]:
    """(vocals, the rest) of a (n, 2) 44.1 kHz mix, same shape."""
    import sherpa_onnx as so

    from .voices import models

    cfg = so.OfflineSourceSeparationConfig(model=so.OfflineSourceSeparationModelConfig(
        uvr=so.OfflineSourceSeparationUvrModelConfig(model=str(models.ensure("separator"))), num_threads=threads))
    eng = so.OfflineSourceSeparation(cfg)
    out = eng.process(sample_rate=44100, samples=np.ascontiguousarray(x44.T, dtype=np.float32))
    voc = np.asarray(out.stems[0].data, dtype=np.float32).T
    rest = np.asarray(out.stems[1].data, dtype=np.float32).T
    n = min(len(voc), len(x44))
    return voc[:n], rest[:n]


def _stretch(y: np.ndarray, factor: float) -> np.ndarray:
    """Shorter by `factor` (> 1) without changing the pitch (ffmpeg atempo)."""
    if factor <= 1.001:
        return y
    ffmpeg = require_tool("ffmpeg")
    r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "f32le", "-ar", str(TTS_SR), "-ac", "1",
                        "-i", "pipe:0", "-af", f"atempo={factor:.4f}", "-f", "f32le", "pipe:1"],
                       input=y.astype(np.float32).tobytes(), capture_output=True, timeout=120, **no_window())
    if r.returncode != 0:
        return y
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def _resample(y: np.ndarray, a: int, b: int) -> np.ndarray:
    from .voices.engines import resample

    return resample(y, a, b)


def _ramp(n: int) -> np.ndarray:
    return np.linspace(0.0, 1.0, max(1, n), dtype=np.float32)


# ===================================================================== the dub


def folder(project: Project) -> Path:
    return project.cache_dir / "dub"


def _sig(cand: dict, lang: str, lines: list[dict]) -> str:
    raw = json.dumps([round(float(cand["start"]), 2), round(float(cand["end"]), 2), lang,
                      [[round(x["start"], 2), round(x["end"], 2), x["text"]] for x in lines],
                      _sample_hash(), POCKET.sha256[:8], 3], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def track_for(project: Project, cand: dict, lang: str) -> dict | None:
    """The newest finished dub of this clip + language that still matches the clip's cut."""
    best = None
    for meta in sorted(folder(project).glob(f"{cand['id']}_{lang}_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            m = read_json(meta)
        except (OSError, ValueError):
            continue
        wav = meta.with_suffix(".wav")
        if wav.is_file() and m.get("start") <= float(cand["start"]) + 0.05 and m.get("end") >= float(cand["end"]) - 0.05:
            best = {**m, "path": str(wav)}
            break
    return best


def make(project: Project, cand: dict, lang: str, on_progress: ProgressFn | None = None,
         translate: Callable[[], list[dict]] | None = None, voice: Voice | None = None,
         engines_override: dict | None = None) -> dict:
    """Make (or reuse) the dub track of one clip. Returns its info (see track_for)."""
    from . import governor

    require_ready(lang)
    transcript = project.load_transcript() if project.transcript_path.is_file() else {}
    spoken = transcript.get("language")
    if spoken == lang:
        raise SharkyClipsError("This clip is already in that language.")
    if on_progress:
        on_progress("translating", None)
    if translate is not None:
        tr_lines = translate()
    else:
        from .analyze import translate_clip

        tr_lines = translate_clip(project, cand["id"], lang)
    from .textutil import sentences

    src_lines = sentences(transcript, cand["start"], cand["end"]) if transcript else []
    if not tr_lines:
        raise SharkyClipsError("Nothing is said in this clip, so there's nothing to dub.")
    sig = _sig(cand, lang, tr_lines)
    out_wav = folder(project) / f"{cand['id']}_{lang}_{sig}.wav"
    out_meta = out_wav.with_suffix(".json")
    if out_wav.is_file() and out_meta.is_file():
        return {**read_json(out_meta), "path": str(out_wav)}
    from . import llm, memory

    memory.release_current()
    try:
        if llm.server_version(timeout=1.0):
            llm.unload_all()  # the voice model never shares the machine's memory with the LLM
    except Exception:  # noqa: BLE001
        pass
    src = project.source_path
    if src is None:
        raise SharkyClipsError("The project's source video is missing.")
    t0 = max(0.0, float(cand["start"]) - PAD)
    t1 = float(cand["end"]) + PAD
    dur = t1 - t0
    threads = max(1, min(8, governor.cpu_threads(4)))
    if on_progress:
        on_progress("separating_voice", None)
    governor.checkpoint()
    mix44 = _decode(src, t0, dur, 44100, 2)
    sep = (engines_override or {}).get("separate") or separate
    voc44, rest44 = sep(mix44, threads)
    # whose line is it?
    from .voices import load as load_voices

    vp = load_voices(project)
    words = []
    if vp:
        from .edit.plan import transcript_words

        words, _ = transcript_words(project, t0, t1)  # the voice pass's words, with speaker ids
    fp = (engines_override or {}).get("fingerprint")
    sample_fp = fp() if fp else fingerprint()
    embed = (engines_override or {}).get("embed")
    if embed is None:
        from .voices import engines

        dia = engines.Diarizer()
        embed = dia.embed
    lines: list[Line] = []
    for x in tr_lines:
        s0 = next((s for s in src_lines if abs(s["start"] - x["start"]) < 0.05), None)
        ln = Line(float(x["start"]), float(x["end"]), x["text"].strip(), (s0 or {}).get("text", ""))
        ln.spk = _speaker_of(words, ln.start, ln.end) if vp else None
        a, b = int((ln.start - t0) * 44100), int((ln.end - t0) * 44100)
        seg = voc44[max(0, a): max(0, b)].mean(axis=1) if b > a else np.zeros(0, np.float32)
        if len(seg) >= 44100 * 0.6 and sample_fp is not None:
            e = embed(_resample(seg, 44100, 16000))
            ln.sim = None if e is None else round(_cos(e, sample_fp), 3)
        lines.append(ln)
    decide(lines, bool(vp))
    governor.checkpoint()
    # the voice
    n = int(round(dur * SR))
    out = _resample_stereo(mix44, 44100, SR, n)
    voc = _resample_stereo(voc44, 44100, SR, n)
    rest = _resample_stereo(rest44, 44100, SR, n)
    dub_track = np.zeros(n, np.float32)
    mask = np.zeros(n, np.float32)
    todo = [ln for ln in lines if ln.dub]
    own_voice = voice
    if todo and own_voice is None:
        if on_progress:
            on_progress("loading_voice_model", None)
        ensure_model(on_progress)
        own_voice = Voice(threads)
    try:
        for k, ln in enumerate(todo):
            governor.checkpoint()
            if on_progress:
                on_progress("dubbing", k / max(1, len(todo)))
            nxt = next((x.start for x in lines if x.start > ln.start + 0.05), None)
            slot = max(0.4, min(nxt if nxt is not None else ln.end + 0.8, t1) - ln.start - 0.05)
            y = own_voice.say(ln.text, 1.0)
            if len(y) / TTS_SR > slot:
                ln.speed = min(MAX_SPEED, (len(y) / TTS_SR) / slot)
                y = own_voice.say(ln.text, ln.speed)
            if len(y) / TTS_SR > slot:
                y = _stretch(y, min(MAX_STRETCH, (len(y) / TTS_SR) / slot))
            y = _resample(y, TTS_SR, SR)
            room = int(slot * SR)
            if len(y) > room:  # still too long: a short fade out at the slot end
                y = y[:room]
                f = min(len(y), int(0.08 * SR))
                y[-f:] *= _ramp(f)[::-1]
            y = _match_level(y, voc, out, ln, t0)
            a = int((ln.start - t0) * SR)
            b = min(n, a + len(y))
            dub_track[a:b] += y[: b - a]
            ma, mb = a, min(n, int((max(ln.end, ln.start + len(y) / SR) - t0) * SR))
            mask[ma:mb] = 1.0
    finally:
        if own_voice is not None and voice is None:
            own_voice.close()
    mask = _smooth(mask, int(0.05 * SR))
    # my voice out where a dubbed line plays; the game sound stays, 6 dB lower, so the voice bleed
    # the separation leaves behind doesn't compete with the new line
    out = out - voc * mask[:, None] - rest * (mask * (1.0 - BED_GAIN))[:, None] + dub_track[:, None]
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    if peak > 0.99:
        out *= 0.99 / peak
    folder(project).mkdir(parents=True, exist_ok=True)
    import soundfile

    tmp = out_wav.with_name(out_wav.stem + ".partial.wav")
    soundfile.write(str(tmp), out, SR, subtype="PCM_16")
    os.replace(tmp, out_wav)
    info = {"clip": cand["id"], "lang": lang, "spoken": spoken, "start": t0, "end": t1, "offset": t0,
            "made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "voice_pass": bool(vp),
            "lines": [{"start": ln.start, "end": ln.end, "text": ln.text, "source": ln.source, "dub": ln.dub,
                       "why": ln.why, "spk": ln.spk, "sim": ln.sim, "speed": round(ln.speed, 2)} for ln in lines],
            "dubbed": sum(1 for ln in lines if ln.dub), "kept": sum(1 for ln in lines if not ln.dub)}
    write_json_atomic(out_meta, info)
    for old in folder(project).glob(f"{cand['id']}_{lang}_*"):
        if old.stem.split(".")[0] != out_wav.stem and old.suffix in (".wav", ".json"):
            old.unlink(missing_ok=True)
    return {**info, "path": str(out_wav)}


def _resample_stereo(x: np.ndarray, a: int, b: int, n: int) -> np.ndarray:
    ch = [_resample(x[:, c], a, b) for c in range(x.shape[1])]
    y = np.stack(ch, axis=1).astype(np.float32)
    if len(y) < n:
        y = np.concatenate([y, np.zeros((n - len(y), y.shape[1]), np.float32)])
    return y[:n]


def _smooth(mask: np.ndarray, k: int) -> np.ndarray:
    if k <= 1 or not mask.any():
        return mask
    kern = np.ones(k, np.float32) / k
    return np.clip(np.convolve(mask, kern, mode="same"), 0.0, 1.0).astype(np.float32)


def _match_level(y: np.ndarray, voc: np.ndarray, mix: np.ndarray, ln: Line, t0: float) -> np.ndarray:
    """The dubbed line as loud as the original voice was, and clearly on top of the game sound
    (at least ~90 % of the whole mix's level there): the voice always leads, like the streamer did."""
    a, b = int((ln.start - t0) * SR), int((ln.end - t0) * SR)

    def rms(x: np.ndarray) -> float:
        return float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0

    r_ref = max(rms(voc[max(0, a): max(0, b)].mean(axis=1)) if b > a else 0.0,
                0.9 * rms(mix[max(0, a): max(0, b)].mean(axis=1)) if b > a else 0.0)
    r_y = rms(y)
    if r_ref < 1e-4 or r_y < 1e-4:
        return y * 0.5
    g = min(6.0, max(0.25, r_ref / r_y))
    return (y * g).astype(np.float32)


def decode_track(info: dict, source: Path, start: float, duration: float | None, sr: int, channels: int) -> np.ndarray:
    """The clip's audio from `start` (source time) with the dub where it exists, else the source."""
    duration = float(duration if duration is not None else 1.0)
    base = _decode(source, start, duration, sr, channels)
    off = float(info["offset"])
    a, b = max(start, off), min(start + duration, float(info["end"]))
    if b <= a:
        return base
    part = _decode(Path(info["path"]), a - off, b - a, sr, channels)
    i = int(round((a - start) * sr))
    m = min(len(part), len(base) - i)
    if m > 0:
        base = base.copy()
        base[i: i + m] = part[:m]
    return base


def clear(project: Project, cid: str) -> int:
    n = 0
    for p in folder(project).glob(f"{cid}_*"):
        p.unlink(missing_ok=True)
        n += 1
    return n
