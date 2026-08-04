---
id: testing-ai-evaluation
doc_type: testing
status: active
authority: normative
owners: [travel-platform]
applies_to: [edd/**, src/evaluation/**, scripts/eval_agents.py]
load_when: [ai-evaluation, edd, judge, trajectory, langsmith]
source_paths: [edd, src/evaluation, scripts/eval_agents.py]
---

# AI evaluation

## Evaluation stack

1. Layer 1: deterministic task/policy/trajectory checks.
2. Layer 2: pointwise groundedness/helpfulness judge over pinned evidence.
3. Layer 3: pairwise experiment with position swap.
4. Layer 4: judge calibration against human labels.

Task completion is primary. Tool choice/arguments, routing, trajectory, evidence use, safety, and helpfulness remain separate metrics. Evaluate the owning boundary; do not judge only final prose for an earlier state/route defect.

## Dataset and evaluator rules

Version cases and truth source. Include normal, edge, adversarial, negative, external-failure, and fixed production regressions. Use `None` for inapplicable metrics. Deterministic evaluators have pass/fail/alternate-valid/not-applicable tests. Semantic judges use structured anchored output and report agreement/bias before thresholds.

## Cost and live-call controls

Inspect each runner before execution: some cache misses can capture live data even without a refresh flag. Before any live capture, model judge, pairwise run, or LangSmith mutation, disclose case count, expected provider/model calls, token/credit estimate, maximum budget, cache policy, and obtain explicit approval. Never set `EDD_REFRESH=1` silently.

## Reporting

Record dataset/fingerprint, configuration, cache/live status, per-metric results, denominators, exclusions, external failures, uncertainty, and cost. Do not generalize beyond the evaluated cases.
