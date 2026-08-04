"""Opaque-owner session index backed by memory locally and PostgreSQL in production."""

from __future__ import annotations

import asyncio
import base64
import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol


_DEPLOYED_ENVIRONMENTS = frozenset({"test", "prod", "production"})
_SUPPORTED_BACKENDS = frozenset({"memory", "postgres"})
_TITLE_WHITESPACE = re.compile(r"\s+")


def deterministic_conversation_title(message: str, *, max_length: int = 64) -> str:
    """Create a stable, non-model title from the first user turn."""

    normalized = _TITLE_WHITESPACE.sub(" ", message).strip()
    if not normalized:
        return "New trip"
    words = normalized.split(" ")[:10]
    title = " ".join(words)
    if len(title) > max_length:
        title = title[: max_length - 1].rstrip() + "…"
    elif len(words) < len(normalized.split(" ")):
        title = title.rstrip(".,;:!? ") + "…"
    return title


def encode_cursor(updated_at: datetime, checkpoint_thread_id: str) -> str:
    payload = json.dumps(
        [updated_at.astimezone(UTC).isoformat(), checkpoint_thread_id],
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
        updated_at = datetime.fromisoformat(payload[0])
        thread_id = str(payload[1])
        if updated_at.tzinfo is None or not thread_id.startswith("session:"):
            raise ValueError
        return updated_at.astimezone(UTC), thread_id
    except (ValueError, TypeError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid session cursor") from exc


@dataclass(frozen=True, slots=True)
class SessionRegistrySettings:
    environment: str
    backend: str
    database_url: str | None = field(repr=False)
    auto_setup: bool = True
    retention_days: int = 365

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str]
    ) -> "SessionRegistrySettings":
        deployment_environment = environment.get("ENVIRONMENT", "development").lower()
        default_backend = (
            "postgres" if deployment_environment in _DEPLOYED_ENVIRONMENTS else "memory"
        )
        backend = environment.get("SESSION_REGISTRY_BACKEND", default_backend).lower()
        database_url = (
            environment.get("SESSION_REGISTRY_DATABASE_URL")
            or environment.get("CHECKPOINT_DATABASE_URL")
            or None
        )
        auto_setup = environment.get(
            "SESSION_REGISTRY_AUTO_SETUP",
            environment.get("CHECKPOINT_AUTO_SETUP", "true"),
        ).strip().lower() in {"1", "true", "yes", "on"}
        retention_days = int(environment.get("SESSION_RETENTION_DAYS", "365"))

        if backend not in _SUPPORTED_BACKENDS:
            raise RuntimeError("SESSION_REGISTRY_BACKEND must be memory or postgres")
        if deployment_environment in _DEPLOYED_ENVIRONMENTS and backend != "postgres":
            raise RuntimeError(
                "Deployed environments require SESSION_REGISTRY_BACKEND=postgres"
            )
        if backend == "postgres" and not database_url:
            raise RuntimeError(
                "SESSION_REGISTRY_DATABASE_URL or CHECKPOINT_DATABASE_URL is required"
            )
        if not 30 <= retention_days <= 3650:
            raise RuntimeError("SESSION_RETENTION_DAYS must be between 30 and 3650")
        return cls(
            environment=deployment_environment,
            backend=backend,
            database_url=database_url,
            auto_setup=auto_setup,
            retention_days=retention_days,
        )


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    checkpoint_thread_id: str
    browser_owner_key: str
    account_owner_key: str | None
    title: str
    created_at: datetime
    updated_at: datetime
    locale: str
    message_count: int


class SessionRegistry(Protocol):
    async def register_turn(
        self,
        *,
        session_id: str,
        checkpoint_thread_id: str,
        browser_owner_key: str,
        account_owner_key: str | None,
        first_message: str,
        locale: str,
        message_count: int,
    ) -> SessionRecord: ...

    async def find_accessible(
        self,
        *,
        session_id: str,
        browser_owner_key: str,
        account_owner_key: str | None,
    ) -> SessionRecord | None: ...

    async def list_account_sessions(
        self,
        account_owner_key: str,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[SessionRecord], str | None]: ...

    async def claim_sessions(
        self,
        *,
        browser_owner_key: str,
        account_owner_key: str,
        session_ids: Sequence[str],
    ) -> int: ...

    async def delete_accessible(
        self,
        *,
        session_id: str,
        browser_owner_key: str,
        account_owner_key: str | None,
    ) -> str | None: ...

    async def get_preference(self, account_owner_key: str) -> str | None: ...

    async def put_preference(self, account_owner_key: str, locale: str) -> None: ...

    async def purge_inactive_saved(self, before: datetime) -> list[str]: ...

    async def delete_account(self, account_owner_key: str) -> list[str]: ...

    async def account_thread_ids(self, account_owner_key: str) -> list[str]: ...


class MemorySessionRegistry:
    """Deterministic local/test registry with the production ownership semantics."""

    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._preferences: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def register_turn(
        self,
        *,
        session_id: str,
        checkpoint_thread_id: str,
        browser_owner_key: str,
        account_owner_key: str | None,
        first_message: str,
        locale: str,
        message_count: int,
    ) -> SessionRecord:
        now = datetime.now(UTC)
        async with self._lock:
            existing = self._records.get(checkpoint_thread_id)
            if existing:
                if (
                    existing.session_id != session_id
                    or existing.browser_owner_key != browser_owner_key
                ):
                    raise ValueError("Checkpoint thread identity is immutable")
                record = replace(
                    existing,
                    account_owner_key=existing.account_owner_key or account_owner_key,
                    updated_at=now,
                    locale=locale,
                    message_count=max(existing.message_count, message_count),
                )
            else:
                record = SessionRecord(
                    session_id=session_id,
                    checkpoint_thread_id=checkpoint_thread_id,
                    browser_owner_key=browser_owner_key,
                    account_owner_key=account_owner_key,
                    title=deterministic_conversation_title(first_message),
                    created_at=now,
                    updated_at=now,
                    locale=locale,
                    message_count=max(0, message_count),
                )
            self._records[checkpoint_thread_id] = record
            return record

    async def find_accessible(
        self,
        *,
        session_id: str,
        browser_owner_key: str,
        account_owner_key: str | None,
    ) -> SessionRecord | None:
        async with self._lock:
            candidates = [
                record
                for record in self._records.values()
                if record.session_id == session_id
                and (
                    record.browser_owner_key == browser_owner_key
                    or (
                        account_owner_key is not None
                        and record.account_owner_key == account_owner_key
                    )
                )
            ]
            return max(candidates, key=lambda item: item.updated_at, default=None)

    async def list_account_sessions(
        self,
        account_owner_key: str,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[SessionRecord], str | None]:
        boundary = decode_cursor(cursor) if cursor else None
        async with self._lock:
            records = sorted(
                (
                    record
                    for record in self._records.values()
                    if record.account_owner_key == account_owner_key
                    and (
                        boundary is None
                        or (record.updated_at, record.checkpoint_thread_id) < boundary
                    )
                ),
                key=lambda item: (item.updated_at, item.checkpoint_thread_id),
                reverse=True,
            )
            page = records[:limit]
            next_cursor = (
                encode_cursor(page[-1].updated_at, page[-1].checkpoint_thread_id)
                if len(records) > limit and page
                else None
            )
            return page, next_cursor

    async def claim_sessions(
        self,
        *,
        browser_owner_key: str,
        account_owner_key: str,
        session_ids: Sequence[str],
    ) -> int:
        selected = set(session_ids)
        claimed = 0
        async with self._lock:
            for thread_id, record in list(self._records.items()):
                if (
                    record.browser_owner_key == browser_owner_key
                    and record.session_id in selected
                    and record.account_owner_key in {None, account_owner_key}
                ):
                    if record.account_owner_key is None:
                        claimed += 1
                    self._records[thread_id] = replace(
                        record,
                        account_owner_key=account_owner_key,
                        updated_at=datetime.now(UTC),
                    )
        return claimed

    async def delete_accessible(
        self,
        *,
        session_id: str,
        browser_owner_key: str,
        account_owner_key: str | None,
    ) -> str | None:
        record = await self.find_accessible(
            session_id=session_id,
            browser_owner_key=browser_owner_key,
            account_owner_key=account_owner_key,
        )
        if record is None:
            return None
        async with self._lock:
            self._records.pop(record.checkpoint_thread_id, None)
        return record.checkpoint_thread_id

    async def get_preference(self, account_owner_key: str) -> str | None:
        async with self._lock:
            return self._preferences.get(account_owner_key)

    async def put_preference(self, account_owner_key: str, locale: str) -> None:
        async with self._lock:
            self._preferences[account_owner_key] = locale

    async def purge_inactive_saved(self, before: datetime) -> list[str]:
        async with self._lock:
            stale = [
                thread_id
                for thread_id, record in self._records.items()
                if record.account_owner_key is not None and record.updated_at < before
            ]
            for thread_id in stale:
                self._records.pop(thread_id, None)
            return stale

    async def delete_account(self, account_owner_key: str) -> list[str]:
        async with self._lock:
            owned = [
                thread_id
                for thread_id, record in self._records.items()
                if record.account_owner_key == account_owner_key
            ]
            for thread_id in owned:
                self._records.pop(thread_id, None)
            self._preferences.pop(account_owner_key, None)
            return owned

    async def account_thread_ids(self, account_owner_key: str) -> list[str]:
        async with self._lock:
            return [
                thread_id
                for thread_id, record in self._records.items()
                if record.account_owner_key == account_owner_key
            ]


class PostgresSessionRegistry:
    """Small PostgreSQL index; checkpoint payloads stay in LangGraph tables."""

    def __init__(self, pool) -> None:
        self._pool = pool

    async def setup(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS wanderlisted_sessions (
                checkpoint_thread_id TEXT PRIMARY KEY,
                public_session_id TEXT NOT NULL,
                browser_owner_key TEXT NOT NULL,
                account_owner_key TEXT,
                title TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                locale VARCHAR(2) NOT NULL CHECK (locale IN ('en', 'pl')),
                message_count INTEGER NOT NULL CHECK (message_count >= 0)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS wanderlisted_sessions_browser_idx
            ON wanderlisted_sessions (browser_owner_key, public_session_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS wanderlisted_sessions_account_idx
            ON wanderlisted_sessions (account_owner_key, updated_at DESC)
            WHERE account_owner_key IS NOT NULL
            """,
            """
            CREATE TABLE IF NOT EXISTS wanderlisted_account_preferences (
                account_owner_key TEXT PRIMARY KEY,
                locale VARCHAR(2) NOT NULL CHECK (locale IN ('en', 'pl')),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
        )
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                for statement in statements:
                    await cursor.execute(statement)

    @staticmethod
    def _record(row) -> SessionRecord:
        return SessionRecord(
            session_id=row["public_session_id"],
            checkpoint_thread_id=row["checkpoint_thread_id"],
            browser_owner_key=row["browser_owner_key"],
            account_owner_key=row["account_owner_key"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            locale=row["locale"],
            message_count=row["message_count"],
        )

    async def register_turn(self, **values) -> SessionRecord:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO wanderlisted_sessions (
                        checkpoint_thread_id, public_session_id, browser_owner_key,
                        account_owner_key, title, locale, message_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (checkpoint_thread_id) DO UPDATE SET
                        account_owner_key = COALESCE(
                            wanderlisted_sessions.account_owner_key,
                            EXCLUDED.account_owner_key
                        ),
                        updated_at = NOW(),
                        locale = EXCLUDED.locale,
                        message_count = GREATEST(
                            wanderlisted_sessions.message_count,
                            EXCLUDED.message_count
                        )
                    WHERE wanderlisted_sessions.public_session_id = EXCLUDED.public_session_id
                      AND wanderlisted_sessions.browser_owner_key = EXCLUDED.browser_owner_key
                    RETURNING *
                    """,
                    (
                        values["checkpoint_thread_id"],
                        values["session_id"],
                        values["browser_owner_key"],
                        values["account_owner_key"],
                        deterministic_conversation_title(values["first_message"]),
                        values["locale"],
                        max(0, values["message_count"]),
                    ),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise ValueError("Checkpoint thread identity is immutable")
                return self._record(row)

    async def find_accessible(self, **values) -> SessionRecord | None:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT * FROM wanderlisted_sessions
                    WHERE public_session_id = %s
                      AND (
                        browser_owner_key = %s
                        OR (%s IS NOT NULL AND account_owner_key = %s)
                      )
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (
                        values["session_id"],
                        values["browser_owner_key"],
                        values["account_owner_key"],
                        values["account_owner_key"],
                    ),
                )
                row = await cursor.fetchone()
                return self._record(row) if row else None

    async def list_account_sessions(
        self,
        account_owner_key: str,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[SessionRecord], str | None]:
        boundary = decode_cursor(cursor) if cursor else None
        params: list[object] = [account_owner_key]
        condition = ""
        if boundary:
            condition = "AND (updated_at, checkpoint_thread_id) < (%s, %s)"
            params.extend(boundary)
        params.append(limit + 1)
        async with self._pool.connection() as connection:
            async with connection.cursor() as db_cursor:
                await db_cursor.execute(
                    f"""
                    SELECT * FROM wanderlisted_sessions
                    WHERE account_owner_key = %s {condition}
                    ORDER BY updated_at DESC, checkpoint_thread_id DESC
                    LIMIT %s
                    """,  # nosec B608 - condition is a fixed internal fragment
                    params,
                )
                rows = await db_cursor.fetchall()
        records = [self._record(row) for row in rows[:limit]]
        next_cursor = (
            encode_cursor(records[-1].updated_at, records[-1].checkpoint_thread_id)
            if len(rows) > limit and records
            else None
        )
        return records, next_cursor

    async def claim_sessions(self, **values) -> int:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    UPDATE wanderlisted_sessions
                    SET account_owner_key = %s, updated_at = NOW()
                    WHERE browser_owner_key = %s
                      AND public_session_id = ANY(%s)
                      AND (account_owner_key IS NULL OR account_owner_key = %s)
                    """,
                    (
                        values["account_owner_key"],
                        values["browser_owner_key"],
                        list(values["session_ids"]),
                        values["account_owner_key"],
                    ),
                )
                return cursor.rowcount

    async def delete_accessible(self, **values) -> str | None:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    DELETE FROM wanderlisted_sessions
                    WHERE checkpoint_thread_id = (
                        SELECT checkpoint_thread_id FROM wanderlisted_sessions
                        WHERE public_session_id = %s
                          AND (
                            browser_owner_key = %s
                            OR (%s IS NOT NULL AND account_owner_key = %s)
                          )
                        ORDER BY updated_at DESC LIMIT 1
                    )
                    RETURNING checkpoint_thread_id
                    """,
                    (
                        values["session_id"],
                        values["browser_owner_key"],
                        values["account_owner_key"],
                        values["account_owner_key"],
                    ),
                )
                row = await cursor.fetchone()
                return row["checkpoint_thread_id"] if row else None

    async def get_preference(self, account_owner_key: str) -> str | None:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT locale FROM wanderlisted_account_preferences WHERE account_owner_key = %s",
                    (account_owner_key,),
                )
                row = await cursor.fetchone()
                return row["locale"] if row else None

    async def put_preference(self, account_owner_key: str, locale: str) -> None:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    INSERT INTO wanderlisted_account_preferences (account_owner_key, locale)
                    VALUES (%s, %s)
                    ON CONFLICT (account_owner_key) DO UPDATE
                    SET locale = EXCLUDED.locale, updated_at = NOW()
                    """,
                    (account_owner_key, locale),
                )

    async def purge_inactive_saved(self, before: datetime) -> list[str]:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    DELETE FROM wanderlisted_sessions
                    WHERE account_owner_key IS NOT NULL AND updated_at < %s
                    RETURNING checkpoint_thread_id
                    """,
                    (before,),
                )
                return [row["checkpoint_thread_id"] for row in await cursor.fetchall()]

    async def delete_account(self, account_owner_key: str) -> list[str]:
        async with self._pool.connection() as connection:
            async with connection.transaction():
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        DELETE FROM wanderlisted_sessions
                        WHERE account_owner_key = %s
                        RETURNING checkpoint_thread_id
                        """,
                        (account_owner_key,),
                    )
                    thread_ids = [
                        row["checkpoint_thread_id"] for row in await cursor.fetchall()
                    ]
                    await cursor.execute(
                        "DELETE FROM wanderlisted_account_preferences WHERE account_owner_key = %s",
                        (account_owner_key,),
                    )
                    return thread_ids

    async def account_thread_ids(self, account_owner_key: str) -> list[str]:
        async with self._pool.connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT checkpoint_thread_id FROM wanderlisted_sessions
                    WHERE account_owner_key = %s
                    """,
                    (account_owner_key,),
                )
                return [row["checkpoint_thread_id"] for row in await cursor.fetchall()]


@asynccontextmanager
async def open_session_registry(
    settings: SessionRegistrySettings,
) -> AsyncIterator[SessionRegistry]:
    if settings.backend == "memory":
        yield MemorySessionRegistry()
        return

    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    assert settings.database_url is not None
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        kwargs={"autocommit": True, "row_factory": dict_row},
        min_size=1,
        max_size=5,
        open=False,
    )
    await pool.open(wait=True)
    registry = PostgresSessionRegistry(pool)
    try:
        if settings.auto_setup:
            await registry.setup()
        yield registry
    finally:
        await pool.close()
