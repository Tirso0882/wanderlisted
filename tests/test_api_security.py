"""Session-ownership and distributed rate-limit security regressions."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import httpx
import pytest
import respx
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from src.api.auth import (
    BrowserAuthSettings,
    BrowserPrincipalMiddleware,
    BrowserPrincipalSigner,
    private_thread_id,
)
from src.api.main import (
    _enforce_rate_limit,
    _graph_dep,
    _rate_limiter_dep,
    app,
)
from src.api.rate_limit import (
    RateLimiterUnavailable,
    RateLimitSettings,
    RedisRateLimiter,
)


class _AllowLimiter:
    async def check(self, _principal_id: str) -> bool:
        return True


class _SessionGraph:
    """Small checkpoint-shaped fake keyed only by the supplied thread ID."""

    def __init__(self) -> None:
        self.states: dict[str, dict] = {}

    async def ainvoke(self, value, config=None):
        thread_id = config["configurable"]["thread_id"]
        state = self.states.get(thread_id, {"messages": []})
        if isinstance(value, dict):
            state = {
                "messages": [
                    *state["messages"],
                    *value.get("messages", []),
                    AIMessage(content="Saved for this browser"),
                ],
                "itinerary_components": {},
                "component_results": {},
            }
            self.states[thread_id] = state
        else:
            state = {
                **state,
                "messages": [*state["messages"], AIMessage(content="Resumed")],
                "itinerary_components": {},
                "component_results": {},
            }
            self.states[thread_id] = state
        return state

    async def aget_state(self, config):
        state = self.states.get(config["configurable"]["thread_id"])
        return SimpleNamespace(values=state) if state is not None else None


@pytest.fixture
def isolated_api():
    graph = _SessionGraph()
    limiter = _AllowLimiter()
    app.dependency_overrides[_graph_dep] = lambda: graph
    app.dependency_overrides[_rate_limiter_dep] = lambda: limiter
    try:
        yield graph
    finally:
        app.dependency_overrides.clear()


def test_same_browser_can_read_and_resume_its_session(isolated_api):
    client = TestClient(app)

    created = client.post(
        "/api/v1/chat",
        json={"message": "Plan a trip", "session_id": "shared-public-id"},
    )
    history = client.get("/api/v1/sessions/shared-public-id/history")
    resumed = client.post(
        "/api/v1/chat/resume",
        json={
            "session_id": "shared-public-id",
            "decision": {"gate": "human_review", "action": "approved"},
        },
    )

    assert created.status_code == 200
    assert history.status_code == 200
    assert history.json()["messages"][0]["content"] == "Plan a trip"
    assert resumed.status_code == 200
    assert resumed.json()["message"] == "Resumed"


def test_other_browser_cannot_read_or_resume_known_public_session(isolated_api):
    owner_a = TestClient(app)
    owner_b = TestClient(app)
    created = owner_a.post(
        "/api/v1/chat",
        json={"message": "Private plan", "session_id": "guessable-session"},
    )

    read_attempt = owner_b.get("/api/v1/sessions/guessable-session/history")
    resume_attempt = owner_b.post(
        "/api/v1/chat/resume",
        json={
            "session_id": "guessable-session",
            "decision": {"gate": "human_review", "action": "approved"},
        },
    )

    assert created.status_code == 200
    assert read_attempt.status_code == 404
    assert resume_attempt.status_code == 404


@respx.mock
def test_google_photo_proxy_rejects_invalid_resource_name_without_request(isolated_api):
    response = TestClient(app).get(
        "/api/v1/media/google-place-photo",
        params={"name": "https://attacker.example/photo"},
    )

    assert response.status_code == 422
    assert len(respx.calls) == 0


def test_google_photo_proxy_fails_closed_without_key(isolated_api, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    response = TestClient(app).get(
        "/api/v1/media/google-place-photo",
        params={"name": "places/place123/photos/photo456"},
    )

    assert response.status_code == 503


@respx.mock
def test_google_photo_proxy_returns_image_without_exposing_key(
    isolated_api, monkeypatch
):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "private-google-key")
    route = respx.get(
        "https://places.googleapis.com/v1/places/place123/photos/photo456/media"
    ).mock(
        return_value=httpx.Response(
            200,
            content=b"image-bytes",
            headers={"content-type": "image/jpeg"},
        )
    )

    response = TestClient(app).get(
        "/api/v1/media/google-place-photo",
        params={
            "name": "places/place123/photos/photo456",
            "max_height": 600,
        },
    )

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["content-type"] == "image/jpeg"
    assert route.calls[0].request.url.params["maxHeightPx"] == "600"
    assert route.calls[0].request.url.params["key"] == "private-google-key"
    assert "private-google-key" not in response.text
    assert "private-google-key" not in str(response.headers)


def test_private_thread_id_is_owner_scoped_and_hides_public_identifiers():
    first_owner = uuid.uuid4().hex
    second_owner = uuid.uuid4().hex

    first = private_thread_id(first_owner, "known-session")
    repeated = private_thread_id(first_owner, "known-session")
    second = private_thread_id(second_owner, "known-session")

    assert first == repeated
    assert first != second
    assert first.startswith("session:")
    assert "known-session" not in first
    assert first_owner not in first


def test_browser_principal_rejects_tampering_expiry_and_future_tokens():
    settings = BrowserAuthSettings(
        environment="test",
        signing_key="a" * 32,
        max_age_seconds=60,
        secure_cookie=True,
    )
    signer = BrowserPrincipalSigner(settings)
    owner_id = uuid.uuid4().hex
    token = signer.issue(owner_id, issued_at=1_000)

    assert signer.verify(token, now=1_030) == owner_id
    assert signer.verify(f"{token[:-1]}x", now=1_030) is None
    assert signer.verify(token, now=1_061) is None
    assert signer.verify(signer.issue(owner_id, issued_at=1_100), now=1_000) is None


def test_deployed_cookie_has_secure_browser_attributes():
    settings = BrowserAuthSettings.from_environment(
        {"ENVIRONMENT": "prod", "SESSION_SIGNING_KEY": "s" * 32}
    )
    signer = BrowserPrincipalSigner(settings)
    cookie_app = FastAPI()
    cookie_app.add_middleware(BrowserPrincipalMiddleware, signer=signer)

    @cookie_app.get("/")
    async def read_owner(request: Request):
        return {"owner_id": request.state.owner_id}

    response = TestClient(cookie_app).get("/")
    cookie = response.headers["set-cookie"].lower()

    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "max-age=2592000" in cookie


class _SharedRedisState:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.lock = asyncio.Lock()


class _FakeRedisClient:
    def __init__(self, state: _SharedRedisState) -> None:
        self.state = state

    async def eval(self, _script, _key_count, key, _window_seconds):
        async with self.state.lock:
            current = self.state.counts.get(key, 0) + 1
            self.state.counts[key] = current
            return current


def _redis_settings(*, max_requests: int = 2) -> RateLimitSettings:
    return RateLimitSettings(
        environment="test",
        backend="redis",
        redis_url="redis://internal:6379",
        max_requests=max_requests,
        window_seconds=60,
    )


async def test_redis_limit_is_shared_across_limiter_instances():
    state = _SharedRedisState()
    first = RedisRateLimiter(_FakeRedisClient(state), _redis_settings())
    second = RedisRateLimiter(_FakeRedisClient(state), _redis_settings())

    assert await first.check("same-browser") is True
    assert await second.check("same-browser") is True
    assert await first.check("same-browser") is False


async def test_redis_outage_fails_closed_with_service_unavailable():
    class BrokenLimiter:
        async def check(self, _principal_id: str) -> bool:
            raise RateLimiterUnavailable("redis unavailable")

    with pytest.raises(HTTPException) as error:
        await _enforce_rate_limit(BrokenLimiter(), uuid.uuid4().hex)

    assert error.value.status_code == 503
    assert error.value.detail == "Request protection is temporarily unavailable."


@pytest.mark.parametrize("environment", ["test", "prod", "production"])
def test_deployed_configuration_requires_signing_key_and_redis(environment):
    with pytest.raises(RuntimeError, match="SESSION_SIGNING_KEY"):
        BrowserAuthSettings.from_environment({"ENVIRONMENT": environment})
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        RateLimitSettings.from_environment({"ENVIRONMENT": environment})
