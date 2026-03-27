import logging
import logging.config
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from langsmith import traceable
from pydantic import BaseModel, Field

from src.agent.agent import create_travel_agent

load_dotenv()

# ── Logging ─────────────────────────────────────────────────────────────────
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            "datefmt": "%H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "loggers": {
        # Show all wanderlisted internals at DEBUG+
        "src": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO"), "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
})

agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = create_travel_agent()
    yield


app = FastAPI(
    title="Wanderlisted Travel Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
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


@traceable(run_type="chain", name="wanderlisted_chat")
async def _run_agent(message: str, session_id: str) -> str:
    """Run the travel agent and return the response text."""
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": session_id}},
    )
    return result["messages"][-1].content


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the travel agent. Provide a session_id to continue a conversation."""
    session_id = request.session_id or str(uuid.uuid4())
    response_text = await _run_agent(request.message, session_id)
    return ChatResponse(message=response_text, session_id=session_id)


@app.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "framework": "langgraph",
        "stage": 1,
    }
