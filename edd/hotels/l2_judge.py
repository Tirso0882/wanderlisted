"""EDD Layer 2 — LLM-as-JUDGE for the HOTELS agent's SUMMARY.

Layer 1 scored the DECISION (city, dates, guests, star/board/budget filters) with
pure code. Layer 2 scores the PROSE the agent writes after the hotel tools return:
    faithfulness — is every CORE hotel claim (name, price, board, star, room,
                   cancellation, city) grounded in the tool RESULTS?
    helpfulness  — does the answer surface the right hotel(s) and honour any
                   stars/board/budget the request asked for?

SAME SCAFFOLD AS FLIGHTS (edd/rubrics.py) — only the spec + the in-context anchors
differ. This is the whole point of the scaffold: a second agent's judge is a
~20-line binding, not a re-written rubric. But the hotel CORE facts are genuinely
different from flights:
  • a wrong BOARD (says all-inclusive when it's room-only) or a wrong CANCELLATION
    (says free-cancel when it's non-refundable) is a real booking error → CORE.
  • a hotel-specific hazard: REVIEW/RATING facts (from `search_places_text`)
    matched to the WRONG hotel. The spec's `core_error` names this explicitly.

LEAKAGE GUARD — the anchors below use a DIFFERENT city/hotel (Lisbon) than
l2_judge_cases.py (Rome + Barcelona), so Layer-4 calibration stays an honest
held-out test rather than a memorization check.

Run the fixture demo (no agent run — a fixed trajectory in, the judge scores it):
    .venv/bin/python edd/hotels/l2_judge.py
"""

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

_SPEC = AGENT_SPECS["hotels"]

# In-context anchors (rubric-construction checklist item 7) — DISJOINT from
# l2_judge_cases.py (that set uses Rome + Barcelona; these use Lisbon). One anchor
# per boundary the judge must hold: a clean 3, a NON-CORE-slip 2, and a CORE-error 1.
_FAITH_EXAMPLES = """EXAMPLES (illustrative anchors — do NOT treat as evidence for the case you score):
  • RESULTS: "1. Hotel Lumen  Category: 4 stars  Location: Baixa, Lisbon
    Room: Deluxe Room  Price: 592.00 EUR (total stay)  Board: Bed and Breakfast
    Cancellation: Free cancellation until 2026-05-01".
    ANSWER: "Hotel Lumen is a 4-star in Baixa, Lisbon — a Deluxe Room with breakfast
    at EUR 592 total, free to cancel until 1 May." -> score 3 (every CORE fact grounded).
  • Same RESULTS. ANSWER: "Hotel Lumen, 4-star in Baixa, Deluxe Room with breakfast
    at EUR 592 total; it has a rooftop pool." -> score 2 (all CORE hotel data
    grounded; the rooftop-pool amenity is an unsupported NON-CORE extra — a minor slip).
  • Same RESULTS. ANSWER: "Hotel Lumen is all-inclusive and non-refundable at EUR 520
    total." -> score 1 (board, cancellation AND price all contradict RESULTS —
    materially misleading CORE errors)."""

# Built once, from the scaffold. `build_judge` is re-exported so the runner and
# l4_calibrate.py import it from here (identically to the flights layout).
_HOTEL_EVIDENCE_RULES = """HOTEL-SPECIFIC EVIDENCE RULES:
    • RECHECK precedence: an availability price marked RECHECK is PROVISIONAL. If
        `check_hotel_rate_hotelbeds` returns an updated price, board, room, or
        cancellation policy for that rate, the CheckRate result is the source of
        truth. Presenting the stale availability value as confirmed is a CORE error.
        Without a successful CheckRate result, a RECHECK price must be described as
        provisional/unverified, not confirmed.
    • Hotel identity: apply `search_places_text` ratings, address, photos, and
        location facts only to the exact hotel they describe. Never transfer Places
        facts between similarly named hotels or between different cities.
    • URL compaction: long evidence URLs may be represented as `<URL>`. If the
        corresponding Places result contains a Maps/Photo/Website field, do not
        penalize the answer merely because it prints the full URL; URL-string
        equality is outside this rubric's CORE hotel facts.
"""

FAITHFULNESS_RUBRIC = (
    faithfulness_rubric(_SPEC, examples=_FAITH_EXAMPLES)
    + "\n\n"
    + _HOTEL_EVIDENCE_RULES
)
_HOTEL_HELPFULNESS_RULES = """HOTEL PRODUCT PRESENTATION:
    • Maps/photo links are required structured data and render as compact links in
        the downstream UI. Do not penalize an answer solely for the raw character
        length of those URLs. Do penalize duplicated, disorganized, or irrelevant
        links when they genuinely make the options hard to compare.
"""

HELPFULNESS_RUBRIC = helpfulness_rubric(_SPEC) + "\n\n" + _HOTEL_HELPFULNESS_RULES

__all__ = [
    "FAITHFULNESS_RUBRIC",
    "HELPFULNESS_RUBRIC",
    "JUDGES",
    "build_judge",
    "judge_faithfulness",
    "judge_helpfulness",
]


# ── The two Hotels judges — thin bindings over the scaffold's scorers ───────
async def judge_faithfulness(judge, traj: Trajectory) -> dict:
    """Score whether the final answer is grounded in the hotel tool results."""
    return await score_faithfulness(judge, traj, rubric=FAITHFULNESS_RUBRIC)


async def judge_helpfulness(judge, traj: Trajectory) -> dict:
    """Score whether the final answer actually serves the traveler's request."""
    return await score_helpfulness(judge, traj, rubric=HELPFULNESS_RUBRIC)


JUDGES = [judge_faithfulness, judge_helpfulness]


# ── Fixture demo — teach the rubric WITHOUT running the agent ────────────────
# Two hand-written trajectories share the SAME evidence; only the ANSWER differs.
# The grounded one should score ~3; the hallucinated one invents a hotel, a price,
# and a board basis that aren't in the evidence.
_EVIDENCE = [
    (
        "search_hotels_hotelbeds",
        "Found 1 hotel in Tokyo (2026-09-01 to 2026-09-04, 2 adults):\n"
        "  1. Hotel Granbell Shibuya\n"
        "     Category: 4 stars\n"
        "     Location: Shibuya, Tokyo\n"
        "     Room: Superior Double\n"
        "       Price: 96000 JPY (total stay)\n"
        "       Board: Room Only\n"
        "       Rate type: BOOKABLE\n"
        "       Cancellation: Free cancellation until 2026-08-25\n",
    )
]

_GROUNDED_TRAJ = Trajectory(
    query="Find a hotel in Tokyo, 2026-09-01 to 2026-09-04, 2 adults.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "Hotel Granbell Shibuya is a 4-star in Shibuya, Tokyo. A Superior Double is "
        "JPY 96,000 for the stay, room-only, with free cancellation until 25 Aug."
    ),
)

_HALLUCINATED_TRAJ = Trajectory(
    query="Find a hotel in Tokyo, 2026-09-01 to 2026-09-04, 2 adults.",
    tool_outputs=_EVIDENCE,
    final_text=(
        "I'd book the Tokyo Hilton — a 5-star with all-inclusive dining for just "
        "JPY 60,000 total. Great deal, reserve it now."
    ),  # Hilton, 5-star, all-inclusive, JPY 60,000 — none of this is in the evidence.
)


async def _demo() -> None:
    judge = build_judge()
    for label, traj in (
        ("GROUNDED answer — faithful to the tool results", _GROUNDED_TRAJ),
        ("HALLUCINATED answer — invents a hotel, board & price", _HALLUCINATED_TRAJ),
    ):
        print(f"\n{label}")
        print("-" * 68)
        print(f"  answer: {traj.final_text}\n")
        for judge_fn in JUDGES:
            out = await judge_fn(judge, traj)
            score = "SKIP" if out["score"] is None else f"{out['score']}/3"
            print(f"  {out['key']:14s} {score:>4s}   {out['comment']}")
    print()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    import truststore  # trust the OS store; never disable verification

    truststore.inject_into_ssl()
    os.environ["LANGSMITH_TRACING"] = "false"  # fixture demo = hermetic
    os.environ["LANGCHAIN_TRACING_V2"] = "false"

    asyncio.run(_demo())
