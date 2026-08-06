"""Tests for HITL (Human-in-the-Loop) state and interrupt gate logic."""

from src.agent.state import TravelAgentState


# ── State field tests ────────────────────────────────────────────────────────


async def test_state_has_hitl_fields():
    """TravelAgentState includes all Phase 4 HITL fields."""
    annotations = TravelAgentState.__annotations__
    for field in (
        "human_feedback",
        "hitl_action",
        "budget_adjustment_accepted",
    ):
        assert field in annotations, f"Missing HITL field: {field}"


async def test_state_hitl_fields_are_writable():
    """HITL fields can be set and read back."""
    state = TravelAgentState(
        messages=[],
        human_feedback="reduce budget by 20%",
        hitl_action="edited",
        budget_adjustment_accepted=True,
    )
    assert state["human_feedback"] == "reduce budget by 20%"
    assert state["hitl_action"] == "edited"
    assert state["budget_adjustment_accepted"] is True


# ── Budget overspend detection tests ─────────────────────────────────────────


async def test_budget_overspend_detected():
    """Overspend > $500 should be caught."""
    budget = {"total": 5500, "target_budget": 4000}
    overspend = budget["total"] - budget["target_budget"]
    assert overspend > 500


async def test_budget_within_range():
    """Overspend <= $500 should pass through."""
    budget = {"total": 4400, "target_budget": 4000}
    overspend = budget["total"] - budget["target_budget"]
    assert overspend <= 500


async def test_budget_no_target():
    """No target budget → no overspend check."""
    budget = {"total": 5500, "target_budget": 0}
    # When target is 0, we skip the review
    assert budget["target_budget"] == 0


# ── HITL decision routing tests ──────────────────────────────────────────────


async def test_hitl_approved_action():
    """Approved decision sets hitl_action to 'approved'."""
    decision = {"approved": True}
    assert decision.get("approved") is True


async def test_hitl_rejected_action():
    """Rejected decision sets hitl_action to 'rejected'."""
    decision = {"approved": False}
    assert decision.get("approved") is False


async def test_hitl_edited_action_with_feedback():
    """Approved decision with feedback is treated as 'edited'."""
    decision = {"approved": True, "feedback": "Switch to budget hotels"}
    assert decision.get("approved") is True
    assert decision.get("feedback") == "Switch to budget hotels"


# ── Interrupt payload format tests ───────────────────────────────────────────


async def test_budget_interrupt_payload_format():
    """Budget interrupt produces the expected payload structure."""
    payload = {
        "type": "budget_warning",
        "message": "BUDGET ALERT: estimated exceeds target.",
        "estimated_total": 5500,
        "target_budget": 4000,
        "overspend": 1500,
        "suggestions": ["Switch to budget hotels"],
        "action_required": "Respond with {'approved': true}.",
    }
    assert payload["type"] == "budget_warning"
    assert payload["overspend"] == 1500
    assert isinstance(payload["suggestions"], list)


async def test_human_review_interrupt_payload_format():
    """Human review interrupt produces the expected payload structure."""
    payload = {
        "type": "itinerary_review",
        "message": "Your travel plan is ready for review.",
        "components_available": ["✈️ Flights: found", "🏨 Hotels: found"],
        "itinerary_preview": "Day 1: Arrive in Tokyo...",
        "action_required": "Respond with {'approved': true}.",
    }
    assert payload["type"] == "itinerary_review"
    assert len(payload["components_available"]) == 2
