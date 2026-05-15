# Docker Production Guide for Agentic AI Projects

A comprehensive guide to containerizing, testing, and deploying production-level
multi-agent AI applications — based on the Wanderlisted architecture.

---

## Table of Contents

1. [Prerequisites & Installation](#1-prerequisites--installation)
2. [Local Testing Commands (Quick Reference)](#2-local-testing-commands)
3. [Architecture Overview](#3-architecture-overview)
4. [Dockerfile Best Practices](#4-dockerfile-best-practices)
5. [Docker Compose for Local Development](#5-docker-compose-for-local-development)
6. [CI/CD Pipeline](#6-cicd-pipeline)
7. [Health Checks and Observability](#7-health-checks-and-observability)
8. [Secrets Management](#8-secrets-management)
9. [Moving to Production with Kubernetes](#9-moving-to-production-with-kubernetes)
10. [Production Checklist](#10-production-checklist)

---

## 1. Prerequisites & Installation

Install these tools before working with the project's container stack.

### Docker Engine

| Platform | Install method |
|----------|---------------|
| **macOS** | [Docker Desktop](https://docs.docker.com/desktop/install/mac-install/) (includes Docker Engine + Compose + BuildKit) |
| **Windows** | [Docker Desktop](https://docs.docker.com/desktop/install/windows-install/) (WSL 2 backend recommended) |
| **Ubuntu/Debian** | `sudo apt-get update && sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin` ([official docs](https://docs.docker.com/engine/install/ubuntu/)) |
| **Fedora/RHEL** | `sudo dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin` |

After installing, verify:

```bash
docker --version          # Docker 24+
docker compose version    # Compose V2 (built-in plugin, NOT docker-compose v1)
```

> **Linux post-install**: add your user to the `docker` group so you don't need `sudo`:
> ```bash
> sudo usermod -aG docker $USER && newgrp docker
> ```

### Docker Compose

Compose V2 ships as a Docker CLI plugin (`docker compose` — no hyphen). It's
included with Docker Desktop on macOS/Windows. On Linux it's installed as
`docker-compose-plugin` (see table above).

Verify:

```bash
docker compose version    # v2.x.x
```

If you still have the legacy `docker-compose` (v1), uninstall it and use the
plugin instead — v1 is EOL.

### kubectl (Kubernetes CLI)

| Platform | Install method |
|----------|---------------|
| **macOS** | `brew install kubectl` |
| **Windows** | `choco install kubernetes-cli` or `winget install Kubernetes.kubectl` |
| **Linux** | `curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && sudo install kubectl /usr/local/bin/` |

Verify:

```bash
kubectl version --client    # v1.28+
```

### Helm (Kubernetes package manager)

```bash
# macOS
brew install helm

# Linux / WSL
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

Verify:

```bash
helm version    # v3.x.x
```

### Local Kubernetes cluster (for testing)

You only need **one** of these for local K8s development:

| Tool | Best for | Install |
|------|----------|--------|
| **Docker Desktop K8s** | Simplest — enable in Docker Desktop → Settings → Kubernetes | Built-in toggle |
| **minikube** | Feature-rich, multi-node | `brew install minikube` / [docs](https://minikube.sigs.k8s.io/docs/start/) |
| **kind** | CI-friendly, lightweight | `brew install kind` / `go install sigs.k8s.io/kind@latest` |

Verify your cluster is running:

```bash
kubectl cluster-info
kubectl get nodes
```

### Optional tools

| Tool | Purpose | Install |
|------|---------|--------|
| **k9s** | Terminal UI for Kubernetes | `brew install k9s` |
| **Lens** | Desktop Kubernetes IDE | [lens.dev](https://k8slens.dev/) |
| **Trivy** | Container image vulnerability scanner | `brew install trivy` |
| **dive** | Inspect Docker image layers | `brew install dive` |

---

## 2. Local Testing Commands

Run these **in order** to fully validate Docker before pushing or merging.

### Step 1: Verify prerequisites

```bash
docker --version          # Docker 24+
docker compose version    # Compose V2 (built-in)
```

### Step 2: Build the image (mirrors CI)

```bash
# Build the production image
docker build -t wanderlisted:local .

# Verify it's built
docker images wanderlisted
```

If the build fails, the Dockerfile or requirements.txt has issues — fix before pushing.

### Step 3: Run the standalone container

```bash
# Run with your .env file
docker run --rm -p 8000:8000 --env-file .env wanderlisted:local

# Or run detached
docker run -d --name wanderlisted-test -p 8000:8000 --env-file .env wanderlisted:local
```

### Step 4: Verify the API responds

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Readiness check (verifies graph is initialized)
curl http://localhost:8000/api/v1/ready

# Quick smoke test
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "test-1"}'
```

### Step 5: Stop the standalone container

```bash
docker stop wanderlisted-test && docker rm wanderlisted-test
# or if running with --rm, just Ctrl+C
```

### Step 6: Test with Docker Compose (full stack)

```bash
# Build and start all services (API + Redis + Postgres)
docker compose up --build -d

# Check all services are running
docker compose ps

# View live logs
docker compose logs -f api

# Verify API through compose
curl http://localhost:8000/healthz
```

### Step 7: Test container internals

```bash
# Shell into the running container
docker compose exec api sh

# Check the non-root user is active
whoami                    # should print "app"

# Verify Python packages are installed
python -c "import langchain_core; print(langchain_core.__version__)"

# Check the knowledge base is mounted
ls /app/knowledge_base/destination_guides/
```

### Step 8: Stop everything and clean up

```bash
# Stop and remove containers
docker compose down

# Stop, remove containers AND volumes (wipes Postgres data)
docker compose down -v

# Remove dangling images
docker image prune -f
```

### Step 9: Validate image tag naming (matches CI)

```bash
# This is what CI generates — test it locally
IMAGE="ghcr.io/$(echo 'YOUR_GITHUB_USER/YOUR_REPO' | tr '[:upper:]' '[:lower:]')"
docker tag wanderlisted:local "$IMAGE:latest"
docker tag wanderlisted:local "$IMAGE:$(git rev-parse --short HEAD)"
echo "Tags created: $IMAGE:latest, $IMAGE:$(git rev-parse --short HEAD)"
```

### Step 10: (Optional) Push to GHCR manually

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u YOUR_USERNAME --password-stdin
docker push "$IMAGE:latest"
```

### All-in-one (Makefile shortcuts)

```bash
make docker-build    # Step 2
make docker-up       # Step 6
make docker-down     # Step 8
```

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  CI Pipeline (GitHub Actions)                               │
│                                                             │
│  PR:   lint → test → eval → docker-build (dry-run)         │
│  main: lint → test → eval → build-and-push (GHCR)          │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Docker Compose (local dev / staging)                       │
│                                                             │
│  ┌─────────┐   ┌─────────┐   ┌────────────┐               │
│  │   API   │──▶│  Redis  │   │  Postgres  │               │
│  │ :8000   │   │ :6379   │   │  :5432     │               │
│  │ 4 workers│   │ cache   │   │  checkpoints│              │
│  └─────────┘   └─────────┘   └────────────┘               │
│       │                                                     │
│       ├── LangGraph supervisor (multi-agent orchestration)  │
│       ├── 8 specialized agents (parallel + sequential)      │
│       ├── HITL interrupt gates (safety, budget, review)     │
│       └── External APIs (Duffel, Hotelbeds, Google Maps, Tavily, etc.)│
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Dockerfile Best Practices

### Multi-stage build (keep images small)

```dockerfile
# Stage 1: Install dependencies into a prefix (not system-wide)
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Copy only what's needed to run
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ src/
COPY config/ config/
# ... only production code, no tests/docs/scripts
```

**Why**: The builder stage has pip, compilers, and build artifacts. The runtime
stage only has the installed packages and your code. Typical savings: 60–80% image size.

### Non-root user (security)

```dockerfile
RUN addgroup --system app && adduser --system --ingroup app app
USER app
```

**Why**: If an attacker escapes the application, they land as an unprivileged user,
not root. Required by most container security scanners (Trivy, Snyk, etc.).

### Environment variables

```dockerfile
ENV PYTHONUNBUFFERED=1           # Real-time log output (critical for agents)
ENV PYTHONDONTWRITEBYTECODE=1    # Don't litter .pyc files in the container
```

### Production ASGI server

```dockerfile
CMD ["uvicorn", "src.api.main:app",
     "--host", "0.0.0.0",
     "--port", "8000",
     "--workers", "4",                    # Multi-process for CPU-bound prep
     "--timeout-graceful-shutdown", "30",  # Let in-flight agent runs finish
     "--limit-concurrency", "100"]         # Backpressure under load
```

**Why agents need special attention**:
- `--workers 4`: Agent pipelines are I/O-heavy (API calls), so multiple workers
  maximize throughput while waiting on LLM responses.
- `--timeout-graceful-shutdown 30`: A supervisor→8-agent pipeline can take 20+ seconds.
  Don't kill it mid-run during deploys.
- `--limit-concurrency 100`: Prevents OOM if too many concurrent agent runs hit the
  LLM APIs simultaneously.

### .dockerignore (keep builds fast and images clean)

```dockerignore
.venv/
__pycache__/
*.pyc
.env
.env.*
.git/
.github/
tests/
scripts/
docs/
logs/
outputs/
htmlcov/
.coverage
.pytest_cache/
.ruff_cache/
*.md
!knowledge_base/**/*.md    # Keep RAG guides, exclude other markdown
```

---

## 5. Docker Compose for Local Development

### Minimum viable stack for agentic projects

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env                           # All API keys live here
    volumes:
      - ./knowledge_base:/app/knowledge_base # Hot-reload RAG guides
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: wanderlisted
      POSTGRES_USER: wanderlisted
      POSTGRES_PASSWORD: localdev           # Fine for local dev ONLY
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data     # Persist across restarts

volumes:
  pgdata:
```

### When to add each service

| Service | When you need it |
|---------|-----------------|
| **Redis** | LangGraph checkpointer (conversation memory), rate limiting, caching LLM responses |
| **Postgres** | Durable checkpoints (survives restarts), user sessions, feedback storage |
| **Qdrant/Chroma** | Self-hosted vector DB (alternative to Pinecone cloud) |
| **LangSmith** | Tracing — use cloud version, no container needed |

---

## 6. CI/CD Pipeline

### PR phase: catch issues early

```yaml
# Runs on every pull request
docker-build:
  needs: [lint]
  if: github.event_name == 'pull_request'
  steps:
    - uses: actions/checkout@v4
    - uses: docker/build-push-action@v5
      with:
        push: false                          # Build only, don't push
        tags: myapp:pr-${{ github.event.pull_request.number }}
```

**Why**: Catches broken Dockerfiles, missing COPY paths, and bad tags BEFORE merge.
The previous build-and-push failure (uppercase tag) would have been caught here.

### Merge phase: build and push

```yaml
# Runs only on push to main (after merge)
build-and-push:
  needs: [lint, test, eval-layer1]
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  steps:
    - uses: actions/checkout@v4
    - name: Lowercase image name
      run: echo "IMAGE_NAME=$(echo '${{ github.repository }}' | tr '[:upper:]' '[:lower:]')" >> "$GITHUB_ENV"
    - uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    - uses: docker/build-push-action@v5
      with:
        push: true
        tags: |
          ghcr.io/${{ env.IMAGE_NAME }}:latest
          ghcr.io/${{ env.IMAGE_NAME }}:${{ github.sha }}
```

### Key lessons learned

1. **Always lowercase image tags** — `github.repository` can contain uppercase
2. **Always dry-run Docker on PRs** — the push-only-on-main pattern has a blind spot
3. **Gate pushes on ALL checks** — `needs: [lint, test, eval]` prevents shipping broken code
4. **Tag with both `latest` and `sha`** — `latest` for convenience, `sha` for rollbacks

---

## 7. Health Checks and Observability

### Implement two endpoints

```python
# /healthz — is the process alive?
@app.get("/healthz")
async def liveness():
    return {"status": "ok"}

# /readyz — is the app ready to serve traffic?
@app.get("/readyz")
async def readiness():
    # Check graph is initialized, DB is connected, etc.
    graph = get_graph()
    if graph is None:
        raise HTTPException(503, "Graph not initialized")
    return {"status": "ready"}
```

### Docker Compose healthcheck

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 15s    # Give agent graph time to initialize
```

### What to monitor for agentic apps

| Metric | Why |
|--------|-----|
| Agent run duration | Detect slow LLM providers or prompt regressions |
| Token usage per run | Cost control — one bad prompt can 10x your bill |
| HITL interrupt rate | High rates mean the safety/budget gates fire too often |
| Error rate by agent | Isolate which specialist agent is failing |
| Concurrent runs | Prevent OOM from too many parallel LLM calls |

---

## 8. Secrets Management

### Local development

```bash
# Copy the example and fill in real keys
cp .env.example .env
# .env is in .gitignore and .dockerignore — never committed
```

### CI (GitHub Actions)

```yaml
env:
  # Fake keys for tests — tools are mocked with respx
  DUFFEL_ACCESS_TOKEN: "duffel_test_fake"
  GOOGLE_MAPS_API_KEY: "test"
  # Real keys only for integration tests (stored in GitHub Secrets)
  # accessed via ${{ secrets.DUFFEL_ACCESS_TOKEN }}
```

### Production

| Method | When |
|--------|------|
| **Environment variables** | Simple deploys (docker run --env-file) |
| **Docker/Swarm secrets** | Self-hosted Docker |
| **Azure Key Vault / AWS Secrets Manager** | Cloud production |
| **GitHub Actions secrets** | CI-only (never logged, masked in output) |

**Never**:
- Hardcode API keys in Dockerfiles or docker-compose.yml
- Commit `.env` files
- Use build-time `ARG` for secrets (they persist in image layers)

---

## 9. Moving to Production with Kubernetes

Docker Compose works for local dev and single-server staging, but production
agentic apps need orchestration: auto-scaling, rolling deploys, secret injection,
and self-healing. Kubernetes provides all of these.

### When to move from Compose to Kubernetes

| Compose is fine when… | Move to K8s when… |
|-----------------------|-------------------|
| Single server, low traffic | Multiple replicas needed for availability |
| Local dev / staging | Zero-downtime deploys required |
| Team of 1–3 | Multiple teams deploying independently |
| Simple restart policy | Auto-scaling based on queue depth or CPU |
| Secrets in `.env` files | Need vault-backed secret injection |

### Kubernetes manifests for an agentic app

#### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: wanderlisted
```

#### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wanderlisted-api
  namespace: wanderlisted
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 1
  selector:
    matchLabels:
      app: wanderlisted-api
  template:
    metadata:
      labels:
        app: wanderlisted-api
    spec:
      containers:
        - name: api
          image: ghcr.io/tirso0882/wanderlisted:latest
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: wanderlisted-secrets
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "2Gi"        # Agents can be memory-hungry
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          startupProbe:
            httpGet:
              path: /healthz
              port: 8000
            failureThreshold: 30
            periodSeconds: 2      # Give the graph up to 60s to initialize
```

**Agentic-specific settings**:
- **Memory limit 2Gi**: LLM client libraries, embedding models, and parallel agent
  state can spike memory. Monitor and adjust.
- **Startup probe**: The LangGraph supervisor graph takes several seconds to compile.
  A startup probe prevents liveness kills during init.
- **Rolling update**: `maxUnavailable: 1` ensures at least 2 of 3 replicas serve
  traffic during deploys.

#### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: wanderlisted-api
  namespace: wanderlisted
spec:
  selector:
    app: wanderlisted-api
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

#### Ingress (expose to the internet)

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: wanderlisted-ingress
  namespace: wanderlisted
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.wanderlisted.com
      secretName: wanderlisted-tls
  rules:
    - host: api.wanderlisted.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: wanderlisted-api
                port:
                  number: 80
```

#### Secrets

```bash
# Create secrets from your .env file
kubectl create secret generic wanderlisted-secrets \\
  --from-env-file=.env \\
  --namespace=wanderlisted
```

For production, use a secrets operator (External Secrets, Azure Key Vault CSI, etc.)
instead of `kubectl create secret`.

#### HorizontalPodAutoscaler

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: wanderlisted-api
  namespace: wanderlisted
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: wanderlisted-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Redis and Postgres on Kubernetes

For **development/staging**, use Helm charts:

```bash
# Redis
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install redis bitnami/redis --namespace wanderlisted \\
  --set architecture=standalone \\
  --set auth.enabled=false

# Postgres
helm install postgres bitnami/postgresql --namespace wanderlisted \\
  --set auth.postgresPassword=<strong-password> \\
  --set auth.database=wanderlisted
```

For **production**, use managed services (Azure Database for PostgreSQL, Amazon RDS,
Azure Cache for Redis, ElastiCache) and connect from the cluster via private endpoints.

### Deploy to a local cluster (kind / minikube)

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Load the local image into the cluster
# kind:
kind load docker-image wanderlisted:local
# minikube:
minikube image load wanderlisted:local

# 3. Update deployment image to "wanderlisted:local" and set imagePullPolicy: Never

# 4. Apply manifests
kubectl apply -f k8s/

# 5. Verify
kubectl get pods -n wanderlisted
kubectl logs -n wanderlisted -l app=wanderlisted-api -f

# 6. Port-forward to test locally
kubectl port-forward -n wanderlisted svc/wanderlisted-api 8000:80
curl http://localhost:8000/healthz
```

### Managed Kubernetes options

| Provider | Service | Best for |
|----------|---------|----------|
| **Azure** | AKS (Azure Kubernetes Service) | Integrated with Azure AI, Key Vault, and managed Postgres |
| **AWS** | EKS (Elastic Kubernetes Service) | Deep AWS ecosystem integration |
| **GCP** | GKE (Google Kubernetes Engine) | Autopilot mode for zero node management |
| **DigitalOcean** | DOKS | Budget-friendly, simpler K8s |

---

## 10. Production Checklist

### Before first deploy

- [ ] Multi-stage Dockerfile (builder → runtime)
- [ ] Non-root user in container
- [ ] `.dockerignore` excludes tests, docs, .env, .git
- [ ] `PYTHONUNBUFFERED=1` for real-time logs
- [ ] Health endpoints (`/healthz`, `/readyz`)
- [ ] Graceful shutdown timeout ≥ max agent run duration
- [ ] Concurrency limit to prevent OOM under load
- [ ] `.env.example` committed (real `.env` in .gitignore)

### CI pipeline

- [ ] Docker dry-run build on PRs (`push: false`)
- [ ] Docker push on main only, gated on all checks
- [ ] Image tags lowercased (OCI requirement)
- [ ] Both `:latest` and `:sha` tags pushed
- [ ] Test env vars are fake (tools mocked, no real API calls)

### Per-deploy validation

- [ ] `docker build` succeeds locally
- [ ] `docker compose up` starts all services
- [ ] `curl /healthz` returns 200
- [ ] `curl /readyz` returns 200
- [ ] Smoke test a chat message end-to-end
- [ ] Check logs for import errors or missing env vars

### Kubernetes (when applicable)

- [ ] Deployment with resource requests and limits
- [ ] Liveness, readiness, and startup probes configured
- [ ] HorizontalPodAutoscaler targeting CPU or custom metrics
- [ ] Secrets managed via External Secrets / Key Vault CSI (not `kubectl create secret`)
- [ ] Rolling update strategy with `maxUnavailable: 1`
- [ ] Ingress with TLS (cert-manager + Let's Encrypt)
- [ ] Redis / Postgres via managed services (not in-cluster for production)
- [ ] `kubectl apply -f k8s/` tested against a local cluster (kind / minikube) before deploying to cloud

### Agentic-specific concerns

- [ ] Agent timeout > LLM response time × number of sequential agents
- [ ] Rate limiter prevents thundering herd on LLM APIs
- [ ] HITL interrupts work correctly (test resume flow)
- [ ] LangSmith tracing enabled (set `LANGCHAIN_TRACING_V2=true`)
- [ ] Checkpointer backend configured (Redis or Postgres, not in-memory)
- [ ] Knowledge base (RAG vectors) accessible from container
- [ ] Error in one agent doesn't crash the entire pipeline
