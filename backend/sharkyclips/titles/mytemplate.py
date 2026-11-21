"""My style template (1.2.63): the creator's fixed title / description / hashtag layout.

The template sits on top of My style (style.py). While it is on, every gaming title, description
and hashtag list follows it, in every output language (the fixed words are translated, the
creator's social block is used word for word):

  titles       3 options, ALL CAPS with the language's own letters (Turkish İ Ş Ğ Ü Ö Ç, never
               "MUKEMMEL"), energetic, 1-2 emojis at the end; story games add "(BÖLÜM N)" on long
               videos (episode number counted up per series, editable); Shorts end with "#Shorts";
               at most 100 characters
  description  "Selamlar! Bu bölümde ..." + 3-5 sentences (Shorts: 1-2) about what really happened,
               ending "... iyi seyirler!"; then the CTA line, the social block, "Etiketler:" and
               9-13 hashtags
  hashtags     game, characters, role / mode, a community tag, the channel tag, one "...Sekansı"
               tag, #BölümN for a series, a platform tag when known, #Shorts on Shorts

Only facts from the transcript, the game screen, the project name or what the creator typed are
used: a name that is not in those sources is a rule problem and the text is written again.

Storage: ~/.sharkyclips/style/template.json (user data, never in the repo). The repo ships only
style_template.example.json, a generic example without personal links.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from pathlib import Path

from .. import config

VERSION = 1
EXAMPLE_FILE = Path(__file__).resolve().parent / "style_template.example.json"
TITLE_LIMIT = 100
TITLE_OPTIONS = 3
HASHTAGS_MIN, HASHTAGS_MAX = 9, 13
_lock = threading.RLock()

# The fixed words of the template per output language (the creator's own Turkish words come
# from the template file; the other languages are translations of the same structure).
STRINGS: dict[str, dict[str, str]] = {
    "tr": {"intro": "Selamlar! Bu bölümde", "outro": "iyi seyirler!",
           "cta": "Kanala abone olmayı, videoyu beğenmeyi ve yorum yapmayı unutmayın! 🚀",
           "label": "Etiketler:", "episode": "BÖLÜM {n}", "episode_tag": "Bölüm{n}", "combo": "Sekansı",
           "community": "#GamingTR"},
    "en": {"intro": "Hey everyone! In this episode", "outro": "enjoy the video!",
           "cta": "Don't forget to subscribe to the channel, like the video and leave a comment! 🚀",
           "label": "Tags:", "episode": "EPISODE {n}", "episode_tag": "Episode{n}", "combo": "Moments",
           "community": "#Gaming"},
    "es": {"intro": "¡Hola a todos! En este episodio", "outro": "¡que lo disfruten!",
           "cta": "¡No olviden suscribirse al canal, darle like al video y dejar un comentario! 🚀",
           "label": "Etiquetas:", "episode": "EPISODIO {n}", "episode_tag": "Episodio{n}", "combo": "Momentos",
           "community": "#GamingEspañol"},
    "pt": {"intro": "Fala, galera! Neste episódio", "outro": "bom vídeo!",
           "cta": "Não esqueçam de se inscrever no canal, curtir o vídeo e comentar! 🚀",
           "label": "Tags:", "episode": "EPISÓDIO {n}", "episode_tag": "Episodio{n}", "combo": "Momentos",
           "community": "#GamingBR"},
    "de": {"intro": "Hallo zusammen! In dieser Folge", "outro": "viel Spaß beim Zuschauen!",
           "cta": "Vergesst nicht, den Kanal zu abonnieren, das Video zu liken und einen Kommentar dazulassen! 🚀",
           "label": "Tags:", "episode": "FOLGE {n}", "episode_tag": "Folge{n}", "combo": "Momente",
           "community": "#GamingDeutsch"},
    "fr": {"intro": "Salut tout le monde ! Dans cet épisode", "outro": "bon visionnage !",
           "cta": "N'oubliez pas de vous abonner à la chaîne, de liker la vidéo et de laisser un commentaire ! 🚀",
           "label": "Tags :", "episode": "ÉPISODE {n}", "episode_tag": "Episode{n}", "combo": "Moments",
           "community": "#GamingFR"},
    "hu": {"intro": "Sziasztok! Ebben a részben", "outro": "jó szórakozást!",
           "cta": "Ne felejtsetek el feliratkozni a csatornára, lájkolni a videót és kommentelni! 🚀",
           "label": "Címkék:", "episode": "{n}. RÉSZ", "episode_tag": "Rész{n}", "combo": "Pillanatok",
           "community": "#GamingHU"},
    "ru": {"intro": "Всем привет! В этом выпуске", "outro": "приятного просмотра!",
           "cta": "Не забудьте подписаться на канал, поставить лайк и написать комментарий! 🚀",
           "label": "Теги:", "episode": "ЧАСТЬ {n}", "episode_tag": "Часть{n}", "combo": "Моменты",
           "community": "#ИгрыРу"},
    "ar": {"intro": "مرحبًا بالجميع! في هذه الحلقة", "outro": "مشاهدة ممتعة!",
           "cta": "لا تنسوا الاشتراك في القناة والإعجاب بالفيديو وكتابة تعليق! 🚀",
           "label": "الوسوم:", "episode": "الحلقة {n}", "episode_tag": "الحلقة{n}", "combo": "لقطات",
           "community": "#ألعاب"},
    "zh": {"intro": "大家好！这一期", "outro": "祝大家观看愉快！",
           "cta": "别忘了订阅频道、点赞视频并留言评论！🚀",
           "label": "标签：", "episode": "第{n}集", "episode_tag": "第{n}集", "combo": "高光",
           "community": "#游戏"},
    "ja": {"intro": "みなさん、こんにちは！今回は", "outro": "ぜひ最後まで楽しんでください！",
           "cta": "チャンネル登録、高評価、コメントをお忘れなく！🚀",
           "label": "タグ：", "episode": "第{n}話", "episode_tag": "第{n}話", "combo": "名場面",
           "community": "#ゲーム実況"},
}
NO_CAPS = ("ar", "zh", "ja")
SENTENCE_END = re.compile(r"(?<=[.!?…。！？])\s*")

# Games the template knows by name (the project name / what the creator typed), so a game
# without a full game profile (Battlefield 6, Rematch, Spider-Man 2) is still named and tagged.
# story: a story game -> (BÖLÜM N) + #BölümN, counted per series.
GAMES: dict[str, dict] = {
    "lol": {"name": "League of Legends", "tag": "#LeagueOfLegends", "aliases": ["league of legends", "lol"],
            "community": {"tr": ["#LolTürkiye", "#LeagueOfLegendsTR"]}, "seq_from": "character"},
    "delta_force": {"name": "Delta Force", "tag": "#DeltaForce", "aliases": ["delta force"],
                    "community": {"tr": ["#DeltaForceTR"]}},
    "valorant": {"name": "Valorant", "tag": "#Valorant", "aliases": ["valorant"],
                 "community": {"tr": ["#ValorantTR"]}},
    "cs2": {"name": "Counter-Strike 2", "tag": "#CS2", "aliases": ["counter-strike 2", "counter strike 2", "cs2"],
            "community": {"tr": ["#CS2TR"]}},
    "battlefield_6": {"name": "Battlefield 6", "tag": "#Battlefield6",
                      "aliases": ["battlefield 6", "battlefield6", "bf6"], "community": {"tr": ["#BattlefieldTR"]}},
    "rematch": {"name": "Rematch", "tag": "#Rematch", "aliases": ["rematch"], "community": {"tr": ["#RematchTR"]}},
    "spider_man_2": {"name": "Marvel's Spider-Man 2", "short": "Spider-Man 2", "tag": "#SpiderMan2",
                     "aliases": ["marvel's spider-man 2", "spider-man 2", "spiderman 2", "spider man 2"],
                     "community": {"tr": ["#SpiderMan2TR"]}, "story": True, "platform": "#PS5"},
}
PLATFORM_WORDS = {"ps5": "#PS5", "playstation 5": "#PS5", "ps4": "#PS4", "xbox": "#Xbox", "pc": "#PC",
                  "steam deck": "#SteamDeck", "switch": "#NintendoSwitch"}
ROLE_WORDS = {"jungle": "#Jungle", "orman": "#Jungle", "top lane": "#TopLane", "mid lane": "#MidLane",
              "bot lane": "#BotLane", "adc": "#ADC", "support": "#Support", "supp": "#Support",
              "ranked": "#Ranked", "dereceli": "#Ranked", "aram": "#ARAM", "duo": "#Duo",
              "conquest": "#Conquest", "breakthrough": "#Breakthrough", "battle royale": "#BattleRoyale",
              "5v5": "#5v5", "hikaye": "#Hikaye", "story": "#Story"}
NAME_KINDS = ("champion", "champions", "operator", "operators", "agent", "agents", "class", "character",
              "characters", "hero", "heroes", "legend", "legends")


# ------------------------------------------------------------------ storage


def path() -> Path:
    return config.config_dir() / "style" / "template.json"


def _read(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _hashtag(h) -> str:
    w = re.sub(r"[^\w]", "", str(h or "").replace("#", ""), flags=re.UNICODE)[:40]
    return f"#{w}" if w else ""


def _clean_block(text) -> str:
    lines = [ln.rstrip() for ln in str(text or "").replace("\r", "").split("\n")]
    out = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", out)[:1500]


def clean(d: dict) -> dict:
    d = d if isinstance(d, dict) else {}
    words = [" ".join(str(w).split())[:30] for w in d.get("title_words") or [] if str(w).strip()][:20]
    ex = [" ".join(str(t).split())[:TITLE_LIMIT + 20] for t in d.get("title_examples") or [] if str(t).strip()][:12]
    series = {}
    for k, v in (d.get("series") or {}).items():
        k = re.sub(r"[^a-z0-9_]", "", str(k).lower())[:40]
        try:
            n = int((v or {}).get("next") or 1)
        except (TypeError, ValueError, AttributeError):
            n = 1
        if k:
            series[k] = {"next": max(1, min(9999, n))}
    story = [re.sub(r"[^a-z0-9_]", "", str(g).lower())[:40] for g in d.get("story_games") or []]
    comm = {}
    for k, v in (d.get("community_tags") or {}).items():
        tags = [t for t in (_hashtag(x) for x in (v if isinstance(v, list) else [v])) if t][:3]
        if tags:
            comm[re.sub(r"[^a-z0-9_]", "", str(k).lower())[:40] or "default"] = tags
    cta = d.get("cta") if isinstance(d.get("cta"), dict) else {}
    return {"version": VERSION, "enabled": bool(d.get("enabled", False)),
            "lang": str(d.get("lang") or "tr")[:5],
            "channel_tag": _hashtag(d.get("channel_tag")),
            "social_block": _clean_block(d.get("social_block")),
            "cta": {k: " ".join(str(v).split())[:300] for k, v in cta.items() if k in STRINGS and str(v).strip()},
            "shorts_socials": d.get("shorts_socials") is not False,
            "title_words": words, "title_examples": ex,
            "community_tags": comm, "story_games": [g for g in dict.fromkeys(story) if g],
            "series": series}


def exists() -> bool:
    return path().is_file()


def example() -> dict:
    return clean(json.loads(EXAMPLE_FILE.read_text(encoding="utf-8")))


def load() -> dict:
    """The creator's template (the generic example, switched off, when there is none yet)."""
    with _lock:
        return clean(_read(path())) if exists() else {**example(), "enabled": False}


def save(data: dict) -> dict:
    keys = ("enabled", "lang", "channel_tag", "social_block", "cta", "shorts_socials", "title_words",
            "title_examples", "community_tags", "story_games", "series")
    with _lock:
        cur = _read(path()) if exists() else example()
        merged = {**cur, **{k: v for k, v in (data or {}).items() if k in keys}}
        out = clean(merged)
        p = path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)
        return out


def digest() -> str:
    t = load()
    if not t["enabled"]:
        return "-"
    keep = {k: v for k, v in t.items() if k != "series"}
    return hashlib.sha1(json.dumps([VERSION, keep], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]


def strings(lang: str, t: dict | None = None) -> dict:
    t = t or load()
    s = dict(STRINGS.get(lang) or STRINGS["en"])
    if t["cta"].get(lang):
        s["cta"] = t["cta"][lang]
    return s


def resolved(lang: str | None) -> dict | None:
    """What the metadata writers need for this output language (None when the template is off)."""
    t = load()
    if not t["enabled"]:
        return None
    lang = lang if lang in STRINGS else "en"
    return {**t, "out_lang": lang, "s": strings(lang, t), "episode": None, "series_key": None, "game": None,
            "platform": None}


# ------------------------------------------------------------------ games + episodes


def _norm(text: str) -> str:
    t = str(text or "").lower().replace("’", "'")
    return " " + " ".join(re.findall(r"[\w'-]+", t)) + " "


def detect_game(text: str) -> str | None:
    """A game named in the project name / what the creator typed ("Battlefield 6 conquest")."""
    n = _norm(text)
    best = None
    for gid, g in GAMES.items():
        for a in g["aliases"]:
            if f" {a} " in n and (best is None or len(a) > best[1]):
                best = (gid, len(a))
    return best[0] if best else None


def game_info(gid: str | None, name: str = "") -> dict:
    g = GAMES.get(gid or "")
    if g:
        return {"id": gid, **g}
    if not name:
        return {}
    camel = "".join(p[:1].upper() + p[1:] for p in re.findall(r"[^\W_]+", name))
    return {"id": gid or "", "name": name, "tag": f"#{camel}", "aliases": [], "community": {}}


def is_story(gid: str | None, t: dict | None = None) -> bool:
    t = t or load()
    return bool(gid) and (gid in t["story_games"] or bool((GAMES.get(gid) or {}).get("story")))


def platform_of(text: str, gid: str | None = None) -> str | None:
    n = _norm(text)
    for w, tag in PLATFORM_WORDS.items():
        if f" {w} " in n:
            return tag
    return (GAMES.get(gid or "") or {}).get("platform")


def episode(project, gid: str | None, *, assign: bool = True) -> dict | None:
    """{series, n} of a story-game project. The first time, the series' next number is taken
    and counted up; later the project keeps its number (the creator can change it)."""
    t = load()
    if not t["enabled"] or not is_story(gid, t):
        return None
    meta = project.load_meta()
    ep = meta.get("episode") if isinstance(meta.get("episode"), dict) else None
    if ep and ep.get("n"):
        return {"series": ep.get("series") or gid, "n": int(ep["n"])}
    if not assign:
        return None
    with _lock:
        t = load()
        key = gid or "series"
        n = (t["series"].get(key) or {}).get("next") or 1
        series = dict(t["series"])
        series[key] = {"next": n + 1}
        save({"series": series})
    meta = project.load_meta()  # re-read: another job may have saved meanwhile
    meta["episode"] = {"series": key, "n": n}
    project.save_meta(meta)
    return {"series": key, "n": n}


def set_episode(project, n: int | None, series: str | None = None) -> dict | None:
    """The creator's own episode number (None removes it). The series' next number never goes
    below this one + 1, so the next episode continues from here."""
    meta = project.load_meta()
    if not n:
        meta.pop("episode", None)
        project.save_meta(meta)
        return None
    n = max(1, min(9999, int(n)))
    old = meta.get("episode") if isinstance(meta.get("episode"), dict) else {}
    key = re.sub(r"[^a-z0-9_]", "", str(series or old.get("series") or "series").lower())[:40] or "series"
    meta["episode"] = {"series": key, "n": n}
    project.save_meta(meta)
    with _lock:
        t = load()
        cur = (t["series"].get(key) or {}).get("next") or 1
        if n + 1 > cur:
            save({"series": {**t["series"], key: {"next": n + 1}}})
    return meta["episode"]


def for_project(p: dict | None, project, game: dict, lang: str) -> dict | None:
    """The My style profile with the project's template data (episode, game, platform)."""
    if p is None or not p.get("template"):
        return p
    gid = game.get("id") if game.get("known") else None
    meta = project.load_meta()
    title = meta.get("title") or ""
    gid = gid or detect_game(title)
    tpl = dict(p["template"])
    tpl["game"] = game_info(gid, game.get("name") if game.get("known") else "")
    ep = episode(project, gid)
    tpl["episode"] = ep["n"] if ep else None
    tpl["series_key"] = ep["series"] if ep else None
    tpl["platform"] = platform_of(title, gid)
    tpl["project_title"] = title
    try:
        from . import banks

        tpl["game_terms"] = banks.glossary_terms(banks.get(gid)) if gid else []
    except Exception:  # noqa: BLE001 - names are a bonus for the facts check
        tpl["game_terms"] = []
    return {**p, "template": tpl}


def project_game(project, game: dict) -> dict:
    """banks.project_game, plus a game the template knows from the project name."""
    if game.get("known"):
        return game
    gid = detect_game(project.load_meta().get("title") or "")
    if not gid:
        return game
    g = GAMES[gid]
    return {**game, "id": gid, "name": g["name"], "known": True, "why": f"title: {g['name']}", "source": "detected"}


# ------------------------------------------------------------------ titles

_I_ONLY = str.maketrans({"İ": "I", "ı": "i", "I": "I", "i": "i"})
# Short words the dictionary check skips (< 4 letters) or that are often written without the
# Turkish letters in capitals.
TR_CAPS_FIX = {"BIR": "BİR", "ILE": "İLE", "IKI": "İKİ", "ICIN": "İÇİN", "ISTE": "İŞTE", "IYI": "İYİ",
               "DORT": "DÖRT", "UC": "ÜÇ", "BES": "BEŞ", "SIZ": "SİZ", "BIZ": "BİZ", "GIBI": "GİBİ",
               "DEGIL": "DEĞİL", "COK": "ÇOK", "IKINCI": "İKİNCİ", "UCUNCU": "ÜÇÜNCÜ", "SIMDI": "ŞİMDİ"}


def repair_tr(text: str, protected: set[str] | frozenset[str] = frozenset()) -> tuple[str, list[tuple[str, str]]]:
    """Turkish letters put back ("MUKEMMEL" -> "MÜKEMMEL", "DUMDUZ" -> "DÜMDÜZ"). An English word
    / name whose only change would be I -> İ stays as it is ("SCORPION", "VILLAIN")."""
    from . import lexicon

    fixes = []

    def sub(m: re.Match) -> str:
        w = m.group(0)
        if lexicon.lower(w, "tr") in protected or w.lower() in protected:
            return w
        if w in TR_CAPS_FIX:
            fixes.append((w, TR_CAPS_FIX[w]))
            return TR_CAPS_FIX[w]
        better = lexicon.best_spelling(w, "tr")
        if not better or better == w:
            return w
        if better.translate(_I_ONLY).upper() == w.translate(_I_ONLY).upper() and w.isascii() and lexicon.zipf(w.lower(), "en") >= 2.5:
            return w
        fixes.append((w, better))
        return better

    return re.sub(r"[^\W\d_]+", sub, text), fixes


def episode_text(tpl: dict) -> str:
    return tpl["s"]["episode"].format(n=tpl["episode"]) if tpl.get("episode") else ""


EPISODE_RE = re.compile(r"^(?:B[ÖO]L[ÜU]M|EPISODE|EPISODIO|EPISÓDIO|FOLGE|ÉPISODE|PART|PARTE|ЧАСТЬ|RÉSZ)\s*\d+$|^\d+\.\s*RÉSZ$"
                        r"|^第\d+[集話]$|^الحلقة\s*\d+$", re.I)


def finish_title(core: str, fmt: str, tpl: dict, lang: str, moment: str | None = None,
                 protected: set[str] | frozenset[str] = frozenset(),
                 names: set[str] | frozenset[str] | None = None) -> str:
    """A fixed My style title in the template's layout:
    BODY (CONTEXT) 🔥😱 (BÖLÜM 9) #Shorts - emojis last before the episode / #Shorts, <= 100."""
    from . import style

    body, paren, em = style.split_title(core)
    if paren and EPISODE_RE.match(paren.strip()):
        paren = ""  # the model's own episode guess: the real number is added below
    if lang == "tr":
        body, _f = repair_tr(body, protected)
        paren, _f = repair_tr(paren, protected)
    if lang not in NO_CAPS:
        body, paren = style.upper(body, lang), style.upper(paren, lang)
        names = {x for x in (protected if names is None else names) if x.isascii() and len(x) >= 2}
        if names:  # an English name keeps the English capital I ("MASTER YI", not "MASTER Yİ")
            def _en(m: re.Match) -> str:
                w = m.group(0)
                fold = w.replace("İ", "I").replace("ı", "i").lower()
                return fold.upper() if fold in names else w

            body = re.sub(r"[^\W\d_]+", _en, body)
            paren = re.sub(r"[^\W\d_]+", _en, paren)
    em = [e for e in dict.fromkeys(em)][:2]
    if not em:
        em = [style.MOOD_EMOJI.get(moment or "", style.MOOD_EMOJI["other"])[0]]
    tail = "".join(em)
    ep = f" ({episode_text(tpl)})" if fmt == "long" and tpl.get("episode") else ""
    shorts = " #Shorts" if fmt == "short" else ""

    def build(b: str, p: str) -> str:
        return f"{b}{f' ({p})' if p else ''} {tail}{ep}{shorts}".strip()

    out = build(body, paren)
    if len(out) > TITLE_LIMIT and paren:
        out = build(body, "")
    if len(out) > TITLE_LIMIT:
        room = TITLE_LIMIT - len(build("", "")) - 2
        cut = body[:room].rsplit(" ", 1)[0].rstrip(" ,;:-")
        out = build(cut if cut.endswith(("!", "?", "...", "…")) else cut + "!", "")
    return out


def check_title(title: str, fmt: str, tpl: dict, lang: str, clip_text: str | None = None) -> list[str]:
    """Template problems of one finished title ([] = fine). clip_text: a censored swear is only
    allowed when a swear was really said in the clip."""
    from . import style

    errs = []
    if clip_text is not None and style.has_censored(title) and \
            not any(style.is_swear(w, lang) for w in re.findall(r"[^\W\d_]+", clip_text)):
        errs.append("no swear words: nobody swore in this clip")
    if len(title) > TITLE_LIMIT:
        errs.append(f"at most {TITLE_LIMIT} characters")
    rest = title
    if fmt == "short":
        if not title.endswith(" #Shorts"):
            errs.append('a Shorts title ends with "#Shorts"')
        rest = title[: -len(" #Shorts")] if title.endswith(" #Shorts") else title
    ep = episode_text(tpl)
    if fmt == "long" and ep:
        if not rest.endswith(f"({ep})"):
            errs.append(f'a story episode title ends with "({ep})"')
        rest = rest[: -len(f"({ep})")].rstrip() if rest.endswith(f"({ep})") else rest
    em_tail = re.search(r"((?:" + style.EMOJI_CLUSTER.pattern + r"))+\s*$", rest)
    n = len(style.emojis(em_tail.group(0))) if em_tail else 0
    if not 1 <= n <= 2:
        errs.append("end with 1-2 fitting emojis")
    if len(style.emojis(rest)) > 2:
        errs.append("at most 2 emojis")
    if style.HASHTAG_RE.search(rest):
        errs.append("no hashtags in the title (only #Shorts at the end of a Short)")
    if lang == "tr":
        plain = style.strip_emojis(rest)
        _fixed, wrong = repair_tr(plain)
        if wrong:
            errs.append("write the Turkish letters (İ, Ş, Ğ, Ü, Ö, Ç): " + ", ".join(f"{a} -> {b}" for a, b in wrong[:3]))
    if re.search(r"tiktok", title, re.I):
        errs.append("never mention TikTok")
    return errs


def title_rules_text(tpl: dict, fmt: str) -> list[str]:
    s = tpl["s"]
    lines = [
        "THE CREATOR'S TEMPLATE (follow it exactly):",
        f"- write {TITLE_OPTIONS} strong options: energetic, like a hyped streamer; the app writes them in CAPITALS "
        "with the language's own letters",
        "- one or two short punchy sentences ending with \"!\" (or \"?!\"), then 1-2 fitting emojis at the very end",
        "- an optional short context in brackets before the emojis, like (EFORSUZ MASTER YI)",
    ]
    if tpl["title_words"]:
        lines.append("- the creator's typical words (use one when it really fits): " + ", ".join(tpl["title_words"]))
    if tpl["title_examples"]:
        lines.append("- the creator's own titles (copy ONLY the style, never their names or events):")
        lines += [f"  {x}" for x in tpl["title_examples"][:6]]
    if fmt == "long" and tpl.get("episode"):
        lines.append(f"- the app adds \"({episode_text(tpl)})\" at the end: never write an episode number yourself")
    if fmt == "short":
        lines.append('- the app adds "#Shorts" at the end: never write hashtags yourself')
    lines += ["- ONLY facts from the clip lines, the game facts or the project name: never invent quest names, "
              "champions, characters or events; when unsure, keep it general",
              f"- {s['intro']!r} is for the description, not the title"]
    return lines


# ------------------------------------------------------------------ descriptions


def desc_schema(fmt: str) -> dict:
    lo, hi = (1, 2) if fmt == "short" else (3, 5)
    return {"type": "object", "properties": {
        "sentences": {"type": "array", "minItems": lo, "maxItems": hi + 1,
                      "items": {"type": "string", "minLength": 8, "maxLength": 260}},
        "mood_hashtags": {"type": "array", "maxItems": 6, "items": {"type": "string", "maxLength": 30}},
        "search_tags": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 60}},
    }, "required": ["sentences", "mood_hashtags", "search_tags"]}


def description_task(tpl: dict, *, fmt: str, game_name: str, what_happens: str, facts: str, clip_text: str,
                     title: str, lang_label: str, terms: list[str], problems: list[str]) -> str:
    s = tpl["s"]
    lo, hi = (1, 2) if fmt == "short" else (3, 5)
    parts = [f"TASK: write the YouTube {'Shorts' if fmt == 'short' else 'video'} description in {lang_label}, "
             "in the creator's own voice (first person: I / we).",
             f"What happens: {what_happens}", f"Game: {game_name or 'unknown (never name a game)'}",
             f"Project name (typed by the creator): {tpl.get('project_title') or '-'}"]
    if facts:
        parts.append(f"Facts (reliable): {facts}")
    parts += [f"Chosen title: {title}", f"What is said in the clip:\n{clip_text[:1500]}", "",
              "Return:",
              f"- sentences: {lo}-{hi} sentences telling what happened (characters / champions, the duo or team, the key "
              f"moments). The app puts \"{s['intro']}\" in front of the FIRST sentence, so the first sentence continues "
              f"it (e.g. \"... Master Yi ile jungle'a girdik ve ...\" after \"Bu bölümde\"). The LAST sentence ends with "
              f"\"{s['outro']}\" (e.g. \"..., {s['outro']}\").",
              "- mood_hashtags: 2-4 event / mood hashtags in CamelCase, real words",
              "- search_tags: 6-8 natural search phrases people type",
              "Rules: ONLY what the clip lines, the facts or the project name say. Never invent quest names, champions, "
              "characters, scores or events; when unsure, keep it general. No swearing, no hashtags, no links, no clip "
              "times, never mention TikTok. Correct spelling with the language's own letters.",
              f"Names: {', '.join(terms[:30]) or '(none)'}"]
    if game_name:
        parts.append(f"Only about {game_name}: never name another game.")
    if problems:
        parts += ["", "Problems last time, fix them:"] + [f"- {x}" for x in problems[:8]]
    return "\n".join(parts)


def _lower_first(text: str, lang: str, keep: set[str] | frozenset[str] = frozenset()) -> str:
    from . import lexicon

    if not text or lang in NO_CAPS:
        return text
    words = text.split(" ")
    first = words[0]
    if re.split(r"['’,.!?]", first)[0].lower() in keep:
        return text  # a name ("League of Legends oynadık")
    if len(first) > 1 and (first.isupper() or any(ch.isupper() for ch in first[1:])):
        return text  # an acronym or a CamelCase name ("ADC", "McLaren")
    if len(words) > 1 and words[1][:1].isupper():
        return text  # a two-word name ("Master Yi ile ...")
    base = re.split(r"['’,.!?]", first)[0]
    if lexicon.available() and lexicon.zipf(lexicon.lower(base, lang), lang) < 3.0:
        return text  # not an everyday word: most likely a name ("Kraven ile ...")
    return lexicon.lower(text[0], lang) + text[1:]


def proper_names(text: str) -> set[str]:
    """Words written with a capital in the middle of a sentence (names the streamer said)."""
    out: set[str] = set()
    for sent in SENTENCE_END.split(text or ""):
        for w in re.findall(r"[^\W\d_][\w'’-]*", sent)[1:]:
            base = re.split(r"['’]", w)[0]
            if base[:1].isupper() and len(base) >= 3:
                out.add(base.lower())
    return out


def _strip_intro(text: str, s: dict, lang: str) -> str:
    """The model's own "Selamlar! Bu bölümde" (or part of it) taken off, so it is never doubled."""
    from . import lexicon

    t = text.strip()
    for piece in (s["intro"], s["intro"].split("!")[-1].strip() if "!" in s["intro"] else "",
                  s["intro"].split("!")[0] + "!" if "!" in s["intro"] else ""):
        if piece and lexicon.lower(t, lang).startswith(lexicon.lower(piece, lang)):
            t = t[len(piece):].lstrip(" ,!")
    return t


def assemble(sentences: list[str], tpl: dict, lang: str, polish=None,
             keep: set[str] | frozenset[str] = frozenset()) -> str:
    """"Selamlar! Bu bölümde <sentences> ..., iyi seyirler!" + the CTA line (no hashtags)."""
    from . import lexicon

    s = tpl["s"]
    sents = [(polish(x) if polish else " ".join(str(x).split())).strip() for x in sentences if str(x).strip()]
    sents = [x for x in sents if x]
    if not sents:
        return ""
    sents[0] = _lower_first(_strip_intro(sents[0], s, lang), lang, keep)
    outro = s["outro"]
    # "...bitirdim. iyi seyirler!" -> "...bitirdim, iyi seyirler!" (the outro closes the last sentence)
    last = sents[-1].rstrip()
    if lexicon.lower(last, lang).endswith(lexicon.lower(outro, lang)) and len(last) > len(outro) + 2:
        head = last[: len(last) - len(outro)].rstrip()
        if head.endswith((".", "!", "…", "。", "！")):
            sents[-1] = head.rstrip(".!…。！ ") + ("，" if lang == "zh" else "、" if lang == "ja" else ", ") + outro
    low = lexicon.lower(sents[-1], lang)
    if not low.rstrip().endswith(lexicon.lower(outro, lang).rstrip("!！ ")) and \
            not low.rstrip().endswith(lexicon.lower(outro, lang)):
        last = sents[-1].rstrip(" .!?…。！？")
        sep = "，" if lang == "zh" else ("、" if lang == "ja" else ", ")
        sents[-1] = f"{last}{sep}{outro}"
    joiner = "" if lang in ("zh", "ja") else " "
    para = f"{s['intro']}{joiner}{joiner.join(sents)}"
    return f"{para}\n\n{s['cta']}"


def count_sentences(para: str, s: dict) -> int:
    body = para
    greet = s["intro"].split("!")[0] + "!" if "!" in s["intro"] else ""
    if greet and body.startswith(greet):
        body = body[len(greet):]
    return len([x for x in SENTENCE_END.split(body.strip()) if len(x.strip()) > 3])


def widen_allowed(allowed_text: str, game_terms: list[str]) -> str:
    """A multi-word name of the game ("Baron Nashor") counts as said when one of its words was
    ("Baron"): the official name, not an invented one."""
    have = _norm(allowed_text)
    extra = [t for t in game_terms if " " in t.strip()
             and any(len(w) >= 4 and f" {w.lower()}" in have for w in t.split())]
    return allowed_text + (" " + " ".join(extra) if extra else "")


def unknown_names(text: str, allowed_text: str, lang: str) -> list[str]:
    """Capitalized words in the middle of a sentence that are not in the facts / transcript /
    project name and are not ordinary words: likely invented names."""
    from . import lexicon

    if not lexicon.available() or lang in NO_CAPS:
        return []
    ok: set[str] = set()
    for tok in re.findall(r"[^\W_][\w'’-]*", allowed_text or ""):
        for x in (tok, re.split(r"['’]", tok)[0], *tok.split("-")):
            if x:
                ok.update({lexicon.lower(x, lang), x.lower()})

    def allowed(low: str) -> bool:
        if low in ok:
            return True
        return len(low) >= 4 and any(len(a) >= 4 and (a.startswith(low) or low.startswith(a)) for a in ok)

    out = []
    for sent in SENTENCE_END.split(text):
        words = re.findall(r"[^\W\d_][\w'’-]*", sent)
        for w in words[1:]:
            base = re.split(r"['’]", w)[0]
            if not base[:1].isupper() or len(base) < 3:
                continue
            low = lexicon.lower(base, lang)
            if allowed(low) or allowed(base.lower()):
                continue
            if lexicon.zipf(low, lang) >= 3.0 or lexicon.zipf(base.lower(), "en") >= 4.0:
                continue
            out.append(base)
    return list(dict.fromkeys(out))


def check_description(text: str, fmt: str, tpl: dict, lang: str, allowed_text: str = "", forbidden=None) -> list[str]:
    from . import lexicon
    from . import style

    s = tpl["s"]
    errs = []
    para, _sep, rest = text.partition("\n\n")
    if not para.startswith(s["intro"]):
        errs.append(f'start with "{s["intro"]}"')
    if not lexicon.lower(para.rstrip(), lang).endswith(lexicon.lower(s["outro"], lang)):
        errs.append(f'end the paragraph with "{s["outro"]}"')
    lo, hi = (1, 2) if fmt == "short" else (3, 5)
    n = count_sentences(para, s)
    if not lo <= n <= hi:
        errs.append(f"{lo}-{hi} sentences about what happened (now {n})")
    if s["cta"] not in rest:
        errs.append("the subscribe / like / comment line follows the paragraph")
    if re.search(r"tiktok", text, re.I):
        errs.append("never mention TikTok")
    names = unknown_names(para, allowed_text, lang) if allowed_text else []
    if names:
        errs.append("names that are not in the clip, the facts or the project name: " + ", ".join(names[:4]))
    errs += style._common_desc_problems(text, lang, forbidden)
    return errs


def fallback_description(tpl: dict, fmt: str, lang: str, game_name: str, facts: dict) -> str:
    """No AI available (or no usable answer): a short general text from the facts only."""
    names = [t["term"] for t in (facts.get("terms") or []) if t.get("kind") in NAME_KINDS][:2]
    events = [e.get("label") for e in (facts.get("events") or []) if e.get("label")][:1]
    g = game_name or ""
    if lang == "tr":
        first = (f"{g} oynadık" if g else "oyuna girdik") + (f", {' ve '.join(names)} ile sahaya çıktık" if names else "")
        sents = [first + "."]
        if events and fmt != "short":
            sents.append(f"Maçın en güzel anı {events[0].lower()} oldu.")
        if fmt != "short":
            sents.append("Tansiyon hiç düşmedi, sonuna kadar mücadele ettik.")
        sents.append("Hepsini bu videoda topladım, iyi seyirler!")
    else:
        sents = [(f"we played {g}" if g else "we jumped into the game") + "."]
        if fmt != "short":
            sents.append("It was intense from start to finish.")
        sents.append("Everything is in this video.")
    keep = {w.lower() for w in re.findall(r"[^\W_]+", f"{g} {' '.join(names)}")}
    return assemble(sents[:2] if fmt == "short" else sents, tpl, lang, keep=keep)


# ------------------------------------------------------------------ hashtags


def build_hashtags(tpl: dict, *, fmt: str, facts: dict, clip_text: str, moment: str | None, lang: str,
                   mood: list[str] | None = None, forbidden=None) -> list[str]:
    """9-13: game, characters, role / mode, community, channel, "...Sekansı", #BölümN,
    platform, #Shorts (then mood / game extras to reach 9)."""
    from . import banks
    from . import style

    g = tpl.get("game") or {}
    s = tpl["s"]
    seen: set[str] = set()
    out: list[str] = []

    def add(t: str | None, check: bool = True) -> None:
        h = _hashtag(t)
        if not h or len(h) > 31 or h.casefold() in seen or len(out) >= HASHTAGS_MAX:
            return
        if check and (banks._profane(h[1:]) or (forbidden and (x := forbidden(h[1:])) and x != "a clip time")):
            return
        seen.add(h.casefold())
        out.append(h)

    names = [t["term"] for t in (facts.get("terms") or []) if t.get("kind") in NAME_KINDS]
    said = _norm(" ".join([tpl.get("project_title") or "", clip_text or ""]))
    title_n = _norm(tpl.get("project_title") or "")
    # the character in the project name first, then the one said most often
    names = sorted(names, key=lambda n: (f" {n.lower()} " not in title_n, -said.count(f" {n.lower()}")))[:3]
    camel = [style._camel(n) for n in names]
    add(g.get("tag"))
    for c in camel:
        add(c)
    text = _norm(" ".join([clip_text or "", tpl.get("project_title") or ""]) +
                 " " + " ".join(t["term"] for t in facts.get("terms") or []))
    text = text.replace("'", " ")  # "jungle'a" -> jungle
    for w, tag in ROLE_WORDS.items():
        if f" {w} " in text:
            add(tag)
            break
    comm = (g.get("community") or {}).get(lang) or []
    user_comm = tpl["community_tags"].get(g.get("id") or "") or tpl["community_tags"].get("default") or []
    add((user_comm or comm or [s["community"]])[0])
    add(tpl["channel_tag"], check=False)
    seq_base = camel[0] if camel else style._camel(g.get("short") or g.get("name") or "")
    if seq_base:
        add(f"{seq_base}{s['combo']}")
    if tpl.get("episode") and tpl.get("series_key"):
        add(s["episode_tag"].format(n=tpl["episode"]), check=False)
    if tpl.get("platform"):
        add(tpl["platform"], check=False)
    tail = ["#Shorts"] if fmt == "short" else []
    room = HASHTAGS_MAX - len(tail)
    extra = list(comm[1:]) + list(user_comm[1:]) + [s["community"]]
    for h in mood or []:
        w = re.sub(r"[^\w]", "", str(h).replace("#", ""), flags=re.UNICODE)
        if w and (banks._known_tag(w, lang) or w.casefold() in {"tilt", "rage", "clutch", "outplay"}):
            extra.append(w)
    if lang == "tr" and moment not in ("useful", "informative"):  # no "#Rehber" on a match video
        extra += style.MOOD_TAGS.get(moment or "", style.MOOD_TAGS["other"])
    if g.get("name"):
        extra += [f"{style._camel(g.get('short') or g['name'])}Gameplay"]
    extra += ["#Gameplay", "#Gaming"]
    for h in extra:
        if len(out) >= max(HASHTAGS_MIN - len(tail), min(room, 11 - len(tail))):
            break
        add(h)
    for h in tail:
        add(h, check=False)
    return out[:HASHTAGS_MAX]


def check_hashtags(tags: list[str], fmt: str, tpl: dict) -> list[str]:
    errs = []
    if not HASHTAGS_MIN <= len(tags) <= HASHTAGS_MAX:
        errs.append(f"{HASHTAGS_MIN}-{HASHTAGS_MAX} hashtags (now {len(tags)})")
    if tpl["channel_tag"] and tpl["channel_tag"] not in tags:
        errs.append(f"the channel tag {tpl['channel_tag']}")
    if fmt == "short" and "#Shorts" not in tags:
        errs.append("#Shorts on a Short")
    if not any(t.endswith(tpl["s"]["combo"]) for t in tags):
        errs.append(f"one ...{tpl['s']['combo']} tag")
    return errs


def layout(lang: str | None) -> dict | None:
    """The description layout for brand.with_socials: CTA in the text, then the social block
    (word for word), then the label and the hashtags."""
    t = resolved(lang)
    if t is None:
        return None
    return {"label": t["s"]["label"], "short_socials": t["shorts_socials"], "block": t["social_block"]}
