"""API compatibility and public readiness payload tests."""

from langchain_core.messages import AIMessage
import pytest

from src.api.main import ChatRequest, _public_components
from src.models import SafetyInfo
from src.readiness import TravelReadinessReport


def test_legacy_destination_target_is_rejected():
    with pytest.raises(ValueError):
        ChatRequest(message="Is Tokyo safe?", target_agent="DestinationAgent")

    request = ChatRequest(message="Is Tokyo safe?", target_agent="TravelReadinessAgent")
    assert request.target_agent == "TravelReadinessAgent"


def test_public_components_keeps_structured_readiness_and_drops_messages():
    components = {
        "routing": ["TravelReadinessAgent"],
        "readiness": {
            "messages": [AIMessage(content="private transcript")],
            "data": {"destinations": ["tokyo"], "limitations": []},
        },
    }
    assert _public_components(components) == {
        "readiness": {"data": {"destinations": ["tokyo"], "limitations": []}}
    }


def test_public_readiness_v2_shape_keeps_nested_visa_and_health_fields():
    report = TravelReadinessReport(
        destinations=["tokyo"],
        safety=SafetyInfo(
            visa_requirements="Passport required.",
            health_requirements=["Routine vaccines."],
        ),
    )
    payload = _public_components(
        {"readiness": {"messages": [], "data": report.model_dump(mode="json")}}
    )["readiness"]["data"]

    assert set(payload) == {
        "destinations",
        "intent",
        "summary",
        "safety",
        "culture",
        "weather",
        "weather_summary",
        "planning_constraints",
        "packing_constraints",
        "sources",
        "citations",
        "limitations",
        "generated_at",
    }
    assert payload["safety"]["visa_requirements"] == "Passport required."
    assert payload["safety"]["health_requirements"] == ["Routine vaccines."]
