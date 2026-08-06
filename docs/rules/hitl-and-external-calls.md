---
id: rules-hitl-external-calls
doc_type: rules
status: active
authority: normative
owners: [travel-platform]
applies_to: [src/agent/stage4_graph.py, src/api/main.py, edd/**, infra/**]
load_when: [hitl, approval, external-call, live, deployment, cost]
source_paths: [src/agent/stage4_graph.py, src/api/main.py, edd, .github/workflows]
---

# HITL and external-call rules

## BR-HITL-002 — Budget decisions are typed

- **Rule:** Budget review accepts the discriminated proceed/cancel/adjust-target contract; supported legacy decisions remain bounded at the API edge.
- **Reason:** Free text cannot safely change monetary targets.
- **Failure:** Validation error or end flow.
- **Evidence:** `BudgetReviewDecision` and resumed state.

## BR-HITL-003 — Final plan approval controls delivery

- **Rule:** Only approved current itinerary proceeds to handbook; edit returns to draft selection and rejection ends.
- **Reason:** Delivery must reflect human review.
- **Failure:** No handbook is rendered.
- **Evidence:** Typed human-review decision and route.

## BR-HITL-004 — Live/paid calls require approval and disclosure

- **Rule:** Before provider, model judge, live EDD, Azure/GitHub mutation, or deployment, disclose target, expected calls/cases, cost/quota ceiling, and obtain explicit approval.
- **Reason:** Prevent silent spend and external state changes.
- **Failure:** Remain offline and report the skipped check.
- **Evidence:** User authorization and execution record.

## BR-HITL-005 — External failure is not quality failure

- **Rule:** Authentication, quota, TLS/network, timeout, and provider/infrastructure failure are classified separately and excluded from model-quality denominators.
- **Reason:** Reliability and model quality require different remediation.
- **Failure:** `blocked_external`/infra result, not a fabricated score.
- **Evidence:** Error category and evaluation exclusion.
