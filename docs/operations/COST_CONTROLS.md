---
id: operations-cost-controls
doc_type: operations
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/**, src/tools/**, edd/**, infra/**]
load_when: [cost, budget, live-evaluation, provider, scaling]
source_paths: [src/agent/concurrency.py, src/readiness/planning.py, edd, infra/main.bicep]
---

# Cost controls

## Runtime

- Route focused requests only to necessary capabilities.
- Enforce readiness query budgets, bounded retries/timeouts, per-tier semaphores, provider result limits, and cache TTL/size.
- Reuse checkpointed preflight and validated exchange-rate evidence; avoid repeated provider work on HITL resume.
- Separate provider/model/platform usage by capability/environment and alert on anomaly.
- Scale test to zero only where startup/session behavior permits; production minimums and durable state are reliability decisions, not cost-only choices.

## Development and evaluation

Hermetic fixtures and cached fingerprint-matched trajectories are default. Before live capture/judge/provider/deploy: disclose cases, calls per case, total model calls, expected tokens/credits, hard maximum budget, cache behavior, and stop condition; obtain explicit approval. `EDD_REFRESH=1` is always approval-gated.

## Stop controls

Abort/contain on unexpected fan-out, cache miss expansion, quota/rate-limit spike, cost above ceiling, wrong environment, or missing usage visibility. Do not continue merely to complete a benchmark.

## Reporting

Report actual cases/calls/tokens/credits/cost when available, cache hits, excluded external failures, and ceiling adherence. Never infer cost from stale model-price tables; use current provider pricing for an approved run.
