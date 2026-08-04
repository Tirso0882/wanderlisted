"""Typed ItineraryAgent: bounded selection plus deterministic compilation."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import ITINERARY_SYSTEM_PROMPT
from src.itinerary import (
    ItineraryAssemblyContext,
    ItineraryPipeline,
    ItineraryRun,
    ItinerarySelectionContext,
    ItineraryValidationError,
    resolve_selection,
    validate_legacy_draft,
)
from src.models import DraftItinerary, ItinerarySelectionProposal


class ItineraryAgent(SpecializedAgent):
    """Select known evidence IDs once, then compile every factual field in code."""

    name = "ItineraryAgent"
    description = (
        "Typed itinerary source selection, canonical dates, and validated scheduling"
    )

    def __init__(self, llm=None):
        super().__init__(llm=llm)
        self.pipeline = ItineraryPipeline()

    @property
    def tools(self):
        return []

    @property
    def system_prompt(self) -> str:
        return ITINERARY_SYSTEM_PROMPT

    async def select_draft(self, context: ItinerarySelectionContext) -> DraftItinerary:
        """Make one bounded ID-only selection, with one validation retry."""
        if self.llm is None:
            raise ItineraryValidationError(["selection model is unavailable"])
        selector = self.llm.with_structured_output(
            ItinerarySelectionProposal, method="function_calling"
        )
        payload = {
            "trip_skeleton": context.skeleton.model_dump(mode="json"),
            "traveler_preferences": {
                "travel_style": context.request.travel_style,
                "interests": context.request.interests,
                "dietary_restrictions": context.request.dietary_restrictions,
                "accessibility_needs": context.request.accessibility_needs,
            },
            "evidence_catalog": context.catalog.prompt_payload(),
            "feedback": context.feedback,
        }
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(
                content=json.dumps(payload, ensure_ascii=False, sort_keys=True)
            ),
        ]
        last_error: ItineraryValidationError | None = None
        for attempt in range(2):
            try:
                result = await selector.ainvoke(messages)
                if isinstance(result, DraftItinerary):
                    return validate_legacy_draft(
                        result,
                        context,
                        raw_evidence=context.raw_evidence,
                    )
                proposal = ItinerarySelectionProposal.model_validate(result)
                return resolve_selection(proposal, context)
            except (ItineraryValidationError, ValueError, TypeError) as exc:
                last_error = (
                    exc
                    if isinstance(exc, ItineraryValidationError)
                    else ItineraryValidationError([str(exc)])
                )
                if attempt == 0:
                    messages.append(
                        HumanMessage(
                            content=(
                                "Your selection failed deterministic validation. "
                                "Return a corrected proposal using only the supplied IDs. "
                                f"Errors: {list(last_error.errors)}"
                            )
                        )
                    )
        raise last_error or ItineraryValidationError(["selection failed"])

    def compile(self, context: ItineraryAssemblyContext) -> ItineraryRun:
        return self.pipeline.run(context)
