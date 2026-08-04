---
id: adr-0008
doc_type: adr
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/api/checkpointing.py, src/api/main.py, Dockerfile, infra/**]
load_when: [checkpoint, persistence, thread, resume, scaling]
source_paths: [src/api/checkpointing.py, src/api/main.py, tests/test_checkpointing.py]
---

# ADR-0008: PostgreSQL checkpoints for durable threads

**ADR status:** Accepted — 2026-08-04

## Context

The API previously compiled each graph with `InMemorySaver` while the container started four workers and Azure allowed several replicas. Session history and HITL resume therefore depended on which process received the next request, and every restart discarded all threads.

## Decision

Production LangGraph checkpoints use `AsyncPostgresSaver` for the complete FastAPI lifespan. The API initializes the checkpoint schema at startup, compiles the graph with that saver, and closes the pool at shutdown. `thread_id` remains the conversation identity used by chat, history, streaming, and typed resume.

Development may explicitly use memory checkpoints. Production defaults to PostgreSQL and fails startup when the database URL is absent or memory is selected. Connection strings remain secret values and are never returned by readiness or written to logs.

Local Compose exercises the PostgreSQL path with persistent storage. Azure Bicep accepts an externally managed PostgreSQL connection string as a secure parameter. API concurrency stays at one worker and one replica until the distributed rate limiter and multi-instance release checks are complete.

## Consequences

- Conversations and interrupts can survive worker replacement and process restarts.
- Database availability, schema permissions, backups, retention, TLS, and recovery become explicit production prerequisites.
- Startup fails closed when durable production state is unavailable.
- PostgreSQL is not long-term cross-thread user memory; it stores graph checkpoints only.

## Alternatives considered

- Keep memory and rely on sticky sessions: rejected because restarts still lose state and affinity is not a durability guarantee.
- SQLite on a shared volume: rejected because multi-process/container concurrency over a network filesystem is unsafe.
- The current Redis container: rejected for checkpoints because it has no durable managed storage or recovery contract; it remains the target for distributed rate limiting.

## Evidence

Implementation is in `src/api/checkpointing.py` and the FastAPI lifespan in `src/api/main.py`. Hermetic configuration, lifecycle, and second-instance resume evidence is in `tests/test_checkpointing.py`.
