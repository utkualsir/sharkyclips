"""The second pass of a render (1.2.18): the music visualizer and the study cards, on top of the
finished clip (see clips.render_clip). Times come from clips.out_mapper, so cuts, the hook flash,
intro cards and replays are respected."""

from __future__ import annotations

import shutil
from pathlib import Path


def _encoder(spec):
    from .clips import video_args
    from .render import cpu_fallback, pick_codec

    enc = pick_codec(spec.codec) or cpu_fallback(spec.codec)
    return enc, video_args(enc, spec)


def clip_words(project, cand: dict, opts, mapper) -> tuple[list[dict], str | None]:
    """The clip's words (translated ones when dubbed / translated subtitles) in clip time."""
    from .clips import clip_text

    words, lang, _h, _hl = clip_text(project, cand, opts)
    start = float(cand["start"])
    out = []
    for w in words:
        a, b = mapper(w["start"] + start, "fwd"), mapper(w["end"] + start, "back")
        if a is not None and b is not None and b > a:
            out.append({**w, "start": a, "end": b})
    return out, lang


def apply(project, cand: dict, opts, spec, base: Path, dest: Path, ex: dict, on_progress=None) -> str | None:
    """base (the rendered clip) -> dest with the extras. Returns the encoder label."""
    from . import config
    from .clips import out_mapper

    mapper = out_mapper(project, cand, opts, spec)
    enc, args = _encoder(spec)
    cur = base
    tmp = dest.with_name(dest.stem + ".viz" + dest.suffix)
    n = int(ex["visualizer"]) + int(ex["cards"])
    step = 0

    def part():
        if not on_progress:
            return None
        a, b = step / n, (step + 1) / n
        return lambda f: on_progress(a + (b - a) * f)

    try:
        if ex["visualizer"]:
            from . import visualizer

            words, lang = clip_words(project, cand, opts, mapper)
            visualizer.render(project, cand, words, lang, cur, tmp, frame="wide" if spec.frame == "wide" else "tall",
                              size=spec.canvas, enc_args=args, on_progress=part())
            cur = tmp
            step += 1
        if ex["cards"]:
            from . import studycards

            use_llm = config.get("llm_enabled") is not False
            if use_llm:
                try:
                    from . import llm

                    llm.ensure_server()
                except Exception:  # noqa: BLE001 - no local AI: the careful rules instead
                    use_llm = False
            cards = studycards.detect(project, cand, use_llm=use_llm)
            placed = []
            for c in cards:
                a, b = mapper(c["start"], "fwd"), mapper(c["end"], "back")
                if a is not None and b is not None and b - a >= 1.0:
                    placed.append({**c, "out_start": a, "out_end": b})
            if placed:
                from .clips import clip_text

                lang = clip_text(project, cand, opts)[1]
                studycards.overlay(cur, placed, dest, frame="wide" if spec.frame == "wide" else "tall", lang=lang,
                                   fps=30, enc_args=args, on_progress=part())
                cur = dest
            step += 1
        if cur != dest:
            shutil.copyfile(cur, dest)
    finally:
        tmp.unlink(missing_ok=True)
    return enc.label if enc else None
