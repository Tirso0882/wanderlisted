"""Process-local development and Redis-backed distributed rate limiting."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol


_DEPLOYED_ENVIRONMENTS = frozenset({"test", "prod", "production"})
_REDIS_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


class RateLimiterUnavailable(RuntimeError):
    """The shared production limiter cannot make a safe decision."""


class RateLimiter(Protocol):
    async def check(self, principal_id: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class RateLimitSettings:
    environment: str
    backend: str
    redis_url: str | None = field(repr=False)
    max_requests: int = 20
    window_seconds: int = 60
    key_prefix: str = "wanderlisted:rate"

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "RateLimitSettings":
        deployment_environment = environment.get("ENVIRONMENT", "development").lower()
        default_backend = (
            "redis" if deployment_environment in _DEPLOYED_ENVIRONMENTS else "memory"
        )
        backend = environment.get("RATE_LIMIT_BACKEND", default_backend).lower()
        if backend not in {"memory", "redis"}:
            raise RuntimeError("RATE_LIMIT_BACKEND must be memory or redis")
        if deployment_environment in _DEPLOYED_ENVIRONMENTS and backend != "redis":
            raise RuntimeError("Deployed environments require RATE_LIMIT_BACKEND=redis")

        redis_url = environment.get("REDIS_URL") or None
        if backend == "redis" and not redis_url:
            raise RuntimeError("REDIS_URL is required when RATE_LIMIT_BACKEND=redis")

        max_requests = int(environment.get("RATE_LIMIT_MAX", "20"))
        window_seconds = int(environment.get("RATE_LIMIT_WINDOW", "60"))
        if max_requests <= 0 or window_seconds <= 0:
            raise RuntimeError("RATE_LIMIT_MAX and RATE_LIMIT_WINDOW must be positive")

        return cls(
            environment=deployment_environment,
            backend=backend,
            redis_url=redis_url,
            max_requests=max_requests,
            window_seconds=window_seconds,
            key_prefix=environment.get("RATE_LIMIT_KEY_PREFIX", "wanderlisted:rate"),
        )


class MemoryRateLimiter:
    """Bounded single-process limiter for local development only."""

    def __init__(self, settings: RateLimitSettings, *, max_keys: int = 10_000) -> None:
        self.settings = settings
        self.max_keys = max_keys
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()

    async def check(self, principal_id: str) -> bool:
        now = time.monotonic()
        key = hashlib.sha256(principal_id.encode("utf-8")).hexdigest()
        async with self._lock:
            expired = [
                item_key
                for item_key, (started, _) in self._windows.items()
                if now - started >= self.settings.window_seconds
            ]
            for item_key in expired:
                self._windows.pop(item_key, None)

            started, count = self._windows.get(key, (now, 0))
            if key not in self._windows and len(self._windows) >= self.max_keys:
                return False
            if count >= self.settings.max_requests:
                return False
            self._windows[key] = (started, count + 1)
            return True


class RedisRateLimiter:
    """Atomic fixed-window limiter shared by all workers and replicas."""

    def __init__(self, client: Any, settings: RateLimitSettings) -> None:
        self.client = client
        self.settings = settings

    async def check(self, principal_id: str) -> bool:
        principal_hash = hashlib.sha256(principal_id.encode("utf-8")).hexdigest()
        key = f"{self.settings.key_prefix}:{principal_hash}"
        try:
            current = await self.client.eval(
                _REDIS_SCRIPT,
                1,
                key,
                self.settings.window_seconds,
            )
        except Exception as exc:
            raise RateLimiterUnavailable("shared rate limiter unavailable") from exc
        return int(current) <= self.settings.max_requests


@asynccontextmanager
async def open_rate_limiter(
    settings: RateLimitSettings,
) -> AsyncIterator[RateLimiter]:
    if settings.backend == "memory":
        yield MemoryRateLimiter(settings)
        return

    try:
        from redis.asyncio import Redis
    except ImportError as exc:  # pragma: no cover - packaging guard
        raise RuntimeError("Redis rate limiting requires the redis package") from exc

    assert settings.redis_url is not None
    client = Redis.from_url(settings.redis_url, decode_responses=False)
    try:
        await client.ping()
        yield RedisRateLimiter(client, settings)
    finally:
        await client.aclose()
