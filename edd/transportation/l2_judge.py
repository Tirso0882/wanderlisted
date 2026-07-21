"""Layer 2 pointwise judges for TransportationAgent answer quality."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402
from edd.rubrics import (  # noqa: E402
    AGENT_SPECS,
    build_judge,
    faithfulness_rubric,
    helpfulness_rubric,
    score_faithfulness,
    score_helpfulness,
)

_SPEC = AGENT_SPECS["transportation"]

_FAITH_EXAMPLES = """EXAMPLES (illustrative anchors - do NOT treat as evidence for the case you score):
  - RESULTS: "Route: Southern Cross Station -> Flinders Street Station\nDistance:
    1.2 km\nDuration: 300s\nMode: TRANSIT\n\nSteps:\n  1. [TRAM 11]
    Southern Cross -> Flinders Street (2 stops) [300s]". ANSWER: "Take Tram 11
    from Southern Cross to Flinders Street: 1.2 km, about 5 minutes, with two
    stops." -> score 3 (mode, line, distance, duration, and stop count are grounded).
  - Same RESULTS. ANSWER: "Tram 11 takes about 5 minutes; it is a pleasant,
    scenic ride." -> score 2 (the scenic claim is one unsupported NON-CORE extra).
  - Same RESULTS. ANSWER: "Take the direct Metro for 2 minutes; the fare is AUD
    4.50." -> score 1 (line/mode, duration, and an invented fare are material
    ROUTE DATA errors)."""

_TRANSPORTATION_EVIDENCE_RULES = """TRANSPORTATION-SPECIFIC EVIDENCE RULES:
  - `Route`, `Distance`, `Duration`, and `Mode` are the authoritative route facts.
    Converting seconds to an accurate approximate duration is faithful; do not
    treat a rounded duration as fabrication.
  - A transit step such as `[TRAIN Elizabeth line] Paddington -> Tottenham Court
    Road (3 stops)` supports only that line, endpoints, and stop count. Do not
    invent extra transfers, platform numbers, schedules, service frequency, or
    real-time reliability.
  - Google Routes returns no fares, passes, accessibility guarantees, reservation
    requirements, luggage rules, or traffic forecasts. An answer may say these
    details were not returned or need checking, but must not assert them as facts.
  - If RESULTS contain `No route found.`, an honest no-route explanation is fully
    grounded. If a route has no step block, do not invent turn-by-turn or transit
    instructions absent from RESULTS.
"""

FAITHFULNESS_RUBRIC = (
    faithfulness_rubric(_SPEC, examples=_FAITH_EXAMPLES)
    + "\n\n"
    + _TRANSPORTATION_EVIDENCE_RULES
)

_TRANSPORTATION_HELPFULNESS_RULES = """TRANSPORTATION PRODUCT PRESENTATION:
  - Surface the recommended/requested mode, distance, duration, and the available
    transit or turn-by-turn steps in a route a traveler can follow.
  - When the request asks about cost, passes, or accessibility but the route output
    does not provide evidence, an explicit limitation and next-check is more useful
    than an unsupported estimate or guarantee.
  - For a comparison request, make each requested route easy to compare; do not
    bury one route or silently omit it.
"""

HELPFULNESS_RUBRIC = (
    helpfulness_rubric(_SPEC) + "\n\n" + _TRANSPORTATION_HELPFULNESS_RULES
)

__all__ = [
    "FAITHFULNESS_RUBRIC",
    "HELPFULNESS_RUBRIC",
    "JUDGES",
    "build_judge",
    "judge_faithfulness",
    "judge_helpfulness",
]


async def judge_faithfulness(judge, trajectory: Trajectory) -> dict:
    return await score_faithfulness(judge, trajectory, rubric=FAITHFULNESS_RUBRIC)


async def judge_helpfulness(judge, trajectory: Trajectory) -> dict:
    return await score_helpfulness(judge, trajectory, rubric=HELPFULNESS_RUBRIC)


JUDGES = [judge_faithfulness, judge_helpfulness]


_EVIDENCE = [
    (
        "compute_route",
        "Route: Fiumicino Airport -> Hotel Artemide, Rome\n"
        "Distance: 31.4 km\n"
        "Duration: 3120s\n"
        "Mode: TRANSIT\n\n"
        "Steps:\n"
        "  1. [TRAIN Leonardo Express] Fiumicino Aeroporto -> Roma Termini "
        "(0 stops) [1920s]\n"
        "  2. Walk to Hotel Artemide (700 m, 1200s)",
    )
]

_GROUNDED_TRAJECTORY = Trajectory(
    query="Give transit directions from Fiumicino Airport to Hotel Artemide in Rome.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "Take the Leonardo Express from Fiumicino Aeroporto to Roma Termini, then "
        "walk 700 m to Hotel Artemide. The 31.4 km transit route takes about 52 minutes."
    ),
)

_HALLUCINATED_TRAJECTORY = Trajectory(
    query="Give transit directions from Fiumicino Airport to Hotel Artemide in Rome.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "Take a direct taxi for EUR 35; it takes only 20 minutes and has no transfers."
    ),
)


async def _demo() -> None:
    judge = build_judge()
    for label, trajectory in (
        ("GROUNDED transportation answer", _GROUNDED_TRAJECTORY),
        ("HALLUCINATED transportation answer", _HALLUCINATED_TRAJECTORY),
    ):
        print(f"\n{label}")
        print("-" * 68)
        print(f"  answer: {trajectory.final_text}\n")
        for judge_fn in JUDGES:
            output = await judge_fn(judge, trajectory)
            score = "SKIP" if output["score"] is None else f"{output['score']}/3"
            print(f"  {output['key']:14s} {score:>4s}   {output['comment']}")
    print()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    import truststore

    truststore.inject_into_ssl()
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    asyncio.run(_demo())
