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

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from edd.harness import Trajectory  # noqa: E402
from src.agent.llm import get_llm  # noqa: E402


# ── The judge's structured verdict ──────────────────────────────────────────
# Forcing structured output is what makes an LLM's opinion MEASURABLE: instead
# of a paragraph we get a number we can average and a reason we can audit.
# `reasoning` is declared BEFORE `score` on purpose — the model fills fields in
# order, so it must justify itself first and commit to a number second
# (cheap chain-of-thought that makes the score more stable and inspectable).
class Verdict(BaseModel):
    """One judge's scored opinion of one dimension of one answer."""

    reasoning: str = Field(
        description="1–2 sentences justifying the score, citing the specific "
        "claim(s) or gap(s) that drove it."
    )
    score: int = Field(ge=0, le=3, description="0–3, per the rubric in the prompt.")


# A Rubric is a structured evaluation framework that breaks down a complex judgment
# into a single dimension with an anchored 0–3 scale.
# ── The rubrics (this is the heart of Layer 2 — 'rubric design') ────────────
# An LLM-as-judge is only as good as its rubric. Good rubrics are:
#   • single-dimension  — each judge scores ONE thing; never blend faithfulness
#                         and helpfulness into a vague "quality" number.
#   • anchored          — say what 0/1/2/3 concretely mean, so scores are
#                         reproducible instead of a mood.
#   • isolation-aware   — the agent was run ALONE on one query (no user profile,
#                         no budget, no upstream agents). The rubric must forbid
#                         punishing the agent for context it was never handed.

FAITHFULNESS_RUBRIC = """You grade the FAITHFULNESS (groundedness) of a travel \
assistant's answer.

You will receive:
  • REQUEST — what the traveler asked for (airline, price, times, stops, route, dates, party size, cabin).
  • RESULTS — the raw output of the `search_flights` tool: the source of truth
    for all FLIGHT DATA. Treat it as complete.
  • ANSWER  — the assistant's prose summary, written for the traveler.

Judge ONE thing: is every claim about FLIGHT DATA (airlines, flight numbers,
prices, times, durations, number of stops, dates) supported by the RESULTS?

Allowed — NOT fabrication: restating parameters from the REQUEST (e.g. "for 1
adult", "economy", the travel date), even if they do not appear in RESULTS. The
traveler supplied those; echoing them is context, not invention. Only NEW flight
facts must come from RESULTS. Ignore style, tone, and helpfulness — grade ONLY
grounding.

CORE vs NON-CORE. The CORE flight facts are: airlines, flight numbers, prices,
times, durations, number of stops, and dates. Everything a traveler would NOT
book a wrong flight over — baggage, meals, seat, lounge, the CITY a stop is in —
is NON-CORE. Grade the grounding of the CORE facts; an unsupported NON-CORE extra
is at most a minor slip, never a fabrication.

Score:
  3 — every CORE flight fact is supported by RESULTS; nothing invented.
      (Restating REQUEST parameters is fine and does NOT lower the score.)
  2 — essentially grounded: at most one MINOR slip that would not change a
      booking decision — a rounded price, a paraphrased time, or an unsupported
      NON-CORE extra (e.g. a free-baggage or meal claim, or a made-up layover
      city) not in RESULTS.
  1 — one materially misleading error in a CORE fact: a price, airline, route,
      or number of stops that is NOT in / contradicts RESULTS, or invented
      per-person/total math the tool did not return.
  0 — largely fabricated, or SEVERAL core facts wrong / directly contradicting
      RESULTS.

Give brief reasoning that names the specific claim you checked, then the score."""

HELPFULNESS_RUBRIC = """You grade how HELPFUL a travel assistant's answer is for \
the traveler's REQUEST.

You will receive:
  • REQUEST — what the traveler asked for.
  • ANSWER  — the assistant's response.

Judge ONE thing: does the ANSWER directly serve the REQUEST — surface the most
relevant flight option(s), give the details a traveler needs to choose, and stay
clear and concise?

IMPORTANT (isolation): the agent was run in isolation on ONLY this request, with
no access to the traveler's profile, budget, loyalty programs, or prior
conversation. Judge only what is answerable from THIS request. Do NOT penalize
the absence of information the agent was never given.

Score:
  3 — directly and clearly answers the request; a traveler could act on it now.
  2 — useful but with a gap: buries the answer, omits one asked-for detail, or
      is noticeably verbose.
  1 — partially relevant but hard to use, or misses most of the request.
  0 — does not address the request (empty, off-topic, or an error message).

Give brief reasoning, then the score."""


# ── The judge handle ────────────────────────────────────────────────────────
def build_judge(tier: str = "reasoning", effort: str | None = None):
    """Build the grader: a strong LLM constrained to emit a `Verdict`.

    WHICH MODEL JUDGES — a rule of thumb: the judge should be at least as
    capable as the thing it grades. The Flights agent runs on the `fast` tier
    (gpt-5.4-mini); we judge with the `reasoning` tier (gpt-5.4) so the grader
    is stronger than the agent, and (bonus) is a *different* model than the one
    under test, which reduces self-preference bias.

    `method="function_calling"` is the codebase-standard way to get reliable
    structured output from the gpt-5.4 reasoning models (see supervisor_agent
    and renderer). The returned runnable takes messages and returns a `Verdict`.

    `effort` overrides the tier's default reasoning effort
    (none|minimal|low|medium|high|xhigh). The A/B experiment
    (flights/l3_judge_ab.py) uses it to vary ONLY the judge's thinking depth.
    """
    overrides = {"reasoning_effort": effort} if effort else {}
    return get_llm(tier=tier, **overrides).with_structured_output(
        Verdict, method="function_calling"
    )


async def _run_judge(
    judge, rubric: str, payload: str, *, timeout: float = 60.0
) -> Verdict:
    """One judge call, with a timeout. Kept tiny so both judges share it."""
    return await asyncio.wait_for(
        judge.ainvoke([SystemMessage(content=rubric), HumanMessage(content=payload)]),
        timeout=timeout,
    )


def _format_evidence(traj: Trajectory, *, max_chars: int = 6000) -> str:
    """The tool outputs = the evidence the answer must be faithful to."""
    text = "\n\n".join(f"[{name}]\n{out}" for name, out in traj.tool_outputs)
    return text[:max_chars]


# ── Judge #1: faithfulness (answer vs the tool's own output) ────────────────
async def judge_faithfulness(judge, traj: Trajectory) -> dict:
    """Score whether the final answer is grounded in the tool results.

    SKIPs (score=None) when there is nothing to ground against — no tool output
    or no answer. (Layer 1's `called_search_flights` already flags a missing
    tool call; each layer checks its own thing.)
    """
    evidence = _format_evidence(traj)
    if not evidence.strip() or not traj.final_text.strip():
        return {
            "key": "faithfulness",
            "score": None,
            "comment": "no tool output and/or no answer to check",
        }
    payload = (
        f"REQUEST:\n{traj.query}\n\n"
        f"RESULTS (source of truth for flight data):\n{evidence}\n\n"
        f"ANSWER (judge this):\n{traj.final_text}"
    )
    try:
        verdict = await _run_judge(judge, FAITHFULNESS_RUBRIC, payload)
    except Exception as exc:  # noqa: BLE001 — a judge failure is data, not a crash
        return {"key": "faithfulness", "score": None, "comment": f"judge error: {exc}"}
    return {"key": "faithfulness", "score": verdict.score, "comment": verdict.reasoning}


# ── Judge #2: helpfulness (answer vs the request) ───────────────────────────
async def judge_helpfulness(judge, traj: Trajectory) -> dict:
    """Score whether the final answer actually serves the traveler's request."""
    if not traj.final_text.strip():
        return {"key": "helpfulness", "score": 0, "comment": "no answer produced"}
    payload = f"REQUEST:\n{traj.query}\n\nANSWER (judge this):\n{traj.final_text}"
    try:
        verdict = await _run_judge(judge, HELPFULNESS_RUBRIC, payload)
    except Exception as exc:  # noqa: BLE001
        return {"key": "helpfulness", "score": None, "comment": f"judge error: {exc}"}
    return {"key": "helpfulness", "score": verdict.score, "comment": verdict.reasoning}


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
    os.environ.setdefault("LANGSMITH_TRACING", "false")  # fixture demo = hermetic

    asyncio.run(_demo())
