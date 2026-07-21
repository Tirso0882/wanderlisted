"""EDD Layer 1 — EVALUATORS for the HOTELS agent's DECISION.

This is our second worker agent. An evaluator
is a PURE function that scores ONE property of the agent's decision and returns
{"key", "score", "comment"}. score: 1 = pass, 0 = fail, None = SKIP (the query
never asked, so there is nothing to grade).

THE CHECKLIST = THE TOOL'S PARAMETER SURFACE. search_hotels_hotelbeds takes:
    city_code, check_in_date, check_out_date, adults, children, children_ages,
    min_category, max_rate, board_codes
Each parameter the agent fills from the query is a decision that can be wrong ->
a candidate check. We keep the ones that can-be-wrong AND matter:

    city_code             -> correct_city
    check_in/out          -> correct_dates
    adults, children      -> correct_guests   (+ children_ages when children > 0)
    min_category (stars)  -> correct_stars    (SKIP if the query didn't ask)
    board_codes           -> correct_board    (SKIP if the query didn't ask)
    max_rate (budget)     -> correct_budget   (SKIP if the query didn't ask)
    (was the tool called?)-> called_search_hotels

THREE HOTEL-SPECIFIC GOTCHAS (vs flights):
  * adults is now REQUIRED on the tool (we made it so) — a missing value is a
    real FAIL, and correct_guests verifies ONE child age per child.
  * hotels search by CITY code (Paris = PAR), never an airport — correct_city
    checks EVERY search call, so an airport-code probe on any call fails.
    * EVERY availability call must preserve the request. A correct first call
        cannot hide a later retry that changes dates, guests, or filters, and an
        unrequested restrictive filter is a failure rather than a skipped check.

We score ONLY the search decision; booking (check_hotel_rate) is a separate
scenario. And we score the DECISION (the args), never the live tool RESULT.

Run the fixture demo (pure functions on a fixed trajectory — no agent, instant):
    .venv/bin/python edd/hotels/l1_evaluate.py
"""

from __future__ import annotations


def _search_hotels_calls(trajectory: list[dict]) -> list[dict]:
    """Return the arguments from every Hotelbeds availability search."""
    return [
        call.get("args", {})
        for call in trajectory
        if call.get("name") == "search_hotels_hotelbeds"
    ]


def _all_search_city_codes(trajectory: list[dict]) -> list[str]:
    """EVERY city_code the agent searched (upper-cased) — lets correct_city catch
    an off-city probe (e.g. an airport code) on ANY call, not just the first."""
    return [
        str(c.get("args", {}).get("city_code") or "").upper()
        for c in trajectory
        if c.get("name") == "search_hotels_hotelbeds"
    ]


def _board_codes(args: dict) -> set[str]:
    """Normalize the comma-separated board-code tool argument."""
    return {
        board.strip().upper()
        for board in str(args.get("board_codes") or "").split(",")
        if board.strip()
    }


def _call_problem(call_number: int, message: str) -> str:
    return f"search #{call_number}: {message}"


def _acceptable(value) -> set[str]:
    """Ground truth may be ONE code or a SET of valid ones (normalised upper)."""
    values = {value} if isinstance(value, str) else set(value)
    return {v.upper() for v in values}


# ── Evaluator #1: did it call the search tool at all? ───────────────────────
def called_search_hotels(trajectory: list[dict], expected: dict) -> dict:
    used = any(c.get("name") == "search_hotels_hotelbeds" for c in trajectory)
    return {
        "key": "called_search_hotels",
        "score": int(used),
        "comment": "" if used else "agent never called search_hotels_hotelbeds",
    }


# ── Evaluator #2: right city? (CITY code, not an airport — check EVERY call) ─
def correct_city(trajectory: list[dict], expected: dict) -> dict:
    want = _acceptable(expected["city"])
    codes = _all_search_city_codes(trajectory)
    if not codes:
        return {
            "key": "correct_city",
            "score": 0,
            "comment": "no search_hotels_hotelbeds call to read a city from",
        }
    off = [
        _call_problem(call_number, f"off-city code {code!r}")
        for call_number, code in enumerate(codes, start=1)
        if code not in want
    ]
    ok = not off
    return {
        "key": "correct_city",
        "score": int(ok),
        "comment": ""
        if ok
        else f"expected every search in {sorted(want)}; {'; '.join(off)}",
    }


# ── Evaluator #3: right stay dates? (check-in always; check-out if expected) ─
def correct_dates(trajectory: list[dict], expected: dict) -> dict:
    if "check_in" not in expected:
        return {"key": "correct_dates", "score": None, "comment": "no reference"}
    calls = _search_hotels_calls(trajectory)
    if not calls:
        return {
            "key": "correct_dates",
            "score": 0,
            "comment": "no search_hotels_hotelbeds call to read dates from",
        }
    problems = []
    for call_number, args in enumerate(calls, start=1):
        if args.get("check_in_date") != expected["check_in"]:
            problems.append(
                _call_problem(
                    call_number,
                    f"check-in expected {expected['check_in']}, "
                    f"got {args.get('check_in_date')}",
                )
            )
        if (
            "check_out" in expected
            and args.get("check_out_date") != expected["check_out"]
        ):
            problems.append(
                _call_problem(
                    call_number,
                    f"check-out expected {expected['check_out']}, "
                    f"got {args.get('check_out_date')}",
                )
            )
    ok = not problems
    return {"key": "correct_dates", "score": int(ok), "comment": "; ".join(problems)}


# ── Evaluator #4: right guests? (adults/children; ONE age per child) ─────────
def correct_guests(trajectory: list[dict], expected: dict) -> dict:
    keys = [k for k in ("adults", "children") if k in expected]
    if not keys:
        return {"key": "correct_guests", "score": None, "comment": "no reference"}
    calls = _search_hotels_calls(trajectory)
    if not calls:
        return {
            "key": "correct_guests",
            "score": 0,
            "comment": "no search_hotels_hotelbeds call to read guests from",
        }
    problems = []
    for call_number, args in enumerate(calls, start=1):
        # adults is REQUIRED on the tool (missing -> None -> fail); children
        # legitimately defaults to 0.
        got = {"adults": args.get("adults"), "children": args.get("children", 0)}
        for key in keys:
            if got[key] != expected[key]:
                problems.append(
                    _call_problem(
                        call_number,
                        f"{key} expected {expected[key]}, got {got[key]}",
                    )
                )

        ages = [
            int(age.strip())
            for age in str(args.get("children_ages") or "").split(",")
            if age.strip().isdigit()
        ]
        # When children > 0 the tool needs ONE age per child. If the dataset
        # labels exact ages, validate the values too: "1,1" is not 4 and 9.
        if expected.get("children", 0) > 0:
            if len(ages) != expected["children"]:
                problems.append(
                    _call_problem(
                        call_number,
                        f"expected {expected['children']} child age(s), got "
                        f"{len(ages)} ({args.get('children_ages')!r})",
                    )
                )
            elif "children_ages" in expected and sorted(ages) != sorted(
                expected["children_ages"]
            ):
                problems.append(
                    _call_problem(
                        call_number,
                        f"children ages expected {expected['children_ages']}, got {ages}",
                    )
                )
        elif ages:
            problems.append(
                _call_problem(
                    call_number,
                    f"expected no child ages, got {ages}",
                )
            )
    ok = not problems
    return {"key": "correct_guests", "score": int(ok), "comment": "; ".join(problems)}


# ── Evaluator #5: right star filter? (only when the query asked for one) ─────
def correct_stars(trajectory: list[dict], expected: dict) -> dict:
    if "min_category" not in expected:
        return {"key": "correct_stars", "score": None, "comment": "no reference"}
    calls = _search_hotels_calls(trajectory)
    problems = [
        _call_problem(
            call_number,
            f"min_category expected {expected['min_category']}, "
            f"got {args.get('min_category')}",
        )
        for call_number, args in enumerate(calls, start=1)
        if args.get("min_category") != expected["min_category"]
    ]
    if not calls:
        problems.append("no search_hotels_hotelbeds call to read stars from")
    ok = not problems
    return {
        "key": "correct_stars",
        "score": int(ok),
        "comment": "; ".join(problems),
    }


# ── Evaluator #6: right board? (only when asked, e.g. "all-inclusive" -> AI) ─
def correct_board(trajectory: list[dict], expected: dict) -> dict:
    if "board" not in expected:
        return {"key": "correct_board", "score": None, "comment": "no reference"}
    raw_want = expected["board"]
    want = (
        {raw_want.upper()}
        if isinstance(raw_want, str)
        else {str(board).upper() for board in raw_want}
    )
    calls = _search_hotels_calls(trajectory)
    problems = [
        _call_problem(
            call_number,
            f"board_codes expected exactly {sorted(want)}, got {sorted(_board_codes(args))}",
        )
        for call_number, args in enumerate(calls, start=1)
        if _board_codes(args) != want
    ]
    if not calls:
        problems.append("no search_hotels_hotelbeds call to read board from")
    ok = not problems
    return {
        "key": "correct_board",
        "score": int(ok),
        "comment": "; ".join(problems),
    }


# ── Evaluator #7: right budget cap? (only when the query gave one) ───────────
def correct_budget(trajectory: list[dict], expected: dict) -> dict:
    if "max_rate" not in expected:
        return {"key": "correct_budget", "score": None, "comment": "no reference"}
    calls = _search_hotels_calls(trajectory)
    problems = [
        _call_problem(
            call_number,
            f"max_rate expected {expected['max_rate']}, got {args.get('max_rate')}",
        )
        for call_number, args in enumerate(calls, start=1)
        if args.get("max_rate") != expected["max_rate"]
    ]
    if not calls:
        problems.append("no search_hotels_hotelbeds call to read budget from")
    ok = not problems
    return {
        "key": "correct_budget",
        "score": int(ok),
        "comment": "; ".join(problems),
    }


# ── Evaluator #8: did it invent a restrictive optional filter? ─────────────
def no_unrequested_filters(trajectory: list[dict], expected: dict) -> dict:
    calls = _search_hotels_calls(trajectory)
    if not calls:
        return {
            "key": "no_unrequested_filters",
            "score": 0,
            "comment": "no search_hotels_hotelbeds call to inspect",
        }

    problems = []
    for call_number, args in enumerate(calls, start=1):
        if "min_category" not in expected and args.get("min_category") is not None:
            problems.append(
                _call_problem(
                    call_number,
                    f"unrequested min_category={args.get('min_category')}",
                )
            )
        if "max_rate" not in expected and args.get("max_rate") is not None:
            problems.append(
                _call_problem(
                    call_number,
                    f"unrequested max_rate={args.get('max_rate')}",
                )
            )
        if "board" not in expected and _board_codes(args):
            problems.append(
                _call_problem(
                    call_number,
                    f"unrequested board_codes={sorted(_board_codes(args))}",
                )
            )

    ok = not problems
    return {
        "key": "no_unrequested_filters",
        "score": int(ok),
        "comment": "; ".join(problems),
    }


# A "suite" is just a list of these functions (same shape as flights EVALUATORS).
EVALUATORS = [
    called_search_hotels,
    correct_city,
    correct_dates,
    correct_guests,
    correct_stars,
    correct_board,
    correct_budget,
    no_unrequested_filters,
]


def required_rechecks_completed(trajectory) -> dict:
    """Deterministically verify every RECHECK rate was sent to CheckRate.

    Applicability comes from the actual Hotelbeds output, not a hand-written
    label: rates vary live. This scores the agent's policy decision separately
    from whether CheckRate itself succeeds (an external operational outcome).
    """
    required: set[str] = set()
    for name, output in trajectory.tool_outputs:
        if name != "search_hotels_hotelbeds":
            continue
        current_rate_type = ""
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line.startswith("Rate type:"):
                current_rate_type = line.partition(":")[2].strip().upper()
            elif line.startswith("Rate key:"):
                if current_rate_type == "RECHECK":
                    required.add(line.partition(":")[2].strip())
                current_rate_type = ""

    if not required:
        return {
            "key": "required_rechecks_completed",
            "score": None,
            "comment": "no RECHECK rates in availability results",
        }

    checked: set[str] = set()
    for call in trajectory.tool_calls:
        if call.get("name") != "check_hotel_rate_hotelbeds":
            continue
        rate_keys = str(call.get("args", {}).get("rate_keys") or "")
        checked.update(key.strip() for key in rate_keys.split("|||") if key.strip())

    missing = sorted(required - checked)
    return {
        "key": "required_rechecks_completed",
        "score": int(not missing),
        "comment": "" if not missing else f"missing CheckRate for {missing}",
    }


# ── Fixture demo — prove the checks on fixed trajectories (no agent) ─────────
# GOOD = the exact args we OBSERVED on the real Bogota run.
GOOD_TRAJECTORY = [
    {
        "name": "search_hotels_hotelbeds",
        "args": {
            "city_code": "BOG",
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-09",
            "adults": 1,
            "children": 0,
            "children_ages": "",
            "min_category": 4,
            "max_rate": None,
            "board_codes": "",
        },
    },
]

# A deliberately WRONG decision, to prove the evaluators catch errors.
BAD_TRAJECTORY = [
    {
        "name": "search_hotels_hotelbeds",
        "args": {
            "city_code": "MEX",  # wrong — that's Mexico City, not Bogota
            "check_in_date": "2026-09-02",  # wrong — off by a day
            "check_out_date": "2026-09-09",
            "adults": 2,  # wrong — the query said 1 adult
            "min_category": 3,  # wrong — the query said 4+
        },
    },
]

# Ground truth for the Bogota query. Only the fields the query specified -> the
# rest (board, budget) SKIP.
EXPECTED = {
    "city": "BOG",
    "check_in": "2026-09-01",
    "check_out": "2026-09-09",
    "adults": 1,
    "min_category": 4,
}


def _score(label: str, trajectory: list[dict]) -> None:
    print(f"\n{label}")
    print("-" * 64)
    for evaluator in EVALUATORS:
        out = evaluator(trajectory, EXPECTED)
        score = out["score"]
        verdict = "SKIP" if score is None else ("PASS" if score else "FAIL")
        print(f"  {out['key']:22s} {verdict}   {out['comment']}")


if __name__ == "__main__":
    _score("GOOD decision — what the agent actually did (Bogota)", GOOD_TRAJECTORY)
    _score(
        "BAD decision — deliberately wrong, to prove it catches errors", BAD_TRAJECTORY
    )
    print()
