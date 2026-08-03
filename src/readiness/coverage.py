"""Explicit per-destination/topic readiness coverage and outcome policy."""

from __future__ import annotations

from src.models import (
    AdvisoryLevel,
    ComponentStatus,
    ErrorCategory,
    ReadinessTopic,
)
from src.readiness.models import (
    CoverageState,
    TopicCoverage,
    TravelReadinessCoverage,
    TravelReadinessReport,
)
from src.readiness.retrieval import ReadinessRetrieval

_CRITICAL_TOPICS = {
    ReadinessTopic.SAFETY,
    ReadinessTopic.ENTRY,
    ReadinessTopic.HEALTH,
}


def build_coverage(
    *,
    destinations: list[str],
    topics: set[ReadinessTopic],
    report: TravelReadinessReport,
    retrieval: ReadinessRetrieval,
    weather_source_ids: dict[str, list[str]] | None = None,
    weather_failures: dict[str, tuple[ErrorCategory, str]] | None = None,
) -> TravelReadinessCoverage:
    weather_source_ids = weather_source_ids or {}
    weather_failures = weather_failures or {}
    report_ids = {source.id for source in report.sources}
    items: list[TopicCoverage] = []

    for destination in destinations:
        for topic in sorted(topics, key=lambda item: item.value):
            candidates = (
                _candidate_ids(retrieval, destination, topic, weather_source_ids)
                & report_ids
            )
            cited = _cited_ids(report, topic)
            grounded_ids = sorted(candidates & cited)
            verified = _has_grounded_value(report, topic) and bool(grounded_ids)
            if topic in _CRITICAL_TOPICS:
                official_ids = set(
                    retrieval.official_source_ids_for(destination, topic)
                )
                verified = verified and set(grounded_ids) <= official_ids

            matching_failures = [
                failure
                for failure in retrieval.failures
                if failure.destination == destination
                and _readiness_topic(failure.topic.value) == topic
            ]
            weather_failure = weather_failures.get(destination)
            if verified:
                state = CoverageState.VERIFIED
                error_category = ErrorCategory.NONE
                detail = ""
            elif matching_failures:
                failure = matching_failures[0]
                state = CoverageState.PROVIDER_FAILED
                error_category = failure.error_category
                detail = failure.detail
            elif topic == ReadinessTopic.WEATHER and weather_failure:
                state = CoverageState.PROVIDER_FAILED
                error_category, detail = weather_failure
            else:
                state = CoverageState.MISSING
                error_category = ErrorCategory.NONE
                detail = "No grounded field-matching evidence was retained."
            items.append(
                TopicCoverage(
                    destination=destination,
                    topic=topic,
                    critical=topic in _CRITICAL_TOPICS,
                    state=state,
                    source_ids=grounded_ids,
                    error_category=error_category,
                    detail=detail,
                )
            )
    return TravelReadinessCoverage(items=items)


def coverage_outcome(
    coverage: TravelReadinessCoverage,
) -> tuple[ComponentStatus, ErrorCategory]:
    if coverage.provider_failed_critical:
        category = next(
            (
                item.error_category
                for item in coverage.provider_failed_critical
                if item.error_category != ErrorCategory.NONE
            ),
            ErrorCategory.PROVIDER,
        )
        return ComponentStatus.BLOCKED_EXTERNAL, category
    if coverage.missing_critical:
        return ComponentStatus.NO_INVENTORY, ErrorCategory.NONE
    return ComponentStatus.COMPLETED, ErrorCategory.NONE


def coverage_limitations(coverage: TravelReadinessCoverage) -> list[str]:
    limitations: list[str] = []
    for item in coverage.items:
        if item.state == CoverageState.VERIFIED:
            continue
        severity = "Critical" if item.critical else "Optional"
        limitations.append(
            f"{severity} {item.topic.value} evidence for {item.destination} "
            f"is {item.state.value.replace('_', ' ')}."
        )
    return limitations


def _candidate_ids(
    retrieval: ReadinessRetrieval,
    destination: str,
    topic: ReadinessTopic,
    weather_source_ids: dict[str, list[str]],
) -> set[str]:
    if topic == ReadinessTopic.WEATHER:
        return set(retrieval.source_ids_for(destination, topic)) | set(
            weather_source_ids.get(destination, [])
        )
    if topic in {ReadinessTopic.CULTURE, ReadinessTopic.PRACTICAL}:
        return set(retrieval.source_ids_for(destination, ReadinessTopic.CULTURE))
    if topic == ReadinessTopic.PACKING:
        candidates: set[str] = set(weather_source_ids.get(destination, []))
        for evidence_topic in (
            ReadinessTopic.CULTURE,
            ReadinessTopic.HEALTH,
            ReadinessTopic.ENTRY,
            ReadinessTopic.WEATHER,
        ):
            candidates.update(retrieval.source_ids_for(destination, evidence_topic))
        return candidates
    return set(retrieval.source_ids_for(destination, topic))


def _cited_ids(report: TravelReadinessReport, topic: ReadinessTopic) -> set[str]:
    prefixes: dict[ReadinessTopic, tuple[str, ...]] = {
        ReadinessTopic.SAFETY: (
            "safety.advisory_level",
            "safety.advisory_summary",
        ),
        ReadinessTopic.ENTRY: ("safety.visa_requirements",),
        ReadinessTopic.HEALTH: ("safety.health_requirements",),
        ReadinessTopic.WEATHER: ("weather", "weather_summary"),
        ReadinessTopic.CULTURE: ("culture.",),
        ReadinessTopic.PRACTICAL: (
            "safety.emergency_numbers",
            "safety.languages",
            "safety.currency_",
            "safety.timezones",
            "safety.embassy_info",
        ),
        ReadinessTopic.PACKING: ("packing_constraints",),
    }
    return {
        source_id
        for path, source_ids in report.citations.items()
        if any(path == prefix or path.startswith(prefix) for prefix in prefixes[topic])
        for source_id in source_ids
    }


def _has_grounded_value(report: TravelReadinessReport, topic: ReadinessTopic) -> bool:
    safety = report.safety
    if topic == ReadinessTopic.SAFETY:
        return safety.advisory_level != AdvisoryLevel.UNKNOWN and bool(
            safety.advisory_summary
        )
    if topic == ReadinessTopic.ENTRY:
        return bool(safety.visa_requirements)
    if topic == ReadinessTopic.HEALTH:
        return bool(safety.health_requirements)
    if topic == ReadinessTopic.WEATHER:
        return bool(report.weather or report.weather_summary)
    if topic == ReadinessTopic.CULTURE:
        return any(
            bool(getattr(report.culture, field))
            for field in type(report.culture).model_fields
            if field not in {"festivals", "food_specialties", "music_and_arts"}
        )
    if topic == ReadinessTopic.PRACTICAL:
        return any(
            (
                safety.emergency_numbers,
                safety.languages,
                safety.currency_name,
                safety.currency_code,
                safety.timezones,
                safety.embassy_info,
            )
        )
    return bool(report.packing_constraints)


def _readiness_topic(value: str) -> ReadinessTopic:
    return ReadinessTopic.ENTRY if value == "visa" else ReadinessTopic(value)
