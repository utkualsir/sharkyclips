"""Forced alignment (1.2.21): exact word times for bleeps, with a free local CTC model.

Whisper's word times are often 50-200 ms off, so a bleep on them lets "si-" or "-na" slip
through. A CTC acoustic model gives a letter probability every 20 ms; aligning the known
words to it (Viterbi over the letters) gives where each word really starts and ends.

Model: Meta's Omnilingual ASR 300M CTC v2 (Apache-2.0, 1600+ languages including all seven
SharkyClips languages), int8 ONNX by k2-fsa/sherpa-onnx, ~290 MB download, run with
onnxruntime on the CPU (the GPU stays free for Whisper). Downloaded once into
<settings>/models/align.
"""

from __future__ import annotations

import os
import tarfile
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import config, downloads
from ..errors import SharkyClipsError

SR = 16000
REMOTE = downloads.Remote(
    url="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-omnilingual-asr-1600-languages-300M-ctc-v2-int8-2026-02-05.tar.bz2",
    sha256="951b32409aade32bd525310bb39e9666773ba3fc611a39e817f620936d76c631",
    size=292313120, name="omnilingual-ctc-300m-v2-int8.tar.bz2")
FILES = {"model.int8.onnx": "e3042b2f3b3ef0af2211bf99d2b4bf94a21f5ac0e9898827e7dd6d003a860e91",
         "tokens.txt": "7d99997ef207ff14c2cfe825f2aa037528ea250113cc3c6392bfe49326884ba6"}
BLANK = 0
SPACE = " "
MAX_SECONDS = 30.0
# About & licenses (/api/licenses): the swear check's models
LICENSES = [{"name": "Omnilingual ASR 300M CTC v2", "by": "Meta (facebookresearch)", "license": "Apache-2.0",
             "license_url": "https://github.com/facebookresearch/omnilingual-asr/blob/main/LICENSE",
             "source_url": "https://github.com/facebookresearch/omnilingual-asr",
             "changes": "onnx_int8",
             "chain": [{"by": "k2-fsa/sherpa-onnx", "url": "https://github.com/k2-fsa/sherpa-onnx"}]},
            {"name": "Whisper large-v3", "by": "OpenAI", "license": "MIT",
             "license_url": "https://github.com/openai/whisper/blob/main/LICENSE",
             "source_url": "https://huggingface.co/openai/whisper-large-v3",
             "changes": "ct2",
             "chain": [{"by": "Systran (faster-whisper)", "url": "https://huggingface.co/Systran/faster-whisper-large-v3"}]}]
_lock = threading.Lock()


def model_dir() -> Path:
    return config.config_dir() / "models" / "align"


def ready() -> bool:
    return all((model_dir() / f).is_file() for f in FILES)


def ensure(on_progress=None) -> Path:
    """Download + unpack once (only the two files, by name: no paths from the archive)."""
    d = model_dir()
    if ready():
        return d
    import hashlib

    with _lock:
        if ready():
            return d
        tar_path = downloads.fetch(REMOTE, d / REMOTE.name, on_progress, label="word aligner")
        with tarfile.open(tar_path, mode="r:bz2") as tar:
            for m in tar.getmembers():
                name = m.name.rsplit("/", 1)[-1]
                if name not in FILES or not m.isfile():
                    continue
                src = tar.extractfile(m)
                if src is None:
                    continue
                h = hashlib.sha256()
                tmp = d / (name + ".part")
                with open(tmp, "wb") as f:
                    while chunk := src.read(1 << 20):
                        h.update(chunk)
                        f.write(chunk)
                if h.hexdigest() != FILES[name]:
                    tmp.unlink(missing_ok=True)
                    raise SharkyClipsError("The downloaded word aligner is damaged (hash mismatch).")
                os.replace(tmp, d / name)
        if not ready():
            raise SharkyClipsError("The word aligner archive is incomplete.")
        tar_path.unlink(missing_ok=True)
    return d


# ------------------------------------------------------------------------------ text

def letters(word: str, lang: str | None, vocab: dict[str, int]) -> list[int]:
    """Token ids of a word's letters (lowercase; accents dropped only when the model doesn't
    know the accented letter)."""
    w = word.replace("I", "ı").replace("İ", "i") if lang == "tr" else word
    out = []
    for ch in w.lower():
        if ch in vocab and ch != SPACE:
            out.append(vocab[ch])
            continue
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        for c in base:
            if c in vocab and c != SPACE and (c.isalnum()):
                out.append(vocab[c])
    return out


# ------------------------------------------------------------------------------ viterbi

def viterbi(logp: np.ndarray, labels: list[int], blank: int = BLANK) -> list[int] | None:
    """Best CTC path of `labels` through log-probs (T, V). Returns, per frame, the index of
    the label it belongs to (-1 = blank), or None when the audio is too short."""
    T, N = logp.shape[0], len(labels)
    if N == 0:
        return [-1] * T
    ext = [blank]
    for lab in labels:
        ext += [lab, blank]
    S = len(ext)
    need = N + sum(1 for i in range(1, N) if labels[i] == labels[i - 1])
    if T < need:
        return None
    ext_a = np.array(ext)
    emit = logp[:, ext_a]  # (T, S)
    skip_ok = np.zeros(S, bool)
    for s in range(2, S):
        skip_ok[s] = ext[s] != blank and ext[s] != ext[s - 2]
    neg = -1e30
    dp = np.full(S, neg)
    dp[0] = emit[0, 0]
    dp[1] = emit[0, 1]
    back = np.zeros((T, S), np.int8)  # 0 stay, 1 from s-1, 2 from s-2
    for t in range(1, T):
        stay = dp
        one = np.concatenate(([neg], dp[:-1]))
        two = np.where(skip_ok, np.concatenate(([neg, neg], dp[:-2])), neg)
        stack = np.stack([stay, one, two])
        arg = stack.argmax(0)
        dp = stack[arg, np.arange(S)] + emit[t]
        back[t] = arg
    s = S - 1 if dp[S - 1] >= dp[S - 2] else S - 2
    path = [0] * T
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(back[t, s])
    return [(p - 1) // 2 if p % 2 == 1 else -1 for p in path]


# ------------------------------------------------------------------------------ model

@dataclass
class Span:
    start: float
    end: float
    conf: float


class Aligner:
    def __init__(self, threads: int | None = None):
        import onnxruntime as ort

        d = ensure()
        self.vocab: dict[str, int] = {}
        for line in (d / "tokens.txt").read_text(encoding="utf-8").splitlines():
            if not line.strip() and line[:1] != " ":
                continue
            tok, idx = line.rsplit(" ", 1)
            self.vocab[tok if tok else SPACE] = int(idx)
        self.space = self.vocab.get(SPACE)
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(threads or max(1, min(4, (os.cpu_count() or 4) // 2)))
        so.log_severity_level = 3
        self.sess = ort.InferenceSession(str(d / "model.int8.onnx"), so, providers=["CPUExecutionProvider"])

    def logprobs(self, x16: np.ndarray) -> tuple[np.ndarray, float]:
        """(T, V) log-probs and seconds per frame. The space token counts as a blank (a word
        boundary is optional between letters)."""
        x = np.asarray(x16, np.float32)[: int(MAX_SECONDS * SR)]
        x = (x - x.mean()) / (x.std() + 1e-7)
        logits = self.sess.run(None, {"x": x[None, :]})[0][0].astype(np.float32)
        m = logits.max(-1, keepdims=True)
        lp = logits - m - np.log(np.exp(logits - m).sum(-1, keepdims=True))
        if self.space is not None:
            lp[:, BLANK] = np.logaddexp(lp[:, BLANK], lp[:, self.space])
        return lp, (len(x) / SR) / max(1, lp.shape[0])

    def align(self, x16: np.ndarray, words: list[str], lang: str | None) -> list[Span | None]:
        """Where each of `words` (spoken in order inside x16) is, in seconds from x16's start."""
        if len(x16) < SR * 0.2 or not words:
            return [None] * len(words)
        lp, dt = self.logprobs(x16)
        per = [letters(w, lang, self.vocab) for w in words]
        labels, owner = [], []
        for wi, ids in enumerate(per):
            labels += ids
            owner += [wi] * len(ids)
        path = viterbi(lp, labels)
        if path is None:
            return [None] * len(words)
        first: dict[int, int] = {}
        last: dict[int, int] = {}
        probs: dict[int, list[float]] = {}
        for t, li in enumerate(path):
            if li < 0:
                continue
            wi = owner[li]
            first.setdefault(wi, t)
            last[wi] = t
            probs.setdefault(wi, []).append(float(np.exp(lp[t, labels[li]])))
        out: list[Span | None] = []
        for wi in range(len(words)):
            if wi not in first:
                out.append(None)
                continue
            out.append(Span(round(first[wi] * dt, 3), round((last[wi] + 1) * dt, 3),
                            round(float(np.mean(probs[wi])), 3)))
        return out
