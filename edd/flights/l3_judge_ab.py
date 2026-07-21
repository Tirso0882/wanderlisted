"""EDD — A/B test the JUDGE on HARD, labeled inputs: does effort change its grades?

Round 1 A/B'd the judge on LIVE agent output and got Δ=0 everywhere — but those
answers were easy, and a judge only earns its effort on BORDERLINE calls. A
faithful agent won't produce a borderline answer on demand, so we switch the
INPUT: hand-crafted, human-LABELED trajectories at graded difficulty
(edd/flights/l2_judge_cases.py), including two with one subtly-unsupported detail.

Still the one rule of A/B — vary exactly ONE thing. The trajectories are fixed
data, so the ONLY difference between the two runs is the judge's reasoning effort.

Because every case carries a human label (the correct score), we get to ask TWO
questions, not one:
  1. Does higher effort CHANGE the grade?         (Δ per case)
  2. Is higher effort CLOSER to the human label?  (calibration — a taste of Layer 4)

Run it:
    .venv/bin/python edd/flights/l3_judge_ab.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import truststore  # noqa: E402  (trust the OS store; never disable verification)

truststore.inject_into_ssl()
os.environ["LANGSMITH_TRACING"] = "false"  # hermetic — just the scores
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from edd.flights.l2_judge import build_judge, judge_faithfulness
from edd.flights.l2_judge_cases import JUDGE_CASES

ARM_A = "medium"  # the current default judge effort
ARM_B = "high"  # the challenger


async def main() -> None:
    print(
        f"\nJudge A/B on labeled fixtures — faithfulness, effort {ARM_A} (A) vs "
        f"{ARM_B} (B), {len(JUDGE_CASES)} cases"
    )
    print("=" * 78)

    # Two judges that differ ONLY in reasoning effort. The trajectories are fixed
    # data (edd/flights/l2_judge_cases.py), so effort is the single varied factor.
    judge_a = build_judge(effort=ARM_A)
    judge_b = build_judge(effort=ARM_B)

    verdicts_a = await asyncio.gather(
        *(judge_faithfulness(judge_a, c["trajectory"]) for c in JUDGE_CASES)
    )
    verdicts_b = await asyncio.gather(
        *(judge_faithfulness(judge_b, c["trajectory"]) for c in JUDGE_CASES)
    )

    print(
        f"\n{'case':26s} {'label':>5s} {'med':>4s} {'high':>5s} {'Δ':>4s}"
        f"  {'med=label':>10s} {'high=label':>11s}"
    )
    print("-" * 78)

    sum_a = sum_b = hits_a = hits_b = n = 0
    borderline: list[tuple[str, int, dict, dict]] = []

    for case, va, vb in zip(JUDGE_CASES, verdicts_a, verdicts_b):
        exp = case["expected"]
        sa, sb = va["score"], vb["score"]
        if sa is None or sb is None:  # judge infra error -> keep it out of the stats
            print(f"{case['name']:26s} {exp:>5d}   [judge error]")
            continue
        n += 1
        sum_a += sa
        sum_b += sb
        hits_a += sa == exp
        hits_b += sb == exp
        print(
            f"{case['name']:26s} {exp:>5d} {sa:>4d} {sb:>5d} {sb - sa:>+4d}"
            f"  {('yes' if sa == exp else 'no'):>10s} {('yes' if sb == exp else 'no'):>11s}"
        )
        if case["name"].startswith("borderline"):
            borderline.append((case["name"], exp, va, vb))

    print("\n" + "=" * 78)
    if n:
        print(
            f"AGGREGATE   mean: {ARM_A}={sum_a / n:.2f}  {ARM_B}={sum_b / n:.2f}"
            f"   |   agrees with human label: {ARM_A} {hits_a}/{n}  {ARM_B} {hits_b}/{n}"
        )

    # On borderline calls the REASONING is the point — show how each arm justified it.
    for name, exp, va, vb in borderline:
        print(f"\nWHY — {name} (human label {exp}):")
        print(f"  {ARM_A} scored {va['score']}: {va['comment']}")
        print(f"  {ARM_B} scored {vb['score']}: {vb['comment']}")

    print(
        "\nReminder: n=4 and a non-deterministic judge — read Δ and the match-counts"
        "\nas a hint, not proof. Formalizing this agreement IS Layer 4.\n"
    )

    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
