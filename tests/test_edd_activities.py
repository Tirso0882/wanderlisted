"""Focused unit tests for Activities EDD Layer 1 contracts."""

from collections import Counter

from edd.activities import run_utils
from edd.activities.l1_dataset import DATASET, DATASET_SIZE, DATASET_VERSION
from edd.activities.l1_evaluate import (
    EVALUATORS,
    correct_accessibility,
    correct_locations,
    correct_proximity,
    minimum_search_calls,
    no_lodging_nearby_types,
    valid_nearby_place_types,
)
from edd.activities.l2_judge import FAITHFULNESS_RUBRIC
from edd.activities.l2_judge_cases import JUDGE_CASES
from edd.activities.l3_pairwise import HELPFULNESS_PAIRWISE_RUBRIC, judge_pairwise
from edd.activities.run_utils import (
    _load_trajectories,
    _save_trajectories,
    classify_activities_outcome,
)
from edd.harness import Trajectory

_EXPECTED_KEYS = {
    "locations",
    "interests",
    "activity_type",
    "accessibility",
    "group_fit",
    "travel_style",
    "venue_rental",
    "max_radius_meters",
    "proximity_location",
    "min_search_calls",
}


def _choice(options: set[str]) -> str:
    return sorted(options)[0]


def _groups(value) -> list[set[str]]:
    if isinstance(value, list):
        return value
    return [value]


def _golden_calls(expected: dict) -> list[dict]:
    terms = []
    for field in (
        "interests",
        "activity_type",
        "accessibility",
        "group_fit",
        "travel_style",
        "venue_rental",
    ):
        for group in _groups(expected.get(field, [])):
            terms.append(_choice(group))

    calls = []
    for location_group in expected["locations"]:
        location = _choice(location_group)
        calls.append(
            {
                "name": "search_places_text",
                "args": {"query": " ".join([*terms, location])},
            }
        )

    if len(calls) < expected.get("min_search_calls", 2) or "max_radius_meters" in expected:
        location = _choice(
            expected.get("proximity_location", expected["locations"][0])
        )
        calls.append(
            {
                "name": "search_places_nearby",
                "args": {
                    "location": location,
                    "place_type": "tourist_attraction",
                    "radius_meters": expected.get("max_radius_meters", 1500),
                },
            }
        )
    return calls


def test_activities_dataset_has_40_unique_well_formed_cases():
    assert DATASET_VERSION == "1.0.0"
    assert len(DATASET) == DATASET_SIZE == 40
    assert len({case["name"] for case in DATASET}) == DATASET_SIZE
    assert len({case["query"] for case in DATASET}) == DATASET_SIZE

    for case in DATASET:
        assert set(case) == {"name", "tags", "query", "expected"}
        assert case["tags"] and len(case["tags"]) == len(set(case["tags"]))
        assert case["query"].strip()
        expected = case["expected"]
        assert expected.keys() <= _EXPECTED_KEYS
        assert expected["locations"]
        assert all(isinstance(group, set) and group for group in expected["locations"])
        if "max_radius_meters" in expected:
            assert expected["max_radius_meters"] > 0
            assert expected["proximity_location"]


def test_activities_dataset_preserves_decision_coverage_floors():
    tags = Counter(tag for case in DATASET for tag in case["tags"])

    assert tags["accessibility"] >= 4
    assert tags["family"] >= 4
    assert tags["multi-city"] >= 3
    assert tags["venue-rental"] >= 5
    assert tags["proximity"] >= 3
    assert tags["travel-style"] >= 4
    assert tags["multilingual"] >= 3


def test_every_activities_golden_call_satisfies_its_evaluator_contract():
    failures = []
    for case in DATASET:
        calls = _golden_calls(case["expected"])
        for evaluator in EVALUATORS:
            result = evaluator(calls, case["expected"])
            if result["score"] == 0:
                failures.append(f"{case['name']}/{result['key']}: {result['comment']}")

    assert not failures, failures


def test_minimum_search_calls_enforces_agent_policy():
    calls = [{"name": "search_places_text", "args": {"query": "museums Tokyo"}}]

    result = minimum_search_calls(calls, {})

    assert result["score"] == 0
    assert "at least 2" in result["comment"]


def test_minimum_search_calls_rejects_duplicate_calls():
    call = {"name": "search_places_text", "args": {"query": "museums Tokyo"}}

    result = minimum_search_calls([call, call], {})

    assert result["score"] == 0
    assert "1 distinct" in result["comment"]


def test_valid_nearby_place_types_accepts_snake_case_identifier():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {"location": "Shinjuku", "place_type": "tourist_attraction"},
        }
    ]

    assert valid_nearby_place_types(calls, {})["score"] == 1


def test_valid_nearby_place_types_rejects_free_text():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {"location": "Paris", "place_type": "art museum"},
        }
    ]

    result = valid_nearby_place_types(calls, {})

    assert result["score"] == 0
    assert "art museum" in result["comment"]


def test_no_lodging_nearby_types_enforces_agent_ownership_boundary():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {"location": "Rome", "place_type": "lodging"},
        }
    ]

    result = no_lodging_nearby_types(calls, {})

    assert result["score"] == 0
    assert "lodging" in result["comment"]


def test_correct_locations_requires_every_requested_city():
    calls = [
        {"name": "search_places_text", "args": {"query": "museums in Tokyo"}},
        {"name": "search_places_text", "args": {"query": "markets in Tokyo"}},
    ]

    result = correct_locations(calls, {"locations": [{"tokyo"}, {"osaka"}]})

    assert result["score"] == 0
    assert "osaka" in result["comment"]


def test_correct_locations_accepts_one_search_per_requested_city():
    calls = [
        {"name": "search_places_text", "args": {"query": "museums in Tokyo"}},
        {"name": "search_places_text", "args": {"query": "markets in Osaka"}},
    ]

    assert correct_locations(calls, {"locations": [{"tokyo"}, {"osaka"}]})["score"] == 1


def test_correct_accessibility_normalizes_hyphens_and_case():
    calls = [
        {
            "name": "search_places_text",
            "args": {"query": "Wheelchair-Accessible museums in London"},
        }
    ]

    assert correct_accessibility(calls, {"accessibility": [{"wheelchair accessible"}]})[
        "score"
    ] == 1


def test_correct_proximity_accepts_requested_nearby_radius():
    calls = [
        {
            "name": "search_places_nearby",
            "args": {
                "location": "Sagrada Familia",
                "place_type": "tourist_attraction",
                "radius_meters": 800,
            },
        }
    ]
    expected = {
        "max_radius_meters": 800,
        "proximity_location": {"sagrada familia"},
    }

    assert correct_proximity(calls, expected)["score"] == 1


def test_correct_proximity_rejects_text_only_search():
    calls = [
        {
            "name": "search_places_text",
            "args": {"query": "attractions within 800m of Sagrada Familia"},
        }
    ]

    result = correct_proximity(calls, {"max_radius_meters": 800})

    assert result["score"] == 0
    assert "search_places_nearby" in result["comment"]


def test_judge_cases_are_balanced_and_held_out():
    labels = Counter(case["expected"] for case in JUDGE_CASES)

    assert len(JUDGE_CASES) == 24
    assert len({case["name"] for case in JUDGE_CASES}) == 24
    assert labels == {0: 6, 1: 6, 2: 6, 3: 6}
    assert "Melbourne" in FAITHFULNESS_RUBRIC
    assert all("Melbourne" not in case["trajectory"].query for case in JUDGE_CASES)


def test_classify_activities_outcome_completed():
    trajectory = Trajectory(
        query="activities",
        tool_outputs=[("search_places_text", "Found 2 result(s): attraction data")],
        final_text="Two activity options",
    )

    assert classify_activities_outcome(trajectory) == "completed"


def test_classify_activities_outcome_no_inventory():
    trajectory = Trajectory(
        query="activities",
        tool_outputs=[("search_places_text", "No places found for: query")],
        final_text="No matching venues were returned.",
    )

    assert classify_activities_outcome(trajectory) == "no_inventory"


def test_classify_activities_outcome_blocked_external():
    trajectory = Trajectory(
        query="activities",
        tool_outputs=[
            ("search_places_text", "Places API error (HTTP 429). Try again.")
        ],
    )

    assert classify_activities_outcome(trajectory) == "blocked_external"


def test_classify_invalid_argument_as_agent_failure():
    trajectory = Trajectory(
        query="activities",
        tool_outputs=[
            ("search_places_nearby", "Places API error (HTTP 400). Try again.")
        ],
        final_text="The nearby search failed.",
    )

    assert classify_activities_outcome(trajectory) == "failed"


def test_classify_missing_api_key_as_blocked_external():
    trajectory = Trajectory(
        query="activities",
        error="RuntimeError: GOOGLE_MAPS_API_KEY environment variable is not set",
    )

    assert classify_activities_outcome(trajectory) == "blocked_external"


def test_activities_trajectory_cache_roundtrip_and_redaction(tmp_path, monkeypatch):
    path = tmp_path / "trajectories.json"
    secret = "configured-google-key"
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", secret)
    original = [
        Trajectory(
            query="wheelchair-accessible museums in Kyoto",
            tool_calls=[
                {
                    "name": "search_places_text",
                    "args": {"query": "wheelchair accessible museums Kyoto"},
                }
            ],
            tool_outputs=[
                (
                    "search_places_text",
                    f"Photo: https://places.example/media?height=400&key={secret}",
                )
            ],
            final_text=f"[Photo](https://places.example/media?key={secret})",
        )
    ]

    _save_trajectories(path, [original[0].query], original)
    payload = path.read_text(encoding="utf-8")
    loaded = _load_trajectories(path, [original[0].query])

    assert secret not in payload
    assert payload.count("<REDACTED>") == 2
    assert loaded is not None
    assert secret not in loaded[0].tool_outputs[0][1]
    assert secret not in loaded[0].final_text


async def test_run_activities_dataset_reuses_identical_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("EDD_ACTIVITIES_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("EDD_REFRESH", raising=False)
    calls = 0

    async def fake_run_agent(agent_cls, query, **kwargs):
        nonlocal calls
        calls += 1
        return Trajectory(
            query=query,
            tool_outputs=[("search_places_text", "Found 1 result(s): Museum")],
            final_text="Museum option",
        )

    monkeypatch.setattr(run_utils, "run_agent", fake_run_agent)
    queries = ["museums in Kyoto"]
    model_config = {"tier": "fast", "azure_deployment": "test-activities-model"}

    first = await run_utils.run_activities_dataset(
        queries, model_config=model_config, max_concurrency=1
    )
    second = await run_utils.run_activities_dataset(
        queries, model_config=model_config, max_concurrency=1
    )

    assert calls == 1
    assert second == first


async def test_run_activities_dataset_does_not_cache_external_failure(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("EDD_ACTIVITIES_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("EDD_REFRESH", raising=False)
    calls = 0

    async def fake_run_agent(agent_cls, query, **kwargs):
        nonlocal calls
        calls += 1
        return Trajectory(
            query=query,
            tool_outputs=[
                ("search_places_text", "Places API error (HTTP 429). Try again.")
            ],
            final_text="The provider is unavailable.",
        )

    monkeypatch.setattr(run_utils, "run_agent", fake_run_agent)
    queries = ["museums in Kyoto"]
    model_config = {"tier": "fast", "azure_deployment": "test-activities-model"}

    await run_utils.run_activities_dataset(
        queries, model_config=model_config, max_concurrency=1
    )
    await run_utils.run_activities_dataset(
        queries, model_config=model_config, max_concurrency=1
    )

    assert calls == 2
    assert not list(tmp_path.glob("trajectories-*.json"))


async def test_pairwise_skips_provider_blocked_arm():
    blocked = Trajectory(
        query="activities",
        tool_outputs=[
            ("search_places_text", "Places API error (HTTP 403). Try again.")
        ],
        final_text="Provider error",
    )
    completed = Trajectory(
        query="activities",
        tool_outputs=[("search_places_text", "Found 1 result(s): Sakura Museum")],
        final_text="Sakura Museum is an activity option.",
    )

    result = await judge_pairwise(None, blocked, completed)

    assert result["winner"] is None
    assert "excluded" in result["comment"]


def test_activities_pairwise_rubric_requires_material_difference():
    assert "MATERIAL-DIFFERENCE RULE" in HELPFULNESS_PAIRWISE_RUBRIC
    assert "Return `tie` when advantages are minor or offsetting" in (
        HELPFULNESS_PAIRWISE_RUBRIC
    )
    assert "One extra venue" in HELPFULNESS_PAIRWISE_RUBRIC
