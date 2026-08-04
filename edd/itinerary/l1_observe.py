"""Construct and execute the hermetic Itinerary Layer-1 scenarios."""

from __future__ import annotations

from datetime import date, timedelta

from src.itinerary import (
    ItineraryAssemblyContext,
    ItineraryEvidenceCatalog,
    ItineraryPipeline,
    ItinerarySelectionContext,
    ItineraryValidationError,
    resolve_selection,
)
from src.models import (
    AccommodationSelectionProposal,
    BudgetBreakdown,
    BudgetCategory,
    BudgetLineItem,
    DayRoute,
    DaySelectionProposal,
    HotelEvidence,
    ItinerarySelectionProposal,
    PlaceEvidence,
    PlaceOpeningPeriod,
    PlaceRef,
    RouteLeg,
    RoutePlan,
    TripRequest,
    build_trip_skeleton,
)

START = date(2026, 9, 1)
CITY_CODES = {"paris": "CDG", "lyon": "LYO"}


def _request(*, destinations=None, duration=4, children=0) -> TripRequest:
    return TripRequest(
        scope="full_itinerary",
        origin_city="warsaw",
        destinations=destinations or ["paris"],
        date_window={
            "exact_start": START.isoformat(),
            "exact_end": (START + timedelta(days=duration - 1)).isoformat(),
            "duration_days": duration,
        },
        travelers={"adults": 2, "children": children},
    )


def _opening(day: date, start="09:00", end="21:00") -> list[PlaceOpeningPeriod]:
    google_day = (day.weekday() + 1) % 7
    return [
        PlaceOpeningPeriod(
            open_day=google_day,
            open_time=start,
            close_day=google_day,
            close_time=end,
        )
    ]


def _place(
    source_id: str,
    name: str,
    *,
    city="paris",
    category="museum",
    visit_day: date | None = None,
    periods: list[PlaceOpeningPeriod] | None = None,
    full_evidence=False,
) -> PlaceEvidence:
    opening_periods = (
        periods if periods is not None else (_opening(visit_day) if visit_day else [])
    )
    return PlaceEvidence(
        source_id=source_id,
        source_component=source_id.split(":", 1)[0],
        place_id=source_id,
        name=name,
        city=city,
        address="1 Evidence Street, Paris" if full_evidence else "",
        latitude=48.8566 if city == "paris" else 45.764,
        longitude=2.3522 if city == "paris" else 4.8357,
        category=category,
        rating=4.7 if full_evidence else None,
        review_count=321 if full_evidence else 0,
        description="Provider-backed description" if full_evidence else "",
        website_url="https://museum.example" if full_evidence else "",
        google_maps_url="https://maps.example/museum-1" if full_evidence else "",
        photo_urls=["https://images.example/museum-1.jpg"] if full_evidence else [],
        opening_hours=["Wednesday: 9:00 AM – 9:00 PM"] if opening_periods else [],
        opening_periods=opening_periods,
    )


def _catalog(skeleton, places: list[PlaceEvidence]) -> ItineraryEvidenceCatalog:
    hotels = {}
    for stay in skeleton.stays:
        rate_key = f"rate-{stay.city}-{stay.sequence}"
        hotels[rate_key] = HotelEvidence(
            source_id=rate_key,
            rate_key=rate_key,
            name=f"{stay.city.title()} Evidence Hotel {stay.sequence}",
            city_code=CITY_CODES[stay.city],
            destination_name=stay.city.title(),
            latitude=48.86 if stay.city == "paris" else 45.76,
            longitude=2.34 if stay.city == "paris" else 4.84,
            check_in=stay.check_in.isoformat(),
            check_out=stay.check_out.isoformat(),
            amount=str(500 + 100 * stay.sequence),
            currency="USD",
        )
    return ItineraryEvidenceCatalog(
        places={item.source_id: item for item in places},
        hotels=hotels,
    )


def _proposal(skeleton, catalog, assignments: dict[int, list[str]]):
    return ItinerarySelectionProposal(
        accommodations=[
            AccommodationSelectionProposal(
                stay_sequence=stay.sequence,
                rate_key=f"rate-{stay.city}-{stay.sequence}",
            )
            for stay in skeleton.stays
        ],
        days=[
            DaySelectionProposal(
                day_number=number,
                stop_source_ids=assignments.get(number, []),
                preferred_mode="walk",
            )
            for number in range(1, skeleton.duration_days + 1)
        ],
    )


def _route(
    draft,
    *,
    reverse_days=(),
    omitted_days=(),
    zero_duration_days=(),
    long_duration_days=(),
) -> RoutePlan:
    days = []
    for day in draft.days:
        if day.day_number in omitted_days:
            continue
        ordered = list(day.stops)
        if day.day_number in reverse_days:
            ordered.reverse()
        locations = [
            day.start_location,
            *ordered,
            day.end_location or day.start_location,
        ]
        legs = []
        for index in range(len(locations) - 1):
            if day.day_number in zero_duration_days:
                duration_seconds = 0
            elif day.day_number in long_duration_days:
                duration_seconds = 900
            else:
                duration_seconds = 601 + index
            legs.append(
                RouteLeg(
                    from_place=locations[index].name,
                    to_place=locations[index + 1].name,
                    mode="walk",
                    distance_meters=701 + index,
                    duration_seconds=duration_seconds,
                    route_leg_index=index,
                    instructions=[f"measured-leg-{index}"],
                )
            )
        days.append(
            DayRoute(
                day_number=day.day_number,
                mode="walk",
                ordered_stops=ordered,
                legs=legs,
                total_distance_meters=sum(item.distance_meters for item in legs),
                total_duration_seconds=sum(item.duration_seconds for item in legs),
            )
        )
    return RoutePlan(days=days)


def _budget(source_id: str) -> BudgetBreakdown:
    return BudgetBreakdown(
        accommodation=600,
        activities=35,
        total=635,
        line_items=[
            BudgetLineItem(
                category=BudgetCategory.ACTIVITIES,
                source_component="activities",
                source_id=source_id,
                source_amount=35,
                source_currency="USD",
                source_total=35,
                amount_usd=35,
            ),
            BudgetLineItem(
                category=BudgetCategory.ACTIVITIES,
                source_component="activities",
                source_id="activities:unselected-999",
                source_amount=999,
                source_currency="USD",
                source_total=999,
                amount_usd=999,
            ),
            BudgetLineItem(
                category=BudgetCategory.MEALS,
                source_component="regional_estimate",
                source_id="regional:meals",
                source_amount=80,
                source_currency="USD",
                source_total=80,
                amount_usd=80,
                estimated=True,
            ),
        ],
        request_fingerprint="budget-edd-v1",
    )


def _scheduled(day):
    return [
        place
        for block in day.time_blocks
        for place in [
            *block.activities,
            *([block.restaurant] if block.restaurant else []),
        ]
    ]


def _summarize(*, plan, draft, route_plan, budget, skeleton) -> dict:
    scheduled = {str(day.day_number): _scheduled(day) for day in plan.days}
    transit = {
        str(day.day_number): [
            step.model_dump(mode="json")
            for block in day.time_blocks
            for step in block.transit
        ]
        for day in plan.days
    }
    return {
        "status": "completed",
        "dates": [day.date for day in plan.days],
        "day_numbers": [day.day_number for day in plan.days],
        "cities": [day.city for day in plan.days],
        "exit_city": skeleton.exit_city,
        "selected_hotel_rate_keys": [
            item.rate_key for item in draft.selected_accommodations
        ],
        "selected_hotel_names": [item.name for item in draft.selected_accommodations],
        "draft_source_ids": [
            stop.source_id for day in draft.days for stop in day.stops
        ],
        "scheduled_source_ids": {
            number: [item.source_id for item in items]
            for number, items in scheduled.items()
        },
        "scheduled_names": {
            number: [item.name for item in items] for number, items in scheduled.items()
        },
        "scheduled_places": {
            number: [item.model_dump(mode="json") for item in items]
            for number, items in scheduled.items()
        },
        "scheduled_starts": {
            number: [item.scheduled_start for item in items]
            for number, items in scheduled.items()
        },
        "scheduled_ends": {
            number: [item.scheduled_end for item in items]
            for number, items in scheduled.items()
        },
        "durations": {
            number: [item.estimated_duration_minutes for item in items]
            for number, items in scheduled.items()
        },
        "duration_bases": {
            number: [item.duration_basis for item in items]
            for number, items in scheduled.items()
        },
        "unscheduled_source_ids": {
            str(day.day_number): [item.source_id for item in day.unscheduled_stops]
            for day in plan.days
        },
        "transit": transit,
        "daily_costs": {str(day.day_number): day.daily_cost_usd for day in plan.days},
        "cost_coverage": {str(day.day_number): day.cost_coverage for day in plan.days},
        "day_feasibility": {
            str(day.day_number): day.feasibility_status for day in plan.days
        },
        "assumptions": {str(day.day_number): day.assumptions for day in plan.days},
        "missing_constraints": plan.missing_constraints,
        "total_budget_usd": plan.total_budget_usd,
        "plan": plan.model_dump(mode="json"),
        "draft": draft.model_dump(mode="json"),
        "route_plan": route_plan.model_dump(mode="json") if route_plan else None,
        "budget": budget.model_dump(mode="json") if budget else None,
    }


def _execute(
    *,
    request,
    skeleton,
    places,
    assignments,
    proposal=None,
    draft_mutator=None,
    route_mutator=None,
    route_kwargs=None,
    budget=None,
):
    catalog = _catalog(skeleton, places)
    try:
        draft = resolve_selection(
            proposal or _proposal(skeleton, catalog, assignments),
            ItinerarySelectionContext(
                request=request,
                skeleton=skeleton,
                catalog=catalog,
            ),
        )
        if draft_mutator:
            draft = draft_mutator(draft)
        route_plan = _route(draft, **(route_kwargs or {}))
        if route_mutator:
            route_plan = route_mutator(route_plan)
        run = ItineraryPipeline().run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route_plan,
                budget=budget,
                request_revision=1,
            )
        )
    except ItineraryValidationError as exc:
        return {"status": "rejected", "error": str(exc)}
    return _summarize(
        plan=run.plan,
        draft=draft,
        route_plan=route_plan,
        budget=budget,
        skeleton=skeleton,
    )


def observe_case(case: dict) -> dict:
    scenario = case["scenario"]
    request = _request()
    skeleton = build_trip_skeleton(cities=["paris"], start_date=START, duration_days=4)
    visit_day = START + timedelta(days=1)

    if scenario == "artifact_place_fields":
        place = _place(
            "activities:museum-1",
            "Provider Museum",
            visit_day=visit_day,
            full_evidence=True,
        )
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[place],
            assignments={2: [place.source_id]},
        )

    if scenario == "artifact_hotel_rate":
        place = _place("activities:anchor", "Anchor Museum", visit_day=visit_day)
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[place],
            assignments={2: [place.source_id]},
        )

    if scenario == "artifact_route":
        first = _place("activities:first", "First Museum", visit_day=visit_day)
        second = _place("activities:second", "Second Museum", visit_day=visit_day)

        def mutate_route(route_plan):
            day = route_plan.days[1]
            day.ordered_stops[0] = day.ordered_stops[0].model_copy(
                update={"name": "Invented Route Name", "address": "Invented"}
            )
            return route_plan

        return _execute(
            request=request,
            skeleton=skeleton,
            places=[first, second],
            assignments={2: [first.source_id, second.source_id]},
            route_kwargs={"reverse_days": (2,)},
            route_mutator=mutate_route,
        )

    if scenario == "artifact_costs":
        place = _place("activities:paid", "Paid Museum", visit_day=visit_day)
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[place],
            assignments={2: [place.source_id]},
            budget=_budget(place.source_id),
        )

    if scenario == "dates_inclusive":
        place = _place("activities:calendar", "Calendar Museum", visit_day=visit_day)
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[place],
            assignments={2: [place.source_id]},
        )

    if scenario == "dates_transition":
        request = _request(destinations=["paris", "lyon"])
        skeleton = build_trip_skeleton(
            cities=["paris", "lyon"], start_date=START, duration_days=4
        )
        paris = _place(
            "activities:paris-stop",
            "Paris Stop",
            city="paris",
            visit_day=START + timedelta(days=1),
        )
        lyon = _place(
            "activities:lyon-stop",
            "Lyon Stop",
            city="lyon",
            visit_day=START + timedelta(days=2),
        )
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[paris, lyon],
            assignments={2: [paris.source_id], 3: [lyon.source_id]},
        )

    if scenario == "dates_exit_city":
        request = _request(destinations=["paris", "lyon"], duration=5)
        skeleton = build_trip_skeleton(
            cities=["paris", "lyon"],
            start_date=START,
            duration_days=5,
            return_to_entry=True,
        )
        lyon = _place(
            "activities:lyon-exit-case",
            "Lyon Museum",
            city="lyon",
            visit_day=START + timedelta(days=2),
        )
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[lyon],
            assignments={3: [lyon.source_id]},
        )

    if scenario == "dates_injected_draft":
        place = _place("activities:immutable", "Immutable Museum", visit_day=visit_day)

        def inject(draft):
            return draft.model_copy(
                update={
                    "days": [
                        day.model_copy(
                            update={"date": "2099-01-01", "city": "atlantis"}
                        )
                        for day in draft.days
                    ]
                }
            )

        return _execute(
            request=request,
            skeleton=skeleton,
            places=[place],
            assignments={2: [place.source_id]},
            draft_mutator=inject,
        )

    if scenario == "feasibility_defaults":
        place = _place("activities:default", "Default Museum", visit_day=visit_day)
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[place],
            assignments={2: [place.source_id]},
        )

    if scenario == "feasibility_family_rest":
        request = _request(children=1)
        places = [
            _place(
                f"activities:family-{index}",
                f"Family Park {index}",
                category="park",
                visit_day=visit_day,
            )
            for index in range(1, 4)
        ]
        return _execute(
            request=request,
            skeleton=skeleton,
            places=places,
            assignments={2: [item.source_id for item in places]},
            route_kwargs={"zero_duration_days": (2,)},
        )

    if scenario == "feasibility_closed":
        opened = _place(
            "activities:open-park",
            "Open Park",
            category="park",
            visit_day=visit_day,
        )
        closed = _place(
            "activities:closed-museum",
            "Closed Museum",
            periods=_opening(visit_day + timedelta(days=1)),
        )
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[opened, closed],
            assignments={2: [opened.source_id, closed.source_id]},
        )

    if scenario == "feasibility_partial_overflow":
        request = _request(duration=5)
        skeleton = build_trip_skeleton(
            cities=["paris"], start_date=START, duration_days=5
        )
        missing = _place(
            "activities:unknown-hours", "Unknown Hours Park", category="park"
        )
        long_stops = [
            _place(
                f"activities:long-{index}",
                f"Long Museum {index}",
                visit_day=START + timedelta(days=2),
            )
            for index in range(1, 6)
        ]
        return _execute(
            request=request,
            skeleton=skeleton,
            places=[missing, *long_stops],
            assignments={
                2: [missing.source_id],
                3: [item.source_id for item in long_stops],
            },
            route_kwargs={"omitted_days": (2,), "long_duration_days": (3,)},
        )

    valid = _place("activities:valid", "Valid Museum", visit_day=visit_day)
    catalog = _catalog(skeleton, [valid])
    if scenario == "hallucination_unknown_id":
        proposal = _proposal(skeleton, catalog, {2: ["activities:invented"]})
    elif scenario == "hallucination_duplicate_id":
        proposal = _proposal(
            skeleton,
            catalog,
            {2: [valid.source_id], 3: [valid.source_id]},
        )
    elif scenario == "hallucination_wrong_city":
        wrong = _place(
            "activities:lyon-wrong",
            "Wrong City Museum",
            city="lyon",
            visit_day=visit_day,
        )
        catalog = _catalog(skeleton, [wrong])
        proposal = _proposal(skeleton, catalog, {2: [wrong.source_id]})
        valid = wrong
    elif scenario == "hallucination_unselected_route":

        def introduce_unselected(route_plan):
            route_plan.days[1].ordered_stops.append(
                PlaceRef(
                    name="Invented Route Stop",
                    source_component="activities",
                    source_id="activities:unselected-route-stop",
                )
            )
            return route_plan

        return _execute(
            request=request,
            skeleton=skeleton,
            places=[valid],
            assignments={2: [valid.source_id]},
            route_mutator=introduce_unselected,
        )
    else:
        raise KeyError(f"unknown itinerary EDD scenario: {scenario}")

    return _execute(
        request=request,
        skeleton=skeleton,
        places=[valid],
        assignments={},
        proposal=proposal,
    )
