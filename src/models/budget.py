"""Public budget report contracts with backwards-compatible USD fields."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.pricing import (
    BudgetCategory,
    NonNumericPriceEvidence,
    PriceBasis,
    PriceEvidence,
    PriceScope,
)


class BudgetCoverageStatus(StrEnum):
    COMPLETE = "complete"
    COMPLETE_WITH_ESTIMATES = "complete_with_estimates"
    PARTIAL = "partial"


class BudgetVerdict(StrEnum):
    NO_TARGET = "no_target"
    WITHIN_BUDGET = "within_budget"
    OVER_BUDGET = "over_budget"
    UNKNOWN = "unknown"


class ConversionStatus(StrEnum):
    NOT_NEEDED = "not_needed"
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


class BudgetReviewAction(StrEnum):
    PROCEED = "proceed"
    ADJUST_TARGET = "adjust_target"
    CANCEL = "cancel"


class BudgetReviewDecision(BaseModel):
    gate: Literal["budget_review"] = "budget_review"
    action: BudgetReviewAction
    new_budget: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_adjusted_target(self) -> "BudgetReviewDecision":
        if self.action == BudgetReviewAction.ADJUST_TARGET and self.new_budget is None:
            raise ValueError("new_budget is required for adjust_target")
        return self


class BudgetAmounts(BaseModel):
    flights: float = Field(default=0, ge=0)
    accommodation: float = Field(default=0, ge=0)
    transport: float = Field(default=0, ge=0)
    meals: float = Field(default=0, ge=0)
    activities: float = Field(default=0, ge=0)
    misc: float = Field(default=0, ge=0)
    total: float = Field(default=0, ge=0)
    per_person: float = Field(default=0, ge=0)
    target_budget: float = Field(default=0, ge=0)
    remaining_budget: float | None = None
    currency: str = "USD"

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, value: str) -> str:
        return value.strip().upper()[:3] if isinstance(value, str) else value


class BudgetLineItem(BaseModel):
    category: BudgetCategory
    source_component: str
    source_id: str
    source_amount: float = Field(ge=0)
    source_currency: str
    quantity: float = Field(default=1, gt=0)
    applied_multiplier: float = Field(default=1, ge=0)
    source_total: float = Field(default=0, ge=0)
    amount_usd: float | None = Field(default=None, ge=0)
    display_amount: float | None = Field(default=None, ge=0)
    display_currency: str = "USD"
    scope: PriceScope = PriceScope.TOTAL
    basis: PriceBasis = PriceBasis.QUOTED
    estimated: bool = False
    assumption: str = ""
    conversion_error: str = ""


class ConversionRateRecord(BaseModel):
    from_currency: str
    to_currency: str
    rate: float = Field(gt=0)
    provider: str = ""
    observed_at: str = ""


class BudgetBreakdown(BaseModel):
    """Auditable budget report; legacy top-level numeric fields remain USD."""

    schema_version: int = 2
    flights: float = Field(default=0, ge=0)
    accommodation: float = Field(default=0, ge=0)
    transport: float = Field(default=0, ge=0)
    meals: float = Field(default=0, ge=0)
    activities: float = Field(default=0, ge=0)
    misc: float = Field(default=0, ge=0)
    total: float = Field(default=0, ge=0)
    per_person: float = Field(default=0, ge=0)
    target_budget: float = Field(default=0, ge=0)
    currency: str = "USD"
    summary: str = ""

    base_currency: str = "USD"
    display_currency: str = "USD"
    display_breakdown: BudgetAmounts | None = None
    line_items: list[BudgetLineItem] = Field(default_factory=list)
    provenance: list[PriceEvidence] = Field(default_factory=list)
    non_numeric_evidence: list[NonNumericPriceEvidence] = Field(default_factory=list)
    conversion_rates: list[ConversionRateRecord] = Field(default_factory=list)
    conversion_status: ConversionStatus = ConversionStatus.NOT_NEEDED
    coverage_status: BudgetCoverageStatus = BudgetCoverageStatus.PARTIAL
    missing_categories: list[BudgetCategory] = Field(default_factory=list)
    estimated_categories: list[BudgetCategory] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    reconciliation_delta: float = 0
    verdict: BudgetVerdict = BudgetVerdict.NO_TARGET
    remaining_budget: float | None = None
    reserve_recommendation: float = Field(default=0, ge=0)
    display_reserve_recommendation: float | None = Field(default=None, ge=0)
    reserve_recommendation_percent: float = Field(default=10, ge=0, le=100)
    contingency_included: bool = False
    contingency_percent: float | None = Field(default=None, ge=0, le=100)
    display_conversion_available: bool = True
    request_fingerprint: str = ""

    @field_validator("currency", "base_currency", "display_currency", mode="before")
    @classmethod
    def _normalise_currency(cls, value: str) -> str:
        return value.strip().upper()[:3] if isinstance(value, str) else value

    @model_validator(mode="after")
    def _auto_total(self) -> "BudgetBreakdown":
        components = (
            self.flights
            + self.accommodation
            + self.transport
            + self.meals
            + self.activities
            + self.misc
        )
        if self.total == 0 and components > 0:
            self.total = round(components, 2)
        return self
