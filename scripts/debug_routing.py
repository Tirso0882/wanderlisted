#!/usr/bin/env python3
"""Debug run: check agent routing and verify handbook generation."""

import asyncio
import sys

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from src.agent.stage4_graph import create_multiagent_travel_graph


async def main():
    g = create_multiagent_travel_graph(checkpointer=MemorySaver())
    result = await g.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "Plan a 5-day trip to Tokyo for a couple. "
                        "Mid-range budget ~$3000. "
                        "Departing from New York JFK November 10-15, 2025. "
                        "Love food and temples."
                    )
                )
            ],
            "session_id": "debug_run",
        },
        config={"configurable": {"thread_id": "debug_run"}},
    )

    comps = result.get("itinerary_components", {})

    print("=== ROUTING ===")
    print("routing:", comps.get("routing", []))
    print("completed_agents:", comps.get("completed_agents", []))
    print()

    print("=== DATA KEYS PRESENT ===")
    for k in [
        "flights", "hotels", "destination", "restaurants",
        "activities", "transportation", "budget", "itinerary",
    ]:
        present = "YES" if k in comps else "NO"
        print(f"  {k}: {present}")
    print()

    print("=== HANDBOOK PATHS ===")
    print(result.get("handbook_paths", "NONE"))
    print()

    print("=== CURRENT AGENT ===")
    print(result.get("current_agent"))
    print()

    for m in reversed(result["messages"]):
        if isinstance(m, AIMessage) and m.content:
            print("=== LAST AI MESSAGE (first 300 chars) ===")
            print(m.content[:300])
            break


asyncio.run(main())
