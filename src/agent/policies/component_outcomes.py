"""Classify specialist execution independently from its prose response."""

from __future__ import annotations

from collections.abc import Iterable

from langchain_core.messages import AIMessage, ToolMessage

from src.models import ComponentResult, ComponentStatus, ErrorCategory

_NO_INVENTORY_MARKERS = (
    "no flights found",
    "no hotel offers found",
    "no places found",
    "no relevant destination guide content found",
)
_EXTERNAL_MARKERS = (
    "could not reach",
    "connection error",
    "rate limit",
    "resourceexhausted",
    "temporarily unavailable",
    "api error",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
)
_CLARIFICATION_MARKERS = (
    "i need",
    "please provide",
    "please tell me",
    "which city",
    "how many",
    "potrzebuję",
    "napisz mi",
    "z jakiego miasta",
    "ile osób",
)


def _text_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text")
        )
    return str(content or "")


def _error_category(text: str) -> ErrorCategory:
    lowered = text.lower()
    if any(
        marker in lowered for marker in ("401", "403", "authentication", "unauthorized")
    ):
        return ErrorCategory.AUTHENTICATION
    if any(marker in lowered for marker in ("429", "rate limit", "resourceexhausted")):
        return ErrorCategory.RATE_LIMIT
    if any(marker in lowered for marker in ("timeout", "timed out")):
        return ErrorCategory.TIMEOUT
    if any(
        marker in lowered for marker in ("http", "provider", "connection", "retryerror")
    ):
        return ErrorCategory.PROVIDER
    return ErrorCategory.INTERNAL


def classify_component_result(
    component: str,
    messages: Iterable,
    *,
    error: Exception | None = None,
) -> ComponentResult:
    """Classify task outcome from trajectory evidence, never prose presence alone."""
    if error is not None:
        detail = f"{type(error).__name__}: {error}"
        category = _error_category(detail)
        external = category in {
            ErrorCategory.AUTHENTICATION,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.TIMEOUT,
            ErrorCategory.PROVIDER,
        }
        return ComponentResult(
            component=component,
            status=(
                ComponentStatus.BLOCKED_EXTERNAL if external else ComponentStatus.FAILED
            ),
            error_category=category,
            error_detail=detail[:500],
        )

    tool_names: list[str] = []
    tool_outputs: list[str] = []
    final_texts: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            tool_names.extend(
                call.get("name", "") for call in message.tool_calls if call.get("name")
            )
            text = _text_content(message.content)
            if text:
                final_texts.append(text)
        elif isinstance(message, ToolMessage):
            tool_outputs.append(_text_content(message.content))

    evidence = "\n".join(tool_outputs).lower()
    final_text = final_texts[-1] if final_texts else ""
    combined = f"{evidence}\n{final_text.lower()}"

    if any(marker in combined for marker in _NO_INVENTORY_MARKERS):
        status = ComponentStatus.NO_INVENTORY
    elif any(marker in combined for marker in _EXTERNAL_MARKERS):
        status = ComponentStatus.BLOCKED_EXTERNAL
    elif tool_names and tool_outputs and final_text.strip():
        status = ComponentStatus.COMPLETED
    elif not tool_names and (
        "?" in final_text
        or any(marker in final_text.lower() for marker in _CLARIFICATION_MARKERS)
    ):
        status = ComponentStatus.NEEDS_USER_INPUT
    else:
        status = ComponentStatus.FAILED

    category = (
        _error_category(combined)
        if status == ComponentStatus.BLOCKED_EXTERNAL
        else ErrorCategory.NONE
    )
    return ComponentResult(
        component=component,
        status=status,
        message=final_text,
        error_category=category,
        tools_called=tool_names,
        evidence_count=len(tool_outputs),
    )
