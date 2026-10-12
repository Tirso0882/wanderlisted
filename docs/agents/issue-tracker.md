# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- Create an issue: `gh issue create --title "..." --body "..."`.
- Read an issue: `gh issue view <number> --comments`.
- List issues: use `gh issue list` with suitable state and label filters.
- Comment: `gh issue comment <number> --body "..."`.
- Apply or remove labels: use `gh issue edit`.
- Close an issue: `gh issue close <number> --comment "..."`.

Infer the repository from `git remote -v`. The `gh` CLI does this automatically inside the clone.

## Pull requests as a triage surface

PRs as a request surface: no.

## Skill operations

When a skill says "publish to the issue tracker", create a GitHub issue.

When a skill says "fetch the relevant ticket", run:

`gh issue view <number> --comments`

GitHub shares one number space across issues and pull requests. If a reference is ambiguous, try `gh pr view <number>` and then `gh issue view <number>`.
