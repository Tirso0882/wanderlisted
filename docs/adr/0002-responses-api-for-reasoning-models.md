# 0002 — Use the Responses API for the gpt-5.4 reasoning family

**Status:** Accepted · **Date:** 2026-07-10 (retroactively documented) · **Deciders:** Tirso Gomez

## Context

Every model Wanderlisted uses is from the **gpt-5.4 family** (`gpt-5.4`, `gpt-5.4-mini`, `gpt-5.4-nano`,
`gpt-5.4-pro`), and **all of them are reasoning models**. This carries provider constraints that broke the
system when first encountered:

- **Tool calling is not supported in Chat Completions with `reasoning: none`** (the Chat Completions default)
  on gpt-5.4 models. Agents that bind tools would fail.
- **`gpt-5.4-pro` is Responses-API-only** — Chat Completions returns HTTP 400.
- Deep queries (anything needing a tool-calling agent) must be able to call tools reliably.

This surfaced as production `400` errors and, at one point, tool-calling loops that hung. See the captured
debugging notes in the repo memory (`gpt54-reasoning-models`, `azure-openai-tool-support`,
`responses-api-tool-calling-bug`).

## Decision

In the LLM factory [../../src/agent/llm.py](../../src/agent/llm.py):

- Enable **`use_responses_api=True`** for all tiers.
- Set a **non-`none` per-tier `reasoning_effort`** so tool calling works: `reasoning=medium`, `fast=low`,
  `utility=low` (tunable via `LLM_EFFORT_<TIER>`).
- Treat model output as **structured content blocks**: the Responses API returns `message.content` as a
  `list[dict]`, not a `str`. All readers go through a single `_extract_text_content()` helper.

## Consequences

**Positive**

- Tool calling works on reasoning models across every tier.
- One code path for all four gpt-5.4 variants, including the Responses-only `gpt-5.4-pro`.
- `reasoning_effort` becomes a per-tier quality/latency/cost dial.

**Negative / costs**

- **Content is never a plain string** — any code that does `message.content.strip()` will break. The
  `_extract_text_content()` helper is mandatory (documented in the project Copilot instructions).
- **Version sensitivity:** `langchain-openai` has historically had bugs where `use_responses_api=True`
  interacted badly with `bind_tools()`. **Retest tool-calling agents on every `langchain-openai` upgrade.**
- Reasoning adds latency vs a plain completion; mitigated by keeping worker/utility tiers at `low` effort.

## Alternatives considered

| Alternative | Why rejected | When to choose it instead |
|-------------|--------------|---------------------------|
| **Chat Completions + `reasoning: none`** | No tool calling on gpt-5.4; 400 on gpt-5.4-pro | Pure text generation with no tools |
| **Pin to a non-reasoning model** | None exists in the gpt-5.4 family we target | If a cheaper non-reasoning model is available and tools are simple |
| **Route only tool-callers to a special deployment** | Fragments config; the Responses API solves it uniformly | Mixed-vendor fleets where one model can't do tools at all |

## References

- Code: [../../src/agent/llm.py](../../src/agent/llm.py) (`use_responses_api`, `reasoning_effort`, `_extract_text_content`)
- Repo memory: `gpt54-reasoning-models`, `azure-openai-tool-support`, `responses-api-tool-calling-bug`
- Related: [ADR-0004](0004-tiered-models-and-semaphore-concurrency.md)
