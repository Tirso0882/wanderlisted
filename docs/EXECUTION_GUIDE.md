# Wanderlisted — Execution & Evaluation Guide

Complete reference for setting up, running, testing, and evaluating the Wanderlisted multi-agent travel planner.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Running the Application](#running-the-application)
4. [Testing](#testing)
5. [Evaluation Framework](#evaluation-framework)
6. [Agent Harness](#agent-harness)
7. [RAG Pipeline](#rag-pipeline)
8. [Docker](#docker)
9. [Kubernetes (Local)](#kubernetes-local)
10. [LangGraph Studio](#langgraph-studio)
11. [Quick Reference](#quick-reference)

---

## Prerequisites

- **Python** 3.12+
- **Node.js** 18+ and **pnpm** (for frontend)
- **Docker** & **Docker Compose** (for containerized mode)
- **kind** + **kubectl** (for local Kubernetes)

---

## Environment Setup

### 1. Clone & Install

```bash
cd wanderlisted
make install
```

This creates a `.venv/` virtual env and installs all Python dependencies from `requirements.txt`.

### 2. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

**Required keys:**

| Variable | Service | Purpose |
|----------|---------|---------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI | LLM inference (default provider) |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI | API endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Azure OpenAI | Model deployment name |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI | API version |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | Azure OpenAI | Embeddings model (3072 dims) |
| `PINECONE_API_KEY` | Pinecone | Vector store for RAG |
| `PINECONE_INDEX_NAME` | Pinecone | Index name (e.g., `wanderlisted-guides`) |
| `LANGCHAIN_API_KEY` | LangSmith | Tracing & evaluation |
| `LANGCHAIN_PROJECT` | LangSmith | Project name for traces |
| `TAVILY_API_KEY` | Tavily | Web search tool |
| `GOOGLE_MAPS_API_KEY` | Google Maps Platform | Places, Routes, Distance Matrix |
| `DUFFEL_ACCESS_TOKEN` | Duffel | Flight search |
| `HOTELBEDS_API_KEY` | Hotelbeds | Hotel availability |
| `HOTELBEDS_API_SECRET` | Hotelbeds | Hotel API auth |
| `OPENWEATHER_API_KEY` | OpenWeatherMap | Weather data |
| `EXCHANGERATE_API_KEY` | ExchangeRate API | Currency conversion |
| `COHERE_API_KEY` | Cohere | Reranking (optional, degrades gracefully) |

**Optional provider keys** (if switching `LLM_PROVIDER`):

| Variable | Provider |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI direct |
| `ANTHROPIC_API_KEY` | Anthropic |
| `GOOGLE_API_KEY` | Google Gemini |
| `OLLAMA_MODEL` / `OLLAMA_BASE_URL` | Ollama (local) |

### 3. Activate Virtual Environment

```bash
source .venv/bin/activate
```

### 4. Install Frontend Dependencies

```bash
make frontend-install
# or: cd frontend && pnpm install
```

---

## Running the Application

### Backend (FastAPI + SSE)

```bash
make dev
# → http://localhost:8000
# → Swagger docs: http://localhost:8000/docs
```

### Frontend (Next.js)

```bash
make frontend
# → http://localhost:3000
```

### Full Stack (both terminals)

```bash
# Terminal 1:
make dev

# Terminal 2:
make frontend
```

### MCP Server (for external AI agents)

```bash
python -m src.mcp_server
# Stdio transport — connect from Claude Desktop, Cursor, etc.
```

---

## Testing

### Layer 1 — Linting

```bash
make lint          # Check for issues
make lint-fix      # Auto-fix what's possible
make fmt           # Format code with ruff
```

### Layer 2 — Unit Tests (mocked, no API keys needed)

```bash
make test-unit     # ~514 tests, ~4-6s
```

### Layer 3 — Coverage Report

```bash
make coverage      # Generates htmlcov/index.html
                   # Fails if coverage < 80%
```

### Layer 4 — Integration Tests (requires live API keys)

```bash
make test          # All tests (unit + integration)
```

Integration tests use `@pytest.mark.integration` and are skipped automatically when the corresponding API key is missing.

### Layer 5 — Graph Smoke Tests (full pipeline, live APIs)

```bash
# Full pipeline: triage → supervisor → 6 parallel agents → fan-in → itinerary
make smoke

# Triage-only path (shallow reply, quick validation)
make smoke-simple
```

Custom query:
```bash
python scripts/test_graph_invoke.py "Weekend getaway in Verona, Italy"
python scripts/test_graph_invoke.py --simple "What's the capital of France?"
```

### Layer 6 — LangGraph Studio (interactive debugging)

```bash
langgraph dev
# Opens browser UI for visual node-by-node inspection
# Graphs defined in langgraph.json:
#   - travel_agent (legacy Stage 3)
#   - multiagent_supervisor (Stage 4 — primary)
```

---

## Evaluation Framework

Wanderlisted uses a **four-layer evaluation framework** powered by LangSmith.

### Layer 1 — Code-Based Evaluators (CI)

Tests supervisor routing, tool routing, and structured output schemas. Runs without LLM cost.

```bash
make eval-layer1
# or: pytest tests/test_evaluators.py -x --tb=short -q
```

### Layer 2 — LLM-as-Judge (LangSmith Experiments)

Upload golden dataset and run evaluator experiments:

```bash
# Upload the 30+ golden dataset cases to LangSmith
python scripts/eval_agents.py --upload-dataset

# Run full evaluation (agent + RAG evaluators)
python scripts/eval_agents.py --run

# Agent-only evaluation
python scripts/eval_agents.py --run --mode agent

# RAG-only evaluation
python scripts/eval_agents.py --run --mode rag

# Tag with experiment prefix
python scripts/eval_agents.py --run --prefix "v2-gpt5.4-mini"
```

### Layer 3 — RAG Quality Evaluation

Compare chunking strategies locally (no Pinecone writes):

```bash
python scripts/eval_rag.py             # Run all 5 strategies
python scripts/eval_rag.py --no-cache  # Ignore cached embeddings
```

Reports: retrieval scores, chunk distributions, Hits@1/3, noise rate.

### Layer 4 — End-to-End with Agent Harness

See [Agent Harness](#agent-harness) below.

---

## Agent Harness

Test individual specialized agents in isolation with HTML report output.

### Run All 8 Agents

```bash
make harness
```

### Run a Single Agent

```bash
make harness-agent AGENT=flights
make harness-agent AGENT=hotels
make harness-agent AGENT=destination
make harness-agent AGENT=restaurants
make harness-agent AGENT=activities
make harness-agent AGENT=transportation
make harness-agent AGENT=budget
make harness-agent AGENT=itinerary
```

### Custom Destination / Origin / Dates

```bash
make harness-agent AGENT=hotels ARGS="--dest 'Paris' --origin 'JFK' --dates '2026-09-01 to 2026-09-08'"
make harness-agent AGENT=flights ARGS="--dest 'Barcelona' --origin 'LAX'"
```

### Custom Prompt

```bash
make harness-agent AGENT=destination ARGS="--prompt 'Research visa requirements and safety in Colombia'"
make harness-agent AGENT=hotels ARGS="--dest 'Tokyo' --prompt 'Find luxury ryokan-style hotels near Shinjuku'"
```

### Auto-Open HTML Report

```bash
make harness-agent AGENT=restaurants ARGS="--dest 'Rome' --open"
```

### Save to Specific File

```bash
make harness-agent AGENT=budget ARGS="--dest 'Lisbon' --output outputs/lisbon_budget.html"
```

### List Available Agents

```bash
python scripts/agent_harness.py --list
```

---

## RAG Pipeline

### Index Knowledge Base into Pinecone

```bash
make reindex
# Removes stale manifest, re-chunks and embeds all 29 destination guides
```

### Validate RAG Retrieval

```bash
make rag-test
# Runs 6 sample queries and reports relevance scores
```

### Query Manually

```bash
python scripts/test_rag_query.py
```

---

## Docker

### Build & Run with Docker Compose

```bash
# Start everything (API + Redis + Postgres)
make docker-up
# → API: http://localhost:8000
# → Redis: localhost:6379
# → Postgres: localhost:5432

# Stop
make docker-down
```

### Build Image Only

```bash
make docker-build
```

---

## Kubernetes (Local)

Full local K8s deployment using **kind**.

### First-Time Setup

```bash
# 1. Create cluster with port mappings
make k8s-cluster

# 2. Build and load app image
make k8s-load

# 3. Load dependency images (Redis, Postgres)
make k8s-load-deps

# 4. Create secrets from .env
make k8s-secrets

# 5. Deploy all manifests
make k8s-up
```

### Day-to-Day Development

```bash
# After code changes — rebuild, reload, and rollout:
make k8s-redeploy

# Check status:
make k8s-status

# Follow logs:
make k8s-logs

# Validate endpoints:
make k8s-smoke-test
```

### Tear Down

```bash
make k8s-down
```

---

## LangGraph Studio

Interactive visual debugger for the multi-agent graph.

```bash
langgraph dev
```

The `langgraph.json` config exposes two graphs:
- `travel_agent` — Legacy Stage 3 single-agent
- `multiagent_supervisor` — **Stage 4** (primary): supervisor + 6 parallel agents + fan-in

Use Studio to:
- Step through nodes visually
- Inspect state at each checkpoint
- Test HITL interrupt/resume flows
- Debug routing decisions

---

## Quick Reference

| Task | Command | Time |
|------|---------|------|
| Lint | `make lint` | ~2s |
| Format | `make fmt` | ~2s |
| Unit tests | `make test-unit` | ~4-6s |
| Coverage | `make coverage` | ~6s |
| All tests | `make test` | ~30s |
| Layer 1 eval | `make eval-layer1` | ~4s |
| Graph smoke | `make smoke` | ~30-60s |
| Simple smoke | `make smoke-simple` | ~5s |
| Agent harness (all) | `make harness` | ~3-5min |
| Agent harness (one) | `make harness-agent AGENT=flights` | ~30-60s |
| RAG reindex | `make reindex` | ~2-5min |
| RAG test | `make rag-test` | ~10s |
| Backend dev server | `make dev` | persistent |
| Frontend dev server | `make frontend` | persistent |
| LangGraph Studio | `langgraph dev` | persistent |
| Docker full stack | `make docker-up` | ~30s |
| K8s deploy | `make k8s-up` | ~90s |

### Development Workflow

```bash
# After any code change:
make lint && make test-unit          # ~6s

# After tool/agent logic changes:
make smoke                           # ~30-60s

# Before merging a PR:
make coverage && make test           # ~40s

# Debugging agent flow:
langgraph dev                        # interactive

# Full E2E with UI:
make dev    # terminal 1
make frontend  # terminal 2
```

---

## Useful Scripts

| Script | Purpose |
|--------|---------|
| `scripts/test_graph_invoke.py` | Full graph smoke test |
| `scripts/agent_harness.py` | Individual agent testing with HTML reports |
| `scripts/eval_agents.py` | LangSmith evaluation runner |
| `scripts/eval_rag.py` | RAG chunking strategy comparison |
| `scripts/test_rag_query.py` | Manual RAG query testing |
| `scripts/download_guides.py` | Download destination guides for knowledge base |
| `scripts/test_hotelbeds_live.py` | Live Hotelbeds API test |
| `scripts/test_google_apis.py` | Live Google Maps API test |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Run `source .venv/bin/activate` |
| Tests fail with missing API key | Expected — integration tests skip gracefully |
| `coverage < 80%` | Check omitted paths in `pyproject.toml` |
| LangGraph Studio won't start | Ensure `.env` is populated, check `langgraph.json` |
| Docker build fails | Verify Docker Desktop is running |
| K8s pods in CrashLoopBackOff | Run `make k8s-logs` to inspect errors |
| RAG returns low relevance | Run `make reindex` to refresh embeddings |
