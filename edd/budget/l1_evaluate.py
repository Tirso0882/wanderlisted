"""Deterministic Budget Layer-1 report evaluators."""

from collections import Counter


def _value(report: dict, path: str):
    current = report
    for part in path.split("."):
        current = current[part]
    return current


def evaluate_report(report: dict, expected: dict) -> list[dict]:
    checks: list[dict] = []
    for path, value in expected.get("equals", {}).items():
        actual = _value(report, path)
        checks.append(
            {
                "key": f"equals:{path}",
                "passed": actual == value,
                "actual": actual,
                "expected": value,
            }
        )
    for path, values in expected.get("contains", {}).items():
        actual = _value(report, path)
        checks.append(
            {
                "key": f"contains:{path}",
                "passed": all(value in actual for value in values),
                "actual": actual,
                "expected": values,
            }
        )

    source_ids = [item["source_id"] for item in report["line_items"]]
    for source_id in expected.get("exclude_source_ids", []):
        checks.append(
            {
                "key": f"exclude-source:{source_id}",
                "passed": source_id not in source_ids,
                "actual": source_ids,
                "expected": "absent",
            }
        )
    for source_id, count in expected.get("source_counts", {}).items():
        actual = Counter(source_ids)[source_id]
        checks.append(
            {
                "key": f"source-count:{source_id}",
                "passed": actual == count,
                "actual": actual,
                "expected": count,
            }
        )
    for source_id in expected.get("null_usd_source_ids", []):
        item = next(
            (item for item in report["line_items"] if item["source_id"] == source_id),
            None,
        )
        checks.append(
            {
                "key": f"null-usd:{source_id}",
                "passed": bool(item) and item["amount_usd"] is None,
                "actual": item,
                "expected": "amount_usd is null",
            }
        )

    signals = {
        (item["source_component"], item["signal"])
        for item in report["non_numeric_evidence"]
    }
    for component, signal in expected.get("signals", []):
        checks.append(
            {
                "key": f"signal:{component}/{signal}",
                "passed": (component, signal) in signals,
                "actual": sorted(signals),
                "expected": [component, signal],
            }
        )
    for component in expected.get("exclude_components", []):
        actual = [
            item
            for item in report["line_items"]
            if item["source_component"] == component
        ]
        checks.append(
            {
                "key": f"exclude-component:{component}",
                "passed": not actual,
                "actual": actual,
                "expected": [],
            }
        )

    checks.append(
        {
            "key": "reconciliation",
            "passed": abs(report["reconciliation_delta"]) < 0.01,
            "actual": report["reconciliation_delta"],
            "expected": 0,
        }
    )
    return checks


def case_passes(report: dict, expected: dict) -> bool:
    return all(check["passed"] for check in evaluate_report(report, expected))
