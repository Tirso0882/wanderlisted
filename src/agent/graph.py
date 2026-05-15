"""LangGraph Studio entrypoint — exposes the compiled graph."""

from langchain.agents import create_agent

from src.agent.llm import get_llm
from src.tools.activities import search_activities
from src.tools.budget import calculate_budget
from src.tools.currency import convert_currency
from src.tools.flights_duffel import search_flights
from src.tools.hotels_hotelbeds import search_hotels_hotelbeds
from src.tools.iata import lookup_iata_code
from src.tools.destination_rag import search_destination_guides
from src.tools.safety import get_safety_info
from src.tools.weather import get_weather
from src.agent.prompts import TRAVEL_AGENT_SYSTEM_PROMPT

_llm = get_llm()

graph = create_agent(
    model=_llm,
    tools=[
        lookup_iata_code,
        search_flights,
        search_hotels_hotelbeds,
        get_weather,
        convert_currency,
        search_activities,
        get_safety_info,
        calculate_budget,
        search_destination_guides,
    ],
    system_prompt=TRAVEL_AGENT_SYSTEM_PROMPT,
)
