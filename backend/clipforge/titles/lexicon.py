"""Offline "is this a real word?" checks and small deterministic spelling fixes for titles.

The word lists come from `wordfreq` (frequencies of real words in each language). Turkish and
Hungarian stick suffixes onto words ("sıkıştım", "lobiyi"), and the small Turkish list misses
many such forms, so a word also counts as known when a common suffix chain can be stripped down
to a known stem. Without wordfreq installed every word counts as known (the check is skipped).

Fixes (all deterministic, applied to LLM output):
  * diacritics: "pompali" -> "pompalı", "schoner" -> "schöner" (tr, de, hu)
  * Turkish question particle vowel harmony: "Pompalı mi?" -> "Pompalı mı?"
  * Title Case / ALL CAPS -> normal sentence case (names and terms kept)
  * emoji removed
"""

from __future__ import annotations

import functools
import itertools
import re

KNOWN_ZIPF = 1.0       # any listed word
STEM_ZIPF = 2.5        # a stem left after stripping suffixes must be a fairly common word
LOAN_ZIPF = 2.0        # English gaming loanwords inside other languages ("spawn", "revive")

WORD_RE = re.compile(r"[^\W\d_]+(?:[-][^\W\d_]+)*", re.UNICODE)
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF️‍]")

TR_SUFFIXES = sorted(set("""
lar ler ları leri ı i u ü yı yi yu yü nı ni nu nü a e ya ye na ne da de ta te nda nde dan den tan ten
ndan nden ın in un ün nın nin nun nün yın yin la le yla yle ım im um üm m ımız imiz umuz ümüz ınız iniz
unuz ünüz sı si su sü dı di du dü tı ti tu tü dım dim dum düm tım tim tum tüm dık dik duk dük tık tik
tuk tük dın din dun dün tın tin dınız diniz mış miş muş müş yor ıyor iyor uyor üyor acak ecek acağ eceğ
yacak yecek ken yken ki sın sin sun sün sınız siniz mı mi mu mü ma me maz mez ca ce ça çe lık lik luk lük
sız siz suz süz lı li lu lü cı ci cu cü çı çi çu çü dır dir dur dür tır tir tur tür k z sa se ysa yse
mak mek arak erek ıp ip up üp ınca ince unca ünce dığ diğ duğ düğ tığ tiğ tuğ tüğ
""".split()), key=len, reverse=True)

HU_SUFFIXES = sorted(set("""
ban ben ba be ból ből ra re ról ről hoz hez höz nál nél tól től val vel nak nek ért ig ként ul ül
t at et ot öt k ak ek ok ök m am em om öm d ad ed od öd ja je a e i ai ei juk jük unk ünk tok tek tök
ják jék ni ott ett ött tt ta te tam tem tunk tünk hat het ás és ság ség s os es ös an en n on ön
""".split()), key=len, reverse=True)

EN_SUFFIXES = ["'s", "ing", "ed", "es", "s", "er", "ly"]
DE_SUFFIXES = ["ern", "en", "er", "es", "em", "e", "n", "s"]
RU_ENDINGS = ["", "а", "я", "ы", "и", "у", "ю", "е", "о", "ой", "ый", "ий", "ая", "ое", "ые", "ом", "ем",
              "ам", "ах", "ть", "л", "ла", "ли"]
AR_PREFIXES = ["وال", "بال", "فال", "كال", "لل", "ال", "و", "ف", "ب", "ل", "ك", "س"]
AR_SUFFIXES = ["ها", "هم", "هن", "كم", "كن", "نا", "ني", "ه", "ك", "ي", "ة", "ات", "ون", "ين", "ان"]
TR_MUTATION = {"ğ": "k", "b": "p", "c": "ç", "d": "t"}

# Letters that LLMs (and keyboards) mix up with their accented siblings.
DIACRITIC_FAMILIES = {
    "tr": [("c", "ç"), ("g", "ğ"), ("i", "ı"), ("o", "ö"), ("s", "ş"), ("u", "ü")],
    "de": [("a", "ä"), ("o", "ö"), ("u", "ü")],
    "hu": [("a", "á"), ("e", "é"), ("i", "í"), ("o", "ó", "ö", "ő"), ("u", "ú", "ü", "ű")],
}


# ------------------------------------------------------------------ basics


@functools.lru_cache(maxsize=1)
def _wordfreq():
    try:
        import wordfreq

        return wordfreq
    except ImportError:
        return None


def available() -> bool:
    return _wordfreq() is not None


def lower(text: str, lang: str | None) -> str:
    if lang in ("tr", "az"):
        text = text.replace("I", "ı").replace("İ", "i")
    return text.lower()


def upper_char(ch: str, lang: str | None) -> str:
    if lang in ("tr", "az"):
        if ch == "i":
            return "İ"
        if ch == "ı":
            return "I"
    return ch.upper()


@functools.lru_cache(maxsize=200_000)
def zipf(word: str, lang: str) -> float:
    wf = _wordfreq()
    if wf is None or not word:
        return 0.0
    try:
        return float(wf.zipf_frequency(word, lang))
    except Exception:  # unsupported language etc.
        return 0.0


def words(text: str) -> list[str]:
    """Word tokens; "Darius'a" -> "Darius" (the suffix after an apostrophe is grammar)."""
    out = []
    for m in WORD_RE.finditer(re.sub(r"['’][^\W\d_]+", "", text)):
        out.extend(p for p in m.group(0).split("-") if p)
    return out


def strip_emoji(text: str) -> str:
    return " ".join(EMOJI_RE.sub("", text).split())


# ------------------------------------------------------------------ known words


def _strip_chain(word: str, suffixes: list[str], lang: str, depth: int = 3, min_stem: int = 3) -> bool:
    if depth == 0:
        return False
    for suf in suffixes:
        if len(word) - len(suf) < min_stem or not word.endswith(suf):
            continue
        stem = word[: -len(suf)]
        cands = [stem]
        if lang == "tr" and stem[-1] in TR_MUTATION:
            cands.append(stem[:-1] + TR_MUTATION[stem[-1]])  # köpeğ-im -> köpek
        for s in cands:
            if zipf(s, lang) >= STEM_ZIPF and len(s) >= min_stem:
                return True
        if _strip_chain(stem, suffixes, lang, depth - 1, min_stem):
            return True
    return False


@functools.lru_cache(maxsize=100_000)
def known_score(word: str, lang: str, min_stem: int = 4) -> float:
    """Roughly how common the word is (zipf 0-8); 0 = not a known word or form."""
    w = lower(word, lang)
    direct = zipf(w, lang)
    if direct >= KNOWN_ZIPF:
        return direct
    if lang == "tr" and _strip_chain(w, TR_SUFFIXES, "tr", min_stem=min_stem):
        return STEM_ZIPF
    if lang == "hu" and _strip_chain(w, HU_SUFFIXES, "hu", min_stem=min_stem):
        return STEM_ZIPF
    if lang == "en" and _strip_chain(w, EN_SUFFIXES, "en", depth=1, min_stem=3):
        return STEM_ZIPF
    if lang == "de":
        if _strip_chain(w, DE_SUFFIXES, "de", depth=1, min_stem=3):
            return STEM_ZIPF
        for i in range(3, len(w) - 2):  # compounds: Gitarren|solo, Lieblings|moment
            a, b = w[:i], w[i:]
            if zipf(b, "de") >= STEM_ZIPF and (zipf(a, "de") >= STEM_ZIPF or zipf(a.rstrip("s"), "de") >= STEM_ZIPF):
                return STEM_ZIPF
    if lang == "ru" and len(w) >= 5:
        for cut in (1, 2, 3):
            stem = w[:-cut]
            if len(stem) >= 3 and any(zipf(stem + e, "ru") >= STEM_ZIPF for e in RU_ENDINGS):
                return STEM_ZIPF
    if lang == "ar":
        norm = re.sub("[أإآ]", "ا", w).replace("ى", "ي")
        for cand in {w, norm}:
            for p in [""] + AR_PREFIXES:
                if not cand.startswith(p):
                    continue
                core = cand[len(p):]
                for s in [""] + AR_SUFFIXES:
                    if core.endswith(s) and len(core) - len(s) >= 2:
                        stem = core[: len(core) - len(s)] if s else core
                        if zipf(stem, "ar") >= STEM_ZIPF:
                            return STEM_ZIPF
    if re.fullmatch(r"[a-z]+", w) and lang != "en" and zipf(w, "en") >= LOAN_ZIPF:
        return LOAN_ZIPF  # "spawn", "revive", "loot" in a Turkish title
    return 0.0


def is_known(word: str, lang: str, allowed: set[str] | frozenset[str] = frozenset()) -> bool:
    if not available() or lang in ("zh", "ja"):
        return True
    if len(word) <= 2 or any(ch.isdigit() for ch in word):
        return True
    if word.isupper() and len(word) <= 6:  # acronyms: QBZ, AWP, MVP
        return True
    if lower(word, lang) in allowed:
        return True
    return known_score(word, lang) > 0


def unknown_words(text: str, lang: str, allowed: set[str] | frozenset[str] = frozenset()) -> list[str]:
    seen, out = set(), []
    for w in words(text):
        if not is_known(w, lang, allowed) and w not in seen:
            seen.add(w)
            out.append(w)
    return out


# ------------------------------------------------------------------ fixes


def _variants(word: str, lang: str) -> list[str]:
    fams = DIACRITIC_FAMILIES.get(lang)
    if not fams:
        return []
    alt: dict[str, tuple[str, ...]] = {}
    for fam in fams:
        for ch in fam:
            alt[ch] = tuple(x for x in fam if x != ch)
    pos = [i for i, ch in enumerate(word) if ch in alt]
    if not pos:
        return []
    out = []
    if lang == "tr" and len(pos) <= 10:  # 2-way families: try every combination
        for combo in itertools.product(*[(word[i],) + alt[word[i]] for i in pos]):
            chars = list(word)
            for i, ch in zip(pos, combo):
                chars[i] = ch
            v = "".join(chars)
            if v != word:
                out.append(v)
        return out
    for n in (1, 2):  # otherwise at most two changed letters
        for ps in itertools.combinations(pos, n):
            for combo in itertools.product(*[alt[word[i]] for i in ps]):
                chars = list(word)
                for i, ch in zip(ps, combo):
                    chars[i] = ch
                out.append("".join(chars))
    return out


def _restore_case(orig: str, new_lower: str, lang: str) -> str:
    return "".join(upper_char(n, lang) if o.isupper() else n for o, n in zip(orig, new_lower))


@functools.lru_cache(maxsize=50_000)
def best_spelling(word: str, lang: str) -> str | None:
    """A clearly better-known accented spelling of `word`, or None."""
    if not available() or len(word) < 4 or lang not in DIACRITIC_FAMILIES:
        return None
    w = lower(word, lang)
    cur = zipf(w, lang)
    if cur >= 3.5:
        return None
    unknown = cur == 0 and known_score(w, lang) == 0
    best, best_s = None, 0.0
    for v in _variants(w, lang):
        # Real dictionary hits only; a long stem + suffix counts only for totally unknown words
        # ("sikistim" -> "sıkıştım"), so short stems can't turn names into other words.
        s = zipf(v, lang) or (2.0 if unknown and known_score(v, lang, min_stem=5) else 0.0)
        if s > best_s:
            best, best_s = v, s
    if best and ((cur == 0 and best_s >= 2.0) or best_s >= cur + 1.5):
        return _restore_case(word, best, lang)
    return None


def repair_diacritics(text: str, lang: str, protected: set[str] | frozenset[str] = frozenset()) -> tuple[str, list[tuple[str, str]]]:
    fixes = []

    def sub(m: re.Match) -> str:
        w = m.group(0)
        if lower(w, lang) in protected:
            return w
        better = best_spelling(w, lang)
        if better and better != w:
            fixes.append((w, better))
            return better
        return w

    return re.sub(r"[^\W\d_]+", sub, text), fixes


TR_VOWELS = "aeıioöuü"
TR_HARMONY = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}
TR_PARTICLE = re.compile(r"(?P<prev>[^\W\d_]+)(?P<sep>\s+)(?P<q>[mM][ıiuüIİUÜ](?:s[ıiuü]n(?:[ıiuü]z)?|y[ıiuü][mz]|yd[ıiuü](?:[mnk]|n[ıiuü]z)?|ym[ıiuü]ş)?)(?![^\W\d_])")


def fix_tr_question_particle(text: str) -> tuple[str, list[tuple[str, str]]]:
    """mı/mi/mu/mü follow the last vowel of the word before ("pompalı mi" -> "pompalı mı")."""
    fixes = []

    def sub(m: re.Match) -> str:
        prev, q = m.group("prev"), m.group("q")
        vowels = [c for c in lower(prev, "tr") if c in TR_VOWELS]
        if not vowels:
            return m.group(0)
        v = TR_HARMONY[vowels[-1]]
        new = "".join((upper_char(v, "tr") if c.isupper() else v) if lower(c, "tr") in TR_VOWELS else c for c in q)
        if new != q:
            fixes.append((q, new))
        return prev + m.group("sep") + new

    return TR_PARTICLE.sub(sub, text), fixes


def sentence_case(text: str, lang: str, keep: set[str] | frozenset[str] = frozenset()) -> str:
    """'İnanılmaz Bir Durum!' -> 'İnanılmaz bir durum!' (names, terms and acronyms kept).
    Only for Title Case / ALL CAPS titles; German nouns are capitalized on purpose, so not de."""
    if lang in ("de", "zh", "ja", "ar"):
        return text
    ws = [w for w in re.findall(r"[^\W\d_]+", text) if len(w) >= 2]
    if len(ws) < 3:
        return text
    caps = sum(w[0].isupper() for w in ws)
    all_caps = all(w.isupper() for w in ws)
    if not all_caps and caps / len(ws) < 0.75:
        return text
    first = True

    def sub(m: re.Match) -> str:
        nonlocal first
        w = m.group(0)
        if first:
            first = False
            return w[0] + lower(w[1:], lang) if all_caps and lower(w, lang) not in keep else w
        if lower(w, lang) in keep or (not all_caps and w.isupper() and len(w) <= 5):
            return w
        return lower(w, lang)

    return re.sub(r"[^\W\d_]+", sub, text)


def polish(text: str, lang: str, keep: set[str] | frozenset[str] = frozenset(),
           protected: set[str] | frozenset[str] = frozenset()) -> tuple[str, list[tuple[str, str]]]:
    """All deterministic fixes for one title / hook text. Returns (text, [(old, new), ...])."""
    fixes: list[tuple[str, str]] = []
    out = strip_emoji(text).strip()
    out = re.sub(r"^\s*[\[(][a-z_ ]{3,15}[\])]\s*", "", out)  # "[question] ..." echoed by the model
    out = out.strip(" \"'“”«»")
    if out.endswith(".") and not out.endswith(".."):
        out = out[:-1]  # titles don't end with a full stop
    out = re.sub(r"\s+([?!.,…])", r"\1", out)
    out = re.sub(r"([!?])\1+", r"\1", out)  # "!!!" -> "!"
    cased = sentence_case(out, lang, keep)
    if cased != out:
        fixes.append((out, cased))
        out = cased
    out, f = repair_diacritics(out, lang, protected)
    fixes += f
    if lang == "tr":
        out, f = fix_tr_question_particle(out)
        fixes += f
    return out, fixes
