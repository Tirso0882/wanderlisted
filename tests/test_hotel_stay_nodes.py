"""Post-TripSkeleton per-city Hotelbeds execution tests."""

from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agent.stage4_graph import hotel_fan_in_node, hotel_stay_node
from src.models import TripRequest


async def test_hotel_worker_receives_exact_stay_city_code_and_occupancy():
    executor = AsyncMock()

    async def invoke(payload):
        call = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_hotels_hotelbeds",
                    "args": {
                        "city_code": "KRK",
                        "check_in_date": "2026-08-24",
                        "check_out_date": "2026-08-27",
                        "adults": 2,
                    },
                    "id": "hotel-call",
                    "type": "tool_call",
                }
            ],
        )
        tool = ToolMessage(
            name="search_hotels_hotelbeds",
            content="Hotels from Hotelbeds in KRK: Hotel Test",
            tool_call_id="hotel-call",
        )
        return {
            "messages": [
                *payload["messages"],
                call,
                tool,
                AIMessage(content="Hotel Test is available for the exact stay."),
            ]
        }

    executor.ainvoke.side_effect = invoke
    request = TripRequest(
        scope="full_itinerary",
        destinations=["krakow"],
        date_window={"exact_start": "2026-08-24", "exact_end": "2026-08-27"},
        travelers={"adults": 2, "children": 1, "child_ages": [7]},
    )
    state = {
        "messages": [HumanMessage(content="Find hotels")],
        "trip_request": request.model_dump(mode="json"),
        "itinerary_components": {},
        "active_hotel_stay": {
            "sequence": 1,
            "city": "krakow",
            "check_in": "2026-08-24",
            "check_out": "2026-08-27",
            "nights": 3,
        },
    }

    result = await hotel_stay_node(state, executor=executor)

    input_messages = executor.ainvoke.await_args.args[0]["messages"]
    instruction = input_messages[0].content
    assert "city_code=KRK" in instruction
    assert "check_in_date=2026-08-24" in instruction
    assert "check_out_date=2026-08-27" in instruction
    assert "adults=2" in instruction
    assert "children_ages='7'" in instruction
    search = result["hotel_search_results"]["stay-1"]
    assert search["city_code"] == "KRK"
    assert search["outcome"]["status"] == "completed"


def _search_result(sequence: int, city: str, status: str) -> dict:
    final = AIMessage(content=f"{city} hotel result")
    return {
        "stay": {
            "sequence": sequence,
            "city": city,
            "check_in": f"2026-08-{20 + sequence:02d}",
            "check_out": f"2026-08-{21 + sequence:02d}",
            "nights": 1,
        },
        "city_code": "TST",
        "messages": [final],
        "outcome": {
            "component": "hotels",
            "status": status,
            "data": None,
            "missing_fields": [],
            "message": final.content,
            "error_category": "none",
            "error_detail": "",
            "tools_called": ["search_hotels_hotelbeds"],
            "evidence_count": 1,
            "request_fingerprint": "",
        },
    }


async def test_hotel_fan_in_completes_only_when_every_city_completes():
    state = {
        "itinerary_components": {"routing": ["HotelsAgent", "ItineraryAgent"]},
        "hotel_search_results": {
            "stay-2": _search_result(2, "krakow", "completed"),
            "stay-1": _search_result(1, "warszawa", "completed"),
        },
    }

    result = await hotel_fan_in_node(state)

    assert result["component_results"]["hotels"]["status"] == "completed"
    stays = result["component_results"]["hotels"]["data"]["stays"]
    assert [stay["stay"]["city"] for stay in stays] == ["warszawa", "krakow"]
    assert len(result["itinerary_components"]["hotels"]["messages"]) == 2


async def test_hotel_fan_in_preserves_no_inventory_failure():
    state = {
        "itinerary_components": {"routing": ["HotelsAgent", "ItineraryAgent"]},
        "hotel_search_results": {
            "stay-1": _search_result(1, "warszawa", "completed"),
            "stay-2": _search_result(2, "krakow", "no_inventory"),
        },
    }

    result = await hotel_fan_in_node(state)

    assert result["component_results"]["hotels"]["status"] == "no_inventory"
    assert "krakow: no_inventory" in result["component_results"]["hotels"]["message"]
