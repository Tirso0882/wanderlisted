"""Hermetic 16-case ItineraryAgent production-contract dataset."""

DATASET_VERSION = "1.0.0"
DATASET_SIZE = 16

DATASET: list[dict] = [
    {
        "name": "artifact-place-fields",
        "tags": ["artifact_consumption", "places"],
        "query": "Compile the selected provider place without rewriting its facts.",
        "scenario": "artifact_place_fields",
        "expected": {
            "equals": {
                "status": "completed",
                "scheduled_source_ids.2": ["activities:museum-1"],
                "scheduled_places.2.0.name": "Provider Museum",
                "scheduled_places.2.0.address": "1 Evidence Street, Paris",
                "scheduled_places.2.0.website_url": "https://museum.example",
                "scheduled_places.2.0.google_maps_url": "https://maps.example/museum-1",
                "scheduled_places.2.0.photo_urls": [
                    "https://images.example/museum-1.jpg"
                ],
            }
        },
    },
    {
        "name": "artifact-hotel-rate-key",
        "tags": ["artifact_consumption", "hotels"],
        "query": "Resolve the selected accommodation from its exact Hotelbeds rate key.",
        "scenario": "artifact_hotel_rate",
        "expected": {
            "equals": {
                "status": "completed",
                "selected_hotel_rate_keys": ["rate-paris-1"],
                "selected_hotel_names": ["Paris Evidence Hotel 1"],
            }
        },
    },
    {
        "name": "artifact-route-order-measurements",
        "tags": ["artifact_consumption", "routes"],
        "query": "Use RoutePlan order and preserve measured metres and seconds exactly.",
        "scenario": "artifact_route",
        "expected": {
            "equals": {
                "status": "completed",
                "scheduled_source_ids.2": [
                    "activities:second",
                    "activities:first",
                ],
                "scheduled_names.2": ["Second Museum", "First Museum"],
                "transit.2.0.distance_meters": 701,
                "transit.2.0.duration_seconds": 601,
                "transit.2.0.fare_estimate_usd": 0.0,
            }
        },
    },
    {
        "name": "artifact-supported-daily-costs",
        "tags": ["artifact_consumption", "budget"],
        "query": "Allocate only mapped non-estimated Budget line items to the selected day.",
        "scenario": "artifact_costs",
        "expected": {
            "equals": {
                "status": "completed",
                "daily_costs.2": 35.0,
                "cost_coverage.2": "complete",
                "total_budget_usd": 635.0,
            }
        },
    },
    {
        "name": "dates-inclusive-contiguous",
        "tags": ["date_consistency", "calendar"],
        "query": "Build every inclusive calendar day from the trip skeleton.",
        "scenario": "dates_inclusive",
        "expected": {
            "equals": {
                "status": "completed",
                "dates": [
                    "2026-09-01",
                    "2026-09-02",
                    "2026-09-03",
                    "2026-09-04",
                ],
                "day_numbers": [1, 2, 3, 4],
            }
        },
    },
    {
        "name": "dates-multicity-transition",
        "tags": ["date_consistency", "city-transition"],
        "query": "Derive each city from contiguous multi-city stays.",
        "scenario": "dates_transition",
        "expected": {
            "equals": {
                "status": "completed",
                "cities": ["paris", "paris", "lyon", "lyon"],
                "scheduled_source_ids.2": ["activities:paris-stop"],
                "scheduled_source_ids.3": ["activities:lyon-stop"],
            },
            "contains": {"missing_constraints": ["day_3_intercity_transfer_time"]},
        },
    },
    {
        "name": "dates-final-exit-city",
        "tags": ["date_consistency", "exit-city"],
        "query": "Use the skeleton exit city on the final day of a return-gateway trip.",
        "scenario": "dates_exit_city",
        "expected": {
            "equals": {
                "status": "completed",
                "cities": ["paris", "paris", "lyon", "paris", "paris"],
                "exit_city": "paris",
            }
        },
    },
    {
        "name": "dates-ignore-draft-injection",
        "tags": ["date_consistency", "immutable-calendar"],
        "query": "Ignore dates and cities injected into a draft and compile the skeleton calendar.",
        "scenario": "dates_injected_draft",
        "expected": {
            "equals": {
                "status": "completed",
                "dates": [
                    "2026-09-01",
                    "2026-09-02",
                    "2026-09-03",
                    "2026-09-04",
                ],
                "cities": ["paris", "paris", "paris", "paris"],
            },
            "excludes": {"dates": ["2099-01-01"], "cities": ["atlantis"]},
        },
    },
    {
        "name": "feasibility-default-duration-buffer",
        "tags": ["feasibility", "timing"],
        "query": "Schedule a museum with measured transit, a handling buffer, and default duration.",
        "scenario": "feasibility_defaults",
        "expected": {
            "equals": {
                "status": "completed",
                "day_feasibility.2": "verified",
                "scheduled_starts.2": ["09:26"],
                "scheduled_ends.2": ["11:26"],
                "durations.2": [120],
                "duration_bases.2": ["configured_estimate"],
            }
        },
    },
    {
        "name": "feasibility-family-rest",
        "tags": ["feasibility", "family"],
        "query": "Add the configured rest after two stops for a family.",
        "scenario": "feasibility_family_rest",
        "expected": {
            "equals": {
                "status": "completed",
                "scheduled_starts.2": ["09:15", "11:00", "13:15"],
            },
            "contains": {
                "assumptions.2": [
                    "A 30-minute rest break follows every two stops for this party."
                ]
            },
        },
    },
    {
        "name": "feasibility-closed-unscheduled",
        "tags": ["feasibility", "opening-hours"],
        "query": "Move a closed selected stop out of the timed schedule.",
        "scenario": "feasibility_closed",
        "expected": {
            "equals": {
                "status": "completed",
                "day_feasibility.2": "infeasible",
                "scheduled_source_ids.2": ["activities:open-park"],
                "unscheduled_source_ids.2": ["activities:closed-museum"],
            }
        },
    },
    {
        "name": "feasibility-partial-and-overflow",
        "tags": ["feasibility", "partial-degradation", "overflow"],
        "query": "Degrade missing route/hours honestly and unschedule a day-window overflow.",
        "scenario": "feasibility_partial_overflow",
        "expected": {
            "equals": {
                "status": "completed",
                "day_feasibility.2": "needs_review",
                "scheduled_starts.2": [""],
                "day_feasibility.3": "infeasible",
                "unscheduled_source_ids.3": ["activities:long-5"],
            },
            "contains": {
                "missing_constraints": [
                    "route_plan",
                    "opening_hours:activities:unknown-hours",
                ]
            },
        },
    },
    {
        "name": "hallucination-unknown-source-id",
        "tags": ["hallucination_resistance", "unknown-id"],
        "query": "Reject a place source ID that is absent from the evidence catalog.",
        "scenario": "hallucination_unknown_id",
        "expected": {
            "equals": {"status": "rejected"},
            "contains": {"error": ["unknown place source ID"]},
        },
    },
    {
        "name": "hallucination-duplicate-source-id",
        "tags": ["hallucination_resistance", "duplicate-id"],
        "query": "Reject the same selected source ID assigned to two days.",
        "scenario": "hallucination_duplicate_id",
        "expected": {
            "equals": {"status": "rejected"},
            "contains": {"error": ["duplicate selected stop"]},
        },
    },
    {
        "name": "hallucination-wrong-city-source",
        "tags": ["hallucination_resistance", "wrong-city"],
        "query": "Reject a Lyon place assigned to a Paris day.",
        "scenario": "hallucination_wrong_city",
        "expected": {
            "equals": {"status": "rejected"},
            "contains": {"error": ["belongs to lyon"]},
        },
    },
    {
        "name": "hallucination-unselected-route-stop",
        "tags": ["hallucination_resistance", "route-boundary"],
        "query": "Reject a route that introduces an unselected stop.",
        "scenario": "hallucination_unselected_route",
        "expected": {
            "equals": {"status": "rejected"},
            "contains": {
                "error": ["route references stops outside the selected draft"]
            },
        },
    },
]
