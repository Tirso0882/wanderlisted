"""Optional Clerk JWT validation and request-scoped opaque account ownership."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from fastapi.responses import JSONResponse
from jwt import PyJWK
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


_DEPLOYED_ENVIRONMENTS = frozenset({"test", "prod", "production"})
_current_account_owner: ContextVar[str | None] = ContextVar(
    "wanderlisted_account_owner", default=None
)


class ClerkJWTError(ValueError):
    """A bearer token failed a Clerk trust-boundary check."""


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError("CLERK_ENABLED must be true or false")


def _validated_https_url(value: str, *, name: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username:
        raise RuntimeError(f"{name} must be an absolute HTTPS URL")
    return value.rstrip("/")


@dataclass(frozen=True, slots=True)
class ClerkAuthSettings:
    enabled: bool
    issuer: str = ""
    jwks_url: str = field(default="", repr=False)
    authorized_parties: frozenset[str] = field(default_factory=frozenset)
    owner_hash_key: str = field(default="", repr=False)
    jwks_cache_seconds: int = 300
    clock_skew_seconds: int = 5

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "ClerkAuthSettings":
        enabled = _parse_bool(environment.get("CLERK_ENABLED"))
        if not enabled:
            return cls(enabled=False)

        issuer = _validated_https_url(
            environment.get("CLERK_ISSUER", ""), name="CLERK_ISSUER"
        )
        jwks_url = _validated_https_url(
            environment.get("CLERK_JWKS_URL", f"{issuer}/.well-known/jwks.json"),
            name="CLERK_JWKS_URL",
        )
        parties = frozenset(
            party.strip().rstrip("/")
            for party in environment.get("CLERK_AUTHORIZED_PARTIES", "").split(",")
            if party.strip()
        )
        if not parties:
            raise RuntimeError(
                "CLERK_AUTHORIZED_PARTIES is required when Clerk is enabled"
            )

        owner_hash_key = environment.get("CLERK_OWNER_HASH_KEY") or environment.get(
            "SESSION_SIGNING_KEY", ""
        )
        if len(owner_hash_key.encode("utf-8")) < 32:
            raise RuntimeError(
                "CLERK_OWNER_HASH_KEY or SESSION_SIGNING_KEY must contain at least 32 bytes"
            )

        cache_seconds = int(environment.get("CLERK_JWKS_CACHE_SECONDS", "300"))
        clock_skew = int(environment.get("CLERK_CLOCK_SKEW_SECONDS", "5"))
        if cache_seconds <= 0 or not 0 <= clock_skew <= 60:
            raise RuntimeError("Clerk cache/skew settings are outside safe bounds")

        deployment_environment = environment.get("ENVIRONMENT", "development").lower()
        if deployment_environment in _DEPLOYED_ENVIRONMENTS:
            for party in parties:
                _validated_https_url(party, name="CLERK_AUTHORIZED_PARTIES")

        return cls(
            enabled=True,
            issuer=issuer,
            jwks_url=jwks_url,
            authorized_parties=parties,
            owner_hash_key=owner_hash_key,
            jwks_cache_seconds=cache_seconds,
            clock_skew_seconds=clock_skew,
        )


def opaque_account_owner(subject: str, *, hash_key: str) -> str:
    """Derive a stable opaque owner key without persisting a raw Clerk subject."""

    if not subject or len(hash_key.encode("utf-8")) < 32:
        raise ValueError("A subject and strong account-owner hash key are required")
    digest = hmac.new(
        hash_key.encode("utf-8"), subject.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"acct:{digest}"


class ClerkJWTValidator:
    """Validate Clerk session JWTs against a bounded, cached JWKS set."""

    def __init__(
        self,
        settings: ClerkAuthSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._http_client = http_client
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _refresh_keys(self) -> None:
        async with self._lock:
            if self._keys and time.monotonic() < self._expires_at:
                return
            owns_client = self._http_client is None
            client = self._http_client or httpx.AsyncClient(
                timeout=httpx.Timeout(5.0), follow_redirects=False
            )
            try:
                response = await client.get(
                    self.settings.jwks_url,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise ClerkJWTError("Identity verification is unavailable") from exc
            finally:
                if owns_client:
                    await client.aclose()

            keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(keys, list) or not keys:
                raise ClerkJWTError("Identity verification returned no signing keys")
            parsed: dict[str, Any] = {}
            for raw_key in keys:
                if not isinstance(raw_key, dict) or not raw_key.get("kid"):
                    continue
                try:
                    parsed[str(raw_key["kid"])] = PyJWK.from_dict(raw_key).key
                except (jwt.PyJWTError, ValueError, TypeError):
                    continue
            if not parsed:
                raise ClerkJWTError(
                    "Identity verification returned invalid signing keys"
                )
            self._keys = parsed
            self._expires_at = time.monotonic() + self.settings.jwks_cache_seconds

    async def validate_token(self, token: str) -> Mapping[str, Any]:
        if not self.settings.enabled:
            raise ClerkJWTError("Account authentication is disabled")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise ClerkJWTError("Invalid account token") from exc
        kid = header.get("kid")
        algorithm = header.get("alg")
        if not isinstance(kid, str) or algorithm != "RS256":
            raise ClerkJWTError("Invalid account token header")

        if kid not in self._keys or time.monotonic() >= self._expires_at:
            await self._refresh_keys()
        key = self._keys.get(kid)
        if key is None:
            # Rotation may occur before the cache expires. Force one bounded refresh.
            self._keys = {}
            self._expires_at = 0
            await self._refresh_keys()
            key = self._keys.get(kid)
        if key is None:
            raise ClerkJWTError("Unknown account signing key")

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                leeway=self.settings.clock_skew_seconds,
                options={
                    "verify_aud": False,
                    "require": ["exp", "iat", "iss", "sub", "azp"],
                },
            )
        except jwt.PyJWTError as exc:
            raise ClerkJWTError("Invalid or expired account token") from exc

        authorized_party = str(claims.get("azp", "")).rstrip("/")
        if authorized_party not in self.settings.authorized_parties:
            raise ClerkJWTError("Account token has an unauthorized party")
        return claims

    async def account_owner_from_authorization(
        self, authorization: str | None
    ) -> str | None:
        if not authorization:
            return None
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token.strip():
            raise ClerkJWTError("Malformed account authorization header")
        claims = await self.validate_token(token.strip())
        return opaque_account_owner(
            str(claims["sub"]), hash_key=self.settings.owner_hash_key
        )


def current_account_owner() -> str | None:
    """Read the account owner scoped to the current ASGI request."""

    return _current_account_owner.get()


class ClerkIdentityMiddleware(BaseHTTPMiddleware):
    """Verify optional bearer tokens and expose only an opaque owner key."""

    def __init__(self, app, *, validator: ClerkJWTValidator) -> None:
        super().__init__(app)
        self.validator = validator

    async def dispatch(self, request: Request, call_next):
        try:
            account_owner = await self.validator.account_owner_from_authorization(
                request.headers.get("authorization")
            )
        except ClerkJWTError as exc:
            return JSONResponse(status_code=401, content={"detail": str(exc)})

        context_token = _current_account_owner.set(account_owner)
        request.state.account_owner_id = account_owner
        try:
            return await call_next(request)
        finally:
            _current_account_owner.reset(context_token)
