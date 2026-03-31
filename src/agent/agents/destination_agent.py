"""Destination expertise and travel context agent."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import DESTINATION_SYSTEM_PROMPT
from src.tools.destination_rag import search_destination_guides
from src.tools.weather import get_weather
from src.tools.safety import get_safety_info


class DestinationAgent(SpecializedAgent):
    """Specialized agent for destination context, culture, safety, and insider tips."""

    name = "DestinationAgent"
    description = "Expert in destination culture, weather, safety, and insider travel knowledge"

    @property
    def tools(self):
        return [search_destination_guides, get_weather, get_safety_info]

    @property
    def system_prompt(self) -> str:
        return DESTINATION_SYSTEM_PROMPT
