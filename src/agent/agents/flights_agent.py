"""Flights specialist agent."""

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import FLIGHTS_SYSTEM_PROMPT
from src.tools.flights_duffel import (
    confirm_flight_price,
    get_cheapest_flight,
    search_cheapest_flight_in_month,
    search_cheapest_round_trip_in_window,
    search_flights,
    search_nearby_airports,
)
from src.tools.iata import lookup_iata_code


class FlightsAgent(SpecializedAgent):
    """Specialized agent for flight searches and air travel planning.

    NOTE: This agent is used in the parallel fan-out during itinerary planning.
    It only has SEARCH tools — no booking.
    Includes search_nearby_airports for airport discovery.
    """

    name = "FlightsAgent"
    description = "Expert in flight searches, airlines, booking optimization, and departure/arrival logistics"

    @property
    def tools(self):
        return [
            lookup_iata_code,
            search_flights,
            get_cheapest_flight,
            search_cheapest_round_trip_in_window,
            search_cheapest_flight_in_month,
            confirm_flight_price,
            search_nearby_airports,
        ]

    @property
    def system_prompt(self) -> str:
        return FLIGHTS_SYSTEM_PROMPT
