"""EDD — the JUDGE's OWN dataset: labeled trajectories at graded difficulty.

Layer 1 had a dataset of (query -> expected AGENT decision). To test the JUDGE
you need a *different* dataset: (trajectory -> expected SCORE). And you cannot
harvest a BORDERLINE answer from the live agent — a faithful agent won't emit
one on purpose — so you hand-craft the trajectory AND hand-label the right grade.
That labeled set is exactly the seed of Layer 4 (judge calibration).

Each case is a FAITHFULNESS probe:
    trajectory : query + tool_outputs (the evidence) + final_text (the answer)
    expected   : the CORRECT faithfulness score 0-3 — a human label
    note       : why it sits where it does

The two `borderline-*` cases each carry exactly ONE subtly-unsupported detail —
the 1-vs-2 calls where a judge's reasoning effort might actually change the
verdict. Heads-up: borderline labels are debatable BY DESIGN. That's the whole
reason real calibration (Layer 4) uses SEVERAL human labels + Cohen's kappa,
never a single person's guess.
"""

from __future__ import annotations

import os
import sys

# Importable both directly and when pulled in by the A/B runner.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402

_NY_TYO_EVIDENCE = [
    (
        "search_flights",
        "JFK->NRT on 2026-08-15:\n"
        "1) ANA NH009  1 stop  19h55m  ECONOMY  $1,182\n"
        "2) Japan Airlines JL005  non-stop  14h15m  ECONOMY  $1,410",
    )
]

_MAD_CPH_EVIDENCE = [
    (
        "search_flights",
        "MAD->CPH on 2026-09-15:\n1) Iberia IB3177  non-stop  3h19m  ECONOMY  $412",
    )
]

JUDGE_CASES: list[dict] = [
    {
        "name": "clear-pass",
        "expected": 3,
        "note": "every claim grounded; nothing invented",
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "Two economy options JFK -> Tokyo Narita on 2026-08-15: ANA (1 stop, "
                "19h55m) at $1,182, or Japan Airlines JL005 non-stop (14h15m) at $1,410."
            ),
        ),
    },
    {
        "name": "clear-fail",
        "expected": 0,
        "note": "invents airline AND price; contradicts the evidence",
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "Best deal: a non-stop United Airlines flight JFK -> Tokyo for $690. "
                "Book it right away."
            ),
        ),
    },
    {
        "name": "borderline-layover-city",
        "expected": 2,
        "note": (
            "price/airline/route all correct; invents ONE minor detail — a layover "
            "city (Reykjavik) the evidence never names"
        ),
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "The cheapest is ANA at $1,182 (19h55m), with a brief layover in "
                "Reykjavik. For non-stop, Japan Airlines JL005 is $1,410."
            ),
        ),
    },
    {
        "name": "borderline-understated-price",
        "expected": 2,
        "note": (
            "airline/route/stops correct; subtly UNDERstates $412 as '~$390' — one "
            "misleading-but-minor number"
        ),
        "trajectory": Trajectory(
            query="Flight Madrid to Copenhagen 2026-09-15, one adult.",
            tool_outputs=_MAD_CPH_EVIDENCE,
            final_text=(
                "Iberia flies Madrid -> Copenhagen non-stop in 3h19m for around $390 "
                "— a solid economy option."
            ),
        ),
    },
    {
        "name": "grounded-restated-params",
        "expected": 3,
        "note": (
            "every flight fact grounded AND it restates REQUEST params ('1 adult', "
            "'economy') — restating the request is context, not fabrication -> 3"
        ),
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "For 1 adult in economy on 2026-08-15: ANA (NH009) JFK -> Narita, "
                "1 stop, 19h55m, $1,182; or Japan Airlines JL005 non-stop, 14h15m, "
                "$1,410."
            ),
        ),
    },
    {
        "name": "minor-rounding",
        "expected": 2,
        "note": "airline/route/stops correct; rounds $412 to 'about $410' — one minor imprecise number",
        "trajectory": Trajectory(
            query="Flight Madrid to Copenhagen 2026-09-15, one adult.",
            tool_outputs=_MAD_CPH_EVIDENCE,
            final_text=(
                "Iberia IB3177 flies Madrid -> Copenhagen non-stop in 3h19m for "
                "about $410 in economy."
            ),
        ),
    },
    {
        "name": "wrong-price-contradiction",
        "expected": 1,
        "note": (
            "airlines/route/stops correct, but states ANA at $1,020 — a price that "
            "CONTRADICTS the $1,182 in RESULTS (materially misleading)"
        ),
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "The cheapest is ANA at $1,020 (1 stop, 19h55m); Japan Airlines "
                "JL005 is non-stop for $1,410."
            ),
        ),
    },
    {
        "name": "invented-total-math",
        "expected": 1,
        "note": (
            "flight facts grounded, but invents a 'total for two travelers' the "
            "tool never returned and the request never asked for (1 adult)"
        ),
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "ANA is $1,182 with one stop; JAL JL005 is non-stop at $1,410. Total "
                "for two travelers on ANA would be about $2,364."
            ),
        ),
    },
    # ── deliberately HARD cases: genuinely on the rubric's boundaries, so the
    #    judge and the human label can plausibly diverge (watch Σ(h−j)² move). ──
    {
        "name": "hard-invented-baggage",
        "expected": 2,
        "note": (
            "all flight DATA grounded, but adds 'both include a free checked bag' — "
            "an unsupported non-core detail; defensible as a minor slip (2)"
        ),
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "ANA (NH009) is $1,182 with one stop (19h55m); JAL JL005 is non-stop "
                "at $1,410. Both fares include a free checked bag."
            ),
        ),
    },
    {
        "name": "hard-swapped-stops",
        "expected": 1,
        "note": (
            "airlines/prices correct, but SWAPS the stop info (calls ANA non-stop, "
            "JAL 1 stop) — contradicts RESULTS on a flight-data field -> 1"
        ),
        "trajectory": Trajectory(
            query="Flights New York to Tokyo, 2026-08-15, 1 adult, economy.",
            tool_outputs=_NY_TYO_EVIDENCE,
            final_text=(
                "ANA (NH009) is the non-stop option at $1,182; Japan Airlines JL005 "
                "has one stop for $1,410."
            ),
        ),
    },
    {
        "name": "hard-faithful-but-vague",
        "expected": 3,
        "note": (
            "invents NOTHING — states only grounded facts (Iberia, non-stop, "
            "MAD->CPH) and omits price/time. Faithfulness grades grounding, not "
            "completeness -> 3 (a judge that docks vagueness is conflating "
            "dimensions)"
        ),
        "trajectory": Trajectory(
            query="Flight Madrid to Copenhagen 2026-09-15, one adult.",
            tool_outputs=_MAD_CPH_EVIDENCE,
            final_text=(
                "Iberia flies Madrid to Copenhagen non-stop — a quick, convenient "
                "economy hop."
            ),
        ),
    },
]
