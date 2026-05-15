#!/usr/bin/env python
"""Graph smoke test — run a query through the full stage4 graph and show results.

This is Layer 6 testing: validates that the full graph (triage → supervisor
→ parallel agents → fan-in) works end-to-end with real API keys.

Usage:
    python scripts/test_graph_invoke.py                     # default: Tokyo trip
    python scripts/test_graph_invoke.py "Weekend in Verona, Italy"  # custom query
    python scripts/test_graph_invoke.py --simple "Hello"    # test triage → shallow_reply
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage


# ── ANSI helpers ─────────────────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _header(text: str) -> str:
    return f"\n{BOLD}{CYAN}{'═' * 70}\n  {text}\n{'═' * 70}{RESET}\n"


def _agent_line(agent: str, status: str, elapsed: float) -> str:
    color = GREEN if "✓" in status else YELLOW
    return f"  {color}[{agent:20s}]{RESET} {status} ({elapsed:.1f}s)"


async def run_smoke_test(query: str):
    """Run a single query through the stage4 graph and report results."""
    # Lazy import to avoid loading the graph when --help is used
    from src.agent.stage4_graph import graph

    print(_header(f"Graph Smoke Test — {query!r}"))

    config = {"configurable": {"thread_id": f"smoke-{int(time.time())}"}}
    start = time.time()

    # Stream to see node-by-node progress
    last_agent = ""
    agent_start = start
    agents_seen: list[str] = []
    tool_calls: dict[str, list[str]] = {}

    try:
        async for event in graph.astream(
            {"messages": [HumanMessage(query)], "session_id": "smoke-test"},
            config,
            stream_mode="updates",
        ):
            for node_name, node_output in event.items():
                now = time.time()

                # Track agent transitions
                if node_name != last_agent:
                    if last_agent:
                        elapsed = now - agent_start
                        print(_agent_line(last_agent, "✓ done", elapsed))
                    last_agent = node_name
                    agent_start = now
                    agents_seen.append(node_name)
                    print(f"  {YELLOW}[{node_name:20s}]{RESET} running...")

                # Track tool calls from messages
                if isinstance(node_output, dict):
                    for msg in node_output.get("messages", []):
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tool_calls.setdefault(node_name, []).append(
                                    tc.get("name", "?")
                                )

        # Final agent
        if last_agent:
            print(_agent_line(last_agent, "✓ done", time.time() - agent_start))

    except Exception as e:
        elapsed = time.time() - start
        if "interrupt" in str(type(e).__name__).lower() or "interrupt" in str(e).lower():
            print(f"\n  {YELLOW}⏸  HITL interrupt after {elapsed:.1f}s{RESET}")
            print(f"  Agents reached: {' → '.join(agents_seen)}")
        else:
            print(f"\n  {RED}✗ FAILED after {elapsed:.1f}s: {e}{RESET}")
            raise

    total = time.time() - start

    # ── Summary ──────────────────────────────────────────────────────────
    print(_header("Summary"))
    print(f"  Query:     {query!r}")
    print(f"  Total:     {total:.1f}s")
    print(f"  Agents:    {' → '.join(agents_seen)}")
    if tool_calls:
        print("  Tool calls:")
        for agent, tools in tool_calls.items():
            print(f"    {agent}: {', '.join(tools)}")
    print()


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--simple" in args:
        args.remove("--simple")
        query = " ".join(args) if args else "Hello, what can you help with?"
    else:
        query = " ".join(args) if args else "Plan a 3-day trip to Amalfi Coast for a couple, mid-range budget"

    asyncio.run(run_smoke_test(query))


if __name__ == "__main__":
    main()
