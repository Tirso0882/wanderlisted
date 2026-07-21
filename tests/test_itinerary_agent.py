"""Unit tests for ItineraryAgent — class structure and tool registration."""

from unittest.mock import MagicMock

from src.agent.agents.itinerary_agent import ItineraryAgent
from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import ITINERARY_SYSTEM_PROMPT


class TestItineraryAgent:
    def setup_method(self):
        self.agent = ItineraryAgent(llm=MagicMock())

    def test_extends_specialized_agent(self):
        assert isinstance(self.agent, SpecializedAgent)

    def test_name(self):
        assert self.agent.name == "ItineraryAgent"

    def test_description_is_set(self):
        assert self.agent.description
        assert "itinerar" in self.agent.description.lower()

    def test_system_prompt(self):
        assert self.agent.system_prompt == ITINERARY_SYSTEM_PROMPT

    def test_has_correct_tools(self):
        assert self.agent.tools == []

    def test_tool_count(self):
        assert len(self.agent.tools) == 0

    def test_repr(self):
        assert "ItineraryAgent" in repr(self.agent)
        assert "tools=0" in repr(self.agent)
