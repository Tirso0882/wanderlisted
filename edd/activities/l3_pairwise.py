"""Layer 3 pairwise helpfulness judge for ActivitiesAgent variants."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.activities.run_utils import classify_activities_outcome  # noqa: E402
from edd.harness import Trajectory  # noqa: E402
from edd.rubrics import (  # noqa: E402
    AGENT_SPECS,
    build_pairwise_judge,
    compare_pairwise,
    pairwise_rubric,
)

_SPEC = AGENT_SPECS["activities"]

HELPFULNESS_PAIRWISE_RUBRIC = (
    pairwise_rubric(_SPEC)
    + """

ACTIVITIES PRODUCT PRESENTATION:
  - When the request includes accessibility, prefer an answer that clearly
    distinguishes returned evidence from a venue-confirmation caveat. Do not
    reward an unsupported accessibility guarantee.
  - For venue-rental requests, prefer an answer that makes returned rental
    candidates easy to compare without inventing capacity, availability, or price.
  - Ignore raw Maps/website URL length. Compare relevance, organization, useful
    venue details, and how quickly the traveler can choose.

MATERIAL-DIFFERENCE RULE (apply before choosing a winner):
  1. Extract the request's explicit constraints (location, interests, activity or
      venue type, accessibility, group fit, style, rental need, or radius).
  2. Compare BOTH answers against those SAME constraints in that order. Do not
      start from whichever answer appears first.
  3. Choose a winner only when one answer materially satisfies an explicit
      constraint better, is substantially more actionable, or avoids a major
      relevance/usability flaw present in the other answer.
  4. Return `tie` when advantages are minor or offsetting. One extra venue, one
      extra link, a final shortlist, slight reordering, small length differences,
      or marginally different organization are NOT enough to declare a winner.
  5. Prefer a focused set of strong matches over breadth for its own sake. Do not
      reward more recommendations unless the request explicitly asks for breadth.
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
    outcome_a = classify_activities_outcome(trajectory_a)
    outcome_b = classify_activities_outcome(trajectory_b)
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


_REQUEST = "Find wheelchair-accessible art museums in Kyoto."

_VAGUE = Trajectory(
    query=_REQUEST,
    final_text="Kyoto has many museums and cultural venues to explore.",
)

_CLEAR = Trajectory(
    query=_REQUEST,
    final_text=(
        "Sakura Arts Museum at 12 Higashiyama is a moderate art museum rated 4.7/5 "
        "from 516 reviews; its listing notes a wheelchair-accessible entrance and "
        "Tuesday-Sunday hours of 10:00-18:00."
    ),
)

_CLEAR_PARAPHRASE = Trajectory(
    query=_REQUEST,
    final_text=(
        "Sakura Arts Museum fits: it is a moderate Kyoto art museum at 12 Higashiyama, "
        "rated 4.7/5 from 516 reviews, with a listed wheelchair-accessible entrance "
        "and Tuesday-Sunday 10:00-18:00 hours."
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
