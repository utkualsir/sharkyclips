"""The live preview draws what the renderer cuts and zooms (1.2.23).

1. zoom.factor_out / fx.shake_at (what the preview check compares against) equal the ffmpeg
   expressions the renderer really sends, evaluated here with a small expression interpreter.
2. frontend/src/previewMath.ts (run with Node) equals the Python functions.
3. Whisper's endless junk words are cleaned before anything shows them.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from sharkyclips import clips
from sharkyclips.clips import Facecam
from sharkyclips.edit import fx as fx_mod
from sharkyclips.edit import zoom
from sharkyclips.textutil import clean_transcript, clean_word, clean_words

ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------- ffmpeg expression interpreter


class Expr:
    """Enough of ffmpeg's expression language for the zoom / shake filters."""

    def __init__(self, text: str, env: dict[str, float]):
        self.toks = re.findall(r"\d+\.\d*|\d*\.\d+|\d+|[A-Za-z_]\w*|[-+*/(),;]", text)
        self.i = 0
        self.env = env
        self.reg = [0.0] * 10

    def peek(self) -> str | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want: str | None = None) -> str:
        tok = self.toks[self.i]
        if want is not None and tok != want:
            raise ValueError(f"expected {want}, got {tok}")
        self.i += 1
        return tok

    def run(self) -> float:
        val = self.seq()
        assert self.peek() is None, self.toks[self.i:]
        return val

    def seq(self) -> float:  # a;b;c -> c (side effects in order)
        val = self.add()
        while self.peek() == ";":
            self.take()
            val = self.add()
        return val

    def add(self) -> float:
        val = self.mul()
        while self.peek() in ("+", "-"):
            op = self.take()
            rhs = self.mul()
            val = val + rhs if op == "+" else val - rhs
        return val

    def mul(self) -> float:
        val = self.unary()
        while self.peek() in ("*", "/"):
            op = self.take()
            rhs = self.unary()
            val = val * rhs if op == "*" else val / rhs
        return val

    def unary(self) -> float:
        if self.peek() == "-":
            self.take()
            return -self.unary()
        return self.atom()

    def args(self) -> list[float]:
        self.take("(")
        out = [self.seq()]
        while self.peek() == ",":
            self.take()
            out.append(self.seq())
        self.take(")")
        return out

    def atom(self) -> float:
        tok = self.take()
        if tok == "(":
            val = self.seq()
            self.take(")")
            return val
        if re.match(r"[\d.]", tok):
            return float(tok)
        if self.peek() == "(":
            a = self.args()
            if tok == "st":
                self.reg[int(a[0])] = a[1]
                return a[1]
            if tok == "ld":
                return self.reg[int(a[0])]
            fn = {"clip": lambda x, lo, hi: min(max(x, lo), hi), "min": min, "max": max, "sin": math.sin,
                  "cos": math.cos, "between": lambda x, lo, hi: 1.0 if lo <= x <= hi else 0.0}[tok]
            return float(fn(*a))
        if tok == "PI":
            return math.pi
        return self.env[tok]


def option(filter_str: str, name: str) -> str:
    m = re.search(rf"[:=]{name}='([^']*)'", filter_str)
    assert m, (name, filter_str)
    return m.group(1)


def ev(text: str, **env: float) -> float:
    return Expr(text, env).run()


# --------------------------------------------------------------- 1. Python mirrors == ffmpeg


@pytest.mark.parametrize("cy", [0.5, 0.45])
def test_factor_out_matches_the_perspective_expression(cy):
    pulses = [(0.4, 2.1), (2.0, 4.0), (6.0, 6.9)]  # two overlap: the expression adds them up
    zmax, fps, W, H = 1.2, 30, 1080, 768
    f = zoom.perspective_filter(pulses, zmax, fps, cy=cy)
    x0, y0, enable = option(f, "x0"), option(f, "y0"), option(f, "enable")
    for n in range(0, 240):
        t = n / fps
        on = ev(enable, t=t)
        want = zoom.factor_out(t, pulses, zmax)
        if not on:
            assert want == 1.0
            continue
        got_z = (W / 2) / (W / 2 - ev(x0, W=W, H=H, **{"in": n}))
        assert got_z == pytest.approx(want, abs=2e-3), t
        assert ev(y0, W=W, H=H, **{"in": n}) == pytest.approx(H * cy - H * cy / want, abs=0.5)


def test_zoom_never_passes_the_cap():
    assert zoom.factor_out(1.0, [(0.0, 3.0)], 5.0) <= zoom.MAX_ZOOM + 1e-9
    assert "1+0.250*" in zoom.perspective_filter([(0.0, 3.0)], 5.0, 30)


@pytest.mark.parametrize("base", [1.0, 1.12, 1.2])
def test_shake_at_matches_the_shake_expression(base):
    shakes, punches, fps, W, H = [(1.0, 1.8)], [(1.5, 2.4), (5.0, 5.6)], 30, 1080, 1920
    f = fx_mod.shake_filter(shakes, punches, fps, base)
    x0, y0, x1, enable = (option(f, k) for k in ("x0", "y0", "x1", "enable"))
    for n in range(0, 200):
        t = n / fps
        z, dx, dy = fx_mod.shake_at(t, shakes, punches, base, fps)
        if not ev(enable, t=t):
            assert (z, dx, dy) == (1.0, 0.0, 0.0)
            continue
        env = {"W": W, "H": H, "in": n}
        left, right, top = ev(x0, **env), ev(x1, **env), ev(y0, **env)
        assert W / (right - left) == pytest.approx(z, abs=1e-4)  # the filter prints 4 decimals
        assert left == pytest.approx((0.5 - 0.5 / z + dx) * W, abs=0.1)
        assert top == pytest.approx((0.5 - 0.5 / z + dy) * H, abs=0.1)
        assert z * base <= zoom.MAX_ZOOM + 1e-9  # smart zoom x shake never past the cap
        assert left >= -1e-6 and right <= W + 1e-6  # the picture never leaves the frame


def test_split_rects_are_what_the_filter_cuts():
    fc = Facecam(x=0.0, y=0.737, w=0.2667, h=0.263)
    graph = clips._filter_graph("split", 1920, 1080, fc)
    crops = [tuple(int(v) for v in m) for m in re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", graph)]
    cam, game = clips.split_rects(1920, 1080, fc)
    assert crops[0] == (cam[2], cam[3], cam[0], cam[1])
    assert crops[1] == (game[2], game[3], game[0], game[1])
    geo = clips.preview_geometry("auto", 1920, 1080, fc)
    assert geo["layout"] == "split" and geo["cam"][2] == pytest.approx(cam[2] / 1920, abs=1e-6)


# --------------------------------------------------------------- 2. previewMath.ts == Python


def _node_ts() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "-e", "console.log(process.features && process.features.typescript || '')"],
                         capture_output=True, text=True)
    return node if out.stdout.strip() not in ("", "false", "undefined") else None


CASES = {
    "split": [[1920, 1080, {"x": 0.0, "y": 0.737, "w": 0.2667, "h": 0.263}],
              [1920, 1080, {"x": 0.74, "y": 0.0, "w": 0.26, "h": 0.3}],
              [1280, 720, {"x": 0.3, "y": 0.3, "w": 0.4, "h": 0.6}],
              [2560, 1080, {"x": -0.1, "y": 0.9, "w": 0.5, "h": 0.5}],
              [1080, 1920, {"x": 0.05, "y": 0.05, "w": 0.9, "h": 0.2}]],
    "keep": [[10.0, 12.5], [13.0, 20.0]],
    "pulses": [{"t0": 10.4, "t1": 12.9, "target": "scene", "code": ""},
               {"t0": 14.0, "t1": 16.0, "target": "cam", "code": ""},
               {"t0": 15.0, "t1": 17.5, "target": "scene", "code": ""}],
    "shakes": [[1.0, 1.8]], "punches": [[1.5, 2.4], [6.0, 6.6]],
}


def test_preview_math_ts_matches_the_renderer(tmp_path):
    node = _node_ts()
    if not node:
        pytest.skip("needs Node with TypeScript support (22.18+)")
    src = (ROOT / "frontend" / "src" / "previewMath.ts").as_uri()
    script = tmp_path / "run.mjs"
    script.write_text(f"""
const m = await import({json.dumps(src)});
const c = {json.dumps(CASES)};
const out = {{ split: c.split.map(([w, h, f]) => m.splitRects(w, h, f)), zoom: [], shake: [] }};
for (let t = 9.5; t <= 20.5; t += 0.05) {{
  const fx = {{ level: 1.2, pulses: c.pulses, keep: c.keep, loop: false, shakes: [], punches: [], fps: 30 }};
  const z = m.zoomsAt(t, fx);
  out.zoom.push([t, m.toMain(t, c.keep), z.scene, z.cam, z.full]);
}}
for (let n = 0; n < 240; n++) {{
  const s = m.shakeAt(n / 30, c.shakes, c.punches, 1.12, 30);
  out.shake.push([n / 30, s.z, s.dx, s.dy]);
}}
console.log(JSON.stringify(out));
""", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    got = json.loads(res.stdout)

    for (w, h, f), ts in zip(CASES["split"], got["split"]):
        cam, game = clips.split_rects(w, h, Facecam(**f))
        assert ts["cam"] == list(cam) and ts["game"] == list(game), (w, h, f)

    from sharkyclips.edit.plan import EditPlan, merge
    from sharkyclips.edit.zoom import Pulse

    plan = EditPlan(start=10.0, end=20.0, fps=30, keep=[tuple(k) for k in CASES["keep"]],
                    pulses=[Pulse(p["t0"], p["t1"], p["target"]) for p in CASES["pulses"]], zoom_level=1.2)
    ps, pc = plan.out_pulses("scene"), plan.out_pulses("cam")
    for t, tm, scene, cam_z, full in got["zoom"]:
        want_tm = plan.to_out(t)
        assert (tm is None) == (want_tm is None), t
        if want_tm is None:
            assert scene == cam_z == full == 1
            continue
        assert tm == pytest.approx(want_tm, abs=1e-9)
        assert scene == pytest.approx(zoom.factor_out(want_tm, ps, 1.2), abs=1e-9), t
        assert cam_z == pytest.approx(zoom.factor_out(want_tm, pc, 1.2), abs=1e-9), t
        assert full == pytest.approx(zoom.factor_out(want_tm, merge(ps + pc), 1.2), abs=1e-9), t

    for t, z, dx, dy in got["shake"]:
        wz, wdx, wdy = fx_mod.shake_at(t, [tuple(s) for s in CASES["shakes"]], [tuple(p) for p in CASES["punches"]], 1.12, 30)
        assert (z, dx, dy) == pytest.approx((wz, wdx, wdy), abs=1e-9), t


# --------------------------------------------------------------- 3. junk words


def test_endless_words_are_cleaned():
    assert clean_word(" Z" + "z" * 375) == " Zzzz"
    assert clean_word(" �" * 22) == ""
    assert clean_word(" hello") == " hello"
    assert clean_word(" amınaaaaaaa") == " amınaaa"  # still "stretched" for the swear check
    assert len(clean_word(" " + "abcdefghij" * 10).strip()) == 40
    words = [{"start": 1, "end": 2, "word": " ok"}, {"start": 2, "end": 3, "word": " ��"},
             {"start": 3, "end": 4, "word": " Z" + "z" * 300}]
    assert [w["word"] for w in clean_words(words)] == [" ok", " Zzzz"]
    tr = {"segments": [{"start": 0, "end": 4, "text": " ok �� Z" + "z" * 300, "words": words}]}
    clean_transcript(tr)
    assert tr["segments"][0]["text"] == " ok Zzzz"
    assert clean_transcript(json.loads(json.dumps(tr))) == tr  # idempotent
