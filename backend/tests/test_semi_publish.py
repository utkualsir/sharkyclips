"""1.2.39: Instagram and TikTok are semi-automatic by default, also on the one Publish button.
SharkyClips makes the file (Downloads/SharkyClips, caption .txt next to it), the UI copies the
caption and opens the upload page, the user posts and taps "I shared it". No account needed;
automatic posting only with the switch on AND a working token."""

from __future__ import annotations

import pytest

from sharkyclips import config, platforms as PF
from sharkyclips.errors import SharkyClipsError
from test_multipost import _client, _rec, _rendered
from test_publishing import _clean_projects, _idle, _project, _wait, cfg  # noqa: F401 - fixtures


@pytest.fixture
def semi(monkeypatch, tmp_path, cfg):  # noqa: F811
    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(tmp_path / "dl"))
    for p in ("tiktok", "reels"):
        PF.forget(p)
    config.update(platform_modes={}, publish_targets=["tiktok", "reels"])
    _clean_projects()
    yield tmp_path / "dl"
    _wait(_idle, 60)
    for p in ("tiktok", "reels"):
        PF.forget(p)
    config.update(publish_targets=None, platform_modes={})
    _clean_projects()


def test_semi_is_the_default_and_needs_no_account(semi):
    project = _project("pub-semi-default")
    _rendered(project, "c01")
    c = _client()
    v = c.get(f"/api/publish/{project.id}/c01?platforms=tiktok,reels").json()
    assert v["modes"] == {"youtube": "api", "tiktok": "semi", "reels": "semi"}
    assert not [p for p in v["problems"] if p["code"] in ("not_connected", "signed_out", "quota_full")]
    assert v["tiktok"] is None  # no API post screen by hand
    assert v["accounts"]["reels"]["mode"] == "semi"
    # no TikTok API consent needed either
    r = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["reels", "tiktok"], "when": "now"})
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    assert res["reels"]["mode"] == "semi" and res["reels"]["upload_page"].startswith("https://www.instagram.com")
    _wait(_idle)
    for p, label in (("reels", "Instagram"), ("tiktok", "TikTok")):
        rec = _rec(project, "c01", p)
        assert rec["mode"] == "semi" and rec["status"] == "ready"
        assert rec["file"].endswith(f"- {label}.mp4") and rec["file"].startswith(str(semi))
        txt = rec["file"][:-4] + ".txt"
        assert open(txt, encoding="utf-8").read().strip() == rec["caption"].strip()
    h = c.get(f"/api/publish/{project.id}/c01/handoff").json()["platforms"]
    assert h["reels"]["status"] == "ready" and h["reels"]["file"] and "#" in h["reels"]["caption"] + "#"
    assert h["tiktok"]["upload_page"] == PF.UPLOAD_PAGE["tiktok"]
    # not posted yet: Publish doesn't make the file again
    again = c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["reels"], "when": "now"}).json()
    assert again["results"]["reels"]["skipped"]


def test_i_shared_it_marks_the_post_published(semi):
    project = _project("pub-semi-shared")
    _rendered(project, "c01")
    c = _client()
    c.post(f"/api/publish/{project.id}/c01", json={"platforms": ["reels"], "when": "now"})
    _wait(_idle)
    r = c.post(f"/api/publish/{project.id}/c01/shared/reels", json={"url": "https://www.instagram.com/reel/abc/"})
    assert r.status_code == 200
    st = r.json()["platforms"]["reels"]
    assert st["status"] == "published" and st["manual"] and st["url"] == "https://www.instagram.com/reel/abc/"
    with pytest.raises(SharkyClipsError):
        from sharkyclips.web import multipost as MP

        MP.shared(project, "c01", "tiktok")  # never started: nothing waits for the user


def test_planned_time_still_makes_the_file_now(semi):
    from datetime import datetime, timedelta, timezone

    project = _project("pub-semi-plan")
    _rendered(project, "c01")
    when = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    res = _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": when}).json()
    assert res["results"]["tiktok"]["status"] == "preparing"
    _wait(_idle)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "ready" and rec["remind_at"]


def test_automatic_only_with_the_switch_and_a_working_token(semi):
    PF.save_token("reels", {"access_token": "IGAAx", "graph": "instagram", "user_id": "1", "account": "me"})
    assert PF.mode("reels") == "semi"  # connected, switch off: still by hand
    PF.set_mode("reels", "api")
    assert PF.mode("reels") == "api"
    PF.note_problem("reels", "signed_out", "revoked")
    assert PF.mode("reels") == "semi"  # a broken token: back to by hand by itself
    PF.note_problem("reels", None)
    assert PF.mode("reels") == "api"


def test_long_paths_are_shortened_and_errors_show_on_the_clip(semi, monkeypatch, tmp_path):
    import shutil

    deep = tmp_path / ("d" * 60) / ("e" * 60)  # a deep Downloads folder: Windows stops at 260 characters
    monkeypatch.setenv("SHARKYCLIPS_DOWNLOADS", str(deep))
    project = _project("pub-semi-long")
    _rendered(project, "c01")
    from sharkyclips.web import multipost as MP

    MP.save_clip_store(project, "c01", drafts={"youtube": {"title": "A really long title " * 8}})
    _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["reels"], "when": "now"})
    _wait(_idle)
    rec = _rec(project, "c01", "reels")
    assert rec["status"] == "ready" and len(rec["file"]) <= 240

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copyfile", boom)
    _client().post(f"/api/publish/{project.id}/c01", json={"platforms": ["tiktok"], "when": "now"})
    _wait(_idle)
    rec = _rec(project, "c01", "tiktok")
    assert rec["status"] == "failed" and "TikTok" in rec["error"]["message"]  # never stuck "preparing"
