"""LLM signal (study mode): the local LLM reads the transcript in overlapping windows and
marks self-contained explanations - the parts that still make sense as a standalone clip.

Reason: llm_explanation, value = the topic in a few words.
Needs Ollama; without it the signal is skipped and the other study signals still work.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
from scipy.ndimage import gaussian_filter1d

from ... import config
from ...errors import SharkyClipsError
from ...ui import console
from ...textutil import mmss, sentences
from .base import ReasonEvent, Signal, SignalResult, SignalUnavailable, clip01, register

WINDOW_S = 150.0
HOP_S = 90.0
PROMPT_VERSION = 1

SYSTEM = (
    "You are an expert short-video editor for educational content. You read a transcript and "
    "find passages that would work as a standalone 30-60 second clip: a complete explanation, "
    "definition, tip, or answer that a viewer understands without the rest of the video. "
    "Only use line numbers that exist. Answer only with JSON."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "passages": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "first_line": {"type": "integer", "minimum": 1},
                    "last_line": {"type": "integer", "minimum": 1},
                    "self_contained": {"type": "boolean"},
                    "usefulness": {"type": "integer", "minimum": 0, "maximum": 10},
                    "topic": {"type": "string", "minLength": 2, "maxLength": 60},
                },
                "required": ["first_line", "last_line", "self_contained", "usefulness", "topic"],
            },
        }
    },
    "required": ["passages"],
}


@register
class LLMStudySignal(Signal):
    name = "llm"
    version = PROMPT_VERSION
    cacheable = True

    def check(self, ctx) -> None:
        from ... import llm

        if not ctx.transcript:
            raise SignalUnavailable("no transcript yet")
        if config.get("llm_enabled") is False:
            raise SignalUnavailable("LLM disabled in config (llm_enabled: false)")
        if llm.ollama_exe() is None and not llm.server_version():
            raise SignalUnavailable("Ollama not installed - run `python cli.py doctor`")

    def cache_key(self, ctx) -> str:
        from ... import llm

        payload = {"v": self.version, "t": ctx.transcript_fingerprint, "m": llm.choose_model()}
        return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def compute(self, ctx) -> SignalResult:
        from ... import llm
        from ...ui import time_progress

        n = ctx.n
        scores = np.zeros(n)
        best_topic: dict[int, tuple[float, str]] = {}
        windows = []
        t = 0.0
        while t < ctx.duration:
            windows.append((t, min(ctx.duration, t + WINDOW_S)))
            if t + WINDOW_S >= ctx.duration:
                break
            t += HOP_S
        title = ctx.meta.get("title") or ""
        found = 0
        with llm.session() as model, time_progress() as prog:
            task = prog.add_task("LLM reading", total=ctx.duration)
            for w0, w1 in windows:
                lines = sentences(ctx.transcript, w0, w1)
                if len(" ".join(x["text"] for x in lines)) < 200:
                    prog.update(task, completed=w1)
                    continue
                listing = "\n".join(f"L{i + 1} [{mmss(x['start'])}] {x['text']}" for i, x in enumerate(lines))
                prompt = (f"Video title: {title}\nTranscript language: {ctx.language}\n\n{listing}\n\n"
                          "List up to 4 passages (by line numbers) that would make good standalone "
                          "educational clips of roughly 25-60 seconds. Rate usefulness 0-10. "
                          "Write the topic in English. Return an empty list if nothing qualifies.")

                def check(data: dict, k=len(lines)) -> list[str]:
                    return [f"passage {i + 1}: line numbers must be between 1 and {k} and first <= last"
                            for i, p in enumerate(data["passages"])
                            if not (1 <= p["first_line"] <= p["last_line"] <= k)]

                try:
                    data = model.json(SYSTEM, prompt, SCHEMA, temperature=0.3, soft=check, num_predict=700)
                except SharkyClipsError as exc:  # one bad window must not cost the whole signal
                    console.print(f"[yellow]LLM skipped {mmss(w0)}-{mmss(w1)}: {exc.message[:120]}[/]")
                    prog.update(task, completed=w1)
                    continue
                for p in data["passages"]:
                    if not (1 <= p["first_line"] <= p["last_line"] <= len(lines)):
                        continue  # a line number that doesn't exist
                    a = lines[p["first_line"] - 1]["start"]
                    b = lines[p["last_line"] - 1]["end"]
                    if not p["self_contained"] or b - a < 12:
                        continue
                    v = p["usefulness"] / 10.0
                    lo, hi = int(a), min(n, int(b) + 1)
                    scores[lo:hi] = np.maximum(scores[lo:hi], v)
                    mid = int((a + b) / 2)
                    if mid < n and v > best_topic.get(mid, (0, ""))[0]:
                        best_topic[mid] = (v, p["topic"])
                    found += 1
                prog.update(task, completed=w1)
            calls, secs = model.calls, model.seconds
        # Soft edges, so the candidate picker sees one plateau per passage.
        scores = clip01(gaussian_filter1d(scores, 2.0))
        events = [ReasonEvent(float(t), "llm_explanation", topic, v) for t, (v, topic) in sorted(best_topic.items())]
        return SignalResult(self.name, scores, events,
                            {"model": llm.choose_model(), "windows": len(windows), "passages": found,
                             "llm_calls": calls, "llm_seconds": round(secs, 1)})
