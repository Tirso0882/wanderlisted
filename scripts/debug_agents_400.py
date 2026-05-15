"""Debug: test each agent executor individually to find which one triggers 400."""

import asyncio

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from src.agent.llm import get_llm
from src.agent.agents import (
    FlightsAgent,
    HotelsAgent,
    DestinationAgent,
    RestaurantsAgent,
    ActivitiesAgent,
    TransportationAgent,
)

AGENT_TIERS = {
    "FlightsAgent": "fast",
    "HotelsAgent": "fast",
    "RestaurantsAgent": "fast",
    "ActivitiesAgent": "fast",
    "TransportationAgent": "fast",
    "DestinationAgent": "fast",
}

AGENT_CLASSES = {
    "FlightsAgent": FlightsAgent,
    "HotelsAgent": HotelsAgent,
    "RestaurantsAgent": RestaurantsAgent,
    "ActivitiesAgent": ActivitiesAgent,
    "TransportationAgent": TransportationAgent,
    "DestinationAgent": DestinationAgent,
}


async def test_single_agent(name: str):
    tier = AGENT_TIERS[name]
    llm = get_llm(tier=tier)
    cls = AGENT_CLASSES[name]
    agent = cls(llm)
    executor = create_agent(
        model=llm,
        tools=agent.tools,
        system_prompt=agent.system_prompt,
    )
    try:
        result = await executor.ainvoke(
            {
                "messages": [
                    HumanMessage(content="3-day trip to Paris, mid-range budget")
                ]
            },
        )
        msgs = result.get("messages", [])
        print(f"  OK — {name}: {len(msgs)} messages")
    except Exception as e:
        print(f"  FAIL — {name}: {type(e).__name__}: {e}")


async def main():
    for name in AGENT_CLASSES:
        print(f"Testing {name} (tier={AGENT_TIERS[name]})...")
        await test_single_agent(name)
        print()


if __name__ == "__main__":
    asyncio.run(main())
