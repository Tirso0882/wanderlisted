---
mode: agent
description: Prepare categorized commits and push only after explicit approval.
---

# Prepare ship

Read `/AGENTS.md` and `/docs/agent-map.yaml`. Inspect status/diffs, protect pre-existing work, and run scoped hermetic validation. Propose exact file groups and conventional commit messages; wait for explicit approval before staging, committing, or pushing.

Never force-push, deploy, include secrets/caches/generated/personal files, or silently run live providers/models. After approval, stage only accepted paths, push the current branch normally, and report commit hashes, branch, remote, and checks.
