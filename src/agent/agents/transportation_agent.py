"""Transportation specialist agent — powered by the Google Routes API."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import TRANSPORTATION_SYSTEM_PROMPT
from src.tools.google_maps import compute_route


class TransportationAgent(SpecializedAgent):
    """Specialized agent for local transport, routes, and getting around."""

    name = "TransportationAgent"
    description = "Expert in local transportation, directions, transit, and getting between places"

    @property
    def tools(self):
        return [compute_route]

    @property
    def system_prompt(self) -> str:
        return TRANSPORTATION_SYSTEM_PROMPT
