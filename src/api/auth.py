"""Signed browser principals and owner-scoped checkpoint thread identities."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


_DEPLOYED_ENVIRONMENTS = frozenset({"test", "prod", "production"})


def _urlsafe(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True)
class BrowserAuthSettings:
    environment: str
    signing_key: str = field(repr=False)
    cookie_name: str = "wanderlisted_principal"
    max_age_seconds: int = 60 * 60 * 24 * 30
    secure_cookie: bool = False
    ephemeral_key: bool = False

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "BrowserAuthSettings":
        deployment_environment = environment.get("ENVIRONMENT", "development").lower()
        signing_key = environment.get("SESSION_SIGNING_KEY", "")
        ephemeral_key = False
        if not signing_key:
            if deployment_environment in _DEPLOYED_ENVIRONMENTS:
                raise RuntimeError(
                    "SESSION_SIGNING_KEY is required in deployed environments"
                )
            signing_key = secrets.token_urlsafe(48)
            ephemeral_key = True
        if len(signing_key.encode("utf-8")) < 32:
            raise RuntimeError("SESSION_SIGNING_KEY must contain at least 32 bytes")

        max_age = int(environment.get("SESSION_COOKIE_MAX_AGE_SECONDS", "2592000"))
        if max_age <= 0:
            raise RuntimeError("SESSION_COOKIE_MAX_AGE_SECONDS must be positive")

        secure_default = deployment_environment in _DEPLOYED_ENVIRONMENTS
        secure_raw = environment.get("SESSION_COOKIE_SECURE")
        secure_cookie = (
            secure_default
            if secure_raw is None
            else secure_raw.strip().lower() in {"1", "true", "yes", "on"}
        )
        if deployment_environment in _DEPLOYED_ENVIRONMENTS and not secure_cookie:
            raise RuntimeError("SESSION_COOKIE_SECURE cannot be disabled when deployed")

        return cls(
            environment=deployment_environment,
            signing_key=signing_key,
            cookie_name=environment.get(
                "SESSION_COOKIE_NAME", "wanderlisted_principal"
            ),
            max_age_seconds=max_age,
            secure_cookie=secure_cookie,
            ephemeral_key=ephemeral_key,
        )


class BrowserPrincipalSigner:
    """Issue and verify tamper-evident anonymous browser identities."""

    def __init__(self, settings: BrowserAuthSettings) -> None:
        self.settings = settings
        self._key = settings.signing_key.encode("utf-8")

    def issue(self, owner_id: str, *, issued_at: int | None = None) -> str:
        canonical_owner = uuid.UUID(owner_id).hex
        timestamp = int(time.time()) if issued_at is None else issued_at
        payload = f"v1.{canonical_owner}.{timestamp}"
        signature = hmac.new(
            self._key, payload.encode("ascii"), hashlib.sha256
        ).digest()
        return f"{payload}.{_urlsafe(signature)}"

    def verify(self, token: str | None, *, now: int | None = None) -> str | None:
        if not token:
            return None
        try:
            version, raw_owner, raw_timestamp, supplied_signature = token.split(".")
            if version != "v1":
                return None
            owner_id = uuid.UUID(raw_owner).hex
            issued_at = int(raw_timestamp)
        except (TypeError, ValueError):
            return None

        current_time = int(time.time()) if now is None else now
        if issued_at > current_time + 60:
            return None
        if current_time - issued_at > self.settings.max_age_seconds:
            return None

        payload = f"v1.{owner_id}.{issued_at}"
        expected_signature = _urlsafe(
            hmac.new(self._key, payload.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_signature, supplied_signature):
            return None
        return owner_id


def private_thread_id(owner_id: str, public_session_id: str) -> str:
    """Namespace a public session under its authenticated browser owner."""

    digest = hashlib.sha256(
        f"{uuid.UUID(owner_id).hex}\0{public_session_id}".encode("utf-8")
    ).hexdigest()
    return f"session:{digest}"


class BrowserPrincipalMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, signer: BrowserPrincipalSigner) -> None:
        super().__init__(app)
        self.signer = signer

    async def dispatch(self, request: Request, call_next):
        token = request.cookies.get(self.signer.settings.cookie_name)
        owner_id = self.signer.verify(token)
        issue_cookie = owner_id is None
        if owner_id is None:
            owner_id = uuid.uuid4().hex
        request.state.owner_id = owner_id

        response = await call_next(request)
        if issue_cookie:
            response.set_cookie(
                key=self.signer.settings.cookie_name,
                value=self.signer.issue(owner_id),
                max_age=self.signer.settings.max_age_seconds,
                path="/",
                secure=self.signer.settings.secure_cookie,
                httponly=True,
                samesite="lax",
            )
        return response
