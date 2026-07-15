"""EDD — observe the HOTELS agent, this time with LangSmith tracing.

Hotels is our second WORKER agent: it calls a LIVE external API (HotelBeds). So
this is also where we start separating the agent's DECISION (which tool, which
args) from the tool RESULT (live data we can't assert on directly).

Run it:
    .venv/bin/python edd/hotels/l1_observe.py
Then open the printed LangSmith URL.
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# 1) Corporate TLS fix. This VERIFIES against the system
#    trust store — it does NOT disable verification.
import truststore  # noqa: E402

truststore.inject_into_ssl()

# 2) Turn LangSmith tracing ON for this run and name the project so the trace
#    is easy to find. (LANGSMITH_API_KEY comes from your .env.)
os.environ["LANGSMITH_TRACING"] = "true"
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.context import collect_runs  # noqa: E402
from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402
from langsmith import Client  # noqa: E402

from edd.harness import run_agent  # shared "run + capture" machinery
from src.agent.agents import HotelsAgent  # noqa: E402


async def main() -> None:
    query = (
        "Find hotels in Bogota for 2026-09-01 to 2026-09-09 for 1 adult. "
        "I only want boutique hotels with a rating of 4 stars or higher. "
        "Please provide the hotel name, address, and price per night."
    )

    print(f"\nQUERY: {query}")
    print("=" * 70)

    # collect_runs captures the root run so we can print a direct trace link.
    # The harness runs the agent; we just print the Trajectory it returns.
    with collect_runs() as runs_cb:
        traj = await run_agent(HotelsAgent, query)

    if traj.error:
        print(f"ERROR: {traj.error}")
        wait_for_all_tracers()
        return

    for tool_call in traj.tool_calls:
        print(f"\n  [TOOL CALL ] {tool_call['name']}")
        print(f"              args = {tool_call['args']}")
    for name, output in traj.tool_outputs:
        preview = output if len(output) <= 600 else output[:600] + " …[truncated]"
        print(f"\n  [TOOL RESULT] {name}")
        for line in preview.splitlines():
            print(f"              {line}")
    if traj.final_text:
        print("\nFINAL ANSWER")
        print("-" * 70)
        print(traj.final_text)

    # Flush spans to LangSmith, then print a direct link to the trace.
    wait_for_all_tracers()
    print("\n" + "=" * 70)
    try:
        run = runs_cb.traced_runs[0]
        print(f"LangSmith trace: {Client().read_run(run.id).url}")
    except Exception as exc:  # noqa: BLE001
        project = os.environ["LANGSMITH_PROJECT"]
        print(
            f"Trace sent. Open smith.langchain.com → project '{project}' → newest run"
        )
        print(f"(couldn't auto-fetch the URL: {type(exc).__name__})")


if __name__ == "__main__":
    asyncio.run(main())
