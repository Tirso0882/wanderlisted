"""IATA airport-code lookup backed by process-scoped CSV repositories."""

from langchain_core.tools import tool

from src.tools.iata_repository import IATA_REPOSITORY

# Compatibility views for existing imports. The repository owns these immutable
# indexes; new code should use the public helper functions below.
_IATA_BY_NAME = IATA_REPOSITORY.codes_by_name
_VALID_CODES = IATA_REPOSITORY.valid_codes
_COUNTRY_BY_CODE = IATA_REPOSITORY.countries_by_code

# ── Public helpers ────────────────────────────────────────────────────────


def get_airport_country(iata_code: str) -> str:
    """Return the country name for a given IATA airport code, or empty string."""
    return IATA_REPOSITORY.country_for_code(iata_code)


def iata_to_flag_emoji(iata_code: str) -> str:
    """Derive a country flag emoji from an IATA code via country name lookup."""
    iso = IATA_REPOSITORY.country_iso_for_code(iata_code)
    if not iso:
        return ""
    # Convert ISO-3166-1 alpha-2 to flag emoji (regional indicator symbols)
    return chr(ord(iso[0]) + 0x1F1A5) + chr(ord(iso[1]) + 0x1F1A5)


@tool
def lookup_iata_code(location: str) -> str:
    """Look up the IATA airport code for a city, airport name, or IATA code.
    Call this tool BEFORE searching for flights to get the correct airport code.

    Args:
        location: City name (e.g. "Seattle"), airport name (e.g. "Narita"),
                  or IATA code (e.g. "SEA"). Case-insensitive.
    """
    code = resolve_iata_code(location)
    if code:
        key = location.strip().lower()
        if len(key) == 3 and key.upper() == code:
            return f"{code} — already a valid IATA code"
        return f"{code} — resolved from '{location}'"
    return (
        f"No IATA code found for '{location}'. Try a major city name or airport name."
    )


def resolve_iata_code(location: str) -> str | None:
    """Resolve a city/airport/code to one IATA code without presentation text."""
    return IATA_REPOSITORY.resolve_code(location)
