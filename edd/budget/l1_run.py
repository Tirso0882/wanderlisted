"""Run the free, hermetic Budget Layer-1 production gate."""

from __future__ import annotations

import asyncio

from edd.budget.l1_dataset import DATASET
from edd.budget.l1_evaluate import evaluate_report
from edd.budget.l1_observe import observe_case


async def main() -> None:
    failures: list[str] = []
    for case in DATASET:
        report = await observe_case(case)
        checks = evaluate_report(report, case["expected"])
        failed = [check for check in checks if not check["passed"]]
        print(f"{case['name']}: {'PASS' if not failed else 'FAIL'}")
        failures.extend(f"{case['name']}/{check['key']}" for check in failed)
    if failures:
        raise SystemExit("Budget Layer 1 failures: " + ", ".join(failures))
    print(f"Budget Layer 1: {len(DATASET)}/{len(DATASET)} cases passed")


if __name__ == "__main__":
    asyncio.run(main())
