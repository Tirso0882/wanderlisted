"""Cache-only helpers for Budget EDD Layers 2-4."""

from __future__ import annotations

import os

from edd.baseline_config import get_baseline_config
from edd.baseline_store import load_trajectories, trajectory_cache_path
from edd.harness import Trajectory

BASELINE_CONFIG = get_baseline_config("budget")


def classify_budget_outcome(trajectory: Trajectory) -> str:
    if trajectory.error:
        lowered = trajectory.error.lower()
        if any(
            marker in lowered
            for marker in ("exchange", "provider", "timeout", "rate limit")
        ):
            return "blocked_external"
        return "infra_error"
    return "completed" if trajectory.final_text.strip() else "failed"


def load_cached_budget_trajectories(
    queries: list[str], *, model_config: dict
) -> list[Trajectory]:
    """Load a pinned snapshot and fail closed instead of capturing live data."""
    if os.environ.get("EDD_REFRESH", "").strip().lower() in {"1", "true", "yes"}:
        raise RuntimeError(
            "Budget EDD live refresh is disabled. Provide a request/model-call/credit "
            "estimate and obtain explicit approval before adding a capture path."
        )
    path = trajectory_cache_path(BASELINE_CONFIG, queries, model_config)
    trajectories = load_trajectories(path, queries)
    if trajectories is None:
        raise FileNotFoundError(
            f"Budget EDD cache miss at {path}. Live capture is intentionally disabled."
        )
    return trajectories


def require_judge_approval(*, layer: str, estimated_calls: int) -> None:
    """Prevent silent model spend in pointwise, pairwise, and calibration runs."""
    if os.environ.get("EDD_LIVE_JUDGE_APPROVED", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise RuntimeError(
            f"Budget {layer} would make approximately {estimated_calls} judge-model "
            "calls. Set EDD_LIVE_JUDGE_APPROVED=1 only after explicit approval."
        )
