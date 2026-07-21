"""Run Restaurant Layer 2 judges over cached live trajectories."""

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
from edd.models import MODELS  # noqa: E402
from edd.restaurants.l1_dataset import DATASET  # noqa: E402
from edd.restaurants.l2_judge import JUDGES, build_judge  # noqa: E402
from edd.restaurants.run_utils import (  # noqa: E402
    BASELINE_CONFIG,
    classify_restaurant_outcome,
    run_restaurant_dataset,
)

AGENT = "terra"
JUDGE_CASE_CONCURRENCY = 3


async def main() -> None:
    print(
        f"\nRestaurants agent - Layer 2 over {len(DATASET)} cases"
        f"   |   model: {AGENT} {MODELS[AGENT]}"
    )
    print("=" * 74)

    queries = [case["query"] for case in DATASET]
    trajectories = await run_restaurant_dataset(queries, model_config=MODELS[AGENT])
    judge = build_judge()
    judge_semaphore = asyncio.Semaphore(JUDGE_CASE_CONCURRENCY)

    async def judge_trajectory(trajectory, outcome: str):
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
            return await asyncio.gather(
                *(judge_fn(judge, trajectory) for judge_fn in JUDGES)
            )

    outcomes = [classify_restaurant_outcome(trajectory) for trajectory in trajectories]
    verdicts_per_case = await asyncio.gather(
        *(
            judge_trajectory(trajectory, outcome)
            for trajectory, outcome in zip(trajectories, outcomes)
        )
    )

    score_sums: dict[str, int] = defaultdict(int)
    score_counts: dict[str, int] = defaultdict(int)
    for case, trajectory, outcome, verdicts in zip(
        DATASET, trajectories, outcomes, verdicts_per_case
    ):
        print(f"\n{case['name']}   [task_outcome={outcome}]")
        if trajectory.error:
            print(f"    INFRA/PROVIDER ERROR: {trajectory.error}")
        for output in verdicts:
            if output["score"] is None:
                print(f"    {output['key']:14s} SKIP   {output['comment']}")
                continue
            score_sums[output["key"]] += output["score"]
            score_counts[output["key"]] += 1
            print(f"    {output['key']:14s} {output['score']}/3    {output['comment']}")

    print("\n" + "=" * 74)
    print("TASK OUTCOMES - provider/agent result categories:")
    for outcome, count in sorted(Counter(outcomes).items()):
        print(f"  {outcome:18s} {count}/{len(outcomes)}")
    print("\nAGGREGATE - mean rubric score per dimension:")
    for key in ("faithfulness", "helpfulness"):
        count = score_counts[key]
        summary = f"{score_sums[key] / count:.2f}/3   (n={count})" if count else "n/a"
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
