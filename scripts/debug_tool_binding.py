"""Debug: test gpt-5.4-pro tool binding to capture the exact 400 error."""
import asyncio
import traceback

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from src.agent.llm import get_llm


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Sunny, 22C in {city}"


async def main():
    llm = get_llm(tier="reasoning")
    underlying = llm._llm if hasattr(llm, "_llm") else llm

    print(f"Model wrapper: {type(llm).__name__}")
    print(f"Underlying: {type(underlying).__name__}")
    if hasattr(underlying, "azure_deployment"):
        print(f"Deployment: {underlying.azure_deployment}")
    if hasattr(underlying, "api_version"):
        print(f"API Version: {underlying.api_version}")
    if hasattr(underlying, "azure_endpoint"):
        print(f"Endpoint: {underlying.azure_endpoint}")
    if hasattr(underlying, "model_name"):
        print(f"Model name: {underlying.model_name}")

    print("\n=== Test 1: bind_tools + ainvoke ===")
    try:
        bound = llm.bind_tools([get_weather])
        result = await bound.ainvoke(
            [HumanMessage(content="What is the weather in Paris?")]
        )
        content = result.content[:200] if result.content else "(tool call)"
        print(f"  SUCCESS: {content}")
        if result.tool_calls:
            print(f"  Tool calls: {result.tool_calls}")
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")
        # Walk the exception chain to find the HTTP response
        current = exc
        found = False
        while current:
            if hasattr(current, "response"):
                resp = current.response
                print(f"  HTTP Status: {resp.status_code}")
                print(f"  HTTP Headers: {dict(resp.headers)}")
                try:
                    print(f"  HTTP Body: {resp.text[:1000]}")
                except Exception:
                    print("  HTTP Body: (could not read)")
                found = True
                break
            current = getattr(current, "__cause__", None) or getattr(
                current, "__context__", None
            )

        if not found:
            # Check RetryError's nested futures
            for arg in getattr(exc, "args", []):
                if hasattr(arg, "result"):
                    try:
                        arg.result()
                    except Exception as inner_exc:
                        inner_current = inner_exc
                        while inner_current:
                            if hasattr(inner_current, "response"):
                                resp = inner_current.response
                                print(f"  HTTP Status: {resp.status_code}")
                                print(f"  HTTP Headers: {dict(resp.headers)}")
                                try:
                                    print(f"  HTTP Body: {resp.text[:1000]}")
                                except Exception:
                                    pass
                                found = True
                                break
                            inner_current = getattr(
                                inner_current, "__cause__", None
                            )
                if found:
                    break

        if not found:
            print("  Full traceback:")
            traceback.print_exc()

    print("\n=== Test 2: plain ainvoke (no tools) ===")
    try:
        result = await llm.ainvoke(
            [HumanMessage(content="What is the weather in Paris?")]
        )
        print(f"  SUCCESS: {result.content[:200]}")
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")

    print("\n=== Test 3: bind_tools on underlying model directly (bypass semaphore) ===")
    try:
        bound = underlying.bind_tools([get_weather])
        result = await bound.ainvoke(
            [HumanMessage(content="What is the weather in Paris?")]
        )
        content = result.content[:200] if result.content else "(tool call)"
        print(f"  SUCCESS: {content}")
        if result.tool_calls:
            print(f"  Tool calls: {result.tool_calls}")
    except Exception as exc:
        print(f"  FAIL: {type(exc).__name__}: {exc}")
        current = exc
        while current:
            if hasattr(current, "response"):
                resp = current.response
                print(f"  HTTP Status: {resp.status_code}")
                try:
                    print(f"  HTTP Body: {resp.text[:1000]}")
                except Exception:
                    pass
                break
            current = getattr(current, "__cause__", None) or getattr(
                current, "__context__", None
            )

    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
