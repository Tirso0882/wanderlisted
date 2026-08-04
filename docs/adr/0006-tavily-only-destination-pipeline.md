# 0006 — Tavily-only bounded destination pipeline

**Status:** Accepted · **Date:** 2026-07-26 · **Deciders:** Tirso Gomez

## Context

Destination research combined an inner ReAct agent, a curated guide corpus,
Pinecone retrieval, Cohere reranking, OpenWeatherMap, REST Countries, and Tavily.
That architecture duplicated planning and synthesis responsibilities, made claim
provenance difficult to enforce, and required several independent credentials,
indexes, fallbacks, and evaluation paths.

Destination output also fed safety review and handbook rendering as prose. Those
consumers had to infer structure again and could silently invent defaults when
evidence was absent.

## Decision

Replace the complete destination implementation with a fixed asynchronous
pipeline while preserving its graph and API contract:

1. Plan at most six intent-adaptive queries with the utility model.
2. Execute Tavily searches directly through a shared `httpx.AsyncClient`, with
   at most four concurrent requests, transient retries, and a six-hour bounded
   cache keyed by every search parameter.
3. Ignore Tavily-generated answers; normalize and deduplicate result snippets.
4. Synthesize a typed `DestinationReport` with the reasoning model.
5. Render chat text and citations deterministically from that report.

Every factual field references returned source IDs. Sensitive safety, weather,
health, visa, and emergency claims require a configured permitted official
domain or remain unverified. Missing safety evidence maps to `unknown`, never to
a reassuring default. Retrieved text is untrusted data and embedded instructions
are ignored.

The safety gate and handbook renderer consume the typed report directly. The
legacy single-agent graph uses the same Tavily provider through a small tool
adapter. The previous RAG, weather, and country-information implementations and
their dependencies are removed without a feature flag or fallback.

## Consequences

**Positive**

- A bounded request and concurrency budget makes latency and cost predictable.
- Source IDs and field-level mappings make citation integrity testable.
- Official-source policy and explicit unknown states reduce unsafe defaults.
- One provider and one evidence model substantially simplify operations.
- Typed consumers no longer need destination-specific LLM re-extraction.

**Negative / costs**

- Search quality and availability now depend on Tavily.
- The removed curated corpus no longer provides offline or editorial coverage.
- Snippet-only synthesis can omit details that require full-page retrieval.
- Adding another source requires extending the evidence normalization contract.

## Alternatives considered

| Alternative | Why rejected | When to choose it instead |
|---|---|---|
| Keep hybrid RAG plus live search | Highest operational and grounding complexity | A maintained proprietary corpus provides proven, unique value |
| Keep the destination ReAct loop | Tool-call count and behavior are harder to bound | Open-ended research is more important than deterministic coverage |
| Use Tavily SDK | Adds a dependency without needed behavior | The SDK provides required transport features not available through HTTP |
| Add a runtime feature flag | Preserves two implementations and two failure surfaces | A staged rollout needs reversible production traffic splitting |

## References

- Pipeline: `src/destination/pipeline.py`
- Provider: `src/destination/provider.py`
- Typed models: `src/destination/models.py`
- Graph integration: `src/agent/stage4_graph.py`
- Supersedes: [0005](0005-two-tier-rag-chunking-strategy.md)
