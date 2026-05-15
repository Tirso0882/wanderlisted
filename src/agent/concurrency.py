"""LLM concurrency guardrails — per-tier asyncio semaphores.

  reasoning (gpt-5.4, 300K TPM):
      Destination agent: ~5 ReAct tool calls × 3 K tokens ≈ 15 K tokens/run.
      300K TPM / 15 K = ~20 reasoning runs/min.
      Cap: 4 concurrent ainvokes — leaves headroom for spikes.

  fast (gpt-5.4-mini, 500K TPM):
      Worker agents (Flights, Hotels, etc.): ~3 tool calls × 2 K = ~6 K/run.
      500K TPM / 6 K = ~83 runs/min.
      Cap: 15 concurrent ainvokes.

  utility (gpt-5.4-nano, 200K TPM):
      Triage, supervisor, render extractions: ~1–2 K tokens/call.
      200K TPM / 2 K = ~100 calls/min.
      Cap: 15 concurrent ainvokes.

All gpt-5.4 family models are reasoning models.  The LLM factory
enables the Responses API and sets per-tier reasoning_effort to ensure
tool calling works (tool calling is not supported in Chat Completions
with reasoning: none on gpt-5.4 models).

Tuning guidance:
  - Raise limits if you observe queueing under normal load (monitor semaphore
    wait time in LangSmith traces).
  - Lower limits if you receive 429s because concurrent burst exceeds your
    Azure quota ceiling.
"""

import asyncio
from typing import Any

# ── Per-tier concurrency caps ─────────────────────────────────────────────
_SEMAPHORE_LIMITS: dict[str, int] = {
    "reasoning": 4,  # 300K TPM / 15K per call = 20 calls/min max
    "fast": 15,  # 500K TPM / 6K per call = 83 calls/min max
    "utility": 15,  # 200K TPM / 2K per call = 100 calls/min max
}

# Module-level singletons — lazily created so no event loop is required at
# import time (Python 3.10+ Semaphore no longer binds to a loop on creation).
_llm_semaphores: dict[str, asyncio.Semaphore] = {}


def _get_llm_semaphore(tier: str) -> asyncio.Semaphore:
    """Return (creating lazily) the shared per-tier asyncio.Semaphore."""
    if tier not in _llm_semaphores:
        _llm_semaphores[tier] = asyncio.Semaphore(_SEMAPHORE_LIMITS.get(tier, 10))
    return _llm_semaphores[tier]


# ── Proxy wrappers ────────────────────────────────────────────────────────


class _SemaphoreRunnable:
    """Wraps a LangChain Runnable (e.g. structured-output chain) with a semaphore.

    Used by ``_SemaphoreLLM.with_structured_output()`` so every structured
    extraction call is also gated.
    """

    def __init__(self, runnable: Any, semaphore: asyncio.Semaphore) -> None:
        object.__setattr__(self, "_runnable", runnable)
        object.__setattr__(self, "_semaphore", semaphore)

    def __getattr__(self, name: str) -> Any:
        try:
            runnable = object.__getattribute__(self, "_runnable")
        except AttributeError:
            raise AttributeError(name)
        return getattr(runnable, name)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        semaphore = object.__getattribute__(self, "_semaphore")
        runnable = object.__getattribute__(self, "_runnable")
        async with semaphore:
            return await runnable.ainvoke(*args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return object.__getattribute__(self, "_runnable").invoke(*args, **kwargs)


class _SemaphoreLLM:
    """Thin proxy that gates every ``ainvoke()`` call through a per-tier semaphore.

    Wraps any LangChain ``BaseChatModel``.  All attribute accesses not
    explicitly defined here are transparently forwarded to the underlying
    model — LangChain internals (``bind_tools``, ``configurable_fields``,
    ``model_name``, etc.) work without modification.

    ``ainvoke`` is the only hot path we need to gate; ``invoke`` is left
    ungated because the graph is fully async.
    """

    def __init__(self, model: Any, semaphore: asyncio.Semaphore) -> None:
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_semaphore", semaphore)

    def __getattr__(self, name: str) -> Any:
        try:
            model = object.__getattribute__(self, "_model")
        except AttributeError:
            raise AttributeError(name)
        return getattr(model, name)

    # ── gated hot path ────────────────────────────────────────────────────

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        semaphore = object.__getattribute__(self, "_semaphore")
        model = object.__getattribute__(self, "_model")
        async with semaphore:
            return await model.ainvoke(*args, **kwargs)

    async def astream(self, *args: Any, **kwargs: Any) -> Any:
        semaphore = object.__getattribute__(self, "_semaphore")
        model = object.__getattribute__(self, "_model")
        async with semaphore:
            async for chunk in model.astream(*args, **kwargs):
                yield chunk

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return object.__getattribute__(self, "_model").invoke(*args, **kwargs)

    # ── wrap returned runnables so gating propagates ───────────────────────

    def with_structured_output(self, *args: Any, **kwargs: Any) -> _SemaphoreRunnable:
        model = object.__getattribute__(self, "_model")
        semaphore = object.__getattribute__(self, "_semaphore")
        inner = model.with_structured_output(*args, **kwargs)
        return _SemaphoreRunnable(inner, semaphore)

    def bind_tools(self, *args: Any, **kwargs: Any) -> "_SemaphoreLLM":
        model = object.__getattribute__(self, "_model")
        semaphore = object.__getattribute__(self, "_semaphore")
        inner = model.bind_tools(*args, **kwargs)
        return _SemaphoreLLM(inner, semaphore)

    def bind(self, *args: Any, **kwargs: Any) -> "_SemaphoreLLM":
        model = object.__getattribute__(self, "_model")
        semaphore = object.__getattribute__(self, "_semaphore")
        inner = model.bind(*args, **kwargs)
        return _SemaphoreLLM(inner, semaphore)
