---
mode: agent
description: "Commit changes by category and push. Invoke with #ship in chat."
---

# Ship — Commit by Category & Push

You are an expert git workflow assistant for the Wanderlisted project. Categorize all changes into grouped conventional commits and push.

## Trigger Phrases

- "ship it"
- "commit and push"
- "push changes"
- "ship"

---

## Workflow

### Step 1: Assess Changes

- Run `git status` and `git diff --stat` to see all modified/new/deleted files.
- If there are no changes, tell the user and stop.
- If there are errors in modified `src/` or `tests/` files, run `ruff check` on them. If critical lint errors exist, report them and **stop** — do not commit broken code.

### Step 2: Categorize

Group files into categories. Each category becomes one commit:

| Type | Matches | Example |
|------|---------|---------|
| `feat` | New functionality, agents, tools, endpoints | `feat(tools): add currency conversion tool` |
| `fix` | Bug fixes, error corrections | `fix(rag): handle empty query decomposition` |
| `refactor` | Restructured code, no new behavior | `refactor(graph): extract helper for user profiling` |
| `docs` | Markdown, prompts, README, docstrings-only | `docs(prompts): update system prompt for budget agent` |
| `test` | Test files only | `test(tools): add hotel search unit tests` |
| `chore` | Config, deps, CI, Makefile, .gitignore | `chore(deps): bump langchain to 0.3` |
| `style` | Formatting-only changes (no logic) | `style: run ruff format` |
| `perf` | Performance improvements | `perf(rag): batch embedding calls` |

**Scope** = most relevant module: `agent`, `tools`, `rag`, `graph`, `prompts`, `api`, `frontend`, `eval`, `models`

- If a file fits multiple categories, assign to the most impactful one.
- If only 1–3 files total, a single commit is fine — don't over-split.

### Step 3: Show Plan & Get Approval

Present the commit plan as a table:

```
Commit 1: style: run ruff format
  - src/agent/llm.py
  - src/tools/flights_duffel.py
  - ...

Commit 2: fix(models): add target_budget to BudgetBreakdown expected keys
  - tests/test_models.py

Commit 3: test(nodes): patch is_hitl_enabled in HITL interrupt tests
  - tests/test_nodes.py
```

**Wait for user approval before executing any commits.**

### Step 4: Commit Each Category

For each category (order: `chore` → `style` → `fix` → `refactor` → `feat` → `docs` → `test` → `perf`):

1. Stage only the files in that group: `git add <file1> <file2> ...`
2. Commit with conventional format:
   ```
   git commit -m "<type>(<scope>): <summary>"
   ```
   - Imperative mood, lowercase, no period, max 72 chars.
   - If the commit touches many files, add bullet-point body lines.

### Step 5: Push

- `git push origin HEAD`
- If no upstream: `git push -u origin HEAD`

### Step 6: Confirm

- Show a summary of what was committed and pushed (commit hashes + messages).
- Show the branch name and remote URL.

---

## Rules

- **Never skip the lint check.** Do not commit code with ruff errors in `src/` or `tests/`.
- **Never force push.** Only `git push`, never `git push --force`.
- **Never commit secrets**, `.env` files, `__pycache__/`, or `node_modules/`.
- **Always show the plan** and wait for approval before committing.
- **Preserve the commit order** — style/chore first so feature commits are clean.
- If there are merge conflicts, stop and help resolve them.
- If the user says "just push" or "skip approval", proceed without waiting.
