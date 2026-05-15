"""Verify use_responses_api=True works with AzureChatOpenAI + tools."""
import asyncio
import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import AzureChatOpenAI

load_dotenv()


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Sunny, 22C in {city}"


async def main():
    llm = AzureChatOpenAI(
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        use_responses_api=True,
    )

    print(f"Deployment: {llm.deployment_name}")
    print(f"use_responses_api: {llm.use_responses_api}")

    # Test 1: plain ainvoke
    print("\n=== Test 1: plain ainvoke ===")
    try:
        result = await llm.ainvoke([HumanMessage(content="Say hello in one word")])
        print(f"  SUCCESS: {result.content[:200]}")
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")

    # Test 2: bind_tools + ainvoke
    print("\n=== Test 2: bind_tools + ainvoke ===")
    try:
        bound = llm.bind_tools([get_weather])
        result = await bound.ainvoke(
            [HumanMessage(content="What is the weather in Paris?")]
        )
        content = result.content[:200] if result.content else "(no text content)"
        print(f"  SUCCESS: {content}")
        if result.tool_calls:
            print(f"  Tool calls: {result.tool_calls}")
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")
        if hasattr(exc, "response"):
            print(f"  HTTP {exc.response.status_code}: {exc.response.text[:500]}")

    # Test 3: multi-turn with tool result
    print("\n=== Test 3: full tool loop ===")
    try:
        from langchain_core.messages import ToolMessage

        bound = llm.bind_tools([get_weather])
        # Initial call — model should request tool
        msg1 = await bound.ainvoke(
            [HumanMessage(content="What is the weather in Paris?")]
        )
        if msg1.tool_calls:
            tc = msg1.tool_calls[0]
            print(f"  Model requested tool: {tc['name']}({tc['args']})")
            tool_result = get_weather.invoke(tc["args"])
            msg2 = await bound.ainvoke(
                [
                    HumanMessage(content="What is the weather in Paris?"),
                    msg1,
                    ToolMessage(content=tool_result, tool_call_id=tc["id"]),
                ]
            )
            print(f"  Final response: {msg2.content[:200]}")
        else:
            print(f"  No tool call: {msg1.content[:200]}")
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")

    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
