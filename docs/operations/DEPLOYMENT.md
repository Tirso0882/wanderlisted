---
id: operations-deployment
doc_type: operations
status: active
authority: normative
owners: [travel-platform]
applies_to: [infra/**, .github/workflows/deploy-*.yml]
load_when: [deployment, azure, container-apps, release]
source_paths: [infra/main.bicep, infra/setup.sh, .github/workflows/deploy-test.yml, .github/workflows/deploy-prod.yml]
---

# Deployment

## Current target

Azure Container Apps hosts API, frontend, and internal Redis in separate test/production managed environments declared by Bicep. ACR stores images and Log Analytics receives platform logs. GitHub Actions authenticates with Azure OIDC.

## Mutating-action boundary

Every `az`, `gh`, workflow dispatch, image push/import, release publication, secret/environment update, and deployment changes external state. Agents must not execute these actions without explicit user approval naming the environment. Redact identifiers only when needed; never print secret values.

## One-time setup

`infra/setup.sh` creates the resource group, Entra application/service principal, federated credentials, GitHub Azure identity secrets, and both base environments. It grants Contributor on the resource group and mutates GitHub/Azure; review every command and target before an authorized run.

## Test deployment

Push to `main` or manual dispatch triggers `deploy-test.yml`: OIDC login, API/frontend image build and ACR push using the commit SHA, Bicep deployment with test parameters, then Container App secret and environment-variable updates. The GitHub `test` environment controls authorization.

## Production deployment

Release publication or manual dispatch triggers `deploy-prod.yml` under the protected `production` environment. Confirm the requested API/frontend image tag exists and matches the approved commit before deployment; the current workflow's release-tag import/tag behavior must be reviewed rather than assumed correct.

## Required gates

1. CI and documentation contracts pass on the exact commit.
2. Image digest/tag provenance is recorded.
3. Bicep change/what-if is reviewed for the named resource group.
4. Required secret names/variables and frontend/API URLs are present without exposing values.
5. Test environment health/readiness and approved smoke checks pass.
6. Production reviewer approves release and rollback tag.
7. Post-deploy probes, logs, error/latency/cost signals are checked.

## Rollback

Redeploy a previously verified immutable image tag/digest through the production workflow or Container App revision control under explicit approval. Do not rebuild source during rollback. Revert configuration separately when it caused the incident and record both revisions.

## Known current risks

See [`DEPLOYMENT_VIEW.md`](../architecture/DEPLOYMENT_VIEW.md): ACR admin credentials, wildcard platform CORS, post-Bicep secret injection, non-shared in-process rate limiting, and unproven durable checkpoint use require hardening/verification before horizontal production claims.
