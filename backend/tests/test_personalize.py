"""1.2.69 Settings > Personalization.

1. frontend/src/themeMath.ts (run with Node): WCAG contrast and the automatic fix (every fixed
   colour reaches AA, keeps its hue side, and a colour that already passes is left alone).
2. The setting is checked on the server (only known keys, #rrggbb colours) and survives a
   round trip through /api/settings; a theme file with junk is refused.
3. The splash page takes the theme's colours, and refuses anything that isn't a plain colour
   (the value is written into a <style> block).
"""

from __future__ import annotations

import json
import subprocess

import pytest

from sharkyclips import config, personal, welcome
from test_multipost import _client
from test_preview_math import ROOT, _node_ts


def test_contrast_maths_and_the_automatic_fix(tmp_path):
    node = _node_ts()
    if not node:
        pytest.skip("needs Node with TypeScript support (22.18+)")
    src = (ROOT / "frontend" / "src" / "themeMath.ts").as_uri()
    script = tmp_path / "run.mjs"
    script.write_text(f"""
const m = await import({json.dumps(src)});
const P = (s) => m.parseColor(s);
const out = {{}};
out.bw = m.contrast(P("#000000"), P("#ffffff"));
out.same = m.contrast(P("#777777"), P("#777777"));
out.rgba = m.parseColor("rgba(255, 210, 63, 0.12)");
out.hex3 = m.parseColor("#fff");
out.bad = [m.parseColor("red"), m.parseColor("#12345"), m.parseColor("rgb(1,2)")];
out.hex6 = [m.isHex6("#a1B2c3"), m.isHex6("#abc"), m.isHex6("#a1b2c3;}}"), m.isHex6("url(x)")];
// pairs that fail: text on its own background, yellow on white, mid grey on mid grey
const cases = [["#777777", "#808080", 4.5], ["#ffd23f", "#ffffff", 4.5], ["#3fd0c9", "#e8efed", 4.5],
               ["#1a1a1a", "#0a1020", 4.5], ["#ff8a7a", "#ffffff", 3], ["#0000ff", "#000000", 4.5]];
out.fixed = cases.map(([fg, bg, need]) => {{
  const f = m.fixContrast(P(fg), P(bg), need);
  const hex = m.toHex(f);
  return [fg, bg, need, hex, m.contrast(P(hex), P(bg))];
}});
out.kept = m.toHex(m.fixContrast(P("#0e1a33"), P("#ffffff")));
out.on = [m.toHex(m.bestOn(P("#ffd23f"))), m.toHex(m.bestOn(P("#0b4f7a")))];
console.log(JSON.stringify(out));
""", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    r = json.loads(res.stdout)
    assert r["bw"] == pytest.approx(21, abs=0.01) and r["same"] == pytest.approx(1)
    assert r["rgba"] == [255, 210, 63, 0.12] and r["hex3"] == [255, 255, 255, 1]
    assert r["bad"] == [None, None, None]
    assert r["hex6"] == [True, False, False, False]
    for fg, bg, need, hexed, ratio in r["fixed"]:
        assert ratio >= need, (fg, bg, hexed, ratio)
    assert r["kept"] == "#0e1a33"  # already readable: untouched
    assert r["on"] == ["#000000", "#ffffff"]


def test_the_setting_is_checked_and_kept():
    good = {"v": 1, "preset": "ocean", "mode": "system", "accent": "#3FD0C9", "titlebar": True, "autofix": True,
            "colors": {"dark": {"bg": "#061423", "text": "#e2eef7", "nope": "#ffffff", "link": "red"},
                       "light": {"button": "#0b4f7a;}body{display:none"}}, "at": 1764160000000}
    c = personal.clean(good)
    assert c["accent"] == "#3fd0c9" and c["colors"] == {"dark": {"bg": "#061423", "text": "#e2eef7"}, "light": {}}
    assert personal.clean({"preset": "neon", "mode": "dark"}) is None
    assert personal.clean({"preset": "classic", "mode": "dusk"}) is None
    assert personal.clean("classic") is None

    client = _client()
    try:
        r = client.put("/api/settings", json={"ui_personal": good})
        assert r.status_code == 200, r.text
        got = client.get("/api/settings").json()["ui_personal"]
        assert got["preset"] == "ocean" and got["mode"] == "system" and got["titlebar"] is True
        assert got["colors"]["dark"] == {"bg": "#061423", "text": "#e2eef7"}
        bad = client.put("/api/settings", json={"ui_personal": {"preset": "x", "mode": "dark"}})
        assert bad.status_code >= 400
        assert client.get("/api/settings").json()["ui_personal"]["preset"] == "ocean"  # unchanged
        assert client.put("/api/settings", json={"ui_personal": None}).status_code == 200
        assert client.get("/api/settings").json()["ui_personal"] is None
    finally:
        config.update(ui_personal=None, ui_splash=None)


def test_the_splash_page_takes_the_theme_colours():
    dark = {k: "#102030" for k in welcome.SPLASH_KEYS}
    light = {k: "rgb(240, 241, 242)" for k in welcome.SPLASH_KEYS}
    try:
        config.update(ui_splash={"dark": dark, "light": light})
        css = welcome.splash_theme_css(config.load())
        assert "--l-bg: #102030;" in css and "--l-bg: rgb(240, 241, 242);" in css
        assert ':root[data-theme="auto"]' in css
        html = welcome.write_splash("http://127.0.0.1:8000/").read_text(encoding="utf-8")
        assert "__THEME_CSS__" not in html and "--l-bg: #102030;" in html
        # anything but a plain colour: the default (Classic) colours instead
        evil = {**dark, "l-bg": "#000; } body { background: url(http://x/) } :root {"}
        config.update(ui_splash={"dark": evil, "light": light})
        css = welcome.splash_theme_css(config.load())
        assert "url(" not in css and "--l-bg: #0a1020;" in css
        # and the settings API drops it without saving
        config.update(ui_splash=None)
        client = _client()
        assert client.put("/api/settings", json={"ui_splash": {"dark": evil, "light": light}}).status_code == 200
        assert config.load().get("ui_splash") is None
    finally:
        config.update(ui_splash=None)


def test_the_sign_in_result_page_uses_the_theme():
    page = welcome.result_page("Instagram is connected. <b>x</b>", True)
    assert "var(--l-bg)" in page and "--l-bg: #0a1020;" in page  # Classic until the UI sends its colours
    assert "&lt;b&gt;x&lt;/b&gt;" in page and "<b>x</b>" not in page
