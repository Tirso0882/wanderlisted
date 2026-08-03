"""Pure, immutable assembly of preflight and detail readiness reports."""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel

from src.models import SafetyInfo
from src.readiness.models import (
    PlanningConstraint,
    ReadinessSource,
    TravelReadinessReport,
)
from src.tools.tavily import normalize_url

_PREFLIGHT_SAFETY_FIELDS = (
    "advisory_level",
    "advisory_level_num",
    "advisory_summary",
    "seasonal_risks",
    "natural_hazards",
    "safety_tips",
)

_DETAIL_SAFETY_FIELDS = (
    "visa_requirements",
    "health_requirements",
    "emergency_numbers",
    "languages",
    "currency_name",
    "currency_symbol",
    "currency_code",
    "timezones",
    "embassy_info",
)

_PATH_PART = re.compile(r"^(?P<name>[^\[]+)?(?P<indexes>(?:\[\d+\])*)$")
_INDEX = re.compile(r"\[(\d+)\]")
_MISSING = object()


def assemble_readiness_report(
    preflight: TravelReadinessReport,
    details: TravelReadinessReport,
) -> TravelReadinessReport:
    """Combine stage-owned fields without mutating either input report."""
    preflight_copy = preflight.model_copy(deep=True)
    details_copy = details.model_copy(deep=True)
    if preflight_copy.destinations != details_copy.destinations:
        raise ValueError(
            "preflight and details destinations must match exactly: "
            f"{preflight_copy.destinations!r} != {details_copy.destinations!r}"
        )

    sources, preflight_ids, detail_ids = _merge_sources(
        preflight_copy.sources, details_copy.sources
    )
    known_ids = {source.id for source in sources}

    safety_payload = {
        field: getattr(preflight_copy.safety, field)
        for field in _PREFLIGHT_SAFETY_FIELDS
    }
    safety_payload.update(
        {field: getattr(details_copy.safety, field) for field in _DETAIL_SAFETY_FIELDS}
    )

    constraints, preflight_constraint_indexes, detail_constraint_indexes = (
        _merge_constraints(
            preflight_copy.planning_constraints,
            details_copy.planning_constraints,
            preflight_ids,
            detail_ids,
            known_ids,
        )
    )
    summaries = _unique_nonempty([preflight_copy.summary, details_copy.summary])
    report = TravelReadinessReport(
        destinations=details_copy.destinations,
        intent=details_copy.intent,
        summary="\n\n".join(summaries),
        safety=SafetyInfo.model_validate(safety_payload),
        culture=details_copy.culture,
        weather=details_copy.weather,
        weather_summary=details_copy.weather_summary,
        planning_constraints=constraints,
        packing_constraints=details_copy.packing_constraints,
        sources=sources,
        limitations=_unique_nonempty(
            [*preflight_copy.limitations, *details_copy.limitations]
        ),
        generated_at=details_copy.generated_at,
    )

    citations: dict[str, list[str]] = {}
    _copy_owned_citations(
        citations,
        preflight_copy.citations,
        preflight_ids,
        owner="preflight",
    )
    _copy_owned_citations(
        citations,
        details_copy.citations,
        detail_ids,
        owner="details",
    )
    for old_index, new_index in preflight_constraint_indexes.items():
        source_ids = constraints[new_index].source_ids
        if source_ids:
            citations[f"planning_constraints[{new_index}]"] = source_ids
    for old_index, new_index in detail_constraint_indexes.items():
        source_ids = constraints[new_index].source_ids
        if source_ids:
            citations[f"planning_constraints[{new_index}]"] = source_ids

    # A merged summary preserves both stage summaries and both citation sets.
    summary_ids = _remap_ids(preflight_copy.citations.get("summary", []), preflight_ids)
    summary_ids.extend(
        _remap_ids(details_copy.citations.get("summary", []), detail_ids)
    )
    summary_ids = _known_unique(summary_ids, known_ids)
    if report.summary and summary_ids:
        citations["summary"] = summary_ids

    report.citations = {
        path: _known_unique(ids, known_ids)
        for path, ids in citations.items()
        if _path_has_value(report, path) and _known_unique(ids, known_ids)
    }
    return finalize_readiness_report(report)


def finalize_readiness_report(
    report: TravelReadinessReport,
) -> TravelReadinessReport:
    """Prune non-field citations and unused sources, then revalidate v2 JSON."""
    finalized = report.model_copy(deep=True)
    known_ids = {source.id for source in finalized.sources}
    finalized.citations = {
        path: _known_unique(ids, known_ids)
        for path, ids in finalized.citations.items()
        if _path_has_value(finalized, path) and _known_unique(ids, known_ids)
    }
    used_ids = {
        source_id
        for ids in finalized.citations.values()
        for source_id in ids
    } | {
        source_id
        for constraint in finalized.planning_constraints
        for source_id in constraint.source_ids
    }
    finalized.sources = [
        source for source in finalized.sources if source.id in used_ids
    ]
    # Re-parse instead of trusting assignment validation, ensuring the assembled
    # report satisfies the same public model boundary as an API payload.
    return TravelReadinessReport.model_validate(finalized.model_dump(mode="json"))


def _merge_sources(
    preflight_sources: list[ReadinessSource],
    detail_sources: list[ReadinessSource],
) -> tuple[list[ReadinessSource], dict[str, str], dict[str, str]]:
    merged: list[ReadinessSource] = []
    id_to_url: dict[str, str] = {}
    url_to_id: dict[str, str] = {}
    mappings: list[dict[str, str]] = []

    for stage_sources in (preflight_sources, detail_sources):
        mapping: dict[str, str] = {}
        for source in stage_sources:
            normalized_url = normalize_url(source.url)
            previous_url = id_to_url.get(source.id)
            if previous_url is not None and previous_url != normalized_url:
                raise ValueError(
                    f"source ID {source.id!r} refers to conflicting URLs"
                )
            canonical_id = url_to_id.get(normalized_url)
            if canonical_id is None:
                canonical_id = source.id
                id_to_url[source.id] = normalized_url
                url_to_id[normalized_url] = source.id
                merged.append(source.model_copy(deep=True))
            else:
                id_to_url.setdefault(source.id, normalized_url)
            mapping[source.id] = canonical_id
        mappings.append(mapping)
    return merged, mappings[0], mappings[1]


def _merge_constraints(
    preflight_constraints: list[PlanningConstraint],
    detail_constraints: list[PlanningConstraint],
    preflight_ids: dict[str, str],
    detail_ids: dict[str, str],
    known_ids: set[str],
) -> tuple[list[PlanningConstraint], dict[int, int], dict[int, int]]:
    merged: list[PlanningConstraint] = []
    seen: dict[tuple, int] = {}
    index_maps: list[dict[int, int]] = []
    for constraints, id_map in (
        (preflight_constraints, preflight_ids),
        (detail_constraints, detail_ids),
    ):
        index_map: dict[int, int] = {}
        for old_index, constraint in enumerate(constraints):
            source_ids = _known_unique(
                _remap_ids(constraint.source_ids, id_map), known_ids
            )
            if not source_ids:
                continue
            signature = (
                constraint.category,
                constraint.severity,
                constraint.summary.strip(),
                constraint.destination.strip().lower(),
                tuple(constraint.affected_dates),
            )
            existing_index = seen.get(signature)
            if existing_index is not None:
                current = merged[existing_index]
                current.source_ids = _known_unique(
                    [*current.source_ids, *source_ids], known_ids
                )
                index_map[old_index] = existing_index
                continue
            new_index = len(merged)
            merged.append(
                constraint.model_copy(update={"source_ids": source_ids}, deep=True)
            )
            seen[signature] = new_index
            index_map[old_index] = new_index
        index_maps.append(index_map)
    return merged, index_maps[0], index_maps[1]


def _copy_owned_citations(
    target: dict[str, list[str]],
    source: dict[str, list[str]],
    id_map: dict[str, str],
    *,
    owner: str,
) -> None:
    for path, source_ids in source.items():
        if path == "summary" or path.startswith("planning_constraints"):
            continue
        if owner == "preflight" and not _preflight_owns(path):
            continue
        if owner == "details" and not _details_owns(path):
            continue
        remapped = _remap_ids(source_ids, id_map)
        if remapped:
            target[path] = list(dict.fromkeys([*target.get(path, []), *remapped]))


def _preflight_owns(path: str) -> bool:
    return any(path == f"safety.{field}" or path.startswith(f"safety.{field}[")
               for field in _PREFLIGHT_SAFETY_FIELDS)


def _details_owns(path: str) -> bool:
    if any(path == f"safety.{field}" or path.startswith(f"safety.{field}")
           for field in _DETAIL_SAFETY_FIELDS):
        return True
    return path == "weather" or path.startswith(
        ("weather[", "weather_summary", "culture.", "packing_constraints")
    )


def _remap_ids(source_ids: Iterable[str], mapping: dict[str, str]) -> list[str]:
    return [mapping[source_id] for source_id in source_ids if source_id in mapping]


def _known_unique(source_ids: Iterable[str], known_ids: set[str]) -> list[str]:
    return list(dict.fromkeys(source_id for source_id in source_ids if source_id in known_ids))


def _unique_nonempty(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _path_has_value(report: TravelReadinessReport, path: str) -> bool:
    value: object = report
    for part in path.split("."):
        match = _PATH_PART.fullmatch(part)
        if match is None:
            return False
        name = match.group("name") or ""
        if name:
            if isinstance(value, BaseModel):
                value = getattr(value, name, _MISSING)
            elif isinstance(value, dict):
                value = value.get(name, _MISSING)
            else:
                return False
        if value is _MISSING:
            return False
        for index_text in _INDEX.findall(match.group("indexes")):
            if not isinstance(value, (list, tuple)):
                return False
            index = int(index_text)
            if index >= len(value):
                return False
            value = value[index]
    if value is _MISSING or value is None:
        return False
    if isinstance(value, (str, bytes, list, tuple, dict, set, frozenset)):
        return bool(value)
    # Numeric zero and False can be legitimate, cited values (for example a
    # 0% rain probability); they are not orphaned merely because they are falsy.
    return True
