# Evaluation Spec: <Behavior or Change>

## Decision

- **Owner:** <name/team>
- **Date:** <YYYY-MM-DD>
- **Thing under test:** <component, integration, end-to-end, thread, or RAG>
- **Change being evaluated:** <one prompt/model/tool/retrieval/graph change>
- **Decision this evaluation supports:** <release, choose variant, diagnose, monitor>

## Completion Contract

> Given `<request and available context>`, the system succeeds when
> `<observable user outcome>` without `<critical failure>`.

- **Completion labels:** <completed / partial / failed / blocked_external / needs_user_input>
- **Who decides:** <code / reference / calibrated judge / human>
- **Critical must-pass invariants:** <list>

## Failure Hypothesis

- **Suspected failure:** <falsifiable behavior>
- **Owning boundary:** <agent, graph node, reducer, HITL gate, renderer, thread>
- **Evidence that would disconfirm it:** <specific trace/state/output observation>

## Dataset

- **Dataset and pinned version:** <name/version>
- **Input/evidence shape:** <fields>
- **Ground-truth source:** <domain expert, API contract, authoritative document>
- **Splits:** <regression, edge, adversarial, production, external-failure>
- **Metadata:** <intent, agent, destination, risk, model/prompt version>
- **Valid alternatives and N/A rules:** <sets, categories, score=None behavior>

## Metric Cards

Create one row per single-dimension question.

| Key | Question | Scope | Evidence | Relation | Mechanism | Feedback | Role |
|---|---|---|---|---|---|---|---|
| `task_outcome` | Did the user achieve the requested goal? | End-to-end | Full trace/state/output | Reference-free | Code/judge | Categorical | Primary outcome |
| `<key>` | <one question> | <level> | <evidence> | <reference-based/free> | <code/judge/human> | <boolean/category/ordinal/continuous> | <gate/metric/monitor> |

For each metric, define:

- **Pass/category/score anchors:** <observable definitions>
- **Not-applicable or missing-evidence behavior:** <explicit behavior>
- **Structured comment requirement:** <evidence the evaluator must cite>
- **Known confounders:** <external API, unavailable context, multiple valid paths>

## Judge Rubric

Complete only for LLM judges.

- **Single dimension:** <name>
- **Allowed evidence:** <request, tool results, retrieved context, state, reference>
- **Forbidden assumptions:** <context the judge must not infer>
- **Output schema:** <reasoning then constrained score/value>
- **Anchors:**
  - `0` / `<category>`: <observable behavior>
  - `1` / `<category>`: <observable behavior>
  - `2` / `<category>`: <observable behavior>
  - `3` / `<category>`: <observable behavior>
- **Borderline examples:** <labeled examples>

## Evaluator Validation

- [ ] Deterministic pass fixture
- [ ] Deterministic fail fixture
- [ ] Alternate-valid fixture
- [ ] Not-applicable fixture
- [ ] Human-labeled judge calibration set
- [ ] Exact, within-one, MAE, bias, and weighted kappa reviewed
- [ ] Pairwise positions swapped when comparing variants
- [ ] Held-out scenario slice reviewed

## Experiment

- **Baseline:** <version and configuration>
- **Candidate:** <version and the one changed variable>
- **Constants:** <dataset, tools, provider conditions, judge, seeds where applicable>
- **Primary outcome metric:** <key>
- **Diagnostic metrics:** <keys>
- **Deterministic release gates:** <keys>
- **Subjective comparison method:** <delta, pairwise win/tie/loss, confidence>

## Result and Adjudication

| Case/slice | Result | Cause | Action |
|---|---|---|---|
| <case> | <metric/comment> | <agent/evaluator/data/external> | <fix/label/monitor> |

- **Decision:** <ship / revise / reject / gather labels>
- **Confirmed failures added to regression data:** <cases>
- **Evaluator changes made:** <rubric/ground truth changes and rationale>

## Production Loop

- **Deterministic checks and coverage:** <all/sample>
- **Judge sampling rule:** <random %, failures, high-risk slices>
- **Thread terminal condition:** <when thread evaluation runs>
- **Human annotation trigger:** <low confidence, novelty, safety, disagreement>
- **Dashboard slices:** <intent, agent, destination, risk, version>
- **Promotion process:** <trace -> human label -> dataset split -> offline regression>
