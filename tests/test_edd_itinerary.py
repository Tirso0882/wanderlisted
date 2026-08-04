"""Itinerary EDD Layer-1 gate and live-spend control contracts."""

from collections import Counter

import pytest

from edd.itinerary.l1_dataset import DATASET, DATASET_SIZE, DATASET_VERSION
from edd.itinerary.l1_evaluate import evaluate_report
from edd.itinerary.l1_observe import observe_case
from edd.itinerary.run_utils import (
    load_cached_itinerary_trajectories,
    require_judge_approval,
)


def test_itinerary_dataset_has_16_unique_well_formed_cases():
    assert DATASET_VERSION == "1.0.0"
    assert len(DATASET) == DATASET_SIZE == 16
    assert len({case["name"] for case in DATASET}) == 16
    assert len({case["query"] for case in DATASET}) == 16
    assert all(
        set(case) == {"name", "tags", "query", "scenario", "expected"}
        for case in DATASET
    )


def test_itinerary_dataset_has_four_cases_per_risk_family():
    tags = Counter(tag for case in DATASET for tag in case["tags"])
    assert tags["artifact_consumption"] == 4
    assert tags["date_consistency"] == 4
    assert tags["feasibility"] == 4
    assert tags["hallucination_resistance"] == 4


def test_all_itinerary_layer1_cases_pass_offline():
    failures = []
    for case in DATASET:
        report = observe_case(case)
        failures.extend(
            f"{case['name']}/{check['key']}"
            for check in evaluate_report(report, case["expected"])
            if not check["passed"]
        )
    assert failures == []


def test_itinerary_cache_miss_never_captures_live(tmp_path, monkeypatch):
    monkeypatch.setenv("EDD_ITINERARY_CACHE_DIR", str(tmp_path))
    with pytest.raises(
        FileNotFoundError, match="Live capture is intentionally disabled"
    ):
        load_cached_itinerary_trajectories(["case"], model_config={"tier": "fast"})


def test_itinerary_refresh_and_judge_spend_require_explicit_approval(monkeypatch):
    monkeypatch.setenv("EDD_REFRESH", "1")
    with pytest.raises(RuntimeError, match="live refresh is disabled"):
        load_cached_itinerary_trajectories(["case"], model_config={"tier": "fast"})
    with pytest.raises(RuntimeError, match="live refresh is disabled"):
        require_judge_approval(layer="Layer 4", estimated_calls=8)

    monkeypatch.delenv("EDD_REFRESH")
    monkeypatch.delenv("EDD_LIVE_JUDGE_APPROVED", raising=False)
    with pytest.raises(RuntimeError, match="approximately 32 judge-model calls"):
        require_judge_approval(layer="Layer 2", estimated_calls=32)
