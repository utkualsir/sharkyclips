"""Study cards (1.2.18): key formulas, definitions and steps of a lesson clip as clean cards.

In study mode (switch: off / auto) the clip's transcript is read by the local LLM, which picks up
to MAX_CARDS moments worth a card:
  formula     the formula as LaTeX (rendered with matplotlib's mathtext: fractions, roots,
              exponents, Greek letters; no LaTeX install, no browser) + a one-line meaning
  definition  the term and a short definition
  steps       up to 5 short steps
Without the LLM a careful fallback finds spoken definitions ("X is ...", "X demek ...") and
formulas said with "equals" / "eşittir" only.

Cards are PNGs in the app style (navy card, gold label, white text) and slide + fade in on top of
the finished clip while the teacher talks about it (a second encode of the video, audio copied).
Cache: <project>/cache/llm/cards_<clip>_<sig>.json and cache/cards/<clip>_<n>_<frame>.png.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import SharkyClipsError, require_tool
from .procs import no_window
from .project import Project, read_json, write_json_atomic

MAX_CARDS = 3
MIN_SHOW, MAX_SHOW = 3.0, 7.0
KINDS = ("formula", "definition", "steps")
NAVY, GOLD, WHITE, SOFT = (14, 26, 51), (217, 181, 106), (255, 255, 255), (200, 210, 230)
LABELS = {
    "en": {"formula": "FORMULA", "definition": "DEFINITION", "steps": "STEPS"},
    "tr": {"formula": "FORMÜL", "definition": "TANIM", "steps": "ADIMLAR"},
    "de": {"formula": "FORMEL", "definition": "DEFINITION", "steps": "SCHRITTE"},
    "hu": {"formula": "KÉPLET", "definition": "DEFINÍCIÓ", "steps": "LÉPÉSEK"},
    "ru": {"formula": "ФОРМУЛА", "definition": "ОПРЕДЕЛЕНИЕ", "steps": "ШАГИ"},
    "ar": {"formula": "صيغة", "definition": "تعريف", "steps": "خطوات"},
    "zh": {"formula": "公式", "definition": "定义", "steps": "步骤"},
}

SCHEMA = {
    "type": "object",
    "properties": {"cards": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": list(KINDS)},
            "title": {"type": "string"},
            "latex": {"type": "string"},
            "text": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
            "line": {"type": "integer", "minimum": 1},
        },
        "required": ["kind", "title", "text", "line"]}}},
    "required": ["cards"],
}


# ===================================================================== which moments


def _lines(project: Project, cand: dict) -> tuple[list[dict], str | None]:
    from .textutil import sentences

    tr = project.load_transcript() if project.transcript_path.is_file() else {}
    return sentences(tr, float(cand["start"]), float(cand["end"])) if tr else [], tr.get("language")


def _sig(cand: dict, lines: list[dict]) -> str:
    raw = json.dumps([round(float(cand["start"]), 2), round(float(cand["end"]), 2),
                      [x["text"] for x in lines], 1], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def cache_path(project: Project, cand: dict, sig: str) -> Path:
    return project.cache_dir / "llm" / f"cards_{cand['id']}_{sig}.json"


def detect(project: Project, cand: dict, use_llm: bool = True, model=None) -> list[dict]:
    """Cards of one clip: [{kind, title, latex, text, steps, start, end}] in source time."""
    lines, lang = _lines(project, cand)
    if not lines:
        return []
    sig = _sig(cand, lines)
    cp = cache_path(project, cand, sig)
    if cp.is_file():
        try:
            return read_json(cp)["cards"]
        except (OSError, ValueError, KeyError):
            pass
    cards = None
    how = "rules"
    if use_llm:
        try:
            cards = _ask_llm(lines, lang, model)
            how = "llm"
        except SharkyClipsError:
            cards = None
    if cards is None:
        cards = heuristic(lines, lang)
    cards = _place(cards, lines, float(cand["end"]))
    cp.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(cp, {"cards": cards, "how": how, "lang": lang})
    return cards


def _ask_llm(lines: list[dict], lang: str | None, model=None) -> list[dict]:
    from . import llm
    from .languages import get as lang_get

    listing = "\n".join(f"{i + 1}. {x['text']}" for i, x in enumerate(lines))
    lname = (lang_get(lang).english_name if lang and lang_get(lang) else "the transcript's language")
    prompt = (
        "This is the transcript of a short lesson clip (numbered sentences). Pick at most "
        f"{MAX_CARDS} moments that deserve an on-screen study card: a FORMULA the teacher states, a key "
        "DEFINITION, or a short list of STEPS. Only things actually said; skip chit-chat. For a formula "
        "give it as LaTeX math in 'latex' (no $ signs; use \\frac, ^, _, \\sqrt, \\Delta, \\cdot) and a "
        "one-line meaning in 'text'. For a definition: the term in 'title', a definition of at most 14 "
        "words in 'text'. For steps: up to 5 steps of at most 6 words each in 'steps'. 'title' is at "
        f"most 4 words. Write title/text/steps in {lname}. 'line' = the sentence number where it is "
        f"said. If nothing deserves a card, return an empty list.\n\n{listing}")

    def check(d: dict) -> list[str]:
        errs = []
        for c in d["cards"]:
            if not 1 <= c["line"] <= len(lines):
                errs.append(f"line must be 1..{len(lines)}")
            if c["kind"] == "formula" and not (c.get("latex") or "").strip():
                errs.append("a formula card needs 'latex'")
            if c["kind"] == "steps" and not c.get("steps"):
                errs.append("a steps card needs 'steps'")
        return errs

    def run(m) -> dict:
        return m.json("You make clean study cards from lessons. Answer only with JSON.", prompt, SCHEMA,
                      temperature=0.2, check=check, num_predict=900)

    if model is not None:
        data = run(model)
    else:
        if not llm.server_version(timeout=1.0):
            raise SharkyClipsError("The local AI isn't running.")
        with llm.session() as m:
            data = run(m)
    out = []
    for c in data["cards"][:MAX_CARDS]:
        out.append({"kind": c["kind"], "title": c["title"].strip()[:40], "latex": (c.get("latex") or "").strip()[:160],
                    "text": c["text"].strip()[:140], "steps": [s.strip()[:48] for s in (c.get("steps") or [])][:5],
                    "line": int(c["line"])})
    return out


_DEF = {
    "en": re.compile(r"^(?:so\s+|and\s+)?(?P<term>[\w\s-]{3,30}?)\s+(?:is defined as|means|is called)\s+(?P<rest>.{8,120})", re.I),
    "tr": re.compile(r"^(?P<term>[\w\s-]{3,30}?)\s+(?:demek|denir|olarak tanımlanır|nedir)[,:]?\s*(?P<rest>.{8,120})", re.I),
    "de": re.compile(r"^(?P<term>[\w\s-]{3,30}?)\s+(?:bedeutet|heißt|ist definiert als)\s+(?P<rest>.{8,120})", re.I),
}
_EQ = re.compile(r"(?P<lhs>[\w\s]{1,30}?)\s+(?:equals|is equal to|eşittir|eşit|gleich)\s+(?P<rhs>[\w\s/+*×÷-]{1,60})", re.I)
_OPS = [(r"\b(?:divided by|bölü|geteilt durch)\b", "/"), (r"\b(?:times|çarpı|mal)\b", r" \\cdot "),
        (r"\b(?:plus|artı)\b", "+"), (r"\b(?:minus|eksi)\b", "-"), (r"\b(?:squared|kare)\b", "^2")]


def heuristic(lines: list[dict], lang: str | None) -> list[dict]:
    """Without the LLM: only clear spoken definitions and "X equals Y" formulas."""
    out: list[dict] = []
    for i, ln in enumerate(lines):
        text = ln["text"].strip()
        m = _EQ.search(text)
        if m and any(re.search(p, m.group("rhs"), re.I) for p, _r in _OPS):
            rhs = m.group("rhs").strip()
            for pat, rep in _OPS:
                rhs = re.sub(pat, rep, rhs, flags=re.I)
            parts = [p.strip() for p in rhs.split("/")]
            expr = rf"\frac{{{_tex_words(parts[0])}}}{{{_tex_words(parts[1])}}}" if len(parts) == 2 else _tex_words(rhs)
            out.append({"kind": "formula", "title": m.group("lhs").strip().title()[:40],
                        "latex": f"{_tex_words(m.group('lhs').strip())} = {expr}", "text": text[:140], "steps": [],
                        "line": i + 1})
            continue
        dm = _DEF.get(lang or "en")
        d = dm.search(text) if dm else None
        if d:
            out.append({"kind": "definition", "title": d.group("term").strip().title()[:40],
                        "text": d.group("rest").strip().rstrip(".")[:140], "latex": "", "steps": [], "line": i + 1})
        if len(out) >= MAX_CARDS:
            break
    return out


def _tex_words(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip())
    return r"\mathrm{" + s.replace(" ", r"\ ") + "}" if re.search(r"[A-Za-z]{2,}", s) else s


def _place(cards: list[dict], lines: list[dict], clip_end: float) -> list[dict]:
    """Source-time window per card: from its sentence, MIN..MAX_SHOW s, no overlaps."""
    out = []
    last = -1.0
    for c in sorted(cards, key=lambda c: c["line"]):
        ln = lines[c["line"] - 1]
        a = max(float(ln["start"]), last + 0.3)
        b = min(clip_end - 0.2, max(a + MIN_SHOW, min(a + MAX_SHOW, float(ln["end"]) + 2.5)))
        if b - a < 1.5:
            continue
        out.append({**c, "start": round(a, 2), "end": round(b, 2)})
        last = b
    return out


# ===================================================================== drawing


def _font(bold: bool, size: int, lang: str | None):
    from PIL import ImageFont

    from .edit.bubbles import _font_file

    if lang == "zh":
        for f in (r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
                  "/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
            if Path(f).is_file():
                return ImageFont.truetype(f, size)
    f = _font_file(bold)
    try:
        return ImageFont.truetype(f, size) if f else ImageFont.load_default(size)
    except OSError:
        return ImageFont.load_default(size)


def math_image(latex: str, px: int, color=WHITE):
    """LaTeX math -> transparent PIL image (matplotlib mathtext). None if it doesn't parse."""
    import io

    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import mathtext  # noqa: F401 - registers the parser
    from matplotlib.figure import Figure
    from PIL import Image

    expr = latex.strip().strip("$")
    if not expr:
        return None
    fig = Figure(figsize=(0.01, 0.01), dpi=100)
    fig.text(0, 0, f"${expr}$", fontsize=px * 0.72, color=tuple(v / 255 for v in color))
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0.04, dpi=100)
    except (ValueError, RuntimeError):
        return None
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


def _wrap(draw, text: str, font, width: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    if " " not in text.strip() and len(text) > 8:  # Chinese: wrap by characters
        words = list(text.strip())
        sep = ""
    else:
        sep = " "
    lines, cur = [], ""
    for w in words:
        t = (cur + sep + w) if cur else w
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def draw_card(card: dict, width: int, lang: str | None, dest: Path) -> Path:
    """One card as a PNG with transparency (rounded navy card, gold label + accent bar)."""
    from PIL import Image, ImageDraw

    s = width / 900
    pad = int(44 * s)
    inner = width - 2 * pad
    label = LABELS.get(lang or "en", LABELS["en"])[card["kind"]]
    f_label, f_title, f_text = _font(True, int(30 * s), lang), _font(True, int(50 * s), lang), _font(False, int(40 * s), lang)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    blocks: list[tuple[str, object]] = []
    y = pad
    blocks.append(("label", (label, y)))
    y += int(48 * s)
    if card.get("title"):
        for ln in _wrap(probe, card["title"], f_title, inner, 2):
            blocks.append(("title", (ln, y)))
            y += int(62 * s)
    math = math_image(card["latex"], int(84 * s)) if card["kind"] == "formula" and card.get("latex") else None
    if math is not None:
        if math.width > inner:
            k = inner / math.width
            math = math.resize((inner, max(1, int(math.height * k))), Image.LANCZOS)
        y += int(10 * s)
        blocks.append(("math", (math, y)))
        y += math.height + int(16 * s)
    body = card.get("text") or ""
    if card["kind"] == "formula" and math is None and card.get("latex"):
        body = card["latex"] + ("  —  " + body if body else "")
    if card["kind"] == "steps" and card.get("steps"):
        for i, st in enumerate(card["steps"][:5]):
            for j, ln in enumerate(_wrap(probe, st, f_text, inner - int(60 * s), 2)):
                blocks.append(("step", (ln, y, i + 1 if j == 0 else None)))
                y += int(52 * s)
    elif body:
        for ln in _wrap(probe, body, f_text, inner, 4):
            blocks.append(("text", (ln, y)))
            y += int(52 * s)
    h = y + pad
    img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(30 * s)
    d.rounded_rectangle((0, 0, width - 1, h - 1), radius=r, fill=NAVY + (238,), outline=GOLD + (255,), width=max(2, int(3 * s)))
    d.rounded_rectangle((pad, int(pad * 0.55), pad + int(70 * s), int(pad * 0.55) + int(8 * s)), radius=int(4 * s), fill=GOLD + (255,))
    rtl = lang == "ar"

    def x_for(text: str, font, indent: int = 0) -> int:
        return width - pad - indent - int(d.textlength(text, font=font)) if rtl else pad + indent

    for kind, val in blocks:
        if kind == "label":
            d.text((x_for(val[0], f_label), val[1]), val[0], font=f_label, fill=GOLD + (255,))
        elif kind == "title":
            d.text((x_for(val[0], f_title), val[1]), val[0], font=f_title, fill=WHITE + (255,))
        elif kind == "math":
            m, yy = val
            img.alpha_composite(m, ((width - m.width) // 2, yy))
        elif kind == "text":
            d.text((x_for(val[0], f_text), val[1]), val[0], font=f_text, fill=SOFT + (255,))
        elif kind == "step":
            text, yy, n = val
            if n is not None:
                cx = width - pad - int(22 * s) if rtl else pad + int(22 * s)
                d.ellipse((cx - int(20 * s), yy + int(4 * s), cx + int(20 * s), yy + int(44 * s)), fill=GOLD + (255,))
                num = str(n)
                d.text((cx - d.textlength(num, font=f_label) / 2, yy + int(8 * s)), num, font=f_label, fill=NAVY + (255,))
            d.text((x_for(text, f_text, int(60 * s)), yy), text, font=f_text, fill=WHITE + (255,))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return dest


# ===================================================================== on the video


def overlay(video: Path, cards: list[dict], dest: Path, *, frame: str, lang: str | None, fps: float,
            enc_args: list[str], on_progress=None) -> None:
    """Cards (with "out_start"/"out_end" in clip time) slide + fade in on top of `video`."""
    from .clips import run_ffmpeg

    ffmpeg = require_tool("ffmpeg")
    probe = subprocess.run([ffmpeg, "-hide_banner", "-i", str(video)], capture_output=True, text=True, **no_window())
    m = re.search(r"Stream.*Video.* (\d{2,5})x(\d{2,5})", probe.stderr)
    W, H = (int(m.group(1)), int(m.group(2))) if m else ((1080, 1920) if frame != "wide" else (1920, 1080))
    dur_m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr)
    total = (int(dur_m.group(1)) * 3600 + int(dur_m.group(2)) * 60 + float(dur_m.group(3))) if dur_m else 60.0
    cw = int(W * (0.84 if frame != "wide" else 0.36))
    work = Path(tempfile.mkdtemp(prefix="sharkyclips-cards-"))
    try:
        inputs, chain, last = ["-i", str(video)], [], "0:v"
        for i, c in enumerate(cards):
            png = draw_card(c, cw, lang, work / f"card{i}.png")
            a, b = float(c["out_start"]), float(c["out_end"])
            inputs += ["-loop", "1", "-t", f"{b + 0.1:.3f}", "-i", png.name]
            x = "(W-w)/2" if frame != "wide" else f"W-w-{int(W * 0.04)}"
            y0 = int(H * (0.14 if frame != "wide" else 0.08))
            # slide up 40 px while fading in (0.35 s), fade out (0.3 s)
            ys = f"{y0}+40*max(0\\,1-(t-{a:.3f})/0.35)"
            chain.append(f"[{i + 1}:v]format=rgba,fade=t=in:st={a:.3f}:d=0.35:alpha=1,"
                         f"fade=t=out:st={max(a, b - 0.3):.3f}:d=0.3:alpha=1[c{i}]")
            chain.append(f"[{last}][c{i}]overlay=x={x}:y='{ys}':enable='between(t,{a:.3f},{b:.3f})':"
                         f"eof_action=pass[v{i}]")
            last = f"v{i}"
        graph = ";".join(chain) + f";[{last}]format=yuv420p[v]"
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostats", *inputs, "-filter_complex", graph,
               "-map", "[v]", "-map", "0:a?", "-c:a", "copy", *enc_args, "-movflags", "+faststart",
               "-progress", "pipe:1", str(dest)]
        code, err = run_ffmpeg(cmd, total, on_progress, cwd=work)
        if code != 0:
            raise SharkyClipsError(f"Could not add the study cards: {err.strip()[-300:]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
