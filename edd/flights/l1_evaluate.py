"""EDD Step 2 — first EVALUATORS (for the Flights agent's DECISION).

An evaluator is a small function that judges ONE property of the agent's
behaviour and returns a score. It turns "did the agent do the right thing?"
into a concrete, repeatable measurement.

WHY they exist:
    - Catch failures & regressions automatically instead of eyeballing runs.
    - Measure objectively, so you can prove a change (prompt/model) helped.
    - Scale: you can't hand-read hundreds of traces; evaluators do it for you.

WHEN you build them:
    Right after you OBSERVE and can state what "good" looks like — and BEFORE
    you improve the agent, so the eval can prove the improvement.

HOW they're shaped:
    A pure function: input = the agent's trajectory (+ optional expected answer),
    output = {"key", "score", "comment"}. Because it's pure, we test it here on
    a CAPTURED trajectory — no live agent, no API cost, instant and deterministic.

Run it:
    .venv/bin/python edd/flights/l1_evaluate.py
"""

from __future__ import annotations


# ── The decision from the trace (the "New York -> Tokyo" query) ──
# This is the exact args dict it's read in the LangSmith `search_flights` span.
GOOD_TRAJECTORY = [
    {"name": "lookup_iata_code", "args": {"location": "New York"}},
    {"name": "lookup_iata_code", "args": {"location": "Tokyo"}},
    {
        "name": "search_flights",
        "args": {
            "origin": "JFK",
            "destination": "NRT",
            "departure_date": "2026-08-15",
            "return_date": "2026-08-22",
            "adults": 1,
            "children": 0,
            "infants": 0,
            "travel_class": "ECONOMY",
            "non_stop": False,
        },
    },
]

# A deliberately WRONG decision, so we can prove the evaluator catches errors.
BAD_TRAJECTORY = [
    {"name": "lookup_iata_code", "args": {"location": "New York"}},
    {
        "name": "search_flights",
        "args": {
            "origin": "LAX",  # wrong — that's Los Angeles
            "destination": "LHR",  # wrong — that's London
            "departure_date": "2026-08-15",
            "travel_class": "ECONOMY",
        },
    },
]

# The ground truth for the "New York -> Tokyo" query. Includes date/cabin/pax so
# the fixture demo exercises ALL five evaluators (not just airports).
EXPECTED = {
    "origin": "JFK",
    "destination": "NRT",
    "departure_date": "2026-08-15",
    "adults": 1,
    "cabin": "ECONOMY",
}


def _search_flights_args(trajectory: list[dict]) -> dict:
    """Pull the args of the search_flights call out of a trajectory (or {})."""
    for call in trajectory:
        if call.get("name") == "search_flights":
            return call.get("args", {})
    return {}


# ── Evaluator #1: the simplest possible — did it call the tool at all? ──────
def called_search_flights(trajectory: list[dict], expected: dict) -> dict:
    # (Ignores `expected` — some checks need no reference answer. Evaluator
    #  frameworks still hand every evaluator the same arguments, so we accept it.)
    used = any(call.get("name") == "search_flights" for call in trajectory)
    return {
        "key": "called_search_flights",
        "score": int(used),
        "comment": "" if used else "agent never called search_flights",
    }


# ── Evaluator #2: did the DECISION use the right airports? ───────────────────
def _acceptable(value) -> set[str]:
    """Ground truth for an airport may be ONE code or a SET of valid ones.

    A city like New York has JFK, EWR and LGA — any is a correct answer. We
    normalise the expected value to a set and check MEMBERSHIP, instead of
    demanding one specific code (which would false-fail a valid alternative).
    """
    return {value} if isinstance(value, str) else set(value)


def correct_airports(trajectory: list[dict], expected: dict) -> dict:
    args = _search_flights_args(trajectory)
    origins = _acceptable(expected["origin"])
    destinations = _acceptable(expected["destination"])
    ok = args.get("origin") in origins and args.get("destination") in destinations
    return {
        "key": "correct_airports",
        "score": int(ok),
        "comment": ""
        if ok
        else (
            f"expected origin in {sorted(origins)}, dest in {sorted(destinations)}; "
            f"got {args.get('origin')}->{args.get('destination')}"
        ),
    }


# ── Evaluator #3: right dates? (departure always; return only if expected) ──
def correct_dates(trajectory: list[dict], expected: dict) -> dict:
    if "departure_date" not in expected:
        return {"key": "correct_dates", "score": None, "comment": "no reference"}
    args = _search_flights_args(trajectory)
    problems = []
    if args.get("departure_date") != expected["departure_date"]:
        problems.append(
            f"departure expected {expected['departure_date']}, got {args.get('departure_date')}"
        )
    if "return_date" in expected and args.get("return_date") != expected["return_date"]:
        problems.append(
            f"return expected {expected['return_date']}, got {args.get('return_date')}"
        )
    ok = not problems
    return {"key": "correct_dates", "score": int(ok), "comment": "; ".join(problems)}


# ── Evaluator #4: right cabin class? (only when the query specified one) ─────
def correct_cabin(trajectory: list[dict], expected: dict) -> dict:
    if "cabin" not in expected:
        return {"key": "correct_cabin", "score": None, "comment": "no reference"}
    args = _search_flights_args(trajectory)
    got = str(args.get("travel_class") or "").upper()
    want = str(expected["cabin"]).upper()
    ok = got == want
    return {
        "key": "correct_cabin",
        "score": int(ok),
        "comment": "" if ok else f"expected {want}, got {got or None}",
    }


# ── Evaluator #5: right passenger counts? (adults / children / infants) ────
def correct_passengers(trajectory: list[dict], expected: dict) -> dict:
    keys = [k for k in ("adults", "children", "infants") if k in expected]
    if not keys:
        return {"key": "correct_passengers", "score": None, "comment": "no reference"}
    args = _search_flights_args(trajectory)
    defaults = {"adults": 1, "children": 0, "infants": 0}  # the tool's own defaults
    problems = []
    for k in keys:
        got = args.get(k, defaults[k])
        if got != expected[k]:
            problems.append(f"{k} expected {expected[k]}, got {got}")
    ok = not problems
    return {
        "key": "correct_passengers",
        "score": int(ok),
        "comment": "; ".join(problems),
    }


# A "suite" is just a list of these functions.
EVALUATORS = [
    called_search_flights,
    correct_airports,
    correct_dates,
    correct_cabin,
    correct_passengers,
]


def _score(label: str, trajectory: list[dict]) -> None:
    print(f"\n{label}")
    print("-" * 64)
    for evaluator in EVALUATORS:
        out = evaluator(trajectory, EXPECTED)
        score = out["score"]
        verdict = "SKIP" if score is None else ("PASS" if score else "FAIL")
        print(f"  {out['key']:24s} {verdict}   {out['comment']}")


if __name__ == "__main__":
    _score("GOOD decision — what the agent actually did", GOOD_TRAJECTORY)
    _score(
        "BAD decision — deliberately wrong, to prove it catches errors", BAD_TRAJECTORY
    )
    print()
