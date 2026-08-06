"""Typed ItineraryAgent selection, scheduling, and grounded rendering inputs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from typing import Any

from src.itinerary.evidence import ItineraryEvidenceCatalog
from src.models import (
    BudgetBreakdown,
    BudgetCategory,
    DayPlan,
    DraftDay,
    DraftItinerary,
    FeasibilityStatus,
    HotelEvidence,
    ItineraryCoverageStatus,
    ItineraryPlan,
    ItinerarySelectionProposal,
    Money,
    PlaceCard,
    PlaceEvidence,
    PlaceRef,
    PriceBasis,
    PriceEvidence,
    PriceScope,
    RouteLeg,
    RoutePlan,
    RequestedCapability,
    SelectedAccommodation,
    SelectionStatus,
    TimeBlock,
    TransitStep,
    TripRequest,
    TripSkeleton,
)
from src.tools.iata import resolve_iata_code


DAY_START_MINUTE = 9 * 60
DAY_END_MINUTE = 21 * 60
STOP_BUFFER_MINUTES = 15
REST_BREAK_MINUTES = 30
MAX_STOPS_PER_DAY = 5


class ItineraryValidationError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(dict.fromkeys(str(error) for error in errors if error))
        super().__init__("; ".join(self.errors) or "itinerary validation failed")


@dataclass(frozen=True, slots=True)
class ItinerarySelectionContext:
    request: TripRequest
    skeleton: TripSkeleton
    catalog: ItineraryEvidenceCatalog
    feedback: str = ""
    raw_evidence: str = ""


@dataclass(frozen=True, slots=True)
class ItineraryAssemblyContext:
    request: TripRequest
    skeleton: TripSkeleton
    draft: DraftItinerary
    route_plan: RoutePlan | None
    budget: BudgetBreakdown | None = None
    readiness: Any | None = None
    request_revision: int = 0


@dataclass(frozen=True, slots=True)
class ItineraryRun:
    plan: ItineraryPlan
    message: str


def _date_city(skeleton: TripSkeleton, current: date) -> str:
    if current == skeleton.end_date:
        return skeleton.exit_city
    for stay in skeleton.stays:
        if stay.check_in <= current < stay.check_out:
            return stay.city
    raise ItineraryValidationError([f"no city stay covers {current.isoformat()}"])


def _stay_for_date(skeleton: TripSkeleton, current: date):
    if current == skeleton.end_date:
        return skeleton.stays[-1]
    for stay in skeleton.stays:
        if stay.check_in <= current < stay.check_out:
            return stay
    raise ItineraryValidationError(
        [f"no accommodation stay covers {current.isoformat()}"]
    )


def _hotel_ref(hotel: HotelEvidence) -> PlaceRef:
    return PlaceRef(
        name=hotel.name,
        source_component="hotels",
        source_id=hotel.rate_key,
        address=hotel.address,
        place_id=hotel.place_id,
        latitude=hotel.latitude,
        longitude=hotel.longitude,
        category="hotel",
        description=hotel.description,
        website_url=hotel.website_url,
        google_maps_url=hotel.google_maps_url,
        photo_urls=hotel.photo_urls,
    )


def _place_ref(place: PlaceEvidence) -> PlaceRef:
    return PlaceRef(
        name=place.name,
        source_component=place.source_component,
        source_id=place.source_id,
        address=place.address,
        place_id=place.place_id,
        latitude=place.latitude,
        longitude=place.longitude,
        category=place.category,
        price_level=place.price_level,
        rating=place.rating,
        review_count=place.review_count,
        description=place.description,
        website_url=place.website_url,
        google_maps_url=place.google_maps_url,
        photo_urls=place.photo_urls,
        opening_hours=place.opening_hours,
        opening_periods=place.opening_periods,
        utc_offset_minutes=place.utc_offset_minutes,
        estimated_duration_minutes=place.estimated_duration_minutes,
    )


def _city_anchor(city: str) -> PlaceRef:
    """Return a non-booking route anchor without inventing accommodation facts."""
    return PlaceRef(
        name=f"{city.title()} city centre",
        source_component="trip_request",
        source_id=f"city-anchor:{city.casefold()}",
        address=city,
        category="city_anchor",
    )


def _is_beach_place(place: PlaceEvidence) -> bool:
    labels = [place.category, *place.types]
    return any("beach" in label.casefold() for label in labels)


def resolve_selection(
    proposal: ItinerarySelectionProposal,
    context: ItinerarySelectionContext,
) -> DraftItinerary:
    """Resolve model-selected IDs to immutable evidence and canonical dates."""
    errors: list[str] = []
    skeleton = context.skeleton
    day_proposals = {item.day_number: item for item in proposal.days}
    if len(day_proposals) != len(proposal.days):
        errors.append("day selections must use unique day numbers")
    invalid_days = sorted(
        number
        for number in day_proposals
        if number < 1 or number > skeleton.duration_days
    )
    if invalid_days:
        errors.append(f"day selections outside canonical range: {invalid_days}")

    accommodation_proposals = {
        item.stay_sequence: item for item in proposal.accommodations
    }
    if len(accommodation_proposals) != len(proposal.accommodations):
        errors.append("accommodation selections must use unique stay sequences")
    accommodation_rate_keys = [item.rate_key for item in proposal.accommodations]
    if len(accommodation_rate_keys) != len(set(accommodation_rate_keys)):
        errors.append("accommodation selections must use unique hotel rate keys")

    selected_hotels: dict[int, HotelEvidence] = {}
    selected_accommodations: list[SelectedAccommodation] = []
    hotels_authorized = (
        RequestedCapability.HOTELS in context.request.requested_capabilities
        and RequestedCapability.HOTELS not in context.request.declined_capabilities
    )
    for stay in skeleton.stays:
        selection = accommodation_proposals.get(stay.sequence)
        if selection is None:
            if hotels_authorized:
                errors.append(f"stay {stay.sequence} has no selected accommodation")
            continue
        if not hotels_authorized:
            errors.append("accommodation was selected without hotel-search consent")
            continue
        hotel = context.catalog.hotels.get(selection.rate_key)
        if hotel is None:
            errors.append(f"unknown hotel rate key: {selection.rate_key}")
            continue
        expected_city_code = resolve_iata_code(stay.city)
        if (
            hotel.city_code
            and expected_city_code
            and hotel.city_code.casefold() != expected_city_code.casefold()
        ):
            errors.append(
                f"hotel {hotel.rate_key} belongs to {hotel.city_code}, "
                f"not stay {stay.sequence} {stay.city}"
            )
            continue
        if hotel.check_in and hotel.check_in != stay.check_in.isoformat():
            errors.append(
                f"hotel {hotel.rate_key} check-in contradicts stay {stay.sequence}"
            )
            continue
        if hotel.check_out and hotel.check_out != stay.check_out.isoformat():
            errors.append(
                f"hotel {hotel.rate_key} check-out contradicts stay {stay.sequence}"
            )
            continue
        try:
            amount = Decimal(hotel.amount)
        except Exception:
            amount = Decimal("0")
        evidence = PriceEvidence(
            category=BudgetCategory.ACCOMMODATION,
            money=Money(amount=amount, currency=hotel.currency),
            source_component="hotels",
            source_id=hotel.rate_key,
            scope=PriceScope.TOTAL,
            basis=PriceBasis.QUOTED,
            selection_status=SelectionStatus.SELECTED,
        )
        selected_hotels[stay.sequence] = hotel
        selected_accommodations.append(
            SelectedAccommodation(
                stay_sequence=stay.sequence,
                name=hotel.name,
                rate_key=hotel.rate_key,
                price_evidence=evidence,
            )
        )

    seen_stops: set[str] = set()
    beach_days: set[int] = set()
    days: list[DraftDay] = []
    for offset in range(skeleton.duration_days):
        day_number = offset + 1
        current = skeleton.start_date + timedelta(days=offset)
        city = _date_city(skeleton, current)
        stay = _stay_for_date(skeleton, current)
        hotel = selected_hotels.get(stay.sequence)
        anchor = _hotel_ref(hotel) if hotel is not None else _city_anchor(city)
        selection = day_proposals.get(day_number)
        stop_ids = list(selection.stop_source_ids) if selection else []
        if len(stop_ids) > MAX_STOPS_PER_DAY:
            errors.append(f"day {day_number} exceeds {MAX_STOPS_PER_DAY} stops")
        stops: list[PlaceRef] = []
        for source_id in stop_ids:
            if source_id in seen_stops:
                errors.append(f"duplicate selected stop: {source_id}")
                continue
            evidence = context.catalog.places.get(source_id)
            if evidence is None:
                errors.append(f"unknown place source ID: {source_id}")
                continue
            if evidence.city and evidence.city.casefold() != city.casefold():
                errors.append(
                    f"place {source_id} belongs to {evidence.city}, not day {day_number} {city}"
                )
                continue
            seen_stops.add(source_id)
            if _is_beach_place(evidence):
                beach_days.add(day_number)
            stops.append(_place_ref(evidence))
        days.append(
            DraftDay(
                day_number=day_number,
                date=current.isoformat(),
                city=city,
                start_location=anchor,
                end_location=anchor,
                stops=stops,
                preferred_mode=(
                    context.request.primary_transport_mode
                    or (selection.preferred_mode if selection else "transit")
                ),
            )
        )

    if set(accommodation_proposals) - {stay.sequence for stay in skeleton.stays}:
        errors.append("accommodation proposal references an unknown stay")
    if not seen_stops:
        errors.append("no provider-backed stops were selected")
    if len(beach_days) < context.request.minimum_beach_days:
        errors.append(
            "minimum beach-day requirement is not covered by selected provider evidence"
        )
    if len(days) != skeleton.duration_days:
        errors.append("canonical day construction is incomplete")
    if errors:
        raise ItineraryValidationError(errors)
    return DraftItinerary(
        days=days,
        selected_accommodations=selected_accommodations,
        selection_notes=[
            *proposal.selection_notes,
            *context.catalog.warnings,
            *(
                [
                    "Hotel search was not authorized; city-centre route anchors are used and accommodation is not selected or priced."
                ]
                if not hotels_authorized
                else []
            ),
        ],
    )


def validate_legacy_draft(
    draft: DraftItinerary,
    context: ItinerarySelectionContext,
    *,
    raw_evidence: str,
) -> DraftItinerary:
    """Compatibility adapter: resolve only unique, exact catalog-name matches."""
    accommodation_by_stay = {
        item.stay_sequence: item for item in draft.selected_accommodations
    }
    days: list[DraftDay] = []
    selected_accommodations: list[SelectedAccommodation] = []
    selected_hotels: dict[int, HotelEvidence] = {}
    errors: list[str] = []
    for stay in context.skeleton.stays:
        selected = accommodation_by_stay.get(stay.sequence)
        hotel = (
            context.catalog.hotels.get(selected.rate_key)
            if selected is not None
            else None
        )
        if selected is None or hotel is None:
            errors.append(
                f"legacy draft lacks a validated hotel for stay {stay.sequence}"
            )
            continue
        if selected.name != hotel.name:
            errors.append(
                f"legacy hotel is not an exact evidence match: {selected.name}"
            )
            continue
        selected_hotels[stay.sequence] = hotel
        selected_accommodations.append(
            SelectedAccommodation(
                stay_sequence=stay.sequence,
                name=hotel.name,
                rate_key=hotel.rate_key,
                price_evidence=selected.price_evidence,
            )
        )
    draft_by_number = {item.day_number: item for item in draft.days}
    seen: set[str] = set()
    for offset in range(context.skeleton.duration_days):
        number = offset + 1
        current = context.skeleton.start_date + timedelta(days=offset)
        old = draft_by_number.get(number)
        if old is None:
            errors.append(f"legacy draft omitted day {number}")
            continue
        stay = _stay_for_date(context.skeleton, current)
        hotel = selected_hotels.get(stay.sequence)
        if hotel is None:
            continue
        if old.start_location.name != hotel.name:
            errors.append(
                f"legacy hotel is not an exact evidence match: {old.start_location.name}"
            )
        canonical_stops: list[PlaceRef] = []
        for stop in old.stops:
            matches = [
                item
                for item in context.catalog.places.values()
                if item.name == stop.name
                and (
                    not item.city
                    or item.city.casefold()
                    == _date_city(context.skeleton, current).casefold()
                )
            ]
            if len(matches) != 1:
                errors.append(
                    f"legacy stop is not an exact evidence match: {stop.name}"
                )
                continue
            evidence = matches[0]
            source_id = evidence.source_id
            if source_id in seen:
                errors.append(f"duplicate legacy stop: {stop.name}")
                continue
            seen.add(source_id)
            canonical_stops.append(_place_ref(evidence))
        days.append(
            old.model_copy(
                update={
                    "date": current.isoformat(),
                    "city": _date_city(context.skeleton, current),
                    "start_location": _hotel_ref(hotel),
                    "end_location": _hotel_ref(hotel),
                    "stops": canonical_stops,
                }
            )
        )
    if not seen:
        errors.append("legacy draft selected no exact evidence-backed stops")
    if errors:
        raise ItineraryValidationError(errors)
    return DraftItinerary(
        days=days,
        selected_accommodations=selected_accommodations,
        selection_notes=[*draft.selection_notes, "Legacy exact-match adapter used."],
        mobility_notes=draft.mobility_notes,
    )


def compute_artifact_fingerprint(context: ItineraryAssemblyContext) -> str:
    def _dump(value):
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        return value

    payload = {
        "request": context.request.model_dump(mode="json"),
        "skeleton": context.skeleton.model_dump(mode="json"),
        "draft": context.draft.model_dump(mode="json"),
        "route_plan": (
            context.route_plan.model_dump(mode="json") if context.route_plan else None
        ),
        "budget": _dump(context.budget),
        "readiness": _dump(context.readiness),
        "request_revision": context.request_revision,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _clock(value: int) -> str:
    value = max(0, min(value, 24 * 60 - 1))
    return f"{value // 60:02d}:{value % 60:02d}"


def _duration(ref: PlaceRef) -> tuple[int, str]:
    if ref.estimated_duration_minutes > 0:
        return ref.estimated_duration_minutes, "provider"
    category = ref.category.casefold()
    if any(
        token in category
        for token in ("museum", "gallery", "aquarium", "zoo", "attraction")
    ):
        return 120, "configured_estimate"
    if any(
        token in category
        for token in ("park", "landmark", "shopping", "place_of_worship")
    ):
        return 90, "configured_estimate"
    if any(token in category for token in ("restaurant", "cafe", "food", "meal")):
        return 75, "configured_estimate"
    if "event" in category:
        return 120, "configured_estimate"
    return 90, "configured_estimate"


def _opening_fit(
    ref: PlaceRef, current: date, earliest: int, duration: int
) -> int | None:
    if not ref.opening_periods:
        return earliest
    google_day = (current.weekday() + 1) % 7
    windows: list[tuple[int, int]] = []
    week_minutes = 7 * 24 * 60
    day_start = google_day * 24 * 60
    day_end = day_start + 24 * 60
    for period in ref.opening_periods:
        opened = period.open_day * 24 * 60 + _minutes(period.open_time)
        closed = period.close_day * 24 * 60 + _minutes(period.close_time)
        if closed <= opened:
            closed += week_minutes
        for shift in (-week_minutes, 0, week_minutes):
            shifted_open = opened + shift
            shifted_close = closed + shift
            overlap_start = max(day_start, shifted_open)
            overlap_end = min(day_end, shifted_close)
            if overlap_start < overlap_end:
                windows.append((overlap_start - day_start, overlap_end - day_start))
    for opened, closed in sorted(windows):
        start = max(earliest, opened)
        if start + duration <= closed:
            return start
    return None


def _period(minute: int) -> str:
    if minute < 12 * 60:
        return "morning"
    if minute < 18 * 60:
        return "afternoon"
    return "evening"


def _place_card(
    ref: PlaceRef,
    *,
    start: str,
    end: str,
    duration: int,
    duration_basis: str,
    cost: float,
) -> PlaceCard:
    return PlaceCard(
        source_component=ref.source_component,
        source_id=ref.source_id,
        name=ref.name,
        category=ref.category,
        rating=ref.rating,
        review_count=ref.review_count,
        price_level=ref.price_level,
        address=ref.address,
        description=ref.description,
        website_url=ref.website_url,
        google_maps_url=ref.google_maps_url,
        photo_urls=ref.photo_urls,
        opening_hours=ref.opening_hours,
        latitude=ref.latitude,
        longitude=ref.longitude,
        estimated_cost_usd=cost,
        estimated_duration_minutes=duration,
        scheduled_start=start,
        scheduled_end=end,
        duration_basis=duration_basis,
    )


def _transit_step(
    leg: RouteLeg,
    *,
    day_number: int,
    index: int,
    start: int,
    timing_reliable: bool,
) -> TransitStep:
    end = start + (leg.duration_seconds + 59) // 60
    return TransitStep(
        mode=leg.mode,
        from_place=leg.from_place,
        to_place=leg.to_place,
        distance_text=f"{leg.distance_meters / 1000:.1f} km",
        duration_text=f"{max(0, round(leg.duration_seconds / 60))} min",
        instructions="; ".join(leg.instructions),
        distance_meters=leg.distance_meters,
        duration_seconds=leg.duration_seconds,
        route_leg_index=index,
        source_day_number=day_number,
        scheduled_start=_clock(start) if timing_reliable else "",
        scheduled_end=_clock(end) if timing_reliable else "",
    )


def _status_rank(status: FeasibilityStatus) -> int:
    return {
        FeasibilityStatus.VERIFIED: 0,
        FeasibilityStatus.NEEDS_REVIEW: 1,
        FeasibilityStatus.INFEASIBLE: 2,
    }[status]


class ItineraryPipeline:
    """Compile canonical artifacts into a date- and source-validated plan."""

    def run(self, context: ItineraryAssemblyContext) -> ItineraryRun:
        if not context.draft.days:
            raise ItineraryValidationError(["draft itinerary has no days"])
        if not any(day.stops for day in context.draft.days):
            raise ItineraryValidationError(["draft itinerary has no schedulable stops"])
        draft_day_numbers = [day.day_number for day in context.draft.days]
        if len(draft_day_numbers) != len(set(draft_day_numbers)):
            raise ItineraryValidationError(["draft contains duplicate day numbers"])
        selected_source_ids = [
            stop.source_id for day in context.draft.days for stop in day.stops
        ]
        if any(not source_id for source_id in selected_source_ids):
            raise ItineraryValidationError(
                ["every selected stop must have a stable source ID"]
            )
        if len(selected_source_ids) != len(set(selected_source_ids)):
            raise ItineraryValidationError(
                ["selected stop source IDs must be unique across the trip"]
            )
        accommodation_by_stay = {
            item.stay_sequence: item for item in context.draft.selected_accommodations
        }
        expected_stays = {stay.sequence for stay in context.skeleton.stays}
        hotels_authorized = (
            RequestedCapability.HOTELS in context.request.requested_capabilities
            and RequestedCapability.HOTELS not in context.request.declined_capabilities
        )
        if hotels_authorized and set(accommodation_by_stay) != expected_stays:
            raise ItineraryValidationError(
                ["draft accommodations must cover every canonical city stay"]
            )
        if not hotels_authorized and accommodation_by_stay:
            raise ItineraryValidationError(
                ["draft contains accommodation without hotel-search consent"]
            )

        route_days = list(context.route_plan.days if context.route_plan else [])
        route_by_day = {item.day_number: item for item in route_days}
        if len(route_by_day) != len(route_days):
            raise ItineraryValidationError(
                ["route plan contains duplicate day numbers"]
            )
        unknown_route_days = set(route_by_day) - set(
            range(1, context.skeleton.duration_days + 1)
        )
        if unknown_route_days:
            raise ItineraryValidationError(
                [f"route plan contains unknown days: {sorted(unknown_route_days)}"]
            )
        budget_items = {
            item.source_id: item
            for item in (context.budget.line_items if context.budget else [])
            if item.amount_usd is not None and not item.estimated
        }
        weather_by_date = {
            item.date: item for item in getattr(context.readiness, "weather", [])
        }
        transition_dates = {
            stay.check_in for stay in context.skeleton.stays if stay.sequence > 1
        }
        pace_needs_rest = bool(context.request.accessibility_needs) or (
            context.request.travelers.children > 0
            or context.request.travelers.infants > 0
        )

        days: list[DayPlan] = []
        plan_warnings: list[str] = []
        missing_constraints: list[str] = []
        if not hotels_authorized:
            missing_constraints.append("accommodation_not_selected")
        overall = FeasibilityStatus.VERIFIED

        draft_by_day = {item.day_number: item for item in context.draft.days}
        for offset in range(context.skeleton.duration_days):
            number = offset + 1
            current = context.skeleton.start_date + timedelta(days=offset)
            draft_day = draft_by_day.get(number)
            if draft_day is None:
                raise ItineraryValidationError(
                    [f"draft omitted canonical day {number}"]
                )
            stay = _stay_for_date(context.skeleton, current)
            end_location = draft_day.end_location or draft_day.start_location
            if hotels_authorized:
                selected_hotel = accommodation_by_stay[stay.sequence]
                if (
                    draft_day.start_location.source_id != selected_hotel.rate_key
                    or end_location.source_id != selected_hotel.rate_key
                ):
                    raise ItineraryValidationError(
                        [f"day {number} hotel locations do not match the selected rate"]
                    )
            elif (
                draft_day.start_location.category != "city_anchor"
                or end_location.category != "city_anchor"
            ):
                raise ItineraryValidationError(
                    [f"day {number} requires non-booking city anchors"]
                )
            route = route_by_day.get(number)
            day_warnings: list[str] = []
            day_assumptions = [
                "Visit durations use versioned category defaults unless provider evidence supplies one.",
                "A 15-minute handling buffer is added at every scheduled stop.",
            ]
            day_status = FeasibilityStatus.VERIFIED
            selected_ids = [stop.source_id for stop in draft_day.stops]
            selected_by_id = {stop.source_id: stop for stop in draft_day.stops}
            route_order = list(route.ordered_stops) if route else []
            ordered_ids = [stop.source_id for stop in route_order]
            if not route:
                ordered = list(draft_day.stops)
                day_status = FeasibilityStatus.NEEDS_REVIEW
                warning = f"Day {number}: no measured route plan is available."
                day_warnings.append(warning)
                missing_constraints.append("route_plan")
            elif Counter(ordered_ids) != Counter(selected_ids):
                raise ItineraryValidationError(
                    [f"day {number} route references stops outside the selected draft"]
                )
            else:
                ordered = [selected_by_id[source_id] for source_id in ordered_ids]

            legs = list(route.legs) if route else []
            legs_by_index: dict[int, RouteLeg] = {}
            for fallback_index, leg in enumerate(legs):
                leg_index = (
                    leg.route_leg_index
                    if leg.route_leg_index is not None
                    else fallback_index
                )
                if leg_index in legs_by_index:
                    raise ItineraryValidationError(
                        [f"day {number} route contains duplicate leg index {leg_index}"]
                    )
                legs_by_index[leg_index] = leg
            expected_leg_indexes = set(range(len(ordered) + 1))
            timing_reliable = bool(route) and set(legs_by_index) == expected_leg_indexes
            if route and route.warning:
                day_status = FeasibilityStatus.NEEDS_REVIEW
                day_warnings.append(route.warning)
                missing_constraints.append(f"day_{number}_route")
            if route and not timing_reliable:
                day_status = FeasibilityStatus.NEEDS_REVIEW
                day_warnings.append(
                    f"Day {number}: measured route has {len(legs)} of {len(ordered) + 1} required legs."
                )
                missing_constraints.append(f"day_{number}_route_legs")
            if current in transition_dates:
                day_status = max(
                    day_status,
                    FeasibilityStatus.NEEDS_REVIEW,
                    key=_status_rank,
                )
                day_warnings.append(
                    "Inter-city transfer timing is not present in the canonical artifacts."
                )
                missing_constraints.append(f"day_{number}_intercity_transfer_time")
            if number in {1, context.skeleton.duration_days}:
                day_status = max(
                    day_status,
                    FeasibilityStatus.NEEDS_REVIEW,
                    key=_status_rank,
                )
                day_warnings.append(
                    "Arrival/departure clock time is unavailable; time slots are planning estimates."
                )
                missing_constraints.append(f"day_{number}_flight_time")

            blocks: dict[str, TimeBlock] = {}
            unscheduled: list[PlaceCard] = []
            cursor = DAY_START_MINUTE
            scheduled_count = 0
            for index, stop in enumerate(ordered):
                if index >= MAX_STOPS_PER_DAY:
                    remaining = ordered[index:]
                    unscheduled.extend(
                        _place_card(
                            item,
                            start="",
                            end="",
                            duration=_duration(item)[0],
                            duration_basis=_duration(item)[1],
                            cost=0,
                        )
                        for item in remaining
                    )
                    day_status = FeasibilityStatus.INFEASIBLE
                    day_warnings.append("The five-stop daily limit was exceeded.")
                    break
                if pace_needs_rest and scheduled_count and scheduled_count % 2 == 0:
                    cursor += REST_BREAK_MINUTES
                    day_assumptions.append(
                        "A 30-minute rest break follows every two stops for this party."
                    )
                incoming = legs_by_index.get(index)
                transit: TransitStep | None = None
                if incoming is not None:
                    transit = _transit_step(
                        incoming,
                        day_number=number,
                        index=index,
                        start=cursor,
                        timing_reliable=timing_reliable,
                    )
                    cursor += (incoming.duration_seconds + 59) // 60
                cursor += STOP_BUFFER_MINUTES
                duration, basis = _duration(stop)
                if not stop.opening_periods:
                    day_status = max(
                        day_status,
                        FeasibilityStatus.NEEDS_REVIEW,
                        key=_status_rank,
                    )
                    day_warnings.append(
                        f"Opening hours are unavailable for {stop.name}."
                    )
                    missing_constraints.append(f"opening_hours:{stop.source_id}")
                fitted = _opening_fit(stop, current, cursor, duration)
                remaining_route_minutes = sum(
                    (legs_by_index[leg_index].duration_seconds + 59) // 60
                    for leg_index in range(index + 1, len(ordered) + 1)
                    if leg_index in legs_by_index
                )
                latest_end = DAY_END_MINUTE - remaining_route_minutes
                if fitted is None or fitted + duration > latest_end:
                    for item in ordered[index:]:
                        item_duration, item_basis = _duration(item)
                        item_cost = float(
                            budget_items[item.source_id].amount_usd
                            if item.source_id in budget_items
                            else 0
                        )
                        unscheduled.append(
                            _place_card(
                                item,
                                start="",
                                end="",
                                duration=item_duration,
                                duration_basis=item_basis,
                                cost=item_cost,
                            )
                        )
                    reason = (
                        f"{stop.name} does not fit its known opening hours."
                        if fitted is None
                        else f"{stop.name} and later stops exceed the 21:00 day limit."
                    )
                    day_warnings.append(reason)
                    day_status = FeasibilityStatus.INFEASIBLE
                    break
                cursor = fitted
                item = budget_items.get(stop.source_id)
                cost = (
                    float(item.amount_usd)
                    if item and item.amount_usd is not None
                    else 0.0
                )
                start_text = _clock(cursor) if timing_reliable else ""
                end_text = _clock(cursor + duration) if timing_reliable else ""
                card = _place_card(
                    stop,
                    start=start_text,
                    end=end_text,
                    duration=duration,
                    duration_basis=basis,
                    cost=cost,
                )
                period = _period(cursor)
                block = blocks.setdefault(period, TimeBlock(period=period))
                if transit is not None:
                    block.transit.append(transit)
                if stop.source_component == "restaurants" or any(
                    token in stop.category.casefold()
                    for token in ("restaurant", "cafe", "food")
                ):
                    if block.restaurant is None:
                        block.restaurant = card
                    else:
                        block.activities.append(card)
                else:
                    block.activities.append(card)
                block.subtotal_usd += cost
                if start_text and (
                    not block.start_time or start_text < block.start_time
                ):
                    block.start_time = start_text
                if end_text and end_text > block.end_time:
                    block.end_time = end_text
                cursor += duration
                scheduled_count += 1

            # The final measured leg starts at the last RoutePlan stop.  Once a
            # selected stop is unscheduled, that origin was not visited and the
            # leg must not be presented as the traveler's return route.
            final_leg = legs_by_index.get(len(ordered))
            if (
                legs
                and scheduled_count
                and scheduled_count == len(ordered)
                and final_leg is not None
            ):
                final_transit = _transit_step(
                    final_leg,
                    day_number=number,
                    index=len(ordered),
                    start=cursor,
                    timing_reliable=timing_reliable,
                )
                final_period = _period(min(cursor, DAY_END_MINUTE - 1))
                blocks.setdefault(
                    final_period, TimeBlock(period=final_period)
                ).transit.append(final_transit)
                cursor += (final_leg.duration_seconds + 59) // 60
                if cursor > DAY_END_MINUTE:
                    day_status = FeasibilityStatus.INFEASIBLE
                    day_warnings.append(
                        "The measured return to the hotel ends after 21:00."
                    )

            scheduled_ids = {
                card.source_id
                for block in blocks.values()
                for card in [
                    *block.activities,
                    *([block.restaurant] if block.restaurant else []),
                ]
            }
            daily_cost = sum(
                float(budget_items[source_id].amount_usd or 0)
                for source_id in scheduled_ids
                if source_id in budget_items
            )
            if context.budget is None:
                cost_coverage = "unavailable"
            elif scheduled_ids and scheduled_ids.issubset(budget_items):
                cost_coverage = "complete"
            else:
                cost_coverage = "partial"
            walking_meters = sum(
                leg.distance_meters for leg in legs if str(leg.mode) == "walk"
            )
            ordered_blocks = [
                blocks[name]
                for name in ("morning", "afternoon", "evening")
                if name in blocks
            ]
            day_plan = DayPlan(
                day_number=number,
                date=current.isoformat(),
                city=_date_city(context.skeleton, current),
                weather=weather_by_date.get(current.isoformat()),
                time_blocks=ordered_blocks,
                daily_cost_usd=round(daily_cost, 2),
                walking_km=round(walking_meters / 1000, 2),
                feasibility_status=day_status,
                feasibility_warnings=list(dict.fromkeys(day_warnings)),
                assumptions=list(dict.fromkeys(day_assumptions)),
                cost_coverage=cost_coverage,
                unscheduled_stops=unscheduled,
            )
            days.append(day_plan)
            overall = max(overall, day_status, key=_status_rank)
            plan_warnings.extend(day_plan.feasibility_warnings)

        if not any(day.time_blocks for day in days):
            raise ItineraryValidationError(
                ["no schedulable days remain after validation"]
            )
        coverage = (
            ItineraryCoverageStatus.COMPLETE
            if overall == FeasibilityStatus.VERIFIED and not missing_constraints
            else ItineraryCoverageStatus.PARTIAL
        )
        plan = ItineraryPlan(
            start_date=context.skeleton.start_date.isoformat(),
            end_date=context.skeleton.end_date.isoformat(),
            duration_days=context.skeleton.duration_days,
            days=days,
            coverage_status=coverage,
            feasibility_status=overall,
            missing_constraints=list(dict.fromkeys(missing_constraints)),
            warnings=list(dict.fromkeys(plan_warnings)),
            artifact_fingerprint=compute_artifact_fingerprint(context),
            request_revision=context.request_revision,
            total_budget_usd=context.budget.total if context.budget else 0,
        )
        return ItineraryRun(plan=plan, message=render_plan_message(plan))


def render_plan_message(plan: ItineraryPlan) -> str:
    lines = [
        f"## Itinerary — {plan.start_date} to {plan.end_date}",
        f"Feasibility: **{plan.feasibility_status}** · Coverage: **{plan.coverage_status}**",
    ]
    for day in plan.days:
        lines.append(f"\n### Day {day.day_number} — {day.date} · {day.city}")
        for block in day.time_blocks:
            lines.append(f"- {str(block.period).title()}")
            for place in block.activities:
                timing = (
                    f" ({place.scheduled_start}–{place.scheduled_end})"
                    if place.scheduled_start and place.scheduled_end
                    else ""
                )
                lines.append(f"  - {place.name}{timing}")
            if block.restaurant:
                place = block.restaurant
                timing = (
                    f" ({place.scheduled_start}–{place.scheduled_end})"
                    if place.scheduled_start and place.scheduled_end
                    else ""
                )
                lines.append(f"  - Meal: {place.name}{timing}")
        if day.unscheduled_stops:
            lines.append(
                "- Unscheduled: "
                + ", ".join(place.name for place in day.unscheduled_stops)
            )
        lines.extend(f"- ⚠ {warning}" for warning in day.feasibility_warnings)
    if plan.total_budget_usd:
        lines.append(f"\nValidated trip budget: ${plan.total_budget_usd:,.2f} USD")
    return "\n".join(lines)


__all__ = [
    "DAY_END_MINUTE",
    "DAY_START_MINUTE",
    "ItineraryAssemblyContext",
    "ItineraryPipeline",
    "ItineraryRun",
    "ItinerarySelectionContext",
    "ItineraryValidationError",
    "compute_artifact_fingerprint",
    "render_plan_message",
    "resolve_selection",
    "validate_legacy_draft",
]
