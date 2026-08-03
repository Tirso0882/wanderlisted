"""Canonical travel-readiness package."""

from src.readiness.assembly import (
    assemble_readiness_report,
    finalize_readiness_report,
)
from src.readiness.models import (
    CoverageState,
    DetailSafetySynthesis,
    PlanningConstraint,
    PreflightSafetySynthesis,
    ReadinessEvidenceTopic,
    ReadinessIntent,
    ReadinessQuery,
    ReadinessResearchPlan,
    ReadinessSource,
    TopicCoverage,
    TravelReadinessCombinedSynthesis,
    TravelReadinessCoverage,
    TravelReadinessDetailsSynthesis,
    TravelReadinessPreflightSynthesis,
    TravelReadinessReport,
    TravelReadinessRun,
)
from src.readiness.pipeline import TravelReadinessPipeline
from src.readiness.retrieval import (
    ReadinessEvidenceProvider,
    ReadinessQueryFailure,
    ReadinessRetrieval,
)
from src.readiness.weather import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
    WeatherResult,
)

__all__ = [
    "CoverageState",
    "DetailSafetySynthesis",
    "OpenMeteoWeatherProvider",
    "PlanningConstraint",
    "PreflightSafetySynthesis",
    "ReadinessEvidenceProvider",
    "ReadinessEvidenceTopic",
    "ReadinessIntent",
    "ReadinessQuery",
    "ReadinessQueryFailure",
    "ReadinessResearchPlan",
    "ReadinessRetrieval",
    "ReadinessSource",
    "TopicCoverage",
    "TravelReadinessCombinedSynthesis",
    "TravelReadinessCoverage",
    "TravelReadinessDetailsSynthesis",
    "TravelReadinessPipeline",
    "TravelReadinessPreflightSynthesis",
    "TravelReadinessReport",
    "TravelReadinessRun",
    "WeatherProviderError",
    "WeatherResult",
    "assemble_readiness_report",
    "finalize_readiness_report",
]
