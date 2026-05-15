"""Constrained enums for travel model fields.

Each StrEnum defines the valid values for a categorical field.
The ``_missing_`` override normalises LLM output (case, hyphens, spaces)
and falls back to a safe default so structured-output parsing never crashes.
"""

from enum import StrEnum


# ── helpers ──────────────────────────────────────────────────────────────


def _normalise(value: str) -> str:
    """Lowercase, strip whitespace, replace hyphens/spaces with underscores."""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _lookup_or_default(cls: type[StrEnum], value: object, default: StrEnum) -> StrEnum:
    """Try normalised match against *cls* members; return *default* on miss."""
    if not isinstance(value, str):
        return default
    normalised = _normalise(value)
    for member in cls:
        if member.value == normalised:
            return member
    return default


# ── enums ────────────────────────────────────────────────────────────────


class CabinClass(StrEnum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"

    @classmethod
    def _missing_(cls, value: object) -> "CabinClass":
        return _lookup_or_default(cls, value, cls.ECONOMY)


class TransitMode(StrEnum):
    WALK = "walk"
    TRANSIT = "transit"
    DRIVE = "drive"
    TRAIN = "train"
    BUS = "bus"
    FERRY = "ferry"
    BICYCLE = "bicycle"
    SUBWAY = "subway"

    @classmethod
    def _missing_(cls, value: object) -> "TransitMode":
        if isinstance(value, str):
            aliases = {
                "walking": cls.WALK,
                "driving": cls.DRIVE,
                "cycling": cls.BICYCLE,
            }
            hit = aliases.get(_normalise(value))
            if hit:
                return hit
        return _lookup_or_default(cls, value, cls.TRANSIT)


class DayPeriod(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"

    @classmethod
    def _missing_(cls, value: object) -> "DayPeriod":
        return _lookup_or_default(cls, value, cls.MORNING)


class AdvisoryLevel(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED = "red"

    @classmethod
    def _missing_(cls, value: object) -> "AdvisoryLevel":
        return _lookup_or_default(cls, value, cls.GREEN)


class PackingCategory(StrEnum):
    CLOTHING = "clothing"
    DOCUMENTS = "documents"
    TECH = "tech"
    HEALTH = "health"
    MONEY = "money"
    TOILETRIES = "toiletries"
    ACCESSORIES = "accessories"

    @classmethod
    def _missing_(cls, value: object) -> "PackingCategory":
        return _lookup_or_default(cls, value, cls.CLOTHING)


class TravelStyle(StrEnum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"

    @classmethod
    def _missing_(cls, value: object) -> "TravelStyle":
        return _lookup_or_default(cls, value, cls.MID_RANGE)


class GroupType(StrEnum):
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"
    GROUP = "group"

    @classmethod
    def _missing_(cls, value: object) -> "GroupType":
        return _lookup_or_default(cls, value, cls.SOLO)


class Season(StrEnum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

    @classmethod
    def _missing_(cls, value: object) -> "Season":
        return _lookup_or_default(cls, value, cls.SUMMER)
