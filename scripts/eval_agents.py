"""Upload and evaluate the Wanderlisted travel-planning dataset in LangSmith.

Usage:
    python scripts/eval_agents.py --upload-dataset
    python scripts/eval_agents.py --run
    python scripts/eval_agents.py --run --prefix "v5-gpt4o-mini"
"""

import argparse
import asyncio
import os
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("LANGSMITH_TRACING", "true")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client, evaluate  # noqa: E402

from src.evaluation.evaluators import (  # noqa: E402
    budget_completeness,
    correct_destination,
    correct_tool_routing,
    handbook_section_completeness,
    non_empty_response,
    travel_quality_judge,
    valid_routing_decision,
)
from src.evaluation.golden_dataset import GOLDEN_DATASET  # noqa: E402

DATASET_NAME = "Wanderlisted Travel Planning Golden Dataset"


def upload_dataset() -> str:
    """Replace the travel-planning golden dataset in LangSmith."""
    client = Client()
    try:
        existing = client.read_dataset(dataset_name=DATASET_NAME)
        print(
            f"Dataset '{DATASET_NAME}' already exists (id={existing.id}). "
            "Deleting and recreating."
        )
        client.delete_dataset(dataset_id=existing.id)
    except Exception:
        pass

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="Golden dataset for Wanderlisted travel-planning evaluation",
    )
    client.create_examples(
        inputs=[case["inputs"] for case in GOLDEN_DATASET],
        outputs=[case["outputs"] for case in GOLDEN_DATASET],
        dataset_id=dataset.id,
    )
    print(f"Uploaded {len(GOLDEN_DATASET)} examples (id={dataset.id})")
    return str(dataset.id)


async def wanderlisted_target(inputs: dict) -> dict:
    """Run the complete graph and return fields consumed by evaluators."""
    from langchain_core.messages import HumanMessage
    from langgraph.checkpoint.memory import InMemorySaver

    from src.agent.stage4_graph import create_multiagent_travel_graph

    graph = create_multiagent_travel_graph(checkpointer=InMemorySaver())
    try:
        result = await asyncio.wait_for(
            graph.ainvoke(
                {"messages": [HumanMessage(content=inputs["question"])]},
                config={"configurable": {"thread_id": f"eval-{uuid.uuid4()}"}},
            ),
            timeout=180,
        )
    except asyncio.TimeoutError:
        return {"output": "TIMEOUT", "destinations_covered": [], "agents_routed": []}
    except Exception as exc:
        return {
            "output": f"ERROR: {exc}",
            "destinations_covered": [],
            "agents_routed": [],
        }

    components = result.get("itinerary_components", {})
    return {
        "output": result["messages"][-1].content,
        "destinations_covered": result.get("destinations", []),
        "agents_routed": components.get("routing", []),
        "budget_structured": components.get("budget_structured", {}),
        "tools_called": components.get("tools_called", []),
    }


def run_evaluation(prefix: str, *, use_llm_judge: bool = True) -> None:
    """Run the travel-planning evaluation experiment."""
    evaluators = [
        correct_tool_routing,
        valid_routing_decision,
        budget_completeness,
        correct_destination,
        non_empty_response,
        handbook_section_completeness,
    ]
    if use_llm_judge:
        evaluators.append(travel_quality_judge)

    evaluate(
        wanderlisted_target,
        data=DATASET_NAME,
        evaluators=evaluators,
        experiment_prefix=prefix,
        max_concurrency=2,
        metadata={
            "model": os.environ.get("OPENAI_MODEL", "configured-provider"),
            "prompt_version": "destination-tavily-v1",
        },
    )
    print("Done. View results at https://smith.langchain.com")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wanderlisted Agent Evaluation")
    parser.add_argument("--upload-dataset", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--prefix", default="wanderlisted-eval")
    parser.add_argument("--no-llm-judge", action="store_true")
    args = parser.parse_args()

    if args.upload_dataset:
        upload_dataset()
    if args.run:
        run_evaluation(args.prefix, use_llm_judge=not args.no_llm_judge)
    if not args.upload_dataset and not args.run:
        parser.print_help()


if __name__ == "__main__":
    main()
