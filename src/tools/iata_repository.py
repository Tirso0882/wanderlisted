"""CSV-backed repository for IATA airport resolution data."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from types import MappingProxyType

_DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
_AIRPORTS_PATH = _DATA_ROOT / "iata_codes.csv"
_POLICY_ROOT = _DATA_ROOT / "iata"
_ALIASES_PATH = _POLICY_ROOT / "aliases.csv"
_PRIMARY_AIRPORTS_PATH = _POLICY_ROOT / "primary_airports.csv"
_COUNTRIES_PATH = _POLICY_ROOT / "countries.csv"

_TYPE_RANK = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}


def _normalize(value: str) -> str:
    """Normalize user-facing names while retaining meaningful accents."""
    return " ".join(value.strip().casefold().split())


@dataclass(frozen=True, slots=True)
class AirportRecord:
    """Airport fields needed to rank and resolve a location."""

    code: str
    airport_name: str
    city_name: str
    country: str
    airport_type: str
    scheduled_service: str

    @property
    def score(self) -> tuple[int, int, str]:
        """Prefer scheduled commercial service, then larger airports."""
        return (
            0 if self.scheduled_service == "yes" else 1,
            _TYPE_RANK.get(self.airport_type, 3),
            self.code,
        )


@dataclass(frozen=True, slots=True)
class IataRepository:
    """Immutable in-memory indexes loaded from the IATA CSV data files."""

    codes_by_name: Mapping[str, str]
    valid_codes: frozenset[str]
    countries_by_code: Mapping[str, str]
    aliases: Mapping[str, str]
    primary_airports: Mapping[str, str]
    iso_codes_by_country: Mapping[str, str]

    @classmethod
    def from_csv_files(
        cls,
        *,
        airports_path: Path,
        aliases_path: Path,
        primary_airports_path: Path,
        countries_path: Path,
    ) -> IataRepository:
        """Build all lookup indexes once from generated and curated CSV data."""
        city_entries: dict[str, list[AirportRecord]] = {}
        airport_entries: list[tuple[str, str]] = []
        valid_codes: set[str] = set()
        countries_by_code: dict[str, str] = {}

        with airports_path.open(newline="", encoding="utf-8") as csv_file:
            for row in csv.DictReader(csv_file):
                code = (row.get("iata_code") or "").strip().upper()
                if len(code) != 3 or not code.isalpha():
                    continue

                airport_type = (row.get("type") or "").strip()
                if airport_type == "closed":
                    continue

                airport_name = _normalize(row.get("airport_name") or "")
                city_name = _normalize(row.get("city_name") or "")
                country = (row.get("country") or "").strip()
                record = AirportRecord(
                    code=code,
                    airport_name=airport_name,
                    city_name=city_name,
                    country=country,
                    airport_type=airport_type,
                    scheduled_service=(row.get("scheduled_service") or "").strip(),
                )

                valid_codes.add(code)
                if country:
                    countries_by_code[code] = country
                if city_name:
                    city_entries.setdefault(city_name, []).append(record)
                    base_city = city_name.split("(", 1)[0].split(",", 1)[0].strip()
                    if base_city and base_city != city_name:
                        city_entries.setdefault(base_city, []).append(record)
                if airport_name:
                    airport_entries.append((airport_name, code))

        aliases = _load_code_mapping(
            aliases_path,
            key_field="alias",
            valid_codes=valid_codes,
        )
        primary_airports = _load_code_mapping(
            primary_airports_path,
            key_field="city_name",
            valid_codes=valid_codes,
        )
        iso_codes_by_country = _load_country_mapping(countries_path)

        codes_by_name = {code.casefold(): code for code in valid_codes}
        for city_name, entries in city_entries.items():
            selected = primary_airports.get(city_name)
            if selected is None:
                selected = min(entries, key=lambda entry: entry.score).code
            codes_by_name.setdefault(city_name, selected)

        for airport_name, code in airport_entries:
            codes_by_name.setdefault(airport_name, code)

        # A primary city can be a traveler-facing name that differs from the
        # source municipality, so policy data is also a direct name index.
        codes_by_name.update(primary_airports)

        return cls(
            codes_by_name=MappingProxyType(codes_by_name),
            valid_codes=frozenset(valid_codes),
            countries_by_code=MappingProxyType(countries_by_code),
            aliases=MappingProxyType(aliases),
            primary_airports=MappingProxyType(primary_airports),
            iso_codes_by_country=MappingProxyType(iso_codes_by_country),
        )

    def resolve_code(self, location: str) -> str | None:
        """Resolve a city, airport name, alias, or IATA code."""
        key = _normalize(location)
        if not key:
            return None

        alias_code = self.aliases.get(key)
        if alias_code:
            return alias_code

        direct_code = self.codes_by_name.get(key)
        if direct_code:
            return direct_code

        upper = key.upper()
        if len(key) == 3 and upper in self.valid_codes:
            return upper

        if len(key) >= 4:
            substring_matches = [
                (name, code)
                for name, code in self.codes_by_name.items()
                if key in name and len(name) > len(key)
            ]
            if substring_matches:
                return min(substring_matches, key=lambda match: len(match[0]))[1]

        fuzzy_matches = get_close_matches(
            key, self.codes_by_name.keys(), n=3, cutoff=0.6
        )
        if fuzzy_matches:
            return self.codes_by_name[fuzzy_matches[0]]
        return None

    def country_for_code(self, iata_code: str) -> str:
        """Return the country name associated with an IATA code."""
        return self.countries_by_code.get(iata_code.upper().strip(), "")

    def country_iso_for_code(self, iata_code: str) -> str:
        """Return the ISO alpha-2 country code associated with an IATA code."""
        country = self.country_for_code(iata_code)
        return self.iso_codes_by_country.get(_normalize(country), "")


def _load_code_mapping(
    path: Path,
    *,
    key_field: str,
    valid_codes: set[str],
) -> dict[str, str]:
    """Load and validate an alias-like name-to-IATA mapping."""
    mapping: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as csv_file:
        for line_number, row in enumerate(csv.DictReader(csv_file), start=2):
            key = _normalize(row.get(key_field) or "")
            code = (row.get("iata_code") or "").strip().upper()
            if not key or not code:
                raise ValueError(
                    f"{path}:{line_number}: name and iata_code are required"
                )
            if code not in valid_codes:
                raise ValueError(f"{path}:{line_number}: unknown IATA code {code!r}")
            existing = mapping.get(key)
            if existing and existing != code:
                raise ValueError(
                    f"{path}:{line_number}: {key!r} maps to both "
                    f"{existing!r} and {code!r}"
                )
            mapping[key] = code
    return mapping


def _load_country_mapping(path: Path) -> dict[str, str]:
    """Load country names and ISO alpha-2 codes used for flag rendering."""
    mapping: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as csv_file:
        for line_number, row in enumerate(csv.DictReader(csv_file), start=2):
            country = _normalize(row.get("country_name") or "")
            iso_code = (row.get("iso_code") or "").strip().upper()
            if not country or len(iso_code) != 2 or not iso_code.isalpha():
                raise ValueError(
                    f"{path}:{line_number}: country_name and alpha-2 iso_code "
                    "are required"
                )
            mapping[country] = iso_code
    return mapping


# Importing the tool module constructs this repository once per Python process.
IATA_REPOSITORY = IataRepository.from_csv_files(
    airports_path=_AIRPORTS_PATH,
    aliases_path=_ALIASES_PATH,
    primary_airports_path=_PRIMARY_AIRPORTS_PATH,
    countries_path=_COUNTRIES_PATH,
)
