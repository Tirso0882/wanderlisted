---
id: architecture-deployment-view
doc_type: architecture
status: active
authority: descriptive
owners: [travel-platform]
applies_to: [Dockerfile, docker-compose.yml, infra/**, .github/workflows/**]
load_when: [deployment, infrastructure, docker, azure, operations]
source_paths: [Dockerfile, docker-compose.yml, infra/main.bicep, .github/workflows/deploy-test.yml, .github/workflows/deploy-prod.yml]
---

# Deployment view

## Local/container view

The Python 3.12 multi-stage Docker image installs runtime packages from the frozen `uv.lock` and runs one FastAPI worker on port 8000. Docker Compose starts PostgreSQL with a persistent local volume and healthy Redis, configures the API for durable checkpoints plus shared rate limiting, and uses a stable development-only signing key so browser-owned threads survive an API restart. Its API health check calls `/api/v1/health`.

## Azure view

`infra/main.bicep` declares one environment-specific Log Analytics workspace, shared ACR name, Azure Container Apps environment, internal TCP-ingress Redis container app, external API container app, and external frontend container app. It accepts checkpoint/session-registry PostgreSQL URLs plus browser and Clerk secret material as secure parameters and exposes them only through Container Apps secret references. The repository does not provision the database or Clerk application itself. Non-secret parameters carry the bilingual UI flag, Clerk flag, issuer/JWKS/authorized-party settings, publishable key, and locale-specific consultation URLs. Both flags default off in test and production parameter files. The API uses Redis atomically across replicas and scales to two test or three production replicas. Parameter files target `eastus2` unless changed.

GitHub Actions uses OIDC to Azure. The test workflow builds API and frontend images once, labels/tags both with the exact commit SHA, resolves their ACR digests, and deploys those digests through Bicep. The frontend reads `API_URL` at request time through its server-side proxy, so environment configuration does not require rebuilding the image. The production workflow resolves the same SHA-tagged artifacts, verifies both digests exist, and deploys them unchanged under the protected `production` environment.

## Trust and persistence gaps

- Bicep currently enables ACR admin credentials and uses them as Container App registry secrets.
- Provider secrets are injected by workflows after infrastructure deployment rather than declared in Bicep.
- PostgreSQL service availability, backups, retention, TLS, and recovery are deployment prerequisites outside this Bicep template.
- The internal Redis app is single-replica and ephemeral. Requests fail closed when it is unavailable, but this is not a high-availability rate-limit service.
- Clerk configuration, OAuth credentials, webhook delivery, key rotation, and account-provider availability remain externally operated prerequisites. Guest chat continues when Clerk is deliberately disabled.
- Anonymous browser ownership alone is not cross-device identity; only explicitly claimed sessions enter account history. Edge abuse controls remain an operational requirement.
- A production release is blocked unless both exact commit-SHA tags resolve to valid ACR digests.

These are documented current-state risks, not claims that production hardening is complete.

## Deployment evidence

CI, Bicep static validation, image build, test-environment health/readiness, logs, and an approved smoke journey are separate gates. A successful image build does not prove provider connectivity or checkpoint durability. See the release checklist and runbook.
