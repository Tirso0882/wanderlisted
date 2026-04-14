"""Hotels and activities specialist agent."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import HOTELS_SYSTEM_PROMPT
from src.tools.hotels import search_hotels
from src.tools.activities import search_activities
from src.tools.google_maps import search_places_text


class HotelsAgent(SpecializedAgent):
    """Specialized agent for accommodation and local activities."""

    name = "HotelsAgent"
    description = (
        "Expert in hotels, neighborhoods, activities, dining, and local experiences"
    )

    @property
    def tools(self):
        return [search_hotels, search_activities, search_places_text]

    @property
    def system_prompt(self) -> str:
        return HOTELS_SYSTEM_PROMPT
