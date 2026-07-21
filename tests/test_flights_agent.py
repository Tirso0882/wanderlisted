"""FlightsAgent tool ownership tests."""

from unittest.mock import MagicMock

from src.agent.agents.flights_agent import FlightsAgent


def test_flights_agent_exposes_flexible_round_trip_window_search():
    agent = FlightsAgent(llm=MagicMock())
    tool_names = {tool.name for tool in agent.tools}

    assert "search_cheapest_round_trip_in_window" in tool_names
    assert "search_flights" in tool_names
    assert "lookup_iata_code" in tool_names
