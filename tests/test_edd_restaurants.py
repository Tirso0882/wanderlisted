"""Focused unit tests for Restaurant EDD evaluators and run policy."""

from collections import Counter

from edd.harness import Trajectory
from edd.restaurants.l1_dataset import DATASET
from edd.restaurants.l1_evaluate import (
    EVALUATORS,
    correct_dietary,
    correct_location,
    correct_proximity,
    minimum_search_calls,
    valid_nearby_place_types,
)
from edd.restaurants.l2_judge import FAITHFULNESS_RUBRIC
from edd.restaurants.l2_judge_cases import JUDGE_CASES
from edd.restaurants.l3_pairwise import HELPFULNESS_PAIRWISE_RUBRIC, judge_pairwise
from edd.restaurants.run_utils import (
    _load_trajectories,
    _save_trajectories,
    classify_restaurant_outcome,
)
from edd.rubrics import Preference, compare_pairwise


def test_minimum_search_calls_enforces_agent_policy():
    calls = [{"name": "search_places_text", "args": {"query": "sushi Tokyo"}}]

    result = minimum_search_calls(calls, {})

    assert result["score"] == 0
    assert "at least 2" in result["comment"]


def test_minimum_search_calls_rejects_duplicate_calls():
    call = {"name": "search_places_text", "args": {"query": "sushi Tokyo"}}

    result = minimum_search_calls([call, call], {})

    assert result["score"] == 0
    assert "1 distinct" in result["comment"]


def test_valid_nearby_place_types_accepts_snake_case_identifier():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {
                "location": "Shinjuku",
                "place_type": "sushi_restaurant",
            },
        }
    ]

    assert valid_nearby_place_types(calls, {})["score"] == 1


def test_valid_nearby_place_types_rejects_free_text():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {
                "location": "Alfama",
                "place_type": "seafood restaurant",
            },
        }
    ]

    result = valid_nearby_place_types(calls, {})

    assert result["score"] == 0
    assert "seafood restaurant" in result["comment"]


def test_correct_location_checks_every_places_call():
    calls = [
        {"name": "search_places_text", "args": {"query": "sushi in Tokyo"}},
        {"name": "search_places_text", "args": {"query": "ramen in Osaka"}},
    ]

    result = correct_location(calls, {"location": {"tokyo", "shinjuku"}})

    assert result["score"] == 0
    assert "osaka" in result["comment"]


def test_correct_location_accepts_neighborhood_as_location_context():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {"location": "Shinjuku", "place_type": "restaurant"},
        }
    ]

    result = correct_location(calls, {"location": {"tokyo", "shinjuku"}})

    assert result["score"] == 1


def test_correct_dietary_normalizes_hyphens_and_case():
    calls = [
        {
            "name": "search_places_text",
            "args": {"query": "Best Gluten-Free bakeries in Paris"},
        }
    ]

    assert correct_dietary(calls, {"dietary": {"gluten free"}})["score"] == 1


def test_term_matching_accepts_regular_plural():
    calls = [
        {
            "name": "search_places_text",
            "args": {"query": "restaurants and food markets in Istanbul"},
        }
    ]
    expected = {"venue_type": [{"restaurant"}, {"food market", "market"}]}

    result = next(
        evaluator(calls, expected)
        for evaluator in EVALUATORS
        if evaluator.__name__ == "correct_venue_type"
    )

    assert result["score"] == 1


def test_term_matching_accepts_y_to_ies_plural():
    calls = [
        {
            "name": "search_places_text",
            "args": {"query": "gluten free bakeries in Paris"},
        }
    ]

    result = next(
        evaluator(calls, {"venue_type": {"bakery"}})
        for evaluator in EVALUATORS
        if evaluator.__name__ == "correct_venue_type"
    )

    assert result["score"] == 1


def test_multi_concept_constraint_requires_every_group():
    calls = [
        {
            "name": "search_places_text",
            "args": {"query": "food markets in Bangkok"},
        }
    ]
    expected = {"venue_type": [{"food market", "market"}, {"street food"}]}

    result = next(
        evaluator(calls, expected)
        for evaluator in EVALUATORS
        if evaluator.__name__ == "correct_venue_type"
    )

    assert result["score"] == 0
    assert "street food" in result["comment"]


def test_correct_proximity_accepts_requested_nearby_radius():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {
                "location": "Sagrada Familia",
                "place_type": "restaurant",
                "radius_meters": 800,
            },
        }
    ]
    expected = {
        "max_radius_meters": 800,
        "proximity_location": {"sagrada familia"},
    }

    assert correct_proximity(calls, expected)["score"] == 1


def test_correct_proximity_rejects_undersized_search_radius():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {
                "location": "Sagrada Familia",
                "place_type": "restaurant",
                "radius_meters": 500,
            },
        }
    ]

    result = correct_proximity(
        calls,
        {
            "max_radius_meters": 800,
            "proximity_location": {"sagrada familia"},
        },
    )

    assert result["score"] == 0


def test_correct_proximity_rejects_text_only_search():
    calls = [
        {
            "name": "search_places_text",
            "args": {"query": "restaurants within 800m of Sagrada Familia"},
        }
    ]

    result = correct_proximity(calls, {"max_radius_meters": 800})

    assert result["score"] == 0
    assert "search_places_nearby" in result["comment"]


def test_dataset_exercises_every_optional_evaluator():
    scored = {evaluator.__name__: 0 for evaluator in EVALUATORS}
    for case in DATASET:
        for evaluator in EVALUATORS:
            if evaluator([], case["expected"])["score"] is not None:
                scored[evaluator.__name__] += 1

    assert len(DATASET) == 50
    assert len({case["name"] for case in DATASET}) == 50
    assert len({case["query"] for case in DATASET}) == 50
    assert all(
        count > 0
        for name, count in scored.items()
        if name != "valid_nearby_place_types"
    )


def test_judge_cases_are_balanced_and_held_out():
    labels = Counter(case["expected"] for case in JUDGE_CASES)

    assert len(JUDGE_CASES) == 50
    assert len({case["name"] for case in JUDGE_CASES}) == 50
    assert labels == {0: 12, 1: 12, 2: 13, 3: 13}
    assert "Melbourne" in FAITHFULNESS_RUBRIC
    assert all("Melbourne" not in case["trajectory"].query for case in JUDGE_CASES)


def test_classify_restaurant_outcome_completed():
    trajectory = Trajectory(
        query="restaurants",
        tool_outputs=[("search_places_text", "Found 2 result(s): restaurant data")],
        final_text="Two restaurant options",
    )

    assert classify_restaurant_outcome(trajectory) == "completed"


def test_classify_restaurant_outcome_no_inventory():
    trajectory = Trajectory(
        query="restaurants",
        tool_outputs=[("search_places_text", "No places found for: query")],
        final_text="No matching venues were returned.",
    )

    assert classify_restaurant_outcome(trajectory) == "no_inventory"


def test_classify_restaurant_outcome_blocked_external():
    trajectory = Trajectory(
        query="restaurants",
        tool_outputs=[
            ("search_places_text", "Places API error (HTTP 429). Try again.")
        ],
    )

    assert classify_restaurant_outcome(trajectory) == "blocked_external"


def test_classify_invalid_argument_as_agent_failure():
    trajectory = Trajectory(
        query="restaurants",
        tool_outputs=[
            ("search_places_nearby", "Places API error (HTTP 400). Try again.")
        ],
        final_text="The nearby search failed.",
    )

    assert classify_restaurant_outcome(trajectory) == "failed"


def test_classify_provider_server_error_as_blocked_external():
    trajectory = Trajectory(
        query="restaurants",
        tool_outputs=[
            ("search_places_text", "Places API error (HTTP 503). Try again.")
        ],
    )

    assert classify_restaurant_outcome(trajectory) == "blocked_external"


def test_classify_geocoding_failure_as_agent_or_result_failure():
    trajectory = Trajectory(
        query="restaurants",
        tool_outputs=[
            ("search_places_nearby", "Could not geocode the provided location.")
        ],
        final_text="I could not resolve that location.",
    )

    assert classify_restaurant_outcome(trajectory) == "failed"


def test_classify_missing_api_key_as_blocked_external():
    trajectory = Trajectory(
        query="restaurants",
        error="RuntimeError: GOOGLE_MAPS_API_KEY environment variable is not set",
    )

    assert classify_restaurant_outcome(trajectory) == "blocked_external"


def test_restaurant_trajectory_cache_roundtrip(tmp_path):
    path = tmp_path / "trajectories.json"
    queries = ["sushi in Tokyo"]
    original = [
        Trajectory(
            query=queries[0],
            tool_calls=[
                {
                    "name": "search_places_text",
                    "args": {"query": "sushi in Tokyo"},
                }
            ],
            tool_outputs=[("search_places_text", "Found 1 result(s): Sushi Sora")],
            final_text="Sushi Sora",
        )
    ]

    _save_trajectories(path, queries, original)
    loaded = _load_trajectories(path, queries)

    assert loaded == original
    assert loaded[0].tool_outputs == [
        ("search_places_text", "Found 1 result(s): Sushi Sora")
    ]


def test_restaurant_trajectory_cache_redacts_api_keys(tmp_path, monkeypatch):
    path = tmp_path / "trajectories.json"
    secret = "configured-google-key"
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", secret)
    trajectory = Trajectory(
        query="restaurants",
        tool_outputs=[
            (
                "search_places_text",
                f"Photo: https://places.example/media?height=400&key={secret}",
            )
        ],
        final_text=f"[Photo](https://places.example/media?key={secret})",
    )

    _save_trajectories(path, [trajectory.query], [trajectory])
    payload = path.read_text(encoding="utf-8")
    loaded = _load_trajectories(path, [trajectory.query])

    assert secret not in payload
    assert payload.count("<REDACTED>") == 2
    assert loaded is not None
    assert secret not in loaded[0].tool_outputs[0][1]
    assert secret not in loaded[0].final_text


async def test_pairwise_skips_provider_blocked_arm():
    blocked = Trajectory(
        query="restaurants",
        tool_outputs=[
            ("search_places_text", "Places API error (HTTP 403). Try again.")
        ],
        final_text="Provider error",
    )
    completed = Trajectory(
        query="restaurants",
        tool_outputs=[("search_places_text", "Found 1 result(s): Sushi Sora")],
        final_text="Sushi Sora is a good option.",
    )

    result = await judge_pairwise(None, blocked, completed)

    assert result["winner"] is None
    assert "excluded" in result["comment"]


async def test_pairwise_preserves_both_order_specific_verdicts():
    class FirstSlotJudge:
        async def ainvoke(self, messages):
            payload = messages[-1].content
            first_answer = payload.split("ANSWER A:\n", 1)[1].split(
                "\n\nANSWER B:\n", 1
            )[0]
            return Preference(
                reasoning=f"Preferred the first slot containing {first_answer}.",
                winner="A",
            )

    trajectory_a = Trajectory(query="restaurants", final_text="Terra answer")
    trajectory_b = Trajectory(query="restaurants", final_text="Luna answer")

    result = await compare_pairwise(
        FirstSlotJudge(), trajectory_a, trajectory_b, rubric="Compare helpfulness."
    )

    assert result["winner"] == "tie"
    assert result["consistent"] is False
    assert result["winner_forward"] == "A"
    assert result["winner_reverse"] == "B"
    assert result["slot_winner_forward"] == "A"
    assert result["slot_winner_reverse"] == "A"
    assert result["inconsistency_type"] == "winner_reversal"
    assert "Terra answer" in result["reasoning_forward"]
    assert "Luna answer" in result["reasoning_reverse"]


async def test_pairwise_classifies_winner_vs_tie_as_boundary_instability():
    class ForwardWinnerReverseTieJudge:
        async def ainvoke(self, messages):
            payload = messages[-1].content
            first_answer = payload.split("ANSWER A:\n", 1)[1].split(
                "\n\nANSWER B:\n", 1
            )[0]
            if first_answer == "Terra answer":
                return Preference(reasoning="Terra materially wins.", winner="A")
            return Preference(reasoning="The answers are equivalent.", winner="tie")

    result = await compare_pairwise(
        ForwardWinnerReverseTieJudge(),
        Trajectory(query="restaurants", final_text="Terra answer"),
        Trajectory(query="restaurants", final_text="Luna answer"),
        rubric="Compare helpfulness.",
    )

    assert result["winner"] == "tie"
    assert result["consistent"] is False
    assert result["inconsistency_type"] == "tie_boundary"


def test_restaurant_pairwise_rubric_requires_material_difference():
    assert "MATERIAL-DIFFERENCE RULE" in HELPFULNESS_PAIRWISE_RUBRIC
    assert "Return `tie` when advantages are minor or offsetting" in (
        HELPFULNESS_PAIRWISE_RUBRIC
    )
    assert "One extra venue" in HELPFULNESS_PAIRWISE_RUBRIC
