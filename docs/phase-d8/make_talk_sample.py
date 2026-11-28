"""Synthetic "Just Chatting" sample for the phase D8 measurement (no third-party content).

    python docs/phase-d8/make_talk_sample.py audio <out_dir>      -> <out_dir>/audio.wav (16 kHz mono)
    python docs/phase-d8/make_talk_sample.py chat <out_dir>       -> <out_dir>/chat.json (needs transcript.json)

The voice is Windows' built-in offline speech (SAPI, System.Speech): no download, nothing leaves the
PC. The script has the kinds of moments a talk stream has and kill-only tools miss. Each one has an
ANCHOR phrase, found in the Whisper transcript afterwards, so the measurement knows where each moment
really is:

  joke       a story with a setup, then laughter ("ha ha ha") and "I'm crying"   -> funny / laugh
  silence    11 s of quiet (reading chat), then a loud, high "WHAT? NO WAY!"     -> silence break
  fail       spills coffee: "what did I just do"                                 -> fail
  scream     a jump scare: a loud, high scream                                   -> scream
  chat       a calm line that makes chat explode (KEKW wave, only in chat.json)  -> chat went wild
  marker     "that was amazing ... clip it"                                      -> spoken marker
Between them: calm talk at a normal pitch (the baseline).
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

CALM = [
    "Okay so welcome back everyone, today we are just hanging out and talking about the week.",
    "I went to the store this morning and honestly it was pretty normal, nothing special happened.",
    "Let me check the chat for a second, I see a few new names, welcome welcome.",
    "So the plan for later is maybe some cooking, maybe we read some of your stories, we will see.",
    "The weather here has been kind of grey, which is fine, it is cozy weather for streaming.",
    "Somebody asked about my setup, it is just a normal microphone and an old webcam, nothing fancy.",
    "I have been trying to drink more water this week, so far it is going okay I think.",
    "Alright, next question from chat, what is my favourite snack, probably popcorn to be honest.",
    "I also started reading a new book, it is slow at the start but people say it gets better.",
    "Let me fix my hair real quick, the camera makes it look weird, okay that is better.",
]
MOMENTS = [
    ("joke", [("say", "So my neighbour has this tiny dog, right, and every morning it barks at the mailman like a lion."),
              ("say", "And today the mailman barked back. He just looked at the dog and went woof."),
              ("say", "And the dog fell over. It literally fell over in shock.", {"rate": "fast"}),
              ("say", "Ha ha ha ha ha! Ha ha ha!", {"pitch": "+45%", "rate": "fast", "volume": "x-loud"}),
              ("say", "I'm crying, I can't breathe, that's so funny.", {"pitch": "+25%", "rate": "fast"})]),
    ("silence", [("say", "Okay let me read some messages, give me a second."),
                 ("pause", 11.0),
                 ("say", "WHAT? NO WAY! Are you serious?", {"pitch": "+60%", "volume": "x-loud", "rate": "fast"}),
                 ("say", "Somebody just sent the biggest donation I have ever seen, thank you so much.")]),
    ("fail", [("say", "Hold on, let me grab my coffee, it is right here next to the keyboard."),
              ("say", "Oh no. Oh no no no. I just spilled it all over the desk.", {"pitch": "+30%", "rate": "fast"}),
              ("say", "What did I just do. Why did I do that. I'm so bad at this.", {"pitch": "+20%"})]),
    ("scream", [("say", "Let me show you the scary video everybody keeps sending me, apparently there is a jump scare."),
                ("pause", 3.0),
                ("scream",),  # SAPI speaks "AAAAH" as silence: a synthetic scream is spliced in here
                ("say", "Okay that got me, my heart is beating so fast right now.")]),
    ("chat", [("say", "By the way, I think pineapple on pizza is actually the best topping, and I will not change my mind."),
              ("say", "Yes I know, I know, chat is going crazy right now.")]),
    ("marker", [("say", "Look at this, I finally finished the drawing I started last week."),
                ("say", "That was amazing, honestly my best one so far.", {"pitch": "+20%"}),
                ("say", "Clip it."),
                ("say", "Okay moving on.")]),
]
ANCHOR = {"joke": "ha ha", "silence": "what", "fail": "what did i just do", "scream": "aaa",
          "chat": "pineapple", "marker": "clip it"}
# Whisper usually writes nothing for a wordless scream: then the line right after it is the anchor
FALLBACK = {"scream": ("okay that got me", -3.0)}


HEAD = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
SPLIT = "</speak>|" + HEAD  # a scream goes between two separately spoken parts


def scream(seconds: float = 1.8, sr: int = 16000) -> np.ndarray:
    """A loud, high, wavering voiced 'aaah' (harmonics + vibrato + a little breath noise)."""
    t = np.arange(int(seconds * sr)) / sr
    f0 = 560 + 60 * np.sin(2 * np.pi * 6 * t) - 80 * t / seconds
    phase = 2 * np.pi * np.cumsum(f0) / sr
    x = sum(np.sin(k * phase) / k ** 0.8 for k in range(1, 8))
    env = np.minimum(1, t / 0.08) * np.minimum(1, (seconds - t) / 0.25)
    rng = np.random.default_rng(5)
    return (0.32 * env * x / np.abs(x).max() + 0.01 * rng.normal(size=len(t))).astype(np.float32)


def _ssml() -> str:
    rnd = random.Random(7)
    parts = [HEAD]

    def say(text: str, pros: dict | None = None) -> None:
        if pros:
            attrs = " ".join(f'{k}="{v}"' for k, v in pros.items())
            parts.append(f"<prosody {attrs}>{text}</prosody>")
        else:
            parts.append(text)
        parts.append(f'<break time="{rnd.uniform(0.5, 1.4):.1f}s"/>')

    calm = list(CALM)
    for _name, items in MOMENTS:
        for _ in range(4):  # ~40 s of calm talk before every moment
            say(calm[rnd.randrange(len(calm))])
        for it in items:
            if it[0] == "pause":
                parts.append(f'<break time="{it[1]:.0f}s"/>')
            elif it[0] == "scream":
                parts.append(SPLIT)
            else:
                say(it[1], it[2] if len(it) > 2 else None)
    for _ in range(4):
        say(calm[rnd.randrange(len(calm))])
    parts.append("</speak>")
    return "".join(parts)


def make_audio(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    pieces = []
    for i, part in enumerate(_ssml().split("|")):
        ssml = out / f"talk{i}.ssml"
        ssml.write_text(part, encoding="utf-8")
        raw = out / f"tts{i}.wav"
        ps = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "$f = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, "
            "[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono);"
            f"$s.SetOutputToWaveFile('{raw}', $f);"
            f"$s.SpeakSsml([IO.File]::ReadAllText('{ssml}'));"
            "$s.Dispose()"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, timeout=600,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with wave.open(str(raw), "rb") as w:
            pieces.append(np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0 * 0.6)
        raw.unlink()
        ssml.unlink()
    x = pieces[0]
    for nxt in pieces[1:]:  # each split point is a scream
        x = np.concatenate([x, scream() / 0.6, np.zeros(8000, np.float32), nxt])
    rng = np.random.default_rng(3)
    x = x + rng.normal(0, 0.003, len(x)).astype(np.float32)  # a quiet room, not digital silence
    dest = out / "audio.wav"
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return dest


def anchors(transcript: dict) -> dict[str, float]:
    """moment -> the time its anchor phrase starts in the transcript."""
    words = [(w["start"], "".join(c for c in w["word"].casefold() if c.isalnum() or c == " ").strip())
             for s in transcript["segments"] for w in s.get("words", [])]
    def find(phrase: str, after: float = 0.0) -> float | None:
        toks = phrase.split()
        for i in range(len(words)):
            got = [w for _, w in words[i:i + len(toks)]]
            if words[i][0] >= after and len(got) == len(toks) and all(g.startswith(t) for g, t in zip(got, toks)):
                return round(words[i][0], 2)
        return None

    out = {}
    last = 0.0
    for name, phrase in ANCHOR.items():  # in script order: each anchor comes after the one before
        t = find(phrase, last)
        if t is None and name in FALLBACK:
            fb = find(FALLBACK[name][0], last)
            t = None if fb is None else round(fb + FALLBACK[name][1], 2)
        if t is not None:
            out[name] = t
            last = t
    return out


def make_chat(out: Path) -> Path:
    tr = json.loads((out / "transcript.json").read_text(encoding="utf-8"))
    dur = max(s["end"] for s in tr["segments"]) + 5
    at = anchors(tr)
    rng = random.Random(11)
    normal = ["hi", "hello", "how are you", "nice", "lol", "what are you eating", "first time here",
              "love the stream", "same", "true", "yeah", "cozy", "o7", "hey hey"]
    rows = []
    t = 0.0
    while t < dur:  # ~0.4 messages / s baseline
        t += rng.expovariate(0.4)
        rows.append((t, rng.choice(normal), f"u{rng.randrange(60)}"))
    waves = {"joke": ["KEKW", "LUL", "ahaha", "KEKW KEKW"], "chat": ["KEKW", "OMEGALUL", "NOOOO", "W", "KEKW KEKW KEKW"],
             "silence": ["W", "POGGERS", "W W W"], "fail": ["F", "LUL", "F F"]}
    size = {"joke": 25, "chat": 60, "silence": 30, "fail": 18}
    for name, texts in waves.items():
        if name not in at:
            continue
        base = at[name] + 5  # chat reacts a few seconds later (stream delay + typing)
        for _ in range(size[name]):
            rows.append((base + rng.uniform(0, 8), rng.choice(texts), f"v{rng.randrange(400)}"))
    rows.sort()
    authors: dict[str, int] = {}
    msgs = [[round(t, 2), text, authors.setdefault(a, len(authors))] for t, text, a in rows]
    data = {"version": 1, "status": "ok", "source": "synthetic", "reason": None, "count": len(msgs),
            "authors": len(authors), "messages": msgs}
    dest = out / "chat.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    (out / "anchors.json").write_text(json.dumps(at, indent=1), encoding="utf-8")
    return dest


if __name__ == "__main__":
    step, folder = sys.argv[1], Path(sys.argv[2])
    print(make_audio(folder) if step == "audio" else make_chat(folder))
