"""Transcript helpers shared by the LLM tasks: sentence lines with timestamps."""

from __future__ import annotations

SENTENCE_END = tuple(".!?。！？…؟")
NO_SPACE_LANGS = {"zh", "ja"}


def words_between(transcript: dict, start: float, end: float) -> list[dict]:
    out = []
    for seg in transcript.get("segments", []):
        if seg["end"] < start or seg["start"] > end:
            continue
        for w in seg.get("words", []):
            mid = (w["start"] + w["end"]) / 2
            if start <= mid <= end and w["word"].strip():
                out.append(w)
    return out


def sentences(transcript: dict, start: float = 0.0, end: float = float("inf"),
              max_words: int = 22, max_gap: float = 1.2) -> list[dict]:
    """Group words into sentence-like lines: {start, end, text}, split at punctuation,
    long pauses, or max_words."""
    lang = transcript.get("language")
    joiner = "" if lang in NO_SPACE_LANGS else " "
    lines: list[dict] = []
    cur: list[dict] = []

    def flush() -> None:
        if cur:
            text = joiner.join(w["word"].strip() for w in cur)
            lines.append({"start": round(cur[0]["start"], 2), "end": round(cur[-1]["end"], 2), "text": text})
            cur.clear()

    for w in words_between(transcript, start, end):
        if cur and (w["start"] - cur[-1]["end"] > max_gap or len(cur) >= max_words):
            flush()
        cur.append(w)
        if w["word"].strip().endswith(SENTENCE_END):
            flush()
    flush()
    return lines


def mmss(t: float) -> str:
    t = max(0, int(round(t)))
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
