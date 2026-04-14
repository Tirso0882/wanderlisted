#!/usr/bin/env python3
"""Run Wanderlisted multi-agent travel planner end-to-end.

Generates a full travel handbook (HTML + Markdown + JSON) in outputs/.

Usage:
    .venv/bin/python scripts/run_itinerary.py
"""

import asyncio
import sys
import time

sys.path.insert(0, ".")

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.agent.stage4_graph import create_multiagent_travel_graph

QUERY = (
    "Plan a 5-day trip to Tokyo, Japan for a couple. "
    "We're mid-range budget travelers (~$3,000 total) who love authentic food, "
    "temples, and street photography. "
    "Departing from New York (JFK) on November 10, 2026, returning November 15, 2026. "
    "We'd like one day-trip to Kamakura if possible. "
    "No dietary restrictions. We prefer boutique hotels over chains."
)


async def main():
    print("\n🌍  Wanderlisted — Multi-Agent Travel Planner")
    print("=" * 60)
    print(f"Query: {QUERY[:100]}...")
    print("=" * 60)

    checkpointer = MemorySaver()
    graph = create_multiagent_travel_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "demo_run"}}

    start = time.time()
    print("\n⏳ Running agents... (this takes 1-3 minutes)\n")

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=QUERY)],
            "session_id": "demo_run",
        },
        config=config,
    )

    # Auto-approve HITL interrupts so the full pipeline completes
    max_resumes = 5
    for i in range(max_resumes):
        # Check if the graph was interrupted
        snapshot = await graph.aget_state(config)
        if not snapshot.tasks or not any(
            hasattr(t, "interrupts") and t.interrupts for t in snapshot.tasks
        ):
            break  # No interrupt — graph finished normally

        # Log which interrupt we're auto-approving
        for task in snapshot.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for intr in task.interrupts:
                    payload = intr.value if hasattr(intr, "value") else intr
                    itype = (
                        payload.get("type", "unknown")
                        if isinstance(payload, dict)
                        else "unknown"
                    )
                    print(f"  🔄 Auto-approving HITL interrupt: {itype}")

        result = await graph.ainvoke(
            Command(resume={"approved": True}),
            config=config,
        )

    elapsed = time.time() - start
    print(f"\n✅ Done in {elapsed:.1f}s")

    # Print final AI message
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            print(f"\n{msg.content}")
            break

    # Print handbook paths
    paths = result.get("handbook_paths", {})
    if paths:
        print("\n📁 Output files:")
        for fmt, path in paths.items():
            print(f"   {fmt}: {path}")

    return paths


if __name__ == "__main__":
    paths = asyncio.run(main())
    if paths and "html" in paths:
        print(f"\n💡 Open in browser:  open {paths['html']}")
