import asyncio
import json
import os
import uuid
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Callable, Literal

from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, Depends, HTTPException, Path, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph
from langsmith import Client, traceable
from langsmith.run_helpers import get_current_run_tree
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

from custom_logging import AppLogger
from src.agent.stage4_graph import create_multiagent_travel_graph
from src.api.auth import (
    BrowserAuthSettings,
    BrowserPrincipalMiddleware,
    BrowserPrincipalSigner,
    private_thread_id,
)
from src.api.checkpointing import (
    CheckpointSettings,
    open_checkpointer,
)
from src.api.clerk_auth import (
    ClerkAuthSettings,
    ClerkIdentityMiddleware,
    ClerkJWTValidator,
    current_account_owner,
    opaque_account_owner,
)
from src.api.clerk_webhooks import (
    ClerkWebhookError,
    ClerkWebhookSettings,
    verify_clerk_webhook,
)
from src.api.rate_limit import (
    RateLimiter,
    RateLimiterUnavailable,
    RateLimitSettings,
    open_rate_limiter,
)
from src.api.session_registry import (
    SessionRecord,
    SessionRegistry,
    SessionRegistrySettings,
    open_session_registry,
)
from src.models import BudgetBreakdown, BudgetReviewDecision, ServiceScopeDecision
import config as app_config

# Explicit process/CI settings must win over developer-local .env values so
# hermetic tests can disable tracing and production injection remains authoritative.
load_dotenv()

_api_cfg = app_config.get("api") or {}
_API_VERSION = _api_cfg.get("version", "2.0.0")
_REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "120"))

# ── Logging ─────────────────────────────────────────────────────────────────
logger = AppLogger(
    logger_name="api",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)

_auth_settings = BrowserAuthSettings.from_environment(os.environ)
_principal_signer = BrowserPrincipalSigner(_auth_settings)
if _auth_settings.ephemeral_key:
    logger.warning(
        "Using an ephemeral browser-principal signing key; local sessions will "
        "not survive an API restart"
    )

_clerk_settings = ClerkAuthSettings.from_environment(os.environ)
_clerk_validator = ClerkJWTValidator(_clerk_settings)
_clerk_webhook_settings = ClerkWebhookSettings.from_environment(os.environ)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _extract_text_content(content) -> str:
    """Extract text from LangChain message.content.

    Handles both:
    - Chat Completions: content is str
    - Responses API: content is list of {"type": "text", "text": "..."} blocks
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and block.get("text")
        ]
        return " ".join(texts)
    return str(content or "")


_INTERNAL_MESSAGE_MARKERS = (
    "PLACE_RESULTS_JSON:",
    "HOTEL_RESULTS_JSON:",
    "HOTEL_PRICING_JSON:",
    "FLIGHT_WINDOW_RESULT_JSON:",
    "FLIGHT_PRICING_JSON:",
    "TRIP_SKELETON_JSON:",
    "DRAFT_ITINERARY_JSON:",
    "ROUTE_PLAN_JSON:",
)


def _public_response_message(values: dict) -> str:
    """Return the final traveler-facing message, excluding orchestration artifacts."""
    for message in reversed(values.get("messages", [])):
        if not isinstance(message, AIMessage):
            continue
        text = _extract_text_content(message.content).strip()
        if not text:
            continue
        if text.startswith("Routing to ") or text.startswith("Przekazuję do "):
            continue
        if any(marker in text for marker in _INTERNAL_MESSAGE_MARKERS):
            continue
        return text
    return ""


def _public_components(
    components: dict | None,
    component_results: dict | None = None,
    safety_warning: dict | None = None,
    service_scope_offer: dict | None = None,
) -> dict | None:
    """Expose structured component data without serializing chat transcripts."""
    public: dict = {}
    for key, value in (components or {}).items():
        if key in {"routing", "completed_agents"}:
            continue
        if isinstance(value, dict):
            value = {
                field: item for field, item in value.items() if field != "messages"
            }
            if key in {"readiness", "readiness_preflight"}:
                value = {"data": value.get("data")}
        public[key] = jsonable_encoder(value)
    if component_results:
        public["component_results"] = jsonable_encoder(component_results)
    if safety_warning:
        public["safety_warning"] = jsonable_encoder(safety_warning)
    if service_scope_offer:
        public["service_scope_offer"] = jsonable_encoder(service_scope_offer)
    return public or None


def _current_langsmith_run_id() -> str | None:
    """Return the active traced run ID, or None when tracing is disabled."""
    run_tree = get_current_run_tree()
    return str(run_tree.id) if run_tree is not None else None


# ── Graph dependency (replaces global mutable state) ────────────────────────
class _GraphDependency:
    """Lazy-initialized graph singleton, injectable via FastAPI Depends."""

    def __init__(
        self,
        *,
        graph_factory: Callable = create_multiagent_travel_graph,
        settings_factory: Callable[[], CheckpointSettings] | None = None,
        checkpointer_context_factory: Callable = open_checkpointer,
    ) -> None:
        self._graph: CompiledStateGraph | None = None
        self._graph_factory = graph_factory
        self._settings_factory = settings_factory or (
            lambda: CheckpointSettings.from_environment(os.environ)
        )
        self._checkpointer_context_factory = checkpointer_context_factory
        self._exit_stack: AsyncExitStack | None = None
        self.backend: str | None = None

    async def initialize(self) -> None:
        if self._graph is not None:
            return

        settings = self._settings_factory()
        exit_stack = AsyncExitStack()
        try:
            checkpointer = await exit_stack.enter_async_context(
                self._checkpointer_context_factory(settings)
            )
            graph = self._graph_factory(checkpointer=checkpointer)
        except BaseException:
            await exit_stack.aclose()
            raise

        self._exit_stack = exit_stack
        self._graph = graph
        self.backend = settings.backend
        logger.info(
            f"Multi-agent graph initialized with {settings.backend} checkpoints"
        )

    async def shutdown(self) -> None:
        self._graph = None
        self.backend = None
        if self._exit_stack is not None:
            exit_stack = self._exit_stack
            self._exit_stack = None
            await exit_stack.aclose()

    def __call__(self) -> CompiledStateGraph:
        if self._graph is None:
            raise RuntimeError("Graph not initialized — app did not start correctly")
        return self._graph


_graph_dep = _GraphDependency()


# ── Rate limiter ────────────────────────────────────────────────────────────
class _RateLimiterDependency:
    def __init__(
        self,
        *,
        settings_factory: Callable[[], RateLimitSettings] | None = None,
        limiter_context_factory: Callable = open_rate_limiter,
    ) -> None:
        self._settings_factory = settings_factory or (
            lambda: RateLimitSettings.from_environment(os.environ)
        )
        self._limiter_context_factory = limiter_context_factory
        self._limiter: RateLimiter | None = None
        self._exit_stack: AsyncExitStack | None = None
        self.backend: str | None = None

    async def initialize(self) -> None:
        if self._limiter is not None:
            return
        settings = self._settings_factory()
        exit_stack = AsyncExitStack()
        try:
            limiter = await exit_stack.enter_async_context(
                self._limiter_context_factory(settings)
            )
        except BaseException:
            await exit_stack.aclose()
            raise
        self._limiter = limiter
        self._exit_stack = exit_stack
        self.backend = settings.backend
        logger.info(f"Rate limiter initialized with {settings.backend} backend")

    async def shutdown(self) -> None:
        self._limiter = None
        self.backend = None
        if self._exit_stack is not None:
            exit_stack = self._exit_stack
            self._exit_stack = None
            await exit_stack.aclose()

    def __call__(self) -> RateLimiter:
        if self._limiter is None:
            raise RuntimeError("Rate limiter not initialized")
        return self._limiter


_rate_limiter_dep = _RateLimiterDependency()


class _SessionRegistryDependency:
    """Own the session-index pool for the FastAPI lifespan."""

    def __init__(
        self,
        *,
        settings_factory: Callable[[], SessionRegistrySettings] | None = None,
        registry_context_factory: Callable = open_session_registry,
    ) -> None:
        self._settings_factory = settings_factory or (
            lambda: SessionRegistrySettings.from_environment(os.environ)
        )
        self._registry_context_factory = registry_context_factory
        self._registry: SessionRegistry | None = None
        self._exit_stack: AsyncExitStack | None = None
        self.backend: str | None = None
        self.retention_days = 365

    async def initialize(self) -> None:
        if self._registry is not None:
            return
        settings = self._settings_factory()
        exit_stack = AsyncExitStack()
        try:
            registry = await exit_stack.enter_async_context(
                self._registry_context_factory(settings)
            )
        except BaseException:
            await exit_stack.aclose()
            raise
        self._registry = registry
        self._exit_stack = exit_stack
        self.backend = settings.backend
        self.retention_days = settings.retention_days
        logger.info(f"Session registry initialized with {settings.backend} backend")

    async def shutdown(self) -> None:
        self._registry = None
        self.backend = None
        if self._exit_stack is not None:
            exit_stack = self._exit_stack
            self._exit_stack = None
            await exit_stack.aclose()

    def __call__(self) -> SessionRegistry:
        if self._registry is None:
            raise RuntimeError("Session registry not initialized")
        return self._registry


_session_registry_dep = _SessionRegistryDependency()


def _optional_session_registry() -> SessionRegistry | None:
    """Allow direct unit calls and disabled-lifespan tests to remain hermetic."""

    try:
        return _session_registry_dep()
    except RuntimeError:
        return None


def _required_account_owner() -> str:
    account_owner = current_account_owner()
    if not account_owner:
        raise HTTPException(status_code=401, detail="Sign in to use saved trips.")
    return account_owner


async def _resolve_session_record(
    *,
    owner_id: str,
    session_id: str,
    account_owner_id: str | None,
    registry: SessionRegistry | None,
) -> tuple[str, SessionRecord | None]:
    if registry is not None:
        record = await registry.find_accessible(
            session_id=session_id,
            browser_owner_key=owner_id,
            account_owner_key=account_owner_id,
        )
        if record is not None:
            return record.checkpoint_thread_id, record
    return private_thread_id(owner_id, session_id), None


async def _record_session_turn(
    registry: SessionRegistry | None,
    *,
    session_id: str,
    thread_id: str,
    owner_id: str,
    account_owner_id: str | None,
    existing: SessionRecord | None,
    first_message: str,
    locale: str,
    message_count: int,
) -> SessionRecord | None:
    if registry is None:
        return existing
    return await registry.register_turn(
        session_id=session_id,
        checkpoint_thread_id=thread_id,
        browser_owner_key=(
            existing.browser_owner_key if existing is not None else owner_id
        ),
        account_owner_key=account_owner_id,
        first_message=first_message,
        locale=locale if locale in {"en", "pl"} else "en",
        message_count=message_count,
    )


async def _delete_checkpoint_thread(
    graph: CompiledStateGraph,
    thread_id: str,
    *,
    strict: bool = False,
) -> bool:
    checkpointer = getattr(graph, "checkpointer", None)
    delete = getattr(checkpointer, "adelete_thread", None)
    if delete is None:
        if strict:
            raise RuntimeError("Checkpoint backend cannot delete owned data")
        logger.warning("Checkpoint backend does not expose thread deletion")
        return False
    await delete(thread_id)
    return True


def _owner_id(request: Request) -> str:
    owner_id = getattr(request.state, "owner_id", None)
    if not owner_id:
        raise HTTPException(status_code=401, detail="Browser identity is required.")
    return owner_id


def _thread_config(owner_id: str, session_id: str) -> dict:
    return {"configurable": {"thread_id": private_thread_id(owner_id, session_id)}}


async def _enforce_rate_limit(
    rate_limiter: RateLimiter,
    owner_id: str,
) -> None:
    try:
        allowed = await rate_limiter.check(owner_id)
    except RateLimiterUnavailable:
        logger.error("Shared rate limiter unavailable; request denied")
        raise HTTPException(
            status_code=503, detail="Request protection is temporarily unavailable."
        )
    if not allowed:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Try again shortly."
        )


# ── Error-handling middleware ───────────────────────────────────────────────
class _ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                f"Unhandled error on {request.method} {request.url.path}: {exc}"
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "An internal error occurred. Please try again."},
            )


# ── Request-ID middleware ──────────────────────────────────────────────────
class _RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Lifespan ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await _graph_dep.initialize()
    try:
        await _rate_limiter_dep.initialize()
        try:
            await _session_registry_dep.initialize()
            try:
                registry = _session_registry_dep()
                stale_before = datetime.now(UTC) - timedelta(
                    days=_session_registry_dep.retention_days
                )
                stale_threads = await registry.purge_inactive_saved(stale_before)
                graph = _graph_dep()
                for thread_id in stale_threads:
                    await _delete_checkpoint_thread(graph, thread_id)
                if stale_threads:
                    logger.info(f"Removed {len(stale_threads)} inactive saved sessions")
                yield
            finally:
                await _session_registry_dep.shutdown()
        finally:
            await _rate_limiter_dep.shutdown()
    finally:
        await _graph_dep.shutdown()
        logger.info("Shutting down — checkpoint and rate-limit resources closed")


# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Wanderlisted Travel Agent",
    version=_API_VERSION,
    lifespan=lifespan,
)

_cors_origins = _api_cfg.get("cors_origins", ["http://localhost:3000"])
_origins = (
    [os.environ["FRONTEND_URL"]] if os.environ.get("FRONTEND_URL") else _cors_origins
)

app.add_middleware(_ErrorHandlerMiddleware)
app.add_middleware(_RequestIDMiddleware)
app.add_middleware(BrowserPrincipalMiddleware, signer=_principal_signer)
if _clerk_settings.enabled:
    app.add_middleware(ClerkIdentityMiddleware, validator=_clerk_validator)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# ── Request / Response models ──────────────────────────────────────────────
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="Session ID for conversation continuity. Omit to start a new session.",
    )
    service_scope_decision: ServiceScopeDecision | None = Field(
        default=None,
        description="Typed response to the current fingerprinted service-scope offer.",
    )
    ui_locale: Literal["en", "pl"] | None = Field(
        default=None,
        description=(
            "Selected interface locale used only when the message language and "
            "conversation history are ambiguous."
        ),
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must contain non-whitespace characters")
        return stripped


class ChatResponse(BaseModel):
    message: str
    session_id: str
    run_id: str | None = Field(
        default=None,
        description="LangSmith run ID — use for feedback submission via /api/v1/feedback.",
    )
    interrupted: bool = Field(
        default=False,
        description="True if the graph paused at a HITL gate waiting for user input.",
    )
    interrupt_data: dict | None = Field(
        default=None,
        description="HITL interrupt payload — present when interrupted=True.",
    )
    budget: BudgetBreakdown | None = Field(
        default=None,
        description="Structured budget breakdown when BudgetAgent has run.",
    )
    components: dict | None = Field(
        default=None,
        description="All structured agent results (flights, hotels, restaurants, etc.).",
    )
    locale: str = Field(
        default="en",
        pattern=r"^[a-z]{2,3}$",
        description="Resolved assistant response locale for this turn.",
    )


class SessionInfo(BaseModel):
    session_id: str
    message_count: int


class SessionSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    locale: Literal["en", "pl"]
    message_count: int


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    next_cursor: str | None = None


class AccountPreferences(BaseModel):
    locale: Literal["en", "pl"]


class AccountPreferencesResponse(BaseModel):
    locale: Literal["en", "pl"] | None = None


class ClaimSessionsRequest(BaseModel):
    session_ids: list[str] = Field(min_length=1, max_length=50)

    @field_validator("session_ids")
    @classmethod
    def validate_session_ids(cls, values: list[str]) -> list[str]:
        validated: list[str] = []
        for value in values:
            if (
                not value
                or len(value) > 128
                or not all(
                    character.isalnum() or character in {"_", "-"}
                    for character in value
                )
            ):
                raise ValueError("session_ids contain an invalid ID")
            if value not in validated:
                validated.append(value)
        return validated


class ClaimSessionsResponse(BaseModel):
    claimed: int


@app.get("/api/v1/media/google-place-photo")
async def google_place_photo(
    name: str = Query(
        ...,
        min_length=10,
        max_length=500,
        pattern=r"^places/[A-Za-z0-9._~-]+/photos/[A-Za-z0-9._~-]+$",
    ),
    max_height: int = Query(default=400, ge=100, le=1600),
    owner_id: str = Depends(_owner_id),
    rate_limiter: RateLimiter = Depends(_rate_limiter_dep),
):
    """Resolve one bounded Google Places photo without exposing credentials."""
    await _enforce_rate_limit(rate_limiter, owner_id)
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="Place photos are unavailable")

    url = f"https://places.googleapis.com/v1/{name}/media"
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            upstream = await client.get(
                url,
                params={"maxHeightPx": max_height, "key": api_key},
                timeout=10,
            )
        upstream.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Google Places photo proxy failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Place photo unavailable") from exc

    content_type = upstream.headers.get("content-type", "application/octet-stream")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Invalid place photo response")
    if len(upstream.content) > 10_000_000:
        raise HTTPException(status_code=502, detail="Place photo response is too large")
    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


# ── Core graph runner ──────────────────────────────────────────────────────
@traceable(run_type="chain", name="wanderlisted_chat")
async def _run_agent(
    message: str,
    thread_id: str,
    graph: CompiledStateGraph,
    service_scope_decision: ServiceScopeDecision | None = None,
    ui_locale: Literal["en", "pl"] | None = None,
) -> dict:
    """Run the multi-agent supervisor graph and return response data."""
    run_id = _current_langsmith_run_id()

    graph_input: dict = {"messages": [HumanMessage(content=message)]}
    if service_scope_decision:
        graph_input["service_scope_decision"] = service_scope_decision.model_dump(
            mode="json"
        )
    if ui_locale:
        graph_input["ui_locale"] = ui_locale

    result = await asyncio.wait_for(
        graph.ainvoke(
            graph_input,
            config={"configurable": {"thread_id": thread_id}},
        ),
        timeout=_REQUEST_TIMEOUT,
    )
    components = result.get("itinerary_components", {})

    exposed = _public_components(
        components,
        result.get("component_results"),
        result.get("safety_warning"),
        result.get("service_scope_offer"),
    )

    # Check for HITL interrupts
    interrupts = result.get("__interrupt__", [])
    interrupted = bool(interrupts)
    interrupt_data = None
    if interrupted and interrupts:
        interrupt_data = (
            interrupts[0].value
            if hasattr(interrupts[0], "value")
            else str(interrupts[0])
        )

    return {
        "message": _public_response_message(result),
        "run_id": run_id,
        "interrupted": interrupted,
        "interrupt_data": interrupt_data if isinstance(interrupt_data, dict) else None,
        "budget": components.get("budget_structured"),
        "components": exposed,
        "locale": result.get("response_locale", ui_locale or "en"),
        "message_count": len(result.get("messages", [])),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────
@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    owner_id: str = Depends(_owner_id),
    rate_limiter: RateLimiter = Depends(_rate_limiter_dep),
    graph: CompiledStateGraph = Depends(_graph_dep),
):
    """Chat with the travel agent. Provide a session_id to continue a conversation."""
    session_id = request.session_id or str(uuid.uuid4())

    await _enforce_rate_limit(rate_limiter, owner_id)
    registry = _optional_session_registry()
    account_owner_id = current_account_owner()
    thread_id, record = await _resolve_session_record(
        owner_id=owner_id,
        session_id=session_id,
        account_owner_id=account_owner_id,
        registry=registry,
    )
    record = await _record_session_turn(
        registry,
        session_id=session_id,
        thread_id=thread_id,
        owner_id=owner_id,
        account_owner_id=account_owner_id,
        existing=record,
        first_message=request.message,
        locale=request.ui_locale or (record.locale if record else "en"),
        message_count=record.message_count if record else 0,
    )

    try:
        data = await _run_agent(
            request.message,
            thread_id,
            graph,
            service_scope_decision=request.service_scope_decision,
            ui_locale=request.ui_locale,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="The agent pipeline timed out. Please try a simpler query.",
        )

    await _record_session_turn(
        registry,
        session_id=session_id,
        thread_id=thread_id,
        owner_id=owner_id,
        account_owner_id=account_owner_id,
        existing=record,
        first_message=request.message,
        locale=data.get("locale", request.ui_locale or "en"),
        message_count=data.get("message_count", 0),
    )

    return ChatResponse(
        message=data["message"],
        session_id=session_id,
        run_id=data.get("run_id"),
        interrupted=data.get("interrupted", False),
        interrupt_data=data.get("interrupt_data"),
        budget=data["budget"],
        components=data["components"],
        locale=data.get("locale", request.ui_locale or "en"),
    )


@app.post("/api/v1/chat/stream")
async def chat_stream(
    request: ChatRequest,
    owner_id: str = Depends(_owner_id),
    rate_limiter: RateLimiter = Depends(_rate_limiter_dep),
    graph: CompiledStateGraph = Depends(_graph_dep),
):
    """Stream agent execution events via SSE."""
    session_id = request.session_id or str(uuid.uuid4())

    await _enforce_rate_limit(rate_limiter, owner_id)
    registry = _optional_session_registry()
    account_owner_id = current_account_owner()
    thread_id, record = await _resolve_session_record(
        owner_id=owner_id,
        session_id=session_id,
        account_owner_id=account_owner_id,
        registry=registry,
    )
    record = await _record_session_turn(
        registry,
        session_id=session_id,
        thread_id=thread_id,
        owner_id=owner_id,
        account_owner_id=account_owner_id,
        existing=record,
        first_message=request.message,
        locale=request.ui_locale or (record.locale if record else "en"),
        message_count=record.message_count if record else 0,
    )
    config = {"configurable": {"thread_id": thread_id}}

    async def _event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        # Use an asyncio.Queue to decouple graph streaming from SSE output,
        # allowing us to inject keepalive pings while agents are working.
        queue: asyncio.Queue = asyncio.Queue()
        _SENTINEL = object()
        _KEEPALIVE_INTERVAL = 15  # seconds
        stream_run_id: str | None = None

        @traceable(run_type="chain", name="wanderlisted_chat_stream")
        async def _stream_graph():
            """Push graph events into the queue; signal completion with _SENTINEL."""
            nonlocal stream_run_id
            stream_run_id = _current_langsmith_run_id()
            try:
                graph_input: dict = {
                    "messages": [HumanMessage(content=request.message)]
                }
                if request.service_scope_decision:
                    graph_input["service_scope_decision"] = (
                        request.service_scope_decision.model_dump(mode="json")
                    )
                if request.ui_locale:
                    graph_input["ui_locale"] = request.ui_locale

                async for node_output in graph.astream(
                    graph_input,
                    config=config,
                    stream_mode="updates",
                ):
                    for node_name, update in node_output.items():
                        agent_name = {
                            "flights": "FlightsAgent",
                            "hotel_stay": "HotelsAgent",
                            "hotel_fan_in": "HotelsAgent",
                            "readiness_preflight": "TravelReadinessAgent",
                            "readiness": "TravelReadinessAgent",
                            "restaurants": "RestaurantsAgent",
                            "activities": "ActivitiesAgent",
                            "transportation": "TransportationAgent",
                            "budget": "BudgetAgent",
                            "itinerary": "ItineraryAgent",
                        }.get(node_name)
                        if agent_name:
                            await queue.put(
                                f"data: {json.dumps({'type': 'agent_start', 'agent': agent_name})}\n\n"
                            )
                        messages = update.get("messages", [])
                        for msg in messages:
                            if isinstance(msg, AIMessage) and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    await queue.put(
                                        f"data: {json.dumps({'type': 'tool_call', 'tool': tc['name']})}\n\n"
                                    )
                            if isinstance(msg, ToolMessage):
                                await queue.put(
                                    f"data: {json.dumps({'type': 'tool_result', 'tool': msg.name or ''})}\n\n"
                                )
            except asyncio.TimeoutError:
                await queue.put(
                    f"data: {json.dumps({'type': 'error', 'message': 'Agent pipeline timed out'})}\n\n"
                )
            except Exception as exc:
                logger.error(f"Stream error for session {session_id}: {exc}")
                await queue.put(
                    f"data: {json.dumps({'type': 'error', 'message': 'An internal error occurred'})}\n\n"
                )
            finally:
                await queue.put(_SENTINEL)

        # Launch the graph stream as a background task
        stream_task = asyncio.create_task(_stream_graph())

        try:
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(), timeout=_KEEPALIVE_INTERVAL
                    )
                except asyncio.TimeoutError:
                    # No event within the interval — send SSE keepalive comment
                    yield ": keepalive\n\n"
                    continue

                if item is _SENTINEL:
                    break
                yield item
        finally:
            if not stream_task.done():
                stream_task.cancel()

        # Check for HITL interrupts and send one final structured payload.
        state = await graph.aget_state(config)
        interrupt_payload = None
        interrupted = bool(state and state.next)
        if interrupted:
            # Graph is paused at a HITL gate
            if hasattr(state, "tasks"):
                for task in state.tasks:
                    if hasattr(task, "interrupts") and task.interrupts:
                        interrupt_payload = (
                            task.interrupts[0].value
                            if hasattr(task.interrupts[0], "value")
                            else str(task.interrupts[0])
                        )
                        break
            yield f"data: {json.dumps({'type': 'interrupt', 'gate': state.next[0] if state.next else '', 'data': interrupt_payload})}\n\n"
        values = state.values if state else {}
        final_message = _public_response_message(values)
        if final_message:
            yield f"data: {json.dumps({'type': 'token', 'token': final_message})}\n\n"
        components = values.get("itinerary_components", {})
        done_payload = {
            "type": "done",
            "run_id": stream_run_id,
            "interrupted": interrupted,
            "interrupt_data": (
                interrupt_payload if isinstance(interrupt_payload, dict) else None
            ),
            "budget": jsonable_encoder(components.get("budget_structured")),
            "components": _public_components(
                components,
                values.get("component_results"),
                values.get("safety_warning"),
                values.get("service_scope_offer"),
            ),
            "locale": values.get("response_locale", request.ui_locale or "en"),
        }
        await _record_session_turn(
            registry,
            session_id=session_id,
            thread_id=thread_id,
            owner_id=owner_id,
            account_owner_id=account_owner_id,
            existing=record,
            first_message=request.message,
            locale=done_payload["locale"],
            message_count=len(values.get("messages", [])),
        )
        yield f"data: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _session_summary(record: SessionRecord) -> SessionSummary:
    return SessionSummary(
        id=record.session_id,
        title=record.title,
        created_at=record.created_at,
        updated_at=record.updated_at,
        locale=record.locale,
        message_count=record.message_count,
    )


def _interrupt_from_state(state) -> tuple[bool, dict | None]:
    interrupted = bool(state and getattr(state, "next", None))
    if not interrupted:
        return False, None
    for task in getattr(state, "tasks", ()):
        interrupts = getattr(task, "interrupts", ())
        if interrupts:
            value = getattr(interrupts[0], "value", None)
            return True, value if isinstance(value, dict) else None
    return True, None


@app.get("/api/v1/account/preferences", response_model=AccountPreferencesResponse)
async def get_account_preferences(
    account_owner_id: str = Depends(_required_account_owner),
    registry: SessionRegistry = Depends(_session_registry_dep),
):
    """Return only non-sensitive account UI preferences."""
    return AccountPreferencesResponse(
        locale=await registry.get_preference(account_owner_id)
    )


@app.put("/api/v1/account/preferences", response_model=AccountPreferences)
async def put_account_preferences(
    preferences: AccountPreferences,
    account_owner_id: str = Depends(_required_account_owner),
    registry: SessionRegistry = Depends(_session_registry_dep),
):
    await registry.put_preference(account_owner_id, preferences.locale)
    return preferences


@app.get("/api/v1/sessions", response_model=SessionListResponse)
async def list_sessions(
    cursor: str | None = Query(default=None, max_length=1024),
    limit: int = Query(default=20, ge=1, le=50),
    account_owner_id: str = Depends(_required_account_owner),
    registry: SessionRegistry = Depends(_session_registry_dep),
):
    """List saved sessions for the verified account with cursor pagination."""
    try:
        records, next_cursor = await registry.list_account_sessions(
            account_owner_id, cursor=cursor, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SessionListResponse(
        items=[_session_summary(record) for record in records],
        next_cursor=next_cursor,
    )


@app.post("/api/v1/account/claim-sessions", response_model=ClaimSessionsResponse)
async def claim_sessions(
    claim: ClaimSessionsRequest,
    owner_id: str = Depends(_owner_id),
    account_owner_id: str = Depends(_required_account_owner),
    registry: SessionRegistry = Depends(_session_registry_dep),
):
    """Explicitly attach selected sessions from this browser to the account."""
    claimed = await registry.claim_sessions(
        browser_owner_key=owner_id,
        account_owner_key=account_owner_id,
        session_ids=claim.session_ids,
    )
    return ClaimSessionsResponse(claimed=claimed)


@app.get("/api/v1/sessions/{session_id}/snapshot")
async def get_session_snapshot(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    ],
    owner_id: str = Depends(_owner_id),
    graph: CompiledStateGraph = Depends(_graph_dep),
):
    """Restore public conversation, typed results, and a pending HITL gate."""
    thread_id, record = await _resolve_session_record(
        owner_id=owner_id,
        session_id=session_id,
        account_owner_id=current_account_owner(),
        registry=_optional_session_registry(),
    )
    state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    if not state or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Session not found")
    messages = []
    for message in state.values["messages"]:
        if isinstance(message, HumanMessage):
            messages.append(
                {"role": "user", "content": _extract_text_content(message.content)}
            )
        elif isinstance(message, AIMessage) and message.content:
            messages.append(
                {
                    "role": "assistant",
                    "content": _extract_text_content(message.content),
                }
            )
    components = state.values.get("itinerary_components", {})
    interrupted, interrupt_data = _interrupt_from_state(state)
    return {
        "session": (
            _session_summary(record).model_dump(mode="json") if record else None
        ),
        "messages": messages,
        "interrupted": interrupted,
        "interrupt_data": interrupt_data,
        "budget": jsonable_encoder(components.get("budget_structured")),
        "components": _public_components(
            components,
            state.values.get("component_results"),
            state.values.get("safety_warning"),
            state.values.get("service_scope_offer"),
        ),
        "locale": state.values.get(
            "response_locale", record.locale if record else "en"
        ),
    }


@app.delete("/api/v1/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    ],
    owner_id: str = Depends(_owner_id),
    graph: CompiledStateGraph = Depends(_graph_dep),
    registry: SessionRegistry = Depends(_session_registry_dep),
):
    """Delete one accessible registry record and its checkpoint payload."""
    account_owner_id = current_account_owner()
    record = await registry.find_accessible(
        session_id=session_id,
        browser_owner_key=owner_id,
        account_owner_key=account_owner_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await _delete_checkpoint_thread(graph, record.checkpoint_thread_id, strict=True)
    deleted = await registry.delete_accessible(
        session_id=session_id,
        browser_owner_key=owner_id,
        account_owner_key=account_owner_id,
    )
    if deleted is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


@app.post("/api/v1/webhooks/clerk")
async def clerk_webhook(
    request: Request,
    graph: CompiledStateGraph = Depends(_graph_dep),
    registry: SessionRegistry = Depends(_session_registry_dep),
):
    """Apply verified Clerk lifecycle deletion without storing Clerk PII."""
    if _clerk_webhook_settings is None or not _clerk_settings.enabled:
        raise HTTPException(status_code=404, detail="Webhook is not configured")
    body = await request.body()
    try:
        event = verify_clerk_webhook(
            body,
            request.headers,
            settings=_clerk_webhook_settings,
        )
    except ClerkWebhookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if event.get("type") != "user.deleted":
        return {"received": True, "deleted": 0}
    data = event.get("data")
    subject = data.get("id") if isinstance(data, dict) else None
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=400, detail="Deleted user ID is missing")
    account_owner_id = opaque_account_owner(
        subject, hash_key=_clerk_settings.owner_hash_key
    )
    thread_ids = await registry.account_thread_ids(account_owner_id)
    for thread_id in thread_ids:
        await _delete_checkpoint_thread(graph, thread_id, strict=True)
    await registry.delete_account(account_owner_id)
    return {"received": True, "deleted": len(thread_ids)}


@app.get("/api/v1/sessions/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    ],
    owner_id: str = Depends(_owner_id),
    graph: CompiledStateGraph = Depends(_graph_dep),
):
    """Get session info including message count."""
    thread_id, _ = await _resolve_session_record(
        owner_id=owner_id,
        session_id=session_id,
        account_owner_id=current_account_owner(),
        registry=_optional_session_registry(),
    )
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    if not state or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(
        session_id=session_id,
        message_count=len(state.values["messages"]),
    )


@app.get("/api/v1/sessions/{session_id}/history")
async def get_session_history(
    session_id: Annotated[
        str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    ],
    owner_id: str = Depends(_owner_id),
    graph: CompiledStateGraph = Depends(_graph_dep),
):
    """Get conversation history for a session."""
    thread_id, _ = await _resolve_session_record(
        owner_id=owner_id,
        session_id=session_id,
        account_owner_id=current_account_owner(),
        registry=_optional_session_registry(),
    )
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)
    if not state or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Session not found")
    messages = []
    for msg in state.values["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage) and msg.content:
            messages.append(
                {"role": "assistant", "content": _extract_text_content(msg.content)}
            )
    return {"session_id": session_id, "messages": messages}


@app.get("/api/v1/health")
async def health():
    """Liveness probe — is the process alive?"""
    return {"status": "healthy", "version": _API_VERSION}


@app.get("/api/v1/ready")
async def readiness(
    graph: CompiledStateGraph = Depends(_graph_dep),
    rate_limiter: RateLimiter = Depends(_rate_limiter_dep),
):
    """Readiness probe — is the graph initialized and able to serve traffic?"""
    return {
        "status": "ready",
        "version": _API_VERSION,
        "framework": "langgraph",
        "checkpoint_backend": _graph_dep.backend,
        "rate_limit_backend": _rate_limiter_dep.backend,
        "session_registry_backend": _session_registry_dep.backend,
    }


# ── HITL: Resume interrupted graph execution ────────────────────────────────


class HumanResumeDecision(BaseModel):
    gate: Literal["human_review"]
    action: Literal["approved", "edited", "rejected"]
    feedback: str = Field(default="", max_length=2000)


class LegacyResumeDecision(BaseModel):
    """Backward-compatible decision accepted from older persisted clients."""

    model_config = ConfigDict(extra="forbid")

    approved: bool
    feedback: str = Field(default="", max_length=2000)


TypedResumeDecision = Annotated[
    BudgetReviewDecision | HumanResumeDecision,
    Field(discriminator="gate"),
]


class ResumeRequest(BaseModel):
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="The public session ID of the interrupted graph",
    )
    decision: TypedResumeDecision | LegacyResumeDecision = Field(
        ...,
        description="Typed budget or itinerary-review decision.",
    )
    ui_locale: Literal["en", "pl"] | None = None


class ResumeResponse(BaseModel):
    message: str
    session_id: str
    status: str  # "resumed", "completed", "interrupted"
    interrupted: bool = False
    interrupt_data: dict | None = None
    budget: BudgetBreakdown | None = None
    components: dict | None = None
    locale: str = Field(default="en", pattern=r"^[a-z]{2,3}$")


@app.post("/api/v1/chat/resume", response_model=ResumeResponse)
async def resume_chat(
    request: ResumeRequest,
    owner_id: str = Depends(_owner_id),
    rate_limiter: RateLimiter = Depends(_rate_limiter_dep),
    graph: CompiledStateGraph = Depends(_graph_dep),
):
    """Resume an interrupted graph execution with a human decision.

    Use this endpoint after the graph pauses at budget_review or human_review.
    The decision dict is passed back via Command(resume=decision).
    """
    from langgraph.types import Command

    await _enforce_rate_limit(rate_limiter, owner_id)
    registry = _optional_session_registry()
    account_owner_id = current_account_owner()
    thread_id, record = await _resolve_session_record(
        owner_id=owner_id,
        session_id=request.session_id,
        account_owner_id=account_owner_id,
        registry=registry,
    )
    config = {"configurable": {"thread_id": thread_id}}

    # Verify session exists and is in interrupted state
    state = await graph.aget_state(config)
    if not state or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        command_update = {"ui_locale": request.ui_locale} if request.ui_locale else None
        result = await asyncio.wait_for(
            graph.ainvoke(
                Command(
                    resume=request.decision.model_dump(mode="json", exclude_none=True),
                    update=command_update,
                ),
                config,
            ),
            timeout=_REQUEST_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Resume timed out.")

    last_message = (
        _extract_text_content(result["messages"][-1].content)
        if result.get("messages")
        else ""
    )

    # Determine the status
    interrupts = result.get("__interrupt__", [])
    interrupted = bool(interrupts)
    status = "interrupted" if interrupted else "completed"
    interrupt_data = None
    if interrupts:
        interrupt_data = (
            interrupts[0].value if hasattr(interrupts[0], "value") else None
        )
    components = result.get("itinerary_components", {})
    exposed = _public_components(
        components,
        result.get("component_results"),
        result.get("safety_warning"),
        result.get("service_scope_offer"),
    )
    response_locale = result.get(
        "response_locale",
        state.values.get("response_locale", request.ui_locale or "en"),
    )
    first_human_message = next(
        (
            _extract_text_content(message.content)
            for message in result.get("messages", [])
            if isinstance(message, HumanMessage)
        ),
        "Saved trip",
    )
    await _record_session_turn(
        registry,
        session_id=request.session_id,
        thread_id=thread_id,
        owner_id=owner_id,
        account_owner_id=account_owner_id,
        existing=record,
        first_message=first_human_message,
        locale=response_locale,
        message_count=len(result.get("messages", [])),
    )

    return ResumeResponse(
        message=last_message,
        session_id=request.session_id,
        status=status,
        interrupted=interrupted,
        interrupt_data=interrupt_data if isinstance(interrupt_data, dict) else None,
        budget=components.get("budget_structured"),
        components=exposed,
        locale=response_locale,
    )


# ── User Feedback Collection for LangSmith ──────────────────────────────────


class FeedbackRequest(BaseModel):
    run_id: uuid.UUID = Field(
        ..., description="Actual LangSmith run ID returned by a traced chat request"
    )
    score: float = Field(
        ..., ge=0.0, le=1.0, description="1.0 = thumbs up, 0.0 = thumbs down"
    )
    comment: str = Field(
        default="", max_length=1000, description="Optional feedback text"
    )
    key: str = Field(
        default="user_rating",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.-]+$",
        description="Feedback key name",
    )


@app.post("/api/v1/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    owner_id: str = Depends(_owner_id),
    rate_limiter: RateLimiter = Depends(_rate_limiter_dep),
):
    """Collect user feedback and link to a LangSmith run.

    The frontend should store the run_id from a previous chat response
    and POST it here when the user clicks thumbs up/down.
    """
    await _enforce_rate_limit(rate_limiter, owner_id)
    try:
        client = Client()
        client.create_feedback(
            run_id=request.run_id,
            key=request.key,
            score=request.score,
            comment=request.comment if request.comment else None,
        )
        return {"status": "ok", "run_id": str(request.run_id), "key": request.key}
    except Exception as exc:
        logger.error(f"Failed to submit feedback: {exc}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")
