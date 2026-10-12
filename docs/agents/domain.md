# Domain docs

How engineering skills should consume Wanderlisted's domain documentation.

## Before exploring

1. Read `docs/domain/CONTEXT_MAP.md`.
2. Read the relevant context documents under `docs/domain/`.
3. Read relevant accepted decisions under `docs/adr/`.
4. Follow `docs/agent-map.yaml` for task-specific document routing and context budgets.

If a referenced document does not exist, proceed without suggesting that it be created upfront.

## Layout

This repository uses a multi-context layout:

- `docs/domain/CONTEXT_MAP.md` defines bounded contexts and permitted handoffs.
- `docs/domain/*.md` contains context-specific vocabulary and ownership.
- `docs/domain/GLOSSARY.md` defines shared vocabulary.
- `docs/adr/` contains system-wide architectural decisions.

Use the context map's ownership rules before moving facts or decisions between contexts.

## Vocabulary

Use terms defined by the relevant domain document and glossary. If a needed concept is missing, record the gap for domain modeling instead of inventing competing terminology.

## ADR conflicts

If proposed work contradicts an accepted ADR, identify the conflict explicitly rather than silently overriding it.
