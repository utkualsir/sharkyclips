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
    path.parent.mkdir(parents=True, exist_ok=True)
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
        # 1.2.57: from a connected channel (the Library's source line), a long stream title
        "channel": {"key": "kick:layout-vod-1", "id": "kick:democreator", "platform": "kick", "name": "DemoCreator",
                    "own": True, "stream_title": "GECE YAYINI: Delta Force ranked, 55 kill rekor denemesi ve sohbet",
                    "started_at": 1790000000},
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
            "reasons": [{"code": c, "t": s + 1, "strength": 1} for c in ("loudness_spike", "multikill", "pause_burst")[: 1 + i % 3]]
            # 1.2.58: c01 has a game event the animated graphics show (preview-check.mjs pass 3)
            + ([{"code": "df_multikill", "t": s + 1, "value": "3", "strength": 0.85}] if i == 0 else []),
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
    # (1.2.47: an item expires keep-days after deleted_at, so "deleted" an hour ago)
    from datetime import datetime, timedelta, timezone

    _recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    for tid, kind, title, cids in (("20261001-000000-aaaaaa", "project", "LAYOUT CHECK: a deleted stream with a very long title (DELTA FORCE) that wraps", []),
                                   ("20261001-000001-bbbbbb", "clips", "LAYOUT CHECK project", ["c09", "c10"])):
        (ws / "_trash" / tid).mkdir(parents=True)
        _json(ws / "_trash" / tid / "trash.json", {
            "id": tid, "kind": kind, "project_id": "gone-" + tid, "project_title": title, "clip_ids": cids,
            "titles": [TITLES[0], TITLES[1]] if cids else [], "deleted_at": _recent,
            "expires_at": "2099-01-01T00:00:00+00:00", "bytes": 3_400_000_000 if kind == "project" else 12_000_000,
            "files": [], "data": {}, "plans": {}, "posts": None,
            "original": {"path": "C:/Users/me/Videos/a-very-long-recording-name-2026-10-01 19-12-58.mkv", "moved": True,
                         "bytes": 5_000_000_000, "outside_workspace": True} if kind == "project" else None})
    (d / "previews").mkdir()
    _video(d / "previews" / "01_s100_00-00-01.mp4", "180x320", 1.0)
    _channel_style(home)
    _channels(home)
    # 1.2.51: the full video waits on its confirm screen (long title / description / chapters)
    _ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=1:duration=1", "-frames:v", "1", str(d / "full_thumb.jpg"))
    _json(d / "full_upload.json", {"status": "review", "draft": {
        "title": "TOPLAM 55 KILL & 44 REVIVE! LOBİYİ TEK BAŞIMIZA TEMİZLEDİK, KİMSE DURDURAMADI! 🚨💀 (DELTA FORCE)",
        "titles": [TITLES[0], TITLES[3], "TOPLAM 55 KILL & 44 REVIVE! LOBİYİ TEK BAŞIMIZA TEMİZLEDİK! 🚨💀 (DELTA FORCE)"],
        "description": "Delta Force'ta efsane bir maçla karşınızdayım!\n\n⏱️ Bölümler:\n00:00 Giriş\n01:35 İlk kill\n\n"
                       "#DeltaForce #democreator", "chapters": [{"t": 0, "label": "Giriş"}, {"t": 95, "label": "İlk kill"},
                                                              {"t": 300, "label": "Final"}],
        "hashtags": ["#DeltaForce", "#democreator"], "tags": ["Delta Force Türkçe", "democreator"], "category": "20",
        "made_for_kids": False, "language": "tr", "publish_at": "2099-01-01T19:00:00Z",
        "thumbnail": str(d / "full_thumb.jpg") if (d / "full_thumb.jpg").is_file() else None}})
    # 1.2.66 Share clips: every status badge on the board (shared with a link, scheduled, failed,
    # waiting for you to post); fixed dates far from today so the daily count stays the same
    _json(d / "platform_uploads.json", {
        "c03": {"tiktok": {"mode": "semi", "status": "published", "manual": True, "posted_at": "2026-10-02T12:00:00+00:00",
                           "url": "https://www.tiktok.com/@democreator/video/7000000000000000001"}},
        "c08": {"tiktok": {"mode": "api", "status": "scheduled", "publish_at": "2099-01-05T18:00:00+00:00"}},
        "c09": {"tiktok": {"mode": "semi", "status": "failed", "error": {
            "message": "Couldn't save the TikTok file: the disk is full.", "hint": "Free some space, then press Try again.",
            "kind": "fatal"}}},
        # 1.2.70 assisted upload: "did you post it?" on a card
        "c10": {"tiktok": {"mode": "assist", "status": "ready", "assist": {
            "id": "fixtask0000000002", "state": "confirm", "reason": "closed", "browser_name": "Google Chrome"}}},
    })
    # 1.2.70: the assisted-upload bar on every screen (one post filled in and waiting for the click)
    _json(home / "browser" / "assist_tasks.json", {"tasks": [
        {"id": "fixtask0000000001", "project_id": PID, "clip_id": "c02", "platform": "tiktok",
         "title": TITLES[1], "text": "x", "state": "ready", "notes": [], "browser": "chrome",
         "browser_name": "Google Chrome", "created_at": 4102444800, "updated_at": 4102444800, "ready_at": 4102444800,
         "file": "", "file_name": "clip.mp4"}]})
    _stamp_current(home, ws, d)
    _slideshow(home, ws)
    return PID


SLIDESHOW = "layout-check-slideshow-0001"


def _slideshow(home: Path, ws: Path) -> None:
    """1.2.72: a photo slideshow (10 generated pictures, labels, an export) for the slideshow screens."""
    import os
    import sys
    import time

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    old_home = os.environ.get("SHARKYCLIPS_HOME")
    os.environ["SHARKYCLIPS_HOME"] = str(home)
    os.environ.setdefault("SHARKYCLIPS_NO_MIGRATE", "1")
    try:
        import io

        from PIL import Image, ImageDraw

        from sharkyclips import slideshow as S
        from sharkyclips.project import Project

        d = ws / SLIDESHOW
        d.mkdir(parents=True)
        project = Project(SLIDESHOW, d)
        project.save_meta({"title": "Mutfak tadilatı: önce ve sonra, uzun bir başlık denemesi", "kind": "slideshow",
                           "mode": "slideshow", "created_at": "2026-10-02T00:00:00+00:00", "duration": 0.0})
        S.save(project, S.defaults())
        sizes = [(1200, 1600), (1600, 1200), (1000, 1000), (1200, 1600), (4000, 900)]
        for i in range(10):
            w, h = sizes[i % len(sizes)]
            img = Image.new("RGB", (w, h), (40 + 18 * i, 90, 160 - 10 * i))
            dr = ImageDraw.Draw(img)
            for x in range(0, w + h, 80):
                dr.line([(x, 0), (x - h, h)], fill=(200, 200 - 12 * i, 120), width=10)
            buf = io.BytesIO()
            exif = Image.Exif()
            exif.get_ifd(0x8769)[36867] = f"2026:05:{i + 1:02d} 09:00:00"
            img.save(buf, "JPEG", quality=80, exif=exif.tobytes())
            S.add_photo(project, f"IMG_{2040 + i}.jpg", buf.getvalue())
        data = S.load(project)
        data.update(labels=True, subject="Mutfak tadilatı")
        S.active(data)[4]["text"] = "Day 3"
        S.save(project, data)
        (d / "clips").mkdir(exist_ok=True)
        _video(d / "clips" / "slideshow.mp4", "270x480", 3.0, vp9=True)
        lang = S.language_of(project, data)
        S.write_clip(project, {"file": "slideshow.mp4", "duration": S.duration(10, 3.0, True), "width": S.W,
                               "height": S.H, "encoder": "CPU (x264)", "photos": 10,
                               "fingerprint": S.fingerprint(data, lang, S.W)})
        (d / "cache").mkdir(exist_ok=True)
        _video(d / "cache" / "slideshow_preview.mp4", "180x320", 3.0, vp9=True)
        meta = project.load_meta()
        fp = S.fingerprint(data, lang, S.W // S.PREVIEW_SCALE)
        meta["preview"] = {"stamp": f"{fp}{int(time.time())}", "fingerprint": fp}
        project.save_meta(meta)
    finally:
        if old_home is None:
            os.environ.pop("SHARKYCLIPS_HOME", None)
        else:
            os.environ["SHARKYCLIPS_HOME"] = old_home


def _stamp_current(home: Path, ws: Path, d: Path) -> None:
    """1.2.65: mark the grid clips as rendered with exactly the options, cut and fingerprints the
    app wants TODAY (asked from the app itself), so the checks never queue renders. A copied
    options dict went stale with every new Easy option (the 1.2.64 redesign shots queued GPU renders)."""
    import os
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    old_home = os.environ.get("SHARKYCLIPS_HOME")
    os.environ["SHARKYCLIPS_HOME"] = str(home)
    os.environ.setdefault("SHARKYCLIPS_NO_MIGRATE", "1")
    try:
        from sharkyclips import easy as E
        from sharkyclips.clips import ClipOptions
        from sharkyclips.edit import bleepcheck
        from sharkyclips.project import Project
        from sharkyclips.web import easy as WE
        from sharkyclips.web import state

        project = Project(d.name, d)
        hl = state.load_highlights(project)
        review = state.load_review(project, hl)
        data = E.load(project)
        by = {c["id"]: c for c in hl["candidates"]}
        doc = json.loads((d / "clips.json").read_text(encoding="utf-8"))
        style, music_ok, lang = E.hook_style(), WE._music_ok(), WE._lang(project)
        for cid, clip in doc["clips"].items():
            cand = by[cid]
            opts, hook = WE.wanted(project, cand, data, review, style, music_ok, lang)
            eff = state.effective_cand(cand, review)
            clip.update(options={**opts, "hook_text": hook}, start=eff["start"], end=eff["end"],
                        edit_fp=state.edit_fingerprint(cand, review, opts),
                        bleep_fp=bleepcheck.inputs_fingerprint(
                            project, eff, ClipOptions.from_dict({**opts, "hook_text": hook}).to_dict()))
        _json(d / "clips.json", doc)
    finally:
        if old_home is None:
            os.environ.pop("SHARKYCLIPS_HOME", None)
        else:
            os.environ["SHARKYCLIPS_HOME"] = old_home


def _channels(home: Path) -> None:
    """1.2.57 Settings > Channels: an own Kick channel (live, long names, every finished state) and
    someone else's paused YouTube channel. next_check far in the future and no waiting VOD of an
    enabled channel: the server's monitor never goes online or starts a download here."""
    far = 4102444800  # 2100-01-01
    base = 1790000000
    chans = {
        "kick:democreator": {"id": "kick:democreator", "platform": "kick", "handle": "democreator",
                             "name": "DemoCreator_with_a_rather_long_channel_name", "avatar": None,
                             "url": "https://kick.com/democreator", "own": True, "mode": "auto", "game": "auto",
                             # keep_days -1: the "done" stream below is the layout project, whose
                             # source must stay (7 days after a September date = trashed at once)
                             "auto_publish": False, "keep_days": -1, "yt_kinds": "both", "enabled": True,
                             "added_at": base, "baseline": base, "live": True, "live_since": base + 7200,
                             "ended_at": None, "last_check": base + 7300, "next_check": far, "fails": 0,
                             "last_error": None, "last_ok": base + 7300},
        "youtube:UCdemo0000000000000000000": {
            "id": "youtube:UCdemo0000000000000000000", "platform": "youtube", "handle": "UCdemo0000000000000000000",
            "name": "Someone Else", "avatar": None, "url": "https://www.youtube.com/channel/UCdemo0000000000000000000",
            "at": "@someoneelse", "own": False, "mode": "gaming", "game": "delta_force", "auto_publish": False,
            "keep_days": -1, "yt_kinds": "live", "enabled": False, "added_at": base, "baseline": base, "live": False,
            "live_since": None, "ended_at": None, "last_check": base + 3600, "next_check": far, "fails": 2,
            "last_error": "YouTube: HTTP 503", "last_ok": base}}
    long = "GECE YAYINI: Delta Force ranked, 55 kill rekor denemesi, sohbet ve sürprizler (çok uzun bir başlık)"
    rows = [("kick:v-live", "kick:democreator", "live", None, None), ("kick:v-done", "kick:democreator", "done", None, 6),
            ("kick:v-sub", "kick:democreator", "skipped", "subscriber_only", None),
            ("kick:v-gone", "kick:democreator", "gone", "deleted", None),
            ("kick:v-err", "kick:democreator", "error", "download_failed", None),
            ("youtube:v-disk", "youtube:UCdemo0000000000000000000", "waiting_disk", None, None)]
    vods = {}
    for i, (key, ch, st, note, clips) in enumerate(rows):
        vods[key] = {"channel": ch, "platform": ch.split(":")[0], "vod_id": key.split(":")[1],
                     "url": None if st == "live" else f"https://kick.com/democreator/videos/{key}",
                     "title": long if i % 2 == 0 else f"Stream {i}", "started_at": base + 7200 - i * 86400,
                     "duration": None if st == "live" else 3 * 3600 + i * 600, "status": st, "note": note,
                     "clips": clips, "project_id": PID if st == "done" else None, "first_seen": base,
                     "done_at": base + 9000 if st in ("done", "skipped", "gone", "error") else None}
    vods["kick:v-old"] = {"channel": "kick:democreator", "platform": "kick", "vod_id": "v-old", "status": "baseline",
                          "url": "https://kick.com/democreator/videos/v-old", "title": "Old", "started_at": base - 99999,
                          "duration": 7200, "first_seen": base}
    _json(home / "channels.json", {"version": 1, "channels": chans, "vods": vods, "log": []})


def _channel_style(home: Path) -> None:
    """1.2.51: a Channel style profile of a synthetic channel (Studio > Brand kit), analysed by the
    real code, with a preview table of long titles."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
    try:
        from sharkyclips import channelstyle as cs
    except Exception:  # noqa: BLE001 - no backend deps here: the card shows its empty state
        return
    vids = []
    for i in range(24):
        short = i % 3 != 0
        title = (TITLES[i % len(TITLES)] + (" 😂💀" if i % 2 else "")) if short else (
            "DEMİR ELODA AKIL SAĞLIĞIMI KAYBETTİM! VİKTOR İLE 1v9 MAÇ TAŞIDIM! ⚡🤬 (LOL TR)")
        vids.append({"id": f"V{i:03d}", "title": title, "description": "Kanka bu ne ya 😂 Siz olsanız? 👇\n\n"
                     "🎮 Canlı Yayınlar & Sosyal Medya:\n🟩 Kick: https://kick.com/example\n\n#gaming #shorts #example",
                     "tags": ["Delta Force Shorts"], "published_at": f"2026-10-{1 + i % 28:02d}T18:00:00Z",
                     "duration_s": 25 if short else 1800, "views": 100 + (i * 137) % 1600, "likes": 3, "comments": 0,
                     "category": "20", "privacy": "public", "game": "delta_force", "game_name": "Delta Force",
                     "format": "short" if short else "long", "kind": "gaming"})
    data = {"fetched_at": "2026-10-30T00:00:00+00:00", "channel": {"id": "UC0", "title": "Layout Check Channel"},
            "videos": vids}
    prof = cs.analyze(data)
    prof["edits"] = cs.clean_edits({"always_hashtags": ["#example"], "notes": "Samimi ol, küfür yok.",
                                    "extra_rules": ["Başlıkta oyunun adı geçsin"]})
    folder = home / "style"
    folder.mkdir(parents=True, exist_ok=True)
    _json(folder / "channel_videos.json", data)
    _json(folder / "style_profile.json", prof)
    _json(folder / "style_preview.json", {"at": "2026-10-30T00:00:00+00:00", "items": [
        {"id": v["id"], "format": v["format"], "kind": "gaming", "real": v["title"], "views": v["views"],
         "published_at": v["published_at"], "generated": [TITLES[(k + j) % len(TITLES)] for j in range(3)]}
        for k, v in enumerate(vids[:3])]})


if __name__ == "__main__":
    print(build(Path(sys.argv[1]).resolve()))
