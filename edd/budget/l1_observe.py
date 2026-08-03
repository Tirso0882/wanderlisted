"""Construct and execute hermetic Budget Layer-1 scenarios."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from langchain_core.messages import ToolMessage

from src.budget import BudgetContext, BudgetPipeline
from src.budget.currency import ExchangeRateQuote, ExchangeRateUnavailable
from src.models import (
    BudgetCategory,
    CityStay,
    DraftDay,
    DraftItinerary,
    FlightWindowOption,
    HotelPriceOption,
    HotelSearchPricing,
    KnownTripCost,
    Money,
    PlaceRef,
    PriceEvidence,
    PriceScope,
    SelectedAccommodation,
    SelectionStatus,
    TravelerParty,
    TripRequest,
    TripSkeleton,
)
from src.models.trip_request import DateWindow


class StaticRates:
    """No-network exchange-rate provider for deterministic EDD."""

    def __init__(self, rates: dict[tuple[str, str], str]) -> None:
        self.rates = rates
        self.cache: dict[tuple[str, str], ExchangeRateQuote] = {}

    def remember_rate(self, quote: ExchangeRateQuote) -> None:
        self.cache[(quote.from_currency, quote.to_currency)] = quote

    async def get_rate(self, source: str, target: str) -> ExchangeRateQuote:
        key = (source, target)
        if source == target:
            return ExchangeRateQuote(source, target, Decimal("1"), "identity", "")
        if key in self.cache:
            return self.cache[key]
        if key not in self.rates:
            raise ExchangeRateUnavailable(f"no static rate for {source}/{target}")
        quote = ExchangeRateQuote(
            source, target, Decimal(self.rates[key]), "static-edd", "2026-08-03"
        )
        self.cache[key] = quote
        return quote


def _known(category, amount, *, currency="USD", scope=PriceScope.TOTAL):
    return KnownTripCost(
        category=category,
        money=Money(amount=Decimal(str(amount)), currency=currency),
        scope=scope,
    )


def _complete(*, currency="USD"):
    return [
        _known(BudgetCategory.FLIGHTS, 400, currency=currency),
        _known(BudgetCategory.ACCOMMODATION, 300, currency=currency),
        _known(BudgetCategory.TRANSPORT, 50, currency=currency),
        _known(BudgetCategory.MEALS, 100, currency=currency),
        _known(BudgetCategory.ACTIVITIES, 80, currency=currency),
        _known(BudgetCategory.MISC, 70, currency=currency),
    ]


def _request(
    *,
    costs=None,
    travelers=1,
    style="mid-range",
    target=None,
    currency="USD",
    destinations=None,
):
    return TripRequest(
        destinations=destinations or ["tokyo"],
        date_window=DateWindow(
            exact_start=date(2026, 9, 1), exact_end=date(2026, 9, 4), duration_days=4
        ),
        travelers=TravelerParty(adults=travelers),
        travel_style=style,
        known_costs=costs or [],
        budget_amount=target,
        budget_currency=currency,
    )


def _skeleton(*, flight=None, multicity=False):
    stays = [
        CityStay(
            sequence=1,
            city="tokyo",
            check_in=date(2026, 9, 1),
            check_out=date(2026, 9, 4),
            nights=3,
        )
    ]
    if multicity:
        stays = [
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
        ]
    return TripSkeleton(
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 4),
        duration_days=4,
        total_nights=3,
        entry_city="tokyo",
        exit_city="warsaw" if multicity else "tokyo",
        stays=stays,
        selected_flight=flight,
    )


def _selected(category, amount, source_id, *, component="edd"):
    return PriceEvidence(
        category=category,
        money=Money(amount=Decimal(str(amount)), currency="USD"),
        source_component=component,
        source_id=source_id,
        selection_status=SelectionStatus.SELECTED,
    )


def build_context(scenario: str) -> tuple[BudgetContext, StaticRates]:
    rates = StaticRates({})
    request = _request(costs=_complete())
    skeleton = None
    draft = None
    components = {}
    additional = ()

    if scenario == "party_scaling":
        costs = [cost for cost in _complete() if cost.category != BudgetCategory.MEALS]
        costs.append(_known(BudgetCategory.MEALS, 10, scope=PriceScope.PER_PERSON_DAY))
        request = _request(costs=costs, travelers=3)
    elif scenario == "duration_scaling":
        costs = [
            cost
            for cost in _complete()
            if cost.category != BudgetCategory.ACCOMMODATION
        ]
        costs.append(
            _known(BudgetCategory.ACCOMMODATION, 100, scope=PriceScope.PER_NIGHT)
        )
        request = _request(costs=costs)
        skeleton = _skeleton()
    elif scenario == "budget_style":
        request = _request(
            costs=[
                _known(BudgetCategory.FLIGHTS, 400),
                _known(BudgetCategory.ACCOMMODATION, 500),
            ],
            style="budget",
        )
    elif scenario == "flight_selection":
        evidence = _selected(
            BudgetCategory.FLIGHTS, 500, "flight-selected", component="flights"
        )
        flight = FlightWindowOption(
            departure_date=date(2026, 9, 1),
            return_date=date(2026, 9, 4),
            total_amount="500",
            offer_id="flight-selected",
            price_evidence=evidence,
        )
        costs = [
            cost for cost in _complete() if cost.category != BudgetCategory.FLIGHTS
        ]
        request = _request(costs=costs)
        skeleton = _skeleton(flight=flight)
        additional = (
            PriceEvidence(
                category=BudgetCategory.FLIGHTS,
                money=Money(amount=9999, currency="USD"),
                source_component="flights",
                source_id="flight-distractor",
                selection_status=SelectionStatus.CANDIDATE,
            ),
        )
    elif scenario == "hotel_selection":
        costs = [
            cost
            for cost in _complete()
            if cost.category != BudgetCategory.ACCOMMODATION
        ]
        request = _request(costs=costs)
        pricing = HotelSearchPricing(
            city_code="TYO",
            options=[
                HotelPriceOption(
                    rate_key="hotel-selected",
                    hotel_name="Selected",
                    money=Money(amount=600, currency="USD"),
                ),
                HotelPriceOption(
                    rate_key="hotel-distractor",
                    hotel_name="Distractor",
                    money=Money(amount=9999, currency="USD"),
                ),
            ],
        )
        components = {
            "hotels": {
                "messages": [
                    ToolMessage(
                        name="search_hotels_hotelbeds",
                        tool_call_id="h",
                        content=f"HOTEL_PRICING_JSON:\n{pricing.model_dump_json()}",
                    )
                ]
            }
        }
        draft = DraftItinerary(
            selected_accommodations=[
                SelectedAccommodation(
                    stay_sequence=1, name="Selected", rate_key="hotel-selected"
                )
            ]
        )
    elif scenario == "missing_flight":
        request = _request(
            costs=[
                cost for cost in _complete() if cost.category != BudgetCategory.FLIGHTS
            ],
            target=2000,
        )
    elif scenario == "missing_lodging":
        request = _request(
            costs=[
                cost
                for cost in _complete()
                if cost.category != BudgetCategory.ACCOMMODATION
            ],
            target=2000,
        )
    elif scenario == "conversion_success":
        request = _request(costs=_complete(currency="EUR"), target=1200, currency="EUR")
        rates = StaticRates({("EUR", "USD"): "1.1", ("USD", "EUR"): "0.9"})
    elif scenario == "conversion_failure":
        costs = _complete()
        costs[0] = _known(BudgetCategory.FLIGHTS, 400, currency="EUR")
        request = _request(costs=costs, target=2000)
    elif scenario == "multicity_estimates":
        request = _request(
            costs=[
                _known(BudgetCategory.FLIGHTS, 500),
                _known(BudgetCategory.ACCOMMODATION, 600),
            ],
            destinations=["tokyo", "warsaw"],
        )
        skeleton = _skeleton(multicity=True)
    elif scenario == "target_within":
        request = _request(costs=_complete(), target=1200)
    elif scenario == "target_over":
        request = _request(costs=_complete(), target=800)
    elif scenario == "places_signal":
        draft = DraftItinerary(
            days=[
                DraftDay(
                    day_number=1,
                    city="tokyo",
                    start_location=PlaceRef(
                        name="Hotel", place_id="hotel", price_level="$$$$"
                    ),
                    stops=[
                        PlaceRef(
                            name="Museum",
                            place_id="museum",
                            category="museum",
                            price_level="$$$",
                        )
                    ],
                )
            ]
        )
    elif scenario == "routes_signal":
        components = {"route_plan_structured": {"days": [{"day_number": 1}]}}
    elif scenario == "numeric_distractor":
        costs = [
            cost for cost in _complete() if cost.category != BudgetCategory.FLIGHTS
        ]
        request = _request(costs=costs)
        selected = _selected(BudgetCategory.FLIGHTS, 500, "selected-500")
        additional = (
            selected,
            selected,
            PriceEvidence(
                category=BudgetCategory.FLIGHTS,
                money=Money(amount=99999, currency="USD"),
                source_component="edd",
                source_id="numeric-99999",
                selection_status=SelectionStatus.CANDIDATE,
            ),
        )
    elif scenario != "arithmetic":
        raise KeyError(f"unknown budget EDD scenario: {scenario}")

    return BudgetContext(request, skeleton, draft, components, additional), rates


async def observe_case(case: dict) -> dict:
    context, rates = build_context(case["scenario"])
    run = await BudgetPipeline(rates).run(context)
    return run.report.model_dump(mode="json")
