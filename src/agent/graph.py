"""LangGraph Studio entrypoint — exposes the compiled graph."""

from langchain.agents import create_agent

from src.agent.llm import get_llm
from src.tools.activities import search_activities
from src.tools.flights_duffel import search_flights
from src.tools.hotels_hotelbeds import search_hotels_hotelbeds
from src.tools.iata import lookup_iata_code
from src.tools.web_search import search_destination_web
from src.agent.prompts import TRAVEL_AGENT_SYSTEM_PROMPT

_llm = get_llm()

graph = create_agent(
    model=_llm,
    tools=[
        lookup_iata_code,
        search_flights,
        search_hotels_hotelbeds,
        search_activities,
        search_destination_web,
    ],
    system_prompt=TRAVEL_AGENT_SYSTEM_PROMPT,
)
