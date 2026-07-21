"""Single source of truth for component EDD cache and baseline configuration."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

from edd.activities.l1_dataset import DATASET_VERSION as ACTIVITIES_DATASET_VERSION
from edd.baseline_store import BaselineConfig
from edd.flights.l1_dataset import DATASET_VERSION as FLIGHTS_DATASET_VERSION
from edd.hotels.l1_dataset import DATASET_VERSION as HOTELS_DATASET_VERSION
from edd.restaurants.l1_dataset import DATASET_VERSION as RESTAURANTS_DATASET_VERSION
from edd.transportation.l1_dataset import (
    DATASET_VERSION as TRANSPORTATION_DATASET_VERSION,
)

_ROOT = Path(__file__).resolve().parents[1]
_EDD_ROOT = _ROOT / "edd"
_PROMPT_SOURCE = _ROOT / "src" / "agent" / "prompts" / "agent_prompt.py"
_LLM_SOURCE = _ROOT / "src" / "agent" / "llm.py"
_HARNESS_SOURCE = _EDD_ROOT / "harness.py"


def _component_config(
    component: str,
    *,
    dataset_version: str,
    cache_env_var: str,
    display_name: str,
    sources: tuple[Path, ...],
    secret_env_vars: tuple[str, ...],
) -> BaselineConfig:
    return BaselineConfig(
        component=component,
        dataset_version=dataset_version,
        source_files=(
            Path(__file__).resolve(),
            _EDD_ROOT / component / "run_utils.py",
            _HARNESS_SOURCE,
            _EDD_ROOT / component / "l1_dataset.py",
            _LLM_SOURCE,
            _PROMPT_SOURCE,
            *sources,
        ),
        cache_env_var=cache_env_var,
        default_cache_dir=_EDD_ROOT / component / ".cache",
        secret_env_vars=secret_env_vars,
        display_name=display_name,
    )


BASELINE_CONFIGS = MappingProxyType(
    {
        "flights": _component_config(
            "flights",
            dataset_version=FLIGHTS_DATASET_VERSION,
            cache_env_var="EDD_FLIGHT_CACHE_DIR",
            display_name="Flight",
            secret_env_vars=("DUFFEL_ACCESS_TOKEN",),
            sources=(
                _ROOT / "src" / "agent" / "agents" / "flights_agent.py",
                _ROOT / "src" / "tools" / "flights_duffel.py",
                _ROOT / "src" / "tools" / "iata.py",
                _ROOT / "src" / "tools" / "iata_repository.py",
                _ROOT / "src" / "data" / "iata_codes.csv",
                _ROOT / "src" / "data" / "iata" / "aliases.csv",
                _ROOT / "src" / "data" / "iata" / "primary_airports.csv",
                _ROOT / "src" / "data" / "iata" / "countries.csv",
            ),
        ),
        "hotels": _component_config(
            "hotels",
            dataset_version=HOTELS_DATASET_VERSION,
            cache_env_var="EDD_HOTEL_CACHE_DIR",
            display_name="Hotel",
            secret_env_vars=(
                "HOTELBEDS_API_KEY",
                "HOTELBEDS_API_SECRET",
                "GOOGLE_MAPS_API_KEY",
            ),
            sources=(
                _ROOT / "src" / "agent" / "agents" / "hotels_agent.py",
                _ROOT / "src" / "tools" / "hotels_hotelbeds.py",
                _ROOT / "src" / "tools" / "activities.py",
                _ROOT / "src" / "tools" / "google_maps.py",
            ),
        ),
        "restaurants": _component_config(
            "restaurants",
            dataset_version=RESTAURANTS_DATASET_VERSION,
            cache_env_var="EDD_RESTAURANT_CACHE_DIR",
            display_name="Restaurant",
            secret_env_vars=("GOOGLE_MAPS_API_KEY",),
            sources=(
                _ROOT / "src" / "agent" / "agents" / "restaurants_agent.py",
                _ROOT / "src" / "tools" / "google_maps.py",
            ),
        ),
        "activities": _component_config(
            "activities",
            dataset_version=ACTIVITIES_DATASET_VERSION,
            cache_env_var="EDD_ACTIVITIES_CACHE_DIR",
            display_name="Activities",
            secret_env_vars=("GOOGLE_MAPS_API_KEY",),
            sources=(
                _ROOT / "src" / "agent" / "agents" / "activities_agent.py",
                _ROOT / "src" / "tools" / "google_maps.py",
            ),
        ),
        "transportation": _component_config(
            "transportation",
            dataset_version=TRANSPORTATION_DATASET_VERSION,
            cache_env_var="EDD_TRANSPORTATION_CACHE_DIR",
            display_name="Transportation",
            secret_env_vars=("GOOGLE_MAPS_API_KEY",),
            sources=(
                _ROOT / "src" / "agent" / "agents" / "transportation_agent.py",
                _ROOT / "src" / "tools" / "google_maps.py",
            ),
        ),
    }
)


def get_baseline_config(component: str) -> BaselineConfig:
    """Return the immutable baseline configuration for an EDD component."""
    try:
        return BASELINE_CONFIGS[component]
    except KeyError as exc:
        supported = ", ".join(sorted(BASELINE_CONFIGS))
        raise KeyError(
            f"no EDD baseline configuration for {component!r}; supported: {supported}"
        ) from exc
