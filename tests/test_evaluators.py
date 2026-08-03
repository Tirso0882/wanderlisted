"""Tests for LangSmith evaluators in src/evaluation/evaluators.py."""

from src.evaluation.evaluators import (
    correct_destination,
    correct_tool_routing,
    valid_routing_decision,
    budget_completeness,
    non_empty_response,
    handbook_section_completeness,
    calibration_report,
)


# ── correct_tool_routing ─────────────────────────────────────────────────────


async def test_correct_tool_routing_flights():
    result = correct_tool_routing(
        inputs={"question": "Find flights from NYC to Tokyo"},
        outputs={"agents_routed": ["FlightsAgent"]},
    )
    assert result["key"] == "correct_tool_routing"
    assert result["score"] == 1


async def test_correct_tool_routing_hotels():
    result = correct_tool_routing(
        inputs={"question": "Best hotels to stay in Shinjuku"},
        outputs={"agents_routed": ["HotelsAgent"]},
    )
    assert result["score"] == 1


async def test_correct_tool_routing_restaurants():
    result = correct_tool_routing(
        inputs={"question": "Where to eat good ramen in Tokyo?"},
        outputs={"agents_routed": ["RestaurantsAgent"]},
    )
    assert result["score"] == 1


async def test_correct_tool_routing_weather():
    result = correct_tool_routing(
        inputs={"question": "What's the weather like in Bangkok in April?"},
        outputs={"agents_routed": ["TravelReadinessAgent"]},
    )
    assert result["score"] == 1


async def test_correct_tool_routing_budget():
    result = correct_tool_routing(
        inputs={"question": "How much will the trip cost?"},
        outputs={"agents_routed": ["BudgetAgent"]},
    )
    assert result["score"] == 1


async def test_correct_tool_routing_generic():
    """Generic queries should pass (score 1) since any routing works."""
    result = correct_tool_routing(
        inputs={"question": "Plan a trip to Barcelona"},
        outputs={"agents_routed": ["TravelReadinessAgent", "HotelsAgent"]},
    )
    assert result["score"] == 1


async def test_correct_tool_routing_wrong_route():
    """Flight query routed to HotelsAgent should fail."""
    result = correct_tool_routing(
        inputs={"question": "Find flights to London"},
        outputs={"agents_routed": ["HotelsAgent"]},
    )
    assert result["score"] == 0


# ── valid_routing_decision ───────────────────────────────────────────────────


async def test_valid_routing_decision_valid():
    result = valid_routing_decision(
        inputs={},
        outputs={
            "agents_routed": ["FlightsAgent", "HotelsAgent", "TravelReadinessAgent"]
        },
    )
    assert result["key"] == "valid_routing_decision"
    assert result["score"] == 1


async def test_valid_routing_decision_invalid_agent():
    result = valid_routing_decision(
        inputs={},
        outputs={"agents_routed": ["FlightsAgent", "FakeAgent"]},
    )
    assert result["score"] == 0


async def test_valid_routing_decision_empty():
    result = valid_routing_decision(
        inputs={},
        outputs={"agents_routed": []},
    )
    assert result["score"] == 0


# ── budget_completeness ──────────────────────────────────────────────────────


async def test_budget_completeness_full():
    result = budget_completeness(
        inputs={},
        outputs={
            "budget_structured": {
                "flights": 1200,
                "accommodation": 800,
                "meals": 300,
                "activities": 200,
                "transport": 150,
            },
        },
    )
    assert result["key"] == "budget_completeness"
    assert result["score"] == 1.0


async def test_budget_completeness_partial():
    result = budget_completeness(
        inputs={},
        outputs={
            "budget_structured": {
                "flights": 1200,
                "accommodation": 800,
                # missing: meals, activities, transport
            },
        },
    )
    assert 0 < result["score"] < 1.0


async def test_budget_completeness_empty():
    result = budget_completeness(
        inputs={},
        outputs={"budget_structured": {}},
    )
    assert result["score"] == 0.0


async def test_budget_completeness_missing_key():
    result = budget_completeness(
        inputs={},
        outputs={},
    )
    assert result["score"] == 0.0


# ── correct_destination ──────────────────────────────────────────────────────


async def test_correct_destination_match():
    result = correct_destination(
        inputs={},
        reference_outputs={"destinations": ["Tokyo", "Kyoto"]},
        outputs={"destinations_covered": ["tokyo", "kyoto"]},
    )
    assert result["key"] == "correct_destination"
    assert result["score"] == 1.0


async def test_correct_destination_partial():
    result = correct_destination(
        inputs={},
        reference_outputs={"destinations": ["Tokyo", "Kyoto", "Osaka"]},
        outputs={"destinations_covered": ["tokyo"]},
    )
    assert abs(result["score"] - 1 / 3) < 0.01


async def test_correct_destination_mismatch():
    result = correct_destination(
        inputs={},
        reference_outputs={"destinations": ["Tokyo"]},
        outputs={"destinations_covered": ["Bangkok"]},
    )
    assert result["score"] == 0.0


async def test_correct_destination_no_reference():
    """No reference destinations → score should be 1.0 (nothing to check)."""
    result = correct_destination(
        inputs={},
        reference_outputs={"destinations": []},
        outputs={"destinations_covered": ["Tokyo"]},
    )
    assert result["score"] == 1


# ── non_empty_response ───────────────────────────────────────────────────────


async def test_non_empty_response_valid():
    result = non_empty_response(
        outputs={"output": "Here is your Tokyo travel plan with flights and hotels..."},
    )
    assert result["key"] == "non_empty_response"
    assert result["score"] == 1


async def test_non_empty_response_empty():
    result = non_empty_response(outputs={"output": ""})
    assert result["score"] == 0


async def test_non_empty_response_whitespace():
    result = non_empty_response(outputs={"output": "   \n  "})
    assert result["score"] == 0


async def test_non_empty_response_error():
    result = non_empty_response(outputs={"output": "Error: something went wrong"})
    assert result["score"] == 0


async def test_non_empty_response_error_later_in_text():
    """Error keyword after first 50 chars should still pass."""
    result = non_empty_response(
        outputs={
            "output": "Here is a great travel plan. " * 3
            + "Also handle errors gracefully."
        },
    )
    assert result["score"] == 1


# ── handbook_section_completeness ────────────────────────────────────────────


async def test_handbook_section_completeness_full():
    output = (
        "Flight from NYC to Tokyo confirmed. "
        "Hotel in Shinjuku booked. "
        "Budget: $3500 total. "
        "Safety: Level 1 advisory. "
        "Itinerary: Day 1 arrive in Tokyo. "
        "Restaurant: Ichiran Ramen. "
        "Activities: visit Meiji Shrine."
    )
    result = handbook_section_completeness(outputs={"output": output})
    assert result["key"] == "handbook_section_completeness"
    assert result["score"] >= 0.8


async def test_handbook_section_completeness_minimal():
    result = handbook_section_completeness(outputs={"output": "Hello, welcome!"})
    assert result["score"] < 0.3


# ── calibration_report ───────────────────────────────────────────────────────


async def test_calibration_report_perfect_agreement():
    human = [3, 2, 1, 0, 3]
    judge = [3, 2, 1, 0, 3]
    report = calibration_report(human, judge)
    assert report["exact_match_pct"] == 1.0
    assert report["within_one_pct"] == 1.0
    assert report["mean_absolute_error"] == 0.0


async def test_calibration_report_within_one():
    human = [3, 2, 1, 0]
    judge = [2, 3, 2, 1]
    report = calibration_report(human, judge)
    assert report["exact_match_pct"] == 0.0
    assert report["within_one_pct"] == 1.0
    assert report["mean_absolute_error"] == 1.0


async def test_calibration_report_empty():
    report = calibration_report([], [])
    assert report["exact_match_pct"] == 0
    assert report["mean_absolute_error"] == float("inf")


async def test_calibration_report_mixed():
    human = [3, 2, 1, 0, 3]
    judge = [3, 0, 1, 2, 1]
    report = calibration_report(human, judge)
    assert 0 < report["exact_match_pct"] < 1.0
    assert report["within_one_pct"] < 1.0
