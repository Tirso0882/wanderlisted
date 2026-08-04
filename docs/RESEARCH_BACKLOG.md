# Research Backlog — "The Next Big Thing"

> A disciplined place to park hypotheses about where AI is going, so experimentation is deliberate rather than
> shiny-object chasing. Each item is a **hypothesis + a small, time-boxed spike + a decision**. Ship one spike
> end-to-end before starting the next; retire the rest with a written "why not."
>
> _Last updated: 2026-07-10 · Owner: Tirso Gomez_

---

## How to run a spike

1. **Hypothesis** — one sentence: "If we do X, then metric Y improves because Z."
2. **Kill criteria** — what result would make us drop it.
3. **Smallest test** — the least work that could validate/invalidate the hypothesis.
4. **Measure** — reuse the [EDD evaluators](../edd/) so results are numbers, not vibes.
5. **Decide** — adopt (fold into the roadmap), park (revisit later), or kill (write why).

Spike template:

```
### <name>
- Status: proposed | active | adopted | parked | killed
- Hypothesis:
- Kill criteria:
- Smallest test:
- Metric / result:
- Decision:
```

---

## Backlog (ranked by signal-to-effort)

### 1. Long-term agentic memory (LangGraph `Store`)
- **Status:** proposed
- **Hypothesis:** persisting user preferences (travel style, dietary needs, past destinations) across threads
  via the LangGraph `Store` improves personalization and cuts re-elicitation, raising itinerary quality scores.
- **Kill criteria:** no measurable lift on the golden dataset, or memory retrieval adds >300 ms p50.
- **Smallest test:** store `travel_style` + `dietary_restrictions` under a `user_id` namespace; inject on the
  next thread; A/B against no-memory using the existing L3 pairwise judge.
- **Ties to:** Pillar 2 (autonomous decisions), Pillar 6 (auditable memory writes).

### 2. Local reasoning model on-device
- **Status:** proposed
- **Hypothesis:** a small local reasoning model (served via Ollama/vLLM) can handle the **utility tier**
  (triage/routing/extraction) at near-zero marginal cost and full offline capability, matching gpt-5.4-nano on
  routing accuracy.
- **Kill criteria:** routing accuracy drops >5 pts vs the commercial utility tier on the benchmark.
- **Smallest test:** point the utility tier at a local model; run the Pillar 7 benchmark harness.
- **Ties to:** Pillars 1, 3, 7 (on-prem, published local-first library, benchmarking/custom models).

### 3. Semantic caching for tool + LLM calls
- **Status:** proposed
- **Hypothesis:** caching by semantic similarity (embedding of the request) cuts cost and latency for repeated
  or near-duplicate queries (common in travel: same city, same dates).
- **Kill criteria:** cache hit rate <15% on realistic traffic, or stale-answer risk unacceptable.
- **Smallest test:** wrap the utility-tier calls with an embedding-keyed cache; measure hit rate + cost delta.

### 4. GraphRAG / entity-linked retrieval
- **Status:** proposed
- **Hypothesis:** linking entities (neighborhoods, POIs, transit lines) across guides improves multi-hop
  questions ("a walkable area near the old town with vegan food and metro access") over flat vector RAG.
- **Kill criteria:** no lift on multi-constraint queries vs the current pipeline; index cost too high.
- **Smallest test:** build a small entity graph for one city; compare answers on 10 multi-constraint prompts.

### 5. Auto prompt-optimization in the loop
- **Status:** proposed
- **Hypothesis:** an offline optimizer that mutates agent prompts and selects with the L3 pairwise judge can
  beat hand-tuned prompts on agent quality without human effort.
- **Kill criteria:** optimizer can't beat the hand-tuned baseline after a fixed budget.
- **Smallest test:** run it on the Flights agent (where L1–L3 evals already exist in [../edd/flights/](../edd/flights/)).

### 6. Computer-use / browser agent for live checks
- **Status:** proposed
- **Hypothesis:** a sandboxed browser agent can verify live availability/prices the batch APIs miss, improving
  factual accuracy of the final itinerary.
- **Kill criteria:** reliability/latency too poor for production; safety surface too large.
- **Smallest test:** one narrow task (verify a hotel's published cancellation policy) behind a HITL gate.

### 7. MCP client federation
- **Status:** proposed
- **Hypothesis:** consuming external MCP servers lets clients plug in their own tools/data without code
  changes — a strong enterprise-integration story.
- **Kill criteria:** protocol overhead or auth complexity outweighs the plug-in benefit.
- **Smallest test:** connect the graph to one external MCP server as a tool source.

---

## Retired / parked

_None yet — this section records killed spikes and the reason, so we don't relitigate them._
