"""1.2.68: titles made for views on every short-video platform (also without My style template).

  views_title   ALL CAPS with the language's own letters (Turkish İ Ş Ğ Ü Ö Ç, an English name
                keeps its I), the words fixed where Whisper / the model dropped Turkish letters,
                1-2 fitting emojis at the end (the moment's mood when it had none), YouTube Shorts
                end with "#Shorts", at most 100 characters. Arabic, Chinese and Japanese have no
                capitals: only the emojis and #Shorts are added there.

A title the user typed by hand is never changed (multipost.drafts only formats generated ones).
Hashtag rules per platform live in the caption builders: Instagram at most igpace.HASHTAGS (5),
TikTok captions at most platforms.CAPTION_MAX (2,200 characters), YouTube descriptions 5,000.
"""

from __future__ import annotations

import re

from . import mytemplate

LIMIT = 100
_TAG = re.compile(r"(?<![\w#])#[^\s#]+")


def views_title(title: str, lang: str | None, platform: str = "youtube", moment: str | None = None) -> str:
    core = _TAG.sub("", title or "").strip()
    core = re.sub(r"\s{2,}", " ", core)
    if not core:
        return (title or "").strip()[:LIMIT]
    fmt = "short" if platform == "youtube" else "social"
    try:
        out = mytemplate.finish_title(core, fmt, {}, lang or "en", moment)
    except Exception:  # noqa: BLE001 - never lose the title over formatting
        out = core
    return out[:LIMIT]
