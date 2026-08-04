"""Handbook rendering pipeline.

Takes raw agent outputs from ``TravelAgentState.itinerary_components``,
builds a ``TripHandbook`` Pydantic model, and renders it through a Jinja2
template into HTML.  Also produces Markdown and JSON exports.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from custom_logging import AppLogger
from src.models import BudgetBreakdown, DraftItinerary, TripRequest, TripSkeleton
from src.models.itinerary import (
    FlightOption,
    FlightSegment,
    HotelOption,
    ItineraryPlan,
    TripHandbook,
)
from src.readiness import TravelReadinessReport

logger = AppLogger(logger_name="agent.renderer", level="DEBUG")

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@dataclass
class SeasonPalette:
    accent: str
    gradient_from: str
    gradient_to: str
    hero_emoji: str


# (destination_slug, season) → SeasonPalette
_SEASON_PALETTES: dict[tuple[str, str], SeasonPalette] = {
    # Japan
    ("japan", "spring"): SeasonPalette("#c0395a", "#f4b8c8", "#c0395a", "🌸"),
    ("tokyo", "spring"): SeasonPalette("#c0395a", "#f4b8c8", "#c0395a", "🌸"),
    ("kyoto", "spring"): SeasonPalette("#b5375a", "#f0b0c2", "#b5375a", "🌸"),
    ("osaka", "spring"): SeasonPalette("#c0395a", "#f4b8c8", "#c0395a", "🌸"),
    ("japan", "summer"): SeasonPalette("#1a7a3a", "#2e9e52", "#145f2e", "🎋"),
    ("tokyo", "summer"): SeasonPalette("#1a7a3a", "#2e9e52", "#145f2e", "🎋"),
    ("japan", "autumn"): SeasonPalette("#c44a20", "#e8723a", "#8b2500", "🍁"),
    ("tokyo", "autumn"): SeasonPalette("#c44a20", "#e8723a", "#8b2500", "🍁"),
    ("japan", "winter"): SeasonPalette("#1e3a8a", "#3b6fd4", "#0d1e5c", "❄️"),
    ("tokyo", "winter"): SeasonPalette("#1e3a8a", "#3b6fd4", "#0d1e5c", "❄️"),
    # France / Paris
    ("france", "spring"): SeasonPalette("#2c5f8a", "#5b9fd4", "#1a3a5f", "🌷"),
    ("paris", "spring"): SeasonPalette("#2c5f8a", "#5b9fd4", "#1a3a5f", "🌷"),
    ("france", "summer"): SeasonPalette("#1e3a8a", "#4a7fc1", "#0d2050", "☀️"),
    ("paris", "summer"): SeasonPalette("#1e3a8a", "#4a7fc1", "#0d2050", "☀️"),
    ("france", "autumn"): SeasonPalette("#c47820", "#e6a23c", "#8b4513", "🍂"),
    ("paris", "autumn"): SeasonPalette("#c47820", "#e6a23c", "#8b4513", "🍂"),
    ("france", "winter"): SeasonPalette("#2c5f8a", "#4a7fc1", "#1a3360", "⛄"),
    ("paris", "winter"): SeasonPalette("#2c5f8a", "#4a7fc1", "#1a3360", "⛄"),
    # Italy / Rome
    ("italy", "spring"): SeasonPalette("#c4793a", "#e0986a", "#8b4e1c", "🌹"),
    ("rome", "spring"): SeasonPalette("#c4793a", "#e0986a", "#8b4e1c", "🌹"),
    ("italy", "summer"): SeasonPalette("#c4793a", "#f5a623", "#8b4513", "🍕"),
    ("rome", "summer"): SeasonPalette("#c4793a", "#f5a623", "#8b4513", "🍕"),
    ("italy", "autumn"): SeasonPalette("#8b4513", "#c0692c", "#5c2e00", "🍂"),
    ("rome", "autumn"): SeasonPalette("#8b4513", "#c0692c", "#5c2e00", "🍂"),
    ("italy", "winter"): SeasonPalette("#c4793a", "#e0986a", "#8b4e1c", "🎄"),
    ("rome", "winter"): SeasonPalette("#c4793a", "#e0986a", "#8b4e1c", "🎄"),
    # Spain / Barcelona
    ("spain", "spring"): SeasonPalette("#c43a3a", "#e87070", "#8b1a1a", "🌺"),
    ("barcelona", "spring"): SeasonPalette("#c43a3a", "#e87070", "#8b1a1a", "🌺"),
    ("spain", "summer"): SeasonPalette("#e67e22", "#f3a23c", "#a0541a", "🌊"),
    ("barcelona", "summer"): SeasonPalette("#e67e22", "#f3a23c", "#a0541a", "🌊"),
    ("spain", "autumn"): SeasonPalette("#c43a3a", "#e06060", "#8b1a1a", "🍷"),
    ("barcelona", "autumn"): SeasonPalette("#c43a3a", "#e06060", "#8b1a1a", "🍷"),
    # UK / London
    ("uk", "spring"): SeasonPalette("#1e3a5f", "#4a7fc1", "#0d1e3a", "🌷"),
    ("london", "spring"): SeasonPalette("#1e3a5f", "#4a7fc1", "#0d1e3a", "🌷"),
    ("uk", "summer"): SeasonPalette("#1e3a5f", "#4a90d9", "#0d1e3a", "⛅"),
    ("london", "summer"): SeasonPalette("#1e3a5f", "#4a90d9", "#0d1e3a", "⛅"),
    ("uk", "autumn"): SeasonPalette("#4a2c2a", "#8b5e3c", "#2c1a18", "🍂"),
    ("london", "autumn"): SeasonPalette("#4a2c2a", "#8b5e3c", "#2c1a18", "🍂"),
    ("uk", "winter"): SeasonPalette("#1e3a5f", "#4a7fc1", "#0d2050", "❄️"),
    ("london", "winter"): SeasonPalette("#1e3a5f", "#4a7fc1", "#0d2050", "❄️"),
    # Morocco / Marrakech
    ("morocco", "spring"): SeasonPalette("#b87a2b", "#e0a843", "#7a5020", "🌺"),
    ("marrakech", "spring"): SeasonPalette("#b87a2b", "#e0a843", "#7a5020", "🌺"),
    ("morocco", "summer"): SeasonPalette("#b87a2b", "#f5b942", "#7a5020", "☀️"),
    ("marrakech", "summer"): SeasonPalette("#b87a2b", "#f5b942", "#7a5020", "☀️"),
    ("morocco", "winter"): SeasonPalette("#b87a2b", "#d4953a", "#7a5020", "🌙"),
    ("marrakech", "winter"): SeasonPalette("#b87a2b", "#d4953a", "#7a5020", "🌙"),
    # Egypt / Cairo
    ("egypt", "spring"): SeasonPalette("#b8860b", "#daa520", "#8b6508", "🌅"),
    ("cairo", "spring"): SeasonPalette("#b8860b", "#daa520", "#8b6508", "🌅"),
    ("egypt", "summer"): SeasonPalette("#b8860b", "#f5c342", "#8b6508", "☀️"),
    ("cairo", "summer"): SeasonPalette("#b8860b", "#f5c342", "#8b6508", "☀️"),
    ("egypt", "autumn"): SeasonPalette("#b8860b", "#d4a020", "#8b6508", "🏛"),
    ("cairo", "autumn"): SeasonPalette("#b8860b", "#d4a020", "#8b6508", "🏛"),
    ("egypt", "winter"): SeasonPalette("#b8860b", "#c5981e", "#8b6508", "🌙"),
    ("cairo", "winter"): SeasonPalette("#b8860b", "#c5981e", "#8b6508", "🌙"),
    # Turkey / Istanbul
    ("turkey", "spring"): SeasonPalette("#a0342e", "#d45f59", "#6b1f1b", "🌷"),
    ("istanbul", "spring"): SeasonPalette("#a0342e", "#d45f59", "#6b1f1b", "🌷"),
    ("turkey", "summer"): SeasonPalette("#a0342e", "#c55050", "#6b1f1b", "☀️"),
    ("istanbul", "summer"): SeasonPalette("#a0342e", "#c55050", "#6b1f1b", "☀️"),
    ("turkey", "autumn"): SeasonPalette("#a0342e", "#c24848", "#6b1f1b", "🍂"),
    ("istanbul", "autumn"): SeasonPalette("#a0342e", "#c24848", "#6b1f1b", "🍂"),
    # Colombia / Bogotá / Medellín / Cartagena
    ("colombia", "spring"): SeasonPalette("#e8b81a", "#f5d03c", "#a07e08", "🌻"),
    ("bogota", "spring"): SeasonPalette("#e8b81a", "#f5d03c", "#a07e08", "🌻"),
    ("medellin", "spring"): SeasonPalette("#e86a1a", "#f5923c", "#a04408", "🌺"),
    ("cartagena", "summer"): SeasonPalette("#1a8a8a", "#2eaec0", "#0d5a5a", "🏖"),
    # Mexico
    ("mexico", "spring"): SeasonPalette("#2e7a3e", "#4aab5e", "#1e5228", "🌵"),
    ("mexico_city", "summer"): SeasonPalette("#2e7a3e", "#4aab5e", "#1e5228", "🌮"),
    ("cancun", "summer"): SeasonPalette("#1a7a8a", "#2eaec0", "#0d4e5c", "🏖"),
}

# Fallback single-colour map (for unmapped destination+season combos)
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


def _get_season(start_date_str: str) -> str:
    """Derive meteorological season from start date string (YYYY-MM-DD or similar)."""
    if not start_date_str:
        return "summer"
    try:
        month = datetime.fromisoformat(start_date_str[:10]).month
    except (ValueError, TypeError):
        return "summer"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _pick_palette(destinations: list[str], season: str) -> SeasonPalette:
    """Pick a seasonal colour palette for the given destinations."""
    for dest in destinations:
        slug = dest.lower().strip()
        key = (slug, season)
        if key in _SEASON_PALETTES:
            return _SEASON_PALETTES[key]
        # Try any season as a base for the destination's brand colour
        for s in ("summer", "spring", "autumn", "winter"):
            if (slug, s) in _SEASON_PALETTES:
                p = _SEASON_PALETTES[(slug, s)]
                return SeasonPalette(p.accent, p.accent, p.gradient_to, p.hero_emoji)
        # Final fallback: use legacy single-colour map
        if slug in _DESTINATION_THEMES:
            accent = _DESTINATION_THEMES[slug]
            return SeasonPalette(accent, accent, accent + "cc", "✈️")
    default = _DESTINATION_THEMES["default"]
    return SeasonPalette(default, default, "#b01028", "✈️")


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
        """Build a handbook exclusively from validated structured artifacts."""
        components = state.get("itinerary_components", {})
        request = TripRequest.model_validate(state.get("trip_request", {}))
        skeleton = TripSkeleton.model_validate(
            components.get("trip_skeleton_structured", {})
        )
        draft = DraftItinerary.model_validate(
            components.get("draft_itinerary_structured", {})
        )
        plan = ItineraryPlan.model_validate(components.get("itinerary_structured", {}))
        raw_budget = components.get("budget_structured")
        budget = BudgetBreakdown.model_validate(raw_budget) if raw_budget else None
        raw_readiness = components.get("readiness", {}).get("data") or components.get(
            "readiness_preflight", {}
        ).get("data")
        readiness = (
            TravelReadinessReport.model_validate(raw_readiness)
            if raw_readiness
            else TravelReadinessReport()
        )
        destinations = list(request.destinations) or list(readiness.destinations)
        season = _get_season(plan.start_date)
        palette = _pick_palette(destinations, season)

        selected_flight = skeleton.selected_flight
        flights: list[FlightOption] = []
        budget_items = {
            item.source_id: item
            for item in (budget.line_items if budget else [])
            if item.amount_usd is not None and not item.estimated
        }
        if selected_flight is not None:
            flight_cost = 0.0
            line_item = budget_items.get(selected_flight.offer_id)
            if line_item is not None and line_item.amount_usd is not None:
                flight_cost = float(line_item.amount_usd)
            elif selected_flight.currency == "USD":
                try:
                    flight_cost = float(selected_flight.total_amount)
                except (TypeError, ValueError):
                    flight_cost = 0.0
            flights.append(
                FlightOption(
                    outbound=[
                        FlightSegment(
                            carrier=selected_flight.airline_name,
                            departure_airport=selected_flight.origin,
                            arrival_airport=selected_flight.destination,
                        )
                    ],
                    inbound=[
                        FlightSegment(
                            carrier=selected_flight.airline_name,
                            departure_airport=selected_flight.destination,
                            arrival_airport=selected_flight.origin,
                        )
                    ],
                    total_price_usd=flight_cost,
                    currency="USD",
                )
            )

        selected_by_stay = {
            item.stay_sequence: item for item in draft.selected_accommodations
        }
        draft_by_day = {item.day_number: item for item in draft.days}
        hotels: list[HotelOption] = []
        for stay in skeleton.stays:
            selected = selected_by_stay.get(stay.sequence)
            if selected is None:
                continue
            first_day_number = (stay.check_in - skeleton.start_date).days + 1
            fallback_ref = (
                draft_by_day.get(first_day_number).start_location
                if draft_by_day.get(first_day_number)
                else None
            )
            hotel_cost = 0.0
            line_item = budget_items.get(selected.rate_key)
            if line_item is not None and line_item.amount_usd is not None:
                hotel_cost = float(line_item.amount_usd)
            elif (
                selected.price_evidence is not None
                and selected.price_evidence.money.currency == "USD"
            ):
                try:
                    hotel_cost = float(selected.price_evidence.money.amount)
                except (TypeError, ValueError):
                    hotel_cost = 0.0
            hotels.append(
                HotelOption(
                    name=selected.name,
                    price_per_night_usd=(
                        round(hotel_cost / stay.nights, 2) if stay.nights else 0
                    ),
                    total_price_usd=hotel_cost,
                    check_in=stay.check_in.isoformat(),
                    check_out=stay.check_out.isoformat(),
                    latitude=fallback_ref.latitude if fallback_ref else 0,
                    longitude=fallback_ref.longitude if fallback_ref else 0,
                    photo_urls=fallback_ref.photo_urls if fallback_ref else [],
                    google_maps_url=(
                        fallback_ref.google_maps_url if fallback_ref else ""
                    ),
                    website_url=fallback_ref.website_url if fallback_ref else "",
                    description=fallback_ref.description if fallback_ref else "",
                )
            )

        route_cities = list(dict.fromkeys(stay.city for stay in skeleton.stays))
        if skeleton.exit_city and skeleton.exit_city not in route_cities:
            route_cities.append(skeleton.exit_city)
        route_transport = list(
            dict.fromkeys(
                str(step.mode)
                for day in plan.days
                for block in day.time_blocks
                for step in block.transit
            )
        )

        handbook = TripHandbook(
            trip_title=(
                "Trip to "
                + ", ".join(destination.title() for destination in destinations)
                if destinations
                else "Your Travel Handbook"
            ),
            origin_city=request.origin_city,
            destinations=destinations,
            start_date=plan.start_date,
            end_date=plan.end_date,
            total_budget_usd=budget.total if budget else 0,
            travel_style=request.travel_style or state.get("travel_style", ""),
            group_type=state.get("group_type", ""),
            dietary_restrictions=request.dietary_restrictions,
            accessibility_needs=request.accessibility_needs,
            route_cities=route_cities,
            route_transport=route_transport,
            flights=flights,
            hotels=hotels,
            days=list(plan.days),
            safety=readiness.safety,
            culture=readiness.culture,
            packing=list(readiness.packing_constraints),
            local_currency_code=readiness.safety.currency_code,
            theme_accent_color=palette.accent,
            hero_gradient_from=palette.gradient_from,
            hero_gradient_to=palette.gradient_to,
            hero_emoji=palette.hero_emoji,
            season=season,
            generated_at=readiness.generated_at if raw_readiness else "",
            langsmith_run_id=run_id,
        )

        # ── Budget ───────────────────────────────────────────────
        if budget is not None:
            # Inline handbook totals are the validated USD base values. Requested
            # display-currency values are carried separately for newer clients.
            handbook.budget_flights = budget.flights
            handbook.budget_accommodation = budget.accommodation
            handbook.budget_transport = budget.transport
            handbook.budget_meals = budget.meals
            handbook.budget_activities = budget.activities
            handbook.budget_misc = budget.misc
            handbook.budget_total = budget.total
            handbook.budget_per_person = budget.per_person
            handbook.budget_summary = budget.summary
            handbook.budget_base_currency = budget.base_currency
            handbook.budget_display_currency = budget.display_currency
            handbook.budget_display_breakdown = budget.display_breakdown
            handbook.budget_coverage_status = budget.coverage_status
            handbook.budget_missing_categories = list(budget.missing_categories)
            handbook.budget_estimated_categories = list(budget.estimated_categories)
            handbook.budget_assumptions = list(budget.assumptions)
            handbook.budget_reserve_recommendation = budget.reserve_recommendation
            handbook.budget_display_reserve_recommendation = (
                budget.display_reserve_recommendation
            )
            handbook.budget_contingency_included = budget.contingency_included

        logger.info(
            "Handbook built: title=%s destinations=%s budget_total=%.0f",
            handbook.trip_title,
            handbook.destinations,
            handbook.budget_total,
        )
        return handbook

    def render_html(self, handbook: TripHandbook) -> str:
        """Render TripHandbook to a self-contained HTML string."""
        # Google Maps Embed API key is intentionally passed to the client-side
        # Maps iframe — this key should be restricted by HTTP Referrer in Google
        # Cloud Console (not a secret; Maps Embed API is designed for public URLs).
        maps_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        return self._template.render(handbook=handbook, google_maps_api_key=maps_key)

    def render_markdown(self, handbook: TripHandbook) -> str:
        """Render TripHandbook to Markdown."""
        lines: list[str] = []
        lines.append(f"# {handbook.trip_title}\n")

        if handbook.start_date or handbook.end_date:
            lines.append(f"**Dates:** {handbook.start_date} — {handbook.end_date}  ")
        if handbook.destinations:
            lines.append(
                f"**Destinations:** {', '.join(d.title() for d in handbook.destinations)}  "
            )
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
                    lines.append(
                        f"  - **Price:** ${f.total_price_usd:,.0f} {f.currency}"
                    )
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
