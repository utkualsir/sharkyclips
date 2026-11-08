"""Swear-word recognition beyond plain word lists (1.2.21): stems + suffixes, letter
variants, stretched letters, leetspeak, already-censored output and a Turkish-aware
phonetic distance. Used by swears.detect() for every transcript word.

classify(token, lang) -> (kind, score, why) | None
  kind "sure"   a swear form (stem + a suffix of the language, an abbreviation, a censored
                "s**" form that fits a list word)
  kind "maybe"  sounds like one (Turkish ı/i, voiced/voiceless pairs, one vowel off...) and
                is not a normal word of the language (wordfreq + a hand list of look-alikes)

Turkish example: "sik-" + any suffix chain is sure ("siktir", "sikeyim", "sikerler"), but
"sıkıntı" / "sıktım" (trouble / I shot) are real words, and "sıkeyim" (no such word) is a
"maybe" that the re-listen or the local AI decides. "göt" is sure, "götür" (carry) is not.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

LEET = str.maketrans({"4": "a", "@": "a", "3": "e", "1": "i", "!": "i", "0": "o", "5": "s", "$": "s",
                      "7": "t", "€": "e"})
_INNER_SEP = re.compile(r"(?<=\w)[.\-_'’·]+(?=\w)", re.UNICODE)
_EDGE = re.compile(r"^[^\w*]+|[^\w*]+$", re.UNICODE)
_RUN3 = re.compile(r"(.)\1{2,}")
_RUN2 = re.compile(r"(.)\1+")
# Latin letters that look like Cyrillic ones (mixed-script spellings "сyка", "xуй").
_LAT2CYR = str.maketrans({"a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у", "k": "к",
                          "m": "м", "t": "т", "h": "н", "b": "в"})
_AR = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي"})


def lower(text: str, lang: str | None) -> str:
    if lang == "tr":
        text = text.replace("I", "ı").replace("İ", "i")
    return text.lower()


def raw_key(word: str, lang: str | None) -> str:
    """Lowercase, punctuation around and inside the word removed ("s.i.k", "a-q"), leet
    digits read as letters, letter runs of 3+ squeezed ("siiiiktir" -> "siktir"). Accents and
    Turkish letters stay. '*' stays (censored words)."""
    t = lower(word.strip(), lang)
    t = _EDGE.sub("", t)
    if any("a" <= ch <= "z" for ch in t) or lang not in ("ru", "ar", "zh"):
        t = t.translate(LEET)
    t = _INNER_SEP.sub("", t)
    if lang == "ru" and any("а" <= ch <= "я" for ch in t):
        t = t.translate(_LAT2CYR).replace("ё", "е")
    if lang == "ar":
        t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))
        t = t.translate(_AR).replace("ـ", "")
    return _RUN3.sub(r"\1", t)


def tr_key(t: str, dotless: bool = True) -> str:
    """Turkish spelling folded: ş->s, ç->c, ğ->g, ö->o, ü->u, q->k, w->v, x->ks, â->a.
    dotless=True keeps ı apart from i (so 'sık' stays 'sık'); False folds it too."""
    t = t.replace("ş", "s").replace("ç", "c").replace("ğ", "g").replace("ö", "o").replace("ü", "u")
    t = t.replace("q", "k").replace("w", "v").replace("x", "ks").replace("â", "a").replace("î", "i").replace("û", "u")
    if not dotless:
        t = t.replace("ı", "i")
    return t


def latin_key(t: str) -> str:
    """Accents off (á -> a, ß -> ss), for de / hu / en."""
    t = t.replace("ß", "ss")
    return "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))


# ------------------------------------------------------------------------------ patterns

@dataclass(frozen=True)
class Pat:
    rx: re.Pattern
    kind: str = "sure"  # sure | maybe
    why: str = "form"


def _p(rx: str, kind: str = "sure", why: str = "form") -> Pat:
    return Pat(re.compile(rx), kind, why)


# Turkish, on tr_key(dotless=True): "ı" is still "ı", everything else folded.
_SUF = r"[a-zı]*"
TR_ABBREV = {"amk", "amq", "aq", "amkk", "mk", "mq", "amınakoyim", "amnk", "amnskm", "aminakoyim", "oç"}
TR_PATTERNS: list[Pat] = [
    _p(r"^amk" + _SUF + "$", why="abbrev"),
    _p(r"^am[ıi]n[aeıi]" + _SUF + "$"),                     # amına, amını, amina, amınakoyayım
    _p(r"^am[ıi]na?k" + _SUF + "$"),                        # amınak, aminakim (fast "amına koyayım")
    _p(r"^amc[ıi]k" + _SUF + "$"),
    _p(r"^(has+)?sik(?!ke)" + _SUF + "$"),                  # sik, siktir, sikeyim, sikerler, hassiktir
    _p(r"^(has+)?sık(t[ıi]r|ey[ıi]m|er[ıi]m|em|ecem|[ıi]cem|ko|[ıi]k$|[ıi]s|im$|[ıi]y[ıi]m)" + _SUF + "$",
       "maybe", "dotless"),                                 # "sıkeyim", "sıktır": Whisper's ı for i
    _p(r"^or[ou]?s[pb]u" + _SUF + "$"),                     # orospu, orosbu, orspu, oruspu
    _p(r"^pic(?!k|n|t|s|a|o)" + _SUF + "$"),                # piç, piçin, piçler, piçlik (not pick/picnic)
    _p(r"^yar+ak" + _SUF + "$|^yar+ag" + _SUF + "$|^yarram" + _SUF + "$|^dalyar+ak" + _SUF + "$"),
    _p(r"^got(?!ur|ik|ham)" + r"[a-zı]{0,8}$"),        # göt, götü, götün, götveren (not götür = carry)
    _p(r"^kahpe" + _SUF + "$|^kaltak" + _SUF + "$|^ibne" + _SUF + "$|^pust" + _SUF + "$|^gavat" + _SUF + "$"),
    _p(r"^pezeven[kg]" + _SUF + "$|^yavsak" + _SUF + "$|^serefsiz" + _SUF + "$|^surtuk" + _SUF + "$"),
    _p(r"^tas+ak" + _SUF + "$|^das+ak" + _SUF + "$"),
    _p(r"^kavat" + _SUF + "$", "maybe", "sound"),
]
# Real words (or names) that the patterns above would catch (folded like tr_key dotless=True).
TR_NOT = {"sikke", "sikkeler", "sikkesi", "gotik", "picasso", "amine", "amin", "amino", "aminoasit",
          "kahperengi", "tasavvur", "siklet", "sikletler", "sikleti", "gotten", "gotta"}

EN_PATTERNS = [
    _p(r"^(mother|mutha|motha)?f+u+c?k+" + r"[a-z]*$"),     # fuck, fuuck, fucking, fuckin, motherfucker
    _p(r"^f+c?k+(ing|in|er|ers|ed)?$|^fuk(ing|in|er)?$|^phuck[a-z]*$|^fook[a-z]*$"),
    _p(r"^(bull|horse|dip|ape|chicken)?shi+t+[a-z]*$|^sh[i1]t[a-z]*$"),
    _p(r"^(dumb|jack|fat|smart|bad)?ass(hole|holes|wipe|hat|es)?$|^arse(hole)?s?$"),
    _p(r"^b+i+a?t+c+h[a-z]*$|^biatch[a-z]*$"),
    _p(r"^(dick|cock)(head|heads|sucker|suckers|s)?$|^cunts?$|^twats?$|^wankers?$"),
    _p(r"^niggas?$|^niggers?$|^faggots?$|^fags?$|^retards?(ed)?$|^whores?$|^sluts?$|^bastards?$|^pussy$|^pussies$"),
    _p(r"^mf$|^mofo$", "maybe", "abbrev"),
]
DE_PATTERNS = [
    _p(r"^(ver)?(scheiss|scheis|schais)[a-z]*$"),
    _p(r"^(ver)?fick[a-z]*$|^arschloch[a-z]*$|^arsch$|^hurensohn[a-z]*$|^huren[a-z]*$|^hure$"),
    _p(r"^wi(ch|x)ser[a-z]*$|^fotze[a-z]*$|^schlampe[a-z]*$|^missgeburt[a-z]*$|^spast[a-z]*$|^drecksau$"),
    _p(r"^schwanzlutscher[a-z]*$|^pisser$|^fuck[a-z]*$|^shit[a-z]*$"),
]
HU_PATTERNS = [
    _p(r"^kurv[a-z]*$|^(ki|el|meg|fel|be|szet)?bas+z[a-z]*$|^baz+d+meg[a-z]*$|^geci[a-z]*$"),
    _p(r"^fasz[a-z]*$|^pics[a-z]*$|^buzi[a-z]*$|^kocsog[a-z]*$|^ribanc[a-z]*$|^anyad(at|ba)?$"),
    _p(r"^fuck[a-z]*$"),
]
RU_PATTERNS = [
    _p(r"^(бля|бляд|блят|блеат|мля)[а-я]*$"),
    _p(r"^(на|по|о|от|за|до|ни)?ху[йеяиюё][а-я]*$"),
    _p(r"^(рас|рос|рас|за|от|у|вы|на|до|пере|при|об|подъ|съ|въ|отъ|изъ|раз|долбо)?[её]б(а|у|л|ан|ат|ну|нут|и)[а-я]*$"),
    _p(r"^(рас)?пизд[а-я]*$|^сук[аи]$|^сучк[а-я]*$|^сучар[а-я]*$|^муда[кч][а-я]*$|^мудил[а-я]*$"),
    _p(r"^пид[ао]?р[а-я]*$|^гандон[а-я]*$|^шлюх[а-я]*$|^залуп[а-я]*$|^уеб[а-я]*$|^пздц$"),
]
AR_PATTERNS = [
    _p(r"^(ك+س|كسم|كسمك|كسختك)[؀-ۿ]*$"),
    _p(r"^(ال)?(شرموط|منيوك|متناك|عرص|قحب|خول|طيز)[؀-ۿ]*$"),
    _p(r"^(ي|ت|ن)?نيك[؀-ۿ]*$|^زب[ي]?$|^يلعن[؀-ۿ]*$|^خرا$"),
]
# Chinese / Japanese: substrings of the running text (words.py NO_SPACE_LANGS) + Latin slang.
ZH_SUBSTR = ["我操", "卧槽", "我草", "操你", "草你", "肏", "他妈的", "他媽的", "妈的", "媽的", "傻逼", "傻屄", "傻b",
             "屄", "鸡巴", "雞巴", "狗日", "王八蛋", "尼玛", "你妈", "婊子", "贱人", "幹你", "干你娘", "屌", "艹",
             "操蛋", "草泥马", "去你的"]
ZH_LATIN = re.compile(r"^(sb|cnm|nmsl|tmd|wcnm|nmb|mlgb|wtf)$")

PATTERNS = {"tr": TR_PATTERNS, "en": EN_PATTERNS, "de": DE_PATTERNS, "hu": HU_PATTERNS,
            "ru": RU_PATTERNS, "ar": AR_PATTERNS}

# The stems for the phonetic near-miss (phonetic keys, see phon()).
PHON_STEMS: dict[str, list[str]] = {
    "tr": ["aminakoyim", "aminakoyayim", "amina", "aminak", "amcik", "siktir", "sikeyim", "sikerim", "sikim",
           "sikik", "orospu", "yarak", "yaram", "piclik", "pezevenk", "kahpe", "kaltak", "serefsiz", "yavsak"],
    "en": ["fuck", "fucking", "motherfucker", "shit", "bullshit", "bitch", "asshole", "dickhead", "bastard"],
    "de": ["scheisse", "ficken", "arschloch", "hurensohn", "wichser"],
    "hu": ["kurva", "bazdmeg", "baszd", "geci", "faszom", "picsaba", "kibaszott"],
    "ru": ["блять", "блядь", "сука", "нахуй", "пиздец", "ебать", "хуйня", "мудак"],
}


# ------------------------------------------------------------------------------ phonetics

_VOWELS = set("aeıioöuüäéáíóúőűyаеёиоуыэюя")
_PAIRS = [set(p) for p in ("bp", "dt", "gkğ", "cçj", "sşz", "vfw", "ıiüuyeöo", "aeä", "mn", "rl",
                           "бп", "дт", "гк", "зс", "вф", "аоя", "еиэ")]


def phon(t: str) -> str:
    """A phonetic key: Turkish letters folded, no accents, doubles collapsed."""
    t = t.replace("ı", "i").replace("ğ", "").replace("q", "k").replace("w", "v").replace("x", "ks")
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))
    t = re.sub(r"[^a-zа-яё؀-ۿ]", "", t)
    return _RUN2.sub(r"\1", t)


def _sub_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    for p in _PAIRS:
        if a in p and b in p:
            return 0.5
    if a in _VOWELS and b in _VOWELS:
        return 0.7
    return 1.0


def wdist(a: str, b: str, limit: float = 2.0) -> float:
    """Weighted edit distance: similar sounds (b/p, k/g, s/z, i/ı/u, a/e...) cost half."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = [float(j) for j in range(len(b) + 1)]
    for i, ca in enumerate(a, 1):
        cur = [float(i)] + [0.0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + _sub_cost(ca, cb))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


# ------------------------------------------------------------------------------ common words

# Look-alikes that wordfreq may not know well enough (spoken forms, gaming slang).
NOT_SWEARS: dict[str, set[str]] = {
    "tr": {"sıkıntı", "sıkıntılı", "sıktım", "sıktı", "sıkıyor", "sıkıyo", "sıkış", "sıkışık", "sıkıştım", "sıkıcı",
           "sıkma", "sıkıl", "sıkıldım", "amaç", "amacı", "aman", "amca", "amcam", "ama", "amele", "amin", "amir",
           "götür", "götürdü", "götürüyor", "götürdüm", "piknik", "pikachu", "yara", "yaram", "yaramaz", "yarar",
           "kavak", "sikke", "gotik", "orası", "tasarım"},
}


@lru_cache(maxsize=20000)
def common_word(tok: str, lang: str | None) -> bool:
    """A normal word of the language: "sıkıntı" is never a near-miss of "sik"."""
    if not lang or len(tok) < 3:
        return False
    if tok in NOT_SWEARS.get(lang, set()):
        return True
    try:
        from wordfreq import zipf_frequency

        if zipf_frequency(tok, lang) >= 3.0:
            return True
        # spoken Turkish drops the r of -yor ("sıkıyo" = "sıkıyor", to shoot)
        if lang == "tr" and "yo" in tok:
            k = tok.rindex("yo") + 2
            return zipf_frequency(tok[:k] + "r" + tok[k:], lang) >= 2.5
    except Exception:  # noqa: BLE001 - language not in wordfreq
        return False
    return False


# ------------------------------------------------------------------------------ censored

_MASK = re.compile(r"^[^\W\d_]*\*+[^\W\d_*]*(\*+[^\W\d_*]*)*$|^\*{3,}$", re.UNICODE)


def is_censored(word: str) -> bool:
    """Whisper's own censoring: "s**", "a***", "f*ck", "s*kt*r", "****"."""
    w = _EDGE.sub("", word.strip())
    return "*" in w and bool(_MASK.match(w)) and (len(w) >= 3 or w.count("*") >= 1 and len(w) >= 2)


# ------------------------------------------------------------------------------ main

def variants(word: str, lang: str | None) -> list[str]:
    """Keys of one transcript word to try against the list: as written, squeezed, folded."""
    k = raw_key(word, lang)
    out = [k]
    if lang == "tr":
        out += [tr_key(k), tr_key(k, dotless=False)]
    elif lang in ("en", "de", "hu"):
        out.append(latin_key(k))
    sq = _RUN2.sub(r"\1", k)
    if sq != k and lang not in ("tr",):  # "fuuck" -> "fuck"; Turkish keeps "yarrak"/"yarak" apart
        out.append(latin_key(sq) if lang in ("en", "de", "hu") else sq)
    seen: list[str] = []
    for v in out:
        if v and v not in seen:
            seen.append(v)
    return seen


def classify(word: str, lang: str | None, prob: float = 1.0) -> tuple[str, float, str] | None:
    """('sure' | 'maybe', score, why) for one transcript word, or None."""
    k = raw_key(word, lang)
    if not k or len(k) > 40:
        return None
    if is_censored(word):
        return ("sure", 1.0, "masked")
    if lang in ("zh", "ja"):
        if ZH_LATIN.match(k) or any(s in k for s in ZH_SUBSTR):
            return ("sure", 1.0, "form")
        return None
    if lang == "tr":
        if k in TR_ABBREV:
            return ("sure", 1.0, "abbrev")
        key = tr_key(k)  # ı kept
        if key in TR_NOT or k.startswith(("şikay", "şikây")):  # "şikayet" (complaint) folds to "sik..."
            return None
        for p in TR_PATTERNS:
            if not p.rx.match(key):
                continue
            if key.startswith("got") and "ö" not in k:
                return ("maybe", 0.45, "sound")  # English "got" in a Turkish sentence
            if p.kind == "sure":
                return ("sure", 1.0, p.why)
            if common_word(k, lang):  # a "maybe" form that is a real word ("sıktım")
                return None
            return ("maybe", 0.62 if prob < 0.9 else 0.52, p.why)
    else:
        pats = PATTERNS.get(lang or "")
        for v in variants(word, lang) if pats else []:
            for p in pats:
                if p.rx.match(v):
                    if p.kind == "maybe" and common_word(k, lang):
                        return None
                    return (p.kind, 1.0 if p.kind == "sure" else 0.55, p.why)
    # phonetic near-miss of a stem
    stems = PHON_STEMS.get(lang or "")
    if not stems or common_word(k, lang):
        return None
    pk = phon(tr_key(k) if lang == "tr" else k)
    if len(pk) < 4:
        return None
    best = 9.0
    for s in stems:
        if len(pk) > len(s) + 3:  # "kahretsizsin" only starts like "kahpe": another word
            continue
        head = pk[:len(s)] if len(pk) > len(s) else pk
        if abs(len(head) - len(s)) > 1:
            continue
        best = min(best, wdist(head, s, 1.5))
    if best <= 0.0:
        return ("maybe", 0.6 if prob < 0.9 else 0.5, "phonetic")
    limit = 0.5 if len(pk) < 5 else 1.0
    if best <= limit:
        return ("maybe", round(0.42 + (1.0 - best) * 0.12 + (0.75 - min(prob, 0.75)) * 0.25, 2), "fuzzy")
    return None


__all__ = ["classify", "common_word", "is_censored", "phon", "raw_key", "tr_key", "variants", "wdist"]
