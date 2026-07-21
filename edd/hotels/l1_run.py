"""EDD Layer 1 — run the HOTELS evaluators against the LIVE agent, over the DATASET.

Run the real HotelsAgent on each query,
capture its trajectory, score the DECISION with the pure evaluators, aggregate.
Same skeleton — only the agent, dataset, and evaluators are the hotel versions;
`harness.py` and `models.py` are reused UNCHANGED.

Run it:
    .venv/bin/python edd/hotels/l1_run.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Trust the OS store (public certs + corporate proxy); stay hermetic (just score).
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
from edd.hotels.l1_dataset import DATASET  # the hotels golden dataset
from edd.hotels.l1_evaluate import (  # the hotels evaluators
    EVALUATORS,
    required_rechecks_completed,
)
from edd.hotels.run_utils import (
    BASELINE_CONFIG,
    classify_hotel_outcome,
    run_hotel_dataset,
)
from edd.models import MODELS  # shared model registry (single source of truth)

# Which model to evaluate — a key in edd/models.py. Swap in ONE word.
AGENT = "terra"


def _fmt(value) -> str:
    """Display helper: a set of city codes -> 'PAR'; a string -> itself."""
    if isinstance(value, (set, frozenset)):
        return "/".join(sorted(value))
    return str(value)


async def main() -> None:
    print(
        f"\nHotels agent — system eval (Layer 1) over {len(DATASET)} cases"
        f"   |   model: {AGENT} {MODELS[AGENT]}"
    )
    print("=" * 70)

    # Hotel runs fan out to several Places calls. Bound case-level concurrency
    # so the eval does not manufacture Hotelbeds 429s or agent timeouts.
    queries = [case["query"] for case in DATASET]
    trajectories = await run_hotel_dataset(queries, model_config=MODELS[AGENT])

    names = [ev.__name__ for ev in EVALUATORS]
    passed = dict.fromkeys(names, 0)
    scored = dict.fromkeys(names, 0)  # cases where the check applied (score not None)
    evaluated = 0  # examples that actually ran (no infra error)
    perfect = 0  # examples where EVERY applicable check passed (exact match)
    recheck_passed = 0
    recheck_scored = 0
    outcomes = [classify_hotel_outcome(trajectory) for trajectory in trajectories]

    for case, trajectory, outcome in zip(DATASET, trajectories, outcomes):
        want = case["expected"]
        if trajectory.error:
            print(f"\n{_fmt(want['city'])}   [INFRA ERROR: {trajectory.error}]")
            continue
        evaluated += 1
        case_ok = True  # flips False on any FAIL -> drives decision_accuracy
        calls = trajectory.tool_calls
        got = next(
            (c["args"] for c in calls if c["name"] == "search_hotels_hotelbeds"), {}
        )
        print(
            f"\n{_fmt(want['city'])}   (agent chose {got.get('city_code')})"
            f"   [task_outcome={outcome}]"
        )
        for ev in EVALUATORS:
            out = ev(calls, want)
            score = out["score"]
            if score is None:
                verdict = "SKIP"  # this case didn't specify anything to check
            else:
                scored[ev.__name__] += 1
                if score:
                    passed[ev.__name__] += 1
                else:
                    case_ok = False  # one FAIL -> not an exact-match example
                verdict = "PASS" if score else "FAIL"
            print(f"    {out['key']:22s} {verdict}   {out['comment']}")
        recheck = required_rechecks_completed(trajectory)
        if recheck["score"] is None:
            recheck_verdict = "SKIP"
        else:
            recheck_scored += 1
            recheck_passed += recheck["score"]
            if not recheck["score"]:
                case_ok = False
            recheck_verdict = "PASS" if recheck["score"] else "FAIL"
        print(f"    {recheck['key']:29s} {recheck_verdict}   {recheck['comment']}")
        perfect += int(case_ok)

    print("\n" + "=" * 70)
    print("TASK OUTCOMES — separate from decision correctness:")
    for outcome, count in sorted(Counter(outcomes).items()):
        print(f"  {outcome:18s} {count}/{len(outcomes)}")
    print()
    print("AGGREGATE — this is your eval of the system:")
    print("\n  Per-check (which individual decisions were right):")
    for name in names:
        n = scored[name]
        summary = f"{passed[name]}/{n}  ({passed[name] / n * 100:.0f}%)" if n else "n/a"
        print(f"    {name:22s} {summary}")
    recheck_summary = (
        f"{recheck_passed}/{recheck_scored}  "
        f"({recheck_passed / recheck_scored * 100:.0f}%)"
        if recheck_scored
        else "n/a"
    )
    print(f"    {'required_rechecks_completed':29s} {recheck_summary}")

    if evaluated:
        print(
            f"\n  decision_accuracy (exact match): {perfect}/{evaluated}  "
            f"({perfect / evaluated * 100:.0f}%)"
        )
    per_check = {
        name: {
            "passed": passed[name],
            "scored": scored[name],
            "rate": passed[name] / scored[name] if scored[name] else None,
        }
        for name in names
    }
    per_check["required_rechecks_completed"] = {
        "passed": recheck_passed,
        "scored": recheck_scored,
        "rate": recheck_passed / recheck_scored if recheck_scored else None,
    }
    record_component_report(
        BASELINE_CONFIG,
        layer="l1",
        metrics={
            "task_outcomes": dict(sorted(Counter(outcomes).items())),
            "evaluated_cases": evaluated,
            "per_check": per_check,
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
