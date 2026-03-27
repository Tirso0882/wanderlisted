"""Unit tests for budget calculator tool — pure Python, no APIs."""

from src.tools.budget import calculate_budget


class TestValidBudget:
    """Budget calculations with valid inputs."""

    def test_basic_budget(self):
        result = calculate_budget.invoke({
            "destination_region": "east asia",
            "travel_style": "mid-range",
            "duration_days": 5,
            "num_travelers": 2,
        })
        assert "Budget Estimate" in result
        assert "East Asia" in result
        assert "Mid-Range" in result

    def test_includes_category_breakdown(self):
        result = calculate_budget.invoke({
            "destination_region": "east asia",
            "travel_style": "mid-range",
            "duration_days": 5,
            "num_travelers": 1,
        })
        assert "Meals" in result
        assert "Transport" in result
        assert "Activities" in result
        assert "TOTAL" in result

    def test_budget_style_scales(self):
        """Luxury should cost more than budget for the same trip."""
        budget_result = calculate_budget.invoke({
            "destination_region": "western europe",
            "travel_style": "budget",
            "duration_days": 7,
            "num_travelers": 1,
        })
        luxury_result = calculate_budget.invoke({
            "destination_region": "western europe",
            "travel_style": "luxury",
            "duration_days": 7,
            "num_travelers": 1,
        })
        # Extract TOTAL line — $ amount
        def _extract_total(text: str) -> float:
            for line in text.split("\n"):
                if "TOTAL" in line:
                    # Find the dollar amount after $
                    parts = line.split("$")
                    if len(parts) >= 2:
                        return float(parts[-1].strip().replace(",", ""))
            return 0.0

        assert _extract_total(luxury_result) > _extract_total(budget_result)

    def test_flight_hotel_cost_included(self):
        result = calculate_budget.invoke({
            "destination_region": "east asia",
            "travel_style": "mid-range",
            "duration_days": 3,
            "num_travelers": 1,
            "flight_cost": 800.0,
            "hotel_cost": 450.0,
        })
        assert "800" in result
        assert "450" in result
        assert "not yet searched" not in result

    def test_warns_when_flights_hotels_zero(self):
        result = calculate_budget.invoke({
            "destination_region": "east asia",
            "travel_style": "mid-range",
            "duration_days": 3,
            "num_travelers": 1,
        })
        assert "not yet searched" in result


class TestAllRegions:
    """Every supported region should return a valid budget."""

    REGIONS = [
        "east asia", "southeast asia", "western europe", "eastern europe",
        "north america", "south america", "middle east", "oceania", "africa",
    ]

    def test_all_regions_return_budget(self):
        for region in self.REGIONS:
            result = calculate_budget.invoke({
                "destination_region": region,
                "travel_style": "mid-range",
                "duration_days": 3,
                "num_travelers": 1,
            })
            assert "Budget Estimate" in result, f"Failed for region: {region}"


class TestInvalidInputs:
    def test_unknown_region(self):
        result = calculate_budget.invoke({
            "destination_region": "mars",
            "travel_style": "mid-range",
            "duration_days": 3,
            "num_travelers": 1,
        })
        assert "Unknown region" in result
        assert "Available regions" in result

    def test_unknown_style_uses_default(self):
        """Unknown style should fall back to 1.0 multiplier (mid-range)."""
        result = calculate_budget.invoke({
            "destination_region": "east asia",
            "travel_style": "ultra-premium",
            "duration_days": 3,
            "num_travelers": 1,
        })
        # Should still produce a budget, not crash
        assert "Budget Estimate" in result
