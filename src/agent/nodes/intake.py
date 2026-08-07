"""Structured request intake and deterministic clarification gate."""

from __future__ import annotations

import json
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langsmith import traceable

from custom_logging import AppLogger
from src.agent.policies.requirements import (
    apply_service_scope_decision,
    build_clarification_message,
    build_service_scope_offer,
    missing_required_fields,
    resolve_service_scope_reply,
)
from src.agent.localization import (
    detect_clear_language,
    language_name,
    language_tag,
    normalize_locale,
)
from src.agent.prompts import (
    INTAKE_CONTEXT_PROMPT,
    INTAKE_SYSTEM_PROMPT,
    RESPONSE_LOCALE_CONTEXT_PROMPT,
)
from src.agent.state import TravelAgentState
from src.models import (
    ServiceScopeDecision,
    TripRequest,
    TripRequestPatch,
    merge_trip_request,
)

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
    pending_questions = state.get("pending_questions", [])
    decision_data = state.get("service_scope_decision")
    free_text_decision = (
        resolve_service_scope_reply(current, latest_text)
        if not decision_data and "service_scope_confirmation" in pending_questions
        else None
    )
    clear_locale = None if decision_data else detect_clear_language(latest_text)
    response_locale = clear_locale or normalize_locale(
        state.get("response_locale")
        or state.get("last_clear_locale")
        or state.get("ui_locale")
        or current.locale
    )
    try:
        if decision_data:
            decision = ServiceScopeDecision.model_validate(decision_data)
            request = apply_service_scope_decision(current, decision)
        else:
            request_base = (
                apply_service_scope_decision(current, free_text_decision)
                if free_text_decision
                else current
            )
            remaining_questions = [
                question
                for question in pending_questions
                if question != "service_scope_confirmation"
            ]
            if free_text_decision and not remaining_questions:
                request = request_base
            else:
                structured_llm = llm.with_structured_output(
                    TripRequestPatch,
                    method="function_calling",
                )
                context = INTAKE_CONTEXT_PROMPT.format(
                    current_date=date.today().isoformat(),
                    canonical_request=json.dumps(
                        request_base.model_dump(mode="json"), ensure_ascii=False
                    ),
                )
                patch = await structured_llm.ainvoke(
                    [
                        SystemMessage(content=INTAKE_SYSTEM_PROMPT),
                        SystemMessage(
                            content=RESPONSE_LOCALE_CONTEXT_PROMPT.format(
                                language=language_name(response_locale),
                                locale_tag=language_tag(response_locale),
                            )
                        ),
                        SystemMessage(content=context),
                        HumanMessage(content=latest_text),
                    ]
                )
                # Locale is conversation metadata, not an extraction guess.
                # A deterministic scope decision owns permission fields.
                patch_update = {"locale": clear_locale}
                if free_text_decision:
                    patch_update.update(
                        {
                            "requested_capabilities": None,
                            "declined_capabilities": None,
                            "capability_scope_confirmed": None,
                            "capability_scope_exclusive": None,
                        }
                    )
                patch = patch.model_copy(update=patch_update)
                request = merge_trip_request(request_base, patch)
    except Exception as exc:
        _log.warning("Trip request extraction failed: %s", exc)
        locale = response_locale
        message = (
            "Nie udało mi się zrozumieć szczegółów podróży. "
            "Opisz proszę miejsce, daty i liczbę podróżnych."
            if locale == "pl"
            else "No pude entender los detalles del viaje. Indica el destino, las fechas y el número de viajeros."
            if locale == "es"
            else "I could not understand the trip details. Please provide the "
            "destination, dates, and number of travelers."
        )
        return {
            "messages": [AIMessage(content=message)],
            "current_agent": "intake:failed",
            "workflow_status": "needs_user_input",
            "pending_questions": ["request_details"],
            "response_locale": response_locale,
            "last_clear_locale": clear_locale or state.get("last_clear_locale", ""),
            "service_scope_decision": {},
        }

    missing = missing_required_fields(request)
    service_scope_offer = build_service_scope_offer(request)
    status = "needs_user_input" if missing else "ready"
    result: dict = {
        "current_agent": f"intake:{status}",
        "trip_request": request.model_dump(mode="json"),
        "workflow_status": status,
        "pending_questions": missing,
        "service_scope_offer": (
            service_scope_offer.model_dump(mode="json") if service_scope_offer else {}
        ),
        "service_scope_decision": {},
        "request_revision": state.get("request_revision", 0) + 1,
        "response_locale": response_locale,
        "last_clear_locale": clear_locale or state.get("last_clear_locale", ""),
        # HITL decisions are scoped to one execution, not future requests.
        "hitl_action": "",
        "safety_warning": {},
        "budget_adjustment_accepted": False,
        "destinations": request.destinations or state.get("destinations", []),
        "travel_style": request.travel_style or state.get("travel_style", ""),
        "accessibility_needs": request.accessibility_needs
        or state.get("accessibility_needs", []),
        "dietary_restrictions": request.dietary_restrictions
        or state.get("dietary_restrictions", []),
    }
    if missing:
        result["messages"] = [
            AIMessage(
                content=build_clarification_message(
                    missing,
                    response_locale,
                    service_scope_offer.offered_capabilities
                    if service_scope_offer
                    else (),
                )
            )
        ]
    return result
