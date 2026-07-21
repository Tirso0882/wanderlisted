"""EDD — the HOTELS judge's OWN dataset: labeled trajectories at graded difficulty.

The hotel analog of edd/flights/l2_judge_cases.py. To test the JUDGE you need
(trajectory -> expected SCORE) cases, not (query -> expected DECISION) cases —
and a BORDERLINE hotel answer won't fall out of a live run, so you hand-craft the
trajectory AND hand-label the right faithfulness grade. That labeled set is the
seed of Layer 4 (judge calibration).

Each case is a FAITHFULNESS probe:
    trajectory : query + tool_outputs (the evidence) + final_text (the answer)
    expected   : the CORRECT faithfulness score 0-3 — a human label
    note       : why it sits where it does

Hotel-specific hard cases include:
  • wrong-cancellation / wrong-board — CORE booking facts unique to hotels.
  • wrong-hotel-mixup — attributes one hotel's stars/room to another hotel's
    price (the `search_places_text` cross-match hazard the rubric warns about).
    • stale RECHECK price — ignores the authoritative CheckRate result.
    • Places identity — moves a rating/address from one hotel to another.

These use Rome, Barcelona, Kyoto, and Cancun; the rubric's in-context anchors use
Lisbon — disjoint BY DESIGN so Layer 4 is an honest held-out test, not a
memorization check.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402

_ROME_EVIDENCE = [
    (
        "search_hotels_hotelbeds",
        "Found 1 hotel in Rome (2026-06-20 to 2026-06-24, 2 adults):\n"
        "  1. Hotel Artemide\n"
        "     Category: 4 stars\n"
        "     Location: Via Nazionale, Rome\n"
        "     Room: Classic Double\n"
        "       Price: 840.00 EUR (total stay)\n"
        "       Board: Bed and Breakfast\n"
        "       Rate type: BOOKABLE\n"
        "       Cancellation: Free cancellation until 2026-06-10\n",
    )
]

_BCN_EVIDENCE = [
    (
        "search_hotels_hotelbeds",
        "Found 2 hotels in Barcelona (2026-07-05 to 2026-07-08, 2 adults):\n"
        "  1. Hotel Marina Blau\n"
        "     Category: 4 stars\n"
        "     Location: Barceloneta, Barcelona\n"
        "     Room: Sea View Double\n"
        "       Price: 720.00 EUR (total stay)\n"
        "       Board: Half Board\n"
        "       Rate type: BOOKABLE\n"
        "       Cancellation: Free cancellation until 2026-06-25\n"
        "  2. Hotel Sol Central\n"
        "     Category: 3 stars\n"
        "     Location: Eixample, Barcelona\n"
        "     Room: Standard Twin\n"
        "       Price: 480.00 EUR (total stay)\n"
        "       Board: Room Only\n"
        "       Rate type: BOOKABLE\n"
        "       Cancellation: Non-refundable\n",
    )
]

_KYOTO_EVIDENCE = [
    (
        "search_hotels_hotelbeds",
        "Hotels from Hotelbeds in KYO (2026-10-12 to 2026-10-15, 2 adults):\n"
        "  1. Hotel Sakura Gion\n"
        "     Category: 4 stars\n"
        "     Location: Gion, Kyoto\n"
        "     Room: Superior Twin\n"
        "       Price: 66000 JPY (total stay)\n"
        "       Board: Bed and Breakfast\n"
        "       Rate type: BOOKABLE\n"
        "       Cancellation: Free cancellation until 2026-10-01\n"
        "  2. Kamo Stay\n"
        "     Category: 3 stars\n"
        "     Location: Kawaramachi, Kyoto\n"
        "     Room: Standard Double\n"
        "       Price: 48000 JPY (total stay)\n"
        "       Board: Room Only\n"
        "       Rate type: BOOKABLE\n"
        "       Cancellation: Non-refundable\n",
    ),
    (
        "search_places_text",
        "Found 1 result(s):\n\n"
        "• Hotel Sakura Gion\n"
        "  Address: 12 Gionmachi, Higashiyama, Kyoto\n"
        "  Rating: 4.6/5 (328 reviews)\n"
        "  Google Maps: https://maps.example/sakura-gion",
    ),
    (
        "search_places_text",
        "Found 1 result(s):\n\n"
        "• Kamo Stay\n"
        "  Address: 8 Kawaramachi, Nakagyo, Kyoto\n"
        "  Rating: 4.2/5 (91 reviews)\n"
        "  Google Maps: https://maps.example/kamo-stay",
    ),
]

_CANCUN_RECHECK_EVIDENCE = [
    (
        "search_hotels_hotelbeds",
        "Hotels from Hotelbeds in CUN (2026-10-10 to 2026-10-17, 2 adults):\n"
        "  1. Hotel Coral Bay\n"
        "     Category: 5 stars\n"
        "     Location: Hotel Zone, Cancun\n"
        "     Room: Ocean King\n"
        "       Price: 900.00 USD (total stay)\n"
        "       Board: All Inclusive\n"
        "       Rate type: RECHECK\n"
        "       Cancellation: Free cancellation until 2026-09-20\n"
        "       Rate key: RK-CORAL-1\n"
        "       Rate requires CheckRate verification before booking",
    ),
    (
        "check_hotel_rate_hotelbeds",
        "Hotelbeds CheckRate results:\n"
        "Hotel: Hotel Coral Bay\n"
        "Check-in: 2026-10-10 -> Check-out: 2026-10-17\n"
        "Total: 960.00 USD\n"
        "  Room: Ocean King\n"
        "    Net: 960.00 | Board: All Inclusive\n"
        "    Rate key: RK-CORAL-1\n"
        "    Cancellation: 960.00 USD from 2026-09-20",
    ),
]

JUDGE_CASES: list[dict] = [
    {
        "name": "clear-pass",
        "expected": 3,
        "note": "every CORE hotel fact grounded; nothing invented",
        "trajectory": Trajectory(
            query="Hotel in Rome, 2026-06-20 to 2026-06-24, 2 adults.",
            tool_outputs=_ROME_EVIDENCE,
            final_text=(
                "Hotel Artemide is a 4-star on Via Nazionale, Rome: a Classic Double "
                "with breakfast at EUR 840 total, free to cancel until 10 June."
            ),
        ),
    },
    {
        "name": "clear-fail",
        "expected": 0,
        "note": "invents hotel, star rating AND price; nothing grounded",
        "trajectory": Trajectory(
            query="Hotel in Rome, 2026-06-20 to 2026-06-24, 2 adults.",
            tool_outputs=_ROME_EVIDENCE,
            final_text=(
                "The best value is Hotel Roma Palace, a 5-star with free breakfast "
                "at EUR 520 total. Book it right away."
            ),
        ),
    },
    {
        "name": "grounded-restated-params",
        "expected": 3,
        "note": (
            "every hotel fact grounded AND restates REQUEST params (2 adults, the "
            "dates) — restating the request is context, not fabrication -> 3"
        ),
        "trajectory": Trajectory(
            query="Hotel in Rome, 2026-06-20 to 2026-06-24, 2 adults.",
            tool_outputs=_ROME_EVIDENCE,
            final_text=(
                "For 2 adults, 20-24 June: Hotel Artemide, 4-star on Via Nazionale, "
                "Classic Double, breakfast included, EUR 840 total, free cancellation "
                "until 10 June."
            ),
        ),
    },
    {
        "name": "borderline-invented-amenity",
        "expected": 2,
        "note": (
            "all CORE hotel data grounded; adds 'rooftop bar' — an unsupported "
            "NON-CORE amenity; a minor slip (2)"
        ),
        "trajectory": Trajectory(
            query="Hotel in Rome, 2026-06-20 to 2026-06-24, 2 adults.",
            tool_outputs=_ROME_EVIDENCE,
            final_text=(
                "Hotel Artemide, 4-star, Classic Double with breakfast at EUR 840 "
                "total (free cancel to 10 June), and it has a rooftop bar."
            ),
        ),
    },
    {
        "name": "minor-rounding",
        "expected": 2,
        "note": "hotel/board/stars correct; rounds EUR 840 to 'about EUR 850' — one minor imprecise number",
        "trajectory": Trajectory(
            query="Hotel in Rome, 2026-06-20 to 2026-06-24, 2 adults.",
            tool_outputs=_ROME_EVIDENCE,
            final_text=(
                "Hotel Artemide (4-star, Via Nazionale) — Classic Double with "
                "breakfast, about EUR 850 total, free cancellation until 10 June."
            ),
        ),
    },
    {
        "name": "wrong-board-contradiction",
        "expected": 1,
        "note": (
            "name/stars/price correct, but states all-inclusive — the board is Bed "
            "and Breakfast in RESULTS (materially misleading CORE fact)"
        ),
        "trajectory": Trajectory(
            query="Hotel in Rome, 2026-06-20 to 2026-06-24, 2 adults.",
            tool_outputs=_ROME_EVIDENCE,
            final_text=(
                "Hotel Artemide is a 4-star with all-inclusive dining at EUR 840 "
                "total — great value for Rome."
            ),
        ),
    },
    {
        "name": "wrong-cancellation-contradiction",
        "expected": 1,
        "note": (
            "Sol Central is Non-refundable in RESULTS, but the answer calls it "
            "free-cancel — a CORE cancellation error a traveler WOULD book wrong over"
        ),
        "trajectory": Trajectory(
            query="Cheapest hotel in Barcelona, 2026-07-05 to 2026-07-08, 2 adults.",
            tool_outputs=_BCN_EVIDENCE,
            final_text=(
                "Hotel Sol Central, 3-star in Eixample, Standard Twin, room-only at "
                "EUR 480 total, with free cancellation if your plans change."
            ),
        ),
    },
    {
        "name": "hard-wrong-hotel-mixup",
        "expected": 1,
        "note": (
            "attributes Marina Blau's EUR 720 price to Sol Central while keeping "
            "Sol's other facts correct — one WRONG-HOTEL CORE error"
        ),
        "trajectory": Trajectory(
            query="Hotel in Barcelona, 2026-07-05 to 2026-07-08, 2 adults.",
            tool_outputs=_BCN_EVIDENCE,
            final_text=(
                "Hotel Sol Central is a 3-star in Eixample with a Standard Twin, "
                "room-only and non-refundable, at EUR 720 total."
            ),
        ),
    },
    {
        "name": "hard-invented-discount",
        "expected": 1,
        "note": (
            "hotel facts grounded, but invents a '20% loyalty discount' and a "
            "derived EUR 672 total the tool never returned (fabricated math)"
        ),
        "trajectory": Trajectory(
            query="Hotel in Rome, 2026-06-20 to 2026-06-24, 2 adults.",
            tool_outputs=_ROME_EVIDENCE,
            final_text=(
                "Hotel Artemide is EUR 840 total, but with the 20% loyalty discount "
                "it's just EUR 672 for the stay."
            ),
        ),
    },
    {
        "name": "hard-faithful-but-vague",
        "expected": 3,
        "note": (
            "invents NOTHING — states only grounded facts (Marina Blau, 4-star, "
            "Barceloneta, half board) and omits price/cancellation. Faithfulness "
            "grades grounding, not completeness -> 3"
        ),
        "trajectory": Trajectory(
            query="Hotel in Barcelona, 2026-07-05 to 2026-07-08, 2 adults.",
            tool_outputs=_BCN_EVIDENCE,
            final_text="Hotel Marina Blau in Barceloneta is a 4-star with half board.",
        ),
    },
    {
        "name": "hard-both-hotels-grounded",
        "expected": 3,
        "note": (
            "presents BOTH hotels with each one's own correct stars/board/price/"
            "cancellation — no cross-match, nothing invented -> 3"
        ),
        "trajectory": Trajectory(
            query="Hotel options in Barcelona, 2026-07-05 to 2026-07-08, 2 adults.",
            tool_outputs=_BCN_EVIDENCE,
            final_text=(
                "Two options: Hotel Marina Blau (4-star, Barceloneta) — Sea View "
                "Double, half board, EUR 720 total, free cancel to 25 June; or the "
                "cheaper Hotel Sol Central (3-star, Eixample) — Standard Twin, "
                "room-only, EUR 480 total, non-refundable."
            ),
        ),
    },
    # ── Added coverage (11 -> 25): Places identity, RECHECK precedence, and a
    #    balanced spread across 0/1/2/3. These are still one person's labels;
    #    independent human review remains the next trust upgrade. ──
    {
        "name": "clear-pass-enriched",
        "expected": 3,
        "note": "Hotelbeds and exact-hotel Places facts are all attached correctly",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Hotel Sakura Gion is a 4-star in Gion: Superior Twin with "
                "breakfast for JPY 66,000 total, free cancellation until 1 October. "
                "Google Places rates it 4.6/5 from 328 reviews."
            ),
        ),
    },
    {
        "name": "clear-pass-recheck",
        "expected": 3,
        "note": "uses the authoritative CheckRate total instead of the provisional availability price",
        "trajectory": Trajectory(
            query="All-inclusive Cancun hotel, 2026-10-10 to 2026-10-17, 2 adults.",
            tool_outputs=_CANCUN_RECHECK_EVIDENCE,
            final_text=(
                "Hotel Coral Bay is a confirmed 5-star all-inclusive in Cancun's "
                "Hotel Zone: Ocean King room, USD 960 total after CheckRate. A "
                "USD 960 cancellation penalty applies from 20 September."
            ),
        ),
    },
    {
        "name": "minor-invented-pool",
        "expected": 2,
        "note": "all CORE facts grounded; adds one unsupported NON-CORE pool amenity",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Hotel Sakura Gion is a 4-star in Gion, Superior Twin with breakfast "
                "for JPY 66,000 total, and it has a rooftop pool."
            ),
        ),
    },
    {
        "name": "minor-rounded-total",
        "expected": 2,
        "note": "rounds JPY 66,000 to about JPY 65,000; all other CORE facts match",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Hotel Sakura Gion is a 4-star in Gion with breakfast for about "
                "JPY 65,000 total."
            ),
        ),
    },
    {
        "name": "minor-walkability-claim",
        "expected": 2,
        "note": "all CORE facts grounded; adds one unsupported five-minute-walk claim",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Kamo Stay is a 3-star in Kawaramachi: Standard Double, room-only, "
                "JPY 48,000 total, non-refundable, and five minutes from the station."
            ),
        ),
    },
    {
        "name": "minor-invented-wifi",
        "expected": 2,
        "note": "all CORE facts grounded; free Wi-Fi is an unsupported NON-CORE amenity",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Kamo Stay is a 3-star in Kawaramachi, Standard Double, room-only, "
                "JPY 48,000 total and non-refundable, with free Wi-Fi."
            ),
        ),
    },
    {
        "name": "minor-rounded-rating",
        "expected": 2,
        "note": "rounds the supported 4.6 Places rating down to about 4.5; hotel identity remains correct",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Hotel Sakura Gion is a 4-star in Gion at JPY 66,000 total with "
                "breakfast; its Google rating is about 4.5/5."
            ),
        ),
    },
    {
        "name": "stale-recheck-price",
        "expected": 1,
        "note": "calls the provisional USD 900 availability price confirmed after CheckRate updated it to USD 960",
        "trajectory": Trajectory(
            query="All-inclusive Cancun hotel, 2026-10-10 to 2026-10-17, 2 adults.",
            tool_outputs=_CANCUN_RECHECK_EVIDENCE,
            final_text=(
                "Hotel Coral Bay is confirmed at USD 900 total for an Ocean King "
                "with all-inclusive board."
            ),
        ),
    },
    {
        "name": "wrong-places-hotel-rating",
        "expected": 1,
        "note": "transfers Sakura Gion's 4.6/328 Places rating to Kamo Stay",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Kamo Stay is a 3-star in Kawaramachi at JPY 48,000 total, room-only "
                "and non-refundable; Google rates it 4.6/5 from 328 reviews."
            ),
        ),
    },
    {
        "name": "wrong-board-one-core-error",
        "expected": 1,
        "note": "Kamo Stay is Room Only, but the answer claims breakfast included",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Kamo Stay is a 3-star in Kawaramachi: Standard Double with "
                "breakfast, JPY 48,000 total and non-refundable."
            ),
        ),
    },
    {
        "name": "fabricated-kyoto-hotel",
        "expected": 0,
        "note": "hotel name, stars, room, board, and price are all invented",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Kyoto Imperial Palace Hotel is a 5-star with an Imperial Suite, "
                "all-inclusive dining and a JPY 30,000 total."
            ),
        ),
    },
    {
        "name": "recheck-several-contradictions",
        "expected": 0,
        "note": "contradicts CheckRate on price, board, room, and cancellation",
        "trajectory": Trajectory(
            query="All-inclusive Cancun hotel, 2026-10-10 to 2026-10-17, 2 adults.",
            tool_outputs=_CANCUN_RECHECK_EVIDENCE,
            final_text=(
                "Hotel Coral Bay is confirmed at USD 800 total for a Standard Twin, "
                "room-only and freely cancellable through arrival."
            ),
        ),
    },
    {
        "name": "cross-hotel-composite",
        "expected": 0,
        "note": "uses Kamo Stay's name with Sakura's stars, area, room, board, price, and rating",
        "trajectory": Trajectory(
            query="Hotels in Kyoto, 2026-10-12 to 2026-10-15, 2 adults.",
            tool_outputs=_KYOTO_EVIDENCE,
            final_text=(
                "Kamo Stay is a 4-star in Gion: Superior Twin with breakfast for "
                "JPY 66,000 total, rated 4.6/5 from 328 reviews."
            ),
        ),
    },
    {
        "name": "fabricated-barcelona-option",
        "expected": 0,
        "note": "hotel, price, stars, room, and cancellation are absent from RESULTS",
        "trajectory": Trajectory(
            query="Hotel in Barcelona, 2026-07-05 to 2026-07-08, 2 adults.",
            tool_outputs=_BCN_EVIDENCE,
            final_text=(
                "Barcelona Grand Palace is a refundable 5-star suite with all meals "
                "for EUR 300 total."
            ),
        ),
    },
]
