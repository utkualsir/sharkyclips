"""Game events read from the screen (and optional sound clips) as a highlight signal.

Kills, multikills, objectives, deaths and result screens become reason events (codes like
"lol_pentakill", "df_multikill" with value "3") and lift the hype curve around them: a ramp
during the build-up before the event, full strength over the event itself (all kills of a
multikill), a short tail after. Bigger events lift more (pentakill >> double kill).

The span of each event also goes into meta["spans"]: the candidate picker extends a clip so
the whole event fits, with build-up before it.

Skipped (weight re-normalized away) when the game isn't one with a HUD preset, the user chose
"Other", or OCR isn't installed.
"""

from __future__ import annotations

import numpy as np

from .base import ReasonEvent, Signal, SignalResult, SignalUnavailable, register

BUILD_UP = 6.0  # seconds before an event that are lifted (ramping up)
TAIL = 3.0  # seconds after
MIN_STRENGTH_FOR_SPAN = 0.3  # small events (an assist) don't force clip boundaries


@register
class GameSignal(Signal):
    name = "game"
    version = 1

    def check(self, ctx) -> None:
        from ...game import ocr, resolve

        info = resolve(ctx.project)
        ctx.game_info = info
        if not info["game"]:
            if info["choice"] == "other":
                raise SignalUnavailable("game set to Other")
            raise SignalUnavailable(f"game not recognized ({info['why']})")
        if not ocr.installed():
            raise SignalUnavailable("OCR not installed (python -m pip install rapidocr)")
        if ctx.project.source_path is None:
            raise SignalUnavailable("no video file")

    def compute(self, ctx) -> SignalResult:
        from ... import game
        from ...ui import time_progress

        info = ctx.game_info
        gid = info["game"]
        with time_progress() as prog:
            task = prog.add_task("Reading the game HUD", total=ctx.duration)  # job stage "reading_hud"
            sc = game.scan(ctx.project, gid, on_progress=lambda d, _total: prog.update(task, completed=d))
        try:
            hits, sound_info = game.sound_matches(ctx.project, gid)
        except Exception as exc:  # a broken reference clip must not stop the analysis
            hits, sound_info = [], {"error": str(exc)}
        events = game.combine(gid, sc, hits)

        n = ctx.n
        scores = np.zeros(n)
        spans = []
        for e in events:
            s = float(e["strength"])
            a, b = float(e["start"]), float(e["end"])
            lo, hi = max(0, int(a - BUILD_UP)), min(n - 1, int(np.ceil(b + TAIL)))
            for i in range(lo, hi + 1):
                if i < a:
                    w = 0.45 + 0.55 * (1 - (a - i) / BUILD_UP)
                elif i <= b + 1:
                    w = 1.0
                else:
                    w = max(0.0, 1 - (i - b - 1) / TAIL)
                scores[i] = max(scores[i], s * w)
            if s >= MIN_STRENGTH_FOR_SPAN:
                spans.append([round(a, 2), round(b, 2), round(s, 3)])

        reasons = []
        for e in events:
            # df_multikill: how many kills; LoL: the champion ("Quadra kill · Yasuo").
            value = e.get("value") if e["code"] == "df_multikill" else e.get("champion")
            reasons.append(ReasonEvent(float(e["t"]), e["code"], value, float(e["strength"])))
        return SignalResult(self.name, scores, reasons, {
            "game": gid, "detected_by": info["why"], "events": len(events), "spans": spans,
            "champion": game.champion_name(sc),
            "scan": {k: sc["stats"].get(k) for k in ("decoder", "seconds", "speed", "ocr_calls")},
            "sounds": len(sound_info.get("clips", [])),
        })
