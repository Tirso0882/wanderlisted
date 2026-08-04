"""Deterministic Itinerary Layer-1 evaluators and cross-case invariants."""

from __future__ import annotations

from datetime import date, timedelta


def _value(report: dict, path: str):
    current = report
    for part in path.split("."):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def _check(key, passed, actual, expected):
    return {"key": key, "passed": bool(passed), "actual": actual, "expected": expected}


def _invariant_checks(report: dict) -> list[dict]:
    if report.get("status") != "completed":
        return []
    plan = report["plan"]
    start = date.fromisoformat(plan["start_date"])
    expected_dates = [
        (start + timedelta(days=offset)).isoformat()
        for offset in range(plan["duration_days"])
    ]
    checks = [
        _check(
            "invariant:calendar",
            report["dates"] == expected_dates,
            report["dates"],
            expected_dates,
        ),
        _check(
            "invariant:day-numbers",
            report["day_numbers"] == list(range(1, plan["duration_days"] + 1)),
            report["day_numbers"],
            list(range(1, plan["duration_days"] + 1)),
        ),
    ]

    emitted = {
        source_id
        for values in [
            *report["scheduled_source_ids"].values(),
            *report["unscheduled_source_ids"].values(),
        ]
        for source_id in values
    }
    selected = set(report["draft_source_ids"])
    checks.append(
        _check(
            "invariant:selected-source-ids",
            emitted <= selected,
            sorted(emitted),
            sorted(selected),
        )
    )

    route_by_day = {
        item["day_number"]: item
        for item in (report.get("route_plan") or {}).get("days", [])
    }
    route_measurements_ok = True
    route_actual = []
    for number, steps in report["transit"].items():
        route = route_by_day.get(int(number))
        if route is None:
            route_measurements_ok = route_measurements_ok and not steps
            continue
        legs = {
            (
                leg["route_leg_index"]
                if leg.get("route_leg_index") is not None
                else position
            ): leg
            for position, leg in enumerate(route["legs"])
        }
        for step in steps:
            index = step["route_leg_index"]
            if index not in legs:
                route_measurements_ok = False
                continue
            leg = legs[index]
            route_actual.append(
                (int(number), index, step["distance_meters"], step["duration_seconds"])
            )
            route_measurements_ok = route_measurements_ok and (
                step["distance_meters"] == leg["distance_meters"]
                and step["duration_seconds"] == leg["duration_seconds"]
                and step["fare_estimate_usd"] == 0
            )
    checks.append(
        _check(
            "invariant:route-measurements-and-no-fares",
            route_measurements_ok,
            route_actual,
            "exact RoutePlan metres/seconds and zero invented fares",
        )
    )

    budget = report.get("budget")
    if budget:
        supported = {
            item["source_id"]: float(item["amount_usd"])
            for item in budget["line_items"]
            if item["amount_usd"] is not None and not item["estimated"]
        }
        expected_costs = {
            number: round(
                sum(supported.get(source_id, 0) for source_id in source_ids), 2
            )
            for number, source_ids in report["scheduled_source_ids"].items()
        }
        checks.append(
            _check(
                "invariant:daily-cost-source-mapping",
                report["daily_costs"] == expected_costs,
                report["daily_costs"],
                expected_costs,
            )
        )
        checks.append(
            _check(
                "invariant:overall-budget-copy",
                report["total_budget_usd"] == budget["total"],
                report["total_budget_usd"],
                budget["total"],
            )
        )
    return checks


def evaluate_report(report: dict, expected: dict) -> list[dict]:
    checks: list[dict] = []
    for path, value in expected.get("equals", {}).items():
        actual = _value(report, path)
        checks.append(_check(f"equals:{path}", actual == value, actual, value))
    for path, values in expected.get("contains", {}).items():
        actual = _value(report, path)
        checks.append(
            _check(
                f"contains:{path}",
                all(value in actual for value in values),
                actual,
                values,
            )
        )
    for path, values in expected.get("excludes", {}).items():
        actual = _value(report, path)
        checks.append(
            _check(
                f"excludes:{path}",
                all(value not in actual for value in values),
                actual,
                values,
            )
        )
    return [*checks, *_invariant_checks(report)]


def case_passes(report: dict, expected: dict) -> bool:
    return all(check["passed"] for check in evaluate_report(report, expected))
