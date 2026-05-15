"""Final verification: full graph with use_responses_api=True fix."""
import asyncio

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from src.agent.stage4_graph import create_multiagent_travel_graph


async def main():
    graph = create_multiagent_travel_graph(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "verify-responses-api-final"}}
    nodes_seen = []
    try:
        cnt = 0
        async for node_output in graph.astream(
            {"messages": [HumanMessage(content="Plan a 3-day trip to Paris")]},
            config=config,
            stream_mode="updates",
        ):
            for node_name in node_output:
                nodes_seen.append(node_name)
                cnt += 1
                if cnt % 3 == 0:
                    print(f"  NODE: {node_name}")
        print(f"\nSUCCESS — {len(nodes_seen)} node updates through full pipeline")
        return True
    except Exception as exc:
        print(f"FAIL at node #{len(nodes_seen)} — {type(exc).__name__}: {exc}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
