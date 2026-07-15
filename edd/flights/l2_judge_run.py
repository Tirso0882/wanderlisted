"""EDD Layer 2 — run the JUDGES against the LIVE agent, over the DATASET.

The Layer-2 analog of flights/l1_run.py. Same skeleton — run the real agent over
every case, then aggregate — but the scorer is now an LLM judge, and the score
is a 0–3 rubric grade instead of a 0/1 pass/fail.

    capture (live agent = LLM + Duffel)  ->  Trajectory  ->  LLM judge  ->  0–3
       NON-DETERMINISTIC                       data         NON-DETERMINISTIC

Note the honest difference from Layer 1: here BOTH ends are non-deterministic
(the agent AND the judge). That's the cost of grading prose — and the reason
Layer 4 later calibrates the judge against human labels before you trust it.

We reuse everything: `run_agent` (harness), `DATASET` (the same golden cases),
and the `JUDGES` from flights/l2_judge.py — unchanged.

Run it (this DOES cost LLM calls — one agent run + two judge calls per case):
    .venv/bin/python edd/flights/l2_judge_run.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv()

# Trust the OS store (public certs + corporate proxy) the secure way.
import truststore  # noqa: E402

truststore.inject_into_ssl()
# Toggle: "false" = hermetic loop (just the scores); "true" = trace agent + judge.
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from edd.flights.l1_dataset import DATASET  # the SAME golden dataset as Layer 1
from edd.flights.l2_judge import JUDGES, build_judge  # the LLM judges
from edd.harness import run_agent  # shared "run + capture" machinery
from edd.models import MODELS  # shared model registry (single source of truth)
from src.agent.agents import FlightsAgent  # noqa: E402

# Which model's SUMMARY to judge — a key in edd/models.py. Swap in ONE word.
# The judge stays on the reasoning tier = a DIFFERENT model, as it should be.
AGENT = "terra"


def _fmt(value) -> str:
    """A set of airports -> 'EWR/JFK/LGA'; a string -> itself (display only)."""
    if isinstance(value, (set, frozenset)):
        return "/".join(sorted(value))
    return str(value)


async def main() -> None:
    print(
        f"\nFlights agent — LLM-as-judge (Layer 2) over {len(DATASET)} cases"
        f"   |   model: {AGENT} {MODELS[AGENT]}"
    )
    print("=" * 74)

    # 1) Capture every trajectory live (concurrently) on the chosen model.
    trajectories = await asyncio.gather(
        *(run_agent(FlightsAgent, case["query"], **MODELS[AGENT]) for case in DATASET)
    )

    # 2) Judge each trajectory with every judge. Build the grader ONCE; the
    #    per-tier semaphore inside get_llm keeps concurrency within rate limits.
    judge = build_judge()
    verdicts_per_case = await asyncio.gather(
        *(
            asyncio.gather(*(judge_fn(judge, traj) for judge_fn in JUDGES))
            for traj in trajectories
        )
    )

    # 3) Aggregate: mean rubric score per dimension (over cases that applied).
    score_sums: dict[str, int] = defaultdict(int)
    score_counts: dict[str, int] = defaultdict(int)

    for case, traj, verdicts in zip(DATASET, trajectories, verdicts_per_case):
        want = case["expected"]
        header = f"\n{_fmt(want['origin'])}->{_fmt(want['destination'])}"
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
    print("AGGREGATE — mean rubric score per dimension (higher is better):")
    for key in ("faithfulness", "helpfulness"):
        n = score_counts[key]
        summary = f"{score_sums[key] / n:.2f}/3   (n={n})" if n else "n/a"
        print(f"  {key:14s} {summary}")
    print()

    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
