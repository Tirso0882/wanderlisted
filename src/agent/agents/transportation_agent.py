"""Transportation specialist agent — powered by Google Routes/Directions APIs."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import TRANSPORTATION_SYSTEM_PROMPT
from src.tools.google_maps import (
    get_directions,
    get_distance_matrix,
    compute_route,
)


class TransportationAgent(SpecializedAgent):
    """Specialized agent for local transport, routes, and getting around."""

    name = "TransportationAgent"
    description = "Expert in local transportation, directions, transit, and getting between places"

    @property
    def tools(self):
        return [get_directions, get_distance_matrix, compute_route]

    @property
    def system_prompt(self) -> str:
        return TRANSPORTATION_SYSTEM_PROMPT
