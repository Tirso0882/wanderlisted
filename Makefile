.PHONY: help install dev test reindex rag-test clean lint fmt \
       docker-build docker-up docker-down eval-layer1

help:
	@echo "Wanderlisted — Travel Agent Build System"
	@echo ""
	@echo "Available targets:"
	@echo "  make install      — Install dependencies in venv"
	@echo "  make dev          — Start FastAPI dev server (http://localhost:8000)"
	@echo "  make test         — Run all tests (unit + integration)"
	@echo "  make test-unit    — Run unit tests only"
	@echo "  make reindex      — Re-index all 29 guides into Pinecone"
	@echo "  make rag-test     — Test RAG retrieval with 6 sample queries"
	@echo "  make coverage     — Show test coverage report"
	@echo "  make lint         — Lint code with ruff"
	@echo "  make fmt          — Format code with ruff"
	@echo "  make clean        — Remove cache, logs, and compiled files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build — Build the production Docker image"
	@echo "  make docker-up    — Start API + Redis + Postgres (docker compose)"
	@echo "  make docker-down  — Stop all containers"
	@echo ""
	@echo "Evaluation:"
	@echo "  make eval-layer1  — Run Layer 1 code-based evaluator tests"
	@echo ""

install:
	python -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -r requirements.txt

dev:
	.venv/bin/python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

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
	docker build -t wanderlisted:latest .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# ── Evaluation ────────────────────────────────────────────────────
eval-layer1:
	.venv/bin/pytest tests/test_evaluators.py -x --tb=short -q
