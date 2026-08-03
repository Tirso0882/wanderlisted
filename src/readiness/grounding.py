"""Deterministic field-level evidence grounding for readiness synthesis."""

from __future__ import annotations

from typing import Any

from src.models import AdvisoryLevel, SafetyInfo
from src.readiness.models import (
    PlanningConstraint,
    ReadinessEvidenceTopic,
    ReadinessResearchPlan,
    ReadinessSource,
    TravelReadinessDetailsSynthesis,
    TravelReadinessPreflightSynthesis,
    TravelReadinessReport,
)
from src.readiness.retrieval import (
    build_official_source_policy,
    is_official_domain,
)


class _GroundingContext:
    def __init__(
        self,
        *,
        sources: list[ReadinessSource],
        citations: dict[str, list[str]],
        limitations: list[str],
    ) -> None:
        self.sources = sources
        self.known = {source.id for source in sources}
        self.source_by_id = {source.id: source for source in sources}
        self.raw_citations = {
            path: list(
                dict.fromkeys(source_id for source_id in ids if source_id in self.known)
            )
            for path, ids in citations.items()
        }
        self.citations: dict[str, list[str]] = {}
        self.limitations = list(limitations)

    def ids_for(self, path: str) -> list[str]:
        return self.raw_citations.get(path, [])

    def child_ids(self, path: str) -> list[str]:
        source_ids: list[str] = []
        for citation_path, ids in self.raw_citations.items():
            if citation_path == path or citation_path.startswith(f"{path}."):
                source_ids.extend(ids)
        return list(dict.fromkeys(source_ids))

    def record(self, path: str, source_ids: list[str]) -> None:
        if source_ids:
            self.citations[path] = list(
                dict.fromkeys([*self.citations.get(path, []), *source_ids])
            )

    def official(self, source_ids: list[str], allowed: list[str] | None = None) -> bool:
        if not source_ids:
            return False
        cited = [self.source_by_id[source_id] for source_id in source_ids]
        if allowed is not None:
            return bool(allowed) and all(
                is_official_domain(source.domain, allowed) for source in cited
            )
        return all(source.is_official for source in cited)

    def supported(
        self,
        source_ids: list[str],
        *,
        official_domains: list[str] | None = None,
        require_official: bool = False,
        allowed_topics: set[ReadinessEvidenceTopic] | None = None,
    ) -> bool:
        if not source_ids:
            return False
        if allowed_topics is not None and any(
            self.source_by_id[source_id].topic not in allowed_topics
            for source_id in source_ids
        ):
            return False
        if official_domains is not None or require_official:
            return self.official(source_ids, official_domains)
        return True

    def ground_field(
        self,
        model: Any,
        prefix: str,
        field: str,
        *,
        official_domains: list[str] | None = None,
        require_official: bool = False,
        allowed_topics: set[ReadinessEvidenceTopic] | None = None,
    ) -> None:
        value = getattr(model, field)
        if not value:
            return
        path = f"{prefix}.{field}" if prefix else field
        aggregate_ids = self.ids_for(path)

        if isinstance(value, list):
            retained = []
            retained_ids: list[str] = []
            for old_index, item in enumerate(value):
                old_path = f"{path}[{old_index}]"
                item_ids = self.child_ids(old_path) or aggregate_ids
                if not self.supported(
                    item_ids,
                    official_domains=official_domains,
                    require_official=require_official,
                    allowed_topics=allowed_topics,
                ):
                    continue
                new_path = f"{path}[{len(retained)}]"
                retained.append(item)
                retained_ids.extend(item_ids)
                self.record(new_path, item_ids)
            setattr(model, field, retained)
            self.record(path, retained_ids)
            if not retained:
                self.limitations.append(
                    f"{path.replace('_', ' ').title()} lacked verified evidence."
                )
            elif len(retained) != len(value):
                self.limitations.append(
                    f"Some {path.replace('_', ' ')} entries lacked verified "
                    "evidence and were omitted."
                )
            return

        if isinstance(value, dict):
            retained = {}
            retained_ids: list[str] = []
            for key, item in value.items():
                item_path = f"{path}.{key}"
                item_ids = self.child_ids(item_path) or aggregate_ids
                if not self.supported(
                    item_ids,
                    official_domains=official_domains,
                    require_official=require_official,
                    allowed_topics=allowed_topics,
                ):
                    continue
                retained[key] = item
                retained_ids.extend(item_ids)
                self.record(item_path, item_ids)
            setattr(model, field, retained)
            self.record(path, retained_ids)
            if not retained:
                self.limitations.append(
                    f"{path.replace('_', ' ').title()} lacked verified evidence."
                )
            elif len(retained) != len(value):
                self.limitations.append(
                    f"Some {path.replace('_', ' ')} entries lacked verified "
                    "evidence and were omitted."
                )
            return

        if self.supported(
            aggregate_ids,
            official_domains=official_domains,
            require_official=require_official,
            allowed_topics=allowed_topics,
        ):
            self.record(path, aggregate_ids)
        else:
            _reset(model, field)
            self.limitations.append(
                f"{path.replace('_', ' ').title()} lacked verified evidence."
            )


class ReadinessGrounder:
    def __init__(self, official_sources: dict | None = None) -> None:
        self.official_sources = build_official_source_policy(official_sources)

    def ground_preflight(
        self,
        plan: ReadinessResearchPlan,
        synthesis: TravelReadinessPreflightSynthesis,
        sources: list[ReadinessSource],
    ) -> TravelReadinessReport:
        context = _GroundingContext(
            sources=sources,
            citations=synthesis.citations,
            limitations=synthesis.limitations,
        )
        safety = SafetyInfo.model_validate(synthesis.safety.model_dump())
        if safety.advisory_level != AdvisoryLevel.UNKNOWN:
            advisory_ids = context.ids_for("safety.advisory_level")
            if context.supported(
                advisory_ids,
                require_official=True,
                allowed_topics={ReadinessEvidenceTopic.SAFETY},
            ):
                context.record("safety.advisory_level", advisory_ids)
            else:
                safety.advisory_level = AdvisoryLevel.UNKNOWN
                safety.advisory_level_num = 0
                context.limitations.append(
                    "Travel advisory level lacked official evidence."
                )
        for field in (
            "advisory_summary",
            "seasonal_risks",
            "natural_hazards",
            "safety_tips",
        ):
            context.ground_field(
                safety,
                "safety",
                field,
                require_official=True,
                allowed_topics={ReadinessEvidenceTopic.SAFETY},
            )

        summary = _ground_summary(context, synthesis.summary)
        constraints = self._ground_constraints(
            context,
            synthesis.planning_constraints,
            allowed_categories={"safety"},
        )
        return TravelReadinessReport(
            destinations=plan.destinations,
            intent=plan.intent,
            summary=summary,
            safety=safety,
            planning_constraints=constraints,
            sources=sources,
            citations=context.citations,
            limitations=list(dict.fromkeys(context.limitations)),
        )

    def ground_details(
        self,
        plan: ReadinessResearchPlan,
        synthesis: TravelReadinessDetailsSynthesis,
        sources: list[ReadinessSource],
        *,
        entry_domains: list[str],
    ) -> TravelReadinessReport:
        context = _GroundingContext(
            sources=sources,
            citations=synthesis.citations,
            limitations=synthesis.limitations,
        )
        safety = SafetyInfo.model_validate(synthesis.safety.model_dump())
        for field in (
            "languages",
            "currency_name",
            "currency_symbol",
            "currency_code",
            "timezones",
        ):
            context.ground_field(
                safety,
                "safety",
                field,
                allowed_topics={
                    ReadinessEvidenceTopic.CULTURE,
                    ReadinessEvidenceTopic.PRACTICAL,
                },
            )
        context.ground_field(
            safety,
            "safety",
            "visa_requirements",
            official_domains=entry_domains,
            allowed_topics={ReadinessEvidenceTopic.ENTRY},
        )
        context.ground_field(
            safety,
            "safety",
            "health_requirements",
            official_domains=self.official_sources["health"],
            allowed_topics={ReadinessEvidenceTopic.HEALTH},
        )
        context.ground_field(
            safety,
            "safety",
            "emergency_numbers",
            official_domains=self.official_sources["emergency"],
            allowed_topics={
                ReadinessEvidenceTopic.CULTURE,
                ReadinessEvidenceTopic.PRACTICAL,
            },
        )
        context.ground_field(
            safety,
            "safety",
            "embassy_info",
            official_domains=self.official_sources["emergency"],
            allowed_topics={
                ReadinessEvidenceTopic.CULTURE,
                ReadinessEvidenceTopic.PRACTICAL,
            },
        )

        culture = synthesis.culture.model_copy(deep=True)
        for field in ("festivals", "food_specialties", "music_and_arts"):
            _reset(culture, field)
        for field in type(culture).model_fields:
            if field not in {"festivals", "food_specialties", "music_and_arts"}:
                context.ground_field(
                    culture,
                    "culture",
                    field,
                    allowed_topics={ReadinessEvidenceTopic.CULTURE},
                )

        top_level = synthesis.model_copy(deep=True)
        context.ground_field(
            top_level,
            "",
            "weather_summary",
            allowed_topics={ReadinessEvidenceTopic.WEATHER},
        )
        context.ground_field(
            top_level,
            "",
            "packing_constraints",
            allowed_topics={
                ReadinessEvidenceTopic.CULTURE,
                ReadinessEvidenceTopic.ENTRY,
                ReadinessEvidenceTopic.HEALTH,
                ReadinessEvidenceTopic.WEATHER,
            },
        )
        summary = _ground_summary(context, synthesis.summary)
        constraints = self._ground_constraints(
            context,
            synthesis.planning_constraints,
            allowed_categories={"entry", "health", "weather", "culture"},
            entry_domains=entry_domains,
        )
        return TravelReadinessReport(
            destinations=plan.destinations,
            intent=plan.intent,
            summary=summary,
            safety=safety,
            culture=culture,
            weather_summary=top_level.weather_summary,
            planning_constraints=constraints,
            packing_constraints=top_level.packing_constraints,
            sources=sources,
            citations=context.citations,
            limitations=list(dict.fromkeys(context.limitations)),
        )

    def _ground_constraints(
        self,
        context: _GroundingContext,
        constraints: list[PlanningConstraint],
        *,
        allowed_categories: set[str],
        entry_domains: list[str] | None = None,
    ) -> list[PlanningConstraint]:
        grounded: list[PlanningConstraint] = []
        for constraint in constraints:
            if constraint.category not in allowed_categories:
                continue
            valid_ids = [
                source_id
                for source_id in constraint.source_ids
                if source_id in context.known
            ]
            if not valid_ids:
                context.limitations.append(
                    "A planning constraint lacked source citations."
                )
                continue
            expected_topics = {
                "safety": {ReadinessEvidenceTopic.SAFETY},
                "entry": {ReadinessEvidenceTopic.ENTRY},
                "health": {ReadinessEvidenceTopic.HEALTH},
                "weather": {ReadinessEvidenceTopic.WEATHER},
                "culture": {ReadinessEvidenceTopic.CULTURE},
            }[constraint.category]
            if not context.supported(valid_ids, allowed_topics=expected_topics):
                context.limitations.append(
                    "A planning constraint lacked topic-matching evidence."
                )
                continue
            if constraint.category == "safety" and not context.official(valid_ids):
                context.limitations.append(
                    "A safety planning constraint lacked official evidence."
                )
                continue
            if constraint.category == "entry" and not context.official(
                valid_ids, entry_domains or []
            ):
                context.limitations.append(
                    "An entry planning constraint lacked official evidence."
                )
                continue
            if constraint.category == "health" and not context.official(
                valid_ids, self.official_sources["health"]
            ):
                context.limitations.append(
                    "A health planning constraint lacked official evidence."
                )
                continue
            candidate = constraint.model_copy(update={"source_ids": valid_ids})
            if not _actionable_constraint(candidate):
                continue
            context.record(f"planning_constraints[{len(grounded)}]", valid_ids)
            grounded.append(candidate)
        return grounded


def _ground_summary(context: _GroundingContext, summary: str) -> str:
    source_ids = context.ids_for("summary")
    if summary and source_ids:
        context.record("summary", source_ids)
        return summary
    return ""


def _reset(model: Any, field: str) -> None:
    model_field = type(model).model_fields[field]
    setattr(model, field, model_field.get_default(call_default_factory=True))


def _actionable_constraint(constraint: PlanningConstraint) -> bool:
    if constraint.category != "culture":
        return True
    if constraint.severity in {"warning", "blocking"} or constraint.affected_dates:
        return True
    markers = (
        "access",
        "admission",
        "closed",
        "closure",
        "restricted",
        "not permitted",
        "prohibited",
        "dress code",
        "cover shoulders",
        "cover knees",
    )
    return any(marker in constraint.summary.lower() for marker in markers)
