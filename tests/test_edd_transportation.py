"""Focused unit tests for Transportation EDD data, evaluators, and run policy."""

from collections import Counter
import re

from edd.harness import Trajectory
from edd.transportation.l1_dataset import DATASET, DATASET_SIZE, DATASET_VERSION
from edd.transportation.l1_evaluate import (
    EVALUATORS,
    correct_include_steps,
    correct_route_pairs,
    correct_travel_modes,
    correct_waypoints,
    no_unrequested_route_pairs,
    no_unrequested_waypoints,
    valid_travel_modes,
)
from edd.transportation.l2_judge import FAITHFULNESS_RUBRIC
from edd.transportation.l2_judge_cases import JUDGE_CASES
from edd.transportation.l3_pairwise import (
    HELPFULNESS_PAIRWISE_RUBRIC,
    judge_pairwise,
)
from edd.transportation.run_utils import (
    _load_trajectories,
    _save_trajectories,
    classify_transportation_outcome,
)

_EXPECTED_KEYS = {"routes", "min_route_calls"}
_ROUTE_KEYS = {
    "origin",
    "destination",
    "travel_mode",
    "waypoints",
    "include_steps",
}
_VALID_TRAVEL_MODES = {"DRIVE", "BICYCLE", "WALK", "TRANSIT", "TWO_WHEELER"}


def _choice(options: set[str]) -> str:
    return sorted(options)[0]


def _golden_calls(expected: dict) -> list[dict]:
    calls = []
    for route in expected["routes"]:
        args = {
            "origin": _choice(route["origin"]),
            "destination": _choice(route["destination"]),
            "travel_mode": route["travel_mode"],
            "include_steps": route["include_steps"],
        }
        if "waypoints" in route:
            args["waypoints"] = [_choice(options) for options in route["waypoints"]]
        calls.append({"name": "compute_route", "args": args})
    return calls


def test_transportation_dataset_has_40_unique_well_formed_cases():
    assert DATASET_VERSION == "1.0.0"
    assert len(DATASET) == DATASET_SIZE == 40
    assert len({case["name"] for case in DATASET}) == DATASET_SIZE
    assert len({case["query"] for case in DATASET}) == DATASET_SIZE

    for case in DATASET:
        assert set(case) == {"name", "tags", "query", "expected"}
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case["name"])
        assert case["tags"] and len(case["tags"]) == len(set(case["tags"]))
        assert case["query"].strip()

        expected = case["expected"]
        assert expected.keys() <= _EXPECTED_KEYS
        assert expected["routes"]
        if "min_route_calls" in expected:
            assert expected["min_route_calls"] >= len(expected["routes"])

        for route in expected["routes"]:
            assert {
                "origin",
                "destination",
                "travel_mode",
                "include_steps",
            } <= route.keys()
            assert route.keys() <= _ROUTE_KEYS
            assert isinstance(route["origin"], set) and route["origin"]
            assert isinstance(route["destination"], set) and route["destination"]
            assert all(isinstance(value, str) and value for value in route["origin"])
            assert all(
                isinstance(value, str) and value for value in route["destination"]
            )
            assert route["travel_mode"] in _VALID_TRAVEL_MODES
            assert route["include_steps"] is True
            for waypoint_options in route.get("waypoints", []):
                assert isinstance(waypoint_options, set) and waypoint_options


def test_transportation_dataset_preserves_decision_coverage_floors():
    tags = Counter(tag for case in DATASET for tag in case["tags"])
    modes = {
        route["travel_mode"] for case in DATASET for route in case["expected"]["routes"]
    }

    assert modes == _VALID_TRAVEL_MODES
    assert tags["airport-transfer"] >= 12
    assert tags["waypoints"] >= 3
    assert tags["comparison"] >= 2
    assert tags["correction"] >= 3
    assert tags["multilingual"] >= 4
    assert tags["disambiguation"] >= 3


def test_every_transportation_golden_call_satisfies_its_evaluator_contract():
    failures = []
    for case in DATASET:
        calls = _golden_calls(case["expected"])
        for evaluator in EVALUATORS:
            result = evaluator(calls, case["expected"])
            if result["score"] == 0:
                failures.append(f"{case['name']}/{result['key']}: {result['comment']}")

    assert not failures, failures


def test_correct_route_pairs_requires_every_comparison_destination():
    expected = {
        "routes": [
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Colosseum"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            },
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Vatican Museums"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            },
        ]
    }
    calls = _golden_calls({"routes": [expected["routes"][0]]})

    result = correct_route_pairs(calls, expected)

    assert result["score"] == 0
    assert "vatican" in result["comment"].lower()


def test_route_pair_matching_preserves_unicode_punctuation_boundaries():
    expected = {
        "routes": [
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Fiumicino Airport"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            }
        ]
    }
    calls = [
        {
            "name": "compute_route",
            "args": {
                "origin": "Hotel Artemide, Rome, Italy",
                "destination": "Leonardo da Vinci–Fiumicino Airport, Italy",
                "travel_mode": "TRANSIT",
                "include_steps": True,
            },
        }
    ]

    assert correct_route_pairs(calls, expected)["score"] == 1


def test_correct_travel_modes_rejects_non_matching_mode():
    expected = {
        "routes": [
            {
                "origin": {"FCO Airport"},
                "destination": {"Hotel Artemide"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    calls[0]["args"]["travel_mode"] = "DRIVE"

    result = correct_travel_modes(calls, expected)

    assert result["score"] == 0
    assert "DRIVE" in result["comment"]


def test_correct_travel_modes_rejects_speculative_alternate_mode_call():
    expected = {
        "routes": [
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Colosseum"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    calls.append(
        {
            "name": "compute_route",
            "args": {
                "origin": "Hotel Artemide",
                "destination": "Colosseum",
                "travel_mode": "WALK",
                "include_steps": True,
            },
        }
    )

    result = correct_travel_modes(calls, expected)

    assert result["score"] == 0
    assert "WALK" in result["comment"]


def test_no_unrequested_route_pairs_rejects_substituted_endpoint():
    expected = {
        "routes": [
            {
                "origin": {"Tokyo Station"},
                "destination": {"Senso ji"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    calls.append(
        {
            "name": "compute_route",
            "args": {
                "origin": "Tokyo Station",
                "destination": "Asakusa Station",
                "travel_mode": "TRANSIT",
                "include_steps": True,
            },
        }
    )

    result = no_unrequested_route_pairs(calls, expected)

    assert result["score"] == 0
    assert "Asakusa Station" in result["comment"]


def test_valid_travel_modes_rejects_natural_language_mode():
    calls = [
        {
            "name": "compute_route",
            "args": {"origin": "A", "destination": "B", "travel_mode": "TRAIN"},
        }
    ]

    result = valid_travel_modes(calls, {"routes": []})

    assert result["score"] == 0
    assert "TRAIN" in result["comment"]


def test_correct_waypoints_accepts_reordered_intermediate_stops():
    expected = {
        "routes": [
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Trastevere"},
                "travel_mode": "WALK",
                "waypoints": [{"Piazza Navona"}, {"Pantheon"}],
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    calls[0]["args"]["waypoints"] = ["Pantheon", "Piazza Navona"]

    assert correct_waypoints(calls, expected)["score"] == 1


def test_correct_waypoints_rejects_a_retry_that_drops_requested_stops():
    expected = {
        "routes": [
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Trastevere"},
                "travel_mode": "WALK",
                "waypoints": [{"Piazza Navona"}, {"Pantheon"}],
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    calls.append(
        {
            "name": "compute_route",
            "args": {
                "origin": "Hotel Artemide",
                "destination": "Trastevere",
                "travel_mode": "WALK",
            },
        }
    )

    result = correct_waypoints(calls, expected)

    assert result["score"] == 0
    assert "did not preserve waypoint" in result["comment"]


def test_non_transit_multistop_policy_rejects_duplicate_leg_calls():
    expected = {
        "routes": [
            {
                "origin": {"A"},
                "destination": {"D"},
                "travel_mode": "WALK",
                "waypoints": [{"B"}, {"C"}],
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    for origin, destination in (("A", "B"), ("B", "C"), ("C", "D")):
        calls.append(
            {
                "name": "compute_route",
                "args": {
                    "origin": origin,
                    "destination": destination,
                    "travel_mode": "WALK",
                    "include_steps": True,
                },
            }
        )

    result = no_unrequested_route_pairs(calls, expected)

    assert result["score"] == 0
    assert "unrequested route" in result["comment"]


def test_transit_multistop_policy_accepts_only_consecutive_requested_legs():
    expected = {
        "routes": [
            {
                "origin": {"A"},
                "destination": {"B"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            },
            {
                "origin": {"B"},
                "destination": {"C"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            },
            {
                "origin": {"C"},
                "destination": {"D"},
                "travel_mode": "TRANSIT",
                "include_steps": True,
            },
        ]
    }
    calls = _golden_calls(expected)

    failures = [
        result
        for evaluator in EVALUATORS
        if (result := evaluator(calls, expected))["score"] == 0
    ]

    assert failures == []


def test_no_unrequested_waypoints_rejects_an_invented_stop():
    expected = {
        "routes": [
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Colosseum"},
                "travel_mode": "WALK",
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    calls[0]["args"]["waypoints"] = ["Trevi Fountain"]

    result = no_unrequested_waypoints(calls, expected)

    assert result["score"] == 0
    assert "Trevi Fountain" in result["comment"]


def test_correct_include_steps_accepts_the_tool_default():
    expected = {
        "routes": [
            {
                "origin": {"Hotel Artemide"},
                "destination": {"Colosseum"},
                "travel_mode": "WALK",
                "include_steps": True,
            }
        ]
    }
    calls = _golden_calls(expected)
    calls[0]["args"].pop("include_steps")

    assert correct_include_steps(calls, expected)["score"] == 1


def test_classify_transportation_outcome_completed():
    trajectory = Trajectory(
        query="route",
        tool_outputs=[
            (
                "compute_route",
                "Route: FCO Airport -> Hotel Artemide\nDistance: 31.4 km\nDuration: 3120s\nMode: TRANSIT",
            )
        ],
        final_text="Take transit.",
    )

    assert classify_transportation_outcome(trajectory) == "completed"


def test_classify_transportation_outcome_no_route():
    trajectory = Trajectory(
        query="route",
        tool_outputs=[("compute_route", "No route found.")],
        final_text="No route was returned.",
    )

    assert classify_transportation_outcome(trajectory) == "no_route"


def test_classify_transportation_outcome_blocked_external():
    trajectory = Trajectory(
        query="route",
        tool_outputs=[("compute_route", "Routes API error (HTTP 429).")],
        final_text="Provider rate limited.",
    )

    assert classify_transportation_outcome(trajectory) == "blocked_external"


def test_classify_invalid_route_request_as_agent_or_result_failure():
    trajectory = Trajectory(
        query="route",
        tool_outputs=[("compute_route", "Routes API error (HTTP 400).")],
        final_text="The requested route failed.",
    )

    assert classify_transportation_outcome(trajectory) == "failed"


def test_classify_missing_api_key_as_blocked_external():
    trajectory = Trajectory(
        query="route",
        error="RuntimeError: GOOGLE_MAPS_API_KEY environment variable is not set",
    )

    assert classify_transportation_outcome(trajectory) == "blocked_external"


def test_transportation_trajectory_cache_roundtrip(tmp_path):
    path = tmp_path / "trajectories.json"
    queries = ["route from A to B"]
    original = [
        Trajectory(
            query=queries[0],
            tool_calls=[
                {
                    "name": "compute_route",
                    "args": {"origin": "A", "destination": "B"},
                }
            ],
            tool_outputs=[("compute_route", "Route: A -> B")],
            final_text="Route A to B",
        )
    ]

    _save_trajectories(path, queries, original)
    loaded = _load_trajectories(path, queries)

    assert loaded == original
    assert loaded[0].tool_outputs == [("compute_route", "Route: A -> B")]


def test_transportation_trajectory_cache_redacts_api_keys(tmp_path, monkeypatch):
    path = tmp_path / "trajectories.json"
    secret = "configured-google-key"
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", secret)
    trajectory = Trajectory(
        query="route",
        tool_outputs=[
            (
                "compute_route",
                f"Route preview: https://maps.example/route?key={secret}",
            )
        ],
        final_text=f"[Route](https://maps.example/route?key={secret})",
    )

    _save_trajectories(path, [trajectory.query], [trajectory])
    payload = path.read_text(encoding="utf-8")
    loaded = _load_trajectories(path, [trajectory.query])

    assert secret not in payload
    assert payload.count("<REDACTED>") == 2
    assert loaded is not None
    assert secret not in loaded[0].tool_outputs[0][1]
    assert secret not in loaded[0].final_text


def test_judge_cases_are_balanced_and_held_out():
    labels = Counter(case["expected"] for case in JUDGE_CASES)

    assert len(JUDGE_CASES) == 28
    assert len({case["name"] for case in JUDGE_CASES}) == 28
    assert labels == {0: 7, 1: 7, 2: 7, 3: 7}
    assert "Southern Cross Station" in FAITHFULNESS_RUBRIC
    assert all("Southern Cross" not in case["trajectory"].query for case in JUDGE_CASES)


def test_judge_cases_cover_unsupported_transportation_contract_claims():
    contract_cases = {
        case["name"]: case for case in JUDGE_CASES if "operational" in case["name"]
    }

    assert set(contract_cases) == {
        "operational-limitations-grounded",
        "invented-operational-contract",
        "no-route-invented-operational-contract",
    }
    assert {case["expected"] for case in contract_cases.values()} == {0, 1, 3}
    assert "waiting-time buffer" in next(
        case["note"]
        for case in JUDGE_CASES
        if case["name"] == "soft-unverified-waiting-buffer"
    )


async def test_pairwise_skips_provider_blocked_arm():
    blocked = Trajectory(
        query="route",
        tool_outputs=[("compute_route", "Routes API error (HTTP 403).")],
        final_text="Provider error",
    )
    completed = Trajectory(
        query="route",
        tool_outputs=[("compute_route", "Route: A -> B\nMode: TRANSIT")],
        final_text="Take transit.",
    )

    result = await judge_pairwise(None, blocked, completed)

    assert result["winner"] is None
    assert "excluded" in result["comment"]


def test_transportation_pairwise_rubric_requires_material_difference():
    assert "MATERIAL-DIFFERENCE RULE" in HELPFULNESS_PAIRWISE_RUBRIC
    assert "Return `tie` when advantages are minor or offsetting" in (
        HELPFULNESS_PAIRWISE_RUBRIC
    )
