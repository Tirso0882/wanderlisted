"""Restaurants specialist agent — powered by Google Places API."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import RESTAURANTS_SYSTEM_PROMPT
from src.tools.google_maps import search_places_nearby, search_places_text


class RestaurantsAgent(SpecializedAgent):
    """Specialized agent for restaurant and dining recommendations."""

    name = "RestaurantsAgent"
    description = "Expert in restaurants, street food, cafes, bars, and dining experiences"

    @property
    def tools(self):
        return [search_places_nearby, search_places_text]

    @property
    def system_prompt(self) -> str:
        return RESTAURANTS_SYSTEM_PROMPT
