#!/usr/bin/env python3
"""Debug the readiness structured-output path against the configured model."""

import asyncio
import os

from src.agent.agents import TravelReadinessAgent
from src.agent.llm import get_llm
from src.models import TripRequest

os.environ["LANGCHAIN_TRACING_V2"] = "false"


async def main() -> None:
    llm = get_llm(tier="reasoning")
    agent = TravelReadinessAgent(llm)
    try:
        result = await agent.research(
            question="Tokyo dining etiquette",
            trip_request=TripRequest(
                destinations=["tokyo"], readiness_topics=["culture"]
            ),
        )
        print(result.message)
    finally:
        await agent.aclose()


if __name__ == "__main__":
    asyncio.run(main())
