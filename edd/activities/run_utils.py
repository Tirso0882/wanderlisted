"""Bounded live-run and trajectory-cache helpers for Activities EDD."""

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
from src.agent.agents import ActivitiesAgent

ACTIVITIES_CASE_CONCURRENCY = 3
ACTIVITIES_RUN_TIMEOUT_SECONDS = 150.0
_ROOT = Path(__file__).resolve().parents[2]
BASELINE_CONFIG = get_baseline_config("activities")
_DEFAULT_CACHE_DIR = BASELINE_CONFIG.default_cache_dir
_CACHE_SOURCE_FILES = BASELINE_CONFIG.source_files

_EXTERNAL_OUTPUT_MARKERS = ("could not reach places api",)
_EXTERNAL_HTTP_ERROR_RE = re.compile(
    r"places api error \(http (?:401|403|429|5\d\d)\)", re.IGNORECASE
)
_EXTERNAL_ERROR_MARKERS = (
    "google_maps_api_key environment variable is not set",
    "authentication",
    "permissiondenied",
    "rate limit",
    "resourceexhausted",
)
_NO_INVENTORY_MARKERS = ("no places found", " found near ")
_SECRET_QUERY_PARAM_RE = re.compile(
    r"([?&](?:key|api[_-]?key|token|access_token)=)[A-Za-z0-9._~-]+",
    re.IGNORECASE,
)


def _redact_sensitive_text(text: str) -> str:
    """Remove credentials from provider URLs and errors before they reach disk."""
    return redact_text(text, BASELINE_CONFIG.secret_env_vars)


def _redact_cache_value(value):
    return redact_value(value, BASELINE_CONFIG.secret_env_vars)


def classify_activities_outcome(trajectory: Trajectory) -> str:
    """Classify task completion separately from model decision correctness.

    Values: completed, no_inventory, blocked_external, failed, infra_error.
    """
    if trajectory.error:
        error = trajectory.error.lower()
        if any(marker in error for marker in _EXTERNAL_ERROR_MARKERS):
            return "blocked_external"
        return "infra_error"

    outputs = [
        output
        for name, output in trajectory.tool_outputs
        if name in {"search_places_text", "search_places_nearby"}
    ]
    if not outputs:
        return "failed"

    lowered = [output.lower() for output in outputs]
    has_results = any(output.startswith("found ") for output in lowered)
    if has_results:
        return "completed" if trajectory.final_text.strip() else "failed"
    if any(
        marker in output for output in lowered for marker in _EXTERNAL_OUTPUT_MARKERS
    ) or any(_EXTERNAL_HTTP_ERROR_RE.search(output) for output in lowered):
        return "blocked_external"
    if all(
        output.startswith("no ")
        or any(marker in output for marker in _NO_INVENTORY_MARKERS)
        for output in lowered
    ):
        return "no_inventory"
    return "failed"


def _cache_path(queries: list[str], model_config: dict) -> Path:
    return trajectory_cache_path(BASELINE_CONFIG, queries, model_config)


def _load_trajectories(path: Path, queries: list[str]) -> list[Trajectory] | None:
    return load_trajectories(path, queries)


def _save_trajectories(
    path: Path, queries: list[str], trajectories: list[Trajectory]
) -> None:
    save_trajectories(path, BASELINE_CONFIG, queries, trajectories)


async def run_activities_dataset(
    queries: list[str],
    *,
    model_config: dict,
    max_concurrency: int = ACTIVITIES_CASE_CONCURRENCY,
    timeout: float = ACTIVITIES_RUN_TIMEOUT_SECONDS,
) -> list[Trajectory]:
    """Run or reuse a pinned ActivitiesAgent snapshot for a model and dataset."""
    return await run_cached_dataset(
        config=BASELINE_CONFIG,
        queries=queries,
        model_config=model_config,
        agent_cls=ActivitiesAgent,
        classify_outcome=classify_activities_outcome,
        run_agent_fn=run_agent,
        max_concurrency=max_concurrency,
        timeout=timeout,
    )
