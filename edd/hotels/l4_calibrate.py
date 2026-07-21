"""EDD Layer 4 — CALIBRATE the HOTELS faithfulness judge against human labels.

The hotel analog of edd/flights/l4_calibrate.py — now a thin wrapper, because the
calibration math + reporting live in edd/calibration.py (shared by every agent).
This file just points the shared runner at the HOTEL judge and the HOTEL labeled
cases and reads κ + bias.

    human label (ground truth)  ─┐
                                 ├─ compare ─> agreement metrics ─> trust / recalibrate
    LLM judge score (under test)─┘

A bad calibration is a signal to fix the RUBRIC (edd/hotels/l2_judge.py) and
re-run — NEVER to bend the human labels to match the judge.

Run it:
    .venv/bin/python edd/hotels/l4_calibrate.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import truststore  # noqa: E402  (trust the OS store; never disable verification)

truststore.inject_into_ssl()
os.environ["LANGSMITH_TRACING"] = "false"  # hermetic — just the metrics
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from edd.calibration import run_calibration  # noqa: E402
from edd.hotels.l2_judge import build_judge, judge_faithfulness  # noqa: E402
from edd.hotels.l2_judge_cases import JUDGE_CASES  # noqa: E402


async def main() -> None:
    await run_calibration(
        build_judge=build_judge,
        judge_faithfulness=judge_faithfulness,
        cases=JUDGE_CASES,
        agent="Hotels",
        rubric_module="edd/hotels/l2_judge.py",
    )
    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
