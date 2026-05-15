"""Debug: check exactly what create_agent binds and sends to Azure."""
import os

os.environ["LANGCHAIN_TRACING_V2"] = "false"

from src.agent.agents import DestinationAgent
from src.agent.llm import get_llm
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
import asyncio


def main():
    llm = get_llm(tier="reasoning")
    agent = DestinationAgent(llm)

    # Get the raw model from the semaphore proxy
    raw_model = object.__getattribute__(llm, "_model")
    print(f"Model type: {type(raw_model).__name__}")
    print(f"Deployment: {getattr(raw_model, 'azure_deployment', 'unknown')}")
    print(f"API version: {getattr(raw_model, 'openai_api_version', 'unknown')}")
    print(f"Streaming: {getattr(raw_model, 'streaming', 'unknown')}")
    print()

    # Check what bind_tools produces
    bound = raw_model.bind_tools(agent.tools)
    for k, v in bound.kwargs.items():
        if k == "tools":
            print(f"bind_tools sends {len(v)} tools")
            for t in v:
                fname = t.get("function", {}).get("name", "?")
                strict = t.get("function", {}).get("strict")
                print(f"  - {fname} (strict={strict})")
        else:
            print(f"bind_tools kwarg: {k} = {str(v)[:200]}")
    print()

    # Test: does bind_tools + ainvoke work with reasoning?
    print("Testing bind_tools + ainvoke on reasoning tier...")
    result = asyncio.run(bound.ainvoke([HumanMessage(content="What tools do you have?")]))
    print(f"  OK: {type(result).__name__}, content={result.content[:100] if result.content else 'none'}")
    print()

    # Now test create_agent
    print("Testing create_agent executor...")
    executor = create_agent(model=llm, tools=agent.tools, system_prompt=agent.system_prompt)

    # Check the model node inside create_agent's graph
    for node_name, node in executor.nodes.items():
        print(f"  Graph node: {node_name}")
    print()

    # Test create_agent with ainvoke
    print("Running create_agent executor.ainvoke()...")
    try:
        result = asyncio.run(executor.ainvoke(
            {"messages": [HumanMessage(content="Tell me about Paris safety")]},
        ))
        msgs = result.get("messages", [])
        print(f"  OK: {len(msgs)} messages")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
