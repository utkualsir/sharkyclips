"""1.2.72 Photo slideshow: photo order (date / drag), EXIF rotation, every shape and odd size fitted
without stretching, HEIC / PNG / WebP, 2 and 20 photos, the duration math, Ken Burns limits, labels
in every language inside the safe zone, the logo outro, the render (1080x1920 H.264 + silent AAC)
and the editor API down to the normal Share flow."""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from sharkyclips import config, slideshow as S
from test_multipost import _client
from test_publishing import _idle, _wait, cfg  # noqa: F401 - fixture

ROOT = Path(__file__).resolve().parents[2]
FF = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FF is None, reason="ffmpeg not installed")


def _jpeg(w: int, h: int, color=(180, 120, 80), *, orient: int | None = None, date: str | None = None,
          split: bool = False, fmt: str = "JPEG") -> bytes:
    img = Image.new("RGB", (w, h), color)
    if split:  # left half red, right half blue: shows which way up a photo was turned
        ImageDraw.Draw(img).rectangle([w // 2, 0, w, h], fill=(0, 0, 255))
        ImageDraw.Draw(img).rectangle([0, 0, w // 2 - 1, h], fill=(255, 0, 0))
    buf = io.BytesIO()
    if fmt == "JPEG":
        exif = Image.Exif()
        if orient:
            exif[274] = orient
        if date:
            exif.get_ifd(0x8769)[36867] = date
        img.save(buf, "JPEG", quality=92, exif=exif.tobytes())
    else:
        img.save(buf, fmt)
    return buf.getvalue()


@pytest.fixture
def show():
    p = S.create("Test slideshow")
    yield p
    shutil.rmtree(p.dir, ignore_errors=True)  # under the throwaway test workspace (conftest checks)


def _probe(path: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,profile,width,height,pix_fmt,r_frame_rate,sample_rate,channels"
                          ":format=duration", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# ===================================================================== order


def test_order_by_photo_date_then_upload_order(show):
    S.add_photo(show, "c.jpg", _jpeg(40, 30, date="2026:03:03 10:00:00"))
    S.add_photo(show, "nodate1.png", _jpeg(40, 30, fmt="PNG"))
    S.add_photo(show, "a.jpg", _jpeg(40, 30, date="2026:03:01 08:00:00"))
    S.add_photo(show, "nodate2.webp", _jpeg(40, 30, fmt="WEBP"))
    S.add_photo(show, "b.jpg", _jpeg(40, 30), modified_ms=datetime(2026, 3, 2, 12).timestamp() * 1000)
    names = [p["name"] for p in S.active(S.load(show))]
    # EXIF date, else the file's date; no date at all keeps the upload order, at the end
    assert names == ["a.jpg", "b.jpg", "c.jpg", "nodate1.png", "nodate2.webp"]
    data = S.load(show)
    sources = {p["name"]: p["date_source"] for p in S.active(data)}
    assert sources["a.jpg"] == "exif" and sources["b.jpg"] == "file" and sources["nodate1.png"] is None


def test_drag_order_keeps_every_photo_and_date_sort_comes_back(show):
    for i in range(4):
        S.add_photo(show, f"p{i}.jpg", _jpeg(40, 30, date=f"2026:01:0{i + 1} 10:00:00"))
    data = S.load(show)
    ids = [p["id"] for p in S.active(data)]
    # a stale browser: one id missing, one unknown -> nothing is lost, the missing one goes last
    S.apply_order(data, [ids[3], "nope", ids[1], ids[0]])
    assert [p["id"] for p in S.active(data)] == [ids[3], ids[1], ids[0], ids[2]] and data["order_mode"] == "manual"
    S.save(show, data)
    S.add_photo(show, "late.jpg", _jpeg(40, 30, date="2020:01:01 10:00:00"))  # manual order: added at the end
    assert S.active(S.load(show))[-1]["name"] == "late.jpg"
    data = S.sort_by_date(S.load(show))
    assert [p["name"] for p in S.active(data)][0] == "late.jpg" and data["order_mode"] == "date"


def test_remove_is_undoable_and_the_limit_counts_only_photos_in_the_video(show):
    ids = [S.add_photo(show, f"p{i}.jpg", _jpeg(20, 20))["id"] for i in range(S.MAX_PHOTOS)]
    with pytest.raises(Exception, match="at most 20"):
        S.add_photo(show, "x.jpg", _jpeg(20, 20))
    S.remove_photo(show, ids[0])
    assert len(S.active(S.load(show))) == 19 and (S.photos_dir(show) / S.load(show)["photos"][0]["file"]).is_file()
    S.add_photo(show, "x.jpg", _jpeg(20, 20))
    with pytest.raises(Exception, match="at most 20"):  # Undo can't go over the limit either
        S.remove_photo(show, ids[0], removed=False)


def test_bad_files_are_refused_clearly(show):
    with pytest.raises(Exception, match="supported photo type"):
        S.add_photo(show, "clip.mp4", b"12345")
    with pytest.raises(Exception, match="isn't a photo"):
        S.add_photo(show, "broken.jpg", b"not really a jpeg")
    with pytest.raises(Exception, match="empty"):
        S.add_photo(show, "empty.jpg", b"")
    assert not list(S.photos_dir(show).glob("*.part"))  # nothing half-stored is left
    assert S.active(S.load(show)) == []


# ===================================================================== picture


def test_exif_rotation_is_fixed(show):
    # stored landscape, orientation 6 = shown turned 90 degrees clockwise (a phone held upright)
    photo = S.add_photo(show, "phone.jpg", _jpeg(400, 200, orient=6, split=True))
    assert (photo["width"], photo["height"]) == (200, 400)
    frame = S.compose(S.photos_dir(show) / photo["file"], 270, 480)
    top, bottom = frame.getpixel((135, 150)), frame.getpixel((135, 330))
    assert top[0] > 200 and top[2] < 60, top  # the red left half is on top now
    assert bottom[2] > 200 and bottom[0] < 60, bottom


@pytest.mark.parametrize("size", [(1080, 1920), (1920, 1080), (1000, 1000), (3000, 4000), (1, 1), (7, 5000),
                                  (5000, 7), (37, 23), (1081, 1919), (4032, 3024)])
def test_every_shape_fits_without_stretching(show, size):
    w, h = size
    photo = S.add_photo(show, f"p{w}x{h}.png", _jpeg(w, h, color=(250, 20, 20), fmt="PNG"))
    fw, fh = S.fit_size(w, h, S.W, S.H)
    assert fw <= S.W and fh <= S.H and (fw == S.W or fh == S.H)  # as big as fits
    if min(w, h) > 10:  # same shape (rounding to whole pixels only)
        assert abs(fw / fh - w / h) / (w / h) < 0.02
    frame = S.compose(S.photos_dir(show) / photo["file"], 360, 640)
    assert frame.size == (360, 640) and frame.mode == "RGB"
    pw, ph = S.fit_size(w, h, 360, 640)
    c = frame.getpixel(((360 - pw) // 2 + pw // 2, (640 - ph) // 2 + ph // 2))
    assert c[0] > 200 and c[1] < 80, c  # the photo itself is in the middle
    if h * 360 / w < 400 and min(w, h) > 10:  # wide photo: blurred, darker fill above it, not black bars
        top = frame.getpixel((180, 10))
        assert 20 < top[0] < 200 and top != (0, 0, 0)


def test_heic_photos_open(show):
    """An iPhone-style HEIC (tests/data, made once with pillow-heif): read, dated, turned once."""
    if not S._heif():
        pytest.skip("no HEIC decoder installed (pi-heif)")
    data = (Path(__file__).parent / "data" / "slideshow-tiny.heic").read_bytes()
    photo = S.add_photo(show, "IMG_0001.HEIC", data)
    # stored 300 x 200 with "rotate 90": shown upright as 200 x 300, the red left half on top
    assert (photo["width"], photo["height"]) == (200, 300) and photo["file"].endswith(".heic")
    assert photo["taken_at"] == "2026-04-05T06:07:08" and photo["date_source"] == "exif"
    assert (S.photos_dir(show) / f"{photo['id']}.thumb.jpg").is_file()
    frame = S.compose(S.photos_dir(show) / photo["file"], 180, 320)
    top, bottom = frame.getpixel((90, 110)), frame.getpixel((90, 210))
    assert top[0] > 180 and top[1] < 90, top
    assert bottom[1] > 150 and bottom[0] < 90, bottom


# ===================================================================== timing, zoom, text


@pytest.mark.parametrize("n", [2, 3, 10, 20])
@pytest.mark.parametrize("seconds", [2.0, 2.5, 3.0, 5.0])
@pytest.mark.parametrize("outro", [True, False])
def test_duration_math(n, seconds, outro):
    tl = S.timeline(n, seconds, outro)
    assert tl["total"] == pytest.approx(n * seconds + (S.OUTRO_S if outro else 0))
    assert tl["xfade"] <= seconds / 3 and tl["xfade"] == pytest.approx(min(S.XFADE_S, seconds / 3), abs=1e-3)
    for k, seg in enumerate(tl["segments"]):
        assert seg["start"] == pytest.approx(k * seconds)
        # a photo's stream lasts until the next one has fully come in
        if k < n - 1:
            assert seg["start"] + seg["length"] == pytest.approx((k + 1) * seconds + tl["xfade"])
    last = tl["segments"][-1]
    assert last["length"] == pytest.approx(seconds + (S.OUTRO_XFADE_S if outro else 0))
    # every photo is on its own (no transition) for most of its time
    assert seconds - tl["xfade"] >= seconds * 2 / 3 - 1e-9


def test_seconds_are_clamped_to_the_slider():
    assert S.clean_seconds(1) == 2.0 and S.clean_seconds(9) == 5.0 and S.clean_seconds("3.3") == 3.5
    assert S.clean_seconds(None) == 3.0 and S.clean_seconds(float("nan")) == 3.0
    assert S.duration(10, 3.0, True) == 31.5  # the typical one: 10 photos, 3 s, outro


def test_ken_burns_never_cuts_the_middle_of_a_photo():
    for k in range(4):
        for i in range(101):
            z = S.zoom_at(k, i / 100)
            assert 1.0 <= z <= S.ZOOM_MAX + 1e-9
            assert S.kept_fraction(z) >= 0.94  # at most 3 % of each edge leaves the picture
    assert S.zoom_at(0, 0) == 1.0 and S.zoom_at(1, 0) == pytest.approx(S.ZOOM_MAX)  # in, then out


def test_labels_in_every_language():
    from sharkyclips import languages

    assert set(S.LABELS) == set(S.WORDS) == set(languages.LANGUAGES)
    for lang, (b, p, r) in S.LABELS.items():
        assert S.label_texts(2, lang) == [b, r]
        assert S.label_texts(5, lang) == [b, p, p, p, r]
        assert all(x.strip() for x in (b, p, r))
    assert S.upper("Önce", "tr") == "ÖNCE" and S.upper("sonuç iş", "tr") == "SONUÇ İŞ"
    assert S.upper("قبل", "ar") == "قبل"


def test_own_text_wins_and_is_cleaned(show):
    for i in range(3):
        S.add_photo(show, f"p{i}.jpg", _jpeg(30, 30, date=f"2026:01:0{i + 1} 10:00:00"))
    data = S.load(show)
    data["labels"] = True
    S.active(data)[1]["text"] = r"day 3 {\b1}\N" + "x" * 80
    assert S.texts(data, "en") == ["BEFORE", "DAY 3 B1 N" + "X" * (S.TEXT_MAX - 10), "RESULT"]
    data["labels"] = False
    assert S.texts(data, "en")[0] == "" and S.texts(data, "en")[2] == ""


def test_text_stays_in_the_safe_zone():
    for w, h in ((S.W, S.H), (S.W // S.PREVIEW_SCALE, S.H // S.PREVIEW_SCALE)):
        b = S.text_box(w, h)
        k = w / S.W
        assert b["left"] >= S.SAFE["left"] * k - 1 and b["right"] <= w - S.SAFE["right"] * k + 1
        assert b["y"] >= S.SAFE["top"] * k and b["y"] + b["size"] * 1.6 < h - S.SAFE["bottom"] * k
    ass = S.labels_ass(["BEFORE", "", "A VERY LONG LABEL TEXT HERE 123"], S.timeline(3, 3.0, True), S.W, S.H, "en")
    assert ass.count("Dialogue:") == 2 and "Archivo SC" in ass and r"\fad(" in ass
    sizes = [int(x.split("\\fs")[1].split("\\")[0]) for x in ass.splitlines() if x.startswith("Dialogue")]
    assert sizes[1] < sizes[0]  # a long text gets smaller so it fits the safe width


def test_fonts_ship_with_the_app():
    from PIL import ImageFont

    assert S.FONT_FILE.is_file() and (S.FONT_FILE.parent / "OFL-archivo.txt").is_file()
    f = ImageFont.truetype(str(S.FONT_FILE), 40)
    assert f.getname()[0] == S.FONT_NAME
    assert S.font_for("tr") == S.FONT_NAME and S.font_for("ar") != S.FONT_NAME and S.font_for("zh") != S.FONT_NAME


# ===================================================================== outro


def test_outro_uses_the_logo_geometry_of_the_app():
    spec = importlib.util.spec_from_file_location("make_icons", ROOT / "installer" / "make_icons.py")
    mi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mi)
    assert (S.FIN, S.PLAY, S.WAVE, S.WAVE_Y, S.WAVE_W) == (mi.FIN, mi.PLAY, mi.WAVE, mi.WAVE_Y, mi.WAVE_W)
    assert (S.TILE_R, S.EDGE_W, S.GLYPH) == (mi.TILE_R, mi.EDGE_W, mi.GLYPH)
    assert (S.NAVY, S.TILE_DARK, S.EDGE_DARK, S.WHITE, S.BLUE, S.GOLD) == (
        mi.NAVY, mi.TILE_DARK, mi.EDGE_DARK, mi.WHITE, mi.BLUE, mi.GOLD)


def test_outro_animates_and_ends_on_a_clean_logo(tmp_path):
    first = S.outro_frame(0.0, 216, 384)
    last = S.outro_frame(S.OUTRO_S - 1 / S.FPS, 216, 384)
    mid = S.outro_frame(0.5, 216, 384)

    def white(img) -> int:  # the fin and the wordmark (the background is navy)
        px = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
        return sum(1 for r, g, b in px if r > 235 and g > 235 and b > 235)

    assert white(first) == 0 and white(last) > 1000 and 0 < white(mid)  # it moves, the logo lands
    assert first.getpixel((5, 5)) == last.getpixel((5, 5))  # same deep-water background
    n = S.write_outro(tmp_path / "o", 108, 192)
    assert n == round(S.OUTRO_S * S.FPS) == len(list((tmp_path / "o").glob("o*.png")))


# ===================================================================== render


@needs_ffmpeg
def test_render_two_photos_full_size_for_reels_and_shorts(show, monkeypatch):
    from sharkyclips import render as R

    S.add_photo(show, "before.jpg", _jpeg(1600, 1200, date="2026:01:01 10:00:00"))
    S.add_photo(show, "after.jpg", _jpeg(1200, 1600, orient=6, date="2026:01:09 10:00:00"))
    data = S.load(show)
    data["labels"] = True
    S.save(show, data)
    monkeypatch.setattr(R, "pick_encoder", lambda: (R.ENCODERS["libx264"], []))  # same on every CI runner
    res = S.render(show, show.dir / "clips" / "slideshow.mp4")
    info = _probe(show.dir / "clips" / "slideshow.mp4")
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (v["codec_name"], v["width"], v["height"], v["pix_fmt"], v["r_frame_rate"]) == ("h264", 1080, 1920, "yuv420p", "30/1")
    assert v["profile"] == "High" and a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000
    assert float(info["format"]["duration"]) == pytest.approx(2 * 3.0 + S.OUTRO_S, abs=0.08)
    assert res["duration"] == 2 * 3.0 + S.OUTRO_S
    head = (show.dir / "clips" / "slideshow.mp4").read_bytes()[:4096]
    assert head.find(b"moov") != -1 and head.find(b"moov") < max(head.find(b"mdat"), 4096)  # faststart
    assert not list((show.dir / "clips").glob("*.partial*"))


@needs_ffmpeg
def test_render_twenty_photos_preview_has_the_exact_length(show):
    sizes = [(1200, 1600), (1600, 1200), (900, 900), (31, 3000), (3000, 31)]
    for i in range(20):
        w, h = sizes[i % len(sizes)]
        S.add_photo(show, f"p{i:02d}.png", _jpeg(w, h, color=(10 * i, 100, 200 - 9 * i), fmt="PNG"))
    data = S.load(show)
    data.update(seconds=2.0, transition="slide", outro=False)
    S.save(show, data)
    res = S.render(show, show.cache_dir / "prev.mp4", preview=True)
    info = _probe(show.cache_dir / "prev.mp4")
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (360, 640) and res["photos"] == 20
    assert float(info["format"]["duration"]) == pytest.approx(40.0, abs=0.1)


@needs_ffmpeg
@pytest.mark.parametrize("transition", ["crossfade", "zoom"])
def test_transitions_and_outro_render(show, transition):
    for i in range(3):
        S.add_photo(show, f"p{i}.jpg", _jpeg(800, 600, color=(200, 40 * i, 40)))
    data = S.load(show)
    data.update(transition=transition, outro=True, seconds=2.0)
    S.save(show, data)
    S.render(show, show.cache_dir / "t.mp4", preview=True)
    assert float(_probe(show.cache_dir / "t.mp4")["format"]["duration"]) == pytest.approx(6.0 + S.OUTRO_S, abs=0.1)
    # the last frame is the outro (deep water + yellow logo), not a photo
    png = show.cache_dir / "last.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.1", "-i", str(show.cache_dir / "t.mp4"),
                    "-frames:v", "1", str(png)], check=True)
    img = Image.open(png).convert("RGB")
    r, g, b = img.getpixel((5, 5))
    assert r < 40 and g < 60 and b < 70  # deep water corner


def test_too_few_photos_is_a_clear_error(show):
    S.add_photo(show, "one.jpg", _jpeg(40, 30))
    with pytest.raises(Exception, match="at least 2"):
        S.render(show, show.cache_dir / "x.mp4", preview=True)


# ===================================================================== API + Share


def _up(c, pid: str, name: str, body: bytes, modified: float | None = None):
    q = f"?filename={name}" + (f"&modified={modified}" if modified else "")
    return c.put(f"/api/slideshow/{pid}/photos{q}", content=body, headers={"Content-Type": "application/octet-stream"})


@needs_ffmpeg
def test_api_from_photos_to_the_share_board(cfg, monkeypatch):  # noqa: F811
    from sharkyclips import render as R

    monkeypatch.setattr(R, "pick_encoder", lambda: (R.ENCODERS["libx264"], []))
    c = _client()
    v = c.post("/api/slideshow", json={"title": "Kitchen"}).json()
    pid = v["id"]
    assert pid.startswith(S.ID_PREFIX) and "_" not in __import__("sharkyclips.project").project.slugify("x_y z")
    from sharkyclips.project import get_project

    proj = get_project(pid)
    S.save(proj, {**S.load(proj), "language": "en"})  # other tests leave another content language set
    try:
        assert v["ready"] is False and v["settings"]["seconds"] == 3.0 and v["settings"]["outro"] is True
        for i, (w, h) in enumerate([(1200, 1600), (1600, 1200), (1000, 1000)]):
            r = _up(c, pid, f"p{i}.jpg", _jpeg(w, h, date=f"2026:02:0{3 - i} 10:00:00"))
            assert r.status_code == 200, r.text
        assert _up(c, pid, "x.gif", b"GIF89a").status_code == 400
        v = c.get(f"/api/slideshow/{pid}").json()
        assert [p["name"] for p in v["photos"]] == ["p2.jpg", "p1.jpg", "p0.jpg"]  # by date
        assert [p["shape"] for p in v["photos"]] == ["square", "landscape", "portrait"]
        assert v["timeline"]["total"] == 3 * 3.0 + S.OUTRO_S and v["ready"]
        assert c.get(f"/api/slideshow/{pid}/photos/{v['photos'][0]['id']}/thumb").status_code == 200
        ids = [p["id"] for p in v["photos"]]
        v = c.put(f"/api/slideshow/{pid}", json={"order": ids[::-1], "seconds": 2, "transition": "slide",
                                                  "labels": True, "texts": {ids[1]: "Day 3"}}).json()
        assert [p["id"] for p in v["photos"]] == ids[::-1] and v["settings"]["order_mode"] == "manual"
        assert [p["shown_text"] for p in v["photos"]] == ["BEFORE", "DAY 3", "RESULT"]
        v = c.post(f"/api/slideshow/{pid}/photos/{ids[0]}/remove").json()
        assert len(v["photos"]) == 2 and v["removed"][0]["id"] == ids[0]
        v = c.post(f"/api/slideshow/{pid}/photos/{ids[0]}/restore").json()
        assert len(v["photos"]) == 3
        # a stream project's lists don't show slideshows (they have their own)
        assert pid not in [p["id"] for p in c.get("/api/projects").json()]
        assert pid not in [p["id"] for p in c.get("/api/easy/projects").json()]
        assert pid in [r["id"] for r in c.get("/api/slideshow").json()]
        # preview, then export
        assert c.post(f"/api/slideshow/{pid}/preview").status_code == 200
        _wait(_idle, 120)
        v = c.get(f"/api/slideshow/{pid}").json()
        assert v["preview"]["fresh"] and c.get(f"/api/slideshow/{pid}/preview.mp4").status_code == 200
        j = c.post(f"/api/slideshow/{pid}/export").json()
        assert j["kind"] == "slideshow_export" and j["lane"] == "gpu"
        _wait(_idle, 300)
        v = c.get(f"/api/slideshow/{pid}").json()
        assert v["jobs"]["slideshow_export"]["status"] == "done", v["jobs"]
        assert v["export"]["fresh"] and v["export"]["duration"] == pytest.approx(3 * 2.0 + S.OUTRO_S)
        assert c.get(f"/api/slideshow/{pid}/video.mp4").status_code == 200
        # the normal Share board: one clip, the rendered video, nothing shared yet
        b = c.get(f"/api/share/{pid}").json()
        assert [x["id"] for x in b["clips"]] == [S.CID] and b["clips"][0]["video"]["kind"] == "clip"
        assert b["clips"][0]["status"]["kind"] == "not_shared"
        assert b["clips"][0]["duration"] == pytest.approx(7.5)
        assert b["kind"] == "slideshow"
        fr = c.get(f"/api/projects/{pid}/frame.jpg?t=1.0&w=640")  # the card's picture: from the export
        assert fr.status_code == 200 and fr.headers["content-type"] == "image/jpeg"
        # its texts: in the content language, ready for every platform (YouTube Shorts gets #Shorts)
        pv = c.get(f"/api/publish/{pid}/{S.CID}?platforms=youtube,tiktok,reels").json()
        assert pv["drafts"]["youtube"]["title"] and "#" in pv["drafts"]["tiktok"]["caption"]
        assert pv["source"] == "clip" and pv["ready"]
        # the normal share plan works for it (TikTok by hand here: nothing is posted anywhere)
        plan = c.post(f"/api/share/{pid}/plan", json={"clips": [S.CID], "platforms": ["tiktok"]}).json()
        assert [r["clip_id"] for r in plan["rows"]] == [S.CID]
        # never in "Render all accepted" (its clip is the export) or the phone approval list
        assert pid not in [o["project_id"] for o in c.get("/api/queue/accepted").json()]
        # changing a setting makes the export "not up to date" until it's made again
        v = c.put(f"/api/slideshow/{pid}", json={"outro": False}).json()
        assert v["export"]["fresh"] is False and v["timeline"]["total"] == 6.0
        # Save + Open folder: into Downloads/SharkyClips/<title>/ (the test home's)
        s = c.post(f"/api/slideshow/{pid}/save").json()
        folder = Path(s["folder"])
        assert folder.is_dir() and str(folder).startswith(str(config.config_dir()))
        assert sorted(p.suffix for p in folder.iterdir()) == [".mp4", ".txt"]
        assert c.post(f"/api/slideshow/{pid}/open-folder").json()["opened"] is False  # never in tests
    finally:
        _wait(_idle, 120)
        shutil.rmtree(config.workspace_dir() / pid, ignore_errors=True)


def test_api_refuses_unknown_and_non_slideshow_projects(cfg):  # noqa: F811
    from test_publishing import _project

    c = _client()
    assert c.get("/api/slideshow/nope-123").status_code == 404
    assert c.get("/api/slideshow/..%2F..%2Fetc").status_code == 404
    p = _project("pub-ss-stream", 1)
    try:
        assert c.get(f"/api/slideshow/{p.id}").status_code == 404  # a stream project isn't a slideshow
    finally:
        shutil.rmtree(p.dir, ignore_errors=True)


def test_api_photo_limits(cfg):  # noqa: F811
    c = _client()
    pid = c.post("/api/slideshow", json={}).json()["id"]
    try:
        for i in range(S.MAX_PHOTOS):
            assert _up(c, pid, f"p{i}.jpg", _jpeg(16, 16), modified=time.time() * 1000).status_code == 200
        r = _up(c, pid, "p21.jpg", _jpeg(16, 16))
        assert r.status_code == 400 and "20" in r.json()["error"]
    finally:
        _wait(_idle, 120)
        shutil.rmtree(config.workspace_dir() / pid, ignore_errors=True)
