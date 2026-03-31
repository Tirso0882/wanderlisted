"""Flights specialist agent."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import FLIGHTS_SYSTEM_PROMPT
from src.tools.flights import search_flights
from src.tools.iata import lookup_iata_code


class FlightsAgent(SpecializedAgent):
    """Specialized agent for flight searches and air travel planning."""

    name = "FlightsAgent"
    description = "Expert in flight searches, airlines, booking optimization, and departure/arrival logistics"

    @property
    def tools(self):
        return [lookup_iata_code, search_flights]

    @property
    def system_prompt(self) -> str:
        return FLIGHTS_SYSTEM_PROMPT
