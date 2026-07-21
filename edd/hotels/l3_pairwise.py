"""EDD Layer 3 — PAIRWISE preference for the HOTELS agent: is B better than A?

The hotel analog of edd/flights/l3_pairwise.py, and just as thin now that the
machinery lives in the scaffold (edd/rubrics.py). Layers 1-2 score a hotel answer
in isolation; Layer 3 asks the sharper, comparative question that actually drives
iteration — "I changed the prompt / model / effort; is the new answer BETTER?".

WHY HELPFULNESS IS PAIRWISE BUT FAITHFULNESS STAYS POINTWISE (Layer 2).
    Pairwise needs a SHARED reference both answers are graded against. Helpfulness
    has one — the request is identical for both variants. Faithfulness does NOT:
    each variant is a separate live run with its OWN hotel results, so grading A's
    claims against B's evidence is nonsense. Faithfulness stays a pointwise
    Layer-2 check; Layer 3 compares the shared-reference dimension — helpfulness.

POSITION BIAS is handled inside `compare_pairwise` (imported from the scaffold):
    it judges every pair in BOTH slot orders and declares a winner only when both
    agree; a flip is folded into a tie and flagged.

Run the fixture demo (no agent run — two fixed answers in, the judge picks):
    .venv/bin/python edd/hotels/l3_pairwise.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402
from edd.hotels.run_utils import classify_hotel_outcome  # noqa: E402
from edd.rubrics import (  # noqa: E402
    AGENT_SPECS,
    build_pairwise_judge,
    compare_pairwise,
    pairwise_rubric,
)

_SPEC = AGENT_SPECS["hotels"]

# The pairwise helpfulness rubric, built from the shared scaffold — identical in
# shape to every other agent's, so nothing drifts.
HELPFULNESS_PAIRWISE_RUBRIC = (
    pairwise_rubric(_SPEC)
    + """

HOTEL PRODUCT PRESENTATION:
    • Maps/photo links are required structured data and render compactly in the
        downstream UI. Ignore raw URL character length; compare the organization,
        relevance, and actionability of the hotel choices. Missing required links
        or duplicated/disorganized links may still make an answer less helpful.
"""
)

__all__ = [
    "HELPFULNESS_PAIRWISE_RUBRIC",
    "build_pairwise_judge",
    "judge_pairwise",
]


async def judge_pairwise(
    judge,
    traj_a: Trajectory,
    traj_b: Trajectory,
    *,
    rubric: str = HELPFULNESS_PAIRWISE_RUBRIC,
) -> dict:
    """Compare A vs B on helpfulness, controlling for POSITION BIAS.

    Thin binding over the scaffold's `compare_pairwise`, which judges BOTH slot
    orders and only declares a winner when they agree (a flip -> 'tie', flagged
    consistent=False). `build_pairwise_judge` is imported from the scaffold and
    re-exported here so l3_pairwise_run.py keeps importing both from this file.
    """
    outcome_a = classify_hotel_outcome(traj_a)
    outcome_b = classify_hotel_outcome(traj_b)
    if "blocked_external" in {outcome_a, outcome_b}:
        return {
            "key": "helpfulness_pairwise",
            "winner": None,
            "consistent": None,
            "comment": (
                "provider blocked at least one arm "
                f"(A={outcome_a}, B={outcome_b}); excluded from model comparison"
            ),
        }
    return await compare_pairwise(judge, traj_a, traj_b, rubric=rubric)


# ── Fixture demo — teach the pairwise judge WITHOUT running the agent ────────
# Three answers to the SAME request. Helpfulness needs no tool output (its
# reference is the request), so the trajectories carry only query + final_text.
_REQUEST = (
    "Find a 4-star hotel in Rome with breakfast, 2026-06-20 to 2026-06-24, 2 adults."
)

_VAGUE = Trajectory(
    query=_REQUEST,
    final_text=(
        "There are several hotels in Rome around those dates. Prices vary by area, "
        "star rating and board, so you can pick whichever one suits you best."
    ),  # relevant but useless — no named hotel, no price, nothing to act on.
)

_CLEAR = Trajectory(
    query=_REQUEST,
    final_text=(
        "Hotel Artemide (4-star, Via Nazionale) fits: a Classic Double with "
        "breakfast at EUR 840 total, free to cancel until 10 June. It matches your "
        "4-star + breakfast ask and is centrally located."
    ),
)

_CLEAR_PARAPHRASE = Trajectory(
    query=_REQUEST,
    final_text=(
        "Go with Hotel Artemide — a central 4-star on Via Nazionale. The Classic "
        "Double includes breakfast and runs EUR 840 for the stay, with free "
        "cancellation up to 10 June. It ticks your 4-star and breakfast boxes."
    ),  # same substance AND decision cue as _CLEAR, only reworded -> should tie.
)


async def _demo() -> None:
    judge = build_pairwise_judge()
    pairs = [
        ("vague (A) vs clear (B)            -> expect B", _VAGUE, _CLEAR),
        ("clear (A) vs clear-paraphrase (B) -> expect tie", _CLEAR, _CLEAR_PARAPHRASE),
    ]
    for label, traj_a, traj_b in pairs:
        print(f"\n{label}")
        print("-" * 68)
        out = await judge_pairwise(judge, traj_a, traj_b)
        winner = out["winner"] or "SKIP"
        flag = "" if out["consistent"] else "   (order-sensitive!)"
        print(f"  winner: {winner}{flag}")
        print(f"  why:    {out['comment']}")
    print()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    import truststore  # trust the OS store; never disable verification

    truststore.inject_into_ssl()
    os.environ["LANGSMITH_TRACING"] = "false"  # fixture demo = hermetic
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    asyncio.run(_demo())
