"""TripSkeleton node tests for exact and flexible date selection."""

from langchain_core.messages import ToolMessage

from src.agent.nodes.trip_skeleton import trip_skeleton_node
from src.models import FlightWindowOption, FlightWindowSearchResult, TripRequest


def _flight_message(result: FlightWindowSearchResult, call_id: str) -> ToolMessage:
    return ToolMessage(
        name="search_cheapest_round_trip_in_window",
        content=(
            "Flexible round-trip search coverage: exhaustive.\n"
            "FLIGHT_WINDOW_RESULT_JSON:\n" + result.model_dump_json()
        ),
        tool_call_id=call_id,
    )


async def test_exact_dates_build_generic_duration_skeleton_without_flight_evidence():
    request = TripRequest(
        scope="focused",
        destinations=["paris", "lyon"],
        requested_capabilities=["hotels"],
        date_window={"exact_start": "2026-10-01", "exact_end": "2026-10-09"},
        travelers={"adults": 1},
    )

    result = await trip_skeleton_node(
        {"trip_request": request.model_dump(mode="json"), "itinerary_components": {}}
    )

    skeleton = result["itinerary_components"]["trip_skeleton_structured"]
    assert result["workflow_status"] == "skeleton_ready"
    assert skeleton["duration_days"] == 9
    assert skeleton["total_nights"] == 8
    assert [stay["nights"] for stay in skeleton["stays"]] == [4, 4]


async def test_flexible_skeleton_selects_global_cheapest_gateway_option():
    expensive = FlightWindowSearchResult(
        origin="BOG",
        destination="KRK",
        earliest_departure="2026-08-20",
        latest_return="2026-09-20",
        duration_days=14,
        total_valid_pairs=19,
        searched_pairs=19,
        coverage_complete=True,
        options=[
            FlightWindowOption(
                departure_date="2026-08-22",
                return_date="2026-09-04",
                total_amount="900.00",
                origin="BOG",
                destination="KRK",
            )
        ],
    )
    cheap = FlightWindowSearchResult(
        origin="BOG",
        destination="WAW",
        earliest_departure="2026-08-20",
        latest_return="2026-09-20",
        duration_days=14,
        total_valid_pairs=19,
        searched_pairs=19,
        coverage_complete=True,
        options=[
            FlightWindowOption(
                departure_date="2026-08-25",
                return_date="2026-09-07",
                total_amount="700.00",
                origin="BOG",
                destination="WAW",
            )
        ],
    )
    request = TripRequest(
        scope="full_itinerary",
        origin_city="bogota",
        destinations=["warszawa", "wroclaw", "krakow", "gdansk"],
        date_window={
            "earliest_start": "2026-08-20",
            "latest_end": "2026-09-20",
            "duration_days": 14,
            "flexible": True,
        },
        travelers={"adults": 1},
    )
    state = {
        "trip_request": request.model_dump(mode="json"),
        "itinerary_components": {
            "flights": {
                "messages": [
                    _flight_message(expensive, "flight-1"),
                    _flight_message(cheap, "flight-2"),
                ]
            }
        },
    }

    result = await trip_skeleton_node(state)

    skeleton = result["itinerary_components"]["trip_skeleton_structured"]
    assert skeleton["start_date"] == "2026-08-25"
    assert skeleton["end_date"] == "2026-09-07"
    assert skeleton["selected_flight"]["destination"] == "WAW"
    assert skeleton["selected_flight"]["total_amount"] == "700.00"
    assert sum(stay["nights"] for stay in skeleton["stays"]) == 13
    assert skeleton["entry_city"] == "warszawa"
    assert skeleton["exit_city"] == "warszawa"
    assert skeleton["stays"][-1]["city"] == "warszawa"
    assert skeleton["stays"][-1]["nights"] == 1


async def test_flexible_skeleton_fails_without_typed_flight_window_evidence():
    request = TripRequest(
        scope="full_itinerary",
        origin_city="bogota",
        destinations=["warszawa", "krakow"],
        date_window={
            "earliest_start": "2026-08-20",
            "latest_end": "2026-09-20",
            "duration_days": 14,
            "flexible": True,
        },
        travelers={"adults": 1},
    )

    result = await trip_skeleton_node(
        {"trip_request": request.model_dump(mode="json"), "itinerary_components": {}}
    )

    assert result["workflow_status"] == "failed"
    assert result["component_results"]["trip_skeleton"]["status"] == "failed"
    assert "typed round-trip flight search" in result["messages"][0].content
