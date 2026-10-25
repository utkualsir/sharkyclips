"""Supported languages registry, shared by the whole app (UI, transcription, outputs)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .errors import SharkyClipsError

AUTO = "auto"


@dataclass(frozen=True)
class Language:
    code: str  # SharkyClips / ISO 639-1 code
    native_name: str
    english_name: str
    is_rtl: bool
    whisper_code: str  # code Whisper expects

    def to_dict(self) -> dict:
        return asdict(self)


_ALL = [
    Language("tr", "Türkçe", "Turkish", False, "tr"),
    Language("en", "English", "English", False, "en"),
    Language("ru", "Русский", "Russian", False, "ru"),
    Language("hu", "Magyar", "Hungarian", False, "hu"),
    Language("de", "Deutsch", "German", False, "de"),
    Language("ar", "العربية", "Arabic", True, "ar"),
    Language("zh", "中文", "Chinese", False, "zh"),
]

LANGUAGES: dict[str, Language] = {lang.code: lang for lang in _ALL}

DEFAULT_UI_LANGUAGE = "tr"
DEFAULT_OUTPUT_LANGUAGE = "tr"


def codes() -> list[str]:
    return list(LANGUAGES)


def get(code: str | None) -> Language | None:
    if not code:
        return None
    return LANGUAGES.get(code.lower())


def require(code: str) -> Language:
    lang = get(code)
    if lang is None:
        raise SharkyClipsError(
            f"Unsupported language '{code}'.",
            f"Use one of: {AUTO}, {', '.join(codes())}",
        )
    return lang


def from_whisper_code(whisper_code: str | None) -> Language | None:
    for lang in _ALL:
        if lang.whisper_code == whisper_code:
            return lang
    return None


def is_rtl(code: str | None) -> bool:
    lang = get(code)
    return bool(lang and lang.is_rtl)
