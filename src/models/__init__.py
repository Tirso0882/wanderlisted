"""`Pydantic` data models used as structured output schemas.

BudgetBreakdown — returned by BudgetAgent via ``with_structured_output()``.
TripHandbook — top-level handbook model assembled by ItineraryAgent.
"""

from pydantic import BaseModel, Field


class BudgetBreakdown(BaseModel):
    """Flat budget breakdown produced by BudgetAgent.

    Used as a ``with_structured_output`` schema so the LLM returns
    machine-readable cost data rather than free-text.
    """

    flights: float = Field(default=0, description="Total flight costs in USD")
    accommodation: float = Field(default=0, description="Total accommodation costs in USD")
    transport: float = Field(default=0, description="Local transport costs in USD")
    meals: float = Field(default=0, description="Total meal costs in USD")
    activities: float = Field(default=0, description="Activity/attraction costs in USD")
    misc: float = Field(default=0, description="Miscellaneous costs (tips, SIM, contingency) in USD")
    total: float = Field(default=0, description="Grand total in USD")
    per_person: float = Field(default=0, description="Per-person cost in USD")
    currency: str = Field(default="USD", description="Currency code for all amounts")
    summary: str = Field(default="", description="Brief text summary of the budget")


from src.models.itinerary import (  # noqa: E402
    DayPlan,
    DayWeather,
    FlightOption,
    FlightSegment,
    HotelOption,
    PackingItem,
    PlaceCard,
    SafetyInfo,
    CultureGuide,
    TimeBlock,
    TransitStep,
    TripHandbook,
)
