"""Handbook rendering pipeline.

Takes raw agent outputs from ``TravelAgentState.itinerary_components``,
builds a ``TripHandbook`` Pydantic model, and renders it through a Jinja2
template into HTML.  Also produces Markdown and JSON exports.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from custom_logging import AppLogger
from src.models.itinerary import (
    CultureGuide,
    DayPlan,
    DayWeather,
    FlightOption,
    FlightSegment,
    HotelOption,
    PackingItem,
    PlaceCard,
    SafetyInfo,
    TimeBlock,
    TransitStep,
    TripHandbook,
)

logger = AppLogger(logger_name="agent.renderer", level="DEBUG")

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Destination → accent colour mapping
_DESTINATION_THEMES: dict[str, str] = {
    "japan": "#c0395a",
    "tokyo": "#c0395a",
    "kyoto": "#c0395a",
    "osaka": "#c0395a",
    "italy": "#c4793a",
    "rome": "#c4793a",
    "france": "#2c5f8a",
    "paris": "#2c5f8a",
    "greece": "#1a7f8a",
    "morocco": "#b87a2b",
    "marrakech": "#b87a2b",
    "spain": "#c43a3a",
    "barcelona": "#c43a3a",
    "uk": "#1e3a5f",
    "london": "#1e3a5f",
    "mexico": "#2a7a3a",
    "colombia": "#e8c83a",
    "bogota": "#e8c83a",
    "peru": "#8b4513",
    "lima": "#8b4513",
    "egypt": "#b8860b",
    "cairo": "#b8860b",
    "turkey": "#a0342e",
    "istanbul": "#a0342e",
    "poland": "#c43a4e",
    "default": "#e41e3f",
}

# Weather condition → emoji mapping
_WEATHER_EMOJIS: dict[str, str] = {
    "clear": "☀️",
    "sunny": "☀️",
    "clouds": "☁️",
    "cloudy": "☁️",
    "overcast": "☁️",
    "partly": "⛅",
    "rain": "🌧",
    "drizzle": "🌦",
    "thunderstorm": "⛈",
    "snow": "❄️",
    "mist": "🌫",
    "fog": "🌫",
    "haze": "🌫",
}


def _weather_emoji(condition: str) -> str:
    """Map a weather condition description to an emoji."""
    lower = condition.lower()
    for key, emoji in _WEATHER_EMOJIS.items():
        if key in lower:
            return emoji
    return "🌤"


def _pick_accent(destinations: list[str]) -> str:
    """Pick a theme accent colour based on destination names."""
    for dest in destinations:
        slug = dest.lower().strip()
        if slug in _DESTINATION_THEMES:
            return _DESTINATION_THEMES[slug]
    return _DESTINATION_THEMES["default"]


class HandbookRenderer:
    """Assembles TripHandbook from agent outputs and renders to HTML/MD/JSON."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("handbook_template.html.j2")

    # ── public API ───────────────────────────────────────────────────

    def build_handbook(
        self,
        state: dict[str, Any],
        *,
        run_id: str = "",
    ) -> TripHandbook:
        """Parse ``TravelAgentState`` dict into a ``TripHandbook``.

        This is the core assembly step — it reads free-text agent outputs
        and the state metadata to populate every field.
        """
        components = state.get("itinerary_components", {})
        destinations = state.get("destinations", [])

        handbook = TripHandbook(
            destinations=destinations,
            travel_style=state.get("travel_style", ""),
            group_type=state.get("group_type", ""),
            dietary_restrictions=state.get("dietary_restrictions", []),
            accessibility_needs=state.get("accessibility_needs", []),
            theme_accent_color=_pick_accent(destinations),
            generated_at=datetime.now().strftime("%B %d, %Y at %H:%M"),
            langsmith_run_id=run_id,
        )

        # ── Trip title ───────────────────────────────────────────
        if destinations:
            dest_str = ", ".join(d.title() for d in destinations)
            handbook.trip_title = f"Trip to {dest_str}"
        else:
            handbook.trip_title = "Your Travel Handbook"

        # ── Budget ───────────────────────────────────────────────
        budget_data = components.get("budget_structured")
        if budget_data and isinstance(budget_data, dict):
            handbook.budget_flights = budget_data.get("flights", 0)
            handbook.budget_accommodation = budget_data.get("accommodation", 0)
            handbook.budget_transport = budget_data.get("transport", 0)
            handbook.budget_meals = budget_data.get("meals", 0)
            handbook.budget_activities = budget_data.get("activities", 0)
            handbook.budget_misc = budget_data.get("misc", 0)
            handbook.budget_total = budget_data.get("total", 0)
            handbook.budget_per_person = budget_data.get("per_person", 0)
            handbook.budget_summary = budget_data.get("summary", "")

        # ── Route cities (from destinations) ─────────────────────
        if destinations:
            handbook.route_cities = [d.title() for d in destinations]

        logger.info(
            "Handbook built: title=%s destinations=%s budget_total=%.0f",
            handbook.trip_title,
            handbook.destinations,
            handbook.budget_total,
        )
        return handbook

    def render_html(self, handbook: TripHandbook) -> str:
        """Render TripHandbook to a self-contained HTML string."""
        return self._template.render(handbook=handbook)

    def render_markdown(self, handbook: TripHandbook) -> str:
        """Render TripHandbook to Markdown."""
        lines: list[str] = []
        lines.append(f"# {handbook.trip_title}\n")

        if handbook.start_date or handbook.end_date:
            lines.append(f"**Dates:** {handbook.start_date} — {handbook.end_date}  ")
        if handbook.destinations:
            lines.append(f"**Destinations:** {', '.join(d.title() for d in handbook.destinations)}  ")
        if handbook.travel_style:
            lines.append(f"**Style:** {handbook.travel_style.title()}  ")
        if handbook.total_budget_usd:
            lines.append(f"**Budget:** ${handbook.total_budget_usd:,.0f} USD  ")
        lines.append("")

        # Safety
        if handbook.safety.advisory_summary:
            lines.append(f"## Safety\n\n{handbook.safety.advisory_summary}\n")

        # Flights
        if handbook.flights:
            lines.append("## Flights\n")
            for i, f in enumerate(handbook.flights, 1):
                for seg in f.outbound:
                    lines.append(
                        f"- **Flight {i}:** {seg.departure_airport} → {seg.arrival_airport} "
                        f"| {seg.flight_number} | {seg.departure_time} → {seg.arrival_time}"
                    )
                if f.total_price_usd:
                    lines.append(f"  - **Price:** ${f.total_price_usd:,.0f} {f.currency}")
            lines.append("")

        # Hotels
        if handbook.hotels:
            lines.append("## Hotels\n")
            for h in handbook.hotels:
                lines.append(
                    f"- **{h.name}** {'★' * h.star_rating} | "
                    f"${h.price_per_night_usd:.0f}/night | "
                    f"{h.check_in} → {h.check_out}"
                )
            lines.append("")

        # Day-by-day
        if handbook.days:
            lines.append("## Day-by-Day Itinerary\n")
            for day in handbook.days:
                lines.append(f"### Day {day.day_number} — {day.date} · {day.city}\n")
                if day.weather:
                    lines.append(
                        f"**Weather:** {day.weather.emoji} "
                        f"{day.weather.temp_low_c:.0f}–{day.weather.temp_high_c:.0f}°C, "
                        f"{day.weather.rain_probability_pct}% rain\n"
                    )
                for block in day.time_blocks:
                    lines.append(f"**{block.period.title()}**\n")
                    for act in block.activities:
                        rating = f" ⭐ {act.rating}" if act.rating else ""
                        lines.append(f"- {act.name}{rating} | {act.address}")
                    if block.restaurant:
                        r = block.restaurant
                        lines.append(f"- 🍽 {r.name} | {r.price_level} | {r.address}")
                    lines.append("")
                if day.cultural_tip:
                    lines.append(f"> 💡 **Cultural Tip:** {day.cultural_tip}\n")
                lines.append(f"**Day cost:** ${day.daily_cost_usd:.0f}\n")
                lines.append("---\n")

        # Budget
        if handbook.budget_total:
            lines.append("## Budget Summary\n")
            lines.append("| Category | Amount |")
            lines.append("|---|---|")
            for label, val in [
                ("Flights", handbook.budget_flights),
                ("Hotels", handbook.budget_accommodation),
                ("Meals", handbook.budget_meals),
                ("Activities", handbook.budget_activities),
                ("Transport", handbook.budget_transport),
                ("Misc", handbook.budget_misc),
                ("**Total**", handbook.budget_total),
            ]:
                if val:
                    lines.append(f"| {label} | ${val:,.0f} |")
            lines.append("")

        # Culture
        if handbook.culture.phrases:
            lines.append("## Phrasebook\n")
            lines.append("| English | Local | Romanized |")
            lines.append("|---|---|---|")
            for p in handbook.culture.phrases:
                lines.append(
                    f"| {p.get('english', '')} | {p.get('local', '')} | "
                    f"{p.get('romanized', '')} |"
                )
            lines.append("")

        # Packing
        if handbook.packing:
            lines.append("## Packing List\n")
            for item in handbook.packing:
                check = "☑" if item.essential else "☐"
                lines.append(f"- {check} {item.item} — {item.reason}")
            lines.append("")

        lines.append(f"\n---\n*Generated by Wanderlisted · {handbook.generated_at}*\n")
        return "\n".join(lines)

    def render_json(self, handbook: TripHandbook) -> str:
        """Serialize TripHandbook to pretty-printed JSON."""
        return handbook.model_dump_json(indent=2)

    def write_outputs(
        self,
        handbook: TripHandbook,
        output_dir: str | Path = "outputs",
    ) -> dict[str, Path]:
        """Render all formats and write to disk.

        Returns a dict mapping format name → file path.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        paths: dict[str, Path] = {}

        # HTML
        html_path = out / "handbook.html"
        html_path.write_text(self.render_html(handbook), encoding="utf-8")
        paths["html"] = html_path
        logger.info("Wrote %s", html_path)

        # Markdown
        md_path = out / "handbook.md"
        md_path.write_text(self.render_markdown(handbook), encoding="utf-8")
        paths["markdown"] = md_path
        logger.info("Wrote %s", md_path)

        # JSON
        json_path = out / "handbook.json"
        json_path.write_text(self.render_json(handbook), encoding="utf-8")
        paths["json"] = json_path
        logger.info("Wrote %s", json_path)

        return paths
