"""1.2.63 clip end point: frontend/src/clipEnd.ts (run with Node) - markers on the progress bar, time
left, and the stop / loop decision exactly at the clip's end for every clip length; plus the UI
wiring (every player that shows a clip uses it)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"


def _node_ts() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "-e", "console.log(process.features && process.features.typescript || '')"],
                         capture_output=True, text=True)
    return node if out.stdout.strip() not in ("", "false", "undefined") else None


def _run(tmp_path, body: str):
    node = _node_ts()
    if not node:
        pytest.skip("needs Node with TypeScript support (22.18+)")
    script = tmp_path / "run.mjs"
    script.write_text(f"const m = await import({json.dumps((SRC / 'clipEnd.ts').as_uri())});\n{body}", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_markers_range_and_time_left(tmp_path):
    got = _run(tmp_path, """
console.log(JSON.stringify([
  m.clipState(12, 10, 20, 100), m.clipState(20, 10, 20, 100), m.clipState(5, 10, 20, 100),
  m.clipState(1.5, 0, 3, 3), m.clipState(0, 0, 3, null), m.clipState(19.99, 10, 20, 100),
  m.fmtLeft(2.46), m.fmtLeft(12.9), m.fmtLeft(-1), m.seekTarget(0.5, 60), m.seekTarget(1.4, 60)]));
""")
    a, at_end, before, file_mid, file_start, hair, l1, l2, l3, s1, s2 = got
    assert a["startPct"] == 10 and a["endPct"] == 20 and a["playPct"] == 12 and a["inClip"]
    assert abs(a["left"] - 8) < 1e-9 and abs(a["progress"] - 0.2) < 1e-9 and not a["atEnd"]
    assert at_end["atEnd"] and at_end["left"] == 0 and at_end["inClip"]
    assert not before["inClip"] and before["progress"] == 0
    assert file_mid["endPct"] == 100 and abs(file_mid["left"] - 1.5) < 1e-9  # a rendered clip file
    assert file_start["startPct"] == 0 and file_start["endPct"] == 100
    assert hair["atEnd"]  # within one frame of the end counts as the end
    assert (l1, l2, l3) == ("2.4", "12", "0.0")
    assert s1 == 30 and s2 == 60


@pytest.mark.parametrize("start,end", [(0, 3), (10, 24.5), (100.25, 160.0), (0, 0.6)])
def test_playback_stops_or_loops_exactly_at_the_end(tmp_path, start, end):
    """A 60 fps playhead: the first frame at / past the end triggers it, never a frame later,
    never earlier than half a frame before the end."""
    got = _run(tmp_path, f"""
const start = {start}, end = {end}, out = [];
for (const mode of ["stop", "loop"]) {{
  let first = null;
  for (let t = start; t < end + 1; t += 1 / 60) {{
    if (m.endAction(t, end, mode) !== "none") {{ first = [t, m.endAction(t, end, mode)]; break; }}
  }}
  out.push(first);
}}
console.log(JSON.stringify(out));
""")
    (t_stop, a_stop), (t_loop, a_loop) = got
    assert a_stop == "stop" and a_loop == "loop"
    for t in (t_stop, t_loop):
        assert end - (1 / 30) / 2 - 1e-9 <= t <= end + 1 / 60 + 1e-9


def test_loop_wrap_is_noticed(tmp_path):
    got = _run(tmp_path, """
console.log(JSON.stringify([m.wrapped(2.95, 0.02, 0, 3), m.wrapped(1.0, 0.5, 0, 3), m.wrapped(23.9, 10.1, 10, 24)]));
""")
    assert got == [True, False, True]


def test_every_clip_player_shows_the_end_point():
    """Pro main player (source video + clip range), the 9:16 live preview, rendered clips, the
    final preview, the Easy cards and the Easy trim editor all use the clip end parts."""
    project = (SRC / "pages" / "Project.tsx").read_text(encoding="utf-8")
    assert "<ClipBar" in project and project.count("<EndBadge") >= 2 and "<ClipVideo" in project
    assert 'controlsList="nofullscreen"' in project  # big preview = our box, so the markers stay visible
    easy = (SRC / "pages" / "EasyProject.tsx").read_text(encoding="utf-8")
    assert easy.count("<ClipBar") >= 2 and easy.count("<EndBadge") >= 2 and "useClipEnforcer" in easy
    assert "<ClipVideo" in (SRC / "components" / "PreviewExtras.tsx").read_text(encoding="utf-8")
    editing = (SRC / "editing.ts").read_text(encoding="utf-8")
    assert re.search(r"v\.pause\(\);\s*v\.currentTime = end;", editing)  # stops ON the last frame
    for lang in ("en", "tr", "es", "pt", "de", "fr", "hu", "ru", "ar", "zh", "ja"):
        loc = (SRC / "i18n" / "locales" / f"{lang}.ts").read_text(encoding="utf-8")
        assert '"clipend.end"' in loc and '"clipend.left"' in loc and "{s}" in loc.split('"clipend.left"')[1][:80]
