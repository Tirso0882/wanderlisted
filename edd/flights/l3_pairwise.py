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

THE ONE RULE OF A/B — vary exactly ONE thing.
    A pairwise result is only attributable if the two answers differ in a SINGLE
    factor. The runner (l3_pairwise_run.py) holds the agent, tools, query, and
    model fixed and changes only the reasoning EFFORT — the same knob
    l3_judge_ab.py turned on the JUDGE, now turned on the AGENT.

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
from typing import Literal

# Put the project root on the path so `edd.*` / `src.*` import whether this file
# is run directly (python edd/flights/l3_pairwise.py) or imported by the runner.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from edd.harness import Trajectory  # noqa: E402
from src.agent.llm import get_llm  # noqa: E402


# ── The pairwise verdict ─────────────────────────────────────────────────────
# Same trick as Layer 2's `Verdict`: forcing structured output turns an opinion
# into a measurement. `reasoning` is declared BEFORE `winner` so the model must
# justify itself first and commit to a choice second (cheap chain-of-thought that
# makes the pick more stable and inspectable). The winner is a THREE-way enum —
# 'tie' is a first-class outcome, not a failure to decide.
class Preference(BaseModel):
    """One judge's pairwise verdict comparing two answers on ONE dimension."""

    reasoning: str = Field(
        description="1–2 sentences naming the concrete difference that decided "
        "it, or why the two answers are equally good (a tie)."
    )
    winner: Literal["A", "B", "tie"] = Field(
        description="Which answer is better on THIS dimension: 'A', 'B', or 'tie' "
        "when they are equally good."
    )


# ── The rubric (single-dimension, isolation-aware, tie-honest) ───────────────
# Mirrors Layer 2's rubric discipline, but phrased as a CHOICE, not a score.
# The two extra guards are what keep a pairwise judge honest:
#   • isolation  — same as Layer 2: neither answer had the traveler's profile.
#   • fairness   — forbid the two cheapest shortcuts to a bogus winner: rewarding
#                  the longer or the more confident answer. Ties are allowed and
#                  expected; do not invent a winner.
HELPFULNESS_PAIRWISE_RUBRIC = """You compare TWO travel-assistant answers to the \
SAME request and pick the more HELPFUL one.

You will receive:
  • REQUEST — what the traveler asked for.
  • ANSWER A and ANSWER B — two responses to that same request.

Judge ONE thing: which answer better serves the REQUEST — surfaces the most
relevant option(s), gives the details a traveler needs to choose, and stays clear
and concise?

IMPORTANT (isolation): both answers were produced with no access to the
traveler's profile, budget, loyalty programs, or prior conversation. Judge only
what is answerable from THIS request; do not reward or punish either answer for
context neither was given.

IMPORTANT (fairness): ignore superficial length and confidence. A longer or more
assertive answer is NOT automatically better. Answer 'tie' when the two are
equally useful — do not invent a winner.

Reply with:
  • reasoning — name the concrete difference that decided it, or why it's a tie.
  • winner — 'A', 'B', or 'tie'.
"""


# ── The judge handle ─────────────────────────────────────────────────────────
def build_pairwise_judge(
    tier: str = "reasoning", effort: str | None = None, **overrides
):
    """Build the pairwise grader: a strong LLM constrained to emit a `Preference`.

    WHO SHOULD JUDGE — two rules:
      • at least as capable as the answers it compares (the Flights agent runs on
        `fast`; we judge on `reasoning`), and
      • a THIRD model, distinct from BOTH arms under test. If one arm IS the
        `reasoning`-tier model, judging on `reasoning` shares identity with a
        contestant and reintroduces self-preference bias — point the judge at a
        different strong model instead (pass `tier=`, `effort=`, or an explicit
        `azure_deployment=` / `model=` here). Position bias is handled separately,
        by the order-swap inside `judge_pairwise`.

    `method="function_calling"` is the codebase-standard structured-output path
    for the gpt-5.4 reasoning models (see supervisor_agent and renderer). Extra
    `**overrides` are forwarded verbatim to get_llm().
    """
    if effort:
        overrides["reasoning_effort"] = effort
    return get_llm(tier=tier, **overrides).with_structured_output(
        Preference, method="function_calling"
    )


def _pairwise_payload(request: str, answer_a: str, answer_b: str) -> str:
    """One request, two answers to compare — the judge's whole input."""
    return f"REQUEST:\n{request}\n\nANSWER A:\n{answer_a}\n\nANSWER B:\n{answer_b}"


async def _one_verdict(
    judge, rubric: str, payload: str, *, timeout: float = 60.0
) -> Preference:
    """A single pairwise judge call, with a timeout. Both orders share it."""
    return await asyncio.wait_for(
        judge.ainvoke([SystemMessage(content=rubric), HumanMessage(content=payload)]),
        timeout=timeout,
    )


# Map a swapped-order verdict back to the ORIGINAL labels: in the swapped call,
# "A" meant traj_b and "B" meant traj_a, so A<->B; 'tie' is symmetric.
_DESWAP = {"A": "B", "B": "A", "tie": "tie"}


async def judge_pairwise(
    judge,
    traj_a: Trajectory,
    traj_b: Trajectory,
    *,
    rubric: str = HELPFULNESS_PAIRWISE_RUBRIC,
) -> dict:
    """Compare A vs B on one dimension, controlling for POSITION BIAS.

    An LLM judge favors whichever answer sits in a given slot, so a single call
    is untrustworthy. We ask TWICE, swapping the slots, and only declare a winner
    when both orders agree:

        pass 1 (as-is)   : slot A = traj_a,  slot B = traj_b
        pass 2 (swapped) : slot A = traj_b,  slot B = traj_a

    De-swap pass 2 back to the original labels, then reconcile:
      • both orders point to the SAME answer -> that answer wins (robust)
      • both say 'tie'                       -> genuine tie
      • they disagree (order-sensitive)      -> 'tie', flagged consistent=False

    Returns {"winner": "A"|"B"|"tie"|None, "consistent": bool|None, "comment"},
    with the winner in terms of the ORIGINAL labels (traj_a = A, traj_b = B).
    SKIPs (winner=None) when there is nothing to compare — an answer is empty or
    the run errored. A judge failure is captured as data, never raised.
    """
    if (
        traj_a.error
        or traj_b.error
        or not traj_a.final_text.strip()
        or not traj_b.final_text.strip()
    ):
        return {
            "key": "helpfulness_pairwise",
            "winner": None,
            "consistent": None,
            "comment": "an answer was empty or the run errored — nothing to compare",
        }

    request = traj_a.query  # both variants ran the SAME query
    payload_ab = _pairwise_payload(request, traj_a.final_text, traj_b.final_text)
    payload_ba = _pairwise_payload(request, traj_b.final_text, traj_a.final_text)

    try:
        v1, v2 = await asyncio.gather(
            _one_verdict(judge, rubric, payload_ab),
            _one_verdict(judge, rubric, payload_ba),
        )
    except Exception as exc:  # noqa: BLE001 — a judge failure is data, not a crash
        return {
            "key": "helpfulness_pairwise",
            "winner": None,
            "consistent": None,
            "comment": f"judge error: {exc}",
        }

    w1 = v1.winner  # already in original labels (A=traj_a, B=traj_b)
    w2 = _DESWAP[v2.winner]  # de-swapped back to original labels

    if w1 == w2:
        # Both orders agree — a robust verdict (a real win, or a genuine tie).
        return {
            "key": "helpfulness_pairwise",
            "winner": w1,
            "consistent": True,
            "comment": v1.reasoning,
        }
    # Orders disagree -> the pick depended on position, not quality. Don't trust
    # it: count it as a tie, but flag the inconsistency (a Layer-4 trust signal).
    return {
        "key": "helpfulness_pairwise",
        "winner": "tie",
        "consistent": False,
        "comment": (
            f"order-sensitive: shown one way -> {w1}, swapped -> {w2}; "
            f"counted as tie. ({v1.reasoning})"
        ),
    }


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
    os.environ.setdefault("LANGSMITH_TRACING", "false")  # fixture demo = hermetic

    asyncio.run(_demo())
