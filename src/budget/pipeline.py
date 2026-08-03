"""Deterministic budget normalization, arithmetic, coverage, and rendering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

import config as app_config

from src.budget.currency import (
    ExchangeRateProvider,
    ExchangeRateQuote,
    ExchangeRateUnavailable,
)
from src.budget.estimates import regional_estimates
from src.budget.evidence import (
    BudgetContext,
    assemble_price_evidence,
    non_numeric_price_evidence,
)
from src.models import (
    BudgetAmounts,
    BudgetBreakdown,
    BudgetCategory,
    BudgetCoverageStatus,
    BudgetLineItem,
    BudgetVerdict,
    ConversionRateRecord,
    ConversionStatus,
    Money,
    PriceBasis,
    PriceEvidence,
    PriceScope,
    SelectionStatus,
)

_CENT = Decimal("0.01")
_DAILY_CATEGORIES = {
    BudgetCategory.MEALS,
    BudgetCategory.TRANSPORT,
    BudgetCategory.ACTIVITIES,
    BudgetCategory.MISC,
}


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _as_float(value: Decimal) -> float:
    return float(_money(value))


@dataclass(frozen=True, slots=True)
class BudgetRun:
    report: BudgetBreakdown
    message: str
    evidence: tuple[PriceEvidence, ...] = ()


class BudgetPipeline:
    def __init__(self, exchange_rates: ExchangeRateProvider | None = None) -> None:
        self.exchange_rates = exchange_rates or ExchangeRateProvider()

    @staticmethod
    def _scope_multiplier(item: PriceEvidence, context: BudgetContext) -> Decimal:
        travelers = max(
            1,
            (context.request.travelers.adults or 0)
            + context.request.travelers.children
            + context.request.travelers.infants,
        )
        days = context.request.date_window.duration_days or 1
        nights = (
            context.skeleton.total_nights
            if context.skeleton is not None
            else max(0, days - 1)
        )
        scope_multiplier = {
            PriceScope.TOTAL: Decimal("1"),
            PriceScope.PER_PERSON: Decimal(travelers),
            PriceScope.PER_NIGHT: Decimal(nights),
            PriceScope.PER_PERSON_DAY: Decimal(travelers * days),
        }[item.scope]
        return item.quantity * scope_multiplier

    async def _to_usd(
        self,
        item: PriceEvidence,
        source_total: Decimal,
        rates: dict[tuple[str, str], ExchangeRateQuote],
    ) -> Decimal:
        currency = item.money.currency
        if currency == "USD":
            return source_total
        quote = await self.exchange_rates.get_rate(currency, "USD")
        rates[(currency, "USD")] = quote
        return source_total * quote.rate

    async def run(self, context: BudgetContext) -> BudgetRun:
        for stored in context.stored_rates:
            self.exchange_rates.remember_rate(
                ExchangeRateQuote(
                    from_currency=stored.from_currency,
                    to_currency=stored.to_currency,
                    rate=Decimal(str(stored.rate)),
                    provider=stored.provider,
                    observed_at=stored.observed_at,
                )
            )

        selected, warnings = assemble_price_evidence(context)
        non_numeric = non_numeric_price_evidence(context)
        present = {item.category for item in selected}
        uncovered = _DAILY_CATEGORIES - present
        estimates, estimate_assumptions = regional_estimates(
            context.request,
            context.skeleton,
            uncovered=uncovered,
        )
        items = [*selected, *estimates]

        rates: dict[tuple[str, str], ExchangeRateQuote] = {}
        normalised: list[tuple[PriceEvidence, Decimal, Decimal | None, str]] = []
        conversion_failures: list[str] = []
        for item in items:
            multiplier = self._scope_multiplier(item, context)
            source_total = _money(item.money.amount * multiplier)
            try:
                amount_usd = _money(await self._to_usd(item, source_total, rates))
                normalised.append((item, source_total, amount_usd, ""))
            except ExchangeRateUnavailable as exc:
                error = str(exc)
                conversion_failures.append(f"{item.source_id}: {error}")
                normalised.append((item, source_total, None, error))

        converted = [
            (item, amount_usd)
            for item, _, amount_usd, _ in normalised
            if amount_usd is not None
        ]

        category_totals = {category: Decimal("0") for category in BudgetCategory}
        for item, amount_usd in converted:
            category_totals[item.category] += amount_usd

        contingency_included = context.request.contingency_percent is not None
        subtotal = sum(category_totals.values(), Decimal("0"))
        contingency_percent = context.request.contingency_percent
        if contingency_included and contingency_percent:
            contingency = _money(
                subtotal * Decimal(str(contingency_percent)) / Decimal("100")
            )
            contingency_item = PriceEvidence(
                category=BudgetCategory.MISC,
                money=Money(amount=contingency, currency="USD"),
                source_component="traveler",
                source_id=f"traveler:contingency:{contingency_percent:g}",
                scope=PriceScope.TOTAL,
                basis=PriceBasis.CONTINGENCY,
                selection_status=SelectionStatus.USER_SUPPLIED,
                evidence_text=(
                    f"Explicit {contingency_percent:g}% contingency on the converted subtotal."
                ),
            )
            items.append(contingency_item)
            normalised.append((contingency_item, contingency, contingency, ""))
            converted.append((contingency_item, contingency))
            category_totals[BudgetCategory.MISC] += contingency
        reserve_percent = Decimal(
            str(app_config.get("budget", "reserve_recommendation_percent", 10))
        )
        total = _money(sum(category_totals.values(), Decimal("0")))
        reserve = (
            Decimal("0")
            if contingency_included
            else _money(total * reserve_percent / Decimal("100"))
        )

        missing: list[BudgetCategory] = []
        converted_categories = {item.category for item, _ in converted}
        if BudgetCategory.FLIGHTS not in converted_categories:
            missing.append(BudgetCategory.FLIGHTS)
        if BudgetCategory.ACCOMMODATION not in converted_categories:
            missing.append(BudgetCategory.ACCOMMODATION)
        if conversion_failures:
            missing.extend(
                item.category
                for item, _, amount_usd, conversion_error in normalised
                if amount_usd is None and conversion_error
            )
        missing = list(dict.fromkeys(missing))

        estimated_categories = sorted(
            {item.category for item in estimates}, key=lambda value: value.value
        )
        if missing:
            coverage = BudgetCoverageStatus.PARTIAL
        elif estimated_categories:
            coverage = BudgetCoverageStatus.COMPLETE_WITH_ESTIMATES
        else:
            coverage = BudgetCoverageStatus.COMPLETE

        target_usd = Decimal("0")
        target_conversion_ok = True
        target = context.request.budget_amount
        target_currency = context.request.budget_currency or "USD"
        if target is not None:
            try:
                target_money = Decimal(str(target))
                if target_currency == "USD":
                    target_usd = target_money
                else:
                    quote = await self.exchange_rates.get_rate(target_currency, "USD")
                    rates[(target_currency, "USD")] = quote
                    target_usd = target_money * quote.rate
            except ExchangeRateUnavailable as exc:
                target_conversion_ok = False
                conversion_failures.append(f"target_budget: {exc}")

        travelers = max(
            1,
            (context.request.travelers.adults or 0)
            + context.request.travelers.children
            + context.request.travelers.infants,
        )
        per_person = _money(total / Decimal(travelers))
        if target is None:
            verdict = BudgetVerdict.NO_TARGET
            remaining_usd = None
        elif coverage == BudgetCoverageStatus.PARTIAL or not target_conversion_ok:
            verdict = BudgetVerdict.UNKNOWN
            remaining_usd = None
        else:
            remaining_usd = _money(target_usd - total)
            verdict = (
                BudgetVerdict.WITHIN_BUDGET
                if remaining_usd >= 0
                else BudgetVerdict.OVER_BUDGET
            )

        display_currency = target_currency
        display_rate = Decimal("1")
        display_available = True
        display_conversion_failure = ""
        if display_currency != "USD":
            try:
                quote = await self.exchange_rates.get_rate("USD", display_currency)
                rates[("USD", display_currency)] = quote
                display_rate = quote.rate
            except ExchangeRateUnavailable as exc:
                display_available = False
                display_conversion_failure = str(exc)

        line_items: list[BudgetLineItem] = []
        for item, source_total, amount_usd, conversion_error in normalised:
            multiplier = self._scope_multiplier(item, context)
            line_items.append(
                BudgetLineItem(
                    category=item.category,
                    source_component=item.source_component,
                    source_id=item.source_id,
                    source_amount=_as_float(item.money.amount),
                    source_currency=item.money.currency,
                    quantity=float(item.quantity),
                    applied_multiplier=float(multiplier),
                    source_total=_as_float(source_total),
                    amount_usd=(
                        _as_float(amount_usd) if amount_usd is not None else None
                    ),
                    display_amount=(
                        _as_float(amount_usd * display_rate)
                        if display_available and amount_usd is not None
                        else None
                    ),
                    display_currency=display_currency,
                    scope=item.scope,
                    basis=item.basis,
                    estimated=item.basis == PriceBasis.REGIONAL_ESTIMATE,
                    assumption=item.evidence_text,
                    conversion_error=conversion_error,
                )
            )

        assumptions = [*warnings, *estimate_assumptions]
        if conversion_failures:
            assumptions.append(
                "Some currency conversions were unavailable; affected amounts were excluded."
            )
        if display_conversion_failure:
            assumptions.append(
                "The requested display-currency conversion was unavailable; USD values remain authoritative."
            )
        if non_numeric:
            assumptions.append(
                "Places price levels and Routes no-fare signals were retained as non-numeric evidence and excluded from arithmetic."
            )
        if not contingency_included:
            assumptions.append(
                f"The {reserve_percent:g}% reserve is a recommendation and is excluded from totals."
            )
        else:
            assumptions.append(
                f"The traveler-supplied {contingency_percent:g}% contingency is included in miscellaneous costs."
            )

        amounts = {
            category.value: _money(value) for category, value in category_totals.items()
        }
        sum_components = sum(amounts.values(), Decimal("0"))
        reconciliation_delta = _money(total - sum_components)
        fingerprint_payload = {
            "request": context.request.model_dump(mode="json"),
            "skeleton": context.skeleton.model_dump(mode="json")
            if context.skeleton
            else None,
            "draft": context.draft.model_dump(mode="json") if context.draft else None,
            "sources": sorted(item.source_id for item in items),
            "non_numeric_sources": sorted(item.source_id for item in non_numeric),
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        display_total = _money(total * display_rate) if display_available else total
        display_target = (
            Decimal(str(target))
            if target is not None and display_available
            else Decimal("0")
        )
        display_remaining = (
            _money(remaining_usd * display_rate)
            if remaining_usd is not None and display_available
            else None
        )
        display = (
            BudgetAmounts(
                **{
                    category.value: _as_float(value * display_rate)
                    for category, value in category_totals.items()
                },
                total=_as_float(display_total),
                per_person=_as_float(display_total / Decimal(travelers)),
                target_budget=_as_float(display_target),
                remaining_budget=(
                    _as_float(display_remaining)
                    if display_remaining is not None
                    else None
                ),
                currency=display_currency,
            )
            if display_available
            else None
        )

        report = BudgetBreakdown(
            **{
                category.value: _as_float(value)
                for category, value in category_totals.items()
            },
            total=_as_float(total),
            per_person=_as_float(per_person),
            target_budget=_as_float(target_usd),
            currency="USD",
            summary=self._summary(total, travelers, coverage, verdict, missing),
            base_currency="USD",
            display_currency=display_currency,
            display_breakdown=display,
            line_items=line_items,
            provenance=items,
            non_numeric_evidence=non_numeric,
            conversion_rates=[
                ConversionRateRecord(
                    from_currency=quote.from_currency,
                    to_currency=quote.to_currency,
                    rate=float(quote.rate),
                    provider=quote.provider,
                    observed_at=quote.observed_at,
                )
                for _, quote in sorted(rates.items())
            ],
            conversion_status=(
                ConversionStatus.UNAVAILABLE
                if conversion_failures
                else ConversionStatus.COMPLETE
                if rates
                else ConversionStatus.NOT_NEEDED
            ),
            coverage_status=coverage,
            missing_categories=missing,
            estimated_categories=estimated_categories,
            assumptions=list(dict.fromkeys(assumptions)),
            reconciliation_delta=_as_float(reconciliation_delta),
            verdict=verdict,
            remaining_budget=(
                _as_float(remaining_usd) if remaining_usd is not None else None
            ),
            reserve_recommendation=_as_float(reserve),
            display_reserve_recommendation=(
                _as_float(reserve * display_rate) if display_available else None
            ),
            reserve_recommendation_percent=float(reserve_percent),
            contingency_included=contingency_included,
            contingency_percent=contingency_percent,
            display_conversion_available=display_available,
            request_fingerprint=fingerprint,
        )
        return BudgetRun(
            report=report,
            message=report.summary,
            evidence=tuple(selected),
        )

    @staticmethod
    def _summary(total, travelers, coverage, verdict, missing) -> str:
        summary = f"Estimated trip total: USD {_money(total):,.2f} for {travelers} traveler(s)."
        if coverage == BudgetCoverageStatus.PARTIAL:
            labels = ", ".join(category.value for category in missing)
            return f"{summary} Coverage is partial; missing: {labels}."
        if verdict == BudgetVerdict.OVER_BUDGET:
            return f"{summary} The estimate is over the stated target."
        if verdict == BudgetVerdict.WITHIN_BUDGET:
            return f"{summary} The estimate is within the stated target."
        return summary
