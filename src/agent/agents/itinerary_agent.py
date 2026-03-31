"""Itinerary assembly agent — stitches subagent outputs into a day-by-day plan.

Also owns the handbook rendering pipeline: after the LLM assembles a
structured ``TripHandbook``, the renderer converts it to HTML / Markdown / JSON.
"""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import ITINERARY_SYSTEM_PROMPT
from src.tools.google_maps import optimize_day_route, get_distance_matrix


class ItineraryAgent(SpecializedAgent):
    """Final assembly agent that builds optimised day-by-day itineraries."""

    name = "ItineraryAgent"
    description = "Expert in assembling day-by-day itineraries with route optimisation"

    @property
    def tools(self):
        return [optimize_day_route, get_distance_matrix]

    @property
    def system_prompt(self) -> str:
        return ITINERARY_SYSTEM_PROMPT
