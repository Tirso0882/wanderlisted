"""Budget Layer-3 pairwise helpfulness judge."""

from edd.budget.run_utils import classify_budget_outcome
from edd.harness import Trajectory
from edd.rubrics import (
    AGENT_SPECS,
    build_pairwise_judge,
    compare_pairwise,
    pairwise_rubric,
)

HELPFULNESS_PAIRWISE_RUBRIC = (
    pairwise_rubric(AGENT_SPECS["budget"])
    + """

Prefer the answer that preserves the validated display currency and makes
coverage, missing costs, estimates, assumptions, reserve/contingency, and any
supported overage easiest to understand. Prefer an honest unknown verdict over
an affordability claim based on incomplete evidence.
"""
)

__all__ = [
    "HELPFULNESS_PAIRWISE_RUBRIC",
    "build_pairwise_judge",
    "judge_pairwise",
]


async def judge_pairwise(
    judge, trajectory_a: Trajectory, trajectory_b: Trajectory
) -> dict:
    outcomes = {
        classify_budget_outcome(trajectory_a),
        classify_budget_outcome(trajectory_b),
    }
    if outcomes & {"blocked_external", "infra_error"}:
        return {
            "key": "helpfulness_pairwise",
            "winner": None,
            "consistent": None,
            "comment": "external or infrastructure failure excluded",
        }
    return await compare_pairwise(
        judge, trajectory_a, trajectory_b, rubric=HELPFULNESS_PAIRWISE_RUBRIC
    )
