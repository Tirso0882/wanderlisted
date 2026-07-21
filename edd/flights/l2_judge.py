"""EDD Layer 2 — LLM-as-JUDGE for the Flights agent's SUMMARY.

Layer 1 scored the agent's DECISION (which tool, which args) with pure-code
evaluators — deterministic, free, instant. But a tool-calling agent also writes
PROSE: after `search_flights` returns, it summarizes the results for the
traveler. You cannot grade prose with `==`. That's what Layer 2 is for.

WHAT CHANGES FROM LAYER 1
    Layer 1:  input = tool_calls (the DECISION)         judge = pure code  (deterministic)
    Layer 2:  input = final_text + tool_outputs (PROSE) judge = an LLM     (non-deterministic)

    We move UP the ReAct loop: Layer 1 checked Reason→Act (the call it made);
    Layer 2 checks Observe→Answer (what it did with the results).

WHAT WE JUDGE (two dimensions, each scored 0–3 against a rubric)
    faithfulness — is every claim in the answer SUPPORTED by the tool results?
                   (catches hallucination: an invented airline, a made-up price)
    helpfulness  — does the answer actually address the traveler's request,
                   clearly and concisely?

KEY IDEA — no hand-written ground truth for faithfulness.
    Layer 1 needed an `expected` dict per case (you wrote the right answer).
    Faithfulness needs NONE: the tool's OWN output IS the reference. The judge
    checks the answer against the evidence the agent itself retrieved. That's
    why LLM-as-judge scales to cases you never hand-labelled.

THE NEW WRINKLE — the judge is itself an LLM, so it is non-deterministic.
    We shrink that variance (a strong judge model, an anchored rubric, forced
    structured output) but we cannot erase it. A judge you haven't checked is
    just another unverified component — which is exactly what Layer 4
    (human calibration) exists to fix. Layer 2 builds the judge; Layer 4 trusts it.

Run the fixture demo (no agent run — a fixed trajectory in, the judge scores it):
    .venv/bin/python edd/flights/l2_judge.py
"""

from __future__ import annotations

import asyncio
import os
import sys

# Put the project root on the path so `edd.*` / `src.*` import whether this file
# is run directly (python edd/flights/l2_judge.py) or imported by the runner.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402
from edd.rubrics import (  # noqa: E402
    AGENT_SPECS,
    build_judge,
    faithfulness_rubric,
    helpfulness_rubric,
    score_faithfulness,
    score_helpfulness,
)


_SPEC = AGENT_SPECS["flights"]

# In-context anchors (rubric-construction checklist item 7) — DISJOINT from
# l2_judge_cases.py (the Layer-4 calibration set). Showing the judge the very
# cases it is later scored on would inflate κ by memorization; these use
# different routes/numbers on purpose. One anchor per boundary the judge must
# hold: a clean 3, a NON-CORE-slip 2, and a CORE-error 1.
_FAITH_EXAMPLES = """EXAMPLES (illustrative anchors — do NOT treat as evidence for the case you score):
  • RESULTS: "LHR->JFK 2026-05-02: British Airways BA175 non-stop 8h05m ECONOMY $612".
    ANSWER: "British Airways BA175 flies London Heathrow to New York JFK non-stop
    in 8h05m for $612 in economy." -> score 3 (every CORE fact grounded).
  • Same RESULTS. ANSWER: "BA175 is non-stop LHR->JFK for $612, and it includes a
    free checked bag." -> score 2 (all flight data grounded; the free-bag claim is
    an unsupported NON-CORE extra — a minor slip).
  • Same RESULTS. ANSWER: "The cheapest is a non-stop Virgin Atlantic flight for
    $540." -> score 1 (airline AND price contradict RESULTS — a materially
    misleading CORE error)."""

# Built once, from the scaffold. `build_judge` is re-exported (imported above) so
# the runners and l4_calibrate.py keep importing it from here unchanged. The
# Flights base wording is preserved from the calibrated (κ=0.95) rubric; the only
# additions are the in-context anchors above and the scaffold's verbosity clause.
FAITHFULNESS_RUBRIC = faithfulness_rubric(_SPEC, examples=_FAITH_EXAMPLES)
HELPFULNESS_RUBRIC = helpfulness_rubric(_SPEC)


# ── The two Flights judges — thin bindings over the scaffold's scorers ──────
async def judge_faithfulness(judge, traj: Trajectory) -> dict:
    """Score whether the final answer is grounded in the tool results."""
    return await score_faithfulness(judge, traj, rubric=FAITHFULNESS_RUBRIC)


async def judge_helpfulness(judge, traj: Trajectory) -> dict:
    """Score whether the final answer actually serves the traveler's request."""
    return await score_helpfulness(judge, traj, rubric=HELPFULNESS_RUBRIC)


# A "judge suite" is just a list of these — same idea as Layer 1's EVALUATORS,
# but each returns a 0–3 score (a rubric grade) instead of 0/1 (a pass/fail).
JUDGES = [judge_faithfulness, judge_helpfulness]


# ── Fixture demo — teach the rubric WITHOUT running the agent ────────────────
# Two hand-written trajectories share the SAME evidence; only the ANSWER differs.
# The grounded one should score ~3 on faithfulness; the hallucinated one should
# be caught (it invents an airline and a price that aren't in the evidence).
_EVIDENCE = [
    (
        "search_flights",
        "Found 2 options JFK->NRT on 2026-08-15:\n"
        "1) ANA (NH tenminus009) dep 11:00 arr 14:55+1, 1 stop, 19h55m, ECONOMY, $1,182\n"
        "2) Japan Airlines (JL005) dep 13:25 arr 16:40+1, non-stop, 14h15m, ECONOMY, $1,410",
    )
]

_GROUNDED_TRAJ = Trajectory(
    query="Find flights from New York to Tokyo on 2026-08-15, 1 adult, economy.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "I found two economy options from JFK to Tokyo Narita on 2026-08-15. "
        "The cheapest is ANA at $1,182 with one stop (19h55m). If you'd rather fly "
        "direct, Japan Airlines JL005 is non-stop in 14h15m for $1,410."
    ),
)

_HALLUCINATED_TRAJ = Trajectory(
    query="Find flights from New York to Tokyo on 2026-08-15, 1 adult, economy.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "The best deal is a non-stop United Airlines flight from JFK to Tokyo for "
        "$690 — a steal for August. I'd book it right away."
    ),  # United, $690, 'best deal non-stop' — none of this is in the evidence.
)


async def _demo() -> None:
    judge = build_judge()
    for label, traj in (
        ("GROUNDED answer — faithful to the tool results", _GROUNDED_TRAJ),
        ("HALLUCINATED answer — invents an airline & price", _HALLUCINATED_TRAJ),
    ):
        print(f"\n{label}")
        print("-" * 68)
        print(f"  answer: {traj.final_text}\n")
        for judge_fn in JUDGES:
            out = await judge_fn(judge, traj)
            score = "SKIP" if out["score"] is None else f"{out['score']}/3"
            print(f"  {out['key']:14s} {score:>4s}   {out['comment']}")
    print()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    import truststore  # trust the OS store; never disable verification

    truststore.inject_into_ssl()
    os.environ["LANGSMITH_TRACING"] = "false"  # fixture demo = hermetic
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    asyncio.run(_demo())
