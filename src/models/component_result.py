"""Structured outcome contract for specialist and workflow components."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ComponentStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_USER_INPUT = "needs_user_input"
    NO_INVENTORY = "no_inventory"
    BLOCKED_EXTERNAL = "blocked_external"
    FAILED = "failed"
    STALE = "stale"


class ErrorCategory(StrEnum):
    NONE = "none"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    PROVIDER = "provider"
    VALIDATION = "validation"
    INTERNAL = "internal"


class ComponentResult(BaseModel):
    """Machine-readable outcome kept separately from conversational messages."""

    component: str
    status: ComponentStatus
    data: dict[str, Any] | None = None
    missing_fields: list[str] = Field(default_factory=list)
    message: str = ""
    error_category: ErrorCategory = ErrorCategory.NONE
    error_detail: str = ""
    tools_called: list[str] = Field(default_factory=list)
    evidence_count: int = Field(default=0, ge=0)
    request_fingerprint: str = ""
