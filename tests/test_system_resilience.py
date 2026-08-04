"""Hermetic restart, multi-instance, SSE failure, and load regressions."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TypedDict

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt

from src.agent.nodes.component_gate import component_gate_node
from src.agent.state import TravelAgentState
from src.api.main import ChatRequest, chat_stream
from src.api.rate_limit import RateLimitSettings, RedisRateLimiter
from src.models import ComponentStatus, ErrorCategory


class _RestartState(TypedDict):
    provider_evidence: str
    decision: str


def _restartable_graph(checkpointer, provider_calls: list[str]):
    def provider_node(_state: _RestartState):
        provider_calls.append("provider-called")
        return {"provider_evidence": "pinned evidence"}

    def approval_node(_state: _RestartState):
        decision = interrupt({"gate": "test_review"})
        return {"decision": decision}

    return (
        StateGraph(_RestartState)
        .add_node("provider", provider_node)
        .add_node("approval", approval_node)
        .add_edge(START, "provider")
        .add_edge("provider", "approval")
        .add_edge("approval", END)
        .compile(checkpointer=checkpointer)
    )


def test_new_graph_instance_resumes_checkpoint_without_repeating_provider_work():
    shared_backend = InMemorySaver()
    provider_calls: list[str] = []
    first_worker = _restartable_graph(shared_backend, provider_calls)
    config = {"configurable": {"thread_id": "durable-owner-thread"}}

    interrupted = first_worker.invoke({"provider_evidence": "", "decision": ""}, config)
    del first_worker  # simulate worker/process replacement
    replacement_worker = _restartable_graph(shared_backend, provider_calls)
    resumed = replacement_worker.invoke(Command(resume="approved"), config)

    assert interrupted["__interrupt__"][0].value == {"gate": "test_review"}
    assert resumed == {
        "provider_evidence": "pinned evidence",
        "decision": "approved",
    }
    assert provider_calls == ["provider-called"]


def test_two_workers_keep_independent_checkpoint_threads_isolated():
    shared_backend = InMemorySaver()
    provider_calls: list[str] = []
    first_worker = _restartable_graph(shared_backend, provider_calls)
    second_worker = _restartable_graph(shared_backend, provider_calls)
    first_config = {"configurable": {"thread_id": "owner-a"}}
    second_config = {"configurable": {"thread_id": "owner-b"}}

    first_worker.invoke({"provider_evidence": "", "decision": ""}, first_config)
    second_worker.invoke({"provider_evidence": "", "decision": ""}, second_config)
    first = second_worker.invoke(Command(resume="first-approved"), first_config)
    second = first_worker.invoke(Command(resume="second-rejected"), second_config)

    assert first["decision"] == "first-approved"
    assert second["decision"] == "second-rejected"
    assert provider_calls == ["provider-called", "provider-called"]


def _outcome(component: str, status: ComponentStatus, message: str = "") -> dict:
    return {
        "component": component,
        "status": status,
        "message": message,
        "missing_fields": [],
        "error_category": (
            ErrorCategory.PROVIDER
            if status == ComponentStatus.BLOCKED_EXTERNAL
            else ErrorCategory.NONE
        ),
        "error_detail": message,
        "tools_called": [],
        "evidence_count": 0,
        "request_fingerprint": "test-fingerprint",
        "data": None,
    }


def _partial_failure_graph(problem_status: ComponentStatus):
    def bootstrap(_state: TravelAgentState):
        return {
            "trip_request": {"locale": "en"},
            "itinerary_components": {"routing": ["FlightsAgent", "ActivitiesAgent"]},
        }

    def fan_out(state: TravelAgentState):
        return [Send("flights", state), Send("activities", state)]

    def flights(_state: TravelAgentState):
        return {
            "itinerary_components": {
                "flights": {"offers": [{"id": "safe-partial-offer"}]}
            },
            "component_results": {
                "flights": _outcome("flights", ComponentStatus.COMPLETED)
            },
        }

    def activities(_state: TravelAgentState):
        return {
            "itinerary_components": {
                "activities": {
                    "data": [{"id": "available-evidence"}],
                    "limitations": ["provider did not complete all requested data"],
                }
            },
            "component_results": {
                "activities": _outcome(
                    "activities",
                    problem_status,
                    "upstream provider unavailable"
                    if problem_status == ComponentStatus.BLOCKED_EXTERNAL
                    else "only bounded partial evidence is available",
                )
            },
        }

    async def gate(state: TravelAgentState):
        return await component_gate_node(
            state, eligible_components={"flights", "activities"}
        )

    builder = StateGraph(TravelAgentState)
    builder.add_node("bootstrap", bootstrap)
    builder.add_node("flights", flights)
    builder.add_node("activities", activities)
    builder.add_node("component_gate", gate)
    builder.add_edge(START, "bootstrap")
    builder.add_conditional_edges("bootstrap", fan_out, ["flights", "activities"])
    builder.add_edge("flights", "component_gate")
    builder.add_edge("activities", "component_gate")
    builder.add_edge("component_gate", END)
    return builder.compile(checkpointer=InMemorySaver())


class _AllowLimiter:
    async def check(self, _principal_id: str) -> bool:
        return True


async def _stream_payloads(status: ComponentStatus) -> list[dict]:
    response = await chat_stream(
        ChatRequest(message="run failure path", session_id="resilience-session"),
        owner_id=uuid.uuid4().hex,
        rate_limiter=_AllowLimiter(),
        graph=_partial_failure_graph(status),
    )
    body = ""
    async for chunk in response.body_iterator:
        body += chunk.decode() if isinstance(chunk, bytes) else chunk
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.parametrize(
    "status", [ComponentStatus.BLOCKED_EXTERNAL, ComponentStatus.PARTIAL]
)
async def test_sse_preserves_completed_evidence_and_structured_failure(status):
    payloads = await _stream_payloads(status)
    done = payloads[-1]

    assert payloads[0] == {
        "type": "session",
        "session_id": "resilience-session",
    }
    assert done["type"] == "done"
    assert done["interrupted"] is False
    assert done["components"]["flights"]["offers"][0]["id"] == ("safe-partial-offer")
    assert done["components"]["component_results"]["flights"]["status"] == ("completed")
    assert done["components"]["component_results"]["activities"]["status"] == (status)
    assert done["components"]["activities"]["limitations"]


class _SharedCounter:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.lock = asyncio.Lock()


class _AtomicRedisClient:
    def __init__(self, counter: _SharedCounter) -> None:
        self.counter = counter

    async def eval(self, _script, _key_count, key, _window_seconds):
        async with self.counter.lock:
            value = self.counter.values.get(key, 0) + 1
            self.counter.values[key] = value
            return value


async def test_concurrent_load_obeys_one_atomic_limit_across_four_replicas():
    maximum = 25
    settings = RateLimitSettings(
        environment="test",
        backend="redis",
        redis_url="redis://internal:6379",
        max_requests=maximum,
        window_seconds=60,
    )
    counter = _SharedCounter()
    replicas = [
        RedisRateLimiter(_AtomicRedisClient(counter), settings) for _ in range(4)
    ]

    results = await asyncio.gather(
        *(replicas[index % len(replicas)].check("same-owner") for index in range(200))
    )

    assert sum(results) == maximum
    assert len(counter.values) == 1
    assert next(iter(counter.values.values())) == 200
