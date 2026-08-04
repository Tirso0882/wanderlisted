"""Hermetic Clerk JWT and webhook trust-boundary tests."""

from __future__ import annotations

import base64
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from src.api import main as api
from src.api.clerk_auth import (
    ClerkAuthSettings,
    ClerkJWTError,
    ClerkJWTValidator,
    opaque_account_owner,
)
from src.api.clerk_webhooks import (
    ClerkWebhookError,
    ClerkWebhookSettings,
    verify_clerk_webhook,
)


def _key_material():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    public_jwk.update({"kid": "test-key", "alg": "RS256", "use": "sig"})
    return private_key, public_jwk


def _settings() -> ClerkAuthSettings:
    return ClerkAuthSettings(
        enabled=True,
        issuer="https://clerk.example.test",
        jwks_url="https://clerk.example.test/.well-known/jwks.json",
        authorized_parties=frozenset({"https://app.example.test"}),
        owner_hash_key="o" * 32,
        jwks_cache_seconds=300,
        clock_skew_seconds=0,
    )


def _token(private_key, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "https://clerk.example.test",
        "sub": "user_2abc",
        "azp": "https://app.example.test",
        "iat": now - 1,
        "exp": now + 120,
    }
    claims.update(overrides)
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"},
    )


async def test_valid_jwt_is_cached_and_reduced_to_opaque_owner():
    private_key, public_jwk = _key_material()
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json={"keys": [public_jwk]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        validator = ClerkJWTValidator(_settings(), http_client=client)
        authorization = f"Bearer {_token(private_key)}"
        first = await validator.account_owner_from_authorization(authorization)
        second = await validator.account_owner_from_authorization(authorization)

    assert first == second
    assert first is not None and first.startswith("acct:")
    assert "user_2abc" not in first
    assert requests == 1


@pytest.mark.parametrize(
    "claim_overrides,error",
    [
        ({"exp": int(time.time()) - 30}, "expired"),
        ({"iss": "https://attacker.example"}, "[Ii]nvalid"),
        ({"azp": "https://attacker.example"}, "unauthorized party"),
    ],
)
async def test_jwt_rejects_expiry_issuer_and_authorized_party(claim_overrides, error):
    private_key, public_jwk = _key_material()
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"keys": [public_jwk]})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        validator = ClerkJWTValidator(_settings(), http_client=client)
        with pytest.raises(ClerkJWTError, match=error):
            await validator.validate_token(_token(private_key, **claim_overrides))


async def test_jwt_rejects_wrong_signature_and_malformed_bearer():
    private_key, public_jwk = _key_material()
    attacker_key, _ = _key_material()
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"keys": [public_jwk]})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        validator = ClerkJWTValidator(_settings(), http_client=client)
        with pytest.raises(ClerkJWTError, match="Invalid or expired"):
            await validator.validate_token(_token(attacker_key))
        with pytest.raises(ClerkJWTError, match="Malformed"):
            await validator.account_owner_from_authorization("Basic credentials")


def test_clerk_settings_require_issuer_party_and_strong_opaque_owner_key():
    with pytest.raises(RuntimeError, match="CLERK_ISSUER"):
        ClerkAuthSettings.from_environment(
            {"CLERK_ENABLED": "true", "SESSION_SIGNING_KEY": "s" * 32}
        )
    with pytest.raises(RuntimeError, match="AUTHORIZED_PARTIES"):
        ClerkAuthSettings.from_environment(
            {
                "CLERK_ENABLED": "true",
                "CLERK_ISSUER": "https://clerk.example",
                "SESSION_SIGNING_KEY": "s" * 32,
            }
        )
    assert opaque_account_owner("user", hash_key="s" * 32).startswith("acct:")


def _signed_webhook(body: bytes, settings: ClerkWebhookSettings, timestamp: int):
    import hashlib
    import hmac

    message_id = "msg_test"
    signed = f"{message_id}.{timestamp}.".encode() + body
    signature = base64.b64encode(
        hmac.new(settings.key, signed, hashlib.sha256).digest()
    ).decode()
    return {
        "svix-id": message_id,
        "svix-timestamp": str(timestamp),
        "svix-signature": f"v1,{signature}",
    }


def test_webhook_verification_accepts_current_signature_and_rejects_tampering():
    settings = ClerkWebhookSettings(
        signing_secret="whsec_" + base64.b64encode(b"webhook-secret").decode(),
        tolerance_seconds=300,
    )
    body = b'{"type":"user.deleted","data":{"id":"user_2abc"}}'
    now = 1_000
    headers = _signed_webhook(body, settings, now)

    assert verify_clerk_webhook(body, headers, settings=settings, now=now)["type"] == (
        "user.deleted"
    )
    with pytest.raises(ClerkWebhookError, match="signature"):
        verify_clerk_webhook(body + b" ", headers, settings=settings, now=now)
    with pytest.raises(ClerkWebhookError, match="Expired"):
        verify_clerk_webhook(body, headers, settings=settings, now=now + 301)


async def test_verified_user_deleted_webhook_cleans_registry_and_checkpoints(
    monkeypatch,
):
    from src.api.session_registry import MemorySessionRegistry

    registry = MemorySessionRegistry()
    settings = _settings()
    account_owner = opaque_account_owner("user_2abc", hash_key=settings.owner_hash_key)
    await registry.register_turn(
        session_id="saved-trip",
        checkpoint_thread_id="session:owned-thread",
        browser_owner_key="browser-a",
        account_owner_key=account_owner,
        first_message="Plan Poland",
        locale="en",
        message_count=2,
    )
    await registry.put_preference(account_owner, "pl")

    class Checkpointer:
        def __init__(self):
            self.deleted = []

        async def adelete_thread(self, thread_id):
            self.deleted.append(thread_id)

    graph = type("Graph", (), {"checkpointer": Checkpointer()})()
    webhook_settings = ClerkWebhookSettings(
        signing_secret="whsec_" + base64.b64encode(b"webhook-secret").decode(),
        tolerance_seconds=300,
    )
    monkeypatch.setattr(api, "_clerk_settings", settings)
    monkeypatch.setattr(api, "_clerk_webhook_settings", webhook_settings)
    api.app.dependency_overrides[api._graph_dep] = lambda: graph
    api.app.dependency_overrides[api._session_registry_dep] = lambda: registry

    body = json.dumps(
        {"type": "user.deleted", "data": {"id": "user_2abc"}},
        separators=(",", ":"),
    ).encode()
    headers = _signed_webhook(body, webhook_settings, int(time.time()))
    headers["content-type"] = "application/json"
    try:
        response = TestClient(api.app).post(
            "/api/v1/webhooks/clerk", content=body, headers=headers
        )
    finally:
        api.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["deleted"] == 1
    assert graph.checkpointer.deleted == ["session:owned-thread"]
    assert await registry.account_thread_ids(account_owner) == []
    assert await registry.get_preference(account_owner) is None
