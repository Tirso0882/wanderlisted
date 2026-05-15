"""Hotels specialist agent — powered by Hotelbeds Booking API."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import HOTELS_SYSTEM_PROMPT
from src.tools.hotels_hotelbeds import search_hotels_hotelbeds, check_hotel_rate_hotelbeds
from src.tools.google_maps import search_places_text


class HotelsAgent(SpecializedAgent):
    """Specialized agent for accommodation search, pricing, and neighborhood context."""

    name = "HotelsAgent"
    description = (
        "Expert in hotels, neighborhoods, pricing, and accommodation options"
    )

    @property
    def tools(self):
        return [
            search_hotels_hotelbeds,
            check_hotel_rate_hotelbeds,
            search_places_text,
        ]

    @property
    def system_prompt(self) -> str:
        return HOTELS_SYSTEM_PROMPT
