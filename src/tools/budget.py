"""Budget calculator tool — pure Python, no API calls.

Computes an itemized trip budget estimate using regional daily baselines
and travel style multipliers. This gives the agent a quick budget framework
even before flight/hotel prices come back from APIs.
"""

from langchain_core.tools import tool

# Daily baselines per person in USD (mid-range)
_REGION_BASELINES: dict[str, dict[str, float]] = {
    "east asia": {
        "meals": 40, "transport": 15, "activities": 20, "misc": 10
    },
    "southeast asia": {
        "meals": 20, "transport": 8, "activities": 12, "misc": 8
    },
    "western europe": {
        "meals": 55, "transport": 20, "activities": 25, "misc": 15
    },
    "eastern europe": {
        "meals": 30, "transport": 10, "activities": 15, "misc": 8
    },
    "north america": {
        "meals": 50, "transport": 25, "activities": 30, "misc": 15
    },
    "south america": {
        "meals": 25, "transport": 10, "activities": 15, "misc": 8
    },
    "middle east": {
        "meals": 40, "transport": 20, "activities": 20, "misc": 12
    },
    "oceania": {
        "meals": 50, "transport": 22, "activities": 25, "misc": 15
    },
    "africa": {
        "meals": 25, "transport": 15, "activities": 20, "misc": 10
    },
}

_STYLE_MULTIPLIERS: dict[str, float] = {
    "budget": 0.6,
    "mid-range": 1.0,
    "luxury": 2.0,
}


@tool
def calculate_budget(
    destination_region: str,
    travel_style: str = "mid-range",
    duration_days: int = 7,
    num_travelers: int = 1,
    flight_cost: float = 0,
    hotel_cost: float = 0,
) -> str:
    """Calculate an estimated trip budget with itemized breakdown.
    Use this AFTER getting flight and hotel prices for a complete picture,
    or BEFORE to give the traveler a quick ballpark estimate.

    Args:
        destination_region: One of: east asia, southeast asia, western europe,
            eastern europe, north america, south america, middle east, oceania, africa
        travel_style: One of: budget, mid-range, luxury
        duration_days: Number of days for the trip
        num_travelers: Number of travelers
        flight_cost: Total flight cost for ALL travelers (0 if unknown)
        hotel_cost: Total hotel cost for the full stay (0 if unknown)
    """
    region_key = destination_region.strip().lower()
    style_key = travel_style.strip().lower()

    baseline = _REGION_BASELINES.get(region_key)
    if not baseline:
        available = ", ".join(sorted(_REGION_BASELINES.keys()))
        return (
            f"Unknown region '{destination_region}'. "
            f"Available regions: {available}"
        )

    multiplier = _STYLE_MULTIPLIERS.get(style_key, 1.0)

    # Calculate daily costs per person, then total
    daily_meals = baseline["meals"] * multiplier
    daily_transport = baseline["transport"] * multiplier
    daily_activities = baseline["activities"] * multiplier
    daily_misc = baseline["misc"] * multiplier

    total_meals = daily_meals * duration_days * num_travelers
    total_transport = daily_transport * duration_days * num_travelers
    total_activities = daily_activities * duration_days * num_travelers
    total_misc = daily_misc * duration_days * num_travelers

    grand_total = (
        flight_cost + hotel_cost + total_meals
        + total_transport + total_activities + total_misc
    )

    lines = [
        f"Budget Estimate — {destination_region.title()} "
        f"({travel_style.title()} style)",
        f"{duration_days} days · {num_travelers} traveler(s)\n",
        "Category breakdown:",
        f"  ✈️  Flights:      ${flight_cost:>10,.2f}"
        f"{'  (not yet searched)' if flight_cost == 0 else ''}",
        f"  🏨 Hotels:       ${hotel_cost:>10,.2f}"
        f"{'  (not yet searched)' if hotel_cost == 0 else ''}",
        f"  🍱 Meals:        ${total_meals:>10,.2f}"
        f"  (${daily_meals:.0f}/person/day)",
        f"  🚅 Transport:    ${total_transport:>10,.2f}"
        f"  (${daily_transport:.0f}/person/day)",
        f"  🎟️  Activities:   ${total_activities:>10,.2f}"
        f"  (${daily_activities:.0f}/person/day)",
        f"  🛍️  Misc:         ${total_misc:>10,.2f}"
        f"  (${daily_misc:.0f}/person/day)",
        f"  {'─' * 40}",
        f"  💰 TOTAL:        ${grand_total:>10,.2f}",
    ]

    if flight_cost == 0 or hotel_cost == 0:
        lines.append(
            "\n⚠️  Note: Flight and/or hotel costs are $0 — search for "
            "flights and hotels first for an accurate total."
        )

    return "\n".join(lines)
