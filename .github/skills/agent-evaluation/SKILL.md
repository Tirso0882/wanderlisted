---
name: agent-evaluation
description: 'Design, implement, review, and operate evaluation for the Wanderlisted multi-agent travel system. WHEN working on LLM evaluation metrics, EDD, LangSmith evaluators or datasets, golden cases, task completion, tool correctness or argument validation, graph/agent trajectory, multi-turn or thread evaluation, RAG context precision/recall/faithfulness, LLM-as-a-judge rubrics, pairwise experiments, human calibration, offline regression evals, online production monitoring, or turning traces into tests.'
---

# Wanderlisted Agent Evaluation

Use this skill to turn a product requirement or observed failure into a metric,
dataset, evaluator, experiment, and production feedback loop. It distills
[LangChain's LLM evaluation metrics guide](https://www.langchain.com/resources/llm-evaluation-metrics#ai-agent-evaluation-metrics)
and adapts it to Wanderlisted's Stage 4 graph and evaluation-driven development
(EDD) workflow.

## Load the Right Detail

- Read [Metric and rubric reference](./references/metric-catalog.md) when choosing
  an evaluator, feedback type, RAG metric, judge rubric, or bias mitigation.
- Read [Wanderlisted evaluation map](./references/wanderlisted-map.md) when
  defining task completion, graph trajectories, thread metrics, scorecards, or
  deciding where new evaluation code belongs.
- Start a new evaluation design from
  [Evaluation spec template](./assets/evaluation-spec.md).

Local sources of truth:

- Component EDD contract and worked Flights example:
  [edd/README.md](../../../edd/README.md)
- Captured component trajectory shape:
  [edd/harness.py](../../../edd/harness.py)
- Current shared evaluators:
  [src/evaluation/evaluators.py](../../../src/evaluation/evaluators.py)
- Current end-to-end dataset:
  [src/evaluation/golden_dataset.py](../../../src/evaluation/golden_dataset.py)
- Current LangSmith runner:
  [scripts/eval_agents.py](../../../scripts/eval_agents.py)
- Primary graph under test:
  [src/agent/stage4_graph.py](../../../src/agent/stage4_graph.py)

## Core Model

1. **Task completion is the primary outcome.** First ask whether the traveler
   achieved the requested goal. A fluent answer that does not complete the task
   is a failure.
2. **Tool correctness and trajectory are diagnostics.** Use them to explain why
   task completion failed: wrong tool, wrong arguments, bad routing, loops,
   missing fan-in, inappropriate HITL behavior, or premature termination.
3. **Evaluate at the owning boundary.** Use component metrics for one agent,
   integration metrics for routing/state/HITL, end-to-end metrics for the final
   trip outcome, and thread metrics for follow-ups and resumed conversations.
4. **Keep quality dimensions separate.** Faithfulness, helpfulness,
   personalization, safety, and task completion answer different questions.
   Never hide them inside one unexplained "quality" score.
5. **Tests and evaluations have different jobs.** Deterministic must-pass facts
   gate deployment. Subjective metrics compare variants and trend quality; do not
   turn an uncalibrated fuzzy score into an arbitrary release gate.
6. **Offline and online evaluation form one loop.** Curated datasets protect
   changes before release; sampled production traces reveal drift and become
   human-adjudicated regression cases.

## Scope Router

Choose one level before writing a metric:

| Level | Thing under test | Start here |
|---|---|---|
| Component | One specialized agent and its tool decisions | `edd/<agent>/` using `edd/harness.py` |
| Integration | Supervisor routing, `Send()` fan-out, reducer merge, HITL gates | Stage 4 trace/state plus a dedicated integration dataset |
| End-to-end | Full request through approved handbook | `src/evaluation/` and `scripts/eval_agents.py` |
| Thread | Follow-up, correction, approval/resume, context retention | Full LangSmith thread, not one final run |
| RAG | Retriever and context-grounded generation | Separate retrieval and generation datasets/metrics |

Do not score only the final prose when the behavior is owned by an earlier graph
node. Do not judge an isolated worker for context it was never given.

## Workflow

### 1. Name the User Outcome

Write one falsifiable completion statement before selecting metrics:

> Given `<request and available context>`, the system succeeds when
> `<observable traveler outcome>` without `<critical failure>`.

Examples live in the [Wanderlisted map](./references/wanderlisted-map.md). Define
who decides completion: deterministic state, a reference answer, a calibrated
judge, or a human reviewer.

### 2. Observe the Real Execution

Run one representative case and inspect the complete evidence available at the
chosen level:

- input and user/profile context;
- graph nodes, routes, tool names, and tool arguments;
- tool outputs and errors;
- state before/after reducer merges;
- interrupts and resumes;
- final response or handbook;
- latency, token/cost metadata, and termination reason when available.

For an isolated agent, use `edd.harness.run_agent()` and inspect its
`Trajectory`. For the full graph or a conversation, inspect the LangSmith trace
or thread. Observation precedes rubric or assertion design.

### 3. Build an Evaluation Contract

For every metric, record:

| Field | Required decision |
|---|---|
| Question | What single uncertainty does this metric resolve? |
| Scope | Component, integration, end-to-end, thread, or RAG? |
| Evidence | Input, reference, tool output, trajectory, state, or human label? |
| Relation | Reference-based or reference-free? |
| Mechanism | Code, LLM judge, pairwise judge, or human review? |
| Feedback | Boolean, categorical, ordinal, or continuous? |
| Role | Release gate, regression diagnostic, experiment metric, or monitor? |

If the metric cannot be stated as one clear question, split it.

### 4. Define Task Completion First

Prefer observable completion signals over textual resemblance:

- full trip: all required planning stages completed, critical constraints are
  honored, approval is obtained when required, and the handbook renders;
- focused request: the requested capability returns a usable result or an honest
  no-result explanation;
- shallow request: a direct answer returns without launching the full graph;
- follow-up: the requested change is applied without losing prior approved
  context;
- safety/budget interruption: the graph pauses or continues according to the
  policy and the user's resume action.

Use a boolean when success is unambiguous. Use a small categorical outcome such
as `completed`, `partial`, `failed`, `blocked_external`, `needs_user_input` when
partial completion and external failure must remain distinguishable.

### 5. Add Only Diagnostic Metrics That Explain Failure

Decompose failed completion into the smallest useful questions:

- **Tool selection:** Was the appropriate tool called?
- **Argument correctness:** Did user constraints reach the correct fields?
- **Routing:** Did the supervisor choose the required workers and avoid
  irrelevant ones?
- **Trajectory validity:** Did execution reach required nodes, avoid loops, merge
  parallel results, and terminate at the right point?
- **Evidence use:** Is final prose supported by tool or retrieved evidence?
- **Constraint satisfaction:** Were budget, dates, group, diet, accessibility,
  safety, and travel style preserved?

Score the agent's decision separately from volatile live API results. Record
provider availability and tool errors as operational outcomes, not as proof that
an otherwise correct decision was wrong.

### 6. Match the Evaluator to the Criterion

Use the cheapest reliable mechanism:

| Criterion | Preferred evaluator | Feedback/use |
|---|---|---|
| Schema, required node, exact argument, policy invariant | Deterministic code | Boolean gate |
| Known answer or valid set of answers | Reference-based code/semantic evaluator | Boolean or explicit ratio |
| Task completion visible in structured state | Deterministic code | Boolean/categorical gate |
| Task completion requiring semantic interpretation | Calibrated LLM judge | Categorical/ordinal metric |
| Faithfulness to tool/retrieval evidence | Evidence-based LLM judge | Anchored ordinal metric |
| Helpfulness, relevance, personalization, tone | Reference-free LLM judge | Categorical/ordinal trend |
| Prompt/model variant | Pairwise judge in both position orders | Win/tie/loss experiment |
| Quality not yet clearly defined | Human annotation | Labels first; automate later |

Do not use an LLM judge for JSON validity, required keys, regex checks, exact
tool names, or other facts code can decide consistently.

### 7. Design Ground Truth and Datasets

- Keep one dataset per thing under test; use splits for scenario families.
- Write expected values from domain truth, not from the agent's output.
- Accept every valid representation with sets or explicit alternatives.
- Return `score=None` for a genuinely inapplicable property and exclude it from
  the denominator. Never silently count missing labels as success.
- Include normal, edge, adversarial, negative, external-failure, and previously
  fixed production cases.
- Store metadata such as source, intent, destination, risk, model/prompt version,
  and dataset version so results can be sliced and reproduced.

### 8. Implement at the Owning Layer

- Component behavior: extend the relevant `edd/<agent>/` package.
- Shared deterministic or LangSmith evaluators: update
  `src/evaluation/evaluators.py` and focused tests.
- End-to-end or RAG cases: use a level-specific dataset rather than growing one
  mixed file indefinitely.
- Full-system targets: preserve structured state and trajectory evidence; do not
  flatten away the fields the evaluator needs.
- LLM judges: use `get_llm(tier=...)`, structured output, and a stronger suitable
  tier. Never copy hard-coded provider/model construction from legacy evaluator
  code.
- Responses API content: use the repository's text extraction pattern; never
  assume `message.content` is a string.

Every evaluator returns structured feedback:

```python
{"key": "tool_arguments_correct", "score": 1, "comment": "All requested dates and occupancies matched."}
```

Use `value` instead of `score` for a non-numeric category when supported.

### 9. Validate the Evaluator Before Trusting It

1. Unit-test deterministic evaluators with pass, fail, alternate-valid, and
   not-applicable fixtures.
2. Test judge rubrics on fixed labeled examples, especially borderline cases.
3. Compare judge labels with human labels using exact agreement, within-one,
   MAE, directional bias, and quadratic-weighted Cohen's kappa for ordinal data.
4. Run pairwise comparisons twice with answer positions swapped; inconsistent
   verdicts become ties or are flagged as order-sensitive.
5. Prefer boolean, categorical, or anchored ordinal outputs. If continuous judge
   scores are necessary, calibrate anchors and use repeated runs or confidence
   intervals when the decision is consequential.

Known judge risks are position bias, verbosity bias, self-preference, and
run-to-run inconsistency. A judge is another component under test.

### 10. Run the Improvement Loop

1. Establish a baseline on a pinned dataset version.
2. Change one prompt, model, retrieval setting, or graph behavior.
3. Re-run the same cases and inspect per-metric deltas and comments.
4. Decide whether each failure is an agent bug, evaluator bug, data problem, or
   external dependency failure.
5. Lock confirmed failures into the appropriate dataset and deterministic test.
6. After deployment, sample production runs/threads with reference-free and
   evidence-based evaluators.
7. Send notable traces to human review; promote adjudicated inputs and labels to
   offline regression datasets.

## Validation Commands

Choose the narrowest command for the touched layer:

```bash
# Deterministic shared evaluator tests
.venv/bin/pytest tests/test_evaluators.py -q

# Component fixture and live loops (Flights example)
.venv/bin/python edd/flights/l1_evaluate.py
.venv/bin/python edd/flights/l1_run.py

# Tracked LangSmith experiments (requires configured services/API keys)
.venv/bin/python scripts/eval_agents.py --run --mode agent
.venv/bin/python scripts/eval_agents.py --run --mode rag
```

Report skipped live checks explicitly. Never weaken TLS verification or leak
credentials to make an evaluation run.

## Hard Rules

- Do not use BLEU/ROUGE or exact prose matching as the main quality metric for
  open-ended itineraries.
- Do not optimize proxy metrics while ignoring task completion.
- Do not combine retrieval, grounding, usefulness, safety, and outcome into one
  opaque score.
- Do not gate deployment on an arbitrary uncalibrated subjective threshold.
- Do not use the model under test as the source of ground truth.
- Do not compare pairwise answers in only one order.
- Do not claim an evaluator is human-aligned without labeled calibration data.
- Do not evaluate a single response when the failure can only be seen across a
  graph trajectory or multi-turn thread.
