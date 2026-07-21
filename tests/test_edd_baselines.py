"""Shared EDD baseline-store regression tests."""

from __future__ import annotations

import json

import pytest

from edd.baseline_store import (
    BaselineConfig,
    BaselineConflictError,
    load_trajectories,
    preserve_baseline_run,
    record_baseline_report,
    record_component_report,
    run_fingerprint,
    save_trajectories,
)
from edd.baseline_config import BASELINE_CONFIGS, get_baseline_config
from edd.compare_baselines import collect_component_rows, render_component_comparison
from edd.calibration import run_calibration
from edd.harness import Trajectory


def _config(tmp_path, source_file) -> BaselineConfig:
    return BaselineConfig(
        component="test_agent",
        dataset_version="1.2.3",
        source_files=(source_file,),
        cache_env_var="EDD_TEST_AGENT_CACHE_DIR",
        default_cache_dir=tmp_path / ".cache",
        secret_env_vars=("TEST_PROVIDER_KEY",),
        display_name="Test agent",
    )


def test_shared_registry_covers_every_component_with_complete_configuration():
    assert set(BASELINE_CONFIGS) == {
        "flights",
        "hotels",
        "restaurants",
        "activities",
        "transportation",
    }
    for component, config in BASELINE_CONFIGS.items():
        assert get_baseline_config(component) is config
        assert config.dataset_version
        assert config.cache_env_var.startswith("EDD_")
        assert config.source_files
        assert all(source.is_file() for source in config.source_files)


def test_cache_roundtrip_uses_shared_redaction(tmp_path, monkeypatch):
    source_file = tmp_path / "agent.py"
    source_file.write_text("PROMPT = 'test'\n", encoding="utf-8")
    config = _config(tmp_path, source_file)
    secret = "provider-secret"
    monkeypatch.setenv("TEST_PROVIDER_KEY", secret)
    path = tmp_path / ".cache" / "trajectories.json"
    trajectories = [
        Trajectory(
            query="test",
            tool_outputs=[("tool", f"https://example.test/result?key={secret}")],
            final_text=f"credential={secret}",
        )
    ]

    save_trajectories(path, config, ["test"], trajectories)
    loaded = load_trajectories(path, ["test"])

    assert secret not in path.read_text(encoding="utf-8")
    assert loaded is not None
    assert loaded[0].tool_outputs[0][1].endswith("key=<REDACTED>")
    assert loaded[0].final_text == "credential=<REDACTED>"


def test_run_fingerprint_changes_with_behavior_source(tmp_path):
    source_file = tmp_path / "agent.py"
    source_file.write_text("PROMPT = 'first'\n", encoding="utf-8")
    config = _config(tmp_path, source_file)
    first = run_fingerprint(config, ["query"], {"tier": "fast"})

    source_file.write_text("PROMPT = 'second'\n", encoding="utf-8")
    second = run_fingerprint(config, ["query"], {"tier": "fast"})

    assert first != second


def test_named_baseline_preserves_provenance_and_is_idempotent(tmp_path, monkeypatch):
    source_file = tmp_path / "agent.py"
    source_file.write_text("PROMPT = 'test'\n", encoding="utf-8")
    config = _config(tmp_path, source_file)
    monkeypatch.setenv("EDD_BASELINE", "release-candidate-1")
    monkeypatch.setenv("EDD_BASELINE_DIR", str(tmp_path / "baselines"))
    trajectories = [Trajectory(query="query", final_text="answer")]

    first = preserve_baseline_run(
        config,
        ["query"],
        {"tier": "fast", "api_key": "must-not-persist"},
        trajectories,
    )
    second = preserve_baseline_run(
        config,
        ["query"],
        {"tier": "fast", "api_key": "must-not-persist"},
        trajectories,
    )

    assert first is not None
    assert second == first
    manifest = json.loads((first.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_version"] == "1.2.3"
    assert manifest["dataset_case_count"] == 1
    assert manifest["model_config"]["api_key"] == "<REDACTED>"
    assert manifest["sources"]
    assert manifest["trajectories_sha256"]


def test_named_baseline_detects_tampered_trajectory_bundle(tmp_path, monkeypatch):
    source_file = tmp_path / "agent.py"
    source_file.write_text("PROMPT = 'test'\n", encoding="utf-8")
    config = _config(tmp_path, source_file)
    monkeypatch.setenv("EDD_BASELINE", "tamper-test")
    monkeypatch.setenv("EDD_BASELINE_DIR", str(tmp_path / "baselines"))
    trajectories = [Trajectory(query="query", final_text="answer")]
    preserved = preserve_baseline_run(config, ["query"], {"tier": "fast"}, trajectories)
    assert preserved is not None
    trajectory_file = preserved.path / "trajectories.json"
    trajectory_file.chmod(0o644)
    trajectory_file.write_text("{}\n", encoding="utf-8")

    with pytest.raises(BaselineConflictError, match="conflicts"):
        preserve_baseline_run(config, ["query"], {"tier": "fast"}, trajectories)


def test_metrics_report_is_append_once_for_same_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("EDD_BASELINE", "metrics-test")
    monkeypatch.setenv("EDD_BASELINE_DIR", str(tmp_path / "baselines"))
    context = {"dataset_version": "1.0.0", "model": "terra"}

    first = record_baseline_report(
        component="transportation",
        layer="l1",
        metrics={"decision_accuracy": 0.85},
        run_refs={"terra": "abc123"},
        context=context,
    )
    second = record_baseline_report(
        component="transportation",
        layer="l1",
        metrics={"decision_accuracy": 0.85},
        run_refs={"terra": "abc123"},
        context=context,
    )

    assert first == second
    with pytest.raises(BaselineConflictError, match="different metrics"):
        record_baseline_report(
            component="transportation",
            layer="l1",
            metrics={"decision_accuracy": 0.90},
            run_refs={"terra": "abc123"},
            context=context,
        )


def test_component_report_links_metrics_to_exact_model_run(tmp_path, monkeypatch):
    source_file = tmp_path / "agent.py"
    source_file.write_text("PROMPT = 'test'\n", encoding="utf-8")
    config = _config(tmp_path, source_file)
    monkeypatch.setenv("EDD_BASELINE", "linked-report")
    monkeypatch.setenv("EDD_BASELINE_DIR", str(tmp_path / "baselines"))
    model_config = {"tier": "fast", "azure_deployment": "test-model"}
    preserve_baseline_run(
        config,
        ["query"],
        model_config,
        [Trajectory(query="query", final_text="answer")],
    )

    report_path = record_component_report(
        config,
        layer="l2",
        metrics={"faithfulness": {"mean": 2.5, "scored": 4}},
        queries=["query"],
        model_configs={"terra": model_config},
        report_source_files=(source_file,),
    )

    assert report_path is not None
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["run_refs"] == {
        "terra": run_fingerprint(config, ["query"], model_config)
    }
    assert report["context"]["dataset_version"] == "1.2.3"
    assert report["context"]["model_configs"]["terra"] == model_config
    assert report["context"]["report_sources"][0]["sha256"]
    assert report["git"]["commit"]
    assert report["metrics_sha256"]


async def test_calibration_automatically_records_layer4_report(tmp_path, monkeypatch):
    monkeypatch.setenv("EDD_BASELINE", "calibration-test")
    monkeypatch.setenv("EDD_BASELINE_DIR", str(tmp_path / "baselines"))
    cases = [
        {
            "name": f"score-{score}",
            "expected": score,
            "trajectory": Trajectory(query="test", final_text=str(score)),
        }
        for score in range(4)
    ]

    async def fake_faithfulness(_judge, trajectory):
        return {
            "key": "faithfulness",
            "score": int(trajectory.final_text),
            "comment": "fixed test verdict",
        }

    metrics = await run_calibration(
        build_judge=lambda: object(),
        judge_faithfulness=fake_faithfulness,
        cases=cases,
        agent="Transportation",
        rubric_module="edd/transportation/l2_judge.py",
    )

    reports = list(
        (
            tmp_path / "baselines" / "transportation" / "calibration-test" / "reports"
        ).glob("l4-*.json")
    )
    assert metrics["exact"] == 1.0
    assert len(reports) == 1
    payload = json.loads(reports[0].read_text(encoding="utf-8"))
    assert payload["metrics"]["kappa"] == 1.0
    assert len(payload["metrics"]["case_results"]) == 4
    assert payload["context"]["calibration_cases_sha256"]


def test_baseline_comparison_renders_l1_l2_deltas(tmp_path):
    baseline_root = tmp_path / "baselines"

    def write_report(
        baseline_name,
        layer,
        report_id,
        run_id,
        metrics,
        created_at,
    ):
        report_path = (
            baseline_root
            / "transportation"
            / baseline_name
            / "reports"
            / f"{layer}-{report_id}.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "baseline_name": baseline_name,
                    "component": "transportation",
                    "context": {"dataset_case_count": 10},
                    "created_at": created_at,
                    "layer": layer,
                    "metrics": metrics,
                    "report_id": report_id,
                    "run_refs": {"terra": run_id},
                }
            ),
            encoding="utf-8",
        )

    before_l1 = {
        "decision_accuracy": {"passed": 7, "scored": 10, "rate": 0.7},
        "per_check": {
            "correct_route_pairs": {"passed": 7, "scored": 10, "rate": 0.7},
            "correct_travel_modes": {"passed": 9, "scored": 10, "rate": 0.9},
        },
        "task_outcomes": {"completed": 8, "no_route": 2},
    }
    after_l1 = {
        "decision_accuracy": {"passed": 9, "scored": 10, "rate": 0.9},
        "per_check": {
            "correct_route_pairs": {"passed": 9, "scored": 10, "rate": 0.9},
            "correct_travel_modes": {"passed": 10, "scored": 10, "rate": 1.0},
        },
        "task_outcomes": {"completed": 9, "no_route": 1},
    }
    before_l2 = {
        "rubric_scores": {
            "faithfulness": {"mean": 1.0, "scored": 10},
            "helpfulness": {"mean": 2.0, "scored": 10},
        },
        "task_outcomes": {"completed": 8, "no_route": 2},
    }
    after_l2 = {
        "rubric_scores": {
            "faithfulness": {"mean": 2.0, "scored": 10},
            "helpfulness": {"mean": 2.2, "scored": 10},
        },
        "task_outcomes": {"completed": 9, "no_route": 1},
    }
    write_report(
        "before",
        "l1",
        "before-l1",
        "run-before",
        before_l1,
        "2026-07-20T00:00:00+00:00",
    )
    write_report(
        "before",
        "l2",
        "before-l2",
        "run-before",
        before_l2,
        "2026-07-20T00:00:01+00:00",
    )
    write_report(
        "after", "l1", "after-l1", "run-after", after_l1, "2026-07-21T00:00:00+00:00"
    )
    write_report(
        "after", "l2", "after-l2", "run-after", after_l2, "2026-07-21T00:00:01+00:00"
    )

    rows, warnings = collect_component_rows(
        baseline_root,
        "transportation",
        ["before", "after"],
    )
    output = render_component_comparison("transportation", rows)

    assert warnings == []
    assert "90.0% (9/10)" in output
    assert "+20.00 pp" in output
    assert "+1.00 pts" in output
    assert "L1 lowest check: correct_route_pairs at 90.0% (9/10)." in output
    assert "L2 lowest rubric: faithfulness at 2.00 (n=10)." in output
