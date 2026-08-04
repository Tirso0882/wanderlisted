# Wanderlisted agent contract

## Purpose and authority

Wanderlisted is a typed LangGraph travel-planning system with provider-backed discovery, fail-closed readiness checks, deterministic budget/itinerary stages, human approval gates, and handbook delivery.

Use sources in this order when they disagree: the current user task; the nearest `AGENTS.md`; this file; active normative documents in `docs/`; current implementation; tests and EDD evidence; optional or superseded references. Documentation states approved intent, code states current behavior, and tests/EDD state demonstrated behavior. Report conflicts instead of silently choosing a convenient source.

## Mandatory read order

Before editing:

1. Inspect `git status --short` and the relevant diff. Never overwrite unrelated or uncommitted work.
2. Read this file and every nearer `AGENTS.md` that applies to the target path.
3. Read `docs/agent-map.yaml` and use its path/trigger routing and byte budgets.
4. Read an active task packet under `docs/tasks/active/` when one matches.
5. Read only the matched Critical, then Recommended documents.
6. Inspect focused tests and source code. Load Optional documents only to resolve a specific uncertainty.

Use `.agents/skills/<name>/SKILL.md` when its description matches the task. Keep reusable workflow detail there, not in this file.

## Repository boundaries

- The production graph is `src/agent/stage4_graph.py`; `src/agent/state.py` owns merge semantics and state reducers.
- Structured intake is the canonical request boundary. Readiness runs before dependent discovery when safety or readiness context is required. Inventory/discovery components feed deterministic trip skeleton, selection, transportation, budget, itinerary, review, and delivery stages.
- Package ownership is documented in `docs/domain/CONTEXT_MAP.md`. Do not move facts or decisions across owners without updating contracts and traceability.
- Static runtime prompts remain in `src/agent/prompts/agent_prompt.py` and are re-exported from that package. Callers may interpolate dynamic state; they must not create competing static prompts.
- Preserve typed artifacts and evidence IDs across API, graph, frontend, and renderer boundaries. Do not replace structured outcomes with prose parsing.
- Never fabricate provider availability, prices, citations, routes, opening hours, or safety facts.

## Safety, cost, and validation

Default to hermetic checks. Before any provider call, live EDD capture, paid judge/model run, Azure action, or deployment, disclose expected external calls/cost and obtain explicit approval. Never set `EDD_REFRESH=1` without that approval. Classify provider/infra failure separately from model quality.

Use repository executables:

```bash
.venv/bin/pytest <focused-tests> -q
.venv/bin/ruff check <touched-python-paths>
.venv/bin/ruff format --check <touched-python-paths>
make docs-check
```

Do not weaken TLS, safety gates, validation, or tests to make a check pass. Do not commit, push, deploy, or mutate external systems unless the user explicitly requests it.

## Definition of done

- The requested behavior and all affected cross-layer contracts are implemented.
- Focused hermetic tests pass; broader checks are proportional to risk.
- Documentation, business-rule traceability, and examples match the implementation.
- No unrelated diff changed and no secret, generated output, personal file, or cache was added.
- The final report distinguishes completed checks, skipped live checks, assumptions, and remaining risk.

## Review rules

Review behavior and evidence before style. Trace inputs through routing, reducers, typed models, API consumers, frontend rendering, tests, and EDD. Treat missing evidence, stale fingerprints, unsafe fallbacks, uncontrolled fan-out, and hidden external spend as blocking issues.
