"""Fail-closed cache and spend controls for Itinerary EDD Layers 2-4."""

from __future__ import annotations

import os

from edd.baseline_config import get_baseline_config
from edd.baseline_store import load_trajectories, trajectory_cache_path
from edd.harness import Trajectory

BASELINE_CONFIG = get_baseline_config("itinerary")


def _refresh_requested() -> bool:
    return os.environ.get("EDD_REFRESH", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _reject_live_refresh() -> None:
    if _refresh_requested():
        raise RuntimeError(
            "Itinerary EDD live refresh is disabled. Disclose exact provider requests, "
            "selection-model calls, judge calls, expected credits, and a budget cap, then "
            "obtain explicit approval before adding a capture path."
        )


def classify_itinerary_outcome(trajectory: Trajectory) -> str:
    if trajectory.error:
        lowered = trajectory.error.lower()
        if any(
            marker in lowered
            for marker in ("provider", "timeout", "rate limit", "model")
        ):
            return "blocked_external"
        return "infra_error"
    return "completed" if trajectory.final_text.strip() else "failed"


def load_cached_itinerary_trajectories(
    queries: list[str], *, model_config: dict
) -> list[Trajectory]:
    """Load an exact snapshot and never fall through to providers or models."""
    _reject_live_refresh()
    path = trajectory_cache_path(BASELINE_CONFIG, queries, model_config)
    trajectories = load_trajectories(path, queries)
    if trajectories is None:
        raise FileNotFoundError(
            f"Itinerary EDD cache miss at {path}. Live capture is intentionally disabled."
        )
    return trajectories


def require_judge_approval(*, layer: str, estimated_calls: int) -> None:
    _reject_live_refresh()
    if os.environ.get("EDD_LIVE_JUDGE_APPROVED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise RuntimeError(
            f"Itinerary {layer} would make approximately {estimated_calls} judge-model "
            "calls. Set EDD_LIVE_JUDGE_APPROVED=1 only after explicit approval."
        )
