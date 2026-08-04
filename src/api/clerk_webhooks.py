"""Svix-compatible verification for Clerk lifecycle webhooks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class ClerkWebhookError(ValueError):
    """Webhook payload or signature is not authentic and current."""


@dataclass(frozen=True, slots=True)
class ClerkWebhookSettings:
    signing_secret: str = field(repr=False)
    tolerance_seconds: int = 300

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str]
    ) -> "ClerkWebhookSettings | None":
        enabled = environment.get("CLERK_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        secret = environment.get("CLERK_WEBHOOK_SIGNING_SECRET", "").strip()
        if not enabled and not secret:
            return None
        if not secret.startswith("whsec_"):
            raise RuntimeError(
                "CLERK_WEBHOOK_SIGNING_SECRET must use Clerk's whsec_ format"
            )
        tolerance = int(environment.get("CLERK_WEBHOOK_TOLERANCE_SECONDS", "300"))
        if not 30 <= tolerance <= 900:
            raise RuntimeError("Webhook signature tolerance must be 30-900 seconds")
        return cls(signing_secret=secret, tolerance_seconds=tolerance)

    @property
    def key(self) -> bytes:
        encoded = self.signing_secret.removeprefix("whsec_")
        try:
            return base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise RuntimeError("Clerk webhook signing secret is invalid") from exc


def verify_clerk_webhook(
    body: bytes,
    headers: Mapping[str, str],
    *,
    settings: ClerkWebhookSettings,
    now: int | None = None,
) -> Mapping[str, Any]:
    """Verify Svix ID, timestamp, and at least one v1 HMAC signature."""

    message_id = headers.get("svix-id", "")
    raw_timestamp = headers.get("svix-timestamp", "")
    signatures = headers.get("svix-signature", "")
    if not message_id or not raw_timestamp or not signatures:
        raise ClerkWebhookError("Missing Clerk webhook signature headers")
    try:
        timestamp = int(raw_timestamp)
    except ValueError as exc:
        raise ClerkWebhookError("Invalid Clerk webhook timestamp") from exc
    current = int(time.time()) if now is None else now
    if abs(current - timestamp) > settings.tolerance_seconds:
        raise ClerkWebhookError("Expired Clerk webhook timestamp")

    signed = f"{message_id}.{timestamp}.".encode("utf-8") + body
    expected = base64.b64encode(
        hmac.new(settings.key, signed, hashlib.sha256).digest()
    ).decode("ascii")
    supplied = [
        value
        for item in signatures.split()
        for version, separator, value in [item.partition(",")]
        if separator and version == "v1"
    ]
    if not supplied or not any(
        hmac.compare_digest(expected, candidate) for candidate in supplied
    ):
        raise ClerkWebhookError("Invalid Clerk webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ClerkWebhookError("Invalid Clerk webhook JSON") from exc
    if not isinstance(payload, dict):
        raise ClerkWebhookError("Invalid Clerk webhook payload")
    return payload
