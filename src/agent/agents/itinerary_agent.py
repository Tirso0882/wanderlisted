"""Itinerary assembly agent — stitches typed planning artifacts into a day-by-day plan.

Also owns the handbook rendering pipeline: after the LLM assembles a
structured ``TripHandbook``, the renderer converts it to HTML / Markdown / JSON.
"""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import ITINERARY_SYSTEM_PROMPT


class ItineraryAgent(SpecializedAgent):
    """Final assembly agent that builds optimised day-by-day itineraries."""

    name = "ItineraryAgent"
    description = (
        "Expert in assembling selected and route-optimized day-by-day itineraries"
    )

    @property
    def tools(self):
        return []

    @property
    def system_prompt(self) -> str:
        return ITINERARY_SYSTEM_PROMPT
