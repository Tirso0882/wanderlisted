"""EDD Layer 1 deterministic evaluators for TransportationAgent route decisions.

`compute_route` is the agent's single production tool. These pure functions
score its route decisions, never the volatile Google Routes result:

    origin/destination -> correct_route_pairs
    travel_mode        -> valid_travel_modes / correct_travel_modes
    waypoints          -> correct_waypoints / no_unrequested_waypoints
    include_steps      -> correct_include_steps
    route policy       -> called_compute_route / minimum_route_calls

The dataset represents each requested route as an item in ``expected["routes"]``.
Location alternatives are accepted as sets, so valid address and airport-code
representations do not false-fail.
"""

from __future__ import annotations

import json
import re
import unicodedata

_VALID_TRAVEL_MODES = {"DRIVE", "BICYCLE", "WALK", "TRANSIT", "TWO_WHEELER"}


def _route_calls(trajectory: list[dict]) -> list[dict]:
    return [call for call in trajectory if call.get("name") == "compute_route"]


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in text
    )
    text = text.encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _alternatives(value) -> set[str]:
    values = {value} if isinstance(value, str) else set(value)
    return {_normalize(item) for item in values if _normalize(item)}


def _matches_location(actual: object, expected) -> bool:
    actual_normalized = _normalize(actual)
    if not actual_normalized:
        return False
    actual_tokens = set(actual_normalized.split())
    for alternative in _alternatives(expected):
        alternative_tokens = set(alternative.split())
        if alternative == actual_normalized or alternative_tokens <= actual_tokens:
            return True
    return False


def _route_label(route: dict) -> str:
    origins = "/".join(sorted(_alternatives(route["origin"])))
    destinations = "/".join(sorted(_alternatives(route["destination"])))
    return f"{origins} -> {destinations}"


def _matches_route_pair(args: dict, route: dict) -> bool:
    return _matches_location(args.get("origin"), route["origin"]) and _matches_location(
        args.get("destination"), route["destination"]
    )


def _calls_for_route(calls: list[dict], route: dict) -> list[dict]:
    return [call for call in calls if _matches_route_pair(call.get("args", {}), route)]


def _mode(args: dict) -> str:
    return str(args.get("travel_mode") or "DRIVE").upper()


def _mode_alternatives(value) -> set[str]:
    values = {value} if isinstance(value, str) else set(value)
    return {str(item).upper() for item in values}


def _route_signature(call: dict) -> str:
    args = call.get("args", {})
    return json.dumps(
        {
            "origin": _normalize(args.get("origin")),
            "destination": _normalize(args.get("destination")),
            "travel_mode": _mode(args),
            "waypoints": [_normalize(item) for item in args.get("waypoints") or []],
            "include_steps": args.get("include_steps", True),
        },
        sort_keys=True,
    )


def _waypoint_groups(route: dict) -> list[set[str]]:
    groups = []
    for waypoint in route.get("waypoints", []):
        groups.append(_alternatives(waypoint))
    return groups


def _matches_waypoint(actual: object, alternatives: set[str]) -> bool:
    return _matches_location(actual, alternatives)


def called_compute_route(trajectory: list[dict], expected: dict) -> dict:
    used = bool(_route_calls(trajectory))
    return {
        "key": "called_compute_route",
        "score": int(used),
        "comment": "" if used else "agent never called compute_route",
    }


def minimum_route_calls(trajectory: list[dict], expected: dict) -> dict:
    calls = _route_calls(trajectory)
    required = expected.get("min_route_calls", len(expected["routes"]))
    distinct = {_route_signature(call) for call in calls}
    ok = len(distinct) >= required
    return {
        "key": "minimum_route_calls",
        "score": int(ok),
        "comment": ""
        if ok
        else (
            f"expected at least {required} distinct compute_route calls, got "
            f"{len(distinct)} distinct ({len(calls)} total calls)"
        ),
    }


def correct_route_pairs(trajectory: list[dict], expected: dict) -> dict:
    calls = _route_calls(trajectory)
    if not calls:
        return {
            "key": "correct_route_pairs",
            "score": 0,
            "comment": "no compute_route call to inspect",
        }
    missing = [
        _route_label(route)
        for route in expected["routes"]
        if not _calls_for_route(calls, route)
    ]
    return {
        "key": "correct_route_pairs",
        "score": int(not missing),
        "comment": "" if not missing else f"missing requested route(s): {missing}",
    }


def no_unrequested_route_pairs(trajectory: list[dict], expected: dict) -> dict:
    calls = _route_calls(trajectory)
    if not calls:
        return {
            "key": "no_unrequested_route_pairs",
            "score": 0,
            "comment": "no compute_route call to inspect",
        }
    unrelated = [
        f"{call.get('args', {}).get('origin')!r} -> "
        f"{call.get('args', {}).get('destination')!r}"
        for call in calls
        if not any(
            _matches_route_pair(call.get("args", {}), route)
            for route in expected["routes"]
        )
    ]
    return {
        "key": "no_unrequested_route_pairs",
        "score": int(not unrelated),
        "comment": "" if not unrelated else f"unrequested route(s): {unrelated}",
    }


def valid_travel_modes(trajectory: list[dict], expected: dict) -> dict:
    calls = _route_calls(trajectory)
    if not calls:
        return {
            "key": "valid_travel_modes",
            "score": 0,
            "comment": "no compute_route call to inspect",
        }
    invalid = sorted(
        {_mode(call.get("args", {})) for call in calls} - _VALID_TRAVEL_MODES
    )
    return {
        "key": "valid_travel_modes",
        "score": int(not invalid),
        "comment": "" if not invalid else f"unsupported travel_mode values: {invalid}",
    }


def correct_travel_modes(trajectory: list[dict], expected: dict) -> dict:
    labeled_routes = [route for route in expected["routes"] if "travel_mode" in route]
    if not labeled_routes:
        return {"key": "correct_travel_modes", "score": None, "comment": "no reference"}

    calls = _route_calls(trajectory)
    problems = []
    for route in labeled_routes:
        matching_calls = _calls_for_route(calls, route)
        accepted = _mode_alternatives(route["travel_mode"])
        modes = {_mode(call.get("args", {})) for call in matching_calls}
        if not matching_calls:
            problems.append(f"no call for {_route_label(route)}")
        elif not modes <= accepted:
            problems.append(
                f"{_route_label(route)} expected {sorted(accepted)}, got {sorted(modes)}"
            )
    return {
        "key": "correct_travel_modes",
        "score": int(not problems),
        "comment": "; ".join(problems),
    }


def correct_waypoints(trajectory: list[dict], expected: dict) -> dict:
    labeled_routes = [route for route in expected["routes"] if "waypoints" in route]
    if not labeled_routes:
        return {"key": "correct_waypoints", "score": None, "comment": "no reference"}

    calls = _route_calls(trajectory)
    problems = []
    for route in labeled_routes:
        matching_calls = _calls_for_route(calls, route)
        expected_groups = _waypoint_groups(route)
        calls_missing_waypoints = [
            call
            for call in matching_calls
            if not all(
                any(
                    _matches_waypoint(actual, alternatives)
                    for actual in call.get("args", {}).get("waypoints") or []
                )
                for alternatives in expected_groups
            )
        ]
        if not matching_calls:
            wanted = [sorted(group) for group in expected_groups]
            problems.append(f"{_route_label(route)} missing waypoint(s) {wanted}")
        elif calls_missing_waypoints:
            wanted = [sorted(group) for group in expected_groups]
            problems.append(
                f"{_route_label(route)} did not preserve waypoint(s) {wanted} on "
                f"{len(calls_missing_waypoints)} matching call(s)"
            )
    return {
        "key": "correct_waypoints",
        "score": int(not problems),
        "comment": "; ".join(problems),
    }


def no_unrequested_waypoints(trajectory: list[dict], expected: dict) -> dict:
    calls = _route_calls(trajectory)
    if not calls:
        return {
            "key": "no_unrequested_waypoints",
            "score": 0,
            "comment": "no compute_route call to inspect",
        }
    problems = []
    for route in expected["routes"]:
        if "waypoints" in route:
            continue
        for call in _calls_for_route(calls, route):
            waypoints = call.get("args", {}).get("waypoints") or []
            if waypoints:
                problems.append(
                    f"{_route_label(route)} got unrequested waypoints {waypoints}"
                )
    return {
        "key": "no_unrequested_waypoints",
        "score": int(not problems),
        "comment": "; ".join(problems),
    }


def correct_include_steps(trajectory: list[dict], expected: dict) -> dict:
    labeled_routes = [route for route in expected["routes"] if "include_steps" in route]
    if not labeled_routes:
        return {
            "key": "correct_include_steps",
            "score": None,
            "comment": "no reference",
        }

    calls = _route_calls(trajectory)
    problems = []
    for route in labeled_routes:
        matching_calls = _calls_for_route(calls, route)
        expected_value = route["include_steps"]
        values = {
            call.get("args", {}).get("include_steps", True) for call in matching_calls
        }
        if not matching_calls:
            problems.append(f"no call for {_route_label(route)}")
        elif values != {expected_value}:
            problems.append(
                f"{_route_label(route)} expected include_steps={expected_value}, got {sorted(values)}"
            )
    return {
        "key": "correct_include_steps",
        "score": int(not problems),
        "comment": "; ".join(problems),
    }


EVALUATORS = [
    called_compute_route,
    minimum_route_calls,
    correct_route_pairs,
    no_unrequested_route_pairs,
    valid_travel_modes,
    correct_travel_modes,
    correct_waypoints,
    no_unrequested_waypoints,
    correct_include_steps,
]


GOOD_TRAJECTORY = [
    {
        "name": "compute_route",
        "args": {
            "origin": "FCO Airport",
            "destination": "Hotel Artemide, Rome",
            "travel_mode": "TRANSIT",
            "include_steps": True,
        },
    },
    {
        "name": "compute_route",
        "args": {
            "origin": "Hotel Artemide, Rome",
            "destination": "Trastevere, Rome",
            "travel_mode": "WALK",
            "waypoints": ["Piazza Navona", "Pantheon"],
        },
    },
]

BAD_TRAJECTORY = [
    {
        "name": "compute_route",
        "args": {
            "origin": "FCO Airport",
            "destination": "Hotel Artemide, Rome",
            "travel_mode": "BUS",
            "include_steps": False,
        },
    },
    {
        "name": "compute_route",
        "args": {
            "origin": "Trastevere, Rome",
            "destination": "Hotel Artemide, Rome",
            "travel_mode": "WALK",
        },
    },
]

EXPECTED = {
    "min_route_calls": 2,
    "routes": [
        {
            "origin": {"FCO", "Fiumicino Airport"},
            "destination": {"Hotel Artemide", "Hotel Artemide Rome"},
            "travel_mode": "TRANSIT",
            "include_steps": True,
        },
        {
            "origin": {"Hotel Artemide", "Hotel Artemide Rome"},
            "destination": {"Trastevere", "Trastevere Rome"},
            "travel_mode": "WALK",
            "waypoints": [{"Piazza Navona"}, {"Pantheon"}],
        },
    ],
}


def _score(label: str, trajectory: list[dict]) -> None:
    print(f"\n{label}")
    print("-" * 68)
    for evaluator in EVALUATORS:
        output = evaluator(trajectory, EXPECTED)
        score = output["score"]
        verdict = "SKIP" if score is None else ("PASS" if score else "FAIL")
        print(f"  {output['key']:30s} {verdict}   {output['comment']}")


if __name__ == "__main__":
    _score("GOOD transportation decision", GOOD_TRAJECTORY)
    _score("BAD transportation decision", BAD_TRAJECTORY)
    print()
