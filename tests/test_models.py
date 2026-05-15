"""Unit tests for Pydantic models — schema validation and defaults."""

import pytest

from src.models import (
    BudgetBreakdown,
    DayPlan,
    DayWeather,
    FlightOption,
    FlightSegment,
    HotelOption,
    PackingItem,
    PlaceCard,
    SafetyInfo,
    TimeBlock,
    TransitStep,
    TripHandbook,
)
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
from src.agent.agents.supervisor_agent import RoutingDecision


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
        b = BudgetBreakdown(
            flights=800, accommodation=1500, total=3200, per_person=1600
        )
        data = b.model_dump()
        b2 = BudgetBreakdown(**data)
        assert b2.total == 3200
        assert b2.per_person == 1600

    def test_model_dump_keys(self):
        b = BudgetBreakdown()
        keys = set(b.model_dump().keys())
        expected = {
            "flights",
            "accommodation",
            "transport",
            "meals",
            "activities",
            "misc",
            "total",
            "per_person",
            "target_budget",
            "currency",
            "summary",
        }
        assert keys == expected


# ══════════════════════════════════════════════════════════════
# Enum tests
# ══════════════════════════════════════════════════════════════


class TestCabinClassEnum:
    def test_valid_values(self):
        assert CabinClass("economy") == CabinClass.ECONOMY
        assert CabinClass("business") == CabinClass.BUSINESS
        assert CabinClass("first") == CabinClass.FIRST
        assert CabinClass("premium_economy") == CabinClass.PREMIUM_ECONOMY

    def test_case_insensitive(self):
        assert CabinClass("BUSINESS") == CabinClass.BUSINESS
        assert CabinClass("First") == CabinClass.FIRST

    def test_hyphens_and_spaces(self):
        assert CabinClass("premium-economy") == CabinClass.PREMIUM_ECONOMY
        assert CabinClass("premium economy") == CabinClass.PREMIUM_ECONOMY

    def test_unknown_defaults_to_economy(self):
        assert CabinClass("nonsense") == CabinClass.ECONOMY


class TestTransitModeEnum:
    def test_valid_values(self):
        for val in (
            "walk",
            "transit",
            "drive",
            "train",
            "bus",
            "ferry",
            "bicycle",
            "subway",
        ):
            assert TransitMode(val).value == val

    def test_aliases(self):
        assert TransitMode("walking") == TransitMode.WALK
        assert TransitMode("driving") == TransitMode.DRIVE
        assert TransitMode("cycling") == TransitMode.BICYCLE

    def test_case_insensitive(self):
        assert TransitMode("TRAIN") == TransitMode.TRAIN

    def test_unknown_defaults_to_transit(self):
        assert TransitMode("teleport") == TransitMode.TRANSIT


class TestDayPeriodEnum:
    def test_valid_values(self):
        assert DayPeriod("morning") == DayPeriod.MORNING
        assert DayPeriod("afternoon") == DayPeriod.AFTERNOON
        assert DayPeriod("evening") == DayPeriod.EVENING

    def test_case_insensitive(self):
        assert DayPeriod("AFTERNOON") == DayPeriod.AFTERNOON

    def test_unknown_defaults_to_morning(self):
        assert DayPeriod("midnight") == DayPeriod.MORNING


class TestAdvisoryLevelEnum:
    def test_valid_values(self):
        assert AdvisoryLevel("green") == AdvisoryLevel.GREEN
        assert AdvisoryLevel("yellow") == AdvisoryLevel.YELLOW
        assert AdvisoryLevel("orange") == AdvisoryLevel.ORANGE
        assert AdvisoryLevel("red") == AdvisoryLevel.RED

    def test_case_insensitive(self):
        assert AdvisoryLevel("RED") == AdvisoryLevel.RED

    def test_unknown_defaults_to_green(self):
        assert AdvisoryLevel("purple") == AdvisoryLevel.GREEN


class TestPackingCategoryEnum:
    def test_valid_values(self):
        for val in (
            "clothing",
            "documents",
            "tech",
            "health",
            "money",
            "toiletries",
            "accessories",
        ):
            assert PackingCategory(val).value == val

    def test_unknown_defaults_to_clothing(self):
        assert PackingCategory("furniture") == PackingCategory.CLOTHING


class TestTravelStyleEnum:
    def test_valid_values(self):
        assert TravelStyle("budget") == TravelStyle.BUDGET
        assert TravelStyle("mid_range") == TravelStyle.MID_RANGE
        assert TravelStyle("luxury") == TravelStyle.LUXURY

    def test_hyphen_normalised(self):
        assert TravelStyle("mid-range") == TravelStyle.MID_RANGE

    def test_unknown_defaults_to_mid_range(self):
        assert TravelStyle("ultra") == TravelStyle.MID_RANGE


class TestGroupTypeEnum:
    def test_valid_values(self):
        for val in ("solo", "couple", "family", "friends", "group"):
            assert GroupType(val).value == val

    def test_unknown_defaults_to_solo(self):
        assert GroupType("tribe") == GroupType.SOLO


class TestSeasonEnum:
    def test_valid_values(self):
        for val in ("spring", "summer", "autumn", "winter"):
            assert Season(val).value == val

    def test_unknown_defaults_to_summer(self):
        assert Season("monsoon") == Season.SUMMER


# ══════════════════════════════════════════════════════════════
# BudgetBreakdown validator tests
# ══════════════════════════════════════════════════════════════


class TestBudgetBreakdownValidation:
    def test_negative_values_clamped_to_zero(self):
        b = BudgetBreakdown(
            flights=-100,
            accommodation=-50,
            transport=-10,
            meals=-20,
            activities=-30,
            misc=-5,
            total=-999,
            per_person=-200,
        )
        assert b.flights == 0.0
        assert b.accommodation == 0.0
        assert b.transport == 0.0
        assert b.meals == 0.0
        assert b.activities == 0.0
        assert b.misc == 0.0
        assert b.total == 0.0
        assert b.per_person == 0.0

    def test_currency_normalised_uppercase(self):
        assert BudgetBreakdown(currency="eur").currency == "EUR"

    def test_currency_trimmed_to_3_chars(self):
        assert BudgetBreakdown(currency="euro").currency == "EUR"

    def test_currency_stripped(self):
        assert BudgetBreakdown(currency="  gbp  ").currency == "GBP"

    def test_auto_total_when_zero(self):
        b = BudgetBreakdown(
            flights=100,
            accommodation=200,
            transport=50,
            meals=75,
            activities=60,
            misc=15,
        )
        assert b.total == pytest.approx(500.0)

    def test_explicit_total_preserved(self):
        b = BudgetBreakdown(flights=100, accommodation=200, total=999)
        assert b.total == 999.0

    def test_all_zero_stays_zero(self):
        assert BudgetBreakdown().total == 0.0


# ══════════════════════════════════════════════════════════════
# FlightSegment validator tests
# ══════════════════════════════════════════════════════════════


class TestFlightSegmentValidation:
    def test_iata_uppercased_and_stripped(self):
        seg = FlightSegment(departure_airport="  jfk  ", arrival_airport="lax")
        assert seg.departure_airport == "JFK"
        assert seg.arrival_airport == "LAX"

    def test_negative_duration_clamped(self):
        assert FlightSegment(duration_minutes=-30).duration_minutes == 0

    def test_negative_stops_clamped(self):
        assert FlightSegment(stops=-1).stops == 0

    def test_positive_values_pass(self):
        seg = FlightSegment(duration_minutes=180, stops=1)
        assert seg.duration_minutes == 180
        assert seg.stops == 1

    def test_cabin_class_enum_stored_as_string(self):
        seg = FlightSegment(cabin_class="business")
        assert seg.cabin_class == "business"
        assert isinstance(seg.cabin_class, str)

    def test_cabin_class_normalises_case(self):
        assert FlightSegment(cabin_class="FIRST").cabin_class == "first"

    def test_cabin_class_normalises_hyphens(self):
        assert (
            FlightSegment(cabin_class="premium-economy").cabin_class
            == "premium_economy"
        )

    def test_cabin_class_default(self):
        assert FlightSegment().cabin_class == "economy"


# ══════════════════════════════════════════════════════════════
# FlightOption validator tests
# ══════════════════════════════════════════════════════════════


class TestFlightOptionValidation:
    def test_negative_price_clamped(self):
        assert FlightOption(total_price_usd=-50).total_price_usd == 0.0

    def test_positive_price_passes(self):
        assert FlightOption(total_price_usd=350).total_price_usd == 350.0

    def test_currency_normalised(self):
        assert FlightOption(currency="eur").currency == "EUR"


# ══════════════════════════════════════════════════════════════
# HotelOption validator tests
# ══════════════════════════════════════════════════════════════


class TestHotelOptionValidation:
    def test_star_rating_clamped_high(self):
        assert HotelOption(star_rating=7).star_rating == 5

    def test_star_rating_clamped_low(self):
        assert HotelOption(star_rating=-1).star_rating == 0

    def test_star_rating_valid_passes(self):
        assert HotelOption(star_rating=4).star_rating == 4

    def test_negative_prices_clamped(self):
        h = HotelOption(price_per_night_usd=-100, total_price_usd=-500)
        assert h.price_per_night_usd == 0.0
        assert h.total_price_usd == 0.0

    def test_negative_distance_clamped(self):
        assert HotelOption(distance_from_center_km=-2.5).distance_from_center_km == 0.0


# ══════════════════════════════════════════════════════════════
# PlaceCard validator tests
# ══════════════════════════════════════════════════════════════


class TestPlaceCardValidation:
    def test_rating_clamped_high(self):
        assert PlaceCard(rating=7.5).rating == 5.0

    def test_rating_clamped_low(self):
        assert PlaceCard(rating=-1.0).rating == 0.0

    def test_none_rating_passes(self):
        assert PlaceCard(rating=None).rating is None

    def test_valid_rating_passes(self):
        assert PlaceCard(rating=4.3).rating == 4.3

    def test_negative_cost_clamped(self):
        assert PlaceCard(estimated_cost_usd=-25).estimated_cost_usd == 0.0

    def test_negative_duration_clamped(self):
        assert PlaceCard(estimated_duration_minutes=-10).estimated_duration_minutes == 0

    def test_negative_review_count_clamped(self):
        assert PlaceCard(review_count=-5).review_count == 0


# ══════════════════════════════════════════════════════════════
# TransitStep validator tests
# ══════════════════════════════════════════════════════════════


class TestTransitStepValidation:
    def test_mode_stored_as_string(self):
        t = TransitStep(mode="walk")
        assert t.mode == "walk"
        assert isinstance(t.mode, str)

    def test_mode_alias_walking(self):
        assert TransitStep(mode="walking").mode == "walk"

    def test_mode_alias_driving(self):
        assert TransitStep(mode="driving").mode == "drive"

    def test_mode_alias_cycling(self):
        assert TransitStep(mode="cycling").mode == "bicycle"

    def test_mode_case_insensitive(self):
        assert TransitStep(mode="TRAIN").mode == "train"

    def test_mode_unknown_defaults_transit(self):
        assert TransitStep(mode="teleport").mode == "transit"

    def test_negative_fare_clamped(self):
        assert TransitStep(fare_estimate_usd=-5).fare_estimate_usd == 0.0

    def test_default_mode_is_walk(self):
        assert TransitStep().mode == "walk"


# ══════════════════════════════════════════════════════════════
# DayWeather validator tests
# ══════════════════════════════════════════════════════════════


class TestDayWeatherValidation:
    def test_rain_clamped_above_100(self):
        assert DayWeather(rain_probability_pct=150).rain_probability_pct == 100

    def test_rain_clamped_below_0(self):
        assert DayWeather(rain_probability_pct=-10).rain_probability_pct == 0

    def test_valid_rain_passes(self):
        assert DayWeather(rain_probability_pct=65).rain_probability_pct == 65

    def test_boundary_values(self):
        assert DayWeather(rain_probability_pct=0).rain_probability_pct == 0
        assert DayWeather(rain_probability_pct=100).rain_probability_pct == 100


# ══════════════════════════════════════════════════════════════
# TimeBlock validator tests
# ══════════════════════════════════════════════════════════════


class TestTimeBlockValidation:
    def test_period_stored_as_string(self):
        assert TimeBlock(period="afternoon").period == "afternoon"

    def test_period_case_insensitive(self):
        assert TimeBlock(period="EVENING").period == "evening"

    def test_period_unknown_defaults_morning(self):
        assert TimeBlock(period="midnight").period == "morning"

    def test_negative_subtotal_clamped(self):
        assert TimeBlock(subtotal_usd=-10).subtotal_usd == 0.0

    def test_default_period_is_morning(self):
        assert TimeBlock().period == "morning"


# ══════════════════════════════════════════════════════════════
# DayPlan validator tests
# ══════════════════════════════════════════════════════════════


class TestDayPlanValidation:
    def test_negative_daily_cost_clamped(self):
        assert DayPlan(daily_cost_usd=-100).daily_cost_usd == 0.0

    def test_negative_walking_km_clamped(self):
        assert DayPlan(walking_km=-5).walking_km == 0.0

    def test_positive_values_pass(self):
        dp = DayPlan(daily_cost_usd=150, walking_km=8.5)
        assert dp.daily_cost_usd == 150.0
        assert dp.walking_km == 8.5


# ══════════════════════════════════════════════════════════════
# SafetyInfo validator tests
# ══════════════════════════════════════════════════════════════


class TestSafetyInfoValidation:
    def test_advisory_level_stored_as_string(self):
        s = SafetyInfo(advisory_level="red")
        assert s.advisory_level == "red"
        assert isinstance(s.advisory_level, str)

    def test_advisory_level_case_insensitive(self):
        assert SafetyInfo(advisory_level="RED").advisory_level == "red"

    def test_advisory_level_unknown_defaults_green(self):
        assert SafetyInfo(advisory_level="purple").advisory_level == "green"

    def test_advisory_num_clamped_high(self):
        s = SafetyInfo(advisory_level_num=10)
        # Model validator syncs to advisory_level ("green" → 1)
        assert s.advisory_level_num >= 1
        assert s.advisory_level_num <= 4

    def test_advisory_num_clamped_low(self):
        s = SafetyInfo(advisory_level_num=-1)
        assert s.advisory_level_num >= 1

    def test_currency_code_normalised(self):
        assert SafetyInfo(currency_code="  jpy  ").currency_code == "JPY"

    def test_sync_level_and_num_green(self):
        s = SafetyInfo(advisory_level="green")
        assert s.advisory_level_num == 1

    def test_sync_level_and_num_yellow(self):
        s = SafetyInfo(advisory_level="yellow")
        assert s.advisory_level_num == 2

    def test_sync_level_and_num_orange(self):
        s = SafetyInfo(advisory_level="orange")
        assert s.advisory_level_num == 3

    def test_sync_level_and_num_red(self):
        s = SafetyInfo(advisory_level="red")
        assert s.advisory_level_num == 4

    def test_sync_overrides_mismatched_num(self):
        """LLM says advisory_level='red' but advisory_level_num=1 → corrected to 4."""
        s = SafetyInfo(advisory_level="red", advisory_level_num=1)
        assert s.advisory_level_num == 4


# ══════════════════════════════════════════════════════════════
# PackingItem validator tests
# ══════════════════════════════════════════════════════════════


class TestPackingItemValidation:
    def test_category_stored_as_string(self):
        p = PackingItem(category="tech")
        assert p.category == "tech"
        assert isinstance(p.category, str)

    def test_category_case_insensitive(self):
        assert PackingItem(category="DOCUMENTS").category == "documents"

    def test_category_unknown_defaults_clothing(self):
        assert PackingItem(category="random").category == "clothing"

    def test_default_category_is_clothing(self):
        assert PackingItem().category == "clothing"


# ══════════════════════════════════════════════════════════════
# TripHandbook validator tests
# ══════════════════════════════════════════════════════════════


class TestTripHandbookValidation:
    def test_travel_style_normalised(self):
        assert TripHandbook(travel_style="LUXURY").travel_style == "luxury"

    def test_travel_style_blank_stays_empty(self):
        assert TripHandbook(travel_style="").travel_style == ""

    def test_travel_style_whitespace_stays_empty(self):
        assert TripHandbook(travel_style="   ").travel_style == ""

    def test_travel_style_unknown_coerced(self):
        # _missing_ returns MID_RANGE for unknown values
        assert TripHandbook(travel_style="ultra").travel_style == "mid_range"

    def test_group_type_normalised(self):
        assert TripHandbook(group_type="FAMILY").group_type == "family"

    def test_group_type_blank_stays_empty(self):
        assert TripHandbook(group_type="").group_type == ""

    def test_group_type_unknown_coerced(self):
        assert TripHandbook(group_type="platoon").group_type == "solo"

    def test_season_normalised(self):
        assert TripHandbook(season="WINTER").season == "winter"

    def test_season_blank_stays_empty(self):
        assert TripHandbook(season="").season == ""

    def test_season_unknown_coerced(self):
        assert TripHandbook(season="monsoon").season == "summer"

    def test_negative_budget_fields_clamped(self):
        th = TripHandbook(
            total_budget_usd=-500,
            budget_flights=-100,
            budget_accommodation=-200,
            budget_transport=-50,
            budget_meals=-75,
            budget_activities=-60,
            budget_misc=-15,
        )
        assert th.total_budget_usd == 0.0
        assert th.budget_flights == 0.0
        assert th.budget_accommodation == 0.0

    def test_auto_budget_total_when_zero(self):
        th = TripHandbook(
            budget_flights=500,
            budget_accommodation=800,
            budget_transport=200,
            budget_meals=300,
            budget_activities=150,
            budget_misc=50,
        )
        assert th.budget_total == pytest.approx(2000.0)

    def test_explicit_budget_total_preserved(self):
        th = TripHandbook(budget_flights=500, budget_total=5000)
        assert th.budget_total == 5000.0


# ══════════════════════════════════════════════════════════════
# RoutingDecision validator tests
# ══════════════════════════════════════════════════════════════


class TestRoutingDecisionValidation:
    def test_valid_agents_pass(self):
        rd = RoutingDecision(
            agents=["FlightsAgent", "HotelsAgent"],
            reasoning="Testing",
            user_message="Testing",
        )
        assert rd.agents == ["FlightsAgent", "HotelsAgent"]

    def test_hallucinated_agents_stripped(self):
        rd = RoutingDecision(
            agents=["FlightsAgent", "FakeAgent", "WeatherAgent"],
            reasoning="Testing",
            user_message="Testing",
        )
        assert rd.agents == ["FlightsAgent"]

    def test_all_invalid_agents_yields_empty(self):
        rd = RoutingDecision(
            agents=["BadAgent", "NonsenseAgent"],
            reasoning="Testing",
            user_message="Testing",
        )
        assert rd.agents == []

    def test_destinations_lowercased_and_stripped(self):
        rd = RoutingDecision(
            agents=[],
            reasoning="Testing",
            user_message="Testing",
            destinations=["  PARIS  ", " Tokyo ", "NEW YORK"],
        )
        assert rd.destinations == ["paris", "tokyo", "new york"]

    def test_empty_destinations_filtered(self):
        rd = RoutingDecision(
            agents=[],
            reasoning="Testing",
            user_message="Testing",
            destinations=["rome", "", "  "],
        )
        assert rd.destinations == ["rome"]
