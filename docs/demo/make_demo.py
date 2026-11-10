"""Make the synthetic demo stream behind the README screenshots and GIF.

Nothing in it comes from a real stream, game or person: the "game" is drawn by ffmpeg
(gradients, a grid, moving targets, a HUD), the streamer's voice is the operating system's
speech synthesizer reading a script, the facecam is the SharkyClips logo, and the chat log is
generated. So the media can be shown anywhere without anyone's permission.

    python docs/demo/make_demo.py <out-dir>
    -> <out-dir>/neon-drift-demo.mp4 (96 s, 1280x720, 30 fps) and <out-dir>/neon-drift-chat.txt

Then import both into a SharkyClips that runs on a COPY of the settings folder (see
docs/capture.mjs), let Easy mode finish, and run the capture script.

Needs ffmpeg and a speech synthesizer: Windows (System.Speech, built in), macOS (`say`) or
Linux (`espeak-ng`).
"""

from __future__ import annotations

import random
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
REPO = Path(__file__).resolve().parents[2]
LOGO = REPO / "assets" / "icon" / "sharkyclips.png"

# Seven rounds of a made-up arena shooter, 52 s each: calm talk, one big moment, the cool-down.
# Per round: (seconds into the round, text, excited?); the big moment's explosions at BOOM_AT.
ROUND = 52.0  # > the gaming mode's 45 s minimum gap between two highlights
ROUNDS = [
    [(0.6, "Alright chat, welcome back. Round one of Neon Drift, let's warm up.", False),
     (7.0, "I'm going left this time. Last round they camped the bridge the whole game.", False),
     (14.0, "Okay, quiet. I hear footsteps. Somebody is right below us.", False),
     (20.2, "Oh! Oh my god! Double! Did you see that? Two at once!", True),
     (28.0, "Chat is going crazy. Okay, okay, reload, reload.", False),
     (35.0, "That's the round. We take those.", False)],
    [(1.0, "Low health. One shield left and they have three people. This is bad.", False),
     (9.0, "Here we go. One versus three. Just trust me.", False),
     (17.2, "No way! No way! That's one! That's two! Three! Clutch!", True),
     (27.0, "Honestly, I did not think that would work. My hands are shaking.", False),
     (35.0, "Somebody clip that, please.", False)],
    [(1.0, "Question from chat: what sensitivity do I use? Eight hundred DPI, zero point four in game.", False),
     (10.0, "And no, I don't use aim assist. It's all wrist.", False),
     (18.0, "Okay, focus. They're pushing mid.", False),
     (24.2, "Wait, wait, wait. Behind you! Got him! Oh, that was so close!", True),
     (33.0, "Thank you for the follow, appreciate you.", False)],
    [(1.0, "Wait, what is that sound? Is that the boss? Oh no.", False),
     (9.0, "We have no armor. This is a terrible idea.", False),
     (16.2, "Oh shit, run, run, run! It saw us! Go, go, go!", True),
     (26.0, "We made it. Barely. My heart is pounding.", False),
     (34.0, "Okay, new rule, we don't go near the boss.", False)],
    [(1.0, "Thanks for the raid! Welcome in, everybody.", False),
     (8.0, "We are doing ranked tonight. Current score: four wins, two losses.", False),
     (16.0, "Watch this jump. I've been practicing this all week.", False),
     (22.2, "Yes! Yes! I made it! First try! Did everybody see that?", True),
     (32.0, "Okay, that one is going in the highlights for sure.", False)],
    [(1.0, "Last circle. Four teams left, and we're in the worst spot.", False),
     (9.0, "I have one grenade. Let's make it count.", False),
     (17.2, "Grenade out! Triple! What the hell! Three with one grenade!", True),
     (27.0, "Chat, I'm not even going to pretend I planned that.", False),
     (35.0, "Two teams left. Stay calm.", False)],
    [(1.0, "This is it. One on one for the win.", False),
     (8.0, "He's behind the pillar. I can hear his reload.", False),
     (14.2, "Now! Got him! We win! We actually win! Let's go!", True),
     (24.0, "GG everyone. That was the best game of the night.", False),
     (33.0, "Next round we try the bridge. Last one, I promise.", False)],
]
BOOM_AT = [19.9, 16.9, 23.9, 15.9, 21.9, 16.9, 13.9]  # second into each round
DUR = ROUND * len(ROUNDS)
SCRIPT = [(i * ROUND + t, text, hype) for i, r in enumerate(ROUNDS) for t, text, hype in r]
BOOMS = sorted({i * ROUND + b + d for i, b in enumerate(BOOM_AT) for d in (0.0, 2.6)})
CHAT_NAMES = ["pixelfox", "neonbyte", "glitchgoat", "orbitron", "mintbeam", "lazerlynx", "quietkoi",
              "turbotoast", "voidwalker", "sunnyside", "byte_me", "papercrane", "lowpolyleo", "echo_ash"]
CHAT_IDLE = ["hi chat", "gl", "this map is so pretty", "left side again?", "o7", "how many wins today",
             "bridge is cursed", "nice aim", "music?", "lurking", "first time here, love the colors"]
CHAT_HYPE = ["NO WAY", "W", "CLIP IT", "KEKW", "INSANE", "LETS GOOO", "clutch", "WHAT", "😱", "W W W",
             "actual aimbot", "clip that"]


def _run(args: list[str]) -> None:
    kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    subprocess.run(args, check=True, capture_output=True, **kw)


def _font() -> str:
    for f in ("C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/segoeuib.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if Path(f).is_file():
            return f.replace(":", "\\:")
    raise SystemExit("no font found for the HUD")


# ------------------------------------------------------------------ voice


def _speak(lines: list[tuple[str, bool]], out: Path) -> list[Path]:
    """One WAV per line from the OS speech synthesizer (no window, offline)."""
    out.mkdir(parents=True, exist_ok=True)
    files = [out / f"line{i:02d}.wav" for i in range(len(lines))]
    if sys.platform == "win32":
        ps = ["Add-Type -AssemblyName System.Speech",
              "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer"]
        for (text, hype), f in zip(lines, files):
            prosody = 'rate="fast" pitch="+25%" volume="x-loud"' if hype else 'rate="+5%"'
            ssml = (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
                    f'<prosody {prosody}>{text}</prosody></speak>').replace("'", "''")
            ps += [f"$s.SetOutputToWaveFile('{f}')", f"$s.SpeakSsml('{ssml}')"]
        ps.append("$s.Dispose()")
        script = out / "speak.ps1"
        script.write_text("\n".join(ps), encoding="utf-8-sig")
        _run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)])
    elif shutil.which("say"):
        for (text, hype), f in zip(lines, files):
            aiff = f.with_suffix(".aiff")
            _run(["say", "-r", "230" if hype else "185", "-o", str(aiff), text])
            _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), str(f)])
    elif shutil.which("espeak-ng"):
        for (text, hype), f in zip(lines, files):
            _run(["espeak-ng", "-s", "200" if hype else "165", "-p", "70" if hype else "50", "-w", str(f), text])
    else:
        raise SystemExit("no speech synthesizer (Windows System.Speech, macOS say, or espeak-ng)")
    return files


def _read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        n, sr, ch, width = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16 if width == 2 else np.uint8)
    x = raw.astype(np.float32) / (32768.0 if width == 2 else 128.0)
    if width == 1:
        x -= 1.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return np.interp(np.arange(0, len(x), sr / SR), np.arange(len(x)), x).astype(np.float32)


def _audio(work: Path, out: Path) -> None:
    rng = np.random.default_rng(7)
    n = int(DUR * SR)
    t = np.arange(n) / SR
    mix = np.zeros(n, dtype=np.float32)
    # an ambient arena hum: two slow chords + soft noise
    pad = 0.020 * (np.sin(2 * np.pi * 55 * t) + 0.6 * np.sin(2 * np.pi * 82.4 * t) + 0.4 * np.sin(2 * np.pi * 110 * t))
    mix += (pad * (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t))).astype(np.float32)
    mix += (rng.standard_normal(n) * 0.006).astype(np.float32)
    for b in BOOMS:  # explosions: a noise burst with a falling tail
        i, m = int(b * SR), int(0.9 * SR)
        env = np.exp(-np.arange(m) / (0.18 * SR)).astype(np.float32)
        thump = np.sin(2 * np.pi * 48 * np.arange(m) / SR).astype(np.float32)
        mix[i:i + m] += (0.45 * rng.standard_normal(m).astype(np.float32) + 0.5 * thump)[: n - i] * env[: n - i]
    lines = _speak([(text, hype) for _, text, hype in SCRIPT], work / "voice")
    for (start, _, hype), f in zip(SCRIPT, lines):
        v = _read_wav(f)
        v *= (0.95 if hype else 0.55) / max(1e-6, float(np.abs(v).max()))
        i = int(start * SR)
        mix[i:i + len(v)] += v[: n - i]
    mix = np.clip(mix, -1, 1)
    pcm = (np.stack([mix, mix], axis=1) * 32000).astype(np.int16)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ------------------------------------------------------------------ video


def _video(audio: Path, out: Path) -> None:
    font = _font()
    elims = "+".join(["2"] + [f"gte(t\\,{b + 0.3:.1f})" for b in BOOMS])
    health = "300*(0.55+0.45*abs(cos(t*0.09)))"
    rnd = f"1+floor(t/{ROUND:g})"
    flash = "+".join(f"between(t\\,{b + 0.1:.2f}\\,{b + 0.22:.2f})" for b in BOOMS)
    targets = "".join(
        f",drawbox=x='{x0}+{ax}*sin(t*{fx})':y='{y0}+{ay}*cos(t*{fy})':w={s}:h={s}:color={c}@0.85:t=fill"
        for x0, ax, fx, y0, ay, fy, s, c in [(600, 360, 0.7, 330, 90, 1.1, 46, "0xff3d81"),
                                              (420, 220, 1.3, 260, 60, 0.8, 34, "0x2de2e6"),
                                              (820, 260, 0.9, 420, 70, 1.6, 40, "0xf9c80e")])
    cam = (f"color=c=0x0d1424:s=300x226:r=30:d={DUR}[cambg];[1:v]scale=150:150[logo];"
           f"[cambg][logo]overlay=x=75:y='38+6*sin(t*3)'[cam0];"
           f"[cam0]drawbox=x=0:y=0:w=300:h=226:color=0x7f5af0:t=3,"
           f"drawtext=fontfile='{font}':text='LIVE':x=12:y=10:fontsize=18:fontcolor=white:box=1:boxcolor=0xe0245e:boxborderw=4[cam]")
    main = (f"gradients=s=1280x720:c0=0x0b1026:c1=0x241a5e:c2=0x5b1e8c:c3=0x0e2a47:nb_colors=4:speed=0.012:r=30:d={DUR},"
            f"drawgrid=w=80:h=80:t=1:c=0x9d7bff@0.18{targets},"
            "drawbox=x=636:y=340:w=8:h=40:color=white@0.8:t=fill,drawbox=x=620:y=356:w=40:h=8:color=white@0.8:t=fill,"
            f"drawtext=fontfile='{font}':text='NEON DRIFT ARENA  ·  ROUND %{{eif\\:{rnd}\\:d}}':x=32:y=26:fontsize=26:fontcolor=white@0.92,"
            f"drawtext=fontfile='{font}':text='ELIMS %{{eif\\:{elims}\\:d}}':x=w-tw-32:y=26:fontsize=30:fontcolor=0xf9c80e,"
            f"drawbox=x=32:y=668:w=300:h=16:color=white@0.25:t=fill,"
            f"drawbox=x=32:y=668:w='{health}':h=16:color=0x2de2e6@0.95:t=fill,"
            f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.55:t=fill:enable='{flash}'[game]")
    graph = f"{cam};{main};[game][cam]overlay=x=W-w-24:y=H-h-24[v]"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-loop", "1", "-i", str(LOGO),
          "-filter_complex", graph, "-map", "[v]", "-map", "0:a", "-t", str(DUR),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)])


# ------------------------------------------------------------------- chat


def _chat(out: Path) -> None:
    rng = random.Random(11)
    rows: list[tuple[float, str, str]] = []
    t = 0.5
    while t < DUR:  # a calm chat: a message every ~2.5 s
        rows.append((t, rng.choice(CHAT_NAMES), rng.choice(CHAT_IDLE)))
        t += rng.uniform(1.2, 3.8)
    for b in BOOMS:  # and an explosion of messages right after each big moment
        for _ in range(rng.randint(14, 22)):
            rows.append((b + rng.uniform(0.6, 7.0), rng.choice(CHAT_NAMES), rng.choice(CHAT_HYPE)))
    rows.sort()
    lines = [f"[{int(s // 3600)}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}] {name}: {msg}" for s, name, msg in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = Path(sys.argv[1]).resolve()
    work = out / "_work"
    work.mkdir(parents=True, exist_ok=True)
    _audio(work, work / "mix.wav")
    _video(work / "mix.wav", out / "neon-drift-demo.mp4")
    _chat(out / "neon-drift-chat.txt")
    shutil.rmtree(work, ignore_errors=True)
    print(out / "neon-drift-demo.mp4")


if __name__ == "__main__":
    main()
