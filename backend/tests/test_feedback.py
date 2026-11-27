"""1.2.74 "Send feedback / Report a bug": a pre-filled GitHub issue form, nothing personal in it."""

from __future__ import annotations

import getpass
import json
import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from sharkyclips import feedback

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"


def _ids(name: str) -> set[str]:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    return set(re.findall(r"^\s+id:\s*([a-z_]+)\s*$", text, re.M))


def test_system_label_is_short_and_not_personal():
    label = feedback.system_label()
    assert 0 < len(label) <= 80
    for secret in {getpass.getuser(), socket.gethostname(), platform.node()} - {""}:
        assert secret.lower() not in label.lower()
    assert "\\" not in label and "/" not in label  # no paths


def test_linux_label_reads_only_the_pretty_name(tmp_path):
    f = tmp_path / "os-release"
    f.write_text('NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.1 LTS"\nID=ubuntu\n', encoding="utf-8")
    assert feedback._linux_name(f) == "Ubuntu 24.04.1 LTS"
    assert feedback._linux_name(tmp_path / "missing") == "Linux"


def test_meta_carries_the_system_label():
    from fastapi.testclient import TestClient

    from sharkyclips.web.app import app

    meta = TestClient(app).get("/api/meta").json()  # no `with`: startup would install the real governor
    assert meta["system"] == feedback.system_label()


def test_issue_templates_have_the_fields_the_app_and_site_fill_in():
    bug = _ids("bug_report.yml")
    assert {"what", "version", "os", "source", "logs"} <= bug
    assert "source" in _ids("feature_request.yml")
    ts = (ROOT / "frontend" / "src" / "feedback.ts").read_text(encoding="utf-8")
    for field in re.findall(r'p\.set\("([a-z_]+)"', ts):
        if field in ("template", "labels", "title"):
            continue
        assert field in bug | _ids("feature_request.yml"), field
    assert "bug_report.yml" in ts and "feature_request.yml" in ts


def test_buttons_are_in_about_and_on_every_error_toast():
    lic = (ROOT / "frontend" / "src" / "components" / "Licenses.tsx").read_text(encoding="utf-8")
    assert lic.count("<FeedbackButtons />") == 2  # Easy and Pro settings
    toast = (ROOT / "frontend" / "src" / "toast.tsx").read_text(encoding="utf-8")
    assert 'openFeedback("bug"' in toast and 't.kind === "err"' in toast


def _node_ts() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "-e", "console.log(process.features && process.features.typescript || '')"],
                         capture_output=True, text=True)
    return node if out.stdout.strip() not in ("", "false", "undefined") else None


def test_error_text_is_scrubbed_before_it_goes_into_the_form(tmp_path):
    node = _node_ts()
    if not node:
        pytest.skip("needs Node with TypeScript support (22.18+)")
    src = (ROOT / "frontend" / "src" / "feedback.ts").as_uri()
    err = ("File not found: C:\\Users\\alice\\Videos\\my stream.mp4 - see /home/alice/x.log, "
           "mail alice@example.com, token abcdefghijklmnopqrstuvwxyz0123456789, "
           "url https://www.youtube.com/watch?v=secret123&list=x http://127.0.0.1:8000/api/x")
    script = tmp_path / "run.mjs"
    script.write_text(f"""
const m = await import({json.dumps(src)});
m.setFeedbackInfo({{version: "1.2.74", system: "Windows 11 (AMD64, build 26100)"}});
console.log(JSON.stringify({{bug: m.feedbackUrl("bug", {json.dumps(err)}), plain: m.feedbackUrl("bug"),
  idea: m.feedbackUrl("idea"), scrub: m.scrub({json.dumps(err)})}}));
""", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    for leak in ("alice", "example.com", "abcdefghijklmnopqrstuvwxyz", "secret123", "8000", "Videos"):
        assert leak not in out["scrub"], leak
        assert leak not in out["bug"], leak
    q = {k: v[0] for k, v in parse_qs(urlparse(out["bug"]).query).items()}
    assert urlparse(out["bug"]).netloc == "github.com" and out["bug"].startswith(feedback.REPO_URL + "/issues/new?")
    assert q["template"] == "bug_report.yml" and q["version"] == "1.2.74" and q["source"] == "app"
    assert q["os"] == "Windows 11 (AMD64, build 26100)" and "File not found: <path>" in q["what"]
    plain = {k: v[0] for k, v in parse_qs(urlparse(out["plain"]).query).items()}
    assert set(plain) == {"template", "labels", "version", "os", "source"}  # nothing else without an error
    assert "feature_request.yml" in out["idea"] and "version" not in out["idea"]
