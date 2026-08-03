"""Observe one traced TravelReadinessAgent trajectory before evaluating it."""

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

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402
from langsmith import Client, trace  # noqa: E402

from edd.readiness.run_utils import (  # noqa: E402
    _redact_sensitive_text,
    run_readiness_agent,
)
from src.agent.agents import TravelReadinessAgent  # noqa: E402
from src.models import TripRequest  # noqa: E402


async def main() -> None:
    query = "What etiquette and dining customs should I know before visiting Tokyo?"
    trip_request = TripRequest(destinations=["tokyo"], readiness_topics=["culture"])
    print(f"\nQUERY: {query}")
    print("=" * 70)

    async with trace(
        "readiness_l1_observe",
        inputs={
            "query": query,
            "trip_request": trip_request.model_dump(mode="json"),
        },
        tags=["wanderlisted", "edd", "readiness", "layer-1"],
    ) as observation_run:
        trajectory = await run_readiness_agent(
            TravelReadinessAgent,
            query,
            trip_request=trip_request,
            intent_hint="culture",
        )
        observation_run.end(
            outputs={
                "error": trajectory.error,
                "tool_calls": trajectory.tool_calls,
                "final_text": trajectory.final_text,
            }
        )

    if trajectory.error:
        print(f"ERROR: {trajectory.error}")
        wait_for_all_tracers()
        return

    for tool_call in trajectory.tool_calls:
        print(f"\n  [PIPELINE DECISION] {tool_call['name']}")
        print(f"                      args = {tool_call['args']}")
    for name, output in trajectory.tool_outputs:
        preview = _redact_sensitive_text(output)
        if len(preview) > 1_200:
            preview = preview[:1_200] + " ...[truncated]"
        print(f"\n  [EVIDENCE] {name}")
        for line in preview.splitlines():
            print(f"             {line}")
    if trajectory.final_text:
        print("\nFINAL ANSWER")
        print("-" * 70)
        print(_redact_sensitive_text(trajectory.final_text))

    wait_for_all_tracers()
    print("\n" + "=" * 70)
    try:
        print(f"LangSmith trace: {Client().read_run(observation_run.id).url}")
    except Exception as exc:  # noqa: BLE001
        project = os.environ["LANGSMITH_PROJECT"]
        print(
            f"Trace sent. Open smith.langchain.com -> project '{project}' -> newest run"
        )
        print(f"(could not auto-fetch the URL: {type(exc).__name__})")


if __name__ == "__main__":
    asyncio.run(main())
