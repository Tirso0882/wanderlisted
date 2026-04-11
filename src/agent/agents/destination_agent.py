"""Destination expertise and travel context agent."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import DESTINATION_SYSTEM_PROMPT
from src.tools.destination_rag import search_destination_guides
from src.tools.destination_research import research_destination
from src.tools.google_maps import get_timezone
from src.tools.safety import get_safety_info
from src.tools.weather import get_weather
from src.tools.web_search import search_hidden_gems, search_web


class DestinationAgent(SpecializedAgent):
    """Specialized agent for destination context, culture, safety, and insider tips."""

    name = "DestinationAgent"
    description = "Expert in destination culture, weather, safety, timezone, and insider travel knowledge"

    @property
    def tools(self):
        return [
            research_destination,
            search_destination_guides,
            search_web,
            search_hidden_gems,
            get_weather,
            get_safety_info,
            get_timezone,
        ]

    @property
    def system_prompt(self) -> str:
        return DESTINATION_SYSTEM_PROMPT
