"""Swear words per language, for bleeping / muting them and masking them in captions
(YouTube limits ads on videos with strong language, most of all in the first seconds).

The lists are a starting point: Settings > Studio > Word lists edits them per language
(config `profanity_lists`: {lang: [entries]} replaces the built-in list of that language).
Entry syntax: see words.py ("stem*", "two words", Turkish ı/i rules).
"""

from __future__ import annotations

from .. import config
from .words import compile_entries, find, mask

DEFAULTS: dict[str, list[str]] = {
    "tr": ["amk", "aq", "amq", "amına*", "amını*", "amcık*", "orospu*", "oç", "piç", "piçin*", "piçler*",
           "pezevenk*", "sik", "sike*", "siki*", "sikm*", "sikt*", "sikey*", "siker*", "hassiktir*",
           "hasiktir*", "yarrak*", "yarram*", "yarağ*", "göt", "götü", "götün*", "götveren*", "götlek*",
           "kahpe*", "kaltak*", "ibne*", "puşt*", "gavat*", "şerefsiz*"],
    "en": ["fuck*", "motherfuck*", "shit*", "bullshit*", "bitch*", "asshole*", "ass", "dick", "dickhead*",
           "cunt*", "bastard*", "pussy", "cock", "cocksucker*", "whore*", "slut*", "nigga*", "nigger*",
           "faggot*", "fag", "retard*", "wanker*", "twat*"],
    "de": ["scheisse*", "scheiss*", "fick*", "arschloch*", "arsch", "hurensohn*", "hure", "huren*",
           "wichser*", "fotze*", "schlampe*", "missgeburt*", "spast*", "fuck*", "shit*"],
    "hu": ["kurva*", "bazdmeg*", "baszd*", "baszo*", "baszni", "basszus", "geci*", "fasz", "faszom*",
           "faszt", "faszság*", "faszfej*", "faszkalap*", "picsa*", "picsá*", "kibaszott*", "buzi*",
           "anyád", "fuck*"],
    "ru": ["бля", "бля*", "блять*", "блядь*", "сука", "суки", "сучк*", "сучар*", "хуй*", "хуе*", "хуя*",
           "нахуй*", "похуй*", "охуе*", "пизд*", "ебат*", "ебан*", "ебал*", "ебу*", "заеб*", "уеб*", "выеб*",
           "наеб*", "долбоеб*", "мудак*", "мудил*", "пидор*", "пидар*", "гандон*", "шлюх*", "залуп*"],
    "ar": ["كس", "كسمك", "كس امك", "شرموط*", "منيوك*", "منيك", "نيك", "نيك*", "زب", "زبي", "طيز*", "خول",
           "عرص*", "قحب*", "متناك*", "يلعن*", "ابن الكلب"],
    "zh": ["我操", "卧槽", "操你", "操他", "操蛋", "草泥马", "肏", "他妈的", "妈的", "傻逼", "傻b", "傻屄", "屄",
           "鸡巴", "狗日", "王八蛋", "尼玛", "婊子", "贱人"],
}

MODES = ("auto", "bleep", "mute", "off")


def word_list(lang: str | None) -> list[str]:
    custom = config.get("profanity_lists") or {}
    if lang and isinstance(custom.get(lang), list):
        return [str(w) for w in custom[lang]]
    return list(DEFAULTS.get(lang or "", []))


def find_words(words: list[dict], lang: str | None, entries: list[str] | None = None) -> list[int]:
    """Indices of the swear words among transcript words ({"word": ...})."""
    lst = compile_entries(entries if entries is not None else word_list(lang), lang)
    if not lst or not words:
        return []
    out: list[int] = []
    for a, b, _e in find([w["word"] for w in words], lst, lang):
        out += range(a, b + 1)
    return out


def resolve(mode: str, vertical: bool) -> str:
    """"auto" -> bleep for vertical Shorts / TikTok / Reels videos, off for 16:9 and audio."""
    if mode == "auto":
        return "bleep" if vertical else "off"
    return mode if mode in MODES else "off"


__all__ = ["DEFAULTS", "MODES", "find_words", "mask", "resolve", "word_list"]
