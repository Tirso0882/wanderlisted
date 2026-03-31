"""Unit tests for ActivitiesAgent — class structure and tool registration."""

from unittest.mock import MagicMock

from src.agent.agents.activities_agent import ActivitiesAgent
from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import ACTIVITIES_SYSTEM_PROMPT


class TestActivitiesAgent:
    def setup_method(self):
        self.agent = ActivitiesAgent(llm=MagicMock())

    def test_extends_specialized_agent(self):
        assert isinstance(self.agent, SpecializedAgent)

    def test_name(self):
        assert self.agent.name == "ActivitiesAgent"

    def test_description_is_set(self):
        assert self.agent.description
        assert "attraction" in self.agent.description.lower() or "experience" in self.agent.description.lower()

    def test_system_prompt(self):
        assert self.agent.system_prompt == ACTIVITIES_SYSTEM_PROMPT

    def test_has_correct_tools(self):
        tool_names = {t.name for t in self.agent.tools}
        assert "search_places_nearby" in tool_names
        assert "search_places_text" in tool_names

    def test_tool_count(self):
        assert len(self.agent.tools) == 2

    def test_repr(self):
        assert "ActivitiesAgent" in repr(self.agent)
        assert "tools=2" in repr(self.agent)
