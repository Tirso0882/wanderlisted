---
id: operations-docker-guide
doc_type: operations
status: active
authority: descriptive
owners: [travel-platform]
applies_to: [Dockerfile, docker-compose.yml, .dockerignore]
load_when: [docker, container, local-stack, image]
source_paths: [Dockerfile, docker-compose.yml, .dockerignore]
---

# Docker production guide

## Image

The root multi-stage Python 3.12 Dockerfile installs runtime requirements, copies application/config/data, creates a non-root user, exposes port 8000, checks `/api/v1/health`, and starts Uvicorn. Verify the current file rather than copying generic Docker examples.

## Hermetic local checks

```bash
docker build -t wanderlisted:local .
docker run --rm -p 8000:8000 --env-file .env wanderlisted:local
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:8000/api/v1/ready
```

Running the container can initialize model/provider configuration; use fake/test configuration for startup checks and do not send chat requests without live-call approval.

## Compose

`docker compose up --build` starts API, Redis 7, and Postgres 16. The API depends on Redis and mounts a logs volume; Postgres has local development credentials and a volume. Current Compose presence does not prove API use of Redis/Postgres for checkpoint persistence.

Use `docker compose down` for normal shutdown. Removing volumes is destructive and requires explicit intent because it erases local Postgres data.

## Production image rules

- Build from a reviewed commit; tag with immutable SHA/digest.
- Keep `.env`, Git metadata, caches, personal files, outputs, docs, and tests out of the runtime context as declared by `.dockerignore`.
- Run non-root, keep health/readiness distinct, and set resource/time limits at the platform.
- Inject secrets at runtime, never via build args/layers.
- Scan image/dependencies and record digest before promotion.

## Validation limits

Image build and probes prove packaging/startup only. Provider connectivity, graph persistence, concurrency, and complete user journeys require separate test-environment evidence.
