"""Quick check if fast/utility tiers also need Responses API."""

import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI

load_dotenv()


@tool
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello {name}"


async def test_tier(deployment: str, label: str) -> None:
    print(f"\n--- {label}: {deployment} ---")
    # Without use_responses_api (Chat Completions)
    llm = AzureChatOpenAI(
        azure_deployment=deployment,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )
    try:
        result = await llm.ainvoke([HumanMessage(content="Hi")])
        print(f"  Chat Completions: OK — {str(result.content)[:80]}")
    except Exception as exc:
        print(f"  Chat Completions: FAIL — {type(exc).__name__}: {exc}")

    # With use_responses_api
    llm2 = AzureChatOpenAI(
        azure_deployment=deployment,
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        use_responses_api=True,
    )
    try:
        result2 = await llm2.ainvoke([HumanMessage(content="Hi")])
        print(f"  Responses API: OK — {str(result2.content)[:80]}")
    except Exception as exc:
        print(f"  Responses API: FAIL — {type(exc).__name__}: {exc}")


async def main():
    reasoning = os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
    fast = os.environ.get("AZURE_OPENAI_FAST_DEPLOYMENT_NAME")
    utility = os.environ.get("AZURE_OPENAI_UTILITY_DEPLOYMENT_NAME")

    await test_tier(reasoning, "reasoning")
    if fast:
        await test_tier(fast, "fast")
    if utility:
        await test_tier(utility, "utility")


if __name__ == "__main__":
    asyncio.run(main())
