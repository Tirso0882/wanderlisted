"""`Pydantic` data models used as structured output schemas.

BudgetBreakdown — returned by BudgetAgent via ``with_structured_output()``.
TripHandbook — top-level handbook model assembled by ItineraryAgent.
"""

from pydantic import BaseModel, Field, field_validator, model_validator


class BudgetBreakdown(BaseModel):
    """Flat budget breakdown produced by BudgetAgent.

    Used as a ``with_structured_output`` schema so the LLM returns
    machine-readable cost data rather than free-text.
    """

    flights: float = Field(default=0, description="Total flight costs in USD")
    accommodation: float = Field(
        default=0, description="Total accommodation costs in USD"
    )
    transport: float = Field(default=0, description="Local transport costs in USD")
    meals: float = Field(default=0, description="Total meal costs in USD")
    activities: float = Field(default=0, description="Activity/attraction costs in USD")
    misc: float = Field(
        default=0, description="Miscellaneous costs (tips, SIM, contingency) in USD"
    )
    total: float = Field(default=0, description="Grand total in USD")
    per_person: float = Field(default=0, description="Per-person cost in USD")
    target_budget: float = Field(
        default=0,
        description="The user's stated target/maximum budget in USD. 0 if not specified.",
    )
    currency: str = Field(default="USD", description="Currency code for all amounts")
    summary: str = Field(default="", description="Brief text summary of the budget")

    @field_validator(
        "flights",
        "accommodation",
        "transport",
        "meals",
        "activities",
        "misc",
        "total",
        "per_person",
        "target_budget",
        mode="after",
    )
    @classmethod
    def _non_negative(cls, v: float) -> float:
        return max(0.0, v)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, v: str) -> str:
        return v.strip().upper()[:3] if isinstance(v, str) else v

    @model_validator(mode="after")
    def _auto_total(self) -> "BudgetBreakdown":
        """If total is 0 but components exist, compute the sum."""
        components = (
            self.flights
            + self.accommodation
            + self.transport
            + self.meals
            + self.activities
            + self.misc
        )
        if self.total == 0 and components > 0:
            self.total = components
        return self


from src.models.enums import (  # noqa: E402
    AdvisoryLevel,
    CabinClass,
    DayPeriod,
    GroupType,
    PackingCategory,
    Season,
    TransitMode,
    TravelStyle,
)
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
