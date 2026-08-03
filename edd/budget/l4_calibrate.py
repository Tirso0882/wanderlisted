"""Calibrate the Budget faithfulness judge against held-out labels."""

from __future__ import annotations

import asyncio

from edd.budget.l2_judge import build_judge, judge_faithfulness
from edd.budget.l2_judge_cases import JUDGE_CASES
from edd.budget.run_utils import require_judge_approval
from edd.calibration import run_calibration


async def main() -> None:
    require_judge_approval(layer="Layer 4", estimated_calls=len(JUDGE_CASES))
    await run_calibration(
        build_judge=build_judge,
        judge_faithfulness=judge_faithfulness,
        cases=JUDGE_CASES,
        agent="Budget",
        rubric_module="edd/budget/l2_judge.py",
    )


if __name__ == "__main__":
    asyncio.run(main())
