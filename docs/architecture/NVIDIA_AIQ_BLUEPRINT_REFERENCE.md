# NVIDIA AI-Q Blueprint — Architectural Reference for Wanderlisted
> **Purpose:** Architectural reference and adoption guide derived from the NVIDIA AI-Q Blueprint, applied to the Wanderlisted multi-agent travel itinerary system.  
> **Source:** NVIDIA AI-Q Blueprint (open source, Apache 2.0)  
> **Stack alignment:** LangGraph · LangChain · LlamaIndex (RAG) · LangSmith  
> **Date:** March 2026

---

## Table of Contents

1. [What AI-Q Is](#1-what-ai-q-is)
2. [Core Architecture](#2-core-architecture)
3. [Shallow vs. Deep Research Routing](#3-shallow-vs-deep-research-routing)
4. [YAML Workflow Configuration](#4-yaml-workflow-configuration)
5. [RAG via LlamaIndex — Destination Guides](#5-rag-via-llamaindex--destination-guides)
6. [Evaluation Harnesses](#6-evaluation-harnesses)
7. [What Wanderlisted Adopts from AI-Q](#7-what-wanderlisted-adopts-from-ai-q)
8. [What Wanderlisted Omits and Why](#8-what-wanderlisted-omits-and-why)
9. [Production Scaling Appendix](#9-production-scaling-appendix)

---

## 1. What AI-Q Is

NVIDIA AI-Q Blueprint is an open-source reference implementation for building deep research AI agents. It delivers both quick answers and full report-style research in a single system with built-in evaluation harnesses — so quality can be measured and improved over time.

It is ranked top on the **DeepResearch Bench** and **DeepResearch Bench II** leaderboards.

**Core 3rd-party stack:**

| Component | Role |
|-----------|------|
| **LangChain / LangGraph** | Workflow orchestration and state machine |
| **LlamaIndex** | RAG over private/local document knowledge bases |
| **Tavily** | Live web search |
| **Serper** | Academic / Google Scholar search |

**Deployment options:** CLI · Web UI · Docker Compose · Helm

---

## 2. Core Architecture

AI-Q is built as a **LangGraph state machine** where each agent node can run standalone or as part of the full pipeline. This mirrors the Wanderlisted supervisor/router design exactly.

```
User Query
    │
    ▼
┌─────────────────────────┐
│   Orchestration Node    │  ← Classifies intent + sets depth (shallow/deep)
│   (intent router)       │    Handles meta-queries directly
└───────────┬─────────────┘
            │
     ┌──────┴──────┐
     ▼             ▼
┌─────────┐  ┌──────────────┐
│ Shallow │  │    Deep      │
│ Research│  │  Research    │
│  Agent  │  │   Agent      │
└────┬────┘  └──────┬───────┘
     │              │
     │    Tools:    │
     │  Web Search  │
     │  RAG / Docs  │
     │  API Calls   │
     ▼              ▼
         Response
   (Quick answer  or  Full report + citations)
```

**Key design principles:**
- Each agent is **composable** — can run standalone or wired into the full pipeline
- The orchestration node handles both **routing and depth classification** in a single step
- All agents share a **common tool registry** defined in YAML config

---

## 3. Shallow vs. Deep Research Routing

This is the most directly applicable pattern for Wanderlisted.

| Dimension | Shallow Agent | Deep Agent |
|-----------|--------------|------------|
| **Purpose** | Fast, bounded answers | Multi-phase, thorough research |
| **Optimised for** | Speed | Depth + citation |
| **Phases** | Single tool call cycle | Plan → Iterate → Synthesise → Cite |
| **Wanderlisted equivalent** | "What's the weather in Tokyo next week?" | Full multi-day itinerary with flights, hotels, activities, safety, budget |

### Intent Classification Logic

The orchestration node classifies every incoming query on two axes:

1. **Type:** `meta` (questions about the system) vs. `research` (real information tasks)
2. **Depth:** `shallow` (single-pass) vs. `deep` (multi-phase with planning)

```python
# Conceptual orchestration node — Wanderlisted adaptation
class IntentClassifier(TypedDict):
    query_type: Literal["meta", "research"]
    depth: Literal["shallow", "deep"]
    reasoning: str

# Shallow triggers: single-city weather, currency rate, one activity lookup
# Deep triggers: full itinerary, multi-destination trip, budget breakdown + booking suggestions
```

### Applying This to Wanderlisted

| User Request | Depth | Agents Activated |
|---|---|---|
| "What's the visa requirement for Japan?" | Shallow | SafetyTool |
| "Best time to visit Kyoto?" | Shallow | WeatherTool + ActivitiesTool |
| "Plan a 10-day Japan trip for 2, budget $4,000" | Deep | All agents: Flight · Hotel · Weather · Activities · Safety · Budget · Currency |
| "Find me a ryokan in Hakone under $200/night" | Shallow | HotelSearchTool + CurrencyTool |

---

## 4. YAML Workflow Configuration

AI-Q uses YAML configs to define agents, tools, LLMs, and routing — enabling workflow tuning without code changes.

### Why This Matters for Wanderlisted

- Swap the underlying LLM (Claude → GPT-4o → Gemini) per agent without touching Python
- Enable/disable tools (e.g., turn off BookingTool in demo mode)
- Configure routing thresholds for shallow vs. deep classification
- Allow white-label clients to customise agent behaviour through config, not code

### Example Config Structure (Wanderlisted Adaptation)

```yaml
# wanderlisted_config.yaml

orchestrator:
  model: claude-3-5-sonnet
  depth_threshold: 3  # queries touching 3+ tools → deep research

agents:
  shallow:
    model: claude-3-haiku
    max_tool_calls: 2
    tools: [weather, currency, safety]

  deep:
    model: claude-3-5-sonnet
    max_tool_calls: 10
    tools: [flight_search, hotel_search, weather, activities, safety, budget, currency, iata_lookup]

rag:
  enabled: true
  provider: llamaindex
  index_path: ./knowledge_base/destination_guides
  embedding_model: text-embedding-3-large
  top_k: 5

routing:
  meta_response: true   # handle "what can you do?" queries inline
  fallback_to_shallow: true
```

---

## 5. RAG via LlamaIndex — Destination Guides

### Why RAG Belongs in Wanderlisted

Clients may supply proprietary destination knowledge — curated travel guides, local expertise documents, brand-specific recommendations, or vetted safety advisories — that should ground agent responses beyond what live APIs return.

LlamaIndex handles this as an **optional RAG layer** sitting alongside the tool-calling agents.

### Architecture

```
Client uploads destination_guides/*.pdf (or .md / .html)
            │
            ▼
    LlamaIndex ingestion pipeline
    ├── Document chunking
    ├── Embedding (e.g., text-embedding-3-large)
    └── Vector store index (local or hosted)
            │
            ▼
    RAG tool exposed to agents
    └── Agents query index when:
        - A destination-specific question is asked
        - Live API data is insufficient
        - Client has provided curated local knowledge
```

### Implementation Sketch

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import QueryEngineTool

# Build index from client-supplied destination guides
documents = SimpleDirectoryReader("./knowledge_base/destination_guides").load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine(similarity_top_k=5)

# Wrap as a LangChain-compatible tool for use in LangGraph nodes
destination_rag_tool = QueryEngineTool.from_defaults(
    query_engine=query_engine,
    name="destination_guide_search",
    description=(
        "Search curated destination guides for local tips, cultural notes, "
        "neighbourhood recommendations, safety advisories, and insider knowledge. "
        "Use this before or after live API calls to enrich itinerary quality."
    ),
)
```

### When Agents Should Use the RAG Tool

| Scenario | Use RAG |
|----------|---------|
| API returns no results for a niche destination | Yes |
| Client has uploaded a proprietary destination guide | Yes |
| Generic question answerable by live API | No |
| Enriching a draft itinerary with local context | Yes |
| Real-time pricing / availability | No — use live tools |

### Knowledge Base Management

```
knowledge_base/
├── destination_guides/
│   ├── japan_travel_handbook.md        # Already in project (docs/)
│   ├── southeast_asia_guide.pdf
│   └── client_custom_london_brief.pdf
├── safety_advisories/
│   └── fcdo_travel_warnings.md
└── visa_requirements/
    └── visa_matrix_2026.md
```

> **Note:** The `japan_travel_handbook.html` already in `docs/` is a direct candidate for RAG ingestion. Move or symlink it to `knowledge_base/destination_guides/` when the RAG layer is implemented.

---

## 6. Evaluation Harnesses

AI-Q ships with built-in benchmarks (FreshQA, DeepResearch Bench) and evaluation scripts. Wanderlisted should adapt this pattern using LangSmith.

### Proposed Evaluation Suite for Wanderlisted

| Evaluator | Type | What It Checks |
|-----------|------|----------------|
| `itinerary_completeness` | Code-based | All requested days have entries; no gaps |
| `budget_within_range` | Code-based | Total estimated cost ≤ user's stated budget |
| `tools_called_correctly` | Code-based | Deep query used all required agents; shallow used ≤2 |
| `no_hallucinated_iata` | Code-based | All airport codes are valid IATA codes |
| `itinerary_quality` | LLM-as-Judge | Coherence, pacing, local relevance, personalisation (0–3 scale) |
| `rag_citation_accuracy` | LLM-as-Judge | Destination guide citations are accurate and relevant |

### Evaluation Loop (from AI-Q pattern)

```
Build agent version
      │
      ▼
Run against benchmark prompts (e.g., 20 standard trip requests)
      │
      ▼
Score with evaluator suite (LangSmith)
      │
      ▼
Identify failure mode → change one thing (prompt / tool / routing threshold)
      │
      ▼
Re-run and compare scores
```

---

## 7. What Wanderlisted Adopts from AI-Q

| AI-Q Pattern | Wanderlisted Adoption |
|---|---|
| LangGraph state machine | Already in use — AI-Q validates this choice |
| Shallow / deep routing | Implement in orchestration node based on tool count threshold |
| Intent classification node | Single node: classify type + depth before routing |
| YAML workflow config | Replace hardcoded agent wiring with YAML-driven config |
| Composable standalone agents | Each tool-agent (FlightSearch, etc.) runnable independently |
| LlamaIndex RAG | Destination guides knowledge base for client-supplied documents |
| Evaluation harnesses | LangSmith-based benchmark suite against standard trip requests |
| Citation management | Deep research agent tracks which tool/source each fact came from |

---

## 8. What Wanderlisted Omits and Why

### Self-Hosted GPU Model Stack

AI-Q supports fully self-hosted inference using NVIDIA's own models:
- Nemotron 3 Super 120B
- GPT OSS 120B  
- Nemotron 3 Nano 30B
- NeMo Retriever pipelines (OCR, table structure, graphic elements)

**Why this is overkill for Wanderlisted:**

1. **Scale mismatch.** These models require dedicated GPU servers (H100/A100 class hardware). Wanderlisted is a travel itinerary agent, not a document intelligence platform processing millions of PDFs.

2. **Operational cost.** Running a 120B parameter model 24/7 for travel planning is economically irrational when frontier API models (Claude, GPT-4o) cost fractions of a cent per itinerary and outperform most open models on instruction-following tasks.

3. **Maintenance burden.** Self-hosted LLMs require model versioning, CUDA driver management, quantisation decisions, and uptime monitoring — none of which adds value to the travel domain.

4. **The RAG stack is already simpler.** NeMo Retriever's OCR, table extraction, and graphic element pipelines exist to parse complex enterprise documents at scale. Destination guides are well-structured Markdown, HTML, or PDF files — LlamaIndex's `SimpleDirectoryReader` handles these in a few lines of code without GPU infrastructure.

5. **API-first is the right default.** Wanderlisted's competitive advantage is orchestration quality and travel domain knowledge, not model hosting. Frontier APIs (Claude, GPT-4o, Gemini) are updated continuously and require zero infrastructure.

**When self-hosted would make sense:** If a client requires full data sovereignty (no data leaving their network), on-premise deployment becomes relevant. At that point, the NVIDIA stack is the right path — but it is an enterprise configuration concern, not a core architecture decision.

---

## 9. Production Scaling Appendix
> **Source:** [How to Scale Your LangGraph Agents in Production From A Single User to 1,000 Coworkers](https://developer.nvidia.com/blog/how-to-scale-your-langgraph-agents-in-production-from-a-single-user-to-1000-coworkers/) — NVIDIA Developer Blog, August 2025

NVIDIA's internal engineering team deployed AI-Q (the same LangGraph application this document is based on) to hundreds of internal users and documented their exact scaling methodology. The approach is a **3-step loop** applicable to any LangGraph agent at production scale.

---

### Step 1 — Profile the Single-User Baseline

Before scaling, deeply understand what happens for one user. Agentic applications are non-deterministic, so profiling must cover a varied dataset of inputs — not just a single happy path.

**Tool:** NeMo Agent Toolkit profiler (equivalent role in Wanderlisted: LangSmith tracing)

**What to capture:**
- **Gantt/waterfall chart** — which nodes execute in sequence vs. parallel, and where time is lost
- **Token usage per node** — identify which agents consume the most tokens
- **End-to-end workflow runtime** — establish baseline p95 latency before any load
- **Custom evaluation metrics** — quality scores alongside timing (never optimise speed at the cost of correctness)

```yaml
# NeMo Agent Toolkit profiler config (conceptual — Wanderlisted uses LangSmith)
eval:
  general:
    output_dir: single_run_result
    dataset:
      _type: json
      file_path: benchmark_itinerary_inputs.json
    profiler:
      token_uniqueness_forecast: true
      workflow_runtime_forecast: true
      compute_llm_metrics: true
      bottleneck_analysis:
        enable_nested_stack: true
```

**NVIDIA's finding:** The LLM call (not retrieval, not tool calls) was the primary bottleneck. For Wanderlisted, the equivalent is likely the deep research agent's synthesis step or the flight/hotel search tool calls when APIs are slow.

**Wanderlisted profiling checklist (LangSmith):**

| What to measure | LangSmith signal |
|---|---|
| Which node takes longest | Trace timeline view |
| Token cost per itinerary | Token usage per run |
| Tool call failure rate | Error rate per tool |
| Shallow vs. deep routing accuracy | Custom evaluator |
| RAG retrieval relevance | LLM-as-Judge evaluator |

---

### Step 2 — Load Test to Forecast Capacity

Run the application at increasing concurrency levels to find where performance degrades and understand the hardware/replica requirements for your target user count.

**Concurrency ladder used by NVIDIA:** 1 → 2 → 4 → 8 → 16 → 32 → 50 concurrent users

**Key metrics to track at each level:**
- p95 LLM call latency
- p95 end-to-end workflow runtime
- Error rate (timeouts, tool failures)
- CPU and memory utilisation

**Extrapolation formula:**
> If 1 API worker supports N concurrent sessions within your latency threshold,
> then for C concurrent users you need ⌈C / N⌉ workers.

**Two bugs NVIDIA only found under load — both relevant to Wanderlisted:**

1. **CPU starvation from misconfiguration.** A service was deployed with fewer vCPUs than intended (Helm misconfiguration). Under load it pegged at 100% CPU. Lesson: always verify replica resource limits match your profiled requirements before rollout.

2. **LLM timeouts with no retry path.** LLM calls that timed out broke the entire session silently. They fixed this with explicit timeout + retry logic. **This should be implemented in Wanderlisted now, before any scaling concern arises:**

```python
import asyncio

ASYNC_TIMEOUT = 30  # seconds — tune per agent

async def call_llm_with_retry(chain, input, writer, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            async with asyncio.timeout(ASYNC_TIMEOUT):
                answer = ""
                async for chunk in chain.astream(input, stream_usage=True):
                    answer += chunk.content
                    writer({"generating": chunk.content})
                return answer
        except asyncio.TimeoutError:
            if attempt == max_retries:
                writer({"error": "Request timed out. Please try again."})
                return None
            # brief backoff before retry
            await asyncio.sleep(2 ** attempt)
```

> **Apply this pattern to:** every tool-calling node (FlightSearch, HotelSearch, WeatherTool), the deep research synthesis step, and any RAG retrieval call.

---

### Step 3 — Phased Rollout with Live Monitoring

Deploy with the replica count estimated in Step 2, but roll out gradually: small team first, then expand. Monitor continuously during each phase.

**NVIDIA's monitoring stack:** OpenTelemetry (OTEL) collector → Datadog

**Wanderlisted equivalent at current stage:** LangSmith (traces, latency, evaluations) — no additional infrastructure needed

**Monitoring signals that matter in production:**

| Signal | What it reveals |
|---|---|
| Flame graph per user session | Which node is the actual bottleneck in real usage |
| p95 latency by node | Outlier sessions dragging the average |
| Tool error rate by provider | Flaky 3rd-party APIs (flight, hotel, weather) |
| Shallow vs. deep ratio | Whether routing is classifying correctly at scale |
| RAG retrieval hit rate | Whether the destination guide index is being used |

```python
# LangSmith tracing — already planned for Wanderlisted
# Add @traceable to every node for automatic flame graph capture
from langsmith import traceable

@traceable(name="deep_research_agent")
async def deep_research_node(state: ItineraryState) -> ItineraryState:
    # ... agent logic
    pass

@traceable(name="flight_search_tool")
async def call_flight_api(query: str) -> dict:
    # ... API call with timeout + retry
    pass
```

**Phased rollout checklist:**

- [ ] Single-user profiling complete (LangSmith baseline run)
- [ ] Timeout + retry logic added to all LLM and tool calls
- [ ] Load test at 5, 10, 20 concurrent sessions
- [ ] Replica/worker count set based on load test extrapolation
- [ ] LangSmith monitoring active pre-launch
- [ ] Phase 1: internal / demo users only
- [ ] Phase 2: first client — monitor p95 and error rate daily
- [ ] Phase 3: broader rollout with autoscaling configured

---

### Summary: What to Implement Now vs. Later

| Action | When |
|---|---|
| Timeout + retry on all LLM and tool calls | **Now** — before first real user |
| LangSmith `@traceable` on all nodes | **Now** — needed for every subsequent step |
| Benchmark dataset of 10–20 standard trip requests | Before first client |
| Single-user profiling run | Before first client |
| Load test at 10–20 concurrency | Before multi-client rollout |
| Replica/worker autoscaling config | At multi-client scale |
