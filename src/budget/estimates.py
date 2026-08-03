"""Versioned, disclosed regional daily-cost estimates."""

from __future__ import annotations

from decimal import Decimal

from src.models import (
    BudgetCategory,
    Money,
    PriceBasis,
    PriceEvidence,
    PriceScope,
    SelectionStatus,
    TripRequest,
    TripSkeleton,
)
from src.tools.iata import resolve_iata_code
from src.tools.iata_repository import IATA_REPOSITORY

BASELINE_VERSION = "regional-usd-2026-08-v1"

_BASELINES: dict[str, dict[BudgetCategory, Decimal]] = {
    "east_asia": {
        BudgetCategory.MEALS: Decimal("40"),
        BudgetCategory.TRANSPORT: Decimal("15"),
        BudgetCategory.ACTIVITIES: Decimal("20"),
        BudgetCategory.MISC: Decimal("10"),
    },
    "southeast_asia": {
        BudgetCategory.MEALS: Decimal("20"),
        BudgetCategory.TRANSPORT: Decimal("8"),
        BudgetCategory.ACTIVITIES: Decimal("12"),
        BudgetCategory.MISC: Decimal("8"),
    },
    "western_europe": {
        BudgetCategory.MEALS: Decimal("55"),
        BudgetCategory.TRANSPORT: Decimal("20"),
        BudgetCategory.ACTIVITIES: Decimal("25"),
        BudgetCategory.MISC: Decimal("15"),
    },
    "eastern_europe": {
        BudgetCategory.MEALS: Decimal("30"),
        BudgetCategory.TRANSPORT: Decimal("10"),
        BudgetCategory.ACTIVITIES: Decimal("15"),
        BudgetCategory.MISC: Decimal("8"),
    },
    "north_america": {
        BudgetCategory.MEALS: Decimal("50"),
        BudgetCategory.TRANSPORT: Decimal("25"),
        BudgetCategory.ACTIVITIES: Decimal("30"),
        BudgetCategory.MISC: Decimal("15"),
    },
    "south_america": {
        BudgetCategory.MEALS: Decimal("25"),
        BudgetCategory.TRANSPORT: Decimal("10"),
        BudgetCategory.ACTIVITIES: Decimal("15"),
        BudgetCategory.MISC: Decimal("8"),
    },
    "south_asia": {
        BudgetCategory.MEALS: Decimal("20"),
        BudgetCategory.TRANSPORT: Decimal("8"),
        BudgetCategory.ACTIVITIES: Decimal("12"),
        BudgetCategory.MISC: Decimal("8"),
    },
    "middle_east": {
        BudgetCategory.MEALS: Decimal("40"),
        BudgetCategory.TRANSPORT: Decimal("20"),
        BudgetCategory.ACTIVITIES: Decimal("20"),
        BudgetCategory.MISC: Decimal("12"),
    },
    "oceania": {
        BudgetCategory.MEALS: Decimal("50"),
        BudgetCategory.TRANSPORT: Decimal("22"),
        BudgetCategory.ACTIVITIES: Decimal("25"),
        BudgetCategory.MISC: Decimal("15"),
    },
    "africa": {
        BudgetCategory.MEALS: Decimal("25"),
        BudgetCategory.TRANSPORT: Decimal("15"),
        BudgetCategory.ACTIVITIES: Decimal("20"),
        BudgetCategory.MISC: Decimal("10"),
    },
    "global": {
        BudgetCategory.MEALS: Decimal("40"),
        BudgetCategory.TRANSPORT: Decimal("18"),
        BudgetCategory.ACTIVITIES: Decimal("22"),
        BudgetCategory.MISC: Decimal("12"),
    },
}

_STYLE_MULTIPLIERS = {
    "budget": Decimal("0.6"),
    "mid-range": Decimal("1"),
    "luxury": Decimal("2"),
}

_COUNTRY_REGIONS = {
    "US": "north_america",
    "CA": "north_america",
    "MX": "north_america",
    "AR": "south_america",
    "BO": "south_america",
    "BR": "south_america",
    "CL": "south_america",
    "CO": "south_america",
    "EC": "south_america",
    "PE": "south_america",
    "UY": "south_america",
    "VE": "south_america",
    "BD": "south_asia",
    "IN": "south_asia",
    "LK": "south_asia",
    "PK": "south_asia",
    "JP": "east_asia",
    "CN": "east_asia",
    "HK": "east_asia",
    "KR": "east_asia",
    "MO": "east_asia",
    "TW": "east_asia",
    "BN": "southeast_asia",
    "ID": "southeast_asia",
    "KH": "southeast_asia",
    "LA": "southeast_asia",
    "MM": "southeast_asia",
    "MY": "southeast_asia",
    "PH": "southeast_asia",
    "SG": "southeast_asia",
    "TH": "southeast_asia",
    "TL": "southeast_asia",
    "VN": "southeast_asia",
    "AL": "eastern_europe",
    "BA": "eastern_europe",
    "BG": "eastern_europe",
    "BY": "eastern_europe",
    "CZ": "eastern_europe",
    "EE": "eastern_europe",
    "HR": "eastern_europe",
    "HU": "eastern_europe",
    "LT": "eastern_europe",
    "LV": "eastern_europe",
    "MD": "eastern_europe",
    "ME": "eastern_europe",
    "MK": "eastern_europe",
    "PL": "eastern_europe",
    "RO": "eastern_europe",
    "RS": "eastern_europe",
    "SK": "eastern_europe",
    "SI": "eastern_europe",
    "UA": "eastern_europe",
    "RU": "eastern_europe",
    "AE": "middle_east",
    "BH": "middle_east",
    "IL": "middle_east",
    "IR": "middle_east",
    "IQ": "middle_east",
    "JO": "middle_east",
    "KW": "middle_east",
    "LB": "middle_east",
    "OM": "middle_east",
    "PS": "middle_east",
    "QA": "middle_east",
    "SA": "middle_east",
    "TR": "middle_east",
    "AU": "oceania",
    "FJ": "oceania",
    "NZ": "oceania",
    "PG": "oceania",
    "EG": "africa",
    "ET": "africa",
    "GH": "africa",
    "KE": "africa",
    "MA": "africa",
    "NG": "africa",
    "ZA": "africa",
}


def _region_for_city(city: str) -> tuple[str, str]:
    code = resolve_iata_code(city)
    iso = IATA_REPOSITORY.country_iso_for_code(code) if code else ""
    if iso in _COUNTRY_REGIONS:
        return _COUNTRY_REGIONS[iso], iso
    if iso and iso in {
        "GB",
        "IE",
        "FR",
        "DE",
        "ES",
        "PT",
        "IT",
        "AT",
        "BE",
        "NL",
        "LU",
        "CH",
        "DK",
        "FI",
        "IS",
        "NO",
        "SE",
        "GR",
    }:
        return "western_europe", iso
    if (
        iso
        and iso not in {"US", "CA", "MX"}
        and IATA_REPOSITORY.country_for_code(code or "")
    ):
        country = IATA_REPOSITORY.country_for_code(code or "")
        # Countries not covered above intentionally use a disclosed global baseline.
        return "global", f"{iso}:{country}"
    return "global", "unresolved"


def _city_days(
    request: TripRequest, skeleton: TripSkeleton | None
) -> list[tuple[str, int]]:
    if skeleton and skeleton.stays:
        result = [(stay.city, stay.nights) for stay in skeleton.stays]
        city, days = result[-1]
        result[-1] = (city, days + 1)
        return result
    duration = request.date_window.duration_days or 1
    cities = request.destinations or ["unknown"]
    base, remainder = divmod(duration, len(cities))
    return [
        (city, base + (1 if index < remainder else 0))
        for index, city in enumerate(cities)
    ]


def regional_estimates(
    request: TripRequest,
    skeleton: TripSkeleton | None,
    *,
    uncovered: set[BudgetCategory],
) -> tuple[list[PriceEvidence], list[str]]:
    travelers = (
        (request.travelers.adults or 0)
        + request.travelers.children
        + request.travelers.infants
    )
    travelers = max(1, travelers)
    style = request.travel_style.strip().lower() or "mid-range"
    multiplier = _STYLE_MULTIPLIERS.get(style, Decimal("1"))
    assumptions: list[str] = []
    if style not in _STYLE_MULTIPLIERS:
        assumptions.append(
            f"Unknown travel style {style!r}; mid-range multiplier used."
        )

    estimates: list[PriceEvidence] = []
    allocations = _city_days(request, skeleton)
    for allocation_index, (city, days) in enumerate(allocations, start=1):
        region, source = _region_for_city(city)
        if region == "global":
            assumptions.append(
                f"{city}: country/region was {source}; global daily baseline used."
            )
        for category in sorted(uncovered, key=str):
            daily = _BASELINES[region][category] * multiplier
            total = daily * Decimal(days) * Decimal(travelers)
            estimates.append(
                PriceEvidence(
                    category=category,
                    money=Money(amount=total, currency="USD"),
                    source_component="budget_baseline",
                    source_id=(
                        f"{BASELINE_VERSION}:{allocation_index}:{region}:"
                        f"{city}:{category.value}"
                    ),
                    scope=PriceScope.TOTAL,
                    basis=PriceBasis.REGIONAL_ESTIMATE,
                    selection_status=SelectionStatus.SELECTED,
                    evidence_text=(
                        f"{daily} USD/person/day × {days} day(s) × {travelers} traveler(s)"
                    ),
                )
            )
    assumptions.append(
        "Multi-city estimate days use each stay's nights plus the final trip day."
        if skeleton and skeleton.stays
        else "Estimate days are allocated across the requested destinations."
    )
    assumptions.append(f"Daily estimates use baseline version {BASELINE_VERSION}.")
    return estimates, list(dict.fromkeys(assumptions))
