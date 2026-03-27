"""`Pydantic` data models for structured itinerary output."""

from pydantic import BaseModel, Field


class Flight(BaseModel):
    airline: str
    flight_number: str = ""
    origin: str = Field(description="Origin IATA code")
    destination: str = Field(description="Destination IATA code")
    departure_time: str = ""
    arrival_time: str = ""
    duration: str = ""
    price: float
    currency: str = "USD"
    stops: int = 0


class Hotel(BaseModel):
    name: str
    stars: int = 0
    price_per_night: float
    total_price: float
    currency: str = "USD"
    address: str = ""
    amenities: list[str] = []


class Activity(BaseModel):
    name: str
    description: str = ""
    duration_hours: float = 0
    price: float = 0
    currency: str = "USD"
    category: str = ""


class MealBudget(BaseModel):
    breakfast: float = 0
    lunch: float = 0
    dinner: float = 0
    currency: str = "USD"


class DayPlan(BaseModel):
    day: int
    date: str = ""
    city: str = ""
    activities: list[Activity] = []
    meals_budget: MealBudget = MealBudget()
    transport_notes: str = ""
    notes: str = ""


class BudgetBreakdown(BaseModel):
    flights: float = 0
    accommodation: float = 0
    transport: float = 0
    meals: float = 0
    activities: float = 0
    misc: float = 0
    total: float = 0
    currency: str = "USD"


class Itinerary(BaseModel):
    destination: str
    origin: str = ""
    duration_days: int
    num_travelers: int = 1
    travel_style: str = "mid-range"
    outbound_flight: Flight | None = None
    return_flight: Flight | None = None
    hotels: list[Hotel] = []
    days: list[DayPlan] = []
    budget: BudgetBreakdown = BudgetBreakdown()
    safety_notes: str = ""
    weather_summary: str = ""
