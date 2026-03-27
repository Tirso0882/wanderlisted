"""Shared fixtures for all tests."""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


# ── Helpers to detect available API keys ──────────────────────────────────


def _key_is_set(name: str) -> bool:
    val = os.environ.get(name, "")
    return bool(val) and not val.startswith("your-")


HAS_OPENWEATHER = _key_is_set("OPENWEATHER_API_KEY")
HAS_EXCHANGERATE = _key_is_set("EXCHANGERATE_API_KEY")
HAS_AMADEUS = _key_is_set("AMADEUS_API_KEY") and _key_is_set("AMADEUS_API_SECRET")
HAS_GOOGLE_MAPS = _key_is_set("GOOGLE_MAPS_API_KEY")
HAS_AZURE_OPENAI = _key_is_set("AZURE_OPENAI_API_KEY") and _key_is_set("AZURE_OPENAI_ENDPOINT")

skip_no_openweather = pytest.mark.skipif(
    not HAS_OPENWEATHER, reason="OPENWEATHER_API_KEY not set"
)
skip_no_exchangerate = pytest.mark.skipif(
    not HAS_EXCHANGERATE, reason="EXCHANGERATE_API_KEY not set"
)
skip_no_amadeus = pytest.mark.skipif(
    not HAS_AMADEUS, reason="AMADEUS_API_KEY / AMADEUS_API_SECRET not set"
)
skip_no_google_maps = pytest.mark.skipif(
    not HAS_GOOGLE_MAPS, reason="GOOGLE_MAPS_API_KEY not set"
)
skip_no_azure_openai = pytest.mark.skipif(
    not HAS_AZURE_OPENAI, reason="AZURE_OPENAI_API_KEY / ENDPOINT not set"
)
