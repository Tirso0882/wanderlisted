---
id: reference-audit-index
doc_type: reference
status: active
authority: descriptive
owners: [travel-platform]
applies_to: [docs/reference/**, docs/getting-started/**, docs/tools/**]
load_when: [legacy-reference, framework-background]
source_paths: [docs/reference, docs/getting-started, docs/tools]
---

# Optional and historical references

These files are excluded from automatic/task routing unless a specific historical or framework question requires them. They are not architectural or runtime authority; verify version-sensitive claims against current code and official documentation.

| File/group | Priority | Audit status |
|---|---|---|
| Framework guides in this directory | Optional | Background only; dependency/provider APIs may have drifted |
| [`BUILDING_RELIABLE_AGENTS.md`](BUILDING_RELIABLE_AGENTS.md) | Optional | General principles; canonical project controls live in architecture/testing docs |
| [`duffel-integration-plan.md`](duffel-integration-plan.md) | Optional | Historical plan; current implementation/tests are authoritative |
| [`../RESEARCH_BACKLOG.md`](../RESEARCH_BACKLOG.md) | Optional | Proposal backlog, not committed architecture |
| [`../EXECUTION_GUIDE.md`](../EXECUTION_GUIDE.md) | Deprecated | Replaced by `AGENTS.md`, `AI_WORKFLOW.md`, and testing docs |
| [`../getting-started/`](../getting-started/) | Deprecated | Describes removed Stage 1–3 paths and must not guide current changes |
| [`../tools/API_INTEGRATION_GUIDE.md`](../tools/API_INTEGRATION_GUIDE.md) | Optional | Generic background; use tool instructions and current feature contracts |
| [`../tools/HOTELBEDS_INTEGRATION.md`](../tools/HOTELBEDS_INTEGRATION.md) | Superseded | Use the active Hotelbeds feature pack and shared skill |
| [`../tools/TOOLS_REFERENCE.md`](../tools/TOOLS_REFERENCE.md) | Deprecated | Agent/tool roster may be stale; inspect current source |
| [`../tools/TOOL_DEVELOPMENT_GUIDE.md`](../tools/TOOL_DEVELOPMENT_GUIDE.md) | Optional | Generic examples only; scoped instructions/rules take precedence |

Legacy standalone orchestrator prompt documents were removed. Static runtime prompts have one canonical home: `src/agent/prompts/agent_prompt.py`.
