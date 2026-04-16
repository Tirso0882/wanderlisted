.PHONY: help install dev test reindex rag-test clean lint fmt \
       docker-build docker-up docker-down eval-layer1 \
       k8s-cluster k8s-load k8s-load-deps k8s-secrets k8s-up k8s-status k8s-logs k8s-down \
       k8s-redeploy k8s-smoke-test

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
	@echo "Kubernetes (kind — local cluster):"
	@echo "  make k8s-cluster    — Create kind cluster with port mappings"
	@echo "  make k8s-load       — Build app image and load it into kind"
	@echo "  make k8s-load-deps  — Pre-load redis + postgres images into kind"
	@echo "  make k8s-secrets    — Create K8s secrets from .env"
	@echo "  make k8s-up         — Apply all manifests (deploy everything)"
	@echo "  make k8s-status     — Show pods, services, deployments"
	@echo "  make k8s-logs       — Follow API pod logs"
	@echo "  make k8s-redeploy   — Full code-change loop: build → load → rollout"
	@echo "  make k8s-smoke-test — Hit every endpoint and report pass/fail"
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
	docker build -t wanderlisted:local .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# ── Kubernetes (kind — local cluster) ─────────────────────────────

# Step 1: Create the kind cluster with port 8000 mapped
k8s-cluster:
	kind create cluster --name wanderlisted --config k8s/kind-config.yaml
	kubectl cluster-info --context kind-wanderlisted

# Step 2: Build the Docker image and load it into kind
# (kind can't pull from local Docker daemon without this step)
k8s-load:
	docker build -t wanderlisted:local .
	kind load docker-image wanderlisted:local --name wanderlisted
	@echo "✓ App image loaded into kind cluster"

# Step 2b: Pre-pull dependency images and load them into kind.
# On Apple Silicon, kind v0.31+ uses --all-platforms when importing, which
# breaks on manifest-list images from Docker Desktop. We bypass this by
# importing directly into the kind node's containerd without that flag.
k8s-load-deps:
	docker pull redis:7-alpine
	docker save redis:7-alpine -o /tmp/wanderlisted-redis.tar
	docker cp /tmp/wanderlisted-redis.tar wanderlisted-control-plane:/root/redis.tar
	docker exec wanderlisted-control-plane ctr --namespace=k8s.io images import \
	  --digests --snapshotter=overlayfs /root/redis.tar
	docker exec wanderlisted-control-plane rm /root/redis.tar
	rm -f /tmp/wanderlisted-redis.tar
	docker pull postgres:16-alpine
	docker save postgres:16-alpine -o /tmp/wanderlisted-postgres.tar
	docker cp /tmp/wanderlisted-postgres.tar wanderlisted-control-plane:/root/postgres.tar
	docker exec wanderlisted-control-plane ctr --namespace=k8s.io images import \
	  --digests --snapshotter=overlayfs /root/postgres.tar
	docker exec wanderlisted-control-plane rm /root/postgres.tar
	rm -f /tmp/wanderlisted-postgres.tar
	@echo "✓ Dependency images loaded into kind cluster"

# Step 3: Create K8s secrets from your .env file
# This is the safe way — secrets never touch a file on disk
k8s-secrets:
	kubectl create namespace wanderlisted --dry-run=client -o yaml | kubectl apply -f -
	kubectl create secret generic wanderlisted-secrets \
	  --from-env-file=.env \
	  --namespace=wanderlisted \
	  --dry-run=client -o yaml | kubectl apply -f -
	@echo "✓ Secrets synced from .env"

# Step 4: Apply all manifests (namespace → configmap → redis → postgres → api)
k8s-up:
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/configmap.yaml
	kubectl apply -f k8s/redis.yaml
	kubectl apply -f k8s/postgres.yaml
	kubectl apply -f k8s/deployment.yaml
	kubectl apply -f k8s/service.yaml
	@echo "✓ All manifests applied — waiting for pods..."
	kubectl rollout status deployment/wanderlisted-api -n wanderlisted --timeout=90s

# Show the state of everything in the wanderlisted namespace
k8s-status:
	@echo "\n── Pods ──"
	kubectl get pods -n wanderlisted -o wide
	@echo "\n── Deployments ──"
	kubectl get deployments -n wanderlisted
	@echo "\n── Services ──"
	kubectl get services -n wanderlisted
	@echo "\n── Events (last 10) ──"
	kubectl get events -n wanderlisted --sort-by='.lastTimestamp' | tail -10

# Follow logs of the API pods (all replicas)
k8s-logs:
	kubectl logs -n wanderlisted -l app=wanderlisted-api -f --max-log-requests=4

# Tear down: delete the entire namespace (removes all resources inside it)
k8s-down:
	kubectl delete namespace wanderlisted --ignore-not-found

# ── Daily inner loop: one command for every code change ──────────────────────
# This is the command you'll run most often during development:
#   1. Rebuilds the Docker image from current source
#   2. Loads it into the kind cluster
#   3. Performs a rolling restart (zero downtime, probes gate traffic)
#   4. Waits until the rollout is confirmed complete
k8s-redeploy:
	make k8s-load
	kubectl rollout restart deployment/wanderlisted-api -n wanderlisted
	kubectl rollout status deployment/wanderlisted-api -n wanderlisted --timeout=90s
	@echo "✓ Redeploy complete — $(shell kubectl get deployment wanderlisted-api -n wanderlisted -o jsonpath='{.spec.template.spec.containers[0].image}')"

# ── Smoke test: validate every endpoint is reachable and correct ─────────────
k8s-smoke-test:
	@echo "── K8s smoke test ──"
	@curl -sf http://localhost:8000/api/v1/health > /dev/null && echo "✓ /api/v1/health" || echo "✗ /api/v1/health FAILED"
	@curl -sf http://localhost:8000/api/v1/ready > /dev/null && echo "✓ /api/v1/ready" || echo "✗ /api/v1/ready FAILED"
	@curl -sf http://localhost:8000/docs > /dev/null && echo "✓ /docs" || echo "✗ /docs FAILED"
	@curl -sf -X POST http://localhost:8000/api/v1/chat \
	  -H "Content-Type: application/json" \
	  -d '{"message":"Hello","session_id":"smoke-$$"}' > /dev/null && echo "✓ /api/v1/chat" || echo "✗ /api/v1/chat FAILED"
	@curl -s -X POST http://localhost:8000/api/v1/chat \
	  -H "Content-Type: application/json" \
	  -d '{"message":"   "}' | python3 -c \
	  "import sys,json; d=json.load(sys.stdin); print('✓ 422 validation' if 'value_error' in str(d) or 'detail' in d else '✗ 422 validation FAILED')"
	@curl -s http://localhost:8000/api/v1/sessions/no-such-id | python3 -c \
	  "import sys,json; d=json.load(sys.stdin); print('✓ 404 session' if d.get('detail')=='Session not found' else '✗ 404 session FAILED')"
	@echo "── done ──"

# ── Evaluation ────────────────────────────────────────────────────
eval-layer1:
	.venv/bin/pytest tests/test_evaluators.py -x --tb=short -q
