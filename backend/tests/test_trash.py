"""1.2.41 delete + trash: single / several clips and whole projects go to a 30-day trash and come
back with Restore; Empty trash and the 30-day limit delete for good; the original video and the
posts on the platforms are only touched when asked; jobs and plans of deleted things stop;
disk usage and the "Temizlik" helper."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from sharkyclips import config, publishing as P, trash as T
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import write_json_atomic
from sharkyclips.web import state
from test_multipost import _client, _rec, _rendered
from test_publishing import _clean_projects, _project, cfg  # noqa: F401 - fixtures


@pytest.fixture
def tr(cfg, tmp_path):  # noqa: F811
    _clean_projects()
    import shutil

    shutil.rmtree(T.root(), ignore_errors=True)
    for k in list(P.load()):
        P.remove(k)
    yield tmp_path
    _clean_projects()
    shutil.rmtree(T.root(), ignore_errors=True)


def _files(project, cid):
    _rendered(project, cid, size=5000)
    (project.cache_dir / "covers").mkdir(parents=True, exist_ok=True)
    (project.cache_dir / "covers" / f"{cid}_face_tall_abc123.jpg").write_bytes(b"j" * 300)
    (project.cache_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
    (project.cache_dir / "thumbnails" / f"{cid}.jpg").write_bytes(b"t" * 200)


def _cids(project):
    return [c["id"] for c in (state.load_highlights(project) or {}).get("candidates") or []]


def test_delete_one_clip_and_restore_it(tr):
    project = _project("pub-trash-one", n=3)
    for cid in ("c01", "c02"):
        _files(project, cid)
    state.save_review(project, {"accepted": ["c01", "c02"], "rejected": ["c03"]})
    item = T.delete_clips(project.id, ["c02"])
    assert item["kind"] == "clips" and item["clip_ids"] == ["c02"] and item["days_left"] == 30
    assert item["bytes"] >= 5000 + 300 + 200
    assert _cids(project) == ["c01", "c03"]
    assert state.load_review(project)["accepted"] == ["c01"]
    assert "c02" not in state.load_clips(project) and "c01" in state.load_clips(project)
    assert not (project.cache_dir / "covers" / "c02_face_tall_abc123.jpg").exists()
    assert (project.cache_dir / "covers" / "c01_face_tall_abc123.jpg").exists()  # the neighbour is untouched
    assert (project.dir / "source.mp4").exists()
    # in the trash
    s = T.summary()
    assert s["count"] == 1 and s["items"][0]["titles"] and s["bytes"] == item["bytes"]
    # undo
    T.restore(item["id"])
    assert _cids(project) == ["c01", "c02", "c03"]
    assert state.load_review(project)["accepted"] == ["c01", "c02"]
    assert "c02" in state.load_clips(project)
    assert (project.cache_dir / "thumbnails" / "c02.jpg").read_bytes() == b"t" * 200
    assert T.summary()["count"] == 0
    with pytest.raises(SharkyClipsError, match="isn't in the trash"):
        T.restore(item["id"])


def test_several_clips_at_once_and_a_manual_clip(tr):
    from sharkyclips.edit import manual

    project = _project("pub-trash-many", n=3)
    m = manual.add(project, 2.0, 7.0) if hasattr(manual, "add") else None
    ids = _cids(project)
    gone = ["c01", "c03"] + ([m["id"]] if m else [])
    item = T.delete_clips(project.id, gone)
    assert _cids(project) == ["c02"]
    if m:
        assert not any(x["id"] == m["id"] for x in manual.load(project))
        assert m["id"] not in _cids(project)  # it doesn't come back through manual.json
    T.restore(item["id"])
    assert _cids(project) == ids
    if m:
        assert any(x["id"] == m["id"] for x in manual.load(project))
    with pytest.raises(SharkyClipsError, match="No clip"):
        T.delete_clips(project.id, ["c99"])


def test_plans_stop_and_come_back(tr):
    from sharkyclips import platforms as PF, pubqueue as PQ

    project = _project("pub-trash-plans", n=2)
    later = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    item = P.new_item(project.id, "c01", {"title": "T"})
    item["publish_at"] = later
    P.put(item)
    PF.record(project, "c01", "tiktok", status="scheduled", publish_at=later, mode="api")
    PQ.plan_batch([{"id": "x", "source": f"{project.id}:c01", "sha256": "s", "file": "/x.mp4", "title": "T",
                    "platforms": ["instagram"], "mode": "gaming"}], PQ.settings(), batch="b")
    rec = T.delete_clips(project.id, ["c01"])
    assert P.get(P.key_of(project.id, "c01")) is None
    assert _rec(project, "c01", "tiktok")["status"] == "idle"
    assert not [e for e in PQ.load_calendar()["entries"] if e.get("source") == f"{project.id}:c01"]
    T.restore(rec["id"])
    assert P.get(P.key_of(project.id, "c01"))["publish_at"] == later
    assert _rec(project, "c01", "tiktok")["status"] == "scheduled"
    assert [e for e in PQ.load_calendar()["entries"] if e.get("source") == f"{project.id}:c01"]


def test_jobs_of_deleted_things_are_cancelled(tr):
    from sharkyclips.web import app as A

    project = _project("pub-trash-jobs", n=2)
    go = threading.Event()

    def slow(job):
        while not job.cancel_requested and not go.is_set():
            time.sleep(0.02)

    j1 = A.jobs.submit("export", "gpu", project.id, {"clip_id": "c01"}, slow, dedupe=False)
    j2 = A.jobs.submit("export", "net", project.id, {"clip_id": "c02"}, slow, dedupe=False)
    T.delete_clips(project.id, ["c01"])
    assert A.jobs.get(j1.id).status == "cancelled"
    assert A.jobs.get(j2.id).status in ("queued", "running")
    T.delete_project(project.id)
    assert A.jobs.get(j2.id).status == "cancelled"
    go.set()


def test_delete_a_project_keeps_the_original_unless_ticked(tr):
    original = tr / "my-recordings" / "stream.mkv"
    original.parent.mkdir()
    original.write_bytes(b"v" * 4000)
    for with_original in (False, True):
        project = _project(f"pub-trash-proj-{int(with_original)}", n=2)
        meta = project.load_meta()
        meta["source"] = {"type": "file", "value": str(original)}
        project.save_meta(meta)
        info = _client().get(f"/api/projects/{project.id}/delete-info").json()
        assert info["original"]["path"] == str(original) and info["original"]["outside_workspace"]
        r = _client().post(f"/api/projects/{project.id}/delete", json={"original": with_original})
        assert r.status_code == 200, r.text
        item = r.json()["item"]
        assert not project.dir.exists() and project.id not in [p.id for p in __import__("sharkyclips.project", fromlist=["x"]).list_projects()]
        assert original.exists() != with_original
        assert item["original"]["moved"] is with_original
        _client().post(f"/api/trash/{item['id']}/restore")
        assert project.dir.is_dir() and (project.dir / "meta.json").is_file() and original.exists()
        assert original.read_bytes() == b"v" * 4000


def test_posts_are_only_deleted_when_ticked(tr, monkeypatch):
    from sharkyclips import platforms as PF, youtube

    project = _project("pub-trash-posts", n=2)
    state.save_upload(project, "c01", {"video_id": "abcdefghijk", "url": "https://youtu.be/abcdefghijk", "privacy": "public"})
    PF.record(project, "c01", "tiktok", status="published", url="https://www.tiktok.com/@me/video/1", mode="semi")
    gone = []
    monkeypatch.setattr(youtube, "delete_video", lambda vid: gone.append(vid) or True)
    info = _client().get(f"/api/projects/{project.id}/delete-info?clips=c01").json()
    assert {p["platform"] for p in info["posts"]} == {"youtube", "tiktok"}
    a = T.delete_clips(project.id, ["c01"])  # not ticked: nothing on YouTube happens
    assert gone == [] and a["posts"] is None
    T.restore(a["id"])
    b = T.delete_clips(project.id, ["c01"], with_posts=True)
    assert gone == ["abcdefghijk"]
    assert [p["platform"] for p in b["posts"]["by_hand"]] == ["tiktok"]  # TikTok's API can't delete
    assert state.load_uploads(project)["c01"][0]["missing"] is True


def test_empty_trash_needs_the_count_and_old_items_expire(tr):
    project = _project("pub-trash-empty", n=3)
    _files(project, "c01")
    a = T.delete_clips(project.id, ["c01"])
    b = T.delete_clips(project.id, ["c02"])
    c = _client()
    r = c.post("/api/trash/empty", json={"count": 5})
    assert r.status_code == 400 and T.summary()["count"] == 2
    r = c.post("/api/trash/empty", json={"count": 2}).json()
    assert r["deleted"] == 2 and r["bytes"] >= 5000 and r["trash"]["count"] == 0
    assert not (T.root() / a["id"]).exists() and not (T.root() / b["id"]).exists()
    # 30 days
    d = T.delete_clips(project.id, ["c03"])
    rec = T.load(d["id"])
    rec["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    write_json_atomic(T.root() / d["id"] / "trash.json", rec)
    assert T.purge_expired() == 1 and T.summary()["count"] == 0
    # one item for good
    project2 = _project("pub-trash-empty2", n=1)
    e = T.delete_project(project2.id)
    assert c.delete(f"/api/trash/{e['id']}").json()["trash"]["count"] == 0


def test_restore_refuses_when_the_place_is_taken(tr):
    project = _project("pub-trash-clash", n=2)
    a = T.delete_project(project.id)
    _project("pub-trash-clash", n=1)  # imported again meanwhile
    with pytest.raises(SharkyClipsError, match="same name"):
        T.restore(a["id"])
    project = _project("pub-trash-clash2", n=2)
    b = T.delete_clips(project.id, ["c02"])
    hl = state.load_highlights(project)
    hl["candidates"].append({**hl["candidates"][0], "id": "c02"})  # clips were found anew
    write_json_atomic(project.dir / "highlights.json", hl)
    with pytest.raises(SharkyClipsError, match="again"):
        T.restore(b["id"])


def test_disk_usage_and_cleanup(tr):
    project = _project("pub-trash-clean", n=3)
    for cid in ("c01", "c03"):
        _files(project, cid)
    state.save_review(project, {"accepted": ["c01"], "rejected": ["c03"]})
    (project.dir / "previews").mkdir()
    (project.dir / "previews" / "01_s100.mp4").write_bytes(b"p" * 7000)
    (project.cache_dir / "frames").mkdir(parents=True, exist_ok=True)
    (project.cache_dir / "frames" / "1280_3.0.jpg").write_bytes(b"f" * 900)
    u = T.usage(project)
    assert u["cleanable"]["rejected"]["bytes"] >= 5000 and u["cleanable"]["previews"]["bytes"] == 7000
    assert u["cleanable"]["caches"]["bytes"] == 900 and u["total"] >= u["source"] + 7000
    d = _client().get("/api/disk").json()
    assert any(r["project_id"] == project.id and r["cleanable_bytes"] == u["cleanable_bytes"] for r in d["projects"])
    r = _client().post(f"/api/projects/{project.id}/cleanup", json={"what": ["rejected", "previews", "caches"]}).json()
    assert r["freed_now"] == 900 and r["trashed"]["bytes"] >= 12000
    assert not (project.dir / "previews").exists() and "c03" not in state.load_clips(project)
    assert "c01" in state.load_clips(project) and _cids(project) == ["c01", "c02", "c03"]  # the clip itself stays
    assert r["usage"]["cleanable_bytes"] == 0
    T.restore(r["trashed"]["id"])
    assert (project.dir / "previews" / "01_s100.mp4").exists() and "c03" in state.load_clips(project)


def test_deleted_projects_are_invisible_everywhere(tr):
    project = _project("pub-trash-hidden", n=2)
    T.delete_project(project.id)
    c = _client()
    ids = [p["id"] for p in c.get("/api/projects").json()]
    assert project.id not in ids
    assert c.get(f"/api/projects/{project.id}").status_code in (400, 404)
    assert not list(config.workspace_dir().glob("*/uploads.json")) or all(
        "_trash" not in str(p) for p in config.workspace_dir().glob("*/uploads.json"))
    assert json.loads((T.root() / T.summary()["items"][0]["id"] / "trash.json").read_text(encoding="utf-8"))["kind"] == "project"
