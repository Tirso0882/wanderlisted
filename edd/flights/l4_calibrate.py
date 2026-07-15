"""EDD Layer 4 — CALIBRATE the judge: does it agree with a human?

Layers 2–3 built an LLM judge and then TRUSTED its scores. But an unchecked judge
is just another unverified component — maybe it's lenient, maybe it's harsh,
maybe it agrees with you no more than a coin flip would. Layer 4 is where that
trust is EARNED (or exposed): score a set of HUMAN-LABELED trajectories with the
judge and measure how tightly the judge's numbers track the human's.

    human label (ground truth)  ─┐
                                 ├─ compare ─> agreement metrics ─> trust / recalibrate
    LLM judge score (under test)─┘

THE MIRROR IMAGE OF LAYER 2.
    Layer 2: the trajectory was the input; the JUDGE was the thing you built.
    Layer 4: the JUDGE is the thing under test; the trajectories + human labels
             (edd/flights/l2_judge_cases.py) are the FIXED ground truth. You are
             now evaluating the evaluator.

THE METRICS (judge score vs human label, on the 0..3 faithfulness scale):
    • exact-match %  fraction the judge nailed exactly. Harsh: a 2-vs-3 miss
                     counts the same as 0-vs-3.
    • within-1 %     fraction within ±1 — "close enough" on an ordinal scale.
    • MAE            mean |judge − human|: average distance.
    • bias           mean (judge − human): the DIRECTION of the error.
                     +ve = judge too LENIENT, −ve = too HARSH. This is the number
                     that tells you HOW to fix the rubric.
    • Cohen's κ      agreement CORRECTED FOR CHANCE (quadratic-weighted for the
                     ordinal scale). Raw accuracy lies when labels are lopsided —
                     a judge that always says "3" looks great on a set of mostly
                     3s. κ subtracts the agreement you'd get by luck. 1 = perfect,
                     0 = chance, <0 = worse than chance.

THE LOOP (same discipline as every layer): a bad calibration is a signal to fix
the RUBRIC (the judge) and re-run — NEVER to bend the human labels to match the
judge. Once κ is high, you can trust the judge to score UNLABELED production
traffic at scale — which is the entire payoff of the eval stack.

REPEATABLE RECIPE — how you calibrate every OTHER subagent's judge:
    1. Collect 20–50 trajectories for that agent and hand-label each (ideally by
       several people; their agreement is the CEILING the judge can reach).
    2. Point this script's judge + case set at that agent.
    3. Read κ + bias. High κ, ~0 bias -> trust it. Low κ / non-zero bias ->
       rewrite the rubric in the biased direction and re-run.

Run it:
    .venv/bin/python edd/flights/l4_calibrate.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import truststore  # noqa: E402  (trust the OS store; never disable verification)

truststore.inject_into_ssl()
os.environ.setdefault("LANGSMITH_TRACING", "false")  # hermetic — just the metrics
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from edd.flights.l2_judge import build_judge, judge_faithfulness  # noqa: E402
from edd.flights.l2_judge_cases import JUDGE_CASES  # noqa: E402

SCALE = (0, 1, 2, 3)  # the faithfulness rubric's ordinal categories


def quadratic_weighted_kappa(
    humans: list[int], judges: list[int], categories: tuple[int, ...] = SCALE
) -> float | None:
    """Cohen's κ with quadratic weights — chance-corrected agreement on an ORDINAL
    scale, in pure Python (no numpy).

    Quadratic weights make a 0-vs-3 disagreement count far more than a 2-vs-3 one,
    which is what you want for graded scores. Returns None when κ is undefined
    (every label or every judgment collapses into one category, so there is no
    chance disagreement to correct for).
    """
    k = len(categories)
    pos = {c: i for i, c in enumerate(categories)}
    n = len(humans)
    if n == 0:
        return None
    obs = [[0] * k for _ in range(k)]
    for h, j in zip(humans, judges):
        obs[pos[h]][pos[j]] += 1
    row = [sum(obs[a]) for a in range(k)]  # human marginals
    col = [sum(obs[a][b] for a in range(k)) for b in range(k)]  # judge marginals
    # quadratic DISAGREEMENT weights: 0 on the diagonal, 1 at the extremes.
    weight = [[((a - b) ** 2) / ((k - 1) ** 2) for b in range(k)] for a in range(k)]
    observed = sum(weight[a][b] * obs[a][b] for a in range(k) for b in range(k))
    expected = sum(
        weight[a][b] * row[a] * col[b] / n for a in range(k) for b in range(k)
    )
    if expected == 0:  # no expected disagreement -> κ undefined
        return None
    return 1 - observed / expected


def kappa_band(kappa: float | None) -> str:
    """Landis–Koch strength-of-agreement label for a κ value."""
    if kappa is None:
        return "undefined — labels too degenerate (add more/spread cases)"
    if kappa < 0:
        return "worse than chance"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "almost perfect"


async def main() -> None:
    print(
        f"\nJudge calibration (Layer 4) — faithfulness judge vs "
        f"{len(JUDGE_CASES)} human labels"
    )
    print("=" * 74)

    # The judge UNDER TEST is the very one Layer 2 uses — calibrate what you ship.
    judge = build_judge()
    outs = await asyncio.gather(
        *(judge_faithfulness(judge, c["trajectory"]) for c in JUDGE_CASES)
    )

    humans: list[int] = []
    judges: list[int] = []
    print(f"\n{'case':30s} {'human':>5s} {'judge':>5s} {'Δ':>3s}  note")
    print("-" * 74)
    for case, out in zip(JUDGE_CASES, outs):
        h = case["expected"]
        j = out["score"]
        if j is None:  # judge infra error -> keep it out of the stats
            print(f"{case['name']:30s} {h:>5d} {'ERR':>5s}       {out['comment']}")
            continue
        humans.append(h)
        judges.append(j)
        flag = "" if h == j else ("lenient" if j > h else "harsh")
        print(f"{case['name']:30s} {h:>5d} {j:>5d} {j - h:>+3d}  {flag}")

    n = len(humans)
    print("\n" + "=" * 74)
    if not n:
        print("no scored cases (every judge call errored)")
        wait_for_all_tracers()
        return

    exact = sum(h == j for h, j in zip(humans, judges)) / n
    within1 = sum(abs(h - j) <= 1 for h, j in zip(humans, judges)) / n
    mae = sum(abs(h - j) for h, j in zip(humans, judges)) / n
    bias = sum(j - h for h, j in zip(humans, judges)) / n
    kappa = quadratic_weighted_kappa(humans, judges)

    if bias > 0.05:
        bias_word = "lenient — scores HIGHER than humans"
    elif bias < -0.05:
        bias_word = "harsh — scores LOWER than humans"
    else:
        bias_word = "no directional bias"

    print("CALIBRATION — does the judge agree with the humans?")
    print(f"  exact match      {exact:>5.0%}")
    print(f"  within ±1        {within1:>5.0%}")
    print(f"  mean abs error   {mae:>5.2f}   (0 = perfect, 3 = worst)")
    print(f"  bias             {bias:>+5.2f}   {bias_word}")
    kstr = f"{kappa:.2f}" if kappa is not None else "n/a"
    print(f"  Cohen's κ (qwk)  {kstr:>5s}   {kappa_band(kappa)}")

    print()
    if kappa is not None and kappa >= 0.60 and abs(bias) < 0.5:
        print("VERDICT: the judge tracks the humans — trust it to score UNLABELED")
        print("         production traffic. Re-calibrate whenever the rubric changes.")
    else:
        if bias > 0.05:
            fix = "TIGHTEN the FAITHFULNESS rubric (it over-credits)"
        elif bias < -0.05:
            fix = "LOOSEN/CLARIFY the FAITHFULNESS rubric (it over-penalizes)"
        else:
            fix = "SHARPEN the rubric's 0/1/2/3 anchors (scores are scattered)"
        print(f"VERDICT: not yet trustworthy — {fix} in")
        print("         l2_judge.py and re-run. Fix the JUDGE, never the labels.")

    print(
        "\nReminder: n is tiny and one person set these labels — the borderline\n"
        "cases are debatable BY DESIGN. Real calibration wants 20–50 cases and\n"
        "SEVERAL labelers (their mutual agreement is the ceiling the judge can hit).\n"
    )
    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
