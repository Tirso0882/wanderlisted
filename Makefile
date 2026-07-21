.PHONY: help install dev studio test reindex rag-test clean lint fmt \
       docker-build docker-up docker-down eval-layer1 \
       smoke smoke-simple harness harness-agent \
       frontend frontend-build frontend-install

help:
	@echo "Wanderlisted — Travel Agent Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  make install      — Install dependencies in venv"
	@echo "  make dev          — Start FastAPI dev server (http://localhost:8000)"
	@echo "  make studio       — Start LangGraph Studio-compatible dev server"
	@echo "  make test         — Run all tests (unit + integration)"
	@echo "  make test-unit    — Run unit tests only"
	@echo "  make reindex      — Re-index all 29 guides into Pinecone"
	@echo "  make rag-test     — Test RAG retrieval with 6 sample queries"
	@echo "  make coverage     — Show test coverage report"
	@echo "  make lint         — Lint code with ruff"
	@echo "  make fmt          — Format code with ruff"
	@echo "  make clean        — Remove cache, logs, and compiled files"
	@echo ""
	@echo "Frontend:"
	@echo "  make frontend         — Start Next.js dev server (http://localhost:3000)"
	@echo "  make frontend-build   — Production build"
	@echo "  make frontend-install — Install frontend dependencies"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build — Build the production Docker image"
	@echo "  make docker-up    — Start API + Redis + Postgres (docker compose)"
	@echo "  make docker-down  — Stop all containers"
	@echo ""
	@echo "Smoke Tests:"
	@echo "  make smoke           — Quick graph smoke test (full agent pipeline)"
	@echo "  make smoke-simple    — Triage-only smoke test (shallow reply path)"
	@echo ""
	@echo "Agent Harness:"
	@echo "  make harness                    — Test ALL agents, HTML report"
	@echo "  make harness-agent AGENT=flights [ARGS='--dest Paris --open'] — Test one agent"
	@echo ""
	@echo "Evaluation:"
	@echo "  make eval-layer1  — Run Layer 1 code-based evaluator tests"
	@echo ""

install:
	python -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -r requirements.txt

dev:
	HITL_SAFETY_REVIEW=false HITL_BUDGET_REVIEW=false HITL_HUMAN_REVIEW=false \
	.venv/bin/python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

studio:
	.venv/bin/langgraph dev --config ./langgraph.json

test:
	.venv/bin/pytest tests/ -v --tb=short

test-unit:
	.venv/bin/pytest tests/ -v --tb=short -m "not integration"

reindex:
	@echo "Removing stale manifest and re-indexing into Pinecone…"
	rm -f knowledge_base/.cache/manifest.json
	.venv/bin/python -m src.rag.indexer
	@echo "✓ Re-index complete. Run 'make rag-test' to validate."

rag-test:
	@echo "Testing RAG retrieval with 6 sample queries…"
	.venv/bin/python scripts/test_rag_query.py

coverage:
	.venv/bin/pytest --cov=src tests/ --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

lint:
	.venv/bin/ruff check src/ tests/ scripts/

lint-fix:
	.venv/bin/ruff check src/ tests/ scripts/ --fix

fmt:
	.venv/bin/ruff format src/ tests/ scripts/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	rm -rf .coverage htmlcov/
	rm -rf logs/*.log
	@echo "✓ Cleaned up cache, logs, and compiled files"

# ── Docker ────────────────────────────────────────────────────────
docker-build:
	docker build -t wanderlisted:local .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# ── Evaluation ────────────────────────────────────────────────────
eval-layer1:
	.venv/bin/pytest tests/test_evaluators.py -x --tb=short -q

# ── Agent Harness (individual agent testing with HTML reports) ────
# Optional: ARGS="--dest Paris --open"  (extra flags passed to harness)
harness:
	.venv/bin/python scripts/agent_harness.py $(ARGS)

harness-agent:
	@test -n "$(AGENT)" || (echo "Usage: make harness-agent AGENT=flights [ARGS='--dest Paris --open']" && exit 1)
	.venv/bin/python scripts/agent_harness.py --agents $(AGENT) $(ARGS)

# ── Smoke Tests (graph-level) ────────────────────────────────────
smoke:
	.venv/bin/python scripts/test_graph_invoke.py

smoke-simple:
	.venv/bin/python scripts/test_graph_invoke.py --simple "Hello"

# ── Frontend ──────────────────────────────────────────────────────
frontend-install:
	cd frontend && pnpm install

frontend:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build
