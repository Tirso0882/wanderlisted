"""Run Transportation Layer 1 evaluators against live, cached trajectories."""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
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
from edd.transportation.l1_dataset import DATASET  # noqa: E402
from edd.transportation.l1_evaluate import EVALUATORS  # noqa: E402
from edd.transportation.run_utils import (  # noqa: E402
    BASELINE_CONFIG,
    classify_transportation_outcome,
    run_transportation_dataset,
)

AGENT = "terra"


async def main() -> None:
    print(
        f"\nTransportation agent - Layer 1 over {len(DATASET)} cases"
        f"   |   model: {AGENT} {MODELS[AGENT]}"
    )
    print("=" * 74)

    queries = [case["query"] for case in DATASET]
    trajectories = await run_transportation_dataset(queries, model_config=MODELS[AGENT])

    names = [evaluator.__name__ for evaluator in EVALUATORS]
    passed = dict.fromkeys(names, 0)
    scored = dict.fromkeys(names, 0)
    evaluated = 0
    perfect = 0
    outcomes = [
        classify_transportation_outcome(trajectory) for trajectory in trajectories
    ]

    for case, trajectory, outcome in zip(DATASET, trajectories, outcomes):
        print(f"\n{case['name']}   [task_outcome={outcome}]")
        if trajectory.error:
            print(f"    INFRA/PROVIDER ERROR: {trajectory.error}")
            continue
        evaluated += 1
        case_ok = True
        for evaluator in EVALUATORS:
            output = evaluator(trajectory.tool_calls, case["expected"])
            score = output["score"]
            if score is None:
                verdict = "SKIP"
            else:
                scored[evaluator.__name__] += 1
                passed[evaluator.__name__] += score
                if not score:
                    case_ok = False
                verdict = "PASS" if score else "FAIL"
            print(f"    {output['key']:30s} {verdict}   {output['comment']}")
        perfect += int(case_ok)

    print("\n" + "=" * 74)
    print("TASK OUTCOMES - separate from decision correctness:")
    for outcome, count in sorted(Counter(outcomes).items()):
        print(f"  {outcome:18s} {count}/{len(outcomes)}")

    print("\nAGGREGATE - per-decision checks:")
    for name in names:
        count = scored[name]
        summary = (
            f"{passed[name]}/{count}  ({passed[name] / count * 100:.0f}%)"
            if count
            else "n/a"
        )
        print(f"  {name:30s} {summary}")
    if evaluated:
        print(
            f"\n  decision_accuracy (exact match): {perfect}/{evaluated}  "
            f"({perfect / evaluated * 100:.0f}%)"
        )
    record_component_report(
        BASELINE_CONFIG,
        layer="l1",
        metrics={
            "task_outcomes": dict(sorted(Counter(outcomes).items())),
            "evaluated_cases": evaluated,
            "per_check": {
                name: {
                    "passed": passed[name],
                    "scored": scored[name],
                    "rate": passed[name] / scored[name] if scored[name] else None,
                }
                for name in names
            },
            "decision_accuracy": {
                "passed": perfect,
                "scored": evaluated,
                "rate": perfect / evaluated if evaluated else None,
            },
        },
        queries=queries,
        model_configs={AGENT: MODELS[AGENT]},
        report_source_files=(
            Path(__file__),
            Path(__file__).with_name("l1_evaluate.py"),
        ),
    )
    print()
    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
