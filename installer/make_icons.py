"""Draw the SharkyClips logo (a shark fin that is also a play button) in every format the app needs.

    python installer/make_icons.py        (needs Pillow: pip install -r backend/requirements-dev.txt)

Two versions of one mark, in the colours of the app's default "Classic" look (1.2.74; the
1.2.65 "Shark Sign" yellow tile is now only one of the personalization presets):
  dark   white fin + blue water line on a navy tile   (app icon, tray, favicon, dark UI)
  light  blue fin + blue water line on a white tile   (the main logo on light pages: README)
The tile is a rounded square with a thin lighter border, the same proportions as the header logo
in the app (.brand-mark: a 30 px tile around a 20 px mark, radius 8 px). The fin sits above a
water line; the play triangle is cut out of the fin, so the mark reads as "shark" and as "video".

Writes assets/icon/sharkyclips{,-light}.{svg,png}, sharkyclips.ico, sharkyclips.icns,
sharkyclips-mark.svg (no tile, currentColor), the Windows installer's wizard images
(installer/windows/wizard*.bmp), frontend/public/{favicon.svg,favicon.ico,apple-touch-icon.png,
logo-light.svg,logo-dark.svg,icon-192/512.png,icon-maskable-512.png} and the website's
docs/site/{favicon.svg,favicon.ico,apple-touch-icon.png,img/mark.svg,img/logo-*.svg}. The shapes
live here once, so all formats match. `--google` also redraws docs/logo-120.png (the Google OAuth
consent screen logo: changing it there asks Google for a new brand review, so it is never redrawn
by default).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

# Classic colours (frontend/src/themes.css, :root and the light block: --mark-tile, --mark-fin ...)
NAVY = "#0A1020"         # Classic dark page background (--bg)
TILE_DARK = "#0E1A33"    # --mark-tile (dark)
EDGE_DARK = "#2B3E66"    # --mark-tile-border (dark)
WHITE = "#FFFFFF"        # --mark-fin (dark)
BLUE = "#5B9BFF"         # --mark-wave (dark), --l-water
GOLD = "#D9B56A"         # --gold (the accent)
TILE_LIGHT = "#FFFFFF"   # --mark-tile (light)
EDGE_LIGHT = "#D5E1F5"   # --mark-tile-border (light)
FIN_LIGHT = "#1650C8"    # --mark-fin (light)
WAVE_LIGHT = "#1F6FE5"   # --mark-wave (light)
# theme: (tile, border, fin, wave)
COLORS = {"dark": (TILE_DARK, EDGE_DARK, WHITE, BLUE), "light": (TILE_LIGHT, EDGE_LIGHT, FIN_LIGHT, WAVE_LIGHT)}

# The tile: rounded square on the 64 x 64 grid. The mark inside is the header's: a 52-unit-wide
# viewBox (6..58 x 8..56, centre 32, 32) shown 20 px wide in a 30 px tile -> scale 20/30*64/52.
TILE_R = 17.0            # 8 px of 30 px
EDGE_W = 1.6             # ~1 px of 30 px
GLYPH = 20 / 30 * 64 / 52
GLYPH_SMALL = 0.96       # 16-32 px icons (favicon, tray, taskbar): a bigger mark stays readable

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
    """theme: dark (white fin on navy) | light (blue fin on white) | mark (no tile, currentColor)."""
    attrs = f' width="{size}" height="{size}"' if size else ""
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"{attrs}>']
    if theme in COLORS:
        bg, edge, fin, wave = COLORS[theme]
        if tile:
            h = EDGE_W / 2
            p.append(f'<rect x="{h:g}" y="{h:g}" width="{64 - EDGE_W:g}" height="{64 - EDGE_W:g}" '
                     f'rx="{TILE_R - h:g}" fill="{bg}" stroke="{edge}" stroke-width="{EDGE_W:g}"/>')
            p.append(f'<g transform="translate(32 32) scale({GLYPH:.4f}) translate(-32 -32)">')
    else:
        fin, wave = "currentColor", "currentColor"
    # the play triangle is a hole in the fin (evenodd), so it shows whatever is behind the mark
    p.append(f'<path fill-rule="evenodd" d="{_fin_d()}{_play_d()}" fill="{fin}"/>')
    op = ' opacity="0.55"' if theme == "mark" else ""
    p.append(f'<path d="{_wave_d()}" fill="none" stroke="{wave}" stroke-width="{WAVE_W}" '
             f'stroke-linecap="round"{op}/>')
    if theme in COLORS and tile:
        p.append("</g>")
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


def _glyph(pts, scale: float = GLYPH):
    return [(32 + (x - 32) * scale, 32 + (y - 32) * scale) for x, y in pts]


def render(size: int, theme: str = "dark", margin: float = 0.0, tile: bool = True) -> Image.Image:
    """margin: transparent border as a share of the size (macOS icons sit inside a grid)."""
    big = 1024
    inset = big * margin
    s = (big - 2 * inset) / 64

    def tr(pts):
        return [(inset + x * s, inset + y * s) for x, y in pts]

    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg, edge, fin_c, wave_c = COLORS["light" if theme == "light" else "dark"]
    k = (GLYPH_SMALL if size <= 32 else GLYPH) if tile else 1.0
    if tile:
        box = [inset, inset, big - inset - 1, big - inset - 1]
        d.rounded_rectangle(box, radius=TILE_R * s, fill=_hex(edge) + (255,))
        e = EDGE_W * s
        d.rounded_rectangle([box[0] + e, box[1] + e, box[2] - e, box[3] - e], radius=(TILE_R - EDGE_W) * s,
                            fill=_hex(bg) + (255,))
    # fin mask with the play triangle cut out
    mask = Image.new("L", (big, big), 0)
    md = ImageDraw.Draw(mask)
    md.polygon(tr(_glyph(_fin_points(), k)), fill=255)
    md.polygon(tr(_glyph(PLAY, k)), fill=0)
    img.paste(Image.new("RGBA", (big, big), _hex(fin_c) + (255,)), (0, 0), mask)
    wl = Image.new("L", (big, big), 0)
    wd = ImageDraw.Draw(wl)
    pts = tr(_glyph(_wave_points(), k))
    r = WAVE_W * k * s / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):  # round brush stamped along the path: no seams
        steps = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / 2))
        for i in range(steps + 1):
            x, y = x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps
            wd.ellipse([x - r, y - r, x + r, y + r], fill=255)
    img.paste(Image.new("RGBA", (big, big), _hex(wave_c) + (255,)), (0, 0), wl)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def google_logo(path: Path) -> None:
    """Google OAuth consent screen logo: 120 x 120 PNG, square, under 1 MB. On a solid square
    (no transparent corners: Google crops it itself)."""
    img = Image.new("RGB", (120, 120), _hex(NAVY))
    tile = render(120, "dark")
    img.paste(tile, (0, 0), tile)
    img.save(path, optimize=True)


def pwa_icons(pub: Path) -> None:
    """The phone approval page's app icons (manifest.json): normal + maskable (safe zone)."""
    render(192, "dark").save(pub / "icon-192.png")
    render(512, "dark").save(pub / "icon-512.png")
    tile = Image.new("RGBA", (512, 512), (*_hex(TILE_DARK), 255))
    tile.alpha_composite(render(512, "dark", margin=0.12, tile=False))
    tile.save(pub / "icon-maskable-512.png")


def wizard_images(dest: Path) -> None:
    """Inno Setup wizard art (BMP, 100 % / 150 % / 200 % sizes): the big side panel is the Classic
    navy with the white fin above three blue wave lines; the small one is the app icon on white."""
    def wave_line(d: ImageDraw.ImageDraw, w: int, y: float, amp: float, period: float, width: int, color) -> None:
        import math
        pts = [(x, y + amp * math.sin(x / period * 2 * math.pi)) for x in range(-4, w + 5, 2)]
        d.line(pts, fill=color, width=width, joint="curve")

    for scale, suffix in ((1.0, ""), (1.5, "-150"), (2.0, "-200")):
        w, h = round(164 * scale), round(314 * scale)
        img = Image.new("RGB", (w, h), _hex(NAVY))
        d = ImageDraw.Draw(img)
        y0 = h * 0.62
        fin_w = w * 0.62
        fs = fin_w / 36.0  # the fin spans x 13 .. 48.5 on the 64 grid
        ox, oy = (w - fin_w) / 2 - 13 * fs, y0 - 44 * fs
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        md.polygon([(ox + x * fs, oy + y * fs) for x, y in _fin_points()], fill=255)
        md.polygon([(ox + x * fs, oy + y * fs) for x, y in PLAY], fill=0)
        img.paste(Image.new("RGB", (w, h), _hex(WHITE)), (0, 0), mask)
        for k, (amp, alpha) in enumerate(((3.2, 1.0), (2.6, 0.55), (2.0, 0.3))):
            c = tuple(round(a * alpha + b * (1 - alpha)) for a, b in zip(_hex(BLUE), _hex(NAVY)))
            wave_line(d, w, y0 + 6 * scale + k * 14 * scale, amp * scale, 24 * scale, max(2, round(2.4 * scale)), c)
        img.save(dest / f"wizard{suffix}.bmp")
        sw = round(55 * scale), round(58 * scale)
        small = Image.new("RGB", sw, (255, 255, 255))
        icon = render(min(sw) - round(6 * scale), "dark")
        small.paste(icon, ((sw[0] - icon.width) // 2, (sw[1] - icon.height) // 2), icon)
        small.save(dest / f"wizard-small{suffix}.bmp")


def site_icons(site: Path) -> None:
    """The website (docs/site): favicon (svg + ico), apple-touch-icon, header marks."""
    (site / "img").mkdir(parents=True, exist_ok=True)

    def write(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8", newline="\n")

    write(site / "favicon.svg", svg("dark"))
    write(site / "img" / "mark.svg", svg("mark", tile=False))
    write(site / "img" / "logo-dark.svg", svg("dark"))
    write(site / "img" / "logo-light.svg", svg("light"))
    render(48, "dark").save(site / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                            append_images=[render(16, "dark"), render(32, "dark")])
    render(180, "dark").save(site / "apple-touch-icon.png", optimize=True)
    render(512, "dark").save(site / "img" / "icon-512.png", optimize=True)


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
    render(1024, "light").save(out / "sharkyclips-light.png")  # main logo (README, light pages)
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
    site_icons(ROOT / "docs" / "site")
    if "--google" in sys.argv:
        google_logo(ROOT / "docs" / "logo-120.png")
    print(f"Icons written to {out}, {pub} and docs/site")


if __name__ == "__main__":
    main()
