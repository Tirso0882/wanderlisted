"""Small held-out Budget judge-calibration corpus."""

from edd.harness import Trajectory


def _case(name: str, expected: int, report: str, answer: str) -> dict:
    return {
        "name": name,
        "expected": expected,
        "trajectory": Trajectory(
            query="Explain this validated trip budget.",
            tool_outputs=[("budget_report", report)],
            final_text=answer,
        ),
    }


JUDGE_CASES = [
    _case(
        "grounded-complete",
        3,
        '{"total":1000,"currency":"USD","coverage_status":"complete"}',
        "The complete USD total is 1,000.",
    ),
    _case(
        "grounded-partial",
        3,
        '{"total":700,"coverage_status":"partial","missing_categories":["flights"],"verdict":"unknown"}',
        "Known costs total USD 700, but flights are missing, so affordability is unknown.",
    ),
    _case(
        "minor-rounding",
        2,
        '{"total":1000.49,"currency":"USD","coverage_status":"complete"}',
        "The complete estimate is about USD 1,000.",
    ),
    _case(
        "minor-omission",
        2,
        '{"total":1000,"coverage_status":"complete_with_estimates","estimated_categories":["meals"]}',
        "The total is USD 1,000.",
    ),
    _case(
        "wrong-total", 1, '{"total":1000,"currency":"USD"}', "The total is USD 1,500."
    ),
    _case(
        "unsupported-verdict",
        1,
        '{"total":700,"coverage_status":"partial","verdict":"unknown"}',
        "The trip is safely within budget.",
    ),
    _case(
        "invented-place-price",
        0,
        '{"non_numeric_evidence":[{"signal":"price_level","value":"$$$"}],"total":0}',
        "The activity price level means it costs exactly USD 75, so the trip total is USD 75.",
    ),
    _case(
        "fabricated-report",
        0,
        '{"total":0,"coverage_status":"partial"}',
        "Flights cost USD 900, hotels USD 1,200, and the complete total is USD 3,500.",
    ),
]
