"""Read the game HUD from sampled frames and record raw observations.

One Scanner per decoding thread (a segment of the video). It never decides "this was a
quadra kill": it records what it saw (K/D/A readings, new score lines, texts, grey death
screens) with timestamps; events.py turns the merged observations into events, so a multikill
that crosses a segment border is still counted once.

Cost control: every region has a cheap pixel test (did it change? is there text?) and OCR only
runs when that test fires.
"""

from __future__ import annotations

import re
import cv2
import numpy as np

from .frames import Frame
from .ocr import Reader
from .presets import Box

KDA_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")
TEAM_RE = re.compile(r"(\d{1,3})\s*v\s*s?\s*(\d{1,3})\s*$", re.I)


def text_rows(img: np.ndarray, min_h: int = 8) -> list[tuple[int, int, int, int]]:
    """Boxes (x0, y0, x1, y1) of the text lines in a HUD crop, top to bottom. A white top-hat
    keeps thin bright strokes and drops large bright areas, so it also works when the text is
    over a bright floor or sky."""
    k = max(9, img.shape[0] // 5) | 1
    hat = cv2.morphologyEx(img, cv2.MORPH_TOPHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    mask = hat > 45
    prof = mask.sum(axis=1)
    rows = prof >= max(3, img.shape[1] // 120)
    spans, start, gap = [], None, 0
    for y, on in enumerate(list(rows) + [False] * 3):
        if on:
            start = y if start is None else start
            gap = 0
        elif start is not None:
            gap += 1
            if gap > 2:
                spans.append((start, y - gap))
                start, gap = None, 0
    # Busy backgrounds can glue two lines together: split tall bands at their emptiest row.
    pitch = max(14, img.shape[0] * 26 // 94)  # line spacing (26 px in the 94 px tall 1080p box)
    split: list[tuple[int, int]] = []
    todo = list(spans)
    while todo:
        y0, y1 = todo.pop(0)
        if y1 - y0 + 1 > pitch * 1.35:
            lo, hi = y0 + pitch // 2, y1 - pitch // 2
            cut = lo + int(np.argmin(prof[lo:hi + 1])) if hi > lo else (y0 + y1) // 2
            todo[:0] = [(y0, cut - 1), (cut + 1, y1)]
        else:
            split.append((y0, y1))
    out = []
    for y0, y1 in split:
        if y1 - y0 + 1 < min_h:
            continue
        cols = np.flatnonzero(mask[y0:y1 + 1].sum(axis=0) >= 1)
        if len(cols):
            out.append((int(cols[0]), y0, int(cols[-1]), y1))
    return out


def read_lines(reader: Reader, img: np.ndarray, max_lines: int = 3) -> list[str]:
    """Read each text line of a HUD crop on its own (much faster than text detection)."""
    texts = []
    for x0, y0, x1, y1 in text_rows(img, min_h=max(6, img.shape[0] // 12))[:max_lines]:
        pad = 4
        line = img[max(0, y0 - pad):y1 + pad + 1, max(0, x0 - 2 * pad):x1 + 2 * pad + 1]
        text, conf = reader.line(line)
        if text.strip() and conf >= 0.5:
            texts.append(text)
    return texts


def changed_pixels(a: np.ndarray, b: np.ndarray, level: int = 40) -> int:
    return int(np.count_nonzero(cv2.absdiff(a, b) > level))


def bgr_crop(fr: Frame, box: Box) -> np.ndarray:
    """Colour crop from the NV12 planes (only for the few crops that need colour)."""
    x, y, w, h = box.x & ~1, box.y & ~1, box.w & ~1, box.h & ~1
    yy = fr.y[y:y + h, x:x + w]
    uv = fr.uv[y // 2:(y + h) // 2, x // 2:(x + w) // 2].reshape(h // 2, w)
    return cv2.cvtColor(np.ascontiguousarray(np.vstack([yy, uv])), cv2.COLOR_YUV2BGR_NV12)


def thumb(fr: Frame) -> np.ndarray:
    return cv2.resize(fr.y, (64, 36), interpolation=cv2.INTER_AREA).astype(np.int16)


def chroma(fr: Frame) -> float:
    """Mean colourfulness of the middle of the frame (0 = grey)."""
    h, w = fr.uv.shape[:2]
    c = fr.uv[h // 4: 3 * h // 4: 4, w // 4: 3 * w // 4: 4].astype(np.int16) - 128
    return float(np.abs(c).sum(axis=2).mean())


ICON_ON = 0.8  # template match score: real icons score 0.85-1.0, gameplay behind them < 0.7
ICON_OFF = 0.6


class Scanner:
    def __init__(self, game: str, boxes: dict[str, Box], reader: Reader, start: float, end: float,
                 templates: dict[str, np.ndarray] | None = None):
        self.game, self.boxes, self.reader, self.start, self.end = game, boxes, reader, start, end
        self.templates = templates or {}
        self.obs: list[dict] = []  # raw observations
        self.reads: list[dict] = []  # every OCR read (debug view)
        self.portraits: list[np.ndarray] = []
        self._prev_thumb: np.ndarray | None = None
        self._screen_until = self._screen_next = -1.0
        self._screen_last = -99.0
        self._cut_at = -99.0
        self._still = 0
        # League of Legends
        self._prev_crop: dict[str, np.ndarray] = {}
        self._last_read: dict[str, float] = {}
        self._team: tuple[int, int] | None = None
        self._kda: tuple[int, int, int] | None = None
        self._kda_missing = 0
        self._ann_until = self._ann_next = -1.0
        self._ann_base = 0.0
        self._ann_last_trigger = -99.0
        self._portrait_last = -999.0
        self._hud_edges = 0.0
        self._hud_low = 0
        # Delta Force
        self._icon_on: dict[str, bool] = {}
        self._icon_low: dict[str, int] = {}
        self._skull_next = -1.0
        self._chroma_hist: list[float] = []
        self._gray_since: float | None = None
        self._gray_last = -99.0
        self._death_last = -99.0
        self._gray_onset = -99.0

    # ------------------------------------------------------------ shared

    def _read(self, t: float, region: str, text: str, how: str) -> None:
        self.reads.append({"t": round(t, 2), "region": region, "text": text, "how": how})

    def _scene_cut(self, fr: Frame) -> bool:
        """True once the picture settles after a cut: result / death / menu screens are
        still, while fast camera turns in gameplay are not."""
        th = thumb(fr)
        diff = float(np.abs(th - self._prev_thumb).mean()) if self._prev_thumb is not None else 0.0
        self._prev_thumb = th
        if diff > 38:
            self._cut_at, self._still = fr.t, 0
            return False
        if fr.t - self._cut_at <= 4.0:
            self._still = self._still + 1 if diff < 9 else 0
            if self._still == 2:
                self._cut_at = -99.0
                return True
        return False

    def _screen_check(self, fr: Frame, trigger: bool, seconds: float = 0.1) -> None:
        """Look for big centre texts (victory, extraction result) after a trigger: a still
        screen after a cut (one read), or the HUD disappearing (reads for `seconds`)."""
        if trigger and fr.t - self._screen_last > 15:
            self._screen_until = fr.t + seconds
            self._screen_next = fr.t
            self._screen_last = fr.t
        if fr.t <= self._screen_until and fr.t >= self._screen_next:
            box = self.boxes["center"]
            crop = box.crop(fr.y)
            small = cv2.resize(crop, (crop.shape[1] // 3, crop.shape[0] // 3), interpolation=cv2.INTER_AREA)  # big text
            texts = self.reader.area(small, min_score=0.6)
            joined = " ".join(texts)
            self._read(fr.t, "center", joined, "area")
            if joined.strip():
                self.obs.append({"t": fr.t, "kind": "text", "region": "center", "text": joined})
            self._screen_next = fr.t + 1.0

    def handle(self, fr: Frame) -> None:
        if self.game == "lol":
            self._lol(fr)
        elif self.game == "delta_force":
            self._df(fr)

    # ------------------------------------------------------------ League of Legends


    def _read_small(self, fr: Frame, region: str, t: float) -> str | None:
        """Read a small HUD number box when it changed (or every 20 s); None = not read now."""
        crop = self.boxes[region].crop(fr.y)
        prev = self._prev_crop.get(region)
        recent = t - self._last_read.get(region, -99) < 20
        if prev is not None and recent and changed_pixels(crop, prev) < max(5, crop.size // 250):
            return None
        self._prev_crop[region] = crop.copy()
        self._last_read[region] = t
        big = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC) if crop.shape[0] < 24 else crop
        text, _ = self.reader.line(big)
        self._read(t, region, text, "line")
        return text.strip()

    def _lol(self, fr: Frame) -> None:
        t = fr.t
        cut = self._scene_cut(fr)
        hud_gone = False
        team = self._read_small(fr, "team", t)
        if team is not None:
            m = TEAM_RE.search(team)
            if m:
                ally, enemy = int(m.group(1)), int(m.group(2))
                if (ally, enemy) != self._team:
                    self._team = (ally, enemy)
                    self.obs.append({"t": t, "kind": "team", "ally": ally, "enemy": enemy})
                    self._announce_soon(t)  # a kill: the announcer banner follows
        kda = self._read_small(fr, "kda", t)
        if kda is not None:
            m = KDA_RE.search(kda)
            if m:
                k, d, a = (int(x) for x in m.groups())
                if (k, d, a) != self._kda:
                    self._kda = (k, d, a)
                    self._announce_soon(t)
                # every reading is kept: the next one confirms it (events.lol_kda_series)
                self.obs.append({"t": t, "kind": "kda", "k": k, "d": d, "a": a})
                self._kda_missing = 0
                if t - self._portrait_last >= 90 and len(self.portraits) < 12:
                    self._portrait_last = t
                    self.portraits.append(bgr_crop(fr, self.boxes["portrait"]))
            else:
                self._kda_missing += 1
                hud_gone = self._kda_missing == 2
        hud_gone = self._hud_vanished(fr) or hud_gone
        self._lol_announce(fr)
        if hud_gone:  # the game ended (or a menu): the result banner comes a few seconds later
            self._screen_check(fr, True, seconds=8.0)
        else:
            self._screen_check(fr, cut)

    def _hud_vanished(self, fr: Frame) -> bool:
        """The ability bar at the bottom disappears when the game ends (victory/defeat)."""
        crop = self.boxes["hud"].crop(fr.y)
        edges = float(np.count_nonzero(cv2.Canny(crop, 80, 160)))
        base = self._hud_edges
        gone = base > 300 and edges < 0.2 * base
        self._hud_low = self._hud_low + 1 if gone else 0
        if not gone:
            self._hud_edges = edges if base == 0 else 0.95 * base + 0.05 * edges
        return self._hud_low == 2

    def _announce_soon(self, t: float) -> None:
        self._ann_until, self._ann_next = t + 2.6, t + 0.5

    def _lol_announce(self, fr: Frame) -> None:
        t = fr.t
        band = self.boxes["announce"].crop(fr.y)
        bright = float(np.count_nonzero(band > 215))
        # Objective banners (Baron, dragon) come without a kill: a jump in bright text pixels.
        floor = band.size / 60
        if bright > max(floor, 4.0 * self._ann_base) and t - self._ann_last_trigger > 8 and t > self._ann_until:
            self._ann_until, self._ann_next = t + 1.6, t
            self._ann_last_trigger = t
        self._ann_base = 0.9 * self._ann_base + 0.1 * bright
        if self._ann_next <= t <= self._ann_until:
            texts = read_lines(self.reader, band, max_lines=2)
            joined = " ".join(texts)
            self._read(t, "announce", joined, "lines")
            if joined.strip():
                self.obs.append({"t": t, "kind": "text", "region": "announce", "text": joined})
            self._ann_next = t + 1.0

    # ------------------------------------------------------------ Delta Force

    def _df(self, fr: Frame) -> None:
        cut = self._scene_cut(fr)
        self._df_icons(fr)
        self._df_gray(fr)
        self._df_killer(fr)
        self._screen_check(fr, cut)

    def _df_killer(self, fr: Frame) -> None:
        """Own death: the "killed by" card on the right has a red "ÖLDÜREN" label (being only
        downed shows no card). A colour test finds it; one OCR read keeps the killer's name for
        the debug view."""
        t = fr.t
        # Only right after the screen turned grey (the death cam): red walls and enemy markers
        # elsewhere in the game would look like the label too.
        if t - self._death_last < 15 or not (self._gray_onset <= t <= self._gray_onset + 6):
            return
        box = self.boxes["killer"]
        uv = fr.uv[box.y // 2:(box.y + box.h) // 2, box.x // 2:(box.x + box.w) // 2]
        red = (uv[..., 1] > 175) & (uv[..., 0] < 125)
        min_w = max(10, int(40 * fr.uv.shape[1] / 960))
        if int(np.count_nonzero(red.sum(axis=1) >= min_w)) < 6:
            return
        self._death_last = t
        crop = box.crop(fr.y)
        small = cv2.resize(crop, (crop.shape[1] // 2, crop.shape[0] // 2), interpolation=cv2.INTER_AREA)
        joined = " ".join(self.reader.area(small, min_score=0.5))
        self._read(t, "killer", joined, "area")
        self.obs.append({"t": t, "kind": "killcard", "text": joined})

    def _df_icons(self, fr: Frame) -> None:
        """The icons above the score counter say what just happened: a skull for a kill, a
        heartbeat for a revive, a handshake for an assist. Template matching is cheap, so it
        runs on every sampled frame; OCR only runs while a skull is shown (to count kills that
        come together and to spot revenge kills)."""
        t = fr.t
        row = self.boxes["icons"].crop(fr.y)
        for name, tmpl in self.templates.items():
            if row.shape[0] < tmpl.shape[0] or row.shape[1] < tmpl.shape[1]:
                continue
            score = float(cv2.matchTemplate(row, tmpl, cv2.TM_CCOEFF_NORMED).max())
            on = self._icon_on.get(name, False)
            if not on and score >= ICON_ON:
                self._icon_on[name] = True
                self._icon_low[name] = 0
                self.obs.append({"t": t, "kind": "icon", "icon": name, "score": round(score, 2)})
                if name == "skull":
                    self._skull_next = t + 0.5
            elif on:
                self._icon_low[name] = self._icon_low.get(name, 0) + 1 if score < ICON_OFF else 0
                if self._icon_low[name] >= 2:
                    self._icon_on[name] = False
        if self._icon_on.get("skull") and t >= self._skull_next:
            texts = read_lines(self.reader, self.boxes["lines"].crop(fr.y))
            joined = " | ".join(texts)
            self._read(t, "lines", joined, "lines")
            if texts:
                self.obs.append({"t": t, "kind": "lines", "texts": texts})
            self._skull_next = t + 1.0

    def _df_gray(self, fr: Frame) -> None:
        """Own death: the screen turns grey (death cam), then the redeploy map."""
        t = fr.t
        c = chroma(fr)
        hist = self._chroma_hist
        hist.append(c)
        if len(hist) > 120:
            del hist[0]
        if len(hist) < 20:
            return
        ref = float(np.median(hist))
        gray = ref > 5 and c < 0.35 * ref
        if gray:
            if self._gray_since is None:
                self._gray_since = t
            elif t - self._gray_since >= 1.0 and t - self._gray_last > 20:
                self._gray_last = t
                self.obs.append({"t": self._gray_since, "kind": "gray", "chroma": round(c, 1),
                                 "ref": round(ref, 1)})
                self._gray_onset = self._gray_since
        else:
            self._gray_since = None
