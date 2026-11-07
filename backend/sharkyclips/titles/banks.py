"""Per-game metadata banks: one game per project, game-specific hashtags / tags / words, and a
hard check that no title, hashtag or tag names a different game.

    project_game(project)  -> {id, name, known, why, source}: the ONE game of a project
                              (per-project override > HUD pick / detection > title + transcript)
    clip_facts(bank, c, tr) -> events (pentakill, 1v4, extraction...) and names (champion,
                              operator, map, weapon) really in this clip (game events + transcript)
    other_game(text, gid)  -> the name of another game / franchise in `text`, else None
    build_hashtags(...)    -> #channel first, #shorts, the game, then 2-4 clip-specific ones
    build_tags(...)        -> 10-20 YouTube tags (game variants, names, events, TR + EN search phrases)

Built-in banks: titles/game_banks/<id>.json. The user's changes (Studio > Games) live in
<settings>/game_banks.json as {id: {key: value}} and replace those keys of the built-in bank.
An unknown game uses only the "generic" bank: generic gaming words, never a game name.
"""

from __future__ import annotations

import functools
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from .. import config

BANKS_DIR = Path(__file__).resolve().parent / "game_banks"
BUILTIN = ("lol", "delta_force", "cs2", "valorant", "generic")
GENERIC = "generic"
CHOICES = ("auto",) + BUILTIN
BANK_VERSION = 1
MERGE_KEYS = ("terms", "events", "moments", "search", "vocab")  # dicts merged one level deep

# Games / franchises that must never show up on another game's clip (on top of every bank's
# own name + aliases). Ambiguous everyday words (Rust, Halo, Smite, Squad, Deadlock) are left out.
OTHER_FRANCHISES = [
    "Call of Duty", "CoD", "CODM", "Warzone", "Black Ops", "Modern Warfare", "Fortnite", "PUBG", "PUBG Mobile",
    "Battlegrounds", "Apex Legends", "Apex", "Overwatch", "Overwatch 2", "OW2", "Dota 2", "Dota", "Teamfight Tactics",
    "TFT", "Wild Rift", "Minecraft", "Roblox", "GTA", "Grand Theft Auto", "Elden Ring", "Team Fortress", "TF2",
    "Rainbow Six", "R6", "R6S", "Battlefield", "Escape from Tarkov", "Tarkov", "Arena Breakout", "Mobile Legends",
    "MLBB", "Rocket League", "FIFA", "EA FC", "Genshin Impact", "Genshin", "Brawl Stars", "Clash Royale",
    "Clash of Clans", "Free Fire", "Hearthstone", "World of Warcraft", "Marvel Rivals", "Hunt Showdown", "Destiny 2",
    "Halo Infinite", "Among Us", "Fall Guys", "Metin2", "Knight Online", "Wolfteam", "Zula", "Standoff 2",
    "Point Blank", "Lost Ark", "Path of Exile", "Diablo", "StarCraft", "The Finals", "Splitgate", "XDefiant",
    "Arc Raiders", "Hell Let Loose", "Rainbow Six Siege", "Paladins", "Brawlhalla", "Fortnite Battle Royale",
]
# A short name (< 5 letters) only counts as a word of its own or glued to one of these
# ("codmobile", "lolclips", "gta5"), so "apexi" or "codex" don't trip it.
SHORT_SUFFIXES = {"", "m", "mobile", "clips", "clip", "tr", "turkiye", "turkey", "highlights", "funny", "fails",
                  "fail", "moments", "esports", "pro", "shorts", "gameplay", "game", "games", "v", "online", "s",
                  "tv", "meme", "memes", "montage", "community", "news", "tips", "edit", "edits", "fan", "fans"}
# Hashtags that say nothing about the clip (and platform names on another platform's post).
SPAM_TAGS = {"viral", "fyp", "foryou", "foryoupage", "tiktok", "reels", "trending", "explore", "youtube",
             "youtubeshorts", "twitch", "subscribe", "kesfet", "keşfet", "like", "follow", "unknown", "unknowngame",
             "game", "games", "video", "clip", "clips", "shortsvideo", "shortvideo", "ytshorts", "instagram"}


# ------------------------------------------------------------------ banks


def user_file() -> Path:
    return config.config_dir() / "game_banks.json"


@functools.lru_cache(maxsize=8)
def _builtin(gid: str) -> dict:
    p = BANKS_DIR / f"{gid}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _user_all() -> dict:
    p = user_file()
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def ids() -> list[str]:
    extra = [k for k in _user_all() if k not in BUILTIN and re.fullmatch(r"[a-z0-9_]{2,24}", k)]
    return list(BUILTIN) + extra


def merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if k.startswith("_"):
            continue
        if k in MERGE_KEYS and isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def get(gid: str | None, user: bool = True) -> dict:
    """The bank of a game (built-in + the user's changes); unknown ids -> the generic bank.
    user=False: the built-in bank only."""
    gid = gid if gid in ids() else GENERIC
    mine = _user_all() if user else {}
    bank = merge(_builtin(gid), mine.get(gid) or {})
    bank["id"] = gid
    bank.setdefault("name", "")
    if gid != GENERIC:  # generic events and moments are every game's fallback
        g = merge(_builtin(GENERIC), mine.get(GENERIC) or {})
        bank["events"] = {**g.get("events", {}), **bank.get("events", {})}
        bank["moments"] = {**g.get("moments", {}), **bank.get("moments", {})}
    return bank


def validate(data: dict) -> list[str]:
    """Problems with a bank the user typed in Studio (shape only)."""
    errs = []
    if not isinstance(data, dict):
        return ["The bank must be a JSON object."]
    for k in ("aliases", "hashtags", "tags", "keywords", "ambiguous", "hints", "hashtag_kinds"):
        if k in data and not (isinstance(data[k], list) and all(isinstance(x, str) for x in data[k])):
            errs.append(f'"{k}" must be a list of texts.')
    for k in MERGE_KEYS:
        if k in data and not isinstance(data[k], dict):
            errs.append(f'"{k}" must be an object.')
    for h in data.get("hashtags") or []:
        if isinstance(h, str) and not re.fullmatch(r"#?[^\W_][\w]{0,40}", h.strip()):
            errs.append(f"Hashtag {h!r}: letters and numbers only, no spaces.")
    return errs


def save_user(gid: str, data: dict | None) -> dict:
    """Store the user's version of a bank (None = back to the built-in one)."""
    from ..project import write_json_atomic

    if not re.fullmatch(r"[a-z0-9_]{2,24}", gid or ""):
        raise ValueError("bad game id")
    allx = _user_all()
    if data is None:
        allx.pop(gid, None)
    else:
        own, full = _builtin(gid), get(gid, user=False)
        # only what differs from the built-in bank is stored (later built-in updates still arrive);
        # events / moments may come with or without the generic fallback ones
        allx[gid] = {k: v for k, v in data.items() if k != "id" and not k.startswith("_")
                     and own.get(k) != v and full.get(k) != v}
    write_json_atomic(user_file(), allx)
    return get(gid)


def is_custom(gid: str) -> bool:
    return bool(_user_all().get(gid))


# ------------------------------------------------------------------ text helpers


def norm(text: str) -> str:
    """Lowercase ASCII words ("Kai'Sa" -> "kai sa", "Warzone'da" -> "warzone da")."""
    from ..game.presets import normalize

    return normalize((text or "").replace("'", " ").replace("’", " ").replace("#", " #"))


def _tokens(text: str) -> list[str]:
    return [t.lstrip("#") for t in norm(text).split() if t.lstrip("#")]


def names(bank: dict) -> list[str]:
    return [n for n in [bank.get("name") or "", *(bank.get("aliases") or [])] if n]


def all_terms(bank: dict) -> list[tuple[str, str]]:
    out = []
    for kind, terms in (bank.get("terms") or {}).items():
        for t in terms or []:
            out.append((t, kind))
    return out


@functools.lru_cache(maxsize=32)
def _blocked(gid: str, _sig: str) -> tuple[tuple[str, str], ...]:
    """(normalized name, display name) of every OTHER game for a clip of `gid`."""
    bank = get(gid)
    own = {norm(n) for n in names(bank)} | {norm(t) for t, _k in all_terms(bank)}
    own |= {n.replace(" ", "") for n in own}
    out: dict[str, str] = {}
    for other in ids():
        if other in (gid, GENERIC):
            continue
        for n in names(get(other)):
            out.setdefault(norm(n), n)
    for n in OTHER_FRANCHISES:
        out.setdefault(norm(n), n)
    return tuple((k, v) for k, v in out.items() if k and k not in own and k.replace(" ", "") not in own)


def _sig() -> str:
    p = user_file()
    try:
        return str(p.stat().st_mtime_ns) if p.is_file() else "-"
    except OSError:
        return "-"


def other_game(text: str, gid: str | None) -> str | None:
    """The other game / franchise `text` names (title, hashtag or tag), else None."""
    toks = _tokens(text)
    if not toks:
        return None
    joined = " " + " ".join(toks) + " "
    for key, display in _blocked(gid if gid in ids() else GENERIC, _sig()):
        glued = key.replace(" ", "")
        if " " in key:
            if f" {key} " in joined or (len(glued) >= 5 and any(glued in t for t in toks)):
                return display
        elif len(glued) >= 5:
            if any(glued in t for t in toks):
                return display
        else:
            for t in toks:
                if t == glued or (t.startswith(glued) and (t[len(glued):] in SHORT_SUFFIXES or t[len(glued):].isdigit())):
                    return display
    return None


def scrub(text: str, gid: str | None) -> str:
    """Remove other games' names from model text that is passed on to later prompts."""
    if not text or not other_game(text, gid):
        return text
    out = text
    for _key, display in _blocked(gid if gid in ids() else GENERIC, _sig()):
        out = re.sub(rf"(?<!\w)(?:in |on |at |playing )?{re.escape(display)}(?:'\w+)?(?!\w)", "the game", out, flags=re.I)
    return re.sub(r"\s+", " ", out).strip()


# ------------------------------------------------------------------ which game


def detect(title: str, transcript: dict | None) -> tuple[str | None, str]:
    """Title aliases first, then the bank words the streamer says (like game.detect, for every bank)."""
    tt = " " + " ".join(_tokens(title)) + " "
    for gid in ids():
        if gid == GENERIC:
            continue
        for n in sorted(names(get(gid)), key=len, reverse=True):
            k = norm(n)
            if len(k) >= 3 and f" {k} " in tt:
                return gid, f"title: {get(gid)['name']}"
    words = _tokens(title) + _tokens(" ".join(s.get("text", "") for s in (transcript or {}).get("segments", [])))
    vocab = set(words)
    joined = " " + " ".join(words) + " "
    counts: dict[str, set[str]] = {}
    for gid in ids():
        if gid == GENERIC:
            continue
        bank = get(gid)
        amb = {norm(a) for a in bank.get("ambiguous") or []}
        hits = set()
        for term in [t for t, _k in all_terms(bank)] + list(bank.get("hints") or []) + names(bank):
            k = norm(term)
            if not k or k in amb:
                continue
            if " " in k:
                if f" {k} " in joined:
                    hits.add(k)
            elif len(k) >= 4 and (k in vocab or any(w.startswith(k) and len(w) - len(k) <= 4 for w in vocab)):
                hits.add(k)
        counts[gid] = hits
    if not counts:
        return None, "not recognized"
    best = max(counts, key=lambda k: len(counts[k]))
    other = max((len(v) for k, v in counts.items() if k != best), default=0)
    if len(counts[best]) >= 4 and len(counts[best]) >= 2 * other:
        return best, "transcript: " + ", ".join(sorted(counts[best])[:6])
    return None, "not recognized"


def project_game(project) -> dict:
    """The one game of a project for all its metadata. Never a per-clip guess."""
    from .. import game as game_mod

    meta = project.load_meta()
    choice = meta.get("metadata_game") or "auto"
    if choice != "auto" and choice in ids():
        bank = get(choice)
        return {"id": choice, "name": bank.get("name") or "", "known": choice != GENERIC,
                "why": "chosen", "source": "override", "choice": choice}
    try:
        info = game_mod.resolve(project)
    except Exception:  # noqa: BLE001 - a broken transcript must not stop the metadata
        info = {"game": None, "why": "", "choice": "auto"}
    if info.get("game") in ids():
        gid = info["game"]
        return {"id": gid, "name": get(gid)["name"], "known": True, "why": info.get("why") or "",
                "source": "hud" if info.get("choice") not in (None, "auto") else "detected", "choice": "auto"}
    tkey = f"{BANK_VERSION}|{(meta.get('transcript') or {}).get('words')}|{meta.get('title')}|{_sig()}"
    cached = meta.get("metadata_game_detect") or {}
    if cached.get("key") == tkey:
        gid, why = cached.get("game"), cached.get("why", "")
    else:
        transcript = project.load_transcript() if project.transcript_path.is_file() else None
        gid, why = detect(meta.get("title", ""), transcript)
        if transcript is not None:
            meta["metadata_game_detect"] = {"key": tkey, "game": gid, "why": why}
            project.save_meta(meta)
    if gid:
        return {"id": gid, "name": get(gid)["name"], "known": True, "why": why, "source": "detected", "choice": "auto"}
    return {"id": GENERIC, "name": "", "known": False, "why": why or "not recognized", "source": "unknown",
            "choice": "auto"}


# ------------------------------------------------------------------ clip facts

TR_NUM = {"iki": 2, "uc": 3, "dort": 4, "bes": 5}
VS_RE = re.compile(r"(?<![\w.])1\s*(?:v|vs|e|a)\s*([2-5])(?![\w.])")
VS_TR_RE = re.compile(r"\bbire (iki|uc|dort|bes)\b")


def _found(term: str, toks: list[str], joined: str) -> bool:
    k = norm(term)
    if not k:
        return False
    if " " in k:
        return f" {k} " in joined or k.replace(" ", "") in toks
    if k in toks:
        return True
    if len(k) >= 6:  # Whisper spells names loosely ("Mordekayser")
        return any(abs(len(t) - len(k)) <= 2 and t[:1] == k[:1] and SequenceMatcher(None, t, k).ratio() >= 0.85
                   for t in toks)
    return False


def clip_facts(bank: dict, c: dict, transcript: dict | None) -> dict:
    """What really happens in this clip, from the game screen and the clip's own words:
    {"events": [{key, word, label, hashtags, tags}], "terms": [{term, kind}]}."""
    from ..textutil import sentences

    text = " ".join(x["text"] for x in sentences(transcript or {}, max(0.0, c["start"] - 1), c["end"] + 1))
    toks = _tokens(text)
    joined = " " + " ".join(toks) + " "
    evs = bank.get("events") or {}
    events: list[dict] = []
    terms: list[dict] = []
    seen_ev: set[str] = set()
    seen_t: set[str] = set()

    def add_event(key: str, n=None) -> None:
        if key in seen_ev or key not in evs:
            return
        seen_ev.add(key)
        e = evs[key]
        fmt = (lambda s: s.replace("{n}", str(n or "")).strip()) if "{n}" in json.dumps(e) else (lambda s: s)
        events.append({"key": key, "word": fmt(e.get("word") or ""), "label": fmt(e.get("label") or key),
                       "search": (e.get("search") or fmt(e.get("label") or key)).lower(),
                       "hashtags": list(e.get("hashtags") or []), "tags": [fmt(t) for t in e.get("tags") or []]})

    def add_term(term: str, kind: str) -> None:
        if term.casefold() not in seen_t:
            seen_t.add(term.casefold())
            terms.append({"term": term, "kind": kind})

    by_name = {norm(t): (t, k) for t, k in all_terms(bank)}
    for r in sorted(c.get("reasons") or [], key=lambda r: r.get("t", 0)):
        code = r.get("code", "")
        if code in evs:
            add_event(code, r.get("value") if code.endswith("multikill") else None)
        v = r.get("value")
        if isinstance(v, str) and norm(v) in by_name:  # "Quadra kill with Yasuo"
            add_term(*by_name[norm(v)])
    for key, e in evs.items():
        for phrase in e.get("say") or []:
            k = norm(phrase)
            if k and (f" {k} " in joined or (len(k) >= 5 and any(t.startswith(k) and len(t) - len(k) <= 4 for t in toks))):
                add_event(key)
                break
    m = VS_RE.search(joined) or VS_TR_RE.search(joined)
    if m:
        n = TR_NUM.get(m.group(1)) or int(m.group(1))
        word = f"1v{n}"
        seen_ev.add(word)
        events.append({"key": word, "word": word, "label": f"1v{n} clutch", "search": f"1v{n} clutch", "hashtags": [f"#{word}", "#clutch"],
                       "tags": [f"{word} clutch", f"{bank.get('short') or ''} {word}".strip()]})
    amb = {norm(a) for a in bank.get("ambiguous") or []}
    for term, kind in all_terms(bank):
        if norm(term) in amb:
            continue
        if _found(term, toks, joined):
            add_term(term, kind)
    return {"events": events, "terms": terms}


def facts_text(facts: dict) -> str:
    parts = [f"event: {e['label']}" for e in facts.get("events", [])]
    kinds = {"champions": "champion", "operators": "operator", "agents": "agent", "maps": "map", "weapons": "weapon",
             "objectives": "objective", "modes": "mode"}
    parts += [f"{kinds.get(t['kind'], t['kind'].rstrip('s'))}: {t['term']}" for t in facts.get("terms", [])[:6]]
    return "; ".join(parts)


# ------------------------------------------------------------------ hashtags + tags


def _tag_word(text: str) -> str:
    return re.sub(r"[^\w]", "", str(text).replace("#", "").strip(), flags=re.UNICODE)


def _profane(text: str) -> bool:
    from ..analyze import has_profanity

    flat = re.sub(r"(?<=[a-zçğıöşü])(?=[A-ZÇĞİÖŞÜ])", " ", text)
    low = norm(text).replace(" ", "")
    return has_profanity(text) or has_profanity(flat) or any(
        r in low for r in ("fuck", "shit", "bitch", "orospu", "amina", "sikim", "siktir", "yarrak", "pussy"))


def _known_tag(word: str, lang: str) -> bool:
    """A model hashtag must be made of real words (no invented names like '#KocaoYar')."""
    from . import lexicon

    if not lexicon.available():
        return False
    parts = re.findall(r"[A-ZÇĞİÖŞÜ]?[a-zçğıöşü]+|[A-ZÇĞİÖŞÜ]+(?![a-zçğıöşü])|\d+", word) or [word]
    for p in parts:
        if p.isdigit():
            continue
        lw = lexicon.lower(p, lang)
        if not (lexicon.known_score(lw, lang) > 0 or lexicon.known_score(lw.lower(), "en") > 0):
            return False
    return True


def _lang_list(d: dict | None, lang: str) -> list[str]:
    d = d or {}
    return list(d.get(lang) or d.get("en") or [])


def build_hashtags(bank: dict, facts: dict, moment: str | None, lang: str, *, channel: list[str] | None = None,
                   llm: list[str] | None = None, exclude: list[str] | None = None, limit: int = 8) -> list[str]:
    """#channel (always first, never dropped), #shorts, the game, then 2-4 about this clip."""
    gid = bank.get("id") or GENERIC
    out: list[str] = []
    banned = {_tag_word(x).casefold() for x in exclude or [] if len(_tag_word(x)) >= 3}

    def ok(tag: str) -> bool:
        w = _tag_word(tag)
        return (1 < len(w) <= 30 and w.casefold() not in {t[1:].casefold() for t in out}
                and not other_game(w, gid) and not _profane(w))

    def add(tag: str, force: bool = False) -> bool:
        w = _tag_word(tag)
        if not w:
            return False
        if force:
            if w.casefold() in {t[1:].casefold() for t in out}:
                return False
            out.append("#" + w)
            return True
        if ok(w) and w.casefold() not in banned:
            from . import lexicon

            out.append("#" + (w.lower() if w.isascii() else lexicon.lower(w, lang)))
            return True
        return False

    chan = [h for h in channel or [] if _tag_word(h)]
    for h in chan:
        add(h, force=True)
    add("#shorts")
    tags = list(bank.get("hashtags") or [])
    generic = get(GENERIC)
    if gid == GENERIC or not tags:
        tags = list(generic.get("hashtags") or [])
    add(tags[0])
    base = len(out)
    cap = max(limit, base + 2)
    spec_max = min(4, cap - base)

    def spec_n() -> int:
        return len(out) - base

    for e in facts.get("events", [])[:3]:
        for h in e.get("hashtags", [])[:1]:
            if spec_n() < spec_max:
                add(h)
    kinds = set(bank.get("hashtag_kinds") or [])
    for t in [t for t in facts.get("terms", []) if t["kind"] in kinds][:2]:
        if spec_n() < spec_max:
            add(t["term"])
    mom = (bank.get("moments") or {}).get(moment or "") or {}
    for h in _lang_list(mom.get("hashtags"), lang)[:1]:
        if spec_n() < spec_max:
            add(h)
    rest = tags[1:]
    local = re.compile(r"tr$|turkiye|türkiye") if lang == "tr" else None
    if local:  # Turkish audience: one Turkish game tag (#loltr), the rest is international
        rest.sort(key=lambda h: 0 if local.search(h.casefold()) else 1)
        if not any(local.search(h.casefold()) for h in out[base:]) and rest and local.search(rest[0].casefold()):
            if len(out) < cap:
                add(rest[0])
    n_llm = 0
    for h in llm or []:  # at most one of the model's own, and only made of real words
        if n_llm >= 1 or spec_n() >= min(spec_max, 4) or len(out) >= cap:
            break
        w = _tag_word(h)
        if w.casefold() in SPAM_TAGS or w.casefold().startswith(("unknown", "turkish", "türk")):
            continue
        if _known_tag(w, lang) and add(w):
            n_llm += 1
    # fill: the game's other tags (the audience's language first), then generic gaming ones
    for h in rest + list(generic.get("hashtags") or []):
        if spec_n() >= 2 and len(out) >= min(cap, base + 3):
            break
        if len(out) < cap:
            add(h)
    return out


def build_tags(bank: dict, facts: dict, moment: str | None, lang: str, *, channel: list[str] | None = None,
               limit: int = 20) -> list[str]:
    """YouTube tags (no #): what people type to find this clip, in Turkish and English."""
    from .. import youtube

    gid = bank.get("id") or GENERIC
    short = bank.get("short") or ""
    langs = [lang] + [x for x in ("tr", "en") if x != lang and (lang == "tr" or x == "en")]
    out: list[str] = []

    def add(t: str) -> None:
        t = " ".join(str(t).replace("#", " ").split()).strip()
        if (t and "{" not in t and t.casefold() not in {x.casefold() for x in out}
                and not other_game(t, gid) and not _profane(t)):
            out.append(t)

    events = facts.get("events", [])
    terms = facts.get("terms", [])
    for e in events[:3]:
        for t in e.get("tags", [])[:2]:
            add(t)
    search = bank.get("search") or {}
    for t in terms[:3]:
        name = t["term"]
        add(name.lower())
        if short and short not in name.lower():
            add(f"{name.lower()} {short}")
        for lg in langs:
            tmpl = next((s for s in search.get(lg) or [] if "{term}" in s and "{event}" not in s), None)
            if tmpl:
                add(tmpl.replace("{term}", name.lower()))
    for e in events[:2]:
        for lg in langs:
            tmpl = next((s for s in search.get(lg) or [] if "{event}" in s and "{term}" not in s), None)
            if tmpl:
                add(tmpl.replace("{event}", e.get("search") or e["label"].lower()))
        if terms:
            tmpl = next((s for s in search.get("en") or [] if "{event}" in s and "{term}" in s), None)
            if tmpl:
                add(tmpl.replace("{term}", terms[0]["term"].lower()).replace("{event}", e.get("search") or e["label"].lower()))
    for c in channel or []:
        add(c.lstrip("#"))
    for t in bank.get("tags") or []:
        add(t)
    mom = (bank.get("moments") or {}).get(moment or "") or {}
    for lg in langs:
        for t in _lang_list(mom.get("tags"), lg)[:1]:
            add(t)
    for lg in langs:
        for s in search.get(lg) or []:
            if "{" not in s:
                add(s)
    if len(out) < 10 or gid == GENERIC:
        g = get(GENERIC)
        for t in g.get("tags") or []:
            add(t)
        for lg in langs:
            for s in (g.get("search") or {}).get(lg) or []:
                add(s)
    add("shorts")
    return youtube.clean_tags(out)[:limit]


def title_words(bank: dict, facts: dict, lang: str) -> dict:
    """Words for the title prompt: CAPS key words that fit this clip first, then the game's."""
    keys = [e["word"] for e in facts.get("events", []) if e.get("word")]
    keys += [k for k in bank.get("keywords") or [] if k not in keys]
    return {"keywords": keys[:14], "vocab": _lang_list(bank.get("vocab"), lang)[:14]}


def glossary_terms(bank: dict) -> list[str]:
    """The bank's names for the spelling glossary (everyday-word names like "Sona" left out)."""
    amb = {norm(a) for a in bank.get("ambiguous") or []}
    return [t for t, _k in all_terms(bank) if norm(t) not in amb]


def caps_words(bank: dict) -> list[str]:
    return [w for k in bank.get("keywords") or [] for w in k.split()]
