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
- [ ] Secret scan, lint/format, unit/coverage, deterministic EDD, docs contract, frontend/build, and image checks pass for the exact commit.
- [ ] No unexplained skipped critical test or `blocked_external` reliability gap.
- [ ] Image tag/digest exists in ACR and maps to the approved commit.
- [ ] Bicep/workflow diff and environment target are reviewed; no secret values appear.
- [ ] API/frontend contract compatibility and persistence/rate-limit implications are assessed.
- [ ] Expected provider/model traffic and cost impact are documented.

## Test environment

- [ ] Deployment succeeded; `/api/v1/health` and `/api/v1/ready` pass.
- [ ] Logs show no startup/import/config failure.
- [ ] Approved smoke cases cover changed capability, HITL/resume, partial/failure path, and frontend delivery as applicable.
- [ ] Metrics/error/cost signals remain within agreed bounds.

## Production and aftercare

- [ ] Protected production reviewer approved the exact tag and window.
- [ ] Rollback operator/tag and observation owner are assigned.
- [ ] Post-deploy probes and one approved bounded smoke pass.
- [ ] Error rate, latency, interrupts, provider failures, token/credit spend, and Container App revisions are observed.
- [ ] Release evidence and any follow-up are recorded without secrets.
