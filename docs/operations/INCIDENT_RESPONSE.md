---
id: operations-incident-response
doc_type: operations
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/**, frontend/**, infra/**, .github/workflows/**]
load_when: [incident, security, outage, rollback]
source_paths: [SECURITY.md, docs/operations/RUNBOOK.md, .github/workflows/deploy-prod.yml]
---

# Incident response

## Severity guide

- **SEV-1:** credential/data exposure, unsafe safety/entry advice at scale, destructive deployment, complete production outage, uncontrolled spend.
- **SEV-2:** major capability unavailable, HITL bypass/resume loss, cross-user/session risk, severe provider/cost degradation.
- **SEV-3:** bounded partial failure, non-critical provider issue, isolated stale/render defect.

## Response

1. Declare owner/severity/time and preserve sanitized evidence.
2. Contain: revoke/rotate exposed credentials, disable affected path/provider, restrict traffic/replicas, or roll back revision under authorized control.
3. Assess affected sessions/artifacts/data and whether users need notification.
4. Eradicate root cause with tests/rules/traceability update.
5. Recover through reviewed immutable release and bounded verification.
6. Write a blameless record with timeline, cause, control gap, impact, cost, and owners/dates for actions.

## AI-specific controls

Unsafe or unsupported critical readiness content fails closed. Suspected prompt/evidence injection isolates the source and preserves normalized provenance. Model-quality incidents use exact dataset/trace evidence; provider outages remain separate. Uncontrolled live evaluation/deployment is stopped before diagnosis continues.

## Secrets

Never paste credentials into tickets/chat/logs. Rotate in the owning provider and update secret references; verify old credential invalidation without displaying values.
