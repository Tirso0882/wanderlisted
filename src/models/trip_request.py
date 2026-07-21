"""Typed conversational request contract for travel planning."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class RequestScope(StrEnum):
    """How much of the travel workflow the user requested."""

    UNKNOWN = "unknown"
    FOCUSED = "focused"
    FULL_ITINERARY = "full_itinerary"
    REFINEMENT = "refinement"


class RequestedCapability(StrEnum):
    """Stable capability identifiers independent of agent class names."""

    FLIGHTS = "flights"
    HOTELS = "hotels"
    DESTINATION = "destination"
    RESTAURANTS = "restaurants"
    ACTIVITIES = "activities"
    TRANSPORTATION = "transportation"
    BUDGET = "budget"
    ITINERARY = "itinerary"


class DateWindow(BaseModel):
    """Exact dates or a flexible window in which a trip must fit."""

    exact_start: date | None = None
    exact_end: date | None = None
    earliest_start: date | None = None
    latest_end: date | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)
    flexible: bool = False

    @model_validator(mode="after")
    def _validate_order(self) -> DateWindow:
        if self.exact_start and self.exact_end and self.exact_end < self.exact_start:
            raise ValueError("exact_end must be on or after exact_start")
        if (
            self.earliest_start
            and self.latest_end
            and self.latest_end < self.earliest_start
        ):
            raise ValueError("latest_end must be on or after earliest_start")
        return self

    @property
    def is_usable(self) -> bool:
        """Whether downstream planning can choose or use concrete trip dates."""
        exact = bool(self.exact_start and (self.exact_end or self.duration_days))
        flexible = bool(self.earliest_start and self.latest_end and self.duration_days)
        return exact or flexible

    @property
    def has_exact_stay(self) -> bool:
        return bool(self.exact_start and self.exact_end)


class DateWindowPatch(BaseModel):
    """Partial date update extracted from one conversation turn."""

    exact_start: date | None = None
    exact_end: date | None = None
    earliest_start: date | None = None
    latest_end: date | None = None
    duration_days: int | None = Field(default=None, ge=1, le=365)
    flexible: bool | None = None


class TravelerParty(BaseModel):
    """Occupancy and passenger information shared by inventory providers."""

    adults: int | None = Field(default=None, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=8)
    child_ages: list[int] = Field(default_factory=list)
    infants: int = Field(default=0, ge=0, le=8)
    rooms: int = Field(default=1, ge=1, le=8)

    @field_validator("child_ages")
    @classmethod
    def _validate_child_ages(cls, ages: list[int]) -> list[int]:
        if any(age < 0 or age > 17 for age in ages):
            raise ValueError("child ages must be between 0 and 17")
        return ages


class TravelerPartyPatch(BaseModel):
    """Partial traveler update extracted from one conversation turn."""

    adults: int | None = Field(default=None, ge=1, le=9)
    children: int | None = Field(default=None, ge=0, le=8)
    child_ages: list[int] | None = None
    infants: int | None = Field(default=None, ge=0, le=8)
    rooms: int | None = Field(default=None, ge=1, le=8)


class TripRequest(BaseModel):
    """Canonical, language-independent request accumulated across turns."""

    scope: RequestScope = RequestScope.UNKNOWN
    locale: str = "en"
    origin_country: str = ""
    origin_city: str = ""
    origin_airport: str = ""
    destinations: list[str] = Field(default_factory=list)
    requested_capabilities: list[RequestedCapability] = Field(default_factory=list)
    date_window: DateWindow = Field(default_factory=DateWindow)
    travelers: TravelerParty = Field(default_factory=TravelerParty)
    travel_style: str = ""
    budget_amount: float | None = Field(default=None, ge=0)
    budget_currency: str = "USD"
    interests: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)

    @field_validator("locale", mode="before")
    @classmethod
    def _normalise_locale(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            return "en"
        return value.strip().lower().split("-")[0][:2]

    @field_validator("destinations", mode="before")
    @classmethod
    def _normalise_destinations(cls, values: list[str]) -> list[str]:
        if not isinstance(values, list):
            return values
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalised = value.strip().lower()
            if normalised and normalised not in seen:
                seen.add(normalised)
                result.append(normalised)
        return result

    @field_validator("budget_currency", mode="before")
    @classmethod
    def _normalise_currency(cls, value: str) -> str:
        return value.strip().upper()[:3] if isinstance(value, str) else value


class TripRequestPatch(BaseModel):
    """Only values explicitly supplied or safely inferred from one user turn."""

    scope: RequestScope | None = None
    locale: str | None = None
    origin_country: str | None = None
    origin_city: str | None = None
    origin_airport: str | None = None
    destinations: list[str] | None = None
    requested_capabilities: list[RequestedCapability] | None = None
    date_window: DateWindowPatch | None = None
    travelers: TravelerPartyPatch | None = None
    travel_style: str | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    budget_currency: str | None = None
    interests: list[str] | None = None
    dietary_restrictions: list[str] | None = None
    accessibility_needs: list[str] | None = None


def merge_trip_request(
    current: TripRequest | dict | None,
    patch: TripRequestPatch | dict,
) -> TripRequest:
    """Merge one explicit turn patch without erasing prior confirmed values."""
    base = (
        current
        if isinstance(current, TripRequest)
        else TripRequest.model_validate(current or {})
    )
    update = (
        patch
        if isinstance(patch, TripRequestPatch)
        else TripRequestPatch.model_validate(patch)
    )
    merged = base.model_dump()
    patch_data = update.model_dump(exclude_none=True)

    date_patch = patch_data.pop("date_window", None)
    if date_patch is not None:
        merged["date_window"] = {
            **base.date_window.model_dump(),
            **date_patch,
        }

    party_patch = patch_data.pop("travelers", None)
    if party_patch is not None:
        merged["travelers"] = {
            **base.travelers.model_dump(),
            **party_patch,
        }

    merged.update(patch_data)
    return TripRequest.model_validate(merged)
