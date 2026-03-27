import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from src.tools.activities import search_activities
from src.tools.budget import calculate_budget
from src.tools.currency import convert_currency
from src.tools.flights import search_flights
from src.tools.hotels import search_hotels
from src.tools.iata import lookup_iata_code
from src.tools.destination_rag import search_destination_guides
from src.tools.safety import get_safety_info
from src.tools.weather import get_weather
from src.agent.prompts import TRAVEL_AGENT_SYSTEM_PROMPT

load_dotenv()


def create_travel_agent():
    """Create and return the travel agent with LangGraph checkpointer."""
    llm = AzureChatOpenAI(
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    )

    tools = [
        lookup_iata_code,
        search_flights,
        search_hotels,
        get_weather,
        convert_currency,
        search_activities,
        get_safety_info,
        calculate_budget,
        search_destination_guides,
    ]
    checkpointer = InMemorySaver()

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=TRAVEL_AGENT_SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent
