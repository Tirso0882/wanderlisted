"""Human-labeled Activities trajectories for Layer 4 judge calibration.

The 24 cases are balanced across the 0-3 faithfulness scale and held out from
the Melbourne in-context anchors in ``l2_judge.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402

_KYOTO_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Sakura Arts Museum\n"
        "  Address: 12 Higashiyama, Kyoto\n"
        "  Rating: 4.7/5 (516 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Modern Japanese art museum with a wheelchair-accessible entrance\n"
        "  Hours: Tuesday-Sunday: 10:00-18:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: art_museum, museum, tourist_attraction\n\n"
        "* Gion Lantern Walk\n"
        "  Address: 8 Hanamikoji, Kyoto\n"
        "  Rating: 4.4/5 (830 reviews)\n"
        "  Price: INEXPENSIVE\n"
        "  Summary: Evening walking route through historic Gion streets\n"
        "  Hours: Open daily\n"
        "  Status: OPERATIONAL\n"
        "  Types: tourist_attraction, point_of_interest",
    )
]

_LONDON_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Thames Discovery Museum\n"
        "  Address: 41 South Bank, London\n"
        "  Rating: 4.6/5 (1200 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Interactive river-history museum; listing notes wheelchair access\n"
        "  Hours: Daily: 10:00-17:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: museum, tourist_attraction\n\n"
        "* Riverside Gallery\n"
        "  Address: 8 South Bank, London\n"
        "  Rating: 4.3/5 (560 reviews)\n"
        "  Price: EXPENSIVE\n"
        "  Summary: Contemporary art exhibitions\n"
        "  Status: CLOSED_TEMPORARILY\n"
        "  Types: art_gallery, tourist_attraction",
    )
]

_BARCELONA_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Raval Movement Studio\n"
        "  Address: Carrer de la Riera Alta 22, Barcelona\n"
        "  Rating: 4.8/5 (210 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Dance and rehearsal studio; hourly room rental details on website\n"
        "  Hours: Monday-Saturday: 09:00-22:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: dance_school, event_venue\n\n"
        "* Born Event Hall\n"
        "  Address: Passeig del Born 9, Barcelona\n"
        "  Rating: 4.5/5 (140 reviews)\n"
        "  Price: EXPENSIVE\n"
        "  Summary: Private event space with room-hire enquiries by phone\n"
        "  Status: OPERATIONAL\n"
        "  Types: event_venue, point_of_interest",
    )
]

_REYKJAVIK_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Aurora Harbor Tours\n"
        "  Address: Old Harbor, Reykjavik\n"
        "  Rating: 4.6/5 (2200 reviews)\n"
        "  Price: EXPENSIVE\n"
        "  Summary: Evening northern-lights sightseeing tours from the harbor\n"
        "  Hours: Daily: 18:00-23:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: tourist_attraction, travel_agency\n\n"
        "* Harpa Viewpoint\n"
        "  Address: Austurbakki 2, Reykjavik\n"
        "  Rating: 4.7/5 (3300 reviews)\n"
        "  Price: FREE\n"
        "  Summary: Waterfront public viewpoint near Harpa\n"
        "  Status: OPERATIONAL\n"
        "  Types: tourist_attraction, park",
    )
]

_SINGAPORE_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* FutureLab Science Centre\n"
        "  Address: 15 Science Centre Road, Singapore\n"
        "  Rating: 4.7/5 (4100 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Interactive science exhibits designed for children and families\n"
        "  Hours: Tuesday-Sunday: 10:00-17:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: science_museum, museum, tourist_attraction\n\n"
        "* Gardens Learning Walk\n"
        "  Address: Marina Gardens Drive, Singapore\n"
        "  Rating: 4.5/5 (980 reviews)\n"
        "  Price: FREE\n"
        "  Summary: Outdoor educational garden walk\n"
        "  Status: OPERATIONAL\n"
        "  Types: park, tourist_attraction",
    )
]

_ROME_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Forum Stories Museum\n"
        "  Address: Via dei Fori Imperiali 18, Rome\n"
        "  Rating: 4.5/5 (920 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Ancient Rome objects and archaeological displays\n"
        "  Hours: Monday-Saturday: 09:00-18:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: history_museum, museum, tourist_attraction\n\n"
        "* Capitoline Terrace\n"
        "  Address: Piazza del Campidoglio, Rome\n"
        "  Rating: 4.8/5 (690 reviews)\n"
        "  Price: FREE\n"
        "  Summary: Historic public terrace overlooking central Rome\n"
        "  Status: OPERATIONAL\n"
        "  Types: tourist_attraction, point_of_interest",
    )
]


def _case(
    name: str, expected: int, note: str, query: str, evidence, answer: str
) -> dict:
    return {
        "name": name,
        "expected": expected,
        "note": note,
        "trajectory": Trajectory(
            query=query,
            tool_outputs=evidence,
            final_text=answer,
        ),
    }


JUDGE_CASES: list[dict] = [
    # Score 3: every material activity claim is grounded or uncertainty is honest.
    _case(
        "clear-pass-kyoto",
        3,
        "name, type, address, rating, price, access, and hours match Sakura",
        "Wheelchair-accessible art museums in Kyoto.",
        _KYOTO_EVIDENCE,
        "Sakura Arts Museum at 12 Higashiyama is a moderate-price art museum rated 4.7/5 from 516 reviews; its listing notes a wheelchair-accessible entrance and Tuesday-Sunday hours of 10:00-18:00.",
    ),
    _case(
        "clear-pass-london-access",
        3,
        "the access claim is explicitly supported in the returned summary",
        "Wheelchair-accessible museums in London.",
        _LONDON_EVIDENCE,
        "Thames Discovery Museum at 41 South Bank is a moderate interactive river-history museum rated 4.6/5; the listing notes wheelchair access.",
    ),
    _case(
        "clear-pass-barcelona-rental",
        3,
        "rental category is grounded without inventing price or capacity",
        "Hourly dance studio rental in Barcelona.",
        _BARCELONA_EVIDENCE,
        "Raval Movement Studio at Carrer de la Riera Alta 22 is a moderate-price dance and rehearsal studio rated 4.8/5; its listing directs hourly room-rental details to the website.",
    ),
    _case(
        "clear-pass-reykjavik",
        3,
        "all Aurora Harbor Tours facts are grounded",
        "Northern-lights tours in Reykjavik.",
        _REYKJAVIK_EVIDENCE,
        "Aurora Harbor Tours leaves from Old Harbor, is listed operational, and offers evening northern-lights sightseeing tours from 18:00 to 23:00; it is rated 4.6/5 from 2,200 reviews.",
    ),
    _case(
        "clear-pass-singapore-family",
        3,
        "family fit is explicit in the returned summary",
        "Interactive science activities for children in Singapore.",
        _SINGAPORE_EVIDENCE,
        "FutureLab Science Centre at 15 Science Centre Road is a moderate interactive science museum designed for children and families, rated 4.7/5 from 4,100 reviews.",
    ),
    _case(
        "honest-rome-accessibility-uncertainty",
        3,
        "does not turn the accessibility request into unsupported proof",
        "Accessible ancient-history activities in Rome.",
        _ROME_EVIDENCE,
        "Forum Stories Museum is a moderate ancient-Rome museum on Via dei Fori Imperiali, but its Places listing does not verify accessibility; confirm directly before visiting.",
    ),
    # Score 2: one minor, non-decision-changing unsupported or rounded detail.
    _case(
        "minor-rounded-rating-kyoto",
        2,
        "rounds the 4.7 rating while preserving the venue choice",
        "Art museums in Kyoto.",
        _KYOTO_EVIDENCE,
        "Sakura Arts Museum is a moderate Kyoto art museum at 12 Higashiyama, rated about 4.5/5.",
    ),
    _case(
        "minor-duration-kyoto",
        2,
        "visit duration is unsupported but non-core",
        "Art museums in Kyoto.",
        _KYOTO_EVIDENCE,
        "Sakura Arts Museum is a moderate art museum rated 4.7/5; plan exactly ninety minutes for the visit.",
    ),
    _case(
        "minor-ambience-london",
        2,
        "quiet ambience is one unsupported non-core detail",
        "Museums in London.",
        _LONDON_EVIDENCE,
        "Thames Discovery Museum is a moderate, wheelchair-accessible museum rated 4.6/5 with a calm waterside atmosphere.",
    ),
    _case(
        "minor-best-time-reykjavik",
        2,
        "the best-time tip is unsupported but venue facts are right",
        "Northern-lights tours in Reykjavik.",
        _REYKJAVIK_EVIDENCE,
        "Aurora Harbor Tours is an expensive northern-lights tour from Old Harbor rated 4.6/5; the ideal viewing time is exactly 21:15.",
    ),
    _case(
        "minor-architectural-detail-rome",
        2,
        "specific architectural colour is unsupported but non-core",
        "Ancient-history activities in Rome.",
        _ROME_EVIDENCE,
        "Forum Stories Museum is a moderate ancient-Rome museum at Via dei Fori Imperiali 18, rated 4.5/5, with a spectacular marble atrium.",
    ),
    _case(
        "minor-view-singapore",
        2,
        "view description is unsupported but all core activity facts are right",
        "Family activities in Singapore.",
        _SINGAPORE_EVIDENCE,
        "FutureLab Science Centre is a moderate interactive science museum for children and families rated 4.7/5, with a beautiful skyline view.",
    ),
    # Score 1: one materially misleading CORE error.
    _case(
        "wrong-price-kyoto",
        1,
        "calls a moderate museum free",
        "Art museums in Kyoto.",
        _KYOTO_EVIDENCE,
        "Sakura Arts Museum is a free art museum at 12 Higashiyama, rated 4.7/5.",
    ),
    _case(
        "wrong-hours-london",
        1,
        "daily hours contradict the returned listing",
        "Museums in London.",
        _LONDON_EVIDENCE,
        "Thames Discovery Museum is open daily until 22:00 and is rated 4.6/5.",
    ),
    _case(
        "unsupported-accessibility-rome",
        1,
        "guarantees accessibility absent from evidence",
        "Accessible ancient-history activities in Rome.",
        _ROME_EVIDENCE,
        "Forum Stories Museum guarantees step-free access throughout its ancient-Rome exhibits.",
    ),
    _case(
        "wrong-address-barcelona",
        1,
        "assigns Born Event Hall's address to Raval Movement Studio",
        "Hourly dance studio rental in Barcelona.",
        _BARCELONA_EVIDENCE,
        "Raval Movement Studio is a moderate dance studio at Passeig del Born 9, rated 4.8/5.",
    ),
    _case(
        "wrong-status-london",
        1,
        "temporarily closed gallery is presented as operating",
        "Art galleries in London.",
        _LONDON_EVIDENCE,
        "Riverside Gallery is an operational expensive art gallery at 8 South Bank, rated 4.3/5.",
    ),
    _case(
        "wrong-family-fit-singapore",
        1,
        "states an incompatible adult-only policy absent from and contrary to summary",
        "Family science activities in Singapore.",
        _SINGAPORE_EVIDENCE,
        "FutureLab Science Centre is a moderate science museum rated 4.7/5, but it is strictly adults-only.",
    ),
    # Score 0: fabricated or several independent core contradictions.
    _case(
        "fabricated-kyoto-venue",
        0,
        "identity, price, rating, address, and access facts are invented",
        "Accessible art museums in Kyoto.",
        _KYOTO_EVIDENCE,
        "Kyoto Imperial Gallery at Palace Road 99 is a free 5.0-rated museum with guaranteed elevator access.",
    ),
    _case(
        "cross-venue-london",
        0,
        "uses the gallery identity with the museum's access, price, and rating",
        "Accessible art galleries in London.",
        _LONDON_EVIDENCE,
        "Riverside Gallery is a moderate wheelchair-accessible museum at 41 South Bank, rated 4.6/5.",
    ),
    _case(
        "fabricated-rental-barcelona",
        0,
        "invented venue and rental terms are absent from the evidence",
        "Dance studio rental in Barcelona.",
        _BARCELONA_EVIDENCE,
        "Barcelona Dance Palace rents a 100-person mirrored studio for EUR 20 per hour at Gran Via 99 and is rated 5.0/5.",
    ),
    _case(
        "several-reykjavik-contradictions",
        0,
        "tour name, price, time, and rating all contradict results",
        "Northern-lights tours in Reykjavik.",
        _REYKJAVIK_EVIDENCE,
        "Aurora Harbor Tours is a free morning tour from the airport, rated 5.0/5 and open only until noon.",
    ),
    _case(
        "cross-venue-singapore",
        0,
        "moves FutureLab's category, price, and rating to Gardens Learning Walk",
        "Family activities in Singapore.",
        _SINGAPORE_EVIDENCE,
        "Gardens Learning Walk is a moderate interactive science museum for children at 15 Science Centre Road, rated 4.7/5.",
    ),
    _case(
        "several-rome-contradictions",
        0,
        "identity, address, price, and category facts are fabricated",
        "Ancient-history activities in Rome.",
        _ROME_EVIDENCE,
        "Roman Empire Experience at Via Veneto 77 is a free virtual-reality museum rated 5.0/5 and open 24 hours.",
    ),
]
