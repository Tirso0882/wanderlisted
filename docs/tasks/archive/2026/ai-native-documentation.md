---
id: task-ai-native-documentation-archive
doc_type: task
status: archived
authority: descriptive
owners: [travel-platform]
applies_to: [AGENTS.md, .agents/skills/**, .github/**, docs/**, scripts/docs/**]
load_when: [ai-native-documentation-history]
source_paths: [AGENTS.md, docs/agent-map.yaml, docs/traceability.yaml, scripts/docs/check_docs.py]
---

# AI-native documentation migration — 2026-08-03

## Outcome

Implemented one progressive-disclosure documentation plane for GitHub Copilot VS Code and Codex: root/scoped `AGENTS.md`, five shared `.agents/skills`, thin Copilot adapters, canonical architecture/domain/rules/features/testing/operations docs, machine routing/traceability, task continuity, deterministic validation, Make targets, CI, and contract tests. Removed legacy `.github/skills`, Continue/Claude prompt artifacts, and the frontend `CLAUDE.md` adapter.

## Decisions

- Documentation is approved intent; code is current behavior; tests/EDD are evidence.
- Static runtime prompts remain in `src/agent/prompts/agent_prompt.py`.
- Root plus nearest instructions have an 8 KB budget; routed task docs have a 24 KB default budget.
- Live providers, models/judges, deployment, commit, and push remain explicit approval boundaries.
- Accepted ADR content remains historical; ADR-0007 supersedes obsolete Destination/readiness ownership.

## Protected work

Pre-existing Itinerary/backend/frontend/test/EDD/`pyproject.toml` work was not edited. The application-only tracked diff (`src`, `frontend/src`, existing `tests`, `edd`, and `pyproject.toml`) retained SHA-256 `80cb5361732a08908cec67e5d95365098fe59bbd2d7a53e1b033fcf015639518`, matching the pre-task baseline. The only new test is `tests/test_docs_contract.py`.

## Migration evidence

The untracked operations guides were copied, compared byte-for-byte, and only then removed from their old location. Initial SHA-256 values were `1e99a954b3498c6580c382cc7b9068571f71994748e0f04bbc6c88877e6340dc` for `DEPLOYMENT.md` and `818f3b050a022e20e484a698c74a6e5fe396a58f530cdad8780ccb7dbbd48cdd` for `DOCKER_PRODUCTION_GUIDE.md`; both were subsequently audited and replaced with current canonical guidance.

## Validation evidence

- `make docs-check`: passed.
- `.venv/bin/pytest tests/test_docs_contract.py -q`: 9 passed.
- Ruff check and format-check on documentation tooling/test: passed.
- Python compilation of `scripts/docs/`: passed.
- Skill creator validation: all five skills valid and below 6 KB.
- `git diff --check`: passed.
- Budget, frontend, infrastructure, readiness, and Itinerary routing: expected scoped instructions/docs selected; task-doc totals 6.6–15.0 KB.
- Copilot adapter: 300 bytes; root plus every nearest scoped instruction: below 8 KB.
- No provider/model/judge request, live EDD refresh, Azure/GitHub mutation, deployment, commit, push, or external spend occurred.

## Remaining work

No work remains for this migration. For the next feature or bug, resolve its bundle with `make docs-context PATHS="<path>"`, create an active task packet when continuity is needed, and update rules/traceability with behavior changes.
