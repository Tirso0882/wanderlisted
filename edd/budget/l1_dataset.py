"""Lean 16-case BudgetAgent production contract dataset."""

DATASET_VERSION = "1.0.0"
DATASET_SIZE = 16

DATASET: list[dict] = [
    {
        "name": "arithmetic-reconciliation",
        "tags": ["arithmetic", "reconciliation"],
        "query": "Reconcile six explicit USD category costs.",
        "scenario": "arithmetic",
        "expected": {
            "equals": {
                "total": 1000,
                "reconciliation_delta": 0,
                "coverage_status": "complete",
            }
        },
    },
    {
        "name": "party-scaling",
        "tags": ["party", "scaling"],
        "query": "Scale a per-person-per-day meal cost for three travelers.",
        "scenario": "party_scaling",
        "expected": {"equals": {"meals": 120, "total": 1020, "per_person": 340}},
    },
    {
        "name": "duration-scaling",
        "tags": ["duration", "scaling"],
        "query": "Scale a nightly lodging cost over three nights.",
        "scenario": "duration_scaling",
        "expected": {"equals": {"accommodation": 300, "total": 1000}},
    },
    {
        "name": "budget-style-regional-estimates",
        "tags": ["style", "estimates"],
        "query": "Estimate uncovered Tokyo daily categories for budget travel style.",
        "scenario": "budget_style",
        "expected": {
            "equals": {
                "meals": 96,
                "total": 1104,
                "coverage_status": "complete_with_estimates",
            }
        },
    },
    {
        "name": "selected-flight-only",
        "tags": ["selection", "flights"],
        "query": "Count the selected flight offer and ignore a more expensive candidate.",
        "scenario": "flight_selection",
        "expected": {
            "equals": {"flights": 500, "total": 1100},
            "exclude_source_ids": ["flight-distractor"],
        },
    },
    {
        "name": "selected-hotel-only",
        "tags": ["selection", "hotels"],
        "query": "Count the selected hotel rate and ignore unselected inventory.",
        "scenario": "hotel_selection",
        "expected": {
            "equals": {"accommodation": 600, "total": 1300},
            "exclude_source_ids": ["hotel-distractor"],
        },
    },
    {
        "name": "missing-flight-partial",
        "tags": ["missing-major", "coverage"],
        "query": "Report partial coverage when no selected flight price exists.",
        "scenario": "missing_flight",
        "expected": {
            "equals": {"coverage_status": "partial", "verdict": "unknown"},
            "contains": {"missing_categories": ["flights"]},
        },
    },
    {
        "name": "missing-lodging-partial",
        "tags": ["missing-major", "coverage"],
        "query": "Report partial coverage when no selected lodging price exists.",
        "scenario": "missing_lodging",
        "expected": {
            "equals": {"coverage_status": "partial", "verdict": "unknown"},
            "contains": {"missing_categories": ["accommodation"]},
        },
    },
    {
        "name": "currency-conversion",
        "tags": ["conversion", "display-currency"],
        "query": "Convert explicit EUR costs to USD and render EUR display values.",
        "scenario": "conversion_success",
        "expected": {
            "equals": {
                "total": 1100,
                "display_breakdown.total": 990,
                "conversion_status": "complete",
            }
        },
    },
    {
        "name": "conversion-failure",
        "tags": ["conversion", "failure", "coverage"],
        "query": "Preserve an unconverted EUR flight and withhold the target verdict.",
        "scenario": "conversion_failure",
        "expected": {
            "equals": {
                "coverage_status": "partial",
                "verdict": "unknown",
                "conversion_status": "unavailable",
            },
            "null_usd_source_ids": ["traveler:0:flights"],
        },
    },
    {
        "name": "multicity-regional-allocation",
        "tags": ["estimates", "multi-city", "duration"],
        "query": "Allocate daily estimates by stay nights plus the final day.",
        "scenario": "multicity_estimates",
        "expected": {
            "equals": {"meals": 140, "coverage_status": "complete_with_estimates"}
        },
    },
    {
        "name": "within-target-verdict",
        "tags": ["target", "within-budget"],
        "query": "Compare a complete USD total with a higher target.",
        "scenario": "target_within",
        "expected": {"equals": {"verdict": "within_budget", "remaining_budget": 200}},
    },
    {
        "name": "over-target-verdict",
        "tags": ["target", "over-budget"],
        "query": "Compare a complete USD total with a lower target.",
        "scenario": "target_over",
        "expected": {"equals": {"verdict": "over_budget", "remaining_budget": -200}},
    },
    {
        "name": "places-price-level-unsupported",
        "tags": ["unsupported-signal", "places"],
        "query": "Retain Places price levels without inventing numeric costs.",
        "scenario": "places_signal",
        "expected": {
            "signals": [["places", "price_level"]],
            "exclude_components": ["places"],
        },
    },
    {
        "name": "routes-no-fare-unsupported",
        "tags": ["unsupported-signal", "routes"],
        "query": "Retain Routes no-fare output without inventing a fare.",
        "scenario": "routes_signal",
        "expected": {
            "signals": [["routes", "fare_status"]],
            "exclude_components": ["routes"],
        },
    },
    {
        "name": "ambiguous-numeric-distractors",
        "tags": ["ambiguity", "numeric-distractor", "duplicates", "selection"],
        "query": "Ignore an unselected 99999 distractor and a repeated selected source.",
        "scenario": "numeric_distractor",
        "expected": {
            "equals": {"flights": 500, "total": 1100},
            "exclude_source_ids": ["numeric-99999"],
            "source_counts": {"selected-500": 1},
        },
    },
]
