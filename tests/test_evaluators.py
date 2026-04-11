"""Tests for LangSmith evaluators in src/evaluation/evaluators.py."""

from unittest.mock import patch, MagicMock

from src.evaluation.evaluators import (
    correct_destination,
    correct_tool_routing,
    valid_routing_decision,
    budget_completeness,
    non_empty_response,
    handbook_section_completeness,
    calibration_report,
    # RAG evaluators
    context_precision,
    context_recall,
    context_entity_recall,
    noise_sensitivity,
    response_relevancy,
    faithfulness,
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
        outputs={"agents_routed": ["DestinationAgent"]},
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
        outputs={"agents_routed": ["DestinationAgent", "HotelsAgent"]},
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
        outputs={"agents_routed": ["FlightsAgent", "HotelsAgent", "DestinationAgent"]},
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
        outputs={"output": "Here is a great travel plan. " * 3 + "Also handle errors gracefully."},
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


# ── RAG Evaluators (mock LLM calls) ─────────────────────────────────────────

def _mock_rag_judge(score: float, reasoning: str = "test"):
    """Create a mock for _ask_rag_judge returning a fixed score."""
    return patch(
        "src.evaluation.evaluators._ask_rag_judge",
        return_value={"score": score, "reasoning": reasoning},
    )


async def test_context_precision_returns_correct_key():
    with _mock_rag_judge(0.85):
        result = context_precision(
            inputs={"question": "Best temples in Bangkok?"},
            reference_outputs={"reference": "Wat Pho, Wat Arun"},
            outputs={"retrieved_contexts": ["Wat Pho is famous.", "Unrelated text."]},
        )
    assert result["key"] == "context_precision"
    assert result["score"] == 0.85
    assert "comment" in result


async def test_context_recall_returns_correct_key():
    with _mock_rag_judge(0.70):
        result = context_recall(
            inputs={"question": "How to get to Bangkok airport?"},
            reference_outputs={"reference": "Airport Rail Link to Phaya Thai."},
            outputs={"retrieved_contexts": ["Airport Rail Link info."]},
        )
    assert result["key"] == "context_recall"
    assert result["score"] == 0.70


async def test_context_entity_recall_returns_correct_key():
    with _mock_rag_judge(1.0):
        result = context_entity_recall(
            inputs={},
            reference_outputs={"reference": "Wat Pho and Wat Arun are top temples."},
            outputs={"retrieved_contexts": ["Wat Pho is the oldest temple.", "Wat Arun overlooks the river."]},
        )
    assert result["key"] == "context_entity_recall"
    assert result["score"] == 1.0


async def test_noise_sensitivity_returns_correct_key():
    with _mock_rag_judge(0.90):
        result = noise_sensitivity(
            inputs={"question": "Best food in Tokyo?"},
            reference_outputs={"reference": "Sushi, ramen, tempura."},
            outputs={
                "output": "Top foods include sushi and ramen.",
                "retrieved_contexts": ["Tokyo ramen is famous.", "Paris has the Eiffel Tower."],
            },
        )
    assert result["key"] == "noise_sensitivity"
    assert result["score"] == 0.90


async def test_response_relevancy_returns_correct_key():
    with _mock_rag_judge(0.95):
        result = response_relevancy(
            inputs={"question": "Best area to stay in Bangkok?"},
            outputs={"output": "Sukhumvit and Silom are great areas to stay."},
        )
    assert result["key"] == "response_relevancy"
    assert result["score"] == 0.95


async def test_faithfulness_returns_correct_key():
    with _mock_rag_judge(0.80):
        result = faithfulness(
            inputs={},
            outputs={
                "output": "Pad Thai costs 40-60 baht from street vendors.",
                "retrieved_contexts": ["Pad Thai costs 40-60 baht at street stalls in Bangkok."],
            },
        )
    assert result["key"] == "faithfulness"
    assert result["score"] == 0.80


async def test_rag_evaluators_handle_empty_contexts():
    with _mock_rag_judge(0.0, "No contexts provided"):
        result = faithfulness(
            inputs={},
            outputs={"output": "Some answer", "retrieved_contexts": []},
        )
    assert result["score"] == 0.0
