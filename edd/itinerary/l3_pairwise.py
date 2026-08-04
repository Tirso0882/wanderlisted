"""Itinerary Layer-3 pairwise helpfulness judge."""

from edd.harness import Trajectory
from edd.itinerary.run_utils import classify_itinerary_outcome
from edd.rubrics import (
    AGENT_SPECS,
    build_pairwise_judge,
    compare_pairwise,
    pairwise_rubric,
)

HELPFULNESS_PAIRWISE_RUBRIC = (
    pairwise_rubric(AGENT_SPECS["itinerary"])
    + """

Prefer the answer that preserves canonical dates and selected source IDs, reports
measured route facts without invented fares, and makes feasibility warnings,
missing constraints, supported daily costs, and unscheduled stops easiest to act on.
"""
)


async def judge_pairwise(
    judge, trajectory_a: Trajectory, trajectory_b: Trajectory
) -> dict:
    outcomes = {
        classify_itinerary_outcome(trajectory_a),
        classify_itinerary_outcome(trajectory_b),
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


__all__ = [
    "HELPFULNESS_PAIRWISE_RUBRIC",
    "build_pairwise_judge",
    "judge_pairwise",
]
