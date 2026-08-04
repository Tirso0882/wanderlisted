# Graph change checklist

- Production factory: `create_multiagent_travel_graph` in `src/agent/stage4_graph.py`.
- State/reducers: `src/agent/state.py`.
- Canonical request: `src/models/trip_request.py` and intake node.
- Machine outcome: `src/models/component_result.py`.
- Agent names: `src/agent/agents/supervisor_agent.py`.
- Public execution/resume/streaming: `src/api/main.py`.
- Routing/node tests: `tests/test_nodes.py`, component gate tests, API contract tests.

Current high-level lifecycle: triage and intake; supervisor/readiness routing; discovery fan-out and component gates; exact trip skeleton and per-stay hotels; bounded itinerary selection and routes; deterministic budget and review; deterministic itinerary compilation and human review; handbook rendering. Focused requests may take shorter paths.

Never copy agent counts or node line numbers into durable instructions; derive them from the graph factory.
