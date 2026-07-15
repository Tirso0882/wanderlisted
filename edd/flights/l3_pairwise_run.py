"""EDD Layer 3 — run the PAIRWISE judge on the AGENT, A/B over the DATASET.

The Layer-3 analog of l2_judge_run.py. Same skeleton — run the real agent over
every case, then aggregate — but now we run TWO variants of the agent per query
and ask the judge which answer is better, instead of scoring one answer 0–3.

    variant A (LLM + Duffel)  ┐
                              ├─ same query ─> two answers ─> pairwise judge ─> A|B|tie
    variant B (LLM + Duffel)  ┘                               (run TWICE, slots swapped)

WHAT VARIES — the model. LINEUP names the contestants from the shared registry
    (edd/models.py). Two names run a single A/B; three or more run a ROUND-ROBIN
    tournament — every model vs every other, aggregated into a win-rate
    leaderboard (how an LLM arena ranks many models from 2-at-a-time battles).
    The judge always compares exactly TWO answers; you scale to N models by
    playing more pairs, never by asking it to grade N answers at once.

POSITION BIAS is handled inside `judge_pairwise` (it judges each pair in both
orders and only counts a win when they agree). Here we aggregate the verdicts
into per-model W/L/T and a win-rate — and track how often the judge flipped with
order, a Layer-4-flavored trust signal on the judge itself.

The JUDGE (a registry key) is built ONCE and must be a DIFFERENT model from every
contestant — a judge grading its own answers has self-preference bias. The
strongest model makes the best referee, so Sol judges the Terra-vs-Luna worker
contest it would only distort as a contestant (a flagship over-reasons a simple
worker task).

Run it (cost scales: N agent runs x D cases, plus C(N,2) x D x 2 judge calls):
    .venv/bin/python edd/flights/l3_pairwise_run.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from itertools import combinations

from dotenv import load_dotenv

load_dotenv()

# Trust the OS store (public certs + corporate proxy) the secure way.
import truststore  # noqa: E402

truststore.inject_into_ssl()
# Toggle: "false" = hermetic loop (just the verdicts); "true" = trace agents + judge.
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from edd.flights.l1_dataset import DATASET  # the SAME golden dataset as Layers 1–2
from edd.flights.l3_pairwise import build_pairwise_judge, judge_pairwise  # noqa: E402
from edd.harness import run_agent  # shared "run + capture" machinery
from edd.models import MODELS  # the shared model registry (single source of truth)
from src.agent.agents import FlightsAgent  # noqa: E402

# The models to put in the ring — keys from edd/models.py. TWO names = a single
# A/B; THREE or more = a round-robin tournament (every model vs every other, then
# a win-rate leaderboard). Changing the field under test is editing this ONE list.
LINEUP = ["terra", "luna"]

# The referee — a registry key, the STRONGEST model, and deliberately NOT a
# contestant: a judge grading its own answers has self-preference bias. Sol
# outranks both workers, so it's the ideal neutral grader for this contest.
JUDGE = "sol"


async def main() -> None:
    if JUDGE in LINEUP:
        raise SystemExit(
            f"JUDGE {JUDGE!r} is also a contestant — pick a neutral referee "
            "(a judge grading its own answers = self-preference bias)."
        )
    print(
        f"\nFlights agent — PAIRWISE Layer 3 over {len(DATASET)} cases"
        f"\nlineup: {', '.join(LINEUP)}   judge: {JUDGE}   (configs from edd/models.py)"
    )
    print("=" * 74)

    # 1) Run each contestant's agent over the whole dataset ONCE (concurrently)
    #    and cache its trajectories — N models x D cases agent runs.
    trajs: dict[str, list] = {}
    for name in LINEUP:
        trajs[name] = await asyncio.gather(
            *(run_agent(FlightsAgent, c["query"], **MODELS[name]) for c in DATASET)
        )

    # 2) Play every unordered pair. judge_pairwise runs BOTH slot orders and folds
    #    position bias into each verdict, so one call per (pair, case) suffices.
    #    Build the grader ONCE — Sol (strongest) and NOT a contestant.
    judge = build_pairwise_judge(**MODELS[JUDGE])
    tally = {n: {"w": 0, "l": 0, "t": 0} for n in LINEUP}
    pair_rows: list[tuple] = []

    for a, b in combinations(LINEUP, 2):
        verdicts = await asyncio.gather(
            *(judge_pairwise(judge, ta, tb) for ta, tb in zip(trajs[a], trajs[b]))
        )
        wa = wb = tie = flips = 0
        for v in verdicts:
            if v["winner"] is None:  # a run errored / empty — not a game
                continue
            if not v["consistent"]:
                flips += 1
            if v["winner"] == "A":
                wa += 1
                tally[a]["w"] += 1
                tally[b]["l"] += 1
            elif v["winner"] == "B":
                wb += 1
                tally[b]["w"] += 1
                tally[a]["l"] += 1
            else:
                tie += 1
                tally[a]["t"] += 1
                tally[b]["t"] += 1
        pair_rows.append((a, b, wa, wb, tie, flips))

    # 3) Head-to-head detail (A = the first name's wins), then the leaderboard.
    print(f"\n{'matchup':24s} {'A':>4s} {'B':>4s} {'tie':>4s} {'flips':>6s}")
    print("-" * 74)
    for a, b, wa, wb, tie, flips in pair_rows:
        print(f"{f'{a} vs {b}':24s} {wa:>4d} {wb:>4d} {tie:>4d} {flips:>6d}")

    def _win_rate(rec: dict) -> float:
        games = rec["w"] + rec["l"] + rec["t"]
        return (rec["w"] + 0.5 * rec["t"]) / games if games else 0.0

    print("\n" + "=" * 74)
    print("LEADERBOARD — win-rate (ties = ½), best flights model first:")
    for rank, name in enumerate(
        sorted(LINEUP, key=lambda n: _win_rate(tally[n]), reverse=True), start=1
    ):
        rec = tally[name]
        games = rec["w"] + rec["l"] + rec["t"]
        print(
            f"  {rank}. {name:8s} {_win_rate(rec):>4.0%}   "
            f"(W {rec['w']}  L {rec['l']}  T {rec['t']}  over {games} games)"
        )

    total_flips = sum(flips for *_, flips in pair_rows)
    total_decided = sum(wa + wb + tie for _, _, wa, wb, tie, _ in pair_rows)
    if total_decided:
        print(
            f"\norder-sensitive verdicts (folded into ties): "
            f"{total_flips}/{total_decided} battles  <- judge stability; "
            "formalizing it is Layer 4."
        )
    print(
        "\nReminder: tiny n and non-deterministic agents feeding a non-deterministic"
        "\njudge — read the leaderboard as a hint, not proof.\n"
    )

    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
