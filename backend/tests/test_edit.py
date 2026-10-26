"""Phase 10 (1.2.4): editing power tools - swear words, fillers, silence cuts, zoom, the sound
mix (crossfades, bleeps, ducking, -14 LUFS), music library, brand kit, manual clips."""

from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import config
from sharkyclips.clips import ClipOptions, OutputSpec
from sharkyclips.edit import audiomix, brand, fillers, loudness, manual, music, plan, profanity, silence, words, zoom
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic


def W(*items):
    """[(start, end, word), ...] -> transcript words."""
    return [{"start": a, "end": b, "word": w} for a, b, w in items]


# ------------------------------------------------------------------ word matching


def test_turkish_dotless_i_rules():
    lst = words.compile_entries(["amına*", "sik", "siki*"], "tr")
    found = words.find(["Amina", "AMINA", "amınakim.", "sıkıntı", "sık", "sikik", "SIKINTI"], lst, "tr")
    hit = {i for a, b, _e in found for i in range(a, b + 1)}
    # ı in the list also finds a typed i; i in the list never finds ı ("sıkıntı" = trouble)
    assert hit == {0, 1, 2, 5}
    assert 3 not in hit and 4 not in hit
    assert 6 not in hit  # Turkish capitals: the I in "SIKINTI" is ı


def test_accents_phrases_and_cjk():
    de = words.compile_entries(["scheisse*"], "de")
    assert words.find(["Scheiße!"], de, "de")
    hu = words.compile_entries(["picsa*"], "hu")
    assert words.find(["picsába"], hu, "hu")
    ar = words.compile_entries(["كس امك"], "ar")
    assert words.find(["يا", "كس", "امك"], ar, "ar") == [(1, 2, "كس امك")]
    zh = words.compile_entries(["他妈的"], "zh")
    assert words.find(["我", "他妈", "的", "操作"], zh, "zh") == [(1, 2, "他妈的")]
    assert profanity.find_words(W((0, 1, "操作"), (1, 2, "很好")), "zh") == []  # "operate" is fine


def test_mask():
    assert words.mask("ass") == "a**"
    assert words.mask("Amına,") == "A****,"
    assert words.mask("«fuck»") == "«f***»"
    assert words.mask("傻逼") == "**"


def test_profanity_lists_per_language_and_custom():
    for lang in ("tr", "en", "de", "hu", "ru", "ar", "zh"):
        assert profanity.DEFAULTS[lang], lang
    ws = W((0, 0.4, "Bu"), (0.4, 0.9, "amına"), (0.9, 1.3, "koyim"), (1.3, 2, "kahpe!"))
    assert profanity.find_words(ws, "tr") == [1, 3]
    assert profanity.find_words(W((0, 1, "what"), (1, 2, "the"), (2, 3, "fuck")), "en") == [2]
    assert profanity.find_words(W((0, 1, "Блять,"), (1, 2, "сука")), "ru") == [0, 1]
    config.update(profanity_lists={"en": ["heck"]})
    try:
        assert profanity.find_words(W((0, 1, "heck"), (1, 2, "fuck")), "en") == [0]
    finally:
        config.update(profanity_lists={})
    assert profanity.resolve("auto", True) == "bleep" and profanity.resolve("auto", False) == "off"
    assert profanity.resolve("mute", False) == "mute"


def test_fillers_sure_and_maybe():
    ws = W((0, 0.5, "Iııı"), (1.0, 1.4, "şey"), (2.0, 2.3, "bir"), (2.3, 2.6, "şey"), (2.62, 3.0, "aldım"),
           (3.0, 3.3, "eeee"))
    assert fillers.find_fillers(ws, "tr", "light") == [0, 5]
    # "şey" alone (pauses around it) is a filler; inside "bir şey aldım" it is a word
    assert fillers.find_fillers(ws, "tr", "strong") == [0, 1, 5]
    assert fillers.find_fillers(ws, "tr", "off") == []
    hu = W((0, 0.3, "ő"), (0.3, 0.6, "mondta"), (1, 1.4, "ööö"))
    assert fillers.find_fillers(hu, "hu", "light") == [2]  # "ő" = he/she, not the filler "ö"
    assert fillers.find_fillers(W((0, 0.4, "Um,"), (0.5, 1, "yes")), "en", "light") == [0]


# ------------------------------------------------------------------ silence + plan


def test_silence_needs_quiet_and_no_words():
    db = np.full(300, -20.0, np.float32)  # 6 s of 20 ms frames
    db[50:150] = -70  # 1.0 .. 3.0 s quiet
    db[200:250] = -70  # 4.0 .. 5.0 s quiet but someone speaks at 4.2-4.6
    got = silence.find_silences(db, [(4.2, 4.6)], 0.5, start=0.0)
    assert len(got) == 1 and got[0][0] == pytest.approx(1.0) and got[0][1] == pytest.approx(3.0)


class _P:
    """Project stand-in for plans without audio / caches."""

    def __init__(self, d: Path):
        self.dir = d
        self.audio_path = d / "none.wav"
        self.cache_dir = d / "cache"
        self.transcript_path = d / "none.json"

    def load_meta(self):
        return {"mode": "gaming"}


def test_plan_deleted_words_map_and_mask(tmp_path):
    ws = W((10.2, 10.6, "Hello"), (10.7, 11.0, "fucking"), (11.1, 11.5, "world"), (12.0, 12.4, "again"))
    cand = {"id": "c01", "start": 10.0, "end": 13.0, "reasons": []}
    opts = ClipOptions.from_dict({"profanity": "bleep"})
    p = plan.build(_P(tmp_path), cand, opts, fps=30, edit={"deleted": [[11.05, 11.6]]}, words=ws, lang="en")
    assert p.cuts and len(p.keep) == 2
    assert p.out_duration == pytest.approx(3.0 - 0.55, abs=1 / 30 + 1e-6)
    out = p.out_words()
    assert [w["word"] for w in out] == ["Hello", "f******", "again"]
    assert out[-1]["start"] == pytest.approx(12.0 - 10.0 - 0.55, abs=0.05)
    assert p.bleeps and p.bleeps[0][0] == pytest.approx(0.67, abs=0.05)
    for fa, fb in p.frames():  # cut points sit on the frame grid
        assert fb > fa
    assert p.to_out(11.3) is None and p.to_out(11.3, "fwd") == pytest.approx(p.to_out(11.6), abs=0.04)
    assert p.active and p.audio_active


def test_plan_protects_laughs_and_nothing_left(tmp_path):
    proj = _P(tmp_path)
    ws = W((0.0, 0.4, "um"), (5.0, 5.4, "uh"))
    cand = {"id": "c01", "start": 0.0, "end": 8.0, "reasons": [{"code": "laughter", "t": 5.2, "strength": 1}]}
    p = plan.build(proj, cand, ClipOptions.from_dict({"cuts": "light", "profanity": "off"}), fps=30, words=ws,
                   lang="en")
    kinds = [(round(r["a"], 1), r["kind"]) for r in p.removed]
    assert kinds == [(0.0, "filler")]  # the "uh" inside the laugh stays
    with pytest.raises(SharkyClipsError):
        plan.build(proj, cand, ClipOptions(), fps=30, edit={"deleted": [[0, 8]]}, words=ws, lang="en")


def test_plan_inactive_without_tools(tmp_path):
    ws = W((1, 2, "hello"))
    p = plan.build(_P(tmp_path), {"id": "c1", "start": 0, "end": 5}, ClipOptions(), fps=30, words=ws, lang="en")
    assert not p.active and not p.cuts


# ------------------------------------------------------------------ zoom


def test_zoom_pulses_and_expression():
    cand = {"start": 100.0, "end": 130.0, "reasons": [
        {"code": "df_multikill", "t": 110.0, "strength": 0.8}, {"code": "loudness_spike", "t": 111.0, "strength": 1},
        {"code": "laughter", "t": 120.0, "strength": 0.9}]}
    ps = zoom.pulses(cand)
    scene = [p for p in ps if p.target == "scene"]
    cam = [p for p in ps if p.target == "cam"]
    assert len(scene) == 2  # 110 and 111 are too close: one pulse
    assert cam and all(p.t0 >= 100 for p in ps)
    assert zoom.factor_at(110.0, ps, "scene", 1.15) == pytest.approx(1.15, abs=0.01)
    assert zoom.factor_at(105.0, ps, "scene", 1.15) == 1.0
    f = zoom.perspective_filter([(1.0, 3.0)], 1.15, 60)
    assert f.startswith("perspective=") and "eval=frame" in f and "between(t,1.000,3.000)" in f
    assert zoom.perspective_filter([], 1.15, 60) == ""


# ------------------------------------------------------------------ sound


def test_loudness_meter_and_limiter():
    t = np.arange(48000 * 3) / 48000
    sine = (0.5 * np.sin(2 * np.pi * 997 * t)).astype(np.float32)
    mono = loudness.integrated_lufs(np.stack([sine, np.zeros_like(sine)], 1))
    assert mono == pytest.approx(-3.01 - 6.02, abs=0.3)  # BS.1770 reference: 0 dBFS sine in one channel = -3.01
    y, _ = loudness.normalize(np.stack([sine, sine], 1) * 0.05, -14.0)
    assert loudness.integrated_lufs(y) == pytest.approx(-14.0, abs=0.2)
    assert np.abs(y).max() <= 10 ** (-1 / 20) + 1e-4
    loud = np.stack([sine * 2, sine * 2], 1)
    assert np.abs(loudness.limit(loud, -1.0)).max() <= 10 ** (-1 / 20) + 1e-4


def test_cut_and_join_keeps_length_and_crossfades(tmp_path):
    sr = audiomix.SR
    src = np.ones((sr * 4, 2), np.float32) * 0.5
    src[int(sr * 1.5): int(sr * 2.5)] = -0.5  # the part that gets cut
    p = plan.EditPlan(0.0, 4.0, 30.0, [(0.0, 1.5), (2.5, 4.0)])
    out = audiomix.cut_and_join(src, 0.0, p)
    assert len(out) == int(sr * 3.0)
    assert out[: sr].mean() == pytest.approx(0.5) and out[-sr:].mean() == pytest.approx(0.5)
    join = out[int(sr * 1.5) - 960: int(sr * 1.5) + 960, 0]
    assert join.min() > -0.5  # crossfaded, not a hard jump into the cut audio


def test_bleep_and_mute():
    sr = audiomix.SR
    y = np.full((sr, 2), 0.2, np.float32)
    b = audiomix.apply_bleeps(y.copy(), [(0.2, 0.4)], "bleep")
    seg = b[int(sr * 0.25): int(sr * 0.35), 0]
    assert abs(seg.mean()) < 0.02 and seg.std() > 0.04  # a tone, not the speech
    m = audiomix.apply_bleeps(y.copy(), [(0.2, 0.4)], "mute")
    assert np.abs(m[int(sr * 0.25): int(sr * 0.35)]).max() < 1e-6
    assert m[int(sr * 0.6), 0] == pytest.approx(0.2)


def test_duck_envelope():
    sr = audiomix.SR
    env = audiomix.duck_envelope(sr * 6, [(2.0, 4.0)], -11.0)
    assert env[int(sr * 0.5)] == pytest.approx(1.0, abs=0.01)
    assert env[int(sr * 3.0)] == pytest.approx(10 ** (-11 / 20), abs=0.02)
    assert env[int(sr * 1.95)] < 0.8  # already going down before the first word (look-ahead)
    assert env[int(sr * 5.9)] > 0.9  # back up in the pause


# ------------------------------------------------------------------ music + brand


def test_best_start_and_moods():
    hop = 0.1
    e = np.full(700, -30.0)
    e[300:] = -8.0  # the strong part starts at 30 s
    assert music.best_start(e, hop, np.arange(0, 70, 0.5)) == pytest.approx(30.0, abs=0.6)
    assert music.best_start(np.full(100, -10.0), hop) == 0.0  # short songs start at 0
    assert music.mood_for({"llm": {"funny": 8, "exciting": 5}})[0] == "funny"
    assert music.mood_for({"llm": {"funny": 2, "exciting": 8, "moment_type": "skill"}})[0] == "hype"
    assert music.mood_for({"signal_scores": {"laughter": 0.7}})[0] == "funny"
    assert music.mood_for({}, "study")[0] == "chill"


def _wav(path: Path, seconds: float, freq: float = 220.0, amp: float = 0.3) -> None:
    t = np.arange(int(48000 * seconds)) / 48000
    y = amp * np.sin(2 * np.pi * freq * t)
    pcm = (np.stack([y, y], 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(pcm.tobytes())


def test_music_library_tags_and_suggestion():
    folder = music.folder()
    (folder / "song.txt").write_text("not music")
    _wav(folder / "Chill One.wav", 1.0)
    idx = {"Chill One.wav": {"version": music.ANALYSIS_VERSION, "size_bytes": (folder / "Chill One.wav").stat().st_size,
                             "duration": 60.0, "best_start": 12.0, "mood_guess": "chill", "moods": ["chill"]}}
    write_json_atomic(config.config_dir() / "music_library.json", {"version": 1, "tracks": idx})
    try:
        lib = music.library()
        assert [t["name"] for t in lib] == ["Chill One.wav"] and lib[0]["analyzed"]
        music.update("Chill One.wav", {"moods": ["funny", "bogus"], "artist": "Me"})
        assert music.track("Chill One.wav")["moods"] == ["funny"]
        s = music.suggest({"id": "c01", "duration": 20, "signal_scores": {"laughter": 0.9}})
        assert s["name"] == "Chill One.wav" and s["mood"] == "funny" and s["matched"]
        assert music.credit_line(music.track("Chill One.wav")) == "Music: Chill One by Me"
        with pytest.raises(SharkyClipsError):
            music.update("../evil.wav", {})
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        (config.config_dir() / "music_library.json").unlink(missing_ok=True)


def test_brand_presets_validate_and_revision():
    data = brand.save([{"name": "Main", "handle": "@me plays", "logo_pos": "zz", "logo_size": 99,
                        "caption_color": "red", "intro": {"enabled": True, "seconds": 30}}], None)
    p = data["presets"][0]
    assert data["active"] == p["id"] and p["handle"] == "meplays" and p["logo_pos"] == "tr"
    assert p["logo_size"] == 45 and p["caption_color"] == "#FFFFFF" and p["intro"]["seconds"] == 6.0
    assert brand.card_seconds(p) == (6.0, 0.0)
    rev = p["rev"]
    p2 = brand.save([{**p, "channel": "My Channel"}], p["id"])["presets"][0]
    assert p2["rev"] == rev + 1 and brand.outro_text(p2) == "@meplays"
    assert brand.ass_color("#D9B56A") == "&H006AB5D9"
    with pytest.raises(SharkyClipsError):
        brand.store_logo(p["id"], b"not an image", "logo.png")
    brand.save([], None)
    assert brand.active_preset() is None


# ------------------------------------------------------------------ manual clips


def _project(pid: str) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "Test", "duration": 100.0, "mode": "gaming"})
    write_json_atomic(d / "highlights.json", {"mode": "gaming", "created_at": "x", "candidates": [
        {"rank": 1, "id": "c01", "start": 10.0, "end": 30.0, "duration": 20.0, "peak": 20.0, "hype_score": 80,
         "reasons": [], "signal_scores": {}, "text": "hi"}]})
    write_json_atomic(d / "hype_curve.json", {"duration": 100, "resolution_s": 1, "combined": list(range(100)),
                                              "signals": {"loudness": {"share": 1, "values": [50] * 100}}})
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [
        {"start": 40, "end": 44, "words": [{"start": 40.5, "end": 41, "word": " Look"}, {"start": 41, "end": 41.5, "word": " here"}]}]})
    return Project(pid, d)


def test_manual_clips_survive_and_get_scores():
    from sharkyclips.web import state

    proj = _project("manual-test")
    c = manual.add(proj, 45.0, 39.0)  # swapped in/out are fine
    assert c["id"] == "m01" and c["start"] == 39.0 and c["end"] == 45.0 and c["rank"] == 2
    assert c["text"] == "Look here" and c["hype_score"] == 44 and c["manual"]
    with pytest.raises(SharkyClipsError):
        manual.add(proj, 50, 51)  # too short
    # Something rewrote highlights.json without it (a running analysis): it comes back.
    hl = json.loads((proj.dir / "highlights.json").read_text(encoding="utf-8"))
    hl["candidates"] = hl["candidates"][:1]
    write_json_atomic(proj.dir / "highlights.json", hl)
    assert [x["id"] for x in state.load_highlights(proj)["candidates"]] == ["c01", "m01"]
    assert manual.remove(proj, "m01") and not manual.remove(proj, "c01")
    assert [x["id"] for x in state.load_highlights(proj)["candidates"]] == ["c01"]
    shutil.rmtree(proj.dir, ignore_errors=True)


def test_review_edits_and_effective_candidate():
    from sharkyclips.web import state

    proj = _project("review-test")
    r = state.save_review(proj, {"edits": {"c01": {"start": 12, "deleted": [[15, 16], [20, 19], "x"]},
                                           "c02": {}}, "music": {"c01": "a.mp3", "c02": None}, "rejected": ["c03"]})
    assert r["edits"] == {"c01": {"start": 12.0, "deleted": [[15.0, 16.0]]}} and r["music"] == {"c01": "a.mp3"}
    eff = state.effective_cand({"id": "c01", "start": 10.0, "end": 30.0}, r)
    assert eff["start"] == 12.0 and eff["duration"] == 18.0 and eff["edit"]["music"] == "a.mp3"
    assert state.edit_fingerprint({"id": "c01", "start": 10, "end": 30}, r, {"music": False}) != ""
    assert state.edit_fingerprint({"id": "c09", "start": 10, "end": 30}, r, {"music": True}) != ""
    assert state.edit_fingerprint({"id": "c09", "start": 10, "end": 30}, r, {}) == ""
    shutil.rmtree(proj.dir, ignore_errors=True)


def test_options_validate():
    o = ClipOptions.from_dict({"cuts": "strong", "zoom": "subtle", "music": 1, "brand": 0})
    assert o.cuts == "strong" and o.music is True and o.brand is False and o.profanity == "auto"
    for bad in ({"cuts": "max"}, {"zoom": "wild"}, {"profanity": "maybe"}):
        with pytest.raises(SharkyClipsError):
            ClipOptions.from_dict(bad)


def test_api_studio_endpoints():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    lists = client.get("/api/wordlists").json()
    assert set(lists["profanity"]) >= {"tr", "en", "de", "hu", "ru", "ar", "zh"}
    put = client.put("/api/wordlists", json={"profanity": {"en": ["darn", "darn"]}, "silence_ms": {"light": 10}}).json()
    assert put["profanity"]["en"]["words"] == ["darn"] and put["profanity"]["en"]["custom"]
    assert put["silence_ms"]["light"] == 150
    back = client.put("/api/wordlists", json={"profanity": {"en": None}}).json()
    assert not back["profanity"]["en"]["custom"] and "fuck*" in back["profanity"]["en"]["words"]
    b = client.put("/api/brand", json={"presets": [{"name": "X"}]}).json()
    assert b["presets"][0]["name"] == "X" and b["active"] == b["presets"][0]["id"]
    assert client.get(f"/api/brand/{b['active']}/logo").status_code == 400
    client.put("/api/brand", json={"presets": []})
    m = client.get("/api/music").json()
    assert m["moods"] == ["hype", "chill", "sad", "funny"] and m["credit_enabled"]
    assert client.put("/api/music/upload?filename=evil.exe", content=b"x").status_code == 400

    proj = _project("api-edit-test")
    r = client.post(f"/api/projects/{proj.id}/candidates", json={"start": 40, "end": 50})
    assert r.status_code == 200 and r.json()["candidate"]["manual"]
    plan_view = client.post(f"/api/projects/{proj.id}/candidates/m01/plan",
                            json={"options": {"profanity": "bleep"}, "edit": {"deleted": [[41, 41.5]]}}).json()
    assert plan_view["duration"] == pytest.approx(9.5, abs=0.05)
    assert [w["word"] for w in plan_view["words"] if w.get("removed")] == ["here"]
    assert client.delete(f"/api/projects/{proj.id}/candidates/c01").status_code == 400
    assert client.delete(f"/api/projects/{proj.id}/candidates/m01").json()["removed"]
    shutil.rmtree(proj.dir, ignore_errors=True)


# ------------------------------------------------------------------ real renders (ffmpeg)


def _source_project(pid: str, seconds: float = 6.0) -> Project:
    proj = _project(pid)
    ffmpeg = shutil.which("ffmpeg")
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=size=640x360:rate=30:duration={seconds}", "-f", "lavfi", "-i",
                    f"sine=frequency=300:sample_rate=48000:duration={seconds}", "-c:v", "libx264", "-preset",
                    "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(proj.dir / "source.mp4")],
                   check=True, capture_output=True)
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(proj.dir / "source.mp4"),
                    "-ac", "1", "-ar", "16000", str(proj.dir / "audio.wav")], check=True, capture_output=True)
    write_json_atomic(proj.dir / "meta.json", {"title": "T", "duration": seconds, "width": 640, "height": 360,
                                               "fps": 30, "audio_codec": "aac", "mode": "gaming"})
    write_json_atomic(proj.dir / "transcript.json", {"language": "en", "segments": [
        {"start": 0.5, "end": 4.0, "words": [{"start": 0.5, "end": 1.0, "word": " this"},
                                              {"start": 1.0, "end": 1.6, "word": " shit"},
                                              {"start": 3.0, "end": 3.6, "word": " works"}]}]})
    return proj


def _probe(path: Path) -> dict:
    out = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "stream=codec_type,duration",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return {s["codec_type"]: float(s["duration"]) for s in json.loads(out)["streams"]}


@pytest.mark.requires_ffmpeg
def test_render_with_cuts_bleep_zoom_music_brand(tmp_path):
    from sharkyclips.clips import render_clip

    proj = _source_project("render-edit-test")
    cand = {"id": "c01", "rank": 1, "start": 0.0, "end": 5.0, "duration": 5.0, "peak": 2.0,
            "reasons": [{"code": "loudness_spike", "t": 2.0, "strength": 1}],
            "edit": {"deleted": [[1.9, 2.6]], "music": "Song.wav"}}
    _wav(music.folder() / "Song.wav", 30.0, 440.0)
    data = brand.save([{"name": "B", "handle": "me", "intro": {"enabled": True, "seconds": 1.0}}], None)
    logo = tmp_path / "logo.png"
    import cv2

    cv2.imwrite(str(logo), np.full((40, 80, 4), 255, np.uint8))
    brand.store_logo(data["active"], logo.read_bytes(), "logo.png")
    try:
        music.analyze("Song.wav")
        opts = ClipOptions.from_dict({"profanity": "bleep", "zoom": "strong", "music": True, "brand": True,
                                      "layout": "fit", "hook": True})
        dest = tmp_path / "out.mp4"
        res = render_clip(proj, cand, opts, None, dest, spec=OutputSpec())
        got = _probe(dest)
        want = 1.0 + 5.0 - 0.7
        assert got["video"] == pytest.approx(want, abs=0.07) and got["audio"] == pytest.approx(want, abs=0.07)
        assert res.info["cuts"] == 1 and res.info["bleeps"] == 1 and res.info["music"]["name"] == "Song.wav"
        assert res.info["lufs"] == pytest.approx(-14.0, abs=0.5)
        # plain options still take the old, unchanged path
        res2 = render_clip(proj, {**cand, "edit": {}}, ClipOptions.from_dict({"profanity": "off"}), None,
                           tmp_path / "plain.mp4", spec=OutputSpec())
        assert res2.info == {} and _probe(tmp_path / "plain.mp4")["video"] == pytest.approx(5.0, abs=0.07)
    finally:
        brand.save([], None)
        shutil.rmtree(music.folder(), ignore_errors=True)
        (config.config_dir() / "music_library.json").unlink(missing_ok=True)
        shutil.rmtree(proj.dir, ignore_errors=True)
