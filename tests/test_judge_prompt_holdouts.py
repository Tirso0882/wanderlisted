"""Regression checks that Layer-4 judge calibration remains held out."""

from __future__ import annotations

import re

import pytest

from edd.activities.l2_judge import (
    CALIBRATION_HOLDOUT_MARKERS as ACTIVITIES_MARKERS,
)
from edd.activities.l2_judge import FAITHFULNESS_RUBRIC as ACTIVITIES_RUBRIC
from edd.activities.l2_judge_cases import JUDGE_CASES as ACTIVITIES_CASES
from edd.flights.l2_judge import CALIBRATION_HOLDOUT_MARKERS as FLIGHTS_MARKERS
from edd.flights.l2_judge import FAITHFULNESS_RUBRIC as FLIGHTS_RUBRIC
from edd.flights.l2_judge_cases import JUDGE_CASES as FLIGHTS_CASES
from edd.readiness.l2_judge import (
    CALIBRATION_HOLDOUT_MARKERS as READINESS_MARKERS,
)
from edd.readiness.l2_judge import FAITHFULNESS_RUBRIC as READINESS_RUBRIC
from edd.readiness.l2_judge_cases import JUDGE_CASES as READINESS_CASES
from edd.hotels.l2_judge import CALIBRATION_HOLDOUT_MARKERS as HOTELS_MARKERS
from edd.hotels.l2_judge import FAITHFULNESS_RUBRIC as HOTELS_RUBRIC
from edd.hotels.l2_judge_cases import JUDGE_CASES as HOTELS_CASES
from edd.restaurants.l2_judge import (
    CALIBRATION_HOLDOUT_MARKERS as RESTAURANTS_MARKERS,
)
from edd.restaurants.l2_judge import FAITHFULNESS_RUBRIC as RESTAURANTS_RUBRIC
from edd.restaurants.l2_judge_cases import JUDGE_CASES as RESTAURANTS_CASES
from edd.transportation.l2_judge import (
    CALIBRATION_HOLDOUT_MARKERS as TRANSPORTATION_MARKERS,
)
from edd.transportation.l2_judge import FAITHFULNESS_RUBRIC as TRANSPORTATION_RUBRIC
from edd.transportation.l2_judge_cases import JUDGE_CASES as TRANSPORTATION_CASES


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _case_text(case: dict) -> str:
    trajectory = case["trajectory"]
    evidence = "\n".join(output for _, output in trajectory.tool_outputs)
    return "\n".join((trajectory.query, evidence, trajectory.final_text))


@pytest.mark.parametrize(
    ("agent", "rubric", "markers", "cases"),
    [
        ("activities", ACTIVITIES_RUBRIC, ACTIVITIES_MARKERS, ACTIVITIES_CASES),
        (
            "readiness",
            READINESS_RUBRIC,
            READINESS_MARKERS,
            READINESS_CASES,
        ),
        ("flights", FLIGHTS_RUBRIC, FLIGHTS_MARKERS, FLIGHTS_CASES),
        ("hotels", HOTELS_RUBRIC, HOTELS_MARKERS, HOTELS_CASES),
        ("restaurants", RESTAURANTS_RUBRIC, RESTAURANTS_MARKERS, RESTAURANTS_CASES),
        (
            "transportation",
            TRANSPORTATION_RUBRIC,
            TRANSPORTATION_MARKERS,
            TRANSPORTATION_CASES,
        ),
    ],
)
def test_judge_prompt_examples_are_disjoint_from_calibration_cases(
    agent: str, rubric: str, markers: tuple[str, ...], cases: list[dict]
):
    """Prompt anchors must not identify or reproduce Layer-4 labeled cases."""
    prompt = _normalise(rubric)
    calibration_corpus = _normalise("\n".join(_case_text(case) for case in cases))

    assert markers, f"{agent} must declare stable prompt-anchor identifiers"
    for marker in markers:
        marker = _normalise(marker)
        assert marker in prompt, f"{agent} holdout marker is not in the judge prompt"
        assert marker not in calibration_corpus, (
            f"{agent} prompt anchor {marker!r} appears in l2_judge_cases"
        )

    for case in cases:
        trajectory = case["trajectory"]
        for label, value in (
            ("request", trajectory.query),
            ("answer", trajectory.final_text),
            ("evidence", "\n".join(output for _, output in trajectory.tool_outputs)),
        ):
            normalised_value = _normalise(value)
            # Short generic phrases (for example, "No route found.") legitimately
            # occur in the rubric rules. Long fixture fields identify a held-out case.
            if len(normalised_value) >= 40:
                assert normalised_value not in prompt, (
                    f"{agent} calibration case {case['name']!r} has its {label} copied "
                    "into the judge prompt"
                )
