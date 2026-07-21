"""Layer 1 deterministic evaluators for RestaurantsAgent search decisions."""

from __future__ import annotations

import json
import re
import unicodedata

_PLACE_TOOLS = {"search_places_text", "search_places_nearby"}


def _places_calls(trajectory: list[dict]) -> list[dict]:
    return [call for call in trajectory if call.get("name") in _PLACE_TOOLS]


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _terms(value) -> set[str]:
    values = {value} if isinstance(value, str) else set(value)
    return {_normalize(item) for item in values}


def _term_groups(value) -> list[set[str]]:
    """Return required concept groups; terms inside one group are alternatives."""
    if isinstance(value, list):
        return [_terms(group) for group in value]
    return [_terms(value)]


def _call_search_text(call: dict) -> str:
    args = call.get("args", {})
    return _normalize(
        " ".join(
            str(args.get(key) or "") for key in ("query", "location", "place_type")
        )
    )


def _plural_variants(term: str) -> set[str]:
    """Accept ordinary singular/plural wording without fuzzy substring matches."""
    words = term.split()
    if not words:
        return {term}
    last = words[-1]
    if last.endswith("y") and len(last) > 1 and last[-2] not in "aeiou":
        plural = last[:-1] + "ies"
    elif last.endswith(("s", "x", "z", "ch", "sh")):
        plural = last + "es"
    else:
        plural = last + "s"
    return {term, " ".join([*words[:-1], plural])}


def _contains_any(text: str, expected_terms) -> bool:
    normalized = f" {text} "
    variants = {
        variant for term in _terms(expected_terms) for variant in _plural_variants(term)
    }
    return any(f" {variant} " in normalized for variant in variants)


def _term_check(
    trajectory: list[dict], expected: dict, *, field: str, key: str
) -> dict:
    if field not in expected:
        return {"key": key, "score": None, "comment": "no reference"}
    calls = _places_calls(trajectory)
    search_texts = [_call_search_text(call) for call in calls]
    groups = _term_groups(expected[field])
    missing = [
        sorted(group)
        for group in groups
        if not any(_contains_any(text, group) for text in search_texts)
    ]
    matched = not missing
    return {
        "key": key,
        "score": int(matched),
        "comment": ""
        if matched
        else f"Places searches missed required {field} concept(s): {missing}",
    }


def called_places_search(trajectory: list[dict], expected: dict) -> dict:
    used = bool(_places_calls(trajectory))
    return {
        "key": "called_places_search",
        "score": int(used),
        "comment": "" if used else "agent never called a Google Places search tool",
    }


def minimum_search_calls(trajectory: list[dict], expected: dict) -> dict:
    required = expected.get("min_search_calls", 2)
    calls = _places_calls(trajectory)
    signatures = {
        (
            call.get("name"),
            json.dumps(call.get("args", {}), sort_keys=True, default=str),
        )
        for call in calls
    }
    count = len(signatures)
    ok = count >= required
    return {
        "key": "minimum_search_calls",
        "score": int(ok),
        "comment": ""
        if ok
        else (
            f"expected at least {required} distinct Places calls, got {count} distinct "
            f"({len(calls)} total calls)"
        ),
    }


def valid_nearby_place_types(trajectory: list[dict], expected: dict) -> dict:
    nearby_calls = [
        call
        for call in _places_calls(trajectory)
        if call.get("name") == "search_places_nearby"
    ]
    if not nearby_calls:
        return {
            "key": "valid_nearby_place_types",
            "score": None,
            "comment": "no nearby search",
        }
    invalid = sorted(
        {
            str(call.get("args", {}).get("place_type") or "")
            for call in nearby_calls
            if not re.fullmatch(
                r"[a-z][a-z0-9_]*",
                str(call.get("args", {}).get("place_type") or ""),
            )
        }
    )
    return {
        "key": "valid_nearby_place_types",
        "score": int(not invalid),
        "comment": ""
        if not invalid
        else f"Nearby Search place_type must be a lowercase identifier: {invalid}",
    }


def correct_location(trajectory: list[dict], expected: dict) -> dict:
    if "location" not in expected:
        return {"key": "correct_location", "score": None, "comment": "no reference"}
    calls = _places_calls(trajectory)
    if not calls:
        return {
            "key": "correct_location",
            "score": 0,
            "comment": "no Places call to read a location from",
        }
    off_location = [
        _call_search_text(call)
        for call in calls
        if not _contains_any(_call_search_text(call), expected["location"])
    ]
    ok = not off_location
    return {
        "key": "correct_location",
        "score": int(ok),
        "comment": ""
        if ok
        else f"searches missing the requested location: {off_location}",
    }


def correct_area(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(trajectory, expected, field="area", key="correct_area")


def correct_cuisine(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(trajectory, expected, field="cuisine", key="correct_cuisine")


def correct_dietary(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(trajectory, expected, field="dietary", key="correct_dietary")


def correct_venue_type(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(
        trajectory, expected, field="venue_type", key="correct_venue_type"
    )


def correct_price_style(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(
        trajectory, expected, field="price_style", key="correct_price_style"
    )


def correct_group_fit(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(trajectory, expected, field="group_fit", key="correct_group_fit")


def correct_proximity(trajectory: list[dict], expected: dict) -> dict:
    if "max_radius_meters" not in expected:
        return {"key": "correct_proximity", "score": None, "comment": "no reference"}
    nearby_calls = [
        call
        for call in _places_calls(trajectory)
        if call.get("name") == "search_places_nearby"
    ]
    if not nearby_calls:
        return {
            "key": "correct_proximity",
            "score": 0,
            "comment": "explicit radius request was not handled with search_places_nearby",
        }
    max_radius = expected["max_radius_meters"]
    valid = []
    for call in nearby_calls:
        args = call.get("args", {})
        radius = args.get("radius_meters", 1500)
        location_ok = "proximity_location" not in expected or _contains_any(
            _normalize(args.get("location") or ""), expected["proximity_location"]
        )
        valid.append(
            isinstance(radius, (int, float)) and radius == max_radius and location_ok
        )
    ok = any(valid)
    return {
        "key": "correct_proximity",
        "score": int(ok),
        "comment": ""
        if ok
        else f"no nearby search used the requested location at radius {max_radius}m",
    }


EVALUATORS = [
    called_places_search,
    minimum_search_calls,
    valid_nearby_place_types,
    correct_location,
    correct_area,
    correct_cuisine,
    correct_dietary,
    correct_venue_type,
    correct_price_style,
    correct_group_fit,
    correct_proximity,
]


GOOD_TRAJECTORY = [
    {
        "name": "search_places_text",
        "args": {"query": "best sushi restaurants in Shinjuku Tokyo"},
    },
    {
        "name": "search_places_nearby",
        "args": {
            "location": "Shinjuku Tokyo",
            "place_type": "restaurant",
            "radius_meters": 1500,
        },
    },
]

BAD_TRAJECTORY = [
    {
        "name": "search_places_text",
        "args": {"query": "popular restaurants in Paris"},
    }
]

EXPECTED = {
    "location": {"tokyo", "shinjuku"},
    "area": {"shinjuku"},
    "cuisine": {"sushi", "japanese"},
    "venue_type": {"restaurant", "sushi"},
}


def _score(label: str, trajectory: list[dict]) -> None:
    print(f"\n{label}")
    print("-" * 68)
    for evaluator in EVALUATORS:
        output = evaluator(trajectory, EXPECTED)
        score = output["score"]
        verdict = "SKIP" if score is None else ("PASS" if score else "FAIL")
        print(f"  {output['key']:22s} {verdict}   {output['comment']}")


if __name__ == "__main__":
    _score("GOOD restaurant search decision", GOOD_TRAJECTORY)
    _score("BAD restaurant search decision", BAD_TRAJECTORY)
    print()
