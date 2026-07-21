# Metric and Rubric Reference

This is a distilled, project-oriented reference derived from LangChain's
[LLM Evaluation Metrics: Measuring What Matters for Your Users](https://www.langchain.com/resources/llm-evaluation-metrics#ai-agent-evaluation-metrics)
(published April 8, 2026; reviewed July 16, 2026). It summarizes concepts and
adapts them for implementation; it is not a copy of the article.

## Evaluation Has Several Independent Axes

Avoid calling every technique a "metric." Specify each axis explicitly.

| Axis | Choices | Meaning |
|---|---|---|
| Evidence relation | Reference-based / reference-free | Whether a known expected output is required |
| Evaluation mechanism | Code / LLM judge / pairwise judge / human | Who or what applies the criterion |
| Feedback shape | Boolean / categorical / ordinal / continuous | How the result is represented |
| Operating mode | Offline / online | Curated pre-release cases or sampled production behavior |
| Observation scope | Run / trajectory / thread | One output, multi-step execution, or full conversation |
| Product role | Test / metric / monitor | Gate correctness, compare quality, or detect production drift |

Examples:

- `correct_departure_date`: reference-based, code, boolean, offline,
  trajectory, test.
- `response_helpfulness`: reference-free, LLM judge, ordinal, offline/online,
  run or thread, metric.
- `task_outcome`: reference-free, calibrated judge, categorical, online,
  thread, monitor.

## Agent Metric Hierarchy

### 1. Task Completion: Outcome

Task completion asks whether the user's actual goal was achieved. It is the
primary metric because polished language and valid tool calls are only useful if
they produce the requested outcome.

Possible forms:

- Boolean: completed or not completed.
- Categorical: `completed`, `partial`, `failed`, `blocked_external`,
  `needs_user_input`.
- Rate over eligible cases:

$$
\text{Task Completion Rate} =
\frac{\text{completed eligible tasks}}{\text{all eligible tasks}}
$$

Define completion per intent. Never use response length, section count, or tool
call presence alone as a substitute for the outcome.

### 2. Tool Correctness: Capability Diagnostic

Tool correctness should be decomposed rather than scored as one vague property:

- selection: the right capability was chosen;
- argument extraction: dates, places, people, constraints, and filters match the
  request;
- call policy: required preconditions and ordering were respected;
- result handling: errors, empty results, and recheck requirements were handled
  honestly;
- evidence use: the response did not invent facts absent from the result.

Useful deterministic ratios:

$$
\text{Tool Selection Accuracy} =
\frac{\text{cases with an acceptable selected tool}}{\text{eligible cases}}
$$

$$
\text{Argument Accuracy} =
\frac{\text{correct applicable argument fields}}{\text{all applicable argument fields}}
$$

Keep decision quality separate from provider reliability. A correctly selected
API that times out is an operational failure, not necessarily an agent-decision
failure.

### 3. Trajectory Assessment: Process Diagnostic

Trajectory evaluation asks whether the agent took a reasonable path:

- required nodes or agents were reached;
- irrelevant agents or tools were avoided;
- branches and handoffs matched the intent;
- loops and repeated calls were absent or justified;
- parallel outputs survived fan-in and state merge;
- HITL interrupts occurred only under their policy conditions;
- the process terminated, degraded gracefully, or requested missing input;
- latency, calls, tokens, and cost were proportionate to task complexity.

There is rarely one universal "correct" trajectory. Represent acceptable paths
as invariants, partial orders, required/forbidden events, or a calibrated rubric.
Do not require exact trace identity when multiple paths are valid.

## Multi-Turn and Thread Evaluation

Single-turn checks miss failures that emerge over a conversation. Evaluate the
whole thread for:

- final task completion and user outcome;
- context retention across follow-ups;
- correct incorporation of corrections and preferences;
- contradiction or repeated-question rate;
- progress versus circular behavior;
- interrupt/resume correctness;
- trajectory appropriateness across all turns.

The evaluator needs the ordered conversation plus relevant child runs and state,
not only the final assistant message.

## RAG Metric Stack

Evaluate retrieval and generation separately because either can fail while the
other succeeds.

### Retrieval

**Context precision** measures how much retrieved material is relevant:

$$
\text{Context Precision} =
\frac{\text{relevant retrieved context}}{\text{all retrieved context}}
$$

Low precision means noisy context and wasted context-window capacity.

**Context recall** measures how much necessary evidence was retrieved:

$$
\text{Context Recall} =
\frac{\text{retrieved required evidence}}{\text{all required evidence}}
$$

Low recall means the generator never received enough information for a complete
answer. Reference answers, expected documents, claim sets, or entity sets can
define required evidence.

Local extensions already implemented in Wanderlisted:

- context entity recall: whether expected places, organizations, prices, and
  dates appeared in context;
- noise sensitivity: whether irrelevant retrieved material misled generation.

### Generation

**Faithfulness** measures whether response claims are supported by supplied
evidence:

$$
\text{Faithfulness} =
\frac{\text{supported factual claims}}{\text{all factual claims}}
$$

The evidence may be retrieved documents or tool outputs. Restated user-provided
facts should be treated as available evidence when the rubric says so.

**Answer relevance/helpfulness** measures whether the response addresses the
question and provides a usable answer. A response can be faithful but irrelevant,
or helpful-sounding but fabricated. Keep these metrics separate.

### Diagnostic Combinations

| Pattern | Likely failure |
|---|---|
| High precision, low recall | Retriever is selective but misses required evidence |
| High precision, low faithfulness | Generator invents claims despite good context |
| High faithfulness, low recall | Grounded but incomplete because retrieval missed evidence |
| High recall, low precision | Required evidence is present but buried in noise |
| High faithfulness, low relevance | Grounded answer does not solve the user's request |

## Choosing an Evaluator

### Reference-Based

Use when curated ground truth exists. Best for offline correctness, semantic
similarity on constrained answers, known entities, expected routes, and required
facts. Ground truth should describe valid outcomes, not one exact phrasing.

### Reference-Free

Use when no expected answer exists, especially in production. Criteria include
tone, conciseness, evidence-groundedness, and thread outcome. The criterion and
evidence still need to be explicit even when no gold answer exists.

### Code/Functional

Use deterministic logic for facts with objective answers:

- schema or JSON validity;
- required keys/sections;
- regex or format constraints;
- exact/acceptable tool names;
- argument values and policy invariants;
- graph node reachability and loop limits;
- token, latency, and cost limits when measured reliably.

Code is faster, cheaper, and more consistent than an LLM judge for these facts.

### LLM-as-a-Judge

Use for semantic or subjective criteria that need reasoning: helpfulness,
faithfulness, domain accuracy, personalization, task completion without a
structured signal, and holistic thread assessment.

Use a custom judge only when:

- the quality dimension is domain-specific;
- examples or a written rubric already define good behavior;
- evaluation volume makes human-only review impractical;
- deterministic or prebuilt evaluators cannot decide the criterion.

If the team cannot explain the difference between adjacent scores, collect human
labels before automating.

### Pairwise

Use to compare prompt, model, retrieval, or graph variants when relative quality
is easier to judge than an absolute score. Hold inputs and the scored dimension
constant. Judge both `(A, B)` and `(B, A)`; count an answer as the winner only if
both orders agree. Report win/tie/loss and order-sensitive rate.

### Human Review

Use humans to define new criteria, adjudicate ambiguous cases, label critical
domain examples, and calibrate automated judges. Humans are not merely a fallback;
their labels establish whether the evaluator measures the intended construct.

## Feedback Types

### Boolean

Best for hard facts and gates: required format, PII detected, correct tool,
policy violated, task completed. It is consistent but cannot express partial
success.

### Categorical

Best when named outcomes matter more than magnitude: completion state, tone class,
failure cause, routing class. Categories preserve operational meaning and are
usually more stable than free-form scores.

### Ordinal

A constrained ordered scale such as 0-3 is often better than arbitrary decimals.
Every level needs a behavioral anchor. Treat it as ordinal data during
calibration; weighted agreement is appropriate.

### Continuous

Useful for ratios computed from countable items and for coarse trend comparison.
Judge-generated decimals imply more precision than may exist. Use them only with
clear anchors, calibration, repeated sampling, and uncertainty reporting when the
decision matters.

## Structured Feedback Contract

Return a stable metric key, score or categorical value, and an actionable reason:

```json
{
  "key": "faithfulness",
  "score": 2,
  "comment": "One quoted hotel price was absent from the Hotelbeds result."
}
```

The comment should identify evidence and failure, not restate the number. Stable
keys enable aggregation; comments make low scores debuggable.

## Rubric Construction

Build one rubric per dimension:

1. Name the single question being scored.
2. State all evidence the judge may use: request, profile, tool outputs,
   retrieved context, state, or reference answer.
3. Define exclusions, such as context unavailable to an isolated agent.
4. Anchor every allowed score with observable behavior.
5. Define `not_applicable` or missing-evidence behavior.
6. Require a concise evidence-citing reason before the score.
7. Add a few representative and borderline labeled examples.
8. Force structured output.

Avoid criteria such as "overall quality" that blend correctness, style, safety,
and completeness. A low blended score does not identify what to fix.

## Judge Failure Modes and Mitigations

| Risk | Mitigation |
|---|---|
| Position bias | Swap answer order in pairwise evaluation and aggregate only consistent verdicts |
| Verbosity bias | State that extra length is neutral or harmful unless it adds requested value |
| Run-to-run inconsistency | Prefer constrained labels; repeat consequential evaluations and report variance |
| Self-preference | Prefer a capable, distinct judge; calibrate against humans |
| Leniency/harshness | Measure directional bias against human labels and adjust rubric anchors |
| Prompt overfitting | Calibrate on held-out labeled examples and multiple scenario families |

Recommended calibration for an ordinal judge:

- exact match;
- agreement within one category;
- mean absolute error;
- mean signed error (judge minus human) for directional bias;
- quadratic-weighted Cohen's kappa for chance-corrected ordinal agreement.

Automated judge scores are evidence, not absolute truth.

## Testing Versus Evaluation

**Tests** answer "is it safe to ship?" They enforce deterministic requirements
and fixed regressions with pass/fail behavior.

**Evaluations** answer "which version is better, where does it fail, and is it
improving?" They measure fuzzy or relative quality and should be read by metric,
slice, confidence, and trend.

Do not impose an arbitrary threshold such as `faithfulness >= 0.7` merely to make
a subjective metric look like a test. A calibrated metric may support a release
policy, but the policy needs domain evidence, labeled validation, and a documented
risk tolerance.

## Offline and Online Loop

### Offline

Use curated, versioned datasets before release to reproduce known risks, compare
variants, and protect fixed failures. Sources include expert-created examples,
adjudicated production traces, and synthetic edge cases reviewed for validity.

### Online

Evaluate a sampled subset of production runs and completed threads. Prefer cheap
code checks on broad traffic and costlier judges on targeted or random samples.
Monitor task outcome, evidence use, failure categories, latency/cost, and drift by
intent or user segment.

### Data Flywheel

1. Production traces reveal a failure or new usage pattern.
2. A human reviews the trace and labels the desired behavior.
3. The case enters the correct level-specific dataset and split.
4. Offline evaluation reproduces the failure.
5. One change is made and compared against the baseline.
6. Deployment occurs after deterministic gates pass.
7. Online evaluation verifies the result and finds the next case.

This loop keeps offline data representative and ensures production failures become
durable regression protection.

## Traditional NLP Metrics

BLEU and ROUGE measure n-gram overlap; BERTScore measures embedding-level
similarity; perplexity estimates model surprise/fluency. They remain useful for
tasks where lexical or semantic similarity is the intended construct, but they
do not establish task completion, tool correctness, trajectory quality,
helpfulness, safety, or domain accuracy for an open-ended travel agent. Use them
only as narrow supporting signals when the task justifies them.
