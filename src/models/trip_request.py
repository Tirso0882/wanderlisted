"""Typed conversational request contract for travel planning."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
import hashlib
import json
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.enums import TransitMode
from src.models.pricing import KnownTripCost


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
    TRAVEL_READINESS = "travel_readiness"
    RESTAURANTS = "restaurants"
    ACTIVITIES = "activities"
    TRANSPORTATION = "transportation"
    BUDGET = "budget"
    ITINERARY = "itinerary"


class ReadinessTopic(StrEnum):
    """Focused, non-commercial destination-readiness topics."""

    SAFETY = "safety"
    ENTRY = "entry"
    HEALTH = "health"
    WEATHER = "weather"
    CULTURE = "culture"
    PRACTICAL = "practical"
    PACKING = "packing"


class ServiceScopeOffer(BaseModel):
    """Pending confirmation of applicable services before external work starts."""

    selected_capabilities: list[RequestedCapability] = Field(default_factory=list)
    offered_capabilities: list[RequestedCapability] = Field(default_factory=list)
    request_fingerprint: str = Field(min_length=1)


class ServiceScopeDecisionAction(StrEnum):
    INCLUDE_ALL = "include_all"
    INCLUDE_SELECTED = "include_selected"
    SELECTED_ONLY = "selected_only"


class ServiceScopeDecision(BaseModel):
    """Traveler response to one fingerprinted service-scope offer."""

    action: ServiceScopeDecisionAction
    selected_capabilities: list[RequestedCapability] = Field(default_factory=list)
    request_fingerprint: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_selected_action(self) -> ServiceScopeDecision:
        if (
            self.action == ServiceScopeDecisionAction.INCLUDE_SELECTED
            and not self.selected_capabilities
        ):
            raise ValueError("include_selected requires at least one capability")
        if (
            self.action != ServiceScopeDecisionAction.INCLUDE_SELECTED
            and self.selected_capabilities
        ):
            raise ValueError("selected_capabilities is only valid for include_selected")
        return self


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
    passport_country: str = ""
    origin_city: str = ""
    origin_airport: str = ""
    destinations: list[str] = Field(default_factory=list)
    route_goal: str = ""
    route_waypoints: list[str] = Field(default_factory=list)
    overnight_cities: list[str] = Field(default_factory=list)
    route_scope_confirmed: bool = False
    route_scope_delegated: bool = False
    requested_capabilities: list[RequestedCapability] = Field(default_factory=list)
    declined_capabilities: list[RequestedCapability] = Field(default_factory=list)
    capability_scope_confirmed: bool = False
    capability_scope_exclusive: bool = False
    readiness_topics: list[ReadinessTopic] = Field(default_factory=list)
    primary_transport_mode: TransitMode | None = None
    date_window: DateWindow = Field(default_factory=DateWindow)
    travelers: TravelerParty = Field(default_factory=TravelerParty)
    travel_style: str = ""
    budget_amount: float | None = Field(default=None, ge=0)
    budget_currency: str = "USD"
    known_costs: list[KnownTripCost] = Field(default_factory=list)
    contingency_percent: float | None = Field(default=None, ge=0, le=100)
    interests: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)
    minimum_beach_days: int = Field(default=0, ge=0, le=30)

    @field_validator("locale", mode="before")
    @classmethod
    def _normalise_locale(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            return "en"
        return value.strip().lower().split("-")[0][:2]

    @field_validator(
        "destinations", "route_waypoints", "overnight_cities", mode="before"
    )
    @classmethod
    def _normalise_locations(cls, values: list[str]) -> list[str]:
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

    @model_validator(mode="after")
    def _promote_confirmed_route_cities(self) -> TripRequest:
        broad_markers = re.compile(
            r"(?:^|\s)(?:sea|coast|coastline|border|morze|wybrzeże|granica)(?:$|\s)",
            re.IGNORECASE,
        )
        exact_cities: list[str] = []
        broad_locations: list[str] = []
        for destination in self.destinations:
            normalised = destination.replace("-", " ")
            if broad_markers.search(normalised):
                broad_locations.append(destination)
            else:
                exact_cities.append(destination)
        if broad_locations:
            self.destinations = exact_cities
            if not self.route_goal:
                self.route_goal = ", ".join(broad_locations)
            self.route_scope_confirmed = False
            self.route_scope_delegated = False
        if self.route_scope_confirmed:
            self.route_scope_delegated = False
        elif self.route_scope_delegated and not self.overnight_cities:
            self.route_scope_delegated = False
        if self.route_scope_resolved and self.overnight_cities:
            self.destinations = list(
                dict.fromkeys([*self.destinations, *self.overnight_cities])
            )
        return self

    @property
    def route_scope_resolved(self) -> bool:
        """Whether exact route cities are confirmed or explicitly delegated."""
        return self.route_scope_confirmed or (
            self.route_scope_delegated and bool(self.overnight_cities)
        )


class TripRequestPatch(BaseModel):
    """Only values explicitly supplied or safely inferred from one user turn."""

    scope: RequestScope | None = None
    locale: str | None = None
    origin_country: str | None = None
    passport_country: str | None = None
    origin_city: str | None = None
    origin_airport: str | None = None
    destinations: list[str] | None = None
    route_goal: str | None = None
    route_waypoints: list[str] | None = None
    overnight_cities: list[str] | None = None
    route_scope_confirmed: bool | None = None
    route_scope_delegated: bool | None = None
    requested_capabilities: list[RequestedCapability] | None = None
    declined_capabilities: list[RequestedCapability] | None = None
    capability_scope_confirmed: bool | None = None
    capability_scope_exclusive: bool | None = None
    readiness_topics: list[ReadinessTopic] | None = None
    primary_transport_mode: TransitMode | None = None
    date_window: DateWindowPatch | None = None
    travelers: TravelerPartyPatch | None = None
    travel_style: str | None = None
    budget_amount: float | None = Field(default=None, ge=0)
    budget_currency: str | None = None
    known_costs: list[KnownTripCost] | None = None
    contingency_percent: float | None = Field(default=None, ge=0, le=100)
    interests: list[str] | None = None
    dietary_restrictions: list[str] | None = None
    accessibility_needs: list[str] | None = None
    minimum_beach_days: int | None = Field(default=None, ge=0, le=30)


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

    route_fields = {"destinations", "route_goal", "route_waypoints", "overnight_cities"}
    route_resolution_fields = {"route_scope_confirmed", "route_scope_delegated"}
    if route_fields & patch_data.keys() and not (
        route_resolution_fields & patch_data.keys()
    ):
        merged["route_scope_confirmed"] = False
        merged["route_scope_delegated"] = False

    requested_patch = patch_data.pop("requested_capabilities", None)
    declined_patch = patch_data.pop("declined_capabilities", None)
    confirmation_supplied = "capability_scope_confirmed" in patch_data

    requested = list(base.requested_capabilities)
    declined = list(base.declined_capabilities)
    if requested_patch is not None:
        requested = list(dict.fromkeys([*requested, *requested_patch]))
        declined = [item for item in declined if item not in requested_patch]
    if declined_patch is not None:
        declined = list(dict.fromkeys([*declined, *declined_patch]))
        requested = [item for item in requested if item not in declined_patch]
    if requested_patch is not None or declined_patch is not None:
        merged["requested_capabilities"] = requested
        merged["declined_capabilities"] = declined
        if not confirmation_supplied:
            merged["capability_scope_confirmed"] = False

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


def service_scope_fingerprint(request: TripRequest) -> str:
    """Fingerprint the request revision that owns a pending service offer."""
    payload = request.model_dump(mode="json", exclude={"capability_scope_confirmed"})
    canonical = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
