"""Fan-in completeness gate regression tests."""

from src.agent.nodes.component_gate import component_gate_node


def _outcome(status: str, message: str = "") -> dict:
    return {
        "component": "test",
        "status": status,
        "message": message,
        "missing_fields": [],
        "error_category": "none",
        "error_detail": "",
        "tools_called": [],
        "evidence_count": 0,
        "request_fingerprint": "",
        "data": None,
    }


async def test_all_requested_discovery_components_continue_to_safety():
    state = {
        "itinerary_components": {
            "routing": ["FlightsAgent", "HotelsAgent", "DestinationAgent"]
        },
        "component_results": {
            "flights": _outcome("completed"),
            "hotels": _outcome("completed"),
            "destination": _outcome("completed"),
        },
    }

    result = await component_gate_node(state)

    assert result["workflow_status"] == "planning"
    assert result["current_agent"] == "component_gate:ready"
    assert "messages" not in result


async def test_initial_gate_ignores_hotels_until_exact_stays_exist():
    state = {
        "itinerary_components": {
            "routing": ["FlightsAgent", "HotelsAgent", "DestinationAgent"]
        },
        "component_results": {
            "flights": _outcome("completed"),
            "destination": _outcome("completed"),
        },
    }

    result = await component_gate_node(
        state,
        eligible_components={"flights", "destination"},
    )

    assert result["workflow_status"] == "planning"


async def test_poland_trace_failures_stop_before_dependent_planning():
    state = {
        "trip_request": {"locale": "pl"},
        "itinerary_components": {
            "routing": [
                "FlightsAgent",
                "HotelsAgent",
                "DestinationAgent",
                "ItineraryAgent",
            ]
        },
        "component_results": {
            "flights": _outcome(
                "needs_user_input",
                "Z jakiego miasta w Kolumbii wylatujesz?",
            ),
            "hotels": _outcome(
                "needs_user_input",
                "Ile osób dorosłych podróżuje?",
            ),
            "destination": _outcome("blocked_external"),
        },
    }

    result = await component_gate_node(state)

    assert result["workflow_status"] == "needs_user_input"
    assert result["pending_questions"] == ["flights", "hotels"]
    assert result["current_agent"] == "component_gate:needs_user_input"
    message = result["messages"][0].content
    assert "Nie mogę jeszcze" in message
    assert "flights" in message
    assert "hotels" in message
    assert "destination" in message


async def test_missing_outcome_is_failed_instead_of_implicitly_successful():
    state = {
        "trip_request": {"locale": "en"},
        "itinerary_components": {"routing": ["FlightsAgent"]},
        "component_results": {},
    }

    result = await component_gate_node(state)

    assert result["workflow_status"] == "failed"
    assert "Missing component outcome" in result["messages"][0].content
