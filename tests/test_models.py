"""Unit tests for Pydantic models — schema validation and defaults."""

from src.models import BudgetBreakdown


class TestBudgetBreakdownModel:
    def test_defaults_zero(self):
        b = BudgetBreakdown()
        assert b.flights == 0
        assert b.total == 0
        assert b.per_person == 0
        assert b.currency == "USD"
        assert b.summary == ""

    def test_full_budget(self):
        b = BudgetBreakdown(
            flights=800,
            accommodation=1500,
            transport=200,
            meals=600,
            activities=300,
            misc=150,
            total=3550,
            per_person=1775,
            currency="USD",
            summary="Budget for 2 travelers, 5 days in Tokyo.",
        )
        assert b.total == 3550
        assert b.per_person == 1775
        assert "Tokyo" in b.summary

    def test_serialization_roundtrip(self):
        b = BudgetBreakdown(flights=800, accommodation=1500, total=3200, per_person=1600)
        data = b.model_dump()
        b2 = BudgetBreakdown(**data)
        assert b2.total == 3200
        assert b2.per_person == 1600

    def test_model_dump_keys(self):
        b = BudgetBreakdown()
        keys = set(b.model_dump().keys())
        expected = {
            "flights", "accommodation", "transport", "meals",
            "activities", "misc", "total", "per_person", "currency", "summary",
        }
        assert keys == expected
