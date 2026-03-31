"""Supervisor agent that routes queries to specialized sub-agents via LLM."""

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import SUPERVISOR_SYSTEM_PROMPT

VALID_AGENT_NAMES = frozenset({
    "FlightsAgent", "HotelsAgent", "DestinationAgent", "BudgetAgent",
    "RestaurantsAgent", "ActivitiesAgent", "TransportationAgent",
    "ItineraryAgent",
})


class RoutingDecision(BaseModel):
    """Structured output schema for the supervisor's routing classification."""

    agents: list[str] = Field(
        description=(
            "List of specialist agent names to invoke. "
            "Valid names: FlightsAgent, HotelsAgent, DestinationAgent, "
            "BudgetAgent, RestaurantsAgent, ActivitiesAgent, "
            "TransportationAgent, ItineraryAgent."
        ),
    )
    reasoning: str = Field(
        description="One-sentence explanation of why these agents were chosen.",
    )
    user_message: str = Field(
        description=(
            "A short, friendly message to the user explaining what you will do. "
            "Example: 'I'll search for flights and hotels for your Tokyo trip.'"
        ),
    )
    destinations: list[str] = Field(
        default=[],
        description=(
            "List of confirmed city names extracted from the user's query, "
            "as lowercase slugs (e.g. ['tokyo', 'kyoto']). Empty if no "
            "specific destination is mentioned."
        ),
    )
    travel_style: str = Field(
        default="",
        description="Travel budget style if mentioned: 'budget', 'mid-range', or 'luxury'. Empty if not specified.",
    )
    group_type: str = Field(
        default="",
        description="Group type if mentioned: 'solo', 'couple', 'family', 'friends', or 'group' (for 10+ people). Empty if not specified.",
    )
    accessibility_needs: list[str] = Field(
        default=[],
        description="Accessibility requirements mentioned, e.g. ['wheelchair', 'limited mobility'].",
    )
    dietary_restrictions: list[str] = Field(
        default=[],
        description="Dietary restrictions mentioned, e.g. ['vegetarian', 'halal', 'gluten-free'].",
    )


class SupervisorAgent(SpecializedAgent):
    """Supervisor agent that routes user queries to appropriate specialized agents."""

    name = "SupervisorAgent"
    description = "Coordinator that routes travel planning queries to specialized sub-agents"

    @property
    def tools(self):
        """Supervisor has no direct tools; coordinates other agents."""
        return []

    @property
    def system_prompt(self) -> str:
        return SUPERVISOR_SYSTEM_PROMPT

    async def aget_routing_decision(
        self, user_query: str, existing_data_summary: str = "",
    ) -> RoutingDecision:
        """Use the LLM with structured output to classify the query.

        Args:
            user_query: The latest user message.
            existing_data_summary: Optional summary of data already collected
                by specialist agents in this conversation thread.

        Returns a RoutingDecision with agents, reasoning, and a user-facing message.
        """
        messages = [SystemMessage(content=self.system_prompt)]
        if existing_data_summary:
            messages.append(SystemMessage(content=existing_data_summary))
        messages.append(HumanMessage(content=user_query))

        structured_llm = self.llm.with_structured_output(RoutingDecision)
        result = await structured_llm.ainvoke(messages)
        # Validate: strip any hallucinated agent names the LLM may invent
        result.agents = [a for a in result.agents if a in VALID_AGENT_NAMES]
        return result
