"""League of Legends: which champion the streamer plays (for titles like "Quadra kill with Yasuo").

The round portrait in the bottom HUD is compared with Riot's official champion icons (Data
Dragon, free, downloaded once into ~/.sharkyclips/game/lol_champions, ~3 MB). Several portraits
from the game vote. Offline or unsure -> no champion (titles just don't name one).
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from .. import config

DDRAGON = "https://ddragon.leagueoflegends.com"
SIZE = 48


def icon_dir() -> Path:
    return config.config_dir() / "game" / "lol_champions"


def ensure_icons(timeout: float = 20) -> Path | None:
    d = icon_dir()
    if (d / "champions.json").is_file():
        return d
    try:
        with urllib.request.urlopen(f"{DDRAGON}/api/versions.json", timeout=timeout) as r:
            version = json.load(r)[0]
        with urllib.request.urlopen(f"{DDRAGON}/cdn/{version}/data/en_US/champion.json", timeout=timeout) as r:
            data = json.load(r)["data"]
        d.mkdir(parents=True, exist_ok=True)
        names = {}
        for key, c in data.items():
            path = d / f"{key}.png"
            if not path.is_file():
                with urllib.request.urlopen(f"{DDRAGON}/cdn/{version}/img/champion/{c['image']['full']}",
                                            timeout=timeout) as r:
                    path.write_bytes(r.read())
            names[key] = c["name"]
        (d / "champions.json").write_text(json.dumps({"version": version, "names": names}), encoding="utf-8")
        return d
    except Exception:
        return None


def _prep(img: np.ndarray) -> np.ndarray:
    """Centre of the portrait (the HUD ring and level badge are cut away), as Lab colours."""
    h, w = img.shape[:2]
    m = 0.2
    core = img[int(h * m):int(h * (1 - m)), int(w * m):int(w * (1 - m))]
    core = cv2.resize(core, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(core, cv2.COLOR_BGR2Lab).astype(np.float32)


_icons: dict[str, np.ndarray] | None = None
_names: dict[str, str] = {}


def _load() -> dict[str, np.ndarray]:
    global _icons, _names
    if _icons is None:
        d = ensure_icons()
        _icons = {}
        if d:
            _names = json.loads((d / "champions.json").read_text(encoding="utf-8"))["names"]
            for key in _names:
                img = cv2.imread(str(d / f"{key}.png"))
                if img is not None:
                    # The HUD shows the icon zoomed in (~1.2x) inside a ring.
                    h, w = img.shape[:2]
                    c = int(h * 0.08)
                    _icons[key] = _prep(img[c:h - c, c:w - c])
    return _icons


def _score(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean(axis=(0, 1))
    b = b - b.mean(axis=(0, 1))
    return float((a * b).sum() / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-6))


def identify(portraits: list[np.ndarray]) -> dict | None:
    icons = _load()
    if not icons or not portraits:
        return None
    votes: dict[str, float] = {}
    for p in portraits:
        if p is None or p.size == 0 or float(p.std()) < 12:
            continue  # empty / black frame
        q = _prep(p)
        scored = sorted(((_score(q, ic), k) for k, ic in icons.items()), reverse=True)
        (s1, k1), (s2, _k2) = scored[0], scored[1]
        if s1 >= 0.45 and s1 - s2 >= 0.03:
            votes[k1] = votes.get(k1, 0) + s1
    if not votes:
        return None
    best = max(votes, key=votes.get)
    share = votes[best] / sum(votes.values())
    if share < 0.5:
        return None
    return {"key": best, "name": _names.get(best, best), "confidence": round(share, 2)}
