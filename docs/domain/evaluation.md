---
id: domain-evaluation
doc_type: domain
status: active
authority: normative
owners: [travel-platform]
applies_to: [edd/**, src/evaluation/**, tests/test_edd_*.py]
load_when: [evaluation, edd, judge, dataset, baseline]
source_paths: [edd, src/evaluation, tests/test_edd_runtime.py]
---

# Evaluation context

## Purpose

Provide reproducible evidence about runtime outcomes without becoming a source of runtime truth.

## Invariants

Task completion is primary; routing/tool/trajectory metrics diagnose causes. Deterministic invariants gate releases. Semantic judges use anchored rubrics and human calibration. Pairwise variants run in both orders. Dataset truth comes from domain owners/humans, never the model under test.

Cached trajectories require matching fingerprints. Live capture, judges, and experiment uploads are approval/cost gated. External/infra failure is separated from model quality. Reports retain dataset version, denominators, exclusions, model/provider config, and uncertainty.

## Validation

Every evaluator has pass, fail, alternate-valid, and not-applicable tests where relevant. EDD package/baseline registration is checked hermetically.
