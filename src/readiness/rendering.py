"""Markdown rendering for an already-grounded readiness report."""

from __future__ import annotations

from src.readiness.models import TravelReadinessReport


def render_markdown(report: TravelReadinessReport) -> str:
    source_map = {source.id: source for source in report.sources}

    def refs(path: str, fallback_path: str | None = None) -> str:
        source_ids = report.citations.get(path, [])
        if not source_ids and fallback_path:
            source_ids = report.citations.get(fallback_path, [])
        links = [
            f"[{source_id}]({source_map[source_id].url})"
            for source_id in source_ids
            if source_id in source_map
        ]
        return " " + " ".join(links) if links else ""

    def add_scalar(heading: str, value: str, path: str) -> None:
        if value:
            lines.extend(["", f"### {heading}", f"- {value}{refs(path)}"])

    def add_list(heading: str, items: list, path: str, formatter=str) -> None:
        if not items:
            return
        lines.extend(["", f"### {heading}"])
        for index, item in enumerate(items):
            item_path = f"{path}[{index}]"
            lines.append(f"- {formatter(item)}{refs(item_path, fallback_path=path)}")

    def format_mapping(item: dict) -> str:
        return "; ".join(
            f"{str(key).replace('_', ' ').title()}: {value}"
            for key, value in item.items()
            if value
        )

    lines = [
        f"## Travel essentials: {', '.join(d.title() for d in report.destinations)}"
    ]
    if report.summary:
        lines.extend(["", report.summary + refs("summary")])
    add_scalar("Safety", report.safety.advisory_summary, "safety.advisory_summary")
    add_list("Safety tips", report.safety.safety_tips, "safety.safety_tips")
    add_list(
        "Weather forecast",
        report.weather,
        "weather",
        lambda item: (
            f"{item.date}: {item.temp_low_c:.0f}–{item.temp_high_c:.0f}°C, "
            f"{item.condition}, {item.rain_probability_pct}% rain"
        ),
    )
    add_list("Seasonal weather", report.weather_summary, "weather_summary")
    add_list(
        "Culture and etiquette",
        report.culture.etiquette_tips,
        "culture.etiquette_tips",
    )
    add_list(
        "Dining customs",
        report.culture.dining_customs,
        "culture.dining_customs",
    )
    add_scalar("Tipping", report.culture.tipping_guide, "culture.tipping_guide")
    add_list(
        "Local customs",
        report.culture.local_customs,
        "culture.local_customs",
        format_mapping,
    )
    add_list(
        "Dress guidance",
        report.culture.dress_code_notes,
        "culture.dress_code_notes",
    )
    add_list(
        "Religious customs",
        report.culture.religious_customs,
        "culture.religious_customs",
    )
    add_list(
        "Useful phrases",
        report.culture.phrases,
        "culture.phrases",
        format_mapping,
    )
    add_scalar(
        "Entry requirements",
        report.safety.visa_requirements,
        "safety.visa_requirements",
    )
    add_list(
        "Health",
        report.safety.health_requirements,
        "safety.health_requirements",
    )
    add_list(
        "Preparation constraints",
        report.packing_constraints,
        "packing_constraints",
        lambda item: f"{item.item}: {item.reason}",
    )
    if report.planning_constraints:
        lines.extend(["", "### Planning constraints"])
        for constraint in report.planning_constraints:
            links = " ".join(
                f"[{source_id}]({source_map[source_id].url})"
                for source_id in constraint.source_ids
                if source_id in source_map
            )
            suffix = f" {links}" if links else ""
            lines.append(
                f"- **{constraint.severity} / {constraint.category}:** "
                f"{constraint.summary}{suffix}"
            )
    if report.limitations:
        lines.extend(["", "### Limitations"])
        lines.extend(f"- {item}" for item in report.limitations)
    if report.sources:
        lines.extend(["", "### Sources"])
        lines.extend(
            f"- [{source.id}] [{source.title}]({source.url})"
            + (" — official source" if source.is_official else "")
            for source in report.sources
        )
    return "\n".join(lines)
