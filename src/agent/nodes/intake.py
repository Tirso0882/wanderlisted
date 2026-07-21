"""Structured request intake and deterministic clarification gate."""

from __future__ import annotations

import json
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langsmith import traceable

from custom_logging import AppLogger
from src.agent.policies.requirements import (
    build_clarification_message,
    missing_required_fields,
)
from src.agent.prompts import INTAKE_SYSTEM_PROMPT
from src.agent.state import TravelAgentState
from src.models import TripRequest, TripRequestPatch, merge_trip_request

_log = AppLogger("agent.nodes.intake")


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text")
        )
    return str(content or "")


@traceable(run_type="chain", name="intake_node", tags=["wanderlisted", "intake"])
async def intake_node(state: TravelAgentState, *, llm) -> dict:
    """Merge the latest turn into TripRequest and stop if inputs are missing."""
    current = TripRequest.model_validate(state.get("trip_request", {}))
    latest = state.get("messages", [])[-1]
    latest_text = _message_text(latest.content)
    structured_llm = llm.with_structured_output(
        TripRequestPatch,
        method="function_calling",
    )

    context = (
        f"Current date: {date.today().isoformat()}\n"
        "Current canonical request (preserve values not changed by this turn):\n"
        f"{json.dumps(current.model_dump(mode='json'), ensure_ascii=False)}"
    )
    try:
        patch = await structured_llm.ainvoke(
            [
                SystemMessage(content=INTAKE_SYSTEM_PROMPT),
                SystemMessage(content=context),
                HumanMessage(content=latest_text),
            ]
        )
        request = merge_trip_request(current, patch)
    except Exception as exc:
        _log.warning("Trip request extraction failed: %s", exc)
        locale = current.locale if current.locale in {"en", "pl"} else "en"
        message = (
            "Nie udało mi się zrozumieć szczegółów podróży. "
            "Opisz proszę miejsce, daty i liczbę podróżnych."
            if locale == "pl"
            else "I could not understand the trip details. Please provide the "
            "destination, dates, and number of travelers."
        )
        return {
            "messages": [AIMessage(content=message)],
            "current_agent": "intake:failed",
            "workflow_status": "needs_user_input",
            "pending_questions": ["request_details"],
        }

    missing = missing_required_fields(request)
    status = "needs_user_input" if missing else "ready"
    result: dict = {
        "current_agent": f"intake:{status}",
        "trip_request": request.model_dump(mode="json"),
        "workflow_status": status,
        "pending_questions": missing,
        "request_revision": state.get("request_revision", 0) + 1,
        "destinations": request.destinations or state.get("destinations", []),
        "travel_style": request.travel_style or state.get("travel_style", ""),
        "accessibility_needs": request.accessibility_needs
        or state.get("accessibility_needs", []),
        "dietary_restrictions": request.dietary_restrictions
        or state.get("dietary_restrictions", []),
    }
    if missing:
        result["messages"] = [
            AIMessage(content=build_clarification_message(missing, request.locale))
        ]
    return result
