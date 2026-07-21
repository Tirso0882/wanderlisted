"""Observe one traced RestaurantsAgent trajectory before evaluating it."""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import truststore  # noqa: E402

truststore.inject_into_ssl()
os.environ["LANGSMITH_TRACING"] = "true"
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.context import collect_runs  # noqa: E402
from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402
from langsmith import Client  # noqa: E402

from edd.harness import run_agent  # noqa: E402
from edd.restaurants.run_utils import _redact_sensitive_text  # noqa: E402
from src.agent.agents import RestaurantsAgent  # noqa: E402


async def main() -> None:
    query = "Find vegan ramen restaurants in Kyoto for a budget traveler."
    print(f"\nQUERY: {query}")
    print("=" * 70)

    with collect_runs() as runs_callback:
        trajectory = await run_agent(RestaurantsAgent, query)

    if trajectory.error:
        print(f"ERROR: {trajectory.error}")
        wait_for_all_tracers()
        return

    for tool_call in trajectory.tool_calls:
        print(f"\n  [TOOL CALL ] {tool_call['name']}")
        print(f"              args = {tool_call['args']}")
    for name, output in trajectory.tool_outputs:
        output = _redact_sensitive_text(output)
        preview = output if len(output) <= 600 else output[:600] + " ...[truncated]"
        print(f"\n  [TOOL RESULT] {name}")
        for line in preview.splitlines():
            print(f"              {line}")
    if trajectory.final_text:
        print("\nFINAL ANSWER")
        print("-" * 70)
        print(_redact_sensitive_text(trajectory.final_text))

    wait_for_all_tracers()
    print("\n" + "=" * 70)
    try:
        run = runs_callback.traced_runs[0]
        print(f"LangSmith trace: {Client().read_run(run.id).url}")
    except Exception as exc:  # noqa: BLE001
        project = os.environ["LANGSMITH_PROJECT"]
        print(
            f"Trace sent. Open smith.langchain.com -> project '{project}' -> newest run"
        )
        print(f"(could not auto-fetch the URL: {type(exc).__name__})")


if __name__ == "__main__":
    asyncio.run(main())
