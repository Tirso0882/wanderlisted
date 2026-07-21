"""Shared eval harness — run ONE agent and capture its trajectory.

The reusable "run + capture" machinery for the whole eval track: give it an
agent class and a query, get back a Trajectory. It is the ONLY code here that
touches the live world (LLM + external API), so all nondeterminism and external
dependencies are encapsulated in one place — which is also where mocking,
retries, timeouts, and caching belong.

Consumers:
  - *_observe.py  -> print a Trajectory (look at what the agent did)
  - *_run.py      -> score Trajectory.tool_calls with evaluators
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agent.agents.base import SpecializedAgent
from src.agent.llm import get_llm


def extract_text(content) -> str:
    """Read text from a LangChain message.content.

    Reasoning models (the gpt-5.6 family, via the Responses API) return content
    as a list of blocks [{"type": "text", "text": "..."}], not a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content or "")


@dataclass
class Trajectory:
    """A structured record of ONE isolated agent run — what we observe & score.

    tool_calls   : [{"name", "args"}]  -> the DECISION (what the evaluators score)
    tool_outputs : [(name, text)]      -> the RESULT of each tool (for observing)
    final_text   : the agent's final answer
    error        : set instead of raising, so one bad case can't crash a run
    """

    query: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_outputs: list[tuple[str, str]] = field(default_factory=list)
    final_text: str = ""
    error: str | None = None


async def run_agent(
    agent_cls: type[SpecializedAgent],
    query: str,
    *,
    tier: str = "fast",
    effort: str | None = None,
    timeout: float = 90.0,
    **model_kwargs,
) -> Trajectory:
    """Run ONE agent exactly like production and capture its Trajectory.

    Mirrors src/agent/stage4_graph.py: create_agent(model, tools, system_prompt)
    on the agent's real tier, then a single ainvoke with only the user query
    (isolation — no upstream graph context). Any failure is captured as
    Trajectory.error rather than raised, so one bad case can't crash a run.

    The model is fully configurable, which is what makes a Layer 3 A/B clean —
    vary exactly ONE of these between the two arms:
      • `tier`   — one of the three env-configured deployments
                   (reasoning / fast / utility).
      • `effort` — override the tier's default reasoning effort.
      • `**model_kwargs` — forwarded verbatim to get_llm(), so you can pin ANY
                   model directly: azure_deployment="gpt-5.6-sol" (Azure),
                   model="gpt-4o" (openai/anthropic/…), temperature=..., etc.
    """
    overrides = dict(model_kwargs)
    if effort:
        overrides["reasoning_effort"] = effort
    model = get_llm(tier=tier, **overrides)
    agent = agent_cls(model)
    executor = create_agent(
        model=model, tools=agent.tools, system_prompt=agent.system_prompt
    )

    try:
        result = await asyncio.wait_for(
            executor.ainvoke({"messages": [HumanMessage(content=query)]}),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return Trajectory(query=query, error=f"timeout after {timeout:.0f}s")
    except Exception as exc:  # noqa: BLE001 — capture infra/model errors as data
        return Trajectory(query=query, error=f"{type(exc).__name__}: {exc}")

    traj = Trajectory(query=query)
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage):
            for tool_call in msg.tool_calls or []:
                traj.tool_calls.append(
                    {"name": tool_call["name"], "args": tool_call.get("args", {}) or {}}
                )
            text = extract_text(msg.content)
            if text:
                traj.final_text = text
        elif isinstance(msg, ToolMessage):
            traj.tool_outputs.append((msg.name or "", extract_text(msg.content)))
    return traj
