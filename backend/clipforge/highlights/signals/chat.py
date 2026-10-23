"""Chat activity: messages per second against a rolling baseline, plus reaction spam.

Chat reacts a few seconds after the moment (stream delay + typing), so the curve is
shifted earlier by `chat_delay` seconds (config, default 5).

Reasons:
  chat_spike      value "5.2x" = message rate vs. the usual rate around that time
  chat_reactions  value = the most spammed reaction ("KEKW", "ahahah", "????")
"""

from __future__ import annotations

import functools
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter, uniform_filter1d

from ... import config
from ...chat import load_chat
from .base import ReasonEvent, Signal, SignalResult, SignalUnavailable, clip01, local_peaks, register

PATTERNS_FILE = Path(__file__).resolve().parents[1] / "triggers" / "chat_reactions.json"
MIN_MESSAGES = 30
WINDOW_S = 5  # reaction burst window
BASELINE_S = 121  # rolling median window for "usual" chat speed


@functools.lru_cache(maxsize=1)
def _patterns() -> tuple[re.Pattern, re.Pattern]:
    data = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    whole, contains = [], []
    for key, lists in data.items():
        if key.startswith("_"):
            continue
        whole += lists.get("whole", [])
        contains += lists.get("contains", [])
    return (re.compile(r"^(?:" + "|".join(whole) + r")$", re.I),
            re.compile("|".join(contains), re.I))


def _norm(text: str) -> str:
    t = text.casefold().strip()
    return re.sub(r"(.)\1{2,}", r"\1\1", t)  # "kekwwwww" ~ "kekww", "?????" ~ "??"


def is_reaction(text: str) -> bool:
    whole, contains = _patterns()
    t = text.strip()
    return bool(whole.match(t) or contains.search(t))


@register
class ChatSignal(Signal):
    name = "chat"
    version = 2

    def check(self, ctx) -> None:
        chat = load_chat(ctx.project)
        if chat is None:
            raise SignalUnavailable("no chat replay (run `python cli.py chat <id>` or import a log)")
        if chat.get("status") != "ok":
            raise SignalUnavailable(chat.get("reason") or "no chat")
        if chat.get("count", 0) < MIN_MESSAGES:
            raise SignalUnavailable(f"only {chat.get('count', 0)} chat messages")

    def compute(self, ctx) -> SignalResult:
        chat = load_chat(ctx.project)
        delay = float(config.get("chat_delay") or 5)
        n = ctx.n
        rate = np.zeros(n)
        react = np.zeros(n)
        react_text: dict[int, Counter] = {}
        msgs = chat["messages"]

        # Copy-paste waves: the same short message from 3+ people within a few seconds.
        by_text: dict[str, list[tuple[float, int]]] = {}
        for t, text, author in msgs:
            by_text.setdefault(_norm(text)[:40], []).append((t, author))
        wave_keys = set()
        for key, items in by_text.items():
            if len(items) < 3 or len(key) > 40 or (key.isdigit() and len(key) <= 2):
                continue  # short numbers are poll votes, not reactions
            times = [x[0] for x in items]
            for i in range(len(times) - 2):
                if times[i + 2] - times[i] <= WINDOW_S and len({items[j][1] for j in range(i, i + 3)}) >= 3:
                    wave_keys.add(key)
                    break

        for t, text, _author in msgs:
            s = int(t - delay)
            if s < 0 or s >= n:
                continue
            rate[s] += 1
            key = _norm(text)[:40]
            if is_reaction(text) or key in wave_keys:
                react[s] += 1
                react_text.setdefault(s, Counter())[text.strip()[:24]] += 1

        rate5 = uniform_filter1d(rate, WINDOW_S, mode="constant")
        react5 = uniform_filter1d(react, WINDOW_S, mode="constant")
        mean = max(rate.mean(), 1e-3)
        baseline = median_filter(rate5, size=min(BASELINE_S, max(3, n // 2 * 2 - 1)), mode="nearest")
        baseline = np.maximum(baseline, mean * 0.4)
        ratio = rate5 / baseline
        # How unusual is this many messages? Ratio alone overrates sparse chats (2 msgs = "8x"),
        # so the spike is also capped by a Poisson-style z-score over a 10 s window.
        count10 = uniform_filter1d(rate, 10, mode="constant") * 10
        expected10 = baseline * 10
        z = (count10 - expected10) / np.sqrt(expected10 + 1.0)
        spike = np.minimum(clip01(np.log2(np.maximum(ratio, 1e-6)) / np.log2(6)),  # 6x usual = 1.0
                           clip01(z / 5.0))
        burst = np.minimum(clip01(react5 / (baseline * 1.5)), clip01(react5 * WINDOW_S / 4.0))
        scores = clip01(0.65 * spike + 0.35 * burst)

        events = []
        for p in local_peaks(scores, 0.4, 20):
            events.append(ReasonEvent(float(p), "chat_spike", f"{ratio[p]:.1f}x", float(scores[p])))
            if react5[p] >= 0.5 * rate5[p] and react5[p] * WINDOW_S >= 3:
                window = Counter()
                for s in range(max(0, p - WINDOW_S), min(n, p + WINDOW_S + 1)):
                    window.update(react_text.get(s, {}))
                if window:
                    events.append(ReasonEvent(float(p), "chat_reactions", window.most_common(1)[0][0],
                                              float(burst[p])))
        meta = {"messages": len(msgs), "authors": chat.get("authors"), "source": chat.get("source"),
                "per_minute": round(len(msgs) / max(1, ctx.duration / 60), 1), "delay_s": delay,
                "reaction_share": round(float(react.sum() / max(1, rate.sum())), 3)}
        return SignalResult(self.name, scores, events, meta)
