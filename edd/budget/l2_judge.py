"""Budget Layer-2 pointwise report-quality judges."""

from edd.harness import Trajectory
from edd.rubrics import (
    AGENT_SPECS,
    build_judge,
    faithfulness_rubric,
    helpfulness_rubric,
    score_faithfulness,
    score_helpfulness,
)

_SPEC = AGENT_SPECS["budget"]

FAITHFULNESS_RUBRIC = (
    faithfulness_rubric(_SPEC)
    + """

BUDGET EVIDENCE RULES:
  - Legacy top-level categories are USD base amounts and must reconcile to total.
  - Only selected source IDs and explicit traveler costs are numeric evidence.
  - Regional estimates are valid only when labeled estimated with their baseline.
  - Places price levels and Routes no-fare signals never support numeric amounts.
  - Partial coverage or a required conversion failure requires verdict=unknown.
"""
)

HELPFULNESS_RUBRIC = (
    helpfulness_rubric(_SPEC)
    + """

BUDGET PRESENTATION:
  - Surface display currency, coverage, missing major costs, estimated categories,
    assumptions, reserve/contingency status, and a supported target overage.
"""
)


async def judge_faithfulness(judge, trajectory: Trajectory) -> dict:
    return await score_faithfulness(judge, trajectory, rubric=FAITHFULNESS_RUBRIC)


async def judge_helpfulness(judge, trajectory: Trajectory) -> dict:
    return await score_helpfulness(judge, trajectory, rubric=HELPFULNESS_RUBRIC)


JUDGES = [judge_faithfulness, judge_helpfulness]

__all__ = [
    "FAITHFULNESS_RUBRIC",
    "HELPFULNESS_RUBRIC",
    "JUDGES",
    "build_judge",
    "judge_faithfulness",
    "judge_helpfulness",
]
