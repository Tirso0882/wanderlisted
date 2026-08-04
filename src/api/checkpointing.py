"""Checkpoint backend selection and lifecycle for the production graph."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any


_DURABLE_ENVIRONMENTS = frozenset({"test", "prod", "production"})
_SUPPORTED_BACKENDS = frozenset({"memory", "postgres"})


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(
        "CHECKPOINT_AUTO_SETUP must be one of true/false, 1/0, yes/no, or on/off"
    )


@dataclass(frozen=True, slots=True)
class CheckpointSettings:
    """Validated, non-secret checkpoint configuration."""

    environment: str
    backend: str
    database_url: str | None = field(repr=False)
    auto_setup: bool = True

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "CheckpointSettings":
        deployment_environment = environment.get("ENVIRONMENT", "development").lower()
        default_backend = (
            "postgres" if deployment_environment in _DURABLE_ENVIRONMENTS else "memory"
        )
        backend = environment.get("CHECKPOINT_BACKEND", default_backend).lower()
        database_url = environment.get("CHECKPOINT_DATABASE_URL") or None
        auto_setup = _parse_bool(environment.get("CHECKPOINT_AUTO_SETUP"), default=True)

        if backend not in _SUPPORTED_BACKENDS:
            supported = ", ".join(sorted(_SUPPORTED_BACKENDS))
            raise RuntimeError(
                f"Unsupported CHECKPOINT_BACKEND {backend!r}; expected one of: {supported}"
            )
        if deployment_environment in _DURABLE_ENVIRONMENTS and backend != "postgres":
            raise RuntimeError(
                "Deployed environments require CHECKPOINT_BACKEND=postgres; "
                "in-memory checkpoints are not durable across workers or replicas"
            )
        if backend == "postgres" and not database_url:
            raise RuntimeError(
                "CHECKPOINT_DATABASE_URL is required when CHECKPOINT_BACKEND=postgres"
            )

        return cls(
            environment=deployment_environment,
            backend=backend,
            database_url=database_url,
            auto_setup=auto_setup,
        )


@asynccontextmanager
async def open_checkpointer(
    settings: CheckpointSettings,
) -> AsyncIterator[Any]:
    """Open the configured saver without logging its secret connection string."""

    if settings.backend == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        yield InMemorySaver()
        return

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    except ImportError as exc:  # pragma: no cover - packaging guard
        raise RuntimeError(
            "PostgreSQL checkpointing requires langgraph-checkpoint-postgres"
        ) from exc

    assert settings.database_url is not None
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as saver:
        if settings.auto_setup:
            await saver.setup()
        yield saver
