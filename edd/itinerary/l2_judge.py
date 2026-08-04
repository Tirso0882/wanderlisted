"""Itinerary Layer-2 pointwise groundedness and usefulness judges."""

from edd.harness import Trajectory
from edd.rubrics import (
    AGENT_SPECS,
    build_judge,
    faithfulness_rubric,
    helpfulness_rubric,
    score_faithfulness,
    score_helpfulness,
)

_SPEC = AGENT_SPECS["itinerary"]

FAITHFULNESS_RUBRIC = (
    faithfulness_rubric(_SPEC)
    + """

TYPED ITINERARY RULES:
  - TripSkeleton alone owns dates, day numbers, stay cities, and the final exit city.
  - Hotels and stops must resolve to exact selected rate keys/source IDs in the catalog.
  - RoutePlan alone owns route order and measured metres/seconds; no fare may be invented.
  - Missing hours, route legs, flight times, or inter-city timing cannot be called verified.
  - Daily costs include only mapped, non-estimated Budget line items; the overall budget is copied.
"""
)

HELPFULNESS_RUBRIC = (
    helpfulness_rubric(_SPEC)
    + """

ITINERARY PRESENTATION:
  - Surface local times when verified, feasibility warnings, assumptions, missing constraints,
    cost coverage, and every selected stop that was moved to the unscheduled list.
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
