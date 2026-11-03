"""Chat bubbles: real chat messages from the clip's moment, drawn as rounded bubbles.

- Only messages sent during the clip (chat.json: the replay download, an imported log or the
  live chat SharkyClips recorded during the stream), at the time they were sent.
- Filtered: swear words (the profanity lists of every language), links, e-mail addresses,
  phone numbers, @mentions (personal), bot commands ("!..."), walls of text.
- At most 3 on screen, one new bubble per second at most, 12 per clip; newest at the bottom,
  older ones slide up and fade out after a few seconds.
- Emotes stay as their text names (KEKW, LUL): no images to download.
- Placed in a zone that avoids the captions, the hook and the platform's own buttons (safe zones).
"""

from __future__ import annotations

import functools
import hashlib
import platform
import re
from pathlib import Path

from .words import compile_entries, find

MAX_ON_SCREEN = 3
SHOW_S = 4.0
MIN_GAP_S = 1.0
MAX_PER_CLIP = 12
MAX_CHARS = 90
PALETTE = ["#FF6B6B", "#4ECDC4", "#FFD166", "#06D6A0", "#B388FF", "#F15BB5", "#00BBF9", "#FB8500"]

_URL = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|net|org|tv|gg|io|ly|me|ru|tr|de|co|app|link|xyz|info|biz)\b"
                  r"|discord\.gg|t\.me/|bit\.ly)", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"(\+?\d[\d\s().\-/]{6,}\d)")
_MENTION = re.compile(r"(^|\s)@\w")
_REPEAT = re.compile(r"(.)\1{4,}")


@functools.lru_cache(maxsize=1)
def _all_lists():
    from . import profanity

    out = []
    for lang in profanity.DEFAULTS:
        entries = compile_entries(profanity.word_list(lang), lang)
        if entries:
            out.append((lang, entries))
    return out


def has_swear(text: str) -> bool:
    tokens = [t for t in re.split(r"[\s,.!?;:\"'()\[\]]+", text) if t]
    if not tokens:
        return False
    for lang, entries in _all_lists():
        if find(tokens, entries, lang):
            return True
    return False


def clean(text: str, author: str | None = None) -> str | None:
    """The message as shown, or None when it must not be shown."""
    text = " ".join(str(text or "").split())
    if not text or text.startswith("!") or len(text) > 160:
        return None
    if _URL.search(text) or _EMAIL.search(text) or _MENTION.search(text):
        return None
    for m in _PHONE.finditer(text):
        if sum(c.isdigit() for c in m.group(1)) >= 7:
            return None
    if has_swear(text) or (author and has_swear(author)):
        return None
    text = _REPEAT.sub(lambda m: m.group(1) * 4, text)  # "aaaaaaaa" -> "aaaa"
    if len(text) > MAX_CHARS:
        cut = text[:MAX_CHARS].rsplit(" ", 1)[0]
        text = (cut if len(cut) > MAX_CHARS // 2 else text[:MAX_CHARS]).rstrip(" ,.;:") + "…"
    return text


def color_for(name: str) -> str:
    h = int(hashlib.md5(name.casefold().encode("utf-8")).hexdigest()[:6], 16)
    return PALETTE[h % len(PALETTE)]


def pick(chat: dict | None, plan, start: float, end: float) -> list[dict]:
    """Bubbles in the clip's main-part time: [{"a", "b", "user", "text", "color"}]."""
    if not chat or chat.get("status") != "ok":
        return []
    names = chat.get("names") or []
    colors = chat.get("colors") or {}
    out: list[dict] = []
    last = -1e9
    for row in chat.get("messages") or []:
        t, text = float(row[0]), row[1]
        if t < start + 0.3 or t > end - 1.0:
            continue
        o = plan.to_out(t)
        if o is None or o - last < MIN_GAP_S:
            continue
        idx = int(row[2]) if len(row) > 2 and row[2] is not None else -1
        user = str(names[idx]) if 0 <= idx < len(names) else ""
        shown = clean(text, user)
        if not shown:
            continue
        user = user.lstrip("@")[:24]
        out.append({"a": round(o, 3), "b": round(min(o + SHOW_S, plan.out_duration), 3), "user": user,
                    "text": shown, "color": colors.get(user) or color_for(user or shown)})
        last = o
        if len(out) >= MAX_PER_CLIP:
            break
    return [b for b in out if b["b"] - b["a"] >= 1.0]


# --------------------------------------------------------------------- drawing


def _font_file(bold: bool) -> str | None:
    system = platform.system()
    cands = {
        "Windows": [r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"],
        "Darwin": ["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
                   "/System/Library/Fonts/Supplemental/Arial.ttf"],
    }.get(system, ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    return next((c for c in cands if Path(c).is_file()), None)


@functools.lru_cache(maxsize=16)
def _font(bold: bool, size: int):
    try:
        from PIL import ImageFont

        f = _font_file(bold)
        return ImageFont.truetype(f, size) if f else None
    except Exception:  # noqa: BLE001 - Pillow missing / font broken: estimate instead
        return None


def text_width(text: str, size: int, bold: bool = False) -> float:
    f = _font(bold, size)
    if f is not None:
        try:
            return float(f.getlength(text))
        except Exception:  # noqa: BLE001
            pass
    wide = sum(1 for c in text if ord(c) > 0x2E80)  # CJK: about square
    return size * (0.56 * (len(text) - wide) + 1.0 * wide) * (1.06 if bold else 1.0)


def wrap(text: str, size: int, width: float, max_lines: int = 2) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        nxt = f"{cur} {w}".strip()
        if text_width(nxt, size) <= width or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        last = " ".join(lines[max_lines - 1:])
        while last and text_width(last + "…", size) > width:
            last = last[:-1]
        lines = lines[: max_lines - 1] + [last.rstrip() + "…"]
    out = []
    for ln in lines:  # one long word (no spaces, CJK): hard-cut by width
        while ln and text_width(ln, size) > width:
            ln = ln[:-1]
        out.append(ln)
    return out


def ass_color(hex_color: str) -> str:
    h = (hex_color.lstrip("#") + "FFFFFF")[:6]
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def _rounded(w: float, h: float, r: float) -> str:
    w, h, r = round(w), round(h), round(min(r, h / 2, w / 2))
    return (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def ass_lines(bubbles: list[dict], zone: dict, font: str, ts) -> list[str]:
    """ASS Dialogue lines. bubbles: final-time {"a", "b", ...}; zone: {"x", "bottom", "w", "scale",
    "hidden": [(a, b)...] (final times with no bubbles: replays)}; ts: seconds -> ASS time."""
    if not bubbles:
        return []
    s = float(zone.get("scale") or 1.0)
    size, name_size = round(40 * s), round(34 * s)
    pad_x, pad_y, gap, line_h, radius = round(22 * s), round(14 * s), round(12 * s), round(48 * s), round(22 * s)
    max_w = float(zone["w"])
    shapes = []
    for b in bubbles:
        name_w = text_width(b["user"], name_size, True) if b["user"] else 0.0
        lines = wrap(b["text"], size, max_w - 2 * pad_x)
        body_w = max(text_width(ln, size) for ln in lines)
        w = min(max_w, max(name_w, body_w) + 2 * pad_x)
        h = 2 * pad_y + (round(40 * s) if b["user"] else 0) + line_h * len(lines)
        shapes.append({**b, "lines": lines, "w": w, "h": h})

    # Time slices: whenever a bubble appears or expires, the visible set (max 3, newest at the
    # bottom) is laid out again; a bubble that moved slides to its new place.
    hidden = [tuple(x) for x in zone.get("hidden") or []]
    times = sorted({t for sh in shapes for t in (sh["a"], sh["b"])} | {t for a, b in hidden for t in (a, b)})
    slices = []
    for t0, t1 in zip(times, times[1:]):
        if t1 - t0 < 0.02:
            continue
        mid = (t0 + t1) / 2
        if any(a <= mid < b for a, b in hidden):
            continue
        vis = [i for i, sh in enumerate(shapes) if sh["a"] <= mid < sh["b"]][-MAX_ON_SCREEN:]
        if vis:
            slices.append((t0, t1, vis))
    pos: dict[tuple[int, int], int] = {}  # (slice, bubble) -> top y
    for si, (_t0, _t1, vis) in enumerate(slices):
        y = float(zone["bottom"])
        for i in reversed(vis):
            y -= shapes[i]["h"]
            pos[(si, i)] = round(y)
            y -= gap
    out: list[str] = []
    x = round(float(zone["x"]))
    for si, (t0, t1, vis) in enumerate(slices):
        for i in vis:
            sh = shapes[i]
            y = pos[(si, i)]
            prev = pos.get((si - 1, i)) if si > 0 and slices[si - 1][1] >= t0 - 0.02 else None
            nxt = pos.get((si + 1, i)) if si + 1 < len(slices) and slices[si + 1][0] <= t1 + 0.02 else None
            fade_in = 160 if prev is None else 0
            fade_out = 160 if nxt is None else 0
            if prev is None:
                move = f"\\move({x},{y + round(26 * s)},{x},{y},0,160)"
            elif prev != y:
                move = f"\\move({x},{prev},{x},{y},0,160)"
            else:
                move = f"\\pos({x},{y})"
            fad = f"\\fad({fade_in},{fade_out})" if fade_in or fade_out else ""
            tag = f"{{\\an7{move}{fad}"
            bg = f"{tag}\\p1\\bord0\\shad0\\1c&H1A1210&\\1a&H38&}}{_rounded(sh['w'], sh['h'], radius)}"
            out.append(f"Dialogue: 3,{ts(t0)},{ts(t1)},bubble,,0,0,0,,{bg}")
            text = []
            if sh["user"]:
                text.append(f"{{\\fs{name_size}\\b1\\c{ass_color(sh['color'])}}}{_esc(sh['user'])}{{\\b0}}")
            text.append(f"{{\\fs{size}\\c&HFFFFFF&}}" + "\\N".join(_esc(ln) for ln in sh["lines"]))
            # The text starts at the bubble's padding (same movement, shifted)
            if prev is None:
                tmove = f"\\move({x + pad_x},{y + pad_y + round(26 * s)},{x + pad_x},{y + pad_y},0,160)"
            elif prev != y:
                tmove = f"\\move({x + pad_x},{prev + pad_y},{x + pad_x},{y + pad_y},0,160)"
            else:
                tmove = f"\\pos({x + pad_x},{y + pad_y})"
            out.append(f"Dialogue: 4,{ts(t0)},{ts(t1)},bubble,,0,0,0,,{{\\an7{tmove}{fad}}}" + "\\N".join(text))
    return out


def style_line(font: str) -> str:
    return (f"Style: bubble,{font},40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,"
            "100,100,0,0,1,0,0,7,0,0,0,1")
