"""Guest/account session index, pagination, deletion, and retention contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from src.api import main as api
from src.api.session_registry import (
    MemorySessionRegistry,
    decode_cursor,
    deterministic_conversation_title,
)


async def _record(
    registry,
    *,
    session_id="trip-1",
    thread_id="session:thread-1",
    browser="browser-a",
    account=None,
    message="Plan a quiet week in Gdańsk near the sea",
    locale="pl",
    count=2,
):
    return await registry.register_turn(
        session_id=session_id,
        checkpoint_thread_id=thread_id,
        browser_owner_key=browser,
        account_owner_key=account,
        first_message=message,
        locale=locale,
        message_count=count,
    )


def test_title_is_deterministic_bounded_and_requires_no_model():
    message = "  Plan   a long food-focused journey through northern Poland with trains please  "
    first = deterministic_conversation_title(message)
    assert first == deterministic_conversation_title(message)
    assert len(first) <= 64
    assert first.endswith("…")


async def test_guest_isolation_and_explicit_claim_enable_cross_device_access():
    registry = MemorySessionRegistry()
    await _record(registry)

    assert (
        await registry.find_accessible(
            session_id="trip-1",
            browser_owner_key="browser-b",
            account_owner_key=None,
        )
        is None
    )
    assert (
        await registry.claim_sessions(
            browser_owner_key="browser-b",
            account_owner_key="acct:owner",
            session_ids=["trip-1"],
        )
        == 0
    )
    assert (
        await registry.claim_sessions(
            browser_owner_key="browser-a",
            account_owner_key="acct:owner",
            session_ids=["trip-1"],
        )
        == 1
    )
    cross_device = await registry.find_accessible(
        session_id="trip-1",
        browser_owner_key="browser-b",
        account_owner_key="acct:owner",
    )
    assert cross_device is not None
    assert cross_device.checkpoint_thread_id == "session:thread-1"


async def test_account_history_paginates_without_duplicates():
    registry = MemorySessionRegistry()
    for index in range(5):
        await _record(
            registry,
            session_id=f"trip-{index}",
            thread_id=f"session:thread-{index}",
            account="acct:owner",
        )

    first, cursor = await registry.list_account_sessions(
        "acct:owner", cursor=None, limit=2
    )
    second, next_cursor = await registry.list_account_sessions(
        "acct:owner", cursor=cursor, limit=2
    )

    assert len(first) == len(second) == 2
    assert {item.session_id for item in first}.isdisjoint(
        item.session_id for item in second
    )
    assert cursor is not None and next_cursor is not None
    assert decode_cursor(cursor)[1].startswith("session:")


async def test_delete_and_account_cleanup_remove_only_owned_data():
    registry = MemorySessionRegistry()
    await _record(registry, account="acct:one")
    await _record(
        registry,
        session_id="trip-2",
        thread_id="session:thread-2",
        browser="browser-b",
        account="acct:two",
    )
    await registry.put_preference("acct:one", "pl")

    assert (
        await registry.delete_accessible(
            session_id="trip-1",
            browser_owner_key="intruder",
            account_owner_key="acct:two",
        )
        is None
    )
    deleted = await registry.delete_account("acct:one")
    assert deleted == ["session:thread-1"]
    assert await registry.get_preference("acct:one") is None
    assert await registry.account_thread_ids("acct:two") == ["session:thread-2"]


async def test_retention_removes_only_inactive_saved_sessions():
    registry = MemorySessionRegistry()
    saved = await _record(registry, account="acct:owner")
    guest = await _record(
        registry,
        session_id="guest",
        thread_id="session:guest",
        browser="browser-b",
    )
    old = datetime.now(UTC) - timedelta(days=366)
    registry._records[saved.checkpoint_thread_id] = replace(saved, updated_at=old)
    registry._records[guest.checkpoint_thread_id] = replace(guest, updated_at=old)

    purged = await registry.purge_inactive_saved(
        datetime.now(UTC) - timedelta(days=365)
    )
    assert purged == ["session:thread-1"]
    assert await registry.find_accessible(
        session_id="guest", browser_owner_key="browser-b", account_owner_key=None
    )


class _SnapshotGraph:
    async def aget_state(self, config):
        assert config["configurable"]["thread_id"] == "session:thread-1"
        interrupt = SimpleNamespace(
            value={"gate": "human_review", "summary": "Sprawdź plan podróży."}
        )
        return SimpleNamespace(
            values={
                "messages": [
                    HumanMessage(content="Zaplanuj Gdańsk"),
                    AIMessage(content="Przygotowałem plan."),
                ],
                "response_locale": "pl",
                "itinerary_components": {},
                "component_results": {},
            },
            next=("human_review",),
            tasks=(SimpleNamespace(interrupts=(interrupt,)),),
        )


async def test_snapshot_restores_polish_locale_and_pending_hitl(monkeypatch):
    registry = MemorySessionRegistry()
    await _record(registry)
    monkeypatch.setattr(api._session_registry_dep, "_registry", registry)

    snapshot = await api.get_session_snapshot(
        "trip-1", owner_id="browser-a", graph=_SnapshotGraph()
    )

    assert snapshot["locale"] == "pl"
    assert snapshot["interrupted"] is True
    assert snapshot["interrupt_data"]["summary"] == "Sprawdź plan podróży."
    assert snapshot["messages"][0]["role"] == "user"
