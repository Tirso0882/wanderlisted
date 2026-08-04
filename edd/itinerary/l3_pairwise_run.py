"""Run Itinerary Layer 3 using two cache-only snapshots."""

from __future__ import annotations

import asyncio

from edd.itinerary.l1_dataset import DATASET
from edd.itinerary.l3_pairwise import build_pairwise_judge, judge_pairwise
from edd.itinerary.run_utils import (
    load_cached_itinerary_trajectories,
    require_judge_approval,
)
from edd.models import MODELS

LINEUP = ("terra", "luna")


async def main() -> None:
    queries = [case["query"] for case in DATASET]
    arms = {
        name: load_cached_itinerary_trajectories(
            queries, model_config=MODELS[name]
        )
        for name in LINEUP
    }
    require_judge_approval(layer="Layer 3", estimated_calls=len(DATASET) * 2)
    judge = build_pairwise_judge(**MODELS["sol"])
    for case, first, second in zip(DATASET, arms[LINEUP[0]], arms[LINEUP[1]]):
        print(case["name"], await judge_pairwise(judge, first, second))


if __name__ == "__main__":
    asyncio.run(main())
