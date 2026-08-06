"""Specialist trajectory outcome classification tests."""

import json

from langchain_core.messages import AIMessage, ToolMessage

from src.agent.policies.component_outcomes import classify_component_result


def test_clarification_without_tool_call_needs_user_input():
    result = classify_component_result(
        "flights",
        [AIMessage(content="Z jakiego miasta w Kolumbii wylatujesz?")],
    )
    assert result.status == "needs_user_input"
    assert result.tools_called == []


def test_tool_evidence_and_final_answer_complete_component():
    result = classify_component_result(
        "hotels",
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_hotels_hotelbeds",
                        "args": {"city_code": "WAW"},
                        "id": "hotel-call",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="Hotels from Hotelbeds in WAW: Hotel Central",
                tool_call_id="hotel-call",
            ),
            AIMessage(content="Hotel Central is the best matching option."),
        ],
    )
    assert result.status == "completed"
    assert result.tools_called == ["search_hotels_hotelbeds"]
    assert result.evidence_count == 1


def test_no_inventory_is_not_marked_completed():
    result = classify_component_result(
        "flights",
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_flights",
                        "args": {},
                        "id": "flight-call",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="No flights found from BOG to WAW.",
                tool_call_id="flight-call",
            ),
            AIMessage(content="No flights found for those dates."),
        ],
    )
    assert result.status == "no_inventory"


def test_provider_timeout_is_blocked_external():
    result = classify_component_result(
        "destination",
        [],
        error=TimeoutError("request timed out"),
    )
    assert result.status == "blocked_external"
    assert result.error_category == "timeout"


def test_places_component_requires_and_exposes_structured_evidence():
    payload = {
        "places": [
            {
                "source_id": "place-1",
                "place_id": "place-1",
                "name": "Museum",
                "search_context": "museums in paris",
            }
        ]
    }
    result = classify_component_result(
        "activities",
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_places_text",
                        "args": {"query": "museums in paris"},
                        "id": "places-call",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="PLACE_RESULTS_JSON:\n" + json.dumps(payload),
                tool_call_id="places-call",
            ),
            AIMessage(content="I found one matching museum."),
        ],
    )

    assert result.status == "completed"
    assert result.data == payload
    assert result.evidence_count == 1


def test_places_component_prose_without_structured_evidence_fails():
    result = classify_component_result(
        "activities",
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_places_text",
                        "args": {"query": "museums in paris"},
                        "id": "places-call",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(content="Museum A", tool_call_id="places-call"),
            AIMessage(content="Visit Museum A at 10:00 and budget 20 EUR."),
        ],
    )

    assert result.status == "failed"
    assert result.data is None
