"""Thin orchestration facade for the modular travel-readiness pipeline."""

from __future__ import annotations

import asyncio

from langchain_core.language_models.chat_models import BaseChatModel
from langsmith import trace

from src.models import ComponentStatus, ErrorCategory, ReadinessTopic, TripRequest
from src.readiness.assembly import (
    assemble_readiness_report,
    finalize_readiness_report,
)
from src.readiness.coverage import (
    build_coverage,
    coverage_limitations,
    coverage_outcome,
)
from src.readiness.grounding import ReadinessGrounder
from src.readiness.models import (
    ReadinessIntent,
    ReadinessResearchPlan,
    ReadinessSource,
    TravelReadinessCoverage,
    TravelReadinessReport,
    TravelReadinessRun,
)
from src.readiness.planning import (
    ReadinessPlanBuilder,
    readiness_request_fingerprint,
    requested_topics,
)
from src.readiness.rendering import render_markdown
from src.readiness.retrieval import (
    ReadinessEvidenceProvider,
    ReadinessRetrieval,
)
from src.readiness.synthesis import ReadinessSynthesizer
from src.readiness.weather import OpenMeteoWeatherProvider
from src.tools.tavily import normalize_url


class TravelReadinessPipeline:
    """Orchestrate planning, retrieval, synthesis, grounding, and assembly."""

    def __init__(
        self,
        *,
        synthesis_llm: BaseChatModel,
        provider: ReadinessEvidenceProvider,
        weather_provider: OpenMeteoWeatherProvider | None = None,
        max_queries: int = 6,
        official_sources: dict | None = None,
    ) -> None:
        self.provider = provider
        self.weather_provider = weather_provider or OpenMeteoWeatherProvider()
        self.planner = ReadinessPlanBuilder(
            max_queries=max_queries,
            official_sources=official_sources,
        )
        self.synthesizer = ReadinessSynthesizer(synthesis_llm)
        self.grounder = ReadinessGrounder(official_sources)

    async def preflight(
        self, *, question: str, trip_request: TripRequest
    ) -> TravelReadinessRun:
        """Require grounded official advisory evidence before the safety gate."""
        if not trip_request.destinations:
            return self._clarification("destinations")
        fingerprint_topics = requested_topics(question, trip_request) | {
            ReadinessTopic.SAFETY
        }
        fingerprint = readiness_request_fingerprint(trip_request, fingerprint_topics)
        if (
            ReadinessTopic.ENTRY in fingerprint_topics
            and not trip_request.passport_country
        ):
            return self._clarification("passport_country", fingerprint=fingerprint)

        plan = self._plan(
            question=question,
            trip_request=trip_request,
            topics={ReadinessTopic.SAFETY},
        )
        retrieval = await self._search(plan)
        if retrieval.sources:
            synthesis = await self.synthesizer.preflight(
                plan, question, trip_request, retrieval.sources
            )
            report = self.grounder.ground_preflight(plan, synthesis, retrieval.sources)
        else:
            report = TravelReadinessReport(
                destinations=plan.destinations,
                intent=ReadinessIntent.SAFETY,
                limitations=[
                    "No official travel-advisory evidence was available; "
                    "discovery was not started."
                ],
            )
        report = finalize_readiness_report(report)
        coverage = build_coverage(
            destinations=plan.destinations,
            topics={ReadinessTopic.SAFETY},
            report=report,
            retrieval=retrieval,
        )
        return self._complete_run(report, coverage, fingerprint)

    async def run(
        self, *, question: str, trip_request: TripRequest
    ) -> TravelReadinessRun:
        """Answer one focused readiness request within the existing call budget."""
        if not trip_request.destinations:
            return self._clarification("destinations")
        topics = requested_topics(question, trip_request)
        fingerprint = readiness_request_fingerprint(trip_request, topics)
        if ReadinessTopic.ENTRY in topics and not trip_request.passport_country:
            return self._clarification("passport_country", fingerprint=fingerprint)
        if not topics:
            report = TravelReadinessReport(
                destinations=trip_request.destinations,
                limitations=[
                    "ActivitiesAgent owns activities, attractions, dated events, "
                    "and hidden-gem discovery; no readiness search was run."
                ],
            )
            return self._complete_run(report, TravelReadinessCoverage(), fingerprint)

        weather = await self._weather(trip_request, topics)
        plan = self._plan(
            question=question,
            trip_request=trip_request,
            topics=topics,
            seasonal_weather=weather.seasonal_destinations,
        )
        retrieval = await self._search(plan)
        retrieval = _reserve_source_ids(retrieval, set())
        weather.assign_ids({source.id for source in retrieval.sources})
        sources = retrieval.sources

        has_safety = ReadinessTopic.SAFETY in topics
        has_details = bool(topics - {ReadinessTopic.SAFETY})
        if sources and has_safety and has_details:
            synthesis = await self.synthesizer.combined(
                plan, question, trip_request, sources
            )
            preflight = self.grounder.ground_preflight(
                plan, synthesis.preflight, sources
            )
            details = self.grounder.ground_details(
                plan,
                synthesis.details,
                sources,
                entry_domains=self.planner.entry_domains(trip_request),
            )
            details = weather.attach(details)
            report = assemble_readiness_report(preflight, details)
        elif sources and has_safety:
            synthesis = await self.synthesizer.preflight(
                plan, question, trip_request, sources
            )
            report = self.grounder.ground_preflight(plan, synthesis, sources)
            report = weather.attach(report)
        elif sources:
            synthesis = await self.synthesizer.details(
                plan, question, trip_request, sources
            )
            report = self.grounder.ground_details(
                plan,
                synthesis,
                sources,
                entry_domains=self.planner.entry_domains(trip_request),
            )
            report = weather.attach(report)
        else:
            report = weather.attach(
                TravelReadinessReport(
                    destinations=plan.destinations,
                    intent=plan.intent,
                )
            )
        report = finalize_readiness_report(report)
        coverage = build_coverage(
            destinations=plan.destinations,
            topics=topics,
            report=report,
            retrieval=retrieval,
            weather_source_ids=weather.source_ids,
            weather_failures=weather.failures,
        )
        return self._complete_run(report, coverage, fingerprint)

    async def run_details(
        self,
        *,
        question: str,
        trip_request: TripRequest,
        preflight_report: TravelReadinessReport | None = None,
        preflight_fingerprint: str = "",
    ) -> TravelReadinessRun:
        """Run post-gate details and immutably assemble the preflight report."""
        if not trip_request.destinations:
            return self._clarification("destinations")
        all_topics = requested_topics(question, trip_request) | {ReadinessTopic.SAFETY}
        fingerprint = readiness_request_fingerprint(trip_request, all_topics)
        topics = all_topics - {ReadinessTopic.SAFETY}
        if ReadinessTopic.ENTRY in topics and not trip_request.passport_country:
            return self._clarification("passport_country", fingerprint=fingerprint)
        if preflight_report is not None and preflight_fingerprint != fingerprint:
            return TravelReadinessRun(
                report=None,
                message=(
                    "The saved readiness preflight does not match the current "
                    "destinations, passport, dates, or topics and was rejected."
                ),
                status=ComponentStatus.STALE,
                error_category=ErrorCategory.VALIDATION,
                request_fingerprint=fingerprint,
            )
        if not topics:
            if preflight_report is None:
                empty = TravelReadinessReport(destinations=trip_request.destinations)
                return self._complete_run(empty, TravelReadinessCoverage(), fingerprint)
            return self._complete_run(
                preflight_report, TravelReadinessCoverage(), fingerprint
            )

        weather = await self._weather(trip_request, topics)
        plan = self._plan(
            question=question,
            trip_request=trip_request,
            topics=topics,
            seasonal_weather=weather.seasonal_destinations,
        )
        retrieval = await self._search(plan)
        reserved_ids = (
            {source.id for source in preflight_report.sources}
            if preflight_report
            else set()
        )
        retrieval = _reserve_source_ids(retrieval, reserved_ids)
        weather.assign_ids(reserved_ids | {source.id for source in retrieval.sources})

        if retrieval.sources:
            synthesis = await self.synthesizer.details(
                plan, question, trip_request, retrieval.sources
            )
            details = self.grounder.ground_details(
                plan,
                synthesis,
                retrieval.sources,
                entry_domains=self.planner.entry_domains(trip_request),
            )
        else:
            details = TravelReadinessReport(
                destinations=plan.destinations,
                intent=plan.intent,
            )
        details = finalize_readiness_report(weather.attach(details))
        report = (
            assemble_readiness_report(preflight_report, details)
            if preflight_report is not None
            else finalize_readiness_report(details)
        )
        coverage_retrieval = _align_retrieval_to_report(retrieval, report)
        coverage_weather_ids = weather.aligned_source_ids(report)
        coverage = build_coverage(
            destinations=plan.destinations,
            topics=topics,
            report=report,
            retrieval=coverage_retrieval,
            weather_source_ids=coverage_weather_ids,
            weather_failures=weather.failures,
        )
        report = report.model_copy(
            update={
                "limitations": list(
                    dict.fromkeys(
                        [*report.limitations, *coverage_limitations(coverage)]
                    )
                )
            },
            deep=True,
        )
        return self._complete_run(
            report,
            coverage,
            fingerprint,
            add_coverage_limitations=False,
        )

    def _plan(
        self,
        *,
        question: str,
        trip_request: TripRequest,
        topics: set[ReadinessTopic],
        seasonal_weather: set[str] | None = None,
    ) -> ReadinessResearchPlan:
        with trace(
            "readiness_query_plan",
            inputs={
                "question": question,
                "destinations": trip_request.destinations,
                "topics": sorted(topic.value for topic in topics),
            },
            tags=["readiness", "planning"],
        ) as span:
            plan = self.planner.build(
                question=question,
                trip_request=trip_request,
                topics=topics,
                seasonal_weather=seasonal_weather,
            )
            span.end(outputs=plan.model_dump(mode="json"))
        return plan

    async def _search(self, plan: ReadinessResearchPlan) -> ReadinessRetrieval:
        if not plan.queries:
            return ReadinessRetrieval()
        async with trace(
            "readiness_tavily_search",
            run_type="tool",
            inputs={
                "queries": [query.model_dump(mode="json") for query in plan.queries]
            },
            tags=["readiness", "tavily"],
        ) as span:
            result = await self.provider.search_many(plan.queries)
            span.end(outputs=result.model_dump(mode="json"))
        return result

    async def _weather(
        self, trip_request: TripRequest, topics: set[ReadinessTopic]
    ) -> _WeatherBatch:
        if ReadinessTopic.WEATHER not in topics:
            return _WeatherBatch()
        values = await asyncio.gather(
            *(
                self.weather_provider.forecast(destination, trip_request.date_window)
                for destination in trip_request.destinations
            ),
            return_exceptions=True,
        )
        batch = _WeatherBatch()
        for destination, value in zip(trip_request.destinations, values, strict=True):
            if isinstance(value, BaseException):
                batch.seasonal_destinations.add(destination)
                batch.failures[destination] = (
                    ErrorCategory.PROVIDER,
                    f"{type(value).__name__}: {value}",
                )
                batch.limitations.append(
                    f"Weather retrieval failed for {destination}; seasonal "
                    "evidence was attempted instead."
                )
                continue
            batch.weather.extend(value.daily)
            batch.limitations.extend(value.limitations)
            if value.source:
                batch.sources.append((destination, value.source))
            if not value.daily:
                batch.seasonal_destinations.add(destination)
        return batch

    def _complete_run(
        self,
        report: TravelReadinessReport,
        coverage: TravelReadinessCoverage,
        fingerprint: str,
        *,
        add_coverage_limitations: bool = True,
    ) -> TravelReadinessRun:
        if add_coverage_limitations:
            report = report.model_copy(
                update={
                    "limitations": list(
                        dict.fromkeys(
                            [*report.limitations, *coverage_limitations(coverage)]
                        )
                    )
                },
                deep=True,
            )
        report = TravelReadinessReport.model_validate(report.model_dump(mode="json"))
        status, error_category = coverage_outcome(coverage)
        with trace(
            "readiness_render",
            inputs={"report": report.model_dump(mode="json")},
            tags=["readiness", "render"],
        ) as span:
            message = render_markdown(report)
            span.end(outputs={"markdown": message})
        return TravelReadinessRun(
            report=report,
            message=message,
            coverage=coverage,
            status=status,
            error_category=error_category,
            request_fingerprint=fingerprint,
        )

    @staticmethod
    def _clarification(field: str, *, fingerprint: str = "") -> TravelReadinessRun:
        if field == "passport_country":
            text = "Which country issued the passport you will use for this trip?"
        else:
            text = "Which destination would you like me to check for travel readiness?"
        return TravelReadinessRun(
            report=None,
            message=text,
            clarification_question=text,
            status=ComponentStatus.NEEDS_USER_INPUT,
            missing_fields=[field],
            request_fingerprint=fingerprint,
        )

    # Stable rendering entry point retained as part of the readiness facade.
    render_markdown = staticmethod(render_markdown)


class _WeatherBatch:
    def __init__(self) -> None:
        self.weather = []
        self.sources: list[tuple[str, ReadinessSource]] = []
        self.source_ids: dict[str, list[str]] = {}
        self.limitations: list[str] = []
        self.seasonal_destinations: set[str] = set()
        self.failures: dict[str, tuple[ErrorCategory, str]] = {}

    def assign_ids(self, reserved_ids: set[str]) -> None:
        next_index = 1
        assigned: list[tuple[str, ReadinessSource]] = []
        for destination, source in self.sources:
            while f"W{next_index}" in reserved_ids:
                next_index += 1
            source_id = f"W{next_index}"
            reserved_ids.add(source_id)
            assigned_source = source.model_copy(update={"id": source_id})
            assigned.append((destination, assigned_source))
            self.source_ids.setdefault(destination, []).append(source_id)
            next_index += 1
        self.sources = assigned

    def attach(self, report: TravelReadinessReport) -> TravelReadinessReport:
        sources = [source for _, source in self.sources]
        citations = dict(report.citations)
        if sources and self.weather:
            citations["weather"] = [source.id for source in sources]
        return report.model_copy(
            update={
                "weather": list(self.weather),
                "sources": [*report.sources, *sources],
                "citations": citations,
                "limitations": list(
                    dict.fromkeys([*report.limitations, *self.limitations])
                ),
            },
            deep=True,
        )

    def aligned_source_ids(self, report: TravelReadinessReport) -> dict[str, list[str]]:
        mapping = _canonical_id_map([source for _, source in self.sources], report)
        return {
            destination: [
                mapping[source_id] for source_id in source_ids if source_id in mapping
            ]
            for destination, source_ids in self.source_ids.items()
        }


def _reserve_source_ids(
    retrieval: ReadinessRetrieval, reserved_ids: set[str]
) -> ReadinessRetrieval:
    mapping: dict[str, str] = {}
    sources: list[ReadinessSource] = []
    next_index = 1
    for source in retrieval.sources:
        while f"S{next_index}" in reserved_ids:
            next_index += 1
        source_id = f"S{next_index}"
        reserved_ids.add(source_id)
        mapping[source.id] = source_id
        sources.append(source.model_copy(update={"id": source_id}))
        next_index += 1
    return retrieval.model_copy(
        update={
            "sources": sources,
            "evidence_by_scope": {
                scope: [mapping[source_id] for source_id in source_ids]
                for scope, source_ids in retrieval.evidence_by_scope.items()
            },
            "official_evidence_by_scope": {
                scope: [mapping[source_id] for source_id in source_ids]
                for scope, source_ids in retrieval.official_evidence_by_scope.items()
            },
        },
        deep=True,
    )


def _align_retrieval_to_report(
    retrieval: ReadinessRetrieval,
    report: TravelReadinessReport,
) -> ReadinessRetrieval:
    mapping = _canonical_id_map(retrieval.sources, report)
    sources_by_id = {source.id: source for source in retrieval.sources}
    aligned_sources: list[ReadinessSource] = []
    seen: set[str] = set()
    for source_id, canonical_id in mapping.items():
        if canonical_id in seen:
            continue
        seen.add(canonical_id)
        aligned_sources.append(
            sources_by_id[source_id].model_copy(update={"id": canonical_id})
        )

    def remap(scopes: dict[str, list[str]]) -> dict[str, list[str]]:
        return {
            scope: list(
                dict.fromkeys(
                    mapping[source_id]
                    for source_id in source_ids
                    if source_id in mapping
                )
            )
            for scope, source_ids in scopes.items()
        }

    return retrieval.model_copy(
        update={
            "sources": aligned_sources,
            "evidence_by_scope": remap(retrieval.evidence_by_scope),
            "official_evidence_by_scope": remap(retrieval.official_evidence_by_scope),
        },
        deep=True,
    )


def _canonical_id_map(
    sources: list[ReadinessSource],
    report: TravelReadinessReport,
) -> dict[str, str]:
    canonical_by_url = {
        normalize_url(source.url): source.id for source in report.sources
    }
    return {
        source.id: canonical_by_url[normalize_url(source.url)]
        for source in sources
        if normalize_url(source.url) in canonical_by_url
    }
