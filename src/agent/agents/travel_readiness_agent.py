"""Adapter for the fixed travel-readiness research pipeline."""

from langchain_core.language_models.chat_models import BaseChatModel

import config as app_config

from src.agent.llm import get_llm
from src.models import TripRequest
from src.readiness import (
    OpenMeteoWeatherProvider,
    ReadinessEvidenceProvider,
    TravelReadinessPipeline,
    TravelReadinessReport,
    TravelReadinessRun,
)


class TravelReadinessAgent:
    """Evidence-grounded safety, weather, entry, health, and cultural guidance."""

    name = "TravelReadinessAgent"
    description = (
        "Evidence-grounded safety, entry, health, weather, culture, and "
        "practical preparation guidance; never place discovery"
    )

    def __init__(
        self,
        synthesis_llm: BaseChatModel | None = None,
        *,
        provider: ReadinessEvidenceProvider | None = None,
        weather_provider: OpenMeteoWeatherProvider | None = None,
    ) -> None:
        self.synthesis_llm = synthesis_llm or get_llm(tier="reasoning")
        readiness_config = app_config.get("travel_readiness") or {}
        official_sources = readiness_config.get("official_sources", {})
        self.provider = provider or ReadinessEvidenceProvider(
            timeout_seconds=readiness_config.get("timeout_seconds", 15),
            max_results=readiness_config.get("max_results_per_query", 5),
            concurrency=readiness_config.get("concurrency", 4),
            max_retries=readiness_config.get("max_retries", 3),
            cache_ttl_seconds=readiness_config.get("cache_ttl_seconds", 21600),
            cache_max_size=readiness_config.get("cache_max_size", 200),
            official_sources=official_sources,
        )
        weather_config = readiness_config.get("weather", {})
        self.weather_provider = weather_provider or OpenMeteoWeatherProvider(
            timeout_seconds=weather_config.get("timeout_seconds", 10),
            max_retries=weather_config.get("max_retries", 2),
            forecast_horizon_days=weather_config.get("forecast_horizon_days", 16),
            cache_ttl_seconds=weather_config.get("cache_ttl_seconds", 3600),
        )
        self.pipeline = TravelReadinessPipeline(
            synthesis_llm=self.synthesis_llm,
            provider=self.provider,
            weather_provider=self.weather_provider,
            max_queries=readiness_config.get("max_queries", 6),
            official_sources=official_sources,
        )

    async def preflight(
        self, *, question: str, trip_request: TripRequest
    ) -> TravelReadinessRun:
        return await self.pipeline.preflight(
            question=question, trip_request=trip_request
        )

    async def research(
        self, *, question: str, trip_request: TripRequest
    ) -> TravelReadinessRun:
        return await self.pipeline.run(question=question, trip_request=trip_request)

    async def research_details(
        self,
        *,
        question: str,
        trip_request: TripRequest,
        preflight_report: TravelReadinessReport | None = None,
        preflight_fingerprint: str = "",
    ) -> TravelReadinessRun:
        return await self.pipeline.run_details(
            question=question,
            trip_request=trip_request,
            preflight_report=preflight_report,
            preflight_fingerprint=preflight_fingerprint,
        )

    async def aclose(self) -> None:
        """Close provider clients when the owning process or evaluation exits."""
        await self.provider.aclose()
        await self.weather_provider.aclose()

    def __repr__(self) -> str:
        return "TravelReadinessAgent(pipeline=tavily+open-meteo)"
