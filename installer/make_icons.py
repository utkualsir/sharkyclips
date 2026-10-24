"""Draw the ClipForge icon (gold diamond on navy) in every format the app needs.

    python installer/make_icons.py        (needs Pillow: pip install -r backend/requirements-dev.txt)

Writes assets/icon/clipforge.{svg,png,ico,icns}, frontend/public/favicon.svg and
frontend/public/apple-touch-icon.png. The shapes live here once, so all formats match.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
NAVY = "#0E1A33"
EDGE = "#22345A"
# 64 x 64 grid. Crown (top) facets are lighter, pavilion (bottom) facets darker: a flat, faceted gem.
FACETS = [
    ("#E9CB86", [(22, 15), (26, 25), (13, 25)]),            # crown left
    ("#F6E2AE", [(22, 15), (42, 15), (38, 25), (26, 25)]),  # table
    ("#D9B56A", [(42, 15), (51, 25), (38, 25)]),            # crown right
    ("#C9A257", [(13, 25), (26, 25), (32, 51)]),            # pavilion left
    ("#DDBB72", [(26, 25), (38, 25), (32, 51)]),            # pavilion middle
    ("#A9843F", [(38, 25), (51, 25), (32, 51)]),            # pavilion right
]
RADIUS = 14


def svg(background: bool = True) -> str:
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">']
    if background:
        parts.append(f'<rect width="64" height="64" rx="{RADIUS}" fill="{NAVY}"/>')
    for color, pts in FACETS:
        d = "M" + "L".join(f"{x} {y}" for x, y in pts) + "Z"
        parts.append(f'<path d="{d}" fill="{color}"/>')
    parts.append("</svg>")
    return "".join(parts) + "\n"


def render(size: int, margin: float = 0.0) -> Image.Image:
    """margin: transparent border as a share of the size (macOS icons sit inside a grid)."""
    big = 1024
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    inset = big * margin
    scale = (big - 2 * inset) / 64
    d.rounded_rectangle([inset, inset, big - inset - 1, big - inset - 1], radius=RADIUS * scale,
                        fill=NAVY, outline=EDGE, width=max(1, round(scale * 0.6)))
    for color, pts in FACETS:
        d.polygon([(inset + x * scale, inset + y * scale) for x, y in pts], fill=color)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    out = ROOT / "assets" / "icon"
    out.mkdir(parents=True, exist_ok=True)
    (out / "clipforge.svg").write_text(svg(), encoding="utf-8", newline="\n")
    (ROOT / "frontend" / "public" / "favicon.svg").write_text(svg(), encoding="utf-8", newline="\n")
    render(512).save(out / "clipforge.png")
    render(180).save(ROOT / "frontend" / "public" / "apple-touch-icon.png")
    ico_sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    base = render(256)
    base.save(out / "clipforge.ico", sizes=[(s, s) for s in ico_sizes],
              append_images=[render(s) for s in ico_sizes[:-1]])
    render(1024, margin=0.09).save(out / "clipforge.icns")  # macOS: Pillow writes every icns size
    print(f"Icons written to {out}")


if __name__ == "__main__":
    main()
