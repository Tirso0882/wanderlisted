"""Unit tests for IATA lookup tool — no external APIs, CSV-backed."""

from src.tools.iata import (
    _IATA_BY_NAME,
    _VALID_CODES,
    lookup_iata_code,
)


class TestIATADataLoading:
    """Verify the CSV was loaded correctly at import time."""

    def test_loaded_thousands_of_entries(self):
        assert len(_IATA_BY_NAME) > 10_000

    def test_loaded_thousands_of_codes(self):
        assert len(_VALID_CODES) > 5_000

    def test_common_codes_present(self):
        for code in ["JFK", "LAX", "NRT", "LHR", "CDG", "SEA"]:
            assert code in _VALID_CODES


class TestDirectMatch:
    """Exact city name, airport name, or IATA code lookups."""

    def test_city_name(self):
        result = lookup_iata_code.invoke("Seattle")
        assert "SEA" in result

    def test_city_name_case_insensitive(self):
        result = lookup_iata_code.invoke("sEaTtLe")
        assert "SEA" in result

    def test_iata_code_as_input(self):
        result = lookup_iata_code.invoke("NRT")
        assert "NRT" in result

    def test_lowercased_iata_code(self):
        result = lookup_iata_code.invoke("nrt")
        assert "NRT" in result

    def test_international_airport_preference(self):
        """Fairbanks should resolve to FAI (international), not EIL (air base)."""
        result = lookup_iata_code.invoke("Fairbanks")
        assert "FAI" in result


class TestSubstringMatch:
    """Substring fallback for names like 'Tallinn' inside longer CSV entries."""

    def test_tallinn(self):
        result = lookup_iata_code.invoke("Tallinn")
        assert "TLL" in result

    def test_substring_result_explains_match(self):
        result = lookup_iata_code.invoke("Tallinn")
        assert "substring match" in result.lower() or "resolved" in result.lower()


class TestFuzzyMatch:
    """Fuzzy matching via difflib for misspelled inputs."""

    def test_fuzzy_seattle(self):
        result = lookup_iata_code.invoke("Seattl")
        assert "SEA" in result

    def test_fuzzy_includes_match_explanation(self):
        result = lookup_iata_code.invoke("Seattl")
        assert "closest match" in result.lower() or "resolved" in result.lower()


class TestNoMatch:
    """Inputs that shouldn't match anything."""

    def test_gibberish(self):
        result = lookup_iata_code.invoke("xyzzyplugh123")
        assert "No IATA code found" in result

    def test_empty_string(self):
        result = lookup_iata_code.invoke("")
        assert "No IATA code found" in result or result  # shouldn't crash


class TestWhitespaceHandling:
    def test_leading_trailing_spaces(self):
        result = lookup_iata_code.invoke("  Tokyo  ")
        assert "NRT" in result
