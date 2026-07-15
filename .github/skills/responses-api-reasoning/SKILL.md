---
name: responses-api-reasoning
description: 'Diagnose and prevent gpt-5.4 reasoning-model and Responses API failures in Wanderlisted. WHEN tool-calling agent hangs or times out, agent never returns, use_responses_api, bind_tools, create_agent loop stuck, 400 error from Azure OpenAI chat completions, gpt-5.4 / gpt-5.4-mini / gpt-5.4-nano / gpt-5.4-pro, reasoning model, reasoning_effort, message.content is a list not a string, empty or blank agent output, _extract_text_content, choosing an LLM tier, adding a tool-calling agent, or upgrading langchain-openai / langchain.'
---

# gpt-5.4 Reasoning Models + Responses API

The single most fragile area of the backend. Read this before touching
`src/agent/llm.py`, adding a tool-calling agent, changing model tiers, or
upgrading `langchain-openai`.

## Durable invariants (rarely change)

1. **Every gpt-5.4 model is a reasoning model** (gpt-5.4, -mini, -nano, -pro).
2. **Tool calling is NOT supported in Chat Completions with `reasoning: none`**
   (the default). Full tool calling needs the **Responses API**.
3. The factory sets `use_responses_api=True` and a **per-tier
   `reasoning_effort`** to work around this. It is the only supported path.
4. **`gpt-5.4-pro` is Responses-API-only** — Chat Completions returns `400`,
   and it does not support `reasoning: none` at all.
5. **Content from the Responses API is a `list[dict]` of blocks**
   (`[{"type": "text", "text": "..."}]`), never a plain `str`. You must run it
   through `_extract_text_content()` before reading `message.content`.

## The landmine (version-sensitive — verify before trusting)

There is a real, previously-shipped production bug: with some
`langchain-openai` versions, `use_responses_api=True` combined with
`bind_tools()` / `create_agent()` tool-calling loops **hangs indefinitely**
(plain `ainvoke()` without tools works fine). Deep queries that need
tool-calling agents time out silently.

**Current mitigation encoded in code:** tool-calling worker agents run on the
`fast` tier (reference deployment `gpt-5.4-mini`, `reasoning_effort=low`), which
supports Chat Completions and has been validated to work. `gpt-5.4-pro` is
avoided for tool-calling loops.

**If tool-calling agents hang after a dependency upgrade, this is suspect #1.**
Retest, then update this skill and `llm.py` together.

## Rules when writing code

- Never construct an LLM directly. Always use `get_llm(tier=...)` from
  [src/agent/llm.py](../../../src/agent/llm.py). Never hardcode model names —
  the deployment is resolved from env vars per tier.
- After any `llm.ainvoke(...)`, read the reply with
  `_extract_text_content(response.content)`. Never assume `.content` is a `str`.
- Pick the tier by role: `reasoning` = deep synthesis (Destination, Itinerary);
  `fast` = tool-calling workers; `utility` = triage/supervisor/render/shallow.

## Source of truth / verify against (do not hardcode these — read them)

- Tier → deployment resolution: `_resolve_deployment()` in [src/agent/llm.py](../../../src/agent/llm.py)
- Tier → reasoning effort: `_TIER_REASONING_EFFORT` in [src/agent/llm.py](../../../src/agent/llm.py)
- Concurrency caps + TPM math: `_SEMAPHORE_LIMITS` in [src/agent/concurrency.py](../../../src/agent/concurrency.py)
  (NOTE: exact TPM/semaphore numbers have historically drifted between
  `llm.py`, `concurrency.py`, and `copilot-instructions.md` — trust
  `concurrency.py` for caps, and never copy a number into prose.)
- Content extractor: `_extract_text_content()` in [src/agent/stage4_graph.py](../../../src/agent/stage4_graph.py)
  — currently **duplicated** in [src/api/main.py](../../../src/api/main.py); keep both in sync.
