"""Layer 2 pointwise judges for RestaurantsAgent answer quality."""

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

_SPEC = AGENT_SPECS["restaurants"]

# These Melbourne anchors are deliberately disjoint from l2_judge_cases.py.
_FAITH_EXAMPLES = """EXAMPLES (illustrative anchors - do NOT treat as evidence for the case you score):
  - RESULTS: "Harbour Table, 18 Flinders Lane, Melbourne; Rating 4.6/5
    (340 reviews); Price MODERATE; Summary: modern Australian seafood;
    Status: OPERATIONAL". ANSWER: "Harbour Table is a moderate-price seafood
    restaurant at 18 Flinders Lane, rated 4.6 from 340 reviews." -> score 3
    (every CORE fact is grounded).
  - Same RESULTS. ANSWER: "Harbour Table is rated 4.6 and has a romantic candlelit
    terrace." -> score 2 (the rating is grounded; ambience is one unsupported
    NON-CORE extra).
  - Same RESULTS. ANSWER: "Harbour Table is a cheap, fully vegan restaurant rated
    4.9." -> score 1 (price, dietary suitability, and rating contradict or exceed
    the evidence; materially misleading CORE claims)."""

_RESTAURANT_EVIDENCE_RULES = """RESTAURANT-SPECIFIC EVIDENCE RULES:
  - Dietary proof: words in the REQUEST or search query (such as vegan, halal, or
    gluten-free) describe search intent, not verified venue attributes. A dietary
    claim is grounded only when the returned place name, types, or summary supports
    it. Otherwise the answer must label suitability unverified and advise checking
    with the venue rather than assert compliance.
  - Place identity: attach rating, review count, price, address, hours, status, and
    summary only to the exact place whose result contains them. Moving a fact to a
    similarly named or neighboring venue is a CORE error.
  - Hours and status: a weekly hours listing does not prove a venue is open at the
    traveler's future arrival time. Do not penalize a faithful paraphrase of listed
    hours, but treat an unsupported 'open now/on your date' guarantee as a CORE error.
  - URL compaction: evidence URLs may be represented as <URL>. Do not score URL
    string equality; a Maps or Website field supports providing the corresponding
    link.
"""

FAITHFULNESS_RUBRIC = (
    faithfulness_rubric(_SPEC, examples=_FAITH_EXAMPLES)
    + "\n\n"
    + _RESTAURANT_EVIDENCE_RULES
)

_RESTAURANT_HELPFULNESS_RULES = """RESTAURANT PRODUCT PRESENTATION:
  - Dietary suitability must be explicit when the request includes a restriction;
    an honest 'not verified - contact the venue' caveat is more helpful than an
    unsupported guarantee.
  - Maps/website links render compactly downstream. Ignore raw URL length, but
    penalize duplicated or irrelevant links that make choices hard to compare.
"""

HELPFULNESS_RUBRIC = helpfulness_rubric(_SPEC) + "\n\n" + _RESTAURANT_HELPFULNESS_RULES

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
        "search_places_text",
        "Found 1 result(s):\n\n"
        "* Sora Vegan Ramen\n"
        "  Address: 12 Kawaramachi, Kyoto\n"
        "  Rating: 4.7/5 (516 reviews)\n"
        "  Price: INEXPENSIVE\n"
        "  Summary: Fully vegan ramen and Japanese small plates\n"
        "  Status: OPERATIONAL\n"
        "  Types: vegan_restaurant, ramen_restaurant, restaurant",
    )
]

_GROUNDED_TRAJECTORY = Trajectory(
    query="Find vegan ramen in Kyoto.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "Sora Vegan Ramen at 12 Kawaramachi is a fully vegan, inexpensive ramen "
        "restaurant rated 4.7/5 from 516 reviews."
    ),
)

_HALLUCINATED_TRAJECTORY = Trajectory(
    query="Find vegan ramen in Kyoto.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "Book Kyoto Imperial Noodles: a Michelin-starred steak restaurant with a "
        "4.9 rating and guaranteed gluten-free menu."
    ),
)


async def _demo() -> None:
    judge = build_judge()
    for label, trajectory in (
        ("GROUNDED restaurant answer", _GROUNDED_TRAJECTORY),
        ("HALLUCINATED restaurant answer", _HALLUCINATED_TRAJECTORY),
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
