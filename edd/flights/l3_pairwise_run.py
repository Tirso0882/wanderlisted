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

Run it (agent captures are reused by fingerprint; judge cost scales as
C(N,2) x D x 2 calls):
    .venv/bin/python edd/flights/l3_pairwise_run.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from itertools import combinations
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Trust the OS store (public certs + corporate proxy) the secure way.
import truststore  # noqa: E402

truststore.inject_into_ssl()
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from edd.baseline_store import record_component_report
from edd.flights.l1_dataset import DATASET  # the SAME golden dataset as Layers 1–2
from edd.flights.l3_pairwise import build_pairwise_judge, judge_pairwise  # noqa: E402
from edd.flights.run_utils import BASELINE_CONFIG, run_flight_dataset
from edd.models import MODELS  # the shared model registry (single source of truth)

# The models to put in the ring — keys from edd/models.py. TWO names = a single
# A/B; THREE or more = a round-robin tournament (every model vs every other, then
# a win-rate leaderboard). Changing the field under test is editing this ONE list.
LINEUP = ["terra", "luna"]

# The referee — a registry key, the STRONGEST model, and deliberately NOT a
# contestant: a judge grading its own answers has self-preference bias. Sol
# outranks both workers, so it's the ideal neutral grader for this contest.
JUDGE = "sol"
JUDGE_CASE_CONCURRENCY = 3


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

    # 1) Run or reuse each contestant's pinned dataset snapshot once.
    trajs: dict[str, list] = {}
    queries = [case["query"] for case in DATASET]
    for name in LINEUP:
        trajs[name] = await run_flight_dataset(queries, model_config=MODELS[name])

    # 2) Play every unordered pair. judge_pairwise runs BOTH slot orders and folds
    #    position bias into each verdict, so one call per (pair, case) suffices.
    #    Build the grader ONCE — Sol (strongest) and NOT a contestant.
    judge = build_pairwise_judge(**MODELS[JUDGE])
    judge_semaphore = asyncio.Semaphore(JUDGE_CASE_CONCURRENCY)
    tally = {n: {"w": 0, "l": 0, "t": 0} for n in LINEUP}
    pair_rows: list[tuple] = []

    async def judge_battle(trajectory_a, trajectory_b):
        async with judge_semaphore:
            return await judge_pairwise(judge, trajectory_a, trajectory_b)

    for a, b in combinations(LINEUP, 2):
        verdicts = await asyncio.gather(
            *(judge_battle(ta, tb) for ta, tb in zip(trajs[a], trajs[b]))
        )
        wa = wb = tie = flips = skipped = 0
        print(f"\nCASE REASONS — {a} vs {b}:")
        for case_number, (case, v) in enumerate(zip(DATASET, verdicts), start=1):
            winner = v["winner"] or "SKIP"
            consistency = "" if v["consistent"] else " (order-sensitive)"
            print(f"  {case_number:>2}. {winner}{consistency} — {case['query']}")
            print(f"      {v['comment']}")
            if v["winner"] is None:  # a run errored / empty — not a game
                skipped += 1
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
        pair_rows.append((a, b, wa, wb, tie, flips, skipped))

    # 3) Head-to-head detail (A = the first name's wins), then the leaderboard.
    print(
        f"\n{'matchup':24s} {'A':>4s} {'B':>4s} {'tie':>4s} {'flips':>6s} {'skip':>5s}"
    )
    print("-" * 74)
    for a, b, wa, wb, tie, flips, skipped in pair_rows:
        print(
            f"{f'{a} vs {b}':24s} {wa:>4d} {wb:>4d} {tie:>4d} {flips:>6d} {skipped:>5d}"
        )

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

    total_flips = sum(row[5] for row in pair_rows)
    total_skipped = sum(row[6] for row in pair_rows)
    total_decided = sum(row[2] + row[3] + row[4] for row in pair_rows)
    if total_decided:
        print(
            f"\norder-sensitive verdicts (folded into ties): "
            f"{total_flips}/{total_decided} battles  <- judge stability; "
            "formalizing it is Layer 4."
        )
    if total_skipped:
        print(
            f"\nskipped battles: {total_skipped} (provider-blocked or errored "
            "arms are not model-quality evidence)"
        )
    record_component_report(
        BASELINE_CONFIG,
        layer="l3",
        metrics={
            "matchups": [
                {
                    "model_a": a,
                    "model_b": b,
                    "wins_a": wins_a,
                    "wins_b": wins_b,
                    "ties": ties,
                    "order_sensitive": flips,
                    "skipped": skipped,
                }
                for a, b, wins_a, wins_b, ties, flips, skipped in pair_rows
            ],
            "leaderboard": {
                name: {
                    "wins": tally[name]["w"],
                    "losses": tally[name]["l"],
                    "ties": tally[name]["t"],
                    "win_rate": _win_rate(tally[name]),
                }
                for name in LINEUP
            },
            "judge_stability": {
                "order_sensitive": total_flips,
                "decided": total_decided,
                "order_sensitive_rate": (
                    total_flips / total_decided if total_decided else None
                ),
                "skipped": total_skipped,
            },
        },
        queries=queries,
        model_configs={name: MODELS[name] for name in LINEUP},
        context={"lineup": LINEUP, "judge": JUDGE, "judge_config": MODELS[JUDGE]},
        report_source_files=(
            Path(__file__),
            Path(__file__).with_name("l3_pairwise.py"),
            Path(__file__).resolve().parents[1] / "rubrics.py",
        ),
    )
    print(
        "\nReminder: tiny n and non-deterministic agents feeding a non-deterministic"
        "\njudge — read the leaderboard as a hint, not proof.\n"
    )

    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
