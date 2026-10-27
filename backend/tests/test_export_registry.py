"""Export bookkeeping: request validation, the registry, deleting, subtitle files."""

from __future__ import annotations

import json

import pytest

from sharkyclips import export
from sharkyclips.errors import SharkyClipsError
from sharkyclips.project import Project


@pytest.fixture
def project(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    return Project("proj", d)


def _entry(project, eid, names):
    root = export.exports_root(project)
    root.mkdir(parents=True, exist_ok=True)
    files = []
    for n in names:
        (root / n).write_bytes(b"data")
        files.append({"name": n, "role": "video", "mime": "video/mp4", "size_bytes": 4})
    export._save_entry(project, {"id": eid, "files": files})


def test_request_validation():
    r = export.ExportRequest.from_dict({"format": "mp4_h264", "preset": "tiktok", "subtitles": ["srt", "xyz"],
                                        "editors": ["fcpxml", "avid"], "gif_max_mb": "500"})
    assert r.subtitles == ("srt",) and r.editors == ("fcpxml",) and r.gif_max_mb == 100.0
    assert export.ExportRequest.from_dict({"format": "gif", "gif_max_mb": "x"}).gif_max_mb == export.DEFAULT_GIF_MB
    assert export.ExportRequest.from_dict({"format": None, "subtitles": ["vtt"]}).format is None
    for bad in ({"format": "exe"}, {"format": "mp4_h264", "preset": "myspace"}, {"format": None},
                {"format": "mp4_h264", "subtitle_lang": "xx"}):
        with pytest.raises(SharkyClipsError):
            export.ExportRequest.from_dict(bad)
    d = r.to_dict()
    assert d["subtitles"] == ["srt"] and json.dumps(d)
    assert export.export_stem({"rank": 3, "id": "c07"}, r) == "03_c07_tiktok_mp4_h264"


def test_registry_lists_only_existing_files_and_deletes(project):
    _entry(project, "e1", ["a.mp4", "a.srt"])
    _entry(project, "e2", ["b.mp4"])
    (export.exports_root(project) / "a.srt").unlink()  # deleted by hand
    reg = {e["id"]: [f["name"] for f in e["files"]] for e in export.load_registry(project)}
    assert reg == {"e1": ["a.mp4"], "e2": ["b.mp4"]}
    assert export.file_path(project, "b.mp4") == export.exports_root(project) / "b.mp4"
    assert export.file_path(project, "nope.mp4") is None
    assert export.delete_export(project, "e2") and not (export.exports_root(project) / "b.mp4").exists()
    assert not export.delete_export(project, "e2")
    assert [e["id"] for e in export.load_registry(project)] == ["e1"]


def test_registry_ignores_names_with_paths(project, tmp_path):
    outside = project.dir / "precious.txt"
    outside.write_text("keep me", encoding="utf-8")
    export.exports_root(project).mkdir(parents=True)
    export.registry_path(project).write_text(json.dumps({"exports": [
        {"id": "evil", "files": [{"name": "../../precious.txt"}, {"name": ".."}, {"name": None}]}]}),
        encoding="utf-8")
    assert export.load_registry(project) == []
    assert not export.delete_export(project, "evil")
    assert export.file_path(project, "../../precious.txt") is None
    assert outside.read_text(encoding="utf-8") == "keep me"


def test_broken_registry_counts_as_empty(project):
    export.registry_path(project).parent.mkdir(parents=True)
    export.registry_path(project).write_text("{oops", encoding="utf-8")
    assert export.load_registry(project) == []


def test_subtitle_files(tmp_path):
    cues = [{"start": 0.0, "end": 1.5, "text": "Hello"}, {"start": 61.25, "end": 3725.5, "text": "there"}]
    srt = export.to_srt(cues)
    assert "1\n00:00:00,000 --> 00:00:01,500\nHello" in srt and "01:02:05,500" in srt
    vtt = export.to_vtt(cues, "en")
    assert vtt.startswith("WEBVTT") and "00:01:01.250 --> 01:02:05.500" in vtt
    paths = export.write_subtitles(tmp_path / "clip", cues, "en", ["srt", "vtt"])
    assert sorted(p.suffix for p in paths) == [".srt", ".vtt"] and all(p.is_file() for p in paths)
