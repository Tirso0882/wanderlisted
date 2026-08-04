---
name: agent-evaluation
description: Design, implement, review, or run Wanderlisted agent evaluations when a task mentions EDD, datasets, deterministic evaluators, trajectories, LLM judges, pairwise comparison, calibration, task completion, grounding, regression gates, LangSmith experiments, or production feedback.
---

# Agent evaluation

## Inputs

Collect the capability under test, user outcome, owning layer, changed behavior, available evidence, dataset/case budget, and whether live calls are authorized. Read `../../../docs/testing/AI_EVALUATION.md` and the relevant feature `EVALUATION.md` first.

Use these references only as needed:

- [Metric selection](references/metric-catalog.md)
- [Repository evaluation map](references/repository-map.md)
- [Evaluation specification template](references/evaluation-spec.md)

## Workflow

1. State one falsifiable completion condition: given the request and available context, define the observable success and critical failure.
2. Select the owning boundary: component, graph integration, end-to-end artifact, multi-turn thread, or retrieval/generation.
3. Inspect the real typed output and trajectory at that boundary. Do not evaluate final prose for behavior owned by routing, tools, reducers, or gates.
4. Define each metric as one question with evidence, mechanism, feedback type, and role. Keep task completion, policy, grounding, helpfulness, safety, and operations separate.
5. Choose the cheapest reliable evaluator: deterministic code for schemas/invariants; reference comparison for known truth; a calibrated judge for semantic criteria; human labels when quality is not yet operationalized.
6. Build versioned cases from domain truth. Include normal, edge, adversarial, negative, stale, external-failure, and fixed-regression examples. Never use the model under test as ground truth.
7. Implement at the owner: `edd/<component>/` for component EDD, focused tests for deterministic contracts, and `src/evaluation/` for shared/end-to-end evaluation.
8. Validate evaluators before trusting scores. Test pass/fail/not-applicable cases; calibrate judges against labeled data; run pairwise variants in both orders.
9. Establish a pinned baseline, change one factor, compare per-metric results, classify failures, and promote confirmed failures into deterministic regressions.
10. Report dataset version, denominators, exclusions, cache/live status, model/provider configuration, uncertainty, and cost.

Treat `blocked_external` and infrastructure errors as operational outcomes, not model-quality failures. A cache hit is usable only when the runner fingerprint matches.

## Stop conditions

Stop and ask before any cache-miss capture, provider request, paid model/judge, `EDD_REFRESH=1`, LangSmith mutation, or experiment upload unless the user explicitly approved a disclosed call/case/cost budget. Stop if the owner, success criterion, or ground truth cannot be identified.

## Output

Return the evaluation contract, changed datasets/evaluators/tests, exact hermetic results, excluded cases, skipped live checks, and a release recommendation tied to named gates.

## Validation

Run the narrowest offline checks first, for example:

```bash
.venv/bin/pytest tests/test_edd_<component>.py -q
.venv/bin/pytest tests/test_evaluators.py -q
.venv/bin/ruff check edd/<component> tests/test_edd_<component>.py
```

Inspect every runner before executing it; names such as `l1_run.py` do not guarantee an offline path.
