# Architecture decision records

Accepted ADR content is immutable. When a decision changes, add a numbered ADR with `supersedes` metadata; do not rewrite the accepted record. `docs/check_docs.py` validates numbering, status, and supersession targets.

| ADR | Decision | Lifecycle |
|---|---|---|
| [0001](0001-multi-agent-supervisor-parallel-fanout.md) | Supervisor and parallel `Send` fan-out | Accepted |
| [0002](0002-responses-api-for-reasoning-models.md) | Responses API for configured reasoning deployments | Accepted; verify current provider behavior |
| [0003](0003-custom-reducers-for-parallel-state-merge.md) | Reducers for parallel state merge | Accepted |
| [0004](0004-tiered-models-and-semaphore-concurrency.md) | Tiered models and concurrency guards | Accepted; numbers live in code |
| [0005](0005-two-tier-rag-chunking-strategy.md) | Destination RAG chunking | Superseded by 0006 |
| [0006](0006-tavily-only-destination-pipeline.md) | Bounded live destination retrieval | Ownership portions superseded by 0007 |
| [0007](0007-travel-readiness-ownership-and-fail-closed-preflight.md) | Readiness ownership and fail-closed preflight | Accepted |

Use [`docs/_templates/ADR.md`](../_templates/ADR.md) for new decisions.
