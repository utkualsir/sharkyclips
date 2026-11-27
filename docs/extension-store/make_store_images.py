"""Store images for the SharkyClips Helper (Edge Add-ons + Firefox Add-ons), 1.2.74.

    python docs/extension-store/make_store_images.py <shots-dir>

<shots-dir> holds three browser captures (made against a throwaway SharkyClips with no accounts):
  popup-connected.png  the Helper's popup after pairing        (380 x 420)
  popup-pair.png       the popup before pairing (code field)   (380 x 420)
  app-code.png         SharkyClips' "Installed the Helper from a store?" box with a code
Writes docs/extension-store/: screenshot-1..3.png (1280 x 800), promo-440x280.png, logo-300.png.
Only the Classic colours, the app's font and the logo: no third-party marks.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FONT = ROOT / "backend" / "sharkyclips" / "assets" / "fonts" / "ArchivoSC-ExtraBold.ttf"
_spec = importlib.util.spec_from_file_location("make_icons", ROOT / "installer" / "make_icons.py")
mi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mi)
NAVY, TEXT, MUTED, GOLD = mi._hex(mi.NAVY), (238, 242, 248), (174, 183, 202), mi._hex(mi.GOLD)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def canvas(w: int = 1280, h: int = 800) -> Image.Image:
    img = Image.new("RGB", (w, h), NAVY)
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse([w * 0.45, -h * 0.6, w * 1.3, h * 0.6], fill=80)
    img.paste((34, 58, 110), (0, 0), glow.filter(ImageFilter.GaussianBlur(w / 9)))
    return img


def paste_card(img: Image.Image, shot: Image.Image, xy: tuple[int, int], width: int) -> None:
    s = shot.convert("RGB")
    s = s.resize((width, round(s.height * width / s.width)), Image.Resampling.LANCZOS)
    x, y = xy
    sh = Image.new("L", img.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle([x + 10, y + 18, x + s.width + 10, y + s.height + 18], radius=16, fill=150)
    img.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(22)))
    mask = Image.new("L", s.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s.width - 1, s.height - 1], radius=14, fill=255)
    img.paste(s, (x, y), mask)
    ImageDraw.Draw(img).rounded_rectangle([x, y, x + s.width - 1, y + s.height - 1], radius=14,
                                          outline=mi._hex(mi.EDGE_DARK), width=2)


def text_block(img: Image.Image, x: int, y: int, title: str, lines: list[str], width: int) -> None:
    d = ImageDraw.Draw(img)
    logo = mi.render(72, "dark")
    img.paste(logo, (x, y), logo)
    d.text((x + 90, y + 14), "SharkyClips Helper", font=font(34), fill=TEXT)
    ty = y + 120
    for part in wrap(d, title, font(52), width):
        d.text((x, ty), part, font=font(52), fill=(255, 255, 255))
        ty += 62
    d.rectangle([x, ty + 12, x + 90, ty + 18], fill=GOLD)
    ty += 48
    for line in lines:
        for i, part in enumerate(wrap(d, line, font(26), width - 34)):
            if i == 0:
                d.ellipse([x, ty + 11, x + 10, ty + 21], fill=GOLD)
            d.text((x + 28, ty), part, font=font(26), fill=MUTED)
            ty += 38
        ty += 10


def wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    out, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            out.append(cur)
            cur = w
    return out + [cur] if cur else out


def main(shots: Path) -> None:
    connected = Image.open(shots / "popup-connected.png")
    pair = Image.open(shots / "popup-pair.png")
    raw = Image.open(shots / "app-code.png").convert("RGB")
    pad = round(raw.width * 0.04)
    code = Image.new("RGB", (raw.width + 2 * pad, raw.height + 2 * pad), raw.getpixel((raw.width - 3, raw.height - 3)))
    code.paste(raw, (pad, pad))  # the element shot has no margin: give the text room

    img = canvas()
    text_block(img, 70, 70, "Fills in your upload. You click Post.",
               ["Puts your SharkyClips video and caption into TikTok's and Instagram's upload page",
                "Stops before Post: you check it and post it yourself",
                "Never types or stores a password"], 620)
    paste_card(img, connected, (790, 150), 420)
    img.save(OUT / "screenshot-1.png", optimize=True)

    img = canvas()
    text_block(img, 70, 70, "Connect once with a code.",
               ["SharkyClips shows a 6-digit code (Settings, Helper guide)",
                "Type it into the Helper's popup",
                "The code works once, for 10 minutes"], 560)
    paste_card(img, code, (650, 120), 570)
    paste_card(img, pair, (900, 380), 300)
    img.save(OUT / "screenshot-2.png", optimize=True)

    img = canvas()
    text_block(img, 70, 70, "Private by design.",
               ["Runs only on tiktok.com and instagram.com",
                "Talks only to the SharkyClips app on your own PC (127.0.0.1)",
                "Collects no data, has no server, shows no ads",
                "Free and open source (MIT)"], 1100)
    img.save(OUT / "screenshot-3.png", optimize=True)

    promo = canvas(440, 280)
    d = ImageDraw.Draw(promo)
    logo = mi.render(84, "dark")
    promo.paste(logo, (30, 40), logo)
    d.text((132, 52), "SharkyClips", font=font(34), fill=(255, 255, 255))
    d.text((132, 94), "Helper", font=font(34), fill=GOLD)
    for i, line in enumerate(("Fills in your TikTok and", "Instagram upload. You", "click Post yourself.")):
        d.text((30, 160 + i * 30), line, font=font(22), fill=MUTED)
    promo.save(OUT / "promo-440x280.png", optimize=True)
    mi.render(300, "dark").save(OUT / "logo-300.png", optimize=True)
    print("store images written to", OUT)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
