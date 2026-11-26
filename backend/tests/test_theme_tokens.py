"""1.2.69 themes: every colour lives in frontend/src/themes.css (or one of the few artwork
palettes below), and every preset is readable (WCAG AA) in light and dark.

1. No hard-coded colour (hex, rgb(), hsl(), white/black keywords in colour properties) in any
   stylesheet / component / the launcher's splash page outside the allowed files.
2. Each preset x mode resolves every token, and the main text pairs reach 4.5:1.
3. A preset's light block repeats every colour its dark block sets (else the dark value leaks
   into light mode through the cascade).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"
THEMES = SRC / "themes.css"

# Artwork with its own fixed colours (not UI chrome). Each one is a palette module: the rest of
# the app imports colours from it, nobody writes a colour literal anywhere else.
ALLOWED = {
    "themes.css": "the theme tokens",
    "components/Flags.tsx": "national flags of the language switcher",
    "components/PlatformIcons.tsx": "YouTube / TikTok / Instagram / Google logos (their brand rules)",
    "exportLook.ts": "the colours burnt into the video, which the 9:16 preview must match",
    "minigame/art.ts": "the mini game's fish, sharks and power-ups (sprites, not UI)",
    "themeMath.ts": "colour maths: builds rgba() strings from colours read from the theme",
}

COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")
KEYWORD = re.compile(
    r"(?:color|background|fill|stroke|border[a-z-]*|outline|stopColor|stop-color|fillStyle|strokeStyle)"
    r"\s*[:=]\s*[\"'{]?\s*(white|black)\b",
    re.I,
)


def _strip_comments(text: str, suffix: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    if suffix in (".ts", ".tsx"):
        text = re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", text)
    if suffix == ".html":
        text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return text


def _files():
    for p in sorted(SRC.rglob("*")):
        if p.suffix in (".css", ".ts", ".tsx") and "i18n" not in p.parts:
            yield p
    yield ROOT / "frontend" / "index.html"
    yield ROOT / "backend" / "sharkyclips" / "web" / "splash.html"
    yield from sorted((ROOT / "backend" / "sharkyclips" / "web").glob("*.py"))  # pages the server writes


def test_no_hard_coded_colours_outside_the_theme():
    bad = []
    for p in _files():
        rel = p.relative_to(SRC).as_posix() if SRC in p.parents else p.name
        suffix = ".ts" if p.suffix == ".py" else p.suffix  # (comments: "#" lines are not stripped, fine)
        if rel in ALLOWED:
            continue
        text = _strip_comments(p.read_text(encoding="utf-8"), suffix)
        for n, line in enumerate(text.splitlines(), 1):
            # a route ("#/x") or an id with letters past f (url(#boot-fin), "#settings") is not a colour
            line = re.sub(r"[\"'`]#/[^\"'`]*[\"'`]|#[\w-]*[g-zG-Z_-][\w-]*", "", line)
            if COLOUR.search(line) or KEYWORD.search(line):
                bad.append(f"{rel}:{n}: {line.strip()[:120]}")
    assert not bad, "hard-coded colours (use a token from themes.css):\n" + "\n".join(bad)


# ---------------------------------------------------------------- the presets themselves


def _blocks() -> list[tuple[str, dict[str, str]]]:
    css = re.sub(r"/\*.*?\*/", " ", THEMES.read_text(encoding="utf-8"), flags=re.S)
    out = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        decl = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body))
        out.append((" ".join(sel.split()), {k: v.strip() for k, v in decl.items()}))
    return out


def resolve(preset: str, mode: str) -> dict[str, str]:
    """The cascade on <html data-preset data-theme> for these simple selectors (source order,
    higher specificity wins: :root < :root[a] < :root[a][b]). Keys without the leading --."""

    def matches(sel: str) -> int | None:
        best = None
        for s in sel.split(","):
            s = s.strip()
            if " " in s or not s.startswith(":root"):
                continue  # the data-theme-local copies
            attrs = dict(re.findall(r"\[([\w-]+)=\"([\w-]+)\"\]", s))
            if attrs.get("data-preset", preset) == preset and attrs.get("data-theme", mode) == mode:
                best = max(best or 0, len(attrs))
        return best

    win: dict[str, tuple[int, int, str]] = {}
    for i, (sel, decl) in enumerate(_blocks()):
        spec = matches(sel)
        if spec is None:
            continue
        for k, v in decl.items():
            if k not in win or (spec, i) >= win[k][:2]:
                win[k] = (spec, i, v)
    return {k[2:]: v for k, (_, _, v) in win.items()}


def _rgb(v: str, under=None) -> tuple[float, float, float]:
    v = v.strip()
    if v.startswith("#"):
        h = v[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    m = re.fullmatch(r"rgba?\(([^)]*)\)", v)
    assert m, v
    parts = [float(x) for x in re.split(r"[,\s/]+", m.group(1).strip()) if x]
    r, g, b = (x / 255 for x in parts[:3])
    a = parts[3] if len(parts) > 3 else 1.0
    if a < 1:
        assert under is not None, f"{v} needs a background"
        r, g, b = (a * c + (1 - a) * u for c, u in zip((r, g, b), under))
    return (r, g, b)


def _lum(c) -> float:
    def ch(x):
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    r, g, b = (ch(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


PRESETS = ["classic", "ocean", "sign", "contrast"]
TEXT_PAIRS = [  # (foreground, background): 4.5:1
    ("text", "bg"), ("text", "surface"), ("text", "surface-2"), ("strong", "surface"),
    ("muted", "bg"), ("muted", "surface"), ("muted", "surface-2"),
    ("gold-text", "surface"), ("gold-text", "bg"), ("link", "surface"), ("link", "bg"),
    ("success", "surface"), ("warn", "surface"), ("danger", "surface"), ("danger", "bg"),
    ("chip-text", "chip-bg"), ("primary-text", "primary-bg"), ("primary-text", "primary-hover"),
    ("on-sign", "gold"), ("bleep-text", "surface"), ("on-danger", "danger-fill"),
    ("l-text", "l-bg"), ("l-muted", "l-bg"), ("warn", "warn-soft"), ("danger", "danger-soft"),
    ("success", "success-soft"), ("gold-text", "gold-soft"), ("text", "gold-soft"),
]
UI_PAIRS = [("on", "surface"), ("mark", "surface")]  # 3:1 (non-text marks)


def colour(t: dict[str, str], name: str, under=None):
    v = t[name]
    while v.startswith("var("):
        v = t[v[4:].split(")")[0].split(",")[0].strip()[2:]]
    return _rgb(v, under)


@pytest.mark.parametrize("mode", ["dark", "light"])
@pytest.mark.parametrize("preset", PRESETS)
def test_every_preset_is_readable(preset, mode):
    t = resolve(preset, mode)
    for k in ("bg", "surface", "text", "muted", "gold", "primary-bg", "link", "bleep", "mark", "l-bg", "mg-water-a"):
        assert k in t, (preset, mode, k)
    bad = []
    for pairs, need in ((TEXT_PAIRS, 4.5), (UI_PAIRS, 3.0)):
        for fg, bg in pairs:
            back = colour(t, bg, colour(t, "surface"))
            r = ratio(colour(t, fg, back), back)
            if r < need:
                bad.append(f"{fg} on {bg}: {r:.2f} (needs {need})")
    assert not bad, f"{preset} {mode}: " + ", ".join(bad)


@pytest.mark.parametrize("preset", PRESETS)
def test_light_block_repeats_the_dark_colours(preset):
    blocks = _blocks()
    same_in_both = {"--cut-k", "--cut", "--cut-card", "--fin-r", "--fin-r-card", "--media-bg", "--tip-bg", "--shadow"}
    dark_sel = ":root" if preset == "classic" else f':root[data-preset="{preset}"]'
    light_sel = ':root[data-theme="light"]' if preset == "classic" else f':root[data-preset="{preset}"][data-theme="light"]'
    dark: dict[str, str] = {}
    for s, d in blocks:
        if s == dark_sel:
            dark.update(d)
    light = next(d for s, d in blocks if s.split(",")[0].strip() == light_sel)
    missing = [k for k in dark if k not in light and k not in same_in_both and not k.startswith("--mg-")]
    if preset == "classic":  # the first :root block holds the fixed tokens
        fixed = next(d for s, d in blocks if s == ":root")
        missing = [k for k in missing if k not in fixed and k != "--page-glow"]
    assert not missing, f"{preset}: the light block must set {missing}"
