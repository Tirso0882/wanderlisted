---
id: operations-release-checklist
doc_type: operations
status: active
authority: normative
owners: [travel-platform]
applies_to: [.github/workflows/**, infra/**, Dockerfile]
load_when: [release, production, deployment-gate]
source_paths: [.github/workflows/ci.yml, .github/workflows/deploy-prod.yml, infra/main.bicep]
---

# Release checklist

## Before approval

- [ ] Scope, changelog, migrations/config/rule changes, and rollback tag are reviewed.
- [ ] Frozen Python/frontend installs, secret scan, full Python/EDD lint-format, unit/coverage, every hermetic Layer-1 gate, docs contract, frontend lint/type/unit/mocked-browser/build, and image checks pass for the exact commit.
- [ ] No unexplained skipped critical test or `blocked_external` reliability gap.
- [ ] Both SHA-tagged API/frontend artifacts exist in ACR, carry the approved commit revision, and resolve to the digests passed to Bicep.
- [ ] Bicep/workflow diff and environment target are reviewed; no secret values appear.
- [ ] API/frontend contract compatibility and persistence/rate-limit implications are assessed.
- [ ] `CHECKPOINT_DATABASE_URL` and a 32-byte-or-longer `SESSION_SIGNING_KEY` are present as masked environment secrets; database and Redis recovery ownership is confirmed.
- [ ] `CHAT_UI_V2_ENABLED` and `CLERK_ENABLED` are reviewed independently. When Clerk is enabled, issuer/JWKS/authorized parties and publishable/server/owner/webhook keys are complete and masked as appropriate.
- [ ] Expected provider/model traffic and cost impact are documented.

## Test environment

- [ ] Deployment succeeded; `/api/v1/health` and `/api/v1/ready` pass.
- [ ] `/api/v1/ready` reports PostgreSQL checkpoints and Redis rate limiting; restart/resume, cross-browser isolation, Redis-outage fail-closed, and multi-instance limit evidence pass.
- [ ] SSE failure/partial payloads retain completed evidence and expose structured status without leaking provider errors; bounded concurrent-limit evidence passes.
- [ ] Logs show no startup/import/config failure.
- [ ] Approved smoke cases cover changed capability, HITL/resume, partial/failure path, and frontend delivery as applicable.
- [ ] Bilingual rollout order is UI, then Clerk/history, then each configured consultation CTA; guest chat and flag rollback are checked between phases.
- [ ] Metrics/error/cost signals remain within agreed bounds.

## Production and aftercare

- [ ] Protected production reviewer approved the exact commit SHA, resolved digests, and window.
- [ ] Rollback operator/digests and observation owner are assigned.
- [ ] Post-deploy probes and one approved bounded smoke pass.
- [ ] Error rate, latency, interrupts, provider failures, token/credit spend, and Container App revisions are observed.
- [ ] Release evidence and any follow-up are recorded without secrets.
