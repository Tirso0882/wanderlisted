"""Layer 1 deterministic evaluators for ActivitiesAgent Places decisions.

The agent owns two Google Places tools. These functions score only the stable
decision surface: policy-compliant calls, requested city coverage, and each
constraint the traveler actually stated. Provider results remain outside Layer
1 so volatile live inventory cannot alter a deterministic score.
"""

from __future__ import annotations

import json
import re
import unicodedata

_PLACE_TOOLS = {"search_places_text", "search_places_nearby"}
_LODGING_PLACE_TYPES = {"bed_and_breakfast", "hostel", "hotel", "lodging", "motel", "resort"}


def _places_calls(trajectory: list[dict]) -> list[dict]:
    return [call for call in trajectory if call.get("name") in _PLACE_TOOLS]


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _terms(value: object) -> set[str]:
    values = {value} if isinstance(value, str) else set(value)
    return {_normalize(item) for item in values if _normalize(item)}


def _term_groups(value: object) -> list[set[str]]:
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


def _contains_any(text: str, expected_terms: object) -> bool:
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
    search_texts = [_call_search_text(call) for call in _places_calls(trajectory)]
    missing = [
        sorted(group)
        for group in _term_groups(expected[field])
        if not any(_contains_any(text, group) for text in search_texts)
    ]
    return {
        "key": key,
        "score": int(not missing),
        "comment": "" if not missing else f"Places searches missed {field}: {missing}",
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
    return {
        "key": "minimum_search_calls",
        "score": int(count >= required),
        "comment": ""
        if count >= required
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


def no_lodging_nearby_types(trajectory: list[dict], expected: dict) -> dict:
    """Activities owns attractions, not the HotelsAgent lodging search surface."""
    lodging_types = sorted(
        {
            str(call.get("args", {}).get("place_type") or "")
            for call in _places_calls(trajectory)
            if call.get("name") == "search_places_nearby"
            and str(call.get("args", {}).get("place_type") or "")
            in _LODGING_PLACE_TYPES
        }
    )
    return {
        "key": "no_lodging_nearby_types",
        "score": int(not lodging_types),
        "comment": ""
        if not lodging_types
        else f"ActivitiesAgent must not search lodging place types: {lodging_types}",
    }


def correct_locations(trajectory: list[dict], expected: dict) -> dict:
    if "locations" not in expected:
        return {"key": "correct_locations", "score": None, "comment": "no reference"}
    calls = _places_calls(trajectory)
    if not calls:
        return {
            "key": "correct_locations",
            "score": 0,
            "comment": "no Places call to read requested locations from",
        }
    search_texts = [_call_search_text(call) for call in calls]
    missing = [
        sorted(group)
        for group in _term_groups(expected["locations"])
        if not any(_contains_any(text, group) for text in search_texts)
    ]
    return {
        "key": "correct_locations",
        "score": int(not missing),
        "comment": "" if not missing else f"searches missed requested location(s): {missing}",
    }


def correct_interests(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(trajectory, expected, field="interests", key="correct_interests")


def correct_activity_type(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(
        trajectory, expected, field="activity_type", key="correct_activity_type"
    )


def correct_accessibility(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(
        trajectory, expected, field="accessibility", key="correct_accessibility"
    )


def correct_group_fit(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(trajectory, expected, field="group_fit", key="correct_group_fit")


def correct_travel_style(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(
        trajectory, expected, field="travel_style", key="correct_travel_style"
    )


def correct_venue_rental(trajectory: list[dict], expected: dict) -> dict:
    return _term_check(
        trajectory, expected, field="venue_rental", key="correct_venue_rental"
    )


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
    return {
        "key": "correct_proximity",
        "score": int(any(valid)),
        "comment": ""
        if any(valid)
        else f"no nearby search used the requested location at radius {max_radius}m",
    }


EVALUATORS = [
    called_places_search,
    minimum_search_calls,
    valid_nearby_place_types,
    no_lodging_nearby_types,
    correct_locations,
    correct_interests,
    correct_activity_type,
    correct_accessibility,
    correct_group_fit,
    correct_travel_style,
    correct_venue_rental,
    correct_proximity,
]


GOOD_TRAJECTORY = [
    {
        "name": "search_places_text",
        "args": {"query": "wheelchair accessible art museums in Paris"},
    },
    {
        "name": "search_places_nearby",
        "args": {
            "location": "Louvre Museum Paris",
            "place_type": "museum",
            "radius_meters": 800,
        },
    },
]

BAD_TRAJECTORY = [
    {
        "name": "search_places_nearby",
        "args": {"location": "Paris", "place_type": "lodging"},
    }
]

EXPECTED = {
    "locations": [{"paris", "louvre museum"}],
    "interests": [{"art"}],
    "activity_type": [{"museum"}],
    "accessibility": [{"wheelchair accessible"}],
    "max_radius_meters": 800,
    "proximity_location": {"louvre museum"},
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
    _score("GOOD activities search decision", GOOD_TRAJECTORY)
    _score("BAD activities search decision", BAD_TRAJECTORY)
    print()
