"""1.2.69: "Clips from this video were shared on <date>" right at import time.

1. frontend/src/fingerprint.ts (run with Node) gives exactly history.fingerprint for small,
   1 MiB-ish and multi-sample files, with crypto.subtle and with its own SHA-256.
2. /api/history/source?fp= and /api/history/check-path answer before any project exists.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from sharkyclips import history
from test_multipost import _client
from test_preview_math import ROOT, _node_ts
from test_publishing import _clean_projects, _project, cfg  # noqa: F401 - fixtures

SIZES = [0, 5, 1024 * 1024 - 1, 1024 * 1024, 1024 * 1024 + 7, 2 * 1024 * 1024 + 333, 3 * 1024 * 1024 + 1, 5_000_001]


def test_fingerprint_ts_matches_python(tmp_path):
    node = _node_ts()
    if not node:
        pytest.skip("needs Node with TypeScript support (22.18+)")
    files = []
    for i, n in enumerate(SIZES):
        f = tmp_path / f"v{i}.bin"
        f.write_bytes(os.urandom(n))
        files.append(f)
    src = (ROOT / "frontend" / "src" / "fingerprint.ts").as_uri()
    script = tmp_path / "run.mjs"
    script.write_text(f"""
import {{ readFileSync }} from "node:fs";
const m = await import({json.dumps(src)});
const out = [];
for (const p of {json.dumps([str(f) for f in files])}) {{
  const buf = readFileSync(p);
  const blob = new Blob([buf]);
  const viaApi = await m.fingerprintFile(blob);
  const samples = m.sampleRanges(buf.length).map(([a, b]) => new Uint8Array(buf.subarray(a, b)));
  const viaJs = "v1:" + m.sha256Hex(m.fingerprintInput(buf.length, samples)).slice(0, 40);
  out.push([viaApi, viaJs]);
}}
console.log(JSON.stringify(out));
""", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr
    for f, (via_api, via_js) in zip(files, json.loads(res.stdout)):
        want = history.fingerprint(f)
        assert via_api == want and via_js == want, f.stat().st_size


@pytest.fixture
def hist_env(cfg):  # noqa: F811
    history.path().unlink(missing_ok=True)
    _clean_projects()
    yield
    history.path().unlink(missing_ok=True)
    _clean_projects()


def test_import_time_lookup_by_fingerprint_and_by_path(hist_env, tmp_path):
    p1 = _project("pub-imp-hist-a", 2)
    history.note_post(p1, "c01", "youtube", url="https://youtu.be/x1", video_id="x1")
    history.note_post(p1, "c02", "tiktok", url=None, manual=True)
    copy = tmp_path / "renamed copy.mp4"
    shutil.copyfile(p1.dir / "source.mp4", copy)
    fp = history.fingerprint(copy)
    c = _client()
    r = c.get("/api/history/source", params={"fp": fp}).json()
    assert r["before"]["by_platform"] == {"youtube": 1, "tiktok": 1} and r["before"]["first_at"]
    assert r["before_projects"] == ["Stream pub-imp-hist-a"]
    assert c.post("/api/history/check-path", json={"path": str(copy)}).json()["before"]["count"] == 2
    # unknown video, junk fingerprint, URL, missing file: no warning, no error
    other = tmp_path / "other.mp4"
    other.write_bytes(b"x" * 4000)
    assert c.get("/api/history/source", params={"fp": history.fingerprint(other)}).json()["before"] is None
    assert c.get("/api/history/source", params={"fp": "../../etc"}).json() == {"fingerprint": None, "before": None, "before_projects": []}
    assert c.post("/api/history/check-path", json={"path": "https://example.com/v.mp4"}).json()["before"] is None
    assert c.post("/api/history/check-path", json={"path": str(tmp_path / "nope.mp4")}).json()["before"] is None
