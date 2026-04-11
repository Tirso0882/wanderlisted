#!/usr/bin/env python3
"""Debug: run parallel agents individually to find failures."""

import asyncio
import sys
import traceback

sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from src.agent.llm import get_llm
from src.agent.agents import (
    FlightsAgent, HotelsAgent, DestinationAgent,
)


async def test_agent(name, agent_cls):
    print(f"\n{'=' * 60}")
    print(f"Testing {name}...")
    print(f"{'=' * 60}")
    try:
        llm = get_llm()
        agent = agent_cls(llm)
        executor = create_agent(
            model=llm,
            tools=agent.tools,
            system_prompt=agent.system_prompt,
        )
        result = await executor.ainvoke({
            "messages": [
                SystemMessage(content="USER PROFILE:\nDestinations: Tokyo\nTravel style: mid-range\nGroup type: couple"),
                HumanMessage(content="Plan a 5-day trip to Tokyo for a couple. Mid-range budget ~$3000. Departing from New York JFK November 10-15, 2025."),
            ]
        })
        ai_msgs = [m for m in result["messages"] if hasattr(m, "content") and m.content]
        print(f"  SUCCESS: {len(ai_msgs)} messages returned")
        if ai_msgs:
            print(f"  Last message (first 200 chars): {ai_msgs[-1].content[:200]}")
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()


async def main():
    for name, cls in [
        ("FlightsAgent", FlightsAgent),
        ("HotelsAgent", HotelsAgent),
        ("DestinationAgent", DestinationAgent),
    ]:
        await test_agent(name, cls)


asyncio.run(main())
