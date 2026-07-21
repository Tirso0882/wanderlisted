"""Layer 2 pointwise judges for ActivitiesAgent answer quality."""

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

_SPEC = AGENT_SPECS["activities"]

_FAITH_EXAMPLES = """EXAMPLES (illustrative anchors - do NOT treat as evidence for the case you score):
  - RESULTS: "Lantern Gallery, 18 Flinders Lane, Melbourne; Rating 4.6/5
    (340 reviews); Price MODERATE; Summary: contemporary Australian art with a
    wheelchair-accessible entrance; Hours: Tuesday-Sunday: 10:00-18:00;
    Status: OPERATIONAL; Types: art_gallery, tourist_attraction". ANSWER:
    "Lantern Gallery at 18 Flinders Lane is a moderate-price art gallery rated
    4.6/5 from 340 reviews; its listing notes a wheelchair-accessible entrance."
    -> score 3 (every CORE activity fact is grounded).
  - Same RESULTS. ANSWER: "Lantern Gallery is a highly rated art gallery with a
    peaceful hidden courtyard." -> score 2 (the courtyard is one unsupported
    NON-CORE ambience extra).
  - Same RESULTS. ANSWER: "Lantern Gallery is free, open every day until 22:00,
    and fully accessible for every mobility need." -> score 1 (price, hours, and
    accessibility claims materially exceed the evidence)."""

_ACTIVITIES_EVIDENCE_RULES = """ACTIVITIES-SPECIFIC EVIDENCE RULES:
  - Accessibility proof: words in the REQUEST or search query such as
    "wheelchair accessible" describe search intent, not verified venue access.
    An accessibility claim is grounded only when the returned place name, types,
    or summary explicitly supports it. Otherwise the answer must mark access as
    unverified and advise direct confirmation.
  - Place identity: attach rating, review count, price, address, hours, status,
    type, capacity, and rental terms only to the exact venue whose result contains
    them. Moving a fact to a nearby or similarly named attraction is a CORE error.
  - Hours and status: a weekly hours listing does not prove the venue is open on
    the traveler's future date. A faithful paraphrase of listed hours is allowed;
    an unsupported "open on your date" guarantee is a CORE error.
  - Visit duration, "must-see" emphasis, historical colour, and best-time tips
    are non-core unless the result explicitly supplies them. Do not mistake a
    request for a tour, event, or venue rental as proof of availability, capacity,
    or price.
  - URL compaction: evidence URLs may be represented as <URL>. Do not score URL
    string equality; a Maps or Website field supports providing the corresponding
    link.
"""

FAITHFULNESS_RUBRIC = (
    faithfulness_rubric(_SPEC, examples=_FAITH_EXAMPLES)
    + "\n\n"
    + _ACTIVITIES_EVIDENCE_RULES
)

_ACTIVITIES_HELPFULNESS_RULES = """ACTIVITIES PRODUCT PRESENTATION:
  - Surface the activity or venue name, returned type, address, rating, and any
    returned price/hours that help the traveler choose. Do not fabricate visit
    duration, event availability, admission price, capacity, or rental terms.
  - When accessibility is requested, distinguish an evidence-backed accessibility
    detail from an honest "not verified - confirm with the venue" caveat.
  - For venue-rental requests, prioritize clearly comparable rental candidates;
    only state capacity, hourly/daily terms, and contact information when they
    appear in the returned evidence.
  - Maps/website links render compactly downstream. Ignore raw URL length, but
    penalize duplicated or irrelevant links that make choices hard to compare.
"""

HELPFULNESS_RUBRIC = helpfulness_rubric(_SPEC) + "\n\n" + _ACTIVITIES_HELPFULNESS_RULES

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
        "* Sakura Arts Museum\n"
        "  Address: 12 Higashiyama, Kyoto\n"
        "  Rating: 4.7/5 (516 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Modern Japanese art museum with a wheelchair-accessible entrance\n"
        "  Hours: Tuesday-Sunday: 10:00-18:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: art_museum, museum, tourist_attraction",
    )
]

_GROUNDED_TRAJECTORY = Trajectory(
    query="Find wheelchair-accessible art museums in Kyoto.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "Sakura Arts Museum at 12 Higashiyama is a moderate-price Kyoto art museum "
        "rated 4.7/5 from 516 reviews; its listing notes a wheelchair-accessible entrance."
    ),
)

_HALLUCINATED_TRAJECTORY = Trajectory(
    query="Find wheelchair-accessible art museums in Kyoto.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "Book Kyoto Imperial Palace Gallery: it is free, open daily until 22:00, "
        "and guarantees step-free access throughout."
    ),
)


async def _demo() -> None:
    judge = build_judge()
    for label, trajectory in (
        ("GROUNDED activities answer", _GROUNDED_TRAJECTORY),
        ("HALLUCINATED activities answer", _HALLUCINATED_TRAJECTORY),
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
