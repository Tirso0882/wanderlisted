"""Typed handbook rendering tests: no model or provider reconstruction."""

from datetime import date
from unittest.mock import MagicMock

from src.agent.renderer import HandbookRenderer
from src.agent.stage4_graph import render_handbook_node
from src.itinerary import ItineraryAssemblyContext, ItineraryPipeline
from src.models import (
    BudgetBreakdown,
    BudgetCategory,
    BudgetLineItem,
    DayRoute,
    DraftDay,
    DraftItinerary,
    PlaceOpeningPeriod,
    PlaceRef,
    RouteLeg,
    RoutePlan,
    SelectedAccommodation,
    TripRequest,
    build_trip_skeleton,
)


def _typed_state() -> dict:
    request = TripRequest(
        scope="full_itinerary",
        origin_city="warsaw",
        destinations=["paris"],
        requested_capabilities=["hotels", "activities", "itinerary"],
        capability_scope_confirmed=True,
        date_window={
            "exact_start": "2026-09-01",
            "exact_end": "2026-09-03",
            "duration_days": 3,
        },
        travelers={"adults": 2},
        travel_style="mid-range",
    )
    skeleton = build_trip_skeleton(
        cities=["paris"], start_date=date(2026, 9, 1), duration_days=3
    )
    hotel = PlaceRef(
        name="Hotel Central",
        source_component="hotels",
        source_id="rate-central",
        latitude=48.86,
        longitude=2.34,
        category="hotel",
    )
    museum = PlaceRef(
        name="City Museum",
        source_component="activities",
        source_id="activities:museum",
        place_id="museum",
        latitude=48.85,
        longitude=2.35,
        category="museum",
        photo_urls=["https://example.test/museum.jpg"],
        opening_periods=[
            PlaceOpeningPeriod(
                open_day=3,
                open_time="09:00",
                close_day=3,
                close_time="18:00",
            )
        ],
    )
    draft = DraftItinerary(
        selected_accommodations=[
            SelectedAccommodation(
                stay_sequence=1,
                name="Hotel Central",
                rate_key="rate-central",
            )
        ],
        days=[
            DraftDay(
                day_number=1,
                date="2026-09-01",
                city="paris",
                start_location=hotel,
                end_location=hotel,
            ),
            DraftDay(
                day_number=2,
                date="2026-09-02",
                city="paris",
                start_location=hotel,
                end_location=hotel,
                stops=[museum],
                preferred_mode="walk",
            ),
            DraftDay(
                day_number=3,
                date="2026-09-03",
                city="paris",
                start_location=hotel,
                end_location=hotel,
            ),
        ],
    )
    route = RoutePlan(
        days=[
            DayRoute(
                day_number=1,
                mode="walk",
                legs=[
                    RouteLeg(
                        from_place="Hotel Central",
                        to_place="Hotel Central",
                        mode="walk",
                    )
                ],
            ),
            DayRoute(
                day_number=2,
                mode="walk",
                ordered_stops=[museum],
                legs=[
                    RouteLeg(
                        from_place="Hotel Central",
                        to_place="City Museum",
                        mode="walk",
                        distance_meters=1100,
                        duration_seconds=720,
                    ),
                    RouteLeg(
                        from_place="City Museum",
                        to_place="Hotel Central",
                        mode="walk",
                        distance_meters=1200,
                        duration_seconds=780,
                    ),
                ],
            ),
            DayRoute(
                day_number=3,
                mode="walk",
                legs=[
                    RouteLeg(
                        from_place="Hotel Central",
                        to_place="Hotel Central",
                        mode="walk",
                    )
                ],
            ),
        ]
    )
    budget = BudgetBreakdown(
        accommodation=600,
        activities=35,
        total=635,
        line_items=[
            BudgetLineItem(
                category=BudgetCategory.ACCOMMODATION,
                source_component="hotels",
                source_id="rate-central",
                source_amount=600,
                source_currency="USD",
                source_total=600,
                amount_usd=600,
            ),
            BudgetLineItem(
                category=BudgetCategory.ACTIVITIES,
                source_component="activities",
                source_id="activities:museum",
                source_amount=35,
                source_currency="USD",
                source_total=35,
                amount_usd=35,
            ),
        ],
        request_fingerprint="budget-v1",
    )
    plan = (
        ItineraryPipeline()
        .run(
            ItineraryAssemblyContext(
                request=request,
                skeleton=skeleton,
                draft=draft,
                route_plan=route,
                budget=budget,
                request_revision=2,
            )
        )
        .plan
    )
    return {
        "trip_request": request.model_dump(mode="json"),
        "request_revision": 2,
        "group_type": "couple",
        "itinerary_components": {
            "trip_skeleton_structured": skeleton.model_dump(mode="json"),
            "draft_itinerary_structured": draft.model_dump(mode="json"),
            "route_plan_structured": route.model_dump(mode="json"),
            "budget_structured": budget.model_dump(mode="json"),
            "itinerary_structured": plan.model_dump(mode="json"),
        },
    }


def test_rendered_html_never_contains_google_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "private-render-key")
    renderer = HandbookRenderer()
    handbook = renderer.build_handbook(_typed_state())

    html = renderer.render_html(handbook)

    assert "private-render-key" not in html
    assert "maps/embed/v1/place?key=" not in html
    assert "maps/search/?api=1" in html


async def test_renderer_fails_closed_without_typed_plan():
    llm = MagicMock()

    result = await render_handbook_node(
        {"itinerary_components": {}},
        llm=llm,
    )

    assert result["current_agent"] == "render_handbook:failed"
    assert result["component_results"]["handbook"]["status"] == "failed"
    assert result["itinerary_components"]["handbook_structured"] is None
    assert llm.mock_calls == []


async def test_renderer_copies_typed_days_budget_and_known_evidence(
    monkeypatch, tmp_path
):
    state = _typed_state()
    llm = MagicMock()
    photo_lookup = MagicMock(side_effect=AssertionError("photo lookup called"))
    monkeypatch.setattr("src.tools.google_maps.lookup_place_photo", photo_lookup)
    captured = []

    def _write_outputs(_renderer, handbook, output_dir="outputs"):
        captured.append(handbook)
        return {
            "html": tmp_path / "handbook.html",
            "markdown": tmp_path / "handbook.md",
            "json": tmp_path / "handbook.json",
        }

    monkeypatch.setattr(
        "src.agent.stage4_graph.HandbookRenderer.write_outputs", _write_outputs
    )

    result = await render_handbook_node(state, llm=llm)

    assert result["current_agent"] == "render_handbook"
    assert result["component_results"]["handbook"]["status"] == "partial"
    handbook = result["itinerary_components"]["handbook_structured"]
    plan = state["itinerary_components"]["itinerary_structured"]
    assert handbook["days"] == plan["days"]
    assert handbook["budget_total"] == 635
    assert handbook["total_budget_usd"] == 635
    assert handbook["hotels"][0]["name"] == "Hotel Central"
    assert handbook["hotels"][0]["booking_url"] == ""
    assert captured[0].model_dump(mode="json")["days"] == plan["days"]


async def test_renderer_makes_zero_model_or_photo_calls(monkeypatch, tmp_path):
    state = _typed_state()
    llm = MagicMock()
    photo_lookup = MagicMock(side_effect=AssertionError("photo lookup called"))
    monkeypatch.setattr("src.tools.google_maps.lookup_place_photo", photo_lookup)
    monkeypatch.setattr(
        "src.agent.stage4_graph.HandbookRenderer.write_outputs",
        lambda self, handbook, output_dir="outputs": {
            "html": tmp_path / "h.html",
            "markdown": tmp_path / "h.md",
            "json": tmp_path / "h.json",
        },
    )

    await render_handbook_node(state, llm=llm)

    assert llm.mock_calls == []
    photo_lookup.assert_not_called()


async def test_renderer_marks_fingerprint_mismatch_stale(monkeypatch):
    state = _typed_state()
    writer = MagicMock()
    monkeypatch.setattr(
        "src.agent.stage4_graph.HandbookRenderer.write_outputs",
        writer,
    )
    state["itinerary_components"]["route_plan_structured"]["days"][1]["legs"][0][
        "duration_seconds"
    ] = 9999

    result = await render_handbook_node(state, llm=MagicMock())

    assert result["current_agent"] == "render_handbook:stale"
    assert result["component_results"]["itinerary"]["status"] == "stale"
    assert result["component_results"]["handbook"]["status"] == "stale"
    assert result["itinerary_components"]["handbook_structured"] is None
    writer.assert_not_called()


async def test_renderer_marks_budget_artifact_mutation_stale(monkeypatch):
    state = _typed_state()
    writer = MagicMock()
    monkeypatch.setattr(
        "src.agent.stage4_graph.HandbookRenderer.write_outputs",
        writer,
    )
    state["itinerary_components"]["budget_structured"]["summary"] = (
        "Canonical budget changed without recompiling the itinerary."
    )

    result = await render_handbook_node(state, llm=MagicMock())

    assert result["current_agent"] == "render_handbook:stale"
    assert result["component_results"]["itinerary"]["status"] == "stale"
    assert result["itinerary_components"]["handbook_structured"] is None
    writer.assert_not_called()
