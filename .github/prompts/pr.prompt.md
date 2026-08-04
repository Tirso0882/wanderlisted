---
mode: agent
description: Prepare validated commits and a pull request after explicit approval.
---

# Prepare pull request

Read `/AGENTS.md` and `/docs/agent-map.yaml`. Inspect the full worktree, separate pre-existing/unrelated changes, and never stage them implicitly. Run the narrowest required hermetic checks from scoped instructions and report skipped live checks.

Propose file groups, conventional commit messages, PR title/body, and exact commands. Wait for explicit approval before committing, pushing, or creating the PR. Never force-push, expose secrets, deploy, or include caches/generated/personal files. After approval, execute only the accepted groups and report hashes, branch, validation, and PR URL.
