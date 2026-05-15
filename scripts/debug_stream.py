"""Debug script: reproduce the 400 error during streaming."""
import asyncio

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.agent.stage4_graph import create_multiagent_travel_graph


async def main():
    checkpointer = InMemorySaver()
    graph = create_multiagent_travel_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "test-debug-1"}}

    print("=== Test 1: astream with updates mode (what our API uses) ===")
    try:
        async for node_output in graph.astream(
            {"messages": [HumanMessage(content="Plan a 3-day trip to Paris")]},
            config=config,
            stream_mode="updates",
        ):
            for node_name, update in node_output.items():
                msgs = update.get("messages", [])
                print(f"  NODE {node_name}: {len(msgs)} messages")
        print("  SUCCESS")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    print("\n=== Test 2: astream_events (what langgraph dev uses) ===")
    config2 = {"configurable": {"thread_id": "test-debug-2"}}
    try:
        async for event in graph.astream_events(
            {"messages": [HumanMessage(content="Plan a 3-day trip to Paris")]},
            config=config2,
            version="v2",
        ):
            kind = event["event"]
            name = event.get("name", "")
            if kind == "on_chain_start" and name:
                print(f"  CHAIN_START: {name}")
            elif kind == "on_chat_model_start":
                print(f"  CHAT_START: {name}")
            elif kind == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    print(f"  TOKEN({name}): {token[:60]}")
            elif kind == "on_tool_start":
                print(f"  TOOL_START: {name}")
            elif kind == "on_chat_model_end":
                print(f"  CHAT_END: {name}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    print("\n=== Done ===")


if __name__ == "__main__":
    asyncio.run(main())
