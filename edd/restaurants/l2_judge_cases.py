"""Human-labeled Restaurant trajectories for Layer 4 judge calibration.

The 50 cases are balanced across the 0-3 faithfulness scale and are disjoint
from the Melbourne in-context anchors in l2_judge.py.
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
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Osteria Campo\n"
        "  Address: Piazza Campo de' Fiori 7, Rome\n"
        "  Rating: 4.7/5 (920 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Traditional Roman trattoria with handmade pasta\n"
        "  Hours: Monday-Sunday: 12:00-23:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: italian_restaurant, restaurant\n\n"
        "* Verde Roma\n"
        "  Address: Via Urbana 18, Rome\n"
        "  Rating: 4.5/5 (410 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Fully vegan Roman and Mediterranean cooking\n"
        "  Hours: Tuesday-Sunday: 11:30-22:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: vegan_restaurant, mediterranean_restaurant, restaurant",
    )
]

_KYOTO_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Ramen Kaze\n"
        "  Address: 22 Nishikikoji, Kyoto\n"
        "  Rating: 4.6/5 (650 reviews)\n"
        "  Price: INEXPENSIVE\n"
        "  Summary: Vegan ramen, gyoza, and Japanese small plates\n"
        "  Hours: Daily: 11:00-21:30\n"
        "  Status: OPERATIONAL\n"
        "  Types: vegan_restaurant, ramen_restaurant, restaurant\n\n"
        "* Gion Yakitori\n"
        "  Address: 9 Hanamikoji, Kyoto\n"
        "  Rating: 4.4/5 (830 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Charcoal-grilled chicken skewers and sake\n"
        "  Hours: Tuesday-Sunday: 17:00-23:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: yakitori_restaurant, japanese_restaurant, restaurant",
    )
]

_MEXICO_EVIDENCE = [
    (
        "search_places_nearby",
        "Found 2 restaurant(s):\n\n"
        "* Mercado Roma\n"
        "  Address: Queretaro 225, Roma Norte, Mexico City\n"
        "  Rating: 4.4/5 (12400 reviews)\n"
        "  Price: INEXPENSIVE\n"
        "  Summary: Food hall with independent Mexican and international vendors\n"
        "  Status: OPERATIONAL\n"
        "  Types: food_court, market, restaurant\n\n"
        "* Tacos del Sur\n"
        "  Address: Medellin 44, Roma Norte, Mexico City\n"
        "  Rating: 4.8/5 (780 reviews)\n"
        "  Price: INEXPENSIVE\n"
        "  Summary: Counter-service tacos and regional salsas\n"
        "  Status: OPERATIONAL\n"
        "  Types: taco_restaurant, mexican_restaurant, restaurant",
    )
]

_LONDON_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Cedar Grill\n"
        "  Address: 41 Edgware Road, London\n"
        "  Rating: 4.5/5 (1200 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Lebanese grill serving a certified halal menu\n"
        "  Hours: Daily: 12:00-00:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: lebanese_restaurant, halal_restaurant, restaurant\n\n"
        "* River Bistro\n"
        "  Address: 8 South Bank, London\n"
        "  Rating: 4.3/5 (560 reviews)\n"
        "  Price: EXPENSIVE\n"
        "  Summary: Modern European tasting menus\n"
        "  Status: CLOSED_TEMPORARILY\n"
        "  Types: european_restaurant, fine_dining_restaurant, restaurant",
    )
]

_SEOUL_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Han River Table\n"
        "  Address: 10 Insadong-gil, Jongno, Seoul\n"
        "  Rating: 4.7/5 (1250 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Traditional Korean dishes including bibimbap and grilled beef\n"
        "  Hours: Daily: 11:00-22:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: korean_restaurant, restaurant\n\n"
        "* Green Temple Seoul\n"
        "  Address: 22 Itaewon-ro, Yongsan, Seoul\n"
        "  Rating: 4.6/5 (420 reviews)\n"
        "  Price: INEXPENSIVE\n"
        "  Summary: Fully vegan Korean bowls and handmade dumplings\n"
        "  Hours: Tuesday-Sunday: 11:30-21:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: vegan_restaurant, korean_restaurant, restaurant",
    )
]

_PARIS_EVIDENCE = [
    (
        "search_places_text",
        "Found 2 result(s):\n\n"
        "* Maison Sans Ble\n"
        "  Address: 15 Rue Oberkampf, Paris\n"
        "  Rating: 4.8/5 (690 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Dedicated gluten-free bakery and cafe serving pastries\n"
        "  Hours: Tuesday-Sunday: 08:00-19:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: bakery, cafe, food_store\n\n"
        "* Cafe Lumiere\n"
        "  Address: 7 Rue Cler, Paris\n"
        "  Rating: 4.5/5 (980 reviews)\n"
        "  Price: EXPENSIVE\n"
        "  Summary: French brunch plates and specialty coffee\n"
        "  Hours: Daily: 08:00-17:00\n"
        "  Status: CLOSED_TEMPORARILY\n"
        "  Types: brunch_restaurant, cafe, coffee_shop",
    )
]

_CAPE_TOWN_EVIDENCE = [
    (
        "search_places_nearby",
        "Found 2 restaurant(s):\n\n"
        "* Harbour Catch\n"
        "  Address: Pierhead, V&A Waterfront, Cape Town\n"
        "  Rating: 4.6/5 (2200 reviews)\n"
        "  Price: EXPENSIVE\n"
        "  Summary: South African seafood and grilled line fish\n"
        "  Hours: Daily: 12:00-23:00\n"
        "  Status: OPERATIONAL\n"
        "  Types: seafood_restaurant, south_african_restaurant, restaurant\n\n"
        "* Table Mountain Kitchen\n"
        "  Address: 40 Long Street, Cape Town\n"
        "  Rating: 4.4/5 (760 reviews)\n"
        "  Price: MODERATE\n"
        "  Summary: Contemporary South African tasting plates\n"
        "  Hours: Wednesday-Sunday: 17:00-22:00\n"
        "  Status: CLOSED_TEMPORARILY\n"
        "  Types: south_african_restaurant, fine_dining_restaurant, restaurant",
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
    # Score 3: fully grounded, including honest uncertainty and selective answers.
    _case(
        "clear-pass-rome",
        3,
        "all stated venue facts match Osteria Campo",
        "Traditional restaurants in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is a moderate-price Roman trattoria at Piazza Campo de' Fiori 7, rated 4.7/5 from 920 reviews.",
    ),
    _case(
        "clear-pass-vegan",
        3,
        "dietary claim is explicit in the returned summary and type",
        "Vegan restaurants in Rome.",
        _ROME_EVIDENCE,
        "Verde Roma at Via Urbana 18 is fully vegan, moderately priced, and rated 4.5/5 from 410 reviews.",
    ),
    _case(
        "clear-pass-kyoto",
        3,
        "name, diet, cuisine, price, address, and rating are grounded",
        "Vegan ramen in Kyoto.",
        _KYOTO_EVIDENCE,
        "Ramen Kaze, 22 Nishikikoji, serves vegan ramen and is inexpensive, with a 4.6/5 rating from 650 reviews.",
    ),
    _case(
        "both-kyoto-venues",
        3,
        "keeps facts correctly attached to both restaurants",
        "Restaurant options in Kyoto.",
        _KYOTO_EVIDENCE,
        "Ramen Kaze is inexpensive vegan ramen rated 4.6; Gion Yakitori is a moderate-price yakitori restaurant rated 4.4.",
    ),
    _case(
        "clear-pass-halal",
        3,
        "halal suitability is explicitly supported",
        "Halal restaurants in London.",
        _LONDON_EVIDENCE,
        "Cedar Grill at 41 Edgware Road serves a certified halal Lebanese menu; it is moderately priced and rated 4.5/5.",
    ),
    _case(
        "faithful-but-vague",
        3,
        "faithfulness grades grounding, not completeness",
        "Cheap eats in Roma Norte.",
        _MEXICO_EVIDENCE,
        "Tacos del Sur is an inexpensive taco restaurant in Roma Norte.",
    ),
    _case(
        "honest-dietary-uncertainty",
        3,
        "does not turn a dietary search request into unsupported proof",
        "Gluten-free traditional food in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is a traditional Roman option, but the Places result does not verify gluten-free handling; confirm directly before visiting.",
    ),
    # Score 2: one minor, non-decision-changing unsupported or rounded detail.
    _case(
        "minor-rounded-rating",
        2,
        "rounds 4.7 to about 4.5 while other facts remain correct",
        "Traditional restaurants in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is a moderate Roman trattoria at Campo de' Fiori, rated about 4.5/5.",
    ),
    _case(
        "minor-invented-dish",
        2,
        "unsupported signature dish is non-core",
        "Traditional restaurants in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is a moderate Roman trattoria rated 4.7/5, famous for its signature artichoke ravioli.",
    ),
    _case(
        "minor-ambience",
        2,
        "unsupported ambience is non-core",
        "Vegan restaurants in Rome.",
        _ROME_EVIDENCE,
        "Verde Roma is a fully vegan, moderate-price restaurant rated 4.5/5 with a romantic candlelit room.",
    ),
    _case(
        "minor-wait-time",
        2,
        "estimated wait is unsupported but non-core",
        "Vegan ramen in Kyoto.",
        _KYOTO_EVIDENCE,
        "Ramen Kaze is inexpensive vegan ramen rated 4.6/5; expect about a ten-minute wait.",
    ),
    _case(
        "minor-invented-ambience-mexico",
        2,
        "all core facts are grounded; lively ambience is one unsupported non-core extra",
        "Cheap eats in Roma Norte.",
        _MEXICO_EVIDENCE,
        "Mercado Roma is an inexpensive food hall in Roma Norte, rated 4.4/5, with a lively communal atmosphere.",
    ),
    _case(
        "minor-reservation-tip",
        2,
        "unsupported reservation timing is a non-core tip",
        "Halal restaurants in London.",
        _LONDON_EVIDENCE,
        "Cedar Grill is a moderate halal Lebanese restaurant rated 4.5/5; reserve exactly three weeks ahead for a window table.",
    ),
    # Score 1: one materially misleading core error.
    _case(
        "wrong-price-level",
        1,
        "calls a moderate venue inexpensive",
        "Traditional restaurants in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is an inexpensive Roman trattoria rated 4.7/5 at Piazza Campo de' Fiori 7.",
    ),
    _case(
        "wrong-rating",
        1,
        "one core rating contradicts the result",
        "Vegan ramen in Kyoto.",
        _KYOTO_EVIDENCE,
        "Ramen Kaze is inexpensive vegan ramen at 22 Nishikikoji with a 4.9/5 rating.",
    ),
    _case(
        "unsupported-dietary-claim",
        1,
        "claims gluten-free suitability absent from evidence",
        "Gluten-free traditional food in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is fully gluten-free and safe for celiac diners, rated 4.7/5.",
    ),
    _case(
        "wrong-open-status",
        1,
        "temporarily closed venue is presented as open",
        "Fine dining in London.",
        _LONDON_EVIDENCE,
        "River Bistro is open and serving its expensive modern European tasting menu now.",
    ),
    _case(
        "cross-place-rating",
        1,
        "moves Tacos del Sur's rating to Mercado Roma",
        "Cheap eats in Roma Norte.",
        _MEXICO_EVIDENCE,
        "Mercado Roma is an inexpensive food hall at Queretaro 225, rated 4.8/5 from 780 reviews.",
    ),
    _case(
        "wrong-address",
        1,
        "assigns Verde Roma's address to Osteria Campo",
        "Traditional restaurants in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is a moderate Roman trattoria at Via Urbana 18, rated 4.7/5.",
    ),
    # Score 0: largely fabricated or several independent core contradictions.
    _case(
        "fabricated-rome-venue",
        0,
        "name, address, rating, and price are fabricated",
        "Traditional restaurants in Rome.",
        _ROME_EVIDENCE,
        "Roma Royal at Via Veneto 99 is a cheap 4.9-rated Roman restaurant with 3,000 reviews.",
    ),
    _case(
        "cross-venue-composite",
        0,
        "uses Gion's name with Ramen Kaze's diet, price, address, and rating",
        "Restaurant options in Kyoto.",
        _KYOTO_EVIDENCE,
        "Gion Yakitori is inexpensive vegan ramen at 22 Nishikikoji, rated 4.6/5.",
    ),
    _case(
        "several-london-contradictions",
        0,
        "price, status, cuisine, and rating all contradict River Bistro",
        "Fine dining in London.",
        _LONDON_EVIDENCE,
        "River Bistro is an open, inexpensive halal grill rated 4.9/5.",
    ),
    _case(
        "fabricated-mexico-market",
        0,
        "venue and every attached place fact are absent",
        "Cheap eats in Roma Norte.",
        _MEXICO_EVIDENCE,
        "Azteca Grand Market at Oaxaca 100 is a free 5.0-rated night market open 24 hours.",
    ),
    _case(
        "several-rome-contradictions",
        0,
        "real name but diet, price, rating, and address are all wrong",
        "Vegan restaurants in Rome.",
        _ROME_EVIDENCE,
        "Osteria Campo is a cheap fully vegan restaurant at Via Urbana 18, rated 5.0/5.",
    ),
    _case(
        "fabricated-kyoto-option",
        0,
        "restaurant, cuisine, rating, price, and dietary facts are invented",
        "Vegan ramen in Kyoto.",
        _KYOTO_EVIDENCE,
        "Kyoto Dragon Steakhouse is a free, fully vegan steak venue rated 5.0/5 with 10,000 reviews.",
    ),
    # Added coverage (25 -> 50): new destinations and a near-even final label
    # spread of {0: 12, 1: 12, 2: 13, 3: 13}.
    # Score 3: fully grounded or honestly uncertain.
    _case(
        "clear-pass-seoul",
        3,
        "all stated Han River Table facts match the evidence",
        "Traditional Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Han River Table at 10 Insadong-gil serves traditional Korean dishes, is moderately priced, and is rated 4.7/5 from 1,250 reviews.",
    ),
    _case(
        "clear-pass-seoul-vegan",
        3,
        "vegan status, cuisine, price, address, and rating are explicit",
        "Vegan Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Green Temple Seoul is a fully vegan, inexpensive Korean restaurant at 22 Itaewon-ro, rated 4.6/5 from 420 reviews.",
    ),
    _case(
        "both-seoul-venues-grounded",
        3,
        "keeps each Seoul venue's facts attached to the correct identity",
        "Restaurant options in Seoul.",
        _SEOUL_EVIDENCE,
        "Han River Table is a moderate Korean restaurant rated 4.7, while Green Temple Seoul is an inexpensive vegan Korean restaurant rated 4.6.",
    ),
    _case(
        "clear-pass-paris-gluten-free",
        3,
        "gluten-free suitability is explicit in the venue summary",
        "Gluten-free bakeries in Paris.",
        _PARIS_EVIDENCE,
        "Maison Sans Ble at 15 Rue Oberkampf is a dedicated gluten-free bakery and cafe, moderately priced and rated 4.8/5.",
    ),
    _case(
        "clear-pass-cape-seafood",
        3,
        "name, seafood cuisine, price, address, rating, and status are grounded",
        "Seafood at the V&A Waterfront in Cape Town.",
        _CAPE_TOWN_EVIDENCE,
        "Harbour Catch at the V&A Waterfront is an expensive South African seafood restaurant rated 4.6/5 from 2,200 reviews and listed operational.",
    ),
    _case(
        "honest-paris-dietary-uncertainty",
        3,
        "does not infer gluten-free suitability for Cafe Lumiere",
        "Gluten-free cafes in Paris.",
        _PARIS_EVIDENCE,
        "Cafe Lumiere is a French brunch cafe, but its listing does not verify gluten-free suitability; it is also listed temporarily closed.",
    ),
    # Score 2: one non-core unsupported detail or minor approximation.
    _case(
        "minor-seoul-rounded-rating",
        2,
        "rounds 4.7 to about 4.5 while preserving every other core fact",
        "Traditional Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Han River Table is a moderate Korean restaurant at 10 Insadong-gil, rated about 4.5/5.",
    ),
    _case(
        "minor-seoul-invented-ambience",
        2,
        "romantic ambience is one unsupported non-core detail",
        "Vegan Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Green Temple Seoul is an inexpensive fully vegan Korean restaurant rated 4.6/5, with a romantic candlelit dining room.",
    ),
    _case(
        "minor-paris-invented-pastry",
        2,
        "specific signature pastry is unsupported but non-core",
        "Gluten-free bakeries in Paris.",
        _PARIS_EVIDENCE,
        "Maison Sans Ble is a moderate dedicated gluten-free bakery rated 4.8/5, famous for its signature pistachio croissant.",
    ),
    _case(
        "minor-paris-reservation-tip",
        2,
        "exact reservation timing is unsupported but non-core",
        "Brunch cafes in Paris.",
        _PARIS_EVIDENCE,
        "Cafe Lumiere is an expensive French brunch cafe rated 4.5/5 and temporarily closed; when it reopens, reserve exactly two weeks ahead.",
    ),
    _case(
        "minor-cape-rounded-reviews",
        2,
        "rounds 2,200 reviews to about 2,000 without changing venue choice",
        "Seafood at the V&A Waterfront in Cape Town.",
        _CAPE_TOWN_EVIDENCE,
        "Harbour Catch is an expensive South African seafood restaurant at Pierhead, rated 4.6/5 from about 2,000 reviews.",
    ),
    _case(
        "minor-cape-wait-time",
        2,
        "wait-time estimate is unsupported but non-core",
        "Seafood restaurants in Cape Town.",
        _CAPE_TOWN_EVIDENCE,
        "Harbour Catch is an operational seafood restaurant rated 4.6/5; expect a twenty-minute wait at dinner.",
    ),
    _case(
        "minor-cape-invented-view",
        2,
        "mountain-view claim is unsupported non-core ambience",
        "South African fine dining in Cape Town.",
        _CAPE_TOWN_EVIDENCE,
        "Table Mountain Kitchen is a moderate South African fine-dining restaurant rated 4.4/5 and temporarily closed, with panoramic mountain views.",
    ),
    # Score 1: one materially misleading core error.
    _case(
        "wrong-seoul-price",
        1,
        "calls a moderate venue inexpensive",
        "Traditional Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Han River Table is an inexpensive Korean restaurant at 10 Insadong-gil, rated 4.7/5.",
    ),
    _case(
        "wrong-seoul-rating",
        1,
        "changes Green Temple Seoul's core rating",
        "Vegan Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Green Temple Seoul is a fully vegan Korean restaurant at 22 Itaewon-ro with a 4.9/5 rating.",
    ),
    _case(
        "wrong-paris-status",
        1,
        "presents a temporarily closed cafe as open",
        "Brunch cafes in Paris.",
        _PARIS_EVIDENCE,
        "Cafe Lumiere is open daily for expensive French brunch from 08:00 to 17:00.",
    ),
    _case(
        "unsupported-cape-vegan-claim",
        1,
        "asserts vegan suitability absent from the evidence",
        "Vegan seafood in Cape Town.",
        _CAPE_TOWN_EVIDENCE,
        "Harbour Catch serves a fully vegan seafood menu and is rated 4.6/5.",
    ),
    _case(
        "cross-seoul-address",
        1,
        "moves Green Temple Seoul's address to Han River Table",
        "Traditional Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Han River Table is a moderate Korean restaurant at 22 Itaewon-ro, rated 4.7/5.",
    ),
    _case(
        "wrong-paris-cuisine",
        1,
        "labels Cafe Lumiere as an Italian restaurant instead of French brunch",
        "Brunch cafes in Paris.",
        _PARIS_EVIDENCE,
        "Cafe Lumiere is an expensive Italian restaurant at 7 Rue Cler, rated 4.5/5.",
    ),
    # Score 0: fabricated venues or several independent core contradictions.
    _case(
        "fabricated-seoul-venue",
        0,
        "venue, address, price, rating, and review count are fabricated",
        "Traditional Korean restaurants in Seoul.",
        _SEOUL_EVIDENCE,
        "Seoul Royal Palace at 99 Gangnam-daero is a free 5.0-rated restaurant with 8,000 reviews.",
    ),
    _case(
        "cross-seoul-composite",
        0,
        "uses Han River Table's name with Green Temple's diet, price, address, and rating",
        "Restaurant options in Seoul.",
        _SEOUL_EVIDENCE,
        "Han River Table is a fully vegan inexpensive restaurant at 22 Itaewon-ro, rated 4.6/5.",
    ),
    _case(
        "several-paris-contradictions",
        0,
        "price, rating, dietary status, and open status all contradict Cafe Lumiere",
        "Cafes in Paris.",
        _PARIS_EVIDENCE,
        "Cafe Lumiere is an open, inexpensive, dedicated gluten-free cafe rated 5.0/5.",
    ),
    _case(
        "fabricated-paris-bakery",
        0,
        "venue and every attached place fact are absent",
        "Gluten-free bakeries in Paris.",
        _PARIS_EVIDENCE,
        "Paris Wheatless Palace at 100 Champs-Elysees is a free 5.0-rated bakery open 24 hours.",
    ),
    _case(
        "several-cape-contradictions",
        0,
        "price, cuisine, rating, address, and status contradict Table Mountain Kitchen",
        "South African dining in Cape Town.",
        _CAPE_TOWN_EVIDENCE,
        "Table Mountain Kitchen is an open, inexpensive Italian restaurant at the V&A Waterfront, rated 5.0/5.",
    ),
    _case(
        "fabricated-cape-option",
        0,
        "restaurant, cuisine, address, rating, and price are invented",
        "Seafood restaurants in Cape Town.",
        _CAPE_TOWN_EVIDENCE,
        "Cape Ocean Palace at 1 Beach Road is a free Japanese seafood restaurant rated 5.0/5 with 12,000 reviews.",
    ),
]
