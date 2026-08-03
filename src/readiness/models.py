"""Canonical contracts for evidence-grounded travel readiness."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.models import (
    AdvisoryLevel,
    ComponentStatus,
    CultureGuide,
    DayWeather,
    ErrorCategory,
    PackingItem,
    ReadinessTopic,
    SafetyInfo,
)


class ReadinessIntent(StrEnum):
    OVERVIEW = "overview"
    CULTURE = "culture"
    SAFETY = "safety"
    WEATHER = "weather"
    ENTRY = "entry"
    HEALTH = "health"
    PRACTICAL = "practical"
    PACKING = "packing"
    COMPREHENSIVE = "comprehensive"


class ReadinessEvidenceTopic(StrEnum):
    """Evidence categories owned by readiness retrieval.

    ``ENTRY`` intentionally retains the existing serialized value ``visa`` so
    the public v2 report payload does not change.
    """

    CULTURE = "culture"
    SAFETY = "safety"
    WEATHER = "weather"
    ENTRY = "visa"
    HEALTH = "health"
    PRACTICAL = "practical"


class ReadinessQuery(BaseModel):
    """One deterministic, bounded readiness search."""

    destination: str
    query: str = Field(min_length=3, max_length=500)
    topic: ReadinessEvidenceTopic
    search_topic: Literal["general", "news"] = "general"
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)

    @field_validator("destination")
    @classmethod
    def _normalise_destination(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("include_domains", "exclude_domains")
    @classmethod
    def _normalise_domains(cls, domains: list[str]) -> list[str]:
        return sorted(
            {
                domain.strip().lower().removeprefix("www.")
                for domain in domains
                if domain and domain.strip()
            }
        )


class ReadinessResearchPlan(BaseModel):
    destinations: list[str] = Field(default_factory=list)
    intent: ReadinessIntent = ReadinessIntent.OVERVIEW
    requested_topics: list[ReadinessTopic] = Field(default_factory=list)
    queries: list[ReadinessQuery] = Field(default_factory=list)
    clarification_question: str = ""

    @field_validator("destinations")
    @classmethod
    def _normalise_destinations(cls, values: list[str]) -> list[str]:
        return _normalised_destinations(values)


class ReadinessSource(BaseModel):
    """Normalized evidence stored in the public v2 readiness report."""

    id: str = ""
    title: str = "Untitled"
    url: str
    domain: str
    snippet: str = ""
    relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    query: str
    topic: ReadinessEvidenceTopic
    is_official: bool = False
    published_at: str | None = None
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class PlanningConstraint(BaseModel):
    """Sourced condition that later planning stages must account for."""

    category: Literal["safety", "entry", "health", "weather", "culture"]
    severity: Literal["info", "warning", "blocking"] = "info"
    summary: str
    destination: str = ""
    affected_dates: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class TravelReadinessReport(BaseModel):
    """Stable v2 readiness JSON consumed by API, frontend, and handbook."""

    destinations: list[str] = Field(default_factory=list)
    intent: ReadinessIntent = ReadinessIntent.OVERVIEW
    summary: str = ""
    safety: SafetyInfo = Field(default_factory=SafetyInfo)
    culture: CultureGuide = Field(default_factory=CultureGuide)
    weather: list[DayWeather] = Field(default_factory=list)
    weather_summary: list[str] = Field(default_factory=list)
    planning_constraints: list[PlanningConstraint] = Field(default_factory=list)
    packing_constraints: list[PackingItem] = Field(default_factory=list)
    sources: list[ReadinessSource] = Field(default_factory=list)
    citations: dict[str, list[str]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @field_validator("destinations")
    @classmethod
    def _normalise_report_destinations(cls, values: list[str]) -> list[str]:
        return _normalised_destinations(values)

    @model_validator(mode="after")
    def _validate_evidence_links(self) -> TravelReadinessReport:
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("readiness source IDs must be unique")
        known = set(source_ids)
        referenced = {
            source_id
            for ids in self.citations.values()
            for source_id in ids
        } | {
            source_id
            for constraint in self.planning_constraints
            for source_id in constraint.source_ids
        }
        invalid = referenced - known
        if invalid:
            raise ValueError(
                f"readiness evidence references unknown source IDs: {sorted(invalid)}"
            )
        return self

    @property
    def packing(self) -> list[PackingItem]:
        """Projection used by the existing handbook assembler."""
        return self.packing_constraints


class PreflightSafetySynthesis(BaseModel):
    """Only fields owned by the preflight safety stage."""

    model_config = ConfigDict(use_enum_values=True)

    advisory_level: AdvisoryLevel = AdvisoryLevel.UNKNOWN
    advisory_level_num: int = Field(default=0, ge=0, le=4)
    advisory_summary: str = ""
    seasonal_risks: list[str] = Field(default_factory=list)
    natural_hazards: list[str] = Field(default_factory=list)
    safety_tips: list[str] = Field(default_factory=list)


class TravelReadinessPreflightSynthesis(BaseModel):
    summary: str = ""
    safety: PreflightSafetySynthesis = Field(default_factory=PreflightSafetySynthesis)
    planning_constraints: list[PlanningConstraint] = Field(default_factory=list)
    citations: dict[str, list[str]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class DetailSafetySynthesis(BaseModel):
    """Readiness details that cannot overwrite advisory-owned fields."""

    visa_requirements: str = ""
    health_requirements: list[str] = Field(default_factory=list)
    emergency_numbers: dict[str, str] = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)
    currency_name: str = ""
    currency_symbol: str = ""
    currency_code: str = ""
    timezones: list[str] = Field(default_factory=list)
    embassy_info: str = ""


class TravelReadinessDetailsSynthesis(BaseModel):
    summary: str = ""
    safety: DetailSafetySynthesis = Field(default_factory=DetailSafetySynthesis)
    culture: CultureGuide = Field(default_factory=CultureGuide)
    weather_summary: list[str] = Field(default_factory=list)
    planning_constraints: list[PlanningConstraint] = Field(default_factory=list)
    packing_constraints: list[PackingItem] = Field(default_factory=list)
    citations: dict[str, list[str]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class TravelReadinessCombinedSynthesis(BaseModel):
    """One-call focused response with isolated stage-owned sections."""

    preflight: TravelReadinessPreflightSynthesis = Field(
        default_factory=TravelReadinessPreflightSynthesis
    )
    details: TravelReadinessDetailsSynthesis = Field(
        default_factory=TravelReadinessDetailsSynthesis
    )


class CoverageState(StrEnum):
    VERIFIED = "verified"
    MISSING = "missing"
    PROVIDER_FAILED = "provider_failed"


class TopicCoverage(BaseModel):
    destination: str
    topic: ReadinessTopic
    critical: bool = False
    state: CoverageState = CoverageState.MISSING
    source_ids: list[str] = Field(default_factory=list)
    error_category: ErrorCategory = ErrorCategory.NONE
    detail: str = ""


class TravelReadinessCoverage(BaseModel):
    """Per-destination/topic evidence status, separate from public report JSON."""

    items: list[TopicCoverage] = Field(default_factory=list)

    @property
    def missing_critical(self) -> list[TopicCoverage]:
        return [
            item
            for item in self.items
            if item.critical and item.state != CoverageState.VERIFIED
        ]

    @property
    def missing_optional(self) -> list[TopicCoverage]:
        return [
            item
            for item in self.items
            if not item.critical and item.state != CoverageState.VERIFIED
        ]

    @property
    def provider_failed_critical(self) -> list[TopicCoverage]:
        return [
            item
            for item in self.missing_critical
            if item.state == CoverageState.PROVIDER_FAILED
        ]


class TravelReadinessRun(BaseModel):
    report: TravelReadinessReport | None
    message: str
    clarification_question: str = ""
    missing_fields: list[str] = Field(default_factory=list)
    coverage: TravelReadinessCoverage = Field(default_factory=TravelReadinessCoverage)
    status: ComponentStatus = ComponentStatus.COMPLETED
    error_category: ErrorCategory = ErrorCategory.NONE
    request_fingerprint: str = ""


def _normalised_destinations(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalised = value.strip().lower()
        if normalised and normalised not in seen:
            seen.add(normalised)
            result.append(normalised)
    return result
