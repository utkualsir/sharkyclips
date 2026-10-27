"""1.2.5: story clips and the A/B hook test (pre-test, Thompson sampling, the 48 h fetch)."""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from sharkyclips import abtest, config, story
from sharkyclips.clips import ClipOptions
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project, write_json_atomic

FPS = 30
SW = [{"start": float(i) + 0.1, "end": float(i) + 0.8, "word": f"w{i}"} for i in range(0, 200)]


def _c(cid, start, end, score, mtype="", codes=(), text=""):
    return {"id": cid, "rank": int(cid[1:]), "start": start, "end": end, "duration": end - start, "peak": (start + end) / 2,
            "hype_score": score, "reasons": [{"code": c, "t": start + 1} for c in codes], "text": text,
            "llm": {"moment_type": mtype, "what_happens": f"moment {cid}"}, "publish": {}}


def _project(pid: str, cands: list[dict], seconds: float = 0.0) -> Project:
    d = config.workspace_dir() / pid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    write_json_atomic(d / "meta.json", {"title": "Stream", "duration": seconds or 600.0, "fps": FPS, "width": 320,
                                        "height": 180, "audio_codec": "aac", "mode": "gaming"})
    write_json_atomic(d / "highlights.json", {"mode": "gaming", "created_at": "x", "candidates": cands})
    write_json_atomic(d / "transcript.json", {"language": "en", "segments": [
        {"start": 0, "end": 200, "words": [{**w, "word": " " + w["word"]} for w in SW]}]})
    return Project(pid, d)


class FakeLLM:
    model = "fake"

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def json(self, system, prompt, schema, check=None, **kw):
        self.prompts.append(prompt)
        d = self.answers.pop(0)
        assert (check(d) if check else []) == []
        return d


# ===================================================================== story clips


def test_good_moments_drop_weak_and_overlapping():
    cands = [_c("c01", 10, 30, 80), _c("c02", 12, 28, 50), _c("c03", 60, 80, 10), _c("c04", 100, 120, 40)]
    assert [c["id"] for c in story.good_moments(cands)] == ["c01", "c04"]  # c02 overlaps c01, c03 is weak


def test_finalize_keeps_words_whole_no_overlap_and_30_to_60_s():
    cands = {c["id"]: c for c in (_c("c01", 10.4, 34.4, 80), _c("c02", 30.0, 50.5, 60), _c("c03", 90.3, 120.0, 70))}
    raw = {"title": "T", "arc": "setup_payoff", "pitch": "p",
           "segments": [{"clip": "c03"}, {"clip": "c01"}, {"clip": "c01"}, {"clip": "c02"}, {"clip": "nope"}]}
    st = story.finalize(raw, cands, SW, 300.0)
    assert st is not None and [s["cid"] for s in st["segments"]] == ["c01", "c02", "c03"]  # stream order, no duplicate
    segs = st["segments"]
    for a, b in zip(segs, segs[1:]):
        assert a["end"] <= b["start"]  # overlapping moments are trimmed: nothing is shown twice
    for s in segs:
        assert not story.inside_word(SW, s["start"]) and not story.inside_word(SW, s["end"])
    assert story.MIN_TOTAL - 0.5 <= st["duration"] <= story.MAX_TOTAL + 0.5
    kept = story.finalize({**raw, "segments": [{"clip": "c03"}, {"clip": "c01"}]}, cands, SW, 300.0, keep_order=True)
    assert [s["cid"] for s in kept["segments"]] == ["c03", "c01"]  # the user's order is kept
    assert story.finalize({**raw, "segments": [{"clip": "c01"}]}, cands, SW, 300.0) is None  # one moment: no story


def test_story_proposals_with_ai_rules_and_too_few_moments():
    proj = _project("story-few", [_c("c01", 10, 30, 80), _c("c02", 60, 80, 5)])
    try:
        data = story.propose(proj, None, "en")
        assert data["stories"] == [] and data["reason"] == "too_few_moments" and data["good"] == 1
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)
    cands = [_c("c01", 10.4, 30.4, 60, "fail", ["df_death"], "oh no I died"),
             _c("c02", 50.2, 70.6, 80, "skill", ["df_multikill"], "triple kill"),
             _c("c03", 120.1, 140.5, 70, "funny", [], "that was funny")]
    proj = _project("story-ai", cands)
    try:
        rules = story.propose(proj, None, "en")
        assert rules["stories"] and rules["stories"][0]["arc"] == "fail_comeback"
        assert all(s["publish"]["source"] == "clips" for s in rules["stories"])
        llm = FakeLLM([
            {"stories": [{"title": "Died, then wiped them", "arc": "fail_comeback", "pitch": "He dies, then takes revenge.",
                          "segments": [{"clip": "c01", "role": "fail", "card": ""},
                                       {"clip": "c02", "role": "payoff", "card": "Later"}]}], "none_reason": ""},
            {"titles": ["One death, then a triple kill", "Revenge in 20 seconds", "From zero to hero", "He came back"],
             "description": "It starts badly. Then it gets very good, very fast.",
             "hashtags": ["#deltaforce", "#gaming", "#comeback", "#shorts", "#fps"], "hook_text": "Wait for it",
             "cover_scene": "A soldier standing over three fallen enemies", "cover_text": "REVENGE"}])
        data = story.propose(proj, llm, "en")
        assert len(data["stories"]) == 1 and data["source"] == "ai"
        st = data["stories"][0]
        assert [s["cid"] for s in st["segments"]] == ["c01", "c02"] and st["segments"][1]["card"] == "Later"
        assert st["publish"]["source"] == "ai" and st["publish"]["titles"][0].startswith("One death")
        assert "soldier" in st["publish"]["cover_prompt"].lower() and st["publish"]["hashtags"]
        assert "c01" in llm.prompts[0] and "fail" in llm.prompts[0]
        assert story.cut_text(proj, st)[0]["text"].startswith("w")
        up = story.update(proj, st["id"], {"segments": ["c02", "c01"], "cards": False})
        assert [s["cid"] for s in up["segments"]] == ["c02", "c01"] and up["cards"] is False
        with pytest.raises(SharkyClipsError):
            story.update(proj, st["id"], {"segments": ["c02"]})
        assert story.delete(proj, st["id"]) and not story.delete(proj, st["id"])
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)


@pytest.mark.requires_ffmpeg
def test_story_render_continuous_captions_and_even_loudness(tmp_path):
    """Two moments of very different loudness come out at the same level, joined by quick transitions."""
    secs = 44
    cands = [_c("c01", 2.4, 20.4, 70, "fail", ["df_death"]), _c("c02", 24.4, 42.4, 80, "skill")]
    proj = _project("story-render", cands, secs)
    ff = shutil.which("ffmpeg")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate={FPS}:duration={secs}",
                    "-f", "lavfi", "-i", f"aevalsrc=if(lt(t\\,22)\\,0.03\\,0.4)*sin(2*PI*300*t):s=48000:d={secs}",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(proj.dir / "source.mp4")], check=True, capture_output=True)
    try:
        st = story.finalize({"title": "T", "arc": "fail_comeback", "pitch": "p",
                             "segments": [{"clip": "c01"}, {"clip": "c02", "card": "Later"}]},
                            {c["id"]: c for c in cands}, SW, secs)
        assert st is not None
        opts = ClipOptions.from_dict({"layout": "fit", "profanity": "off", "hook": True})
        res = story.render(proj, st, opts, None, tmp_path / "s.mp4")
        info = res.info
        before, after = info["segment_lufs_before"], info["segment_lufs_after"]
        assert abs(before[0] - before[1]) > 15  # the source really is uneven
        assert abs(after[0] - after[1]) < 1.5 and info["lufs"] == pytest.approx(-14.0, abs=0.6)
        out = json.loads(subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                                         "-of", "json", str(tmp_path / "s.mp4")], capture_output=True, text=True).stdout)
        assert float(out["format"]["duration"]) == pytest.approx(info["duration"], abs=0.1)
        assert info["cards"] == 1 and story.MIN_TOTAL - 0.5 <= info["duration"] <= story.MAX_TOTAL + 0.5
        segs = info["segments"]
        assert segs[0]["out_start"] == 0 and segs[1]["out_start"] > segs[0]["out_end"] - story.TRANSITION - 0.01
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)


# ===================================================================== A/B hooks


def test_variant_styles_and_texts():
    cand = {"id": "c01", "start": 10.0, "end": 40.0, "peak": 25.0,
            "publish": {"titles": ["Big win", "How did he do that?"], "title_styles": ["punchy", "question"]}}
    assert "cold_open" in abtest.applicable(cand)
    assert "cold_open" not in abtest.applicable({**cand, "peak": 12.0})
    pair = abtest.pick_pair(cand, [])
    assert len(set(pair)) == 2 and set(pair) <= set(abtest.applicable(cand))
    assert pair == abtest.pick_pair(cand, [])  # same data -> same pair
    assert abtest.question_text(cand, "en") == "How did he do that?"
    assert abtest.question_text({"publish": {}}, "tr") == "Sonra ne oluyor?"
    spec = abtest.variant_spec("cold_open", cand, "Watch", "en", SW)
    assert spec["start"] > cand["start"] and not story.inside_word(SW, spec["start"]) and not spec["hook_flash"]
    assert abtest.variant_spec("flash", cand, "Watch", "en", SW)["hook_flash"]
    assert abtest.style_of({"hook_flash": True}, "x") == "flash" and abtest.style_of({}, "Why?") == "question"


def test_hook_model_reasons_and_channel_calibration():
    f = {"motion": 1.8, "loudness": 4.0, "face": 1.0, "smile": 0.66,
         "text": {"present": True, "words": 4, "question": True, "number": False},
         "triggers": ["oha"], "trigger_weight": 1.0, "emotion_events": ["laughter"]}
    weak = {"motion": 0.6, "loudness": -3.0, "text": {"present": False}, "triggers": [], "emotion_events": []}
    a, b = abtest.score(f, "question", []), abtest.score(weak, "statement", [])
    assert a["score"] > 75 > 40 > b["score"]
    assert {r["code"] for r in a["reasons"]} >= {"motion", "smile", "trigger_words", "text_question"}
    assert a["reasons"] == sorted(a["reasons"], key=lambda r: -abs(r["points"]))
    good = [{"style": "question", "reward": 0.8, "video_id": f"q{i}"} for i in range(8)]
    bad = [{"style": "statement", "reward": 0.2, "video_id": f"s{i}"} for i in range(8)]
    tuned = abtest.score(weak, "question", good + bad)
    assert tuned["score"] > abtest.score(weak, "question", [])["score"]
    assert any(r["code"] == "channel" for r in tuned["reasons"])


def test_thompson_sampling_finds_the_best_style_with_simulated_data():
    rng = random.Random(42)
    true = {"flash": 0.45, "question": 0.62, "cold_open": 0.40, "statement": 0.30}
    obs: list[dict] = []
    picks = {s: 0 for s in true}
    for i in range(400):
        draw = abtest.thompson(list(true), obs, rng)
        s = max(draw, key=draw.get)
        picks[s] += 1
        reward = min(1.0, max(0.0, rng.gauss(true[s], 0.12)))
        obs.append({"style": s, "reward": reward, "video_id": f"sim{i}", "retention": reward * abtest.REWARD_CAP,
                    "simulated": True})
    assert max(picks, key=picks.get) == "question" and picks["question"] > 200
    assert min(picks.values()) >= 5  # every style was still tried
    st = abtest.stats(obs)
    top = st["styles"][0]
    assert top["style"] == "question" and top["p_best"] > 0.9 and top["ci90"][0] < 0.62 < top["ci90"][1]
    assert st["verdict"] == {"style": "question", "confidence": top["p_best"]}
    assert abtest.stats(obs[:3])["verdict"] is None  # 3 results are no proof


def test_fetch_after_48h_learns_once_detects_locks_and_deletes_simulated():
    from sharkyclips.web import state

    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    proj = _project("ab-fetch", [_c("c01", 10, 30, 80)])
    old, young = (now - timedelta(hours=50)).isoformat(), (now - timedelta(hours=10)).isoformat()
    ups = {"c01": [{"video_id": "v_old", "hook_style": "flash", "hook_variant": "A", "published_at": old,
                    "privacy": "public", "requested_privacy": "public", "simulated": True}],
           "c02": [{"video_id": "v_young", "hook_style": "question", "published_at": young, "simulated": True}],
           "c03": [{"video_id": "v_locked", "hook_style": "statement", "uploaded_at": old, "privacy": "private",
                    "requested_privacy": "public", "simulated": True}],
           "c04": [{"video_id": "v_gone", "hook_style": "statement", "uploaded_at": old, "simulated": True}]}
    write_json_atomic(proj.dir / "uploads.json", {"version": 1, "uploads": ups})
    calls = {"retention": 0}

    class FakeYT:
        locked = None

        @staticmethod
        def video_stats(ids):
            return {"v_old": {"privacy": "public", "published_at": old, "views": 900},
                    "v_young": {"privacy": "public", "published_at": young, "views": 50},
                    "v_locked": {"privacy": "private", "published_at": None, "views": 0}}

        @staticmethod
        def retention(ids, start):
            calls["retention"] += 1
            return {"v_old": {"views": 900, "avg_view_percentage": 87.0, "avg_view_duration": 20.0},
                    "v_young": {"views": 50, "avg_view_percentage": 40.0, "avg_view_duration": 9.0}}

        @staticmethod
        def mark_locked(vid):
            FakeYT.locked = vid

    try:
        abtest.clear_simulated()
        res = abtest.fetch_and_learn([proj], now=now, api=FakeYT)
        assert res == {"due": 3, "learned": 1, "locked": True} and FakeYT.locked == "v_locked"  # v_young: < 48 h
        obs = abtest.load_store()["observations"]
        assert len(obs) == 1 and obs[0]["style"] == "flash" and obs[0]["reward"] == pytest.approx(87 / 150, abs=1e-3)
        u = state.load_uploads(proj)
        assert u["c01"][0]["hook_learned"] and u["c04"][0]["missing"] and not u["c02"][0].get("hook_checked_at")
        again = abtest.fetch_and_learn([proj], now=now + timedelta(hours=1), api=FakeYT)
        assert again["due"] == 0 and calls["retention"] == 1  # nothing counted twice; the locked one waits a day
        later = abtest.fetch_and_learn([proj], now=now + timedelta(hours=60), api=FakeYT)
        assert later["learned"] == 1 and len(abtest.load_store()["observations"]) == 2  # v_young, now 70 h old
    finally:
        assert abtest.clear_simulated() == 2  # the simulated results are deleted again
        assert abtest.load_store()["observations"] == []
        shutil.rmtree(proj.dir, ignore_errors=True)


def test_upload_choice_explores_with_real_test_and_follows_pretest_without():
    entry = {"winner": "A", "variants": {"A": {"style": "flash"}, "B": {"style": "question"}}}
    assert abtest.choose_for_upload(entry, [], active=False) == {"label": "A", "how": "pretest"}
    rng = random.Random(1)
    picks = [abtest.choose_for_upload(entry, [], rng=rng, active=True)["label"] for _ in range(200)]
    assert 60 < picks.count("B") < 140  # no data yet: both get tested


def test_a_clip_is_never_uploaded_twice():
    from sharkyclips.web import app as appmod

    proj = _project("ab-twice", [_c("c01", 10, 30, 80)])
    write_json_atomic(proj.dir / "uploads.json", {"version": 1, "uploads": {
        "c01": [{"video_id": "abc", "url": "https://youtu.be/abc", "hook_style": "flash"}]}})
    try:
        with pytest.raises(SharkyClipsError) as e:
            appmod._never_twice(proj, "c01", None)
        assert "already on YouTube" in e.value.message
        write_json_atomic(proj.dir / "uploads.json", {"version": 1, "uploads": {"c01": [{"video_id": "abc", "missing": True}]}})
        appmod._never_twice(proj, "c01", None)  # deleted on YouTube: it may go up again
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)


def test_api_endpoints_for_stories_and_hooks():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    client = TestClient(app)
    proj = _project("api-retention", [_c("c01", 10, 30, 80), _c("c02", 60, 80, 5)])
    try:
        r = client.get(f"/api/projects/{proj.id}/stories").json()
        assert r["stories"] == [] and r["limits"] == {"min": 30.0, "max": 60.0} and "llm" in r
        assert client.get(f"/api/projects/{proj.id}/ab").json()["clips"] == {}
        h = client.get("/api/hooks").json()
        assert {s["style"] for s in h["styles"]} == set(abtest.STYLES) and h["real_test"]["active"] is False
        assert h["real_test"]["reason"] == "not_connected"
        assert client.post("/api/hooks/fetch").status_code == 400
        assert client.get(f"/api/projects/{proj.id}/stories/nope/video").status_code == 400
    finally:
        shutil.rmtree(proj.dir, ignore_errors=True)
