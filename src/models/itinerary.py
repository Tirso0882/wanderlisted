"""Structured output models for the travel handbook.

Every agent returns one of these models via ``with_structured_output()``.
The assembler combines them into a single ``TripHandbook`` that feeds
the Jinja2 template renderer.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models.enums import (
    AdvisoryLevel,
    CabinClass,
    DayPeriod,
    GroupType,
    PackingCategory,
    Season,
    TransitMode,
    TravelStyle,
)


# ── Flights ──────────────────────────────────────────────────────────────


class FlightSegment(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    carrier: str = ""
    flight_number: str = ""
    departure_airport: str = ""
    arrival_airport: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    duration_minutes: int = 0
    cabin_class: CabinClass = CabinClass.ECONOMY
    stops: int = 0
    origin_country: str = ""
    destination_country: str = ""

    @field_validator("departure_airport", "arrival_airport", mode="before")
    @classmethod
    def _normalise_iata(cls, v: str) -> str:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("duration_minutes", "stops", mode="after")
    @classmethod
    def _non_negative_int(cls, v: int) -> int:
        return max(0, v)


class FlightOption(BaseModel):
    outbound: list[FlightSegment] = Field(default_factory=list)
    inbound: list[FlightSegment] = Field(default_factory=list)
    total_price_usd: float = 0
    currency: str = "USD"
    booking_url: str = ""
    skyscanner_url: str = ""
    google_flights_url: str = ""

    @field_validator("total_price_usd", mode="after")
    @classmethod
    def _non_negative_price(cls, v: float) -> float:
        return max(0.0, v)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, v: str) -> str:
        return v.strip().upper()[:3] if isinstance(v, str) else v


# ── Hotels ───────────────────────────────────────────────────────────────


class HotelOption(BaseModel):
    name: str = ""
    star_rating: int = Field(default=0, ge=0, le=5)
    neighbourhood: str = ""
    price_per_night_usd: float = 0
    total_price_usd: float = 0
    room_type: str = ""
    bed_type: str = ""
    check_in: str = ""
    check_out: str = ""
    amenities: list[str] = Field(default_factory=list)
    cancellation_policy: str = ""
    booking_url: str = ""
    booking_com_url: str = ""
    google_hotels_url: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    photo_urls: list[str] = Field(default_factory=list)
    google_maps_url: str = ""
    website_url: str = ""
    description: str = ""
    distance_from_center_km: float = 0.0
    nearby_attractions: list[str] = Field(default_factory=list)
    map_embed_url: str = ""  # Maps Embed API place URL

    @field_validator("star_rating", mode="before")
    @classmethod
    def _clamp_stars(cls, v: int) -> int:
        if isinstance(v, (int, float)):
            return max(0, min(5, int(v)))
        return v

    @field_validator(
        "price_per_night_usd",
        "total_price_usd",
        "distance_from_center_km",
        mode="after",
    )
    @classmethod
    def _non_negative_float(cls, v: float) -> float:
        return max(0.0, v)


# ── Places (activities, restaurants, attractions) ────────────────────────


class PlaceCard(BaseModel):
    """Unified model for activities, restaurants, and attractions."""

    name: str = ""
    category: str = ""
    rating: float | None = None
    review_count: int = 0
    price_level: str = ""
    address: str = ""
    description: str = ""
    website_url: str = ""
    google_maps_url: str = ""
    photo_urls: list[str] = Field(default_factory=list)
    opening_hours: list[str] = Field(default_factory=list)
    latitude: float = 0.0
    longitude: float = 0.0
    estimated_cost_usd: float = 0.0
    estimated_duration_minutes: int = 60

    @field_validator("rating", mode="before")
    @classmethod
    def _clamp_rating(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return max(0.0, min(5.0, float(v)))
        return v

    @field_validator("estimated_cost_usd", mode="after")
    @classmethod
    def _non_negative_cost(cls, v: float) -> float:
        return max(0.0, v)

    @field_validator("estimated_duration_minutes", "review_count", mode="after")
    @classmethod
    def _non_negative_int(cls, v: int) -> int:
        return max(0, v)


# ── Transit ──────────────────────────────────────────────────────────────


class PlaceRef(BaseModel):
    """Stable reference to a selected hotel, activity, or restaurant."""

    name: str
    address: str = ""
    place_id: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    category: str = ""

    def route_location(self) -> str:
        """Return the most precise location accepted by Google Routes."""
        if self.latitude or self.longitude:
            return f"{self.latitude},{self.longitude}"
        return self.address or self.name


class DraftDay(BaseModel):
    """Selected places for one day before route computation."""

    model_config = ConfigDict(use_enum_values=True)

    day_number: int = Field(default=1, ge=1)
    date: str = ""
    city: str = ""
    start_location: PlaceRef
    end_location: PlaceRef | None = None
    stops: list[PlaceRef] = Field(default_factory=list)
    preferred_mode: TransitMode = TransitMode.TRANSIT


class DraftItinerary(BaseModel):
    """Exact hotel and stop selections that Transportation must route."""

    days: list[DraftDay] = Field(default_factory=list)
    selection_notes: list[str] = Field(default_factory=list)
    mobility_notes: list[str] = Field(default_factory=list)


class RouteLeg(BaseModel):
    """Measured route between two selected places."""

    model_config = ConfigDict(use_enum_values=True)

    from_place: str
    to_place: str
    mode: TransitMode = TransitMode.TRANSIT
    distance_meters: int = Field(default=0, ge=0)
    duration_seconds: int = Field(default=0, ge=0)
    instructions: list[str] = Field(default_factory=list)


class DayRoute(BaseModel):
    """Computed route for one selected draft day."""

    model_config = ConfigDict(use_enum_values=True)

    day_number: int = Field(default=1, ge=1)
    mode: TransitMode = TransitMode.TRANSIT
    ordered_stops: list[PlaceRef] = Field(default_factory=list)
    legs: list[RouteLeg] = Field(default_factory=list)
    total_distance_meters: int = Field(default=0, ge=0)
    total_duration_seconds: int = Field(default=0, ge=0)
    warning: str = ""


class RoutePlan(BaseModel):
    """Transportation-owned route artifact consumed by budget and itinerary."""

    days: list[DayRoute] = Field(default_factory=list)
    mobility_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TransitStep(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    mode: TransitMode = TransitMode.WALK
    from_place: str = ""
    to_place: str = ""
    distance_text: str = ""
    duration_text: str = ""
    transit_line: str = ""
    instructions: str = ""
    booking_url: str = ""
    fare_estimate_usd: float = 0.0

    @field_validator("fare_estimate_usd", mode="after")
    @classmethod
    def _non_negative_fare(cls, v: float) -> float:
        return max(0.0, v)


# ── Weather ──────────────────────────────────────────────────────────────


class DayWeather(BaseModel):
    date: str = ""
    condition: str = ""
    emoji: str = "☀️"
    temp_low_c: float = 0
    temp_high_c: float = 0
    rain_probability_pct: int = Field(default=0, ge=0, le=100)
    packing_tip: str = ""

    @field_validator("rain_probability_pct", mode="before")
    @classmethod
    def _clamp_rain(cls, v: int) -> int:
        if isinstance(v, (int, float)):
            return max(0, min(100, int(v)))
        return v


# ── Day plan ─────────────────────────────────────────────────────────────


class TimeBlock(BaseModel):
    """A single block within a day (morning / afternoon / evening)."""

    model_config = ConfigDict(use_enum_values=True)

    period: DayPeriod = DayPeriod.MORNING
    activities: list[PlaceCard] = Field(default_factory=list)
    restaurant: PlaceCard | None = None
    transit: list[TransitStep] = Field(default_factory=list)
    subtotal_usd: float = 0.0

    @field_validator("subtotal_usd", mode="after")
    @classmethod
    def _non_negative_subtotal(cls, v: float) -> float:
        return max(0.0, v)


class DayPlan(BaseModel):
    day_number: int = 0
    date: str = ""
    city: str = ""
    weather: DayWeather | None = None
    time_blocks: list[TimeBlock] = Field(default_factory=list)
    cultural_tip: str = ""
    daily_cost_usd: float = 0.0
    walking_km: float = 0.0
    route_map_url: str = ""  # Maps Embed API directions URL for the day's route

    @field_validator("daily_cost_usd", "walking_km", mode="after")
    @classmethod
    def _non_negative_float(cls, v: float) -> float:
        return max(0.0, v)


# ── Safety ───────────────────────────────────────────────────────────────


_ADVISORY_NUM_MAP: dict[str, int] = {"green": 1, "yellow": 2, "orange": 3, "red": 4}


class SafetyInfo(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    advisory_level: AdvisoryLevel = AdvisoryLevel.GREEN
    advisory_level_num: int = Field(default=1, ge=1, le=4)
    advisory_summary: str = ""
    visa_requirements: str = ""
    health_requirements: list[str] = Field(default_factory=list)
    emergency_numbers: dict[str, str] = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)
    currency_name: str = ""
    currency_symbol: str = ""
    currency_code: str = ""
    timezones: list[str] = Field(default_factory=list)
    seasonal_risks: list[str] = Field(default_factory=list)
    natural_hazards: list[str] = Field(default_factory=list)
    safety_tips: list[str] = Field(default_factory=list)
    embassy_info: str = ""

    @field_validator("advisory_level_num", mode="before")
    @classmethod
    def _clamp_advisory_num(cls, v: int) -> int:
        if isinstance(v, (int, float)):
            return max(1, min(4, int(v)))
        return v

    @field_validator("currency_code", mode="before")
    @classmethod
    def _normalise_currency_code(cls, v: str) -> str:
        return v.strip().upper()[:3] if isinstance(v, str) else v

    @model_validator(mode="after")
    def _sync_advisory_level_num(self) -> SafetyInfo:
        """Keep advisory_level_num consistent with advisory_level."""
        expected = _ADVISORY_NUM_MAP.get(self.advisory_level, 1)
        if self.advisory_level_num != expected:
            self.advisory_level_num = expected
        return self


# ── Culture ──────────────────────────────────────────────────────────────


class CultureGuide(BaseModel):
    phrases: list[dict[str, str]] = Field(default_factory=list)
    etiquette_tips: list[str] = Field(default_factory=list)
    tipping_guide: str = ""
    dining_customs: list[str] = Field(default_factory=list)
    religious_customs: list[str] = Field(default_factory=list)
    dress_code_notes: list[str] = Field(default_factory=list)
    # Enhanced fields
    festivals: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{name, date, description}]
    food_specialties: list[str] = Field(default_factory=list)
    local_customs: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{context, custom, tip}]
    music_and_arts: list[str] = Field(default_factory=list)
    etiquette_cards: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{title, icon, items: str (newline-separated)}]


# ── Currency Exchange ────────────────────────────────────────────────────


class CurrencyExchangeLocation(BaseModel):
    name: str = ""
    address: str = ""
    google_maps_url: str = ""
    rating: float | None = None
    notes: str = ""  # e.g. "Better rates than airport", "Open 24h"


# ── Local Tips & Apps ────────────────────────────────────────────────────


class LocalTipsApps(BaseModel):
    must_have_apps: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{name, purpose, platform, url}]
    sim_card_info: str = ""
    wifi_info: str = ""
    transport_cards: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{name, cost, where_to_buy, notes}]
    power_adapter: str = ""
    useful_websites: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{name, url, description}]


# ── Emergency & Health ───────────────────────────────────────────────────


class EmergencyInfo(BaseModel):
    hospitals: list[PlaceCard] = Field(default_factory=list)
    pharmacies: list[PlaceCard] = Field(default_factory=list)
    insurance_notes: str = ""
    medical_phrases: list[dict[str, str]] = Field(
        default_factory=list
    )  # [{english, local, romanized}]
    vaccination_tips: list[str] = Field(default_factory=list)


# ── Packing ──────────────────────────────────────────────────────────────


class PackingItem(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    item: str = ""
    reason: str = ""
    category: PackingCategory = PackingCategory.CLOTHING
    essential: bool = True
    weather_context: str = ""  # e.g. "60% rain on Day 3"
    activity_context: str = ""  # e.g. "Temple visits on Day 2"


# ── Top-level handbook ───────────────────────────────────────────────────


class TripHandbook(BaseModel):
    """Complete structured output — the single source of truth for rendering."""

    # Header
    trip_title: str = ""
    traveller_names: list[str] = Field(default_factory=list)
    origin_city: str = ""
    destinations: list[str] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    total_budget_usd: float = 0
    travel_style: str = ""
    group_type: str = ""
    dietary_restrictions: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)

    @field_validator("travel_style", mode="before")
    @classmethod
    def _normalise_travel_style(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            return ""
        try:
            return TravelStyle(v).value
        except ValueError:
            return v.strip().lower()

    @field_validator("group_type", mode="before")
    @classmethod
    def _normalise_group_type(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            return ""
        try:
            return GroupType(v).value
        except ValueError:
            return v.strip().lower()

    # Route
    route_cities: list[str] = Field(default_factory=list)
    route_transport: list[str] = Field(default_factory=list)

    # Core content
    flights: list[FlightOption] = Field(default_factory=list)
    hotels: list[HotelOption] = Field(default_factory=list)
    days: list[DayPlan] = Field(default_factory=list)

    # Budget (reuses existing BudgetBreakdown fields inline)
    budget_flights: float = 0
    budget_accommodation: float = 0
    budget_transport: float = 0
    budget_meals: float = 0
    budget_activities: float = 0
    budget_misc: float = 0
    budget_total: float = 0
    budget_per_person: float = 0
    budget_summary: str = ""

    # Info sections
    safety: SafetyInfo = Field(default_factory=SafetyInfo)
    culture: CultureGuide = Field(default_factory=CultureGuide)
    packing: list[PackingItem] = Field(default_factory=list)

    # Extended sections (populated when agents run enhanced searches)
    currency_exchange_locations: list[CurrencyExchangeLocation] = Field(
        default_factory=list
    )
    local_tips: LocalTipsApps = Field(default_factory=LocalTipsApps)
    emergency_info: EmergencyInfo = Field(default_factory=EmergencyInfo)

    # Metadata
    exchange_rate: float = 0
    local_currency_code: str = ""
    theme_accent_color: str = "#e41e3f"
    hero_gradient_from: str = "#e41e3f"
    hero_gradient_to: str = "#b01028"
    hero_emoji: str = "✈️"
    season: str = ""  # spring / summer / autumn / winter
    generated_at: str = ""
    langsmith_run_id: str = ""

    @field_validator("season", mode="before")
    @classmethod
    def _normalise_season(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            return ""
        try:
            return Season(v).value
        except ValueError:
            return v.strip().lower()

    @field_validator(
        "total_budget_usd",
        "budget_flights",
        "budget_accommodation",
        "budget_transport",
        "budget_meals",
        "budget_activities",
        "budget_misc",
        "budget_total",
        "budget_per_person",
        "exchange_rate",
        mode="after",
    )
    @classmethod
    def _non_negative_float(cls, v: float) -> float:
        return max(0.0, v)

    @model_validator(mode="after")
    def _auto_budget_total(self) -> TripHandbook:
        """If budget_total is 0 but components exist, compute the sum."""
        components = (
            self.budget_flights
            + self.budget_accommodation
            + self.budget_transport
            + self.budget_meals
            + self.budget_activities
            + self.budget_misc
        )
        if self.budget_total == 0 and components > 0:
            self.budget_total = components
        return self
