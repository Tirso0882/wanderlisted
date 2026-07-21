"""Layer 3 pairwise helpfulness judge for TransportationAgent variants."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402
from edd.rubrics import (  # noqa: E402
    AGENT_SPECS,
    build_pairwise_judge,
    compare_pairwise,
    pairwise_rubric,
)
from edd.transportation.run_utils import classify_transportation_outcome  # noqa: E402

_SPEC = AGENT_SPECS["transportation"]

HELPFULNESS_PAIRWISE_RUBRIC = (
    pairwise_rubric(_SPEC)
    + """

TRANSPORTATION PRODUCT PRESENTATION:
  - Prefer an answer that preserves the requested origin, destination, and mode,
    then presents measured distance, duration, and usable steps clearly.
  - When cost, passes, accessibility, schedules, or real-time service information
    are absent from the route output, prefer an honest limitation over an invented
    estimate or guarantee.

MATERIAL-DIFFERENCE RULE (apply before choosing a winner):
  1. Extract the request's explicit route constraints: endpoints, requested mode,
      waypoints, comparison alternatives, and any stated accessibility/cost need.
  2. Compare BOTH answers against those SAME constraints in that order. Do not
      start from whichever answer appears first.
  3. Choose a winner only when one answer materially honors an explicit constraint,
      makes the route notably more actionable, or avoids a major route error.
  4. Return `tie` when advantages are minor or offsetting. Slightly different
      wording, one extra nonessential direction, or small length differences are
      not enough to declare a winner.
"""
)

__all__ = [
    "HELPFULNESS_PAIRWISE_RUBRIC",
    "build_pairwise_judge",
    "judge_pairwise",
]


async def judge_pairwise(
    judge,
    trajectory_a: Trajectory,
    trajectory_b: Trajectory,
    *,
    rubric: str = HELPFULNESS_PAIRWISE_RUBRIC,
) -> dict:
    outcome_a = classify_transportation_outcome(trajectory_a)
    outcome_b = classify_transportation_outcome(trajectory_b)
    blocked = {"blocked_external", "infra_error"}
    if outcome_a in blocked or outcome_b in blocked:
        return {
            "key": "helpfulness_pairwise",
            "winner": None,
            "consistent": None,
            "comment": (
                "external/infra failure in at least one arm "
                f"(A={outcome_a}, B={outcome_b}); excluded from model comparison"
            ),
        }
    return await compare_pairwise(judge, trajectory_a, trajectory_b, rubric=rubric)


_REQUEST = "Give transit directions from Fiumicino Airport to Hotel Artemide in Rome."

_VAGUE = Trajectory(
    query=_REQUEST,
    final_text="Use public transport from the airport to central Rome.",
)

_CLEAR = Trajectory(
    query=_REQUEST,
    final_text=(
        "Take the Leonardo Express from Fiumicino Aeroporto to Roma Termini, then "
        "walk 700 m to Hotel Artemide. The 31.4 km route takes about 52 minutes."
    ),
)

_CLEAR_PARAPHRASE = Trajectory(
    query=_REQUEST,
    final_text=(
        "For Hotel Artemide, use the Leonardo Express to Roma Termini and walk the "
        "last 700 m. It is a 31.4 km transit trip of roughly 52 minutes."
    ),
)


async def _demo() -> None:
    judge = build_pairwise_judge()
    pairs = [
        ("vague (A) vs clear (B) -> expect B", _VAGUE, _CLEAR),
        (
            "clear (A) vs clear paraphrase (B) -> expect tie",
            _CLEAR,
            _CLEAR_PARAPHRASE,
        ),
    ]
    for label, trajectory_a, trajectory_b in pairs:
        print(f"\n{label}")
        print("-" * 68)
        output = await judge_pairwise(judge, trajectory_a, trajectory_b)
        winner = output["winner"] or "SKIP"
        flag = "" if output["consistent"] else "   (order-sensitive)"
        print(f"  winner: {winner}{flag}")
        print(f"  why:    {output['comment']}")
    print()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    import truststore

    truststore.inject_into_ssl()
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    asyncio.run(_demo())
