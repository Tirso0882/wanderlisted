"""Deterministic conversation-language resolution for English and Polish v1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


SupportedLocale = Literal["en", "pl"]

_POLISH_DIACRITICS = frozenset("ąćęłńóśźż")
_TOKEN_PATTERN = re.compile(r"[^\W\d_]+", re.UNICODE)

# Function words plus common travel vocabulary make ASCII-only Polish detectable
# without guessing from city/provider names. A one-token acknowledgement such as
# "OK" intentionally remains ambiguous.
_POLISH_MARKERS = frozenset(
    {
        "a",
        "aby",
        "ale",
        "bez",
        "bilety",
        "chce",
        "chcę",
        "czy",
        "dla",
        "do",
        "dziekuje",
        "dziękuję",
        "gdzie",
        "hotel",
        "ile",
        "jest",
        "lot",
        "loty",
        "mi",
        "mnie",
        "na",
        "najtańszy",
        "od",
        "osoby",
        "plan",
        "podroz",
        "podróż",
        "polski",
        "proszę",
        "prosze",
        "tak",
        "tygodnie",
        "w",
        "wakacje",
        "wyjazd",
        "z",
        "za",
        "zaplanuj",
        "znajdź",
        "znajdz",
    }
)
_ENGLISH_MARKERS = frozenset(
    {
        "a",
        "activities",
        "and",
        "book",
        "budget",
        "can",
        "cheapest",
        "find",
        "flight",
        "flights",
        "for",
        "from",
        "hello",
        "hotel",
        "hotels",
        "i",
        "in",
        "is",
        "me",
        "my",
        "of",
        "on",
        "plan",
        "please",
        "thanks",
        "the",
        "to",
        "travel",
        "trip",
        "weeks",
        "with",
        "yes",
    }
)
_STRONG_POLISH = frozenset(
    {"cześć", "czesc", "dziękuję", "dziekuje", "proszę", "prosze", "zaplanuj"}
)
_STRONG_ENGLISH = frozenset({"hello", "thanks", "please"})


@dataclass(frozen=True, slots=True)
class LocaleResolution:
    """Resolved reply locale and whether this turn supplied clear evidence."""

    locale: SupportedLocale
    clear_locale: SupportedLocale | None


def normalize_locale(
    value: str | None, *, fallback: SupportedLocale = "en"
) -> SupportedLocale:
    """Normalize supported UI/request locale tags without accepting new locales."""

    if not value or not isinstance(value, str):
        return fallback
    language = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return "pl" if language == "pl" else "en" if language == "en" else fallback


def detect_clear_language(message: str) -> SupportedLocale | None:
    """Return a language only when bounded lexical evidence is clear.

    This is deliberately conservative: provider names, airport codes, numbers,
    URLs, and short acknowledgements do not reset conversation language.
    """

    normalized = message.casefold()
    tokens = [token.casefold() for token in _TOKEN_PATTERN.findall(normalized)]
    if not tokens:
        return None

    if any(character in _POLISH_DIACRITICS for character in normalized):
        return "pl"

    polish_score = sum(token in _POLISH_MARKERS for token in tokens)
    english_score = sum(token in _ENGLISH_MARKERS for token in tokens)

    if len(tokens) == 1:
        token = tokens[0]
        if token in _STRONG_POLISH:
            return "pl"
        if token in _STRONG_ENGLISH:
            return "en"
        return None

    if polish_score >= 2 and polish_score > english_score:
        return "pl"
    if english_score >= 2 and english_score > polish_score:
        return "en"
    return None


def resolve_response_locale(
    message: str,
    *,
    ui_locale: str | None,
    last_clear_locale: str | None = None,
) -> LocaleResolution:
    """Resolve clear turn -> prior clear turn -> selected UI locale."""

    clear_locale = detect_clear_language(message)
    if clear_locale is not None:
        return LocaleResolution(locale=clear_locale, clear_locale=clear_locale)
    if last_clear_locale in {"en", "pl"}:
        return LocaleResolution(
            locale=normalize_locale(last_clear_locale), clear_locale=None
        )
    return LocaleResolution(locale=normalize_locale(ui_locale), clear_locale=None)
