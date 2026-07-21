"""Shared Layer-4 calibration — does a judge's score agree with a human's?

The rubric scaffold (edd/rubrics.py) makes every agent's JUDGE consistent; this
module makes every agent's CALIBRATION consistent. Point `run_calibration()` at
any agent's `build_judge` + `judge_faithfulness` + labeled `JUDGE_CASES` and it
reports the same five agreement metrics and the same fix-the-rubric verdict — so
calibrating a new agent is one call, not a copied 120-line script.

THE METRICS (judge score vs human label, on the 0..3 ordinal faithfulness scale):
    • exact-match %  fraction the judge nailed exactly.
    • within-1 %     fraction within ±1 — "close enough" on an ordinal scale.
    • MAE            mean |judge − human|: average distance.
    • bias           mean (judge − human): DIRECTION of the error. +ve = judge too
                     LENIENT, −ve = too HARSH — the number that tells you how to
                     fix the rubric.
    • Cohen's κ      agreement CORRECTED FOR CHANCE (quadratic-weighted for the
                     ordinal scale). 1 = perfect, 0 = chance, <0 = worse than chance.

THE LOOP (same discipline as every layer): a bad calibration is a signal to fix
the RUBRIC and re-run — NEVER to bend the human labels to match the judge.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from edd.baseline_store import (
    content_sha256,
    record_baseline_report,
    source_hashes,
)

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


async def run_calibration(
    *,
    build_judge,
    judge_faithfulness,
    cases: list[dict],
    agent: str,
    rubric_module: str,
    categories: tuple[int, ...] = SCALE,
) -> dict:
    """Score `cases` with the agent's faithfulness judge, print the agreement
    table + verdict, and return the metrics dict (for tests / programmatic use).

    Args:
        build_judge: the agent's build_judge (the very judge Layer 2 ships).
        judge_faithfulness: the agent's async faithfulness scorer.
        cases: list of {"name", "expected", "trajectory", ...} labeled cases.
        agent: display name, e.g. "Hotels".
        rubric_module: path shown in the fix-it verdict, e.g. "edd/hotels/l2_judge.py".
    """
    print(
        f"\n{agent} judge calibration (Layer 4) — faithfulness judge vs "
        f"{len(cases)} human labels"
    )
    print("=" * 74)

    # The judge UNDER TEST is the very one Layer 2 uses — calibrate what you ship.
    judge = build_judge()
    outs = await asyncio.gather(
        *(judge_faithfulness(judge, c["trajectory"]) for c in cases)
    )

    humans: list[int] = []
    judges: list[int] = []
    print(f"\n{'case':30s} {'human':>5s} {'judge':>5s} {'Δ':>3s}  note")
    print("-" * 74)
    case_results: list[dict] = []
    for case, out in zip(cases, outs):
        h = case["expected"]
        j = out["score"]
        if j is None:  # judge infra error -> keep it out of the stats
            print(f"{case['name']:30s} {h:>5d} {'ERR':>5s}       {out['comment']}")
            case_results.append(
                {
                    "name": case["name"],
                    "human": h,
                    "judge": None,
                    "delta": None,
                    "comment": out["comment"],
                }
            )
            continue
        humans.append(h)
        judges.append(j)
        case_results.append(
            {
                "name": case["name"],
                "human": h,
                "judge": j,
                "delta": j - h,
                "comment": out["comment"],
            }
        )
        flag = "" if h == j else ("lenient" if j > h else "harsh")
        print(f"{case['name']:30s} {h:>5d} {j:>5d} {j - h:>+3d}  {flag}")

    n = len(humans)
    print("\n" + "=" * 74)
    if not n:
        print("no scored cases (every judge call errored)")
        metrics = {"n": 0, "case_results": case_results}
        _record_calibration_baseline(
            agent=agent,
            rubric_module=rubric_module,
            cases=cases,
            metrics=metrics,
        )
        return metrics

    exact = sum(h == j for h, j in zip(humans, judges)) / n
    within1 = sum(abs(h - j) <= 1 for h, j in zip(humans, judges)) / n
    mae = sum(abs(h - j) for h, j in zip(humans, judges)) / n
    bias = sum(j - h for h, j in zip(humans, judges)) / n
    kappa = quadratic_weighted_kappa(humans, judges, categories)

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
        print(f"         {rubric_module} and re-run. Fix the JUDGE, never the labels.")

    print(
        "\nReminder: n is tiny and one person set these labels — the borderline\n"
        "cases are debatable BY DESIGN. Real calibration wants 20–50 cases and\n"
        "SEVERAL labelers (their mutual agreement is the ceiling the judge can hit).\n"
    )
    metrics = {
        "n": n,
        "exact": exact,
        "within1": within1,
        "mae": mae,
        "bias": bias,
        "kappa": kappa,
        "case_results": case_results,
    }
    _record_calibration_baseline(
        agent=agent,
        rubric_module=rubric_module,
        cases=cases,
        metrics=metrics,
    )
    return metrics


def _record_calibration_baseline(
    *,
    agent: str,
    rubric_module: str,
    cases: list[dict],
    metrics: dict,
) -> None:
    root = Path(__file__).resolve().parents[1]
    rubric_path = root / rubric_module
    case_identity = [
        {
            "name": case["name"],
            "expected": case["expected"],
            "trajectory": asdict(case["trajectory"]),
        }
        for case in cases
    ]
    record_baseline_report(
        component=agent.lower(),
        layer="l4",
        metrics=metrics,
        context={
            "calibration_case_count": len(cases),
            "calibration_cases_sha256": content_sha256(case_identity),
            "rubric_module": rubric_module,
            "judge_config": {"tier": "reasoning", "effort": "tier_default"},
            "report_sources": source_hashes(
                (
                    Path(__file__),
                    root / "edd" / "rubrics.py",
                    rubric_path,
                )
            ),
        },
    )
