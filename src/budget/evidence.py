"""Assemble and validate only explicitly selected budget evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass

from langchain_core.messages import ToolMessage

from src.models import (
    BudgetCategory,
    ConversionRateRecord,
    DraftItinerary,
    HotelSearchPricing,
    Money,
    NonNumericPriceEvidence,
    PriceBasis,
    PriceEvidence,
    SelectionStatus,
    TripRequest,
    TripSkeleton,
)

_HOTEL_MARKER = "HOTEL_PRICING_JSON:\n"


@dataclass(frozen=True, slots=True)
class BudgetContext:
    request: TripRequest
    skeleton: TripSkeleton | None
    draft: DraftItinerary | None
    components: dict
    additional_evidence: tuple[PriceEvidence, ...] = ()
    stored_rates: tuple[ConversionRateRecord, ...] = ()


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("text")
        )
    return str(content or "")


def hotel_price_catalog(components: dict) -> dict[str, object]:
    catalog: dict[str, object] = {}
    for message in components.get("hotels", {}).get("messages", []):
        if (
            not isinstance(message, ToolMessage)
            or message.name != "search_hotels_hotelbeds"
        ):
            continue
        content = _text(message.content)
        if _HOTEL_MARKER not in content:
            continue
        try:
            payload = json.loads(content.split(_HOTEL_MARKER, 1)[1])
            pricing = HotelSearchPricing.model_validate(payload)
        except (json.JSONDecodeError, ValueError):
            continue
        for option in pricing.options:
            catalog[option.rate_key] = option
    return catalog


def assemble_price_evidence(
    context: BudgetContext,
) -> tuple[list[PriceEvidence], list[str]]:
    """Return selected, source-validated facts and validation warnings."""
    evidence: list[PriceEvidence] = []
    warnings: list[str] = []

    if context.skeleton and context.skeleton.selected_flight:
        price = context.skeleton.selected_flight.price_evidence
        if price and price.selection_status == SelectionStatus.SELECTED:
            evidence.append(price)
        else:
            warnings.append("Selected flight has no validated price evidence.")

    catalog = hotel_price_catalog(context.components)
    seen_rates: set[str] = set()
    if context.draft:
        for selected in context.draft.selected_accommodations:
            if selected.rate_key in seen_rates:
                continue
            seen_rates.add(selected.rate_key)
            catalog_option = catalog.get(selected.rate_key)
            if catalog_option is None:
                warnings.append(
                    f"Selected hotel rate {selected.rate_key} was not found in provider evidence."
                )
                continue
            supplied = selected.price_evidence
            if supplied is not None and (
                supplied.money != catalog_option.money
                or supplied.source_id != selected.rate_key
            ):
                warnings.append(
                    f"Selected hotel rate {selected.rate_key} price did not match provider evidence."
                )
                continue
            evidence.append(
                PriceEvidence(
                    category=BudgetCategory.ACCOMMODATION,
                    money=catalog_option.money,
                    source_component="hotels",
                    source_id=selected.rate_key,
                    basis=PriceBasis.QUOTED,
                    selection_status=SelectionStatus.SELECTED,
                    observed_at=catalog_option.observed_at,
                    evidence_text=f"{catalog_option.hotel_name}; total stay",
                )
            )

    for index, known in enumerate(context.request.known_costs):
        evidence.append(
            PriceEvidence(
                category=known.category,
                money=Money(
                    amount=known.money.amount,
                    currency=known.money.currency,
                ),
                source_component="traveler",
                source_id=f"traveler:{index}:{known.category.value}",
                scope=known.scope,
                basis=PriceBasis.USER_SUPPLIED,
                selection_status=SelectionStatus.USER_SUPPLIED,
                evidence_text=known.note,
            )
        )

    existing_ids = {(item.source_component, item.source_id) for item in evidence}
    for item in context.additional_evidence:
        identity = (item.source_component, item.source_id)
        if item.selection_status not in {
            SelectionStatus.SELECTED,
            SelectionStatus.USER_SUPPLIED,
        }:
            continue
        if identity in existing_ids:
            warnings.append(
                f"Duplicate price evidence {item.source_component}/{item.source_id} was ignored."
            )
            continue
        evidence.append(item)
        existing_ids.add(identity)

    return evidence, warnings


def non_numeric_price_evidence(context: BudgetContext) -> list[NonNumericPriceEvidence]:
    """Retain Places price levels and Routes no-fare facts without monetizing them."""
    signals: list[NonNumericPriceEvidence] = []
    seen: set[tuple[str, str, str]] = set()

    def add(signal: NonNumericPriceEvidence) -> None:
        identity = (signal.source_component, signal.source_id, signal.signal)
        if identity not in seen:
            seen.add(identity)
            signals.append(signal)

    if context.draft:
        for day in context.draft.days:
            places = [day.start_location, *day.stops]
            if day.end_location is not None:
                places.append(day.end_location)
            for place in places:
                if not place.price_level:
                    continue
                source_id = place.place_id or f"{place.name}|{place.address}"
                category_text = place.category.lower()
                category = (
                    BudgetCategory.MEALS
                    if any(
                        marker in category_text
                        for marker in ("restaurant", "cafe", "food", "bakery", "bar")
                    )
                    else BudgetCategory.ACTIVITIES
                )
                add(
                    NonNumericPriceEvidence(
                        source_component="places",
                        source_id=source_id,
                        category=category,
                        signal="price_level",
                        value=place.price_level,
                        excluded_reason=(
                            "Google Places price levels are ordinal signals, not amounts."
                        ),
                    )
                )

    route_data = context.components.get("route_plan_structured")
    if route_data:
        for day in route_data.get("days", []):
            day_number = day.get("day_number", "unknown")
            add(
                NonNumericPriceEvidence(
                    source_component="routes",
                    source_id=f"route-day:{day_number}",
                    category=BudgetCategory.TRANSPORT,
                    signal="fare_status",
                    value="not_provided",
                    excluded_reason="Google Routes returned routing data without fares.",
                )
            )

    return signals
