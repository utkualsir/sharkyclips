"""Build a throwaway SharkyClips settings folder + workspace for the layout check.

One synthetic project like a real stream: 18 candidates with long titles (some accepted), several
rendered clips, a hype curve, a facecam, a scheduled-publishing Library row. Nothing from a real
user. Tiny test videos come from ffmpeg (testsrc2) when it is installed; without ffmpeg the files
are placeholders (the layout doesn't need playable video).

Usage: python frontend/scripts/layout-fixture.py <folder>   -> prints the project id
Then:   SHARKYCLIPS_HOME=<folder>/home python backend/cli.py serve --port 8799 --no-browser
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

PID = "layout-check-stream-0001"
N_CANDS = 18
N_CLIPS = 6  # the Easy grid shows the best 6: all rendered, so the check starts no render jobs
SECONDS = 60.0

# Easy mode's render settings (backend/sharkyclips/easy.py DEFAULT_OPTIONS): the clips count as
# rendered in both modes.
OPTIONS = {"layout": "auto", "subtitles": "bold", "hook": True, "hook_flash": False, "subtitle_lang": "",
           "profanity": "bleep", "profanity_captions": True, "bleep_sound": "classic", "speaker_colors": True,
           "speaker_names": False, "cuts": "off", "zoom": "off", "music": False, "brand": False, "loop": False}
# 1.2.34 Easy 2.0 adds these for a gaming project with a facecam (easy.v2_options)
EASY2 = {"cuts": "light", "safe_zone": "shorts", "banner": ""}

TITLES = [
    "Takım arkadaşım beni neden bıraktı, son saniyede inanılmaz bir geri dönüş",
    "Clutch 1v4 on the last round with no armor and half health left",
    "Kanka neden böyle oldu?",
    "Helikopterden atlayıp dört kişiyi birden indirdiğimiz o efsane an",
    "Wait for it… the most unexpected revive of the whole stream",
    "Sürekli önünden arkasından çıkıp duruyorlar",
    "لحظة لا تصدق في آخر ثانية من المباراة",
    "Altına atılan herkes neden öyle yere düştü",
]


def _ff(*args: str) -> None:
    ff = shutil.which("ffmpeg")
    if ff:
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", *args], check=True, capture_output=True)


def _video(path: Path, size: str, seconds: float, vp9: bool = False) -> None:
    """vp9: playable in Playwright's own Chromium (no H.264 there), for the preview check."""
    if shutil.which("ffmpeg"):
        codec = (["-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "600k", "-g", "15"] if vp9
                 else ["-c:v", "libx264", "-preset", "ultrafast"])
        _ff("-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={seconds}", "-f", "lavfi", "-i",
            f"sine=frequency=300:sample_rate=48000:duration={seconds}", *codec,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path))
    else:
        path.write_bytes(b"\0" * 1000)


def _json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def build(root: Path) -> str:
    home, ws = root / "home", root / "ws"
    shutil.rmtree(root, ignore_errors=True)
    d = ws / PID
    (d / "clips").mkdir(parents=True)
    home.mkdir(parents=True)
    version = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
    _json(home / "config.json", {"workspace_dir": str(ws), "onboarding_done": True, "llm_enabled": False,
                                 "publish_auto": False, "ui_language": "en", "ui_motion": "off",
                                 "seen_version": version, "easy_tour_done": True,  # no popups over the page
                                 "easy_banner": False})  # 1.2.34: banner text off, so the renders stay current
    _video(d / "source.mp4", "640x360", SECONDS, vp9=True)
    _json(d / "meta.json", {
        "id": PID, "title": "LAYOUT CHECK: a very long stream title that has to wrap over two lines and get cut off (DELTA FORCE)",
        "mode": "gaming", "duration": SECONDS, "resolution": "640x360", "width": 640, "height": 360, "fps": 30.0,
        "audio_codec": "aac", "video_codec": "vp9", "files": {"source": "source.mp4"},
        "source": {"type": "file", "value": "source.mp4"}, "created_at": "2026-10-01T00:00:00+00:00",
        "transcript": {"language": "tr", "segments": 1, "words": 40}})
    # c01 (1.0-3.6 s) holds one of Whisper's endless "words" on silence: it must not stretch the
    # page (preview-check.mjs; the 1.2.22 "preview zooms in and shifts" report)
    junk = {"start": 2.25, "end": 2.45, "word": " Z" + "z" * 300}
    tr_words = [{"start": 0.5 + i, "end": 1.2 + i, "word": f" kelime{i}"} for i in range(48)]
    _json(d / "transcript.json", {"language": "tr", "segments": [
        {"start": 0.5, "end": 50.0, "words": sorted([*tr_words, junk], key=lambda w: w["start"])}]})
    # "Hear every speaker" result: three voices, swears from a friend (swear review list, speaker chips)
    spoken = ["abi", "amına", "koyayım", "kanka", "siktir", "git", "orosbu", "geldim", "s**yim", "tamam"]
    _json(d / "voices.json", {
        "version": 1, "mode": "separate", "whole": False, "language": "tr", "ranges": [[0.0, SECONDS]],
        "tracks": [{"pos": 0, "title": "", "codec": "aac", "channels": 2, "label": "mixed"}], "labels_from": "guess",
        "speakers": {"me": {"seconds": 30.0}, "f1": {"seconds": 12.0}, "f2": {"seconds": 6.0}},
        "names": {"f1": "Efe Can Yıldırımoğlu"}, "separated": True, "diarized": True, "hints": [],
        "transcript_created_at": None, "created_at": "2026-10-01T00:00:00",
        "words": sorted([{"start": 0.5 + i, "end": 1.2 + i, "word": spoken[i % len(spoken)] if i % 3 else f"kelime{i}",
                   "p": 0.6 if i % 4 else 0.3, "spk": ("me", "f1", "f2")[(i // 4) % 3], "src": "voc"}
                  for i in range(48)] + [{**junk, "p": 0.4, "spk": "me", "src": "voc"}], key=lambda w: w["start"])})
    cands = []
    for i in range(N_CANDS):
        s = 1.0 + i * (SECONDS - 8) / N_CANDS
        dur = 2.6
        cands.append({
            "id": f"c{i + 1:02d}", "rank": i + 1, "start": round(s, 2), "end": round(s + dur, 2), "duration": dur,
            "peak": round(s + 1.2, 2), "hype_score": 100 - i * 4, "score": 0.95 - i * 0.03,
            "text": TITLES[i % len(TITLES)],
            "reasons": [{"code": c, "t": s + 1, "strength": 1} for c in ("loudness_spike", "multikill", "pause_burst")[: 1 + i % 3]],
            "signal_scores": {"loudness": 0.9, "laughter": 0.1, "keywords": 0.5, "speech": 0.8, "game": 0.6},
            "publish": {"available": True, "viral_score": 92 - i * 3, "viral_label": ("high", "medium", "low")[i % 3],
                        "titles": [TITLES[(i + 3) % len(TITLES)], "Alt title"], "hashtags": ["#shorts", "#gaming"],
                        "description": "A moment.\n\n#shorts #gaming", "cover_text": "NO WAY", "language": "tr"}})
    _json(d / "highlights.json", {"version": 1, "project_id": PID, "mode": "gaming", "language": "tr",
                                  "duration": SECONDS, "created_at": "2026-10-01T00:00:00+00:00", "candidates": cands})
    curve = [round(50 + 45 * math.sin(i / 3.0) * math.cos(i / 11.0)) for i in range(int(SECONDS))]
    _json(d / "hype_curve.json", {"version": 1, "project_id": PID, "mode": "gaming", "duration": SECONDS,
                                  "resolution_s": 1, "scale": 100, "combined": curve})
    _json(d / "review.json", {"highlights_created_at": "2026-10-01T00:00:00+00:00", "accepted": ["c01", "c02", "c04"],
                              "hooks": {}, "options": OPTIONS,
                              "facecam": {"x": 0.02, "y": 0.6, "w": 0.25, "h": 0.33, "source": "auto", "confidence": 0.9},
                              "facecam_checked": True})
    clips = {}
    for i in range(N_CLIPS):
        c = cands[i]
        name = f"{i + 1:02d}_{c['id']}.mp4"
        _video(d / "clips" / name, "180x320", 2.0)
        clips[c["id"]] = {"file": name, "id": c["id"], "rank": c["rank"], "start": c["start"], "end": c["end"],
                          "duration": c["duration"], "options": {**OPTIONS, **EASY2, "hook_text": ""},
                          "facecam": {}, "rendered_at": "2026-10-01T10:00:00+00:00",
                          "size_bytes": (d / "clips" / name).stat().st_size, "render_seconds": 3.0, "encoder": "CPU"}
    _json(d / "clips.json", {"version": 1, "clips": clips})
    # Easy 2.0 (1.2.34): every grid clip is already shaped (no shape job), with the longest texts
    whys = [["setup_sentence", "payoff_reaction"], ["setup_lead"], [], ["ai_setup", "payoff_sentence"], ["hook_later"], []]
    hooks = [{"score": 71, "before": 47, "choice": "flash", "moved": 0.0}, {"score": 66, "before": 66, "choice": "start", "moved": 0.0},
             {"score": 44, "before": 44, "choice": "start", "moved": 0.0}, {"score": 59, "before": 50, "choice": "later", "moved": 4.5},
             {"score": 80, "before": 52, "choice": "later", "moved": 1.5}, {"score": 55, "before": 55, "choice": "start", "moved": 0.0}]
    shapes = {}
    for i in range(N_CLIPS):
        c = cands[i]
        shapes[c["id"]] = {"shape": {"v": 1, "base": [c["start"], c["end"]], "start": c["start"], "end": c["end"],
                                     "why": whys[i], "target": {"kind": "action", "min": 20.0, "max": 35.0},
                                     "hook": {**hooks[i], "reasons": [], "options": []}, "flash": False}}
    _json(d / "easy.json", {"easy": True, "mode_auto": True, "shown": 6, "clips": shapes, "v2": True,
                            "notified_for": "2026-10-01T00:00:00+00:00"})
    # 1.2.41: the trash holds a long-named project and two clips (the trash page and its rows)
    for tid, kind, title, cids in (("20261001-000000-aaaaaa", "project", "LAYOUT CHECK: a deleted stream with a very long title (DELTA FORCE) that wraps", []),
                                   ("20261001-000001-bbbbbb", "clips", "LAYOUT CHECK project", ["c09", "c10"])):
        (ws / "_trash" / tid).mkdir(parents=True)
        _json(ws / "_trash" / tid / "trash.json", {
            "id": tid, "kind": kind, "project_id": "gone-" + tid, "project_title": title, "clip_ids": cids,
            "titles": [TITLES[0], TITLES[1]] if cids else [], "deleted_at": "2026-10-01T00:00:00+00:00",
            "expires_at": "2099-01-01T00:00:00+00:00", "bytes": 3_400_000_000 if kind == "project" else 12_000_000,
            "files": [], "data": {}, "plans": {}, "posts": None,
            "original": {"path": "C:/Users/me/Videos/a-very-long-recording-name-2026-10-01 19-12-58.mkv", "moved": True,
                         "bytes": 5_000_000_000, "outside_workspace": True} if kind == "project" else None})
    (d / "previews").mkdir()
    _video(d / "previews" / "01_s100_00-00-01.mp4", "180x320", 1.0)
    return PID


if __name__ == "__main__":
    print(build(Path(sys.argv[1]).resolve()))
