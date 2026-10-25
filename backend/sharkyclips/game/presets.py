"""Per-game presets: where the HUD shows things, and which texts mean which event.

Regions are pixel boxes on a 1920x1080 frame (x, y, w, h) and are scaled to the video's
resolution. A game update can move the HUD: fix a box in the "Game detection" page of the UI
(saved in ~/.sharkyclips/game_regions.json, merged on top of these defaults).

Text patterns are matched against OCR output after normalize() (lowercase, no accents, Turkish
ı/İ -> i), so "Hedefi Etkisiz Hale Getir" and "hedefi etkisiz hale getır" both match. Every event
lists English and Turkish client texts. Texts marked "unverified" were not seen in a real video
yet; the debug page shows the raw OCR text so they can be corrected.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .. import config

PRESETS_VERSION = 1
BASE_W, BASE_H = 1920, 1080

GAMES = {
    "delta_force": "Delta Force",
    "lol": "League of Legends",
}

# ------------------------------------------------------------------ regions

REGIONS: dict[str, dict[str, dict]] = {
    "lol": {
        # Scoreboard at the top right: team kills ("5 vs 6") and own K/D/A ("3/0/0").
        "team": {"box": [1545, 1, 72, 28], "label": "Team score"},
        "kda": {"box": [1630, 1, 110, 28], "label": "K/D/A"},
        # Announcer banners ("Double kill", "Takımından biri katledildi!").
        "announce": {"box": [560, 60, 800, 110], "label": "Announcements"},
        # Victory / defeat ("ZAFER" / "BOZGUN").
        "center": {"box": [560, 330, 800, 230], "label": "Result screen"},
        # Own champion portrait (bottom HUD), used once per game to name the champion.
        "portrait": {"box": [686, 990, 68, 68], "label": "Champion portrait"},
        # Ability bar: it disappears when the game ends, which triggers the result-screen check.
        "hud": {"box": [705, 985, 345, 95], "label": "Ability bar"},
    },
    "delta_force": {
        # Icons above the score counter: skull = kill, heartbeat = revive, handshake = assist.
        "icons": {"box": [830, 712, 260, 58], "label": "Event icons"},
        # The newest score lines ("Öldürme +100 DP"), read while a skull icon is shown.
        "lines": {"box": [700, 806, 520, 94], "label": "Score lines"},
        # Extraction result / big centre texts.
        "center": {"box": [460, 300, 1000, 400], "label": "Result screen"},
        # "Killed by" card on the right after the streamer dies ("ÖLDÜREN:", "Düşman 1-0 Sen").
        "killer": {"box": [1520, 220, 390, 720], "label": "Killer card"},
    },
}

# Icon templates (grayscale PNGs in ./templates, cut from 1080p frames) per game.
TEMPLATES: dict[str, dict[str, str]] = {
    "delta_force": {"skull": "df_skull.png", "revive": "df_revive.png", "assist": "df_assist.png"},
}


def load_templates(game: str, height: int) -> dict:
    """Icon templates scaled to the video height."""
    import cv2

    out = {}
    folder = Path(__file__).resolve().parent / "templates"
    for name, file in TEMPLATES.get(game, {}).items():
        img = cv2.imread(str(folder / file), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        s = height / BASE_H
        if abs(s - 1) > 0.01:
            img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        out[name] = img
    return out


# ------------------------------------------------------------------ text rules

# Each rule: event code -> phrases (any one matches). A phrase starting with "-" must NOT be in
# the text. Phrases are compared with normalize()d OCR text, allowing small OCR mistakes
# ("oldarme", "1pldurme" still match "oldurme"). Order matters for Delta Force score lines: the
# first matching code wins (events.DF_LINE_PRIORITY).
TEXT_RULES: dict[str, dict[str, dict[str, list[str]]]] = {
    "lol": {
        "announce": {
            "lol_pentakill": ["pentakill", "penta kill", "besli les", "besli oldurme"],
            "lol_quadrakill": ["quadra kill", "quadrakill", "dortlu les", "dortlu oldurme"],
            "lol_triplekill": ["triple kill", "triplekill", "uclu les", "uclu oldurme"],
            "lol_doublekill": ["double kill", "doublekill", "cifte les", "cift les", "cifte oldurme"],
            "lol_first_blood": ["first blood", "ilk kan"],
            "lol_shutdown": ["shutdown", "shut down", "buraya kadar", "durduruldu", "engellendi"],
            "lol_ace": ["ace", "takim yok edildi"],
            # "Baron Nashor ortaya çıktı!" = Baron spawned: not an event.
            "lol_baron": ["baron", "-ortaya", "-spawn", "-spawned", "-spawning", "-dogdu", "-cikti"],
            "lol_dragon": ["dragon", "drake", "ejder", "ejderha", "-ortaya", "-spawn", "-spawned", "-spawning",
                           "-dogdu", "-cikti"],
        },
        "center": {
            "lol_victory": ["victory", "zafer"],
            "lol_defeat": ["defeat", "bozgun"],
        },
    },
    "delta_force": {
        "lines": {
            # Seen in a Turkish client (Warfare): "Öldürme +100 DP", "Çifte Öldürme", "İntikam",
            # "Göze Göz", "Kurtarma +100 DP", "Müttefik Kurtarma +150 DP", "Yardım +30 DP".
            # English texts are unverified (no English footage yet).
            "df_multi_line": ["cifte oldurme", "uclu oldurme", "dortlu oldurme", "besli oldurme", "double kill",
                              "triple kill", "multi kill", "multikill"],
            "df_revenge": ["intikam", "goze goz", "revenge", "payback"],
            "df_kill": ["oldurme", "kill", "eliminated", "-assist", "-yardim"],
            "df_knock": ["knock", "knocked", "downed", "yere serme", "yere serildi", "devirme"],
            "df_revive": ["kurtarma", "revive", "revived", "-value", "-alue"],
            "df_assist": ["yardim", "kill assist", "assist", "-bastirma"],
        },
        "center": {
            # unverified: Operations (extraction) mode was not in the test video.
            "df_extracted": ["extraction successful", "extracted", "extraction success", "tahliye basarili",
                             "tahliye edildi", "basariyla tahliye"],
            "df_extract_failed": ["extraction failed", "mission failed", "tahliye basarisiz", "gorev basarisiz",
                                  "killed in action"],
        },
    },
}
MULTI_WORDS = {"cifte": 2, "double": 2, "uclu": 3, "triple": 3, "dortlu": 4, "quadra": 4, "besli": 5, "penta": 5}

# Words that mark an objective as the enemy's (not stolen/secured by us).
LOL_ENEMY = ["enemy", "dusman", "rakip"]
LOL_STEAL = ["steal", "stole", "stolen", "cal", "calindi", "caldi"]


# ------------------------------------------------------------------ helpers


def normalize(text: str) -> str:
    t = (text or "").replace("İ", "i").replace("I", "i").replace("ı", "i").casefold()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-z0-9/+!]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _phrase_in(phrase: str, words: list[str], fuzzy: bool = True) -> bool:
    """Phrase (normalized) in the word list; long phrases allow ~20% OCR character errors."""
    from difflib import SequenceMatcher

    pw = phrase.split()
    k = len(pw)
    for i in range(len(words) - k + 1):
        window = words[i:i + k]
        if window == pw:
            return True
        if fuzzy and len(phrase) >= 5:
            for cand in (" ".join(window), "".join(window)):
                if abs(len(cand) - len(phrase)) <= 2 and SequenceMatcher(None, cand, phrase).ratio() >= 0.8:
                    return True
    # glued words ("hedefiele", "oldurme+100" -> handled by normalize/number stripping)
    if fuzzy and k > 1 and len(phrase) >= 8:
        joined = "".join(words)
        target = phrase.replace(" ", "")
        if target in joined:
            return True
    return False


def match_rules(game: str, region: str, text: str) -> list[str]:
    """Event codes whose phrases occur in the OCR text."""
    norm = re.sub(r"[+/]?\d+", " ", normalize(text))  # drop "+100", "DP" stays a word
    words = [w for w in norm.split() if w not in ("dp", "p", "op", "0p")]
    if not words:
        return []
    out = []
    for code, phrases in TEXT_RULES.get(game, {}).get(region, {}).items():
        neg = [normalize(p[1:]) for p in phrases if p.startswith("-")]
        pos = [normalize(p) for p in phrases if not p.startswith("-")]
        if any(_phrase_in(n, words, fuzzy=False) or any(n in w for w in words) for n in neg):
            continue
        if any(_phrase_in(p, words, fuzzy=len(p) >= 5) for p in pos if p):
            out.append(code)
    return out


def multi_count(text: str) -> int | None:
    for w in normalize(text).split():
        for key, n in MULTI_WORDS.items():
            if w == key or (len(w) >= 5 and w.startswith(key[:4])):
                return n
    return None


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    def crop(self, img):
        return img[self.y:self.y + self.h, self.x:self.x + self.w]


def _overrides_path():
    return config.config_dir() / "game_regions.json"


def load_overrides() -> dict:
    try:
        return json.loads(_overrides_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_override(game: str, region: str, box: list[int] | None) -> dict:
    """Set (or with None, reset) a region box for this computer."""
    if game not in REGIONS or region not in REGIONS[game]:
        raise KeyError(f"{game}/{region}")
    data = load_overrides()
    if box is None:
        data.get(game, {}).pop(region, None)
    else:
        x, y, w, h = (int(round(float(v))) for v in box)
        if w < 4 or h < 4 or x < 0 or y < 0 or x + w > BASE_W or y + h > BASE_H:
            raise ValueError("box outside the 1920x1080 frame")
        data.setdefault(game, {})[region] = [x, y, w, h]
    path = _overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return regions(game)


def regions(game: str) -> dict[str, dict]:
    """Effective regions at 1920x1080 (defaults + this computer's fixes)."""
    out = copy.deepcopy(REGIONS.get(game, {}))
    for name, box in load_overrides().get(game, {}).items():
        if name in out and isinstance(box, list) and len(box) == 4:
            out[name]["box"] = box
            out[name]["custom"] = True
    return out


def scaled_boxes(game: str, width: int, height: int) -> dict[str, Box]:
    """Region boxes for a video of this size. Non-16:9 videos are scaled by height and centred
    (HUDs anchor to the 16:9 safe area in both games)."""
    s = height / BASE_H
    x_off = (width - BASE_W * s) / 2
    out = {}
    for name, r in regions(game).items():
        x, y, w, h = r["box"]
        X = int(round(x * s + x_off))
        Y = int(round(y * s))
        W = max(4, int(round(w * s)))
        H = max(4, int(round(h * s)))
        X = min(max(0, X), max(0, width - W))
        Y = min(max(0, Y), max(0, height - H))
        out[name] = Box(X, Y, W, H)
    return out


def digest(game: str) -> str:
    import hashlib

    payload = json.dumps({"v": PRESETS_VERSION, "r": regions(game), "t": TEXT_RULES.get(game),
                          "i": TEMPLATES.get(game)}, sort_keys=True)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]
