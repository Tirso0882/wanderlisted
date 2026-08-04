---
id: operations-observability
doc_type: operations
status: active
authority: normative
owners: [travel-platform]
applies_to: [custom_logging/**, src/api/main.py, src/agent/**, infra/main.bicep]
load_when: [observability, logging, metrics, tracing]
source_paths: [custom_logging, src/api/main.py, src/agent/stage4_graph.py, infra/main.bicep]
---

# Observability

## Signals

- Request: request ID, environment/revision, endpoint, status, latency; session IDs should be minimized/hashed in analytics.
- Graph: node/route, component status, interrupt/resume, termination, fingerprint mismatch, fan-out count.
- Provider: provider/capability, call count, latency, retry, classified error, cache hit; no request secret/signed URL/raw sensitive query.
- Model: tier/provider/deployment identifier, latency, token/usage/cost where available, structured-output/tool-loop failure.
- Domain: coverage/partial/no-inventory/blocked/stale counts; budget/itinerary validation failures.
- Platform: replicas, restarts, CPU/memory, ingress errors, Log Analytics ingestion, ACR/revision/digest.

## Correlation

Correlate API request ID, session/thread ID, graph run ID, component, and platform revision without logging full traveler messages by default. Traces must redact credentials and minimize passport/accessibility/dietary/personal data.

The chat API reads its ID from the active `@traceable` LangSmith run. Non-streaming responses and the final SSE event expose that genuine UUID only when a run context exists; tracing-disabled requests expose `null`. Feedback accepts only a validated returned run UUID and is rate limited before any LangSmith mutation. A generated UUID that was not supplied to the trace is not a valid correlation ID.

## Alerts

Alert on health/readiness failure, sustained 5xx/latency, provider auth spikes, rate-limit/timeout spikes, graph failed/stale surge, resume failures, cost/token anomaly, and replica/session inconsistency. Thresholds require observed baselines; do not invent fixed production numbers in docs.

## Evidence retention

Retain only what incident/evaluation policy requires. EDD caches are not production telemetry. Human-reviewed traces promoted to datasets must be sanitized and versioned.
