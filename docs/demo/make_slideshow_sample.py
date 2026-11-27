"""The Photo slideshow sample (1.2.72): docs/demo/slideshow-sample.mp4 from generated pictures only.

    python docs/demo/make_slideshow_sample.py [out.mp4]

Eight drawn "photos" of a wall being tiled (before -> progress -> result): no real photos, no
third-party content. They have different shapes (portrait, landscape, square, a wide panorama),
one is stored sideways with an EXIF "rotate" flag (as phones do), and they are given to the app
in a shuffled order with their dates in EXIF, so the sample also shows the date sorting, the
rotation fix, the blurred fill, the labels and the logo outro. Runs in a throwaway settings folder.
"""

from __future__ import annotations

import io
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def wall(w: int, h: int, step: int, seed: int):
    """The wall at step 0 (old, cracked) .. 7 (tiled, with a shelf and a plant)."""
    from PIL import Image, ImageDraw, ImageFilter

    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h), (186, 172, 150))
    d = ImageDraw.Draw(img)
    floor_y = int(h * 0.82)
    d.rectangle([0, floor_y, w, h], fill=(120, 92, 70))
    for x in range(0, w, max(40, w // 12)):
        d.line([(x, floor_y), (x - h // 5, h)], fill=(104, 80, 60), width=max(2, w // 300))
    if step == 0:  # old wall: stains and cracks
        for _ in range(14):
            cx, cy, r = rnd.randrange(w), rnd.randrange(floor_y), rnd.randrange(20, max(30, w // 7))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(160 + rnd.randrange(20), 146, 120))
        img = img.filter(ImageFilter.GaussianBlur(w / 140))
        d = ImageDraw.Draw(img)
        for _ in range(6):
            x, y = rnd.randrange(w), rnd.randrange(floor_y // 2)
            pts = [(x, y)]
            for _k in range(9):
                x += rnd.randrange(-w // 25, w // 25)
                y += rnd.randrange(h // 60, h // 22)
                pts.append((x, y))
            d.line(pts, fill=(92, 80, 66), width=max(2, w // 260))
    if step >= 1:  # fresh plaster
        d.rectangle([0, 0, w, floor_y], fill=(214, 210, 200))
    tile = max(24, w // 9)
    gap = max(2, tile // 14)
    rows = (floor_y // tile) + 1
    done_rows = {1: 0, 2: 1, 3: 3, 4: 5, 5: rows - 1, 6: rows, 7: rows}.get(step, 0)
    for r in range(done_rows):
        y1 = floor_y - (r + 1) * tile
        off = (tile // 2) if r % 2 else 0
        for c in range(-1, w // tile + 2):
            x0 = c * tile + off
            shade = 232 + ((r * 7 + c * 3) % 9)
            d.rectangle([x0 + gap, max(0, y1 + gap), x0 + tile - gap, y1 + tile - gap], fill=(shade - 18, shade - 6, shade))
    if 2 <= step <= 5:  # a bucket and a trowel on the floor
        bx = int(w * 0.68)
        d.rectangle([bx, floor_y - h // 10, bx + w // 7, floor_y + h // 60], fill=(70, 110, 170))
        d.polygon([(int(w * 0.25), floor_y + h // 40), (int(w * 0.36), floor_y + h // 60),
                   (int(w * 0.33), floor_y + h // 22)], fill=(150, 150, 156))
    if step >= 6:  # grout done: a shelf and a plant
        sy = int(floor_y * 0.42)
        d.rectangle([int(w * 0.18), sy, int(w * 0.82), sy + max(8, h // 70)], fill=(140, 98, 64))
        px = int(w * 0.62)
        d.rectangle([px, sy - h // 14, px + w // 12, sy], fill=(196, 92, 60))
        for k in range(5):
            d.ellipse([px - w // 40 + k * w // 60, sy - h // 7 - (k % 2) * h // 40,
                       px + w // 30 + k * w // 60, sy - h // 14], fill=(60, 140 + k * 10, 80))
    if step == 7:  # a warm light: the finished look
        glow = Image.new("RGB", (w, h), (255, 236, 196))
        img = Image.blend(img, glow, 0.10)
    return img


def photos() -> list[tuple[str, bytes]]:
    from PIL import Image

    shapes = [(1200, 1600), (1600, 1200), (1200, 1600), (1100, 1100), (1600, 1200), (3600, 1000),
              (1200, 1600), (1200, 1600)]
    out = []
    for step, (w, h) in enumerate(shapes):
        img = wall(w, h, step, seed=step + 7)
        exif = Image.Exif()
        exif.get_ifd(0x8769)[36867] = f"2026:06:{step * 3 + 1:02d} 10:00:00"
        if step == 2:  # stored sideways, the way a phone does it: EXIF says "rotate 90 clockwise"
            img = img.transpose(Image.Transpose.ROTATE_90)
            exif[274] = 6
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=88, exif=exif.tobytes())
        out.append((f"IMG_{4100 + step}.jpg", buf.getvalue()))
    random.Random(3).shuffle(out)  # the app sorts them by date
    return out


def main(dest: Path) -> None:
    home = Path(tempfile.mkdtemp(prefix="sharkyclips-sample-"))
    (home / "workspace").mkdir()
    (home / "config.json").write_text('{"workspace_dir": "%s", "content_language": "en"}'
                                      % str(home / "workspace").replace("\\", "/"), encoding="utf-8")
    os.environ["SHARKYCLIPS_HOME"] = str(home)
    os.environ["SHARKYCLIPS_NO_MIGRATE"] = "1"
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from sharkyclips import slideshow as S

        project = S.create("Wall tiling: before and after")
        for name, data in photos():
            S.add_photo(project, name, data)
        data = S.load(project)
        data.update(labels=True, seconds=3.0, transition="crossfade", outro=True, subject="Wall tiling")
        S.active(data)[3]["text"] = "Day 10"
        S.save(project, data)
        res = S.render(project, project.dir / "clips" / "slideshow.mp4")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(res["path"], dest)
        print(f"{dest}  {res['duration']} s, {res['size_bytes'] / 1e6:.1f} MB, {res['encoder']}")
    finally:
        shutil.rmtree(home, ignore_errors=True)  # the mkdtemp folder made above


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "demo" / "slideshow-sample.mp4")
