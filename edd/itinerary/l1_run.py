"""Run the free, hermetic Itinerary Layer-1 production gate."""

from __future__ import annotations

import os

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from edd.itinerary.l1_dataset import DATASET  # noqa: E402
from edd.itinerary.l1_evaluate import evaluate_report  # noqa: E402
from edd.itinerary.l1_observe import observe_case  # noqa: E402


def main() -> None:
    failures: list[str] = []
    for case in DATASET:
        report = observe_case(case)
        checks = evaluate_report(report, case["expected"])
        failed = [check for check in checks if not check["passed"]]
        print(f"{case['name']}: {'PASS' if not failed else 'FAIL'}")
        failures.extend(f"{case['name']}/{check['key']}" for check in failed)
    if failures:
        raise SystemExit("Itinerary Layer 1 failures: " + ", ".join(failures))
    print(f"Itinerary Layer 1: {len(DATASET)}/{len(DATASET)} cases passed")


if __name__ == "__main__":
    main()
