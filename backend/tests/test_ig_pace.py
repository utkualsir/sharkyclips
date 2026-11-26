"""1.2.62: Instagram paused as a default target, account / permission refusals are never retried
by themselves (a clear message instead, the other automatic Instagram posts paused), and a safe
pace for Instagram: hours between posts, few and varied hashtags, no identical captions in a row."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from sharkyclips import config, platforms as PF, pubqueue as PQ
from sharkyclips.errors import SharkyClipsError
from sharkyclips.web import igpace, multipost as M
from test_meta_off import manual  # noqa: F401 - fixture (Manual mode, nothing reaches Meta)
from test_multipost import _client, _rec, _rendered
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures


@pytest.fixture
def fresh_choices():
    keys = ("publish_targets", "pubqueue", "ig_paused_at")
    old = {k: config.get(k) for k in keys}
    yield
    config.update(**old)
    igpace.forget_cache()


# ===================================================================== paused as a target


def test_instagram_is_off_by_default_and_paused_once_but_can_be_switched_back_on(fresh_choices):
    config.update(publish_targets=None, ig_paused_at=None, pubqueue=None)
    assert M.targets() == ["youtube", "tiktok"]  # a new user: Instagram off
    # an existing user who had Instagram on: off once, the rest kept
    config.update(publish_targets=["youtube", "tiktok", "reels"], ig_paused_at=None,
                  pubqueue={"platforms": {"instagram": {"on": True, "per_day": 2, "times": ["12:00", "18:00"]}}})
    assert M.targets() == ["youtube", "tiktok"]
    assert config.get("ig_paused_at") and PQ.settings()["platforms"]["instagram"]["on"] is False
    assert PQ.settings()["platforms"]["instagram"]["times"] == ["12:00", "18:00"]  # the setup stays
    # switching it back on is the user's choice, and it stays on
    assert M.set_targets(["youtube", "reels"]) == ["youtube", "reels"]
    assert M.targets() == ["youtube", "reels"]
    PQ.save_settings({"platforms": {"instagram": {"on": True}}})
    assert PQ.settings()["platforms"]["instagram"]["on"] is True


def test_queue_instagram_times_must_be_hours_apart(fresh_choices):
    config.update(pubqueue=None, ig_paused_at=1.0)
    assert PQ.settings()["platforms"]["instagram"]["on"] is False
    assert PQ.cap("instagram", PQ.settings()) <= 4
    for bad in (["12:00", "14:00"], ["12:00", "18:00", "21:00"], ["01:00", "23:00"]):
        with pytest.raises(SharkyClipsError, match="4 hours"):
            PQ.save_settings({"platforms": {"instagram": {"times": bad}}})
    s = PQ.save_settings({"platforms": {"instagram": {"times": ["10:00", "15:00", "20:00"]}}})
    assert s["platforms"]["instagram"]["times"] == ["10:00", "15:00", "20:00"]
    PQ.save_settings({"platforms": {"tiktok": {"times": ["12:00", "13:00"]}}})  # other platforms: as before


# ===================================================================== account / permission refusals


@pytest.mark.parametrize("code,kind", [
    ("10", "account"), ("200", "account"), ("368", "account"), ("3", "account"), ("25:2207050", "account"),
    ("190:459", "account"), ("190", "auth"), ("190:463", "auth"), ("4", "rate_limit"), ("9:2207042", "quota"),
    ("2", "transient"), ("100", "fatal"),
])
def test_meta_refusals_are_sorted_by_what_they_are_about(code, kind):
    e = PF.api_error("reels", "Instagram refused the post: x.", None, code, 400)
    assert e.kind == kind
    assert (e.retry_after is None) == (kind in ("account", "auth", "fatal"))


def test_a_tiktok_posting_ban_is_an_account_refusal():
    assert PF.api_error("tiktok", "TikTok refused.", None, "spam_risk_user_banned_from_posting", 403).kind == "account"


def test_an_account_refusal_says_so_never_retries_and_pauses_the_other_instagram_posts(cfg, fresh_choices):  # noqa: F811
    _clean_projects()
    try:
        config.update(publish_targets=["youtube", "reels"], ig_paused_at=1.0)
        project = _project("pub-igpace-block")
        later = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        PF.record(project, "c02", "reels", mode="api", status="scheduled", publish_at=later, caption="other")
        PF.record(project, "c03", "reels", mode="semi", status="ready", caption="by hand")  # Manual: untouched
        PF.record(project, "c01", "reels", mode="api", status="uploading", attempts=0, caption="this one")
        M._failed(project, "c01", "reels", PF.api_error(
            "reels", "Instagram refused the post: The user is restricted.", None, "25:2207050", 400))
        rec = _rec(project, "c01", "reels")
        assert rec["status"] == "failed" and rec["next_try_at"] is None  # never by itself
        assert rec["error"]["kind"] == "account" and "restricted, suspended" in rec["error"]["message"]
        assert "won't try again" in rec["error"]["hint"] and "restricted" in rec["error"]["detail"]
        assert _rec(project, "c02", "reels")["status"] == "paused"
        assert _rec(project, "c03", "reels")["status"] == "ready"
        assert "reels" not in M.targets()
    finally:
        _clean_projects()


# ===================================================================== pace


def _ev(key, hours_from_now, caption=""):
    return {"key": key, "at": time.time() + hours_from_now * 3600, "caption": caption}


def test_next_safe_keeps_hours_between_instagram_posts():
    now = datetime.now(timezone.utc)
    assert abs((igpace.next_safe(now, []) - now).total_seconds()) < 1
    got = igpace.next_safe(now, [_ev(("p", "a"), -1)])  # posted an hour ago -> 3 more hours
    assert abs((got - now).total_seconds() - 3 * 3600) < 5
    got = igpace.next_safe(now, [_ev(("p", "a"), -1), _ev(("p", "b"), 3.5)])  # a planned one in the way
    assert abs((got - now).total_seconds() - 7.5 * 3600) < 5
    assert abs((igpace.next_safe(now, [_ev(("p", "a"), -1)], skip=("p", "a")) - now).total_seconds()) < 1
    assert igpace.next_safe(now, [_ev(("p", "a"), -5)]) == now  # long enough ago


def test_hashtags_are_few_and_rotate_away_from_the_last_post():
    tags = ["mychan", "deltaforce", "gaming", "clutch", "fps", "ranked", "squad", "win"]
    first = igpace.pick_hashtags(tags, 1, set())
    assert len(first) == igpace.HASHTAGS and first[0] == "mychan"
    second = igpace.pick_hashtags(tags, 1, {t.casefold() for t in first})
    assert second[0] == "mychan" and len(second) == igpace.HASHTAGS and set(second) != set(first)
    assert igpace.pick_hashtags(["a", "b"], 0, {"a", "b"}) == ["a", "b"]  # nothing else to offer: kept


def test_instagram_now_right_after_another_is_never_delayed(manual):  # noqa: F811
    # 1.2.68: the 4-hour pace is a warning in Share (you can post anyway), never an automatic delay
    project = _project("pub-igpace-now")
    _rendered(project, "c01")
    _rendered(project, "c02")
    c = _client()
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["reels"], "when": "now"})
    assert r.status_code == 200, r.text
    _wait(_idle)
    r = c.post(f"/api/publish/{project.id}/c02", json={"platforms": ["reels"], "when": "now"})
    assert r.status_code == 200, r.text
    res = r.json()["results"]["reels"]
    assert res["mode"] == "semi" and "paced_to" not in res
    _wait(_idle)
    rec = _rec(project, "c02", "reels")
    assert not rec.get("remind_at") and rec["status"] == "ready"  # ready to post by hand now


def test_no_identical_instagram_captions_in_a_row(manual):  # noqa: F811
    project = _project("pub-igpace-cap")
    _rendered(project, "c02")
    PF.record(project, "c01", "reels", mode="semi", status="published", manual=True,
              posted_at=datetime.now(timezone.utc).isoformat(), caption="Same words\n\n#deltaforce #gaming")
    igpace.forget_cache()
    v = M.view(project, "c02", ["reels"])
    gen = v["drafts"]["reels"]["caption"]  # generated: already different
    assert igpace.norm(gen) != igpace.norm("Same words\n\n#deltaforce #gaming")
    assert M.hashtag_count(gen) <= igpace.HASHTAGS
    assert "same_caption" not in {p["code"] for p in v["problems"]}
    # the user typed the very same caption: a problem with a one-tap fix
    M.save_clip_store(project, "c02", drafts={"reels": {"caption": "Same words\n\n#deltaforce #gaming"}})
    v = M.view(project, "c02", ["reels"])
    prob = [p for p in v["problems"] if p["code"] == "same_caption"]
    assert prob and prob[0]["fix"] == "vary_caption" and prob[0]["platform"] == "reels"
    # 1.2.70: a by-hand platform never blocks Publish: the caption is varied by itself when it starts
    M.start(project, "c02", {"platforms": ["reels"], "when": "now", "remember": False})
    _wait(_idle, 30)
    same = igpace.norm("Same words\n\n#deltaforce #gaming")
    assert igpace.norm(M.clip_store(project, "c02")["drafts"]["reels"]["caption"]) != same
    M.save_clip_store(project, "c02", drafts={"reels": {"caption": "Same words\n\n#deltaforce #gaming"}})
    v = M.apply_fix(project, "c02", "reels", "vary_caption")
    assert igpace.norm(v["drafts"]["reels"]["caption"]) != igpace.norm("Same words\n\n#deltaforce #gaming")
    assert "same_caption" not in {p["code"] for p in v["problems"]}
