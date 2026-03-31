import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable
from pydantic import BaseModel, Field

from custom_logging import AppLogger
from src.agent.stage4_graph import create_multiagent_travel_graph
import config as app_config

load_dotenv()

_api_cfg = app_config.get("api") or {}

# ── Logging ─────────────────────────────────────────────────────────────────
logger = AppLogger(
    logger_name="api",
    level=os.environ.get("LOG_LEVEL", "INFO"),
)

graph = None
checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph, checkpointer
    from langgraph.checkpoint.memory import InMemorySaver

    checkpointer = InMemorySaver()
    graph = create_multiagent_travel_graph(checkpointer=checkpointer)
    yield


app = FastAPI(
    title="Wanderlisted Travel Agent",
    version=_api_cfg.get("version", "2.0.0"),
    lifespan=lifespan,
)

_cors_origins = _api_cfg.get("cors_origins", ["http://localhost:3000"])
# Allow env var to override config for deployment
_origins = [os.environ.get("FRONTEND_URL")] if os.environ.get("FRONTEND_URL") else _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation continuity. "
        "Omit to start a new session.",
    )


class ChatResponse(BaseModel):
    message: str
    session_id: str
    budget: dict | None = Field(
        default=None,
        description="Structured budget breakdown when BudgetAgent has run.",
    )


class SessionInfo(BaseModel):
    session_id: str
    message_count: int


@traceable(run_type="chain", name="wanderlisted_chat")
async def _run_agent(message: str, session_id: str) -> dict:
    """Run the multi-agent supervisor graph and return response data."""
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": session_id}},
    )
    components = result.get("itinerary_components", {})
    return {
        "message": result["messages"][-1].content,
        "budget": components.get("budget_structured"),
    }


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the travel agent. Provide a session_id to continue a conversation."""
    session_id = request.session_id or str(uuid.uuid4())
    data = await _run_agent(request.message, session_id)
    return ChatResponse(
        message=data["message"],
        session_id=session_id,
        budget=data["budget"],
    )


@app.get("/api/v1/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
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
async def get_session_history(session_id: str):
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
            messages.append({"role": "assistant", "content": msg.content})
    return {"session_id": session_id, "messages": messages}


@app.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": _api_cfg.get("version", "2.0.0"),
        "framework": "langgraph",
        "stage": 4,
    }
