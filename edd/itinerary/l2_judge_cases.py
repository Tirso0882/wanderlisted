"""Held-out Itinerary faithfulness-judge calibration cases."""

from edd.harness import Trajectory


def _case(name: str, expected: int, evidence: str, answer: str) -> dict:
    return {
        "name": name,
        "expected": expected,
        "trajectory": Trajectory(
            query="Explain this validated itinerary.",
            tool_outputs=[("itinerary_plan", evidence)],
            final_text=answer,
        ),
    }


JUDGE_CASES = [
    _case(
        "grounded-timed-plan",
        3,
        '{"date":"2026-09-02","city":"Paris","stop":"Louvre","scheduled_start":"09:30","scheduled_end":"11:30","feasibility_status":"verified"}',
        "On 2 September in Paris, visit the Louvre from 09:30 to 11:30; this slot is verified.",
    ),
    _case(
        "grounded-partial-plan",
        3,
        '{"stop":"Park","scheduled_start":"","feasibility_status":"needs_review","missing_constraints":["opening_hours:park"]}',
        "The park is selected, but its time needs review because opening hours are unavailable.",
    ),
    _case(
        "minor-time-rounding",
        2,
        '{"stop":"Museum","scheduled_start":"09:26","scheduled_end":"11:26"}',
        "Plan on roughly 09:30 to 11:30 for the museum.",
    ),
    _case(
        "minor-warning-omission",
        2,
        '{"date":"2026-09-02","stop":"Museum","feasibility_status":"needs_review","warnings":["flight time unavailable"]}',
        "Visit the museum on 2 September.",
    ),
    _case(
        "wrong-date",
        1,
        '{"date":"2026-09-02","stop":"Museum"}',
        "Visit the museum on 4 September.",
    ),
    _case(
        "unsupported-verified-claim",
        1,
        '{"stop":"Museum","feasibility_status":"needs_review","missing_constraints":["route_plan"]}',
        "The museum schedule and all transit times are fully verified.",
    ),
    _case(
        "invented-stop-and-fare",
        0,
        '{"selected_source_ids":["museum-1"],"route":{"fare":null}}',
        "After museum-1, visit the invented Royal Gallery and pay the exact USD 25 route fare.",
    ),
    _case(
        "fabricated-plan",
        0,
        '{"dates":["2026-09-01"],"scheduled_stops":[]}',
        "Your three-day trip includes a booked Grand Hotel, four restaurants, and two timed tours.",
    ),
]
