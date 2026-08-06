"""Deterministic extraction of itinerary evidence from provider tool messages."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from src.models import HotelEvidence, PlaceEvidence, TripSkeleton


PLACE_RESULTS_MARKER = "PLACE_RESULTS_JSON:\n"
HOTEL_RESULTS_MARKER = "HOTEL_RESULTS_JSON:\n"
HOTEL_PRICING_MARKER = "HOTEL_PRICING_JSON:\n"


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("text")
        )
    return str(content or "")


def _payloads(text: str, marker: str) -> list[dict]:
    decoder = json.JSONDecoder()
    payloads: list[dict] = []
    cursor = 0
    while True:
        index = text.find(marker, cursor)
        if index < 0:
            return payloads
        raw = text[index + len(marker) :].lstrip()
        try:
            payload, consumed = decoder.raw_decode(raw)
        except (json.JSONDecodeError, TypeError):
            cursor = index + len(marker)
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
        cursor = index + len(marker) + consumed


def _canonical_city(search_text: str, skeleton: TripSkeleton) -> str:
    lowered = search_text.casefold()
    matches = [stay.city for stay in skeleton.stays if stay.city.casefold() in lowered]
    return matches[0] if len(set(matches)) == 1 else ""


def _legacy_place_blocks(text: str) -> list[dict]:
    """Parse only the repository's exact bullet format; never fuzzy-match prose."""
    blocks = re.split(r"(?m)^•\s+", text)
    results: list[dict] = []
    for block in blocks[1:]:
        lines = [line.rstrip() for line in block.splitlines()]
        if not lines or not lines[0].strip():
            continue
        item: dict[str, Any] = {"name": lines[0].strip()}
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("Address: "):
                item["address"] = stripped.removeprefix("Address: ")
            elif stripped.startswith("Coordinates: "):
                coords = stripped.removeprefix("Coordinates: ").split(",", 1)
                if len(coords) == 2:
                    try:
                        item["latitude"] = float(coords[0].strip())
                        item["longitude"] = float(coords[1].strip())
                    except ValueError:
                        pass
            elif stripped.startswith("Price: "):
                item["price_level"] = stripped.removeprefix("Price: ")
            elif stripped.startswith("Summary: "):
                item["description"] = stripped.removeprefix("Summary: ")
            elif stripped.startswith("Hours: "):
                item["opening_hours"] = [stripped.removeprefix("Hours: ")]
            elif stripped.startswith("Types: "):
                types = [
                    value.strip()
                    for value in stripped.removeprefix("Types: ").split(",")
                ]
                item["types"] = [value for value in types if value]
                item["category"] = item["types"][0] if item["types"] else ""
            elif stripped.startswith("Google Maps: "):
                item["google_maps_url"] = stripped.removeprefix("Google Maps: ")
            elif stripped.startswith("Website: "):
                item["website_url"] = stripped.removeprefix("Website: ")
            elif stripped.startswith("Photo: "):
                item["photo_urls"] = [stripped.removeprefix("Photo: ")]
        identity = "|".join(
            str(item.get(key, ""))
            for key in ("name", "address", "latitude", "longitude")
        )
        item["source_id"] = (
            "legacy:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        )
        item["place_id"] = item["source_id"]
        results.append(item)
    return results


@dataclass(frozen=True, slots=True)
class ItineraryEvidenceCatalog:
    places: dict[str, PlaceEvidence]
    hotels: dict[str, HotelEvidence]
    warnings: tuple[str, ...] = ()

    def prompt_payload(self) -> dict:
        return {
            "places": [
                value.model_dump(mode="json")
                for _, value in sorted(self.places.items())
            ],
            "hotels": [
                value.model_dump(mode="json")
                for _, value in sorted(self.hotels.items())
            ],
        }


def build_evidence_catalog(
    components: dict[str, Any], skeleton: TripSkeleton
) -> ItineraryEvidenceCatalog:
    places: dict[str, PlaceEvidence] = {}
    hotels: dict[str, HotelEvidence] = {}
    warnings: list[str] = []

    for component in ("activities", "restaurants"):
        component_data = components.get(component, {}).get("data", {})
        structured_places = (
            component_data.get("places", []) if isinstance(component_data, dict) else []
        )
        for raw_place in structured_places:
            try:
                raw = dict(raw_place)
                provider_id = raw.get("source_id")
                if not isinstance(provider_id, str) or not provider_id.strip():
                    raise ValueError("place evidence requires a stable source ID")
                provider_id = provider_id.strip()
                source_id = f"{component}:{provider_id}"
                raw.update(
                    source_id=source_id,
                    source_component=component,
                    city=_canonical_city(
                        " ".join(
                            str(raw.get(key, ""))
                            for key in ("search_context", "address")
                        ),
                        skeleton,
                    ),
                )
                places[source_id] = PlaceEvidence.model_validate(raw)
            except (TypeError, ValueError):
                warnings.append(f"invalid {component} place evidence ignored")

        if structured_places:
            continue

        for message in components.get(component, {}).get("messages", []):
            if not isinstance(message, (AIMessage, ToolMessage)):
                continue
            text = _message_text(message.content)
            structured_found = False
            for payload in _payloads(text, PLACE_RESULTS_MARKER):
                for raw in payload.get("places", []):
                    try:
                        raw = dict(raw)
                        provider_id = raw.get("source_id")
                        if not isinstance(provider_id, str) or not provider_id.strip():
                            raise ValueError(
                                "place evidence requires a stable source ID"
                            )
                        provider_id = provider_id.strip()
                        source_id = f"{component}:{provider_id}"
                        raw.update(
                            source_id=source_id,
                            source_component=component,
                            city=_canonical_city(
                                " ".join(
                                    str(raw.get(key, ""))
                                    for key in ("search_context", "address")
                                ),
                                skeleton,
                            ),
                        )
                        places[source_id] = PlaceEvidence.model_validate(raw)
                        structured_found = True
                    except (TypeError, ValueError):
                        warnings.append(f"invalid {component} place evidence ignored")
            if structured_found:
                continue
            for raw in _legacy_place_blocks(text):
                raw.update(
                    source_id=f"{component}:{raw['source_id']}",
                    source_component=component,
                    city=_canonical_city(text, skeleton),
                    search_context="legacy_exact_format",
                )
                try:
                    evidence = PlaceEvidence.model_validate(raw)
                except ValueError:
                    continue
                places[evidence.source_id] = evidence

    hotel_places_by_name: dict[str, dict[str, PlaceEvidence]] = {}
    hotel_messages = components.get("hotels", {}).get("messages", [])
    for message in hotel_messages:
        if not isinstance(message, (AIMessage, ToolMessage)):
            continue
        text = _message_text(message.content)
        for payload in _payloads(text, PLACE_RESULTS_MARKER):
            for raw in payload.get("places", []):
                try:
                    raw = dict(raw)
                    provider_id = raw.get("source_id")
                    if not isinstance(provider_id, str) or not provider_id.strip():
                        raise ValueError(
                            "hotel place evidence requires a stable source ID"
                        )
                    provider_id = provider_id.strip()
                    raw.update(
                        source_id=f"hotels:{provider_id}",
                        source_component="hotels",
                        city=_canonical_city(
                            " ".join(
                                str(raw.get(key, ""))
                                for key in ("search_context", "address")
                            ),
                            skeleton,
                        ),
                    )
                    place = PlaceEvidence.model_validate(raw)
                except (TypeError, ValueError):
                    warnings.append("invalid hotel place evidence ignored")
                    continue
                hotel_places_by_name.setdefault(place.name, {})[place.source_id] = place
        for payload in _payloads(text, HOTEL_RESULTS_MARKER):
            for raw in payload.get("options", []):
                try:
                    evidence = HotelEvidence.model_validate(raw)
                except (TypeError, ValueError):
                    warnings.append("invalid hotel evidence ignored")
                    continue
                hotels[evidence.rate_key] = evidence
        for payload in _payloads(text, HOTEL_PRICING_MARKER):
            city_code = str(payload.get("city_code", ""))
            for raw in payload.get("options", []):
                rate_key = str(raw.get("rate_key", ""))
                if not rate_key or rate_key in hotels:
                    continue
                money = raw.get("money", {}) or {}
                try:
                    hotels[rate_key] = HotelEvidence(
                        source_id=rate_key,
                        rate_key=rate_key,
                        name=str(raw.get("hotel_name", "Unknown Hotel")),
                        city_code=city_code,
                        room_name=str(raw.get("room_name", "")),
                        check_in=str(raw.get("check_in", "")),
                        check_out=str(raw.get("check_out", "")),
                        amount=str(money.get("amount", "0")),
                        currency=str(money.get("currency", "USD")),
                    )
                except ValueError:
                    warnings.append("invalid legacy hotel pricing ignored")

    for rate_key, hotel in list(hotels.items()):
        exact_matches = list(hotel_places_by_name.get(hotel.name, {}).values())
        if len(exact_matches) > 1:
            warnings.append(
                f"ambiguous exact Google Places matches ignored for hotel {hotel.name}"
            )
            continue
        if not exact_matches:
            continue
        place = exact_matches[0]
        hotels[rate_key] = hotel.model_copy(
            update={
                "place_id": place.place_id,
                "address": place.address,
                "latitude": hotel.latitude or place.latitude,
                "longitude": hotel.longitude or place.longitude,
                "description": place.description,
                "website_url": place.website_url,
                "google_maps_url": place.google_maps_url,
                "photo_urls": list(place.photo_urls),
            }
        )

    if not places:
        warnings.append("no typed or exact-format place evidence was available")
    if not hotels:
        warnings.append("no typed hotel-rate evidence was available")
    return ItineraryEvidenceCatalog(
        places=places, hotels=hotels, warnings=tuple(warnings)
    )


__all__ = [
    "HOTEL_PRICING_MARKER",
    "HOTEL_RESULTS_MARKER",
    "ItineraryEvidenceCatalog",
    "PLACE_RESULTS_MARKER",
    "build_evidence_catalog",
]
