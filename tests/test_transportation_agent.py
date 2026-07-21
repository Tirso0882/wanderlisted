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

    def test_prompt_enforces_requested_route_call_policy(self):
        prompt = self.agent.system_prompt

        assert "use exactly that mode for every requested pair" in prompt
        assert "never route an earlier or nearby substitute" in prompt
        assert "do not also decompose it into legs" in prompt
        assert "one point-to-point call per consecutive requested leg" in prompt

    def test_prompt_matches_tool_evidence_limits(self):
        prompt = self.agent.system_prompt

        assert "It does NOT return fares or costs" in prompt
        assert "departure times, timetables, frequency, or waiting time" in prompt
        assert "accessibility, step-free, ramp, lift, or" in prompt
        assert "Never state or infer those details from memory" in prompt

    def test_tool_description_exposes_the_same_contract(self):
        description = next(
            tool.description
            for tool in self.agent.tools
            if tool.name == "compute_route"
        )

        assert "does not contain" in description
        assert "fares or pass validity" in description
        assert "one call per consecutive leg" in description

    def test_has_correct_tools(self):
        tool_names = {t.name for t in self.agent.tools}
        assert "compute_route" in tool_names

    def test_tool_count(self):
        assert len(self.agent.tools) == 1

    def test_repr(self):
        assert "TransportationAgent" in repr(self.agent)
        assert "tools=1" in repr(self.agent)
