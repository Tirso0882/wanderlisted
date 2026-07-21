# Wanderlisted Evaluation Map

This reference maps the general metric framework to Wanderlisted's Stage 4
supervisor graph, specialized travel agents, RAG pipeline, HITL gates, and
handbook output.

## Evaluation Pyramid

| Level | Outcome question | Primary evidence | Typical diagnostics |
|---|---|---|---|
| Component | Did one worker correctly perform its assigned capability? | Query, tool calls/args, tool output, worker summary | Tool/argument correctness, groundedness, worker helpfulness |
| Integration | Did graph coordination preserve and combine correct work? | Routes, node order, state deltas, fan-in result, interrupts | Routing, reducer merge, graceful degradation, HITL policy |
| End-to-end | Did the traveler receive an approved, usable trip plan? | Full request/profile, final state, handbook, complete graph trace | Constraint coverage, safety, budget, consistency, render success |
| Thread | Did follow-up conversation move the same trip toward the user's goal? | Ordered turns, child runs, persisted state, resumes | Context retention, correction handling, repetition, final outcome |

Build bottom-up for localization, but always retain at least one end-to-end task
completion metric so component improvements remain tied to the user outcome.

## Completion Contracts by Intent

### Full Itinerary

`completed` means:

- the supervisor captured destination and applicable profile constraints;
- required specialist work ran or recorded an explicit recoverable failure;
- parallel outputs survived fan-in;
- safety policy was evaluated and any required safety interrupt occurred;
- budget was calculated and any required budget interrupt occurred;
- itinerary synthesis used available components;
- human review was approved or the case is explicitly labeled
  `needs_user_input`;
- the requested handbook format rendered successfully;
- the final plan does not silently violate critical dates, destinations, group,
  budget, diet, accessibility, or safety constraints.

Do not define success as "all eight agents ran." Routing may legitimately vary
by intent, and external providers may return no inventory.

### Focused Capability Request

Examples: flights only, hotels only, local transportation, restaurant options.

`completed` means the relevant capability produced usable, request-aligned
options, or accurately explained why no result could be produced. Running the
entire itinerary pipeline unnecessarily is a trajectory-quality issue even when
the final answer is acceptable.

### Shallow Interaction

Examples: greeting, thanks, capability question.

`completed` means a concise direct answer was returned without Stage 4 fan-out.

### Follow-Up or Revision

`completed` means the requested change was applied to the existing trip while
unmodified approved facts and constraints remained stable. Evaluate the full
thread and state diff, not only the latest text.

### HITL Resume

Possible outcomes are `needs_user_input`, `approved_and_continued`,
`revised_and_continued`, and `rejected`. Completion depends on the expected stop
point. A deliberate interrupt is not a failed task.

## Minimum Viable Scorecard

Keep dimensions visible rather than producing one weighted total.

| Metric key | Level | Feedback | Role |
|---|---|---|---|
| `task_outcome` | End-to-end/thread | Categorical | Primary outcome |
| `tool_selected_correctly` | Component | Boolean | Diagnostic/test |
| `tool_arguments_correct` | Component | Boolean per property | Diagnostic/test |
| `routing_satisfies_intent` | Integration | Boolean/categorical | Diagnostic/test |
| `trajectory_valid` | Integration/end-to-end | Boolean invariants plus category | Diagnostic/test |
| `constraints_preserved` | End-to-end/thread | Boolean per critical constraint | Diagnostic/test |
| `faithfulness` | Component/RAG/end-to-end | Anchored ordinal | Quality metric |
| `answer_relevance` | Component/RAG/end-to-end | Anchored ordinal | Quality metric |
| `personalization` | End-to-end | Anchored ordinal | Quality metric |
| `safety_policy_correct` | Integration/end-to-end | Boolean/categorical | Critical gate |
| `handbook_rendered` | End-to-end | Boolean | Release gate |
| `latency_seconds`, `token_cost` | Every live level | Numeric | Operational monitor |

Add a metric only when it changes a decision or localizes a failure.

## Component Metrics

Derive Layer 1 checks from each tool signature and prompt contract. Examples:

| Agent | Deterministic decisions to score | Evidence-based quality |
|---|---|---|
| Flights | route, dates, passengers, cabin, non-stop when requested | Fare/airline claims match Duffel output; options answer request |
| Hotels | destination, stay dates, occupancy/paxes, filters, rate handling | Price/board/cancellation claims match Hotelbeds output |
| Destination | research query, destination, relevant source/tool choice | Claims grounded in RAG/web/safety/weather evidence |
| Restaurants | place, cuisine, diet, price/location constraints | Recommendations satisfy diet and match place evidence |
| Activities | location, dates/hours, interests, accessibility | Suggested activities are evidence-backed and practical |
| Transportation | endpoints, mode, date/time, route parameters | Route/duration/fare claims match tool output |
| Budget | travelers, duration, currency, component values | Totals are arithmetically consistent and assumptions disclosed |
| Itinerary | required components consumed, dates/day count | Feasible sequencing, constraint satisfaction, no unsupported facts |

For volatile inventory, score whether the agent made the right request and
handled the returned result, not whether a specific flight or hotel happened to
be available on that run.

## Integration and Trajectory Metrics

### Supervisor Routing

Evaluate intent-to-agent coverage with acceptable sets, not keyword matching
alone. Track:

- required workers selected;
- irrelevant workers avoided;
- shallow and follow-up routes bypass full planning when appropriate;
- sequential Budget and Itinerary stages occur only after fan-in;
- unsupported route names never appear.

### Parallel Fan-Out and State Merge

Useful invariants:

- every selected parallel worker terminates exactly once;
- one worker error does not abort unrelated workers;
- each successful worker's component is present after fan-in;
- error components remain explicit rather than disappearing;
- no component overwrites another during reducer merge.

### HITL Gates

Evaluate policy decisions separately from user outcomes:

- safety interrupt occurs for the configured dangerous advisory and not for
  benign cases;
- budget interrupt occurs for the configured overspend condition;
- human review interrupts before render;
- resume values map to the correct continuation, revision, or termination path;
- state and thread identity survive resume.

### Efficiency and Termination

Track repeated identical calls, node revisits, timeout/error categories, total
calls, latency, and token cost by intent. Compare against a justified range, not
the shortest possible path: additional calls may be necessary for multi-city or
high-risk requests.

## End-to-End Travel Quality

Split the current broad concept of "travel quality" into auditable dimensions:

- **Task completion:** Did the user receive the requested deliverable?
- **Constraint satisfaction:** Were destinations, dates, duration, travelers,
  budget, travel style, diet, accessibility, and interests honored?
- **Cross-section consistency:** Do flights, hotels, budget, and day plans agree
  on dates, locations, traveler counts, and costs?
- **Faithfulness:** Are factual claims supported by tools, retrieved sources, or
  explicit user input?
- **Practicality/helpfulness:** Is the plan actionable and appropriately
  detailed, with tradeoffs and unavailable information disclosed?
- **Safety:** Are material advisories preserved, and is dangerous advice absent?
- **Personalization:** Do recommendations reflect supplied preferences without
  inventing preferences?
- **Render integrity:** Does HTML/Markdown/JSON contain the structured data and
  required sections without blank or contradictory content?

Use one judge rubric per subjective dimension. Deterministic constraint and
render checks should stay out of the judge.

## Thread-Level Scenarios

Create multi-turn examples for at least:

- "make it cheaper" after a complete itinerary;
- date or destination correction;
- add a dietary or accessibility constraint;
- remove one activity while preserving the rest;
- answer a question from existing trip data without rerunning every worker;
- safety/budget/human review approval and revision resumes;
- ambiguous follow-up that should request clarification;
- repeated request that should not duplicate state or bookings.

Score final outcome, context retention, contradiction, trajectory, and whether
the system asked for missing information at the right time.

## RAG Mapping

Maintain two datasets or clearly separated splits:

1. **Retrieval:** query plus expected guides, sections, claims, or entities.
2. **Generation:** query plus captured contexts and generated response.

Evaluate context precision/recall before faithfulness/relevance. This preserves
failure localization:

- poor recall: query decomposition, namespace fallback, indexing, or top-k issue;
- poor precision: retrieval/reranking or chunking issue;
- good retrieval plus poor faithfulness: prompt/generator issue;
- grounded but incomplete response: retrieval recall or answer synthesis issue.

Do not use a generated reference answer as the only truth without verifying it
against destination guides or authoritative sources.

## Dataset Layout

Target organization as coverage grows:

```text
edd/
  flights/                 # component dataset + evaluators
  hotels/
  ...
src/evaluation/
  integration_dataset.py  # routing, merge, HITL scenarios
  e2e_dataset.py           # full trip outcomes
  thread_dataset.py        # multi-turn and resume scenarios
  rag_dataset.py           # retrieval/generation cases or loaders
  evaluators.py            # shared evaluator implementations
```

This is a direction, not a mandate to refactor unrelated files. Add the next
case at the level that owns it and split a file when its input/evidence shape no
longer matches the existing dataset.

Use dataset splits and metadata such as:

- `regression`, `edge`, `adversarial`, `production`, `external-failure`;
- agent/intent, destination/region, single/multi-city;
- safety/budget/HITL risk;
- source and human reviewer;
- prompt/model/retriever and dataset versions.

## Current Implementation: Preserve and Improve Deliberately

Existing strengths:

- `edd/` captures component tool calls, outputs, final text, and errors;
- component checks distinguish applicable properties with `score=None`;
- EDD judges separate faithfulness from helpfulness;
- EDD pairwise evaluation swaps positions;
- EDD Layer 4 includes ordinal human calibration;
- shared evaluators already expose structured `key`, `score`, and `comment`;
- RAG evaluation already separates precision, recall, faithfulness, relevance,
  entity recall, and noise sensitivity;
- LangSmith datasets and offline experiment runners already exist.

Priorities when evaluation work next touches each area:

1. Add an explicit end-to-end `task_outcome` instead of treating output presence
   or section count as task success.
2. Preserve the Stage 4 node/tool/interrupt trajectory in the evaluation target;
   flattened final fields cannot diagnose orchestration failures.
3. Replace keyword-only routing heuristics with intent-labeled expected agent
   sets and separate coverage from unnecessary routing.
4. Split the broad `travel_quality` judge into single-dimension rubrics.
5. Bring shared pairwise comparison up to the EDD standard by swapping positions
   and reporting order sensitivity.
6. Keep the calibration implementation and documentation aligned: if Cohen's
   kappa and directional bias are claimed, compute and test them.
7. Add thread-level datasets for follow-up and HITL resume behavior.
8. Feed adjudicated production traces back into level-specific offline datasets.
9. When legacy evaluator code is touched, replace hard-coded LLM clients/models
   with `get_llm(tier=...)` and the repository's Responses API content handling.

Address these incrementally alongside the behavior under change. Do not perform
a broad evaluation rewrite merely to satisfy the map.

## Production Sampling Plan

Use tiered evaluation to control cost:

1. Run deterministic sanity, policy, schema, error, latency, and route checks on
   all eligible traces.
2. Run evidence-based faithfulness and task-outcome judges on a random sample,
   all deterministic failures, and high-risk safety/budget/HITL cases.
3. Run thread judges when a conversation reaches a terminal outcome or becomes
   inactive, not after every token or child run.
4. Route low-confidence, novel, or high-risk cases to human annotation.
5. Monitor by intent and failure category; a global average can hide a broken
   agent or destination slice.

Never label a deterministic-pass trace with a fabricated medium quality score
merely because the expensive judge was not sampled. Record the subjective metric
as not evaluated so aggregates retain honest denominators.
