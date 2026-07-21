"""Shared fixtures for all tests."""

import os

import pytest
from dotenv import load_dotenv

load_dotenv(override=True)

# Disable LangSmith tracing for all tests - Speeds up runs (no background HTTP calls to api.smith.langchain.com).
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

# ── Helpers to detect available API keys ──────────────────────────────────


def _key_is_set(name: str) -> bool:
    val = os.environ.get(name, "")
    return bool(val) and not val.startswith("your-")


HAS_OPENWEATHER = _key_is_set("OPENWEATHER_API_KEY")
HAS_EXCHANGERATE = _key_is_set("EXCHANGERATE_API_KEY")
HAS_GOOGLE_MAPS = _key_is_set("GOOGLE_MAPS_API_KEY")
HAS_HOTELBEDS = _key_is_set("HOTELBEDS_API_KEY") and _key_is_set("HOTELBEDS_API_SECRET")
HAS_AZURE_OPENAI = _key_is_set("AZURE_OPENAI_API_KEY") and _key_is_set(
    "AZURE_OPENAI_ENDPOINT"
)
HAS_DUFFEL = _key_is_set("DUFFEL_ACCESS_TOKEN")

skip_no_openweather = pytest.mark.skipif(
    not HAS_OPENWEATHER, reason="OPENWEATHER_API_KEY not set"
)
skip_no_exchangerate = pytest.mark.skipif(
    not HAS_EXCHANGERATE, reason="EXCHANGERATE_API_KEY not set"
)
skip_no_google_maps = pytest.mark.skipif(
    not HAS_GOOGLE_MAPS, reason="GOOGLE_MAPS_API_KEY not set"
)
skip_no_hotelbeds = pytest.mark.skipif(
    not HAS_HOTELBEDS, reason="HOTELBEDS_API_KEY / HOTELBEDS_API_SECRET not set"
)
skip_no_azure_openai = pytest.mark.skipif(
    not HAS_AZURE_OPENAI, reason="AZURE_OPENAI_API_KEY / ENDPOINT not set"
)
skip_no_duffel = pytest.mark.skipif(
    not HAS_DUFFEL, reason="DUFFEL_ACCESS_TOKEN not set"
)
