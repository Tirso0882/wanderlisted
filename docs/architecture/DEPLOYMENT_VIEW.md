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

The Python 3.12 multi-stage Docker image runs the FastAPI service on port 8000. Docker Compose adds Redis and Postgres plus persistent local volumes; its API health check calls `/api/v1/health`. Their presence does not prove the application is using them for durable checkpoints or rate limiting.

## Azure view

`infra/main.bicep` declares one environment-specific Log Analytics workspace, shared ACR name, Azure Container Apps environment, internal Redis container app, external API container app, and external frontend container app. Test can scale API/frontend to zero; production keeps at least one replica. Parameter files target `eastus2` unless changed.

GitHub Actions uses OIDC to Azure. The test workflow builds/pushes API and frontend images, deploys Bicep, then configures provider secrets/environment variables. The production workflow is release/manual and uses the protected `production` environment.

## Trust and persistence gaps

- Bicep currently enables ACR admin credentials and uses them as Container App registry secrets.
- API ingress Bicep allows wildcard CORS; runtime FastAPI has a narrower configurable policy, but the platform layer remains broad.
- Provider secrets are injected by workflows after infrastructure deployment rather than declared in Bicep.
- Redis is single-replica and its application persistence role must be verified.
- The in-process rate limiter is not horizontally shared.
- Production image-tag existence must be verified before release deployment.

These are documented current-state risks, not claims that production hardening is complete.

## Deployment evidence

CI, Bicep static validation, image build, test-environment health/readiness, logs, and an approved smoke journey are separate gates. A successful image build does not prove provider connectivity or checkpoint durability. See the release checklist and runbook.
