"""Shared, auditable money and price-evidence contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, WithJsonSchema, field_validator


# Pydantic normally publishes Decimal as number-or-string and adds a regex with
# negative lookahead to the string branch. Azure/OpenAI tool schemas reject that
# lookaround. These annotations change only the validation JSON schema; runtime
# values remain Decimal and retain their deterministic numeric constraints.
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=0),
    WithJsonSchema({"type": "number", "minimum": 0}, mode="validation"),
]
PositiveDecimal = Annotated[
    Decimal,
    Field(gt=0),
    WithJsonSchema({"type": "number", "exclusiveMinimum": 0}, mode="validation"),
]


class BudgetCategory(StrEnum):
    FLIGHTS = "flights"
    ACCOMMODATION = "accommodation"
    TRANSPORT = "transport"
    MEALS = "meals"
    ACTIVITIES = "activities"
    MISC = "misc"


class PriceScope(StrEnum):
    TOTAL = "total"
    PER_PERSON = "per_person"
    PER_NIGHT = "per_night"
    PER_PERSON_DAY = "per_person_day"


class PriceBasis(StrEnum):
    QUOTED = "quoted"
    USER_SUPPLIED = "user_supplied"
    REGIONAL_ESTIMATE = "regional_estimate"
    CONTINGENCY = "contingency"


class SelectionStatus(StrEnum):
    CANDIDATE = "candidate"
    SELECTED = "selected"
    USER_SUPPLIED = "user_supplied"


class Money(BaseModel):
    """Non-negative monetary amount in one ISO-4217-like currency code."""

    amount: NonNegativeDecimal
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        normalised = value.strip().upper()
        if len(normalised) != 3 or not normalised.isalpha():
            raise ValueError("currency must be a three-letter alphabetic code")
        return normalised


class PriceEvidence(BaseModel):
    """A source-bound price that cannot silently become a selected cost."""

    category: BudgetCategory
    money: Money
    source_component: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    scope: PriceScope = PriceScope.TOTAL
    basis: PriceBasis = PriceBasis.QUOTED
    selection_status: SelectionStatus = SelectionStatus.CANDIDATE
    quantity: PositiveDecimal = Field(default_factory=lambda: Decimal("1"))
    observed_at: datetime | None = None
    evidence_text: str = ""


class NonNumericPriceEvidence(BaseModel):
    """Pricing-related provider signal that must never be treated as money."""

    source_component: str
    source_id: str = Field(min_length=1)
    category: BudgetCategory | None = None
    signal: str = Field(min_length=1)
    value: str = ""
    observed_at: datetime | None = None
    excluded_reason: str = "No numeric provider amount was supplied."


class KnownTripCost(BaseModel):
    """Cost explicitly provided by the traveler during intake."""

    category: BudgetCategory
    money: Money
    scope: PriceScope = PriceScope.TOTAL
    note: str = ""


class FlightPriceOption(BaseModel):
    offer_id: str = Field(min_length=1)
    money: Money
    origin: str = ""
    destination: str = ""
    departure_date: str = ""
    return_date: str = ""
    airline_name: str = ""
    observed_at: datetime | None = None


class FlightSearchPricing(BaseModel):
    options: list[FlightPriceOption] = Field(default_factory=list)


class HotelPriceOption(BaseModel):
    rate_key: str = Field(min_length=1)
    hotel_name: str
    money: Money
    room_name: str = ""
    rate_type: str = ""
    check_in: str = ""
    check_out: str = ""
    observed_at: datetime | None = None


class HotelSearchPricing(BaseModel):
    city_code: str
    options: list[HotelPriceOption] = Field(default_factory=list)
