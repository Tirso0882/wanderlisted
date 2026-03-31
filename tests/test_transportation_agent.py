"""Unit tests for TransportationAgent — class structure and tool registration."""

from unittest.mock import MagicMock

from src.agent.agents.transportation_agent import TransportationAgent
from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import TRANSPORTATION_SYSTEM_PROMPT


class TestTransportationAgent:
    def setup_method(self):
        self.agent = TransportationAgent(llm=MagicMock())

    def test_extends_specialized_agent(self):
        assert isinstance(self.agent, SpecializedAgent)

    def test_name(self):
        assert self.agent.name == "TransportationAgent"

    def test_description_is_set(self):
        assert self.agent.description
        assert "transport" in self.agent.description.lower()

    def test_system_prompt(self):
        assert self.agent.system_prompt == TRANSPORTATION_SYSTEM_PROMPT

    def test_has_correct_tools(self):
        tool_names = {t.name for t in self.agent.tools}
        assert "get_directions" in tool_names
        assert "get_distance_matrix" in tool_names
        assert "compute_route" in tool_names

    def test_tool_count(self):
        assert len(self.agent.tools) == 3

    def test_repr(self):
        assert "TransportationAgent" in repr(self.agent)
        assert "tools=3" in repr(self.agent)
