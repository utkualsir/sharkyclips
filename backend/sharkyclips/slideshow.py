"""Photo slideshow (1.2.72): 2-20 photos -> one 9:16 1080x1920 MP4 for Reels / Shorts / TikTok.

A slideshow is a small project of kind "slideshow" (workspace/<id>/):

  meta.json        title, kind "slideshow", duration of the last export
  slideshow.json   the photos (order, date, text), seconds per photo, transition, labels, outro
  photos/          the uploaded copies (<pid>.<ext>) + a small thumbnail each (<pid>.thumb.jpg);
                   a removed photo stays in the folder (Undo), the whole project goes to the trash
  clips/           the exported MP4 (one "clip", c01: the normal Share flow posts it)
  highlights.json  that one clip as a candidate (its title / description / hashtags)

The picture:
  * every photo is turned the right way up (EXIF orientation) and fitted into the 9:16 frame
    WITHOUT stretching; the empty room is filled with a blurred, darker copy of the same photo
  * a gentle Ken Burns zoom (in / out, alternating) of at most ZOOM_MAX: at most 3 % of each edge
    leaves the picture, the middle 94 % of every photo always stays in (never cuts what matters)
  * photo k starts at k * seconds and is followed by a transition of XFADE_S (crossfade, slide or
    zoom), so the video is exactly  photos * seconds  long, + OUTRO_S with the logo outro
  * an optional short text per photo (e.g. "BEFORE", "DAY 3", "RESULT") in the app's own font,
    inside the Shorts / Reels safe zone (their buttons, caption and title cover the edges)
  * the animated SharkyClips logo outro (OUTRO_S, on by default)
  * a silent AAC track (Instagram and some players want an audio track; the music is added in
    the Instagram / YouTube app)

The preview is the same render at a third of the size (fast, CPU), so it shows exactly what the
export makes. The export uses the best working encoder (NVENC / QSV / AMF / VideoToolbox) and
falls back to x264 on the CPU (a slow PC uses the faster x264 preset).
"""

from __future__ import annotations

import hashlib
import math
import re
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import config
from .errors import SharkyClipsError, require_tool
from .project import Project, read_json, replace_retry, slugify, write_json_atomic

W, H, FPS = 1080, 1920, 30
PREVIEW_SCALE = 3  # preview = 360 x 640
MIN_PHOTOS, MAX_PHOTOS = 2, 20
SECONDS_DEFAULT, SECONDS_MIN, SECONDS_MAX = 3.0, 2.0, 5.0
TRANSITIONS = {"crossfade": "fade", "slide": "slideleft", "zoom": "zoomin"}  # ours -> ffmpeg xfade
XFADE_S = 0.6
OUTRO_S = 1.5
OUTRO_XFADE_S = 0.4
ZOOM_MAX = 1.06  # 1 - 1/1.06 = 5.7 % of a side -> at most 2.8 % off each edge
TEXT_MAX = 32
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_PHOTO_BYTES = 60 * 1024 * 1024
MAX_PIXELS = 120_000_000  # a 108 MP phone photo still opens; a "decompression bomb" doesn't
THUMB = 360
CID = "c01"
ID_PREFIX = "slideshow_"  # the UI routes these ids to the slideshow editor (router.ts)
VERSION = 1

# Shorts / Reels / TikTok cover these parts of a 1080 x 1920 video with their own buttons, the
# caption and the title: the text stays inside (left, top, right, bottom margins).
SAFE = {"left": 70, "top": 250, "right": 170, "bottom": 520}

FONT_FILE = Path(__file__).resolve().parent / "assets" / "fonts" / "ArchivoSC-ExtraBold.ttf"
FONT_NAME = "Archivo SC"  # Archivo (the UI font, OFL) as a static ExtraBold TTF: libass can't read WOFF2

# Logo colours and geometry: the same shapes as installer/make_icons.py (test_slideshow checks it).
# 1.2.74: the Classic look (navy rounded tile, white fin, blue water line, gold accent).
NAVY = "#0A1020"
TILE_DARK = "#0E1A33"
EDGE_DARK = "#2B3E66"
WHITE = "#FFFFFF"
BLUE = "#5B9BFF"
GOLD = "#D9B56A"
TILE_R = 17.0
EDGE_W = 1.6
GLYPH = 20 / 30 * 64 / 52
FIN = [("M", (13.0, 44.0)), ("C", (17.5, 33.0), (28.0, 18.0), (48.5, 11.5)),
       ("C", (42.0, 20.0), (39.5, 32.0), (46.5, 44.0)), ("Z",)]
PLAY = [(25.5, 30.0), (25.5, 40.5), (35.0, 35.25)]
WAVE_Y, WAVE_W = 50.0, 3.4
WAVE = [(8.0, WAVE_Y), (20.0, WAVE_Y), (32.0, WAVE_Y), (44.0, WAVE_Y), (56.0, WAVE_Y)]

# "Before / Progress / Result" in every language of the app (ALL CAPS where the script has them).
LABELS: dict[str, tuple[str, str, str]] = {
    "en": ("Before", "Progress", "Result"),
    "tr": ("Önce", "Süreç", "Sonuç"),
    "es": ("Antes", "Proceso", "Resultado"),
    "pt": ("Antes", "Processo", "Resultado"),
    "de": ("Vorher", "Fortschritt", "Ergebnis"),
    "fr": ("Avant", "En cours", "Résultat"),
    "hu": ("Előtte", "Folyamat", "Eredmény"),
    "ru": ("До", "Процесс", "Результат"),
    "ar": ("قبل", "أثناء العمل", "النتيجة"),
    "zh": ("之前", "进行中", "完成"),
    "ja": ("ビフォー", "作業中", "アフター"),
}
# Title / description words when the user typed no subject (My style finishes the title).
WORDS: dict[str, dict[str, str]] = {
    "en": {"subject": "Before and after", "photos": "{n} photos, from start to finish.",
           "tags": "#beforeandafter #transformation #progress"},
    "tr": {"subject": "Öncesi ve sonrası", "photos": "{n} fotoğrafla baştan sona.",
           "tags": "#öncesisonrası #dönüşüm #süreç"},
    "es": {"subject": "Antes y después", "photos": "{n} fotos, de principio a fin.",
           "tags": "#antesydespues #transformacion #proceso"},
    "pt": {"subject": "Antes e depois", "photos": "{n} fotos, do começo ao fim.",
           "tags": "#antesedepois #transformacao #processo"},
    "de": {"subject": "Vorher und nachher", "photos": "{n} Fotos, vom Anfang bis zum Ende.",
           "tags": "#vorhernachher #verwandlung #fortschritt"},
    "fr": {"subject": "Avant et après", "photos": "{n} photos, du début à la fin.",
           "tags": "#avantapres #transformation #progression"},
    "hu": {"subject": "Előtte és utána", "photos": "{n} fotó, az elejétől a végéig.",
           "tags": "#előtteutána #átalakulás #folyamat"},
    "ru": {"subject": "До и после", "photos": "{n} фото, от начала до конца.",
           "tags": "#доипосле #преображение #процесс"},
    "ar": {"subject": "قبل وبعد", "photos": "{n} صور من البداية إلى النهاية.",
           "tags": "#قبل_وبعد #تحول #مراحل_العمل"},
    "zh": {"subject": "前后对比", "photos": "{n} 张照片，从开始到完成。",
           "tags": "#前后对比 #改造 #过程"},
    "ja": {"subject": "ビフォーアフター", "photos": "{n}枚の写真で最初から最後まで。",
           "tags": "#ビフォーアフター #リフォーム #作業記録"},
}
NO_CAPS = ("ar", "zh", "ja")


# ===================================================================== settings + photos


def is_slideshow(project: Project) -> bool:
    try:
        return project.load_meta().get("kind") == "slideshow"
    except Exception:  # noqa: BLE001
        return False


def path_of(project: Project) -> Path:
    return project.dir / "slideshow.json"


def photos_dir(project: Project) -> Path:
    return project.dir / "photos"


def defaults() -> dict:
    return {"version": VERSION, "photos": [], "order_mode": "date", "seconds": SECONDS_DEFAULT,
            "transition": "crossfade", "labels": False, "outro": True, "subject": "", "language": None}


def clean_seconds(v) -> float:
    try:
        s = float(v)
    except (TypeError, ValueError):
        return SECONDS_DEFAULT
    if not math.isfinite(s):
        return SECONDS_DEFAULT
    return round(min(SECONDS_MAX, max(SECONDS_MIN, s)) * 2) / 2  # 0.5 s steps


def clean_text(v) -> str:
    text = re.sub(r"[\x00-\x1f\x7f{}\\]", " ", str(v or ""))  # no ASS override / line codes
    return " ".join(text.split())[:TEXT_MAX]


def load(project: Project) -> dict:
    p = path_of(project)
    data = {**defaults(), **(read_json(p) if p.is_file() else {})}
    data["seconds"] = clean_seconds(data.get("seconds"))
    if data.get("transition") not in TRANSITIONS:
        data["transition"] = "crossfade"
    data["photos"] = [x for x in data.get("photos") or [] if isinstance(x, dict) and x.get("id")]
    return data


def save(project: Project, data: dict) -> dict:
    write_json_atomic(path_of(project), data)
    return data


def active(data: dict) -> list[dict]:
    """The photos in the video, in order (removed ones are kept for Undo, but not shown)."""
    return [p for p in data["photos"] if not p.get("removed")]


def sort_key(p: dict) -> tuple:
    """Photo date first (EXIF, else the file's date); photos without a date keep the upload order."""
    return (0, p["taken_at"], p.get("seq", 0)) if p.get("taken_at") else (1, "", p.get("seq", 0))


def by_date(photos: list[dict]) -> list[dict]:
    return sorted(photos, key=sort_key)


def apply_order(data: dict, order: list[str]) -> dict:
    """A drag-and-drop order (photo ids). Unknown ids are ignored, missing ones keep their place
    at the end, so a stale browser can't lose a photo."""
    pos = {pid: i for i, pid in enumerate(order)}
    live = active(data)
    known = [p for p in live if p["id"] in pos]
    rest = [p for p in live if p["id"] not in pos]
    known.sort(key=lambda p: pos[p["id"]])
    data["photos"] = known + rest + [p for p in data["photos"] if p.get("removed")]
    data["order_mode"] = "manual"
    return data


def sort_by_date(data: dict) -> dict:
    live = by_date(active(data))
    data["photos"] = live + [p for p in data["photos"] if p.get("removed")]
    data["order_mode"] = "date"
    return data


def label_texts(n: int, lang: str) -> list[str]:
    """Before / Progress ... / Result for n photos (2 photos: Before, Result)."""
    before, progress, result = LABELS.get(lang) or LABELS["en"]
    if n <= 0:
        return []
    if n == 1:
        return [before]
    return [before] + [progress] * (n - 2) + [result]


def upper(text: str, lang: str) -> str:
    if lang in NO_CAPS:
        return text
    if lang == "tr":
        text = text.replace("i", "İ").replace("ı", "I")
    return text.upper()


def texts(data: dict, lang: str) -> list[str]:
    """The text on every photo in order: the photo's own text, else its label when Labels is on."""
    live = active(data)
    auto = label_texts(len(live), lang) if data.get("labels") else [""] * len(live)
    return [upper(clean_text(p.get("text")) or auto[i], lang) for i, p in enumerate(live)]


# ===================================================================== timing


def xfade_for(seconds: float) -> float:
    """The transition length: XFADE_S, but never more than a third of a photo's time."""
    return round(min(XFADE_S, seconds / 3.0), 3)


def timeline(n: int, seconds: float, outro: bool) -> dict:
    """Where every photo is in the video. Photo k starts at k * seconds; its stream is `seconds`
    long, + the next transition (it is still visible while the next one comes in)."""
    seconds = clean_seconds(seconds)
    x = xfade_for(seconds)
    segs = []
    for k in range(n):
        last = k == n - 1
        tail = (OUTRO_XFADE_S if outro else 0.0) if last else x
        segs.append({"start": round(k * seconds, 3), "length": round(seconds + tail, 3),
                     "transition_at": None if last and not outro else round((k + 1) * seconds, 3),
                     "transition_s": tail})
    photos_s = n * seconds
    total = photos_s + (OUTRO_S if outro else 0.0)
    return {"seconds": seconds, "xfade": x, "segments": segs, "photos_s": round(photos_s, 3),
            "outro_at": round(photos_s, 3) if outro else None, "total": round(total, 3)}


def duration(n: int, seconds: float, outro: bool) -> float:
    return timeline(n, seconds, outro)["total"]


def zoom_at(k: int, p: float) -> float:
    """Ken Burns zoom of photo k at progress p (0..1): even photos zoom in, odd ones out."""
    p = min(1.0, max(0.0, p))
    return 1.0 + (ZOOM_MAX - 1.0) * (p if k % 2 == 0 else 1.0 - p)


def kept_fraction(z: float) -> float:
    """The share of the frame's width / height still in the picture at zoom z (centred)."""
    return 1.0 / z


# ===================================================================== photos


_HEIF: dict[str, bool] = {}


def _heif() -> bool:
    """HEIC / HEIF (iPhone photos), registered once. pi-heif = pillow-heif's decode-only build
    (LGPL libheif + libde265, no GPL x265 encoder in the installer); pillow-heif works the same.
    The decoder applies the HEIC's own rotation and resets the EXIF flag (never turned twice)."""
    if "ok" not in _HEIF:
        _HEIF["ok"] = False
        for name in ("pi_heif", "pillow_heif"):
            try:
                mod = __import__(name)
                mod.register_heif_opener()
                _HEIF["ok"] = True
                break
            except Exception:  # noqa: BLE001 - not installed yet: HEIC can't be read, everything else can
                continue
    return _HEIF["ok"]


def open_image(path: Path, max_side: int | None = None):
    """The photo the right way up (EXIF orientation), RGB, at most max_side on its long side."""
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    if not _heif() and path.suffix.lower() in (".heic", ".heif"):
        raise SharkyClipsError("HEIC photos need an extra part that isn't installed yet.",
                               "Update SharkyClips (it installs it), or save the photo as JPG.")
    try:
        img = Image.open(path)
        if max_side and img.format == "JPEG":
            img.draft("RGB", (max_side, max_side))  # decode big JPEGs at a smaller size: fast
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
            base = Image.new("RGB", img.size, (255, 255, 255))  # transparent PNG: on white
            img = img.convert("RGBA")
            base.paste(img, (0, 0), img)
            img = base
        else:
            img = img.convert("RGB")
    except Image.DecompressionBombError:
        raise SharkyClipsError("This photo is too big to open.", "Use a photo under 100 megapixels.") from None
    except SharkyClipsError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SharkyClipsError("This photo can't be opened.", f"Use JPG, PNG, HEIC or WebP ({exc}).") from None
    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def _exif_date(img) -> str | None:
    try:
        exif = img.getexif()
        raw = exif.get_ifd(0x8769).get(36867) or exif.get_ifd(0x8769).get(36868) or exif.get(306)
    except Exception:  # noqa: BLE001
        return None
    if not raw:
        return None
    m = re.match(r"(\d{4})[:-](\d{2})[:-](\d{2})[ T](\d{2}):(\d{2}):(\d{2})", str(raw).strip("\x00 "))
    if not m or m.group(1) == "0000":
        return None
    try:
        return datetime(*map(int, m.groups())).isoformat()
    except ValueError:
        return None


def inspect(path: Path) -> dict:
    """Size (the right way up), orientation and the date it was taken."""
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    _heif()
    try:
        with Image.open(path) as img:
            w, h = img.size
            date = _exif_date(img)
            try:
                orient = int(img.getexif().get(274) or 1)
            except Exception:  # noqa: BLE001
                orient = 1
    except Image.DecompressionBombError:
        raise SharkyClipsError("This photo is too big to open.", "Use a photo under 100 megapixels.") from None
    except Exception:  # noqa: BLE001
        if path.name.lower().split(".part")[0].endswith((".heic", ".heif")) and not _heif():
            raise SharkyClipsError("HEIC photos need an extra part that isn't installed yet.",
                                   "Update SharkyClips (it installs it), or save the photo as JPG.") from None
        raise SharkyClipsError("This file isn't a photo SharkyClips can read.", "Use JPG, PNG, HEIC or WebP.") from None
    if orient in (5, 6, 7, 8):
        w, h = h, w
    return {"width": w, "height": h, "orientation": orient, "exif_date": date}


def add_photo(project: Project, name: str, data_bytes: bytes, modified_ms: float | None = None) -> dict:
    """Store one uploaded photo (+ its thumbnail) and put it into the order."""
    suffix = Path(name).suffix.lower()
    if suffix not in EXTS:
        raise SharkyClipsError(f"'{suffix or name}' isn't a supported photo type.", "Use JPG, PNG, HEIC or WebP.")
    if not data_bytes:
        raise SharkyClipsError("This photo file is empty.")
    if len(data_bytes) > MAX_PHOTO_BYTES:
        raise SharkyClipsError("This photo is too big.", "Use a photo under 60 MB.")
    data = load(project)
    if len(active(data)) >= MAX_PHOTOS:
        raise SharkyClipsError(f"A slideshow has at most {MAX_PHOTOS} photos.", "Remove a photo first.")
    pid = uuid.uuid4().hex[:10]
    d = photos_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{pid}{'.jpg' if suffix == '.jpeg' else suffix}"
    part = dest.with_name(dest.name + ".part")
    part.write_bytes(data_bytes)
    try:
        info = inspect(part)
    except SharkyClipsError:
        part.unlink(missing_ok=True)  # our own half-stored upload, never a user file
        raise
    replace_retry(part, dest)
    make_thumb(dest, d / f"{pid}.thumb.jpg")
    taken, source = info["exif_date"], "exif"
    if not taken and modified_ms:
        try:
            taken = datetime.fromtimestamp(float(modified_ms) / 1000.0).replace(microsecond=0).isoformat()
            source = "file"
        except (OverflowError, OSError, ValueError):
            taken = None
    seq = max([p.get("seq", 0) for p in data["photos"]] or [0]) + 1
    photo = {"id": pid, "file": dest.name, "name": Path(name).name[:120], "width": info["width"],
             "height": info["height"], "orientation": info["orientation"], "taken_at": taken,
             "date_source": source if taken else None, "seq": seq, "text": "", "added_at": _now()}
    data["photos"].append(photo)
    if data.get("order_mode") == "date":
        sort_by_date(data)
    save(project, data)
    return photo


def make_thumb(src: Path, dest: Path) -> None:
    img = open_image(src, THUMB * 2)
    img.thumbnail((THUMB, THUMB))
    tmp = dest.with_name(dest.name + ".part")
    img.save(tmp, "JPEG", quality=82)
    replace_retry(tmp, dest)


def remove_photo(project: Project, pid: str, removed: bool = True) -> dict:
    """Take a photo out of the video (kept in the folder, so Undo brings it back)."""
    data = load(project)
    for p in data["photos"]:
        if p["id"] == pid:
            if not removed and p.get("removed") and len(active(data)) >= MAX_PHOTOS:
                raise SharkyClipsError(f"A slideshow has at most {MAX_PHOTOS} photos.")
            if removed:
                p["removed"] = _now()
            else:
                p.pop("removed", None)
            break
    else:
        raise SharkyClipsError("This photo isn't in the slideshow.")
    if not removed and data.get("order_mode") == "date":
        sort_by_date(data)
    return save(project, data)


def compose(path: Path, w: int, h: int):
    """One 9:16 frame: the photo fitted in (never stretched) over a blurred copy of itself."""
    from PIL import Image, ImageEnhance, ImageFilter

    img = open_image(path, max(w, h) * 2)
    iw, ih = img.size
    frame = cover(img, max(8, w // 10), max(8, h // 10))
    frame = frame.filter(ImageFilter.GaussianBlur(max(1.0, w / 400)))
    frame = frame.resize((w, h), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(max(1.0, w / 180)))
    frame = ImageEnhance.Brightness(frame).enhance(0.55)
    fw, fh = fit_size(iw, ih, w, h)
    fg = img.resize((fw, fh), Image.Resampling.LANCZOS)
    x, y = (w - fw) // 2, (h - fh) // 2
    if fw < w - 2 or fh < h - 2:  # a soft shadow lifts the photo off the blurred fill
        sh = Image.new("L", (w, h), 0)
        pad = max(2, w // 90)
        sh.paste(150, (x - pad // 2, y + pad // 2, x + fw + pad // 2, y + fh + pad))
        sh = sh.filter(ImageFilter.GaussianBlur(pad))
        frame.paste((0, 0, 0), (0, 0), sh)
    frame.paste(fg, (x, y))
    return frame


def fit_size(iw: int, ih: int, w: int, h: int) -> tuple[int, int]:
    """The photo's size inside a w x h frame: as big as fits, same shape (no stretching)."""
    s = min(w / iw, h / ih)
    return max(1, min(w, round(iw * s))), max(1, min(h, round(ih * s)))


def cover(img, w: int, h: int):
    """Scaled and centre-cropped to fill w x h (for the blurred background only)."""
    from PIL import Image

    iw, ih = img.size
    s = max(w / iw, h / ih)
    sw, sh = max(w, math.ceil(iw * s)), max(h, math.ceil(ih * s))
    big = img.resize((sw, sh), Image.Resampling.BILINEAR)
    left, top = (sw - w) // 2, (sh - h) // 2
    return big.crop((left, top, left + w, top + h))


# ===================================================================== the outro


def _bezier(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def fin_points() -> list[tuple[float, float]]:
    pts, cur = [], (0.0, 0.0)
    for cmd in FIN:
        if cmd[0] == "M":
            cur = cmd[1]
            pts.append(cur)
        elif cmd[0] == "C":
            pts += _bezier(cur, *cmd[1:])
            cur = cmd[3]
    return pts


def tile_points(inset: float = 0.0, n: int = 10) -> list[tuple[float, float]]:
    """The rounded square tile (make_icons: TILE_R) as a polygon on the 64 grid."""
    r = max(0.5, TILE_R - inset)
    lo, hi = inset, 64.0 - inset
    pts: list[tuple[float, float]] = []
    for cx, cy, a0 in ((hi - r, lo + r, -90), (hi - r, hi - r, 0), (lo + r, hi - r, 90), (lo + r, lo + r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def wave_points() -> list[tuple[float, float]]:
    x0, y = WAVE[0]
    pts = [(x0, y)]
    x, up = x0, True
    while x < WAVE[-1][0] - 0.1:
        c = (x + 3, y - 1.6 if up else y + 1.6)
        end = (x + 6, y)
        for i in range(1, 13):
            t = i / 12
            a, b, e = (1 - t) ** 2, 2 * (1 - t) * t, t ** 2
            pts.append((a * x + b * c[0] + e * end[0], a * y + b * c[1] + e * end[1]))
        x += 6
        up = not up
    return pts


def _rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _seg(t: float, a: float, b: float) -> float:
    return _clamp01((t - a) / (b - a))


def ease_out_cubic(p: float) -> float:
    return 1 - (1 - p) ** 3


def ease_out_back(p: float, s: float = 1.6) -> float:
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def outro_frame(t: float, w: int = W, h: int = H):
    """One frame of the logo outro at t seconds (0 .. OUTRO_S).

    0.05-0.45  the navy tile swings in (scale with a small overshoot, a little turn)
    0.25-0.70  the water line draws itself from left to right
    0.30-0.78  the fin surfaces out of the water
    0.62-0.92  the play triangle opens in the fin (the mark is a shark AND a play button)
    0.72-1.10  a ripple ring spreads; the "SharkyClips" wordmark slides up
    1.10-1.50  hold (a slow breath), so the last frame is a clean logo
    """
    from PIL import Image, ImageChops, ImageDraw, ImageFont

    k = w / W
    bg = _outro_bg(w, h)
    frame = bg.copy()
    tile_px = 380 * k
    cx, cy = w / 2, h * 0.43
    # ---- the tile, drawn 2x for smooth edges in a box around the centre
    box = int(tile_px * 1.9)
    ss = 2
    big = box * ss
    layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    p_tile = _seg(t, 0.05, 0.45)
    breath = 1.0 + 0.018 * _seg(t, 1.1, 1.5)
    scale = (0.55 + 0.45 * ease_out_back(p_tile)) * breath if p_tile > 0 else 0.0
    angle = math.radians(-9.0 * (1 - ease_out_cubic(p_tile)))
    unit = tile_px * ss / 64 * scale
    mid = big / 2

    def tr(pts, dy: float = 0.0, g: float = 1.0):
        """64-grid points -> layer pixels; g = the mark's scale inside the tile (GLYPH)."""
        out = []
        ca, sa = math.cos(angle), math.sin(angle)
        for x, y in pts:
            gx, gy = (x - 32) * g * unit, (y + dy - 32) * g * unit
            out.append((mid + gx * ca - gy * sa, mid + gx * sa + gy * ca))
        return out

    if scale > 0:
        alpha = int(255 * _clamp01(p_tile * 2.2))
        tile_mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(tile_mask).polygon(tr(tile_points()), fill=255)
        inner = Image.new("L", (big, big), 0)
        ImageDraw.Draw(inner).polygon(tr(tile_points(EDGE_W)), fill=255)
        shadow = Image.new("L", (big, big), 0)
        ImageDraw.Draw(shadow).polygon(tr([(x + 1.2, y + 2.2) for x, y in tile_points()]), fill=110)
        layer.paste((0, 0, 0, 255), (0, 0), shadow)
        layer.paste(_rgb(EDGE_DARK) + (255,), (0, 0), tile_mask)
        layer.paste(_rgb(TILE_DARK) + (255,), (0, 0), inner)
        # the fin rises out of the water: clipped at the water line, inside the tile
        rise = ease_out_cubic(_seg(t, 0.30, 0.78))
        if rise > 0:
            fin = Image.new("L", (big, big), 0)
            fd = ImageDraw.Draw(fin)
            fd.polygon(tr(fin_points(), dy=(1 - rise) * 36.0, g=GLYPH), fill=255)
            hole = ease_out_back(_seg(t, 0.62, 0.92), 2.0)
            if hole > 0:
                c0 = (sum(x for x, _ in PLAY) / 3, sum(y for _, y in PLAY) / 3)
                tri = [(c0[0] + (x - c0[0]) * hole, c0[1] + (y - c0[1]) * hole) for x, y in PLAY]
                fd.polygon(tr(tri, dy=(1 - rise) * 36.0, g=GLYPH), fill=0)
            water = Image.new("L", (big, big), 0)
            ImageDraw.Draw(water).polygon(
                tr([(-8, -8), (72, -8), (72, WAVE_Y - 1.0), (-8, WAVE_Y - 1.0)], g=GLYPH), fill=255)
            fin = ImageChops.multiply(ImageChops.multiply(fin, water), inner)
            layer.paste(_rgb(WHITE) + (255,), (0, 0), fin)
        draw_p = ease_out_cubic(_seg(t, 0.25, 0.70))
        if draw_p > 0:
            pts = wave_points()
            upto = max(2, int(len(pts) * draw_p))
            wl = Image.new("L", (big, big), 0)
            wd = ImageDraw.Draw(wl)
            line = tr(pts[:upto], g=GLYPH)
            r = WAVE_W * GLYPH * unit / 2
            for (x0, y0), (x1, y1) in zip(line, line[1:]):
                steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / 2))
                for i in range(steps + 1):
                    x, y = x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps
                    wd.ellipse([x - r, y - r, x + r, y + r], fill=255)
            wl = ImageChops.multiply(wl, inner)
            layer.paste(_rgb(BLUE) + (255,), (0, 0), wl)
        if alpha < 255:
            a = layer.getchannel("A").point(lambda v: v * alpha // 255)
            layer.putalpha(a)
    # ripple ring (behind the tile) as the play opens
    rp = _seg(t, 0.72, 1.12)
    small = layer.resize((box, box), Image.Resampling.LANCZOS)
    if 0 < rp < 1:
        ring = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rad = tile_px * (0.62 + 0.55 * ease_out_cubic(rp))
        width = max(1, int(6 * k * (1 - rp) + 1))
        a = int(170 * (1 - rp))
        rd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=_rgb(GOLD) + (a,), width=width)
        frame.alpha_composite(ring)
    frame.alpha_composite(small, (int(cx - box / 2), int(cy - box / 2)))
    # ---- the wordmark
    wp = ease_out_cubic(_seg(t, 0.72, 1.10))
    if wp > 0:
        size = max(8, int(100 * k))
        font = ImageFont.truetype(str(FONT_FILE), size)
        txt = Image.new("RGBA", (w, int(size * 2.2)), (0, 0, 0, 0))
        td = ImageDraw.Draw(txt)
        a_txt, b_txt = "Sharky", "Clips"
        wa = td.textlength(a_txt, font=font)
        wb = td.textlength(b_txt, font=font)
        x0 = (w - wa - wb) / 2
        td.text((x0, size * 0.3), a_txt, font=font, fill=_rgb(WHITE) + (255,))
        td.text((x0 + wa, size * 0.3), b_txt, font=font, fill=_rgb(WHITE) + (255,))
        up = _seg(t, 0.95, 1.30)
        if up > 0:  # a short gold bar sweeps in under the name
            bw = (wa + wb) * 0.28 * ease_out_cubic(up)
            by = size * 1.55
            td.rectangle([w / 2 - bw / 2, by, w / 2 + bw / 2, by + max(2, 7 * k)], fill=_rgb(GOLD) + (255,))
        if wp < 1:
            txt.putalpha(txt.getchannel("A").point(lambda v: int(v * wp)))
        ty = int(cy + tile_px * 0.5 + 70 * k + (1 - wp) * 46 * k)
        frame.alpha_composite(txt, (0, ty))
    return frame.convert("RGB")


_BG_CACHE: dict[tuple[int, int], object] = {}


def _outro_bg(w: int, h: int):
    """Classic navy with a soft blue glow behind the logo (cached per size)."""
    from PIL import Image, ImageDraw, ImageFilter

    key = (w, h)
    if key not in _BG_CACHE:
        img = Image.new("RGBA", (w, h), _rgb(NAVY) + (255,))
        glow = Image.new("L", (w, h), 0)
        r = w * 0.55
        ImageDraw.Draw(glow).ellipse([w / 2 - r, h * 0.43 - r, w / 2 + r, h * 0.43 + r], fill=60)
        glow = glow.filter(ImageFilter.GaussianBlur(w / 6))
        img.paste((34, 58, 110, 255), (0, 0), glow)
        _BG_CACHE.clear()
        _BG_CACHE[key] = img
    return _BG_CACHE[key]


def write_outro(folder: Path, w: int, h: int, fps: int = FPS) -> int:
    """The outro as numbered PNG frames; returns the frame count."""
    folder.mkdir(parents=True, exist_ok=True)
    n = int(round(OUTRO_S * fps))
    for i in range(n):
        outro_frame(i / fps, w, h).save(folder / f"o{i:03d}.png", compress_level=1)
    return n


# ===================================================================== the text (ASS)


def _ass_time(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    hh, cs = divmod(cs, 360000)
    mm, cs = divmod(cs, 6000)
    ss, cs = divmod(cs, 100)
    return f"{hh}:{mm:02d}:{ss:02d}.{cs:02d}"


def font_for(lang: str) -> str:
    """The app's font for Latin scripts; scripts it has no letters for use a system font
    (libass shapes Arabic and joins it right to left)."""
    import platform

    system = platform.system()
    if lang == "zh":
        return {"Windows": "Microsoft YaHei", "Darwin": "PingFang SC"}.get(system, "Noto Sans CJK SC")
    if lang == "ja":
        return {"Windows": "Yu Gothic", "Darwin": "Hiragino Sans"}.get(system, "Noto Sans CJK JP")
    if lang == "ar":
        return {"Darwin": "Geeza Pro"}.get(system, "Arial")
    if lang == "ru":
        return {"Windows": "Arial", "Darwin": "Helvetica Neue"}.get(system, "DejaVu Sans")
    return FONT_NAME


def text_box(w: int, h: int) -> dict:
    """Where the text goes: centred inside the safe zone, near its top."""
    k = w / W
    left, right = SAFE["left"] * k, w - SAFE["right"] * k
    return {"x": round((left + right) / 2), "y": round(SAFE["top"] * k + 40 * k),
            "left": round(left), "right": round(right), "max_width": round(right - left),
            "size": round(92 * k), "pad": max(1, round(20 * k))}


def labels_ass(words: list[str], tl: dict, w: int, h: int, lang: str) -> str:
    """One label per photo: pops in after its photo settled, fades out into the transition."""
    from .clips import _ass_escape

    box = text_box(w, h)
    font = font_for(lang)
    # ASS colours are &HAABBGGRR: ink text on a sign-yellow box (BorderStyle 3 = opaque box)
    ink = "&H00302A0E"
    sign = "&H003FD2FF"
    lines = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}",
             "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
             "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: L,{font},{box['size']},{ink},{ink},{sign},&H64000000,1,0,0,0,100,100,"
             f"{max(0, round(2 * w / W))},0,3,{box['pad']},0,8,{box['left']},{w - box['right']},{box['y']},1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for k, text in enumerate(words):
        if not text:
            continue
        seg = tl["segments"][k]
        start = seg["start"] + (0.25 if k else 0.15)
        end = seg["start"] + tl["seconds"] + seg["transition_s"] * 0.3
        # long texts get a smaller size so they fit the safe width on one line
        est = len(text) * box["size"] * 0.62
        fs = box["size"] if est <= box["max_width"] - 2 * box["pad"] else \
            max(round(box["size"] * 0.5), int(box["size"] * (box["max_width"] - 2 * box["pad"]) / est))
        pop = r"{\fad(180,220)\fs%d\fscx88\fscy88\t(0,240,\fscx100\fscy100)\pos(%d,%d)}" % (fs, box["x"], box["y"])
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},L,,0,0,0,,{pop}{_ass_escape(text)}")
    return "\n".join(lines) + "\n"


# ===================================================================== render


def fingerprint(data: dict, lang: str, w: int) -> str:
    live = active(data)
    parts = [VERSION, w, data["seconds"], data["transition"], bool(data.get("outro")), texts(data, lang), lang,
             [(p["id"], p["file"]) for p in live]]
    return hashlib.sha1(repr(parts).encode()).hexdigest()[:12]


def _perspective(k: int, frames: int) -> str:
    """Ken Burns as a sub-pixel zoom (perspective: smooth, no 1-pixel steps like zoompan)."""
    n = max(1, frames - 1)
    p = f"min(on/{n}\\,1)"
    z = f"(1+{ZOOM_MAX - 1:.4f}*{p})" if k % 2 == 0 else f"({ZOOM_MAX:.4f}-{ZOOM_MAX - 1:.4f}*{p})"
    m = f"(1-1/{z})/2"
    lo_x, hi_x = f"W*{m}", f"W*(1-{m})"
    lo_y, hi_y = f"H*{m}", f"H*(1-{m})"
    return (f"perspective=x0={lo_x}:y0={lo_y}:x1={hi_x}:y1={lo_y}:x2={lo_x}:y2={hi_y}:"
            f"x3={hi_x}:y3={hi_y}:interpolation=linear:eval=frame")


def build_graph(n: int, tl: dict, transition: str, outro: bool, has_text: bool, w: int, h: int) -> str:
    """The ffmpeg filter graph: n photo streams (+ the outro frames) joined with transitions."""
    parts = []
    for k in range(n):
        frames = int(round(tl["segments"][k]["length"] * FPS))
        parts.append(f"[{k}:v]fps={FPS},scale={w}:{h}:out_range=tv,setsar=1,format=yuv420p,{_perspective(k, frames)},"
                     f"trim=end_frame={frames},settb=AVTB,setpts=PTS-STARTPTS[p{k}]")
    last = "p0"
    xf = TRANSITIONS[transition]
    for k in range(1, n):
        out = f"x{k}"
        parts.append(f"[{last}][p{k}]xfade=transition={xf}:duration={tl['xfade']}:offset={k * tl['seconds']:.3f}[{out}]")
        last = out
    if outro:
        parts.append(f"[{n}:v]fps={FPS},scale={w}:{h}:out_range=tv,setsar=1,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[po]")
        parts.append(f"[{last}][po]xfade=transition=fade:duration={OUTRO_XFADE_S}:offset={tl['outro_at']:.3f}[xo]")
        last = "xo"
    tail = "ass=labels.ass:fontsdir=fonts," if has_text else ""
    parts.append(f"[{last}]{tail}format=yuv420p,setsar=1[v]")
    return ";".join(parts)


# Better quality than the clip preset: photos are full of fine detail (bricks, tiles, wood).
QUALITY = {
    "h264_nvenc": ("-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "23", "-b:v", "0",
                   "-maxrate", "16M", "-bufsize", "32M", "-profile:v", "high"),
    "h264_videotoolbox": ("-b:v", "10M", "-allow_sw", "0", "-profile:v", "high"),
    "h264_qsv": ("-preset", "medium", "-global_quality", "22", "-profile:v", "high"),
    "h264_amf": ("-quality", "balanced", "-rc", "cqp", "-qp_i", "22", "-qp_p", "22", "-profile:v", "high"),
    "libx264": ("-preset", "veryfast", "-crf", "21", "-profile:v", "high"),
}


def _encoder_args(enc, preview: bool) -> tuple[str, ...]:
    if preview:
        return ("-c:v", "libx264", "-preset", "ultrafast", "-crf", "30")
    args = QUALITY.get(enc.name, enc.args)
    if enc.name == "libx264":
        from . import perf

        if perf.light():  # a slow CPU: the faster preset (a bit bigger file, same look)
            args = ("-preset", "superfast", "-crf", "21", "-profile:v", "high")
    return ("-c:v", enc.name, *args)


def render(project: Project, dest: Path, *, preview: bool = False,
           on_progress: Callable[[str, float], None] | None = None, encoder=None) -> dict:
    """Make the video. preview: a third of the size, CPU, fast (the same picture)."""
    from .render import ENCODERS, pick_encoder, run_ffmpeg

    ff = require_tool("ffmpeg")
    data = load(project)
    live = active(data)
    if len(live) < MIN_PHOTOS:
        raise SharkyClipsError(f"Add at least {MIN_PHOTOS} photos.")
    if len(live) > MAX_PHOTOS:
        raise SharkyClipsError(f"A slideshow has at most {MAX_PHOTOS} photos.", "Remove some photos.")
    lang = language_of(project, data)
    w, h = (W // PREVIEW_SCALE, H // PREVIEW_SCALE) if preview else (W, H)
    outro = bool(data.get("outro"))
    tl = timeline(len(live), data["seconds"], outro)
    words = texts(data, lang)
    has_text = any(words)

    def stage(name: str, frac: float) -> None:
        if on_progress:
            on_progress(name, min(1.0, max(0.0, frac)))

    t0 = time.time()
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-slideshow-"))
    try:
        frames_dir = project.cache_dir / "slideshow"
        frames_dir.mkdir(parents=True, exist_ok=True)
        inputs: list[str] = []
        steps = len(live) + (1 if outro else 0)
        for k, p in enumerate(live):
            stage("slideshow_photos", k / steps * 0.9)
            src = photos_dir(project) / p["file"]
            if not src.is_file():
                raise SharkyClipsError("A photo of this slideshow is missing.", "Remove it and add it again.")
            still = frames_dir / f"{p['id']}_{w}.jpg"
            if not still.is_file() or still.stat().st_mtime < src.stat().st_mtime:
                tmp = still.with_name(still.name + ".part")
                compose(src, w, h).save(tmp, "JPEG", quality=93 if not preview else 85)
                replace_retry(tmp, still)
            seg = tl["segments"][k]
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seg['length']:.3f}", "-i", str(still)]
        if outro:
            stage("slideshow_outro", (steps - 1) / steps * 0.9)
            odir = frames_dir / f"outro_{w}_v{VERSION}"
            n_frames = int(round(OUTRO_S * FPS))
            if not (odir / f"o{n_frames - 1:03d}.png").is_file():
                write_outro(odir, w, h)
            inputs += ["-framerate", str(FPS), "-i", str(odir / "o%03d.png")]
        if has_text:
            (work / "labels.ass").write_text(labels_ass(words, tl, w, h, lang), encoding="utf-8")
            (work / "fonts").mkdir()
            shutil.copyfile(FONT_FILE, work / "fonts" / FONT_FILE.name)
        graph = build_graph(len(live), tl, data["transition"], outro, has_text, w, h)
        audio_idx = len(live) + (1 if outro else 0)
        inputs += ["-f", "lavfi", "-t", f"{tl['total']:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_out = dest.with_name(dest.stem + ".partial" + dest.suffix)

        def build(enc) -> list[str]:
            return [ff, "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", graph,
                    "-map", "[v]", "-map", f"{audio_idx}:a", *_encoder_args(enc, preview),
                    "-pix_fmt", "yuv420p", "-color_range", "tv", "-r", str(FPS), "-g", str(FPS * 2),
                    "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-ac", "2",
                    "-t", f"{tl['total']:.3f}", "-movflags", "+faststart",
                    "-progress", "pipe:1", "-nostats", str(tmp_out.resolve())]

        enc = ENCODERS["libx264"] if preview else (encoder or pick_encoder()[0])
        total = tl["total"]
        prog = (lambda s: stage("slideshow_rendering", 0.9 + 0.1 * s / total)) if preview else \
            (lambda s: stage("slideshow_rendering", s / total))
        code, err = run_ffmpeg(build(enc), total, prog, cwd=work)
        if code != 0 and enc.hardware:
            from .ui import console

            console.print(f"[yellow]{enc.label} failed for the slideshow, using the CPU: {err.strip()[-200:]}[/]")
            enc = ENCODERS["libx264"]
            code, err = run_ffmpeg(build(enc), total, prog, cwd=work)
        if code != 0 or not tmp_out.is_file():
            tmp_out.unlink(missing_ok=True)  # our own half-written file
            raise SharkyClipsError("The slideshow video couldn't be made.", (err or "").strip()[-400:] or None)
        replace_retry(tmp_out, dest)
    finally:
        shutil.rmtree(work, ignore_errors=True)  # our own mkdtemp folder
    return {"file": dest.name, "path": str(dest), "duration": total, "width": w, "height": h,
            "photos": len(live), "encoder": enc.label, "seconds": round(time.time() - t0, 1),
            "size_bytes": dest.stat().st_size, "fingerprint": fingerprint(data, lang, w)}


# ===================================================================== project + publish package


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def language_of(project: Project, data: dict | None = None) -> str:
    from . import languages

    data = data or load(project)
    lang = data.get("language") or languages.content_language(None, project)
    return lang if lang in LABELS else "en"


def create(title: str = "") -> Project:
    """A new, empty slideshow project."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = " ".join(str(title or "").split())[:80]
    # "slideshow_": slugify() never makes an underscore, so no stream project id can look like this
    pid = f"{ID_PREFIX}{slugify(title, 24) + '-' if title else ''}{uuid.uuid4().hex[:8]}"
    d = config.workspace_dir() / pid
    d.mkdir(parents=True, exist_ok=False)
    project = Project(pid, d)
    project.save_meta({"title": title or stamp, "kind": "slideshow", "mode": "slideshow",
                       "created_at": _now(), "duration": 0.0, "width": W, "height": H, "fps": FPS})
    save(project, defaults())
    return project


def subject_of(data: dict, lang: str) -> str:
    return clean_text(data.get("subject")) or (WORDS.get(lang) or WORDS["en"])["subject"]


def package(project: Project, data: dict | None = None) -> dict:
    """Title options, description and hashtags of the slideshow in the content language, in the
    creator's own style (My style template: their CTA line; ALL CAPS + emoji titles are made by the
    share step, the same as for every clip)."""
    data = data or load(project)
    lang = language_of(project, data)
    words = WORDS.get(lang) or WORDS["en"]
    subject = subject_of(data, lang)
    n = len(active(data))
    labels = LABELS.get(lang) or LABELS["en"]
    titles = [subject, f"{subject} | {labels[0]} → {labels[2]}", f"{labels[0]} → {labels[2]}: {subject}"]
    desc = [words["photos"].format(n=n)]
    try:
        from .titles import mytemplate

        tpl = mytemplate.resolved(lang)
        if tpl:
            s = mytemplate.strings(lang, tpl)
            if s.get("cta"):
                desc.append(s["cta"])
    except Exception:  # noqa: BLE001 - the template is extra
        pass
    tags = words["tags"].split() + ["#shorts"]
    return {"available": True, "viral_score": None, "viral_label": None, "sub_scores": None,
            "titles": [t[:100] for t in titles], "hashtags": tags,
            "description": "\n\n".join(desc), "cover_prompt": None, "hook_text": None,
            "cover_text": subject, "language": lang}


def write_clip(project: Project, result: dict) -> None:
    """The export as the project's one clip: the normal Share flow (YouTube, Instagram, TikTok,
    by hand) and the Library work with it like with any rendered clip."""
    from .web import state

    data = load(project)
    total = float(result["duration"])
    cand = {"id": CID, "rank": 1, "start": 0.0, "end": total, "duration": total, "peak": min(total, 1.0),
            "score": 1.0, "text": subject_of(data, language_of(project, data)), "reasons": [],
            "kind": "slideshow", "publish": package(project, data)}
    created = _now()
    write_json_atomic(project.dir / "highlights.json", {"created_at": created, "kind": "slideshow",
                                                       "candidates": [cand]})
    review_p = project.dir / "review.json"
    if not review_p.is_file():
        write_json_atomic(review_p, {"highlights_created_at": created, "accepted": [CID]})
    else:
        rv = read_json(review_p)
        rv["highlights_created_at"] = created
        rv["accepted"] = sorted(set(rv.get("accepted") or []) | {CID})
        write_json_atomic(review_p, rv)
    state.save_clip(project, CID, {"file": result["file"], "rendered_at": time.time(), "kind": "slideshow",
                                   "width": result["width"], "height": result["height"],
                                   "duration": total, "encoder": result.get("encoder"),
                                   "fingerprint": result.get("fingerprint")})
    meta = project.load_meta()
    meta.update({"duration": total, "exported_at": created, "photos": result.get("photos")})
    project.save_meta(meta)


def export_name(project: Project) -> str:
    return "slideshow.mp4"


def list_slideshows() -> list[Project]:
    from .project import list_projects

    return [p for p in list_projects() if is_slideshow(p) and not p.posts_only]


def file_url_safe(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+", name or "")) and ".." not in name

