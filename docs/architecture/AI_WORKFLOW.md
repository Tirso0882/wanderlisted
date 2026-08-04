---
id: architecture-ai-workflow
doc_type: architecture
status: active
authority: normative
owners: [travel-platform]
applies_to: [AGENTS.md, .agents/skills/**, .github/**, docs/**]
load_when: [agent-workflow, copilot, codex, planning, documentation]
source_paths: [AGENTS.md, docs/agent-map.yaml, scripts/docs/context_bundle.py]
---

# AI-agent development workflow

## Operating model

Copilot in VS Code and Codex share the same durable sources: root/nearest `AGENTS.md`, `.agents/skills/`, the active task packet, and routed canonical documents. `.github` files are only Copilot entry adapters. Neither agent should preload the whole repository.

## Lifecycle for a feature, bug, or improvement

1. **Orient.** Inspect the worktree and preserve unrelated/uncommitted work. Read root plus nearest instructions.
2. **Route context.** Use `docs/agent-map.yaml` or `make docs-context PATHS="..."` with task triggers. Load Critical documents, then Recommended documents within the task budget.
3. **Create/refresh a task packet.** Record objective, exclusions, protected files, applicable rules/contracts, decisions, validation, and the exact next action. The packet is continuity state, not a chat log.
4. **Inspect evidence.** Read focused tests and source after the documentation. Confirm current implementation matches approved intent; report drift.
5. **Plan ownership.** Assign each change to a bounded context. Trace inputs, state, consumers, error paths, and cost-bearing calls.
6. **Implement narrowly.** Preserve typed artifacts, evidence, and stable business-rule IDs. Update docs/traceability in the same change when behavior changes.
7. **Validate hermetically.** Run focused tests, lint, compilation/build checks, and `make docs-check`. Live providers/models/deployments require separate explicit approval and disclosed cost/call limits.
8. **Review.** Check behavior, security, stale data, partial/failure paths, public contracts, and unrelated diffs.
9. **Handoff.** Record concise evidence and remaining risk. When complete, replace the active packet with one compact archive document.

## Context budget behavior

Root plus one nearest instruction file must stay within the 8 KB automatic instruction budget. Routed task documents default to 24 KB. When the candidate set is larger, order by Critical, Recommended, Optional, then by route order; report omitted documents instead of silently exceeding the budget.

## Continuity rules

- Stable facts and contracts belong in canonical docs, not task packets.
- Reusable procedures belong in skills, not feature docs.
- A task packet carries only task-specific state and evidence.
- Accepted ADRs are never rewritten; a later ADR supersedes them.
- Generated indexes are rebuilt, not hand-edited.

## Completion standard

An agent may claim completion only when the requested change, affected documentation/traceability, and proportional hermetic checks are complete. It must explicitly identify skipped live checks and must not imply provider quality from offline fixtures alone.
