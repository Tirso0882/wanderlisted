"""EDD Step 3 — run evaluators against a live or cached agent DATASET.

Step 2 scored a hardcoded trajectory. Here we remove the training wheels with
the three changes we talked about:

  1. run_agent() (from edd/harness.py) — runs the REAL FlightsAgent and captures
     its trajectory (tool calls in the SAME shape the evaluators expect).
     This replaces the hardcoded literal from Step 2.
  2. DATASET               — replaces the single EXPECTED with several
     (query, expected) cases.
  3. the loop + AGGREGATE  — score every case with the SAME evaluators and
     total it up. That aggregate IS the eval of the system.

Note: the evaluators are imported UNCHANGED from edd/flights/l1_evaluate.py.
Nothing we built gets thrown away — only where the trajectory comes from.

Run it:
    .venv/bin/python edd/flights/l1_run.py

Set EDD_REFRESH=1 to force a fresh LLM + Duffel capture. Otherwise this runner
reuses the snapshot shared with Layers 2 and 3.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Trust the OS store (handles both public certs and the corporate proxy), and
# stay hermetic — this fast loop is about the SCORE, not tracing.
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
from edd.flights.l1_dataset import DATASET  # the golden dataset (its own file)
from edd.flights.l1_evaluate import EVALUATORS  # the SAME evaluators from Step 2
from edd.flights.run_utils import (
    BASELINE_CONFIG,
    classify_flight_outcome,
    run_flight_dataset,
)
from edd.models import MODELS  # shared model registry (single source of truth)

# Which model to evaluate — a key in edd/models.py. Swap in ONE word (no env edits).
# L1 grades one config per run (one dataset per thing-under-test); flip to
# "sol"/"luna" and re-run to score those.
AGENT = "terra"


def _fmt(value) -> str:
    """Display helper: a set of airports -> 'EWR/JFK/LGA'; a string -> itself."""
    if isinstance(value, (set, frozenset)):
        return "/".join(sorted(value))
    return str(value)


async def main() -> None:
    print(
        f"\nFlights agent — system eval (Layer 1) over {len(DATASET)} cases"
        f"   |   model: {AGENT} {MODELS[AGENT]}"
    )
    print("=" * 70)

    # Capture once per dataset/model/source fingerprint. Layer 2 and Layer 3
    # reuse this exact snapshot, so every metric refers to the same agent run.
    queries = [case["query"] for case in DATASET]
    trajectories = await run_flight_dataset(queries, model_config=MODELS[AGENT])

    names = [ev.__name__ for ev in EVALUATORS]
    passed = dict.fromkeys(names, 0)
    scored = dict.fromkeys(names, 0)  # cases where the check applied (score not None)
    evaluated = 0  # examples that actually ran (no infra error)
    perfect = 0  # examples where EVERY applicable check passed (exact match)
    outcomes = [classify_flight_outcome(trajectory) for trajectory in trajectories]

    for case, trajectory, outcome in zip(DATASET, trajectories, outcomes):
        want = case["expected"]
        if outcome in {"blocked_external", "infra_error"}:
            detail = f"   [ERROR: {trajectory.error}]" if trajectory.error else ""
            print(
                f"\n{_fmt(want['origin'])}->{_fmt(want['destination'])}"
                f"   [task_outcome={outcome}]   [NOT EVALUATED]{detail}"
            )
            continue
        evaluated += 1
        case_ok = True  # flips False on any FAIL -> drives decision_accuracy
        calls = trajectory.tool_calls
        got = next((c["args"] for c in calls if c["name"] == "search_flights"), {})
        print(
            f"\n{_fmt(want['origin'])}->{_fmt(want['destination'])}"
            f"   (agent chose {got.get('origin')}->{got.get('destination')})"
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
            print(f"    {out['key']:24s} {verdict}   {out['comment']}")

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
        print(f"    {name:24s} {summary}")

    # decision_accuracy = EXACT MATCH: % of examples where EVERY applicable check
    # passed. The single headline number; stricter than any per-field %.
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

    # If tracing is on, flush the background uploader before we exit — a short
    # script can otherwise drop its spans before they're sent.
    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
