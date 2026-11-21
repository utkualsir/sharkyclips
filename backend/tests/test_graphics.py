"""1.2.58 animated graphics (edit/graphics.py): what shows, when, where, and that the preview and the
renderer agree.

1. Choosing: game events through the game profiles, the kill counter, spoken numbers; one at a time,
   at most 1.5 s, never in the first moment or across a replay / freeze; off / non-gaming = none.
2. Placement: never over the facecam, captions, hook / banner, key action, chat bubbles, the bleep
   badge or the platform buttons, for every layout and platform safe zone.
3. Look: the ASS lines libass draws land where the plan says (pixels), the Light preset uses plain
   fades, previewMath.ts gfxStateAt == graphics.state_at.
4. Nothing else moves: captions and bleeps are identical with graphics on or off.
5. Real event data from League of Legends and Delta Force projects (codes and times only).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from sharkyclips import clips
from sharkyclips.clips import ClipOptions, Facecam, Geometry, OutputSpec
from sharkyclips.edit import graphics as G
from sharkyclips.edit.plan import EditPlan
from sharkyclips.export import PRESETS
from sharkyclips.game import gameprofiles

ROOT = Path(__file__).resolve().parents[1].parent
DATA = Path(__file__).resolve().parent / "data"


@pytest.fixture(autouse=True)
def _not_light(monkeypatch):
    from sharkyclips import perf

    monkeypatch.setattr(perf, "light", lambda m=None: False)


def _plan(start=100.0, end=125.0, words=None, keep=None, lang="en", fps=30):
    return EditPlan(start=start, end=end, fps=fps, keep=keep or [(start, end)], words=words or [], lang=lang)


def _opts(**kw):
    return ClipOptions.from_dict({"graphics": "minimal", **kw})


def _r(code, t, value=None, strength=0.6):
    d = {"code": code, "t": t, "strength": strength}
    if value is not None:
        d["value"] = value
    return d


# ------------------------------------------------------------------ 1. choosing


def test_spoken_numbers():
    def w(*tokens):
        return [{"start": float(i), "end": i + 0.4, "word": t} for i, t in enumerate(tokens)]

    assert G.spoken(w("toplam", "21", "kill", "yaptık"), "tr") == [(1.0, "21 KILL")]
    assert G.spoken(w("üç", "kill", "aldım"), "tr") == [(0.0, "3 KILL")]
    assert G.spoken(w("it", "was", "a", "1v4"), "en") == [(3.0, "1v4")]
    assert G.spoken(w("one", "versus", "four", "clutch"), "en") == [(0.0, "1v4")]
    assert G.spoken(w("1", "v", "3"), "en") == [(0.0, "1v3")]
    assert G.spoken(w("1'e", "4", "kaldım"), "tr") == [(0.0, "1v4")]
    # not a kill count / not a duel
    assert G.spoken(w("21", "people", "1", "kill", "9v9", "100", "kill"), "en") == []


def test_events_counter_and_banner_from_the_profiles():
    kills, events = G.mapping()
    assert {"lol_kill", "df_kill"} <= kills
    assert events["lol_pentakill"]["text"] == "PENTAKILL" and events["val_clutch"]["type"] == "banner"
    cand = {"reasons": [_r("lol_kill", 104.0), _r("lol_kill", 104.5), _r("lol_doublekill", 104.5),
                        _r("lol_kill", 112.0), _r("df_multikill", 118.0, "3"), _r("laughter", 106.0)]}
    gp = G.build(None, cand, _opts(), _plan(), mode="gaming")
    kinds = [(g.kind, g.text) for g in gp.items]
    # the banner wins the double kill moment; the counter shows the later kill; "{n}" filled in
    assert ("banner", "DOUBLE KILL") in kinds and ("banner", "3x KILL") in kinds
    assert ("counter", "3 KILL") in kinds
    assert not any(k == "counter" and abs(g.a - 4.0) < 1 for (k, _t), g in zip(kinds, gp.items))


def test_rules_one_at_a_time_short_and_guarded():
    reasons = [_r("lol_kill", 100.1)] + [_r("val_ace", 100 + t) for t in (2.0, 2.6, 3.1, 6, 9, 12, 15, 18, 21, 23.0)]
    gp = G.build(None, {"reasons": reasons}, _opts(), _plan(), mode="gaming")
    items = gp.items
    assert 1 <= len(items) <= G.MAX_ITEMS
    for a, b in zip(items, items[1:]):
        assert b.a >= a.b + G.MIN_GAP - 1e-9  # never two at once
    for g in items:
        assert g.b - g.a <= G.MAX_S + 1e-9 and g.a >= G.START_GUARD and g.b <= 25.0 - G.END_GUARD + 1e-9
    # graphics off / study or music videos: nothing
    assert G.build(None, {"reasons": reasons}, _opts(graphics="off"), _plan(), mode="gaming") is None
    assert G.build(None, {"reasons": reasons}, _opts(), _plan(), mode="study") is None


def test_never_across_a_replay_or_freeze():
    from sharkyclips.edit.fx import FxPlan, Insert

    plan = _plan()
    plan.fx = FxPlan(inserts=[Insert(8.5, 2.0, "replay", 106.0, 107.0)])
    gp = G.build(None, {"reasons": [_r("val_clutch", 108.0), _r("val_ace", 112.0)]}, _opts(), plan, mode="gaming")
    assert [g.text for g in gp.items] == ["ACE"]  # the clutch banner would straddle the replay at 8.5 s


def test_light_preset_uses_plain_fades(monkeypatch):
    from sharkyclips import perf

    monkeypatch.setattr(perf, "light", lambda m=None: True)
    gp = G.build(None, {"reasons": [_r("val_ace", 110.0)]}, _opts(), _plan(), mode="gaming")
    assert gp.simple
    G.place(gp.items, gp.style, Geometry(), "crop", [])
    lines = G.ass_lines(gp, lambda t: t, 0.0, clips._ass_time)
    # fade in, still, fade out: few lines, no scale / slide
    assert len(lines) < 60 and all("\\fscx100.00" in ln for ln in lines if "\\fscx" in ln)
    states = [G.state_at(gp.items[0].to_dict(), 10.0 + n / 30, "minimal", True, 30) for n in range(45)]
    assert all(s is None or (s["scale"] == 1.0 and s["dy"] == 0.0) for s in states)


# ------------------------------------------------------------------ 2. placement


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


SAFES = {"none": (0, 0, 0, 0), **{k: PRESETS[k].safe for k in ("youtube_shorts", "tiktok", "instagram_reels")}}


@pytest.mark.parametrize("layout", ["split", "fit", "crop"])
@pytest.mark.parametrize("safe", list(SAFES))
@pytest.mark.parametrize("style", ["minimal", "bold"])
def test_placement_keeps_every_zone_free(layout, safe, style):
    spec = OutputSpec(safe=SAFES[safe])
    fc = Facecam(0.0, 0.74, 0.26, 0.26)
    for flags in ({}, {"banner": "CLUTCH TIME"}, {"hook": False, "subtitles": "none"}, {"chat_bubbles": True}):
        opts = ClipOptions.from_dict({"graphics": style, "layout": layout, **flags})
        lay, geo = clips.render_geometry(spec, opts, fc)
        items = [G.Gfx(1.0, 2.4, "banner", "PLAY OF THE GAME", "star"), G.Gfx(3.0, 4.2, "number", "1v4", "target"),
                 G.Gfx(5.0, 6.2, "counter", "1 KILL", "skull", steps=[(0.3, "2 KILL")])]
        bz = {"x": 40, "bottom": 1300, "w": 700, "scale": 1.0} if flags.get("chat_bubbles") else None
        k = max(1080 / 1920, 1920 / 1080)
        fc_rect = None if lay == "split" else (0.0, 0.0, 300.0, 300.0)
        excl = G.exclusions(geo, lay, spec.safe, captions=opts.subtitles != "none", hook=opts.hook,
                            banner=bool(opts.banner), facecam_rect=fc_rect, bubbles_zone=bz)
        G.place(items, style, geo, lay, excl)
        for g in items:
            if g.box is None:
                continue
            b = g.box
            # the whole animated extent: the slide-in (dy up to 28 px) and the pop (scale up to ~1.17)
            grow = G.max_scale(g, style)
            hw, hh = b["w"] * grow / 2, b["h"] * grow / 2
            rect = (b["x"] - hw, b["y"] - hh - 10, b["x"] + hw, b["y"] + hh + 28)
            core = (b["x"] - b["w"] / 2, b["y"] - b["h"] / 2, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
            for e in excl:
                assert not _hit(core, e) and not _hit(rect, e), (layout, safe, style, flags, g.text, b, e)
            assert 0 <= rect[0] and rect[2] <= geo.w and 0 <= rect[1] and rect[3] <= geo.h
        if safe == "none" and not flags:
            assert all(g.box for g in items), (layout, style)  # the usual case: they really show
        del k


def test_split_never_covers_the_facecam_panel_or_the_middle():
    opts = _opts(layout="split")
    lay, geo = clips.render_geometry(OutputSpec(), opts, Facecam(0, 0.7, 0.3, 0.3))
    excl = G.exclusions(geo, lay, (0, 0, 0, 0), captions=True, hook=True, banner=False)
    g = G.Gfx(1, 2.5, "banner", "PENTAKILL", "crown")
    G.place([g], "bold", geo, lay, excl)
    b = g.box
    assert b["y"] - b["h"] / 2 > clips.SPLIT_TOP  # below the camera panel
    mid = (324, clips.SPLIT_TOP + 0.3 * 1152, 756, clips.SPLIT_TOP + 0.7 * 1152)
    assert not _hit((b["x"] - b["w"] / 2, b["y"] - b["h"] / 2, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2), mid)


def test_fit_keeps_the_facecam_inside_the_picture_free():
    opts = _opts(layout="fit")
    fc = Facecam(0.70, 0.0, 0.30, 0.30)  # top right of the game picture
    plan = _plan()
    plan.graphics = G.GfxPlan([G.Gfx(1, 2.4, "banner", "VICTORY ROYALE", "trophy")], "bold", False, 30.0)
    spec = OutputSpec()
    lay, geo = clips.render_geometry(spec, opts, fc)
    [item] = clips.graphics_boxes(plan, opts, spec, geo, lay, fc, 1920, 1080)
    b = item["box"]
    pw, ph = 1080, 1080 * 1080 / 1920
    top = (1920 - ph) / 2
    cam = (0.70 * pw, top, pw, top + 0.30 * ph)
    assert not _hit((b["x"] - b["w"] / 2, b["y"] - b["h"] / 2, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2), cam)


# ------------------------------------------------------------------ 3. look


def _ass_doc(lines):
    head = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "ScaledBorderAndShadow: yes", "",
            "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding", *G.style_lines(), "", "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    return "\n".join(head + lines) + "\n"


@pytest.mark.skipif(shutil.which("ffmpeg") is None and not os.environ.get("SHARKYCLIPS_FFMPEG"), reason="needs ffmpeg")
@pytest.mark.parametrize("style,icon,t", [("minimal", "skull", 1.2), ("bold", "crown", 1.2), ("bold", "flame", 0.62),
                                          ("minimal", "trophy", 0.58)])
def test_libass_draws_where_the_plan_says(style, icon, t):
    """Pill and icon pixels vs the plan (also mid-animation: scaled / sliding)."""
    from sharkyclips.errors import require_tool

    ff = require_tool("ffmpeg")
    g = G.Gfx(0.5, 2.0, "banner", "PENTAKILL", icon)
    G.place([g], style, Geometry(), "crop", [])
    gp = G.GfxPlan([g], style, False, 30.0, {"bg": "#FF0000", "fg": "#00FF00", "ink": "#0000FF"})
    work = Path(tempfile.mkdtemp())
    try:
        (work / "s.ass").write_text(_ass_doc(G.ass_lines(gp, lambda x: x, 0.0, clips._ass_time)), encoding="utf-8")
        n = round(t * 30)  # frame n is drawn with the state at n / 30 (graphics.frame_time)
        t = n / 30
        raw = subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30:d=2.5", "-vf",
                              rf"ass=s.ass,select=eq(n\,{n})", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             cwd=work, capture_output=True, timeout=60).stdout
    finally:
        shutil.rmtree(work, ignore_errors=True)
    img = np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(int)
    st = G.state_at(g.to_dict(), t, style, False, 30.0)
    s, b = st["scale"], g.box
    want = (b["x"] - b["w"] * s / 2, b["y"] + st["dy"] - b["h"] * s / 2, b["x"] + b["w"] * s / 2, b["y"] + st["dy"] + b["h"] * s / 2)
    lit = img.sum(axis=2) > 120 * st["alpha"]
    ys, xs = np.nonzero(lit)
    got = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    assert got == pytest.approx(want, abs=2.5), (st, got, want)
    green = (img[:, :, 1] > 120 * st["alpha"]) & (img[:, :, 0] < 100)
    gy, gx = np.nonzero(green)
    pts = [p for path, tone in G.ICONS[icon] if tone == "fg" for p in G.path_points(path)]
    k = b["icon"] * s / 100
    ix = want[0] + b["icon_x"] * s
    iy = want[1] + (b["h"] * s - b["icon"] * s) / 2
    want_icon = (ix + min(x for x, _ in pts) * k, iy + min(y for _, y in pts) * k,
                 ix + max(x for x, _ in pts) * k, iy + max(y for _, y in pts) * k)
    assert (gx.min(), gy.min(), gx.max() + 1, gy.max() + 1) == pytest.approx(want_icon, abs=2.5)


def _node_ts():
    node = shutil.which("node")
    if not node:
        return None
    out = subprocess.run([node, "-e", "console.log(process.features && process.features.typescript || '')"],
                         capture_output=True, text=True)
    return node if out.stdout.strip() not in ("", "false", "undefined") else None


def test_preview_math_matches_state_at(tmp_path):
    node = _node_ts()
    if not node:
        pytest.skip("needs Node with TypeScript support (22.18+)")
    items = [{"a": 1.0, "b": 2.5, "text": "PENTAKILL", "steps": []},
             {"a": 3.2, "b": 4.6, "text": "1 KILL", "steps": [[0.3, "2 KILL"], [0.55, "3 KILL"]]}]
    src = (ROOT / "frontend" / "src" / "previewMath.ts").as_uri()
    script = tmp_path / "run.mjs"
    script.write_text(f"""
const m = await import({json.dumps(src)});
const items = {json.dumps(items)};
const out = [];
for (const style of ["minimal", "bold"]) for (const simple of [false, true]) for (const fps of [30, 60])
  for (let i = 0; i < items.length; i++) for (let n = 0; n < 6 * fps; n++) {{
    const tm = n / fps + 0.004;
    out.push([style, simple, fps, i, tm, m.gfxStateAt(items[i], tm, style, simple, fps)]);
  }}
out.push(["pill", m.gfxPillPath(300, 92, 46)]);
console.log(JSON.stringify(out));
""", encoding="utf-8")
    res = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    got = json.loads(res.stdout)
    pill = got.pop()
    assert pill[1] == G.to_svg(G.rounded_path(300, 92, 46))
    for style, simple, fps, i, tm, st in got:
        want = G.state_at(items[i], tm, style, simple, fps)
        if want is None:
            assert st is None, (style, simple, fps, i, tm)
            continue
        assert st["text"] == want["text"]
        assert (st["alpha"], st["scale"], st["dy"]) == pytest.approx((want["alpha"], want["scale"], want["dy"]), abs=2e-3)


def test_icons_convert_to_svg():
    for name, layers in G.ICONS.items():
        for path, tone in layers:
            pts = G.path_points(path)
            assert all(-0.01 <= x <= 100.01 and -0.01 <= y <= 100.01 for x, y in pts), name
            d = G.to_svg(path)
            assert d.startswith("M ") and d.endswith(" Z") and tone in ("fg", "bg")


# ------------------------------------------------------------------ 4. nothing else moves


def test_captions_and_bleeps_unchanged_by_graphics():
    words = [{"start": 100.5 + i * 0.5, "end": 100.9 + i * 0.5, "word": w}
             for i, w in enumerate("bu klipte toplam 21 kill yaptık kanka çok iyiydi".split())]
    cand = {"id": "c1", "start": 100.0, "end": 125.0, "reasons": [_r("df_kill", 104.0), _r("df_multikill", 110.0, "2")]}

    def run(style):
        plan = _plan(words=[dict(w) for w in words], lang="tr")
        plan.bleeps = [(1.0, 1.4)]
        plan.graphics = G.build(None, cand, _opts(graphics=style), plan, mode="gaming")
        opts = _opts(graphics=style)
        ass = clips.build_ass(plan.out_words(), plan.out_duration, opts, "crop", "tr", "HOOK", geo=Geometry(),
                              bleep_marks=list(plan.bleeps))
        return plan, ass

    p_off, a_off = run("off")
    p_on, a_on = run("minimal")
    assert p_off.graphics is None and p_on.graphics is not None and len(p_on.graphics.items) >= 2
    assert p_on.out_words() == p_off.out_words() and p_on.bleeps == p_off.bleeps
    assert a_on == a_off  # the graphics are extra lines added by the renderer, captions untouched
    assert any(g.text == "21 KILL" for g in p_on.graphics.items) or any(g.kind == "banner" for g in p_on.graphics.items)


# ------------------------------------------------------------------ 5. profiles + real data


def test_every_game_profile_maps_its_graphics():
    profs = gameprofiles.all_profiles()
    assert len(profs) >= 16
    for gid, p in profs.items():
        assert "graphics" in p and not gameprofiles.validate_graphics(p), gid
        if p.get("engine") == "banners":
            for code in list(p["graphics"]["events"]) + p["graphics"].get("kills", []):
                assert code in p["events"], (gid, code)
    bad = {"id": "x", "name": "X", "aliases": ["x"], "graphics": {"events": {"x_a": {"type": "explode", "text": ""}}}}
    assert gameprofiles.validate(bad)


@pytest.mark.parametrize("game", ["lol", "delta_force"])
def test_real_event_data(game):
    """Clips of real LoL / Delta Force streams (the events SharkyClips read on screen)."""
    rows = [r for r in json.loads((DATA / "gfx_real_events.json").read_text(encoding="utf-8")) if r["game"] == game]
    assert rows
    shown = 0
    for row in rows:
        plan = _plan(row["start"], row["end"])
        gp = G.build(None, {"reasons": row["reasons"]}, _opts(layout="split"), plan, mode="gaming")
        if gp is None:
            continue
        lay, geo = clips.render_geometry(clips.with_safe_zone(OutputSpec(), _opts(safe_zone="shorts")), _opts(layout="split"),
                                         Facecam(0, 0.74, 0.26, 0.26))
        excl = G.exclusions(geo, lay, PRESETS["youtube_shorts"].safe, captions=True, hook=True, banner=False)
        G.place(gp.items, gp.style, geo, lay, excl)
        for a, b in zip(gp.items, gp.items[1:]):
            assert b.a >= a.b
        shown += sum(1 for g in gp.items if g.box)
    assert shown >= 3, shown


def test_easy_mode_switch(tmp_path, monkeypatch):
    from sharkyclips import config, easy

    home = tmp_path / "h"
    (home / "workspace").mkdir(parents=True)
    monkeypatch.setenv("SHARKYCLIPS_HOME", str(home))
    assert easy.fx_options({"fx": True, "gfx": True})["graphics"] == "minimal"  # new projects: on
    assert easy.fx_options({"fx": True})["graphics"] == "off"  # made before 1.2.58: keeps its look
    easy.save_settings({"graphics": False})
    assert easy.settings()["graphics"] is False and easy.fx_options({"fx": True, "gfx": True})["graphics"] == "off"
    easy.save_settings({"graphics": True})
    assert easy.fx_options({"fx": True})["graphics"] == "minimal"  # you flipped it: every project
    assert config.load()["easy_graphics"] is True


# ------------------------------------------------------------------ 6. the game's own HUD (1.2.59)


def test_every_profile_marks_its_hud_areas():
    profs = gameprofiles.all_profiles()
    assert len(profs) >= 16
    for gid, p in profs.items():
        areas = p.get("hud_areas") or {}
        assert areas and not gameprofiles.validate_hud(p), gid
        # the kill feed / score / minimap (or the game's equivalent) is always there
        assert {n.split(".")[0] for n in areas} & {"kill_feed", "kill_text", "score", "minimap"}, gid
        if p["status"] != "verified":  # beta / preview profiles: best guesses, marked as such
            assert all(a.get("guess") is True for a in areas.values()), gid
    bad = {"id": "x", "name": "X", "aliases": ["x"], "hud_areas": {"radar": {"box": [0, 0, 10, 10]}}}
    assert gameprofiles.validate(bad)
    bad["hud_areas"] = {"minimap": {"box": [1900, 0, 300, 300]}}
    assert gameprofiles.validate(bad)
    bad["hud_areas"] = {"minimap": {"box": [0, 0, 1920, 1080]}}  # a whole-screen "HUD" would hide everything
    assert gameprofiles.validate(bad)


def _gfx_items():
    return [G.Gfx(1.0, 2.4, "counter", "1 KILL", "skull", steps=[(0.3, "2 KILL")]),
            G.Gfx(4.0, 5.4, "banner", "3x KILL", "skull"), G.Gfx(7.0, 8.4, "score", "EXTRACTION FAILED", "flag")]


def _extent(g, style):
    b, grow = g["box"], G.max_scale(G.Gfx(0, 1, g["kind"], g["text"], steps=g["steps"]), style)
    hw, hh = b["w"] * grow / 2, b["h"] * grow / 2
    return (b["x"] - hw, b["y"] - hh - 10, b["x"] + hw, b["y"] + hh + 28)


@pytest.mark.parametrize("game", sorted(gameprofiles.all_profiles()))
@pytest.mark.parametrize("layout", ["split", "fit", "crop"])
@pytest.mark.parametrize("style", ["minimal", "bold"])
def test_graphics_never_cover_the_games_hud(game, layout, style):
    hud = gameprofiles.hud_boxes(game)
    fc = Facecam(0.0, 0.74, 0.26, 0.26)
    for safe in ("none", "youtube_shorts"):
        for flags in ({}, {"zoom": "strong"}, {"track": "auto"}):
            spec = OutputSpec(safe=SAFES[safe])
            opts = ClipOptions.from_dict({"graphics": style, "layout": layout, **flags})
            lay, geo = clips.render_geometry(spec, opts, fc)
            plan = _plan(0.0, 20.0)
            plan.graphics = G.GfxPlan(_gfx_items(), style, False, 30.0, hud=hud)
            placed = clips.graphics_boxes(plan, opts, spec, geo, lay, fc, 1920, 1080)
            rects = clips.hud_rects(hud, lay, geo.w, geo.h, 1920, 1080, fc, tracked=flags.get("track") == "auto",
                                    zoomed=False, margin=0)
            for g in placed:
                for r in rects:
                    assert not _hit(_extent(g, style), r), (game, lay, style, safe, flags, g["text"], g["box"], r)


def test_hud_rects_follow_the_layout():
    fc = Facecam(0.0, 0.74, 0.26, 0.26)
    kill_text = [(700 / 1920, 806 / 1080, 1220 / 1920, 900 / 1080)]  # Delta Force's score lines
    [r] = clips.hud_rects(kill_text, "split", 1080, 1920, 1920, 1080, fc, margin=0)
    _cam, (gx, _y, gw, _h) = clips.split_rects(1920, 1080, fc)
    assert r[1] == pytest.approx(clips.SPLIT_TOP + 806 / 1080 * 1152, abs=0.2)
    assert r[0] == pytest.approx(max(0, (700 - gx) / gw * 1080), abs=0.2)
    # fit: inside the picture band in the middle of the 9:16 canvas
    [r] = clips.hud_rects(kill_text, "fit", 1080, 1920, 1920, 1080, None, margin=0)
    assert r[1] == pytest.approx((1920 - 607.5) / 2 + 806 / 1080 * 607.5, abs=0.2)
    # a corner the split crop cuts away is simply gone
    assert clips.hud_rects([(0.0, 0.0, 0.1, 0.1)], "split", 1080, 1920, 1920, 1080, fc) == []
    # tracking crop: the whole height band
    [r] = clips.hud_rects(kill_text, "crop", 1080, 1920, 1920, 1080, fc, tracked=True, margin=0)
    assert (r[0], r[2]) == (0, 1080)


def test_bold_split_keeps_delta_force_kill_text_free():
    """The 1.2.58 known issue: Bold in the split layout sat on Delta Force's own kill text / score lines
    (the bottom of the gameplay panel). Now it moves (a bit smaller) into the free gap above."""
    fc = Facecam(0.0, 0.74, 0.26, 0.26)
    opts = ClipOptions.from_dict({"graphics": "bold", "layout": "split"})
    spec = OutputSpec()
    lay, geo = clips.render_geometry(spec, opts, fc)
    df = gameprofiles.get("delta_force")
    x, y, w, h = df["hud_areas"]["kill_text"]["box"]
    assert x <= 700 and y <= 806 and x + w >= 1220 and y + h >= 900  # the scanner's score-line box is inside
    [kill_text] = clips.hud_rects([(x / 1920, y / 1080, (x + w) / 1920, (y + h) / 1080)], lay, geo.w, geo.h,
                                  1920, 1080, fc, margin=0)
    before = _plan(0.0, 20.0)
    before.graphics = G.GfxPlan(_gfx_items(), "bold", False, 30.0)  # no HUD info (1.2.58)
    old = clips.graphics_boxes(before, opts, spec, geo, lay, fc, 1920, 1080)
    assert any(_hit(_extent(g, "bold"), kill_text) for g in old)  # the bug, as it was
    plan = _plan(0.0, 20.0)
    plan.graphics = G.GfxPlan(_gfx_items(), "bold", False, 30.0, hud=gameprofiles.hud_boxes("delta_force"))
    new = clips.graphics_boxes(plan, opts, spec, geo, lay, fc, 1920, 1080)
    assert len(new) == 3  # still shown
    for g in new:
        assert not _hit(_extent(g, "bold"), kill_text), g["box"]
        assert g["box"]["y"] - g["box"]["h"] / 2 > clips.SPLIT_TOP  # never on the facecam panel
        assert g["box"]["h"] >= 0.7 * G.LOOK["bold"]["h"]  # still clearly "bold"


def test_build_takes_the_hud_from_the_projects_game(tmp_path, monkeypatch):
    from sharkyclips import game as game_mod

    monkeypatch.setattr(game_mod, "resolve", lambda project: {"game": "delta_force"})
    gp = G.build(object(), {"reasons": [_r("df_kill", 105.0)]}, _opts(layout="split"), _plan(), mode="gaming")
    assert gp is not None and gp.hud == gameprofiles.hud_boxes("delta_force") and gp.hud
    monkeypatch.setattr(game_mod, "resolve", lambda project: {"game": None})
    gp2 = G.build(object(), {"reasons": [_r("df_kill", 105.0)]}, _opts(layout="split"), _plan(), mode="gaming")
    assert gp2.hud == [] and gp.fingerprint() != gp2.fingerprint()  # a HUD change re-renders the clip
