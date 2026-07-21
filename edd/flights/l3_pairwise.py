"""EDD Layer 3 — PAIRWISE preference: is version B better than version A?

Layers 1–2 score an answer in ISOLATION: Layer 1 gives the decision a pass/fail,
Layer 2 gives the prose an absolute 0–3. But the question that actually drives
development is COMPARATIVE — "I changed the prompt / bumped the model / raised
reasoning effort; is the new version BETTER?" Two absolute scores can't answer
that when they saturate: a v1 at helpfulness 3/3 and a v2 also at 3/3 look tied,
yet one may read distinctly better. Layer 3 asks the judge the sharper question
directly: A or B?

WHAT CHANGES FROM LAYER 2
    Layer 2 (pointwise):  ONE answer  -> absolute score 0–3   ("how good is this?")
    Layer 3 (pairwise) :  TWO answers -> a preference A|B|tie  ("which is better?")

    Relative judgments are more reliable than absolute ones — the judge doesn't
    have to calibrate an internal 0–3 scale, only spot the difference between two
    concrete answers. That's why pairwise is the backbone of real prompt/model
    iteration (and of "LLM arena" leaderboards).

THE ONE RULE OF A/B — state what varies.
    A controlled A/B result is attributable only when the two answers differ in
    a SINGLE factor: for example, hold the agent, tools, query, and model fixed
    while changing reasoning effort. The default runner
    (l3_pairwise_run.py), however, compares named model configurations from
    edd/models.py: Terra and Luna use different deployments and tiers. Read that
    result as a model-configuration comparison, not an effort-only experiment.

THE NEW HAZARD — position bias.
    LLM judges systematically favor whichever answer sits in a particular slot
    (often the first). One call is a coin flip. So `judge_pairwise` judges every
    pair TWICE with the slots swapped and declares a winner ONLY when both orders
    agree; a flip is counted as a tie (and flagged). That swap is the core rigor
    of this layer.

WHY HELPFULNESS IS PAIRWISE BUT FAITHFULNESS STAYS POINTWISE (Layer 2).
    Pairwise needs a SHARED reference both answers are graded against. Helpfulness
    has one — the request is identical for both variants. Faithfulness does NOT:
    each variant is a separate live run, so each answer has its OWN tool output to
    be grounded in, and grading A's claims against B's evidence is nonsense. So
    faithfulness stays a pointwise Layer-2 check; Layer 3 compares a shared-
    reference dimension — helpfulness here.

Run the fixture demo (no agent run — two fixed answers in, the judge picks):
    .venv/bin/python edd/flights/l3_pairwise.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Put the project root on the path so `edd.*` / `src.*` import whether this file
# is run directly (python edd/flights/l3_pairwise.py) or imported by the runner.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402
from edd.flights.run_utils import classify_flight_outcome  # noqa: E402
from edd.rubrics import (  # noqa: E402
    AGENT_SPECS,
    build_pairwise_judge,
    compare_pairwise,
    pairwise_rubric,
)


# ── The pairwise verdict ─────────────────────────────────────────────────────
# The pairwise verdict schema (`Preference`) now lives in edd/rubrics.py, shared
# by every agent's judge. This file just picks the Flights spec and builds its
# rubric from it — the same single-dimension, tie-honest discipline, one line.
_SPEC = AGENT_SPECS["flights"]


# ── The rubric (single-dimension, isolation-aware, tie-honest) ───────────────
# Mirrors Layer 2's rubric discipline, but phrased as a CHOICE, not a score.
# The two extra guards are what keep a pairwise judge honest:
#   • isolation  — same as Layer 2: neither answer had the traveler's profile.
#   • fairness   — forbid the two cheapest shortcuts to a bogus winner: rewarding
#                  the longer or the more confident answer. Ties are allowed and
#                  expected; do not invent a winner.
HELPFULNESS_PAIRWISE_RUBRIC = pairwise_rubric(_SPEC)


# ── The judge handle ─────────────────────────────────────────────────────────
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
    re-exported here, so l3_pairwise_run.py keeps importing both from this file.

    Returns {"key", "winner": "A"|"B"|"tie"|None, "consistent": bool|None,
    "comment"} in the ORIGINAL labels (traj_a = A, traj_b = B). SKIPs
    (winner=None) when an answer is empty or the run errored.
    """
    outcome_a = classify_flight_outcome(traj_a)
    outcome_b = classify_flight_outcome(traj_b)
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
    return await compare_pairwise(judge, traj_a, traj_b, rubric=rubric)


# ── Fixture demo — teach the pairwise judge WITHOUT running the agent ────────
# Three answers to the SAME request. Helpfulness needs no tool output (its
# reference is the request), so the trajectories carry only query + final_text.
_REQUEST = "Find flights from New York to Tokyo on 2026-08-15, 1 adult, economy."

_VAGUE = Trajectory(
    query=_REQUEST,
    final_text=(
        "There are several flights from New York to Tokyo around that date. Prices "
        "vary depending on the airline and the number of stops, so you can pick "
        "whichever one suits you best."
    ),  # relevant but useless — no option, no price, nothing to act on.
)

_CLEAR = Trajectory(
    query=_REQUEST,
    final_text=(
        "Two economy options JFK -> Tokyo Narita on 2026-08-15: ANA at $1,182 "
        "(1 stop, 19h55m), or Japan Airlines JL005 non-stop (14h15m) at $1,410. "
        "Pick ANA to save, or JAL to fly direct."
    ),
)

_CLEAR_PARAPHRASE = Trajectory(
    query=_REQUEST,
    final_text=(
        "You've got two economy choices on 2026-08-15 from JFK to Tokyo (Narita): "
        "the cheaper ANA at $1,182 with one stop (19h55m), or the non-stop Japan "
        "Airlines JL005 for $1,410 (14h15m). Go with ANA to save, or JAL for the "
        "direct flight."
    ),  # same substance AND decision cue as _CLEAR, only reworded -> should tie.
)


async def _demo() -> None:
    judge = build_pairwise_judge()
    pairs = [
        ("vague (A) vs clear (B)          -> expect B", _VAGUE, _CLEAR),
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
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    asyncio.run(_demo())
