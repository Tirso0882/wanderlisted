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

The graph checkpoint/session-registry database is an externally managed PostgreSQL service. Both GitHub environments must define masked `CHECKPOINT_DATABASE_URL` and `SESSION_SIGNING_KEY` secrets. Bicep places them in the API Container App as secret references; deployment rejects signing keys shorter than 32 bytes, and API startup fails closed if PostgreSQL, Redis, or the required deployed configuration is absent. Clerk server/owner/webhook secrets are separate masked inputs required only when the account feature is enabled.

## Bilingual account rollout

1. Deploy with `CHAT_UI_V2_ENABLED=false` and `CLERK_ENABLED=false`; verify the legacy path, API compatibility, persistence, and rollback.
2. Enable `CHAT_UI_V2_ENABLED` in test only; verify EN/PL UI, locale cookie, chat/typed results, mobile panes, HITL, partial outcomes, and external booking boundaries.
3. After Clerk application, email-code/Google, allowed-origin, JWKS, webhook, secret, and deletion checks are approved, enable `CLERK_ENABLED` in test; verify explicit claiming and cross-device history.
4. Configure and verify each locale's consultation URL independently; an empty URL must keep that CTA hidden.
5. Promote the same sequence to production through the protected environment. Never combine first-time UI, Clerk/history, and CTA enablement in one change.

## Mutating-action boundary

Every `az`, `gh`, workflow dispatch, image push/import, release publication, secret/environment update, and deployment changes external state. Agents must not execute these actions without explicit user approval naming the environment. Redact identifiers only when needed; never print secret values.

## One-time setup

`infra/setup.sh` creates the resource group, Entra application/service principal, federated credentials, GitHub Azure identity secrets, and both base environments. It grants Contributor on the resource group and mutates GitHub/Azure; review every command and target before an authorized run.

## Test deployment

Push to `main` or manual dispatch triggers `deploy-test.yml`: OIDC login, one API build and one frontend build tagged with the full commit SHA, ACR push, immutable digest resolution, Bicep deployment by digest, then Container App secret and environment-variable updates. `API_URL` is runtime-only, so no environment-specific frontend build exists. The GitHub `test` environment controls authorization.

## Production deployment

Release publication or manual dispatch triggers `deploy-prod.yml` under the protected `production` environment. Release events resolve the release tag to its exact commit; manual runs require the full 40-character SHA. The workflow refuses to continue unless both SHA-tagged test artifacts exist and resolve to valid digests, then Bicep deploys those exact digests without rebuilding or retagging.

## Required gates

1. CI and documentation contracts pass on the exact commit.
2. Both image digests resolve from the approved full commit SHA; no production rebuild or mutable release tag is used.
3. Bicep change/what-if is reviewed for the named resource group.
4. Required secret names/variables, rollout flags, authorized parties, and frontend/API URLs are present without exposing values.
5. `/ready` reports `checkpoint_backend=postgres` and `rate_limit_backend=redis`; approved owner-isolation, restart/resume, and shared-limit checks confirm the state boundary.
6. Test environment health/readiness and approved smoke checks pass.
7. Production reviewer approves release and rollback tag.
8. Post-deploy probes, logs, error/latency/cost signals are checked.

## Rollback

Redeploy a previously verified immutable image tag/digest through the production workflow or Container App revision control under explicit approval. Do not rebuild source during rollback. Revert configuration separately when it caused the incident and record both revisions.

## Known current risks

See [`DEPLOYMENT_VIEW.md`](../architecture/DEPLOYMENT_VIEW.md): ACR admin credentials, post-Bicep provider-secret injection, single-replica ephemeral Redis, externally operated Clerk/PostgreSQL, and guest-cookie lifecycle limits remain explicit hardening/ownership items.
