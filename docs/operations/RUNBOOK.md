---
id: operations-runbook
doc_type: operations
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/api/main.py, infra/**, .github/workflows/**]
load_when: [runbook, outage, health, troubleshooting]
source_paths: [src/api/main.py, infra/main.bicep, .github/workflows/deploy-prod.yml]
---

# Operations runbook

## Triage order

1. Confirm environment, revision/image tag, deployment/config change time, and blast radius.
2. Check `/api/v1/health` (process) then `/api/v1/ready` (graph initialization).
3. Inspect Container App revision/events and sanitized API logs; never print secrets.
4. Classify startup/config, graph/checkpointer, provider auth/quota/network, model, application validation, frontend/API contract, or capacity.
5. Mitigate with traffic/revision rollback or provider-specific containment under explicit authorization.

## Common symptoms

| Symptom | First evidence | Safe action |
|---|---|---|
| Health fails | revision events/container logs | Roll back image/config; inspect import/start command |
| Health passes, ready fails | graph initialization/config error | Validate required non-secret env names and model factory |
| 401/403 provider | classified component error | Verify secret reference/clock/provider environment; do not expose credential |
| 429/timeouts | provider/component metrics | Reduce concurrency/traffic, respect retry bounds, preserve partial/blocked status |
| HITL cannot resume | thread/checkpoint and decision schema | Verify same session/checkpoint and typed gate payload |
| Stale handbook | expected vs stored fingerprint | Recompile itinerary; never bypass stale check |
| Cross-replica session loss | revision/replica and checkpointer evidence | Restrict scaling/route traffic until durable shared persistence is proven |

## Recovery verification

Recheck probes, affected typed path, error/latency/provider/cost signals, and one bounded approved user journey. Preserve incident timestamps, revision/digest, root cause, mitigation, and follow-up.
