from src.evaluation.readiness_dataset import READINESS_CASES


def test_readiness_dataset_has_24_unique_cases_and_required_intents():
    assert len(READINESS_CASES) == 24
    assert len({case["id"] for case in READINESS_CASES}) == 24
    intents = {case["intent"] for case in READINESS_CASES}
    assert {
        "culture",
        "safety",
        "weather",
        "entry",
        "health",
        "practical",
        "packing",
        "comprehensive",
    } <= intents
    coverage = {tag for case in READINESS_CASES for tag in case.get("coverage", [])}
    assert {
        "culture",
        "safety",
        "weather",
        "entry",
        "packing_constraints",
        "multi_destination",
        "ownership_boundary",
        "ambiguous",
        "prompt_injection",
        "provider_failure",
    } <= coverage
