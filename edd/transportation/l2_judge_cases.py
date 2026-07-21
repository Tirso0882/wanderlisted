"""Human-labeled Transportation trajectories for Layer 4 judge calibration.

The 28 held-out cases are balanced across the 0-3 faithfulness scale and do not
reuse the Melbourne in-context anchors from ``l2_judge.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from edd.harness import Trajectory  # noqa: E402

_ROME_WALK = [
    (
        "compute_route",
        "Route: Hotel Artemide, Rome -> Colosseum\n"
        "Distance: 1.7 km\n"
        "Duration: 720s\n"
        "Mode: WALK\n\n"
        "Steps:\n"
        "  1. Walk south on Via Nazionale (900 m, 420s)\n"
        "  2. Continue to the Colosseum (800 m, 300s)",
    )
]

_TOKYO_TRANSIT = [
    (
        "compute_route",
        "Route: Haneda Airport -> Shibuya Crossing, Tokyo\n"
        "Distance: 23.0 km\n"
        "Duration: 2400s\n"
        "Mode: TRANSIT\n\n"
        "Steps:\n"
        "  1. [TRAIN Tokyo Monorail] Haneda Airport Terminal 3 -> Hamamatsucho "
        "(6 stops) [1080s]\n"
        "  2. [TRAIN JR Yamanote Line] Hamamatsucho -> Shibuya (7 stops) [1020s]",
    )
]

_LONDON_TRANSIT = [
    (
        "compute_route",
        "Route: Paddington Station -> Tate Modern, London\n"
        "Distance: 5.6 km\n"
        "Duration: 1800s\n"
        "Mode: TRANSIT\n\n"
        "Steps:\n"
        "  1. [SUBWAY Elizabeth line] Paddington -> Tottenham Court Road "
        "(3 stops) [720s]\n"
        "  2. [BUS 26] Tottenham Court Road -> Tate Modern (4 stops) [780s]",
    )
]

_AMSTERDAM_BICYCLE = [
    (
        "compute_route",
        "Route: Anne Frank House, Amsterdam -> Rijksmuseum, Amsterdam\n"
        "Distance: 3.1 km\n"
        "Duration: 840s\n"
        "Mode: BICYCLE\n\n"
        "Steps:\n"
        "  1. Cycle southeast on Prinsengracht (1.3 km, 360s)\n"
        "  2. Continue to Rijksmuseum (1.8 km, 480s)",
    )
]

_NO_ROUTE = [("compute_route", "No route found.")]


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
    _case(
        "rome-walk-grounded",
        3,
        "route endpoints, mode, distance, duration, and steps are all grounded",
        "Walk from Hotel Artemide to the Colosseum.",
        _ROME_WALK,
        "Walk from Hotel Artemide to the Colosseum: 1.7 km in about 12 minutes. Go south on Via Nazionale, then continue to the Colosseum.",
    ),
    _case(
        "tokyo-transit-grounded",
        3,
        "both transit lines, stops, distance, and 40-minute duration match",
        "Take public transport from Haneda Airport to Shibuya Crossing.",
        _TOKYO_TRANSIT,
        "The 23.0 km transit trip takes about 40 minutes: take the Tokyo Monorail to Hamamatsucho, then the JR Yamanote Line to Shibuya.",
    ),
    _case(
        "london-transit-grounded",
        3,
        "the answer keeps each London line and stop count grounded",
        "Get from Paddington Station to Tate Modern by public transport.",
        _LONDON_TRANSIT,
        "From Paddington, take the Elizabeth line to Tottenham Court Road, then Bus 26 to Tate Modern. It is 5.6 km and takes about 30 minutes.",
    ),
    _case(
        "amsterdam-bicycle-grounded",
        3,
        "bicycle mode, route, and duration are all supported",
        "Cycle from Anne Frank House to the Rijksmuseum.",
        _AMSTERDAM_BICYCLE,
        "Cycle 3.1 km from Anne Frank House to the Rijksmuseum via Prinsengracht; the route takes about 14 minutes.",
    ),
    _case(
        "no-route-honest",
        3,
        "honestly reports the only result without adding route facts",
        "Find a route between these two locations.",
        _NO_ROUTE,
        "Google Routes did not return a route for those locations.",
    ),
    _case(
        "request-echo-grounded",
        3,
        "restating the requested public-transport mode is allowed request context",
        "For my airport arrival, take public transport from Haneda Airport to Shibuya Crossing.",
        _TOKYO_TRANSIT,
        "For your airport arrival, public transport from Haneda to Shibuya is 23.0 km and about 40 minutes, using the Tokyo Monorail then the JR Yamanote Line.",
    ),
    _case(
        "rome-soft-scenic-claim",
        2,
        "all core facts are grounded; scenic is one non-core impression",
        "Walk from Hotel Artemide to the Colosseum.",
        _ROME_WALK,
        "This scenic 1.7 km walk from Hotel Artemide to the Colosseum takes about 12 minutes via Via Nazionale.",
    ),
    _case(
        "tokyo-soft-comfort-claim",
        2,
        "the route facts are right; comfortable is one unsupported non-core extra",
        "Take public transport from Haneda Airport to Shibuya Crossing.",
        _TOKYO_TRANSIT,
        "Take the comfortable Tokyo Monorail to Hamamatsucho, then the JR Yamanote Line to Shibuya. The 23.0 km trip takes about 40 minutes.",
    ),
    _case(
        "london-soft-reliability-claim",
        2,
        "all measured route facts are grounded; reliable is a minor extra",
        "Get from Paddington Station to Tate Modern by public transport.",
        _LONDON_TRANSIT,
        "Take the Elizabeth line and then Bus 26 for a reliable 30-minute, 5.6 km trip to Tate Modern.",
    ),
    _case(
        "amsterdam-soft-views-claim",
        2,
        "all core cycling facts match; canal views are unsupported non-core color",
        "Cycle from Anne Frank House to the Rijksmuseum.",
        _AMSTERDAM_BICYCLE,
        "The 3.1 km bike ride via Prinsengracht takes about 14 minutes and has lovely canal views.",
    ),
    _case(
        "rome-rounded-duration",
        2,
        "rounds 12 minutes to roughly 10 while preserving the route",
        "Walk from Hotel Artemide to the Colosseum.",
        _ROME_WALK,
        "Walk south on Via Nazionale from Hotel Artemide to the Colosseum, about 1.7 km and roughly 10 minutes.",
    ),
    _case(
        "tokyo-soft-luggage-tip",
        2,
        "grounded route plus one unsupported but non-decision-changing luggage tip",
        "Take public transport from Haneda Airport to Shibuya Crossing.",
        _TOKYO_TRANSIT,
        "Take the Tokyo Monorail to Hamamatsucho, then the JR Yamanote Line to Shibuya; it is 23.0 km and about 40 minutes. Keep your luggage close during the transfer.",
    ),
    _case(
        "rome-wrong-duration",
        1,
        "12 minutes is changed to 25, a material core duration error",
        "Walk from Hotel Artemide to the Colosseum.",
        _ROME_WALK,
        "Walk 1.7 km from Hotel Artemide to the Colosseum via Via Nazionale; it takes about 25 minutes.",
    ),
    _case(
        "tokyo-wrong-line",
        1,
        "the first transit line is substituted with a line absent from results",
        "Take public transport from Haneda Airport to Shibuya Crossing.",
        _TOKYO_TRANSIT,
        "Take the Keikyu Airport Line to Hamamatsucho, then the JR Yamanote Line to Shibuya in about 40 minutes.",
    ),
    _case(
        "london-invented-fare",
        1,
        "fare is a core route fact that Google Routes did not return",
        "Get from Paddington Station to Tate Modern by public transport.",
        _LONDON_TRANSIT,
        "Take the Elizabeth line and then Bus 26 to Tate Modern; the trip takes about 30 minutes and costs GBP 4.20.",
    ),
    _case(
        "amsterdam-wrong-mode",
        1,
        "calls a BICYCLE route a drive, a materially misleading mode error",
        "Cycle from Anne Frank House to the Rijksmuseum.",
        _AMSTERDAM_BICYCLE,
        "Drive 3.1 km from Anne Frank House to the Rijksmuseum in about 14 minutes.",
    ),
    _case(
        "rome-wrong-distance",
        1,
        "replaces the 1.7 km measured distance with a core wrong value",
        "Walk from Hotel Artemide to the Colosseum.",
        _ROME_WALK,
        "Walk 4.5 km from Hotel Artemide to the Colosseum via Via Nazionale; it takes about 12 minutes.",
    ),
    _case(
        "london-wrong-transfer-count",
        1,
        "claims a direct train despite a subway-to-bus transfer in results",
        "Get from Paddington Station to Tate Modern by public transport.",
        _LONDON_TRANSIT,
        "Take a direct Elizabeth line train from Paddington to Tate Modern in about 30 minutes.",
    ),
    _case(
        "rome-fabricated-taxi",
        0,
        "mode, duration, distance, and fare are all fabricated",
        "Walk from Hotel Artemide to the Colosseum.",
        _ROME_WALK,
        "Take a EUR 25 taxi from Hotel Artemide to the Colosseum: it is a 5 km drive that takes 4 minutes.",
    ),
    _case(
        "tokyo-fabricated-route",
        0,
        "destination, mode, line, duration, and fare do not appear in results",
        "Take public transport from Haneda Airport to Shibuya Crossing.",
        _TOKYO_TRANSIT,
        "Take the direct Narita Express to Shinjuku for JPY 3,000; it takes 12 minutes with no stops.",
    ),
    _case(
        "london-multiple-contradictions",
        0,
        "line, destination, duration, distance, and fare contradict the route",
        "Get from Paddington Station to Tate Modern by public transport.",
        _LONDON_TRANSIT,
        "Take the Piccadilly line directly to Heathrow in 10 minutes; the 40 km ride costs GBP 25.",
    ),
    _case(
        "amsterdam-multiple-contradictions",
        0,
        "mode, distance, duration, and destination all conflict with results",
        "Cycle from Anne Frank House to the Rijksmuseum.",
        _AMSTERDAM_BICYCLE,
        "Ride the metro 12 km from Anne Frank House to Schiphol Airport in 45 minutes for EUR 9.",
    ),
    _case(
        "no-route-invented-directions",
        0,
        "asserts a route, duration, and fare when the tool found none",
        "Find a route between these two locations.",
        _NO_ROUTE,
        "Take Bus 14 directly for 18 minutes; the ticket costs EUR 2.50.",
    ),
    _case(
        "cross-route-composite",
        0,
        "Rome endpoints are combined with unrelated Tokyo mode, lines, and duration",
        "Walk from Hotel Artemide to the Colosseum.",
        _ROME_WALK,
        "From Hotel Artemide to the Colosseum, take the Tokyo Monorail then the JR Yamanote Line for a 40-minute, 23 km transit journey.",
    ),
    _case(
        "operational-limitations-grounded",
        3,
        "route facts are grounded and unsupported fare, pass, schedule, and accessibility details are explicitly left unverified",
        "Get from Paddington Station to Tate Modern by public transport; include fare, pass, schedule, and wheelchair details.",
        _LONDON_TRANSIT,
        "Take the Elizabeth line to Tottenham Court Road, then Bus 26 to Tate Modern. The 5.6 km route takes about 30 minutes. The route result did not provide a fare, pass validity, timetable, or step-free-access status; verify those details with the official operator.",
    ),
    _case(
        "soft-unverified-waiting-buffer",
        2,
        "core route facts match, but an extra waiting-time buffer is not in the route evidence",
        "Get from Paddington Station to Tate Modern by public transport.",
        _LONDON_TRANSIT,
        "Take the Elizabeth line to Tottenham Court Road, then Bus 26 to Tate Modern. The 5.6 km route takes about 30 minutes; allow another 10 minutes for waiting.",
    ),
    _case(
        "invented-operational-contract",
        1,
        "the route is correct but exact fare, pass validity, frequency, and accessibility guarantees are unsupported material claims",
        "Get from Paddington Station to Tate Modern by public transport; include fare, pass, schedule, and wheelchair details.",
        _LONDON_TRANSIT,
        "Take the Elizabeth line and Bus 26 for 30 minutes. It costs GBP 4.20, is covered by every Oyster pass, runs every 5 minutes, and is fully step-free with working lifts.",
    ),
    _case(
        "no-route-invented-operational-contract",
        0,
        "no route exists in the evidence, but the answer invents a route plus fare, pass, frequency, and accessibility facts",
        "Find an accessible transit route and include fare and schedule details.",
        _NO_ROUTE,
        "Take Bus 14 every 10 minutes for EUR 2.50; the city day pass covers it and the whole route is guaranteed step-free.",
    ),
]
