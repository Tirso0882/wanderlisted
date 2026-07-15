import asyncio
import json
import os
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from time import time

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph
from langsmith import traceable
from langsmith import Client
from pydantic import BaseModel, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

from custom_logging import AppLogger
from src.agent.stage4_graph import create_multiagent_travel_graph
import config as app_config

load_dotenv(override=True)

_api_cfg = app_config.get("api") or {}
_API_VERSION = _api_cfg.get("version", "2.0.0")
_REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "120"))

# ── Logging ─────────────────────────────────────────────────────────────────
logger = AppLogger(
    logger_name="api",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)


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


# ── Graph dependency (replaces global mutable state) ────────────────────────
class _GraphDependency:
    """Lazy-initialized graph singleton, injectable via FastAPI Depends."""

    def __init__(self) -> None:
        self._graph: CompiledStateGraph | None = None

    async def initialize(self) -> None:
        from langgraph.checkpoint.memory import InMemorySaver

        checkpointer = InMemorySaver()
        self._graph = create_multiagent_travel_graph(checkpointer=checkpointer)
        logger.info("Multi-agent graph initialized")

    def __call__(self) -> CompiledStateGraph:
        if self._graph is None:
            raise RuntimeError("Graph not initialized — app did not start correctly")
        return self._graph


_graph_dep = _GraphDependency()


# ── Rate limiter ────────────────────────────────────────────────────────────
class _RateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, client_id: str) -> bool:
        now = time()
        self._hits[client_id] = [
            ts for ts in self._hits[client_id] if now - ts < self.window
        ]
        if len(self._hits[client_id]) >= self.max_requests:
            return False
        self._hits[client_id].append(now)
        return True


_rate_limiter = _RateLimiter(
    max_requests=int(os.environ.get("RATE_LIMIT_MAX", "20")),
    window_seconds=int(os.environ.get("RATE_LIMIT_WINDOW", "60")),
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
    yield
    logger.info("Shutting down — cleaning up resources")


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation continuity. Omit to start a new session.",
    )
    target_agent: str | None = Field(
        default=None,
        description=(
            "Isolate a single agent. When set, bypasses triage/supervisor "
            "and routes directly to this agent only. "
            "Valid: FlightsAgent, HotelsAgent, DestinationAgent, "
            "RestaurantsAgent, ActivitiesAgent, TransportationAgent, "
            "BudgetAgent, ItineraryAgent."
        ),
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("message must contain non-whitespace characters")
        return stripped

    @field_validator("target_agent")
    @classmethod
    def validate_target_agent(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valid = {
            "FlightsAgent",
            "HotelsAgent",
            "DestinationAgent",
            "RestaurantsAgent",
            "ActivitiesAgent",
            "TransportationAgent",
            "BudgetAgent",
            "ItineraryAgent",
        }
        if v not in valid:
            raise ValueError(
                f"Invalid target_agent '{v}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return v


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
    budget: dict | None = Field(
        default=None,
        description="Structured budget breakdown when BudgetAgent has run.",
    )
    components: dict | None = Field(
        default=None,
        description="All structured agent results (flights, hotels, restaurants, etc.).",
    )


class SessionInfo(BaseModel):
    session_id: str
    message_count: int


# ── Core graph runner ──────────────────────────────────────────────────────
@traceable(run_type="chain", name="wanderlisted_chat")
async def _run_agent(
    message: str,
    session_id: str,
    graph: CompiledStateGraph,
    target_agent: str | None = None,
) -> dict:
    """Run the multi-agent supervisor graph and return response data."""
    import uuid as _uuid

    run_id = str(_uuid.uuid4())

    graph_input: dict = {"messages": [HumanMessage(content=message)]}
    if target_agent:
        graph_input["target_agent"] = target_agent

    result = await asyncio.wait_for(
        graph.ainvoke(
            graph_input,
            config={"configurable": {"thread_id": session_id}},
        ),
        timeout=_REQUEST_TIMEOUT,
    )
    components = result.get("itinerary_components", {})

    # Build a clean components dict without internal bookkeeping keys
    _internal_keys = {"routing", "completed_agents"}
    exposed = {k: v for k, v in components.items() if k not in _internal_keys}

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
        "message": _extract_text_content(result["messages"][-1].content)
        if result.get("messages")
        else "",
        "run_id": run_id,
        "interrupted": interrupted,
        "interrupt_data": interrupt_data if isinstance(interrupt_data, dict) else None,
        "budget": components.get("budget_structured"),
        "components": exposed or None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────
@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, graph: CompiledStateGraph = Depends(_graph_dep)):
    """Chat with the travel agent. Provide a session_id to continue a conversation."""
    session_id = request.session_id or str(uuid.uuid4())

    if not _rate_limiter.check(session_id):
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Try again shortly."
        )

    try:
        data = await _run_agent(
            request.message, session_id, graph, target_agent=request.target_agent
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="The agent pipeline timed out. Please try a simpler query.",
        )

    return ChatResponse(
        message=data["message"],
        session_id=session_id,
        run_id=data.get("run_id"),
        interrupted=data.get("interrupted", False),
        interrupt_data=data.get("interrupt_data"),
        budget=data["budget"],
        components=data["components"],
    )


@app.post("/api/v1/chat/stream")
async def chat_stream(
    request: ChatRequest, graph: CompiledStateGraph = Depends(_graph_dep)
):
    """Stream agent execution events via SSE."""
    session_id = request.session_id or str(uuid.uuid4())

    if not _rate_limiter.check(session_id):
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Try again shortly."
        )

    async def _event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        # Use an asyncio.Queue to decouple graph streaming from SSE output,
        # allowing us to inject keepalive pings while agents are working.
        queue: asyncio.Queue = asyncio.Queue()
        _SENTINEL = object()
        _KEEPALIVE_INTERVAL = 15  # seconds

        async def _stream_graph():
            """Push graph events into the queue; signal completion with _SENTINEL."""
            try:
                graph_input: dict = {
                    "messages": [HumanMessage(content=request.message)]
                }
                if request.target_agent:
                    graph_input["target_agent"] = request.target_agent

                async for node_output in graph.astream(
                    graph_input,
                    config={"configurable": {"thread_id": session_id}},
                    stream_mode="updates",
                ):
                    for node_name, update in node_output.items():
                        await queue.put(
                            f"data: {json.dumps({'type': 'agent_start', 'agent': node_name})}\n\n"
                        )
                        messages = update.get("messages", [])
                        for msg in messages:
                            if isinstance(msg, AIMessage) and msg.content:
                                await queue.put(
                                    f"data: {json.dumps({'type': 'token', 'token': _extract_text_content(msg.content)})}\n\n"
                                )
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

        # Check for HITL interrupts after the stream completes
        config = {"configurable": {"thread_id": session_id}}
        state = await graph.aget_state(config)
        if state and state.next:
            # Graph is paused at a HITL gate
            interrupt_payload = None
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

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/v1/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str, graph: CompiledStateGraph = Depends(_graph_dep)):
    """Get session info including message count."""
    config = {"configurable": {"thread_id": session_id}}
    state = await graph.aget_state(config)
    if not state or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(
        session_id=session_id,
        message_count=len(state.values["messages"]),
    )


@app.get("/api/v1/sessions/{session_id}/history")
async def get_session_history(
    session_id: str, graph: CompiledStateGraph = Depends(_graph_dep)
):
    """Get conversation history for a session."""
    config = {"configurable": {"thread_id": session_id}}
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
async def readiness(graph: CompiledStateGraph = Depends(_graph_dep)):
    """Readiness probe — is the graph initialized and able to serve traffic?"""
    return {"status": "ready", "version": _API_VERSION, "framework": "langgraph"}


# ── HITL: Resume interrupted graph execution ────────────────────────────────


class ResumeRequest(BaseModel):
    session_id: str = Field(
        ..., description="The session/thread ID of the interrupted graph"
    )
    decision: dict = Field(
        ...,
        description="The human decision, e.g. {'approved': true} or {'approved': true, 'feedback': '...'}",
    )


class ResumeResponse(BaseModel):
    message: str
    session_id: str
    status: str  # "resumed", "completed", "interrupted"


@app.post("/api/v1/chat/resume", response_model=ResumeResponse)
async def resume_chat(
    request: ResumeRequest, graph: CompiledStateGraph = Depends(_graph_dep)
):
    """Resume an interrupted graph execution with a human decision.

    Use this endpoint after the graph pauses at a HITL gate (safety_review,
    budget_review, or human_review). The decision dict is passed back via
    Command(resume=decision).
    """
    from langgraph.types import Command

    config = {"configurable": {"thread_id": request.session_id}}

    # Verify session exists and is in interrupted state
    state = await graph.aget_state(config)
    if not state or not state.values.get("messages"):
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        result = await asyncio.wait_for(
            graph.ainvoke(Command(resume=request.decision), config),
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
    status = "completed"
    if hasattr(result, "__interrupt__") and result.get("__interrupt__"):
        status = "interrupted"

    return ResumeResponse(
        message=last_message,
        session_id=request.session_id,
        status=status,
    )


# ── User Feedback Collection for LangSmith ──────────────────────────────────


class FeedbackRequest(BaseModel):
    run_id: str = Field(..., description="LangSmith run ID to attach feedback to")
    score: float = Field(
        ..., ge=0.0, le=1.0, description="1.0 = thumbs up, 0.0 = thumbs down"
    )
    comment: str = Field(
        default="", max_length=1000, description="Optional feedback text"
    )
    key: str = Field(default="user_rating", description="Feedback key name")


@app.post("/api/v1/feedback")
async def submit_feedback(request: FeedbackRequest):
    """Collect user feedback and link to a LangSmith run.

    The frontend should store the run_id from a previous chat response
    and POST it here when the user clicks thumbs up/down.
    """
    try:
        client = Client()
        client.create_feedback(
            run_id=request.run_id,
            key=request.key,
            score=request.score,
            comment=request.comment if request.comment else None,
        )
        return {"status": "ok", "run_id": request.run_id, "key": request.key}
    except Exception as exc:
        logger.error(f"Failed to submit feedback: {exc}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")
