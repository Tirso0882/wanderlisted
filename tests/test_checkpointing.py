"""Hermetic contracts for durable checkpoint configuration and resume behavior."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from src.api.checkpointing import CheckpointSettings, open_checkpointer
from src.api.main import _GraphDependency


def test_development_defaults_to_memory_checkpoints():
    settings = CheckpointSettings.from_environment({})

    assert settings.environment == "development"
    assert settings.backend == "memory"
    assert settings.database_url is None


def test_production_defaults_to_postgres_and_requires_url():
    with pytest.raises(RuntimeError, match="CHECKPOINT_DATABASE_URL"):
        CheckpointSettings.from_environment({"ENVIRONMENT": "prod"})


def test_production_rejects_explicit_memory_backend():
    with pytest.raises(RuntimeError, match="Deployed environments require"):
        CheckpointSettings.from_environment(
            {"ENVIRONMENT": "production", "CHECKPOINT_BACKEND": "memory"}
        )


def test_postgres_settings_keep_connection_string_out_of_repr_assertions():
    settings = CheckpointSettings.from_environment(
        {
            "ENVIRONMENT": "test",
            "CHECKPOINT_BACKEND": "postgres",
            "CHECKPOINT_DATABASE_URL": "postgresql://user:secret@db/wanderlisted",
            "CHECKPOINT_AUTO_SETUP": "false",
        }
    )

    assert settings.backend == "postgres"
    assert settings.auto_setup is False
    assert "secret" not in repr(settings)


@pytest.mark.asyncio
async def test_postgres_checkpointer_is_initialized_and_closed(monkeypatch):
    from langgraph.checkpoint.postgres import aio as postgres_aio

    events: list[str] = []
    expected_url = "postgresql://user:secret@db/wanderlisted"

    class FakeSaver:
        async def setup(self):
            events.append("setup")

        @classmethod
        @asynccontextmanager
        async def from_conn_string(cls, connection_string):
            assert connection_string == expected_url
            events.append("open")
            yield cls()
            events.append("close")

    monkeypatch.setattr(postgres_aio, "AsyncPostgresSaver", FakeSaver)
    settings = CheckpointSettings(
        environment="test",
        backend="postgres",
        database_url=expected_url,
        auto_setup=True,
    )

    async with open_checkpointer(settings) as saver:
        assert isinstance(saver, FakeSaver)
        assert events == ["open", "setup"]

    assert events == ["open", "setup", "close"]


@pytest.mark.asyncio
async def test_graph_dependency_owns_checkpointer_for_full_lifespan():
    events: list[str] = []
    saver = object()
    compiled_graph = object()

    @asynccontextmanager
    async def checkpoint_context(_settings):
        events.append("open")
        yield saver
        events.append("close")

    def graph_factory(*, checkpointer):
        events.append("compile")
        assert checkpointer is saver
        return compiled_graph

    dependency = _GraphDependency(
        graph_factory=graph_factory,
        settings_factory=lambda: CheckpointSettings(
            environment="test", backend="memory", database_url=None
        ),
        checkpointer_context_factory=checkpoint_context,
    )

    await dependency.initialize()

    assert dependency() is compiled_graph
    assert dependency.backend == "memory"
    assert events == ["open", "compile"]

    await dependency.shutdown()

    assert events == ["open", "compile", "close"]
    with pytest.raises(RuntimeError, match="Graph not initialized"):
        dependency()


class _InterruptState(TypedDict):
    answer: str


def _shared_checkpoint_graph(checkpointer):
    def approval_node(_state: _InterruptState):
        answer = interrupt({"gate": "test_review"})
        return {"answer": answer}

    return (
        StateGraph(_InterruptState)
        .add_node("approval", approval_node)
        .add_edge(START, "approval")
        .add_edge("approval", END)
        .compile(checkpointer=checkpointer)
    )


def test_second_graph_instance_can_resume_from_shared_checkpoint_backend():
    shared_saver = InMemorySaver()
    first_instance = _shared_checkpoint_graph(shared_saver)
    second_instance = _shared_checkpoint_graph(shared_saver)
    config = {"configurable": {"thread_id": "shared-session"}}

    interrupted = first_instance.invoke({"answer": ""}, config)
    resumed = second_instance.invoke(Command(resume="approved"), config)

    assert interrupted["__interrupt__"][0].value == {"gate": "test_review"}
    assert resumed["answer"] == "approved"
