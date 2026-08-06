"""Additive Budget v2 API and typed resume-decision contracts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import ValidationError

from src.agent.stage4_graph import budget_review_node
from src.api.main import ChatResponse, ResumeRequest, resume_chat
from src.models import BudgetBreakdown


def _reliable_overage(*, total: float, target: float) -> dict:
    return {
        "total": total,
        "target_budget": target,
        "coverage_status": "complete",
        "conversion_status": "complete",
        "verdict": "over_budget",
        "reconciliation_delta": 0,
    }


def test_old_budget_payload_remains_readable_through_typed_api_response():
    response = ChatResponse(
        message="done",
        session_id="session",
        budget={"flights": 100, "total": 100, "currency": "USD"},
    )

    assert isinstance(response.budget, BudgetBreakdown)
    assert response.budget.schema_version == 2
    assert response.budget.flights == 100


def test_budget_adjustment_resume_decision_is_typed():
    request = ResumeRequest(
        session_id="session",
        decision={
            "gate": "budget_review",
            "action": "adjust_target",
            "new_budget": 4500,
        },
    )
    assert request.decision.action == "adjust_target"
    assert request.decision.new_budget == 4500

    with pytest.raises(ValidationError):
        ResumeRequest(
            session_id="session",
            decision={"gate": "budget_review", "action": "adjust_target"},
        )


def test_legacy_approved_resume_decision_remains_supported():
    request = ResumeRequest(session_id="session", decision={"approved": True})
    assert request.decision.approved is True


def test_removed_safety_resume_decision_is_rejected():
    with pytest.raises(ValidationError):
        ResumeRequest(
            session_id="session",
            decision={"gate": "safety_review", "approved": True},
        )


@patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
@patch("src.agent.stage4_graph.interrupt")
async def test_gate_interrupts_at_inclusive_material_threshold(interrupt_mock, _hitl):
    interrupt_mock.return_value = {
        "gate": "budget_review",
        "action": "proceed",
    }
    result = await budget_review_node(
        {
            "itinerary_components": {
                "budget_structured": _reliable_overage(total=1100, target=1000)
            },
            "budget_adjustment_accepted": False,
        }
    )

    assert result["hitl_action"] == "proceed"
    interrupt_mock.assert_called_once()


@pytest.mark.parametrize(
    "overrides",
    [
        {"total": 1099},
        {"coverage_status": "partial"},
        {"conversion_status": "unavailable"},
        {"display_conversion_available": False},
        {"verdict": "unknown"},
    ],
)
@patch("src.agent.stage4_graph.is_hitl_enabled", return_value=True)
@patch("src.agent.stage4_graph.interrupt")
async def test_gate_does_not_interrupt_without_reliable_material_overage(
    interrupt_mock, _hitl, overrides
):
    budget = _reliable_overage(total=1100, target=1000)
    budget.update(overrides)

    result = await budget_review_node(
        {
            "itinerary_components": {"budget_structured": budget},
            "budget_adjustment_accepted": False,
        }
    )

    assert result["hitl_action"] == "proceed"
    interrupt_mock.assert_not_called()


class _ResumeGraph:
    def __init__(self) -> None:
        self.ainvoke = AsyncMock(
            return_value={
                "messages": [AIMessage(content="Budget target updated")],
                "itinerary_components": {
                    "budget_structured": {
                        "total": 1000,
                        "target_budget": 1200,
                        "currency": "USD",
                    }
                },
            }
        )

    async def aget_state(self, _config):
        return SimpleNamespace(values={"messages": [HumanMessage(content="plan")]})


class _AllowLimiter:
    async def check(self, _principal_id: str) -> bool:
        return True


async def test_resume_endpoint_passes_typed_budget_decision_to_langgraph():
    graph = _ResumeGraph()
    request = ResumeRequest(
        session_id="session",
        decision={
            "gate": "budget_review",
            "action": "adjust_target",
            "new_budget": 1200,
        },
    )

    response = await resume_chat(
        request,
        owner_id="90f5daf68c5b48bf97dd053bc80869ef",
        rate_limiter=_AllowLimiter(),
        graph=graph,
    )

    command = graph.ainvoke.await_args.args[0]
    assert command.resume == {
        "gate": "budget_review",
        "action": "adjust_target",
        "new_budget": 1200.0,
    }
    assert response.budget is not None
    assert response.budget.target_budget == 1200
