"""Per-message response-language detection with EN/PL interface fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from lingua import Language, LanguageDetector, LanguageDetectorBuilder


ResponseLanguage = str
_LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}$")
_TOKEN_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)
_STRONG_ONE_TOKEN = {
    "bonjour": "fr",
    "cześć": "pl",
    "czesc": "pl",
    "dzięki": "pl",
    "dzieki": "pl",
    "gracias": "es",
    "hi": "en",
    "hello": "en",
    "hola": "es",
    "thanks": "en",
}
_LANGUAGE_NAME_OVERRIDES = {"en": "English", "es": "Spanish", "pl": "Polish"}


@lru_cache(maxsize=1)
def _detector() -> LanguageDetector:
    return (
        LanguageDetectorBuilder.from_all_languages()
        .with_preloaded_language_models()
        .build()
    )


@lru_cache(maxsize=1)
def _languages_by_code() -> dict[str, Language]:
    result: dict[str, Language] = {}
    for language in Language.all():
        if language.iso_code_639_1 is not None:
            result[language.iso_code_639_1.name.lower()] = language
    return result


@dataclass(frozen=True, slots=True)
class LocaleResolution:
    """Resolved reply language and whether this turn supplied clear evidence."""

    locale: ResponseLanguage
    clear_locale: ResponseLanguage | None


def normalize_locale(value: str | None, *, fallback: str = "en") -> ResponseLanguage:
    """Normalize an ISO/BCP-47 language tag without restricting response languages."""
    if not value or not isinstance(value, str):
        return fallback
    language = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return language if _LANGUAGE_CODE.fullmatch(language) else fallback


def language_name(code: str | None) -> str:
    """Return an English language name suitable for model instructions."""
    normalized = normalize_locale(code)
    if normalized in _LANGUAGE_NAME_OVERRIDES:
        return _LANGUAGE_NAME_OVERRIDES[normalized]
    language = _languages_by_code().get(normalized)
    return language.name.title() if language is not None else normalized


def language_tag(code: str | None) -> str:
    """Return a bounded BCP-47-style tag for model instructions."""
    normalized = normalize_locale(code)
    return {"en": "en-GB", "es": "es-ES", "pl": "pl-PL"}.get(normalized, normalized)


def detect_clear_language(message: str) -> ResponseLanguage | None:
    """Detect a clear message language; return None for ambiguous short input."""
    raw_tokens = _TOKEN_PATTERN.findall(message)
    tokens = [token.casefold() for token in raw_tokens]
    if not tokens:
        return None
    if raw_tokens and all(token.isupper() and len(token) <= 4 for token in raw_tokens):
        return None
    if len(tokens) == 1:
        return _STRONG_ONE_TOKEN.get(tokens[0])

    values = _detector().compute_language_confidence_values(message)
    if not values:
        return None
    best = values[0]
    second = values[1].value if len(values) > 1 else 0.0
    code = (
        best.language.iso_code_639_1.name.lower()
        if best.language.iso_code_639_1 is not None
        else None
    )
    if code is None:
        return None
    minimum_confidence = 0.12 if len(tokens) <= 3 else 0.15
    minimum_margin = 0.04 if len(tokens) <= 3 else 0.07
    if best.value < minimum_confidence or best.value - second < minimum_margin:
        return None
    return code


def resolve_response_locale(
    message: str,
    *,
    ui_locale: str | None,
    last_clear_locale: str | None = None,
) -> LocaleResolution:
    """Resolve current message language, then prior clear language, then UI locale."""
    clear_locale = detect_clear_language(message)
    if clear_locale is not None:
        return LocaleResolution(locale=clear_locale, clear_locale=clear_locale)
    if last_clear_locale:
        return LocaleResolution(
            locale=normalize_locale(last_clear_locale), clear_locale=None
        )
    return LocaleResolution(locale=normalize_locale(ui_locale), clear_locale=None)
