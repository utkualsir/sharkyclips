"""1.2.56 Windows installer support: install mode, first-run downloads, migration, updater."""

from __future__ import annotations

import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

from sharkyclips import appinstall, components, config, updater
from sharkyclips.errors import SharkyClipsError

# ------------------------------------------------------------------ a tiny local file server


class _Handler(http.server.BaseHTTPRequestHandler):
    files: dict[str, bytes] = {}
    json_routes: dict[str, dict] = {}
    ranges = True
    hits: list[tuple[str, str | None]] = []
    cut_after: int | None = None  # drop the connection after this many bytes (once)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):  # noqa: N802
        type(self).hits.append((self.path, self.headers.get("Range")))
        if self.path in self.json_routes:
            body = json.dumps(self.json_routes[self.path]).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data = self.files.get(self.path)
        if data is None:
            self.send_response(404)
            self.end_headers()
            return
        start = 0
        rng = self.headers.get("Range")
        if rng and self.ranges:
            start = int(rng.split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        else:
            self.send_response(200)
        part = data[start:]
        self.send_header("Content-Length", str(len(part)))
        self.end_headers()
        cut = type(self).cut_after
        if cut is not None:
            type(self).cut_after = None
            self.wfile.write(part[:cut])
            self.wfile.flush()
            self.connection.close()
            return
        self.wfile.write(part)


@pytest.fixture()
def server(monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_ALLOW_LOCAL_HTTP", "1")
    _Handler.files, _Handler.json_routes, _Handler.hits = {}, {}, []
    _Handler.ranges, _Handler.cut_after = True, None
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", _Handler
    httpd.shutdown()


# ------------------------------------------------------------------ install mode


def test_install_kind_and_default_workspace(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    assert appinstall.kind(root) == "folder"
    (root / ".git").mkdir()
    assert appinstall.kind(root) == "git"
    (root / "install.json").write_text(json.dumps({"kind": "installer", "version": "9.9.9"}), encoding="utf-8")
    assert appinstall.kind(root) == "installer"
    assert appinstall.default_workspace(root).name == "SharkyClips"
    assert not str(appinstall.default_workspace(root)).startswith(str(root))  # never inside the app folder
    (root / "install.json").write_text("not json", encoding="utf-8")
    assert appinstall.kind(root) == "git"


def test_setup_paths_puts_bundled_ffmpeg_and_tools_first(tmp_path, monkeypatch):
    root = tmp_path / "app"
    (root / "ffmpeg" / "bin").mkdir(parents=True)
    (appinstall.tools_dir() / "deno").mkdir(parents=True, exist_ok=True)
    appinstall.gpu_dir().mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PATH", "C:/elsewhere")
    monkeypatch.setattr("sys.path", list(__import__("sys").path))
    appinstall.setup_paths(root)
    parts = __import__("os").environ["PATH"].split(__import__("os").pathsep)
    assert parts[0] == str(root / "ffmpeg" / "bin")
    assert str(appinstall.tools_dir() / "deno") in parts
    assert str(appinstall.gpu_dir()) in __import__("sys").path


def test_migration_from_a_git_install_keeps_projects_where_they_are(tmp_path, monkeypatch):
    old = tmp_path / "SharkyClips"
    (old / "backend").mkdir(parents=True)
    (old / "backend" / "cli.py").write_text("", encoding="utf-8")
    (old / "workspace" / "my-stream").mkdir(parents=True)
    (old / "workspace" / "my-stream" / "meta.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SHARKYCLIPS_OLD_INSTALL", str(old))
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    saved = config.load()
    try:
        cfg = config.load()
        cfg.pop("workspace_dir", None)
        cfg.pop("installer_migrated", None)
        config.save(cfg)
        done = appinstall.migrate_from_git()
        assert done["workspace"] == str(old / "workspace")
        assert config.get("workspace_dir") == str(old / "workspace")
        assert (old / "workspace" / "my-stream" / "meta.json").is_file()  # nothing moved or deleted
        assert appinstall.migrate_from_git() == {}  # once
    finally:
        config.save(saved)


def test_fresh_installer_copy_pins_the_videos_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("SHARKYCLIPS_OLD_INSTALL", str(tmp_path / "none"))
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    saved = config.load()
    try:
        cfg = config.load()
        cfg.pop("workspace_dir", None)
        cfg.pop("installer_migrated", None)
        config.save(cfg)
        appinstall.migrate_from_git()
        assert Path(config.get("workspace_dir")).name == "SharkyClips"
        assert config.get("installer_migrated") is True
    finally:
        config.save(saved)


# ------------------------------------------------------------------ downloads


def test_download_checks_sha256_and_resumes(server, tmp_path):
    base, h = server
    data = bytes(range(256)) * 4096 * 4  # 4 MB (downloads read 1 MB chunks)
    h.files["/f.bin"] = data
    sha = hashlib.sha256(data).hexdigest()
    h.cut_after = 2_500_000  # the first connection breaks after 2.5 MB
    seen = []
    out = components.download(f"{base}/f.bin", tmp_path / "f.bin", sha256=sha, size=len(data),
                              on_bytes=lambda n, t: seen.append(n))
    assert out.read_bytes() == data
    assert any(r and r.startswith("bytes=") for _p, r in h.hits), h.hits  # the second try resumed
    assert not (tmp_path / "f.bin.part").exists()
    # already there and correct: no new request
    n = len(h.hits)
    components.download(f"{base}/f.bin", tmp_path / "f.bin", sha256=sha, size=len(data))
    assert len(h.hits) == n


def test_download_with_a_wrong_checksum_is_deleted(server, tmp_path):
    base, h = server
    h.files["/bad.bin"] = b"x" * 1000
    with pytest.raises(SharkyClipsError, match="checksum"):
        components.download(f"{base}/bad.bin", tmp_path / "bad.bin", sha256="0" * 64, size=1000)
    assert not (tmp_path / "bad.bin").exists() and not (tmp_path / "bad.bin.part").exists()


def test_download_refuses_plain_http(tmp_path, monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_ALLOW_LOCAL_HTTP", raising=False)
    with pytest.raises(SharkyClipsError, match="https"):
        components.download("http://example.com/x", tmp_path / "x", sha256="0" * 64)


def test_git_blob_hash_matches_git(tmp_path):
    f = tmp_path / "config.json"
    f.write_bytes(b"hello\n")
    # `git hash-object` of "hello\n"
    assert components.file_hash(f, "sha1", git_blob=True) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_progress_reports_bytes_speed_and_time_left():
    got = []
    p = components.Progress([{"id": "a", "size_mb": 1}, {"id": "b", "size_mb": 1}], got.append)
    p.start("a", 1000)
    p.set("a", 500)
    p.finish("a")
    p.start("b", 1000)
    last = got[-1]
    assert last["total_bytes"] == 2000 and last["done_bytes"] == 1000
    assert [i["status"] for i in last["items"]] == ["done", "downloading"]


def test_plan_lists_required_parts_and_works_offline(monkeypatch):
    monkeypatch.setattr(components, "whisper_model_for_pc", lambda: "small")
    monkeypatch.setattr(components, "whisper_present", lambda name: name == "tiny")
    monkeypatch.setattr(components, "ollama_present", lambda: False)
    monkeypatch.setattr(components, "llm_present", lambda name: False)
    p = components.plan()
    ids = {i["id"]: i for i in p["items"]}
    assert ids["whisper"]["detail"]["model"] == "small" and ids["whisper"]["selected"]
    assert ids["whisper_tiny"]["present"] and not ids["whisper_tiny"]["selected"]
    assert "whisper" in p["missing_required"] and not p["ready"]
    assert p["total_mb"] >= ids["whisper"]["size_mb"]


def test_install_keeps_going_after_one_part_fails(monkeypatch):
    plan = {"items": [{"id": "whisper", "present": False, "available": True, "size_mb": 1,
                       "detail": {"model": "small"}},
                      {"id": "deno", "present": False, "available": True, "size_mb": 1, "detail": {}}]}
    monkeypatch.setattr(components, "plan", lambda: plan)

    def boom(*a, **k):
        raise SharkyClipsError("no network")

    done = []
    monkeypatch.setattr(components, "install_whisper", boom)
    monkeypatch.setattr(components, "install_deno", lambda prog, iid, c: (done.append(iid), prog.finish(iid)))
    res = components.install(["whisper", "deno"], lambda d: None)
    assert res["results"]["whisper"] == {"ok": False, "error": "no network", "hint": None}
    assert res["results"]["deno"] == {"ok": True} and done == ["deno"] and not res["ok"]


def test_whisper_download_lands_in_the_hf_cache_layout(server, tmp_path, monkeypatch):
    base, h = server
    blobs = {"config.json": b'{"a": 1}', "model.bin": b"M" * 5000, "tokenizer.json": b"{}",
             "vocabulary.txt": b"a\nb\n", "preprocessor_config.json": b"{}"}
    siblings = []
    for name, data in blobs.items():
        sib = {"rfilename": name, "size": len(data),
               "blobId": hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()}
        if name == "model.bin":
            sib["lfs"] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
        siblings.append(sib)
        h.files[f"/org/fw-test/resolve/abc123/{name}"] = data
    h.json_routes["/api/models/org/fw-test?blobs=true"] = {"sha": "abc123", "siblings": siblings}
    monkeypatch.setenv("HF_ENDPOINT", base)
    monkeypatch.setattr(components, "_hf_cache", lambda: tmp_path / "hf")
    import faster_whisper.utils as fwu

    monkeypatch.setitem(fwu._MODELS, "testmodel", "org/fw-test")
    present = {"v": False}
    monkeypatch.setattr(components, "whisper_present", lambda name: present["v"])
    prog = components.Progress([{"id": "whisper", "size_mb": 1}], lambda d: None)

    def fake_present_after(*a, **k):
        present["v"] = (tmp_path / "hf" / "models--org--fw-test" / "snapshots" / "abc123" / "model.bin").is_file()
        return present["v"]

    monkeypatch.setattr(components, "whisper_present", lambda name: fake_present_after())
    present["v"] = False
    # first call (already there?) must say no: no snapshot yet
    components.install_whisper("testmodel", prog, "whisper", lambda: False)
    snap = tmp_path / "hf" / "models--org--fw-test" / "snapshots" / "abc123"
    assert (snap / "model.bin").read_bytes() == blobs["model.bin"]
    assert (tmp_path / "hf" / "models--org--fw-test" / "refs" / "main").read_text() == "abc123"
    assert (tmp_path / "hf" / "models--org--fw-test" / "blobs" / hashlib.sha256(blobs["model.bin"]).hexdigest()).is_file()


# ------------------------------------------------------------------ updater (installed copy)


def _release(base: str, version: str, data: bytes, digest: str | None = None) -> dict:
    name = f"SharkyClips-Setup-{version}.exe"
    sha = hashlib.sha256(data).hexdigest()
    return {"tag_name": f"v{version}", "draft": False, "prerelease": False, "body": "- faster\n- fixed", "html_url": base,
            "assets": [{"name": name, "browser_download_url": f"{base}/{name}", "size": len(data),
                        "digest": digest or f"sha256:{sha}"},
                       {"name": name + ".sha256", "browser_download_url": f"{base}/{name}.sha256", "size": 90}]}


def test_installer_update_status_offers_only_a_newer_release(server, monkeypatch):
    base, h = server
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", f"{base}/latest")
    h.json_routes["/latest"] = _release(base, "99.0.0", b"setup")
    st = updater.status()
    assert st["kind"] == "installer" and st["available"] and st["latest"] == "99.0.0"
    assert st["changes"] == ["faster", "fixed"]
    h.json_routes["/latest"] = _release(base, "0.0.1", b"setup")
    st = updater.status()
    assert not st["available"] and st["reason"] == "not_newer"


def test_installer_update_without_the_installer_asset_is_not_released(server, monkeypatch):
    base, h = server
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", f"{base}/latest")
    rel = _release(base, "99.0.0", b"setup")
    rel["assets"] = []
    h.json_routes["/latest"] = rel
    st = updater.status()
    assert not st["available"] and st["reason"] == "not_released"


def test_installer_update_downloads_and_verifies(server, monkeypatch):
    base, h = server
    data = b"MZ fake installer " * 1000
    name = "SharkyClips-Setup-99.0.0.exe"
    h.files[f"/{name}"] = data
    h.files[f"/{name}.sha256"] = f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode()
    h.json_routes["/latest"] = _release(base, "99.0.0", data)
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", f"{base}/latest")
    monkeypatch.setattr(updater, "authenticode", lambda p: {"status": "NotSigned"})
    res = updater.apply()
    assert res["pending_install"] and res["version"] == "99.0.0"
    assert Path(res["installer"]).read_bytes() == data
    assert Path(res["installer"]).parent == appinstall.updates_dir()


def test_installer_update_refuses_a_digest_mismatch(server, monkeypatch):
    base, h = server
    data = b"MZ fake installer"
    name = "SharkyClips-Setup-99.0.0.exe"
    h.files[f"/{name}"] = data
    h.files[f"/{name}.sha256"] = f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode()
    h.json_routes["/latest"] = _release(base, "99.0.0", data, digest="sha256:" + "1" * 64)
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", f"{base}/latest")
    with pytest.raises(SharkyClipsError, match="don't agree"):
        updater.apply()


def test_installer_update_refuses_a_tampered_file(server, monkeypatch):
    base, h = server
    data = b"MZ fake installer"
    name = "SharkyClips-Setup-99.0.0.exe"
    for old in appinstall.updates_dir().glob("*.exe"):  # an earlier test's (valid) download
        old.unlink()
    h.files[f"/{name}"] = data + b"evil"
    h.files[f"/{name}.sha256"] = f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode()
    h.json_routes["/latest"] = _release(base, "99.0.0", data)
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", f"{base}/latest")
    with pytest.raises(SharkyClipsError, match="checksum"):
        updater.apply()
    assert not list(appinstall.updates_dir().glob("*.exe"))


def test_installer_update_refuses_an_older_release(server, monkeypatch):
    base, h = server
    h.json_routes["/latest"] = _release(base, "0.0.1", b"x")
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", f"{base}/latest")
    with pytest.raises(SharkyClipsError, match="isn't newer"):
        updater.apply()


def test_require_signed_refuses_an_unsigned_installer(server, monkeypatch):
    base, h = server
    data = b"MZ"
    name = "SharkyClips-Setup-99.0.0.exe"
    h.files[f"/{name}"] = data
    h.files[f"/{name}.sha256"] = f"{hashlib.sha256(data).hexdigest()} *{name}\n".encode()
    h.json_routes["/latest"] = _release(base, "99.0.0", data)
    monkeypatch.setenv("SHARKYCLIPS_INSTALL_KIND", "installer")
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", f"{base}/latest")
    monkeypatch.setattr(updater, "authenticode", lambda p: {"status": "NotSigned"})
    saved = config.load()
    try:
        config.update(update_require_signed=True)
        with pytest.raises(SharkyClipsError, match="signed"):
            updater.apply()
    finally:
        config.save(saved)
    monkeypatch.setattr(updater, "authenticode", lambda p: {"status": "HashMismatch"})
    with pytest.raises(SharkyClipsError, match="not valid"):
        updater.apply()


def test_update_api_must_be_https(monkeypatch):
    monkeypatch.delenv("SHARKYCLIPS_ALLOW_LOCAL_HTTP", raising=False)
    monkeypatch.setenv("SHARKYCLIPS_UPDATE_API", "http://evil.example/latest")
    with pytest.raises(SharkyClipsError):
        updater.latest_release()


def test_sha256_file_parsing():
    sha = "a" * 64
    assert updater.parse_sha256_file(f"{sha}  SharkyClips-Setup-1.2.3.exe", "SharkyClips-Setup-1.2.3.exe") == sha
    assert updater.parse_sha256_file(f"{sha} *SharkyClips-Setup-1.2.3.exe", "SharkyClips-Setup-1.2.3.exe") == sha
    assert updater.parse_sha256_file(sha, "x.exe") == sha
    assert updater.parse_sha256_file(f"{sha}  other.exe", "x.exe") is None


# ------------------------------------------------------------------ diagnostics, API


def test_diag_report_has_no_secrets_or_user_name(monkeypatch):
    from sharkyclips import diag

    log = diag.log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    home = str(Path.home())
    fake = "ya29" + "." + "abcdefghij" * 3  # built here: the repo's secret scan must not see a literal
    log.write_text(f"token {fake} for me@example.com in {home}" + chr(10), encoding="utf-8")
    text = diag.report_text(with_hardware=False)
    assert fake not in text and "me@example.com" not in text
    assert home not in text
    assert "SharkyClips" in text and "install:" in text


def test_setup_api_plan_and_start(monkeypatch):
    from fastapi.testclient import TestClient

    from sharkyclips.web import app as A

    monkeypatch.setattr(components, "plan", lambda: {"items": [{"id": "deno", "present": False, "available": True,
                                                                "size_mb": 1, "detail": {}, "selected": True}],
                                                     "ready": True, "missing_required": []})
    started = threading.Event()

    def fake_install(ids, report, cancelled):
        report({"fraction": 1.0, "current": "deno", "items": []})
        started.set()
        return {"ok": True, "results": {"deno": {"ok": True}}, "cancelled": False}

    monkeypatch.setattr(components, "install", fake_install)
    c = TestClient(A.app)
    assert c.get("/api/setup").json()["items"][0]["id"] == "deno"
    r = c.post("/api/setup/download", json={"ids": ["deno", "rm -rf"]})
    assert r.status_code == 200 and r.json()["params"]["ids"] == ["deno"]
    assert started.wait(10)
    assert c.post("/api/setup/download", json={"ids": []}).status_code >= 400
    st = c.get("/api/app").json()
    assert "install_kind" in st and "setup_needed" in st
