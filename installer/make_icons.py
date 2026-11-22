"""Draw the SharkyClips logo (a shark fin that is also a play button) in every format the app needs.

    python installer/make_icons.py        (needs Pillow: pip install -r backend/requirements-dev.txt)

Two versions of one mark ("Shark Sign", 1.2.65):
  dark   deep-water fin on a sign-yellow tile   (app icon, tray, favicon, dark UI)
  light  sign-yellow fin on an ink tile          (the main logo: README, light UI)
The tile has the fin-cut corner (top right chamfer) of the UI. The fin sits above a water line;
the play triangle is cut out of the fin, so the mark reads as "shark" and as "video clip".

Writes assets/icon/sharkyclips{,-light}.{svg,png}, sharkyclips.ico, sharkyclips.icns,
sharkyclips-mark.svg (no tile, currentColor), the Windows installer's wizard images
(installer/windows/wizard*.bmp) and frontend/public/{favicon.svg,favicon.ico,apple-touch-icon.png,
logo-light.svg,logo-dark.svg,icon-192/512.png,icon-maskable-512.png}. The shapes live here once,
so all formats match. `--google` also redraws docs/logo-120.png (the Google OAuth consent screen
logo: changing it there asks Google for a new brand review, so it is never redrawn by default).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

WATER = "#0B1D22"      # deep water (the dark UI background)
INK = "#0E2A30"        # ink (the light UI's text and primary button)
SIGN = "#FFD23F"       # shark-warning-sign yellow
TEAL = "#5FB7C4"       # water line in the installer art
CUT = 16               # fin-cut corner (top right) on the 64 x 64 grid
TILE = [(0.0, 0.0), (64.0 - CUT, 0.0), (64.0, float(CUT)), (64.0, 64.0), (0.0, 64.0)]
COLORS = {"dark": (SIGN, WATER), "light": (INK, SIGN)}  # theme: (tile, fin + wave)

# 64 x 64 grid. Fin: convex leading edge up to the tip, concave trailing edge back down.
FIN = [("M", (13.0, 44.0)), ("C", (17.5, 33.0), (28.0, 18.0), (48.5, 11.5)),
       ("C", (42.0, 20.0), (39.5, 32.0), (46.5, 44.0)), ("Z",)]
PLAY = [(25.5, 30.0), (25.5, 40.5), (35.0, 35.25)]  # cut out of the fin
WAVE_Y, WAVE_W = 50.0, 3.4
WAVE = [(8.0, WAVE_Y), (20.0, WAVE_Y), (32.0, WAVE_Y), (44.0, WAVE_Y), (56.0, WAVE_Y)]  # ~ crests between


def _fin_d() -> str:
    out = []
    for cmd in FIN:
        if cmd[0] == "Z":
            out.append("Z")
        else:
            out.append(cmd[0] + " ".join(f"{x:g} {y:g}" for x, y in cmd[1:]))
    return "".join(out)


def _play_d() -> str:
    return "M" + "L".join(f"{x:g} {y:g}" for x, y in PLAY) + "Z"


def _wave_d() -> str:
    # gentle sine-like line: quarter-wave quadratic segments, amplitude 1.6
    x0, y = WAVE[0]
    d = f"M{x0:g} {y:g}"
    x = x0
    up = True
    while x < WAVE[-1][0] - 0.1:
        d += f"Q{x + 3:g} {y - 1.6 if up else y + 1.6:g} {x + 6:g} {y:g}"
        x += 6
        up = not up
    return d


def svg(theme: str = "dark", tile: bool = True, size: int | None = None) -> str:
    """theme: dark (water fin on yellow) | light (yellow fin on ink) | mark (no tile, currentColor)."""
    attrs = f' width="{size}" height="{size}"' if size else ""
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"{attrs}>']
    if theme in COLORS:
        bg, fin = COLORS[theme]
        wave = fin
        if tile:
            pts = " ".join(f"{x:g},{y:g}" for x, y in TILE)
            p.append(f'<polygon points="{pts}" fill="{bg}"/>')
    else:
        fin, wave = "currentColor", "currentColor"
    # the play triangle is a hole in the fin (evenodd), so it shows whatever is behind the mark
    p.append(f'<path fill-rule="evenodd" d="{_fin_d()}{_play_d()}" fill="{fin}"/>')
    op = ' opacity="0.55"' if theme == "mark" else ""
    p.append(f'<path d="{_wave_d()}" fill="none" stroke="{wave}" stroke-width="{WAVE_W}" '
             f'stroke-linecap="round"{op}/>')
    p.append("</svg>")
    return "".join(p) + "\n"


# ------------------------------------------------------------------ raster


def _bezier(p0, p1, p2, p3, n=48):
    pts = []
    for i in range(1, n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def _fin_points():
    pts, cur = [], None
    for cmd in FIN:
        if cmd[0] == "M":
            cur = cmd[1]
            pts.append(cur)
        elif cmd[0] == "C":
            pts += _bezier(cur, *cmd[1:])
            cur = cmd[3]
    return pts


def _wave_points():
    x0, y = WAVE[0]
    pts = [(x0, y)]
    x, up = x0, True
    while x < WAVE[-1][0] - 0.1:
        c = (x + 3, y - 1.6 if up else y + 1.6)
        end = (x + 6, y)
        for i in range(1, 13):  # quadratic Bezier (x, y) -> c -> end
            t = i / 12
            a, b, e = (1 - t) ** 2, 2 * (1 - t) * t, t ** 2
            pts.append((a * x + b * c[0] + e * end[0], a * y + b * c[1] + e * end[1]))
        x += 6
        up = not up
    return pts


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def render(size: int, theme: str = "dark", margin: float = 0.0, tile: bool = True) -> Image.Image:
    """margin: transparent border as a share of the size (macOS icons sit inside a grid)."""
    big = 1024
    inset = big * margin
    s = (big - 2 * inset) / 64

    def tr(pts):
        return [(inset + x * s, inset + y * s) for x, y in pts]

    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg, fg = COLORS["light" if theme == "light" else "dark"]
    if tile:
        d.polygon(tr(TILE), fill=bg)
    # fin mask with the play triangle cut out
    mask = Image.new("L", (big, big), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(tr(_fin_points()), fill=255)
    md.polygon(tr(PLAY), fill=0)
    img.paste(Image.new("RGBA", (big, big), _hex(fg) + (255,)), (0, 0), mask)
    wave = _hex(fg) + (255,)
    wl = Image.new("L", (big, big), 0)
    wd = ImageDraw.Draw(wl)
    pts = tr(_wave_points())
    r = WAVE_W * s / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):  # round brush stamped along the path: no seams
        steps = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / 2))
        for i in range(steps + 1):
            x, y = x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps
            wd.ellipse([x - r, y - r, x + r, y + r], fill=255)
    if tile:  # keep the line inside the tile
        clip = Image.new("L", (big, big), 0)
        ImageDraw.Draw(clip).polygon(tr(TILE), fill=255)
        wl = ImageChops.multiply(wl, clip)
    img.paste(Image.new("RGBA", (big, big), wave), (0, 0), wl)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def google_logo(path: Path) -> None:
    """Google OAuth consent screen logo: 120 x 120 PNG, square, under 1 MB. On a solid square
    (no transparent corners: Google crops it itself)."""
    img = Image.new("RGB", (120, 120), _hex(WATER))
    tile = render(120, "dark")
    img.paste(tile, (0, 0), tile)
    img.save(path, optimize=True)


def pwa_icons(pub: Path) -> None:
    """The phone approval page's app icons (manifest.json): normal + maskable (safe zone)."""
    render(192, "dark").save(pub / "icon-192.png")
    render(512, "dark").save(pub / "icon-512.png")
    tile = Image.new("RGBA", (512, 512), (*_hex(WATER), 255))
    tile.alpha_composite(render(512, "dark", margin=0.12))
    tile.save(pub / "icon-maskable-512.png")


def wizard_images(dest: Path) -> None:
    """Inno Setup wizard art (BMP, 100 % / 150 % / 200 % sizes): the big side panel is deep water
    with the yellow fin above three wave lines; the small one is the app icon on white."""
    def wave_line(d: ImageDraw.ImageDraw, w: int, y: float, amp: float, period: float, width: int, color) -> None:
        import math
        pts = [(x, y + amp * math.sin(x / period * 2 * math.pi)) for x in range(-4, w + 5, 2)]
        d.line(pts, fill=color, width=width, joint="curve")

    for scale, suffix in ((1.0, ""), (1.5, "-150"), (2.0, "-200")):
        w, h = round(164 * scale), round(314 * scale)
        img = Image.new("RGB", (w, h), _hex(WATER))
        d = ImageDraw.Draw(img)
        y0 = h * 0.62
        fin_w = w * 0.62
        fs = fin_w / 36.0  # the fin spans x 13 .. 48.5 on the 64 grid
        ox, oy = (w - fin_w) / 2 - 13 * fs, y0 - 44 * fs
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        md.polygon([(ox + x * fs, oy + y * fs) for x, y in _fin_points()], fill=255)
        md.polygon([(ox + x * fs, oy + y * fs) for x, y in PLAY], fill=0)
        img.paste(Image.new("RGB", (w, h), _hex(SIGN)), (0, 0), mask)
        for k, (amp, alpha) in enumerate(((3.2, 1.0), (2.6, 0.55), (2.0, 0.3))):
            c = tuple(round(a * alpha + b * (1 - alpha)) for a, b in zip(_hex(TEAL), _hex(WATER)))
            wave_line(d, w, y0 + 6 * scale + k * 14 * scale, amp * scale, 24 * scale, max(2, round(2.4 * scale)), c)
        img.save(dest / f"wizard{suffix}.bmp")
        sw = round(55 * scale), round(58 * scale)
        small = Image.new("RGB", sw, (255, 255, 255))
        icon = render(min(sw) - round(6 * scale), "dark")
        small.paste(icon, ((sw[0] - icon.width) // 2, (sw[1] - icon.height) // 2), icon)
        small.save(dest / f"wizard-small{suffix}.bmp")


def main() -> None:
    import sys

    out = ROOT / "assets" / "icon"
    pub = ROOT / "frontend" / "public"
    out.mkdir(parents=True, exist_ok=True)

    def write(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8", newline="\n")

    write(out / "sharkyclips.svg", svg("dark"))
    write(out / "sharkyclips-light.svg", svg("light"))
    write(out / "sharkyclips-mark.svg", svg("mark", tile=False))
    write(pub / "favicon.svg", svg("dark"))
    write(pub / "logo-light.svg", svg("light"))
    write(pub / "logo-dark.svg", svg("dark"))
    render(512, "dark").save(out / "sharkyclips.png")         # tray + app icon
    render(1024, "light").save(out / "sharkyclips-light.png")  # main logo (README, social)
    render(1024, "dark").save(out / "sharkyclips-dark-1024.png")
    render(180, "dark").save(pub / "apple-touch-icon.png")
    pwa_icons(pub)
    ico_sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    render(256, "dark").save(out / "sharkyclips.ico", sizes=[(s, s) for s in ico_sizes],
                             append_images=[render(s, "dark") for s in ico_sizes[:-1]])
    render(48, "dark").save(pub / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                            append_images=[render(16, "dark"), render(32, "dark")])
    render(1024, "dark", margin=0.09).save(out / "sharkyclips.icns")  # macOS: Pillow writes every icns size
    wizard_images(ROOT / "installer" / "windows")
    if "--google" in sys.argv:
        google_logo(ROOT / "docs" / "logo-120.png")
    print(f"Icons written to {out} and {pub}")


if __name__ == "__main__":
    main()
