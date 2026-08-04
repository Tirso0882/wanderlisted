"""Committed zero-call specialist baseline contracts."""

import json

import pytest

import edd.offline_baselines as offline
from edd.baseline_config import BASELINE_CONFIGS


def test_current_offline_baseline_covers_every_specialist_and_is_fresh():
    paths = offline.verify_offline_baselines()

    assert len(paths) == len(BASELINE_CONFIGS) == 8
    assert {path.parts[-3] for path in paths} == set(BASELINE_CONFIGS)


def test_offline_manifests_do_not_claim_live_model_quality():
    for path in offline.verify_offline_baselines():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        assert manifest["external_calls"] == 0
        assert manifest["cache_status"] == "not_used"
        assert manifest["model_quality_claim"] is False
        assert manifest["metrics"]["contract_tests_failed"] == 0
        if manifest["component"] in {"budget", "itinerary"}:
            assert manifest["evidence_kind"] == "deterministic_pipeline"
            assert manifest["metrics"]["dataset_cases_passed"] == 16
        else:
            assert manifest["evidence_kind"] == "evaluator_contract_only"
            assert manifest["metrics"]["dataset_cases_passed"] is None


def test_offline_verifier_rejects_source_fingerprint_drift(monkeypatch):
    monkeypatch.setattr(
        offline,
        "_manifest_sources",
        lambda _component: [{"path": "changed.py", "sha256": "0" * 64}],
    )

    with pytest.raises(RuntimeError, match="sources"):
        offline.verify_offline_baselines()


@pytest.mark.parametrize("name", ["", "spaces are unsafe", "../escape"])
def test_offline_baseline_name_is_bounded_before_any_gate_runs(name):
    with pytest.raises(ValueError, match="baseline name"):
        offline.create_offline_baselines(name)
