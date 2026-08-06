"""LangSmith run identity and feedback-linkage contracts."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage
from langsmith.run_helpers import tracing_context
from pydantic import ValidationError

import src.api.main as api


class _AllowLimiter:
    async def check(self, _principal_id: str) -> bool:
        return True


class _InvokeGraph:
    async def ainvoke(self, _value, config=None):
        assert config["configurable"]["thread_id"]
        return {
            "messages": [AIMessage(content="Finished")],
            "itinerary_components": {},
            "component_results": {},
        }


def test_current_run_id_reads_langsmith_context_and_has_no_fallback(monkeypatch):
    expected = uuid.uuid4()
    monkeypatch.setattr(
        api, "get_current_run_tree", lambda: SimpleNamespace(id=expected)
    )
    assert api._current_langsmith_run_id() == str(expected)

    monkeypatch.setattr(api, "get_current_run_tree", lambda: None)
    assert api._current_langsmith_run_id() is None


async def test_chat_returns_the_actual_current_langsmith_run_id(monkeypatch):
    expected = str(uuid.uuid4())
    monkeypatch.setattr(api, "_current_langsmith_run_id", lambda: expected)

    result = await api._run_agent("plan", "private-thread", _InvokeGraph())

    assert result["run_id"] == expected


async def test_traceable_chat_captures_its_real_local_run_context(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    with tracing_context(enabled="local", client=MagicMock()):
        result = await api._run_agent("plan", "private-thread", _InvokeGraph())

    assert uuid.UUID(result["run_id"])


async def test_chat_returns_no_run_id_when_tracing_is_disabled(monkeypatch):
    monkeypatch.setattr(api, "_current_langsmith_run_id", lambda: None)

    first = await api._run_agent("plan", "private-thread", _InvokeGraph())
    second = await api._run_agent("plan", "private-thread", _InvokeGraph())

    assert first["run_id"] is None
    assert second["run_id"] is None


class _StreamGraph:
    async def astream(self, _value, config=None, stream_mode=None):
        assert config["configurable"]["thread_id"].startswith("session:")
        assert stream_mode == "updates"
        yield {"supervisor": {"messages": [AIMessage(content="Routing internally")]}}
        yield {
            "activities": {
                "messages": [AIMessage(content='PLACE_RESULTS_JSON:\n{"places": []}')]
            }
        }
        yield {"budget": {"messages": [AIMessage(content="Final public result")]}}

    async def aget_state(self, _config):
        return SimpleNamespace(
            next=(),
            values={
                "messages": [
                    AIMessage(content="Routing to BudgetAgent"),
                    AIMessage(content='PLACE_RESULTS_JSON:\n{"places": []}'),
                    AIMessage(content="Final public result"),
                ],
                "itinerary_components": {},
                "component_results": {},
            },
        )


async def test_stream_done_event_returns_its_actual_trace_run_id(monkeypatch):
    expected = str(uuid.uuid4())
    monkeypatch.setattr(api, "_current_langsmith_run_id", lambda: expected)
    response = await api.chat_stream(
        api.ChatRequest(message="stream", session_id="public-session"),
        owner_id=uuid.uuid4().hex,
        rate_limiter=_AllowLimiter(),
        graph=_StreamGraph(),
    )

    body = ""
    async for chunk in response.body_iterator:
        body += chunk.decode() if isinstance(chunk, bytes) else chunk
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]

    assert payloads[-1]["type"] == "done"
    assert payloads[-1]["run_id"] == expected
    tokens = [payload["token"] for payload in payloads if payload["type"] == "token"]
    assert tokens == ["Final public result"]


def test_public_response_message_drops_internal_artifacts_and_routing():
    values = {
        "messages": [
            AIMessage(content="Useful earlier response"),
            AIMessage(content="Routing to BudgetAgent"),
            AIMessage(content="TRIP_SKELETON_JSON:\n{}"),
        ]
    }

    assert api._public_response_message(values) == "Useful earlier response"


async def test_feedback_uses_the_validated_run_id_returned_by_chat(monkeypatch):
    expected = uuid.uuid4()
    calls: list[dict] = []

    class FakeClient:
        def create_feedback(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(api, "Client", FakeClient)
    response = await api.submit_feedback(
        api.FeedbackRequest(run_id=expected, score=1.0, comment="useful"),
        owner_id=uuid.uuid4().hex,
        rate_limiter=_AllowLimiter(),
    )

    assert calls == [
        {
            "run_id": expected,
            "key": "user_rating",
            "score": 1.0,
            "comment": "useful",
        }
    ]
    assert response["run_id"] == str(expected)


def test_feedback_rejects_non_langsmith_run_ids_and_invalid_keys():
    with pytest.raises(ValidationError):
        api.FeedbackRequest(run_id="not-a-uuid", score=1.0)
    with pytest.raises(ValidationError):
        api.FeedbackRequest(run_id=uuid.uuid4(), score=1.0, key="bad key")


async def test_feedback_is_rate_limited_before_langsmith_mutation(monkeypatch):
    class DenyLimiter:
        async def check(self, _principal_id: str) -> bool:
            return False

    class UnexpectedClient:
        def __init__(self):
            raise AssertionError("LangSmith client must not be constructed")

    monkeypatch.setattr(api, "Client", UnexpectedClient)
    with pytest.raises(HTTPException) as error:
        await api.submit_feedback(
            api.FeedbackRequest(run_id=uuid.uuid4(), score=0.0),
            owner_id=uuid.uuid4().hex,
            rate_limiter=DenyLimiter(),
        )

    assert error.value.status_code == 429
