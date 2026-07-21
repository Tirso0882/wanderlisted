"""Bounded live-run and trajectory-cache helpers for Flight EDD."""

from __future__ import annotations

import re
from pathlib import Path

from edd.baseline_store import (
    load_trajectories,
    redact_text,
    redact_value,
    run_cached_dataset,
    save_trajectories,
    trajectory_cache_path,
)
from edd.baseline_config import get_baseline_config
from edd.harness import Trajectory, run_agent
from src.agent.agents import FlightsAgent

FLIGHT_CASE_CONCURRENCY = 5
FLIGHT_RUN_TIMEOUT_SECONDS = 150.0
_ROOT = Path(__file__).resolve().parents[2]
BASELINE_CONFIG = get_baseline_config("flights")
_DEFAULT_CACHE_DIR = BASELINE_CONFIG.default_cache_dir
_CACHE_SOURCE_FILES = BASELINE_CONFIG.source_files

_EXTERNAL_OUTPUT_MARKERS = (
    "flight search error:",
    "unable to search flights",
)
_EXTERNAL_ERROR_MARKERS = (
    "duffel_access_token",
    "authentication",
    "unauthorized",
    "permissiondenied",
    "rate limit",
    "resourceexhausted",
    "connection error",
)
_SECRET_QUERY_PARAM_RE = re.compile(
    r"([?&](?:key|api[_-]?key|token|access_token)=)[A-Za-z0-9._~-]+",
    re.IGNORECASE,
)


def _redact_sensitive_text(text: str) -> str:
    """Remove credentials from provider output before it reaches disk."""
    return redact_text(text, BASELINE_CONFIG.secret_env_vars)


def _redact_cache_value(value):
    return redact_value(value, BASELINE_CONFIG.secret_env_vars)


def classify_flight_outcome(trajectory: Trajectory) -> str:
    """Classify completion separately from model decision correctness.

    Values: completed, no_inventory, blocked_external, failed, infra_error.
    """
    if trajectory.error:
        error = trajectory.error.lower()
        if any(marker in error for marker in _EXTERNAL_ERROR_MARKERS):
            return "blocked_external"
        return "infra_error"

    outputs = [
        output for name, output in trajectory.tool_outputs if name == "search_flights"
    ]
    if not outputs:
        return "failed"

    combined = "\n".join(outputs).lower()
    if any(marker in combined for marker in _EXTERNAL_OUTPUT_MARKERS):
        return "blocked_external"
    if "no flights found" in combined:
        return "no_inventory"
    has_results = any(output.lstrip().lower().startswith("top ") for output in outputs)
    return "completed" if has_results and trajectory.final_text.strip() else "failed"


def _cache_path(queries: list[str], model_config: dict) -> Path:
    """Key a snapshot by dataset, model configuration, and behavior sources."""
    return trajectory_cache_path(BASELINE_CONFIG, queries, model_config)


def _load_trajectories(path: Path, queries: list[str]) -> list[Trajectory] | None:
    return load_trajectories(path, queries)


def _save_trajectories(
    path: Path, queries: list[str], trajectories: list[Trajectory]
) -> None:
    save_trajectories(path, BASELINE_CONFIG, queries, trajectories)


async def run_flight_dataset(
    queries: list[str],
    *,
    model_config: dict,
    max_concurrency: int = FLIGHT_CASE_CONCURRENCY,
    timeout: float = FLIGHT_RUN_TIMEOUT_SECONDS,
) -> list[Trajectory]:
    """Run or reuse one pinned FlightsAgent snapshot for a model/dataset.

    Set ``EDD_REFRESH=1`` to force live recapture. Provider-blocked and
    infrastructure-error batches are never cached.
    """
    return await run_cached_dataset(
        config=BASELINE_CONFIG,
        queries=queries,
        model_config=model_config,
        agent_cls=FlightsAgent,
        classify_outcome=classify_flight_outcome,
        run_agent_fn=run_agent,
        max_concurrency=max_concurrency,
        timeout=timeout,
    )
