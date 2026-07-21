"""Focused unit tests for Hotels EDD data, evaluators, and evidence handling."""

from collections import Counter
from datetime import date
import re

from edd.harness import Trajectory
from edd.hotels.l1_dataset import DATASET, DATASET_SIZE, DATASET_VERSION
from edd.hotels.l1_evaluate import (
    EVALUATORS,
    correct_board,
    correct_budget,
    correct_city,
    correct_dates,
    correct_guests,
    correct_stars,
    no_unrequested_filters,
    required_rechecks_completed,
)
from edd.hotels.l3_pairwise import judge_pairwise
from edd.hotels.run_utils import (
    _load_trajectories,
    _save_trajectories,
    classify_hotel_outcome,
)
from edd.rubrics import _format_evidence

_EXPECTED_KEYS = {
    "city",
    "check_in",
    "check_out",
    "adults",
    "children",
    "children_ages",
    "min_category",
    "board",
    "max_rate",
}
_REQUIRED_EXPECTED_KEYS = {"city", "check_in", "check_out", "adults", "children"}
_BOARD_CODES = {"AI", "BB", "FB", "HB", "RO"}


def _golden_search_call(expected: dict) -> list[dict]:
    return [
        {
            "name": "search_hotels_hotelbeds",
            "args": {
                "city_code": expected["city"],
                "check_in_date": expected["check_in"],
                "check_out_date": expected["check_out"],
                "adults": expected["adults"],
                "children": expected["children"],
                "children_ages": ",".join(
                    str(age) for age in expected.get("children_ages", [])
                ),
                "min_category": expected.get("min_category"),
                "max_rate": expected.get("max_rate"),
                "board_codes": expected.get("board", ""),
            },
        }
    ]


def test_hotels_dataset_has_40_unique_well_formed_cases():
    assert DATASET_VERSION == "2.0.0"
    assert len(DATASET) == DATASET_SIZE == 40
    assert len({case["name"] for case in DATASET}) == DATASET_SIZE
    assert len({case["query"] for case in DATASET}) == DATASET_SIZE

    for case in DATASET:
        assert set(case) == {"name", "tags", "query", "expected"}
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", case["name"])
        assert case["tags"] and len(case["tags"]) == len(set(case["tags"]))
        assert case["query"].strip()

        expected = case["expected"]
        assert _REQUIRED_EXPECTED_KEYS <= expected.keys(), case["name"]
        assert expected.keys() <= _EXPECTED_KEYS, case["name"]
        assert re.fullmatch(r"[A-Z]{3}", expected["city"]), case["name"]

        check_in = date.fromisoformat(expected["check_in"])
        check_out = date.fromisoformat(expected["check_out"])
        assert check_out > check_in, case["name"]
        assert expected["adults"] >= 1, case["name"]
        assert expected["children"] >= 0, case["name"]

        ages = expected.get("children_ages", [])
        assert len(ages) == expected["children"], case["name"]
        assert all(0 <= age <= 17 for age in ages), case["name"]
        if expected["children"] == 0:
            assert "children_ages" not in expected, case["name"]
        if "min_category" in expected:
            assert 1 <= expected["min_category"] <= 5, case["name"]
        if "board" in expected:
            assert expected["board"] in _BOARD_CODES, case["name"]
        if "max_rate" in expected:
            assert expected["max_rate"] > 0, case["name"]


def test_hotels_dataset_preserves_stress_coverage_floors():
    expected = [case["expected"] for case in DATASET]
    tags = Counter(tag for case in DATASET for tag in case["tags"])

    assert sum("min_category" in item for item in expected) >= 5
    assert sum("board" in item for item in expected) >= 8
    assert {item["board"] for item in expected if "board" in item} == _BOARD_CODES
    assert sum("max_rate" in item for item in expected) >= 7
    assert sum(item["children"] > 0 for item in expected) >= 7
    assert tags["correction"] >= 5
    assert tags["geography"] >= 11
    assert tags["date-reasoning"] >= 5
    assert tags["multilingual"] >= 2
    assert tags["context-resistance"] >= 2


def test_every_hotels_golden_call_satisfies_its_evaluator_contract():
    failures = []
    for case in DATASET:
        calls = _golden_search_call(case["expected"])
        for evaluator in EVALUATORS:
            result = evaluator(calls, case["expected"])
            if result["score"] == 0:
                failures.append(
                    f"{case['name']}/{result['key']}: {result['comment']}"
                )

    assert not failures, failures


def test_all_search_calls_must_preserve_every_requested_constraint():
    expected = {
        "city": "PAR",
        "check_in": "2027-02-08",
        "check_out": "2027-02-12",
        "adults": 2,
        "children": 0,
        "min_category": 4,
        "board": "BB",
        "max_rate": 800,
    }
    good = _golden_search_call(expected)[0]
    bad = {
        "name": "search_hotels_hotelbeds",
        "args": {
            **good["args"],
            "city_code": "LON",
            "check_in_date": "2027-02-09",
            "adults": 1,
            "children": 1,
            "children_ages": "6",
            "min_category": 5,
            "board_codes": "BB,AI",
            "max_rate": 700,
        },
    }

    for evaluator in (
        correct_city,
        correct_dates,
        correct_guests,
        correct_stars,
        correct_board,
        correct_budget,
    ):
        result = evaluator([good, bad], expected)
        assert result["score"] == 0, evaluator.__name__
        assert "search #2" in result["comment"], evaluator.__name__


def test_no_unrequested_filters_rejects_restrictive_inventions():
    expected = {
        "city": "SIN",
        "check_in": "2027-06-15",
        "check_out": "2027-06-18",
        "adults": 1,
        "children": 0,
    }
    call = _golden_search_call(expected)[0]
    call["args"].update(
        {"min_category": 4, "board_codes": "BB", "max_rate": 500}
    )

    result = no_unrequested_filters([call], expected)

    assert result["score"] == 0
    assert "unrequested min_category=4" in result["comment"]
    assert "unrequested board_codes=['BB']" in result["comment"]
    assert "unrequested max_rate=500" in result["comment"]


def test_correct_guests_rejects_wrong_child_ages():
    calls = [
        {
            "name": "search_hotels_hotelbeds",
            "args": {"adults": 2, "children": 2, "children_ages": "1,1"},
        }
    ]
    expected = {"adults": 2, "children": 2, "children_ages": [4, 9]}

    result = correct_guests(calls, expected)

    assert result["score"] == 0
    assert "expected [4, 9]" in result["comment"]


def test_correct_guests_accepts_equivalent_child_age_order():
    calls = [
        {
            "name": "search_hotels_hotelbeds",
            "args": {"adults": 2, "children": 2, "children_ages": "9,4"},
        }
    ]
    expected = {"adults": 2, "children": 2, "children_ages": [4, 9]}

    assert correct_guests(calls, expected)["score"] == 1


def test_required_rechecks_completed_skips_without_recheck_rates():
    trajectory = Trajectory(
        query="hotel",
        tool_outputs=[
            (
                "search_hotels_hotelbeds",
                "Rate type: BOOKABLE\nRate key: BOOKABLE-1",
            )
        ],
    )

    assert required_rechecks_completed(trajectory)["score"] is None


def test_required_rechecks_completed_fails_for_missing_rate_key():
    trajectory = Trajectory(
        query="hotel",
        tool_outputs=[
            (
                "search_hotels_hotelbeds",
                "Rate type: RECHECK\nRate key: RECHECK-1",
            )
        ],
    )

    result = required_rechecks_completed(trajectory)

    assert result["score"] == 0
    assert "RECHECK-1" in result["comment"]


def test_required_rechecks_completed_accepts_batched_rate_keys():
    trajectory = Trajectory(
        query="hotel",
        tool_calls=[
            {
                "name": "check_hotel_rate_hotelbeds",
                "args": {"rate_keys": "RECHECK-1|||RECHECK-2"},
            }
        ],
        tool_outputs=[
            (
                "search_hotels_hotelbeds",
                "Rate type: RECHECK\nRate key: RECHECK-1\n"
                "Rate type: RECHECK\nRate key: RECHECK-2",
            )
        ],
    )

    assert required_rechecks_completed(trajectory)["score"] == 1


def test_format_evidence_keeps_late_hotel_and_later_tool_output():
    hotelbeds = "A" * 7_200 + "Hotel George Washington" + "B" * 1_000
    places = "Rating: 4.4 https://example.com/photo/" + "x" * 2_000
    trajectory = Trajectory(
        query="hotel",
        tool_outputs=[
            ("search_hotels_hotelbeds", hotelbeds),
            ("search_places_text", places),
        ],
    )

    evidence = _format_evidence(trajectory)

    assert "Hotel George Washington" in evidence
    assert "[search_places_text]" in evidence
    assert "Rating: 4.4" in evidence
    assert "<URL>" in evidence
    assert "https://example.com" not in evidence


def test_classify_hotel_outcome_completed():
    trajectory = Trajectory(
        query="hotel",
        tool_outputs=[("search_hotels_hotelbeds", "Hotels from Hotelbeds in PAR")],
        final_text="Hotel option",
    )

    assert classify_hotel_outcome(trajectory) == "completed"


def test_classify_hotel_outcome_no_inventory():
    trajectory = Trajectory(
        query="hotel",
        tool_outputs=[
            ("search_hotels_hotelbeds", "No hotel offers found on Hotelbeds in PAR")
        ],
        final_text="No inventory was returned.",
    )

    assert classify_hotel_outcome(trajectory) == "no_inventory"


def test_classify_hotel_outcome_blocked_external():
    trajectory = Trajectory(
        query="hotel",
        tool_outputs=[
            (
                "search_hotels_hotelbeds",
                "Hotelbeds API error (HTTP 403): Quota exceeded.",
            )
        ],
        final_text="The provider quota is exhausted.",
    )

    assert classify_hotel_outcome(trajectory) == "blocked_external"


def test_trajectory_cache_roundtrip(tmp_path):
    path = tmp_path / "trajectories.json"
    queries = ["hotel in Paris"]
    original = [
        Trajectory(
            query=queries[0],
            tool_calls=[{"name": "search_hotels_hotelbeds", "args": {}}],
            tool_outputs=[("search_hotels_hotelbeds", "Hotel result")],
            final_text="Hotel answer",
        )
    ]

    _save_trajectories(path, queries, original)
    loaded = _load_trajectories(path, queries)

    assert loaded == original
    assert loaded[0].tool_outputs == [("search_hotels_hotelbeds", "Hotel result")]


async def test_pairwise_skips_provider_blocked_arm():
    blocked = Trajectory(
        query="hotel",
        tool_outputs=[
            (
                "search_hotels_hotelbeds",
                "Hotelbeds API error (HTTP 403): Quota exceeded.",
            )
        ],
        final_text="Provider quota exceeded.",
    )
    completed = Trajectory(
        query="hotel",
        tool_outputs=[("search_hotels_hotelbeds", "Hotel result")],
        final_text="Hotel option",
    )

    result = await judge_pairwise(None, blocked, completed)

    assert result["winner"] is None
    assert "provider blocked" in result["comment"]
