"""Run Itinerary Layer 2 from cache-only trajectories."""

from __future__ import annotations

import asyncio

from edd.itinerary.l1_dataset import DATASET
from edd.itinerary.l2_judge import JUDGES, build_judge
from edd.itinerary.run_utils import (
    load_cached_itinerary_trajectories,
    require_judge_approval,
)
from edd.models import MODELS

AGENT = "terra"


async def main() -> None:
    queries = [case["query"] for case in DATASET]
    trajectories = load_cached_itinerary_trajectories(
        queries, model_config=MODELS[AGENT]
    )
    require_judge_approval(
        layer="Layer 2", estimated_calls=len(trajectories) * len(JUDGES)
    )
    judge = build_judge()
    for case, trajectory in zip(DATASET, trajectories):
        verdicts = await asyncio.gather(
            *(judge_fn(judge, trajectory) for judge_fn in JUDGES)
        )
        print(case["name"], verdicts)


if __name__ == "__main__":
    asyncio.run(main())
