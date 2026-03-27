"""Unit tests for Pydantic models — schema validation and defaults."""

from src.models import (
    Activity,
    BudgetBreakdown,
    DayPlan,
    Flight,
    Hotel,
    Itinerary,
    MealBudget,
)


class TestFlightModel:
    def test_minimal_flight(self):
        f = Flight(airline="NH", origin="SEA", destination="NRT", price=850.0)
        assert f.airline == "NH"
        assert f.currency == "USD"
        assert f.stops == 0

    def test_full_flight(self):
        f = Flight(
            airline="DL",
            flight_number="DL167",
            origin="JFK",
            destination="LHR",
            departure_time="2026-06-15T10:00",
            arrival_time="2026-06-15T22:30",
            duration="PT12H30M",
            price=1200.50,
            currency="USD",
            stops=1,
        )
        assert f.stops == 1
        assert f.price == 1200.50


class TestHotelModel:
    def test_minimal_hotel(self):
        h = Hotel(name="Park Hyatt Tokyo", price_per_night=350.0, total_price=1750.0)
        assert h.stars == 0
        assert h.currency == "USD"


class TestActivityModel:
    def test_defaults(self):
        a = Activity(name="Senso-ji Temple")
        assert a.price == 0
        assert a.category == ""


class TestDayPlanModel:
    def test_day_with_activities(self):
        d = DayPlan(
            day=1,
            date="2026-06-15",
            city="Tokyo",
            activities=[
                Activity(name="Meiji Shrine", category="sightseeing"),
                Activity(name="Shibuya Crossing", category="sightseeing"),
            ],
        )
        assert len(d.activities) == 2
        assert d.meals_budget.breakfast == 0


class TestItineraryModel:
    def test_minimal_itinerary(self):
        it = Itinerary(
            destination="Tokyo",
            duration_days=5,
        )
        assert it.num_travelers == 1
        assert it.travel_style == "mid-range"
        assert it.days == []
        assert it.budget.total == 0

    def test_full_itinerary(self):
        it = Itinerary(
            destination="Tokyo",
            origin="Seattle",
            duration_days=5,
            num_travelers=2,
            travel_style="luxury",
            outbound_flight=Flight(
                airline="NH", origin="SEA", destination="NRT", price=850.0
            ),
            hotels=[
                Hotel(name="Park Hyatt", price_per_night=350.0, total_price=1750.0)
            ],
            days=[DayPlan(day=1, city="Tokyo")],
            budget=BudgetBreakdown(
                flights=1700, accommodation=3500, total=8200
            ),
        )
        assert it.outbound_flight is not None
        assert len(it.hotels) == 1
        assert it.budget.total == 8200


class TestBudgetBreakdownModel:
    def test_defaults_zero(self):
        b = BudgetBreakdown()
        assert b.flights == 0
        assert b.total == 0

    def test_serialization_roundtrip(self):
        b = BudgetBreakdown(flights=800, accommodation=1500, total=3200)
        data = b.model_dump()
        b2 = BudgetBreakdown(**data)
        assert b2.total == 3200
