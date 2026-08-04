# Agent graph scope

Read `docs/features/stage4-orchestration/FEATURE.md`, `docs/domain/orchestration.md`, and the matched business rules before changing this package.

- `stage4_graph.py` is the production graph. Preserve checkpoint-safe HITL resume, explicit routing, component gates, and typed state writes.
- Parallel workers write unique component keys; `TravelAgentState` reducers own fan-in semantics. Verify every node, route, reducer, and terminal edge affected by a graph change.
- Readiness precedes discovery when required. Hotels fan out from exact `TripSkeleton` stays. Budget and itinerary consume validated selections/evidence.
- Keep static prompt text in `prompts/agent_prompt.py`; callers pass only dynamic context.
- Use `ComponentResult` statuses for partial, input-required, external-blocked, failed, and stale outcomes. Never hide them in fluent prose.

Validate with focused graph/node/API tests and Ruff. Do not instantiate live LLMs or providers during default validation.
