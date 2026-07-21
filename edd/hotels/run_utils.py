"""Bounded live-run helper for Hotel EDD layers.

One HotelsAgent run can fan out to 3-5 Google Places calls after Hotelbeds.
Launching the entire dataset at once creates evaluator-induced 429s/timeouts,
which are infrastructure noise rather than model quality. Keep a small number
of cases in flight and allow enough time for the complete production workflow.
"""

from __future__ import annotations

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
from src.agent.agents import HotelsAgent

HOTEL_CASE_CONCURRENCY = 3
HOTEL_RUN_TIMEOUT_SECONDS = 180.0
_ROOT = Path(__file__).resolve().parents[2]
BASELINE_CONFIG = get_baseline_config("hotels")
_DEFAULT_CACHE_DIR = BASELINE_CONFIG.default_cache_dir
_CACHE_SOURCE_FILES = BASELINE_CONFIG.source_files

_EXTERNAL_FAILURE_MARKERS = (
    "hotelbeds api error",
    "could not reach hotelbeds api",
    "hotelbeds_api_key and hotelbeds_api_secret",
)


def _redact_sensitive_text(text: str) -> str:
    """Remove provider credentials before trajectories reach disk."""
    return redact_text(text, BASELINE_CONFIG.secret_env_vars)


def _redact_cache_value(value):
    return redact_value(value, BASELINE_CONFIG.secret_env_vars)


def classify_hotel_outcome(trajectory: Trajectory) -> str:
    """Classify the focused hotel task without conflating provider health.

    Values: completed, no_inventory, blocked_external, failed, infra_error.
    """
    if trajectory.error:
        return "infra_error"

    search_outputs = [
        output
        for name, output in trajectory.tool_outputs
        if name == "search_hotels_hotelbeds"
    ]
    if not search_outputs:
        return "failed"

    combined = "\n".join(search_outputs).lower()
    if any(marker in combined for marker in _EXTERNAL_FAILURE_MARKERS):
        return "blocked_external"
    if "no hotel offers found" in combined:
        return "no_inventory"
    return "completed" if trajectory.final_text.strip() else "failed"


def _cache_path(queries: list[str], model_config: dict) -> Path:
    """Key a snapshot by dataset, model config, and behavior-owning sources."""
    return trajectory_cache_path(BASELINE_CONFIG, queries, model_config)


def _load_trajectories(path: Path, queries: list[str]) -> list[Trajectory] | None:
    return load_trajectories(path, queries)


def _save_trajectories(
    path: Path, queries: list[str], trajectories: list[Trajectory]
) -> None:
    save_trajectories(path, BASELINE_CONFIG, queries, trajectories)


async def run_hotel_dataset(
    queries: list[str],
    *,
    model_config: dict,
    max_concurrency: int = HOTEL_CASE_CONCURRENCY,
    timeout: float = HOTEL_RUN_TIMEOUT_SECONDS,
) -> list[Trajectory]:
    """Run or reuse a pinned HotelsAgent snapshot for this model/dataset.

    Set `EDD_REFRESH=1` to force live recapture. Provider-blocked and
    infrastructure-error batches are never cached.
    """
    return await run_cached_dataset(
        config=BASELINE_CONFIG,
        queries=queries,
        model_config=model_config,
        agent_cls=HotelsAgent,
        classify_outcome=classify_hotel_outcome,
        run_agent_fn=run_agent,
        max_concurrency=max_concurrency,
        timeout=timeout,
    )
