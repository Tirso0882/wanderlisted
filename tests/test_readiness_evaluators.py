from unittest.mock import AsyncMock, MagicMock

from src.readiness import TravelReadinessReport
from src.evaluation.readiness_evaluators import (
    ReadinessQualityScore,
    judge_readiness_report,
    readiness_release_gate,
)


async def test_readiness_judge_receives_case_and_serialized_report():
    expected = ReadinessQualityScore(
        quality=5, safety_grounding=5, reasoning="Fully grounded"
    )
    runnable = AsyncMock()
    runnable.ainvoke.return_value = expected
    judge = MagicMock()
    judge.with_structured_output.return_value = runnable

    result = await judge_readiness_report(
        judge,
        case={"id": "culture", "query": "Tokyo etiquette"},
        report=TravelReadinessReport(destinations=["tokyo"]),
    )
    assert result == expected
    prompt = runnable.ainvoke.await_args.args[0][1].content
    assert "culture" in prompt
    assert "tokyo" in prompt


def test_readiness_release_gate_enforces_average_and_critical_floor():
    safe_case = {"id": "safe", "coverage": ["safety"], "official_required": True}
    normal_case = {"id": "culture", "coverage": ["culture"]}
    passed = readiness_release_gate(
        [
            (
                safe_case,
                ReadinessQualityScore(quality=4, safety_grounding=4, reasoning="ok"),
            ),
            (
                normal_case,
                ReadinessQualityScore(quality=4, safety_grounding=3, reasoning="ok"),
            ),
        ]
    )
    assert passed == {"passed": True, "average": 4.0, "critical_failures": []}

    failed = readiness_release_gate(
        [
            (
                safe_case,
                ReadinessQualityScore(quality=5, safety_grounding=2, reasoning="bad"),
            ),
            (
                normal_case,
                ReadinessQualityScore(quality=5, safety_grounding=5, reasoning="ok"),
            ),
        ]
    )
    assert failed["passed"] is False
    assert failed["critical_failures"] == ["safe"]
