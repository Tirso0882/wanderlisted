"""Legacy prose extraction is bounded, source-validated, and single-call."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from langchain_core.messages import ToolMessage

from src.agent.agents.budget_agent import BudgetAgent, LegacyPriceFact, LegacyPriceFacts
from src.budget import BudgetContext
from src.models import (
    BudgetCategory,
    CityStay,
    FlightWindowOption,
    Money,
    PriceEvidence,
    SelectionStatus,
    TravelerParty,
    TripRequest,
    TripSkeleton,
)
from src.models.trip_request import DateWindow


def _context(evidence_text: str) -> BudgetContext:
    request = TripRequest(
        destinations=["tokyo"],
        date_window=DateWindow(
            exact_start=date(2026, 9, 1),
            exact_end=date(2026, 9, 4),
            duration_days=4,
        ),
        travelers=TravelerParty(adults=1),
    )
    skeleton = TripSkeleton(
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
        selected_flight=FlightWindowOption(
            departure_date=date(2026, 9, 1),
            return_date=date(2026, 9, 4),
            total_amount="1234.50",
            currency="USD",
            offer_id="offer-selected",
        ),
    )
    message = ToolMessage(
        name="search_flights",
        tool_call_id="flight-call",
        content=evidence_text,
    )
    return BudgetContext(
        request=request,
        skeleton=skeleton,
        draft=None,
        components={"flights": {"messages": [message]}},
    )


async def test_legacy_price_is_accepted_only_when_id_amount_and_currency_match():
    llm = MagicMock()
    extractor = AsyncMock()
    extractor.ainvoke.return_value = LegacyPriceFacts(
        facts=[
            LegacyPriceFact(
                category=BudgetCategory.FLIGHTS,
                source_id="offer-selected",
                amount=Decimal("1234.50"),
                currency="USD",
            )
        ]
    )
    llm.with_structured_output.return_value = extractor
    agent = BudgetAgent(llm=llm)

    run = await agent.run(
        _context("Offer offer-selected has exact total USD 1,234.50. Distractor 99999.")
    )

    assert run.report.flights == 1234.5
    assert run.evidence[0].source_id == "offer-selected"
    extractor.ainvoke.assert_awaited_once()


async def test_legacy_extraction_preserves_existing_validated_evidence():
    llm = MagicMock()
    extractor = AsyncMock()
    extractor.ainvoke.return_value = LegacyPriceFacts(
        facts=[
            LegacyPriceFact(
                category=BudgetCategory.FLIGHTS,
                source_id="offer-selected",
                amount=Decimal("1234.50"),
                currency="USD",
            )
        ]
    )
    llm.with_structured_output.return_value = extractor
    supplemental = PriceEvidence(
        category=BudgetCategory.ACCOMMODATION,
        money=Money(amount=Decimal("300"), currency="USD"),
        source_component="legacy-migration",
        source_id="rate-already-validated",
        selection_status=SelectionStatus.SELECTED,
    )
    context = _context("Offer offer-selected has exact total USD 1,234.50.")
    context = BudgetContext(
        request=context.request,
        skeleton=context.skeleton,
        draft=context.draft,
        components=context.components,
        additional_evidence=(supplemental,),
    )

    run = await BudgetAgent(llm=llm).run(context)

    assert {item.source_id for item in run.evidence} == {
        "offer-selected",
        "rate-already-validated",
    }


async def test_legacy_numeric_distractor_is_rejected():
    llm = MagicMock()
    extractor = AsyncMock()
    extractor.ainvoke.return_value = LegacyPriceFacts(
        facts=[
            LegacyPriceFact(
                category=BudgetCategory.FLIGHTS,
                source_id="offer-selected",
                amount=Decimal("99999"),
                currency="USD",
            )
        ]
    )
    llm.with_structured_output.return_value = extractor
    agent = BudgetAgent(llm=llm)

    run = await agent.run(
        _context(
            "Offer offer-selected has exact total USD 1,234.50. "
            "A different unselected offer elsewhere costs USD 99999."
        )
    )

    assert run.report.flights == 0
    assert BudgetCategory.FLIGHTS in run.report.missing_categories
    assert run.evidence == ()


async def test_legacy_amount_far_from_source_id_is_rejected():
    llm = MagicMock()
    extractor = AsyncMock()
    extractor.ainvoke.return_value = LegacyPriceFacts(
        facts=[
            LegacyPriceFact(
                category=BudgetCategory.FLIGHTS,
                source_id="offer-selected",
                amount=Decimal("1234.50"),
                currency="USD",
            )
        ]
    )
    llm.with_structured_output.return_value = extractor
    agent = BudgetAgent(llm=llm)

    run = await agent.run(
        _context(
            "Selected source ID: offer-selected\n\n"
            + ("unrelated evidence " * 100)
            + "\nDifferent offer total USD 1,234.50."
        )
    )

    assert run.report.flights == 0
    assert run.evidence == ()
