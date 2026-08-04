"""Create and verify zero-call specialist contract baselines.

These artifacts pin deterministic evaluator/test evidence. They deliberately do
not claim model or live-provider quality; trajectory baselines remain separate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from edd.baseline_config import BASELINE_CONFIGS, get_baseline_config
from edd.baseline_store import BaselineConflictError, content_sha256, source_hashes


OFFLINE_BASELINE_SCHEMA_VERSION = 1
_ROOT = Path(__file__).resolve().parents[1]
_BASELINE_ROOT = _ROOT / "edd" / "baselines"
_INDEX_PATH = _BASELINE_ROOT / "offline-current.json"
_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
_PYTEST_FILES = {
    component: _ROOT / "tests" / f"test_edd_{component}.py"
    for component in BASELINE_CONFIGS
}
_DETERMINISTIC_RUNNERS = {
    "budget": "edd.budget.l1_run",
    "itinerary": "edd.itinerary.l1_run",
}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"offline baseline is unreadable: {path}") from exc


def _stable_payload(manifest: dict) -> dict:
    return {
        key: value
        for key, value in manifest.items()
        if key not in {"artifact_sha256", "created_at"}
    }


def _manifest_sources(component: str) -> list[dict[str, str]]:
    config = get_baseline_config(component)
    component_root = _ROOT / "edd" / component
    files = (
        Path(__file__).resolve(),
        _ROOT / "pyproject.toml",
        _ROOT / "uv.lock",
        _PYTEST_FILES[component],
        component_root / "l1_dataset.py",
        component_root / "l1_evaluate.py",
        *config.source_files,
    )
    return source_hashes(files)


def _run_command(arguments: Sequence[str]) -> str:
    environment = dict(os.environ)
    environment.update(
        {
            "EDD_REFRESH": "0",
            "EDD_LIVE_JUDGE_APPROVED": "0",
            "LANGCHAIN_TRACING_V2": "false",
            "LANGSMITH_TRACING": "false",
        }
    )
    result = subprocess.run(
        list(arguments),
        cwd=_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(
            f"offline baseline gate failed ({' '.join(arguments)}):\n{detail}"
        )
    return result.stdout


def _run_component_gates(component: str) -> dict:
    test_path = _PYTEST_FILES[component]
    pytest_output = _run_command((sys.executable, "-m", "pytest", str(test_path), "-q"))
    match = re.search(r"(?m)(\d+) passed(?:,| in)", pytest_output)
    if match is None:
        raise RuntimeError(f"could not read pytest pass count for {component}")

    metrics = {
        "contract_tests_passed": int(match.group(1)),
        "contract_tests_failed": 0,
        "dataset_cases_executed": None,
        "dataset_cases_passed": None,
    }
    commands = [f"python -m pytest tests/test_edd_{component}.py -q"]

    runner = _DETERMINISTIC_RUNNERS.get(component)
    if runner is not None:
        runner_output = _run_command((sys.executable, "-m", runner))
        runner_match = re.search(r"Layer 1: (\d+)/(\d+) cases passed", runner_output)
        if runner_match is None:
            raise RuntimeError(f"could not read Layer-1 result for {component}")
        passed, executed = map(int, runner_match.groups())
        if passed != executed:
            raise RuntimeError(
                f"{component} deterministic Layer 1 was not clean: {passed}/{executed}"
            )
        metrics.update(
            {
                "dataset_cases_executed": executed,
                "dataset_cases_passed": passed,
            }
        )
        commands.append(f"python -m {runner}")

    return {"commands": commands, "metrics": metrics}


def _write_manifest(component: str, baseline_name: str, gate: dict) -> Path:
    config = get_baseline_config(component)
    dataset = __import__(f"edd.{component}.l1_dataset", fromlist=["DATASET"]).DATASET
    evidence_kind = (
        "deterministic_pipeline"
        if component in _DETERMINISTIC_RUNNERS
        else "evaluator_contract_only"
    )
    manifest = {
        "schema_version": OFFLINE_BASELINE_SCHEMA_VERSION,
        "kind": "edd-offline-contract-baseline",
        "baseline_name": baseline_name,
        "component": component,
        "dataset_version": config.dataset_version,
        "dataset_case_count": len(dataset),
        "evidence_kind": evidence_kind,
        "model_quality_claim": False,
        "external_calls": 0,
        "cache_status": "not_used",
        "commands": gate["commands"],
        "metrics": gate["metrics"],
        "sources": _manifest_sources(component),
    }
    manifest["artifact_sha256"] = content_sha256(manifest)
    manifest["created_at"] = datetime.now(UTC).isoformat()
    path = _BASELINE_ROOT / component / baseline_name / "offline-contract.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = _read_json(path)
        if _stable_payload(existing) != _stable_payload(manifest):
            raise BaselineConflictError(
                f"immutable offline baseline conflicts with current evidence: {path}"
            )
        print(f"{component} offline baseline: EXISTS ({baseline_name})")
        return path
    with path.open("x", encoding="utf-8") as baseline_file:
        baseline_file.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"{component} offline baseline: SAVED ({baseline_name})")
    return path


def create_offline_baselines(baseline_name: str) -> list[Path]:
    """Run only hermetic gates and preserve one named baseline per specialist."""
    if not _NAME_RE.fullmatch(baseline_name):
        raise ValueError(
            "baseline name must be 1-80 letters, digits, dots, underscores, or hyphens"
        )
    paths = []
    for component in BASELINE_CONFIGS:
        paths.append(
            _write_manifest(
                component,
                baseline_name,
                _run_component_gates(component),
            )
        )
    index = {
        "schema_version": OFFLINE_BASELINE_SCHEMA_VERSION,
        "kind": "edd-offline-baseline-index",
        "baselines": {component: baseline_name for component in BASELINE_CONFIGS},
    }
    _INDEX_PATH.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return paths


def verify_offline_baselines() -> list[Path]:
    """Verify coverage, provenance, and zero-call/non-quality semantics."""
    index = _read_json(_INDEX_PATH)
    if index.get("kind") != "edd-offline-baseline-index":
        raise RuntimeError("invalid offline baseline index kind")
    baselines = index.get("baselines", {})
    if set(baselines) != set(BASELINE_CONFIGS):
        raise RuntimeError("offline baseline index must cover every specialist")

    verified = []
    for component in BASELINE_CONFIGS:
        baseline_name = baselines[component]
        path = _BASELINE_ROOT / component / baseline_name / "offline-contract.json"
        manifest = _read_json(path)
        stable = _stable_payload(manifest)
        expected_hash = content_sha256(stable)
        problems = []
        if manifest.get("kind") != "edd-offline-contract-baseline":
            problems.append("kind")
        if manifest.get("component") != component:
            problems.append("component")
        if manifest.get("baseline_name") != baseline_name:
            problems.append("baseline_name")
        if (
            manifest.get("dataset_version")
            != get_baseline_config(component).dataset_version
        ):
            problems.append("dataset_version")
        if manifest.get("external_calls") != 0:
            problems.append("external_calls")
        if manifest.get("model_quality_claim") is not False:
            problems.append("model_quality_claim")
        if manifest.get("sources") != _manifest_sources(component):
            problems.append("sources")
        if manifest.get("artifact_sha256") != expected_hash:
            problems.append("artifact_sha256")
        metrics = manifest.get("metrics", {})
        if metrics.get("contract_tests_failed") != 0:
            problems.append("contract_tests_failed")
        if problems:
            raise RuntimeError(
                f"offline baseline is stale or invalid ({component}: "
                f"{', '.join(problems)}): {path}"
            )
        verified.append(path)
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--name", required=True)
    subparsers.add_parser("verify")
    args = parser.parse_args()

    if args.command == "create":
        paths = create_offline_baselines(args.name)
        print(f"offline baselines created: {len(paths)}")
    else:
        paths = verify_offline_baselines()
        print(f"offline baselines verified: {len(paths)}")


if __name__ == "__main__":
    main()
