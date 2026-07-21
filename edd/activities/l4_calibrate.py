"""Calibrate the Activities faithfulness judge against human labels."""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import truststore  # noqa: E402

truststore.inject_into_ssl()
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("LANGSMITH_PROJECT", "wanderlisted-edd")

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from langchain_core.tracers.langchain import wait_for_all_tracers  # noqa: E402

from edd.activities.l2_judge import (  # noqa: E402
    build_judge,
    judge_faithfulness,
)
from edd.activities.l2_judge_cases import JUDGE_CASES  # noqa: E402
from edd.calibration import run_calibration  # noqa: E402

JUDGE_CASE_CONCURRENCY = 3


async def main() -> None:
    judge_semaphore = asyncio.Semaphore(JUDGE_CASE_CONCURRENCY)

    async def bounded_judge_faithfulness(judge, trajectory):
        async with judge_semaphore:
            return await judge_faithfulness(judge, trajectory)

    await run_calibration(
        build_judge=build_judge,
        judge_faithfulness=bounded_judge_faithfulness,
        cases=JUDGE_CASES,
        agent="Activities",
        rubric_module="edd/activities/l2_judge.py",
    )
    wait_for_all_tracers()


if __name__ == "__main__":
    asyncio.run(main())
