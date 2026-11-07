"""Transcript helpers shared by the LLM tasks: sentence lines with timestamps."""

from __future__ import annotations

import re

SENTENCE_END = tuple(".!?。！？…؟")
NO_SPACE_LANGS = {"zh", "ja"}

# Whisper sometimes "hears" one endless word on silence or snoring ("Zzzzzz..." x 300) or
# writes broken bytes. One such word stretched the whole project page (1.2.23) and would run
# off the burned-in captions, so words are cleaned whenever a transcript is read or written.
MAX_WORD = 40  # longer than any real word in the 7 UI languages (and still fits a caption)
_RUN = re.compile(r"(\w)\1{4,}", re.UNICODE)  # 5+ times the same letter -> 3
_JUNK = re.compile("[�\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]")


def clean_word(word: str) -> str:
    """The word as captions can show it ("" = drop it). Keeps the leading space Whisper uses."""
    if not word:
        return word
    w = _JUNK.sub("", word)
    w = _RUN.sub(lambda m: m.group(1) * 3, w)
    lead = " " if w[:1].isspace() else ""
    core = w.strip()
    if len(core) > MAX_WORD:
        core = core[:MAX_WORD - 1] + "…"
    return lead + core if core else ""


def clean_words(words: list[dict]) -> list[dict]:
    """Copies of the words with clean text; words that are pure junk are left out."""
    out = []
    for w in words:
        text = w.get("word")
        if not isinstance(text, str):
            out.append(w)
            continue
        new = clean_word(text)
        if new == text:
            out.append(w)
        elif new.strip():
            out.append({**w, "word": new})
    return out


def clean_transcript(transcript: dict) -> dict:
    """Cleans the words and segment texts in place (idempotent) and returns the transcript."""
    for seg in transcript.get("segments", []) or []:
        if seg.get("words"):
            seg["words"] = clean_words(seg["words"])
        text = seg.get("text")
        if isinstance(text, str):
            cleaned = " ".join(t for t in (clean_word(x) for x in text.split()) if t)
            if cleaned != " ".join(text.split()):
                seg["text"] = (" " if text[:1].isspace() else "") + cleaned
    return transcript


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
