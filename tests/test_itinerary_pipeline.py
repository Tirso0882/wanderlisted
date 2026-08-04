"""Deterministic Itinerary compiler and evidence-resolution tests."""

from datetime import date
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from src.agent.agents.itinerary_agent import ItineraryAgent
from src.itinerary import (
    ItineraryAssemblyContext,
    ItineraryEvidenceCatalog,
    ItineraryPipeline,
    ItinerarySelectionContext,
    ItineraryValidationError,
    build_evidence_catalog,
    compute_artifact_fingerprint,
    resolve_selection,
)
from src.models import (
    AccommodationSelectionProposal,
    BudgetBreakdown,
    BudgetCategory,
    BudgetLineItem,
    DayPlan,
    DayRoute,
    DaySelectionProposal,
    FeasibilityStatus,
    HotelEvidence,
    ItineraryPlan,
    ItinerarySelectionProposal,
    PlaceEvidence,
    PlaceOpeningPeriod,
    RouteLeg,
    RoutePlan,
    TripRequest,
    build_trip_skeleton,
)


def _request(*, children: int = 0, accessibility: bool = False) -> TripRequest:
    return TripRequest(
        scope="full_itinerary",
        origin_city="warsaw",
        destinations=["paris"],
        date_window={
            "exact_start": "2026-09-01",
            "exact_end": "2026-09-03",
            "duration_days": 3,
        },
        travelers={"adults": 2, "children": children},
        accessibility_needs=["step-free routes"] if accessibility else [],
    )


def _skeleton():
    return build_trip_skeleton(
        cities=["paris"],
        start_date=date(2026, 9, 1),
        duration_days=3,
    )


def _opening_for(day: date, start: str = "09:00", end: str = "21:00"):
    google_day = (day.weekday() + 1) % 7
    return [
        PlaceOpeningPeriod(
            open_day=google_day,
            open_time=start,
            close_day=google_day,
            close_time=end,
        )
    ]


def _catalog(*places: PlaceEvidence) -> ItineraryEvidenceCatalog:
    hotel = HotelEvidence(
        source_id="rate-paris",
        rate_key="rate-paris",
        name="Hotel Central",
        city_code="CDG",
        destination_name="Paris",
        latitude=48.86,
        longitude=2.34,
        check_in="2026-09-01",
        check_out="2026-09-03",
        amount="600",
        currency="USD",
    )
    return ItineraryEvidenceCatalog(
        places={place.source_id: place for place in places},
        hotels={hotel.rate_key: hotel},
    )


def _place(
    source_id: str,
    *,
    name: str,
    category: str = "museum",
    city: str = "paris",
    periods: list[PlaceOpeningPeriod] | None = None,
) -> PlaceEvidence:
    return PlaceEvidence(
        source_id=source_id,
        source_component="activities",
        place_id=source_id,
        name=name,
        city=city,
        category=category,
        latitude=48.85,
        longitude=2.35,
        opening_periods=periods or [],
    )


def _proposal(*source_ids: str) -> ItinerarySelectionProposal:
    return ItinerarySelectionProposal(
        accommodations=[
            AccommodationSelectionProposal(stay_sequence=1, rate_key="rate-paris")
        ],
        days=[
            DaySelectionProposal(day_number=1),
            DaySelectionProposal(day_number=2, stop_source_ids=list(source_ids)),
            DaySelectionProposal(day_number=3),
        ],
    )


def _draft_and_catalog(*places: PlaceEvidence, request: TripRequest | None = None):
    request = request or _request()
    skeleton = _skeleton()
    catalog = _catalog(*places)
    draft = resolve_selection(
        _proposal(*(place.source_id for place in places)),
        ItinerarySelectionContext(
            request=request,
            skeleton=skeleton,
            catalog=catalog,
        ),
    )
    return request, skeleton, draft, catalog


def _route_for_draft(draft, *, reverse_middle: bool = False) -> RoutePlan:
    days = []
    for draft_day in draft.days:
        ordered = list(draft_day.stops)
        if reverse_middle:
            ordered.reverse()
        locations = [draft_day.start_location, *ordered, draft_day.end_location]
        legs = [
            RouteLeg(
                from_place=locations[index].name,
                to_place=locations[index + 1].name,
                mode="walk",
                distance_meters=701 + index,
                duration_seconds=601 + index,
                route_leg_index=index,
                instructions=[f"leg-{index}"],
            )
            for index in range(len(locations) - 1)
        ]
        days.append(
            DayRoute(
                day_number=draft_day.day_number,
                mode="walk",
                ordered_stops=ordered,
                legs=legs,
                total_distance_meters=sum(leg.distance_meters for leg in legs),
                total_duration_seconds=sum(leg.duration_seconds for leg in legs),
            )
        )
    return RoutePlan(days=days)


def _budget(*source_ids: str) -> BudgetBreakdown:
    line_items = [
        BudgetLineItem(
            category=BudgetCategory.ACTIVITIES,
            source_component="activities",
            source_id=source_id,
            source_amount=25,
            source_currency="USD",
            source_total=25,
            amount_usd=25,
        )
        for source_id in source_ids
    ]
    line_items.extend(
        [
            BudgetLineItem(
                category=BudgetCategory.ACTIVITIES,
                source_component="activities",
                source_id="unselected-place",
                source_amount=999,
                source_currency="USD",
                source_total=999,
                amount_usd=999,
            ),
            BudgetLineItem(
                category=BudgetCategory.MEALS,
                source_component="regional_estimate",
                source_id="regional-food",
                source_amount=80,
                source_currency="USD",
                source_total=80,
                amount_usd=80,
                estimated=True,
            ),
        ]
    )
    return BudgetBreakdown(
        accommodation=600,
        activities=25 * len(source_ids),
        total=600 + 25 * len(source_ids),
        line_items=line_items,
        request_fingerprint="budget-v1",
    )


def test_hotel_rate_evidence_uses_only_exact_place_match_for_urls_and_photos():
    hotel_payload = {
        "options": [
            {
                "source_id": "rate-central",
                "rate_key": "rate-central",
                "name": "Hotel Central",
                "city_code": "CDG",
                "check_in": "2026-09-01",
                "check_out": "2026-09-03",
                "amount": "600",
                "currency": "USD",
            },
            {
                "source_id": "rate-annex",
                "rate_key": "rate-annex",
                "name": "Hotel Central Annex",
                "city_code": "CDG",
                "check_in": "2026-09-01",
                "check_out": "2026-09-03",
                "amount": "550",
                "currency": "USD",
            },
        ]
    }
    place_payload = {
        "places": [
            {
                "source_id": "google-hotel-central",
                "place_id": "google-hotel-central",
                "name": "Hotel Central",
                "search_context": "Hotel Central Paris",
                "address": "1 Exact Match Street, Paris",
                "latitude": 48.86,
                "longitude": 2.34,
                "website_url": "https://hotel.example",
                "google_maps_url": "https://maps.example/hotel-central",
                "photo_urls": ["https://images.example/hotel-central.jpg"],
            }
        ]
    }
    message = AIMessage(
        content=(
            "HOTEL_RESULTS_JSON:\n"
            + json.dumps(hotel_payload)
            + "\nPLACE_RESULTS_JSON:\n"
            + json.dumps(place_payload)
        )
    )

    catalog = build_evidence_catalog(
        {"hotels": {"messages": [message]}},
        _skeleton(),
    )

    exact = catalog.hotels["rate-central"]
    assert exact.place_id == "google-hotel-central"
    assert exact.address == "1 Exact Match Street, Paris"
    assert exact.website_url == "https://hotel.example"
    assert exact.google_maps_url == "https://maps.example/hotel-central"
    assert exact.photo_urls == ["https://images.example/hotel-central.jpg"]
    assert catalog.hotels["rate-annex"].photo_urls == []


def test_selection_resolves_only_catalog_ids_and_canonical_calendar():
    museum = _place(
        "activities:museum",
        name="Museum",
        periods=_opening_for(date(2026, 9, 2)),
    )
    request, skeleton, draft, _ = _draft_and_catalog(museum)

    assert [day.date for day in draft.days] == [
        "2026-09-01",
        "2026-09-02",
        "2026-09-03",
    ]
    assert [day.city for day in draft.days] == ["paris", "paris", "paris"]
    assert draft.days[1].stops[0].name == "Museum"
    assert draft.days[1].stops[0].source_id == "activities:museum"
    assert request.destinations == ["paris"]
    assert skeleton.exit_city == "paris"


@pytest.mark.parametrize(
    "proposal, error",
    [
        (
            ItinerarySelectionProposal(
                accommodations=[
                    AccommodationSelectionProposal(
                        stay_sequence=1, rate_key="rate-paris"
                    )
                ],
                days=[
                    DaySelectionProposal(
                        day_number=2, stop_source_ids=["activities:unknown"]
                    )
                ],
            ),
            "unknown place source ID",
        ),
        (
            ItinerarySelectionProposal(
                accommodations=[
                    AccommodationSelectionProposal(
                        stay_sequence=1, rate_key="rate-paris"
                    )
                ],
                days=[
                    DaySelectionProposal(
                        day_number=1, stop_source_ids=["activities:museum"]
                    ),
                    DaySelectionProposal(
                        day_number=2, stop_source_ids=["activities:museum"]
                    ),
                ],
            ),
            "duplicate selected stop",
        ),
    ],
)
def test_selection_rejects_unknown_and_duplicate_ids(proposal, error):
    museum = _place("activities:museum", name="Museum")
    context = ItinerarySelectionContext(
        request=_request(),
        skeleton=_skeleton(),
        catalog=_catalog(museum),
    )

    with pytest.raises(ItineraryValidationError, match=error):
        resolve_selection(proposal, context)


def test_selection_rejects_wrong_city_hotel():
    lyon = _place("activities:lyon", name="Lyon Museum", city="lyon")
    catalog = _catalog(lyon)
    catalog.hotels["rate-paris"] = catalog.hotels["rate-paris"].model_copy(
        update={"city_code": "LYS"}
    )

    with pytest.raises(ItineraryValidationError) as exc:
        resolve_selection(
            _proposal("activities:lyon"),
            ItinerarySelectionContext(
                request=_request(), skeleton=_skeleton(), catalog=catalog
            ),
        )

    assert "belongs to LYS" in str(exc.value)


def test_selection_rejects_duplicate_hotel_rate_keys_across_stays():
    skeleton = build_trip_skeleton(
        cities=["paris", "lyon"],
        start_date=date(2026, 9, 1),
        duration_days=5,
    )
    museum = _place(
        "activities:paris-museum",
        name="Paris Museum",
        city="paris",
    )
    shared_rate = HotelEvidence(
        source_id="rate-shared",
        rate_key="rate-shared",
        name="Ambiguous Hotel",
    )
    proposal = ItinerarySelectionProposal(
        accommodations=[
            AccommodationSelectionProposal(
                stay_sequence=1,
                rate_key=shared_rate.rate_key,
            ),
            AccommodationSelectionProposal(
                stay_sequence=2,
                rate_key=shared_rate.rate_key,
            ),
        ],
        days=[
            DaySelectionProposal(
                day_number=1,
                stop_source_ids=[museum.source_id],
            )
        ],
    )

    with pytest.raises(ItineraryValidationError, match="unique hotel rate keys"):
        resolve_selection(
            proposal,
            ItinerarySelectionContext(
                request=_request(),
                skeleton=skeleton,
                catalog=ItineraryEvidenceCatalog(
                    places={museum.source_id: museum},
                    hotels={shared_rate.rate_key: shared_rate},
                ),
            ),
        )


def test_selection_rejects_wrong_city_place():
    lyon = _place("activities:lyon", name="Lyon Museum", city="lyon")

    with pytest.raises(ItineraryValidationError) as exc:
        resolve_selection(
            _proposal("activities:lyon"),
            ItinerarySelectionContext(
                request=_request(), skeleton=_skeleton(), catalog=_catalog(lyon)
            ),
        )

    assert "belongs to lyon" in str(exc.value)


async def test_selection_model_gets_one_validation_retry_then_resolves_ids():
    museum = _place("activities:museum", name="Museum")
    context = ItinerarySelectionContext(
        request=_request(), skeleton=_skeleton(), catalog=_catalog(museum)
    )
    selector = AsyncMock()
    selector.ainvoke.side_effect = [
        _proposal("activities:invented"),
        _proposal(museum.source_id),
    ]
    llm = MagicMock()
    llm.with_structured_output.return_value = selector

    draft = await ItineraryAgent(llm).select_draft(context)

    assert selector.ainvoke.await_count == 2
    assert draft.days[1].stops[0].source_id == museum.source_id
    assert (
        "failed deterministic validation"
        in selector.ainvoke.await_args.args[0][-1].content
    )
    llm.with_structured_output.assert_called_once_with(
        ItinerarySelectionProposal, method="function_calling"
    )


async def test_selection_model_fails_closed_after_one_retry():
    museum = _place("activities:museum", name="Museum")
    context = ItinerarySelectionContext(
        request=_request(), skeleton=_skeleton(), catalog=_catalog(museum)
    )
    selector = AsyncMock()
    selector.ainvoke.side_effect = [
        _proposal("activities:invented-one"),
        _proposal("activities:invented-two"),
        _proposal(museum.source_id),
    ]
    llm = MagicMock()
    llm.with_structured_output.return_value = selector

    with pytest.raises(ItineraryValidationError, match="invented-two"):
        await ItineraryAgent(llm).select_draft(context)

    assert selector.ainvoke.await_count == 2


def test_route_order_controls_order_but_not_place_facts_and_preserves_measurements():
    first = _place(
        "activities:first",
        name="First Museum",
        periods=_opening_for(date(2026, 9, 2)),
    )
    second = _place(
        "activities:second",
        name="Second Museum",
        periods=_opening_for(date(2026, 9, 2)),
    )
    request, skeleton, draft, _ = _draft_and_catalog(first, second)
    route = _route_for_draft(draft, reverse_middle=True)
    route.days[1].ordered_stops[0] = (
        route.days[1]
        .ordered_stops[0]
        .model_copy(update={"name": "Hallucinated Name", "address": "Invented address"})
    )

    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route,
                budget=_budget(first.source_id, second.source_id),
            )
        )
        .plan
    )

    cards = [card for block in plan.days[1].time_blocks for card in block.activities]
    assert [card.name for card in cards] == ["Second Museum", "First Museum"]
    transit = [step for block in plan.days[1].time_blocks for step in block.transit]
    assert transit[0].distance_meters == 701
    assert transit[0].duration_seconds == 601
    assert transit[0].fare_estimate_usd == 0


def test_complete_route_produces_explicit_times_and_supported_daily_cost_only():
    museum = _place(
        "activities:museum",
        name="Museum",
        periods=_opening_for(date(2026, 9, 2)),
    )
    request, skeleton, draft, _ = _draft_and_catalog(museum)
    route = _route_for_draft(draft)
    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route,
                budget=_budget(museum.source_id),
            )
        )
        .plan
    )

    card = plan.days[1].time_blocks[0].activities[0]
    assert card.scheduled_start == "09:26"
    assert card.scheduled_end == "11:26"
    assert plan.days[1].daily_cost_usd == 25
    assert plan.days[1].cost_coverage == "complete"
    assert plan.total_budget_usd == 625
    assert plan.feasibility_status == FeasibilityStatus.NEEDS_REVIEW


def test_missing_route_leg_does_not_shift_later_measurement_to_wrong_stop():
    museum = _place(
        "activities:museum",
        name="Museum",
        periods=_opening_for(date(2026, 9, 2)),
    )
    request, skeleton, draft, _ = _draft_and_catalog(museum)
    route = RoutePlan(
        days=[
            DayRoute(
                day_number=2,
                mode="walk",
                ordered_stops=draft.days[1].stops,
                legs=[
                    RouteLeg(
                        from_place="Museum",
                        to_place="Hotel Central",
                        mode="walk",
                        distance_meters=1200,
                        duration_seconds=780,
                        route_leg_index=1,
                    )
                ],
            )
        ]
    )

    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route,
            )
        )
        .plan
    )

    transit = [step for block in plan.days[1].time_blocks for step in block.transit]
    assert [
        (step.route_leg_index, step.from_place, step.to_place) for step in transit
    ] == [(1, "Museum", "Hotel Central")]
    assert plan.days[1].feasibility_status == FeasibilityStatus.NEEDS_REVIEW
    assert "day_2_route_legs" in plan.missing_constraints


def test_closed_stop_moves_to_unscheduled_and_marks_day_infeasible():
    wrong_day = date(2026, 9, 3)
    open_park = _place(
        "activities:open",
        name="Open Park",
        category="park",
        periods=_opening_for(date(2026, 9, 2)),
    )
    museum = _place(
        "activities:closed",
        name="Closed Museum",
        periods=_opening_for(wrong_day),
    )
    request, skeleton, draft, _ = _draft_and_catalog(open_park, museum)

    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=_route_for_draft(draft),
            )
        )
        .plan
    )

    day = plan.days[1]
    assert day.feasibility_status == FeasibilityStatus.INFEASIBLE
    assert [stop.source_id for stop in day.unscheduled_stops] == ["activities:closed"]
    assert day.time_blocks[0].activities[0].source_id == "activities:open"
    transit = [step for block in day.time_blocks for step in block.transit]
    assert [step.route_leg_index for step in transit] == [0]


def test_missing_hours_and_route_degrade_without_invented_times():
    park = _place("activities:park", name="Park", category="park")
    request, skeleton, draft, _ = _draft_and_catalog(park)

    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=None,
            )
        )
        .plan
    )

    card = plan.days[1].time_blocks[0].activities[0]
    assert card.scheduled_start == ""
    assert card.scheduled_end == ""
    assert plan.days[1].feasibility_status == FeasibilityStatus.NEEDS_REVIEW
    assert "route_plan" in plan.missing_constraints
    assert f"opening_hours:{park.source_id}" in plan.missing_constraints


def test_family_rest_break_is_applied_after_two_stops():
    visit_day = date(2026, 9, 2)
    places = [
        _place(
            f"activities:p{index}",
            name=f"Park {index}",
            category="park",
            periods=_opening_for(visit_day),
        )
        for index in range(1, 4)
    ]
    request, skeleton, draft, _ = _draft_and_catalog(
        *places, request=_request(children=1)
    )
    route = _route_for_draft(draft)
    for leg in route.days[1].legs:
        leg.duration_seconds = 0

    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route,
            )
        )
        .plan
    )
    cards = [card for block in plan.days[1].time_blocks for card in block.activities]

    assert [card.scheduled_start for card in cards] == ["09:15", "11:00", "13:15"]
    assert any("30-minute rest" in item for item in plan.days[1].assumptions)


def test_week_spanning_open_period_supports_24_hour_evidence():
    always_open = _place(
        "activities:always",
        name="Always Open Landmark",
        category="landmark",
        periods=[
            PlaceOpeningPeriod(
                open_day=0,
                open_time="00:00",
                close_day=0,
                close_time="00:00",
            )
        ],
    )
    request, skeleton, draft, _ = _draft_and_catalog(always_open)

    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=_route_for_draft(draft),
            )
        )
        .plan
    )

    assert plan.days[1].unscheduled_stops == []
    assert plan.days[1].time_blocks[0].activities[0].scheduled_start


def test_fingerprint_changes_when_a_canonical_artifact_changes():
    museum = _place("activities:museum", name="Museum")
    request, skeleton, draft, _ = _draft_and_catalog(museum)
    context = ItineraryAssemblyContext(
        request=request,
        skeleton=skeleton,
        draft=draft,
        route_plan=_route_for_draft(draft),
        budget=_budget(museum.source_id),
        request_revision=1,
    )
    changed = ItineraryAssemblyContext(
        request=request,
        skeleton=skeleton,
        draft=draft,
        route_plan=context.route_plan,
        budget=context.budget.model_copy(update={"request_fingerprint": "budget-v2"}),
        request_revision=1,
    )

    assert compute_artifact_fingerprint(context) != compute_artifact_fingerprint(
        changed
    )

    changed_total = ItineraryAssemblyContext(
        request=request,
        skeleton=skeleton,
        draft=draft,
        route_plan=context.route_plan,
        budget=context.budget.model_copy(update={"total": 999}),
        request_revision=1,
    )
    changed_readiness = ItineraryAssemblyContext(
        request=request,
        skeleton=skeleton,
        draft=draft,
        route_plan=context.route_plan,
        budget=context.budget,
        readiness={"weather": [{"date": "2026-09-02", "condition": "rain"}]},
        request_revision=1,
    )

    assert compute_artifact_fingerprint(context) != compute_artifact_fingerprint(
        changed_total
    )
    assert compute_artifact_fingerprint(context) != compute_artifact_fingerprint(
        changed_readiness
    )


def test_itinerary_plan_rejects_non_contiguous_dates():
    with pytest.raises(ValidationError, match="canonical calendar"):
        ItineraryPlan(
            start_date="2026-09-01",
            end_date="2026-09-03",
            duration_days=3,
            days=[
                DayPlan(day_number=1, date="2026-09-01", city="paris"),
                DayPlan(day_number=2, date="2026-09-03", city="paris"),
                DayPlan(day_number=3, date="2026-09-04", city="paris"),
            ],
            artifact_fingerprint="fingerprint",
        )
