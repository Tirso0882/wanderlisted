# Metric selection reference

| Question | Evidence | Preferred mechanism | Typical feedback |
|---|---|---|---|
| Did the requested task complete? | Typed state/artifact | Deterministic when possible | Boolean or categorical |
| Was the correct tool/node selected? | Trajectory | Deterministic | Boolean |
| Were arguments and constraints preserved? | Input plus tool call/state | Deterministic | Boolean plus comment |
| Is a claim supported by supplied evidence? | Evidence plus output | Deterministic citations, then calibrated judge | Anchored ordinal |
| Is the result useful/relevant? | Request plus result | Calibrated reference-free judge or human | Anchored ordinal |
| Is one variant better? | Same case, two outputs | Pairwise judge in both orders | Win/tie/loss |
| Does a judge match humans? | Balanced labels | Agreement, MAE, bias, weighted kappa | Calibration report |
| Did retrieval find the needed source? | Query, corpus, reference IDs | Recall/precision at k | Ratio |

Use `None` for genuinely inapplicable metrics and remove them from the denominator. Never turn missing labels into success.

Deterministic release gates belong on typed invariants, critical policy, safety, routing, stale detection, and artifact validity. Subjective dimensions become gates only after their rubric, dataset, and human calibration justify a threshold.

Judge risks include position bias, verbosity bias, self-preference, leakage from references, and run-to-run variance. Keep comments and per-case results; averages alone conceal critical failures.
