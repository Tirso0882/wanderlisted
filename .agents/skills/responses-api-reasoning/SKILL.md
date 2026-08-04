---
name: responses-api-reasoning
description: Diagnose or change Wanderlisted LLM factory behavior, OpenAI or Azure OpenAI Responses API configuration, reasoning effort, model tiers, tool binding, structured output, response content blocks, blank output, hangs, timeouts, or dependency upgrades affecting model calls.
---

# Responses API and reasoning models

## Inputs

Collect provider, deployment/model environment names without secret values, tier, operation type (plain, tools, structured, stream), dependency versions, error/timeout, and whether a live reproduction is authorized. Read `../../../src/agent/llm.py`, `../../../src/agent/concurrency.py`, and [the diagnostic boundary](references/diagnostic-boundary.md).

## Workflow

1. Reproduce configuration resolution without printing credentials. Confirm provider, tier fallback, reasoning effort, API mode, timeout, and semaphore path from current code.
2. Separate plain invocation, structured output, bound tools, agent loop, and streaming. Test the smallest failing operation with a fake model or unit fixture first.
3. Construct runtime models only through `get_llm(tier=...)`. Do not hardcode deployment names or duplicate provider configuration.
4. Treat message content as provider-dependent blocks. Use the repository extraction helper at public boundaries; never assume a plain string.
5. Preserve semaphore wrapping across `ainvoke`, `astream`, `bind`, `bind_tools`, and `with_structured_output`.
6. For dependency changes, inspect installed APIs and official provider documentation, then add a regression test for the exact failing operation before changing compatibility code.
7. Classify authentication, quota, provider validation, network/TLS, timeout, and agent-loop failures separately.

## Stop conditions

Stop before any live model request unless the user approved provider, request count, token/cost ceiling, and safe credential handling. Stop rather than weakening TLS, removing concurrency controls, exposing secrets, or guessing unsupported model capabilities.

## Output

Return the failing boundary, resolved non-secret configuration, root cause or bounded hypothesis, code/tests changed, and live checks skipped or approved.

## Validation

```bash
.venv/bin/pytest tests/test_llm_factory.py -q
.venv/bin/ruff check src/agent/llm.py src/agent/concurrency.py tests/test_llm_factory.py
```
