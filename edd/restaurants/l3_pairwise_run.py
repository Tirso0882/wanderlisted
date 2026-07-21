"""Run a Restaurant Layer 3 round-robin model tournament."""

from __future__ import annotations

import asyncio
import os
import sys
from itertools import combinations
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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
from edd.models import MODELS  # noqa: E402
from edd.restaurants.l1_dataset import DATASET  # noqa: E402
from edd.restaurants.l3_pairwise import (  # noqa: E402
    build_pairwise_judge,
    judge_pairwise,
)
from edd.restaurants.run_utils import (  # noqa: E402
    BASELINE_CONFIG,
    run_restaurant_dataset,
)

LINEUP = ["terra", "luna"]
JUDGE = "sol"
# Each battle launches two order-swapped judge calls. Two concurrent battles
# therefore fill the reasoning tier's four slots without queueing inside timeout.
JUDGE_CASE_CONCURRENCY = 2


async def main() -> None:
    if JUDGE in LINEUP:
        raise SystemExit(
            f"JUDGE {JUDGE!r} is also a contestant; choose a neutral referee"
        )
    print(
        f"\nRestaurants agent - Layer 3 over {len(DATASET)} cases"
        f"\nlineup: {', '.join(LINEUP)}   judge: {JUDGE}"
    )
    print("=" * 74)

    trajectories: dict[str, list] = {}
    queries = [case["query"] for case in DATASET]
    for name in LINEUP:
        trajectories[name] = await run_restaurant_dataset(
            queries, model_config=MODELS[name]
        )

    judge = build_pairwise_judge(**MODELS[JUDGE])
    judge_semaphore = asyncio.Semaphore(JUDGE_CASE_CONCURRENCY)
    tally = {name: {"w": 0, "l": 0, "t": 0} for name in LINEUP}
    pair_rows: list[tuple] = []
    flip_details: list[dict] = []
    skip_details: list[dict] = []

    async def judge_battle(trajectory_a, trajectory_b):
        async with judge_semaphore:
            return await judge_pairwise(judge, trajectory_a, trajectory_b)

    for name_a, name_b in combinations(LINEUP, 2):
        verdicts = await asyncio.gather(
            *(
                judge_battle(trajectory_a, trajectory_b)
                for trajectory_a, trajectory_b in zip(
                    trajectories[name_a], trajectories[name_b]
                )
            )
        )
        wins_a = wins_b = ties = flips = skipped = 0
        for case, trajectory_a, trajectory_b, verdict in zip(
            DATASET, trajectories[name_a], trajectories[name_b], verdicts
        ):
            if verdict["winner"] is None:
                skipped += 1
                skip_details.append(
                    {
                        "matchup": f"{name_a} vs {name_b}",
                        "name_a": name_a,
                        "name_b": name_b,
                        "case": case["name"],
                        "query": case["query"],
                        "comment": verdict.get("comment", "no reason returned"),
                    }
                )
                continue
            if not verdict["consistent"]:
                flips += 1
                flip_details.append(
                    {
                        "matchup": f"{name_a} vs {name_b}",
                        "name_a": name_a,
                        "name_b": name_b,
                        "case": case["name"],
                        "query": case["query"],
                        "winner_forward": verdict.get("winner_forward"),
                        "winner_reverse": verdict.get("winner_reverse"),
                        "slot_winner_forward": verdict.get("slot_winner_forward"),
                        "slot_winner_reverse": verdict.get("slot_winner_reverse"),
                        "inconsistency_type": verdict.get(
                            "inconsistency_type", "unknown"
                        ),
                        "reasoning_forward": verdict.get("reasoning_forward", ""),
                        "reasoning_reverse": verdict.get("reasoning_reverse", ""),
                        "chars_a": len(trajectory_a.final_text),
                        "chars_b": len(trajectory_b.final_text),
                    }
                )
            if verdict["winner"] == "A":
                wins_a += 1
                tally[name_a]["w"] += 1
                tally[name_b]["l"] += 1
            elif verdict["winner"] == "B":
                wins_b += 1
                tally[name_b]["w"] += 1
                tally[name_a]["l"] += 1
            else:
                ties += 1
                tally[name_a]["t"] += 1
                tally[name_b]["t"] += 1
        pair_rows.append((name_a, name_b, wins_a, wins_b, ties, flips, skipped))

    print(
        f"\n{'matchup':24s} {'A':>4s} {'B':>4s} {'tie':>4s} {'flips':>6s} {'skip':>5s}"
    )
    print("-" * 74)
    for name_a, name_b, wins_a, wins_b, ties, flips, skipped in pair_rows:
        print(
            f"{f'{name_a} vs {name_b}':24s} {wins_a:>4d} {wins_b:>4d} "
            f"{ties:>4d} {flips:>6d} {skipped:>5d}"
        )

    def win_rate(record: dict) -> float:
        games = record["w"] + record["l"] + record["t"]
        return (record["w"] + 0.5 * record["t"]) / games if games else 0.0

    print("\n" + "=" * 74)
    print("LEADERBOARD - win rate (ties = 1/2), best restaurant model first:")
    ranking = sorted(LINEUP, key=lambda name: win_rate(tally[name]), reverse=True)
    for rank, name in enumerate(ranking, start=1):
        record = tally[name]
        games = record["w"] + record["l"] + record["t"]
        print(
            f"  {rank}. {name:8s} {win_rate(record):>4.0%}   "
            f"(W {record['w']}  L {record['l']}  T {record['t']}  over {games} games)"
        )

    total_flips = sum(row[5] for row in pair_rows)
    total_skipped = sum(row[6] for row in pair_rows)
    total_decided = sum(row[2] + row[3] + row[4] for row in pair_rows)
    stable_wins_a = sum(row[2] for row in pair_rows)
    stable_wins_b = sum(row[3] for row in pair_rows)
    stable_ties = sum(row[4] - row[5] for row in pair_rows)
    tie_boundary_count = sum(
        detail["inconsistency_type"] == "tie_boundary" for detail in flip_details
    )
    winner_reversal_count = sum(
        detail["inconsistency_type"] == "winner_reversal" for detail in flip_details
    )
    if total_decided:
        print(
            f"\norder-sensitive verdicts (folded into ties): "
            f"{total_flips}/{total_decided} battles"
        )
        print(
            f"  winner reversals: {winner_reversal_count}/{total_decided} "
            "(A vs B - material position-bias risk)"
        )
        print(
            f"  tie-boundary cases: {tie_boundary_count}/{total_decided} "
            "(winner vs tie - conservative tie retained)"
        )
        print(
            f"  stable verdicts: {total_decided - total_flips}/{total_decided} "
            f"(A wins {stable_wins_a}, B wins {stable_wins_b}, "
            f"stable ties {stable_ties})"
        )
        print(
            "  interpretation: compare models using the stable wins above; "
            "all inconsistent cases remain conservative ties"
        )
    if flip_details:
        print("\nORDER-SENSITIVE CASES - inspect before changing a model or prompt:")
        print("=" * 74)
        for detail in flip_details:
            print(
                f"\n{detail['case']}   [{detail['matchup']}; "
                f"{detail['inconsistency_type']}]"
            )
            print(f"  request: {detail['query']}")
            print(
                f"  answer lengths: A={detail['chars_a']} chars, "
                f"B={detail['chars_b']} chars"
            )
            print(
                f"  forward (A={detail['name_a']}, B={detail['name_b']}) "
                f"-> original {detail['winner_forward']} "
                f"(slot {detail['slot_winner_forward']}): "
                f"{detail['reasoning_forward']}"
            )
            print(
                f"  reverse (A={detail['name_b']}, B={detail['name_a']}) "
                f"-> original {detail['winner_reverse']} "
                f"(slot {detail['slot_winner_reverse']}): "
                f"{detail['reasoning_reverse']}"
            )
    if total_skipped:
        print(f"skipped battles: {total_skipped} (external or errored arms)")
        for detail in skip_details:
            print(
                f"  {detail['case']} [{detail['matchup']}]: {detail['comment']} "
                f"(request: {detail['query']})"
            )
    record_component_report(
        BASELINE_CONFIG,
        layer="l3",
        metrics={
            "matchups": [
                {
                    "model_a": name_a,
                    "model_b": name_b,
                    "wins_a": wins_a,
                    "wins_b": wins_b,
                    "ties": ties,
                    "order_sensitive": flips,
                    "skipped": skipped,
                }
                for (
                    name_a,
                    name_b,
                    wins_a,
                    wins_b,
                    ties,
                    flips,
                    skipped,
                ) in pair_rows
            ],
            "leaderboard": {
                name: {
                    "wins": tally[name]["w"],
                    "losses": tally[name]["l"],
                    "ties": tally[name]["t"],
                    "win_rate": win_rate(tally[name]),
                }
                for name in LINEUP
            },
            "judge_stability": {
                "order_sensitive": total_flips,
                "winner_reversals": winner_reversal_count,
                "tie_boundary": tie_boundary_count,
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
    print()
    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
