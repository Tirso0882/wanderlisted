"""Structured output models for the travel handbook.

Every agent returns one of these models via ``with_structured_output()``.
The assembler combines them into a single ``TripHandbook`` that feeds
the Jinja2 template renderer.
"""

from __future__ import annotations


from pydantic import BaseModel, Field


# ── Flights ──────────────────────────────────────────────────────────────


class FlightSegment(BaseModel):
    carrier: str = ""
    flight_number: str = ""
    departure_airport: str = ""
    arrival_airport: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    duration_minutes: int = 0
    cabin_class: str = "economy"
    stops: int = 0
    origin_country: str = ""
    destination_country: str = ""


class FlightOption(BaseModel):
    outbound: list[FlightSegment] = Field(default_factory=list)
    inbound: list[FlightSegment] = Field(default_factory=list)
    total_price_usd: float = 0
    currency: str = "USD"
    booking_url: str = ""
    skyscanner_url: str = ""
    google_flights_url: str = ""


# ── Hotels ───────────────────────────────────────────────────────────────


class HotelOption(BaseModel):
    name: str = ""
    star_rating: int = 0
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


# ── Transit ──────────────────────────────────────────────────────────────


class TransitStep(BaseModel):
    mode: str = ""  # "walk", "transit", "drive", "train", "bus", "ferry"
    from_place: str = ""
    to_place: str = ""
    distance_text: str = ""
    duration_text: str = ""
    transit_line: str = ""
    instructions: str = ""
    booking_url: str = ""
    fare_estimate_usd: float = 0.0


# ── Weather ──────────────────────────────────────────────────────────────


class DayWeather(BaseModel):
    date: str = ""
    condition: str = ""
    emoji: str = "☀️"
    temp_low_c: float = 0
    temp_high_c: float = 0
    rain_probability_pct: int = 0
    packing_tip: str = ""


# ── Day plan ─────────────────────────────────────────────────────────────


class TimeBlock(BaseModel):
    """A single block within a day (morning / afternoon / evening)."""

    period: str = ""  # "morning", "afternoon", "evening"
    activities: list[PlaceCard] = Field(default_factory=list)
    restaurant: PlaceCard | None = None
    transit: list[TransitStep] = Field(default_factory=list)
    subtotal_usd: float = 0.0


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


# ── Safety ───────────────────────────────────────────────────────────────


class SafetyInfo(BaseModel):
    advisory_level: str = "green"  # "green", "yellow", "orange", "red"
    advisory_level_num: int = 1  # 1-4
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
    item: str = ""
    reason: str = ""
    category: str = ""  # "clothing", "documents", "tech", "health", "money"
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
