"""Turn raw HUD observations (from all segments, merged) into game events.

An event: {"t", "code", "value"?, "strength" 0..1, "start", "end", "source"}. start/end is the
span a clip must contain (all kills of a multikill); t is the moment itself (the last kill).
"""

from __future__ import annotations

from .presets import LOL_ENEMY, LOL_STEAL, match_rules, multi_count, normalize

# How much each event lifts the hype curve (0..1): pentakill >> double kill.
STRENGTH = {
    "lol_pentakill": 1.0, "lol_quadrakill": 0.9, "lol_triplekill": 0.75, "lol_doublekill": 0.55,
    "lol_kill": 0.4, "lol_assist": 0.12, "lol_death": 0.2,
    "lol_first_blood": 0.55, "lol_shutdown": 0.65, "lol_ace": 0.75,
    "lol_baron_steal": 0.95, "lol_dragon_steal": 0.85, "lol_baron": 0.5, "lol_dragon": 0.35,
    "lol_victory": 0.6, "lol_defeat": 0.35,
    "df_multikill": 0.6, "df_kill": 0.4, "df_revenge": 0.45, "df_knock": 0.18, "df_revive": 0.15,
    "df_assist": 0.08, "df_death": 0.3, "df_extracted": 0.8, "df_extract_failed": 0.5,
}
MULTI_NAMES = {2: "lol_doublekill", 3: "lol_triplekill", 4: "lol_quadrakill", 5: "lol_pentakill"}
LOL_MULTI_GAP = 10.0  # seconds between kills of a multikill (the game's own rule)
LOL_PENTA_GAP = 30.0  # the 5th kill may come later (if nobody else on the enemy team respawns)
DF_MULTI_GAP = 10.0
DF_LINE_PRIORITY = ["df_multi_line", "df_revenge", "df_revive", "df_assist", "df_kill", "df_knock"]


def df_multikill_strength(n: int) -> float:
    return {2: 0.65, 3: 0.85, 4: 0.95}.get(n, 1.0 if n >= 5 else 0.4)


def _ev(t: float, code: str, value=None, start: float | None = None, end: float | None = None,
        source: str = "screen", strength: float | None = None) -> dict:
    e = {"t": round(t, 2), "code": code, "strength": round(strength if strength is not None else STRENGTH[code], 3),
         "start": round(start if start is not None else t, 2), "end": round(end if end is not None else t, 2),
         "source": source}
    if value is not None:
        e["value"] = value
    return e


def _dedupe(events: list[dict], window: float) -> list[dict]:
    out: list[dict] = []
    last: dict[str, float] = {}
    for e in sorted(events, key=lambda e: e["t"]):
        if e["t"] - last.get(e["code"], -1e9) < window:
            continue
        last[e["code"]] = e["t"]
        out.append(e)
    return out


# ------------------------------------------------------------------ League of Legends


def _plausible(a: dict, b: dict) -> bool:
    dk, dd, da = b["k"] - a["k"], b["d"] - a["d"], b["a"] - a["a"]
    return min(dk, dd, da) >= 0 and dk <= 5 and dd <= 3 and da <= 8


def lol_kda_series(obs: list[dict]) -> list[dict]:
    """Confirmed K/D/A values in time order (with the time each was first seen). A new value
    counts once a later reading agrees with it (the same value, or one that can follow it), so
    a single misread never becomes a kill. A confirmed drop to ~0/0/0 is a new game."""
    readings = sorted((o for o in obs if o["kind"] == "kda"), key=lambda o: o["t"])
    out: list[dict] = []
    cur = None
    for i, o in enumerate(readings):
        key = (o["k"], o["d"], o["a"])
        if cur is not None and key == (cur["k"], cur["d"], cur["a"]):
            continue
        nxt = readings[i + 1] if i + 1 < len(readings) else None
        if nxt is not None and (nxt["k"], nxt["d"], nxt["a"]) != key and not _plausible(o, nxt):
            continue  # not confirmed by the next reading
        if cur is None:
            if sum(key) <= 3:
                cur = o
                out.append(o)
        elif _plausible(cur, o):
            cur = o
            out.append(o)
        elif sum(key) <= 2 and nxt is not None and (nxt["k"], nxt["d"], nxt["a"]) == key:
            cur = {**o, "new_game": True}
            out.append(cur)
    return out


# Banners the game shows for every player: they only count when the streamer got a kill
# at the same moment.
GLOBAL_BANNERS = {"lol_first_blood", "lol_shutdown", "lol_doublekill", "lol_triplekill", "lol_quadrakill",
                  "lol_pentakill"}


def lol_events(obs: list[dict], game_name: str = "lol") -> list[dict]:
    events: list[dict] = []
    series = lol_kda_series(obs)
    teams = sorted((o for o in obs if o["kind"] == "team"), key=lambda o: o["t"])
    kills: list[float] = []
    prev = None
    for o in series:
        if prev is not None and not o.get("new_game"):
            dk, dd, da = o["k"] - prev["k"], o["d"] - prev["d"], o["a"] - prev["a"]
            kills += [o["t"]] * dk
            if da > 0:
                events.append(_ev(o["t"], "lol_assist", value=str(da) if da > 1 else None, source="kda"))
            if dd > 0:
                events.append(_ev(o["t"], "lol_death", source="kda"))
        prev = o

    # Multikills from kill timing (works for any client language).
    chains: list[list[float]] = []
    for t in kills:
        if chains and len(chains[-1]) < 5 and (t - chains[-1][-1] <= LOL_MULTI_GAP
                                               or (len(chains[-1]) == 4 and t - chains[-1][-1] <= LOL_PENTA_GAP)):
            chains[-1].append(t)
        else:
            chains.append([t])
    for ch in chains:
        if len(ch) >= 2:
            events.append(_ev(ch[-1], MULTI_NAMES[len(ch)], value=str(len(ch)), start=ch[0], end=ch[-1], source="kda"))
        else:
            events.append(_ev(ch[0], "lol_kill", source="kda"))
    # First blood: the streamer's kill that made the game's first point.
    if kills:
        t = kills[0]
        seen = [x for x in teams if x["t"] <= t + 3]
        if seen and all(x["ally"] + x["enemy"] <= 1 for x in seen):
            events.append(_ev(t, "lol_first_blood", source="kda"))

    # Announcer banners and result screens (OCR text).
    for o in obs:
        if o["kind"] != "text":
            continue
        for code in match_rules(game_name, o["region"], o["text"]):
            norm = normalize(o["text"])
            if code in GLOBAL_BANNERS and not any(abs(o["t"] - c) <= 6 for c in kills):
                continue  # announced for another player
            if code in ("lol_baron", "lol_dragon"):
                if any(w.startswith(e[:4]) for w in norm.split() for e in LOL_ENEMY):
                    continue  # the enemy took it
                if any(w in norm for w in LOL_STEAL):
                    code = code + "_steal"
            events.append(_ev(o["t"], code, source="banner", value=o["text"][:60]))

    # A banner multikill confirms (or upgrades) the K/D/A one near it; keep one per moment.
    multi = [e for e in events if e["code"] in MULTI_NAMES.values()]
    multi.sort(key=lambda e: (-e["strength"], e["t"]))
    kept: list[dict] = []
    for e in multi:
        if any(abs(e["t"] - k["t"]) <= 12 for k in kept):
            continue
        kept.append(e)
    others = [e for e in events if e["code"] not in MULTI_NAMES.values()]
    for e in kept:  # single kills inside a multikill are part of it
        others = [o for o in others if not (o["code"] == "lol_kill" and e["start"] - 1 <= o["t"] <= e["end"] + 1)]
    windows = {"lol_victory": 60, "lol_defeat": 60, "lol_first_blood": 300}
    out = kept + [e for e in others if e["code"] not in windows and e["source"] != "banner"]
    for code, w in windows.items():
        out += _dedupe([e for e in others if e["code"] == code], w)
    out += _dedupe([e for e in others if e["source"] == "banner" and e["code"] not in windows], 8)
    return sorted(out, key=lambda e: e["t"])


# ------------------------------------------------------------------ Delta Force


def df_events(obs: list[dict], game_name: str = "delta_force") -> list[dict]:
    """Kills from the skull icon (one "episode" per time it appears), counted with the score
    lines read while it is shown ("Öldürme +100 DP" x2 = two kills at once)."""
    obs = sorted(obs, key=lambda o: o["t"])
    events: list[dict] = []
    onsets = [o["t"] for o in obs if o["kind"] == "icon" and o["icon"] == "skull"]
    reads = [o for o in obs if o["kind"] == "lines"]
    kills: list[tuple[float, int]] = []  # (time, kills at that moment)
    for i, t0 in enumerate(onsets):
        t1 = min(onsets[i + 1] if i + 1 < len(onsets) else 1e12, t0 + 4.0)
        n, revenge = 1, False
        for r in reads:
            if not t0 <= r["t"] < t1:
                continue
            codes = [next((c for c in DF_LINE_PRIORITY if c in match_rules(game_name, "lines", x)), None)
                     for x in r["texts"]]
            n = max(n, codes.count("df_kill"))
            for x, c in zip(r["texts"], codes):
                if c == "df_multi_line":
                    n = max(n, multi_count(x) or 2)
                revenge = revenge or c == "df_revenge"
        kills.append((t0, min(n, 5)))
        if revenge:
            events.append(_ev(t0, "df_revenge", source="icon"))
    for o in obs:
        if o["kind"] == "icon" and o["icon"] in ("revive", "assist"):
            events.append(_ev(o["t"], f"df_{o['icon']}", source="icon"))
        elif o["kind"] == "text" and o["region"] == "center":
            for code in match_rules(game_name, "center", o["text"]):
                events.append(_ev(o["t"], code, source="screen", value=o["text"][:60]))
        elif o["kind"] == "killcard":
            events.append(_ev(o["t"], "df_death", source="screen"))

    chains: list[list[tuple[float, int]]] = []
    for k in kills:
        if chains and k[0] - chains[-1][-1][0] <= DF_MULTI_GAP:
            chains[-1].append(k)
        else:
            chains.append([k])
    for ch in chains:
        n = sum(c for _, c in ch)
        if n >= 2:
            events.append(_ev(ch[-1][0], "df_multikill", value=str(n), start=ch[0][0], end=ch[-1][0], source="icon",
                              strength=df_multikill_strength(n)))
        else:
            events.append(_ev(ch[0][0], "df_kill", source="icon"))
    screen = [e for e in events if e["code"] in ("df_extracted", "df_extract_failed")]
    deaths = [e for e in events if e["code"] == "df_death"]
    rest = [e for e in events if e["code"] not in ("df_extracted", "df_extract_failed", "df_death")]
    return sorted(rest + _dedupe(screen, 60) + _dedupe(deaths, 15), key=lambda e: e["t"])


def build_events(game: str, obs: list[dict]) -> list[dict]:
    if game == "lol":
        return lol_events(obs)
    if game == "delta_force":
        return df_events(obs)
    return []
