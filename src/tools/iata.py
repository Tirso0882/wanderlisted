"""IATA airport code lookup with fuzzy matching.

Loads ~7,700 airports from iata_codes.csv at module import time.
The agent calls this tool before flight search to resolve city names
like "Seattle" → "SEA" or "Tokyo" → "NRT".
"""

import csv
from difflib import get_close_matches
from pathlib import Path

from langchain_core.tools import tool

# ── Load CSV once at import time ─────────────────────────────────────────

_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "iata_codes.csv"

# city/airport name (lowercase) → IATA code
_IATA_BY_NAME: dict[str, str] = {}
# IATA code (uppercase) → set — for "already valid" checks
_VALID_CODES: set[str] = set()


def _load_iata_db() -> None:
    """Parse the CSV into lookup dictionaries.

    When a city has multiple airports, prefer the one whose airport_name
    contains "international" (heuristic: that's usually the main one).
    """
    # First pass: collect all entries grouped by city
    _city_entries: dict[str, list[tuple[str, str]]] = {}   # city → [(code, airport_name)]
    _airport_entries: list[tuple[str, str]] = []            # [(airport_name_lower, code)]

    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("iata_code") or "").strip().upper()
            if not code or len(code) != 3:
                continue

            _VALID_CODES.add(code)

            city = (row.get("city_name") or "").strip().lower()
            airport = (row.get("airport_name") or "").strip().lower()

            if city:
                _city_entries.setdefault(city, []).append((code, airport))
            if airport:
                _airport_entries.append((airport, code))

            # Always index the code itself
            _IATA_BY_NAME[code.lower()] = code

    # Resolve city names: prefer "international" airports
    for city, entries in _city_entries.items():
        intl = [e for e in entries if "international" in e[1]]
        best_code = intl[0][0] if intl else entries[0][0]
        if city not in _IATA_BY_NAME:
            _IATA_BY_NAME[city] = best_code

    # Index airport names (first-entry-wins is fine here)
    for airport, code in _airport_entries:
        if airport not in _IATA_BY_NAME:
            _IATA_BY_NAME[airport] = code


_load_iata_db()


@tool
def lookup_iata_code(location: str) -> str:
    """Look up the IATA airport code for a city, airport name, or IATA code.
    Call this tool BEFORE searching for flights to get the correct airport code.

    Args:
        location: City name (e.g. "Seattle"), airport name (e.g. "Narita"),
                  or IATA code (e.g. "SEA"). Case-insensitive.
    """
    key = location.strip().lower()

    # Direct match (city name, airport name, or lowered code)
    if key in _IATA_BY_NAME:
        code = _IATA_BY_NAME[key]
        return f"{code} — resolved from '{location}'"

    # Already a valid 3-letter IATA code
    upper = key.upper()
    if len(key) == 3 and upper in _VALID_CODES:
        return f"{upper} — already a valid IATA code"

    # Substring match — catches "tallinn" inside "tallinn-ulemiste international"
    if len(key) >= 4:
        matches = [(name, code) for name, code in _IATA_BY_NAME.items()
                   if key in name and len(name) > len(key)]
        if matches:
            # Prefer the shortest name (most specific match)
            best_name, best_code = min(matches, key=lambda x: len(x[0]))
            return f"{best_code} — resolved from '{location}' (substring match in '{best_name}')"

    # Fuzzy match against all known names
    candidates = get_close_matches(key, _IATA_BY_NAME.keys(), n=3, cutoff=0.6)
    if candidates:
        best = candidates[0]
        code = _IATA_BY_NAME[best]
        alternatives = ", ".join(
            f"{_IATA_BY_NAME[c]} ({c})" for c in candidates[1:]
        )
        result = f"{code} — closest match for '{location}' (matched '{best}')"
        if alternatives:
            result += f". Other possibilities: {alternatives}"
        return result

    return (
        f"No IATA code found for '{location}'. "
        "Try a major city name or airport name."
    )
