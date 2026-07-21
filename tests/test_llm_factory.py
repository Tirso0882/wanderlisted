"""Regression tests for the LLM provider factory (``src/agent/llm.py``).

Guards the gpt-5.4 reasoning-model invariants documented in
.github/skills/responses-api-reasoning/SKILL.md:

  * Every tier MUST enable the Responses API. Tool calling is not supported in
    Chat Completions with ``reasoning: none``, so silently turning this off
    breaks every tool-calling agent.
  * The factory must apply the per-tier ``reasoning_effort``.
  * Every LLM must be wrapped in the concurrency-gating ``_SemaphoreLLM`` proxy.

The integration smoke test reproduces the historical hang (``use_responses_api``
+ tool binding on the fast tier) and asserts it returns rather than hanging.
"""

import asyncio
import importlib
import os

import pytest
import dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool

from src.agent.concurrency import _SemaphoreLLM
from src.agent.llm import _TIER_REASONING_EFFORT, get_llm
from tests.conftest import skip_no_azure_openai


@pytest.fixture
def fake_azure_env(monkeypatch):
    """Fake Azure credentials so the factory builds a model without any network
    call (construction is offline; only ``ainvoke`` would hit the API)."""
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-key")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "fake-deployment")
    # Don't let a real .env's tier-specific deployments change resolution.
    monkeypatch.delenv("AZURE_OPENAI_FAST_DEPLOYMENT_NAME", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_UTILITY_DEPLOYMENT_NAME", raising=False)


class TestLLMFactoryConfig:
    def test_dotenv_does_not_override_process_configuration(self, monkeypatch):
        import src.agent.llm as llm_module

        loaded_with_override = []

        def fake_load_dotenv(*args, override=False, **kwargs):
            loaded_with_override.append(override)
            for variable in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
                if override or variable not in os.environ:
                    os.environ[variable] = "true"
            return True

        with monkeypatch.context() as context:
            context.setattr(dotenv, "load_dotenv", fake_load_dotenv)
            context.setenv("LANGSMITH_TRACING", "false")
            context.setenv("LANGCHAIN_TRACING_V2", "false")

            importlib.reload(llm_module)

            assert loaded_with_override == [False]
            assert os.environ["LANGSMITH_TRACING"] == "false"
            assert os.environ["LANGCHAIN_TRACING_V2"] == "false"

        importlib.reload(llm_module)

    @pytest.mark.parametrize("tier", ["reasoning", "fast", "utility"])
    def test_responses_api_enabled_for_every_tier(self, fake_azure_env, tier):
        # Critical bug-guard: disabling this breaks gpt-5.4 tool calling.
        llm = get_llm(tier=tier)
        assert llm.use_responses_api is True

    @pytest.mark.parametrize("tier", ["reasoning", "fast", "utility"])
    def test_reasoning_effort_matches_source_of_truth(self, fake_azure_env, tier):
        # Compare against the factory's own mapping — never hardcode the values.
        llm = get_llm(tier=tier)
        assert llm.reasoning_effort == _TIER_REASONING_EFFORT[tier]

    def test_llm_is_semaphore_gated(self, fake_azure_env):
        # Every LLM must go through the per-tier concurrency proxy.
        assert isinstance(get_llm(tier="fast"), _SemaphoreLLM)


@tool
def _echo_city(city: str) -> str:
    """Return the city name (trivial tool for smoke-testing tool binding)."""
    return city


@pytest.mark.integration
class TestFastTierToolCallingSmoke:
    @skip_no_azure_openai
    async def test_fast_tier_tool_binding_does_not_hang(self):
        """Historical bug: ``use_responses_api=True`` + ``bind_tools()`` hung
        indefinitely. ``asyncio.wait_for`` turns a hang into a loud failure
        instead of blocking CI forever."""
        llm = get_llm(tier="fast").bind_tools([_echo_city])
        response = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content="Use the tool with city='Paris'.")]),
            timeout=60,
        )
        assert isinstance(response, AIMessage)
