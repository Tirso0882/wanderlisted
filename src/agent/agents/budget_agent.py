"""Production BudgetAgent: typed extraction plus deterministic calculation."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.agent.agents.base import SpecializedAgent
from src.agent.prompts import BUDGET_SYSTEM_PROMPT
from src.budget import BudgetContext, BudgetPipeline, BudgetRun, ExchangeRateProvider
from src.budget.evidence import assemble_price_evidence
from src.models import (
    BudgetCategory,
    Money,
    PriceBasis,
    PriceEvidence,
    PriceScope,
    SelectionStatus,
)
from src.models.pricing import NonNegativeDecimal


class LegacyPriceFact(BaseModel):
    category: BudgetCategory
    source_id: str = Field(min_length=1)
    amount: NonNegativeDecimal
    currency: str = Field(min_length=3, max_length=3)
    evidence_text: str = ""


class LegacyPriceFacts(BaseModel):
    facts: list[LegacyPriceFact] = Field(default_factory=list)


def _message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("text")
        )
    return str(content or "")


_MONEY_TOKEN = r"(?P<amount>\d[\d,]*(?:\.\d+)?)"
_MAX_SOURCE_AMOUNT_DISTANCE = 1024


def _validated_legacy_amount(raw: str, fact: LegacyPriceFact) -> bool:
    """Bind a fact to the closest explicit currency amount for its source ID."""
    source_positions = [
        match.start() for match in re.finditer(re.escape(fact.source_id), raw)
    ]
    if not source_positions:
        return False
    currency = re.escape(fact.currency.strip().upper())
    patterns = (
        re.compile(rf"(?i)\b{currency}\b\s*{_MONEY_TOKEN}"),
        re.compile(rf"(?i){_MONEY_TOKEN}\s*\b{currency}\b"),
    )
    candidates: list[tuple[int, int, Decimal, int, int]] = []
    for pattern in patterns:
        for match in pattern.finditer(raw):
            try:
                amount = Decimal(match.group("amount").replace(",", ""))
            except Exception:
                continue
            line_start = raw.rfind("\n", 0, match.start()) + 1
            line_end = raw.find("\n", match.end())
            if line_end < 0:
                line_end = len(raw)
            line = raw[line_start:line_end].lower()
            priority = 0 if "price" in line or "total" in line else 1
            candidates.append(
                (
                    priority,
                    (match.start() + match.end()) // 2,
                    amount,
                    line_start,
                    line_end,
                )
            )
    if not candidates:
        return False

    for source_position in source_positions:
        nearby = [
            candidate
            for candidate in candidates
            if abs(candidate[1] - source_position) <= _MAX_SOURCE_AMOUNT_DISTANCE
        ]
        if not nearby:
            continue
        nearest = min(
            nearby,
            key=lambda candidate: (
                candidate[0],
                abs(candidate[1] - source_position),
            ),
        )
        source_line_start = raw.rfind("\n", 0, source_position) + 1
        source_line_end = raw.find("\n", source_position)
        if source_line_end < 0:
            source_line_end = len(raw)
        same_line = nearest[3] == source_line_start and nearest[4] == source_line_end
        between = raw[
            min(source_position, nearest[1]) : max(source_position, nearest[1])
        ]
        if "\n\n" in between or (nearest[0] > 0 and not same_line):
            continue
        if nearest[2] == fact.amount:
            return True
    return False


class BudgetAgent(SpecializedAgent):
    """Fixed Budget pipeline; it is not a ReAct tool loop."""

    name = "BudgetAgent"
    description = "Typed budget evidence, deterministic arithmetic, and coverage"

    def __init__(self, llm=None, *, exchange_rates: ExchangeRateProvider | None = None):
        super().__init__(llm=llm)
        self.pipeline = BudgetPipeline(exchange_rates=exchange_rates)

    @property
    def tools(self):
        return []

    @property
    def system_prompt(self) -> str:
        return BUDGET_SYSTEM_PROMPT

    async def run(self, context: BudgetContext) -> BudgetRun:
        legacy = await self._extract_legacy_selected_prices(context)
        if legacy:
            context = replace(
                context,
                additional_evidence=(*context.additional_evidence, *legacy),
            )
        return await self.pipeline.run(context)

    async def _extract_legacy_selected_prices(
        self, context: BudgetContext
    ) -> list[PriceEvidence]:
        selected_ids: dict[str, BudgetCategory] = {}
        if context.skeleton and context.skeleton.selected_flight:
            selected = context.skeleton.selected_flight
            if selected.offer_id:
                selected_ids[selected.offer_id] = BudgetCategory.FLIGHTS
        if context.draft:
            selected_ids.update(
                {
                    item.rate_key: BudgetCategory.ACCOMMODATION
                    for item in context.draft.selected_accommodations
                }
            )
        existing, _ = assemble_price_evidence(context)
        missing_ids = selected_ids.keys() - {item.source_id for item in existing}
        if not missing_ids:
            return []

        raw_parts = []
        for key in ("flights", "hotels"):
            for message in context.components.get(key, {}).get("messages", []):
                text = _message_text(getattr(message, "content", ""))
                if text:
                    raw_parts.append(text)
        raw = "\n\n".join(raw_parts)
        if not raw:
            return []

        selected_contract = ", ".join(
            f"{source_id}:{selected_ids[source_id].value}"
            for source_id in sorted(missing_ids)
        )
        try:
            extractor = self.llm.with_structured_output(
                LegacyPriceFacts, method="function_calling"
            )
            extracted = await extractor.ainvoke(
                [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(
                        content=(
                            f"Selected source IDs: {selected_contract}\n\n"
                            f"Evidence:\n{raw[:24000]}"
                        )
                    ),
                ]
            )
        except Exception:
            return []

        accepted: list[PriceEvidence] = []
        for fact in extracted.facts:
            expected_category = selected_ids.get(fact.source_id)
            if expected_category != fact.category:
                continue
            if not _validated_legacy_amount(raw, fact):
                continue
            accepted.append(
                PriceEvidence(
                    category=fact.category,
                    money=Money(amount=fact.amount, currency=fact.currency),
                    source_component=(
                        "flights"
                        if fact.category == BudgetCategory.FLIGHTS
                        else "hotels"
                    ),
                    source_id=fact.source_id,
                    scope=PriceScope.TOTAL,
                    basis=PriceBasis.QUOTED,
                    selection_status=SelectionStatus.SELECTED,
                    evidence_text=fact.evidence_text,
                )
            )
        return accepted
