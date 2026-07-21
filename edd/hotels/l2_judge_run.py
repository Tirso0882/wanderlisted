"""EDD Layer 2 — run the HOTELS JUDGES against the LIVE agent, over the DATASET.

The hotel analog of edd/flights/l2_judge_run.py. Same skeleton — run the real
HotelsAgent over every Layer-1 case, then grade each answer with the LLM judges —
but the score is a 0-3 rubric grade instead of a 0/1 pass/fail.

    capture (live agent = LLM + Hotelbeds)  ->  Trajectory  ->  LLM judge  ->  0-3
       NON-DETERMINISTIC                          data          NON-DETERMINISTIC

Both ends are non-deterministic (the agent AND the judge) — which is exactly why
Layer 4 calibrates the judge against human labels before you trust these numbers.

Run it (one agent run + two judge calls per case):
    .venv/bin/python edd/hotels/l2_judge_run.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter, defaultdict
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
from edd.hotels.l1_dataset import DATASET  # the SAME golden dataset as Layer 1
from edd.hotels.l2_judge import JUDGES, build_judge  # the hotel LLM judges
from edd.hotels.run_utils import (
    BASELINE_CONFIG,
    classify_hotel_outcome,
    run_hotel_dataset,
)
from edd.models import MODELS  # shared model registry (single source of truth)

# Which model's SUMMARY to judge — a key in edd/models.py. Swap in ONE word.
# The judge stays on the reasoning tier = a DIFFERENT model, as it should be.
AGENT = "terra"
JUDGE_CASE_CONCURRENCY = 3


def _fmt(value) -> str:
    """A set of city codes -> 'PAR'; a string -> itself (display only)."""
    if isinstance(value, (set, frozenset)):
        return "/".join(sorted(value))
    return str(value)


async def main() -> None:
    print(
        f"\nHotels agent — LLM-as-judge (Layer 2) over {len(DATASET)} cases"
        f"   |   model: {AGENT} {MODELS[AGENT]}"
    )
    print("=" * 74)

    # 1) Capture every trajectory with bounded case-level concurrency. One hotel
    #    case can fan out to 3-5 Places calls; unbounded batches create 429 noise.
    queries = [case["query"] for case in DATASET]
    trajectories = await run_hotel_dataset(queries, model_config=MODELS[AGENT])

    # 2) Judge each trajectory with every judge. Build the grader ONCE; the
    #    per-tier semaphore inside get_llm keeps concurrency within rate limits.
    judge = build_judge()
    judge_semaphore = asyncio.Semaphore(JUDGE_CASE_CONCURRENCY)

    async def judge_trajectory(traj, outcome: str):
        if outcome in {"blocked_external", "infra_error"}:
            return [
                {
                    "key": judge_fn.__name__.removeprefix("judge_"),
                    "score": None,
                    "comment": f"not evaluated: task outcome is {outcome}",
                }
                for judge_fn in JUDGES
            ]
        async with judge_semaphore:
            return await asyncio.gather(*(judge_fn(judge, traj) for judge_fn in JUDGES))

    outcomes = [classify_hotel_outcome(traj) for traj in trajectories]
    verdicts_per_case = await asyncio.gather(
        *(
            judge_trajectory(traj, outcome)
            for traj, outcome in zip(trajectories, outcomes)
        )
    )

    # 3) Aggregate: mean rubric score per dimension (over cases that applied).
    score_sums: dict[str, int] = defaultdict(int)
    score_counts: dict[str, int] = defaultdict(int)

    for case, traj, outcome, verdicts in zip(
        DATASET, trajectories, outcomes, verdicts_per_case
    ):
        want = case["expected"]
        header = f"\n{_fmt(want['city'])}   [task_outcome={outcome}]"
        if traj.error:
            print(f"{header}   [INFRA ERROR: {traj.error}]")
            continue
        print(header)
        for out in verdicts:
            if out["score"] is None:
                print(f"    {out['key']:14s} SKIP   {out['comment']}")
                continue
            score_sums[out["key"]] += out["score"]
            score_counts[out["key"]] += 1
            print(f"    {out['key']:14s} {out['score']}/3    {out['comment']}")

    print("\n" + "=" * 74)
    print("TASK OUTCOMES — provider/agent result categories:")
    for outcome, count in sorted(Counter(outcomes).items()):
        print(f"  {outcome:18s} {count}/{len(outcomes)}")
    print()
    print("AGGREGATE — mean rubric score per dimension (higher is better):")
    for key in ("faithfulness", "helpfulness"):
        n = score_counts[key]
        summary = f"{score_sums[key] / n:.2f}/3   (n={n})" if n else "n/a"
        print(f"  {key:14s} {summary}")
    record_component_report(
        BASELINE_CONFIG,
        layer="l2",
        metrics={
            "task_outcomes": dict(sorted(Counter(outcomes).items())),
            "rubric_scores": {
                key: {
                    "score_sum": score_sums[key],
                    "scored": score_counts[key],
                    "mean": (
                        score_sums[key] / score_counts[key]
                        if score_counts[key]
                        else None
                    ),
                }
                for key in ("faithfulness", "helpfulness")
            },
        },
        queries=queries,
        model_configs={AGENT: MODELS[AGENT]},
        context={"judge_config": {"tier": "reasoning", "effort": "tier_default"}},
        report_source_files=(
            Path(__file__),
            Path(__file__).with_name("l2_judge.py"),
            Path(__file__).resolve().parents[1] / "rubrics.py",
        ),
    )
    print()

    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
