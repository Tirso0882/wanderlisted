"""Activities specialist agent — powered by Google Places API."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import ACTIVITIES_SYSTEM_PROMPT
from src.tools.google_maps import search_places_nearby, search_places_text


class ActivitiesAgent(SpecializedAgent):
    """Specialized agent for tourist attractions, sightseeing, and experiences."""

    name = "ActivitiesAgent"
    description = (
        "Expert in attractions, tours, museums, nightlife, and local experiences"
    )

    @property
    def tools(self):
        return [search_places_nearby, search_places_text]

    @property
    def system_prompt(self) -> str:
        return ACTIVITIES_SYSTEM_PROMPT
