"""Production BudgetAgent contracts: evidence, arithmetic, and coverage."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from langchain_core.messages import ToolMessage

from src.budget import BudgetContext, BudgetPipeline
from src.budget.currency import ExchangeRateQuote, ExchangeRateUnavailable
from src.models import (
    BudgetCategory,
    BudgetCoverageStatus,
    BudgetVerdict,
    CityStay,
    DraftDay,
    DraftItinerary,
    FlightWindowOption,
    HotelPriceOption,
    HotelSearchPricing,
    KnownTripCost,
    Money,
    PlaceRef,
    PriceBasis,
    PriceEvidence,
    PriceScope,
    SelectedAccommodation,
    SelectionStatus,
    TravelerParty,
    TripRequest,
    TripSkeleton,
)
from src.models.trip_request import DateWindow


class FakeRates:
    def __init__(self, rates: dict[tuple[str, str], str] | None = None) -> None:
        self.rates = rates or {}
        self.cache: dict[tuple[str, str], ExchangeRateQuote] = {}
        self.fetches: list[tuple[str, str]] = []

    def remember_rate(self, quote: ExchangeRateQuote) -> None:
        self.cache[(quote.from_currency, quote.to_currency)] = quote

    async def get_rate(self, source: str, target: str) -> ExchangeRateQuote:
        key = (source, target)
        if source == target:
            return ExchangeRateQuote(source, target, Decimal("1"), "identity", "")
        if key in self.cache:
            return self.cache[key]
        self.fetches.append(key)
        if key not in self.rates:
            raise ExchangeRateUnavailable(f"no test rate for {source}/{target}")
        quote = ExchangeRateQuote(
            source,
            target,
            Decimal(self.rates[key]),
            "fake",
            "2026-08-03T00:00:00+00:00",
        )
        self.cache[key] = quote
        return quote


def _request(
    *,
    destinations: list[str] | None = None,
    travelers: int = 1,
    known_costs: list[KnownTripCost] | None = None,
    target: float | None = None,
    currency: str = "USD",
    contingency: float | None = None,
) -> TripRequest:
    return TripRequest(
        destinations=destinations or ["tokyo"],
        date_window=DateWindow(
            exact_start=date(2026, 9, 1),
            exact_end=date(2026, 9, 4),
            duration_days=4,
        ),
        travelers=TravelerParty(adults=travelers),
        travel_style="mid-range",
        known_costs=known_costs or [],
        budget_amount=target,
        budget_currency=currency,
        contingency_percent=contingency,
    )


def _price(
    category: BudgetCategory,
    amount: str,
    source_id: str,
    *,
    currency: str = "USD",
    scope: PriceScope = PriceScope.TOTAL,
) -> PriceEvidence:
    return PriceEvidence(
        category=category,
        money=Money(amount=Decimal(amount), currency=currency),
        source_component="test",
        source_id=source_id,
        scope=scope,
        basis=PriceBasis.QUOTED,
        selection_status=SelectionStatus.SELECTED,
    )


def _known(
    category: BudgetCategory,
    amount: str,
    *,
    currency: str = "USD",
    scope: PriceScope = PriceScope.TOTAL,
) -> KnownTripCost:
    return KnownTripCost(
        category=category,
        money=Money(amount=Decimal(amount), currency=currency),
        scope=scope,
    )


def _complete_known_costs(*, currency: str = "USD") -> list[KnownTripCost]:
    return [
        _known(BudgetCategory.FLIGHTS, "400", currency=currency),
        _known(BudgetCategory.ACCOMMODATION, "300", currency=currency),
        _known(BudgetCategory.TRANSPORT, "50", currency=currency),
        _known(BudgetCategory.MEALS, "100", currency=currency),
        _known(BudgetCategory.ACTIVITIES, "80", currency=currency),
        _known(BudgetCategory.MISC, "70", currency=currency),
    ]


def _skeleton(*, flight: FlightWindowOption | None = None) -> TripSkeleton:
    return TripSkeleton(
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 4),
        duration_days=4,
        total_nights=3,
        entry_city="tokyo",
        exit_city="tokyo",
        stays=[
            CityStay(
                sequence=1,
                city="tokyo",
                check_in=date(2026, 9, 1),
                check_out=date(2026, 9, 4),
                nights=3,
            )
        ],
        selected_flight=flight,
    )


@pytest.mark.parametrize("amount", ["-0.01", "-100"])
def test_money_rejects_negative_input(amount: str):
    with pytest.raises(ValueError):
        Money(amount=Decimal(amount), currency="USD")


def test_money_normalizes_and_validates_currency():
    assert Money(amount=1, currency=" eur ").currency == "EUR"
    with pytest.raises(ValueError):
        Money(amount=1, currency="euro")


async def test_scopes_rounding_and_reconciliation_are_deterministic():
    costs = [
        _known(BudgetCategory.FLIGHTS, "400.005"),
        _known(BudgetCategory.ACCOMMODATION, "100", scope=PriceScope.PER_NIGHT),
        _known(BudgetCategory.TRANSPORT, "50"),
        _known(BudgetCategory.MEALS, "10", scope=PriceScope.PER_PERSON_DAY),
        _known(BudgetCategory.ACTIVITIES, "25", scope=PriceScope.PER_PERSON),
        _known(BudgetCategory.MISC, "20"),
    ]
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(_request(travelers=2, known_costs=costs), _skeleton(), None, {})
    )

    assert run.report.flights == 400.01
    assert run.report.accommodation == 300
    assert run.report.meals == 80
    assert run.report.activities == 50
    assert run.report.total == 900.01
    assert run.report.per_person == 450.01
    assert run.report.reconciliation_delta == 0
    assert run.report.coverage_status == BudgetCoverageStatus.COMPLETE


async def test_duplicate_selected_evidence_is_counted_once():
    duplicated = _price(BudgetCategory.FLIGHTS, "500", "offer-1")
    costs = _complete_known_costs()
    costs = [cost for cost in costs if cost.category != BudgetCategory.FLIGHTS]
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(known_costs=costs),
            None,
            None,
            {},
            additional_evidence=(duplicated, duplicated),
        )
    )

    assert run.report.flights == 500
    assert sum(item.source_id == "offer-1" for item in run.report.line_items) == 1
    assert any("Duplicate price evidence" in item for item in run.report.assumptions)


async def test_only_selected_hotel_rate_and_flight_offer_are_counted():
    flight_evidence = PriceEvidence(
        category=BudgetCategory.FLIGHTS,
        money=Money(amount=Decimal("500"), currency="USD"),
        source_component="flights",
        source_id="offer-selected",
        selection_status=SelectionStatus.SELECTED,
    )
    flight = FlightWindowOption(
        departure_date=date(2026, 9, 1),
        return_date=date(2026, 9, 4),
        total_amount="500",
        currency="USD",
        offer_id="offer-selected",
        price_evidence=flight_evidence,
    )
    pricing = HotelSearchPricing(
        city_code="TYO",
        options=[
            HotelPriceOption(
                rate_key="rate-selected",
                hotel_name="Selected Hotel",
                money=Money(amount=Decimal("600"), currency="USD"),
                observed_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
            ),
            HotelPriceOption(
                rate_key="rate-unselected",
                hotel_name="Distractor Hotel",
                money=Money(amount=Decimal("9999"), currency="USD"),
            ),
        ],
    )
    hotel_message = ToolMessage(
        name="search_hotels_hotelbeds",
        tool_call_id="hotel-call",
        content=f"offers\nHOTEL_PRICING_JSON:\n{pricing.model_dump_json()}",
    )
    draft = DraftItinerary(
        selected_accommodations=[
            SelectedAccommodation(
                stay_sequence=1,
                name="Selected Hotel",
                rate_key="rate-selected",
            )
        ]
    )
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(),
            _skeleton(flight=flight),
            draft,
            {"hotels": {"messages": [hotel_message]}},
        )
    )

    assert run.report.flights == 500
    assert run.report.accommodation == 600
    assert "rate-unselected" not in {item.source_id for item in run.report.line_items}
    assert "rate-unselected" not in {item.source_id for item in run.report.provenance}
    selected_provenance = next(
        item for item in run.report.provenance if item.source_id == "rate-selected"
    )
    assert selected_provenance.observed_at == datetime(2026, 8, 3, tzinfo=timezone.utc)
    assert run.report.total < 9999


async def test_repeated_hotel_rate_reference_is_counted_once():
    pricing = HotelSearchPricing(
        city_code="TYO",
        options=[
            HotelPriceOption(
                rate_key="same-rate",
                hotel_name="Hotel",
                money=Money(amount=Decimal("300"), currency="USD"),
            )
        ],
    )
    message = ToolMessage(
        name="search_hotels_hotelbeds",
        tool_call_id="hotel-call",
        content=f"HOTEL_PRICING_JSON:\n{pricing.model_dump_json()}",
    )
    draft = DraftItinerary(
        selected_accommodations=[
            SelectedAccommodation(stay_sequence=1, name="Hotel", rate_key="same-rate"),
            SelectedAccommodation(stay_sequence=2, name="Hotel", rate_key="same-rate"),
        ]
    )
    costs = _complete_known_costs()
    costs = [cost for cost in costs if cost.category != BudgetCategory.ACCOMMODATION]
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(known_costs=costs),
            None,
            draft,
            {"hotels": {"messages": [message]}},
        )
    )

    assert run.report.accommodation == 300
    assert sum(item.source_id == "same-rate" for item in run.report.line_items) == 1


def test_selected_flight_rejects_mismatched_offer_id_or_amount():
    evidence = PriceEvidence(
        category=BudgetCategory.FLIGHTS,
        money=Money(amount=Decimal("500"), currency="USD"),
        source_component="flights",
        source_id="other-offer",
        selection_status=SelectionStatus.SELECTED,
    )
    with pytest.raises(ValueError, match="offer ID"):
        FlightWindowOption(
            departure_date=date(2026, 9, 1),
            return_date=date(2026, 9, 4),
            total_amount="500",
            offer_id="selected-offer",
            price_evidence=evidence,
        )


async def test_currency_conversion_uses_one_fetch_per_distinct_pair():
    rates = FakeRates({("EUR", "USD"): "1.1", ("USD", "EUR"): "0.9"})
    run = await BudgetPipeline(rates).run(
        BudgetContext(
            _request(
                known_costs=_complete_known_costs(currency="EUR"),
                target=1200,
                currency="EUR",
            ),
            None,
            None,
            {},
        )
    )

    assert rates.fetches == [("EUR", "USD"), ("USD", "EUR")]
    assert run.report.total == 1100
    assert run.report.display_breakdown is not None
    assert run.report.display_breakdown.total == 990
    assert run.report.verdict == BudgetVerdict.WITHIN_BUDGET


async def test_target_adjustment_reuses_stored_evidence_and_rates():
    rates = FakeRates({("EUR", "USD"): "1.1", ("USD", "EUR"): "0.9"})
    request = _request(
        known_costs=_complete_known_costs(currency="EUR"),
        target=900,
        currency="EUR",
    )
    pipeline = BudgetPipeline(rates)
    first = await pipeline.run(BudgetContext(request, None, None, {}))
    fetch_count = len(rates.fetches)
    adjusted = request.model_copy(update={"budget_amount": 1200})
    second = await pipeline.run(
        BudgetContext(
            adjusted,
            None,
            None,
            {},
            additional_evidence=first.evidence,
            stored_rates=tuple(first.report.conversion_rates),
        )
    )

    assert first.report.verdict == BudgetVerdict.OVER_BUDGET
    assert second.report.verdict == BudgetVerdict.WITHIN_BUDGET
    assert len(rates.fetches) == fetch_count
    assert first.report.total == second.report.total


async def test_conversion_failure_preserves_source_value_and_blocks_verdict():
    costs = _complete_known_costs()
    costs[0] = _known(BudgetCategory.FLIGHTS, "400", currency="EUR")
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(known_costs=costs, target=2000),
            None,
            None,
            {},
        )
    )

    flight = next(item for item in run.report.line_items if item.category == "flights")
    assert flight.source_amount == 400
    assert flight.source_currency == "EUR"
    assert flight.amount_usd is None
    assert flight.conversion_error
    assert run.report.coverage_status == BudgetCoverageStatus.PARTIAL
    assert run.report.verdict == BudgetVerdict.UNKNOWN


async def test_contingency_is_opt_in_and_reserve_is_excluded():
    without = await BudgetPipeline(FakeRates()).run(
        BudgetContext(_request(known_costs=_complete_known_costs()), None, None, {})
    )
    with_contingency = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(known_costs=_complete_known_costs(), contingency=10),
            None,
            None,
            {},
        )
    )

    assert without.report.total == 1000
    assert without.report.reserve_recommendation == 100
    assert not without.report.contingency_included
    assert with_contingency.report.total == 1100
    assert with_contingency.report.misc == 170
    assert with_contingency.report.reserve_recommendation == 0
    assert with_contingency.report.contingency_included
    assert any(
        item.basis == PriceBasis.CONTINGENCY
        for item in with_contingency.report.line_items
    )


async def test_multicity_estimates_allocate_stay_nights_plus_final_day():
    skeleton = TripSkeleton(
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 4),
        duration_days=4,
        total_nights=3,
        entry_city="tokyo",
        exit_city="warsaw",
        stays=[
            CityStay(
                sequence=1,
                city="tokyo",
                check_in=date(2026, 9, 1),
                check_out=date(2026, 9, 3),
                nights=2,
            ),
            CityStay(
                sequence=2,
                city="warsaw",
                check_in=date(2026, 9, 3),
                check_out=date(2026, 9, 4),
                nights=1,
            ),
        ],
    )
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(
                destinations=["tokyo", "warsaw"],
                known_costs=[
                    _known(BudgetCategory.FLIGHTS, "500"),
                    _known(BudgetCategory.ACCOMMODATION, "600"),
                ],
            ),
            skeleton,
            None,
            {},
        )
    )

    assert run.report.meals == 140  # Tokyo 2 days × 40 + Warsaw 2 days × 30
    assert run.report.coverage_status == BudgetCoverageStatus.COMPLETE_WITH_ESTIMATES
    assert any("final trip day" in assumption for assumption in run.report.assumptions)


async def test_unresolved_location_uses_disclosed_global_fallback():
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(
                destinations=["unknown moon base"],
                known_costs=[
                    _known(BudgetCategory.FLIGHTS, "500"),
                    _known(BudgetCategory.ACCOMMODATION, "600"),
                ],
            ),
            None,
            None,
            {},
        )
    )

    assert any("global daily baseline" in item for item in run.report.assumptions)


async def test_resolved_african_location_uses_regional_baseline():
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(
                destinations=["cape town"],
                known_costs=[
                    _known(BudgetCategory.FLIGHTS, "500"),
                    _known(BudgetCategory.ACCOMMODATION, "600"),
                ],
            ),
            None,
            None,
            {},
        )
    )

    assert run.report.meals == 100  # Africa baseline: 25 USD x 4 days.
    assert not any(
        "cape town" in item.lower() and "global daily baseline" in item.lower()
        for item in run.report.assumptions
    )


async def test_places_levels_and_routes_no_fare_are_non_numeric_evidence():
    hotel = PlaceRef(name="Hotel", place_id="hotel-1", price_level="$$$$")
    activity = PlaceRef(
        name="Museum",
        place_id="place-1",
        category="museum",
        price_level="$$$",
    )
    draft = DraftItinerary(
        days=[
            DraftDay(day_number=1, city="tokyo", start_location=hotel, stops=[activity])
        ]
    )
    components = {
        "route_plan_structured": {
            "days": [{"day_number": 1, "total_distance_meters": 1000}]
        }
    }
    run = await BudgetPipeline(FakeRates()).run(
        BudgetContext(
            _request(
                known_costs=[
                    _known(BudgetCategory.FLIGHTS, "500"),
                    _known(BudgetCategory.ACCOMMODATION, "600"),
                ]
            ),
            None,
            draft,
            components,
        )
    )

    signals = {
        (item.source_component, item.signal) for item in run.report.non_numeric_evidence
    }
    assert ("places", "price_level") in signals
    assert ("routes", "fare_status") in signals
    assert all(item.source_component != "places" for item in run.report.line_items)
    assert all(item.source_component != "routes" for item in run.report.line_items)
